from __future__ import annotations

import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from bench.engine.adapters.base import ModelAdapter
from bench.engine.adapters.hosted_black_box import (
    HostedBlackBoxAdapter,
    HostedBlackBoxError,
)
from bench.engine.frozen_ladder import evaluate_item, load_items, run_benchmark
from bench.engine.manifest import build_manifest
from bench.engine.platform_package_v0_2 import (
    check_v0_2_package,
    write_v0_2_package,
)
from bench.engine.protocol import (
    FROZEN_DATASET_HASH_ALGORITHM,
    FROZEN_DATASET_ID,
    FROZEN_DATASET_ITEM_COUNT,
    FROZEN_DATASET_SHA256,
    PROTOCOL_VERSION,
    RESPONSE_CAPTURE_VERSION,
    load_protocol_config,
)
from bench.engine.response_cache import MAX_CACHE_RECORD_BYTES, ResponseCacheAdapter
from bench.engine.preflight import preflight
from bench.engine.schema_validation import SchemaValidationError, load_schema, validate
from bench.engine.scoring_core import MAX_SCORING_TEXT_CHARACTERS


ROOT = Path(__file__).resolve().parents[2]
V1_DATA_DIR = ROOT / "bench/data/public/s2"
V2_DATA_DIR = ROOT / "bench/data/v0.2/public/s2"
V2_SCHEMA_DIR = ROOT / "schemas/v0.2"
RAW_OUTPUTS = [
    "  Cafe\u0301\r\n",
    "👩\u200d💻\n",
    "尾随空白  ",
    "fourth raw output",
    "fifth raw output",
]


class RawSequenceAdapter(ModelAdapter):
    def __init__(self) -> None:
        super().__init__(
            model_id="raw-sequence",
            observation_mode="fixture",
            temperature=0.7,
        )

    def generate(
        self,
        prompt: str,
        item: dict[str, object],
        ladder_prompt: dict[str, object],
        *,
        seed: int,
        rerun_index: int,
    ) -> str:
        del prompt, item, ladder_prompt, seed
        return RAW_OUTPUTS[rerun_index]


class LiteralAdapter(ModelAdapter):
    def __init__(self, output: object) -> None:
        super().__init__(model_id="literal", observation_mode="fixture")
        self.output = output

    def generate(
        self,
        prompt: str,
        item: dict[str, object],
        ladder_prompt: dict[str, object],
        *,
        seed: int,
        rerun_index: int,
    ) -> str:
        del prompt, item, ladder_prompt, seed, rerun_index
        return self.output  # type: ignore[return-value]


class ProtocolV02Tests(unittest.TestCase):
    def test_huge_json_integer_validation_does_not_overflow(self) -> None:
        huge = 10**1000
        validate(huge, {"type": "integer"})
        with self.assertRaises(SchemaValidationError):
            validate(huge, {"type": "number", "maximum": 1})

        config = json.loads(
            (ROOT / "bench/config/frozen_ladder-v0.2.json").read_text(encoding="utf-8")
        )
        config["tau"] = huge
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.json"
            path.write_text(json.dumps(config), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "tau must be between"):
                load_protocol_config(path)

    def test_frozen_config_drift_fails_before_adapter_construction(self) -> None:
        config_path = ROOT / "bench/config/frozen_ladder-v0.2.json"
        canonical = json.loads(config_path.read_text(encoding="utf-8"))
        mutations = {
            "protocolVersion": "0.2.1",
            "track": "O",
            "split": "fresh",
            "stratum": "S3",
            "datasetId": "different-dataset",
            "datasetItemCount": 31,
            "datasetSha256": "0" * 64,
            "datasetHashAlgorithm": "different-algorithm",
            "tau": 0.9,
            "k": 17,
            "reruns": 6,
            "bootstrapSamples": 501,
        }
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for field, value in mutations.items():
                with self.subTest(field=field):
                    drifted = json.loads(json.dumps(canonical))
                    drifted[field] = value
                    path = root / f"{field}.json"
                    path.write_text(
                        json.dumps(drifted, indent=2) + "\n", encoding="utf-8"
                    )
                    with self.assertRaisesRegex(ValueError, "config bytes changed"):
                        load_protocol_config(path)

            for field, value in {
                "lcsRatio": 0.6,
                "targetTrigramRecall": 0.4,
                "verbatimSpanUnits": 15,
                "skeletonLcsRatio": 0.7,
                "skeletonTargetTrigramRecall": 0.7,
                "skeletonVerbatimSpanUnits": 31,
            }.items():
                with self.subTest(threshold=field):
                    drifted = json.loads(json.dumps(canonical))
                    drifted["leakageThresholds"][field] = value
                    path = root / f"threshold-{field}.json"
                    path.write_text(
                        json.dumps(drifted, indent=2) + "\n", encoding="utf-8"
                    )
                    with self.assertRaisesRegex(ValueError, "config bytes changed"):
                        load_protocol_config(path)

            drifted = json.loads(json.dumps(canonical))
            drifted["decoding"]["hosted"] += "; drifted=true"
            path = root / "runtime-drift.json"
            path.write_text(json.dumps(drifted, indent=2) + "\n", encoding="utf-8")
            with patch("bench.engine.protocol.PROTOCOL_CONFIG_PATH", path):
                doctor = preflight(data_dir=V2_DATA_DIR, models=["mock-frontier"])
                self.assertEqual(doctor["status"], "blocked")
                self.assertTrue(
                    any("config bytes changed" in error for error in doctor["errors"])
                )
                with self.assertRaisesRegex(ValueError, "config bytes changed"):
                    build_manifest(
                        data_dir=V2_DATA_DIR,
                        models=["mock-frontier"],
                    )
                with patch("bench.engine.frozen_ladder.adapter_for_model") as adapter:
                    with self.assertRaisesRegex(ValueError, "config bytes changed"):
                        run_benchmark(
                            data_dir=V2_DATA_DIR,
                            models=["mock-frontier"],
                        )
                    adapter.assert_not_called()

            drifted = json.loads(json.dumps(canonical))
            drifted["unexpected"] = True
            path = root / "extra-key.json"
            path.write_text(json.dumps(drifted), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, r"unexpected=\['unexpected'\]"):
                load_protocol_config(path)

    def test_v0_2_result_and_items_validate_while_v0_1_is_rejected(self) -> None:
        v2_item = json.loads((V2_DATA_DIR / "s2-001.json").read_text(encoding="utf-8"))
        v1_item = json.loads((V1_DATA_DIR / "s2-001.json").read_text(encoding="utf-8"))
        v2_schema = load_schema(V2_SCHEMA_DIR / "aleph-bench-item.schema.json")
        v1_schema = load_schema(ROOT / "schemas/aleph-bench-item.schema.json")
        validate(v2_item, v2_schema)
        validate(v1_item, v1_schema)
        with self.assertRaises(SchemaValidationError):
            validate(v1_item, v2_schema)
        with self.assertRaises(SchemaValidationError):
            validate(v2_item, v1_schema)
        with self.assertRaisesRegex(ValueError, "rejected dataset item"):
            load_items(V1_DATA_DIR, limit=1)

        result = run_benchmark(
            data_dir=V2_DATA_DIR,
            models=["mock-frontier"],
            limit=2,
        )
        self.assertEqual(result["protocolVersion"], PROTOCOL_VERSION)
        result_schema = load_schema(V2_SCHEMA_DIR / "aleph-bench-result.schema.json")
        validate(result, result_schema)
        self.assertEqual(result["evaluationScope"], "smoke")
        self.assertEqual(result["requestedItemLimit"], 2)
        self.assertEqual(result["evaluatedItemCount"], 2)
        self.assertIn("-smoke-2-", result["id"])

        mislabeled = json.loads(json.dumps(result))
        mislabeled["evaluationScope"] = "canonical"
        with self.assertRaises(SchemaValidationError):
            validate(mislabeled, result_schema)
        with self.assertRaisesRegex(ValueError, "exceeds the available dataset size"):
            run_benchmark(
                data_dir=V2_DATA_DIR,
                models=["mock-frontier"],
                limit=FROZEN_DATASET_ITEM_COUNT + 1,
            )

    def test_artifact_ids_cover_content_and_model_order_is_canonical(self) -> None:
        frontier = run_benchmark(
            data_dir=V2_DATA_DIR,
            models=["mock-frontier"],
            seed=0,
            limit=1,
        )
        small = run_benchmark(
            data_dir=V2_DATA_DIR,
            models=["mock-small"],
            seed=0,
            limit=1,
        )
        reseeded = run_benchmark(
            data_dir=V2_DATA_DIR,
            models=["mock-frontier"],
            seed=1,
            limit=1,
        )
        self.assertNotEqual(frontier["id"], small["id"])
        self.assertNotEqual(frontier["id"], reseeded["id"])
        self.assertNotEqual(
            frontier["itemRuns"][0]["alephRun"]["id"],
            reseeded["itemRuns"][0]["alephRun"]["id"],
        )

        ordered = build_manifest(
            data_dir=V2_DATA_DIR,
            models=["mock-frontier", "mock-small"],
        )
        reversed_order = build_manifest(
            data_dir=V2_DATA_DIR,
            models=["mock-small", "mock-frontier"],
        )
        self.assertEqual(ordered, reversed_order)

        with patch.dict(
            os.environ,
            {
                "ALEPH_CUSTOM_API_BASE_URL": "https://example.invalid/v1",
                "ALEPH_CUSTOM_API_KEY": "fixture-key",
                "ALEPH_CUSTOM_API_DEPLOYMENT_ID": "fixture-deployment",
                "ALEPH_CUSTOM_API_MAX_RETRIES": "0",
            },
            clear=True,
        ):
            no_retry = build_manifest(
                data_dir=V2_DATA_DIR,
                models=["hosted:fixture-model"],
            )
        with patch.dict(
            os.environ,
            {
                "ALEPH_CUSTOM_API_BASE_URL": "https://example.invalid/v1",
                "ALEPH_CUSTOM_API_KEY": "fixture-key",
                "ALEPH_CUSTOM_API_DEPLOYMENT_ID": "fixture-deployment",
                "ALEPH_CUSTOM_API_MAX_RETRIES": "5",
            },
            clear=True,
        ):
            five_retries = build_manifest(
                data_dir=V2_DATA_DIR,
                models=["hosted:fixture-model"],
            )
        self.assertNotEqual(no_retry["id"], five_retries["id"])

    def test_loader_rejects_mixed_versions_and_unknown_metrics_before_limit(self) -> None:
        valid = json.loads((V2_DATA_DIR / "s2-001.json").read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp)
            (data_dir / "s2-001.json").write_text(
                json.dumps(valid), encoding="utf-8"
            )
            mixed = dict(valid)
            mixed["id"] = "s2-002"
            mixed.pop("protocolVersion")
            (data_dir / "s2-002.json").write_text(
                json.dumps(mixed), encoding="utf-8"
            )
            with self.assertRaisesRegex(ValueError, "rejected dataset item"):
                load_items(data_dir, limit=1)

            mixed["protocolVersion"] = PROTOCOL_VERSION
            mixed["metricClass"] = "semantic"
            (data_dir / "s2-002.json").write_text(
                json.dumps(mixed), encoding="utf-8"
            )
            with self.assertRaisesRegex(ValueError, "unsupported metric class"):
                load_items(data_dir, limit=1)

            mixed["metricClass"] = "normalized_edit_similarity"
            mixed["target"] = {"text": "\u200d", "label": "empty after normalization"}
            (data_dir / "s2-002.json").write_text(
                json.dumps(mixed), encoding="utf-8"
            )
            with self.assertRaisesRegex(ValueError, "empty after leakage normalization"):
                load_items(data_dir, limit=1)

    def test_hosted_adapter_preserves_raw_string_and_rejects_non_string(self) -> None:
        adapter = HostedBlackBoxAdapter(
            "fixture-model",
            base_url="https://invalid.example",
            api_key="fixture-key",
            deployment_id="fixture-deployment",
            max_retries=0,
        )
        raw = " \tCafe\u0301\r\n👩\u200d💻  "
        with patch.object(
            adapter,
            "_post_chat_completion",
            return_value={"choices": [{"message": {"content": raw}}]},
        ):
            observed = adapter.generate(
                "prompt",
                {"target": {"text": "target"}},
                {"id": "prompt-1"},
                seed=0,
                rerun_index=0,
            )
        self.assertEqual(observed, raw)

        with patch.object(
            adapter,
            "_post_chat_completion",
            return_value={"choices": [{"message": {"content": None}}]},
        ):
            with self.assertRaisesRegex(HostedBlackBoxError, "must be a string"):
                adapter.generate(
                    "prompt",
                    {"target": {"text": "target"}},
                    {"id": "prompt-1"},
                    seed=0,
                    rerun_index=0,
                )

        with patch.object(
            adapter,
            "_post_chat_completion",
            return_value={
                "choices": [
                    {
                        "message": {
                            "content": "x" * (MAX_SCORING_TEXT_CHARACTERS + 1)
                        }
                    }
                ]
            },
        ):
            with self.assertRaisesRegex(HostedBlackBoxError, "exceeded"):
                adapter.generate(
                    "prompt",
                    {"target": {"text": "target"}},
                    {"id": "prompt-1"},
                    seed=0,
                    rerun_index=0,
                )

    def test_response_cache_round_trips_raw_output_and_versions_identity(self) -> None:
        raw = "  Cafe\u0301\r\n👩\u200d💻  "
        item = json.loads((V2_DATA_DIR / "s2-001.json").read_text(encoding="utf-8"))
        ladder = item["frozenLadder"][2]
        with tempfile.TemporaryDirectory() as tmp:
            cache_dir = Path(tmp) / "cache"
            first = ResponseCacheAdapter(LiteralAdapter(raw), cache_dir, seed=7)
            observed = first.generate(
                ladder["prompt"], item, ladder, seed=7, rerun_index=0
            )
            self.assertEqual(observed, raw)
            cache_files = list(cache_dir.rglob("*.json"))
            self.assertEqual(len(cache_files), 1)
            record = json.loads(cache_files[0].read_text(encoding="utf-8"))
            self.assertEqual(record["output"], raw)
            self.assertEqual(record["protocolVersion"], PROTOCOL_VERSION)
            self.assertEqual(record["responseCaptureVersion"], RESPONSE_CAPTURE_VERSION)

            cached = ResponseCacheAdapter(LiteralAdapter("different"), cache_dir, seed=7)
            self.assertEqual(
                cached.generate(ladder["prompt"], item, ladder, seed=7, rerun_index=0),
                raw,
            )
            self.assertEqual(cached.cache_hits, 1)

    def test_response_cache_does_not_cross_hosted_transport_policies(self) -> None:
        item = json.loads((V2_DATA_DIR / "s2-001.json").read_text(encoding="utf-8"))
        ladder = item["frozenLadder"][2]
        with tempfile.TemporaryDirectory() as tmp:
            cache_dir = Path(tmp) / "cache"
            first_hosted = HostedBlackBoxAdapter(
                "fixture-model",
                base_url="https://example.invalid/v1",
                api_key="fixture-key",
                deployment_id="fixture-deployment",
                max_retries=2,
                retry_delay_seconds=1,
            )
            first = ResponseCacheAdapter(first_hosted, cache_dir, seed=7)
            with patch.object(
                first_hosted,
                "_post_chat_completion",
                return_value={"choices": [{"message": {"content": "first"}}]},
            ):
                self.assertEqual(
                    first.generate(
                        ladder["prompt"], item, ladder, seed=7, rerun_index=0
                    ),
                    "first",
                )

            changed_hosted = HostedBlackBoxAdapter(
                "fixture-model",
                base_url="https://example.invalid/v1",
                api_key="fixture-key",
                deployment_id="fixture-deployment",
                max_retries=5,
                retry_delay_seconds=1,
            )
            changed = ResponseCacheAdapter(changed_hosted, cache_dir, seed=7)
            with patch.object(
                changed_hosted,
                "_post_chat_completion",
                return_value={"choices": [{"message": {"content": "second"}}]},
            ) as post:
                self.assertEqual(
                    changed.generate(
                        ladder["prompt"], item, ladder, seed=7, rerun_index=0
                    ),
                    "second",
                )
                post.assert_called_once()
            self.assertEqual(changed.cache_hits, 0)
            self.assertEqual(changed.cache_misses, 1)

    def test_response_cache_rejects_symlink_entries_without_overwriting_target(self) -> None:
        item = json.loads((V2_DATA_DIR / "s2-001.json").read_text(encoding="utf-8"))
        ladder = item["frozenLadder"][2]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cache = ResponseCacheAdapter(LiteralAdapter("new output"), root / "cache", seed=7)
            identity = cache._request_identity(
                ladder["prompt"], item, ladder, seed=7, rerun_index=0
            )
            entry = cache._path_for_key(cache._cache_key(identity))
            entry.parent.mkdir(parents=True)
            cache.cache_dir.chmod(0o700)
            entry.parent.chmod(0o700)
            victim = root / "victim.txt"
            victim.write_text("preserve\n", encoding="utf-8")
            entry.symlink_to(victim)

            with self.assertRaisesRegex(ValueError, "regular file, not a link"):
                cache.generate(
                    ladder["prompt"], item, ladder, seed=7, rerun_index=0
                )
            self.assertEqual(victim.read_text(encoding="utf-8"), "preserve\n")

    def test_response_cache_uses_private_regular_files(self) -> None:
        item = json.loads((V2_DATA_DIR / "s2-001.json").read_text(encoding="utf-8"))
        ladder = item["frozenLadder"][2]
        with tempfile.TemporaryDirectory() as tmp:
            cache_dir = Path(tmp) / "cache"
            cache = ResponseCacheAdapter(LiteralAdapter("output"), cache_dir, seed=7)
            cache.generate(ladder["prompt"], item, ladder, seed=7, rerun_index=0)
            self.assertEqual(stat.S_IMODE(cache_dir.stat().st_mode), 0o700)
            for directory in (path for path in cache_dir.rglob("*") if path.is_dir()):
                self.assertEqual(stat.S_IMODE(directory.stat().st_mode), 0o700)
            for path in (path for path in cache_dir.rglob("*") if path.is_file()):
                self.assertFalse(path.is_symlink())
                self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)

    def test_response_cache_rejects_oversized_records_before_json_parse(self) -> None:
        item = json.loads((V2_DATA_DIR / "s2-001.json").read_text(encoding="utf-8"))
        ladder = item["frozenLadder"][2]
        with tempfile.TemporaryDirectory() as tmp:
            cache = ResponseCacheAdapter(
                LiteralAdapter("new output"), Path(tmp) / "cache", seed=7
            )
            identity = cache._request_identity(
                ladder["prompt"], item, ladder, seed=7, rerun_index=0
            )
            entry = cache._path_for_key(cache._cache_key(identity))
            entry.parent.mkdir(mode=0o700, parents=True)
            cache.cache_dir.chmod(0o700)
            entry.parent.chmod(0o700)
            entry.write_bytes(b" " * (MAX_CACHE_RECORD_BYTES + 1))
            entry.chmod(0o600)

            with self.assertRaisesRegex(ValueError, "cache entry exceeds"):
                cache.generate(
                    ladder["prompt"], item, ladder, seed=7, rerun_index=0
                )

    def test_response_cache_refuses_existing_shared_directory_without_chmod(self) -> None:
        item = json.loads((V2_DATA_DIR / "s2-001.json").read_text(encoding="utf-8"))
        ladder = item["frozenLadder"][2]
        with tempfile.TemporaryDirectory() as tmp:
            shared = Path(tmp) / "shared"
            shared.mkdir(mode=0o755)
            shared.chmod(0o755)
            cache = ResponseCacheAdapter(LiteralAdapter("output"), shared, seed=7)

            with self.assertRaisesRegex(ValueError, "must have mode 0700"):
                cache.generate(
                    ladder["prompt"], item, ladder, seed=7, rerun_index=0
                )

            self.assertEqual(stat.S_IMODE(shared.stat().st_mode), 0o755)
            self.assertEqual(list(shared.iterdir()), [])

    def test_response_cache_refuses_symlinked_ancestor(self) -> None:
        item = json.loads((V2_DATA_DIR / "s2-001.json").read_text(encoding="utf-8"))
        ladder = item["frozenLadder"][2]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            real_parent = root / "real"
            real_parent.mkdir(mode=0o700)
            linked_parent = root / "linked"
            linked_parent.symlink_to(real_parent, target_is_directory=True)
            cache = ResponseCacheAdapter(
                LiteralAdapter("output"), linked_parent / "cache", seed=7
            )

            with self.assertRaisesRegex(ValueError, "path component"):
                cache.generate(
                    ladder["prompt"], item, ladder, seed=7, rerun_index=0
                )

            self.assertFalse((real_parent / "cache").exists())

    def test_measurements_retain_every_raw_rerun(self) -> None:
        item = json.loads((V2_DATA_DIR / "s2-001.json").read_text(encoding="utf-8"))
        run = evaluate_item(item, RawSequenceAdapter(), seed=0)
        gated = [row for row in run["measurements"] if row["disqualified"]]
        scored = [row for row in run["measurements"] if not row["disqualified"]]
        self.assertTrue(all(row["outputs"] == [] for row in gated))
        self.assertTrue(all(row["outputs"] == RAW_OUTPUTS for row in scored))
        self.assertTrue(all(row["rerunCount"] == 5 for row in scored))

    def test_aleph_run_budget_and_decoding_match_candidates(self) -> None:
        result = run_benchmark(
            data_dir=V2_DATA_DIR,
            models=["mock-frontier"],
            seed=23,
        )
        for item_run in result["itemRuns"]:
            aleph_run = item_run["alephRun"]
            tokens = [candidate["tokens"] for candidate in aleph_run["candidates"]]
            self.assertEqual(
                aleph_run["config"]["budget"]["maxPromptTokens"],
                max(tokens),
            )
            self.assertTrue(
                all(
                    token <= aleph_run["config"]["budget"]["maxPromptTokens"]
                    for token in tokens
                )
            )
            self.assertEqual(aleph_run["config"]["decoding"], "temperature=0")

    def test_non_string_adapter_output_fails_before_scoring(self) -> None:
        item = json.loads((V2_DATA_DIR / "s2-001.json").read_text(encoding="utf-8"))
        with self.assertRaisesRegex(TypeError, "non-string output"):
            evaluate_item(item, LiteralAdapter(7), seed=0)

    def test_v0_2_package_is_deterministic_and_runs_shared_conformance(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            first = Path(tmp) / "first"
            second = Path(tmp) / "second"
            first_manifest = write_v0_2_package(first)
            second_manifest = write_v0_2_package(second)
            self.assertEqual(first_manifest, second_manifest)
            self.assertEqual(first_manifest["datasetId"], FROZEN_DATASET_ID)
            self.assertEqual(
                first_manifest["datasetItemCount"], FROZEN_DATASET_ITEM_COUNT
            )
            self.assertEqual(
                first_manifest["datasetSha256"], FROZEN_DATASET_SHA256
            )
            self.assertEqual(
                first_manifest["datasetHashAlgorithm"],
                FROZEN_DATASET_HASH_ALGORITHM,
            )
            validate(
                first_manifest,
                load_schema(V2_SCHEMA_DIR / "aleph-bench-platform-package.schema.json"),
            )
            self.assertEqual(
                (first / "package-manifest.json").read_bytes(),
                (json.dumps(first_manifest, indent=2, sort_keys=True) + "\n").encode(
                    "utf-8"
                ),
            )
            self.assertEqual(
                (first / "kaggle/_scoring.py").read_bytes(),
                (ROOT / "bench/engine/scoring_core.py").read_bytes(),
            )
            first_files = {
                path.relative_to(first).as_posix(): path.read_bytes()
                for path in first.rglob("*")
                if path.is_file()
            }
            second_files = {
                path.relative_to(second).as_posix(): path.read_bytes()
                for path in second.rglob("*")
                if path.is_file()
            }
            self.assertEqual(first_files, second_files)
            for directory in [first, *(path for path in first.rglob("*") if path.is_dir())]:
                self.assertEqual(stat.S_IMODE(directory.stat().st_mode), 0o755)
            for path in (path for path in first.rglob("*") if path.is_file()):
                expected_mode = (
                    0o755
                    if path.relative_to(first).as_posix() == "kaggle/run_conformance.py"
                    else 0o644
                )
                self.assertEqual(stat.S_IMODE(path.stat().st_mode), expected_mode)
            self.assertEqual(
                check_v0_2_package(first / "package-manifest.json")["status"],
                "ok",
            )
            completed = subprocess.run(
                [sys.executable, str(first / "kaggle/run_conformance.py")],
                check=True,
                capture_output=True,
                text=True,
            )
            report = json.loads(completed.stdout)
            self.assertEqual(report["status"], "ok")
            self.assertEqual(report["fidelityChecks"], 42)
            self.assertEqual(report["leakageChecks"], 28)
            self.assertEqual(report["unsupportedMetricChecks"], 4)

            (first / "unexpected.txt").write_text("unexpected\n", encoding="utf-8")
            tampered = check_v0_2_package(first / "package-manifest.json")
            self.assertEqual(tampered["status"], "failed")
            self.assertIn("unexpected package file: unexpected.txt", tampered["errors"])

    def test_v0_2_package_requires_canonical_dataset_before_writing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            copied_data = Path(tmp) / "data"
            shutil.copytree(V2_DATA_DIR, copied_data)
            item_path = copied_data / "s2-001.json"
            item_path.write_bytes(item_path.read_bytes() + b"\n")
            destination = Path(tmp) / "package"
            with patch(
                "bench.engine.platform_package_v0_2.ITEMS_SOURCE_DIR", copied_data
            ):
                with self.assertRaisesRegex(ValueError, "does not match frozen"):
                    write_v0_2_package(destination)
            self.assertFalse(destination.exists())

    def test_v0_2_package_rejects_existing_destination_without_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            destination = Path(tmp) / "package"
            destination.mkdir()
            sentinel = destination / "sentinel.txt"
            sentinel.write_text("preserve\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "must not already exist"):
                write_v0_2_package(destination)
            self.assertEqual(sentinel.read_text(encoding="utf-8"), "preserve\n")

            broken_link = Path(tmp) / "broken-link"
            broken_link.symlink_to(Path(tmp) / "missing-target", target_is_directory=True)
            with self.assertRaisesRegex(ValueError, "must not already exist"):
                write_v0_2_package(broken_link)
            self.assertTrue(broken_link.is_symlink())

    def test_v0_2_package_checker_enforces_canonical_manifest_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            package = Path(tmp) / "package"
            manifest = write_v0_2_package(package)
            (package / "package-manifest.json").write_text(
                json.dumps(manifest, separators=(",", ":")) + "\n",
                encoding="utf-8",
            )
            report = check_v0_2_package(package / "package-manifest.json")
            self.assertEqual(report["status"], "failed")
            self.assertIn(
                "package-manifest.json is not canonical deterministic JSON",
                report["errors"],
            )

    def test_v0_2_package_checker_rejects_non_closed_world_entries(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)

            extra_dir_package = root / "extra-dir"
            write_v0_2_package(extra_dir_package)
            (extra_dir_package / "unexpected").mkdir()
            report = check_v0_2_package(
                extra_dir_package / "package-manifest.json"
            )
            self.assertIn("unexpected package directory: unexpected", report["errors"])

            symlink_package = root / "symlink-entry"
            write_v0_2_package(symlink_package)
            (symlink_package / "unexpected-link").symlink_to("README.md")
            report = check_v0_2_package(symlink_package / "package-manifest.json")
            self.assertIn(
                "unexpected package symlink: unexpected-link", report["errors"]
            )

            fifo_package = root / "fifo-entry"
            write_v0_2_package(fifo_package)
            os.mkfifo(fifo_package / "unexpected-fifo", 0o644)
            report = check_v0_2_package(fifo_package / "package-manifest.json")
            self.assertIn(
                "unexpected package non-regular entry: unexpected-fifo",
                report["errors"],
            )

            target_package = root / "target"
            write_v0_2_package(target_package)
            linked_package = root / "linked-root"
            linked_package.symlink_to(target_package, target_is_directory=True)
            report = check_v0_2_package(linked_package / "package-manifest.json")
            self.assertIn("package root must not be a symlink", report["errors"])

            hardlink_package = root / "hardlink-entry"
            write_v0_2_package(hardlink_package)
            outside = root / "outside-readme"
            readme = hardlink_package / "README.md"
            outside.write_bytes(readme.read_bytes())
            readme.unlink()
            os.link(outside, readme)
            report = check_v0_2_package(
                hardlink_package / "package-manifest.json"
            )
            self.assertIn(
                "package file link count mismatch: README.md expected 1, found 2",
                report["errors"],
            )

    def test_v0_2_package_checker_enforces_exact_modes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            package = Path(tmp) / "package"
            write_v0_2_package(package)
            package.chmod(0o700)
            (package / "README.md").chmod(0o600)
            (package / "schemas").chmod(0o700)
            (package / "kaggle/run_conformance.py").chmod(0o644)
            report = check_v0_2_package(package / "package-manifest.json")
            self.assertIn(
                "package directory mode mismatch: . expected 0755, found 0700",
                report["errors"],
            )
            self.assertIn(
                "package file mode mismatch: README.md expected 0644, found 0600",
                report["errors"],
            )
            self.assertIn(
                "package directory mode mismatch: schemas expected 0755, found 0700",
                report["errors"],
            )
            self.assertIn(
                "package file mode mismatch: kaggle/run_conformance.py expected 0755, found 0644",
                report["errors"],
            )

    def test_packaged_conformance_rejects_bool_nonfinite_and_field_drift(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source_fixture = json.loads(
                (ROOT / "bench/conformance/scorer-v0.2.json").read_text(
                    encoding="utf-8"
                )
            )

            cases = {
                "bool": lambda fixture: fixture["fidelityVectors"][0]["expected"].__setitem__(
                    "exact", False
                ),
                "nonfinite": lambda fixture: fixture["fidelityVectors"][0][
                    "expected"
                ].__setitem__("normalized_edit_similarity", float("nan")),
                "field-drift": lambda fixture: fixture["leakageVectors"][0][
                    "expected"
                ].pop("unit"),
            }
            for name, mutate in cases.items():
                with self.subTest(name=name):
                    package = root / name
                    write_v0_2_package(package)
                    fixture = json.loads(json.dumps(source_fixture))
                    mutate(fixture)
                    (package / "conformance/scorer-v0.2.json").write_text(
                        json.dumps(fixture, indent=2, sort_keys=True) + "\n",
                        encoding="utf-8",
                    )
                    completed = subprocess.run(
                        [sys.executable, str(package / "kaggle/run_conformance.py")],
                        check=False,
                        capture_output=True,
                        text=True,
                    )
                    self.assertEqual(completed.returncode, 1)
                    report = json.loads(completed.stdout)
                    self.assertEqual(report["status"], "failed")
                    self.assertTrue(report["errors"])


if __name__ == "__main__":
    unittest.main()
