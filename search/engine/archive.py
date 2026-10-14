"""Append-only run bundle: layout, writer, reader, and materializer.

Layout, exactly as specified in issue #106:

```text
runs/<run_id>/
  manifest.json
  events.jsonl
  blobs/sha256/<digest>
  materialized/{archive,views,confirmation,resource-ledger}.json
  exports/{aleph-run,aleph-run-projection}.json
  verify.json
```

``events.jsonl`` is the only authority. Everything under ``materialized/`` is
derived by replaying that stream, so a view can be deleted and rebuilt
byte-identically. Views select and order candidates that the archive already
contains; they may never invent or mutate one.

Writes are append-only: the writer refuses to rewrite an existing event line
and refuses to overwrite a blob whose digest already exists with different
bytes. Blobs are content-addressed, so an identical write is a no-op rather
than a conflict. ``manifest.json`` is written at creation and rewritten exactly
once at ``close()`` (atomic replace) to record the final stream digest;
``events.jsonl`` itself is never rewritten.

PR A materializes the archive, views, confirmation, and ledger. ``exports/`` is
PR B's measurement-lossless projection and is intentionally not written here;
the verifier rejects any run that contains export files it cannot attest.

Pure standard library.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from .canonical import (
    canonical_bytes,
    canonical_json,
    canonicalize,
    digest,
    digest_bytes,
    is_digest,
)
from .contracts import (
    evaluation_receipt_from_canonical,
    proposal_receipt_from_canonical,
)
from .events import (
    EVENT_SCHEMA_VERSION,
    Event,
    EventError,
    check_stream_structure,
    critical_path_length,
    event_from_canonical,
    stream_digest,
)
from .ledger import (
    NESTING_RULES,
    LedgerError,
    Reservation,
    ResourceLedger,
    coordinate_cost_from_canonical,
)

BUNDLE_SCHEMA_VERSION = "aleph-run-bundle/0.1.0"
ENGINE_VERSION = "aleph-engine/0.1.0"

ARCHIVE_VIEW_SCHEMA_VERSION = "aleph-archive-view/0.1.0"
VIEWS_SCHEMA_VERSION = "aleph-views/0.1.0"
CONFIRMATION_VIEW_SCHEMA_VERSION = "aleph-confirmation-view/0.1.0"

MANIFEST_NAME = "manifest.json"
EVENTS_NAME = "events.jsonl"
BLOBS_DIR = "blobs/sha256"
MATERIALIZED_DIR = "materialized"
EXPORTS_DIR = "exports"
VERIFY_NAME = "verify.json"

MATERIALIZED_VIEWS = ("archive", "views", "confirmation", "resource-ledger")
EXPORT_NAMES = ("aleph-run", "aleph-run-projection")

# Names allowed at the top level of a bundle. Anything else is a partial or
# stray write and fails closed in the verifier.
TOP_LEVEL_NAMES = frozenset(
    {MANIFEST_NAME, EVENTS_NAME, "blobs", MATERIALIZED_DIR, EXPORTS_DIR, VERIFY_NAME}
)

# Per-stage decoder work declared by evaluation receipts (T_dec evidence).
_DECODER_RESOURCE_KEYS = (
    "inputTokens",
    "outputTokens",
    "samples",
    "providerReportedTokens",
    "failures",
)

# Per-call search-work extras declared by receipts (W_search evidence).
_SEARCH_WORK_RESOURCE_KEYS = ("retries", "cacheMisses")

class ArchiveError(ValueError):
    """Raised when the bundle layout or an append-only rule is violated."""


class DerivationError(ValueError):
    """Raised when the event stream cannot be replayed into derived state."""


@dataclass(frozen=True)
class RunManifest:
    """Bundle-level declaration of target, metrics, adapters, and accounting policy.

    No timestamps appear anywhere in the manifest: a replayed build must be
    byte-identical, and wall-clock time is not part of the research evidence.
    """

    run_id: str
    target_digest: str
    known_metrics: tuple[str, ...]
    adapter_digests: tuple[str, ...]
    nesting_rule: str
    scheduler_model: str
    model_manifest: Mapping[str, Any]
    target_blob_digest: str | None = None
    closed: bool = False
    stream_digest: str | None = None
    bundle_schema_version: str = BUNDLE_SCHEMA_VERSION
    engine_version: str = ENGINE_VERSION
    event_schema_version: str = EVENT_SCHEMA_VERSION
    canonical_schema_version: str = "aleph-canonical/0.1.0"
    contracts_schema_version: str = "aleph-engine-contracts/0.1.0"
    ledger_schema_version: str = "ResourceLedger/0.1.0"

    def __post_init__(self) -> None:
        if not isinstance(self.run_id, str) or not self.run_id:
            raise ArchiveError("manifest requires a non-empty run id")
        if not is_digest(self.target_digest):
            raise ArchiveError("manifest target digest must be a well-formed digest")
        if self.target_blob_digest is not None and not is_digest(self.target_blob_digest):
            raise ArchiveError("manifest target blob digest must be a well-formed digest")
        if not isinstance(self.known_metrics, tuple) or not self.known_metrics:
            raise ArchiveError("manifest requires a non-empty tuple of known metrics")
        if len(set(self.known_metrics)) != len(self.known_metrics):
            raise ArchiveError("manifest known metrics must be unique")
        for metric in self.known_metrics:
            if not isinstance(metric, str) or not metric:
                raise ArchiveError("manifest metric names must be non-empty str")
        if not isinstance(self.adapter_digests, tuple) or not self.adapter_digests:
            raise ArchiveError("manifest requires a non-empty tuple of adapter digests")
        if len(set(self.adapter_digests)) != len(self.adapter_digests):
            raise ArchiveError("manifest adapter digests must be unique")
        for adapter_digest in self.adapter_digests:
            if not is_digest(adapter_digest):
                raise ArchiveError("manifest adapter digests must be well-formed digests")
        if self.nesting_rule not in NESTING_RULES:
            raise ArchiveError(f"unknown nesting rule: {self.nesting_rule!r}")
        if not isinstance(self.scheduler_model, str) or not self.scheduler_model:
            raise ArchiveError("manifest requires a non-empty scheduler model")
        if not isinstance(self.model_manifest, Mapping) or not self.model_manifest:
            raise ArchiveError("manifest requires a non-empty model manifest")
        if not isinstance(self.closed, bool):
            raise ArchiveError("manifest closed must be a bool")
        if self.closed and self.stream_digest is None:
            raise ArchiveError("a closed manifest requires a stream digest")
        if not self.closed and self.stream_digest is not None:
            raise ArchiveError("an open manifest must not carry a stream digest")
        if self.stream_digest is not None and not is_digest(self.stream_digest):
            raise ArchiveError("manifest stream digest must be a well-formed digest")
        for name in (
            "bundle_schema_version",
            "engine_version",
            "event_schema_version",
            "canonical_schema_version",
            "contracts_schema_version",
            "ledger_schema_version",
        ):
            value = getattr(self, name)
            if not isinstance(value, str) or not value:
                raise ArchiveError(f"manifest requires {name}")

    def to_canonical(self) -> dict[str, Any]:
        return {
            "runId": self.run_id,
            "bundleSchemaVersion": self.bundle_schema_version,
            "engineVersion": self.engine_version,
            "eventSchemaVersion": self.event_schema_version,
            "canonicalSchemaVersion": self.canonical_schema_version,
            "contractsSchemaVersion": self.contracts_schema_version,
            "ledgerSchemaVersion": self.ledger_schema_version,
            "targetDigest": self.target_digest,
            "targetBlobDigest": self.target_blob_digest,
            "knownMetrics": list(self.known_metrics),
            "adapterDigests": list(self.adapter_digests),
            "nestingRule": self.nesting_rule,
            "schedulerModel": self.scheduler_model,
            "modelManifest": canonicalize(dict(self.model_manifest)),
            "closed": self.closed,
            "streamDigest": self.stream_digest,
        }


def manifest_from_canonical(payload: Mapping[str, Any]) -> RunManifest:
    """Rebuild a ``RunManifest`` from its canonical form, rejecting unknown fields."""
    if not isinstance(payload, Mapping):
        raise ArchiveError("manifest payload must be a mapping")
    allowed = {
        "runId",
        "bundleSchemaVersion",
        "engineVersion",
        "eventSchemaVersion",
        "canonicalSchemaVersion",
        "contractsSchemaVersion",
        "ledgerSchemaVersion",
        "targetDigest",
        "targetBlobDigest",
        "knownMetrics",
        "adapterDigests",
        "nestingRule",
        "schedulerModel",
        "modelManifest",
        "closed",
        "streamDigest",
    }
    unknown = set(payload) - allowed
    if unknown:
        raise ArchiveError(f"manifest has unknown fields: {sorted(unknown)}")

    def require(name: str) -> Any:
        if name not in payload:
            raise ArchiveError(f"manifest is missing required field {name!r}")
        return payload[name]

    known_metrics = require("knownMetrics")
    adapter_digests = require("adapterDigests")
    model_manifest = require("modelManifest")
    if not isinstance(known_metrics, list):
        raise ArchiveError("manifest knownMetrics must be a list")
    if not isinstance(adapter_digests, list):
        raise ArchiveError("manifest adapterDigests must be a list")
    if not isinstance(model_manifest, Mapping) or not model_manifest:
        raise ArchiveError("manifest modelManifest must be a non-empty mapping")
    return RunManifest(
        run_id=require("runId"),
        target_digest=require("targetDigest"),
        known_metrics=tuple(known_metrics),
        adapter_digests=tuple(adapter_digests),
        nesting_rule=require("nestingRule"),
        scheduler_model=require("schedulerModel"),
        model_manifest=model_manifest,
        target_blob_digest=payload.get("targetBlobDigest"),
        closed=require("closed"),
        stream_digest=payload.get("streamDigest"),
        bundle_schema_version=payload.get("bundleSchemaVersion", BUNDLE_SCHEMA_VERSION),
        engine_version=payload.get("engineVersion", ENGINE_VERSION),
        event_schema_version=payload.get("eventSchemaVersion", EVENT_SCHEMA_VERSION),
        canonical_schema_version=payload.get("canonicalSchemaVersion", "aleph-canonical/0.1.0"),
        contracts_schema_version=payload.get(
            "contractsSchemaVersion", "aleph-engine-contracts/0.1.0"
        ),
        ledger_schema_version=payload.get("ledgerSchemaVersion", "ResourceLedger/0.1.0"),
    )


def _atomic_write(path: Path, payload: bytes) -> None:
    """Write ``payload`` to ``path`` via a same-directory temp file and rename."""
    tmp = path.with_name(path.name + ".tmp")
    with open(tmp, "wb") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp, path)


def _blob_path(root: Path, blob_digest: str) -> Path:
    return root / BLOBS_DIR / blob_digest.split(":", 1)[1]


def _read_json_mapping(path: Path, label: str) -> Mapping[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ArchiveError(f"cannot read {label}: {error}") from error
    if not isinstance(payload, Mapping):
        raise ArchiveError(f"{label} must contain a JSON object")
    return payload


def read_manifest(root: Path) -> RunManifest:
    """Read and validate ``manifest.json``."""
    return manifest_from_canonical(_read_json_mapping(root / MANIFEST_NAME, "manifest.json"))


def read_events_with_errors(root: Path) -> tuple[tuple[Event, ...], list[str]]:
    """Parse ``events.jsonl`` strictly, collecting every defect.

    A file that does not end in a newline, contains a blank line, or carries a
    line that is not valid canonical event JSON is rejected: partial writes are
    corruption, not evidence.
    """
    path = root / EVENTS_NAME
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as error:
        return (), [f"cannot read events.jsonl: {error}"]
    if not text:
        return (), ["events.jsonl is empty"]
    if not text.endswith("\n"):
        return (), ["events.jsonl does not end in a newline (truncated write)"]
    events: list[Event] = []
    errors: list[str] = []
    for index, line in enumerate(text.splitlines()):
        if not line.strip():
            errors.append(f"events.jsonl line {index + 1} is blank")
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError as error:
            errors.append(f"events.jsonl line {index + 1} is not valid JSON: {error}")
            continue
        try:
            events.append(event_from_canonical(record))
        except (EventError, ValueError) as error:
            errors.append(f"events.jsonl line {index + 1}: {error}")
    return tuple(events), errors


def read_events(root: Path) -> tuple[Event, ...]:
    """Parse ``events.jsonl``, raising on the first defect."""
    events, errors = read_events_with_errors(root)
    if errors:
        raise ArchiveError("; ".join(errors))
    return events


def load_blobs(root: Path, events: Sequence[Event]) -> dict[str, bytes]:
    """Load every referenced blob, verifying each against its declared digest."""
    blobs: dict[str, bytes] = {}
    for event in events:
        for blob_digest in event.blob_digests:
            if blob_digest in blobs:
                continue
            path = _blob_path(root, blob_digest)
            try:
                payload = path.read_bytes()
            except OSError as error:
                raise ArchiveError(f"referenced blob {blob_digest} is missing: {error}")
            if digest_bytes(payload) != blob_digest:
                raise ArchiveError(
                    f"blob {blob_digest} content does not match its declared digest"
                )
            blobs[blob_digest] = payload
    return blobs


@dataclass(frozen=True)
class BundleSnapshot:
    """A bundle read from disk: manifest, validated events, and resolved blobs."""

    root: Path
    manifest: RunManifest
    events: tuple[Event, ...]
    blobs: dict[str, bytes]


def read_bundle(root: Path) -> BundleSnapshot:
    """Read a complete bundle, failing closed on any defect."""
    manifest = read_manifest(root)
    events, errors = read_events_with_errors(root)
    if errors:
        raise ArchiveError("; ".join(errors))
    structure = check_stream_structure(events)
    if structure:
        raise ArchiveError("event stream structure is invalid: " + "; ".join(structure))
    blobs = load_blobs(root, events)
    return BundleSnapshot(root=root, manifest=manifest, events=events, blobs=blobs)


class RunBundle:
    """Append-only writer over ``runs/<run_id>/``.

    Created by :meth:`create`, resumed by :meth:`open_for_append`. Every
    ``append_event`` enforces the next sequence number, unique event ids, and
    content-addressed blob writes before the event line is appended.
    """

    def __init__(self, root: Path, manifest: RunManifest) -> None:
        self._root = root
        self._manifest = manifest
        self._next_sequence = 0
        self._seen_event_ids: set[str] = set()

    @property
    def root(self) -> Path:
        return self._root

    @property
    def manifest(self) -> RunManifest:
        return self._manifest

    @property
    def next_sequence(self) -> int:
        return self._next_sequence

    @property
    def run_id(self) -> str:
        return self._manifest.run_id

    @classmethod
    def create(
        cls,
        root: Path,
        *,
        run_id: str,
        target_digest: str,
        target_content: str | None = None,
        known_metrics: Sequence[str],
        adapter_digests: Sequence[str],
        nesting_rule: str,
        scheduler_model: str,
        model_manifest: Mapping[str, Any],
    ) -> "RunBundle":
        """Create a fresh bundle: layout, manifest, target blob, and ``run_started``."""
        if root.exists():
            if any(root.iterdir()):
                raise ArchiveError(f"refusing to create a bundle in a non-empty root: {root}")
        else:
            root.mkdir(parents=True)
        (root / BLOBS_DIR).mkdir(parents=True)
        (root / MATERIALIZED_DIR).mkdir(parents=True)
        (root / EXPORTS_DIR).mkdir(parents=True)
        (root / EVENTS_NAME).write_text("", encoding="utf-8")

        manifest = RunManifest(
            run_id=run_id,
            target_digest=target_digest,
            known_metrics=tuple(known_metrics),
            adapter_digests=tuple(adapter_digests),
            nesting_rule=nesting_rule,
            scheduler_model=scheduler_model,
            model_manifest=canonicalize(dict(model_manifest)),
        )
        bundle = cls(root, manifest)
        if target_content is not None:
            target_blob = bundle.store_blob_bytes(target_content.encode("utf-8"))
            manifest = RunManifest(
                run_id=run_id,
                target_digest=target_digest,
                known_metrics=tuple(known_metrics),
                adapter_digests=tuple(adapter_digests),
                nesting_rule=nesting_rule,
                scheduler_model=scheduler_model,
                model_manifest=canonicalize(dict(model_manifest)),
                target_blob_digest=target_blob,
            )
            bundle._manifest = manifest
        bundle._write_manifest()
        bundle.append_event(
            Event(
                event_id=f"{run_id}:run-started",
                sequence=0,
                event_type="run_started",
                phase="run",
                payload={"runId": run_id},
            )
        )
        return bundle

    @classmethod
    def open_for_append(cls, root: Path) -> "RunBundle":
        """Reopen an unfinished bundle for append-only resume."""
        snapshot = read_bundle(root)
        if snapshot.manifest.closed:
            raise ArchiveError("cannot append to a closed bundle")
        bundle = cls(root, snapshot.manifest)
        bundle._next_sequence = len(snapshot.events)
        bundle._seen_event_ids = {event.event_id for event in snapshot.events}
        return bundle

    def _write_manifest(self) -> None:
        _atomic_write(
            self._root / MANIFEST_NAME,
            canonical_bytes(self._manifest.to_canonical()) + b"\n",
        )

    def store_blob_bytes(self, payload: bytes) -> str:
        """Store raw bytes content-addressed, returning the prefixed digest."""
        if not isinstance(payload, bytes):
            raise ArchiveError("blob payload must be bytes")
        blob_digest = digest_bytes(payload)
        path = _blob_path(self._root, blob_digest)
        if path.exists():
            existing = path.read_bytes()
            if existing != payload:
                raise ArchiveError(f"blob digest collision at {path.name}: different bytes")
            return blob_digest
        _atomic_write(path, payload)
        return blob_digest

    def store_blob(self, value: Any) -> str:
        """Store a value as its canonical JSON bytes, content-addressed."""
        return self.store_blob_bytes(canonical_bytes(value))

    def append_event(self, event: Event, *, blobs: Mapping[str, bytes] | None = None) -> Event:
        """Append one validated event (and any blobs) to the bundle.

        Blobs are written before the event line, so a crash can leave orphan
        blobs but never an event that references a missing blob. Event ids must
        be unique and sequences strictly consecutive.
        """
        if not isinstance(event, Event):
            raise ArchiveError("append_event requires an Event")
        if self._manifest.closed:
            raise ArchiveError("cannot append to a closed bundle")
        if event.sequence != self._next_sequence:
            raise ArchiveError(
                f"event {event.event_id!r} has sequence {event.sequence}, "
                f"expected {self._next_sequence}"
            )
        if event.event_id in self._seen_event_ids:
            raise ArchiveError(f"duplicate event id: {event.event_id!r}")
        for blob_digest, payload in (blobs or {}).items():
            if not is_digest(blob_digest):
                raise ArchiveError(f"malformed blob digest: {blob_digest!r}")
            self.store_blob_bytes(payload)
        line = canonical_json(event.to_canonical()) + "\n"
        with open(self._root / EVENTS_NAME, "a", encoding="utf-8", newline="\n") as handle:
            handle.write(line)
            handle.flush()
            os.fsync(handle.fileno())
        self._seen_event_ids.add(event.event_id)
        self._next_sequence += 1
        return event

    def close(self, status: str = "completed") -> None:
        """Append the terminal ``run_completed`` event and seal the manifest."""
        if status not in ("completed", "aborted"):
            raise ArchiveError(f"unknown run status: {status!r}")
        if self._manifest.closed:
            raise ArchiveError("bundle is already closed")
        self.append_event(
            Event(
                event_id=f"{self.run_id}:run-completed",
                sequence=self._next_sequence,
                event_type="run_completed",
                phase="run",
                payload={"status": status},
            )
        )
        events = read_events(self._root)
        current = self._manifest
        self._manifest = RunManifest(
            run_id=current.run_id,
            target_digest=current.target_digest,
            known_metrics=current.known_metrics,
            adapter_digests=current.adapter_digests,
            nesting_rule=current.nesting_rule,
            scheduler_model=current.scheduler_model,
            model_manifest=current.model_manifest,
            target_blob_digest=current.target_blob_digest,
            closed=True,
            stream_digest=stream_digest(events),
        )
        self._write_manifest()


@dataclass(frozen=True)
class DerivedState:
    """Everything replayable from a bundle, plus the digests of its materializations."""

    archive_view: dict[str, Any]
    views: dict[str, Any]
    confirmation_view: dict[str, Any]
    ledger: ResourceLedger
    digests: dict[str, str]
    promoted_candidate_ids: tuple[str, ...]
    rejected_candidate_ids: tuple[str, ...]

    def materialized_payloads(self) -> dict[str, Any]:
        return {
            "archive": self.archive_view,
            "views": self.views,
            "confirmation": self.confirmation_view,
            "resource-ledger": self.ledger.to_canonical(),
        }


def _receipt_from_blob(blobs: Mapping[str, bytes], blob_digests: Sequence[str], label: str) -> Any:
    try:
        record = json.loads(blobs[blob_digests[0]])
    except (KeyError, IndexError, json.JSONDecodeError) as error:
        raise DerivationError(f"{label} receipt blob is unavailable or unreadable: {error}")
    return record


def _check_adapter_digest(adapter_digest: str, manifest: RunManifest, label: str) -> None:
    if adapter_digest not in manifest.adapter_digests:
        raise DerivationError(
            f"{label} receipt adapter {adapter_digest} is not declared in the manifest"
        )


def _resource_int(resource_use: tuple[tuple[str, Any], ...], key: str) -> int:
    """Extract a non-negative int declared by a receipt's resource use."""
    values = [value for name, value in resource_use if name == key]
    if not values:
        return 0
    value = values[-1]
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise DerivationError(f"receipt resource use {key!r} must be a non-negative int")
    return value


def derive_state(
    manifest: RunManifest, events: Sequence[Event], blobs: Mapping[str, bytes]
) -> DerivedState:
    """Replay a validated event stream into archive, views, confirmation, and ledger.

    This is the single derivation used by the materializer, the replay adapter,
    and the verifier, so all three agree by construction. It raises
    :class:`DerivationError` on the first inconsistency.
    """
    structure = check_stream_structure(events)
    if structure:
        raise DerivationError("event stream structure is invalid: " + "; ".join(structure))

    ledger = ResourceLedger(
        nesting_rule=manifest.nesting_rule,
        scheduler_model=manifest.scheduler_model,
        model_manifest=manifest.model_manifest,
    )
    candidates: dict[str, dict[str, Any]] = {}
    archive: dict[str, dict[str, Any]] = {}
    promoted: list[str] = []
    rejected: list[str] = []
    archive_root_digest: str | None = None

    freeze_seen = False
    shortlist: list[str] = []
    selection_rule: str | None = None
    discovery_context_digest: str | None = None
    confirmation_started_seen = False
    confirmation_context_digest: str | None = None
    confirmation_seed: str | None = None
    confirmation_outcome: str | None = None
    confirmed_candidate_id: str | None = None
    run_completed_seen = False
    completion_status: str | None = None

    started_evaluations: dict[str, tuple[str, str]] = {}
    terminated_evaluations: set[str] = set()

    w_search = {
        "proposal_calls": 0,
        "proposal_failures": 0,
        "evaluation_calls": 0,
        "evaluation_failures": 0,
        "retries": 0,
        "cache_misses": 0,
        "rejected_candidates": 0,
        "proposed_candidates": 0,
    }
    verify_work = {"fresh_samples": 0, "replays": 0, "tests": 0, "human_checks": 0, "proof_checks": 0}

    def candidate_canonical(candidate_id: str, label: str) -> dict[str, Any]:
        canonical = candidates.get(candidate_id)
        if canonical is None:
            raise DerivationError(f"{label} references undefined candidate {candidate_id}")
        return canonical

    for event in events:
        event_type = event.event_type
        payload = event.payload

        if event_type == "run_started":
            if payload["runId"] != manifest.run_id:
                raise DerivationError(
                    f"run_started declares run {payload['runId']!r}, manifest declares {manifest.run_id!r}"
                )

        elif event_type == "budget_reserved":
            reservation = Reservation(
                reservation_id=payload["reservationId"],
                account=payload["account"],
                stage=payload["stage"],
                event_id=event.event_id,
            )
            try:
                ledger.reserve(reservation)
            except LedgerError as error:
                raise DerivationError(f"budget_reserved {event.event_id}: {error}")

        elif event_type in ("budget_committed", "budget_failed"):
            reservation_id = payload["reservationId"]
            outcome = "committed" if event_type == "budget_committed" else "failed"
            try:
                reservation = ledger.settle(reservation_id, outcome)
            except LedgerError as error:
                raise DerivationError(f"{event_type} {event.event_id}: {error}")
            if payload["account"] != reservation.account or payload["stage"] != reservation.stage:
                raise DerivationError(
                    f"{event_type} {event.event_id} does not match its reservation "
                    f"{reservation_id} ({reservation.account}/{reservation.stage})"
                )

        elif event_type == "proposal_succeeded":
            try:
                reservation = ledger.require_open(payload["reservationId"])
            except LedgerError as error:
                raise DerivationError(f"proposal_succeeded {event.event_id}: {error}")
            if reservation.account != "W_search":
                raise DerivationError(
                    f"proposal call is charged to {reservation.account}, expected W_search"
                )
            record = _receipt_from_blob(blobs, event.blob_digests, "proposal")
            receipt = proposal_receipt_from_canonical(record)
            if receipt.request_id != payload["requestId"]:
                raise DerivationError(
                    f"proposal receipt request {receipt.request_id!r} does not match "
                    f"event payload {payload['requestId']!r}"
                )
            _check_adapter_digest(receipt.adapter.adapter_digest, manifest, "proposal")
            receipt_ids = [candidate.candidate_id for candidate in receipt.candidates]
            if receipt_ids != payload["candidateIds"]:
                raise DerivationError(
                    f"proposal receipt candidate ids {receipt_ids} do not match "
                    f"event payload {payload['candidateIds']}"
                )
            for candidate in receipt.candidates:
                canonical = candidate.to_canonical()
                existing = candidates.get(candidate.candidate_id)
                if existing is not None:
                    raise DerivationError(
                        f"duplicate proposal of candidate identity {candidate.candidate_id}"
                    )
                candidates[candidate.candidate_id] = canonical
            w_search["proposal_calls"] += 1
            w_search["proposed_candidates"] += len(receipt.candidates)
            w_search["retries"] += _resource_int(receipt.resource_use, "retries")
            w_search["cache_misses"] += _resource_int(receipt.resource_use, "cacheMisses")

        elif event_type == "proposal_failed":
            try:
                reservation = ledger.require_open(payload["reservationId"])
            except LedgerError as error:
                raise DerivationError(f"proposal_failed {event.event_id}: {error}")
            if reservation.account != "W_search":
                raise DerivationError(
                    f"proposal call is charged to {reservation.account}, expected W_search"
                )
            if event.blob_digests:
                record = _receipt_from_blob(blobs, event.blob_digests, "proposal failure")
                receipt = proposal_receipt_from_canonical(record)
                if receipt.request_id != payload["requestId"]:
                    raise DerivationError(
                        f"proposal failure receipt request {receipt.request_id!r} does not "
                        f"match event payload {payload['requestId']!r}"
                    )
                _check_adapter_digest(receipt.adapter.adapter_digest, manifest, "proposal failure")
            w_search["proposal_calls"] += 1
            w_search["proposal_failures"] += 1

        elif event_type == "evaluation_started":
            try:
                reservation = ledger.require_open(payload["reservationId"])
            except LedgerError as error:
                raise DerivationError(f"evaluation_started {event.event_id}: {error}")
            if reservation.account != "T_dec":
                raise DerivationError(
                    f"evaluation call is charged to {reservation.account}, expected T_dec"
                )
            candidate_canonical(payload["candidateId"], "evaluation_started")
            if payload["requestId"] in started_evaluations:
                raise DerivationError(
                    f"evaluation request started twice: {payload['requestId']}"
                )
            started_evaluations[payload["requestId"]] = (
                payload["candidateId"],
                event.phase,
            )

        elif event_type == "evaluation_completed":
            started = started_evaluations.pop(payload["requestId"], None)
            if started is None:
                raise DerivationError(
                    f"evaluation_completed without a started request: {payload['requestId']}"
                )
            if started[0] != payload["candidateId"]:
                raise DerivationError(
                    f"evaluation_completed candidate {payload['candidateId']!r} does not "
                    f"match its started request {started[0]!r}"
                )
            if payload["requestId"] in terminated_evaluations:
                raise DerivationError(
                    f"evaluation request terminated twice: {payload['requestId']}"
                )
            terminated_evaluations.add(payload["requestId"])
            try:
                reservation = ledger.require_open(payload["reservationId"])
            except LedgerError as error:
                raise DerivationError(f"evaluation_completed {event.event_id}: {error}")
            if reservation.account != "T_dec":
                raise DerivationError(
                    f"evaluation call is charged to {reservation.account}, expected T_dec"
                )
            record = _receipt_from_blob(blobs, event.blob_digests, "evaluation")
            receipt = evaluation_receipt_from_canonical(record)
            if receipt.request_id != payload["requestId"]:
                raise DerivationError(
                    f"evaluation receipt request {receipt.request_id!r} does not match "
                    f"event payload {payload['requestId']!r}"
                )
            if receipt.candidate_id != payload["candidateId"]:
                raise DerivationError(
                    f"evaluation receipt candidate {receipt.candidate_id!r} does not match "
                    f"event payload {payload['candidateId']!r}"
                )
            _check_adapter_digest(receipt.adapter.adapter_digest, manifest, "evaluation")
            unknown = sorted(set(dict(receipt.metrics)) - set(manifest.known_metrics))
            if unknown:
                raise DerivationError(
                    f"evaluation receipt reports unknown metrics {unknown}; "
                    f"declared: {list(manifest.known_metrics)}"
                )
            for metric_name, metric_value in receipt.metrics:
                if not isinstance(metric_value, (int, float)) or isinstance(metric_value, bool):
                    raise DerivationError(
                        f"metric {metric_name!r} must be an int or float, got {metric_value!r}"
                    )
            stage = event.phase
            if stage == "confirmation":
                if receipt.candidate_id not in shortlist:
                    raise DerivationError(
                        "confirmation evaluation references a candidate outside the frozen shortlist"
                    )
                verify_work["fresh_samples"] += 1
            ledger.decoder[stage].add(
                calls=1,
                input_tokens=_resource_int(receipt.resource_use, "inputTokens"),
                output_tokens=_resource_int(receipt.resource_use, "outputTokens"),
                samples=(
                    _resource_int(receipt.resource_use, "samples")
                    or 1
                ),
                provider_reported_tokens=_resource_int(
                    receipt.resource_use, "providerReportedTokens"
                ),
                failures=_resource_int(receipt.resource_use, "failures"),
            )
            w_search["evaluation_calls"] += 1
            w_search["retries"] += _resource_int(receipt.resource_use, "retries")
            w_search["cache_misses"] += _resource_int(receipt.resource_use, "cacheMisses")

        elif event_type == "evaluation_failed":
            started = started_evaluations.pop(payload["requestId"], None)
            if started is None:
                raise DerivationError(
                    f"evaluation_failed without a started request: {payload['requestId']}"
                )
            if started[0] != payload["candidateId"]:
                raise DerivationError(
                    f"evaluation_failed candidate {payload['candidateId']!r} does not "
                    f"match its started request {started[0]!r}"
                )
            if payload["requestId"] in terminated_evaluations:
                raise DerivationError(
                    f"evaluation request terminated twice: {payload['requestId']}"
                )
            terminated_evaluations.add(payload["requestId"])
            try:
                reservation = ledger.require_open(payload["reservationId"])
            except LedgerError as error:
                raise DerivationError(f"evaluation_failed {event.event_id}: {error}")
            if reservation.account != "T_dec":
                raise DerivationError(
                    f"evaluation call is charged to {reservation.account}, expected T_dec"
                )
            candidate_canonical(payload["candidateId"], "evaluation_failed")
            stage = event.phase
            ledger.decoder[stage].add(calls=1, failures=1)
            w_search["evaluation_calls"] += 1
            w_search["evaluation_failures"] += 1

        elif event_type == "candidate_rejected":
            canonical = candidate_canonical(payload["candidateId"], "candidate_rejected")
            if payload["candidateId"] not in archive:
                raise DerivationError(
                    "candidate_rejected references a candidate that was never archived"
                )
            rejected.append(payload["candidateId"])
            w_search["rejected_candidates"] += 1

        elif event_type == "candidate_promoted":
            canonical = candidate_canonical(payload["candidateId"], "candidate_promoted")
            if payload["candidateId"] not in archive:
                raise DerivationError(
                    "candidate_promoted references a candidate that was never archived"
                )
            if canonical["candidateRole"] != "candidate":
                raise DerivationError(
                    "candidate_promoted may never promote an explicit_reconstruction control"
                )
            if payload["candidateId"] in promoted:
                raise DerivationError(f"candidate promoted twice: {payload['candidateId']}")
            promoted.append(payload["candidateId"])

        elif event_type == "archive_changed":
            candidate_id = payload["candidateId"]
            canonical = candidate_canonical(candidate_id, "archive_changed")
            if candidate_id in archive:
                raise DerivationError(f"archive is append-only: {candidate_id} added twice")
            cost = coordinate_cost_from_canonical(payload["coordinateCost"])
            try:
                ledger.record_coordinate_cost(candidate_id, cost)
            except LedgerError as error:
                raise DerivationError(f"archive_changed {event.event_id}: {error}")
            archive[candidate_id] = canonical
            archive_root_digest = digest(
                {
                    "schemaVersion": ARCHIVE_VIEW_SCHEMA_VERSION,
                    "candidates": dict(archive),
                }
            )
            if archive_root_digest != payload["archiveDigest"]:
                raise DerivationError(
                    f"archive_changed {event.event_id} declares archive digest "
                    f"{payload['archiveDigest']}, derived {archive_root_digest}"
                )

        elif event_type == "search_frozen":
            if archive_root_digest != payload["archiveDigest"]:
                raise DerivationError(
                    f"search_frozen declares archive digest {payload['archiveDigest']}, "
                    f"derived {archive_root_digest}"
                )
            if archive_root_digest is None:
                raise DerivationError("search_frozen requires a non-empty archive")
            shortlist = list(payload["shortlistCandidateIds"])
            missing = sorted(set(shortlist) - set(archive))
            if missing:
                raise DerivationError(f"frozen shortlist references non-archived candidates: {missing}")
            unarchived = sorted(set(candidates) - set(archive))
            if unarchived:
                raise DerivationError(
                    f"freeze commits the archive, but candidates were never archived: {unarchived}"
                )
            selection_rule = payload["selectionRule"]
            discovery_context_digest = payload["discoveryContextDigest"]
            freeze_seen = True

        elif event_type == "confirmation_started":
            if payload["confirmationContextDigest"] == discovery_context_digest:
                raise DerivationError(
                    "confirmation context digest reuses the discovery context digest"
                )
            confirmation_started_seen = True
            confirmation_context_digest = payload["confirmationContextDigest"]
            confirmation_seed = payload["seed"]

        elif event_type == "confirmation_completed":
            if not confirmation_started_seen:
                raise DerivationError("confirmation_completed without confirmation_started")
            confirmation_outcome = payload["outcome"]
            confirmed_candidate_id = payload.get("candidateId")
            if confirmation_outcome == "confirmed":
                if confirmed_candidate_id not in shortlist:
                    raise DerivationError(
                        "confirmed candidate is not in the frozen shortlist"
                    )
            verify_work.update(
                {
                    key: _resource_int_from_payload(payload, payload_key)
                    for key, payload_key in (
                        ("replays", "replays"),
                        ("tests", "tests"),
                        ("human_checks", "humanChecks"),
                        ("proof_checks", "proofChecks"),
                    )
                }
            )

        elif event_type == "run_completed":
            run_completed_seen = True
            completion_status = payload["status"]
            if completion_status == "completed":
                if not freeze_seen:
                    raise DerivationError("a completed run must contain search_frozen")
                if confirmation_outcome is None:
                    raise DerivationError(
                        "a completed run must contain confirmation_completed"
                    )

    if manifest.closed and not run_completed_seen:
        raise DerivationError("the manifest is closed but no run_completed event exists")
    if run_completed_seen and not manifest.closed:
        raise DerivationError("run_completed exists but the manifest is still open")
    if started_evaluations:
        raise DerivationError(
            f"evaluation requests started but never terminated: {sorted(started_evaluations)}"
        )
    if run_completed_seen and completion_status == "completed" and ledger.open_reservations:
        raise DerivationError(
            f"a completed run leaves reservations open: {sorted(ledger.open_reservations)}"
        )

    ledger.search_work.add(**w_search)
    ledger.verification.add(**verify_work)
    ledger.critical_path = critical_path_length(events)

    archive_view = {
        "schemaVersion": ARCHIVE_VIEW_SCHEMA_VERSION,
        "candidates": dict(archive),
    }
    views = {
        "schemaVersion": VIEWS_SCHEMA_VERSION,
        "promotedCandidateIds": promoted,
        "rejectedCandidateIds": rejected,
        "selectionRule": selection_rule,
        "archiveDigestAtFreeze": archive_root_digest,
    }
    confirmation_view = {
        "schemaVersion": CONFIRMATION_VIEW_SCHEMA_VERSION,
        "outcome": confirmation_outcome,
        "candidateId": confirmed_candidate_id,
        "seed": confirmation_seed,
        "confirmationContextDigest": confirmation_context_digest,
        "discoveryContextDigest": discovery_context_digest,
    }

    digests = {
        "archive": digest_bytes(canonical_bytes(archive_view)),
        "views": digest_bytes(canonical_bytes(views)),
        "confirmation": digest_bytes(canonical_bytes(confirmation_view)),
        "resource-ledger": digest_bytes(canonical_bytes(ledger.to_canonical())),
    }
    return DerivedState(
        archive_view=archive_view,
        views=views,
        confirmation_view=confirmation_view,
        ledger=ledger,
        digests=digests,
        promoted_candidate_ids=tuple(promoted),
        rejected_candidate_ids=tuple(rejected),
    )


def _resource_int_from_payload(payload: Mapping[str, Any], key: str) -> int:
    value = payload.get(key)
    if value is None:
        return 0
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise DerivationError(f"confirmation_completed.{key} must be a non-negative int")
    return value


def materialize(root: Path) -> dict[str, str]:
    """Rebuild the four derived views from disk and write them byte-identically."""
    snapshot = read_bundle(root)
    derived = derive_state(snapshot.manifest, snapshot.events, snapshot.blobs)
    payloads = derived.materialized_payloads()
    materialized_dir = root / MATERIALIZED_DIR
    for name, payload in payloads.items():
        _atomic_write(materialized_dir / f"{name}.json", canonical_bytes(payload) + b"\n")
    return dict(derived.digests)
