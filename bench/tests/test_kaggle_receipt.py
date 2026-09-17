from __future__ import annotations

import copy
import io
import json
import math
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from bench.engine.kaggle_receipt import (
    DEFAULT_V0_1_PACKAGE_ROOT,
    KaggleReceiptError,
    _load_legacy_score_function,
    _load_package_context,
    build_kaggle_receipt,
    canonical_json_bytes,
    parse_run_conversations,
    serialize_kaggle_receipt,
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
    scorer = _load_legacy_score_function(DEFAULT_V0_1_PACKAGE_ROOT)
    result = scorer(
        items_path=DEFAULT_V0_1_PACKAGE_ROOT / "data/public_s2_items.jsonl",
        prompts_path=DEFAULT_V0_1_PACKAGE_ROOT / "data/public_s2_prompts.jsonl",
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
            "description": "Fixture full run.",
            "definition": AUDITED_TASK_DEFINITION_PATH.read_text(encoding="utf-8"),
        },
    }


class KaggleConversationParserTests(unittest.TestCase):
    def test_minimal_fixture_preserves_raw_unicode_and_whitespace(self) -> None:
        run = _load_fixture()
        rows, diagnostics = parse_run_conversations(
            run,
            expected_prompts=_fixture_expected_prompts(),
            max_tokens=32,
        )
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["outputText"], "\n Café 🧪 \n")
        self.assertEqual(rows[0]["promptText"], "fixture prompt")
        self.assertEqual(rows[0]["conversationId"], "s2-001:s2-001-r1-p0-9a1370ab")
        self.assertEqual(diagnostics["status"], "valid")
        self.assertEqual(diagnostics["emptyRowIds"], [])

    def test_duplicate_conversation_fails_closed(self) -> None:
        run = _load_fixture()
        run["conversations"].append(copy.deepcopy(run["conversations"][1]))
        with self.assertRaisesRegex(KaggleReceiptError, "duplicate response"):
            parse_run_conversations(
                run,
                expected_prompts=_fixture_expected_prompts(),
                max_tokens=32,
            )

    def test_missing_conversation_fails_closed(self) -> None:
        run = _load_fixture()
        run["conversations"] = run["conversations"][:1]
        with self.assertRaisesRegex(KaggleReceiptError, "coverage mismatch"):
            parse_run_conversations(
                run,
                expected_prompts=_fixture_expected_prompts(),
                max_tokens=32,
            )

    def test_non_string_assistant_output_fails_closed(self) -> None:
        run = _load_fixture()
        run["conversations"][1]["requests"][0]["contents"][1]["parts"][0][
            "text"
        ] = {"not": "a string"}
        with self.assertRaisesRegex(KaggleReceiptError, "ASSISTANT text must be a string"):
            parse_run_conversations(
                run,
                expected_prompts=_fixture_expected_prompts(),
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
                max_tokens=4,
                saturation_margin_tokens=4,
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

    def test_supported_identity_and_operator_assertion_are_content_addressed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            run_path = self._write_run(temporary_directory)
            first = build_kaggle_receipt(run_json_path=run_path, max_tokens=512)
            changed_run = copy.deepcopy(self.run_payload)
            changed_run["modelVersion"]["slug"] = "fixture/other-model"
            changed_path = Path(temporary_directory) / "changed.json"
            changed_path.write_text(json.dumps(changed_run), encoding="utf-8")
            changed = build_kaggle_receipt(
                run_json_path=changed_path,
                max_tokens=512,
            )
            changed_config = build_kaggle_receipt(
                run_json_path=run_path,
                max_tokens=1024,
            )
        self.assertNotEqual(first["id"], changed["id"])
        self.assertNotEqual(first["id"], changed_config["id"])
        self.assertEqual(
            first["scoringIdentity"]["configSha256"],
            changed_config["scoringIdentity"]["configSha256"],
        )
        self.assertEqual(
            first["operatorAssertions"]["maxTokensSource"],
            "operator_asserted_not_present_in_run_json",
        )
        self.assertEqual(first["operatorAssertions"]["maxTokens"], 512)
        self.assertEqual(changed_config["operatorAssertions"]["maxTokens"], 1024)

    def test_unsupported_task_identity_fails_closed(self) -> None:
        mutations = (
            ("name", "some_other_task"),
            ("versionNumber", 4),
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

    def test_non_finite_scalar_object_fails_closed(self) -> None:
        changed = copy.deepcopy(self.run_payload)
        changed["results"][0]["numericResult"]["value"] = math.inf
        with tempfile.TemporaryDirectory() as temporary_directory:
            run_path = self._write_run(temporary_directory, changed)
            with self.assertRaisesRegex(KaggleReceiptError, "non-finite JSON"):
                build_kaggle_receipt(run_json_path=run_path, max_tokens=512)

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

    def test_replay_does_not_modify_immutable_v0_1_receipt(self) -> None:
        before = verify_v0_1_repository_receipt()
        self.assertEqual(before, [])
        with tempfile.TemporaryDirectory() as temporary_directory:
            build_kaggle_receipt(
                run_json_path=self._write_run(temporary_directory),
                max_tokens=512,
            )
        self.assertEqual(verify_v0_1_repository_receipt(), [])

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
