"""Minimal hybrid Pareto scheduler: one adversarial mode per test.

Everything here is a fixture: deterministic echo adapters and content-keyed
simulated metrics. No model evidence, no MLX, no network. The scheduler under
test writes a complete, verifiable run bundle.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from search.engine.archive import derive_state, read_bundle
from search.engine.canonical import digest
from search.engine.confirmation import ConfirmationSpec
from search.engine.contracts import (
    Candidate,
    Message,
    Placement,
    candidate_from_canonical,
    evaluation_receipt,
    proposal_receipt,
    self_compression_arm,
)
from search.engine.fixtures.demo import demo_coordinate_cost
from search.engine.hybrid_pareto import (
    HYBRID_SCHEMA_VERSION,
    PARENT_RULES,
    RACING_RULES,
    STOP_RULES,
    FrozenConfig,
    HybridRunResult,
    SchedulerError,
    frozen_config_from_canonical,
    run_hybrid_search,
    unfreeze_projection,
)
from search.engine.operators import DeleteSpec, ReferenceSpec, RewriteSpec
from search.engine.verify import verify_bundle

TARGET = "The quick brown fox 你好 jumps over 🚀."
TARGET_DIGEST = digest(TARGET)

PLACEMENT = Placement(
    scaffold_id="hybrid-test-scaffold",
    scaffold_digest=digest({"fixture": "hybrid-test-scaffold", "version": "1"}),
    prompt_position="messages[0]",
    rendered_template_version="1",
)

NESTING_RULE = "t_dec_nested_in_w_search"
KNOWN_METRICS = ("fit", "stability")
MODEL_MANIFEST = {
    "fixture": True,
    "model": "hybrid-fixture-model",
    "revision": "fixture",
    "decoding": {"temperature": 0.0, "maxNewTokens": 64},
}


def make_seed(messages, *, role: str = "candidate") -> Candidate:
    return Candidate(
        messages=tuple(Message(role=role_name, content=content) for role_name, content in messages),
        placement=PLACEMENT,
        proposal_mode="seed",
        role=role,
    )


GOOD_SEED = make_seed([("user", "GOOD alpha"), ("user", "beta")])
BAD_SEED = make_seed([("user", "plain"), ("user", "stuff")])
CONTROL_SEED = make_seed([("user", TARGET)], role="explicit_reconstruction")


class EchoProposalAdapter:
    """Fixture proposer: echoes the candidates declared in the request context."""

    def __init__(self, identity, *, rogue: Candidate | None = None, rogue_after: int = 10**9):
        self._identity = identity
        self._rogue = rogue
        self._rogue_after = rogue_after
        self.calls = 0

    @property
    def identity(self):
        return self._identity

    def propose(self, request):
        self.calls += 1
        if self._rogue is not None and self.calls == self._rogue_after:
            return proposal_receipt(
                request_id=request.request_id,
                adapter=self._identity,
                candidates=(self._rogue,),
                resource_use={"fixture": True},
            )
        context = dict(request.context)
        raw = context.get("operatorProducts", context.get("seeds", ()))
        candidates = tuple(candidate_from_canonical(unfreeze_projection(item)) for item in raw)
        return proposal_receipt(
            request_id=request.request_id,
            adapter=self._identity,
            candidates=candidates,
            resource_use={"fixture": True},
        )


class FailingProposalAdapter:
    """Fixture proposer that always raises."""

    def __init__(self, identity):
        self._identity = identity

    @property
    def identity(self):
        return self._identity

    def propose(self, request):
        raise RuntimeError("fixture proposal failure")


class FixtureEvaluationAdapter:
    """Deterministic evaluator: fit 0.9 for content containing 'good', else 0.4."""

    def __init__(self, identity, *, fail_on: str | None = None, fail_on_reservation: str | None = None):
        self._identity = identity
        self._fail_on = fail_on
        self._fail_on_reservation = fail_on_reservation

    @property
    def identity(self):
        return self._identity

    def evaluate(self, request):
        candidate = request.candidate
        joined = " ".join(message.content for message in candidate.messages)
        if self._fail_on_reservation is not None and request.reservation_id.startswith(
            self._fail_on_reservation
        ):
            raise RuntimeError(f"fixture confirmation failure on {request.reservation_id}")
        if self._fail_on is not None and self._fail_on in joined:
            raise RuntimeError(f"fixture evaluation failure: {self._fail_on}")
        fit = 0.9 if "good" in joined.lower() else 0.4
        return evaluation_receipt(
            request_id=request.request_id,
            adapter=self._identity,
            candidate_id=candidate.candidate_id,
            metrics={"fit": fit, "stability": 0.85},
            resource_use={"inputTokens": 8, "outputTokens": 4, "samples": 1},
            outputs={"fixture": True, "simulated": True},
        )


def default_specs():
    return (
        RewriteSpec(index=0, transform="lowercase"),
        DeleteSpec(index=1),
        ReferenceSpec(source_messages=(Message(role="system", content="good reference"),), at="append"),
    )


def make_config(seeds=None, **overrides):
    fields = {
        "seeds": tuple(seeds) if seeds is not None else (GOOD_SEED, BAD_SEED),
        "operator_specs": default_specs(),
        "operator_weights": (("rewrite", 1.0), ("delete", 1.0), ("reference", 1.0)),
        "exploration_share": 0.5,
        "exploit_top_k": 2,
        "parent_rule": "uniform_promoted",
        "metric": "fit",
        "promote_threshold": 0.5,
        "max_proposal_rounds": 2,
        "max_promoted": 5,
        "stop_rule": "rounds",
        "racing_rule": "evaluate_all",
        "retries": 0,
        "rng_seed": 0,
        "control_arm": False,
        "confirmation_checks": (("replays", 1), ("tests", 1)),
    }
    fields.update(overrides)
    return FrozenConfig(**fields)


def make_confirmation(**overrides):
    fields = {
        "discovery_context_digest": digest({"fixture": "discovery-context"}),
        "confirmation_context_digest": digest({"fixture": "confirmation-context"}),
        "seed": "conf-seed-1",
        "metric": "fit",
        "threshold": 0.5,
        "samples": 2,
        "confirm_fraction": 0.5,
        "reject_fraction": 0.25,
    }
    fields.update(overrides)
    return ConfirmationSpec(**fields)


def make_actors():
    return self_compression_arm(
        "hybrid-test-checkpoint",
        "rev-1",
        capabilities=("fixture",),
        manifest={"fixture": True, "runtime": "pure-stdlib"},
    )


def run_case(
    tmp: Path,
    *,
    config: FrozenConfig | None = None,
    confirmation: ConfirmationSpec | None = None,
    proposal=None,
    evaluation=None,
    run_id: str = "hybrid-test-001",
) -> HybridRunResult:
    actors = make_actors()
    if proposal is None:
        proposal = EchoProposalAdapter(actors[0])
    if evaluation is None:
        evaluation = FixtureEvaluationAdapter(actors[1])
    return run_hybrid_search(
        tmp / "bundle",
        run_id,
        config or make_config(),
        confirmation or make_confirmation(),
        proposal,
        evaluation,
        target_digest=TARGET_DIGEST,
        target_content=TARGET,
        known_metrics=KNOWN_METRICS,
        nesting_rule=NESTING_RULE,
        scheduler_model="hybrid-pareto-v0",
        model_manifest=MODEL_MANIFEST,
        coordinate_cost=demo_coordinate_cost,
    )


def fresh_tmp() -> Path:
    return Path(tempfile.mkdtemp(prefix="aleph-hybrid-test-"))


def events_of(root: Path):
    return [event for event in read_bundle(root).events]


class TestFrozenConfig(unittest.TestCase):
    def test_empty_seeds_rejected(self) -> None:
        with self.assertRaises(SchedulerError):
            make_config(seeds=())

    def test_duplicate_seed_identity_rejected(self) -> None:
        with self.assertRaises(SchedulerError):
            make_config(seeds=(GOOD_SEED, GOOD_SEED))

    def test_empty_operator_specs_rejected(self) -> None:
        with self.assertRaises(SchedulerError):
            make_config(operator_specs=())

    def test_weights_must_cover_spec_labels_exactly(self) -> None:
        with self.assertRaises(SchedulerError):
            make_config(operator_weights=(("rewrite", 1.0),))
        with self.assertRaises(SchedulerError):
            make_config(operator_weights=(("rewrite", 1.0), ("delete", 1.0), ("reference", 1.0), ("seed", 1.0)))

    def test_nonpositive_weight_rejected(self) -> None:
        with self.assertRaises(SchedulerError):
            make_config(operator_weights=(("rewrite", 0.0), ("delete", 1.0), ("reference", 1.0)))

    def test_bool_weight_rejected(self) -> None:
        with self.assertRaises(SchedulerError):
            make_config(operator_weights=(("rewrite", True), ("delete", 1.0), ("reference", 1.0)))

    def test_exploration_share_range(self) -> None:
        with self.assertRaises(SchedulerError):
            make_config(exploration_share=1.5)
        with self.assertRaises(SchedulerError):
            make_config(exploration_share=-0.1)

    def test_exploit_top_k_rejected(self) -> None:
        with self.assertRaises(SchedulerError):
            make_config(exploit_top_k=0)

    def test_unknown_parent_rule_rejected(self) -> None:
        with self.assertRaises(SchedulerError):
            make_config(parent_rule="nearest_neighbor")

    def test_unknown_stop_rule_rejected(self) -> None:
        with self.assertRaises(SchedulerError):
            make_config(stop_rule="never")

    def test_unknown_racing_rule_rejected(self) -> None:
        with self.assertRaises(SchedulerError):
            make_config(racing_rule="round_robin")

    def test_empty_metric_rejected(self) -> None:
        with self.assertRaises(SchedulerError):
            make_config(metric="")

    def test_promote_threshold_range(self) -> None:
        with self.assertRaises(SchedulerError):
            make_config(promote_threshold=1.5)
        with self.assertRaises(SchedulerError):
            make_config(promote_threshold=-0.5)

    def test_negative_retries_rejected(self) -> None:
        with self.assertRaises(SchedulerError):
            make_config(retries=-1)

    def test_bool_retries_rejected(self) -> None:
        with self.assertRaises(SchedulerError):
            make_config(retries=True)

    def test_negative_rng_seed_rejected(self) -> None:
        with self.assertRaises(SchedulerError):
            make_config(rng_seed=-1)

    def test_max_promoted_rejected(self) -> None:
        with self.assertRaises(SchedulerError):
            make_config(max_promoted=0)

    def test_control_arm_consistency(self) -> None:
        with self.assertRaises(SchedulerError):
            make_config(seeds=(GOOD_SEED,), control_arm=True)
        with self.assertRaises(SchedulerError):
            make_config(seeds=(CONTROL_SEED,), control_arm=False)

    def test_duplicate_confirmation_check_keys_rejected(self) -> None:
        with self.assertRaises(SchedulerError):
            make_config(confirmation_checks=(("replays", 1), ("replays", 2)))

    def test_unknown_confirmation_check_key_rejected(self) -> None:
        with self.assertRaises(SchedulerError):
            make_config(confirmation_checks=(("wat", 1),))

    def test_constant_tuples(self) -> None:
        self.assertIn("uniform_promoted", PARENT_RULES)
        self.assertIn("evaluate_all", RACING_RULES)
        self.assertIn("rounds", STOP_RULES)
        self.assertIsInstance(HYBRID_SCHEMA_VERSION, str)

    def test_canonical_round_trip(self) -> None:
        config = make_config(seeds=(GOOD_SEED, CONTROL_SEED), control_arm=True)
        rebuilt = frozen_config_from_canonical(config.to_canonical())
        self.assertEqual(rebuilt, config)
        self.assertEqual(rebuilt.config_digest, config.config_digest)

    def test_parser_rejects_unknown_fields(self) -> None:
        payload = make_config().to_canonical()
        payload["sneaky"] = True
        with self.assertRaises(SchedulerError):
            frozen_config_from_canonical(payload)

    def test_parser_rejects_missing_seeds(self) -> None:
        payload = make_config().to_canonical()
        del payload["seeds"]
        with self.assertRaises(SchedulerError):
            frozen_config_from_canonical(payload)


class TestEndToEnd(unittest.TestCase):
    def test_default_run_completes_and_verifies(self) -> None:
        tmp = fresh_tmp()
        result = run_case(tmp)
        self.assertEqual(result.status, "completed")
        self.assertEqual(result.confirmation_outcome, "confirmed")
        self.assertIn(result.confirmed_candidate_id, result.shortlist_candidate_ids)
        report = verify_bundle(result.root)
        self.assertTrue(report.ok, report.errors)

    def test_confirmed_candidate_is_shortlist_best(self) -> None:
        tmp = fresh_tmp()
        result = run_case(tmp, config=make_config(max_proposal_rounds=0))
        # GOOD_SEED promotes; BAD_SEED is rejected, so the shortlist is exactly
        # the good seed and confirmation confirms it.
        self.assertEqual(result.promoted_candidate_ids, (GOOD_SEED.candidate_id,))
        self.assertEqual(result.shortlist_candidate_ids, (GOOD_SEED.candidate_id,))
        self.assertEqual(result.confirmed_candidate_id, GOOD_SEED.candidate_id)

    def test_shortlist_tie_break_is_deterministic_by_id(self) -> None:
        other_good = make_seed([("user", "good one"), ("user", "two")])
        seeds = (GOOD_SEED, other_good)
        tmp = fresh_tmp()
        result = run_case(tmp, config=make_config(seeds=seeds, max_proposal_rounds=0))
        expected = tuple(sorted((GOOD_SEED.candidate_id, other_good.candidate_id)))
        self.assertEqual(result.shortlist_candidate_ids, expected)
        self.assertEqual(result.confirmed_candidate_id, expected[0])

    def test_no_confirmed_candidate_when_nothing_promotes(self) -> None:
        tmp = fresh_tmp()
        result = run_case(tmp, config=make_config(seeds=(BAD_SEED,), max_proposal_rounds=0))
        self.assertEqual(result.promoted_candidate_ids, ())
        self.assertEqual(result.confirmation_outcome, "no_confirmed_candidate")
        self.assertIsNone(result.confirmed_candidate_id)
        report = verify_bundle(result.root)
        self.assertTrue(report.ok, report.errors)
        phases = {event.event_type: event.phase for event in events_of(result.root)}
        self.assertEqual(phases["confirmation_completed"], "confirmation")

    def test_confirmation_rejected_when_below_threshold(self) -> None:
        tmp = fresh_tmp()
        result = run_case(
            tmp,
            config=make_config(max_proposal_rounds=0),
            confirmation=make_confirmation(threshold=0.95),
        )
        self.assertEqual(result.confirmation_outcome, "rejected")
        report = verify_bundle(result.root)
        self.assertTrue(report.ok, report.errors)

    def test_two_runs_are_byte_identical(self) -> None:
        first = run_case(fresh_tmp())
        second = run_case(fresh_tmp())
        self.assertEqual(
            (first.root / "events.jsonl").read_bytes(),
            (second.root / "events.jsonl").read_bytes(),
        )
        self.assertEqual(
            read_bundle(first.root).manifest.stream_digest,
            read_bundle(second.root).manifest.stream_digest,
        )

    def test_frozen_config_digest_pinned_in_confirmation(self) -> None:
        tmp = fresh_tmp()
        config = make_config()
        result = run_case(tmp, config=config)
        completed = [
            e for e in events_of(result.root) if e.event_type == "confirmation_completed"
        ]
        self.assertEqual(len(completed), 1)
        self.assertEqual(completed[0].payload.get("frozenConfigDigest"), config.config_digest)
        self.assertEqual(
            completed[0].payload.get("confirmationSpecDigest"),
            make_confirmation().spec_digest,
        )

    def test_ledger_replay_counts(self) -> None:
        tmp = fresh_tmp()
        result = run_case(tmp, config=make_config(max_proposal_rounds=0))
        snapshot = read_bundle(result.root)
        derived = derive_state(snapshot.manifest, snapshot.events, snapshot.blobs)
        self.assertEqual(derived.ledger.decoder["discovery"].calls, 2)
        self.assertEqual(derived.ledger.decoder["confirmation"].calls, 2)
        self.assertEqual(derived.ledger.search_work.proposal_calls, 1)
        self.assertEqual(derived.ledger.search_work.rejected_candidates, 1)
        self.assertFalse(derived.ledger.open_reservations)

    def test_metric_not_declared_rejected(self) -> None:
        tmp = fresh_tmp()
        actors = make_actors()
        with self.assertRaises(SchedulerError):
            run_hybrid_search(
                tmp / "bundle",
                "hybrid-test-001",
                make_config(metric="auc"),
                make_confirmation(),
                EchoProposalAdapter(actors[0]),
                FixtureEvaluationAdapter(actors[1]),
                target_digest=TARGET_DIGEST,
                known_metrics=KNOWN_METRICS,
                nesting_rule=NESTING_RULE,
                scheduler_model="hybrid-pareto-v0",
                model_manifest=MODEL_MANIFEST,
                coordinate_cost=demo_coordinate_cost,
            )

    def test_non_adapter_inputs_rejected(self) -> None:
        tmp = fresh_tmp()
        with self.assertRaises(SchedulerError):
            run_hybrid_search(
                tmp / "bundle",
                "hybrid-test-001",
                make_config(),
                make_confirmation(),
                "not-an-adapter",  # type: ignore[arg-type]
                "not-an-adapter",  # type: ignore[arg-type]
                target_digest=TARGET_DIGEST,
                known_metrics=KNOWN_METRICS,
                nesting_rule=NESTING_RULE,
                scheduler_model="hybrid-pareto-v0",
                model_manifest=MODEL_MANIFEST,
                coordinate_cost=demo_coordinate_cost,
            )


class TestOperatorRounds(unittest.TestCase):
    def test_duplicate_products_suppressed_with_evidence(self) -> None:
        # DeleteSpec(0) on GOOD_SEED yields ['beta'] -> fit 0.4, rejected, so the
        # promoted pool stays {GOOD_SEED}; the second round regenerates the same
        # product identity, which must be suppressed before any proposal.
        config = make_config(
            operator_specs=(DeleteSpec(index=0),),
            operator_weights=(("delete", 1.0),),
            exploration_share=0.0,
            exploit_top_k=1,
            max_proposal_rounds=2,
            retries=0,
        )
        tmp = fresh_tmp()
        result = run_case(tmp, config=config)
        failed = [
            e for e in events_of(result.root)
            if e.event_type == "proposal_failed"
            and e.payload.get("reason") == "no_applicable_operator_products"
        ]
        self.assertTrue(failed, "expected a suppressed-duplicate proposal failure")
        self.assertEqual(failed[0].payload.get("suppressedDuplicates"), 1)
        self.assertEqual(failed[0].payload.get("attempts"), 1)
        report = verify_bundle(result.root)
        self.assertTrue(report.ok, report.errors)

    def test_inapplicable_operators_exhaust_retries(self) -> None:
        config = make_config(
            operator_specs=(DeleteSpec(index=5),),
            operator_weights=(("delete", 1.0),),
            max_proposal_rounds=1,
            retries=2,
        )
        tmp = fresh_tmp()
        result = run_case(tmp, config=config)
        failed = [
            e for e in events_of(result.root)
            if e.event_type == "proposal_failed"
            and e.payload.get("reason") == "no_applicable_operator_products"
        ]
        self.assertEqual(len(failed), 1)
        self.assertEqual(failed[0].payload.get("attempts"), 3)
        report = verify_bundle(result.root)
        self.assertTrue(report.ok, report.errors)

    def test_racing_first_passing_skips_later_evaluations(self) -> None:
        config = make_config(racing_rule="first_passing", max_proposal_rounds=0)
        tmp = fresh_tmp()
        result = run_case(tmp, config=config)
        events = events_of(result.root)
        bad_evals = [
            e for e in events
            if e.event_type == "evaluation_started" and e.payload.get("candidateId") == BAD_SEED.candidate_id
        ]
        self.assertEqual(bad_evals, [], "racing must skip evaluations after the first passing candidate")
        rejections = [
            e for e in events
            if e.event_type == "candidate_rejected"
            and e.payload.get("candidateId") == BAD_SEED.candidate_id
        ]
        self.assertEqual(rejections[0].payload.get("reason"), "dominated")
        report = verify_bundle(result.root)
        self.assertTrue(report.ok, report.errors)

    def test_archive_full_stop_rule(self) -> None:
        config = make_config(
            stop_rule="archive_full",
            max_promoted=1,
            max_proposal_rounds=100,
            racing_rule="evaluate_all",
        )
        tmp = fresh_tmp()
        result = run_case(tmp, config=config)
        self.assertEqual(result.status, "completed")
        self.assertLessEqual(len(result.promoted_candidate_ids), 100)
        report = verify_bundle(result.root)
        self.assertTrue(report.ok, report.errors)


class TestFailurePaths(unittest.TestCase):
    def test_seed_proposal_failure_aborts_run(self) -> None:
        tmp = fresh_tmp()
        actors = make_actors()
        result = run_case(tmp, proposal=FailingProposalAdapter(actors[0]))
        self.assertEqual(result.status, "aborted")
        self.assertIsNone(result.confirmation_outcome)
        events = events_of(result.root)
        self.assertTrue(any(e.event_type == "proposal_failed" for e in events))
        self.assertTrue(any(e.event_type == "budget_failed" for e in events))
        report = verify_bundle(result.root)
        self.assertTrue(report.ok, report.errors)

    def test_evaluation_failure_is_recorded_and_run_continues(self) -> None:
        tmp = fresh_tmp()
        actors = make_actors()
        boom_seed = make_seed([("user", "boom good"), ("user", "x")])
        evaluation = FixtureEvaluationAdapter(actors[1], fail_on="boom")
        result = run_case(
            tmp,
            config=make_config(seeds=(boom_seed, GOOD_SEED), max_proposal_rounds=0),
            evaluation=evaluation,
        )
        self.assertEqual(result.status, "completed")
        events = events_of(result.root)
        self.assertTrue(any(e.event_type == "evaluation_failed" for e in events))
        rejected = [
            e for e in events
            if e.event_type == "candidate_rejected"
            and e.payload.get("candidateId") == boom_seed.candidate_id
        ]
        self.assertEqual(rejected[0].payload.get("reason"), "evaluation_failed")
        report = verify_bundle(result.root)
        self.assertTrue(report.ok, report.errors)

    def test_confirmation_evaluation_failure_rejects(self) -> None:
        tmp = fresh_tmp()
        actors = make_actors()
        evaluation = FixtureEvaluationAdapter(actors[1], fail_on_reservation="rsv-eval-confirm")
        result = run_case(
            tmp,
            config=make_config(max_proposal_rounds=0),
            evaluation=evaluation,
        )
        self.assertEqual(result.confirmation_outcome, "rejected")
        snapshot = read_bundle(result.root)
        derived = derive_state(snapshot.manifest, snapshot.events, snapshot.blobs)
        self.assertEqual(derived.ledger.decoder["confirmation"].failures, 2)
        report = verify_bundle(result.root)
        self.assertTrue(report.ok, report.errors)

    def test_receipt_mismatch_in_operator_round_fails_proposal_only(self) -> None:
        tmp = fresh_tmp()
        actors = make_actors()
        rogue = make_seed([("user", "rogue ✗")])
        proposal = EchoProposalAdapter(actors[0], rogue=rogue, rogue_after=2)
        result = run_case(tmp, proposal=proposal)
        self.assertEqual(result.status, "completed")
        failed = [
            e for e in events_of(result.root)
            if e.event_type == "proposal_failed" and e.payload.get("reason") == "receipt_mismatch"
        ]
        self.assertEqual(len(failed), 1)
        report = verify_bundle(result.root)
        self.assertTrue(report.ok, report.errors)

    def test_seed_receipt_mismatch_aborts_run(self) -> None:
        tmp = fresh_tmp()
        actors = make_actors()
        rogue = make_seed([("user", "rogue ✗")])
        proposal = EchoProposalAdapter(actors[0], rogue=rogue, rogue_after=1)
        result = run_case(tmp, proposal=proposal)
        self.assertEqual(result.status, "aborted")
        report = verify_bundle(result.root)
        self.assertTrue(report.ok, report.errors)


class TestControlArm(unittest.TestCase):
    def test_control_candidate_is_policy_excluded(self) -> None:
        tmp = fresh_tmp()
        config = make_config(
            seeds=(GOOD_SEED, CONTROL_SEED),
            control_arm=True,
            max_proposal_rounds=0,
        )
        result = run_case(tmp, config=config)
        events = events_of(result.root)
        control_rejections = [
            e for e in events
            if e.event_type == "candidate_rejected"
            and e.payload.get("candidateId") == CONTROL_SEED.candidate_id
        ]
        self.assertEqual(len(control_rejections), 1)
        self.assertEqual(control_rejections[0].payload.get("reason"), "policy_excluded")
        self.assertNotIn(CONTROL_SEED.candidate_id, result.promoted_candidate_ids)
        self.assertNotIn(CONTROL_SEED.candidate_id, result.shortlist_candidate_ids)
        # The control copies the target verbatim and the verifier still passes:
        # explicit_reconstruction is the declared, exempt copy control.
        report = verify_bundle(result.root)
        self.assertTrue(report.ok, report.errors)

    def test_control_never_becomes_parent(self) -> None:
        tmp = fresh_tmp()
        config = make_config(
            seeds=(GOOD_SEED, CONTROL_SEED),
            control_arm=True,
            max_proposal_rounds=3,
        )
        result = run_case(tmp, config=config)
        proposal_events = [
            e for e in events_of(result.root) if e.event_type == "proposal_succeeded"
        ]
        # The seed proposal legitimately carries the control candidate; every
        # operator round must never select it as a parent or propose it again.
        for event in proposal_events[1:]:
            self.assertNotIn(CONTROL_SEED.candidate_id, event.payload.get("candidateIds", []))
        report = verify_bundle(result.root)
        self.assertTrue(report.ok, report.errors)


class TestAcquisitionExtremes(unittest.TestCase):
    def test_pure_exploit_and_pure_explore_runs_verify(self) -> None:
        for share in (0.0, 1.0):
            with self.subTest(exploration_share=share):
                tmp = fresh_tmp()
                result = run_case(tmp, config=make_config(exploration_share=share))
                self.assertEqual(result.status, "completed")
                report = verify_bundle(result.root)
                self.assertTrue(report.ok, report.errors)


class TestHelpers(unittest.TestCase):
    def test_unfreeze_projection_round_trips(self) -> None:
        value = {"a": {"b": [1, 2]}, "c": "x"}
        from search.engine.contracts import _frozen_mapping

        projected = dict(_frozen_mapping(value, "test"))
        rebuilt = {key: unfreeze_projection(item) for key, item in projected.items()}
        self.assertEqual(rebuilt, value)


if __name__ == "__main__":
    unittest.main()


class TestRedTeamRegressions(unittest.TestCase):
    """Regressions pinned by the independent review of the scheduler slice."""

    def test_parser_rejects_missing_required_fields(self) -> None:
        for key in ("metric", "maxProposalRounds", "maxPromoted"):
            with self.subTest(missing=key):
                payload = make_config().to_canonical()
                del payload[key]
                with self.assertRaises(SchedulerError):
                    frozen_config_from_canonical(payload)

    def test_parser_rejects_unknown_schema_version(self) -> None:
        payload = make_config().to_canonical()
        payload["schemaVersion"] = "aleph-engine-hybrid-pareto/9.9.9"
        with self.assertRaises(SchedulerError):
            frozen_config_from_canonical(payload)

    def test_parser_rejects_malformed_seed(self) -> None:
        payload = make_config().to_canonical()
        payload["seeds"] = ["not-a-candidate"]
        with self.assertRaises(SchedulerError):
            frozen_config_from_canonical(payload)

    def test_receipt_request_id_mismatch_fails_proposal(self) -> None:
        tmp = fresh_tmp()
        actors = make_actors()
        rogue = make_seed([("user", "rogue ✗")])
        proposal = RequestIdRogueAdapter(actors[0], rogue=rogue)
        result = run_case(tmp, proposal=proposal)
        self.assertEqual(result.status, "completed")
        failed = [
            e for e in events_of(result.root)
            if e.event_type == "proposal_failed" and e.payload.get("reason") == "receipt_mismatch"
        ]
        self.assertEqual(len(failed), 1)
        self.assertTrue(failed[0].payload.get("receiptRequestId", "").endswith("-tampered"))
        self.assertEqual(failed[0].blob_digests, ())
        report = verify_bundle(result.root)
        self.assertTrue(report.ok, report.errors)


class RequestIdRogueAdapter(EchoProposalAdapter):
    """Rogue once: same candidates, wrong request id."""

    def __init__(self, identity, *, rogue: Candidate):
        super().__init__(identity)
        self._rogue = rogue
        self._n = 0

    def propose(self, request):
        self._n += 1
        context = dict(request.context)
        raw = context.get("operatorProducts", context.get("seeds", ()))
        candidates = tuple(
            candidate_from_canonical(unfreeze_projection(item)) for item in raw
        )
        request_id = request.request_id + "-tampered" if self._n == 2 else request.request_id
        return proposal_receipt(
            request_id=request_id,
            adapter=self._identity,
            candidates=candidates,
            resource_use={"fixture": True},
        )


class TestFuzzRegressions(unittest.TestCase):
    """Regressions found by randomized scheduler fuzzing."""

    def test_large_seed_batch_gets_unique_evaluation_request_ids(self) -> None:
        # Fuzz found: request ids keyed by a candidate-id prefix collide when
        # two candidates share one. Batch+position ids are unique by
        # construction; a 60-candidate seed batch stresses the invariant.
        seeds = tuple(
            make_seed([("user", f"seed {index} content"), ("user", "second")])
            for index in range(60)
        )
        if len({seed.candidate_id for seed in seeds}) != len(seeds):
            self.skipTest("fixture collision is astronomically unlikely; skip")
        tmp = fresh_tmp()
        result = run_case(tmp, config=make_config(seeds=seeds, max_proposal_rounds=0))
        started = [
            e for e in events_of(result.root) if e.event_type == "evaluation_started"
        ]
        request_ids = [e.payload["requestId"] for e in started]
        self.assertEqual(len(request_ids), len(set(request_ids)))
        self.assertEqual(len(started), 60)
        report = verify_bundle(result.root)
        self.assertTrue(report.ok, report.errors)


class TestStopRuleHangRegression(unittest.TestCase):
    """Red-team regression: an unfillable archive must still terminate."""

    def test_archive_full_with_no_growth_stops_at_rounds_bound(self) -> None:
        # All operator products stay below threshold, so max_promoted can
        # never be reached; the rounds bound must terminate the loop anyway.
        config = make_config(
            operator_specs=(DeleteSpec(index=0),),
            operator_weights=(("delete", 1.0),),
            seeds=(GOOD_SEED,),
            stop_rule="archive_full",
            max_promoted=999,
            max_proposal_rounds=3,
            exploration_share=0.0,
            exploit_top_k=1,
        )
        tmp = fresh_tmp()
        result = run_case(tmp, config=config)
        self.assertEqual(result.status, "completed")
        # The only promoted candidate stays below max_promoted forever; the
        # three declared rounds must still run and the run must freeze.
        self.assertEqual(len(result.promoted_candidate_ids), 1)
        report = verify_bundle(result.root)
        self.assertTrue(report.ok, report.errors)
