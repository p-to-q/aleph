from __future__ import annotations

import copy
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import os
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from bench.engine.audit import audit_m0_acceptance, format_audit_report
from bench.engine.adapters.base import ModelAdapter
from bench.engine.adapters.hosted_black_box import HostedBlackBoxAdapter, HostedBlackBoxError
from bench.engine.bundle import build_m0_bundle, compare_bundle
from bench.engine.frozen_ladder import evaluate_item, run_benchmark
from bench.engine.leakage_gate import evaluate_leakage
from bench.engine.manifest import build_manifest
from bench.engine.platform_package import (
    check_platform_package,
    write_platform_package,
)
from bench.engine.metrics import aurc, exact_fidelity, monotone_lower_envelope, rank_by_metric
from bench.engine.preflight import preflight
from bench.engine.report import model_summary_table, per_item_table, render_report_file
from bench.engine.schema_validation import SchemaValidationError, load_schema, validate
from bench.engine.verify import verify_artifacts


ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "bench/data/public/s2"


class FakeChatHandler(BaseHTTPRequestHandler):
    request_payload: dict[str, object] = {}
    request_payloads: list[dict[str, object]] = []
    request_headers: dict[str, str] = {}
    request_headers_list: list[dict[str, str]] = []
    response_status = 200
    response_body: dict[str, object] = {"choices": [{"message": {"content": "synthetic hosted output"}}]}
    response_sequence: list[tuple[int, dict[str, object]]] = []

    def do_POST(self) -> None:
        length = int(self.headers["Content-Length"])
        raw = self.rfile.read(length).decode("utf-8")
        type(self).request_payload = json.loads(raw)
        type(self).request_headers = {
            "path": self.path,
            "authorization": self.headers.get("Authorization", ""),
            "content_type": self.headers.get("Content-Type", ""),
        }
        type(self).request_payloads.append(type(self).request_payload)
        type(self).request_headers_list.append(type(self).request_headers)
        if type(self).response_sequence:
            status, response_body = type(self).response_sequence.pop(0)
        else:
            status, response_body = type(self).response_status, type(self).response_body
        body = json.dumps(response_body).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:
        return


class FakeChatServer:
    def __init__(
        self,
        *,
        status: int = 200,
        body: dict[str, object] | None = None,
        sequence: list[tuple[int, dict[str, object]]] | None = None,
    ):
        FakeChatHandler.request_payload = {}
        FakeChatHandler.request_payloads = []
        FakeChatHandler.request_headers = {}
        FakeChatHandler.request_headers_list = []
        FakeChatHandler.response_status = status
        FakeChatHandler.response_body = body or {
            "choices": [{"message": {"content": "synthetic hosted output"}}]
        }
        FakeChatHandler.response_sequence = list(sequence or [])
        self.server = HTTPServer(("127.0.0.1", 0), FakeChatHandler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    def __enter__(self) -> "FakeChatServer":
        self.thread.start()
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)

    @property
    def base_url(self) -> str:
        host, port = self.server.server_address
        return f"http://{host}:{port}"

    @property
    def payload(self) -> dict[str, object]:
        return FakeChatHandler.request_payload

    @property
    def headers(self) -> dict[str, str]:
        return FakeChatHandler.request_headers

    @property
    def request_count(self) -> int:
        return len(FakeChatHandler.request_payloads)

    @property
    def payloads(self) -> list[dict[str, object]]:
        return FakeChatHandler.request_payloads

    @property
    def headers_list(self) -> list[dict[str, str]]:
        return FakeChatHandler.request_headers_list


class VariableAdapter(ModelAdapter):
    def __init__(self) -> None:
        super().__init__(model_id="variable-adapter", observation_mode="mock", temperature=0.7)

    def generate(
        self,
        prompt: str,
        item: dict[str, object],
        ladder_prompt: dict[str, object],
        *,
        seed: int,
        rerun_index: int,
    ) -> str:
        del prompt, ladder_prompt, seed
        target = item["target"]["text"]
        if rerun_index == 0:
            return target
        if rerun_index == 1:
            return target[: len(target) // 2]
        return "unrelated output"


class M0BenchTests(unittest.TestCase):
    def test_exact_match(self) -> None:
        target = "row 1: n=7; checksum: A-001"
        self.assertEqual(exact_fidelity(target, target), 1.0)
        self.assertGreater(exact_fidelity(target, "row 1: n=7"), 0.3)
        self.assertLess(exact_fidelity(target, "unrelated output"), 0.4)

    def test_leakage_gate(self) -> None:
        target = "S2 sample\nrow 1: n=7; n+step=10; glyph=amber\nchecksum: A-001"
        quoted = f"Reproduce this text exactly:\n\n{target}"
        concept = "Create an arithmetic card from start 7, step 3, amber glyph, checksum A-001."
        self.assertTrue(evaluate_leakage(quoted, target).disqualified)
        self.assertFalse(evaluate_leakage(concept, target).disqualified)

    def test_aurc_monotone(self) -> None:
        points = [
            {"id": "a", "tokens": 4, "distortion": 0.6, "fidelity": 0.4, "disqualified": False},
            {"id": "b", "tokens": 6, "distortion": 0.7, "fidelity": 0.3, "disqualified": False},
            {"id": "c", "tokens": 8, "distortion": 0.2, "fidelity": 0.8, "disqualified": False},
        ]
        frontier = monotone_lower_envelope(points)
        self.assertEqual([point["id"] for point in frontier], ["a", "c"])
        self.assertEqual(aurc(frontier, 10), 0.52)

    def test_schema(self) -> None:
        result = run_benchmark(
            data_dir=DATA_DIR,
            models=["mock-frontier", "mock-mid", "mock-small"],
            seed=0,
            limit=3,
            bootstrap_samples=25,
        )
        schema = load_schema(ROOT / "schemas/aleph-bench-result.schema.json")
        validate(result, schema)
        self.assertEqual(result["config"]["datasetPath"], "bench/data/public/s2")

    def test_iia(self) -> None:
        result = run_benchmark(
            data_dir=DATA_DIR,
            models=["mock-frontier", "mock-mid", "mock-small"],
            seed=0,
            limit=5,
            bootstrap_samples=25,
        )
        full_order = rank_by_metric(result["models"], "aurc")
        reduced = [row for row in result["models"] if row["model"] != "mock-small"]
        reduced_order = rank_by_metric(reduced, "aurc")
        self.assertEqual([model for model in full_order if model != "mock-small"], reduced_order)

    def test_rank_stable_across_two_seeds(self) -> None:
        first = run_benchmark(
            data_dir=DATA_DIR,
            models=["mock-frontier", "mock-mid", "mock-small"],
            seed=0,
            bootstrap_samples=100,
        )
        second = run_benchmark(
            data_dir=DATA_DIR,
            models=["mock-frontier", "mock-mid", "mock-small"],
            seed=1,
            bootstrap_samples=100,
        )
        expected_order = ["mock-frontier", "mock-mid", "mock-small"]
        self.assertEqual(rank_by_metric(first["models"], "aurc"), expected_order)
        self.assertEqual(rank_by_metric(second["models"], "aurc"), expected_order)

        for result in (first, second):
            ordered = sorted(result["models"], key=lambda row: (row["aurc"], row["model"]))
            for left, right in zip(ordered, ordered[1:]):
                self.assertLess(left["aurcCi95"]["high"], right["aurcCi95"]["low"])

    def test_reproducible(self) -> None:
        first = run_benchmark(
            data_dir=DATA_DIR,
            models=["mock-frontier", "mock-mid"],
            seed=17,
            limit=4,
            bootstrap_samples=25,
        )
        second = run_benchmark(
            data_dir=DATA_DIR,
            models=["mock-frontier", "mock-mid"],
            seed=17,
            limit=4,
            bootstrap_samples=25,
        )
        self.assertEqual(first, second)

    def test_measurements_record_rerun_variance(self) -> None:
        item = json.loads((DATA_DIR / "s2-001.json").read_text(encoding="utf-8"))
        run = evaluate_item(item, VariableAdapter(), seed=0, reruns=3)
        non_leaking = [row for row in run["measurements"] if not row["disqualified"]]
        gated = [row for row in run["measurements"] if row["disqualified"]]
        self.assertEqual(len(run["measurements"]), 8)
        self.assertEqual(gated[0]["rerunCount"], 0)
        self.assertIsNone(gated[0]["fidelityVariance"])
        self.assertEqual(non_leaking[0]["rerunCount"], 3)
        self.assertGreater(non_leaking[0]["fidelityVariance"], 0)
        self.assertGreater(non_leaking[0]["fidelityStdDev"], 0)
        self.assertTrue(all(point["rerunCount"] == 3 for point in run["frontier"]))

    def test_preflight_estimates_mock_run(self) -> None:
        report = preflight(data_dir=DATA_DIR, models=["mock-frontier", "mock-mid", "mock-small"])
        self.assertEqual(report["status"], "ready")
        self.assertEqual(report["itemCount"], 30)
        self.assertEqual(report["promptCount"], 240)
        self.assertEqual(report["disqualifiedPromptCount"], 60)
        self.assertEqual(report["nonLeakingPromptCount"], 180)
        self.assertEqual(report["estimatedGenerations"], 540)
        self.assertEqual(report["leakageByRung"], {"0": 60, "1": 0, "2": 0, "3": 0})

    def test_preflight_blocks_hosted_without_env(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            report = preflight(data_dir=DATA_DIR, models=["hosted:frontier-model"])
        self.assertEqual(report["status"], "blocked")
        self.assertEqual(report["models"][0]["evidenceMode"], "black_box")
        self.assertEqual(report["models"][0]["missingEnv"], ["ALEPH_CUSTOM_API_BASE_URL", "ALEPH_CUSTOM_API_KEY"])

    def test_hosted_adapter_posts_openai_compatible_payload(self) -> None:
        with FakeChatServer() as server:
            adapter = HostedBlackBoxAdapter(
                "bench-model",
                base_url=server.base_url,
                api_key="test-key",
                temperature=0.25,
                max_tokens=123,
                timeout_seconds=3,
                max_retries=0,
            )
            output = adapter.generate(
                "produce the target",
                {"target": {"text": "target"}},
                {"id": "prompt-1"},
                seed=0,
                rerun_index=0,
            )
        self.assertEqual(output, "synthetic hosted output")
        self.assertEqual(server.headers["path"], "/chat/completions")
        self.assertEqual(server.headers["authorization"], "Bearer test-key")
        self.assertEqual(server.headers["content_type"], "application/json")
        self.assertEqual(server.payload["model"], "bench-model")
        self.assertEqual(server.payload["messages"], [{"role": "user", "content": "produce the target"}])
        self.assertEqual(server.payload["temperature"], 0.25)
        self.assertEqual(server.payload["max_tokens"], 123)

    def test_hosted_adapter_reports_http_errors(self) -> None:
        with FakeChatServer(status=503, body={"error": "temporary outage"}) as server:
            adapter = HostedBlackBoxAdapter(
                "bench-model",
                base_url=server.base_url,
                api_key="test-key",
                timeout_seconds=3,
                max_retries=0,
            )
            with self.assertRaisesRegex(HostedBlackBoxError, "HTTP 503"):
                adapter.generate("prompt", {"target": {"text": "target"}}, {"id": "prompt-1"}, seed=0, rerun_index=0)

    def test_hosted_adapter_retries_transient_http_errors(self) -> None:
        sequence = [
            (503, {"error": "temporary outage"}),
            (200, {"choices": [{"message": {"content": "recovered output"}}]}),
        ]
        with FakeChatServer(sequence=sequence) as server:
            adapter = HostedBlackBoxAdapter(
                "bench-model",
                base_url=server.base_url,
                api_key="test-key",
                timeout_seconds=3,
                max_retries=1,
                retry_delay_seconds=0,
            )
            output = adapter.generate("prompt", {"target": {"text": "target"}}, {"id": "prompt-1"}, seed=0, rerun_index=0)
        self.assertEqual(output, "recovered output")
        self.assertEqual(server.request_count, 2)

    def test_hosted_adapter_stops_after_bounded_retries(self) -> None:
        sequence = [
            (503, {"error": "temporary outage"}),
            (503, {"error": "still unavailable"}),
        ]
        with FakeChatServer(sequence=sequence) as server:
            adapter = HostedBlackBoxAdapter(
                "bench-model",
                base_url=server.base_url,
                api_key="test-key",
                timeout_seconds=3,
                max_retries=1,
                retry_delay_seconds=0,
            )
            with self.assertRaisesRegex(HostedBlackBoxError, "HTTP 503"):
                adapter.generate("prompt", {"target": {"text": "target"}}, {"id": "prompt-1"}, seed=0, rerun_index=0)
        self.assertEqual(server.request_count, 2)

    def test_hosted_pipeline_returns_schema_valid_black_box_result(self) -> None:
        with FakeChatServer() as server:
            with patch.dict(
                os.environ,
                {
                    "ALEPH_CUSTOM_API_BASE_URL": server.base_url,
                    "ALEPH_CUSTOM_API_KEY": "test-key",
                },
                clear=False,
            ):
                result = run_benchmark(
                    data_dir=DATA_DIR,
                    models=["hosted:bench-model"],
                    seed=0,
                    limit=1,
                    bootstrap_samples=10,
                )
        schema = load_schema(ROOT / "schemas/aleph-bench-result.schema.json")
        validate(result, schema)
        self.assertEqual(server.request_count, 6)
        self.assertEqual(result["config"]["evidenceModes"], ["black_box"])
        self.assertEqual(result["models"][0]["model"], "bench-model")
        self.assertEqual(result["models"][0]["evidenceMode"], "black_box")
        self.assertEqual(result["itemRuns"][0]["alephRun"]["observations"]["mode"], "black_box")
        self.assertTrue(all(headers["authorization"] == "Bearer test-key" for headers in server.headers_list))
        self.assertTrue(all(payload["model"] == "bench-model" for payload in server.payloads))

    def test_hosted_pipeline_response_cache_reuses_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cache_dir = Path(tmp) / "cache"
            with FakeChatServer() as first_server:
                with patch.dict(
                    os.environ,
                    {
                        "ALEPH_CUSTOM_API_BASE_URL": first_server.base_url,
                        "ALEPH_CUSTOM_API_KEY": "test-key",
                    },
                    clear=False,
                ):
                    first = run_benchmark(
                        data_dir=DATA_DIR,
                        models=["hosted:bench-model"],
                        seed=0,
                        limit=1,
                        bootstrap_samples=10,
                        cache_dir=cache_dir,
                    )
            self.assertEqual(first_server.request_count, 6)

            with FakeChatServer(body={"choices": [{"message": {"content": "uncached second output"}}]}) as second_server:
                with patch.dict(
                    os.environ,
                    {
                        "ALEPH_CUSTOM_API_BASE_URL": second_server.base_url,
                        "ALEPH_CUSTOM_API_KEY": "test-key",
                    },
                    clear=False,
                ):
                    second = run_benchmark(
                        data_dir=DATA_DIR,
                        models=["hosted:bench-model"],
                        seed=0,
                        limit=1,
                        bootstrap_samples=10,
                        cache_dir=cache_dir,
                    )
            schema = load_schema(ROOT / "schemas/aleph-bench-result.schema.json")
            validate(second, schema)
            self.assertEqual(second_server.request_count, 0)
            self.assertEqual(first, second)

    def test_manifest_lists_sendable_prompts(self) -> None:
        manifest = build_manifest(data_dir=DATA_DIR, models=["mock-frontier", "mock-mid", "mock-small"])
        schema = load_schema(ROOT / "schemas/aleph-bench-manifest.schema.json")
        validate(manifest, schema)
        self.assertEqual(manifest["datasetPath"], "bench/data/public/s2")
        self.assertEqual(manifest["promptCount"], 240)
        self.assertEqual(manifest["nonLeakingPromptCount"], 180)
        self.assertEqual(manifest["gatedPromptCount"], 60)
        self.assertEqual(manifest["estimatedGenerations"], 540)
        self.assertEqual(len(manifest["prompts"]), 180)
        self.assertEqual(len(manifest["gatedPrompts"]), 60)
        self.assertIn("prompt", manifest["prompts"][0])
        self.assertNotIn("prompt", manifest["gatedPrompts"][0])
        self.assertTrue(all(not row["leakageGate"]["disqualified"] for row in manifest["prompts"]))
        self.assertTrue(all(row["leakageGate"]["disqualified"] for row in manifest["gatedPrompts"]))

    def test_checked_in_manifest_validates(self) -> None:
        manifest = json.loads((ROOT / "bench/results/m0-call-manifest.json").read_text(encoding="utf-8"))
        schema = load_schema(ROOT / "schemas/aleph-bench-manifest.schema.json")
        validate(manifest, schema)
        self.assertEqual(manifest["nonLeakingPromptCount"], 180)
        self.assertEqual(manifest["gatedPromptCount"], 60)

    def test_verify_checked_in_artifacts(self) -> None:
        report = verify_artifacts(
            data_dir=DATA_DIR,
            result_path=ROOT / "bench/results/m0-first-run.json",
            manifest_path=ROOT / "bench/results/m0-call-manifest.json",
            audit_path=ROOT / "bench/results/m0-audit.json",
            bundle_path=ROOT / "bench/results/m0-bundle.json",
        )
        self.assertEqual(report["status"], "ok")
        self.assertEqual(report["itemCount"], 30)
        self.assertEqual(report["resultItemRuns"], 90)
        self.assertEqual(report["resultAlephRunContractCount"], 90)
        self.assertEqual(report["manifestEstimatedGenerations"], 540)
        self.assertEqual(report["auditCheckCount"], 11)
        self.assertEqual(report["bundleArtifactCount"], 5)

    def test_verify_detects_manifest_result_mismatch(self) -> None:
        manifest = json.loads((ROOT / "bench/results/m0-call-manifest.json").read_text(encoding="utf-8"))
        manifest["models"][0]["model"] = "different-model"
        with tempfile.TemporaryDirectory() as tmp:
            manifest_path = Path(tmp) / "manifest.json"
            manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            report = verify_artifacts(
                data_dir=DATA_DIR,
                result_path=ROOT / "bench/results/m0-first-run.json",
                manifest_path=manifest_path,
            )
        self.assertEqual(report["status"], "failed")
        self.assertIn("result models do not match manifest models", report["errors"])

    def test_verify_detects_audit_result_mismatch(self) -> None:
        audit = json.loads((ROOT / "bench/results/m0-audit.json").read_text(encoding="utf-8"))
        audit["resultPath"] = "bench/results/different-result.json"
        with tempfile.TemporaryDirectory() as tmp:
            audit_path = Path(tmp) / "audit.json"
            audit_path.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            report = verify_artifacts(
                data_dir=DATA_DIR,
                result_path=ROOT / "bench/results/m0-first-run.json",
                manifest_path=ROOT / "bench/results/m0-call-manifest.json",
                audit_path=audit_path,
            )
        self.assertEqual(report["status"], "failed")
        self.assertIn("audit resultPath does not match result path", report["errors"])

    def test_verify_detects_bundle_digest_mismatch(self) -> None:
        bundle = json.loads((ROOT / "bench/results/m0-bundle.json").read_text(encoding="utf-8"))
        bundle["artifacts"][0]["sha256"] = "0" * 64
        with tempfile.TemporaryDirectory() as tmp:
            bundle_path = Path(tmp) / "bundle.json"
            bundle_path.write_text(json.dumps(bundle, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            report = verify_artifacts(
                data_dir=DATA_DIR,
                result_path=ROOT / "bench/results/m0-first-run.json",
                manifest_path=ROOT / "bench/results/m0-call-manifest.json",
                audit_path=ROOT / "bench/results/m0-audit.json",
                bundle_path=bundle_path,
            )
        self.assertEqual(report["status"], "failed")
        self.assertIn("bundle artifact result digest or metadata changed", report["errors"])

    def test_report_renders_result_tables(self) -> None:
        result = json.loads((ROOT / "bench/results/m0-first-run.json").read_text(encoding="utf-8"))
        model_table = model_summary_table(result)
        item_table = per_item_table(result)
        report = render_report_file(ROOT / "bench/results/m0-first-run.json")
        self.assertIn("| mock-frontier | mock | 0.047515 | 0.043485-0.051577 |", model_table)
        self.assertIn("| s2-001 | 0.039 / 6 | 0.168 / 34 | 0.348 / 34 |", item_table)
        self.assertIn("Evidence modes: `mock`", report)
        self.assertIn("This report is generated from the result JSON", report)

    def test_audit_m0_acceptance_gate(self) -> None:
        report = audit_m0_acceptance(
            data_dir=DATA_DIR,
            result_path=ROOT / "bench/results/m0-first-run.json",
            evidence_note_path=ROOT / "docs/benchmark/m0-evidence.md",
        )
        text = format_audit_report(report)
        schema = load_schema(ROOT / "schemas/aleph-bench-audit.schema.json")
        validate(report, schema)
        self.assertEqual(report["status"], "ok")
        self.assertIn("[ok] dataset-integrity", text)
        self.assertIn("[ok] aleph-run-contract", text)
        self.assertIn("[ok] exact-match", text)
        self.assertIn("[ok] seed-0-reproducible", text)
        self.assertIn("[ok] rank-stable", text)
        receipt = json.loads((ROOT / "bench/results/m0-audit.json").read_text(encoding="utf-8"))
        validate(receipt, schema)
        self.assertEqual(receipt, report)

    def test_audit_refuses_non_mock_results_without_rerun(self) -> None:
        result = json.loads((ROOT / "bench/results/m0-first-run.json").read_text(encoding="utf-8"))
        result["config"]["evidenceModes"] = ["black_box"]
        result["models"][0]["evidenceMode"] = "black_box"
        result["itemRuns"][0]["alephRun"]["observations"]["mode"] = "black_box"
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "black-box-shaped-result.json"
            path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            report = audit_m0_acceptance(
                data_dir=DATA_DIR,
                result_path=path,
                evidence_note_path=ROOT / "docs/benchmark/m0-evidence.md",
            )
        text = format_audit_report(report)
        self.assertEqual(report["status"], "failed")
        self.assertIn("[failed] mock-only-audit", text)
        self.assertNotIn("seed-0-reproducible", text)
        self.assertNotIn("rank-stable", text)

    def test_bundle_manifest_matches_current_artifacts(self) -> None:
        bundle = build_m0_bundle(
            result_path=ROOT / "bench/results/m0-first-run.json",
            manifest_path=ROOT / "bench/results/m0-call-manifest.json",
            audit_path=ROOT / "bench/results/m0-audit.json",
            report_path=ROOT / "bench/results/m0-report.md",
            evidence_note_path=ROOT / "docs/benchmark/m0-evidence.md",
        )
        schema = load_schema(ROOT / "schemas/aleph-bench-bundle.schema.json")
        validate(bundle, schema)
        checked_in = json.loads((ROOT / "bench/results/m0-bundle.json").read_text(encoding="utf-8"))
        validate(checked_in, schema)
        self.assertEqual(compare_bundle(checked_in, bundle), [])
        self.assertEqual(checked_in, bundle)
        broken = copy.deepcopy(checked_in)
        broken["artifacts"][0]["sha256"] = "not-a-digest"
        with self.assertRaisesRegex(SchemaValidationError, "does not match pattern"):
            validate(broken, schema)

    def test_written_result_validates(self) -> None:
        result = run_benchmark(
            data_dir=DATA_DIR,
            models=["mock-frontier"],
            seed=0,
            limit=2,
            bootstrap_samples=25,
        )
        schema = load_schema(ROOT / "schemas/aleph-bench-result.schema.json")
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "result.json"
            path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            loaded = json.loads(path.read_text(encoding="utf-8"))
        validate(loaded, schema)
        self.assertEqual(copy.deepcopy(loaded), result)

    def test_platform_package_contains_hf_kaggle_and_croissant_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp) / "platform"
            manifest = write_platform_package(out_dir)
            schema = load_schema(ROOT / "schemas/aleph-bench-platform-package.schema.json")
            validate(manifest, schema)
            report = check_platform_package(out_dir / "package-manifest.json")

            self.assertEqual(report["status"], "ok")
            self.assertEqual(set(manifest["targetPlatforms"]), {"huggingface_dataset", "kaggle_dataset", "croissant"})
            self.assertIn("README.md", {artifact["path"] for artifact in manifest["artifacts"]})
            self.assertIn("dataset-metadata.json", {artifact["path"] for artifact in manifest["artifacts"]})
            self.assertIn("croissant.json", {artifact["path"] for artifact in manifest["artifacts"]})

            readme = (out_dir / "README.md").read_text(encoding="utf-8")
            kaggle = json.loads((out_dir / "dataset-metadata.json").read_text(encoding="utf-8"))
            croissant = json.loads((out_dir / "croissant.json").read_text(encoding="utf-8"))
            items = (out_dir / "data/public_s2_items.jsonl").read_text(encoding="utf-8").strip().splitlines()
            prompts = (out_dir / "data/public_s2_prompts.jsonl").read_text(encoding="utf-8").strip().splitlines()
            submission = (out_dir / "data/submission_format.csv").read_text(encoding="utf-8").splitlines()

            self.assertTrue(readme.startswith("---\npretty_name: Aleph-Bench M0"))
            self.assertIn("not a real model leaderboard", readme)
            self.assertEqual(kaggle["id"], "p-to-q/aleph-bench-m0")
            self.assertEqual(kaggle["licenses"], [{"name": "CC0-1.0"}])
            self.assertEqual(croissant["dct:conformsTo"], "http://mlcommons.org/croissant/1.1")
            self.assertEqual(len(items), 30)
            self.assertEqual(len(prompts), 240)
            self.assertEqual(submission[0], "row_id,model_id,item_id,prompt_id,output_text")


if __name__ == "__main__":
    unittest.main()
