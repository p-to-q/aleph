"""Strict, fail-closed, read-only import for ``AlephRun`` exports and run bundles.

The importer is the inverse half of the file-first exchange story recorded by
the persistence practice review
(``docs/research/persistence-layer-practice-review.md`` §6, state-of-play
Next Correct Move #4): export exists, and this module adds the strict import
surface. It reads; it never writes.

Two modes, chosen by the shape of ``source``:

- **bundle mode** (``source`` is a directory): run the fail-closed verifier
  over the bundle (full replay; derived files byte-compared to the replayed
  bytes; export files checked when present), then re-derive the ``AlephRun``
  projection from the replayed stream. ``exports/*`` bytes are never trusted
  as data: the value is derived, and any on-disk export that disagrees with
  the replay fails the bundle; a present ``verify.json`` attestation must
  match the recomputed report (it is checked, never rewritten).
  Verification alone accepts kernel-legal runs that closed as ``aborted``;
  the projection step refuses anything that is not a completed run, because
  only completed runs are exportable.
- **file mode** (``source`` is a file): load one ``aleph-run.json`` export
  file. The file must be ``aleph-canonical/0.2.0`` bytes plus a trailing
  newline; duplicate object keys and non-finite number literals fail closed;
  the parsed value must satisfy the strict ``schemas/aleph-run.schema.json``,
  carry a consistent ``artifactRef`` (known version, matching run id,
  well-formed digests, and a matching digest of the projection without the
  ref), and satisfy the derivations the exporter guarantees. A pure file
  import is self-consistent but **not replay-verified**: ``replay_verified``
  is ``False``. To anchor a shared file to a bundle, pass ``bundle_root``:
  the file must then be byte-identical to the projection re-derived from the
  verified bundle, and ``replay_verified`` becomes ``True``.

Failure atomicity is by construction: nothing is created, rewritten, or
repaired under any bundle root, so a failed import leaves every source
unchanged. Cross-store copying is deliberately not part of this surface.

The read side reuses the same projection function the exporter and verifier
call (``export_aleph_run.project_bundle``), so an exported file, a verified
bundle, and an import can never disagree by construction.

Pure standard library. No MLX, no network, no clock, no randomness.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from .archive import (
    ArchiveError,
    VERIFY_NAME,
    BundleSnapshot,
    read_bundle,
)
from .canonical import CanonicalFormError, canonical_bytes, digest, is_digest
from .export_aleph_run import (
    ARTIFACT_REF_SCHEMA_VERSION,
    DEFAULT_SCHEMA_PATH,
    ExportError,
    ProjectionRecord,
    load_target_blob,
    project_bundle,
    validate_against_schema,
)
from .verify import VerificationReport, verify_bundle

_MAX_REPORTED_ERRORS = 25
_UTF8_BOM = b"\xef\xbb\xbf"


class AlephRunImportError(ValueError):
    """Raised when a source cannot be imported as an ``AlephRun`` without loss or invention."""


@dataclass(frozen=True)
class ImportedAlephRun:
    """The validated result of one import.

    - ``source``: ``"bundle"`` when the value was re-derived by replaying a
      verified bundle, ``"file"`` when it was read from an export file.
    - ``value``: the schema-validated ``AlephRun`` projection.
    - ``replay_verified``: True only when the value is anchored to a verified
      bundle replay (bundle mode, or file mode with ``bundle_root``); a pure
      file import is self-consistent but not replay-verified.
    - ``bundle_root``: the verified bundle root, when one was used.
    - ``bundle_digest``: the verified bundle stream digest when
      ``replay_verified``; otherwise the claimed ``artifactRef.bundleDigest``
      (unverified).
    - ``projection_record`` / ``omitted_candidate_ids``: present whenever
      ``replay_verified`` (re-derived from the bundle); ``None`` for a pure
      file import.
    """

    source: str
    run_id: str
    value: dict[str, Any]
    replay_verified: bool
    bundle_root: Path | None
    bundle_digest: str
    projection_record: dict[str, Any] | None
    omitted_candidate_ids: tuple[str, ...] | None

    def to_canonical_bytes(self) -> bytes:
        """The export-file byte form of the imported value (canonical bytes + newline)."""
        return canonical_bytes(self.value) + b"\n"


# ---------------------------------------------------------------------------
# Strict JSON parsing for the export-file form
# ---------------------------------------------------------------------------


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise AlephRunImportError(f"duplicate object key {key!r}")
        result[key] = value
    return result


def _reject_constant(token: str) -> Any:
    raise AlephRunImportError(f"non-finite number literal {token!r} is not valid canonical JSON")


def _strict_json_loads(text: str) -> Any:
    """Parse JSON with duplicate keys and non-finite literals failing closed."""
    return json.loads(
        text,
        object_pairs_hook=_reject_duplicate_keys,
        parse_constant=_reject_constant,
    )


def _first_difference(left: bytes, right: bytes) -> int:
    limit = min(len(left), len(right))
    for index in range(limit):
        if left[index] != right[index]:
            return index
    return limit


def _summarize_errors(label: str, errors: Sequence[str]) -> str:
    shown = list(errors[:_MAX_REPORTED_ERRORS])
    text = f"{label}: " + "; ".join(shown)
    hidden = len(errors) - len(shown)
    if hidden > 0:
        text += f" (+{hidden} more)"
    return text


# ---------------------------------------------------------------------------
# File-mode checks
# ---------------------------------------------------------------------------


def _check_artifact_ref(value: Mapping[str, Any], errors: list[str]) -> None:
    """The artifact ref must bind the projection to its bundle and its own digest."""
    ref = value.get("artifactRef")
    if ref is None:
        errors.append(
            "missing artifactRef: the export file must carry the artifact ref that binds "
            "the projection to its bundle stream and to the projection digest"
        )
        return
    if not isinstance(ref, Mapping):
        errors.append("artifactRef must be a JSON object")
        return
    version = ref.get("schemaVersion")
    if version != ARTIFACT_REF_SCHEMA_VERSION:
        errors.append(
            f"artifactRef.schemaVersion must be {ARTIFACT_REF_SCHEMA_VERSION!r}, got {version!r} "
            "(unknown versions fail closed)"
        )
    run_id = ref.get("runId")
    if run_id != value.get("id"):
        errors.append(f"artifactRef.runId {run_id!r} does not match the run id {value.get('id')!r}")
    for name in ("bundleDigest", "projectionDigest"):
        declared = ref.get(name)
        if not is_digest(declared):
            errors.append(f"artifactRef.{name} must be a sha256: digest, got {declared!r}")
    declared_digest = ref.get("projectionDigest")
    if isinstance(declared_digest, str):
        without_ref = {key: item for key, item in value.items() if key != "artifactRef"}
        try:
            recomputed = digest(without_ref)
        except CanonicalFormError as error:
            errors.append(f"cannot recompute the projection digest: {error}")
        else:
            if recomputed != declared_digest:
                errors.append(
                    "artifactRef.projectionDigest does not match the recomputed digest of the "
                    f"projection without artifactRef (declared {declared_digest}, recomputed "
                    f"{recomputed}): the value was altered after export"
                )


def _check_exporter_invariants(value: Mapping[str, Any], errors: list[str]) -> None:
    """Mirror the derivations the exporter guarantees (called on schema-clean values).

    These fields are derived by the exporter from the projected candidates; a
    standalone file that violates them cannot have been produced by a
    conforming exporter, so it fails closed.
    """
    candidates = value.get("candidates", [])
    if not candidates:
        errors.append(
            "candidates must not be empty: the exporter only writes projections with at "
            "least one measured candidate, and an empty candidate set loses every coordinate"
        )
        return
    ids = [candidate.get("id") for candidate in candidates]
    config = value.get("config", {})
    budget = config.get("budget", {}) if isinstance(config, Mapping) else {}
    if isinstance(budget, Mapping):
        count = budget.get("candidates")
        if count != len(candidates):
            errors.append(
                f"config.budget.candidates must equal the projected candidate count "
                f"({len(candidates)}), got {count!r} (the exporter derives it from the projection)"
            )
        tokens = [candidate.get("tokens") for candidate in candidates]
        if tokens and all(isinstance(item, int) and not isinstance(item, bool) for item in tokens):
            maximum = max(tokens)
            if budget.get("maxPromptTokens") != maximum:
                errors.append(
                    f"config.budget.maxPromptTokens must equal the maximum coordinate token "
                    f"count over candidates ({maximum}), got {budget.get('maxPromptTokens')!r}"
                )
    selected = value.get("selectedCandidateId")
    if isinstance(selected, str) and selected not in ids:
        errors.append(f"selectedCandidateId {selected!r} is not among the projected candidate ids")


def _load_export_value(
    payload: bytes, schema_path: Path | None
) -> tuple[dict[str, Any] | None, list[str]]:
    """Strictly load one export file; returns ``(value, errors)``.

    ``value`` is non-None only when the bytes parsed into a JSON object; it is
    fully trustworthy only when ``errors`` is empty.
    """
    errors: list[str] = []
    if payload.startswith(_UTF8_BOM):
        errors.append("file starts with a UTF-8 byte-order mark; canonical export files do not")
        return None, errors
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError as error:
        errors.append(f"file is not valid UTF-8: {error}")
        return None, errors
    try:
        value = _strict_json_loads(text)
    except ValueError as error:
        errors.append(f"file is not valid strict JSON: {error}")
        return None, errors
    if not isinstance(value, dict):
        errors.append(f"top level must be a JSON object, got {type(value).__name__}")
        return None, errors
    try:
        expected = canonical_bytes(value) + b"\n"
    except CanonicalFormError as error:
        errors.append(f"value cannot be written as aleph-canonical/0.2.0: {error} (fail closed)")
        return None, errors
    if payload != expected:
        if payload == expected[:-1]:
            errors.append("file is missing the trailing newline of the canonical export form")
        else:
            index = _first_difference(payload, expected)
            errors.append(
                "file is not byte-identical to its canonical form (aleph-canonical/0.2.0 bytes "
                f"plus a trailing newline); first difference at byte {index} "
                f"({len(payload)} bytes on disk, {len(expected)} expected)"
            )
        return None, errors
    schema_clean = True
    try:
        schema_errors = validate_against_schema(
            value, schema_path if schema_path is not None else DEFAULT_SCHEMA_PATH
        )
    except ExportError as error:
        schema_clean = False
        schema_errors = [str(error)]
    errors.extend(schema_errors)
    _check_artifact_ref(value, errors)
    if schema_clean:
        _check_exporter_invariants(value, errors)
    return value, errors


# ---------------------------------------------------------------------------
# Bundle mode
# ---------------------------------------------------------------------------


def _check_existing_verification_report(root: Path, report: VerificationReport) -> None:
    """A present ``verify.json`` must equal the recomputed report (mirrors the
    verifier's own rule, without writing anything)."""
    path = root / VERIFY_NAME
    if not path.exists():
        return
    expected = canonical_bytes(report.payload()) + b"\n"
    try:
        existing = path.read_bytes()
    except OSError as error:
        raise AlephRunImportError(f"cannot read {path}: {error}") from error
    if existing != expected:
        raise AlephRunImportError(
            f"{path} does not match the recomputed verification report (tampered or "
            "stale); re-run the verifier to refresh the attestation"
        )


def _verified_replay(
    root: Path, *, schema_path: Path | None
) -> tuple[BundleSnapshot, ProjectionRecord, str]:
    """Verify ``root`` end to end, then re-derive the projection from the replay."""
    report = verify_bundle(root, write_verify_json=False)
    if not report.ok:
        raise AlephRunImportError(
            _summarize_errors(f"bundle {root} failed verification", report.errors)
        )
    _check_existing_verification_report(root, report)
    try:
        snapshot = read_bundle(root)
        record = project_bundle(
            snapshot.manifest,
            snapshot.events,
            load_target_blob(root, snapshot.manifest, snapshot.blobs),
            schema_path=schema_path,
        )
    except (ArchiveError, ExportError, ValueError) as error:
        raise AlephRunImportError(
            f"cannot re-derive the projection from {root}: {error}"
        ) from error
    stream_digest_value = snapshot.manifest.stream_digest
    if stream_digest_value is None:
        raise AlephRunImportError(f"bundle {root} has no closed stream digest")
    return snapshot, record, stream_digest_value


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def import_aleph_run(
    source: str | Path,
    *,
    bundle_root: str | Path | None = None,
    schema_path: str | Path | None = None,
) -> ImportedAlephRun:
    """Import one ``AlephRun`` from an export file or a verified bundle.

    ``source`` is either a bundle directory (fully verified by replay; the
    projection is re-derived from the stream) or a single ``aleph-run.json``
    export file. For a file, pass ``bundle_root`` to anchor the file to a
    bundle: the file must then be byte-identical to the projection re-derived
    from that verified bundle. Read-only; fails closed with
    :class:`AlephRunImportError`.
    """
    source_path = Path(source)
    schema = Path(schema_path) if schema_path is not None else None
    if source_path.is_dir():
        if bundle_root is not None:
            raise AlephRunImportError(
                "source is a bundle directory and bundle_root was also given; pass exactly one"
            )
        snapshot, record, stream_digest_value = _verified_replay(source_path, schema_path=schema)
        return ImportedAlephRun(
            source="bundle",
            run_id=record.run_id,
            value=record.projection,
            replay_verified=True,
            bundle_root=source_path,
            bundle_digest=stream_digest_value,
            projection_record=record.projection_record,
            omitted_candidate_ids=record.omitted_candidate_ids,
        )
    if not source_path.is_file():
        raise AlephRunImportError(
            f"source does not exist or is neither a file nor a directory: {source_path}"
        )
    try:
        payload = source_path.read_bytes()
    except OSError as error:
        raise AlephRunImportError(f"cannot read {source_path}: {error}") from error
    value, errors = _load_export_value(payload, schema)
    if errors or value is None:
        raise AlephRunImportError(_summarize_errors(f"cannot import {source_path}", errors))
    artifact_ref = value["artifactRef"]
    if bundle_root is None:
        return ImportedAlephRun(
            source="file",
            run_id=value["id"],
            value=value,
            replay_verified=False,
            bundle_root=None,
            bundle_digest=artifact_ref["bundleDigest"],
            projection_record=None,
            omitted_candidate_ids=None,
        )
    root = Path(bundle_root)
    snapshot, record, stream_digest_value = _verified_replay(root, schema_path=schema)
    if value["id"] != snapshot.manifest.run_id:
        raise AlephRunImportError(
            f"file run id {value['id']!r} does not match the bundle run id "
            f"{snapshot.manifest.run_id!r}: the file and the bundle are not the same run"
        )
    if artifact_ref["bundleDigest"] != stream_digest_value:
        raise AlephRunImportError(
            f"file claims bundle digest {artifact_ref['bundleDigest']} but the verified bundle "
            f"stream digest is {stream_digest_value}: the file and the bundle are not the same run"
        )
    expected = canonical_bytes(record.projection) + b"\n"
    if payload != expected:
        raise AlephRunImportError(
            f"file differs from the projection re-derived from {root} "
            "(altered, stale, or exported from a different bundle)"
        )
    return ImportedAlephRun(
        source="file",
        run_id=value["id"],
        value=value,
        replay_verified=True,
        bundle_root=root,
        bundle_digest=artifact_ref["bundleDigest"],
        projection_record=record.projection_record,
        omitted_candidate_ids=record.omitted_candidate_ids,
    )
