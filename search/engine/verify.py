"""Independent fail-closed verifier for Aleph run bundles.

The verifier recomputes every derived artifact from the source stream and
compares it to disk, so it catches corruption rather than trusting any
materialized file. It imports only the artifact kernel — never a scheduler or
search module — and performs no network access and no MLX import.

Checks, all fail-closed:

- layout: unknown top-level files or unknown files under ``exports/``, a
  missing or malformed ``manifest.json``;
- stream: unparseable lines, truncated final writes, altered event content
  digests, reordered or duplicate sequences, duplicate event ids, orphan or
  cyclic parent references, phase-boundary violations (discovery after freeze,
  confirmation before freeze, ``run_completed`` not terminal);
- closed runs: the manifest stream digest must match the stream on disk and
  no blob may be unreferenced;
- blobs: every referenced blob exists and hashes to its digest, and a declared
  target blob exists, hashes, and is valid UTF-8 text;
- receipts: typed proposal/evaluation receipts must parse, match their event
  payloads, cite declared adapters, and report only declared metrics — an
  unknown metric is a failure, never a silent fallback;
- accounting: every adapter call is backed by a prior open budget reservation
  in the right account, every evaluation start has exactly one terminal event,
  every reservation settles exactly once, and a completed run leaves none
  open;
- archive integrity: the archive root digest chain and the frozen archive root
  must match the replayed archive; promoted candidates must be ordinary
  ``candidate`` roles; an ordinary candidate that equals the target text is an
  unlogged target-copy fallback and fails;
- confirmation isolation: the confirmation context digest must not reuse the
  discovery context digest, and confirmation may only evaluate the frozen
  shortlist;
- materialization: all four derived files must exist and equal the replayed
  bytes; ``verify.json`` must equal the recomputed report;
- exports (PR B): when ``exports/`` is present, exactly the two projection
  files must exist and equal the replayed projection byte-for-byte; export
  files in an open run, or a projection the bundle cannot support, fail.

``verify.json`` carries no timestamps: verification is deterministic and
re-runnable byte-identically.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from .archive import (
    EXPORT_NAMES,
    MATERIALIZED_DIR,
    MATERIALIZED_VIEWS,
    TOP_LEVEL_NAMES,
    VERIFY_NAME,
    _atomic_write,
    _blob_path,
    DerivedState,
    DerivationError,
    derive_state,
    load_blobs,
    read_events_with_errors,
    read_manifest,
)
from .canonical import (
    canonical_bytes,
    digest_bytes,
    normalize_text,
)
from .events import check_stream_structure, stream_digest
from .export_aleph_run import ExportError, load_target_blob, project_bundle

VERIFIER_SCHEMA_VERSION = "aleph-verify/0.1.0"


class VerificationError(ValueError):
    """Raised by callers that require a clean report and got a failing one."""


@dataclass(frozen=True)
class VerificationReport:
    """The recomputed, deterministic verdict for one bundle."""

    root: Path
    run_id: str | None
    ok: bool
    errors: tuple[str, ...]
    materialized_digests: dict[str, str] | None
    stream_digest: str | None
    confirmation_outcome: str | None
    archive_digest_at_freeze: str | None

    def payload(self) -> dict[str, Any]:
        return {
            "schemaVersion": VERIFIER_SCHEMA_VERSION,
            "runId": self.run_id,
            "ok": self.ok,
            "errors": list(self.errors),
            "materializedDigests": self.materialized_digests,
            "streamDigest": self.stream_digest,
            "confirmationOutcome": self.confirmation_outcome,
            "archiveDigestAtFreeze": self.archive_digest_at_freeze,
        }


def _verify_target_copy(
    root: Path, manifest: Any, derived: DerivedState, errors: list[str]
) -> None:
    """Fail on an ordinary candidate that copies the target text.

    ``explicit_reconstruction`` is the declared, tagged copy control and is
    exempt by construction; any other candidate whose message content equals
    the target is an unlogged target-copy fallback.
    """
    target_blob = manifest.target_blob_digest
    try:
        target_bytes = _blob_path(root, target_blob).read_bytes()
    except OSError:
        errors.append(f"declared target blob {target_blob} is missing from the bundle")
        return
    if digest_bytes(target_bytes) != target_blob:
        errors.append("target blob content does not match its declared digest")
        return
    try:
        target_text = normalize_text(target_bytes.decode("utf-8"))
    except UnicodeDecodeError as error:
        errors.append(f"target blob is not UTF-8 text: {error}")
        return
    for candidate_id, candidate in sorted(derived.archive_view["candidates"].items()):
        if candidate.get("candidateRole") != "candidate":
            continue
        for message in candidate["messages"]:
            if normalize_text(message["content"]) == target_text:
                errors.append(
                    f"candidate {candidate_id} copies the target text outside the "
                    "explicit_reconstruction control (unlogged target-copy fallback)"
                )
                break


def _verify_materialized(root: Path, derived: DerivedState | None, errors: list[str]) -> None:
    """Compare the four derived files on disk to the replayed bytes."""
    if derived is None:
        return
    payloads = derived.materialized_payloads()
    for name in MATERIALIZED_VIEWS:
        path = root / MATERIALIZED_DIR / f"{name}.json"
        try:
            on_disk = path.read_bytes()
        except OSError:
            errors.append(f"materialized view is missing: {path.name}")
            continue
        expected = canonical_bytes(payloads[name]) + b"\n"
        if on_disk != expected:
            errors.append(
                f"materialized view {path.name} differs from the replayed derivation "
                "(tampered or stale)"
            )


def _verify_unreferenced_blobs(root: Path, events: tuple[Any, ...], manifest: Any, errors: list[str]) -> None:
    """A closed run may not contain blobs no event or the manifest declares."""
    declared = {digest_str for event in events for digest_str in event.blob_digests}
    if manifest.target_blob_digest:
        declared.add(manifest.target_blob_digest)
    blobs_dir = root / "blobs/sha256"
    if not blobs_dir.is_dir():
        return
    for blob_file in sorted(blobs_dir.iterdir()):
        if blob_file.name.startswith("."):
            continue
        if f"sha256:{blob_file.name}" not in declared:
            errors.append(f"unreferenced blob in a closed run: {blob_file.name}")


def _verify_exports(
    root: Path,
    manifest: Any,
    events: tuple[Any, ...],
    blobs: Mapping[str, bytes],
    derived: Any,
    errors: list[str],
) -> None:
    """Attest export files by replaying the same projection the exporter used."""
    exports_dir = root / "exports"
    names = (
        sorted(path.name for path in exports_dir.iterdir() if not path.name.startswith("."))
        if exports_dir.is_dir()
        else []
    )
    if not names:
        return
    allowed = {f"{name}.json" for name in EXPORT_NAMES}
    unknown = sorted(set(names) - allowed)
    missing = sorted(allowed - set(names))
    if unknown:
        errors.append(f"unknown file in exports/: {unknown}")
    if missing:
        errors.append(f"export set is incomplete: missing {missing}")
    if manifest is None:
        errors.append("export files are present but the manifest is invalid")
        return
    if not manifest.closed:
        errors.append("export files are present but the run is not completed (manifest is open)")
        return
    if not events or derived is None:
        errors.append("export files are present but the run cannot be replayed for attestation")
        return
    if unknown or missing:
        return
    try:
        record = project_bundle(manifest, events, load_target_blob(root, manifest, blobs))
    except (ExportError, ValueError) as error:
        errors.append(f"cannot attest export files: {error}")
        return
    expected = {
        "aleph-run.json": canonical_bytes(record.projection) + b"\n",
        "aleph-run-projection.json": canonical_bytes(record.projection_record) + b"\n",
    }
    for name, payload in expected.items():
        try:
            on_disk = (exports_dir / name).read_bytes()
        except OSError as error:
            errors.append(f"cannot read export file {name}: {error}")
            continue
        if on_disk != payload:
            errors.append(f"export file {name} differs from the replayed derivation (tampered or stale)")


def verify_bundle(
    root: Path,
    *,
    require_closed: bool = True,
    write_verify_json: bool = True,
) -> VerificationReport:
    """Verify one bundle from disk and (optionally) write ``verify.json``."""
    root = Path(root)
    errors: list[str] = []
    manifest = None
    derived: DerivedState | None = None
    stream_digest_value: str | None = None
    confirmation_outcome: str | None = None
    archive_digest_at_freeze: str | None = None
    materialized_digests: dict[str, str] | None = None
    run_id: str | None = None

    def report() -> VerificationReport:
        return VerificationReport(
            root=root,
            run_id=run_id,
            ok=not errors,
            errors=tuple(errors),
            materialized_digests=materialized_digests,
            stream_digest=stream_digest_value,
            confirmation_outcome=confirmation_outcome,
            archive_digest_at_freeze=archive_digest_at_freeze,
        )

    if not root.is_dir():
        errors.append(f"bundle root does not exist: {root}")
        result = report()
        if write_verify_json and root.exists():
            _write_report_if_changed(root, result, errors)
            result = report()
        return result

    for path in sorted(root.iterdir()):
        if path.name not in TOP_LEVEL_NAMES:
            errors.append(f"unknown entry in bundle root: {path.name}")
    try:
        manifest = read_manifest(root)
        run_id = manifest.run_id
    except ValueError as error:
        errors.append(f"manifest is invalid: {error}")
        result = report()
        if write_verify_json:
            _write_report_if_changed(root, result, errors)
            result = report()
        return result

    if require_closed and not manifest.closed:
        errors.append("run is not completed (manifest is open)")

    events, parse_errors = read_events_with_errors(root)
    errors.extend(parse_errors)

    blobs: dict[str, bytes] = {}
    if events and not parse_errors:
        try:
            blobs = load_blobs(root, events)
        except ValueError as error:
            errors.append(str(error))
        structure = check_stream_structure(events)
        if structure:
            errors.extend(f"stream structure: {item}" for item in structure)
        else:
            if manifest.closed:
                stream_digest_value = stream_digest(events)
                if stream_digest_value != manifest.stream_digest:
                    errors.append(
                        "manifest stream digest does not match the event stream "
                        "(altered or reordered events)"
                    )
            try:
                derived = derive_state(manifest, events, blobs)
                materialized_digests = dict(derived.digests)
                confirmation_outcome = derived.confirmation_view["outcome"]
                archive_digest_at_freeze = derived.views["archiveDigestAtFreeze"]
            except (DerivationError, ValueError) as error:
                errors.append(f"derivation failed: {error}")
            if manifest.closed:
                _verify_unreferenced_blobs(root, events, manifest, errors)
                if derived is not None and manifest.target_blob_digest:
                    _verify_target_copy(root, manifest, derived, errors)

    _verify_materialized(root, derived, errors)
    if manifest is not None:
        _verify_exports(root, manifest, events if not parse_errors else (), blobs, derived, errors)

    result = report()
    if write_verify_json:
        _write_report_if_changed(root, result, errors)
        result = report()
    return result


def _write_report_if_changed(root: Path, report: VerificationReport, errors: list[str]) -> None:
    """Write ``verify.json`` deterministically, or fail closed on a mismatch.

    An existing ``verify.json`` must equal the recomputed report. Writing uses
    an atomic replace, so a crash never leaves a partial report.

    This function may append errors, so callers must rebuild the report after
    it returns.
    """
    verify_path = root / VERIFY_NAME
    expected = canonical_bytes(report.payload()) + b"\n"
    if verify_path.exists():
        try:
            existing = verify_path.read_bytes()
        except OSError as error:
            errors.append(f"cannot read verify.json: {error}")
            return
        if existing != expected:
            errors.append("verify.json does not match the recomputed report (tampered)")
            return
    try:
        _atomic_write(verify_path, expected)
    except OSError as error:
        errors.append(f"cannot write verify.json: {error}")
