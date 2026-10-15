from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

from bench.engine.croissant_v0_2 import (
    DATASET_DIR,
    DEFAULT_CROISSANT_PATH,
    EXPECTED_ITEM_COUNT,
    EXPECTED_PROMPT_COUNT,
    build_croissant_v0_2,
    check_croissant_v0_2,
    croissant_v0_2_bytes,
    write_croissant_v0_2,
)
from bench.engine.frozen_ladder import load_items

try:
    import mlcroissant as mlc  # type: ignore[import-untyped]
except ImportError:  # pragma: no cover - mlcroissant is optional in unit tests
    mlc = None


ROOT = Path(__file__).resolve().parents[2]

EXPECTED_ITEM_SOURCES = {
    "item_id": "$.id",
    "stratum": "$.stratum",
    "language": "$.language",
    "metric_class": "$.metricClass",
    "target_label": "$.target.label",
    "target_text": "$.target.text",
    "family": "$.provenance.parameters.family",
    "canary_guid": "$.canaryGuid",
    "license": "$.license",
}

EXPECTED_PROMPT_SOURCES = {
    "prompt_id": "$.frozenLadder[*].id",
    "rung": "$.frozenLadder[*].rung",
    "paraphrase": "$.frozenLadder[*].paraphrase",
    "label": "$.frozenLadder[*].label",
    "expected_leakage": "$.frozenLadder[*].expectedLeakage",
    "prompt": "$.frozenLadder[*].prompt",
}


def _text(value: Any) -> str:
    return value.decode("utf-8") if isinstance(value, bytes) else str(value)


class CroissantV0_2Tests(unittest.TestCase):
    def test_checked_in_artifact_is_byte_identical_to_builder(self) -> None:
        self.assertTrue(
            DEFAULT_CROISSANT_PATH.exists(),
            msg=f"missing checked-in artifact: {DEFAULT_CROISSANT_PATH}",
        )
        self.assertEqual(DEFAULT_CROISSANT_PATH.read_bytes(), croissant_v0_2_bytes())

    def test_document_declares_croissant_1_1_and_both_record_sets(self) -> None:
        document = build_croissant_v0_2()
        self.assertEqual(document["conformsTo"], "http://mlcommons.org/croissant/1.1")
        self.assertEqual(document["version"], "0.2.0")
        self.assertEqual(document["license"], "https://spdx.org/licenses/CC0-1.0.html")
        self.assertEqual(document["name"], "Aleph-Bench v0.2 public S2")
        self.assertIs(document["isLiveDataset"], False)
        file_sets = {entry["@id"]: entry for entry in document["distribution"]}
        self.assertEqual(set(file_sets), {"s2-items-files", "s2-prompts-files"})
        for file_set in file_sets.values():
            self.assertEqual(file_set["@type"], "cr:FileSet")
            self.assertEqual(file_set["includes"], "public/s2/s2-*.json")
            self.assertEqual(file_set["encodingFormat"], "application/json")
        record_sets = {entry["@id"]: entry for entry in document["recordSet"]}
        self.assertEqual(set(record_sets), {"public_s2_items", "public_s2_prompts"})
        for record_set in record_sets.values():
            self.assertEqual(record_set["@type"], "cr:RecordSet")
            self.assertTrue(record_set["description"])

    def test_field_sources_match_the_dataset_shape(self) -> None:
        document = build_croissant_v0_2()
        record_sets = {entry["@id"]: entry for entry in document["recordSet"]}
        declared_file_sets = {entry["@id"] for entry in document["distribution"]}
        field_ids: set[str] = set()
        for record_set_id, expected_sources in (
            ("public_s2_items", EXPECTED_ITEM_SOURCES),
            ("public_s2_prompts", EXPECTED_PROMPT_SOURCES),
        ):
            fields = record_sets[record_set_id]["field"]
            observed_sources = {
                field["name"]: field["source"]["extract"]["jsonPath"] for field in fields
            }
            self.assertEqual(observed_sources, expected_sources)
            for field in fields:
                self.assertNotIn(field["@id"], field_ids)
                field_ids.add(field["@id"])
                self.assertIn(field["source"]["fileSet"]["@id"], declared_file_sets)
        items_fields = {field["name"]: field for field in record_sets["public_s2_items"]["field"]}
        prompts_fields = {field["name"]: field for field in record_sets["public_s2_prompts"]["field"]}
        for name, field in items_fields.items():
            self.assertEqual(field["dataType"], "sc:Text", msg=name)
        self.assertEqual(prompts_fields["rung"]["dataType"], "sc:Integer")
        self.assertEqual(prompts_fields["paraphrase"]["dataType"], "sc:Integer")
        for name, field in prompts_fields.items():
            if name not in {"rung", "paraphrase"}:
                self.assertEqual(field["dataType"], "sc:Text", msg=name)

    def test_record_counts_match_the_frozen_dataset(self) -> None:
        items = load_items(DATASET_DIR, require_canonical=True)
        prompt_count = sum(len(item["frozenLadder"]) for item in items)
        self.assertEqual(len(items), EXPECTED_ITEM_COUNT)
        self.assertEqual(prompt_count, EXPECTED_PROMPT_COUNT)

    def test_writer_writes_canonical_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "croissant.json"
            digest = write_croissant_v0_2(path)
            self.assertEqual(path.read_bytes(), croissant_v0_2_bytes())
            self.assertEqual(
                digest, hashlib.sha256(croissant_v0_2_bytes()).hexdigest()
            )

    def test_checker_accepts_canonical_bytes_and_flags_drift(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "croissant.json"
            path.write_bytes(croissant_v0_2_bytes())
            report = check_croissant_v0_2(path)
            self.assertEqual(report["status"], "ok")
            self.assertEqual(report["errors"], [])
            self.assertEqual(
                report["recordSets"],
                {"public_s2_items": EXPECTED_ITEM_COUNT, "public_s2_prompts": EXPECTED_PROMPT_COUNT},
            )
            self.assertEqual(
                report["sha256"], hashlib.sha256(croissant_v0_2_bytes()).hexdigest()
            )
            path.write_bytes(croissant_v0_2_bytes() + b"\n")
            drifted = check_croissant_v0_2(path)
            self.assertEqual(drifted["status"], "failed")
            self.assertTrue(drifted["errors"])
            missing = check_croissant_v0_2(Path(temporary) / "missing.json")
            self.assertEqual(missing["status"], "failed")
            self.assertTrue(missing["errors"])

    def test_cli_check_reports_ok_for_checked_in_artifact(self) -> None:
        result = subprocess.run(
            [
                sys.executable,
                str(ROOT / "bench/run.py"),
                "croissant-v0.2",
                "--check",
                str(DEFAULT_CROISSANT_PATH),
                "--json",
            ],
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report["status"], "ok")

    @unittest.skipUnless(mlc is not None, "mlcroissant is not installed")
    def test_mlcroissant_streams_items_and_prompts(self) -> None:
        dataset = mlc.Dataset(jsonld=str(DEFAULT_CROISSANT_PATH))
        self.assertEqual(dataset.metadata.name, "Aleph-Bench v0.2 public S2")
        items = list(dataset.records("public_s2_items"))
        prompts = list(dataset.records("public_s2_prompts"))
        self.assertEqual(len(items), EXPECTED_ITEM_COUNT)
        self.assertEqual(len(prompts), EXPECTED_PROMPT_COUNT)
        item_ids = {_text(row["public_s2_items/item_id"]) for row in items}
        self.assertEqual(len(item_ids), EXPECTED_ITEM_COUNT)
        self.assertEqual(item_ids, {f"s2-{index:03d}" for index in range(1, 31)})
        families = {_text(row["public_s2_items/family"]) for row in items}
        self.assertEqual(families, {"arithmetic", "route", "letter-lattice"})
        prompt_ids = {_text(row["public_s2_prompts/prompt_id"]) for row in prompts}
        self.assertIn("s2-001-r0-p0", prompt_ids)
        self.assertIn("s2-030-r3-p1", prompt_ids)
        self.assertEqual(
            {row["public_s2_prompts/rung"] for row in prompts}, {0, 1, 2, 3}
        )


if __name__ == "__main__":
    unittest.main()
