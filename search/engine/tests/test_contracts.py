"""Candidate identity and adapter contract tests, including adversarial ones."""

from __future__ import annotations

import unittest

from search.engine.canonical import digest
from search.engine.contracts import (
    AdapterIdentity,
    Candidate,
    ContractViolation,
    EvaluationRequest,
    EvaluationReceipt,
    Message,
    Placement,
    ProposalReceipt,
    ProposalRequest,
    adapter_identity,
    adapter_identity_from_canonical,
    candidate_from_canonical,
    evaluation_receipt,
    evaluation_receipt_from_canonical,
    message_from_canonical,
    placement_from_canonical,
    proposal_receipt,
    proposal_receipt_from_canonical,
    proposal_request,
    proposal_request_from_canonical,
    self_compression_arm,
)


def make_placement() -> Placement:
    return Placement(
        scaffold_id="scaffold/0.1.0",
        scaffold_digest=digest("scaffold"),
        prompt_position="messages[0]",
        rendered_template_version="template/0.1.0",
    )


def make_candidate(content: str = "coordinate", *, role: str = "candidate") -> Candidate:
    return Candidate(
        messages=(Message(role="user", content=content),),
        placement=make_placement(),
        proposal_mode="seed",
        role=role,
    )


class TestMessage(unittest.TestCase):
    def test_content_is_nfc_normalized(self) -> None:
        message = Message(role="user", content="cafe\u0301")
        self.assertEqual(message.content, "caf\u00e9")

    def test_unknown_role_rejected(self) -> None:
        with self.assertRaises(ContractViolation):
            Message(role="planner", content="x")

    def test_round_trip_rejects_unknown_fields(self) -> None:
        payload = message_from_canonical({"role": "user", "content": "x"}).to_canonical()
        payload["extra"] = 1
        with self.assertRaises(ContractViolation):
            message_from_canonical(payload)


class TestPlacement(unittest.TestCase):
    def test_requires_well_formed_scaffold_digest(self) -> None:
        with self.assertRaises(ContractViolation):
            Placement(
                scaffold_id="s",
                scaffold_digest="not-a-digest",
                prompt_position="messages[0]",
                rendered_template_version="v",
            )

    def test_empty_fields_rejected(self) -> None:
        with self.assertRaises(ContractViolation):
            Placement(scaffold_id="", scaffold_digest=digest("x"), prompt_position="p", rendered_template_version="v")

    def test_round_trip_rejects_unknown_fields(self) -> None:
        payload = make_placement().to_canonical()
        payload["extra"] = 1
        with self.assertRaises(ContractViolation):
            placement_from_canonical(payload)


class TestCandidateIdentity(unittest.TestCase):
    def test_identity_excludes_scores_timestamps_parents_and_positions(self) -> None:
        first = make_candidate()
        second = Candidate(
            messages=first.messages,
            placement=first.placement,
            proposal_mode=first.proposal_mode,
            role=first.role,
        )
        self.assertEqual(first.candidate_id, second.candidate_id)

    def test_identity_changes_with_content(self) -> None:
        self.assertNotEqual(
            make_candidate("one").candidate_id, make_candidate("two").candidate_id
        )

    def test_identity_changes_with_role(self) -> None:
        self.assertNotEqual(
            make_candidate(role="candidate").candidate_id,
            make_candidate(role="explicit_reconstruction").candidate_id,
        )

    def test_identity_changes_with_placement(self) -> None:
        other = Candidate(
            messages=make_candidate().messages,
            placement=Placement(
                scaffold_id="scaffold/0.2.0",
                scaffold_digest=digest("other"),
                prompt_position="messages[1]",
                rendered_template_version="template/0.2.0",
            ),
            proposal_mode="seed",
        )
        self.assertNotEqual(make_candidate().candidate_id, other.candidate_id)

    def test_identity_changes_with_proposal_mode(self) -> None:
        other = Candidate(
            messages=make_candidate().messages,
            placement=make_placement(),
            proposal_mode="rewrite",
        )
        self.assertNotEqual(make_candidate().candidate_id, other.candidate_id)

    def test_nfc_equivalent_contents_share_identity(self) -> None:
        self.assertEqual(
            make_candidate("cafe\u0301").candidate_id, make_candidate("caf\u00e9").candidate_id
        )

    def test_round_trip_verifies_declared_id(self) -> None:
        candidate = make_candidate()
        rebuilt = candidate_from_canonical(candidate.to_canonical())
        self.assertEqual(rebuilt, candidate)

    def test_round_trip_rejects_tampered_id(self) -> None:
        payload = make_candidate().to_canonical()
        payload["candidateId"] = "sha256:" + "0" * 64
        with self.assertRaises(ContractViolation):
            candidate_from_canonical(payload)

    def test_round_trip_rejects_unknown_fields(self) -> None:
        payload = make_candidate().to_canonical()
        payload["score"] = 0.99  # adversarial: smuggled evaluator score
        with self.assertRaises(ContractViolation):
            candidate_from_canonical(payload)

    def test_missing_message_fields_rejected(self) -> None:
        payload = make_candidate().to_canonical()
        del payload["messages"][0]["content"]
        with self.assertRaises(ContractViolation):
            candidate_from_canonical(payload)

    def test_unknown_proposal_mode_rejected(self) -> None:
        with self.assertRaises(ContractViolation):
            Candidate(
                messages=(Message(role="user", content="x"),),
                placement=make_placement(),
                proposal_mode="invent",
            )

    def test_empty_messages_rejected(self) -> None:
        with self.assertRaises(ContractViolation):
            Candidate(messages=(), placement=make_placement(), proposal_mode="seed")


class TestAdapterIdentity(unittest.TestCase):
    def test_immutable_capabilities_sorted_deduped(self) -> None:
        identity = adapter_identity("a", "rev", "proposal", capabilities=("b", "a", "b"))
        self.assertEqual(identity.capabilities, ("a", "b"))

    def test_adapter_digest_covers_manifest(self) -> None:
        first = adapter_identity("a", "rev", "proposal", manifest={"x": 1})
        second = adapter_identity("a", "rev", "proposal", manifest={"x": 2})
        self.assertNotEqual(first.adapter_digest, second.adapter_digest)

    def test_round_trip(self) -> None:
        identity = adapter_identity("a", "rev", "evaluation", capabilities=("c",), manifest={"k": [1, 2]})
        rebuilt = adapter_identity_from_canonical(identity.to_canonical())
        self.assertEqual(rebuilt, identity)

    def test_round_trip_rejects_unknown_fields(self) -> None:
        payload = adapter_identity("a", "rev", "proposal").to_canonical()
        payload["secret"] = 1
        with self.assertRaises(ContractViolation):
            adapter_identity_from_canonical(payload)

    def test_unknown_role_rejected(self) -> None:
        with self.assertRaises(ContractViolation):
            adapter_identity("a", "rev", "scheduler")


class TestRequestsAndReceipts(unittest.TestCase):
    def test_proposal_request_requires_well_formed_target_digest(self) -> None:
        adapter = adapter_identity("p", "rev", "proposal")
        with self.assertRaises(ContractViolation):
            proposal_request(
                request_id="r", reservation_id="rsv", adapter=adapter,
                proposal_mode="seed", target_digest="nope",
            )

    def test_proposal_request_requires_proposal_adapter(self) -> None:
        evaluator = adapter_identity("e", "rev", "evaluation")
        with self.assertRaises(ContractViolation):
            proposal_request(
                request_id="r", reservation_id="rsv", adapter=evaluator,
                proposal_mode="seed", target_digest=digest("t"),
            )

    def test_proposal_receipt_forbids_evaluator_scores(self) -> None:
        adapter = adapter_identity("p", "rev", "proposal")
        with self.assertRaises(ContractViolation):
            ProposalReceipt(
                request_id="r",
                adapter=adapter,
                candidates=(make_candidate(),),
                resource_use=(("fit", 0.9),),
            )
        for key in ("score", "scores", "metric", "metrics", "metricVector", "distortion", "reward"):
            with self.assertRaises(ContractViolation, msg=key):
                proposal_receipt(
                    request_id="r", adapter=adapter,
                    candidates=(make_candidate(),), resource_use={key: 1.0},
                )

    def test_evaluation_receipt_requires_metrics(self) -> None:
        adapter = adapter_identity("e", "rev", "evaluation")
        with self.assertRaises(ContractViolation):
            evaluation_receipt(
                request_id="r", adapter=adapter, candidate_id="c", metrics={},
            )

    def test_evaluation_request_requires_evaluation_adapter(self) -> None:
        proposer = adapter_identity("p", "rev", "proposal")
        with self.assertRaises(ContractViolation):
            EvaluationRequest(
                request_id="r", reservation_id="rsv", adapter=proposer,
                candidate=make_candidate(),
            )

    def test_empty_request_ids_rejected(self) -> None:
        adapter = adapter_identity("p", "rev", "proposal")
        with self.assertRaises(ContractViolation):
            proposal_request(
                request_id="", reservation_id="rsv", adapter=adapter,
                proposal_mode="seed", target_digest=digest("t"),
            )

    def test_proposal_receipt_round_trip(self) -> None:
        adapter = adapter_identity("p", "rev", "proposal")
        receipt = proposal_receipt(
            request_id="r", adapter=adapter,
            candidates=(make_candidate("a"), make_candidate("b")),
            resource_use={"calls": 1},
        )
        rebuilt = proposal_receipt_from_canonical(receipt.to_canonical())
        self.assertEqual(rebuilt, receipt)

    def test_proposal_receipt_round_trip_rejects_unknown_fields(self) -> None:
        adapter = adapter_identity("p", "rev", "proposal")
        receipt = proposal_receipt(request_id="r", adapter=adapter, candidates=(make_candidate(),))
        payload = receipt.to_canonical()
        payload["metrics"] = {"fit": 1.0}  # adversarial: scores smuggled into a receipt
        with self.assertRaises(ContractViolation):
            proposal_receipt_from_canonical(payload)

    def test_proposal_receipt_candidates_must_carry_candidate_id(self) -> None:
        adapter = adapter_identity("p", "rev", "proposal")
        receipt = proposal_receipt(request_id="r", adapter=adapter, candidates=(make_candidate(),))
        payload = receipt.to_canonical()
        del payload["candidates"][0]["candidateId"]
        with self.assertRaises(ContractViolation):
            proposal_receipt_from_canonical(payload)

    def test_evaluation_receipt_round_trip(self) -> None:
        adapter = adapter_identity("e", "rev", "evaluation")
        receipt = evaluation_receipt(
            request_id="r", adapter=adapter, candidate_id="c",
            metrics={"fit": 0.9}, resource_use={"inputTokens": 10},
            outputs={"answer": "x"},
        )
        rebuilt = evaluation_receipt_from_canonical(receipt.to_canonical())
        self.assertEqual(rebuilt, receipt)

    def test_evaluation_receipt_round_trip_rejects_unknown_fields(self) -> None:
        adapter = adapter_identity("e", "rev", "evaluation")
        receipt = evaluation_receipt(
            request_id="r", adapter=adapter, candidate_id="c", metrics={"fit": 0.9}
        )
        payload = receipt.to_canonical()
        payload["candidate"] = make_candidate().to_canonical()  # evaluator smuggling a coordinate
        with self.assertRaises(ContractViolation):
            evaluation_receipt_from_canonical(payload)

    def test_proposal_request_round_trip(self) -> None:
        adapter = adapter_identity("p", "rev", "proposal")
        request = proposal_request(
            request_id="r", reservation_id="rsv", adapter=adapter,
            proposal_mode="delete", target_digest=digest("t"),
            context={"task": "fixture"}, parent_candidate_ids=("a", "b"),
        )
        rebuilt = proposal_request_from_canonical(request.to_canonical())
        self.assertEqual(rebuilt, request)


class TestSelfCompressionArm(unittest.TestCase):
    def test_distinct_ids_roles_shared_checkpoint(self) -> None:
        proposal, evaluation = self_compression_arm("ckpt", "rev", capabilities=("fixture",))
        self.assertNotEqual(proposal.adapter_id, evaluation.adapter_id)
        self.assertEqual(proposal.role, "proposal")
        self.assertEqual(evaluation.role, "evaluation")
        self.assertNotEqual(proposal.adapter_digest, evaluation.adapter_digest)
        self.assertEqual(proposal.capabilities, evaluation.capabilities)
        self.assertEqual(proposal.manifest, evaluation.manifest)
        self.assertIn(("arm", "self_compression"), proposal.manifest)


if __name__ == "__main__":
    unittest.main()
