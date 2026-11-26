"""Fixture-mode pipeline test for the canary plan (no MLX).

Runs the exact frozen canary plan (smoke target, seeds, operators, protected
confirmation) with deterministic fixture adapters and checks that the
resulting bundle exports and verifies. Everything here is labelled fixture
evidence; the live pinned-model run is separate (``canary.py`` and
``test_mlx_canary_live.py``).
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from search.engine.canonical import digest
from search.engine.contracts import (
    AdapterIdentity,
    EvaluationReceipt,
    EvaluationRequest,
    evaluation_receipt,
)
from search.engine.export_aleph_run import export_aleph_run
from search.engine.fixtures import canary as canary_fixture
from search.engine.hybrid_pareto import run_hybrid_search
from search.engine.ledger import CoordinateCost
from search.engine.verify import verify_bundle

_FIXTURE_CREATED_AT = "2026-10-15T00:00:00Z"


def fixture_placement():
    return canary_fixture.canary_placement(
        tokenizer_digest=digest({"fixture": "canary-tokenizer"}),
        chat_template_digest=digest({"fixture": "canary-template"}),
    )


def fixture_manifest() -> dict:
    return canary_fixture.canary_manifest(
        model="fixture-model",
        revision="fixture",
        decoding=canary_fixture.canary_decoding(),
        observation_mode="fixture",
        runtime={"fixture": True},
        resolved_files=[],
        tokenizer_view=canary_fixture.CANARY_TOKENIZER_VIEW,
        tokenizer_digest=digest({"fixture": "canary-tokenizer"}),
        chat_template_digest=digest({"fixture": "canary-template"}),
        git_commit="fixture",
    )


class FixtureCanaryEvaluationAdapter:
    """Deterministic fixture evaluator: the smoke answer with declared metrics."""

    def __init__(self, identity: AdapterIdentity) -> None:
        self._identity = identity

    @property
    def identity(self) -> AdapterIdentity:
        return self._identity

    def evaluate(self, request: EvaluationRequest) -> EvaluationReceipt:
        return evaluation_receipt(
            request_id=request.request_id,
            adapter=self._identity,
            candidate_id=request.candidate.candidate_id,
            metrics={"fit": 1.0, "stability": 1.0, "compression": 0.1, "leakage": 0.0},
            resource_use={"inputTokens": 8, "outputTokens": 2, "samples": 2},
            outputs={"text": canary_fixture.CANARY_TARGET, "fixture": True},
        )


def _fixture_coordinate_cost(candidate) -> CoordinateCost:
    coordinate_bytes = sum(len(message.content.encode("utf-8")) for message in candidate.messages)
    tokens = coordinate_bytes // 4 + 1
    return CoordinateCost(
        tokenizer_view=canary_fixture.CANARY_TOKENIZER_VIEW,
        tokenizer_digest=digest({"fixture": "canary-tokenizer"}),
        coordinate_tokens=tokens,
        coordinate_utf8_bytes=coordinate_bytes,
        full_rendered_tokens=tokens + 8,
        full_rendered_utf8_bytes=coordinate_bytes + 64,
        target_tokens=2,
        continuation_tokens=0,
        prefix_free_bits=None,
    )


class CanaryPlanTest(unittest.TestCase):
    def test_plan_is_well_formed(self) -> None:
        placement = fixture_placement()
        seeds = canary_fixture.canary_seeds(placement)
        self.assertEqual(len(seeds), 3)
        self.assertEqual(seeds[2].role, "explicit_reconstruction")
        self.assertEqual(len({seed.candidate_id for seed in seeds}), 3)
        config = canary_fixture.canary_config(placement)
        self.assertTrue(config.control_arm)
        confirmation = canary_fixture.canary_confirmation()
        self.assertGreaterEqual(confirmation.samples, 1)
        self.assertNotEqual(
            confirmation.discovery_context_digest, confirmation.confirmation_context_digest
        )


class CanaryFixtureRunTest(unittest.TestCase):
    def test_fixture_run_exports_and_verifies(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            bundle = Path(tmp) / "bundle"
            placement = fixture_placement()
            config = canary_fixture.canary_config(placement)
            proposal = canary_fixture.CanaryOperatorProposalAdapter(
                canary_fixture.canary_proposal_identity()
            )
            evaluation = FixtureCanaryEvaluationAdapter(
                canary_fixture.canary_evaluation_identity(
                    model="fixture-model",
                    revision="fixture",
                    decoding=canary_fixture.canary_decoding(),
                    observation_mode="fixture",
                    runtime={"fixture": True},
                )
            )
            result = run_hybrid_search(
                bundle,
                canary_fixture.CANARY_RUN_ID,
                config,
                canary_fixture.canary_confirmation(),
                proposal,
                evaluation,
                target_digest=canary_fixture.canary_target_digest(),
                known_metrics=canary_fixture.CANARY_METRICS,
                target_content=canary_fixture.CANARY_TARGET,
                nesting_rule=canary_fixture.CANARY_NESTING_RULE,
                scheduler_model=canary_fixture.CANARY_SCHEDULER_MODEL,
                model_manifest=fixture_manifest(),
                coordinate_cost=_fixture_coordinate_cost,
                run_created_at=_FIXTURE_CREATED_AT,
            )
            self.assertEqual(result.status, "completed")
            self.assertEqual(result.confirmation_outcome, "confirmed")
            export = export_aleph_run(bundle)
            report = verify_bundle(bundle)
            self.assertTrue(report.ok, report.errors)
            selected = export.projection["selectedCandidateId"]
            self.assertTrue(selected)
            candidate_ids = [candidate["id"] for candidate in export.projection["candidates"]]
            self.assertIn(selected, candidate_ids)
            for candidate in export.projection["candidates"]:
                for name in ("fit", "stability", "compression", "leakage"):
                    self.assertIn(name, candidate)
            control_id = canary_fixture.canary_seeds(placement)[2].candidate_id
            self.assertIn(control_id, export.omitted_candidate_ids)
            self.assertEqual(export.projection["observations"]["mode"], "fixture")
            self.assertEqual(export.projection["config"]["model"], "fixture-model")


if __name__ == "__main__":
    unittest.main()
