"""Event model: payload contracts, phase table, and stream structure checks."""

from __future__ import annotations

import unittest

from search.engine.canonical import digest, digest_bytes
from search.engine.events import (
    ADAPTER_CALL_EVENTS,
    CONFIRMATION_OUTCOMES,
    EVENT_PHASES,
    EVENT_PAYLOAD_REQUIRED,
    Event,
    EventError,
    build_event,
    check_stream_structure,
    critical_path_length,
    event_from_canonical,
    iter_adapter_calls,
    stream_digest,
)


def make_event(
    sequence: int = 0,
    event_type: str = "run_started",
    phase: str | None = None,
    payload: dict | None = None,
    **kwargs,
) -> Event:
    if payload is None:
        payload = {"runId": "run-1"} if event_type == "run_started" else {}
    if phase is None:
        if event_type in ("run_started", "run_completed"):
            phase = "run"
        elif event_type == "search_frozen":
            phase = "freeze"
        elif event_type.startswith("confirmation"):
            phase = "confirmation"
        else:
            phase = "discovery"
    return build_event(
        event_id=f"run-1:event-{sequence}",
        sequence=sequence,
        event_type=event_type,
        phase=phase,
        payload=payload,
        **kwargs,
    )


def started_run(*tail: Event) -> tuple[Event, ...]:
    return (make_event(0), *tail)


class TestEventConstruction(unittest.TestCase):
    def test_unknown_event_type_rejected(self) -> None:
        with self.assertRaises(EventError):
            make_event(event_type="invented")

    def test_phase_table_enforced(self) -> None:
        # A proposal can never be labelled as confirmation.
        with self.assertRaises(EventError):
            make_event(
                event_type="proposal_succeeded",
                phase="confirmation",
                payload={
                    "requestId": "r", "reservationId": "rsv", "candidateIds": ["c"],
                },
                blob_digests=(digest_bytes(b"receipt"),),
            )
        # Confirmation events cannot carry a discovery phase.
        with self.assertRaises(EventError):
            make_event(
                event_type="confirmation_completed",
                phase="discovery",
                payload={"outcome": "rejected"},
            )

    def test_required_payload_keys_enforced(self) -> None:
        with self.assertRaises(EventError):
            make_event(event_type="budget_reserved", payload={"reservationId": "r"})

    def test_payload_type_validation(self) -> None:
        with self.assertRaises(EventError):
            make_event(
                event_type="proposal_succeeded",
                payload={"requestId": "r", "reservationId": "rsv", "candidateIds": "c"},
                blob_digests=(digest_bytes(b"receipt"),),
            )
        with self.assertRaises(EventError):
            make_event(
                event_type="proposal_succeeded",
                payload={"requestId": "r", "reservationId": "rsv", "candidateIds": ["c", "c"]},
                blob_digests=(digest_bytes(b"receipt"),),
            )
        with self.assertRaises(EventError):
            make_event(
                event_type="candidate_rejected",
                payload={"candidateId": "c", "reason": "invented-reason"},
            )

    def test_null_required_fields_rejected(self) -> None:
        with self.assertRaises(EventError):
            make_event(
                event_type="candidate_rejected",
                payload={"candidateId": "c", "reason": None},
            )
        with self.assertRaises(EventError):
            make_event(
                event_type="search_frozen",
                payload={
                    "archiveDigest": digest("a"),
                    "shortlistCandidateIds": [],
                    "selectionRule": "r",
                    "discoveryContextDigest": None,
                },
            )
        with self.assertRaises(EventError):
            make_event(
                event_type="confirmation_started",
                payload={"confirmationContextDigest": digest("ctx"), "seed": None},
            )

    def test_receipt_events_require_a_blob(self) -> None:
        for event_type, payload in (
            ("proposal_succeeded", {"requestId": "r", "reservationId": "rsv", "candidateIds": ["c"]}),
            ("evaluation_completed", {"requestId": "r", "reservationId": "rsv", "candidateId": "c"}),
        ):
            with self.assertRaises(EventError, msg=event_type):
                make_event(event_type=event_type, payload=payload)

    def test_budget_stage_must_match_phase(self) -> None:
        with self.assertRaises(EventError):
            make_event(
                event_type="budget_reserved",
                phase="confirmation",
                payload={"reservationId": "r", "account": "W_search", "stage": "discovery"},
            )

    def test_confirmed_outcome_requires_candidate(self) -> None:
        with self.assertRaises(EventError):
            make_event(
                event_type="confirmation_completed",
                phase="confirmation",
                payload={"outcome": "confirmed"},
            )

    def test_malformed_digest_fields_rejected(self) -> None:
        with self.assertRaises(EventError):
            make_event(
                event_type="archive_changed",
                payload={
                    "candidateId": "c",
                    "archiveDigest": "nope",
                    "coordinateCost": {
                        "tokenizerView": "t",
                        "tokenizerDigest": digest("t"),
                        "coordinateTokens": 1,
                        "coordinateUtf8Bytes": 4,
                        "fullRenderedTokens": 2,
                        "fullRenderedUtf8Bytes": 8,
                    },
                },
            )

    def test_malformed_blob_digest_rejected(self) -> None:
        with self.assertRaises(EventError):
            make_event(blob_digests=("nope",))

    def test_negative_sequence_rejected(self) -> None:
        with self.assertRaises(EventError):
            make_event(sequence=-1)

    def test_duplicate_parents_rejected(self) -> None:
        with self.assertRaises(EventError):
            make_event(sequence=1, parent_event_ids=("a", "a"))


class TestEventCanonicalRoundTrip(unittest.TestCase):
    def test_round_trip_verifies_content_digest(self) -> None:
        event = make_event(
            1,
            "budget_reserved",
            payload={"reservationId": "rsv", "account": "W_search", "stage": "discovery"},
            parent_event_ids=("run-1:event-0",),
        )
        rebuilt = event_from_canonical(event.to_canonical())
        self.assertEqual(rebuilt, event)

    def test_tampered_payload_invalidates_digest(self) -> None:
        event = make_event(
            1,
            "budget_reserved",
            payload={"reservationId": "rsv", "account": "W_search", "stage": "discovery"},
        )
        record = event.to_canonical()
        record["payload"] = dict(record["payload"], reservationId="rsv-tampered")
        with self.assertRaises(EventError):
            event_from_canonical(record)

    def test_unknown_record_fields_rejected(self) -> None:
        event = make_event(0)
        record = event.to_canonical()
        record["extra"] = 1
        with self.assertRaises(EventError):
            event_from_canonical(record)

    def test_falsy_non_mapping_payload_not_coerced(self) -> None:
        event = make_event(0)
        record = event.to_canonical()
        record["payload"] = []
        with self.assertRaises(EventError):
            event_from_canonical(record)

    def test_blob_digests_sorted_in_digest_input(self) -> None:
        first = make_event(
            1,
            "budget_reserved",
            payload={"reservationId": "rsv", "account": "W_search", "stage": "discovery"},
            blob_digests=(digest_bytes(b"a"), digest_bytes(b"b")),
        )
        second = make_event(
            1,
            "budget_reserved",
            payload={"reservationId": "rsv", "account": "W_search", "stage": "discovery"},
            blob_digests=(digest_bytes(b"b"), digest_bytes(b"a")),
        )
        self.assertEqual(first.content_digest, second.content_digest)


class TestStreamStructure(unittest.TestCase):
    def test_empty_stream_rejected(self) -> None:
        self.assertTrue(check_stream_structure(()))

    def test_sequence_gap_detected(self) -> None:
        events = started_run(make_event(2))
        errors = check_stream_structure(events)
        self.assertTrue(any("expected 1" in item for item in errors))

    def test_duplicate_event_id_detected(self) -> None:
        first = make_event(0)
        second = make_event(1, "budget_reserved", payload={"reservationId": "r", "account": "W_search", "stage": "discovery"})
        second = build_event(
            event_id=first.event_id, sequence=1, event_type="budget_reserved", phase="discovery",
            payload={"reservationId": "r", "account": "W_search", "stage": "discovery"},
        )
        errors = check_stream_structure((first, second))
        self.assertTrue(any("duplicate event id" in item for item in errors))

    def test_orphan_parent_detected(self) -> None:
        events = started_run(
            make_event(1, "budget_reserved", payload={"reservationId": "r", "account": "W_search", "stage": "discovery"}, parent_event_ids=("missing",))
        )
        errors = check_stream_structure(events)
        self.assertTrue(any("orphan parent" in item for item in errors))

    def test_self_or_future_parent_detected(self) -> None:
        events = started_run(
            make_event(1, "budget_reserved", payload={"reservationId": "r", "account": "W_search", "stage": "discovery"}, parent_event_ids=("run-1:event-1",))
        )
        errors = check_stream_structure(events)
        self.assertTrue(any("at or after itself" in item for item in errors))

    def test_missing_run_started_detected(self) -> None:
        events = (make_event(0, "budget_reserved", payload={"reservationId": "r", "account": "W_search", "stage": "discovery"}),)
        errors = check_stream_structure(events)
        self.assertTrue(any("first event must be run_started" in item for item in errors))

    def test_confirmation_without_freeze_detected(self) -> None:
        events = started_run(
            make_event(1, "confirmation_completed", payload={"outcome": "rejected"})
        )
        errors = check_stream_structure(events)
        self.assertTrue(any("no preceding search_frozen" in item for item in errors))

    def test_discovery_after_freeze_detected(self) -> None:
        events = (
            make_event(0),
            make_event(1, "search_frozen", payload={
                "archiveDigest": digest({"candidates": {}}),
                "shortlistCandidateIds": [],
                "selectionRule": "rule",
                "discoveryContextDigest": digest("ctx"),
            }),
            make_event(2, "budget_reserved", payload={"reservationId": "r", "account": "W_search", "stage": "discovery"}),
        )
        errors = check_stream_structure(events)
        self.assertTrue(any("follows search_frozen" in item for item in errors))

    def test_run_completed_must_be_terminal(self) -> None:
        events = (
            make_event(0),
            make_event(1, "run_completed", payload={"status": "aborted"}),
            make_event(2, "budget_reserved", payload={"reservationId": "r", "account": "W_search", "stage": "discovery"}),
        )
        errors = check_stream_structure(events)
        self.assertTrue(any("terminal event" in item for item in errors))

    def test_multiple_freezes_detected(self) -> None:
        freeze_payload = {
            "archiveDigest": digest({"candidates": {}}),
            "shortlistCandidateIds": [],
            "selectionRule": "rule",
            "discoveryContextDigest": digest("ctx"),
        }
        events = (
            make_event(0),
            make_event(1, "search_frozen", payload=freeze_payload),
            make_event(2, "search_frozen", payload=freeze_payload),
        )
        errors = check_stream_structure(events)
        self.assertTrue(any("at most one search_frozen" in item for item in errors))


class TestStreamDigest(unittest.TestCase):
    def test_digest_covers_order(self) -> None:
        first = make_event(0)
        second = make_event(1, "budget_reserved", payload={"reservationId": "r", "account": "W_search", "stage": "discovery"})
        third = make_event(2, "budget_committed", payload={"reservationId": "r", "account": "W_search", "stage": "discovery"})
        self.assertNotEqual(stream_digest((first, second, third)), stream_digest((first, third, second)))


class TestCriticalPath(unittest.TestCase):
    def test_longest_parent_chain(self) -> None:
        events = (
            make_event(0),
            make_event(1, "budget_reserved", payload={"reservationId": "r", "account": "W_search", "stage": "discovery"}, parent_event_ids=("run-1:event-0",)),
            make_event(2, "budget_reserved", payload={"reservationId": "s", "account": "W_search", "stage": "discovery"}, parent_event_ids=("run-1:event-0",)),
            make_event(3, "budget_committed", payload={"reservationId": "s", "account": "W_search", "stage": "discovery"}, parent_event_ids=("run-1:event-2",)),
            make_event(4, "budget_committed", payload={"reservationId": "r", "account": "W_search", "stage": "discovery"}, parent_event_ids=("run-1:event-1",)),
        )
        self.assertEqual(critical_path_length(events), 3)

    def test_orphan_parents_do_not_contribute(self) -> None:
        events = (
            make_event(0),
            make_event(1, "budget_reserved", payload={"reservationId": "r", "account": "W_search", "stage": "discovery"}, parent_event_ids=("missing",)),
        )
        self.assertEqual(critical_path_length(events), 1)


class TestAdapterCallIteration(unittest.TestCase):
    def test_terminal_calls_only(self) -> None:
        events = (
            make_event(0),
            make_event(1, "evaluation_started", payload={"requestId": "r", "reservationId": "rsv", "candidateId": "c"}),
            make_event(2, "evaluation_completed", payload={"requestId": "r", "reservationId": "rsv", "candidateId": "c"}, blob_digests=(digest_bytes(b"receipt"),)),
            make_event(3, "proposal_failed", payload={"requestId": "p", "reservationId": "rsv", "reason": "malformed_proposal"}),
        )
        call_events = list(iter_adapter_calls(events))
        self.assertEqual(
            [event.event_type for event in call_events],
            ["evaluation_completed", "proposal_failed"],
        )


if __name__ == "__main__":
    unittest.main()
