from __future__ import annotations

import copy
import hashlib
import json
import os
import shlex
import sys
import tempfile
import unicodedata
import unittest
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

from bench.engine import scoring_core
from bench.engine.protocol import DEFAULT_LEAKAGE_THRESHOLDS
from bench.proofs.unicode_runtime_compatibility import (
    CHECKED_RECEIPT_PATH,
    FIDELITY_OUTPUT,
    FIDELITY_TARGET,
    LEAKAGE_PROMPT,
    LEAKAGE_TARGET,
    MAX_WORKER_JSON_BYTES,
    MAX_RECEIPT_BYTES,
    PROPERTY_HEADER,
    PROPERTY_NAMES,
    PROTOCOL_CONFIG_PATH,
    PROTOCOL_MODULE_PATH,
    RUNNER_PATH,
    SCORING_CORE_PATH,
    TEXT_LENGTH,
    ProofError,
    _artifact_id,
    _load_json,
    _run_bounded_process,
    _run_runtime_worker,
    compare_property_tables,
    decode_property_record,
    encode_property_record,
    observe_counterexamples,
    property_record,
    property_values,
    validate_receipt,
)


class UnicodeRuntimeCompatibilityProofTests(unittest.TestCase):
    def test_checked_receipt_is_content_addressed_and_bound_to_inputs(self) -> None:
        receipt = _load_json(CHECKED_RECEIPT_PATH)
        validate_receipt(receipt)
        self.assertEqual(
            receipt["singleCodepointComparison"]["propertyDifferenceCounts"],
            {
                "casefold": 0,
                "category": 5_116,
                "eastAsianWidth": 829_834,
                "isSpace": 0,
                "nfc": 0,
                "nfkc": 62,
            },
        )
        self.assertEqual(
            receipt["singleCodepointComparison"]["differingCodepointCount"],
            829_834,
        )
        for key, path in (
            ("scoringCore", SCORING_CORE_PATH),
            ("protocolConfig", PROTOCOL_CONFIG_PATH),
            ("protocolModule", PROTOCOL_MODULE_PATH),
            ("runner", RUNNER_PATH),
        ):
            self.assertEqual(
                receipt["proofInputs"][key]["sha256"],
                hashlib.sha256(path.read_bytes()).hexdigest(),
            )
        serialized = json.dumps(receipt, ensure_ascii=True, sort_keys=True)
        self.assertNotIn("/Users/", serialized)
        self.assertNotIn("/private/", serialized)

    def test_lossless_record_round_trip_covers_boundaries_and_surrogates(self) -> None:
        for codepoint in (0, 0xD800, 0x10FFFF):
            with self.subTest(codepoint=codepoint):
                encoded = property_record(codepoint)
                handle = BytesIO(encoded)
                self.assertEqual(
                    decode_property_record(handle, role="test"),
                    property_values(codepoint),
                )
                self.assertEqual(handle.read(), b"")
        for invalid in (-1, 0x110000, True, "0"):
            with self.subTest(invalid=invalid):
                with self.assertRaises(ValueError):
                    property_record(invalid)  # type: ignore[arg-type]

    def test_lossless_decoder_rejects_truncated_and_oversized_records(self) -> None:
        with self.assertRaisesRegex(ProofError, "inside a record"):
            decode_property_record(BytesIO(b"CnF"), role="test")
        header = PROPERTY_HEADER.pack(b"Cn", b"F", b"0")
        oversized = TEXT_LENGTH.pack(4 * 65)
        with self.assertRaisesRegex(ProofError, "invalid casefold length"):
            decode_property_record(BytesIO(header + oversized), role="test")

    def test_exact_table_comparison_uses_decoded_fields_not_hashes(self) -> None:
        unchanged = ("Lu", "Na", False, "a", "a", "a")
        old = ("Cn", "F", False, "x", "x", "x")
        new = ("Ll", "W", True, "y", "y", "z")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            left = root / "left.bin"
            right = root / "right.bin"
            left.write_bytes(
                encode_property_record(unchanged) + encode_property_record(old)
            )
            right.write_bytes(
                encode_property_record(unchanged) + encode_property_record(new)
            )
            comparison = compare_property_tables(left, right, codepoint_count=2)
        self.assertEqual(comparison["differingCodepointCount"], 1)
        self.assertEqual(
            comparison["propertyDifferenceCounts"],
            {
                "category": 1,
                "eastAsianWidth": 1,
                "isSpace": 1,
                "casefold": 1,
                "nfc": 1,
                "nfkc": 1,
            },
        )
        self.assertEqual(comparison["firstDifferenceByProperty"]["nfkc"], "U+0001")

    def test_exact_table_comparison_rejects_trailing_bytes(self) -> None:
        record = encode_property_record(("Lu", "Na", False, "a", "a", "a"))
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            left = root / "left.bin"
            right = root / "right.bin"
            left.write_bytes(record + b"x")
            right.write_bytes(record)
            with self.assertRaisesRegex(ProofError, "trailing records or bytes"):
                compare_property_tables(left, right, codepoint_count=1)

    @unittest.skipUnless(os.name == "posix", "worker limits require POSIX")
    def test_worker_output_and_file_size_are_bounded_during_execution(self) -> None:
        with self.assertRaisesRegex(ProofError, "stdout exceeded"):
            _run_bounded_process(
                [
                    sys.executable,
                    "-B",
                    "-c",
                    f"import os; os.write(1, b'x' * {MAX_WORKER_JSON_BYTES + 1})",
                ],
                role="oversized-output worker",
                timeout_seconds=10,
                file_size_limit=1024,
            )

        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "bounded.bin"
            command = (
                "handle = open(" + repr(str(output)) + ", 'wb', buffering=0); "
                "handle.write(b'x' * 2048); handle.write(b'y')"
            )
            with self.assertRaisesRegex(ProofError, "failed with exit code"):
                _run_bounded_process(
                    [sys.executable, "-B", "-c", command],
                    role="oversized-file worker",
                    timeout_seconds=10,
                    file_size_limit=1024,
                )
            self.assertLessEqual(output.stat().st_size, 1024)

    @unittest.skipUnless(os.name == "posix", "wrapper test requires POSIX")
    def test_runtime_worker_rejects_wrapper_identity_switch(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            fake_runner = root / "fake_runner.py"
            fake_runner.write_text(
                "import hashlib, json, sys\n"
                "from pathlib import Path\n"
                "Path(sys.argv[-1]).write_bytes(b'x')\n"
                "executable = Path(sys.executable).resolve()\n"
                "print(json.dumps({'runtime': {'"
                "executableSha256': hashlib.sha256(executable.read_bytes()).hexdigest()}}))\n",
                encoding="ascii",
            )
            wrapper = root / "python-wrapper"
            wrapper.write_text(
                "#!/bin/sh\nexec " + shlex.quote(sys.executable) + ' "$@"\n',
                encoding="ascii",
            )
            wrapper.chmod(0o700)
            table = root / "table.bin"
            with patch(
                "bench.proofs.unicode_runtime_compatibility.RUNNER_PATH",
                fake_runner,
            ):
                with self.assertRaisesRegex(
                    ProofError, "identity does not match requested interpreter"
                ):
                    _run_runtime_worker(
                        wrapper.resolve(), table, timeout_seconds=10
                    )

    @unittest.skipUnless(
        sys.version_info[:2] == (3, 13)
        and unicodedata.unidata_version == "15.1.0",
        "canonical scorer comparison requires Python 3.13/UCD 15.1",
    )
    def test_reference_probe_matches_canonical_entry_points(self) -> None:
        observed = observe_counterexamples()
        canonical_leakage = scoring_core.evaluate_leakage(
            LEAKAGE_PROMPT,
            LEAKAGE_TARGET,
            dict(DEFAULT_LEAKAGE_THRESHOLDS),
        ).as_dict()
        canonical_fidelity = scoring_core.fidelity(
            FIDELITY_TARGET,
            FIDELITY_OUTPUT,
            "normalized_edit_similarity",
        )
        self.assertEqual(observed["leakage"]["result"], canonical_leakage)
        self.assertEqual(
            observed["fidelity"]["normalizedEditSimilarity"],
            canonical_fidelity,
        )
        self.assertTrue(observed["runtimeValidation"]["accepted"])

    def test_receipt_validation_rejects_semantic_tampering(self) -> None:
        receipt = _load_json(CHECKED_RECEIPT_PATH)
        receipt["singleCodepointComparison"]["comparedCodepoints"] -= 1
        with self.assertRaisesRegex(ProofError, "every Unicode code point"):
            validate_receipt(receipt)
        receipt = _load_json(CHECKED_RECEIPT_PATH)
        del receipt["singleCodepointComparison"]["propertyDifferenceCounts"][
            PROPERTY_NAMES[0]
        ]
        with self.assertRaisesRegex(ProofError, "property counts are incomplete"):
            validate_receipt(receipt)
        receipt = _load_json(CHECKED_RECEIPT_PATH)
        receipt["unexpected"] = True
        with self.assertRaisesRegex(ProofError, "proof receipt keys differ"):
            validate_receipt(receipt)
        receipt = _load_json(CHECKED_RECEIPT_PATH)
        receipt["runtimes"]["reference"]["runtimeValidation"] = {
            "accepted": False,
            "error": "forged",
        }
        with self.assertRaisesRegex(ProofError, "reference runtime must pass"):
            validate_receipt(receipt)

        base = _load_json(CHECKED_RECEIPT_PATH)
        forged_codepoints = copy.deepcopy(base)
        forged_codepoints["counterexamples"][0]["negativeControl"][
            "normalizedPromptCodepoints"
        ] = ["not-a-codepoint"]
        payload = {key: value for key, value in forged_codepoints.items() if key != "id"}
        forged_codepoints["id"] = _artifact_id(payload)
        with self.assertRaisesRegex(ProofError, "counterexample semantics drifted"):
            validate_receipt(forged_codepoints)

        forged_threshold = copy.deepcopy(base)
        forged_threshold["counterexamples"][0]["reference"]["result"][
            "thresholds"
        ]["lcsRatio"] = 0.25
        payload = {key: value for key, value in forged_threshold.items() if key != "id"}
        forged_threshold["id"] = _artifact_id(payload)
        with self.assertRaisesRegex(ProofError, "counterexample semantics drifted"):
            validate_receipt(forged_threshold)

    def test_json_loader_rejects_duplicate_keys(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path = root / "duplicate.json"
            path.write_text('{"id":"a","id":"b"}', encoding="ascii")
            with self.assertRaisesRegex(ProofError, "duplicate JSON key"):
                _load_json(path)
            non_finite = root / "non-finite.json"
            non_finite.write_text('{"value":NaN}', encoding="ascii")
            with self.assertRaisesRegex(ProofError, "non-finite JSON value"):
                _load_json(non_finite)
            for index, encoded in enumerate((b'{"value":1e999}', b'{"value":-1e999}')):
                overflow = root / f"overflow-{index}.json"
                overflow.write_bytes(encoded)
                with self.assertRaisesRegex(ProofError, "non-finite JSON value"):
                    _load_json(overflow)
            oversized = root / "oversized.json"
            oversized.write_bytes(b"{" + b" " * MAX_RECEIPT_BYTES + b"}")
            with self.assertRaisesRegex(ProofError, "exceeds"):
                _load_json(oversized)


if __name__ == "__main__":
    unittest.main()
