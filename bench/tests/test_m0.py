from __future__ import annotations

import copy
from http.server import BaseHTTPRequestHandler, HTTPServer
import http.client
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import traceback
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import patch

from bench.engine.audit import audit_m0_acceptance, format_audit_report
from bench.engine.adapters.base import ModelAdapter
from bench.engine.adapters.hosted_black_box import HostedBlackBoxAdapter, HostedBlackBoxError
from bench.engine.bundle import build_m0_bundle, compare_bundle
from bench.engine.frozen_ladder import (
    DEFAULT_BOOTSTRAP_SAMPLES,
    DEFAULT_K,
    DEFAULT_RERUNS,
    DEFAULT_TAU,
    PROTOCOL_CONFIG_PATH,
    evaluate_item,
    load_protocol_config,
    run_benchmark,
)
from bench.engine.leakage_gate import evaluate_leakage
from bench.engine.manifest import build_manifest
from bench.engine.platform_package import check_platform_package
from bench.engine.metrics import (
    aurc,
    elicit_at_k,
    exact_fidelity,
    monotone_lower_envelope,
    normalized_edit_similarity,
    rank_by_metric,
)
from bench.engine.preflight import preflight
from bench.engine.report import (
    model_summary_table,
    per_item_table,
    render_markdown_report,
    render_report_file,
)
from bench.engine.schema_validation import SchemaValidationError, load_schema, validate
from bench.engine.verify import verify_artifacts


ROOT = Path(__file__).resolve().parents[2]
V1_DATA_DIR = ROOT / "bench/data/public/s2"
DATA_DIR = ROOT / "bench/data/v0.2/public/s2"
V2_SCHEMA_DIR = ROOT / "schemas/v0.2"


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


class RedirectTargetHandler(BaseHTTPRequestHandler):
    request_count = 0
    authorization_headers: list[str] = []

    def _record_request(self) -> None:
        type(self).request_count += 1
        type(self).authorization_headers.append(
            self.headers.get("Authorization", "")
        )
        body = json.dumps(
            {"choices": [{"message": {"content": "redirected output"}}]}
        ).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        self._record_request()

    def do_POST(self) -> None:
        self._record_request()

    def log_message(self, format: str, *args: object) -> None:
        return


class RedirectSourceHandler(BaseHTTPRequestHandler):
    location = ""
    request_count = 0

    def do_POST(self) -> None:
        type(self).request_count += 1
        length = int(self.headers.get("Content-Length", "0"))
        self.rfile.read(length)
        self.send_response(302)
        self.send_header("Location", type(self).location)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def log_message(self, format: str, *args: object) -> None:
        return


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
        self.assertEqual(exact_fidelity(target, "row 1: n=7"), 0.0)
        self.assertEqual(exact_fidelity(target, "unrelated output"), 0.0)
        self.assertGreater(normalized_edit_similarity(target, "row 1: n=7"), 0.3)

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
            {"id": "d", "tokens": 4, "distortion": 0.5, "fidelity": 0.5, "disqualified": False},
        ]
        frontier = monotone_lower_envelope(points)
        self.assertEqual([point["id"] for point in frontier], ["d", "c"])
        self.assertEqual(aurc(frontier, 10), 0.64)

    def test_aurc_starts_at_empty_budget_baseline(self) -> None:
        self.assertEqual(aurc([], 10), 1.0)
        point = {"id": "a", "tokens": 4, "distortion": 0.6, "fidelity": 0.4}
        self.assertEqual(aurc([point], 10), 0.76)
        zero_length = {"id": "z", "tokens": 0, "distortion": 0.25, "fidelity": 0.75}
        self.assertEqual(aurc([zero_length], 10), 0.25)

    def test_elicit_at_k_uses_length_budget_not_point_count(self) -> None:
        points = [
            {"id": "long", "tokens": 16, "fidelity": 0.95},
            {"id": "short", "tokens": 2, "fidelity": 0.2},
            {"id": "over", "tokens": 17, "fidelity": 1.0},
        ]
        self.assertFalse(elicit_at_k(points, tau=0.9, k=15))
        self.assertTrue(elicit_at_k(points, tau=0.9, k=16))
        self.assertFalse(elicit_at_k(list(reversed(points)), tau=0.9, k=15))

    def test_protocol_defaults_come_from_checked_in_config(self) -> None:
        config = load_protocol_config(PROTOCOL_CONFIG_PATH)
        self.assertEqual(DEFAULT_TAU, config["tau"])
        self.assertEqual(DEFAULT_K, config["k"])
        self.assertEqual(DEFAULT_RERUNS, config["reruns"])
        self.assertEqual(DEFAULT_BOOTSTRAP_SAMPLES, config["bootstrapSamples"])
        self.assertEqual(DEFAULT_K, 16)

    def test_schema(self) -> None:
        result = run_benchmark(
            data_dir=DATA_DIR,
            models=["mock-frontier", "mock-mid", "mock-small"],
            seed=0,
            limit=3,
        )
        schema = load_schema(V2_SCHEMA_DIR / "aleph-bench-result.schema.json")
        validate(result, schema)
        self.assertEqual(result["config"]["datasetPath"], "bench/data/v0.2/public/s2")

    def test_iia(self) -> None:
        result = run_benchmark(
            data_dir=DATA_DIR,
            models=["mock-frontier", "mock-mid", "mock-small"],
            seed=0,
            limit=5,
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
        )
        second = run_benchmark(
            data_dir=DATA_DIR,
            models=["mock-frontier", "mock-mid", "mock-small"],
            seed=1,
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
        )
        second = run_benchmark(
            data_dir=DATA_DIR,
            models=["mock-frontier", "mock-mid"],
            seed=17,
            limit=4,
        )
        self.assertEqual(first, second)

    def test_measurements_record_rerun_variance(self) -> None:
        item = json.loads((DATA_DIR / "s2-001.json").read_text(encoding="utf-8"))
        run = evaluate_item(item, VariableAdapter(), seed=0)
        non_leaking = [row for row in run["measurements"] if not row["disqualified"]]
        gated = [row for row in run["measurements"] if row["disqualified"]]
        self.assertEqual(len(run["measurements"]), 8)
        self.assertEqual(gated[0]["rerunCount"], 0)
        self.assertIsNone(gated[0]["fidelityVariance"])
        self.assertEqual(non_leaking[0]["rerunCount"], 5)
        self.assertGreater(non_leaking[0]["fidelityVariance"], 0)
        self.assertGreater(non_leaking[0]["fidelityStdDev"], 0)
        self.assertTrue(all(point["rerunCount"] == 5 for point in run["frontier"]))

    def test_preflight_estimates_mock_run(self) -> None:
        report = preflight(data_dir=DATA_DIR, models=["mock-frontier", "mock-mid", "mock-small"])
        self.assertEqual(report["status"], "ready")
        self.assertEqual(report["itemCount"], 30)
        self.assertEqual(report["promptCount"], 240)
        self.assertEqual(report["disqualifiedPromptCount"], 60)
        self.assertEqual(report["nonLeakingPromptCount"], 180)
        self.assertEqual(report["estimatedGenerations"], 540)
        self.assertEqual(report["estimatedMaxHttpAttempts"], 0)
        self.assertEqual(report["leakageByRung"], {"0": 60, "1": 0, "2": 0, "3": 0})

    def test_preflight_blocks_hosted_without_env(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            report = preflight(data_dir=DATA_DIR, models=["hosted:frontier-model"])
        self.assertEqual(report["status"], "blocked")
        self.assertEqual(report["models"][0]["evidenceMode"], "black_box")
        self.assertEqual(
            report["models"][0]["missingEnv"],
            [
                "ALEPH_CUSTOM_API_BASE_URL",
                "ALEPH_CUSTOM_API_KEY",
                "ALEPH_CUSTOM_API_DEPLOYMENT_ID",
            ],
        )
        self.assertEqual(report["estimatedGenerations"], 900)
        self.assertEqual(report["hostedMaxRetries"], 2)
        self.assertEqual(report["hostedRetryDelaySeconds"], 1.0)
        self.assertEqual(report["estimatedMaxHttpAttempts"], 2700)

    def test_hosted_retry_policy_is_bounded_before_calls(self) -> None:
        with patch.dict(
            os.environ,
            {
                "ALEPH_CUSTOM_API_BASE_URL": "https://example.invalid",
                "ALEPH_CUSTOM_API_KEY": "test-key",
                "ALEPH_CUSTOM_API_DEPLOYMENT_ID": "fixture-deployment",
                "ALEPH_CUSTOM_API_MAX_RETRIES": "100",
            },
            clear=True,
        ):
            report = preflight(data_dir=DATA_DIR, models=["hosted:frontier-model"])
            self.assertEqual(report["status"], "blocked")
            self.assertTrue(
                any("MAX_RETRIES" in error for error in report["errors"]),
                msg=report["errors"],
            )
            with self.assertRaisesRegex(ValueError, "MAX_RETRIES"):
                build_manifest(
                    data_dir=DATA_DIR,
                    models=["hosted:frontier-model"],
                )

    def test_hosted_endpoint_validation_fails_before_calls(self) -> None:
        for base_url in (
            "not-a-url",
            "ftp://example.com/v1",
            "http://example.com/v1",
            "https://user:secret@example.com/v1",
            "https://example.com/v1?",
            "https://example.com/v1#",
            "https://example.com/v1/chat/completions",
        ):
            with self.subTest(base_url=base_url):
                with self.assertRaises(RuntimeError):
                    HostedBlackBoxAdapter(
                        "frontier-model",
                        base_url=base_url,
                        api_key="test-key",
                        deployment_id="fixture-deployment",
                    )

        # Exercise the preflight and manifest integration once. Repeating a full
        # frozen-dataset validation for every URL parser vector only retests the
        # same adapter error propagation and makes the suite needlessly slow.
        with patch.dict(
            os.environ,
            {
                "ALEPH_CUSTOM_API_BASE_URL": "not-a-url",
                "ALEPH_CUSTOM_API_KEY": "test-key",
                "ALEPH_CUSTOM_API_DEPLOYMENT_ID": "fixture-deployment",
            },
            clear=True,
        ):
            report = preflight(data_dir=DATA_DIR, models=["hosted:frontier-model"])
            self.assertEqual(report["status"], "blocked")
            self.assertTrue(report["models"][0].get("error"), msg=report)
            with self.assertRaisesRegex(ValueError, "manifest planning failed"):
                build_manifest(
                    data_dir=DATA_DIR,
                    models=["hosted:frontier-model"],
                )

        with patch.dict(
            os.environ,
            {
                "ALEPH_CUSTOM_API_BASE_URL": "http://127.0.0.1:8000/v1",
                "ALEPH_CUSTOM_API_KEY": "test-key",
                "ALEPH_CUSTOM_API_DEPLOYMENT_ID": "fixture-deployment",
            },
            clear=True,
        ):
            report = preflight(data_dir=DATA_DIR, models=["hosted:frontier-model"])
        self.assertEqual(report["status"], "ready", msg=report)

        with patch.dict(
            os.environ,
            {
                "ALEPH_CUSTOM_API_BASE_URL": "https://example.invalid",
                "ALEPH_CUSTOM_API_KEY": "test-key",
                "ALEPH_CUSTOM_API_DEPLOYMENT_ID": "fixture-deployment",
                "ALEPH_CUSTOM_API_RETRY_DELAY_SECONDS": "NaN",
            },
            clear=True,
        ):
            report = preflight(data_dir=DATA_DIR, models=["hosted:frontier-model"])
            self.assertEqual(report["status"], "blocked")
            self.assertTrue(
                any("RETRY_DELAY_SECONDS" in error for error in report["errors"]),
                msg=report["errors"],
            )
            with self.assertRaisesRegex(ValueError, "RETRY_DELAY_SECONDS"):
                build_manifest(
                    data_dir=DATA_DIR,
                    models=["hosted:frontier-model"],
                )

    def test_hosted_adapter_posts_openai_compatible_payload(self) -> None:
        with FakeChatServer() as server:
            adapter = HostedBlackBoxAdapter(
                "bench-model",
                base_url=server.base_url,
                api_key="test-key",
                deployment_id="fixture-deployment",
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
        receipt = adapter.last_response_receipt()
        self.assertIsNotNone(receipt)
        self.assertEqual(receipt["source"], "provider")

    def test_hosted_body_cap_accepts_maximum_json_escaped_output(self) -> None:
        output = "😀" * 16_384
        with FakeChatServer(
            body={"choices": [{"message": {"content": output}}]}
        ) as server:
            adapter = HostedBlackBoxAdapter(
                "bench-model",
                base_url=server.base_url,
                api_key="test-key",
                deployment_id="fixture-deployment",
                max_retries=0,
            )
            observed = adapter.generate(
                "prompt",
                {"target": {"text": "target"}},
                {"id": "prompt-1"},
                seed=0,
                rerun_index=0,
            )
        self.assertEqual(observed, output)

    def test_hosted_adapter_reports_http_errors(self) -> None:
        with FakeChatServer(status=503, body={"error": "temporary outage"}) as server:
            adapter = HostedBlackBoxAdapter(
                "bench-model",
                base_url=server.base_url,
                api_key="test-key",
                deployment_id="fixture-deployment",
                timeout_seconds=3,
                max_retries=0,
            )
            with self.assertRaisesRegex(HostedBlackBoxError, "HTTP 503"):
                adapter.generate("prompt", {"target": {"text": "target"}}, {"id": "prompt-1"}, seed=0, rerun_index=0)

    def test_hosted_adapter_does_not_echo_provider_error_body(self) -> None:
        secret = "SUPER_SECRET_KEY"
        with FakeChatServer(
            status=400,
            body={"error": f"upstream echoed Authorization: Bearer {secret}"},
        ) as server:
            adapter = HostedBlackBoxAdapter(
                "bench-model",
                base_url=server.base_url,
                api_key=secret,
                deployment_id="fixture-deployment",
                timeout_seconds=3,
                max_retries=0,
            )
            with self.assertRaises(HostedBlackBoxError) as raised:
                adapter.generate(
                    "prompt",
                    {"target": {"text": "target"}},
                    {"id": "prompt-1"},
                    seed=0,
                    rerun_index=0,
                )
        self.assertIn("HTTP 400", str(raised.exception))
        self.assertNotIn(secret, str(raised.exception))

    def test_hosted_adapter_rejects_unsafe_api_keys_without_echoing_them(self) -> None:
        unsafe_keys = (
            "SUPER_SECRET_KEY\nX-Test: injected",
            "SUPER_SECRET_KEY\rtrailing",
            "SUPER_SECRET_KEY\x00suffix",
            "SUPER_SECRET_KEY-密钥",
        )
        for secret in unsafe_keys:
            with self.subTest(secret_kind=repr(secret[-8:])):
                with self.assertRaises(RuntimeError) as raised:
                    HostedBlackBoxAdapter(
                        "bench-model",
                        base_url="https://example.invalid/v1",
                        api_key=secret,
                        deployment_id="fixture-deployment",
                        max_retries=0,
                    )
                message = str(raised.exception)
                self.assertIn("printable ASCII without whitespace", message)
                self.assertNotIn(secret, message)
                self.assertNotIn("SUPER_SECRET_KEY", message)

    def test_hosted_adapter_sanitizes_provider_controlled_protocol_errors(self) -> None:
        secret = "SUPER_SECRET_KEY"
        failures = (
            http.client.BadStatusLine(secret),
            http.client.IncompleteRead(secret.encode("ascii"), 999),
            http.client.RemoteDisconnected(secret),
            urllib.error.HTTPError(
                "https://example.invalid/v1/chat/completions",
                400,
                secret,
                {},
                io.BytesIO(secret.encode("ascii")),
            ),
            urllib.error.URLError(secret),
        )
        for failure in failures:
            with self.subTest(failure_type=type(failure).__name__):
                adapter = HostedBlackBoxAdapter(
                    "bench-model",
                    base_url="https://example.invalid/v1",
                    api_key="test-key",
                    deployment_id="fixture-deployment",
                    max_retries=0,
                )
                with patch.object(adapter._opener, "open", side_effect=failure):
                    with self.assertRaises(HostedBlackBoxError) as raised:
                        adapter.generate(
                            "prompt",
                            {"target": {"text": "target"}},
                            {"id": "prompt-1"},
                            seed=0,
                            rerun_index=0,
                        )
                rendered = "".join(traceback.format_exception(raised.exception))
                self.assertNotIn(secret, str(raised.exception))
                self.assertNotIn(secret, rendered)

    def test_hosted_adapter_rejects_redirect_before_sending_credentials(self) -> None:
        RedirectTargetHandler.request_count = 0
        RedirectTargetHandler.authorization_headers = []
        RedirectSourceHandler.request_count = 0
        target_server = HTTPServer(("127.0.0.1", 0), RedirectTargetHandler)
        target_host, target_port = target_server.server_address
        RedirectSourceHandler.location = (
            f"http://{target_host}:{target_port}/credential-capture"
        )
        source_server = HTTPServer(("127.0.0.1", 0), RedirectSourceHandler)
        source_host, source_port = source_server.server_address
        target_thread = threading.Thread(
            target=target_server.serve_forever, daemon=True
        )
        source_thread = threading.Thread(
            target=source_server.serve_forever, daemon=True
        )
        target_thread.start()
        source_thread.start()
        try:
            adapter = HostedBlackBoxAdapter(
                "bench-model",
                base_url=f"http://{source_host}:{source_port}",
                api_key="do-not-forward",
                deployment_id="fixture-deployment",
                timeout_seconds=3,
                max_retries=0,
            )
            with self.assertRaisesRegex(
                HostedBlackBoxError, "redirects are not allowed"
            ):
                adapter.generate(
                    "prompt",
                    {"target": {"text": "target"}},
                    {"id": "prompt-1"},
                    seed=0,
                    rerun_index=0,
                )
        finally:
            source_server.shutdown()
            target_server.shutdown()
            source_server.server_close()
            target_server.server_close()
            source_thread.join(timeout=2)
            target_thread.join(timeout=2)

        self.assertEqual(RedirectSourceHandler.request_count, 1)
        self.assertEqual(RedirectTargetHandler.request_count, 0)
        self.assertEqual(RedirectTargetHandler.authorization_headers, [])

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
                deployment_id="fixture-deployment",
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
                deployment_id="fixture-deployment",
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
                    "ALEPH_CUSTOM_API_DEPLOYMENT_ID": "fixture-deployment",
                },
                clear=False,
            ):
                result = run_benchmark(
                    data_dir=DATA_DIR,
                    models=["hosted:bench-model"],
                    seed=0,
                    limit=1,
                )
        schema = load_schema(V2_SCHEMA_DIR / "aleph-bench-result.schema.json")
        validate(result, schema)
        rendered = render_markdown_report(result)
        self.assertIn("## Hosted Evidence Provenance", rendered)
        self.assertIn("fixture-deployment", rendered)

        incomplete = copy.deepcopy(result)
        for field in (
            "wireProtocol",
            "requestPayloadVersion",
            "endpointSha256",
            "maxTokens",
            "providerModel",
            "deploymentId",
            "timeoutSeconds",
            "maxRetries",
            "retryDelaySeconds",
        ):
            incomplete["models"][0]["adapterIdentity"].pop(field)
        incomplete["models"][0]["responseCapture"] = None
        with self.assertRaises(SchemaValidationError):
            validate(incomplete, schema)
        self.assertEqual(server.request_count, 30)
        self.assertEqual(result["config"]["evidenceModes"], ["black_box"])
        self.assertEqual(result["models"][0]["model"], "hosted:bench-model")
        self.assertEqual(result["models"][0]["evidenceMode"], "black_box")
        self.assertEqual(
            result["models"][0]["adapterIdentity"]["deploymentId"],
            "fixture-deployment",
        )
        self.assertEqual(
            result["models"][0]["responseCapture"]["providerResponseCount"], 30
        )
        self.assertEqual(result["models"][0]["responseCapture"]["cacheHitCount"], 0)
        self.assertEqual(result["itemRuns"][0]["alephRun"]["observations"]["mode"], "black_box")
        self.assertTrue(any("black-box output evidence" in note for note in result["notes"]))
        self.assertFalse(any("Mock rows" in note for note in result["notes"]))
        self.assertTrue(all(headers["authorization"] == "Bearer test-key" for headers in server.headers_list))
        self.assertTrue(all(payload["model"] == "bench-model" for payload in server.payloads))

    def test_hosted_pipeline_response_cache_reuses_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cache_dir = Path(tmp) / "cache"
            with FakeChatServer() as server:
                with patch.dict(
                    os.environ,
                    {
                        "ALEPH_CUSTOM_API_BASE_URL": server.base_url,
                        "ALEPH_CUSTOM_API_KEY": "test-key",
                        "ALEPH_CUSTOM_API_DEPLOYMENT_ID": "fixture-deployment",
                    },
                    clear=False,
                ):
                    first = run_benchmark(
                        data_dir=DATA_DIR,
                        models=["hosted:bench-model"],
                        seed=0,
                        limit=1,
                        cache_dir=cache_dir,
                    )
                    self.assertEqual(server.request_count, 30)
                    FakeChatHandler.response_body = {
                        "choices": [{"message": {"content": "uncached second output"}}]
                    }
                    second = run_benchmark(
                        data_dir=DATA_DIR,
                        models=["hosted:bench-model"],
                        seed=0,
                        limit=1,
                        cache_dir=cache_dir,
                    )
                    self.assertEqual(server.request_count, 30)
            schema = load_schema(V2_SCHEMA_DIR / "aleph-bench-result.schema.json")
            validate(second, schema)
            first_outputs = [
                measurement["outputs"]
                for item_run in first["itemRuns"]
                for measurement in item_run["measurements"]
            ]
            second_outputs = [
                measurement["outputs"]
                for item_run in second["itemRuns"]
                for measurement in item_run["measurements"]
            ]
            self.assertEqual(first_outputs, second_outputs)
            self.assertNotEqual(first["id"], second["id"])
            self.assertEqual(
                first["models"][0]["responseCapture"]["providerResponseCount"], 30
            )
            self.assertEqual(first["models"][0]["responseCapture"]["cacheHitCount"], 0)
            self.assertEqual(
                second["models"][0]["responseCapture"]["providerResponseCount"], 0
            )
            self.assertEqual(second["models"][0]["responseCapture"]["cacheHitCount"], 30)
            self.assertEqual(
                first["models"][0]["responseCapture"]["capturedAtMin"],
                second["models"][0]["responseCapture"]["capturedAtMin"],
            )

    def test_manifest_lists_sendable_prompts(self) -> None:
        manifest = build_manifest(data_dir=DATA_DIR, models=["mock-frontier", "mock-mid", "mock-small"])
        schema = load_schema(V2_SCHEMA_DIR / "aleph-bench-manifest.schema.json")
        validate(manifest, schema)
        self.assertEqual(manifest["datasetPath"], "bench/data/v0.2/public/s2")
        self.assertEqual(manifest["promptCount"], 240)
        self.assertEqual(manifest["nonLeakingPromptCount"], 180)
        self.assertEqual(manifest["gatedPromptCount"], 60)
        self.assertEqual(manifest["estimatedGenerations"], 540)
        self.assertEqual(manifest["hostedMaxRetries"], 2)
        self.assertEqual(manifest["hostedRetryDelaySeconds"], 1.0)
        self.assertEqual(manifest["estimatedMaxHttpAttempts"], 0)
        self.assertEqual(len(manifest["prompts"]), 180)
        self.assertEqual(len(manifest["gatedPrompts"]), 60)
        self.assertIn("prompt", manifest["prompts"][0])
        self.assertNotIn("prompt", manifest["gatedPrompts"][0])
        self.assertTrue(all(not row["leakageGate"]["disqualified"] for row in manifest["prompts"]))
        self.assertTrue(all(row["leakageGate"]["disqualified"] for row in manifest["gatedPrompts"]))

    def test_manifest_schema_requires_complete_ready_hosted_identity(self) -> None:
        schema = load_schema(V2_SCHEMA_DIR / "aleph-bench-manifest.schema.json")
        with patch.dict(
            os.environ,
            {
                "ALEPH_CUSTOM_API_BASE_URL": "https://example.invalid/v1",
                "ALEPH_CUSTOM_API_KEY": "fixture-key",
                "ALEPH_CUSTOM_API_DEPLOYMENT_ID": "fixture-deployment",
            },
            clear=True,
        ):
            ready = build_manifest(
                data_dir=DATA_DIR,
                models=["hosted:fixture-model"],
            )
        validate(ready, schema)

        incomplete = copy.deepcopy(ready)
        incomplete["models"][0]["adapterIdentity"].pop("deploymentId")
        with self.assertRaises(SchemaValidationError):
            validate(incomplete, schema)

        with (
            patch.dict(os.environ, {}, clear=True),
            self.assertRaisesRegex(
                ValueError,
                "hosted:fixture-model.*missing env: ALEPH_CUSTOM_API_BASE_URL",
            ),
        ):
            build_manifest(
                data_dir=DATA_DIR,
                models=["hosted:fixture-model"],
            )

    def test_checked_in_manifest_validates(self) -> None:
        manifest = json.loads((ROOT / "bench/results/m0-call-manifest.json").read_text(encoding="utf-8"))
        schema = load_schema(ROOT / "schemas/aleph-bench-manifest.schema.json")
        validate(manifest, schema)
        self.assertEqual(manifest["nonLeakingPromptCount"], 180)
        self.assertEqual(manifest["gatedPromptCount"], 60)

    def test_verify_checked_in_artifacts(self) -> None:
        report = verify_artifacts(
            data_dir=V1_DATA_DIR,
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
                data_dir=V1_DATA_DIR,
                result_path=ROOT / "bench/results/m0-first-run.json",
                manifest_path=manifest_path,
            )
        self.assertEqual(report["status"], "failed")
        self.assertIn("result models do not match manifest models", report["errors"])

    def test_verify_rejects_unreceipted_v0_1_copies(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data_dir = root / "s2"
            shutil.copytree(V1_DATA_DIR, data_dir)
            result = json.loads(
                (ROOT / "bench/results/m0-first-run.json").read_text(encoding="utf-8")
            )
            manifest = json.loads(
                (ROOT / "bench/results/m0-call-manifest.json").read_text(
                    encoding="utf-8"
                )
            )
            dataset_path = data_dir.as_posix()
            result["config"]["datasetPath"] = dataset_path
            result["models"][0]["aurc"] = 0.987654
            manifest["datasetPath"] = dataset_path
            result_path = root / "result.json"
            manifest_path = root / "manifest.json"
            result_path.write_text(json.dumps(result), encoding="utf-8")
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

            report = verify_artifacts(
                data_dir=data_dir,
                result_path=result_path,
                manifest_path=manifest_path,
            )

        self.assertEqual(report["status"], "failed")
        self.assertTrue(
            any(
                "requires canonical dataset path" in error
                for error in report["errors"]
            ),
            msg=report["errors"],
        )
        self.assertTrue(
            any(
                "requires canonical result path" in error
                for error in report["errors"]
            ),
            msg=report["errors"],
        )

    def test_verify_detects_audit_result_mismatch(self) -> None:
        audit = json.loads((ROOT / "bench/results/m0-audit.json").read_text(encoding="utf-8"))
        audit["resultPath"] = "bench/results/different-result.json"
        with tempfile.TemporaryDirectory() as tmp:
            audit_path = Path(tmp) / "audit.json"
            audit_path.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            report = verify_artifacts(
                data_dir=V1_DATA_DIR,
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
                data_dir=V1_DATA_DIR,
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
        self.assertIn("| mock-frontier | mock | 0.155604 | 0.150746-0.16024 |", model_table)
        self.assertIn("| s2-001 | 0.158 / 6 | 0.256 / 34 | 0.403 / 34 |", item_table)
        self.assertIn("Evidence modes: `mock`", report)
        self.assertIn("This report is generated from the result JSON", report)

    def test_audit_m0_acceptance_gate(self) -> None:
        report = json.loads((ROOT / "bench/results/m0-audit.json").read_text(encoding="utf-8"))
        schema = load_schema(ROOT / "schemas/aleph-bench-audit.schema.json")
        validate(report, schema)
        self.assertEqual(report["status"], "ok")
        self.assertTrue(all(check["status"] == "ok" for check in report["checks"]))

    def test_audit_refuses_non_mock_results_without_rerun(self) -> None:
        result = json.loads((ROOT / "bench/results/m0-first-run.json").read_text(encoding="utf-8"))
        result["config"]["evidenceModes"] = ["black_box"]
        result["models"][0]["evidenceMode"] = "black_box"
        result["itemRuns"][0]["alephRun"]["observations"]["mode"] = "black_box"
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "black-box-shaped-result.json"
            path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            report = audit_m0_acceptance(
                data_dir=V1_DATA_DIR,
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

    def test_bundle_cli_rejects_self_receipted_v0_1_copies(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source_paths = {
                "result": ROOT / "bench/results/m0-first-run.json",
                "manifest": ROOT / "bench/results/m0-call-manifest.json",
                "audit": ROOT / "bench/results/m0-audit.json",
                "report": ROOT / "bench/results/m0-report.md",
                "evidence": ROOT / "docs/benchmark/m0-evidence.md",
            }
            copied = {role: root / path.name for role, path in source_paths.items()}
            for role, source in source_paths.items():
                shutil.copy2(source, copied[role])
            result = json.loads(copied["result"].read_text(encoding="utf-8"))
            result["models"][0]["aurc"] = 0.987654
            copied["result"].write_text(json.dumps(result), encoding="utf-8")
            self_receipt = build_m0_bundle(
                result_path=copied["result"],
                manifest_path=copied["manifest"],
                audit_path=copied["audit"],
                report_path=copied["report"],
                evidence_note_path=copied["evidence"],
            )
            check = root / "bundle.json"
            check.write_text(json.dumps(self_receipt), encoding="utf-8")
            completed = subprocess.run(
                [
                    str(ROOT / "aleph-bench"),
                    "bundle",
                    "--result",
                    str(copied["result"]),
                    "--manifest",
                    str(copied["manifest"]),
                    "--audit",
                    str(copied["audit"]),
                    "--report",
                    str(copied["report"]),
                    "--evidence-note",
                    str(copied["evidence"]),
                    "--check",
                    str(check),
                ],
                capture_output=True,
                text=True,
            )
        self.assertEqual(completed.returncode, 2)
        self.assertIn("requires canonical result path", completed.stderr)

    def test_written_result_validates(self) -> None:
        result = run_benchmark(
            data_dir=DATA_DIR,
            models=["mock-frontier"],
            seed=0,
            limit=2,
        )
        schema = load_schema(V2_SCHEMA_DIR / "aleph-bench-result.schema.json")
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "result.json"
            path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            loaded = json.loads(path.read_text(encoding="utf-8"))
        validate(loaded, schema)
        self.assertEqual(copy.deepcopy(loaded), result)

    def test_checked_in_platform_package_validates(self) -> None:
        report = check_platform_package(ROOT / "bench/results/platform/m0-mock/package-manifest.json")
        self.assertEqual(report["status"], "ok", msg=report)
        self.assertEqual(report["artifactCount"], 32)
        self.assertEqual(
            set(report["targetPlatforms"]),
            {"huggingface_dataset", "kaggle_dataset", "kaggle_community_benchmark", "croissant"},
        )

    def test_generate_s2_check_matches_disk(self) -> None:
        result = subprocess.run(
            [sys.executable, str(ROOT / "bench/data/generate_s2.py"), "--check"],
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertIn("check ok", result.stdout)

if __name__ == "__main__":
    unittest.main()
