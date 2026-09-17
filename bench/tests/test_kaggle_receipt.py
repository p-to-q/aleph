from __future__ import annotations

import copy
import io
import json
import math
import os
import shutil
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from bench.engine.kaggle_receipt import (
    AUDITED_PACKAGE_MANIFEST_SHA256,
    AUDITED_PACKAGE_TREE_SHA256,
    AUDITED_TASK_DESCRIPTION,
    DEFAULT_V0_1_PACKAGE_ROOT,
    KaggleReceiptError,
    MAX_OUTPUT_CODEPOINTS,
    MAX_RUN_JSON_BYTES,
    MAX_TOTAL_OUTPUT_CODEPOINTS,
    _identity_json_bytes,
    _load_legacy_score_function,
    _load_package_context,
    _sha256,
    build_kaggle_receipt,
    canonical_json_bytes,
    capture_kaggle_package_root_identity,
    parse_run_conversations,
    serialize_kaggle_receipt,
    validate_kaggle_replay_output_path,
    write_new_kaggle_receipt,
)
from bench.engine.legacy_v0_1 import verify_v0_1_repository_receipt
from bench.engine.schema_validation import load_schema, validate
from bench.run import main as bench_main


ROOT = Path(__file__).resolve().parents[2]
FIXTURE_PATH = ROOT / "bench/tests/fixtures/kaggle/minimal-run.json"
AUDITED_TASK_DEFINITION_PATH = (
    ROOT / "bench/tests/fixtures/kaggle/audited-v16-task-definition.txt"
)
SCHEMA_PATH = ROOT / "schemas/v0.2/aleph-bench-kaggle-receipt.schema.json"
FIXTURE_MODEL_SLUG = "fixture/model"


def _load_fixture() -> dict:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def _fixture_expected_prompts() -> list[dict[str, str]]:
    return [
        {
            "item_id": "s2-001",
            "prompt_id": "s2-001-r1-p0",
            "prompt": "fixture prompt",
        }
    ]


def _resign_receipt(receipt: dict) -> None:
    payload = {key: value for key, value in receipt.items() if key != "id"}
    receipt["id"] = (
        "aleph-bench-kaggle-receipt-v0.2-artifact-"
        + _sha256(_identity_json_bytes(payload))
    )


def _conversation(
    *,
    item_id: str,
    prompt_id: str,
    prompt: str,
    output: str,
    index: int,
    output_tokens: int = 12,
) -> dict:
    base = f"{item_id}:{prompt_id}"
    conversation_id = f"{base}-{index:08x}"
    metrics = {
        "inputTokens": 8,
        "outputTokens": output_tokens,
        "inputTokensCostNanodollars": "0",
        "outputTokensCostNanodollars": "0",
        "totalBackendLatencyMs": "1",
    }
    return {
        "id": conversation_id,
        "requests": [
            {
                "contents": [
                    {
                        "parts": [{"text": prompt}],
                        "role": "CONTENT_ROLE_USER",
                        "senderName": "User",
                    },
                    {
                        "parts": [{"text": output}],
                        "role": "CONTENT_ROLE_ASSISTANT",
                        "senderName": "fixture/model",
                    },
                ],
                "metrics": metrics,
                "id": f"{conversation_id}-req-1",
            }
        ],
        "metrics": metrics,
        "modelVersionSlug": "model_version_slug for conversation is DEPRECATED",
    }


def _full_run(*, empty_first: bool = False) -> dict:
    package = _load_package_context(DEFAULT_V0_1_PACKAGE_ROOT)
    outputs: list[dict[str, str]] = []
    conversations = [
        {
            "id": "aleph_bench_frozen_ladder-00000000",
            "metrics": {},
            "modelVersionSlug": "model_version_slug for conversation is DEPRECATED",
        }
    ]
    for index, prompt in enumerate(package["sendable"], start=1):
        output = "" if empty_first and index == 1 else f"\nfixture output {index} 🧪\n"
        conversations.append(
            _conversation(
                item_id=prompt["item_id"],
                prompt_id=prompt["prompt_id"],
                prompt=prompt["prompt"],
                output=output,
                index=index,
            )
        )
        outputs.append(
            {
                "row_id": f"{prompt['item_id']}:{prompt['prompt_id']}",
                "model_id": "fixture/model",
                "item_id": prompt["item_id"],
                "prompt_id": prompt["prompt_id"],
                "output_text": output,
            }
        )
    scorer = _load_legacy_score_function(
        scoring_source=package["scoringSource"],
        score_outputs_source=package["scoreSource"],
        item_rows=package["items"],
        prompt_rows=package["prompts"],
    )
    result = scorer(
        items_path="data/public_s2_items.jsonl",
        prompts_path="data/public_s2_prompts.jsonl",
        submission_rows=outputs,
        model_id="fixture/model",
    )
    scalar = 1.0 - float(result["aggregate"]["aurc"])
    return {
        "conversations": conversations,
        "endTime": "2026-09-17T02:29:26.183094Z",
        "modelVersion": {"slug": "fixture/model"},
        "pyRunId": "aleph_bench_frozen_ladder-Run #fixture",
        "results": [
            {"type": "AGGREGATED", "numericResult": {"value": scalar}}
        ],
        "startTime": "2026-09-17T02:20:17.314234Z",
        "state": "BENCHMARK_TASK_RUN_STATE_COMPLETED",
        "taskVersion": {
            "versionNumber": 3,
            "name": "aleph_bench_frozen_ladder",
            "description": AUDITED_TASK_DESCRIPTION,
            "definition": AUDITED_TASK_DEFINITION_PATH.read_text(encoding="utf-8"),
        },
    }


class KaggleConversationParserTests(unittest.TestCase):
    def test_minimal_fixture_preserves_raw_unicode_and_whitespace(self) -> None:
        run = _load_fixture()
        rows, diagnostics = parse_run_conversations(
            run,
            expected_prompts=_fixture_expected_prompts(),
            model_slug=FIXTURE_MODEL_SLUG,
            max_tokens=32,
        )
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["outputText"], "\n Café 🧪 \n")
        self.assertEqual(rows[0]["promptText"], "fixture prompt")
        self.assertEqual(rows[0]["conversationId"], "s2-001:s2-001-r1-p0-9a1370ab")
        self.assertEqual(diagnostics["status"], "valid")
        self.assertEqual(diagnostics["emptyRowIds"], [])
        self.assertEqual(diagnostics["invalidUsageRowIds"], [])

    def test_duplicate_conversation_fails_closed(self) -> None:
        run = _load_fixture()
        run["conversations"].append(copy.deepcopy(run["conversations"][1]))
        with self.assertRaisesRegex(KaggleReceiptError, "duplicate response"):
            parse_run_conversations(
                run,
                expected_prompts=_fixture_expected_prompts(),
                model_slug=FIXTURE_MODEL_SLUG,
                max_tokens=32,
            )

    def test_missing_conversation_fails_closed(self) -> None:
        run = _load_fixture()
        run["conversations"] = run["conversations"][:1]
        with self.assertRaisesRegex(KaggleReceiptError, "coverage mismatch"):
            parse_run_conversations(
                run,
                expected_prompts=_fixture_expected_prompts(),
                model_slug=FIXTURE_MODEL_SLUG,
                max_tokens=32,
            )

    def test_non_string_assistant_output_fails_closed(self) -> None:
        run = _load_fixture()
        run["conversations"][1]["requests"][0]["contents"][1]["parts"][0][
            "text"
        ] = {"not": "a string"}
        with self.assertRaisesRegex(KaggleReceiptError, r"contents\[1\] text must be a string"):
            parse_run_conversations(
                run,
                expected_prompts=_fixture_expected_prompts(),
                model_slug=FIXTURE_MODEL_SLUG,
                max_tokens=32,
            )

    def test_empty_and_near_cap_outputs_are_blocked_but_retained(self) -> None:
        run = _load_fixture()
        request = run["conversations"][1]["requests"][0]
        request["contents"][1]["parts"][0]["text"] = " \n\t"
        request["metrics"]["outputTokens"] = 28
        run["conversations"][1]["metrics"]["outputTokens"] = 28
        rows, diagnostics = parse_run_conversations(
            run,
            expected_prompts=_fixture_expected_prompts(),
            model_slug=FIXTURE_MODEL_SLUG,
            max_tokens=32,
            saturation_margin_tokens=4,
        )
        self.assertEqual(rows[0]["outputText"], " \n\t")
        self.assertEqual(diagnostics["status"], "blocked")
        self.assertEqual(diagnostics["emptyRowIds"], [rows[0]["rowId"]])
        self.assertEqual(diagnostics["nearCapRowIds"], [rows[0]["rowId"]])

    def test_invalid_saturation_configuration_fails_closed(self) -> None:
        with self.assertRaisesRegex(KaggleReceiptError, "smaller than max_tokens"):
            parse_run_conversations(
                _load_fixture(),
                expected_prompts=_fixture_expected_prompts(),
                model_slug=FIXTURE_MODEL_SLUG,
                max_tokens=4,
                saturation_margin_tokens=4,
            )

    def test_extra_system_content_fails_closed(self) -> None:
        run = _load_fixture()
        run["conversations"][1]["requests"][0]["contents"].insert(
            1,
            {
                "parts": [{"text": "unexpected"}],
                "role": "CONTENT_ROLE_SYSTEM",
                "senderName": "System",
            },
        )
        with self.assertRaisesRegex(KaggleReceiptError, "audited two-message exchange"):
            parse_run_conversations(
                run,
                expected_prompts=_fixture_expected_prompts(),
                model_slug=FIXTURE_MODEL_SLUG,
                max_tokens=32,
            )

    def test_assistant_sender_must_match_top_level_model(self) -> None:
        run = _load_fixture()
        run["conversations"][1]["requests"][0]["contents"][1]["senderName"] = (
            "fixture/other-model"
        )
        with self.assertRaisesRegex(KaggleReceiptError, "identity drifted"):
            parse_run_conversations(
                run,
                expected_prompts=_fixture_expected_prompts(),
                model_slug=FIXTURE_MODEL_SLUG,
                max_tokens=32,
            )

    def test_request_and_placeholder_shapes_are_exact(self) -> None:
        request_drift = _load_fixture()
        request_drift["conversations"][1]["requests"][0]["unexpected"] = True
        with self.assertRaisesRegex(KaggleReceiptError, "request fields drifted"):
            parse_run_conversations(
                request_drift,
                expected_prompts=_fixture_expected_prompts(),
                model_slug=FIXTURE_MODEL_SLUG,
                max_tokens=32,
            )

        placeholder_drift = _load_fixture()
        placeholder_drift["conversations"][0]["metrics"] = {"unexpected": 1}
        with self.assertRaisesRegex(KaggleReceiptError, "unexpected request-less"):
            parse_run_conversations(
                placeholder_drift,
                expected_prompts=_fixture_expected_prompts(),
                model_slug=FIXTURE_MODEL_SLUG,
                max_tokens=32,
            )

    def test_deprecated_model_marker_drift_fails_closed(self) -> None:
        run = _load_fixture()
        run["conversations"][1]["modelVersionSlug"] = "fixture/model"
        with self.assertRaisesRegex(KaggleReceiptError, "modelVersionSlug marker drifted"):
            parse_run_conversations(
                run,
                expected_prompts=_fixture_expected_prompts(),
                model_slug=FIXTURE_MODEL_SLUG,
                max_tokens=32,
            )

    def test_zero_token_usage_is_blocked_and_retained(self) -> None:
        run = _load_fixture()
        request_metrics = run["conversations"][1]["requests"][0]["metrics"]
        conversation_metrics = run["conversations"][1]["metrics"]
        request_metrics["inputTokens"] = 0
        conversation_metrics["inputTokens"] = 0
        rows, diagnostics = parse_run_conversations(
            run,
            expected_prompts=_fixture_expected_prompts(),
            model_slug=FIXTURE_MODEL_SLUG,
            max_tokens=32,
        )
        self.assertEqual(rows[0]["usage"]["inputTokens"], 0)
        self.assertEqual(diagnostics["status"], "blocked")
        self.assertEqual(diagnostics["invalidUsageRowIds"], [rows[0]["rowId"]])

    def test_conversation_metrics_use_strict_types(self) -> None:
        run = _load_fixture()
        run["conversations"][1]["metrics"]["inputTokens"] = True
        with self.assertRaisesRegex(KaggleReceiptError, "inputTokens must be an integer"):
            parse_run_conversations(
                run,
                expected_prompts=_fixture_expected_prompts(),
                model_slug=FIXTURE_MODEL_SLUG,
                max_tokens=32,
            )


class KaggleReceiptIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.run_payload = _full_run()

    def _write_run(self, directory: str, run: dict | None = None) -> Path:
        path = Path(directory) / "run.json"
        path.write_text(
            json.dumps(self.run_payload if run is None else run, ensure_ascii=False),
            encoding="utf-8",
        )
        return path

    def test_full_receipt_is_schema_valid_content_addressed_and_stable(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            run_path = self._write_run(temporary_directory)
            first = build_kaggle_receipt(
                run_json_path=run_path,
                max_tokens=512,
            )
            second = build_kaggle_receipt(
                run_json_path=run_path,
                max_tokens=512,
            )
        validate(first, load_schema(SCHEMA_PATH))
        self.assertEqual(first, second)
        self.assertEqual(serialize_kaggle_receipt(first), serialize_kaggle_receipt(second))
        self.assertEqual(first["rowCount"], 180)
        self.assertEqual(first["diagnostics"]["status"], "valid")
        self.assertTrue(first["scalarMatches"])
        self.assertEqual(first["leaderboardScalar"], first["replayedScalar"])
        self.assertEqual(first["submissionRows"][0]["outputText"], "\nfixture output 1 🧪\n")
        reordered = dict(reversed(list(first.items())))
        self.assertEqual(serialize_kaggle_receipt(first), serialize_kaggle_receipt(reordered))
        self.assertEqual(canonical_json_bytes(first), serialize_kaggle_receipt(first))

    def test_supported_model_identity_is_content_addressed_and_cap_is_fixed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            run_path = self._write_run(temporary_directory)
            first = build_kaggle_receipt(run_json_path=run_path, max_tokens=512)
            changed_run = copy.deepcopy(self.run_payload)
            changed_run["modelVersion"]["slug"] = "fixture/other-model"
            for conversation in changed_run["conversations"]:
                if "requests" in conversation:
                    conversation["requests"][0]["contents"][1]["senderName"] = (
                        "fixture/other-model"
                    )
            changed_path = Path(temporary_directory) / "changed.json"
            changed_path.write_text(json.dumps(changed_run), encoding="utf-8")
            changed = build_kaggle_receipt(
                run_json_path=changed_path,
                max_tokens=512,
            )
            with self.assertRaisesRegex(KaggleReceiptError, "requires --max-tokens 512"):
                build_kaggle_receipt(run_json_path=run_path, max_tokens=1024)
            with self.assertRaisesRegex(
                KaggleReceiptError, "requires --saturation-margin-tokens 4"
            ):
                build_kaggle_receipt(
                    run_json_path=run_path,
                    max_tokens=512,
                    saturation_margin_tokens=0,
                )
        self.assertNotEqual(first["id"], changed["id"])
        self.assertEqual(
            first["operatorAssertions"]["maxTokensSource"],
            "operator_asserted_not_present_in_run_json",
        )
        self.assertEqual(first["operatorAssertions"]["maxTokens"], 512)
        self.assertEqual(first["operatorAssertions"]["saturationMarginTokens"], 4)
        self.assertEqual(
            first["datasetIdentity"]["packageManifestSha256"],
            AUDITED_PACKAGE_MANIFEST_SHA256,
        )
        self.assertEqual(
            first["datasetIdentity"]["referencePackageTreeSha256"],
            AUDITED_PACKAGE_TREE_SHA256,
        )

    def test_unsupported_task_identity_fails_closed(self) -> None:
        mutations = (
            ("name", "some_other_task"),
            ("versionNumber", 4),
            ("description", "Drifted task description."),
            (
                "definition",
                self.run_payload["taskVersion"]["definition"] + "# drift\n",
            ),
        )
        for field, value in mutations:
            with self.subTest(field=field):
                changed = copy.deepcopy(self.run_payload)
                changed["taskVersion"][field] = value
                with tempfile.TemporaryDirectory() as temporary_directory:
                    run_path = self._write_run(temporary_directory, changed)
                    with self.assertRaisesRegex(
                        KaggleReceiptError, "unsupported Kaggle task identity"
                    ):
                        build_kaggle_receipt(
                            run_json_path=run_path,
                            max_tokens=512,
                        )

    def test_scalar_mismatch_fails_closed(self) -> None:
        changed = copy.deepcopy(self.run_payload)
        changed["results"][0]["numericResult"]["value"] += 0.01
        with tempfile.TemporaryDirectory() as temporary_directory:
            run_path = self._write_run(temporary_directory, changed)
            with self.assertRaisesRegex(KaggleReceiptError, "does not match replayed"):
                build_kaggle_receipt(run_json_path=run_path, max_tokens=512)

    def test_non_finite_source_json_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            run_path = Path(temporary_directory) / "run.json"
            run_path.write_text('{"value": NaN}', encoding="utf-8")
            with self.assertRaisesRegex(KaggleReceiptError, "non-finite JSON"):
                build_kaggle_receipt(run_json_path=run_path, max_tokens=512)

    def test_duplicate_raw_json_key_fails_closed(self) -> None:
        raw = json.dumps(self.run_payload, ensure_ascii=False)
        duplicate = (
            '{"state":"BENCHMARK_TASK_RUN_STATE_COMPLETED",' + raw[1:]
        )
        with tempfile.TemporaryDirectory() as temporary_directory:
            run_path = Path(temporary_directory) / "run.json"
            run_path.write_text(duplicate, encoding="utf-8")
            with self.assertRaisesRegex(
                KaggleReceiptError, "duplicate JSON object key.*state"
            ):
                build_kaggle_receipt(run_json_path=run_path, max_tokens=512)

    def test_timestamps_must_be_valid_canonical_utc_and_ordered(self) -> None:
        cases = (
            ("2026-09-17T02:20:17+00:00", "canonical RFC 3339 UTC"),
            ("2026-09-17T02:20:17.1234567Z", "canonical RFC 3339 UTC"),
            ("2026-02-30T02:20:17Z", "not a valid UTC timestamp"),
        )
        for start_time, message in cases:
            with self.subTest(start_time=start_time):
                changed = copy.deepcopy(self.run_payload)
                changed["startTime"] = start_time
                with tempfile.TemporaryDirectory() as temporary_directory:
                    run_path = self._write_run(temporary_directory, changed)
                    with self.assertRaisesRegex(KaggleReceiptError, message):
                        build_kaggle_receipt(run_json_path=run_path, max_tokens=512)

        changed = copy.deepcopy(self.run_payload)
        changed["endTime"] = "2026-09-17T02:19:17Z"
        with tempfile.TemporaryDirectory() as temporary_directory:
            run_path = self._write_run(temporary_directory, changed)
            with self.assertRaisesRegex(KaggleReceiptError, "must not precede"):
                build_kaggle_receipt(run_json_path=run_path, max_tokens=512)

    def test_run_input_must_be_bounded_regular_file(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            oversized = Path(temporary_directory) / "oversized.run.json"
            with oversized.open("wb") as handle:
                handle.truncate(MAX_RUN_JSON_BYTES + 1)
            with self.assertRaisesRegex(KaggleReceiptError, "byte safety limit"):
                build_kaggle_receipt(run_json_path=oversized, max_tokens=512)

            symlink = Path(temporary_directory) / "run-link.json"
            target = self._write_run(temporary_directory)
            symlink.symlink_to(target)
            with self.assertRaisesRegex(KaggleReceiptError, "could not safely open"):
                build_kaggle_receipt(run_json_path=symlink, max_tokens=512)

            if hasattr(os, "mkfifo"):
                fifo = Path(temporary_directory) / "run.fifo"
                os.mkfifo(fifo)
                with self.assertRaisesRegex(KaggleReceiptError, "must be a regular file"):
                    build_kaggle_receipt(run_json_path=fifo, max_tokens=512)

    def test_output_text_safety_limits_fail_before_scoring(self) -> None:
        too_long = copy.deepcopy(self.run_payload)
        too_long["conversations"][1]["requests"][0]["contents"][1]["parts"][0][
            "text"
        ] = "x" * (MAX_OUTPUT_CODEPOINTS + 1)
        with tempfile.TemporaryDirectory() as temporary_directory:
            run_path = self._write_run(temporary_directory, too_long)
            with self.assertRaisesRegex(KaggleReceiptError, "output exceeds"):
                build_kaggle_receipt(run_json_path=run_path, max_tokens=512)

        aggregate_too_long = copy.deepcopy(self.run_payload)
        per_row = MAX_TOTAL_OUTPUT_CODEPOINTS // 180 + 1
        for conversation in aggregate_too_long["conversations"][1:]:
            conversation["requests"][0]["contents"][1]["parts"][0]["text"] = (
                "x" * per_row
            )
        with tempfile.TemporaryDirectory() as temporary_directory:
            run_path = self._write_run(temporary_directory, aggregate_too_long)
            with self.assertRaisesRegex(KaggleReceiptError, "aggregate safety limit"):
                build_kaggle_receipt(run_json_path=run_path, max_tokens=512)

    def test_non_finite_scalar_object_fails_closed(self) -> None:
        changed = copy.deepcopy(self.run_payload)
        changed["results"][0]["numericResult"]["value"] = math.inf
        with tempfile.TemporaryDirectory() as temporary_directory:
            run_path = self._write_run(temporary_directory, changed)
            with self.assertRaisesRegex(KaggleReceiptError, "non-finite JSON"):
                build_kaggle_receipt(run_json_path=run_path, max_tokens=512)

    def test_huge_integer_scalar_fails_cleanly(self) -> None:
        changed = copy.deepcopy(self.run_payload)
        changed["results"][0]["numericResult"]["value"] = 10**1_000
        with tempfile.TemporaryDirectory() as temporary_directory:
            run_path = self._write_run(temporary_directory, changed)
            with self.assertRaisesRegex(KaggleReceiptError, "must be finite"):
                build_kaggle_receipt(run_json_path=run_path, max_tokens=512)

    def test_resigned_cross_field_contradictions_fail_semantic_validation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            receipt = build_kaggle_receipt(
                run_json_path=self._write_run(temporary_directory),
                max_tokens=512,
            )

        scalar_drift = copy.deepcopy(receipt)
        scalar_drift["leaderboardScalar"] = 0.0
        scalar_drift["replayedScalar"] = 1.0
        _resign_receipt(scalar_drift)
        with self.assertRaisesRegex(KaggleReceiptError, "scalars disagree"):
            serialize_kaggle_receipt(scalar_drift)

        diagnostic_drift = copy.deepcopy(receipt)
        diagnostic_drift["diagnostics"]["emptyRowIds"] = [
            diagnostic_drift["submissionRows"][0]["rowId"]
        ]
        _resign_receipt(diagnostic_drift)
        with self.assertRaisesRegex(KaggleReceiptError, "diagnostics disagree"):
            serialize_kaggle_receipt(diagnostic_drift)

        output_drift = copy.deepcopy(receipt)
        package = _load_package_context(DEFAULT_V0_1_PACKAGE_ROOT)
        output_drift["submissionRows"][0]["outputText"] = package["items"][0][
            "target"
        ]["text"]
        _resign_receipt(output_drift)
        with self.assertRaisesRegex(KaggleReceiptError, "benchResult disagrees"):
            serialize_kaggle_receipt(output_drift)

        prompt_drift = copy.deepcopy(receipt)
        prompt_drift["submissionRows"][0]["promptText"] = "different prompt"
        _resign_receipt(prompt_drift)
        with self.assertRaisesRegex(KaggleReceiptError, "pinned prompt"):
            serialize_kaggle_receipt(prompt_drift)

        detail_drift = copy.deepcopy(receipt)
        detail_drift["benchResult"]["itemRuns"][0]["frontier"][0]["fidelity"] = 0.123
        _resign_receipt(detail_drift)
        with self.assertRaisesRegex(KaggleReceiptError, "benchResult disagrees"):
            serialize_kaggle_receipt(detail_drift)

    def test_tampered_receipt_fails_artifact_id_check(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            receipt = build_kaggle_receipt(
                run_json_path=self._write_run(temporary_directory),
                max_tokens=512,
            )
        receipt["submissionRows"][0]["outputText"] = "tampered"
        with self.assertRaisesRegex(KaggleReceiptError, "artifact id mismatch"):
            serialize_kaggle_receipt(receipt)

    def test_empty_output_produces_blocked_receipt(self) -> None:
        blocked_run = _full_run(empty_first=True)
        with tempfile.TemporaryDirectory() as temporary_directory:
            receipt = build_kaggle_receipt(
                run_json_path=self._write_run(temporary_directory, blocked_run),
                max_tokens=512,
            )
        self.assertEqual(receipt["diagnostics"]["status"], "blocked")
        self.assertEqual(len(receipt["diagnostics"]["emptyRowIds"]), 1)
        self.assertEqual(receipt["submissionRows"][0]["outputText"], "")
        serialize_kaggle_receipt(receipt)

    def test_zero_usage_produces_schema_valid_blocked_receipt(self) -> None:
        blocked_run = copy.deepcopy(self.run_payload)
        conversation = blocked_run["conversations"][1]
        conversation["requests"][0]["metrics"]["outputTokens"] = 0
        conversation["metrics"]["outputTokens"] = 0
        with tempfile.TemporaryDirectory() as temporary_directory:
            receipt = build_kaggle_receipt(
                run_json_path=self._write_run(temporary_directory, blocked_run),
                max_tokens=512,
            )
        self.assertEqual(receipt["diagnostics"]["status"], "blocked")
        self.assertEqual(len(receipt["diagnostics"]["invalidUsageRowIds"]), 1)
        self.assertEqual(receipt["submissionRows"][0]["usage"]["outputTokens"], 0)
        serialize_kaggle_receipt(receipt)

    def test_replay_does_not_modify_immutable_v0_1_receipt(self) -> None:
        before = verify_v0_1_repository_receipt()
        self.assertEqual(before, [])
        with tempfile.TemporaryDirectory() as temporary_directory:
            build_kaggle_receipt(
                run_json_path=self._write_run(temporary_directory),
                max_tokens=512,
            )
        self.assertEqual(verify_v0_1_repository_receipt(), [])

    def test_scorer_and_data_are_used_from_one_verified_memory_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            copied_package = Path(temporary_directory) / "package"
            shutil.copytree(DEFAULT_V0_1_PACKAGE_ROOT, copied_package)
            package = _load_package_context(copied_package)

            (copied_package / "kaggle/score_outputs.py").write_text(
                "raise RuntimeError('operator path was re-read')\n",
                encoding="utf-8",
            )
            (copied_package / "data/public_s2_items.jsonl").write_text(
                "{}\n",
                encoding="utf-8",
            )

            scorer = _load_legacy_score_function(
                scoring_source=package["scoringSource"],
                score_outputs_source=package["scoreSource"],
                item_rows=package["items"],
                prompt_rows=package["prompts"],
            )
            outputs = []
            for prompt, conversation in zip(
                package["sendable"], self.run_payload["conversations"][1:]
            ):
                outputs.append(
                    {
                        "row_id": f"{prompt['item_id']}:{prompt['prompt_id']}",
                        "model_id": FIXTURE_MODEL_SLUG,
                        "item_id": prompt["item_id"],
                        "prompt_id": prompt["prompt_id"],
                        "output_text": conversation["requests"][0]["contents"][1][
                            "parts"
                        ][0]["text"],
                    }
                )
            result = scorer(
                items_path="data/public_s2_items.jsonl",
                prompts_path="data/public_s2_prompts.jsonl",
                submission_rows=outputs,
                model_id=FIXTURE_MODEL_SLUG,
            )
        self.assertAlmostEqual(
            1.0 - float(result["aggregate"]["aurc"]),
            self.run_payload["results"][0]["numericResult"]["value"],
        )

    def test_manifest_digest_is_independently_pinned(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            copied_package = Path(temporary_directory) / "package"
            shutil.copytree(DEFAULT_V0_1_PACKAGE_ROOT, copied_package)
            manifest = copied_package / "package-manifest.json"
            manifest.write_bytes(manifest.read_bytes() + b"\n")
            with patch(
                "bench.engine.kaggle_receipt.verify_v0_1_package_receipt",
                return_value=[],
            ):
                with self.assertRaisesRegex(
                    KaggleReceiptError, "audited package manifest .* drifted"
                ):
                    _load_package_context(copied_package)

    def test_package_verification_rejects_oversized_files_without_reading_them(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            copied_package = Path(temporary_directory) / "package"
            shutil.copytree(DEFAULT_V0_1_PACKAGE_ROOT, copied_package)
            oversized = copied_package / "EVALUATION.md"
            with oversized.open("wb") as handle:
                handle.truncate(8 * 1024 * 1024 + 1)
            with self.assertRaisesRegex(KaggleReceiptError, "safety limit"):
                _load_package_context(copied_package)

    def test_cli_refuses_existing_output_and_preserves_it(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            run_path = self._write_run(temporary_directory)
            out = Path(temporary_directory) / "existing.json"
            out.write_bytes(b"sentinel")
            with self.assertRaisesRegex(KaggleReceiptError, "refusing to replace"):
                bench_main(
                    [
                        "kaggle-replay",
                        "--run-json",
                        str(run_path),
                        "--max-tokens",
                        "512",
                        "--out",
                        str(out),
                    ]
                )
            self.assertEqual(out.read_bytes(), b"sentinel")

    def test_cli_refuses_source_run_as_output_without_modifying_it(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            run_path = self._write_run(temporary_directory)
            before = run_path.read_bytes()
            with self.assertRaisesRegex(KaggleReceiptError, "refusing to replace"):
                bench_main(
                    [
                        "kaggle-replay",
                        "--run-json",
                        str(run_path),
                        "--max-tokens",
                        "512",
                        "--out",
                        str(run_path),
                    ]
                )
            self.assertEqual(run_path.read_bytes(), before)

    def test_output_must_be_outside_package_through_symlink_alias(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            run_path = self._write_run(temporary_directory)
            package_alias = Path(temporary_directory) / "package-alias"
            package_alias.symlink_to(DEFAULT_V0_1_PACKAGE_ROOT, target_is_directory=True)
            out = package_alias / "receipt-do-not-create.json"
            with self.assertRaisesRegex(KaggleReceiptError, "outside the scorer package"):
                validate_kaggle_replay_output_path(
                    run_json_path=run_path,
                    package_root=DEFAULT_V0_1_PACKAGE_ROOT,
                    out=out,
                )
            self.assertFalse(out.exists())

    def test_atomic_publish_loses_race_without_overwriting(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            run_path = self._write_run(temporary_directory)
            out = Path(temporary_directory) / "raced.json"
            validated_out = validate_kaggle_replay_output_path(
                run_json_path=run_path,
                package_root=DEFAULT_V0_1_PACKAGE_ROOT,
                out=out,
            )
            receipt = build_kaggle_receipt(run_json_path=run_path, max_tokens=512)
            out.write_bytes(b"winner")
            with self.assertRaisesRegex(KaggleReceiptError, "refusing to replace"):
                write_new_kaggle_receipt(
                    validated_out,
                    receipt,
                    run_json_path=run_path,
                    package_root=DEFAULT_V0_1_PACKAGE_ROOT,
                    expected_package_root_identity=(
                        capture_kaggle_package_root_identity(
                            DEFAULT_V0_1_PACKAGE_ROOT
                        )
                    ),
                )
            self.assertEqual(out.read_bytes(), b"winner")

    def test_publish_rejects_replaced_package_directory_identity(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            run_path = self._write_run(temporary_directory)
            receipt = build_kaggle_receipt(run_json_path=run_path, max_tokens=512)
            copied_package = Path(temporary_directory) / "package"
            shutil.copytree(DEFAULT_V0_1_PACKAGE_ROOT, copied_package)
            expected_identity = capture_kaggle_package_root_identity(copied_package)
            copied_package.rename(Path(temporary_directory) / "original-package")
            shutil.copytree(DEFAULT_V0_1_PACKAGE_ROOT, copied_package)
            out = Path(temporary_directory) / "receipt.json"
            with self.assertRaisesRegex(KaggleReceiptError, "package root changed"):
                write_new_kaggle_receipt(
                    out,
                    receipt,
                    run_json_path=run_path,
                    package_root=copied_package,
                    expected_package_root_identity=expected_identity,
                )
            self.assertFalse(out.exists())

    def test_publish_rechecks_package_identity_after_temp_write(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            run_path = self._write_run(temporary_directory)
            receipt = build_kaggle_receipt(run_json_path=run_path, max_tokens=512)
            copied_package = Path(temporary_directory) / "package"
            shutil.copytree(DEFAULT_V0_1_PACKAGE_ROOT, copied_package)
            expected_identity = capture_kaggle_package_root_identity(copied_package)
            out = Path(temporary_directory) / "receipt.json"
            original_fsync = os.fsync
            swapped = False

            def swap_package_after_temp_fsync(descriptor: int) -> None:
                nonlocal swapped
                original_fsync(descriptor)
                if not swapped:
                    swapped = True
                    copied_package.rename(
                        Path(temporary_directory) / "original-package"
                    )
                    shutil.copytree(DEFAULT_V0_1_PACKAGE_ROOT, copied_package)

            with patch(
                "bench.engine.kaggle_receipt.os.fsync",
                side_effect=swap_package_after_temp_fsync,
            ):
                with self.assertRaisesRegex(KaggleReceiptError, "package root changed"):
                    write_new_kaggle_receipt(
                        out,
                        receipt,
                        run_json_path=run_path,
                        package_root=copied_package,
                        expected_package_root_identity=expected_identity,
                    )
            self.assertTrue(swapped)
            self.assertFalse(out.exists())

    def test_structural_failure_never_writes_a_receipt(self) -> None:
        changed = copy.deepcopy(self.run_payload)
        changed["taskVersion"]["description"] = "Drifted task description."
        with tempfile.TemporaryDirectory() as temporary_directory:
            run_path = self._write_run(temporary_directory, changed)
            out = Path(temporary_directory) / "must-not-exist.json"
            with self.assertRaisesRegex(KaggleReceiptError, "unsupported Kaggle task"):
                bench_main(
                    [
                        "kaggle-replay",
                        "--run-json",
                        str(run_path),
                        "--max-tokens",
                        "512",
                        "--out",
                        str(out),
                    ]
                )
            self.assertFalse(out.exists())

    def test_cli_writes_valid_receipt_and_returns_zero(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            run_path = self._write_run(temporary_directory)
            out = Path(temporary_directory) / "receipt.json"
            output = io.StringIO()
            with redirect_stdout(output):
                status = bench_main(
                    [
                        "kaggle-replay",
                        "--run-json",
                        str(run_path),
                        "--package-root",
                        str(DEFAULT_V0_1_PACKAGE_ROOT),
                        "--max-tokens",
                        "512",
                        "--out",
                        str(out),
                    ]
                )
            receipt = json.loads(out.read_text(encoding="utf-8"))
        self.assertEqual(status, 0)
        self.assertEqual(receipt["diagnostics"]["status"], "valid")
        self.assertEqual(out.name, "receipt.json")
        self.assertIn('"rowCount": 180', output.getvalue())

    def test_cli_writes_blocked_receipt_before_returning_two(self) -> None:
        blocked_run = _full_run(empty_first=True)
        with tempfile.TemporaryDirectory() as temporary_directory:
            run_path = self._write_run(temporary_directory, blocked_run)
            out = Path(temporary_directory) / "blocked-receipt.json"
            output = io.StringIO()
            with redirect_stdout(output):
                status = bench_main(
                    [
                        "kaggle-replay",
                        "--run-json",
                        str(run_path),
                        "--package-root",
                        str(DEFAULT_V0_1_PACKAGE_ROOT),
                        "--max-tokens",
                        "512",
                        "--out",
                        str(out),
                    ]
                )
            self.assertTrue(out.is_file())
            receipt = json.loads(out.read_text(encoding="utf-8"))
        self.assertEqual(status, 2)
        self.assertEqual(receipt["diagnostics"]["status"], "blocked")
        self.assertEqual(receipt["submissionRows"][0]["outputText"], "")
        self.assertIn('"status": "blocked"', output.getvalue())


if __name__ == "__main__":
    unittest.main()
