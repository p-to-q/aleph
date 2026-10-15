"""Protected confirmation protocol: one adversarial mode per test.

Everything here is a fixture or a deliberate protocol violation; no model
evidence is involved. The session under test is pure: it produces payloads and
decisions only — the scheduler writes events into the bundle.
"""

from __future__ import annotations

import unittest

from search.engine.canonical import digest
from search.engine.confirmation import (
    CONFIRMATION_OUTCOMES,
    ConfirmationError,
    ConfirmationSession,
    ConfirmationSpec,
    decide_outcome,
)

DISCOVERY_CTX = digest({"fixture": "discovery-context"})
CONFIRM_CTX = digest({"fixture": "confirmation-context"})


def make_spec(**overrides):
    fields = {
        "discovery_context_digest": DISCOVERY_CTX,
        "confirmation_context_digest": CONFIRM_CTX,
        "seed": "seed-1",
        "metric": "fit",
        "threshold": 0.9,
        "samples": 4,
        "confirm_fraction": 0.75,
        "reject_fraction": 0.25,
    }
    fields.update(overrides)
    return ConfirmationSpec(**fields)


class TestSpecValidation(unittest.TestCase):
    def test_context_digest_reuse_rejected(self) -> None:
        with self.assertRaises(ConfirmationError):
            make_spec(confirmation_context_digest=DISCOVERY_CTX)

    def test_malformed_context_digest_rejected(self) -> None:
        with self.assertRaises(ConfirmationError):
            make_spec(confirmation_context_digest="not-a-digest")

    def test_fraction_ordering_rejected(self) -> None:
        with self.assertRaises(ConfirmationError):
            make_spec(confirm_fraction=0.2, reject_fraction=0.5)

    def test_fraction_range_rejected(self) -> None:
        with self.assertRaises(ConfirmationError):
            make_spec(confirm_fraction=1.5)
        with self.assertRaises(ConfirmationError):
            make_spec(reject_fraction=-0.1)

    def test_zero_samples_rejected(self) -> None:
        with self.assertRaises(ConfirmationError):
            make_spec(samples=0)

    def test_candidate_must_be_in_shortlist(self) -> None:
        with self.assertRaises(ConfirmationError):
            ConfirmationSession(make_spec(), shortlist=("c1",), candidate_id="c2")

    def test_deterministic_spec_digest(self) -> None:
        first = make_spec()
        second = make_spec()
        self.assertEqual(first.spec_digest, second.spec_digest)


class TestOutcomeDecision(unittest.TestCase):
    def test_confirmed_at_confirm_fraction(self) -> None:
        # 3 of 4 = 0.75 >= confirm_fraction
        self.assertEqual(decide_outcome(4, 3, 4, 0.75, 0.25), "confirmed")
        self.assertEqual(decide_outcome(4, 4, 4, 0.75, 0.25), "confirmed")

    def test_rejected_below_reject_fraction(self) -> None:
        self.assertEqual(decide_outcome(4, 0, 4, 0.75, 0.25), "rejected")

    def test_indeterminate_band(self) -> None:
        self.assertEqual(decide_outcome(4, 1, 4, 0.75, 0.25), "indeterminate")
        self.assertEqual(decide_outcome(4, 2, 4, 0.75, 0.25), "indeterminate")

    def test_unfinished_sample_plan_is_not_decidable(self) -> None:
        with self.assertRaises(ConfirmationError):
            decide_outcome(4, 3, 3, 0.75, 0.25)

    def test_unknown_outcome_is_not_a_decide_result(self) -> None:
        self.assertIn("confirmed", CONFIRMATION_OUTCOMES)
        self.assertNotIn("invented", CONFIRMATION_OUTCOMES)


class TestSessionLifecycle(unittest.TestCase):
    def test_begin_twice_fails(self) -> None:
        session = ConfirmationSession(make_spec(), shortlist=("c1",), candidate_id="c1")
        session.begin()
        with self.assertRaises(ConfirmationError):
            session.begin()

    def test_complete_before_begin_fails(self) -> None:
        session = ConfirmationSession(make_spec(), shortlist=("c1",), candidate_id="c1")
        with self.assertRaises(ConfirmationError):
            session.complete()

    def test_evaluation_before_begin_fails(self) -> None:
        session = ConfirmationSession(make_spec(), shortlist=("c1",), candidate_id="c1")
        with self.assertRaises(ConfirmationError):
            session.next_evaluation()

    def test_evaluations_are_unique_and_bounded(self) -> None:
        session = ConfirmationSession(make_spec(samples=3), shortlist=("c1",), candidate_id="c1")
        session.begin()
        ids = set()
        for _ in range(3):
            request = session.next_evaluation()
            self.assertIsNotNone(request)
            self.assertNotIn(request.request_id, ids)
            ids.add(request.request_id)
            self.assertEqual(request.candidate_id, "c1")
        self.assertIsNone(session.next_evaluation())

    def test_confirm_path_reaches_confirmed(self) -> None:
        session = ConfirmationSession(make_spec(samples=4), shortlist=("c1",), candidate_id="c1")
        session.begin()
        outcomes = (True, True, True, False)
        for passed in outcomes:
            request = session.next_evaluation()
            session.record_evaluation_outcome(request.request_id, passed)
        payload = session.complete()
        self.assertEqual(payload["outcome"], "confirmed")
        self.assertEqual(payload["candidateId"], "c1")

    def test_indeterminate_path(self) -> None:
        session = ConfirmationSession(make_spec(samples=4), shortlist=("c1",), candidate_id="c1")
        session.begin()
        outcomes = (True, False, False, False)
        for passed in outcomes:
            request = session.next_evaluation()
            session.record_evaluation_outcome(request.request_id, passed)
        payload = session.complete()
        self.assertEqual(payload["outcome"], "indeterminate")

    def test_no_candidate_yields_no_confirmed_candidate(self) -> None:
        session = ConfirmationSession(make_spec(), shortlist=(), candidate_id=None)
        session.begin()
        self.assertIsNone(session.next_evaluation())
        payload = session.complete()
        self.assertEqual(payload["outcome"], "no_confirmed_candidate")
        self.assertNotIn("candidateId", payload)

    def test_unknown_evaluation_recorded_fails(self) -> None:
        session = ConfirmationSession(make_spec(), shortlist=("c1",), candidate_id="c1")
        session.begin()
        with self.assertRaises(ConfirmationError):
            session.record_evaluation_outcome("invented-request", True)

    def test_double_record_fails(self) -> None:
        session = ConfirmationSession(make_spec(samples=2), shortlist=("c1",), candidate_id="c1")
        session.begin()
        request = session.next_evaluation()
        session.record_evaluation_outcome(request.request_id, True)
        with self.assertRaises(ConfirmationError):
            session.record_evaluation_outcome(request.request_id, True)

    def test_complete_twice_fails(self) -> None:
        session = ConfirmationSession(make_spec(samples=2), shortlist=("c1",), candidate_id="c1")
        session.begin()
        for passed in (True, True):
            request = session.next_evaluation()
            session.record_evaluation_outcome(request.request_id, passed)
        session.complete()
        with self.assertRaises(ConfirmationError):
            session.complete()

    def test_complete_with_unfinished_plan_fails(self) -> None:
        session = ConfirmationSession(make_spec(samples=4), shortlist=("c1",), candidate_id="c1")
        session.begin()
        request = session.next_evaluation()
        session.record_evaluation_outcome(request.request_id, True)
        with self.assertRaises(ConfirmationError):
            session.complete()

    def test_begin_payload_carries_fresh_context_and_seed(self) -> None:
        spec = make_spec()
        session = ConfirmationSession(spec, shortlist=("c1",), candidate_id="c1")
        payload = session.begin()
        self.assertEqual(payload["confirmationContextDigest"], CONFIRM_CTX)
        self.assertNotEqual(payload["confirmationContextDigest"], DISCOVERY_CTX)
        self.assertEqual(payload["seed"], spec.seed)


if __name__ == "__main__":
    unittest.main()
