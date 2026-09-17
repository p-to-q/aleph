from __future__ import annotations

import hashlib
import json
import os
import shutil
import stat
import tempfile
from pathlib import Path
from typing import Any

from .frozen_ladder import load_items
from .legacy_v0_1 import assert_not_v0_1_write
from .protocol import (
    FROZEN_DATASET_HASH_ALGORITHM,
    FROZEN_DATASET_ID,
    FROZEN_DATASET_ITEM_COUNT,
    FROZEN_DATASET_SHA256,
)
from .scoring_core import PROTOCOL_VERSION, scoring_profile, validate_scoring_runtime
from .schema_validation import load_schema, validate


REPO_ROOT = Path(__file__).resolve().parents[2]
PACKAGE_ID = "aleph-bench-v0.2-scorer-conformance"
PACKAGE_VERSION = "0.2.0"
FIXED_CREATED_AT = "2026-09-17T00:00:00Z"

SCORING_SOURCE_PATH = REPO_ROOT / "bench/engine/scoring_core.py"
CONFORMANCE_SOURCE_PATH = REPO_ROOT / "bench/conformance/scorer-v0.2.json"
ITEMS_SOURCE_DIR = REPO_ROOT / "bench/data/v0.2/public/s2"
ITEM_SCHEMA_SOURCE_PATH = REPO_ROOT / "schemas/v0.2/aleph-bench-item.schema.json"
RESULT_SCHEMA_SOURCE_PATH = REPO_ROOT / "schemas/v0.2/aleph-bench-result.schema.json"
PACKAGE_SCHEMA_SOURCE_PATH = (
    REPO_ROOT / "schemas/v0.2/aleph-bench-platform-package.schema.json"
)

MANIFEST_NAME = "package-manifest.json"
CHECKSUMS_NAME = "checksums.sha256"
RUN_CONFORMANCE_PATH = "kaggle/run_conformance.py"


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _json_bytes(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _jsonl_bytes(rows: list[dict[str, Any]]) -> bytes:
    return (
        "\n".join(
            json.dumps(row, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
            for row in rows
        )
        + "\n"
    ).encode("utf-8")


def _load_v0_2_items() -> list[dict[str, Any]]:
    return load_items(ITEMS_SOURCE_DIR, require_canonical=True)


def _run_conformance_source() -> str:
    return '''#!/usr/bin/env python3
"""Execute Aleph-Bench v0.2 scorer conformance inside this package."""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path


sys.dont_write_bytecode = True
KAGGLE_DIR = Path(__file__).resolve().parent
PACKAGE_ROOT = KAGGLE_DIR.parent
sys.path.insert(0, str(KAGGLE_DIR))

import _scoring  # noqa: E402


FIXTURE_PATH = PACKAGE_ROOT / "conformance/scorer-v0.2.json"


def _same_number(observed: object, expected: object) -> bool:
    if isinstance(expected, bool) or not isinstance(expected, (int, float)):
        return type(observed) is type(expected) and observed == expected
    if isinstance(expected, int):
        return isinstance(observed, int) and not isinstance(observed, bool) and observed == expected
    if isinstance(observed, bool) or not isinstance(observed, (int, float)):
        return False
    if not math.isfinite(expected) or (
        isinstance(observed, float) and not math.isfinite(observed)
    ):
        return False
    return abs(float(observed) - float(expected)) <= 1e-9


def main() -> int:
    fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    errors: list[str] = []
    expected_fixture_fields = {
        "fixtureVersion",
        "protocolVersion",
        "scoringProfile",
        "leakageThresholds",
        "supportedMetricClasses",
        "unsupportedMetricClasses",
        "fidelityVectors",
        "leakageVectors",
    }
    if set(fixture) != expected_fixture_fields:
        errors.append("fixture fields do not match the scorer conformance contract")

    try:
        _scoring.validate_scoring_runtime()
    except Exception as exc:
        errors.append(f"runtime: {exc}")

    if fixture.get("protocolVersion") != _scoring.PROTOCOL_VERSION:
        errors.append(
            "fixture protocolVersion does not match vendored scorer: "
            f"{fixture.get('protocolVersion')!r} != {_scoring.PROTOCOL_VERSION!r}"
        )
    if fixture.get("scoringProfile") != _scoring.scoring_profile():
        errors.append("fixture scoringProfile does not match vendored scorer")
    if tuple(fixture.get("supportedMetricClasses", [])) != _scoring.SUPPORTED_METRIC_CLASSES:
        errors.append("fixture supportedMetricClasses do not match vendored scorer")

    fidelity_checks = 0
    for vector in fixture.get("fidelityVectors", []):
        expected_by_metric = vector.get("expected", {})
        if not isinstance(expected_by_metric, dict) or set(expected_by_metric) != set(
            _scoring.SUPPORTED_METRIC_CLASSES
        ):
            errors.append(
                f"fidelity {vector.get('id')}: expected fields do not match supported metrics"
            )
            continue
        for metric_class, expected in expected_by_metric.items():
            fidelity_checks += 1
            try:
                observed = _scoring.fidelity(
                    vector["target"], vector["output"], metric_class
                )
            except Exception as exc:
                errors.append(f"fidelity {vector.get('id')}/{metric_class}: {exc}")
                continue
            if not _same_number(observed, expected):
                errors.append(
                    f"fidelity {vector.get('id')}/{metric_class}: "
                    f"expected {expected!r}, found {observed!r}"
                )

    leakage_checks = 0
    thresholds = fixture.get("leakageThresholds", {})
    expected_leakage_fields = {
        "disqualified",
        "unit",
        "failClosedReason",
        "lcsRatio",
        "targetTrigramRecall",
        "verbatimSpanUnits",
        "skeletonLcsRatio",
        "skeletonTargetTrigramRecall",
        "skeletonVerbatimSpanUnits",
    }
    for vector in fixture.get("leakageVectors", []):
        leakage_checks += 1
        try:
            observed = _scoring.evaluate_leakage(
                vector["prompt"], vector["target"], thresholds
            ).as_dict()
        except Exception as exc:
            errors.append(f"leakage {vector.get('id')}: {exc}")
            continue
        expected = vector.get("expected", {})
        if not isinstance(expected, dict) or set(expected) != expected_leakage_fields:
            errors.append(
                f"leakage {vector.get('id')}: expected fields do not match scorer output"
            )
            continue
        observed_without_thresholds = {
            field: value for field, value in observed.items() if field != "thresholds"
        }
        if set(observed_without_thresholds) != expected_leakage_fields:
            errors.append(
                f"leakage {vector.get('id')}: scorer fields do not match conformance contract"
            )
            continue
        for field, expected_value in expected.items():
            observed_value = observed.get(field)
            if not _same_number(observed_value, expected_value):
                errors.append(
                    f"leakage {vector.get('id')}/{field}: "
                    f"expected {expected_value!r}, found {observed_value!r}"
                )

    unsupported_checks = 0
    for metric_class in fixture.get("unsupportedMetricClasses", []):
        unsupported_checks += 1
        try:
            _scoring.fidelity("target", "output", metric_class)
        except ValueError:
            pass
        except Exception as exc:
            errors.append(
                f"unsupported metric {metric_class!r} raised {type(exc).__name__}, "
                "expected ValueError"
            )
        else:
            errors.append(f"unsupported metric {metric_class!r} did not fail closed")

    report = {
        "status": "failed" if errors else "ok",
        "protocolVersion": _scoring.PROTOCOL_VERSION,
        "scoringProfile": _scoring.scoring_profile(),
        "fidelityChecks": fidelity_checks,
        "leakageChecks": leakage_checks,
        "unsupportedMetricChecks": unsupported_checks,
        "errors": errors,
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
'''


def _readme_source() -> str:
    return """# Aleph-Bench v0.2 scorer conformance package

This is a deterministic, self-contained contract package for the Aleph-Bench
v0.2 Unicode scorer core. It is integration and conformance staging for a
future Kaggle evaluator; it is **not** itself a complete Kaggle evaluator,
hosted model evidence, or a leaderboard. It does not provide submission I/O,
model execution, AURC/ECL aggregation, or leaderboard hosting.

The file `kaggle/_scoring.py` is copied byte-for-byte from the repository's
canonical `bench/engine/scoring_core.py`. Do not edit the vendored copy. The
shared conformance fixture, 30 public S2 items, and v0.2 item/result schemas are
included so a platform integration can test the exact released contract.

The scorer fails closed unless it runs on Python 3.13 with Unicode database
15.1.0. Run the complete fidelity, leakage, unsupported-metric, and runtime
checks with:

```bash
python3 kaggle/run_conformance.py
```

Verify every declared digest and the package's closed-world file set from the
Aleph repository with `check_v0_2_package(...)`. `package-manifest.json` and
`checksums.sha256` describe all other files in this directory.
"""


def _encoding_for(path: str) -> str:
    if path.endswith(".jsonl"):
        return "application/x-ndjson"
    if path.endswith(".json"):
        return "application/json"
    if path.endswith(".py"):
        return "text/x-python"
    if path.endswith(".md"):
        return "text/markdown"
    return "application/octet-stream"


def _role_for(path: str) -> str:
    return path.split("/", 1)[0] if "/" in path else "docs"


def _artifact_rows(artifact_bytes: dict[str, bytes]) -> list[dict[str, Any]]:
    return [
        {
            "role": _role_for(path),
            "path": path,
            "sha256": _sha256(artifact_bytes[path]),
            "bytes": len(artifact_bytes[path]),
            "encodingFormat": _encoding_for(path),
        }
        for path in sorted(artifact_bytes)
    ]


def _checksums_bytes(artifacts: list[dict[str, Any]]) -> bytes:
    return (
        "\n".join(f"{artifact['sha256']}  {artifact['path']}" for artifact in artifacts)
        + "\n"
    ).encode("utf-8")


def _expected_package() -> tuple[dict[str, Any], dict[str, bytes], bytes]:
    artifact_bytes = {
        "README.md": _readme_source().encode("utf-8"),
        "conformance/scorer-v0.2.json": CONFORMANCE_SOURCE_PATH.read_bytes(),
        "data/public_s2_items.jsonl": _jsonl_bytes(_load_v0_2_items()),
        "kaggle/_scoring.py": SCORING_SOURCE_PATH.read_bytes(),
        RUN_CONFORMANCE_PATH: _run_conformance_source().encode("utf-8"),
        "schemas/aleph-bench-item.schema.json": ITEM_SCHEMA_SOURCE_PATH.read_bytes(),
        "schemas/aleph-bench-platform-package.schema.json": (
            PACKAGE_SCHEMA_SOURCE_PATH.read_bytes()
        ),
        "schemas/aleph-bench-result.schema.json": RESULT_SCHEMA_SOURCE_PATH.read_bytes(),
    }
    artifacts = _artifact_rows(artifact_bytes)
    manifest = {
        "protocolVersion": PROTOCOL_VERSION,
        "packageVersion": PACKAGE_VERSION,
        "id": PACKAGE_ID,
        "createdAt": FIXED_CREATED_AT,
        "datasetId": FROZEN_DATASET_ID,
        "datasetItemCount": FROZEN_DATASET_ITEM_COUNT,
        "datasetSha256": FROZEN_DATASET_SHA256,
        "datasetHashAlgorithm": FROZEN_DATASET_HASH_ALGORITHM,
        "packageKind": "scorer_conformance",
        "evidenceMode": "none",
        "targetPlatforms": ["kaggle_community_benchmark"],
        "scoringProfile": scoring_profile(),
        "artifacts": artifacts,
        "validationCommands": ["python3 kaggle/run_conformance.py"],
        "notes": [
            "The vendored scorer is byte-identical to bench/engine/scoring_core.py.",
            "This scorer-core package is integration and conformance staging, not a complete Kaggle evaluator.",
            "Submission I/O, model execution, AURC/ECL aggregation, and leaderboard hosting are out of scope.",
            "This package is not model evidence or a leaderboard.",
        ],
    }
    return manifest, artifact_bytes, _checksums_bytes(artifacts)


def write_v0_2_package(out_dir: Path) -> dict[str, Any]:
    """Write the deterministic Aleph-Bench v0.2 scorer conformance package."""

    validate_scoring_runtime()
    requested_out_dir = Path(out_dir).absolute()
    if requested_out_dir.exists() or requested_out_dir.is_symlink():
        raise ValueError(
            f"v0.2 package destination must not already exist: {requested_out_dir}"
        )
    out_dir = requested_out_dir.resolve(strict=False)
    assert_not_v0_1_write(out_dir, recursive=True)
    if out_dir.exists() or out_dir.is_symlink():
        raise ValueError(f"v0.2 package destination must not already exist: {out_dir}")
    out_dir.parent.mkdir(parents=True, exist_ok=True)
    manifest, artifact_bytes, checksums = _expected_package()
    validate(manifest, load_schema(PACKAGE_SCHEMA_SOURCE_PATH))
    staging = Path(
        tempfile.mkdtemp(prefix=f".{out_dir.name}.", dir=out_dir.parent)
    )
    try:
        for relative_path, content in artifact_bytes.items():
            path = staging / relative_path
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
        (staging / RUN_CONFORMANCE_PATH).chmod(0o755)
        (staging / CHECKSUMS_NAME).write_bytes(checksums)
        (staging / MANIFEST_NAME).write_bytes(_json_bytes(manifest))
        allowed_files = set(artifact_bytes) | {MANIFEST_NAME, CHECKSUMS_NAME}
        for relative in allowed_files:
            mode = 0o755 if relative == RUN_CONFORMANCE_PATH else 0o644
            (staging / relative).chmod(mode)
        directories = {staging}
        for relative in allowed_files:
            path = staging / relative
            directories.update(path.parents)
        for directory in directories:
            if directory == staging or staging in directory.parents:
                directory.chmod(0o755)
        check = check_v0_2_package(staging / MANIFEST_NAME)
        if check["status"] != "ok":
            raise RuntimeError(
                "staged v0.2 package failed self-check: " + "; ".join(check["errors"])
            )
        staging.rename(out_dir)
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    return manifest


def _safe_artifact_path(value: object) -> str | None:
    if not isinstance(value, str) or not value:
        return None
    if "\\" in value:
        return None
    path = Path(value)
    if path.is_absolute() or ".." in path.parts or path.as_posix() != value:
        return None
    return value


def _expected_directories(allowed_files: set[str]) -> set[str]:
    directories: set[str] = set()
    for relative in allowed_files:
        parent = Path(relative).parent
        while parent != Path("."):
            directories.add(parent.as_posix())
            parent = parent.parent
    return directories


def _inspect_package_layout(
    out_dir: Path, allowed_files: set[str]
) -> tuple[list[str], set[str]]:
    """Inspect without following links and return trusted regular-file paths."""

    errors: list[str] = []
    regular_files: set[str] = set()
    expected_directories = _expected_directories(allowed_files)
    observed_directories: set[str] = set()

    try:
        root_mode = out_dir.lstat().st_mode
    except OSError as exc:
        return [f"package root is unavailable: {exc}"], regular_files
    if stat.S_ISLNK(root_mode):
        return ["package root must not be a symlink"], regular_files
    if not stat.S_ISDIR(root_mode):
        return ["package root must be a directory"], regular_files
    if stat.S_IMODE(root_mode) != 0o755:
        errors.append(
            f"package directory mode mismatch: . expected 0755, "
            f"found {stat.S_IMODE(root_mode):04o}"
        )

    def inspect(directory: Path, relative_directory: str) -> None:
        try:
            entries = sorted(os.scandir(directory), key=lambda entry: entry.name)
        except OSError as exc:
            errors.append(
                f"could not inspect package directory {relative_directory or '.'}: {exc}"
            )
            return
        for entry in entries:
            relative = (
                f"{relative_directory}/{entry.name}"
                if relative_directory
                else entry.name
            )
            try:
                entry_stat = entry.stat(follow_symlinks=False)
                mode = entry_stat.st_mode
            except OSError as exc:
                errors.append(f"could not inspect package entry {relative}: {exc}")
                continue
            if stat.S_ISLNK(mode):
                errors.append(f"unexpected package symlink: {relative}")
            elif stat.S_ISDIR(mode):
                if relative not in expected_directories:
                    errors.append(f"unexpected package directory: {relative}")
                    continue
                observed_directories.add(relative)
                if stat.S_IMODE(mode) != 0o755:
                    errors.append(
                        f"package directory mode mismatch: {relative} expected 0755, "
                        f"found {stat.S_IMODE(mode):04o}"
                    )
                inspect(Path(entry.path), relative)
            elif stat.S_ISREG(mode):
                if relative not in allowed_files:
                    errors.append(f"unexpected package file: {relative}")
                    continue
                regular_files.add(relative)
                if entry_stat.st_nlink != 1:
                    errors.append(
                        f"package file link count mismatch: {relative} expected 1, "
                        f"found {entry_stat.st_nlink}"
                    )
                expected_mode = 0o755 if relative == RUN_CONFORMANCE_PATH else 0o644
                if stat.S_IMODE(mode) != expected_mode:
                    errors.append(
                        f"package file mode mismatch: {relative} expected "
                        f"{expected_mode:04o}, found {stat.S_IMODE(mode):04o}"
                    )
            else:
                errors.append(f"unexpected package non-regular entry: {relative}")

    inspect(out_dir, "")
    for relative in sorted(expected_directories - observed_directories):
        errors.append(f"missing package directory: {relative}")
    return errors, regular_files


def check_v0_2_package(manifest_path: Path) -> dict[str, Any]:
    """Verify deterministic bytes and a closed-world v0.2 package file set."""

    manifest_path = Path(manifest_path)
    out_dir = manifest_path.parent
    errors: list[str] = []
    expected_manifest, expected_bytes, expected_checksums = _expected_package()
    expected_manifest_bytes = _json_bytes(expected_manifest)
    expected_paths = set(expected_bytes)
    allowed_files = expected_paths | {MANIFEST_NAME, CHECKSUMS_NAME}
    layout_errors, regular_files = _inspect_package_layout(out_dir, allowed_files)
    errors.extend(layout_errors)
    canonical_manifest_path = out_dir / MANIFEST_NAME
    if manifest_path.name != MANIFEST_NAME:
        errors.append(
            f"package manifest path must end with {MANIFEST_NAME}, "
            f"found {manifest_path.name}"
        )

    manifest: dict[str, Any] | None = None
    if MANIFEST_NAME not in regular_files:
        errors.append(f"missing {MANIFEST_NAME}")
    else:
        try:
            manifest_bytes = canonical_manifest_path.read_bytes()
            if manifest_bytes != expected_manifest_bytes:
                errors.append(f"{MANIFEST_NAME} is not canonical deterministic JSON")
            loaded = json.loads(manifest_bytes.decode("utf-8"))
            if isinstance(loaded, dict):
                manifest = loaded
                try:
                    validate(manifest, load_schema(PACKAGE_SCHEMA_SOURCE_PATH))
                except Exception as exc:
                    errors.append(f"{MANIFEST_NAME} schema validation failed: {exc}")
            else:
                errors.append(f"{MANIFEST_NAME} must contain a JSON object")
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            errors.append(f"invalid {MANIFEST_NAME}: {exc}")

    declared_artifacts: list[dict[str, Any]] = []
    if manifest is not None:
        for field in (
            "protocolVersion",
            "packageVersion",
            "datasetId",
            "datasetItemCount",
            "datasetSha256",
            "datasetHashAlgorithm",
            "scoringProfile",
            "artifacts",
        ):
            if field not in manifest:
                errors.append(f"manifest missing required field: {field}")
        if manifest.get("protocolVersion") != PROTOCOL_VERSION:
            errors.append(
                f"manifest protocolVersion must be {PROTOCOL_VERSION!r}; "
                f"found {manifest.get('protocolVersion')!r}"
            )
        if manifest.get("packageVersion") != PACKAGE_VERSION:
            errors.append(
                f"manifest packageVersion must be {PACKAGE_VERSION!r}; "
                f"found {manifest.get('packageVersion')!r}"
            )
        if manifest.get("scoringProfile") != scoring_profile():
            errors.append("manifest scoringProfile does not match the canonical scorer")
        raw_artifacts = manifest.get("artifacts")
        if isinstance(raw_artifacts, list):
            declared_artifacts = [row for row in raw_artifacts if isinstance(row, dict)]
            if len(declared_artifacts) != len(raw_artifacts):
                errors.append("manifest artifacts must all be objects")
        else:
            errors.append("manifest artifacts must be an array")
        if manifest != expected_manifest:
            errors.append("package manifest does not match current deterministic package contents")

    seen_paths: set[str] = set()
    for artifact in declared_artifacts:
        relative = _safe_artifact_path(artifact.get("path"))
        if relative is None:
            errors.append(f"unsafe or invalid artifact path: {artifact.get('path')!r}")
            continue
        if relative in seen_paths:
            errors.append(f"duplicate artifact path: {relative}")
            continue
        seen_paths.add(relative)
        path = out_dir / relative
        if relative not in regular_files:
            errors.append(f"missing artifact: {relative}")
            continue
        data = path.read_bytes()
        if artifact.get("sha256") != _sha256(data):
            errors.append(f"digest mismatch: {relative}")
        if artifact.get("bytes") != len(data):
            errors.append(f"size mismatch: {relative}")

    for relative in sorted(expected_paths - seen_paths):
        errors.append(f"missing artifact declaration: {relative}")
    for relative in sorted(expected_paths):
        path = out_dir / relative
        if relative not in regular_files:
            if relative not in seen_paths:
                errors.append(f"missing artifact: {relative}")
            continue
        if path.read_bytes() != expected_bytes[relative]:
            errors.append(f"artifact content is stale: {relative}")

    checksums_path = out_dir / CHECKSUMS_NAME
    if CHECKSUMS_NAME not in regular_files:
        errors.append(f"missing {CHECKSUMS_NAME}")
    elif checksums_path.read_bytes() != expected_checksums:
        errors.append(f"{CHECKSUMS_NAME} does not match the manifest artifact list")

    return {
        "status": "ok" if not errors else "failed",
        "packageManifest": str(manifest_path),
        "protocolVersion": PROTOCOL_VERSION,
        "packageVersion": PACKAGE_VERSION,
        "artifactCount": len(expected_paths),
        "errors": errors,
    }


def format_v0_2_package_check(report: dict[str, Any]) -> str:
    lines = [
        f"status: {report['status']}",
        f"package: {report['packageManifest']}",
        f"protocol version: {report['protocolVersion']}",
        f"package version: {report['packageVersion']}",
        f"artifacts: {report['artifactCount']}",
    ]
    lines.extend(f"error: {error}" for error in report.get("errors", []))
    return "\n".join(lines)
