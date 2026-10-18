"""Append-only event model for the Aleph engine.

Every state change in a run is one event. Events carry a schema version, a
monotone sequence number, a phase, parent ids, blob digests, and a content
digest over their own canonical payload. The event stream is the source of
truth: materialized archive, views, and ledger are derived from it and may
never invent or rewrite a candidate.

Rejected proposals, duplicates, failures, timeouts, and retries are ordinary
recorded events. They stay in the source archive rather than being dropped,
because a frontier that silently omits its own failures is not evidence.

## Payload contracts

Each event type declares required payload keys (``EVENT_PAYLOAD_REQUIRED``).
Construction validates them, and the strict ``event_from_canonical`` parser
revalidates every line during replay, so a hand-edited event fails closed.
Values are canonicalized the same way everywhere; typed receipts (proposal and
evaluation) are stored as content-addressed blobs and pinned by the event's
``blob_digests``:

- ``proposal_succeeded`` references its ``ProposalReceipt`` blob (first blob).
- ``evaluation_completed`` references its ``EvaluationReceipt`` blob (first blob).
- Other events may attach arbitrary evidence blobs; every referenced blob must
  exist and hash to its declared digest (checked by the verifier).

## Phase table

``EVENT_PHASES`` assigns each type its admissible phase. Proposals happen only
in the discovery phase, so discovery evidence can never be relabelled as
confirmation: the constructor and the stream structure check both reject such
an event.

Pure standard library.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping, Sequence

from .canonical import canonicalize, digest, is_digest
from .ledger import ACCOUNTS, STAGES, coordinate_cost_from_canonical

EVENT_SCHEMA_VERSION = "aleph-engine-event/0.1.0"

PHASES = ("run", "discovery", "freeze", "confirmation")
"""Stage label for every event.

``discovery`` evidence can never be relabelled as ``confirmation``: the
verifier rejects any confirmation-phase event whose sequence precedes
``search_frozen``, and any discovery-phase event after it.
"""

EVENT_TYPES: tuple[str, ...] = (
    "run_started",
    "budget_reserved",
    "budget_committed",
    "budget_failed",
    "proposal_succeeded",
    "proposal_failed",
    "evaluation_started",
    "evaluation_completed",
    "evaluation_failed",
    "candidate_rejected",
    "candidate_promoted",
    "archive_changed",
    "search_frozen",
    "confirmation_started",
    "confirmation_completed",
    "run_completed",
)

"""Admissible phase per event type.

Budget, proposal, and evaluation events carry the stage they run in; proposals
are discovery-only because confirmation evaluates a frozen shortlist and must
not affect discovery. Freeze and run bookkeeping use their own phases.
"""
EVENT_PHASES: dict[str, frozenset[str]] = {
    "run_started": frozenset({"run"}),
    "run_completed": frozenset({"run"}),
    "search_frozen": frozenset({"freeze"}),
    "confirmation_started": frozenset({"confirmation"}),
    "confirmation_completed": frozenset({"confirmation"}),
    "budget_reserved": frozenset({"discovery", "confirmation"}),
    "budget_committed": frozenset({"discovery", "confirmation"}),
    "budget_failed": frozenset({"discovery", "confirmation"}),
    "proposal_succeeded": frozenset({"discovery"}),
    "proposal_failed": frozenset({"discovery"}),
    "evaluation_started": frozenset({"discovery", "confirmation"}),
    "evaluation_completed": frozenset({"discovery", "confirmation"}),
    "evaluation_failed": frozenset({"discovery", "confirmation"}),
    "candidate_rejected": frozenset({"discovery"}),
    "candidate_promoted": frozenset({"discovery"}),
    "archive_changed": frozenset({"discovery"}),
}

"""Required payload keys per event type. Extra keys are allowed (schema
evolution), required keys are validated for type and shape."""
EVENT_PAYLOAD_REQUIRED: dict[str, tuple[str, ...]] = {
    "run_started": ("runId",),
    "budget_reserved": ("reservationId", "account", "stage"),
    "budget_committed": ("reservationId", "account", "stage"),
    "budget_failed": ("reservationId", "account", "stage", "reason"),
    "proposal_succeeded": ("requestId", "reservationId", "candidateIds"),
    "proposal_failed": ("requestId", "reservationId", "reason"),
    "evaluation_started": ("requestId", "reservationId", "candidateId"),
    "evaluation_completed": ("requestId", "reservationId", "candidateId"),
    "evaluation_failed": ("requestId", "reservationId", "candidateId", "reason"),
    "candidate_rejected": ("candidateId", "reason"),
    "candidate_promoted": ("candidateId",),
    "archive_changed": ("candidateId", "archiveDigest", "coordinateCost"),
    "search_frozen": (
        "archiveDigest",
        "shortlistCandidateIds",
        "selectionRule",
        "discoveryContextDigest",
    ),
    "confirmation_started": ("confirmationContextDigest", "seed"),
    "confirmation_completed": ("outcome",),
    "run_completed": ("status",),
}

TERMINAL_RESERVATION_EVENTS = ("budget_committed", "budget_failed")

ADAPTER_CALL_EVENTS = (
    "proposal_succeeded",
    "proposal_failed",
    "evaluation_completed",
    "evaluation_failed",
)

REJECTION_REASONS = (
    "duplicate_candidate",
    "dominated",
    "budget_exhausted",
    "evaluation_failed",
    "malformed_proposal",
    "policy_excluded",
)

CONFIRMATION_OUTCOMES = ("confirmed", "rejected", "indeterminate", "no_confirmed_candidate")

RUN_STATUSES = ("completed", "aborted")


class EventError(ValueError):
    """Raised when an event is structurally invalid."""


def _payload_errors(event_type: str, phase: str, payload: Mapping[str, Any]) -> list[str]:
    """Return every contract violation in an event payload, fail-closed."""
    errors: list[str] = []
    required = EVENT_PAYLOAD_REQUIRED[event_type]

    for key in required:
        if key not in payload:
            errors.append(f"{event_type} payload is missing required key {key!r}")

    def non_empty_str(key: str) -> None:
        value = payload.get(key)
        if not isinstance(value, str) or not value:
            errors.append(f"{event_type}.{key} must be a non-empty str")

    def id_list(key: str, *, allow_empty: bool) -> None:
        value = payload.get(key)
        if not isinstance(value, list) or not all(
            isinstance(item, str) and item for item in value
        ):
            errors.append(f"{event_type}.{key} must be a list of non-empty str")
            return
        if len(set(value)) != len(value):
            errors.append(f"{event_type}.{key} must not contain duplicates")
        if not value and not allow_empty:
            errors.append(f"{event_type}.{key} must not be empty")

    def digest_field(key: str) -> None:
        value = payload.get(key)
        if not is_digest(value):
            errors.append(f"{event_type}.{key} must be a well-formed digest")

    for key in ("requestId", "reservationId", "candidateId"):
        if key in required:
            non_empty_str(key)
    if event_type == "run_started" and "createdAt" in payload:
        # PR B: a run may declare a fixed creation timestamp (never read from
        # the wall clock). Extra payload keys are otherwise allowed, but a
        # declared value that is not a non-empty str must fail closed because
        # the exporter copies it into the strict AlephRun schema.
        non_empty_str("createdAt")
    if "runId" in required:
        non_empty_str("runId")
    if "reason" in required:
        non_empty_str("reason")
    if "candidateIds" in required:
        id_list("candidateIds", allow_empty=False)
    if "shortlistCandidateIds" in required:
        id_list("shortlistCandidateIds", allow_empty=True)
    if "selectionRule" in required:
        non_empty_str("selectionRule")
    if "seed" in required:
        non_empty_str("seed")
    if "status" in required:
        value = payload.get("status")
        if value not in RUN_STATUSES:
            errors.append(f"{event_type}.status must be one of {RUN_STATUSES}")
    if "outcome" in required:
        value = payload.get("outcome")
        if value not in CONFIRMATION_OUTCOMES:
            errors.append(f"{event_type}.outcome must be one of {CONFIRMATION_OUTCOMES}")
        if value == "confirmed" and "candidateId" not in payload:
            errors.append("confirmation_completed with outcome 'confirmed' requires candidateId")
        if value == "confirmed":
            non_empty_str("candidateId")
    if "account" in required:
        value = payload.get("account")
        if value not in ACCOUNTS:
            errors.append(f"{event_type}.account must be one of {ACCOUNTS}")
    if "stage" in required:
        value = payload.get("stage")
        if value not in STAGES:
            errors.append(f"{event_type}.stage must be one of {STAGES}")
        if value is not None and value != phase:
            errors.append(f"{event_type}.stage {value!r} does not match phase {phase!r}")
    if "reason" in required and event_type == "candidate_rejected":
        value = payload.get("reason")
        if value is not None and value not in REJECTION_REASONS:
            errors.append(f"candidate_rejected.reason must be one of {REJECTION_REASONS}")
    for key in ("archiveDigest", "discoveryContextDigest", "confirmationContextDigest"):
        if key in required:
            digest_field(key)
    if "coordinateCost" in required:
        value = payload.get("coordinateCost")
        if not isinstance(value, Mapping):
            errors.append("archive_changed.coordinateCost must be a mapping")
        else:
            try:
                cost = coordinate_cost_from_canonical(value)
                if canonicalize(cost.to_canonical()) != canonicalize(value):
                    errors.append(
                        "archive_changed.coordinateCost is not the canonical form of a C(p) record"
                    )
            except ValueError as error:
                errors.append(f"archive_changed.coordinateCost is invalid: {error}")
    return errors


@dataclass(frozen=True)
class Event:
    """One append-only event.

    ``content_digest`` is taken over the canonical payload of every other field,
    so altering any recorded value invalidates the event in place. The digest is
    not part of its own input.
    """

    event_id: str
    sequence: int
    event_type: str
    phase: str
    payload: Mapping[str, Any] = field(default_factory=dict)
    parent_event_ids: tuple[str, ...] = ()
    blob_digests: tuple[str, ...] = ()
    schema_version: str = EVENT_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if not isinstance(self.event_id, str) or not self.event_id:
            raise EventError("event_id must be a non-empty str")
        if not isinstance(self.sequence, int) or isinstance(self.sequence, bool):
            raise EventError("sequence must be an int")
        if self.sequence < 0:
            raise EventError("sequence must be non-negative")
        if self.event_type not in EVENT_TYPES:
            raise EventError(f"unknown event type: {self.event_type!r}")
        if self.phase not in EVENT_PHASES[self.event_type]:
            raise EventError(
                f"event type {self.event_type!r} cannot carry phase {self.phase!r}; "
                f"admissible: {sorted(EVENT_PHASES[self.event_type])}"
            )
        if not isinstance(self.payload, Mapping):
            raise EventError("payload must be a mapping")
        if not isinstance(self.parent_event_ids, tuple):
            raise EventError("parent_event_ids must be a tuple")
        if len(set(self.parent_event_ids)) != len(self.parent_event_ids):
            raise EventError("parent_event_ids must be unique")
        if not isinstance(self.blob_digests, tuple):
            raise EventError("blob_digests must be a tuple")
        for value in self.blob_digests:
            if not is_digest(value):
                raise EventError(f"malformed blob digest: {value!r}")
        if self.schema_version != EVENT_SCHEMA_VERSION:
            raise EventError(f"unsupported event schema version: {self.schema_version!r}")
        errors = _payload_errors(self.event_type, self.phase, self.payload)
        if not self.blob_digests and self.event_type in (
            "proposal_succeeded",
            "evaluation_completed",
        ):
            errors.append(
                f"{self.event_type} must reference its typed receipt through at least one blob digest"
            )
        if errors:
            raise EventError(f"event {self.event_id!r} violates its payload contract: " + "; ".join(errors))

    @property
    def digest_input(self) -> dict[str, Any]:
        return {
            "schemaVersion": self.schema_version,
            "eventId": self.event_id,
            "sequence": self.sequence,
            "eventType": self.event_type,
            "phase": self.phase,
            "parentEventIds": list(self.parent_event_ids),
            "blobDigests": sorted(self.blob_digests),
            "payload": canonicalize(self.payload),
        }

    @property
    def content_digest(self) -> str:
        return digest(self.digest_input)

    def to_canonical(self) -> dict[str, Any]:
        record = dict(self.digest_input)
        record["contentDigest"] = self.content_digest
        return record


def event_from_canonical(record: Mapping[str, Any]) -> Event:
    """Rebuild an ``Event`` from its canonical record, verifying its digest.

    Strict: unknown record fields, malformed types, and digest mismatches all
    fail closed. Falsy non-mapping values are never silently coerced into
    defaults.
    """
    if not isinstance(record, Mapping):
        raise EventError("event record must be a mapping")
    unknown = set(record) - {
        "schemaVersion",
        "eventId",
        "sequence",
        "eventType",
        "phase",
        "parentEventIds",
        "blobDigests",
        "payload",
        "contentDigest",
    }
    if unknown:
        raise EventError(f"unknown event fields: {sorted(unknown)}")
    # ``payload``, ``parentEventIds``, and ``blobDigests`` keep defaults because
    # ``contentDigest`` is recomputed over all of them below and compared with
    # the declared digest: a substituted value can only survive when it already
    # equalled the default. ``schemaVersion`` is covered by the same digest.
    payload = record.get("payload", {})
    if not isinstance(payload, Mapping):
        raise EventError("event payload must be a mapping")
    parent_ids = record.get("parentEventIds", ())
    if not isinstance(parent_ids, list):
        raise EventError("parentEventIds must be a list")
    blob_digests = record.get("blobDigests", ())
    if not isinstance(blob_digests, list):
        raise EventError("blobDigests must be a list")
    try:
        event = Event(
            event_id=record["eventId"],
            sequence=record["sequence"],
            event_type=record["eventType"],
            phase=record["phase"],
            payload=payload,
            parent_event_ids=tuple(parent_ids),
            blob_digests=tuple(blob_digests),
            schema_version=record.get("schemaVersion", EVENT_SCHEMA_VERSION),
        )
    except KeyError as error:
        raise EventError(f"missing event field: {error}") from error
    declared = record.get("contentDigest")
    if declared is None:
        raise EventError("event record is missing contentDigest")
    if declared != event.content_digest:
        raise EventError(
            f"event {event.event_id} content digest mismatch: "
            f"declared {declared!r}, derived {event.content_digest!r}"
        )
    return event


def build_event(
    *,
    event_id: str,
    sequence: int,
    event_type: str,
    phase: str,
    payload: Mapping[str, Any] | None = None,
    parent_event_ids: Sequence[str] = (),
    blob_digests: Sequence[str] = (),
) -> Event:
    """Construct a validated ``Event``."""
    if payload is not None and not isinstance(payload, Mapping):
        raise EventError("payload must be a mapping or None")
    return Event(
        event_id=event_id,
        sequence=sequence,
        event_type=event_type,
        phase=phase,
        payload=dict(payload or {}),
        parent_event_ids=tuple(parent_event_ids),
        blob_digests=tuple(blob_digests),
    )


def stream_digest(events: Sequence[Event]) -> str:
    """Return a digest over the ordered content digests of ``events``."""
    return digest(
        {
            "schemaVersion": EVENT_SCHEMA_VERSION,
            "contentDigests": [event.content_digest for event in events],
        }
    )


def check_stream_structure(events: Sequence[Event]) -> list[str]:
    """Return every structural defect in an event stream.

    Checks are fail-closed and collected rather than raised, so a verifier can
    report all corruption modes in one pass:

    - sequences must start at 0, be strictly increasing, and have no gaps;
    - event ids must be unique;
    - parent ids must resolve to an earlier event, which forbids orphans and
      cycles at once;
    - exactly one ``run_started`` must open the stream;
    - at most one ``search_frozen``; confirmation events must follow it and
      discovery events must precede it;
    - ``run_completed``, when present, is the terminal event.
    """
    errors: list[str] = []
    if not events:
        return ["event stream is empty"]

    seen_ids: set[str] = set()
    expected_sequence = 0
    for event in events:
        if event.event_id in seen_ids:
            errors.append(f"duplicate event id: {event.event_id}")
        seen_ids.add(event.event_id)
        if event.sequence != expected_sequence:
            errors.append(
                f"event {event.event_id} has sequence {event.sequence}, expected {expected_sequence}"
            )
        expected_sequence = event.sequence + 1

    position_by_id = {event.event_id: index for index, event in enumerate(events)}
    for index, event in enumerate(events):
        for parent in event.parent_event_ids:
            parent_index = position_by_id.get(parent)
            if parent_index is None:
                errors.append(f"event {event.event_id} references orphan parent {parent}")
            elif parent_index >= index:
                errors.append(
                    f"event {event.event_id} references parent {parent} at or after itself"
                )

    if events[0].event_type != "run_started":
        errors.append("first event must be run_started")
    started = [event for event in events if event.event_type == "run_started"]
    if len(started) != 1:
        errors.append(f"expected exactly one run_started event, found {len(started)}")

    freezes = [event for event in events if event.event_type == "search_frozen"]
    if len(freezes) > 1:
        errors.append(f"expected at most one search_frozen event, found {len(freezes)}")
    freeze_sequence = freezes[0].sequence if freezes else None
    for event in events:
        if event.phase == "confirmation":
            if freeze_sequence is None:
                errors.append(
                    f"confirmation event {event.event_id} has no preceding search_frozen"
                )
            elif event.sequence < freeze_sequence:
                errors.append(
                    f"confirmation event {event.event_id} precedes search_frozen"
                )
        if (
            event.phase == "discovery"
            and freeze_sequence is not None
            and event.sequence > freeze_sequence
        ):
            errors.append(f"discovery event {event.event_id} follows search_frozen")

    completed = [event for event in events if event.event_type == "run_completed"]
    if len(completed) > 1:
        errors.append(f"expected at most one run_completed event, found {len(completed)}")
    if completed and events[-1].event_type != "run_completed":
        errors.append("run_completed must be the terminal event")

    return errors


def critical_path_length(events: Sequence[Event]) -> int:
    """Return the longest dependency chain in the event DAG.

    This is the ``D_crit`` graph statistic: the number of events on the longest
    parent chain under the declared scheduler model. It is derived, never
    additive, so adding workers cannot shorten it.
    """
    depth_by_id: dict[str, int] = {}
    longest = 0
    for event in events:
        parent_depth = max(
            (depth_by_id[parent] for parent in event.parent_event_ids if parent in depth_by_id),
            default=0,
        )
        depth = parent_depth + 1
        depth_by_id[event.event_id] = depth
        longest = max(longest, depth)
    return longest


def iter_adapter_calls(events: Iterable[Event]) -> Iterable[Event]:
    """Yield the events that represent a terminal adapter call."""
    for event in events:
        if event.event_type in ADAPTER_CALL_EVENTS:
            yield event
