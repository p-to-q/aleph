"""``ResourceLedger/0.1.0``: six accounts, kept separate.

The normative contract is
``docs/plans/model-relative-coordinate-landmarks.md#six-account-resource-ledger``.
This module is its executable form for the PR A kernel:

- ``C(p)``      prefix-free coordinate cost plus a declared tokenizer view;
- ``T_dec``     decoder calls, tokens, samples, failures, and cost proxies;
- ``W_search``  all proposal, mutation, evaluation, retry, miss, and failed work;
- ``D_crit``    longest event-DAG dependency path under a declared scheduler;
- ``V_verify``  fresh post-freeze samples, replay, tests, and human checks;
- ``M_desc``    model/interface/runtime/scaffold/decoding manifest.

Two rules are enforced mechanically rather than documented and hoped for. The
accounts are never collapsed into one scalar: ``T_dec`` declares an explicit
nesting rule relative to ``W_search`` so per-call decoder work is not added
twice, and ``D_crit`` is a derived graph statistic that never participates in a
sum. Every adapter call needs a prior reservation and exactly one terminal
commit or failure.

Word counts are never a scientific coordinate cost: ``C(p)`` carries exact
tokenizer-view token counts and UTF-8 byte counts, and no word-splitting call
exists anywhere in this package.

Pure standard library.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from .canonical import canonicalize, digest

LEDGER_SCHEMA_VERSION = "ResourceLedger/0.1.0"

ACCOUNTS = ("C_p", "T_dec", "W_search", "D_crit", "V_verify", "M_desc")

NESTING_RULES = ("t_dec_nested_in_w_search", "t_dec_added_to_w_search")
"""Declared relationship between per-call decoder work and total search work."""

STAGES = ("discovery", "confirmation")


class LedgerError(ValueError):
    """Raised when an accounting invariant is broken."""


@dataclass(frozen=True)
class CoordinateCost:
    """``C(p)``: cost of the submitted coordinate under a declared tokenizer view.

    ``coordinate_tokens`` is the exact count from the named tokenizer view, not
    a word count. ``full_rendered_tokens`` is recorded separately because the
    rendered evaluator input is not the coordinate cost; collapsing them would
    let scaffold size masquerade as coordinate length.
    """

    tokenizer_view: str
    tokenizer_digest: str
    coordinate_tokens: int
    coordinate_utf8_bytes: int
    full_rendered_tokens: int
    full_rendered_utf8_bytes: int
    target_tokens: int = 0
    continuation_tokens: int = 0
    prefix_free_bits: int | None = None

    def __post_init__(self) -> None:
        if not self.tokenizer_view or not self.tokenizer_digest:
            raise LedgerError("C(p) requires a declared tokenizer view and digest")
        for name in (
            "coordinate_tokens",
            "coordinate_utf8_bytes",
            "full_rendered_tokens",
            "full_rendered_utf8_bytes",
            "target_tokens",
            "continuation_tokens",
        ):
            value = getattr(self, name)
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                raise LedgerError(f"C(p).{name} must be a non-negative int")
        if self.full_rendered_tokens < self.coordinate_tokens:
            raise LedgerError("full rendered tokens cannot be fewer than coordinate tokens")
        if self.prefix_free_bits is not None and (
            not isinstance(self.prefix_free_bits, int)
            or isinstance(self.prefix_free_bits, bool)
            or self.prefix_free_bits < 0
        ):
            raise LedgerError("prefix_free_bits must be None or a non-negative int")

    def to_canonical(self) -> dict[str, Any]:
        return {
            "tokenizerView": self.tokenizer_view,
            "tokenizerDigest": self.tokenizer_digest,
            "coordinateTokens": self.coordinate_tokens,
            "coordinateUtf8Bytes": self.coordinate_utf8_bytes,
            "fullRenderedTokens": self.full_rendered_tokens,
            "fullRenderedUtf8Bytes": self.full_rendered_utf8_bytes,
            "targetTokens": self.target_tokens,
            "continuationTokens": self.continuation_tokens,
            "prefixFreeBits": self.prefix_free_bits,
            "costBasis": "declared_tokenizer_view_not_word_count",
        }


@dataclass
class DecoderAccount:
    """``T_dec``: decoder execution counters, per stage."""

    calls: int = 0
    failures: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    samples: int = 0
    provider_reported_tokens: int = 0

    def add(
        self,
        *,
        calls: int = 0,
        failures: int = 0,
        input_tokens: int = 0,
        output_tokens: int = 0,
        samples: int = 0,
        provider_reported_tokens: int = 0,
    ) -> None:
        counts = {
            "calls": calls,
            "failures": failures,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "samples": samples,
            "provider_reported_tokens": provider_reported_tokens,
        }
        for name, value in counts.items():
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                raise LedgerError(f"T_dec.{name} must be a non-negative int")
        self.calls += calls
        self.failures += failures
        self.input_tokens += input_tokens
        self.output_tokens += output_tokens
        self.samples += samples
        self.provider_reported_tokens += provider_reported_tokens

    def to_canonical(self) -> dict[str, Any]:
        return {
            "calls": self.calls,
            "failures": self.failures,
            "inputTokens": self.input_tokens,
            "outputTokens": self.output_tokens,
            "samples": self.samples,
            "providerReportedTokens": self.provider_reported_tokens,
        }


@dataclass
class SearchWorkAccount:
    """``W_search``: all discovery-side work, including work that produced nothing.

    Retries, cache misses, failures, and rejected candidates are counted. An
    account that only counted successes would understate discovery cost exactly
    where the method was weakest.
    """

    proposal_calls: int = 0
    proposal_failures: int = 0
    evaluation_calls: int = 0
    evaluation_failures: int = 0
    retries: int = 0
    cache_misses: int = 0
    rejected_candidates: int = 0
    proposed_candidates: int = 0

    def to_canonical(self) -> dict[str, Any]:
        components = {
            "proposalCalls": self.proposal_calls,
            "proposalFailures": self.proposal_failures,
            "evaluationCalls": self.evaluation_calls,
            "evaluationFailures": self.evaluation_failures,
            "retries": self.retries,
            "cacheMisses": self.cache_misses,
            "rejectedCandidates": self.rejected_candidates,
            "proposedCandidates": self.proposed_candidates,
        }
        return {
            "components": components,
            "totalAdapterCalls": self.proposal_calls + self.evaluation_calls,
        }

    def add(
        self,
        *,
        proposal_calls: int = 0,
        proposal_failures: int = 0,
        evaluation_calls: int = 0,
        evaluation_failures: int = 0,
        retries: int = 0,
        cache_misses: int = 0,
        rejected_candidates: int = 0,
        proposed_candidates: int = 0,
    ) -> None:
        counts = {
            "proposal_calls": proposal_calls,
            "proposal_failures": proposal_failures,
            "evaluation_calls": evaluation_calls,
            "evaluation_failures": evaluation_failures,
            "retries": retries,
            "cache_misses": cache_misses,
            "rejected_candidates": rejected_candidates,
            "proposed_candidates": proposed_candidates,
        }
        for name, value in counts.items():
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                raise LedgerError(f"W_search.{name} must be a non-negative int")
        self.proposal_calls += proposal_calls
        self.proposal_failures += proposal_failures
        self.evaluation_calls += evaluation_calls
        self.evaluation_failures += evaluation_failures
        self.retries += retries
        self.cache_misses += cache_misses
        self.rejected_candidates += rejected_candidates
        self.proposed_candidates += proposed_candidates


@dataclass
class VerificationAccount:
    """``V_verify``: work that begins only after ``search_frozen``."""

    fresh_samples: int = 0
    replays: int = 0
    tests: int = 0
    human_checks: int = 0
    proof_checks: int = 0

    def to_canonical(self) -> dict[str, Any]:
        return {
            "freshSamples": self.fresh_samples,
            "replays": self.replays,
            "tests": self.tests,
            "humanChecks": self.human_checks,
            "proofChecks": self.proof_checks,
        }

    def add(
        self,
        *,
        fresh_samples: int = 0,
        replays: int = 0,
        tests: int = 0,
        human_checks: int = 0,
        proof_checks: int = 0,
    ) -> None:
        counts = {
            "fresh_samples": fresh_samples,
            "replays": replays,
            "tests": tests,
            "human_checks": human_checks,
            "proof_checks": proof_checks,
        }
        for name, value in counts.items():
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                raise LedgerError(f"V_verify.{name} must be a non-negative int")
        self.fresh_samples += fresh_samples
        self.replays += replays
        self.tests += tests
        self.human_checks += human_checks
        self.proof_checks += proof_checks


@dataclass(frozen=True)
class Reservation:
    """One budget reservation awaiting a terminal commit or failure."""

    reservation_id: str
    account: str
    stage: str
    event_id: str
    limits: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.account not in ACCOUNTS:
            raise LedgerError(f"unknown account: {self.account!r}")
        if self.stage not in STAGES:
            raise LedgerError(f"unknown stage: {self.stage!r}")
        if not isinstance(self.event_id, str) or not self.event_id:
            raise LedgerError("reservation requires a non-empty event id")
        if not isinstance(self.limits, Mapping):
            raise LedgerError("reservation limits must be a mapping")

    def to_canonical(self) -> dict[str, Any]:
        return {
            "reservationId": self.reservation_id,
            "account": self.account,
            "stage": self.stage,
            "eventId": self.event_id,
            "limits": canonicalize(dict(self.limits)),
        }


@dataclass
class ResourceLedger:
    """All six accounts, held together and never collapsed.

    ``nesting_rule`` is mandatory. Without it a reader cannot tell whether
    ``T_dec`` is already inside ``W_search`` or must be added to it, which is
    exactly the double-counting failure the contract forbids.
    """

    nesting_rule: str
    scheduler_model: str
    model_manifest: Mapping[str, Any]
    coordinate_costs: dict[str, CoordinateCost] = field(default_factory=dict)
    decoder: dict[str, DecoderAccount] = field(default_factory=dict)
    search_work: SearchWorkAccount = field(default_factory=SearchWorkAccount)
    verification: VerificationAccount = field(default_factory=VerificationAccount)
    critical_path: int = 0
    open_reservations: dict[str, Reservation] = field(default_factory=dict)
    settled_reservations: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.nesting_rule not in NESTING_RULES:
            raise LedgerError(f"unknown nesting rule: {self.nesting_rule!r}")
        if not self.scheduler_model:
            raise LedgerError("D_crit requires a declared scheduler model")
        if not isinstance(self.model_manifest, Mapping) or not self.model_manifest:
            raise LedgerError("M_desc requires a non-empty manifest")
        for stage in STAGES:
            self.decoder.setdefault(stage, DecoderAccount())

    def reserve(self, reservation: Reservation) -> None:
        if reservation.reservation_id in self.open_reservations:
            raise LedgerError(f"reservation already open: {reservation.reservation_id}")
        if reservation.reservation_id in self.settled_reservations:
            raise LedgerError(f"reservation already settled: {reservation.reservation_id}")
        self.open_reservations[reservation.reservation_id] = reservation

    def settle(self, reservation_id: str, outcome: str) -> Reservation:
        if outcome not in ("committed", "failed"):
            raise LedgerError(f"unknown reservation outcome: {outcome!r}")
        reservation = self.open_reservations.pop(reservation_id, None)
        if reservation is None:
            if reservation_id in self.settled_reservations:
                raise LedgerError(f"reservation settled twice: {reservation_id}")
            raise LedgerError(f"no open reservation to settle: {reservation_id}")
        self.settled_reservations[reservation_id] = outcome
        return reservation

    def require_open(self, reservation_id: str) -> Reservation:
        """Return the open reservation backing an adapter call, or fail closed."""
        reservation = self.open_reservations.get(reservation_id)
        if reservation is None:
            raise LedgerError(f"adapter call without open reservation: {reservation_id}")
        return reservation

    def record_coordinate_cost(self, candidate_id: str, cost: CoordinateCost) -> None:
        existing = self.coordinate_costs.get(candidate_id)
        if existing is not None and existing.to_canonical() != cost.to_canonical():
            raise LedgerError(f"conflicting C(p) for candidate {candidate_id}")
        self.coordinate_costs[candidate_id] = cost

    def to_canonical(self) -> dict[str, Any]:
        return {
            "schemaVersion": LEDGER_SCHEMA_VERSION,
            "accountsPresent": list(ACCOUNTS),
            "collapsePolicy": "accounts_reported_separately_no_published_conversion",
            "nestingRule": self.nesting_rule,
            "C_p": {
                "byCandidate": {
                    candidate_id: cost.to_canonical()
                    for candidate_id, cost in sorted(self.coordinate_costs.items())
                },
                "candidateCount": len(self.coordinate_costs),
            },
            "T_dec": {
                "byStage": {
                    stage: self.decoder[stage].to_canonical() for stage in sorted(self.decoder)
                },
                "nestedInSearchWork": self.nesting_rule == "t_dec_nested_in_w_search",
            },
            "W_search": self.search_work.to_canonical(),
            "D_crit": {
                "longestDependencyPath": self.critical_path,
                "schedulerModel": self.scheduler_model,
                "statisticKind": "derived_graph_statistic_not_additive_cost",
            },
            "V_verify": self.verification.to_canonical(),
            "M_desc": canonicalize(dict(self.model_manifest)),
            "reservations": {
                "open": [
                    reservation.to_canonical()
                    for _, reservation in sorted(self.open_reservations.items())
                ],
                "settled": {
                    key: value for key, value in sorted(self.settled_reservations.items())
                },
            },
        }

    @property
    def ledger_digest(self) -> str:
        return digest(self.to_canonical())


def new_ledger(
    *,
    nesting_rule: str,
    scheduler_model: str,
    model_manifest: Mapping[str, Any],
) -> ResourceLedger:
    return ResourceLedger(
        nesting_rule=nesting_rule,
        scheduler_model=scheduler_model,
        model_manifest=dict(model_manifest),
    )


def coordinate_cost_from_canonical(payload: Mapping[str, Any]) -> CoordinateCost:
    """Rebuild a ``CoordinateCost`` from its canonical payload."""
    try:
        return CoordinateCost(
            tokenizer_view=payload["tokenizerView"],
            tokenizer_digest=payload["tokenizerDigest"],
            coordinate_tokens=payload["coordinateTokens"],
            coordinate_utf8_bytes=payload["coordinateUtf8Bytes"],
            full_rendered_tokens=payload["fullRenderedTokens"],
            full_rendered_utf8_bytes=payload["fullRenderedUtf8Bytes"],
            target_tokens=payload.get("targetTokens", 0),
            continuation_tokens=payload.get("continuationTokens", 0),
            prefix_free_bits=payload.get("prefixFreeBits"),
        )
    except (KeyError, TypeError) as error:
        raise LedgerError(f"malformed C(p) payload: {error}") from error
