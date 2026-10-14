"""Minimal hybrid Pareto search scheduler for the Aleph engine (PR B).

The scheduler is a deterministic driver over the PR A kernel. It never
imports MLX, touches the network, or defines the scientific frontier:
acquisition scores (operator weights, exploration share, exploit top-k)
decide *which* deterministic operators run on *which* parents, while
promotion decisions use only the declared metric against the declared
threshold.

Loop: seed proposal -> archive -> evaluate -> promote/reject -> operator
rounds (parent/spec selection under the declared acquisition schedule) ->
freeze -> protected confirmation -> close. Every adapter call goes through
the kernel's typed request/receipt boundary with a prior budget reservation,
and every event is appended to the run bundle, so the whole run is
replayable and independently verifiable.

Determinism: all stochastic choices use ``random.Random(config.rng_seed)`` in
a fixed order — per operator round: exploration coin, parent draw, operator
label draw, applicable-spec draw; retries repeat the label and spec draws
with a fresh parent draw. Two runs with the same config, adapters, and
``run_id`` produce byte-identical bundles.

Pure standard library. No adapter is called during replay; adapters are
reached only through the typed kernel boundary.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from .archive import ARCHIVE_VIEW_SCHEMA_VERSION, RunBundle, materialize
from .canonical import canonical_bytes, digest, is_digest
from .confirmation import ConfirmationSession, ConfirmationSpec
from .contracts import (
    Candidate,
    EvaluationAdapter,
    ProposalAdapter,
    evaluation_request,
    proposal_request,
)
from .events import Event, build_event
from .ledger import CoordinateCost
from .operators import OPERATOR_LABELS, OPERATOR_SPEC_BUILDERS, OperatorFailure, OperatorSpec

HYBRID_SCHEMA_VERSION = "aleph-engine-hybrid-pareto/0.1.0"

SELECTION_RULE = "hybrid-pareto-v0"
"""The declared shortlist selection rule written into ``search_frozen``."""

PARENT_RULES = ("uniform_promoted",)
RACING_RULES = ("evaluate_all", "first_passing")
STOP_RULES = ("rounds", "archive_full", "either")

CHECK_KEYS = ("replays", "tests", "humanChecks", "proofChecks")
"""Admissible post-freeze check counters merged into ``confirmation_completed``."""


class SchedulerError(ValueError):
    """Raised when the frozen configuration or a scheduler invariant is violated."""


def unfreeze_projection(value: Any) -> Any:
    """Rebuild a plain JSON value from a hashable context projection.

    Proposal request contexts are stored hashable (tuples in place of lists
    and mappings). Adapters that echo declared products use this helper to
    recover the original canonical payloads.
    """
    if isinstance(value, tuple):
        if value and all(
            isinstance(item, tuple) and len(item) == 2 and isinstance(item[0], str)
            for item in value
        ):
            return {key: unfreeze_projection(item) for key, item in value}
        return [unfreeze_projection(item) for item in value]
    return value


def _check_float(name: str, value: Any, low: float, high: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise SchedulerError(f"{name} must be an int or float")
    value = float(value)
    if not math.isfinite(value) or not low <= value <= high:
        raise SchedulerError(f"{name} must be in [{low}, {high}], got {value}")
    return value


def _check_int(name: str, value: Any, low: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < low:
        raise SchedulerError(f"{name} must be an int >= {low}, got {value!r}")
    return value


@dataclass(frozen=True)
class FrozenConfig:
    """The declared, itemized hybrid search plan.

    Every acquisition and budget choice is declared here so a run can be
    replayed from this object alone. Acquisition parameters (operator
    weights, exploration share, exploit top-k, parent rule) schedule work
    only; they never enter the promotion decision.
    """

    seeds: tuple[Candidate, ...]
    operator_specs: tuple[OperatorSpec, ...]
    operator_weights: tuple[tuple[str, float], ...]
    exploration_share: float
    exploit_top_k: int
    parent_rule: str
    metric: str
    promote_threshold: float
    max_proposal_rounds: int
    max_promoted: int
    stop_rule: str
    racing_rule: str
    # stop_rule semantics: "rounds" stops only at max_proposal_rounds;
    # "archive_full" stops early when max_promoted is reached;
    # "either" stops at whichever comes first. max_proposal_rounds always
    # bounds the loop, so no stop rule can hang an unfillable archive.
    retries: int
    rng_seed: int
    control_arm: bool = False
    confirmation_checks: tuple[tuple[str, int], ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.seeds, tuple) or not self.seeds:
            raise SchedulerError("config requires a non-empty tuple of seeds")
        seed_ids = [seed.candidate_id for seed in self.seeds]
        if len(set(seed_ids)) != len(seed_ids):
            raise SchedulerError("config seeds must have distinct candidate identities")
        control_seeds = [seed for seed in self.seeds if seed.role == "explicit_reconstruction"]
        if not isinstance(self.control_arm, bool):
            raise SchedulerError("control_arm must be a bool")
        if self.control_arm != bool(control_seeds):
            raise SchedulerError(
                "control_arm must be True exactly when the seeds contain an "
                "explicit_reconstruction control candidate"
            )
        if not isinstance(self.operator_specs, tuple) or not self.operator_specs:
            raise SchedulerError("config requires a non-empty tuple of operator specs")
        for spec in self.operator_specs:
            if not isinstance(spec, OperatorSpec) or spec.operator not in OPERATOR_LABELS:
                raise SchedulerError("operator specs must carry an operator label")
        spec_labels = {spec.operator for spec in self.operator_specs}
        if not isinstance(self.operator_weights, tuple) or not self.operator_weights:
            raise SchedulerError("operator_weights must be a non-empty tuple")
        weight_labels: dict[str, float] = {}
        for label, weight in self.operator_weights:
            if not isinstance(label, str) or not label:
                raise SchedulerError("operator weight labels must be non-empty str")
            if isinstance(weight, bool) or not isinstance(weight, (int, float)):
                raise SchedulerError(f"operator weight for {label!r} must be an int or float")
            weight = float(weight)
            if not math.isfinite(weight) or weight <= 0.0:
                raise SchedulerError(f"operator weight for {label!r} must be a positive float")
            if label in weight_labels:
                raise SchedulerError(f"duplicate operator weight label: {label!r}")
            weight_labels[label] = weight
        if set(weight_labels) != spec_labels:
            raise SchedulerError(
                "operator_weights must cover exactly the spec labels: "
                f"{sorted(spec_labels)}, got {sorted(weight_labels)}"
            )
        object.__setattr__(self, "operator_weights", tuple(sorted(self.operator_weights)))
        object.__setattr__(self, "exploration_share", _check_float("exploration_share", self.exploration_share, 0.0, 1.0))
        object.__setattr__(self, "exploit_top_k", _check_int("exploit_top_k", self.exploit_top_k, 1))
        if self.parent_rule not in PARENT_RULES:
            raise SchedulerError(f"unknown parent rule {self.parent_rule!r}; available: {list(PARENT_RULES)}")
        if not isinstance(self.metric, str) or not self.metric:
            raise SchedulerError("metric must be a non-empty str")
        object.__setattr__(self, "promote_threshold", _check_float("promote_threshold", self.promote_threshold, 0.0, 1.0))
        object.__setattr__(self, "max_proposal_rounds", _check_int("max_proposal_rounds", self.max_proposal_rounds, 0))
        object.__setattr__(self, "max_promoted", _check_int("max_promoted", self.max_promoted, 1))
        if self.stop_rule not in STOP_RULES:
            raise SchedulerError(f"unknown stop rule {self.stop_rule!r}; available: {list(STOP_RULES)}")
        if self.racing_rule not in RACING_RULES:
            raise SchedulerError(f"unknown racing rule {self.racing_rule!r}; available: {list(RACING_RULES)}")
        object.__setattr__(self, "retries", _check_int("retries", self.retries, 0))
        object.__setattr__(self, "rng_seed", _check_int("rng_seed", self.rng_seed, 0))
        seen: set[str] = set()
        for key, value in self.confirmation_checks:
            if key not in CHECK_KEYS:
                raise SchedulerError(f"unknown confirmation check key {key!r}; available: {list(CHECK_KEYS)}")
            if key in seen:
                raise SchedulerError(f"duplicate confirmation check key: {key!r}")
            _check_int(f"confirmation check {key}", value, 0)
            seen.add(key)
        object.__setattr__(self, "confirmation_checks", tuple(sorted(self.confirmation_checks)))

    def to_canonical(self) -> dict[str, Any]:
        return {
            "schemaVersion": HYBRID_SCHEMA_VERSION,
            "seeds": [seed.to_canonical() for seed in self.seeds],
            "operatorSpecs": [spec.to_canonical() for spec in self.operator_specs],
            "operatorWeights": {label: weight for label, weight in self.operator_weights},
            "explorationShare": self.exploration_share,
            "exploitTopK": self.exploit_top_k,
            "parentRule": self.parent_rule,
            "metric": self.metric,
            "promoteThreshold": self.promote_threshold,
            "maxProposalRounds": self.max_proposal_rounds,
            "maxPromoted": self.max_promoted,
            "stopRule": self.stop_rule,
            "racingRule": self.racing_rule,
            "retries": self.retries,
            "rngSeed": self.rng_seed,
            "controlArm": self.control_arm,
            "confirmationChecks": {key: value for key, value in self.confirmation_checks},
        }

    @property
    def config_digest(self) -> str:
        return digest(self.to_canonical())


def frozen_config_from_canonical(payload: Mapping[str, Any]) -> FrozenConfig:
    """Rebuild a ``FrozenConfig`` from its canonical form, rejecting unknown fields."""
    if not isinstance(payload, Mapping):
        raise SchedulerError("frozen config payload must be a mapping")
    allowed = {
        "schemaVersion",
        "seeds",
        "operatorSpecs",
        "operatorWeights",
        "explorationShare",
        "exploitTopK",
        "parentRule",
        "metric",
        "promoteThreshold",
        "maxProposalRounds",
        "maxPromoted",
        "stopRule",
        "racingRule",
        "retries",
        "rngSeed",
        "controlArm",
        "confirmationChecks",
    }
    unknown = set(payload) - allowed
    if unknown:
        raise SchedulerError(f"frozen config has unknown fields: {sorted(unknown)}")
    version = payload.get("schemaVersion")
    if version is not None and version != HYBRID_SCHEMA_VERSION:
        raise SchedulerError(f"unsupported frozen config schema version: {version!r}")
    missing = {"metric", "maxProposalRounds", "maxPromoted"} - set(payload)
    if missing:
        raise SchedulerError(f"frozen config is missing required fields: {sorted(missing)}")
    seeds = payload.get("seeds")
    if not isinstance(seeds, list) or not seeds:
        raise SchedulerError("frozen config seeds must be a non-empty list")
    specs = payload.get("operatorSpecs")
    if not isinstance(specs, list) or not specs:
        raise SchedulerError("frozen config operatorSpecs must be a non-empty list")
    weights = payload.get("operatorWeights")
    if not isinstance(weights, Mapping) or not weights:
        raise SchedulerError("frozen config operatorWeights must be a non-empty mapping")
    checks = payload.get("confirmationChecks", {})
    if not isinstance(checks, Mapping):
        raise SchedulerError("frozen config confirmationChecks must be a mapping")
    from .contracts import candidate_from_canonical

    parsed_seeds = []
    for item in seeds:
        try:
            if not isinstance(item, Mapping):
                raise ValueError("seed must be a mapping")
            parsed_seeds.append(candidate_from_canonical(item))
        except ValueError as exc:
            raise SchedulerError(f"malformed seed: {exc}") from exc
    parsed_specs = []
    for spec_payload in specs:
        try:
            if not isinstance(spec_payload, Mapping) or "operator" not in spec_payload:
                raise KeyError("operator")
            parsed_specs.append(OPERATOR_SPEC_BUILDERS[spec_payload["operator"]](spec_payload))
        except (KeyError, OperatorFailure, ValueError) as exc:
            raise SchedulerError(f"malformed operatorSpec: {exc}") from exc
    return FrozenConfig(
        seeds=tuple(parsed_seeds),
        operator_specs=tuple(parsed_specs),
        operator_weights=tuple(
            (str(label), float(weight)) for label, weight in sorted(weights.items())
        ),
        exploration_share=payload.get("explorationShare", 0.5),
        exploit_top_k=payload.get("exploitTopK", 1),
        parent_rule=payload.get("parentRule", "uniform_promoted"),
        metric=payload["metric"],
        promote_threshold=payload.get("promoteThreshold", 0.5),
        max_proposal_rounds=payload["maxProposalRounds"],
        max_promoted=payload["maxPromoted"],
        stop_rule=payload.get("stopRule", "rounds"),
        racing_rule=payload.get("racingRule", "evaluate_all"),
        retries=payload.get("retries", 0),
        rng_seed=payload.get("rngSeed", 0),
        control_arm=payload.get("controlArm", False),
        confirmation_checks=tuple(
            (key, value) for key, value in sorted(checks.items())
        ),
    )


@dataclass(frozen=True)
class HybridRunResult:
    """The verifiable outcome of one scheduled run."""

    root: Path
    run_id: str
    status: str
    event_count: int
    promoted_candidate_ids: tuple[str, ...]
    shortlist_candidate_ids: tuple[str, ...]
    confirmation_outcome: str | None
    confirmed_candidate_id: str | None
    materialized_digests: tuple[tuple[str, str], ...]


class _Scheduler:
    """Single-run driver; all events are appended through the bundle."""

    def __init__(
        self,
        bundle: RunBundle,
        run_id: str,
        config: FrozenConfig,
        confirmation: ConfirmationSpec,
        proposal: ProposalAdapter,
        evaluation: EvaluationAdapter,
        coordinate_cost: Callable[[Candidate], CoordinateCost],
    ) -> None:
        self._bundle = bundle
        self._run_id = run_id
        self._config = config
        self._confirmation = confirmation
        self._proposal = proposal
        self._evaluation = evaluation
        self._coordinate_cost = coordinate_cost
        self._candidates: dict[str, Candidate] = {}
        self._archive: dict[str, dict[str, Any]] = {}
        self._archive_digest: str | None = None
        self._promoted: list[str] = []
        self._promoted_metric: dict[str, float] = {}
        self._seen_identities: set[str] = set()
        self._rng = random.Random(config.rng_seed)
        self._last_event_id = f"{run_id}:run-started"
        self._proposal_counter = 0
        self._evaluation_counter = 0
        self._round = 0

    # -- event plumbing ---------------------------------------------------

    def _emit(
        self,
        event_type: str,
        phase: str,
        payload: Mapping[str, Any],
        *,
        blobs: Mapping[str, bytes] | None = None,
    ) -> Event:
        sequence = self._bundle.next_sequence
        event = build_event(
            event_id=f"{self._run_id}:event-{sequence:04d}",
            sequence=sequence,
            event_type=event_type,
            phase=phase,
            payload=dict(payload),
            parent_event_ids=(self._last_event_id,),
            blob_digests=tuple((blobs or {}).keys()),
        )
        self._bundle.append_event(event, blobs=blobs)
        self._last_event_id = event.event_id
        return event

    # -- proposal / evaluation ---------------------------------------------

    def _propose(
        self,
        mode_label: str,
        context: Mapping[str, Any],
        requested: tuple[Candidate, ...],
        *,
        parent_candidate_ids: Sequence[str] = (),
    ):
        """Run one proposal call through the kernel boundary; return the receipt."""
        self._proposal_counter += 1
        index = self._proposal_counter
        reservation_id = f"rsv-search-{index}"
        self._emit("budget_reserved", "discovery", {
            "reservationId": reservation_id,
            "account": "W_search",
            "stage": "discovery",
        })
        request_id = f"req-proposal-{index}"
        request = proposal_request(
            request_id=request_id,
            reservation_id=reservation_id,
            adapter=self._proposal.identity,
            proposal_mode=mode_label,
            target_digest=self._bundle.manifest.target_digest,
            context=context,
            parent_candidate_ids=tuple(parent_candidate_ids),
        )
        try:
            receipt = self._proposal.propose(request)
        except Exception as exc:  # noqa: BLE001 — adapter boundary, fail closed
            self._emit("proposal_failed", "discovery", {
                "requestId": request_id,
                "reservationId": reservation_id,
                "reason": f"proposal adapter raised: {exc}",
            })
            self._emit("budget_failed", "discovery", {
                "reservationId": reservation_id,
                "account": "W_search",
                "stage": "discovery",
                "reason": "proposal call raised",
            })
            return None
        receipt_ids = tuple(candidate.candidate_id for candidate in receipt.candidates)
        requested_ids = tuple(candidate.candidate_id for candidate in requested)
        if receipt.request_id != request.request_id or receipt_ids != requested_ids:
            # A receipt whose request id matches the declared request can be
            # attached as a blob (the kernel re-checks it). A receipt with a
            # tampered request id cannot legally reference the event, so its
            # evidence is recorded as payload fields instead.
            payload: dict[str, Any] = {
                "requestId": request_id,
                "reservationId": reservation_id,
                "reason": "receipt_mismatch",
                "receiptRequestId": receipt.request_id,
                "receiptCandidateIds": list(receipt_ids),
            }
            blobs = None
            if receipt.request_id == request.request_id:
                receipt_blob_digest = digest(receipt.to_canonical())
                blobs = {receipt_blob_digest: canonical_bytes(receipt.to_canonical())}
            self._emit("proposal_failed", "discovery", payload, blobs=blobs)
            self._emit("budget_failed", "discovery", {
                "reservationId": reservation_id,
                "account": "W_search",
                "stage": "discovery",
                "reason": "proposal receipt did not match the declared request",
            })
            return None
        receipt_blob_digest = digest(receipt.to_canonical())
        self._emit(
            "proposal_succeeded",
            "discovery",
            {
                "requestId": request_id,
                "reservationId": reservation_id,
                "candidateIds": list(receipt_ids),
            },
            blobs={receipt_blob_digest: canonical_bytes(receipt.to_canonical())},
        )
        self._emit("budget_committed", "discovery", {
            "reservationId": reservation_id,
            "account": "W_search",
            "stage": "discovery",
        })
        for candidate in receipt.candidates:
            self._candidates[candidate.candidate_id] = candidate
            self._seen_identities.add(candidate.candidate_id)
        return receipt

    def _failed_proposal(self, *, attempts: int, suppressed: int) -> None:
        self._proposal_counter += 1
        index = self._proposal_counter
        reservation_id = f"rsv-search-{index}"
        self._emit("budget_reserved", "discovery", {
            "reservationId": reservation_id,
            "account": "W_search",
            "stage": "discovery",
        })
        self._emit("proposal_failed", "discovery", {
            "requestId": f"req-proposal-{index}",
            "reservationId": reservation_id,
            "reason": "no_applicable_operator_products",
            "attempts": attempts,
            "suppressedDuplicates": suppressed,
        })
        self._emit("budget_failed", "discovery", {
            "reservationId": reservation_id,
            "account": "W_search",
            "stage": "discovery",
            "reason": "no applicable operator product after declared attempts",
        })

    def _archive_candidate(self, candidate: Candidate) -> None:
        cost = self._coordinate_cost(candidate)
        self._archive[candidate.candidate_id] = candidate.to_canonical()
        self._archive_digest = digest({
            "schemaVersion": ARCHIVE_VIEW_SCHEMA_VERSION,
            "candidates": dict(self._archive),
        })
        self._emit("archive_changed", "discovery", {
            "candidateId": candidate.candidate_id,
            "archiveDigest": self._archive_digest,
            "coordinateCost": cost.to_canonical(),
        })

    def _metric_of(self, receipt: Any) -> float | None:
        metric = dict(receipt.metrics).get(self._config.metric)
        if isinstance(metric, bool) or not isinstance(metric, (int, float)):
            return None
        return float(metric)

    def _evaluate_discovery_batch(self, ordinary: Sequence[Candidate]) -> None:
        if not ordinary:
            return
        self._evaluation_counter += 1
        batch = self._evaluation_counter
        reservation_id = f"rsv-eval-{batch}"
        self._emit("budget_reserved", "discovery", {
            "reservationId": reservation_id,
            "account": "T_dec",
            "stage": "discovery",
        })
        remaining: list[Candidate] = []
        racing_stop = False
        for position, candidate in enumerate(ordinary):
            if racing_stop:
                remaining.append(candidate)
                continue
            # Batch + position make the request id unique by construction; a
            # candidate-id prefix would collide across candidates sharing one.
            request_id = f"req-eval-{batch}-{position}"
            self._emit("evaluation_started", "discovery", {
                "requestId": request_id,
                "reservationId": reservation_id,
                "candidateId": candidate.candidate_id,
            })
            request = evaluation_request(
                request_id=request_id,
                reservation_id=reservation_id,
                adapter=self._evaluation.identity,
                candidate=candidate,
            )
            try:
                receipt = self._evaluation.evaluate(request)
            except Exception as exc:  # noqa: BLE001 — adapter boundary, fail closed
                self._emit("evaluation_failed", "discovery", {
                    "requestId": request_id,
                    "reservationId": reservation_id,
                    "candidateId": candidate.candidate_id,
                    "reason": f"evaluation adapter raised: {exc}",
                })
                self._reject(candidate.candidate_id, "evaluation_failed")
                continue
            receipt_blob_digest = digest(receipt.to_canonical())
            self._emit(
                "evaluation_completed",
                "discovery",
                {
                    "requestId": request_id,
                    "reservationId": reservation_id,
                    "candidateId": candidate.candidate_id,
                },
                blobs={receipt_blob_digest: canonical_bytes(receipt.to_canonical())},
            )
            metric = self._metric_of(receipt)
            if metric is None:
                self._reject(candidate.candidate_id, "malformed_proposal")
                continue
            if metric >= self._config.promote_threshold:
                self._promote(candidate.candidate_id, metric)
                if self._config.racing_rule == "first_passing":
                    racing_stop = True
            else:
                self._reject(candidate.candidate_id, "dominated")
        self._emit("budget_committed", "discovery", {
            "reservationId": reservation_id,
            "account": "T_dec",
            "stage": "discovery",
        })
        for candidate in remaining:
            self._reject(candidate.candidate_id, "dominated")

    def _promote(self, candidate_id: str, metric: float) -> None:
        self._promoted.append(candidate_id)
        self._promoted_metric[candidate_id] = metric
        self._emit("candidate_promoted", "discovery", {"candidateId": candidate_id})

    def _reject(self, candidate_id: str, reason: str) -> None:
        self._emit("candidate_rejected", "discovery", {
            "candidateId": candidate_id,
            "reason": reason,
        })

    # -- operator rounds ---------------------------------------------------

    def _stop_reached(self) -> bool:
        # max_proposal_rounds is always the hard bound; archive_full is an
        # early stop, never an unbounded wait for a promotion that may never
        # come.
        if self._round >= self._config.max_proposal_rounds:
            return True
        if self._config.stop_rule in ("archive_full", "either"):
            return len(self._promoted) >= self._config.max_promoted
        return False

    def _spec_applicable(self, spec: OperatorSpec, parent: Candidate) -> bool:
        try:
            spec.apply(parent)
        except OperatorFailure:
            return False
        return True

    def _operator_round(self) -> None:
        ordered = sorted(
            self._promoted, key=lambda cid: (-self._promoted_metric[cid], cid)
        )
        exploit_pool = ordered[: self._config.exploit_top_k]
        labels = [label for label, _ in self._config.operator_weights]
        weights = [weight for _, weight in self._config.operator_weights]
        specs_by_label = {
            label: [spec for spec in self._config.operator_specs if spec.operator == label]
            for label in labels
        }
        attempts = 0
        suppressed = 0
        for _ in range(1 + self._config.retries):
            attempts += 1
            if self._rng.random() < self._config.exploration_share:
                pool = ordered
            else:
                pool = exploit_pool
            parent_id = self._rng.choice(pool)
            parent = self._candidates[parent_id]
            label = self._rng.choices(labels, weights=weights, k=1)[0]
            applicable = [
                spec for spec in specs_by_label[label] if self._spec_applicable(spec, parent)
            ]
            if not applicable:
                continue
            spec = self._rng.choice(applicable)
            product = spec.apply(parent)
            if product.candidate_id in self._seen_identities:
                suppressed += 1
                continue
            receipt = self._propose(
                label,
                {
                    "proposalMode": label,
                    "operatorSpec": spec.to_canonical(),
                    "parentCandidateId": parent_id,
                    "operatorProducts": [product.to_canonical()],
                },
                (product,),
                parent_candidate_ids=(parent_id,),
            )
            if receipt is None:
                continue
            self._archive_candidate(product)
            self._evaluate_discovery_batch((product,))
            return
        self._failed_proposal(attempts=attempts, suppressed=suppressed)

    # -- freeze, confirmation, close ---------------------------------------

    def _freeze_and_confirm(self) -> None:
        shortlist = sorted(
            self._promoted, key=lambda cid: (-self._promoted_metric[cid], cid)
        )
        self._emit("search_frozen", "freeze", {
            "archiveDigest": self._archive_digest,
            "shortlistCandidateIds": list(shortlist),
            "selectionRule": SELECTION_RULE,
            "discoveryContextDigest": self._confirmation.discovery_context_digest,
        })
        session = ConfirmationSession(
            self._confirmation,
            tuple(shortlist),
            shortlist[0] if shortlist else None,
        )
        started_payload = session.begin()
        self._emit("confirmation_started", "confirmation", {
            "confirmationContextDigest": started_payload["confirmationContextDigest"],
            "seed": started_payload["seed"],
            "specDigest": started_payload["specDigest"],
        })
        sample = 0
        while True:
            next_evaluation = session.next_evaluation()
            if next_evaluation is None:
                break
            sample += 1
            reservation_id = f"rsv-eval-confirm-{sample}"
            self._emit("budget_reserved", "confirmation", {
                "reservationId": reservation_id,
                "account": "T_dec",
                "stage": "confirmation",
            })
            candidate = self._candidates[next_evaluation.candidate_id]
            self._emit("evaluation_started", "confirmation", {
                "requestId": next_evaluation.request_id,
                "reservationId": reservation_id,
                "candidateId": next_evaluation.candidate_id,
            })
            request = evaluation_request(
                request_id=next_evaluation.request_id,
                reservation_id=reservation_id,
                adapter=self._evaluation.identity,
                candidate=candidate,
            )
            try:
                receipt = self._evaluation.evaluate(request)
            except Exception as exc:  # noqa: BLE001 — adapter boundary, fail closed
                self._emit("evaluation_failed", "confirmation", {
                    "requestId": next_evaluation.request_id,
                    "reservationId": reservation_id,
                    "candidateId": next_evaluation.candidate_id,
                    "reason": f"evaluation adapter raised: {exc}",
                })
                session.record_evaluation_outcome(next_evaluation.request_id, False)
                self._emit("budget_committed", "confirmation", {
                    "reservationId": reservation_id,
                    "account": "T_dec",
                    "stage": "confirmation",
                })
                continue
            receipt_blob_digest = digest(receipt.to_canonical())
            self._emit(
                "evaluation_completed",
                "confirmation",
                {
                    "requestId": next_evaluation.request_id,
                    "reservationId": reservation_id,
                    "candidateId": next_evaluation.candidate_id,
                },
                blobs={receipt_blob_digest: canonical_bytes(receipt.to_canonical())},
            )
            metric = dict(receipt.metrics).get(self._confirmation.metric)
            passed = (
                isinstance(metric, (int, float))
                and not isinstance(metric, bool)
                and metric >= self._confirmation.threshold
            )
            session.record_evaluation_outcome(next_evaluation.request_id, bool(passed))
            self._emit("budget_committed", "confirmation", {
                "reservationId": reservation_id,
                "account": "T_dec",
                "stage": "confirmation",
            })
        completed_payload = session.complete()
        completed_payload.update(dict(self._config.confirmation_checks))
        completed_payload["frozenConfigDigest"] = self._config.config_digest
        completed_payload["confirmationSpecDigest"] = self._confirmation.spec_digest
        self._emit("confirmation_completed", "confirmation", completed_payload)
        return completed_payload["outcome"]

    # -- top level ----------------------------------------------------------

    def run(self) -> HybridRunResult:
        context_seeds = [seed.to_canonical() for seed in self._config.seeds]
        receipt = self._propose(
            "seed",
            {"proposalMode": "seed", "seeds": context_seeds},
            self._config.seeds,
        )
        if receipt is None:
            self._bundle.close(status="aborted")
            return self._result("aborted", None)
        ordinary = [candidate for candidate in receipt.candidates if candidate.role == "candidate"]
        for candidate in receipt.candidates:
            self._archive_candidate(candidate)
            if candidate.role != "candidate":
                self._reject(candidate.candidate_id, "policy_excluded")
        self._evaluate_discovery_batch(ordinary)
        while not self._stop_reached():
            if not self._promoted:
                break
            self._round += 1
            self._operator_round()
        outcome = self._freeze_and_confirm()
        self._bundle.close(status="completed")
        return self._result("completed", outcome)

    def _result(self, status: str, outcome: str | None) -> HybridRunResult:
        confirmed = None
        if outcome == "confirmed":
            shortlist = sorted(
                self._promoted, key=lambda cid: (-self._promoted_metric[cid], cid)
            )
            confirmed = shortlist[0] if shortlist else None
        digests = materialize(self._bundle.root)
        return HybridRunResult(
            root=self._bundle.root,
            run_id=self._run_id,
            status=status,
            event_count=self._bundle.next_sequence,
            promoted_candidate_ids=tuple(self._promoted),
            shortlist_candidate_ids=tuple(
                sorted(self._promoted, key=lambda cid: (-self._promoted_metric[cid], cid))
            ),
            confirmation_outcome=outcome,
            confirmed_candidate_id=confirmed,
            materialized_digests=tuple(sorted(digests.items())),
        )



def run_hybrid_search(
    root: Path,
    run_id: str,
    config: FrozenConfig,
    confirmation: ConfirmationSpec,
    proposal: ProposalAdapter,
    evaluation: EvaluationAdapter,
    *,
    target_digest: str,
    known_metrics: Sequence[str],
    nesting_rule: str,
    scheduler_model: str,
    model_manifest: Mapping[str, Any],
    coordinate_cost: Callable[[Candidate], CoordinateCost],
    target_content: str | None = None,
) -> HybridRunResult:
    """Run one complete hybrid Pareto search and return its verifiable result."""
    if not isinstance(config, FrozenConfig):
        raise SchedulerError("run_hybrid_search requires a FrozenConfig")
    if not isinstance(confirmation, ConfirmationSpec):
        raise SchedulerError("run_hybrid_search requires a ConfirmationSpec")
    if not isinstance(proposal, ProposalAdapter) or not isinstance(evaluation, EvaluationAdapter):
        raise SchedulerError("run_hybrid_search requires proposal and evaluation adapters")
    known = tuple(known_metrics)
    if config.metric not in known:
        raise SchedulerError(
            f"config metric {config.metric!r} is not in known_metrics {known}"
        )
    if confirmation.metric not in known:
        raise SchedulerError(
            f"confirmation metric {confirmation.metric!r} is not in known_metrics {known}"
        )
    if not is_digest(target_digest):
        raise SchedulerError("target_digest must be a well-formed digest")
    bundle = RunBundle.create(
        root,
        run_id=run_id,
        target_digest=target_digest,
        target_content=target_content,
        known_metrics=known,
        adapter_digests=(
            proposal.identity.adapter_digest,
            evaluation.identity.adapter_digest,
        ),
        nesting_rule=nesting_rule,
        scheduler_model=scheduler_model,
        model_manifest=model_manifest,
    )
    scheduler = _Scheduler(
        bundle, run_id, config, confirmation, proposal, evaluation, coordinate_cost
    )
    return scheduler.run()
