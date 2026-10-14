"""Deterministic demo run fixture for the PR A artifact kernel.

The demo builds a complete, valid bundle that exercises every event type,
Unicode/CJK/emoji canonicalization, a self-compression adapter arm, a
promotion/rejection pair, protected confirmation, and a tagged
``explicit_reconstruction`` control candidate. It contains no randomness and
no timestamps, so two builds in fresh directories produce byte-identical
digests — the tests pin exactly that property.

Fixture values (token counts, metrics, adapter outputs) are simulated by
construction and are labelled as fixtures; they are never model evidence.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from ..archive import ARCHIVE_VIEW_SCHEMA_VERSION, RunBundle, materialize
from ..canonical import canonical_bytes, digest, utf8_byte_length
from ..contracts import (
    AdapterIdentity,
    Candidate,
    EvaluationAdapter,
    EvaluationReceipt,
    EvaluationRequest,
    Message,
    Placement,
    ProposalAdapter,
    ProposalReceipt,
    ProposalRequest,
    evaluation_receipt,
    proposal_receipt,
    self_compression_arm,
)
from ..events import Event, build_event
from ..ledger import CoordinateCost

DEMO_RUN_ID = "aleph-demo-001"

# The target includes CJK and an emoji; the decomposed spelling of "é" in one
# candidate exercises NFC normalization on the identity path.
DEMO_TARGET = "Aleph compresses: the shortest prompt that reproduces 你好，世界 \U0001f30d."
DEMO_TARGET_DECOMPOSED = DEMO_TARGET.replace("\u00e9", "e\u0301")

DEMO_SCAFFOLD_ID = "demo-scaffold/0.1.0"
DEMO_TEMPLATE_VERSION = "demo-template/0.1.0"
DEMO_TOKENIZER_VIEW = "demo-tokenizer/0.1.0"
DEMO_TOKENIZER_DIGEST = digest({"fixture": "demo-tokenizer-manifest"})
DEMO_SCHEDULER = "demo-single-worker-v0"
DEMO_SELECTION_RULE = "demo-pareto-v0"
DEMO_KNOWN_METRICS = ("fit", "stability")
DEMO_NESTING_RULE = "t_dec_nested_in_w_search"

DEMO_SCAFFOLD_OVERHEAD_TOKENS = 8
DEMO_RENDERED_OVERHEAD_BYTES = 96


@dataclass(frozen=True)
class DemoActors:
    """The declared proposal/evaluation identities of the demo arm."""

    proposal: AdapterIdentity
    evaluation: AdapterIdentity


def demo_scaffold() -> Placement:
    """The fixed scaffold used by every demo candidate."""
    return Placement(
        scaffold_id=DEMO_SCAFFOLD_ID,
        scaffold_digest=digest({"fixture": "demo-scaffold", "version": DEMO_TEMPLATE_VERSION}),
        prompt_position="messages[0]",
        rendered_template_version=DEMO_TEMPLATE_VERSION,
    )


def demo_target_digest() -> str:
    return digest(DEMO_TARGET)


def demo_actors() -> DemoActors:
    """One checkpoint declared in both roles (explicit self_compression arm)."""
    proposal, evaluation = self_compression_arm(
        "demo-checkpoint",
        "rev-1",
        capabilities=("fixture",),
        manifest={"fixture": True, "runtime": "pure-stdlib"},
    )
    return DemoActors(proposal=proposal, evaluation=evaluation)


def _demo_candidate(messages: tuple[Message, ...], *, mode: str = "seed") -> Candidate:
    return Candidate(
        messages=messages,
        placement=demo_scaffold(),
        proposal_mode=mode,
        role="candidate",
    )


def demo_candidates() -> tuple[Candidate, Candidate, Candidate]:
    """Three fixed candidates: two ordinary, one explicit-reconstruction control."""
    short = _demo_candidate(
        (Message(role="user", content="Short hint: the phrase has 你好，世界 and an emoji."),)
    )
    medium = _demo_candidate(
        (
            Message(
                role="user",
                content="Compress this target: 你好，世界 \U0001f30d — keep the greeting.",
            ),
        )
    )
    # NFC exercise: the control copies the target using a decomposed "é".
    control = Candidate(
        messages=(Message(role="user", content=DEMO_TARGET_DECOMPOSED),),
        placement=demo_scaffold(),
        proposal_mode="reference",
        role="explicit_reconstruction",
    )
    return short, medium, control


class DemoProposalAdapter(ProposalAdapter):
    """Fixture proposer: returns the three fixed candidates, no scores."""

    def __init__(self, identity: AdapterIdentity) -> None:
        self._identity = identity

    @property
    def identity(self) -> AdapterIdentity:
        return self._identity

    def propose(self, request: ProposalRequest) -> ProposalReceipt:
        return proposal_receipt(
            request_id=request.request_id,
            adapter=self._identity,
            candidates=demo_candidates(),
            resource_use={"fixture": True},
        )


class DemoEvaluationAdapter(EvaluationAdapter):
    """Fixture evaluator: deterministic metrics keyed by candidate id."""

    _FIT_BY_CANDIDATE = {
        "short": 0.61,
        "medium": 0.82,
        "control": 0.99,
    }

    def __init__(self, identity: AdapterIdentity) -> None:
        self._identity = identity

    @property
    def identity(self) -> AdapterIdentity:
        return self._identity

    def evaluate(self, request: EvaluationRequest) -> EvaluationReceipt:
        candidate = request.candidate
        if "Short hint" in candidate.messages[0].content:
            fit, stability = 0.61, 0.80
        elif "Compress this target" in candidate.messages[0].content:
            fit, stability = 0.82, 0.88
        else:
            fit, stability = 0.99, 0.99
        return evaluation_receipt(
            request_id=request.request_id,
            adapter=self._identity,
            candidate_id=candidate.candidate_id,
            metrics={"fit": fit, "stability": stability},
            resource_use={
                "inputTokens": 32,
                "outputTokens": 12,
                "samples": 1,
                "providerReportedTokens": 44,
            },
            outputs={"fixture": True, "simulated": True},
        )


def demo_coordinate_cost(candidate: Candidate) -> CoordinateCost:
    """Fixture C(p) record for a candidate, with exact byte/token accounting shape."""
    coordinate_bytes = sum(utf8_byte_length(message.content) for message in candidate.messages)
    coordinate_tokens = coordinate_bytes // 4 + 1
    return CoordinateCost(
        tokenizer_view=DEMO_TOKENIZER_VIEW,
        tokenizer_digest=DEMO_TOKENIZER_DIGEST,
        coordinate_tokens=coordinate_tokens,
        coordinate_utf8_bytes=coordinate_bytes,
        full_rendered_tokens=coordinate_tokens + DEMO_SCAFFOLD_OVERHEAD_TOKENS,
        full_rendered_utf8_bytes=coordinate_bytes + DEMO_RENDERED_OVERHEAD_BYTES,
        target_tokens=10,
        continuation_tokens=0,
        prefix_free_bits=None,
    )


def demo_model_manifest() -> dict[str, Any]:
    """Fixture M_desc manifest; nothing here is a real model identity."""
    return {
        "fixture": True,
        "model": "demo-fixture-model",
        "revision": "fixture",
        "tokenizerView": DEMO_TOKENIZER_VIEW,
        "decoding": {"temperature": 0.0, "maxNewTokens": 64},
    }


def demo_bundle_config(*, run_id: str = DEMO_RUN_ID) -> dict[str, Any]:
    """The manifest arguments shared by every demo build."""
    actors = demo_actors()
    return {
        "run_id": run_id,
        "target_digest": demo_target_digest(),
        "target_content": DEMO_TARGET,
        "known_metrics": DEMO_KNOWN_METRICS,
        "adapter_digests": (
            actors.proposal.adapter_digest,
            actors.evaluation.adapter_digest,
        ),
        "nesting_rule": DEMO_NESTING_RULE,
        "scheduler_model": DEMO_SCHEDULER,
        "model_manifest": demo_model_manifest(),
    }


def demo_event_id(sequence: int, run_id: str) -> str:
    return f"{run_id}:event-{sequence:04d}"


def demo_events(run_id: str = DEMO_RUN_ID) -> tuple[tuple[Event, dict[str, bytes]], ...]:
    """The full demo event plan: ``(event, blobs)`` pairs in append order.

    Blobs are receipts stored with the event that references them. The plan is
    pure data — :func:`build_demo_bundle` appends it to a real bundle.
    """
    actors = demo_actors()
    short, medium, control = demo_candidates()
    short_id, medium_id, control_id = (
        short.candidate_id,
        medium.candidate_id,
        control.candidate_id,
    )
    plan: list[tuple[Event, dict[str, bytes]]] = []

    def push(
        sequence: int,
        event_type: str,
        phase: str,
        payload: Mapping[str, Any],
        *,
        parents: Sequence[str] = (),
        blobs: Mapping[str, bytes] | None = None,
    ) -> Event:
        event = build_event(
            event_id=demo_event_id(sequence, run_id),
            sequence=sequence,
            event_type=event_type,
            phase=phase,
            payload=dict(payload),
            parent_event_ids=tuple(parents),
            blob_digests=tuple((blobs or {}).keys()),
        )
        plan.append((event, blobs or {}))
        return event

    # 0: run_started is appended by RunBundle.create; the plan starts at 1.
    push(1, "budget_reserved", "discovery", {
        "reservationId": "rsv-search",
        "account": "W_search",
        "stage": "discovery",
    }, parents=[f"{run_id}:run-started"])

    proposal_request_id = "req-proposal-1"
    receipt = proposal_receipt(
        request_id=proposal_request_id,
        adapter=actors.proposal,
        candidates=(short, medium, control),
        resource_use={"fixture": True},
    )
    receipt_blob = canonical_bytes(receipt.to_canonical())
    proposal_blob_digest = digest(receipt.to_canonical())
    push(2, "proposal_succeeded", "discovery", {
        "requestId": proposal_request_id,
        "reservationId": "rsv-search",
        "candidateIds": [short_id, medium_id, control_id],
    }, parents=[demo_event_id(1, run_id)], blobs={proposal_blob_digest: receipt_blob})

    push(3, "budget_committed", "discovery", {
        "reservationId": "rsv-search",
        "account": "W_search",
        "stage": "discovery",
    }, parents=[demo_event_id(2, run_id)])

    archive: dict[str, Any] = {}
    for sequence, candidate, parent in ((4, short, 2), (5, medium, 4), (6, control, 5)):
        canonical = candidate.to_canonical()
        archive[candidate.candidate_id] = canonical
        archive_digest = digest(
            {"schemaVersion": ARCHIVE_VIEW_SCHEMA_VERSION, "candidates": dict(archive)}
        )
        push(sequence, "archive_changed", "discovery", {
            "candidateId": candidate.candidate_id,
            "archiveDigest": archive_digest,
            "coordinateCost": demo_coordinate_cost(candidate).to_canonical(),
        }, parents=[demo_event_id(parent, run_id)])

    push(7, "budget_reserved", "discovery", {
        "reservationId": "rsv-eval-discovery",
        "account": "T_dec",
        "stage": "discovery",
    }, parents=[demo_event_id(6, run_id)])

    evaluator = DemoEvaluationAdapter(actors.evaluation)
    for sequence, candidate, parent in ((8, short, 7), (10, medium, 7)):
        request_id = f"req-eval-{candidate.candidate_id[:8]}"
        request = EvaluationRequest(
            request_id=request_id,
            reservation_id="rsv-eval-discovery",
            adapter=actors.evaluation,
            candidate=candidate,
        )
        eval_receipt = evaluator.evaluate(request)
        push(sequence, "evaluation_started", "discovery", {
            "requestId": request_id,
            "reservationId": "rsv-eval-discovery",
            "candidateId": candidate.candidate_id,
        }, parents=[demo_event_id(parent, run_id)])
        eval_blob_digest = digest(eval_receipt.to_canonical())
        push(sequence + 1, "evaluation_completed", "discovery", {
            "requestId": request_id,
            "reservationId": "rsv-eval-discovery",
            "candidateId": candidate.candidate_id,
        }, parents=[demo_event_id(sequence, run_id)],
             blobs={eval_blob_digest: canonical_bytes(eval_receipt.to_canonical())})

    push(12, "budget_committed", "discovery", {
        "reservationId": "rsv-eval-discovery",
        "account": "T_dec",
        "stage": "discovery",
    }, parents=[demo_event_id(11, run_id)])

    push(13, "candidate_promoted", "discovery", {
        "candidateId": medium_id,
    }, parents=[demo_event_id(11, run_id)])
    push(14, "candidate_rejected", "discovery", {
        "candidateId": short_id,
        "reason": "dominated",
    }, parents=[demo_event_id(11, run_id)])

    # Failure paths are first-class evidence and stay in the source archive:
    # a failed evaluation, a failed proposal, and a failed budget settlement.
    push(15, "budget_reserved", "discovery", {
        "reservationId": "rsv-eval-fail",
        "account": "T_dec",
        "stage": "discovery",
    }, parents=[demo_event_id(14, run_id)])
    failed_eval_request_id = f"req-eval-fail-{short_id[:8]}"
    push(16, "evaluation_started", "discovery", {
        "requestId": failed_eval_request_id,
        "reservationId": "rsv-eval-fail",
        "candidateId": short_id,
    }, parents=[demo_event_id(15, run_id)])
    push(17, "evaluation_failed", "discovery", {
        "requestId": failed_eval_request_id,
        "reservationId": "rsv-eval-fail",
        "candidateId": short_id,
        "reason": "fixture-simulated-failure",
    }, parents=[demo_event_id(16, run_id)])
    push(18, "budget_committed", "discovery", {
        "reservationId": "rsv-eval-fail",
        "account": "T_dec",
        "stage": "discovery",
    }, parents=[demo_event_id(17, run_id)])

    push(19, "budget_reserved", "discovery", {
        "reservationId": "rsv-search-2",
        "account": "W_search",
        "stage": "discovery",
    }, parents=[demo_event_id(18, run_id)])
    push(20, "proposal_failed", "discovery", {
        "requestId": "req-proposal-2",
        "reservationId": "rsv-search-2",
        "reason": "malformed_proposal",
    }, parents=[demo_event_id(19, run_id)])
    push(21, "budget_failed", "discovery", {
        "reservationId": "rsv-search-2",
        "account": "W_search",
        "stage": "discovery",
        "reason": "proposal call failed",
    }, parents=[demo_event_id(20, run_id)])

    freeze_archive_digest = digest(
        {"schemaVersion": ARCHIVE_VIEW_SCHEMA_VERSION, "candidates": dict(archive)}
    )
    push(22, "search_frozen", "freeze", {
        "archiveDigest": freeze_archive_digest,
        "shortlistCandidateIds": [medium_id],
        "selectionRule": DEMO_SELECTION_RULE,
        "discoveryContextDigest": digest({"fixture": "discovery-context"}),
    }, parents=[demo_event_id(21, run_id)])

    push(23, "budget_reserved", "confirmation", {
        "reservationId": "rsv-eval-confirm",
        "account": "T_dec",
        "stage": "confirmation",
    }, parents=[demo_event_id(22, run_id)])

    confirm_request_id = f"req-eval-confirm-{medium_id[:8]}"
    confirm_request = EvaluationRequest(
        request_id=confirm_request_id,
        reservation_id="rsv-eval-confirm",
        adapter=actors.evaluation,
        candidate=medium,
    )
    confirm_receipt = evaluator.evaluate(confirm_request)
    push(24, "evaluation_started", "confirmation", {
        "requestId": confirm_request_id,
        "reservationId": "rsv-eval-confirm",
        "candidateId": medium_id,
    }, parents=[demo_event_id(23, run_id)])
    confirm_blob_digest = digest(confirm_receipt.to_canonical())
    push(25, "evaluation_completed", "confirmation", {
        "requestId": confirm_request_id,
        "reservationId": "rsv-eval-confirm",
        "candidateId": medium_id,
    }, parents=[demo_event_id(24, run_id)],
         blobs={confirm_blob_digest: canonical_bytes(confirm_receipt.to_canonical())})

    push(26, "budget_committed", "confirmation", {
        "reservationId": "rsv-eval-confirm",
        "account": "T_dec",
        "stage": "confirmation",
    }, parents=[demo_event_id(25, run_id)])

    push(27, "confirmation_started", "confirmation", {
        "confirmationContextDigest": digest({"fixture": "confirmation-context"}),
        "seed": "demo-seed-42",
    }, parents=[demo_event_id(22, run_id)])
    push(28, "confirmation_completed", "confirmation", {
        "outcome": "confirmed",
        "candidateId": medium_id,
        "replays": 1,
        "tests": 1,
    }, parents=[demo_event_id(27, run_id)])

    return tuple(plan)


DEMO_PREFIX_SEQUENCES = tuple(range(1, 15))
"""Events 1..14 (proposal through rejection) form the crash-resume prefix."""


def build_demo_bundle(root: Path, *, run_id: str = DEMO_RUN_ID) -> Path:
    """Build the complete demo bundle from scratch; returns the bundle root."""
    config = demo_bundle_config(run_id=run_id)
    bundle = RunBundle.create(root, **config)
    for event, blobs in demo_events(run_id=run_id):
        bundle.append_event(event, blobs=blobs)
    bundle.close(status="completed")
    materialize(root)
    return root


def build_demo_bundle_interrupted(root: Path, *, run_id: str = DEMO_RUN_ID) -> RunBundle:
    """Build the demo bundle up to the crash point (before ``search_frozen``)."""
    config = demo_bundle_config(run_id=run_id)
    bundle = RunBundle.create(root, **config)
    for event, blobs in demo_events(run_id=run_id):
        if event.sequence in DEMO_PREFIX_SEQUENCES:
            bundle.append_event(event, blobs=blobs)
    return bundle


def resume_demo_bundle(root: Path, *, run_id: str = DEMO_RUN_ID) -> Path:
    """Resume an interrupted demo bundle through the freeze and confirmation."""
    bundle = RunBundle.open_for_append(root)
    for event, blobs in demo_events(run_id=run_id):
        if event.sequence not in DEMO_PREFIX_SEQUENCES:
            bundle.append_event(event, blobs=blobs)
    bundle.close(status="completed")
    materialize(root)
    return root
