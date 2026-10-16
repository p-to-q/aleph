"""Repository-authored smoke target and frozen plan for the pinned MLX canary (PR C).

The canary is the first real-model run of the engine: a pinned local MLX
checkpoint evaluates deterministic operator candidates against a
repository-authored smoke target, and the resulting bundle must verify from
disk. The target is deliberately small and not a public benchmark item: the
numeric answer "42" to two word-spelled arithmetic prompts. Success means the
artifact verifies, not that the model found a strong coordinate.

This module is pure standard library: the MLX runtime is reached only through
``search.engine.canary`` (the opt-in runner) and ``adapters/mlx.py``.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from ..canonical import digest
from ..confirmation import ConfirmationSpec
from ..contracts import (
    AdapterIdentity,
    Candidate,
    Message,
    Placement,
    ProposalReceipt,
    ProposalRequest,
    adapter_identity,
    proposal_receipt,
)
from ..hybrid_pareto import FrozenConfig
from ..operators import DeleteSpec, ReferenceSpec, RewriteSpec

CANARY_RUN_ID = "aleph-mlx-canary-001"
CANARY_TARGET = "42"
CANARY_TARGET_LABEL = "aleph-mlx-canary smoke target: the number forty-two"
CANARY_METRICS = ("fit", "stability", "compression", "leakage")
CANARY_SCHEDULER_MODEL = "hybrid-pareto-v0"
CANARY_NESTING_RULE = "t_dec_nested_in_w_search"
CANARY_MAX_NEW_TOKENS = 64
CANARY_SAMPLES = 2
CANARY_TOKENIZER_VIEW = "aleph-mlx-canary/qwen3-tokenizer/0.1.0"
CANARY_SCAFFOLD_ID = "aleph-mlx-canary/qwen3-chat/0.1.0"
CANARY_TEMPLATE_VERSION = "qwen3-chat-template+no-thinking+add-generation-prompt/v1"
CANARY_SEED_A = ("Compute twenty-one plus twenty-one.", "Reply with only the digits.")
CANARY_SEED_B = ("Find the integer between forty-one and forty-three.", "Reply with only that number.")
CANARY_REFERENCE_TEXT = "Reply with only the digits."
CANARY_DISCOVERY_CONTEXT = "aleph-mlx-canary/discovery/v1"
CANARY_CONFIRMATION_CONTEXT = "aleph-mlx-canary/confirmation/v1"
CANARY_CONFIRMATION_SEED = "aleph-mlx-canary-seed-v1"
CANARY_RNG_SEED = 7


def canary_target_digest() -> str:
    """Declared digest binding of the smoke target text."""
    return digest(CANARY_TARGET)


def canary_decoding() -> dict[str, Any]:
    """The pinned decoding declaration carried into the manifest and receipt."""
    return {
        "temperature": 0.0,
        "maxNewTokens": CANARY_MAX_NEW_TOKENS,
        "samplesPerEvaluation": CANARY_SAMPLES,
        "enableThinking": False,
        "addGenerationPrompt": True,
    }


def canary_scaffold_descriptor(*, tokenizer_digest: str, chat_template_digest: str) -> dict[str, Any]:
    """Descriptor whose digest binds candidate identity to the pinned template."""
    return {
        "scaffoldId": CANARY_SCAFFOLD_ID,
        "renderedTemplateVersion": CANARY_TEMPLATE_VERSION,
        "tokenizerDigest": tokenizer_digest,
        "chatTemplateDigest": chat_template_digest,
        "addGenerationPrompt": True,
        "enableThinking": False,
    }


def canary_placement(*, tokenizer_digest: str, chat_template_digest: str) -> Placement:
    """The frozen placement of every canary candidate."""
    descriptor = canary_scaffold_descriptor(
        tokenizer_digest=tokenizer_digest, chat_template_digest=chat_template_digest
    )
    return Placement(
        scaffold_id=CANARY_SCAFFOLD_ID,
        scaffold_digest=digest(descriptor),
        prompt_position="messages[*]",
        rendered_template_version=CANARY_TEMPLATE_VERSION,
    )


def canary_seeds(placement: Placement) -> tuple[Candidate, Candidate, Candidate]:
    """Two ordinary word-spelled seeds plus the explicit-reconstruction control."""
    seed_a = Candidate(
        messages=tuple(Message(role="user", content=text) for text in CANARY_SEED_A),
        placement=placement,
        proposal_mode="seed",
    )
    seed_b = Candidate(
        messages=tuple(Message(role="user", content=text) for text in CANARY_SEED_B),
        placement=placement,
        proposal_mode="seed",
    )
    control = Candidate(
        messages=(Message(role="user", content=CANARY_TARGET),),
        placement=placement,
        proposal_mode="reference",
        role="explicit_reconstruction",
    )
    return seed_a, seed_b, control


def canary_operator_specs() -> tuple[Any, ...]:
    """The frozen deterministic operators of the canary run."""
    return (
        RewriteSpec(index=0, transform="lowercase"),
        DeleteSpec(index=1),
        ReferenceSpec(
            source_messages=(Message(role="user", content=CANARY_REFERENCE_TEXT),),
            at="append",
        ),
    )


def canary_operator_weights() -> tuple[tuple[str, float], ...]:
    return (("delete", 1.0), ("reference", 1.0), ("rewrite", 1.0))


def canary_config(placement: Placement) -> FrozenConfig:
    """The frozen hybrid search plan of the canary."""
    return FrozenConfig(
        seeds=canary_seeds(placement),
        operator_specs=canary_operator_specs(),
        operator_weights=canary_operator_weights(),
        exploration_share=0.5,
        exploit_top_k=1,
        parent_rule="uniform_promoted",
        metric="fit",
        promote_threshold=0.5,
        max_proposal_rounds=2,
        max_promoted=3,
        stop_rule="rounds",
        racing_rule="evaluate_all",
        retries=1,
        rng_seed=CANARY_RNG_SEED,
        control_arm=True,
        confirmation_checks=(("replays", 1), ("tests", 1)),
    )


def canary_confirmation() -> ConfirmationSpec:
    """The frozen protected-confirmation plan of the canary."""
    return ConfirmationSpec(
        discovery_context_digest=digest({"canary": CANARY_DISCOVERY_CONTEXT}),
        confirmation_context_digest=digest({"canary": CANARY_CONFIRMATION_CONTEXT}),
        seed=CANARY_CONFIRMATION_SEED,
        metric="fit",
        threshold=0.5,
        samples=CANARY_SAMPLES,
        confirm_fraction=1.0,
        reject_fraction=0.5,
    )


def canary_proposal_identity() -> AdapterIdentity:
    """The proposal arm: deterministic operators only, no model access."""
    return adapter_identity(
        "aleph-mlx-canary/operator-echo",
        "0.1.0",
        "proposal",
        capabilities=("deterministic-operators",),
        manifest={"modelAccess": "none", "operators": ["delete", "reference", "rewrite"]},
    )


def canary_evaluation_identity(
    *,
    model: str,
    revision: str,
    decoding: Mapping[str, Any],
    observation_mode: str,
    runtime: Mapping[str, Any],
) -> AdapterIdentity:
    """The evaluation arm: the pinned local MLX checkpoint."""
    return adapter_identity(
        "aleph-mlx-canary/pinned-evaluator",
        "0.1.0",
        "evaluation",
        capabilities=("local-generation", "greedy-decoding", "exact-tokenizer-accounting"),
        manifest={
            "model": model,
            "revision": revision,
            "decoding": dict(decoding),
            "observationMode": observation_mode,
            "runtime": dict(runtime),
        },
    )


def canary_manifest(
    *,
    model: str,
    revision: str,
    decoding: Mapping[str, Any],
    observation_mode: str,
    runtime: Mapping[str, Any],
    resolved_files: Sequence[Mapping[str, Any]],
    tokenizer_view: str,
    tokenizer_digest: str,
    chat_template_digest: str,
    git_commit: str,
    mode: str = "unrestricted",
) -> dict[str, Any]:
    """The run's declared ``M_desc`` manifest (export-required fields included)."""
    return {
        "model": model,
        "revision": revision,
        "mode": mode,
        "observationMode": observation_mode,
        "decoding": dict(decoding),
        "tokenizerView": tokenizer_view,
        "tokenizerDigest": tokenizer_digest,
        "chatTemplateDigest": chat_template_digest,
        "resolvedFiles": [dict(item) for item in resolved_files],
        "runtime": dict(runtime),
        "gitCommit": git_commit,
    }


class CanaryOperatorProposalAdapter:
    """Echoes the candidates declared in the request context; no model calls."""

    def __init__(self, identity: AdapterIdentity) -> None:
        self._identity = identity

    @property
    def identity(self) -> AdapterIdentity:
        return self._identity

    def propose(self, request: ProposalRequest) -> ProposalReceipt:
        from ..contracts import candidate_from_canonical
        from ..hybrid_pareto import unfreeze_projection

        context = dict(request.context)
        raw = context.get("operatorProducts", context.get("seeds", ()))
        candidates = tuple(
            candidate_from_canonical(unfreeze_projection(item)) for item in raw
        )
        return proposal_receipt(
            request_id=request.request_id,
            adapter=self._identity,
            candidates=candidates,
            resource_use={"echoedCandidates": len(candidates)},
        )
