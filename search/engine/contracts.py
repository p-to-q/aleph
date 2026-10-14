"""Narrow adapter contracts and candidate identity for the Aleph engine.

The kernel enforces one structural rule: proposers create candidates and never
see evaluator scores; evaluators receive frozen canonical candidates and can
neither create nor mutate them. Both roles are reached only through typed
request/receipt objects, and both are charged against a prior budget
reservation (see ``ledger.py``).

Every request and receipt has a strict canonical parser
(``*_from_canonical``). The parsers reject unknown fields and verify declared
identifiers, so a bundle that carries a tampered or hand-edited receipt fails
closed instead of being silently reinterpreted.

Pure standard library. No MLX import, here or anywhere in the PR A kernel.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Protocol, Sequence, runtime_checkable

from .canonical import canonicalize, digest, is_digest, normalize_text

CONTRACT_SCHEMA_VERSION = "aleph-engine-contracts/0.1.0"

CANDIDATE_IDENTITY_VERSION = "aleph-candidate-identity/0.1.0"
"""Identity rule version. Any change to the covered field set is breaking."""

PROPOSAL_MODES = ("delete", "rewrite", "repair", "reference", "seed")
"""Frozen proposal modes. PR B adds operators behind these same mode labels."""

CANDIDATE_ROLES = ("candidate", "explicit_reconstruction")
"""``explicit_reconstruction`` is the only tagged target-copy control.

An ordinary ``candidate`` may never be produced by a target-copy fallback. A
copy is admissible only when it is explicitly declared as this control role,
which keeps it out of the ordinary frontier.
"""

MESSAGE_ROLES = ("system", "user", "assistant", "tool")


class ContractViolation(ValueError):
    """Raised when an adapter boundary or candidate invariant is broken."""


def _reject_unknown_fields(payload: Mapping[str, Any], allowed: set[str], label: str) -> None:
    """Fail closed on fields that the typed contract does not cover."""
    unknown = set(payload) - allowed
    if unknown:
        raise ContractViolation(f"{label} has unknown fields: {sorted(unknown)}")


def _require_non_empty_str(value: Any, label: str) -> None:
    if not isinstance(value, str) or not value:
        raise ContractViolation(f"{label} must be a non-empty str")


def _require_key(payload: Mapping[str, Any], key: str, label: str) -> Any:
    """Return ``payload[key]`` or fail closed with a contract violation."""
    if key not in payload:
        raise ContractViolation(f"{label} is missing required field {key!r}")
    return payload[key]


def _frozen_mapping(value: Mapping[str, Any] | None, label: str) -> tuple[tuple[str, Any], ...]:
    """Return a hashable, canonically ordered projection of ``value``."""
    if value is None:
        return ()
    if not isinstance(value, Mapping):
        raise ContractViolation(f"{label} must be a mapping")
    canonical = canonicalize(value)
    return tuple((key, canonical_json_safe(canonical[key])) for key in sorted(canonical))


def canonical_json_safe(value: Any) -> Any:
    """Return a hashable projection of an already-canonical value."""
    if isinstance(value, Mapping):
        return tuple((key, canonical_json_safe(value[key])) for key in sorted(value))
    if isinstance(value, list):
        return tuple(canonical_json_safe(item) for item in value)
    return value


@dataclass(frozen=True)
class Message:
    """One canonical role/content message in a candidate coordinate."""

    role: str
    content: str

    def __post_init__(self) -> None:
        if self.role not in MESSAGE_ROLES:
            raise ContractViolation(f"unknown message role: {self.role!r}")
        if not isinstance(self.content, str):
            raise ContractViolation("message content must be a str")
        object.__setattr__(self, "content", normalize_text(self.content))

    def to_canonical(self) -> dict[str, Any]:
        return {"role": self.role, "content": self.content}


def message_from_canonical(payload: Mapping[str, Any]) -> Message:
    """Rebuild a ``Message`` from its canonical form, rejecting unknown fields."""
    if not isinstance(payload, Mapping):
        raise ContractViolation("message payload must be a mapping")
    _reject_unknown_fields(payload, {"role", "content"}, "message")
    return Message(
        role=_require_key(payload, "role", "message"),
        content=_require_key(payload, "content", "message"),
    )


@dataclass(frozen=True)
class Placement:
    """Frozen prompt placement and scaffold identity.

    The scaffold is identified by digest rather than inlined text so a rendered
    chat template can be pinned without the identity rule depending on how the
    template happens to be stored.
    """

    scaffold_id: str
    scaffold_digest: str
    prompt_position: str
    rendered_template_version: str

    def __post_init__(self) -> None:
        for name in (
            "scaffold_id",
            "scaffold_digest",
            "prompt_position",
            "rendered_template_version",
        ):
            value = getattr(self, name)
            _require_non_empty_str(value, f"placement.{name}")
        if not is_digest(self.scaffold_digest):
            raise ContractViolation("placement.scaffoldDigest must be a well-formed digest")

    def to_canonical(self) -> dict[str, Any]:
        return {
            "scaffoldId": self.scaffold_id,
            "scaffoldDigest": self.scaffold_digest,
            "promptPosition": self.prompt_position,
            "renderedTemplateVersion": self.rendered_template_version,
        }


def placement_from_canonical(payload: Mapping[str, Any]) -> Placement:
    """Rebuild a ``Placement`` from its canonical form, rejecting unknown fields."""
    if not isinstance(payload, Mapping):
        raise ContractViolation("placement payload must be a mapping")
    _reject_unknown_fields(
        payload,
        {"scaffoldId", "scaffoldDigest", "promptPosition", "renderedTemplateVersion"},
        "placement",
    )
    return Placement(
        scaffold_id=_require_key(payload, "scaffoldId", "placement"),
        scaffold_digest=_require_key(payload, "scaffoldDigest", "placement"),
        prompt_position=_require_key(payload, "promptPosition", "placement"),
        rendered_template_version=_require_key(payload, "renderedTemplateVersion", "placement"),
    )


@dataclass(frozen=True)
class Candidate:
    """An immutable proposed coordinate.

    ``candidate_id`` is derived, never supplied. It is a SHA-256 digest over the
    canonical role/content structure, placement/scaffold, proposal mode, and
    candidate role. Scores, timestamps, parent links, and array positions are
    excluded on purpose: the same coordinate proposed twice, by different
    operators or in a different order, has one identity, so duplicates are
    detectable rather than silently distinct.
    """

    messages: tuple[Message, ...]
    placement: Placement
    proposal_mode: str
    role: str = "candidate"

    def __post_init__(self) -> None:
        if not isinstance(self.messages, tuple) or not self.messages:
            raise ContractViolation("candidate requires a non-empty tuple of messages")
        if not all(isinstance(message, Message) for message in self.messages):
            raise ContractViolation("candidate messages must be Message instances")
        if self.proposal_mode not in PROPOSAL_MODES:
            raise ContractViolation(f"unknown proposal mode: {self.proposal_mode!r}")
        if self.role not in CANDIDATE_ROLES:
            raise ContractViolation(f"unknown candidate role: {self.role!r}")

    @property
    def identity_payload(self) -> dict[str, Any]:
        return {
            "identityVersion": CANDIDATE_IDENTITY_VERSION,
            "messages": [message.to_canonical() for message in self.messages],
            "placement": self.placement.to_canonical(),
            "proposalMode": self.proposal_mode,
            "candidateRole": self.role,
        }

    @property
    def candidate_id(self) -> str:
        return digest(self.identity_payload)

    def to_canonical(self) -> dict[str, Any]:
        payload = dict(self.identity_payload)
        payload["candidateId"] = self.candidate_id
        return payload


def candidate_from_canonical(payload: Mapping[str, Any]) -> Candidate:
    """Rebuild a ``Candidate`` from its canonical form, verifying its identity."""
    if not isinstance(payload, Mapping):
        raise ContractViolation("candidate payload must be a mapping")
    _reject_unknown_fields(
        payload,
        {"identityVersion", "messages", "placement", "proposalMode", "candidateRole", "candidateId"},
        "candidate",
    )
    messages = payload.get("messages")
    if not isinstance(messages, list) or not messages:
        raise ContractViolation("candidate messages must be a non-empty list")
    candidate = Candidate(
        messages=tuple(message_from_canonical(item) for item in messages),
        placement=placement_from_canonical(_require_key(payload, "placement", "candidate")),
        proposal_mode=_require_key(payload, "proposalMode", "candidate"),
        role=payload.get("candidateRole", "candidate"),
    )
    declared = payload.get("candidateId")
    if declared is not None and declared != candidate.candidate_id:
        raise ContractViolation(
            f"candidate id mismatch: declared {declared!r}, derived {candidate.candidate_id!r}"
        )
    declared_version = payload.get("identityVersion")
    if declared_version is not None and declared_version != CANDIDATE_IDENTITY_VERSION:
        raise ContractViolation(f"unsupported candidate identity version: {declared_version!r}")
    return candidate


@dataclass(frozen=True)
class AdapterIdentity:
    """Immutable adapter identity, revision, and declared capabilities."""

    adapter_id: str
    revision: str
    role: str
    capabilities: tuple[str, ...] = ()
    manifest: tuple[tuple[str, Any], ...] = ()

    def __post_init__(self) -> None:
        if self.role not in ("proposal", "evaluation"):
            raise ContractViolation(f"adapter role must be proposal or evaluation: {self.role!r}")
        for name in ("adapter_id", "revision"):
            value = getattr(self, name)
            _require_non_empty_str(value, f"adapter {name}")
        if not isinstance(self.capabilities, tuple):
            raise ContractViolation("adapter capabilities must be a tuple")
        object.__setattr__(self, "capabilities", tuple(sorted(set(self.capabilities))))

    def to_canonical(self) -> dict[str, Any]:
        return {
            "adapterId": self.adapter_id,
            "revision": self.revision,
            "role": self.role,
            "capabilities": list(self.capabilities),
            "manifest": {key: _unfreeze(value) for key, value in self.manifest},
        }

    @property
    def adapter_digest(self) -> str:
        return digest(self.to_canonical())


def _unfreeze(value: Any) -> Any:
    if isinstance(value, tuple):
        if value and all(
            isinstance(item, tuple) and len(item) == 2 and isinstance(item[0], str)
            for item in value
        ):
            return {key: _unfreeze(item) for key, item in value}
        return [_unfreeze(item) for item in value]
    return value


def adapter_identity(
    adapter_id: str,
    revision: str,
    role: str,
    *,
    capabilities: Sequence[str] = (),
    manifest: Mapping[str, Any] | None = None,
) -> AdapterIdentity:
    """Build an ``AdapterIdentity`` with a frozen manifest projection."""
    return AdapterIdentity(
        adapter_id=adapter_id,
        revision=revision,
        role=role,
        capabilities=tuple(capabilities),
        manifest=_frozen_mapping(manifest, "adapter manifest"),
    )


def adapter_identity_from_canonical(payload: Mapping[str, Any]) -> AdapterIdentity:
    """Rebuild an ``AdapterIdentity`` from its canonical form, rejecting unknown fields."""
    if not isinstance(payload, Mapping):
        raise ContractViolation("adapter identity payload must be a mapping")
    _reject_unknown_fields(
        payload, {"adapterId", "revision", "role", "capabilities", "manifest"}, "adapter identity"
    )
    capabilities = payload.get("capabilities", [])
    if not isinstance(capabilities, list) or not all(
        isinstance(item, str) for item in capabilities
    ):
        raise ContractViolation("adapter capabilities must be a list of str")
    manifest = payload.get("manifest", {})
    if not isinstance(manifest, Mapping):
        raise ContractViolation("adapter manifest must be a mapping")
    return adapter_identity(
        adapter_id=_require_key(payload, "adapterId", "adapter identity"),
        revision=_require_key(payload, "revision", "adapter identity"),
        role=_require_key(payload, "role", "adapter identity"),
        capabilities=capabilities,
        manifest=manifest,
    )


@dataclass(frozen=True)
class ProposalRequest:
    """Typed proposal request.

    A proposer receives the target, frozen context, parent candidate ids, and
    its reservation. It does not receive evaluator scores or metric vectors, so
    the structural separation does not depend on proposer good behaviour.
    """

    request_id: str
    reservation_id: str
    adapter: AdapterIdentity
    proposal_mode: str
    target_digest: str
    context: tuple[tuple[str, Any], ...] = ()
    parent_candidate_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _require_non_empty_str(self.request_id, "proposal request id")
        _require_non_empty_str(self.reservation_id, "proposal reservation id")
        if self.adapter.role != "proposal":
            raise ContractViolation("ProposalRequest requires a proposal adapter")
        if self.proposal_mode not in PROPOSAL_MODES:
            raise ContractViolation(f"unknown proposal mode: {self.proposal_mode!r}")
        if not is_digest(self.target_digest):
            raise ContractViolation("proposal target digest must be a well-formed digest")
        if not isinstance(self.parent_candidate_ids, tuple):
            raise ContractViolation("parent_candidate_ids must be a tuple")

    def to_canonical(self) -> dict[str, Any]:
        return {
            "requestId": self.request_id,
            "reservationId": self.reservation_id,
            "adapter": self.adapter.to_canonical(),
            "proposalMode": self.proposal_mode,
            "targetDigest": self.target_digest,
            "context": {key: _unfreeze(value) for key, value in self.context},
            "parentCandidateIds": list(self.parent_candidate_ids),
        }


def proposal_request_from_canonical(payload: Mapping[str, Any]) -> ProposalRequest:
    """Rebuild a ``ProposalRequest`` from its canonical form, rejecting unknown fields."""
    if not isinstance(payload, Mapping):
        raise ContractViolation("proposal request payload must be a mapping")
    _reject_unknown_fields(
        payload,
        {"requestId", "reservationId", "adapter", "proposalMode", "targetDigest", "context", "parentCandidateIds"},
        "proposal request",
    )
    context = payload.get("context", {})
    if not isinstance(context, Mapping):
        raise ContractViolation("proposal request context must be a mapping")
    parent_ids = payload.get("parentCandidateIds", [])
    if not isinstance(parent_ids, list):
        raise ContractViolation("parentCandidateIds must be a list")
    return ProposalRequest(
        request_id=_require_key(payload, "requestId", "proposal request"),
        reservation_id=_require_key(payload, "reservationId", "proposal request"),
        adapter=adapter_identity_from_canonical(_require_key(payload, "adapter", "proposal request")),
        proposal_mode=_require_key(payload, "proposalMode", "proposal request"),
        target_digest=_require_key(payload, "targetDigest", "proposal request"),
        context=_frozen_mapping(context, "proposal context"),
        parent_candidate_ids=tuple(parent_ids),
    )


@dataclass(frozen=True)
class ProposalReceipt:
    """Typed proposal receipt: candidates plus proposal-side resource use only.

    ``resource_use`` must not carry evaluator scores. An empty candidate tuple
    is legal and is recorded as a typed proposal failure by the caller; no
    fallback may substitute a target slice.
    """

    request_id: str
    adapter: AdapterIdentity
    candidates: tuple[Candidate, ...]
    resource_use: tuple[tuple[str, Any], ...] = ()

    _FORBIDDEN_RESOURCE_KEYS = frozenset(
        {"score", "scores", "fit", "metric", "metrics", "metricVector", "distortion", "reward"}
    )

    def __post_init__(self) -> None:
        _require_non_empty_str(self.request_id, "proposal receipt request id")
        if self.adapter.role != "proposal":
            raise ContractViolation("ProposalReceipt requires a proposal adapter")
        if not isinstance(self.candidates, tuple):
            raise ContractViolation("candidates must be a tuple")
        for candidate in self.candidates:
            if not isinstance(candidate, Candidate):
                raise ContractViolation("proposal receipts carry Candidate instances")
        for key, _ in self.resource_use:
            if key in self._FORBIDDEN_RESOURCE_KEYS:
                raise ContractViolation(
                    f"proposal receipts may not carry evaluator scores: {key!r}"
                )

    def to_canonical(self) -> dict[str, Any]:
        return {
            "requestId": self.request_id,
            "adapter": self.adapter.to_canonical(),
            "candidates": [candidate.to_canonical() for candidate in self.candidates],
            "resourceUse": {key: _unfreeze(value) for key, value in self.resource_use},
        }


def proposal_receipt_from_canonical(payload: Mapping[str, Any]) -> ProposalReceipt:
    """Rebuild a ``ProposalReceipt`` from its canonical form, rejecting unknown fields.

    Receipts are typed evidence: candidate items must carry their derived
    ``candidateId``, which is verified against the candidate structure.
    """
    if not isinstance(payload, Mapping):
        raise ContractViolation("proposal receipt payload must be a mapping")
    _reject_unknown_fields(
        payload, {"requestId", "adapter", "candidates", "resourceUse"}, "proposal receipt"
    )
    candidates = payload.get("candidates")
    if not isinstance(candidates, list):
        raise ContractViolation("proposal receipt candidates must be a list")
    parsed: list[Candidate] = []
    for item in candidates:
        if not isinstance(item, Mapping) or "candidateId" not in item:
            raise ContractViolation("proposal receipt candidate items must carry candidateId")
        parsed.append(candidate_from_canonical(item))
    resource_use = payload.get("resourceUse", {})
    if not isinstance(resource_use, Mapping):
        raise ContractViolation("proposal receipt resourceUse must be a mapping")
    return ProposalReceipt(
        request_id=_require_key(payload, "requestId", "proposal receipt"),
        adapter=adapter_identity_from_canonical(_require_key(payload, "adapter", "proposal receipt")),
        candidates=tuple(parsed),
        resource_use=_frozen_mapping(resource_use, "proposal resource use"),
    )


@dataclass(frozen=True)
class EvaluationRequest:
    """Typed evaluation request over one frozen canonical candidate."""

    request_id: str
    reservation_id: str
    adapter: AdapterIdentity
    candidate: Candidate
    frozen_context: tuple[tuple[str, Any], ...] = ()

    def __post_init__(self) -> None:
        _require_non_empty_str(self.request_id, "evaluation request id")
        _require_non_empty_str(self.reservation_id, "evaluation reservation id")
        if self.adapter.role != "evaluation":
            raise ContractViolation("EvaluationRequest requires an evaluation adapter")
        if not isinstance(self.candidate, Candidate):
            raise ContractViolation("evaluation requires a Candidate instance")

    def to_canonical(self) -> dict[str, Any]:
        return {
            "requestId": self.request_id,
            "reservationId": self.reservation_id,
            "adapter": self.adapter.to_canonical(),
            "candidateId": self.candidate.candidate_id,
            "frozenContext": {key: _unfreeze(value) for key, value in self.frozen_context},
        }


@dataclass(frozen=True)
class EvaluationReceipt:
    """Typed evaluation receipt.

    The receipt references a candidate by id and never carries a candidate
    structure, so an evaluator cannot create or mutate a coordinate. Metrics are
    a typed vector: an unknown metric name is a failure, never a silent
    fallback.
    """

    request_id: str
    adapter: AdapterIdentity
    candidate_id: str
    metrics: tuple[tuple[str, Any], ...]
    resource_use: tuple[tuple[str, Any], ...] = ()
    outputs: tuple[tuple[str, Any], ...] = ()

    def __post_init__(self) -> None:
        _require_non_empty_str(self.request_id, "evaluation receipt request id")
        if self.adapter.role != "evaluation":
            raise ContractViolation("EvaluationReceipt requires an evaluation adapter")
        if not isinstance(self.candidate_id, str) or not self.candidate_id:
            raise ContractViolation("evaluation receipt requires a candidate id")
        if not self.metrics:
            raise ContractViolation("evaluation receipt requires a non-empty metric vector")

    def to_canonical(self) -> dict[str, Any]:
        return {
            "requestId": self.request_id,
            "adapter": self.adapter.to_canonical(),
            "candidateId": self.candidate_id,
            "metrics": {key: _unfreeze(value) for key, value in self.metrics},
            "resourceUse": {key: _unfreeze(value) for key, value in self.resource_use},
            "outputs": {key: _unfreeze(value) for key, value in self.outputs},
        }


def evaluation_receipt_from_canonical(payload: Mapping[str, Any]) -> EvaluationReceipt:
    """Rebuild an ``EvaluationReceipt`` from its canonical form, rejecting unknown fields."""
    if not isinstance(payload, Mapping):
        raise ContractViolation("evaluation receipt payload must be a mapping")
    _reject_unknown_fields(
        payload,
        {"requestId", "adapter", "candidateId", "metrics", "resourceUse", "outputs"},
        "evaluation receipt",
    )
    metrics = payload.get("metrics")
    if not isinstance(metrics, Mapping) or not metrics:
        raise ContractViolation("evaluation receipt metrics must be a non-empty mapping")
    resource_use = payload.get("resourceUse", {})
    if not isinstance(resource_use, Mapping):
        raise ContractViolation("evaluation receipt resourceUse must be a mapping")
    outputs = payload.get("outputs", {})
    if not isinstance(outputs, Mapping):
        raise ContractViolation("evaluation receipt outputs must be a mapping")
    return EvaluationReceipt(
        request_id=_require_key(payload, "requestId", "evaluation receipt"),
        adapter=adapter_identity_from_canonical(_require_key(payload, "adapter", "evaluation receipt")),
        candidate_id=_require_key(payload, "candidateId", "evaluation receipt"),
        metrics=_frozen_mapping(metrics, "metrics"),
        resource_use=_frozen_mapping(resource_use, "evaluation resource use"),
        outputs=_frozen_mapping(outputs, "evaluation outputs"),
    )


@runtime_checkable
class ProposalAdapter(Protocol):
    """Narrow proposer boundary: propose candidates, report own resource use."""

    @property
    def identity(self) -> AdapterIdentity: ...

    def propose(self, request: ProposalRequest) -> ProposalReceipt: ...


@runtime_checkable
class EvaluationAdapter(Protocol):
    """Narrow evaluator boundary: score a frozen candidate, create nothing."""

    @property
    def identity(self) -> AdapterIdentity: ...

    def evaluate(self, request: EvaluationRequest) -> EvaluationReceipt: ...


def proposal_request(
    *,
    request_id: str,
    reservation_id: str,
    adapter: AdapterIdentity,
    proposal_mode: str,
    target_digest: str,
    context: Mapping[str, Any] | None = None,
    parent_candidate_ids: Sequence[str] = (),
) -> ProposalRequest:
    return ProposalRequest(
        request_id=request_id,
        reservation_id=reservation_id,
        adapter=adapter,
        proposal_mode=proposal_mode,
        target_digest=target_digest,
        context=_frozen_mapping(context, "proposal context"),
        parent_candidate_ids=tuple(parent_candidate_ids),
    )


def proposal_receipt(
    *,
    request_id: str,
    adapter: AdapterIdentity,
    candidates: Sequence[Candidate],
    resource_use: Mapping[str, Any] | None = None,
) -> ProposalReceipt:
    return ProposalReceipt(
        request_id=request_id,
        adapter=adapter,
        candidates=tuple(candidates),
        resource_use=_frozen_mapping(resource_use, "proposal resource use"),
    )


def evaluation_request(
    *,
    request_id: str,
    reservation_id: str,
    adapter: AdapterIdentity,
    candidate: Candidate,
    frozen_context: Mapping[str, Any] | None = None,
) -> EvaluationRequest:
    return EvaluationRequest(
        request_id=request_id,
        reservation_id=reservation_id,
        adapter=adapter,
        candidate=candidate,
        frozen_context=_frozen_mapping(frozen_context, "frozen context"),
    )


def evaluation_receipt(
    *,
    request_id: str,
    adapter: AdapterIdentity,
    candidate_id: str,
    metrics: Mapping[str, Any],
    resource_use: Mapping[str, Any] | None = None,
    outputs: Mapping[str, Any] | None = None,
) -> EvaluationReceipt:
    return EvaluationReceipt(
        request_id=request_id,
        adapter=adapter,
        candidate_id=candidate_id,
        metrics=_frozen_mapping(metrics, "metrics"),
        resource_use=_frozen_mapping(resource_use, "evaluation resource use"),
        outputs=_frozen_mapping(outputs, "evaluation outputs"),
    )


def self_compression_arm(
    checkpoint_id: str,
    revision: str,
    *,
    capabilities: Sequence[str] = (),
    manifest: Mapping[str, Any] | None = None,
) -> tuple[AdapterIdentity, AdapterIdentity]:
    """Declare one checkpoint in both roles as an explicit ``self_compression`` arm.

    The two identities share the checkpoint and revision but keep distinct
    adapter ids and roles, so calls and costs stay separately accounted even
    when the same weights fill both sides.
    """
    shared = dict(manifest or {})
    shared["arm"] = "self_compression"
    shared["checkpointId"] = checkpoint_id
    return (
        adapter_identity(
            f"{checkpoint_id}#proposal",
            revision,
            "proposal",
            capabilities=capabilities,
            manifest=shared,
        ),
        adapter_identity(
            f"{checkpoint_id}#evaluation",
            revision,
            "evaluation",
            capabilities=capabilities,
            manifest=shared,
        ),
    )
