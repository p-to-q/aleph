from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .frozen_ladder import stable_dataset_path
from .schema_validation import load_schema, validate


REPO_ROOT = Path(__file__).resolve().parents[2]
FIXED_CREATED_AT = "2026-06-03T00:00:00Z"


def _sha256(path: Path) -> tuple[str, int]:
    data = path.read_bytes()
    return hashlib.sha256(data).hexdigest(), len(data)


def _schema_path_for(role: str) -> Path | None:
    if role == "result":
        return REPO_ROOT / "schemas/aleph-bench-result.schema.json"
    if role == "manifest":
        return REPO_ROOT / "schemas/aleph-bench-manifest.schema.json"
    if role == "audit":
        return REPO_ROOT / "schemas/aleph-bench-audit.schema.json"
    return None


def _artifact(role: str, path: Path, *, evidence_mode: str, note: str) -> dict[str, Any]:
    schema_path = _schema_path_for(role)
    if schema_path is not None:
        validate(json.loads(path.read_text(encoding="utf-8")), load_schema(schema_path))
    digest, byte_count = _sha256(path)
    return {
        "role": role,
        "path": stable_dataset_path(path),
        "sha256": digest,
        "bytes": byte_count,
        "evidenceMode": evidence_mode,
        "schemaPath": stable_dataset_path(schema_path) if schema_path is not None else None,
        "note": note,
    }


def build_m0_bundle(
    *,
    result_path: Path,
    manifest_path: Path,
    audit_path: Path,
    report_path: Path,
    evidence_note_path: Path,
) -> dict[str, Any]:
    return {
        "id": "aleph-bench-m0-mock-bundle",
        "createdAt": FIXED_CREATED_AT,
        "status": "ok",
        "evidenceMode": "mock",
        "artifacts": [
            _artifact(
                "result",
                result_path,
                evidence_mode="mock",
                note="Deterministic three-model mock BenchResult.",
            ),
            _artifact(
                "manifest",
                manifest_path,
                evidence_mode="mock",
                note="No-call prompt manifest for the checked-in mock result.",
            ),
            _artifact(
                "audit",
                audit_path,
                evidence_mode="mock",
                note="Generated M0 acceptance-gate receipt.",
            ),
            _artifact(
                "report",
                report_path,
                evidence_mode="mock",
                note="Markdown tables rendered from the mock result JSON.",
            ),
            _artifact(
                "evidence_note",
                evidence_note_path,
                evidence_mode="none",
                note="Interpretive evidence note; not model evidence by itself.",
            ),
        ],
        "validationCommands": [
            "./aleph-bench verify --audit bench/results/m0-audit.json --bundle bench/results/m0-bundle.json",
            "./aleph-bench audit",
            "./aleph-bench bundle --check bench/results/m0-bundle.json",
        ],
        "notes": [
            "This bundle is a file-integrity index for the checked-in deterministic mock M0 evidence.",
            "It is not a real model leaderboard and does not add evidence beyond the referenced artifacts.",
            "Hosted black-box runs should produce their own result, manifest, and report rather than reusing this mock bundle.",
        ],
    }


def compare_bundle(expected: dict[str, Any], actual: dict[str, Any]) -> list[str]:
    if expected == actual:
        return []
    errors = []
    expected_by_role = {artifact["role"]: artifact for artifact in expected.get("artifacts", [])}
    actual_by_role = {artifact["role"]: artifact for artifact in actual.get("artifacts", [])}
    for role in sorted(set(expected_by_role) | set(actual_by_role)):
        expected_artifact = expected_by_role.get(role)
        actual_artifact = actual_by_role.get(role)
        if expected_artifact != actual_artifact:
            errors.append(f"artifact {role} digest or metadata changed")
    for key in ("id", "createdAt", "status", "evidenceMode", "validationCommands", "notes"):
        if expected.get(key) != actual.get(key):
            errors.append(f"bundle field {key} changed")
    return errors or ["bundle changed"]
