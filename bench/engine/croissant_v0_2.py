"""Deterministic Croissant 1.1 metadata for the v0.2 public S2 dataset.

The immutable v0.1 M0 package embedded a Croissant file generated from its flat
CSV tables (``bench/engine/platform_package.py``). The v0.2 line publishes the
raw frozen dataset files (``bench/data/v0.2/public/s2/s2-*.json``), so this
module describes those files directly:

- two ``cr:FileSet`` entries over the ``s2-*.json`` glob — one per record set,
  because mlcroissant rejects a shared file set when record sets extract
  different numbers of values per file;
- ``cr:Field`` sources extracted with ``jsonPath`` expressions — items (one row
  per file: ``$.id``, ``$.target.text``, ...) and frozen-ladder prompts (eight
  rows per file: ``$.frozenLadder[*].id``, ...). A prompt row carries its item
  id as the ``prompt_id`` prefix (``s2-001-r0-p0`` belongs to ``s2-001``); a
  dedicated scalar ``item_id`` field cannot be expressed because every field in
  a record set must extract the same number of values per file.

Output is byte-deterministic: canonical house JSON (``indent=2,
sort_keys=True``), fixed dates, and a dataset pinned by
``load_items(..., require_canonical=True)``. The checked-in artifact is guarded
by ``python3 bench/run.py croissant-v0.2 --check bench/data/v0.2/croissant.json``
and streamed with mlcroissant in CI.

Research basis: ``docs/benchmark/01-research-synthesis.md`` (section 5: a
Croissant metadata file is part of the minimum bar; section 6: meet people in
their tools) and ``docs/benchmark/07-release-strategy.md`` section 3. Layout
precedent: the immutable v0.1 package at
``bench/results/platform/m0-mock/croissant.json``.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .frozen_ladder import REPO_ROOT, load_items
from .legacy_v0_1 import safe_write_bytes
from .scoring_core import PROTOCOL_VERSION


V0_2_DATA_ROOT = REPO_ROOT / "bench/data/v0.2"
DATASET_DIR = V0_2_DATA_ROOT / "public/s2"
DEFAULT_CROISSANT_PATH = V0_2_DATA_ROOT / "croissant.json"

# Fixed date for the v0.2 protocol line (mirrors FIXED_CREATED_AT in
# platform_package_v0_2.py) so the artifact never depends on wall-clock time.
FIXED_DATE = "2026-09-17"

ITEMS_RECORD_SET_ID = "public_s2_items"
PROMPTS_RECORD_SET_ID = "public_s2_prompts"
ITEMS_FILE_SET_ID = "s2-items-files"
PROMPTS_FILE_SET_ID = "s2-prompts-files"
FILE_SET_INCLUDES = "public/s2/s2-*.json"

EXPECTED_ITEM_COUNT = 30
EXPECTED_PROMPT_COUNT = 240


def _context() -> dict[str, Any]:
    return {
        "@language": "en",
        "@vocab": "https://schema.org/",
        "citeAs": "cr:citeAs",
        "column": "cr:column",
        "conformsTo": "dct:conformsTo",
        "cr": "http://mlcommons.org/croissant/",
        "data": {"@id": "cr:data", "@type": "@json"},
        "dataType": {"@id": "cr:dataType", "@type": "@vocab"},
        "dct": "http://purl.org/dc/terms/",
        "examples": {"@id": "cr:examples", "@type": "@json"},
        "extract": "cr:extract",
        "field": "cr:field",
        "fileObject": "cr:fileObject",
        "fileProperty": "cr:fileProperty",
        "fileSet": "cr:fileSet",
        "format": "cr:format",
        "includes": "cr:includes",
        "isLiveDataset": "cr:isLiveDataset",
        "jsonPath": "cr:jsonPath",
        "key": "cr:key",
        "md5": "cr:md5",
        "parentField": "cr:parentField",
        "path": "cr:path",
        "rai": "http://mlcommons.org/croissant/RAI/",
        "recordSet": "cr:recordSet",
        "references": "cr:references",
        "regex": "cr:regex",
        "repeated": "cr:repeated",
        "replace": "cr:replace",
        "sc": "https://schema.org/",
        "separator": "cr:separator",
        "source": "cr:source",
        "subField": "cr:subField",
        "transform": "cr:transform",
    }


def _field(
    record_set_id: str,
    file_set_id: str,
    name: str,
    description: str,
    data_type: str,
    json_path: str,
) -> dict[str, Any]:
    return {
        "@type": "cr:Field",
        "@id": f"{record_set_id}/{name}",
        "name": name,
        "description": description,
        "dataType": data_type,
        "source": {
            "fileSet": {"@id": file_set_id},
            "extract": {"jsonPath": json_path},
        },
    }


def _items_fields() -> list[dict[str, Any]]:
    record_set_id = ITEMS_RECORD_SET_ID
    file_set_id = ITEMS_FILE_SET_ID
    return [
        _field(record_set_id, file_set_id, "item_id", "Bench item id.", "sc:Text", "$.id"),
        _field(record_set_id, file_set_id, "stratum", "Benchmark stratum (S2).", "sc:Text", "$.stratum"),
        _field(record_set_id, file_set_id, "language", "ISO 639-1 language code.", "sc:Text", "$.language"),
        _field(record_set_id, file_set_id, "metric_class", "Primary fidelity metric class.", "sc:Text", "$.metricClass"),
        _field(record_set_id, file_set_id, "target_label", "Short target label for cold reading.", "sc:Text", "$.target.label"),
        _field(record_set_id, file_set_id, "target_text", "Target output text.", "sc:Text", "$.target.text"),
        _field(record_set_id, file_set_id, "family", "Synthetic family (arithmetic/route/letter-lattice).", "sc:Text", "$.provenance.parameters.family"),
        _field(record_set_id, file_set_id, "canary_guid", "Dataset-level contamination canary GUID.", "sc:Text", "$.canaryGuid"),
        _field(record_set_id, file_set_id, "license", "Item license.", "sc:Text", "$.license"),
    ]


def _prompts_fields() -> list[dict[str, Any]]:
    record_set_id = PROMPTS_RECORD_SET_ID
    file_set_id = PROMPTS_FILE_SET_ID
    return [
        _field(record_set_id, file_set_id, "prompt_id", "Frozen ladder prompt id (<item-id>-r<rung>-p<paraphrase>).", "sc:Text", "$.frozenLadder[*].id"),
        _field(record_set_id, file_set_id, "rung", "Frozen ladder rung (0..3).", "sc:Integer", "$.frozenLadder[*].rung"),
        _field(record_set_id, file_set_id, "paraphrase", "Paraphrase index within rung.", "sc:Integer", "$.frozenLadder[*].paraphrase"),
        _field(record_set_id, file_set_id, "label", "Human-readable rung label.", "sc:Text", "$.frozenLadder[*].label"),
        _field(record_set_id, file_set_id, "expected_leakage", "Declared leakage class of the prompt.", "sc:Text", "$.frozenLadder[*].expectedLeakage"),
        _field(record_set_id, file_set_id, "prompt", "Prompt text.", "sc:Text", "$.frozenLadder[*].prompt"),
    ]


def build_croissant_v0_2() -> dict[str, Any]:
    """Build the Croissant 1.1 document from the frozen v0.2 S2 dataset."""

    items = load_items(DATASET_DIR, require_canonical=True)
    prompt_count = sum(len(item["frozenLadder"]) for item in items)
    if len(items) != EXPECTED_ITEM_COUNT or prompt_count != EXPECTED_PROMPT_COUNT:
        raise ValueError(
            "v0.2 Croissant metadata expects "
            f"{EXPECTED_ITEM_COUNT} items and {EXPECTED_PROMPT_COUNT} prompts, "
            f"found {len(items)} items and {prompt_count} prompts"
        )
    return {
        "@context": _context(),
        "@type": "sc:Dataset",
        "conformsTo": "http://mlcommons.org/croissant/1.1",
        "name": "Aleph-Bench v0.2 public S2",
        "description": (
            "Thirty public S2 compositional targets with frozen-ladder prompts "
            "for the Aleph-Bench v0.2 protocol."
        ),
        "version": PROTOCOL_VERSION,
        "dateCreated": FIXED_DATE,
        "datePublished": FIXED_DATE,
        "creator": {"@type": "sc:Organization", "name": "p-to-q"},
        "publisher": {"@type": "sc:Organization", "name": "p-to-q"},
        "license": "https://spdx.org/licenses/CC0-1.0.html",
        "sdLicense": "https://spdx.org/licenses/CC0-1.0.html",
        "citeAs": "Aleph-Bench Maintainers (2026). Aleph-Bench v0.2 public S2 dataset.",
        "inLanguage": ["en"],
        "keywords": [
            "benchmark",
            "prompt compression",
            "reverse prompt search",
            "synthetic data",
            "LLM evaluation",
        ],
        "isLiveDataset": False,
        "distribution": [
            {
                "@type": "cr:FileSet",
                "@id": ITEMS_FILE_SET_ID,
                "name": ITEMS_FILE_SET_ID,
                "encodingFormat": "application/json",
                "includes": FILE_SET_INCLUDES,
            },
            {
                "@type": "cr:FileSet",
                "@id": PROMPTS_FILE_SET_ID,
                "name": PROMPTS_FILE_SET_ID,
                "encodingFormat": "application/json",
                "includes": FILE_SET_INCLUDES,
            },
        ],
        "recordSet": [
            {
                "@type": "cr:RecordSet",
                "@id": ITEMS_RECORD_SET_ID,
                "name": ITEMS_RECORD_SET_ID,
                "description": "Thirty public S2 compositional BenchItems.",
                "field": _items_fields(),
            },
            {
                "@type": "cr:RecordSet",
                "@id": PROMPTS_RECORD_SET_ID,
                "name": PROMPTS_RECORD_SET_ID,
                "description": (
                    "Frozen-ladder prompt rows (eight per item); join to "
                    "public_s2_items by the item-id prefix of prompt_id."
                ),
                "field": _prompts_fields(),
            },
        ],
    }


def croissant_v0_2_bytes() -> bytes:
    return (json.dumps(build_croissant_v0_2(), indent=2, sort_keys=True) + "\n").encode("utf-8")


def write_croissant_v0_2(path: Path) -> str:
    """Write the deterministic v0.2 Croissant metadata and return its sha256."""

    payload = croissant_v0_2_bytes()
    safe_write_bytes(Path(path), payload, mode=0o644)
    return hashlib.sha256(payload).hexdigest()


def check_croissant_v0_2(path: Path) -> dict[str, Any]:
    """Verify the checked-in Croissant metadata against regenerated bytes."""

    path = Path(path)
    try:
        observed = path.read_bytes()
    except OSError as exc:
        return {
            "status": "failed",
            "path": str(path),
            "sha256": None,
            "recordSets": {},
            "errors": [f"could not read {path}: {exc}"],
        }
    errors: list[str] = []
    digest = hashlib.sha256(observed).hexdigest()
    if observed != croissant_v0_2_bytes():
        errors.append(
            f"{path} differs from the generated v0.2 Croissant metadata "
            f"(regenerate with `python3 bench/run.py croissant-v0.2 --out {path}`)"
        )
    try:
        document = json.loads(observed.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        errors.append(f"{path} is not valid UTF-8 JSON: {exc}")
        document = None
    if isinstance(document, dict):
        if document.get("conformsTo") != "http://mlcommons.org/croissant/1.1":
            errors.append(f"{path} must declare Croissant 1.1 via conformsTo")
        record_set_ids = {
            entry.get("@id")
            for entry in document.get("recordSet", [])
            if isinstance(entry, dict)
        }
        for record_set_id in (ITEMS_RECORD_SET_ID, PROMPTS_RECORD_SET_ID):
            if record_set_id not in record_set_ids:
                errors.append(f"{path} is missing record set {record_set_id}")
    elif document is not None:
        errors.append(f"{path} must contain a JSON object")
    return {
        "status": "failed" if errors else "ok",
        "path": str(path),
        "sha256": digest,
        "recordSets": {
            ITEMS_RECORD_SET_ID: EXPECTED_ITEM_COUNT,
            PROMPTS_RECORD_SET_ID: EXPECTED_PROMPT_COUNT,
        },
        "errors": errors,
    }


def format_croissant_v0_2_check(report: dict[str, Any]) -> str:
    lines = [
        f"status: {report['status']}",
        f"croissant: {report['path']}",
    ]
    if report.get("sha256"):
        lines.append(f"sha256: {report['sha256']}")
    for record_set_id, count in sorted(report.get("recordSets", {}).items()):
        lines.append(f"record set {record_set_id}: {count} rows")
    lines.extend(f"error: {error}" for error in report.get("errors", []))
    return "\n".join(lines)
