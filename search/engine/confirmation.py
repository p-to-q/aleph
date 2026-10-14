"""Protected confirmation protocol for the Aleph engine (PR B).

This module is a pure planner/state machine. It produces payloads and
decisions only; the scheduler writes events into the run bundle. The kernel
(``events.py``/``archive.py``) independently re-checks every rule this module
encodes, so a hand-edited or scheduler-drifted confirmation still fails
closed:

- ``confirmation_started`` carries a context digest that must differ from the
  discovery context digest;
- confirmation evaluations may only target the frozen shortlist;
- confirmation events must follow ``search_frozen`` (phase table + stream
  structure), so confirmation can never influence discovery;
- every evaluation request id, reservation, and seed is used exactly once.

Outcomes are exactly the kernel's ``CONFIRMATION_OUTCOMES``: ``confirmed``,
``rejected``, ``indeterminate``, ``no_confirmed_candidate``.

Pure standard library. No MLX, no network, no adapter calls.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping

from .canonical import digest, is_digest
from .events import CONFIRMATION_OUTCOMES

CONFIRMATION_SCHEMA_VERSION = "aleph-engine-confirmation/0.1.0"


class ConfirmationError(ValueError):
    """Raised when the confirmation protocol is violated or undecidable."""


@dataclass(frozen=True)
class ConfirmationSpec:
    """The frozen confirmation plan, declared before any confirmation event.

    ``samples`` fresh evaluations of the shortlisted candidate are planned.
    With ``passes`` passing evaluations, the outcome is:

    - ``confirmed`` when ``passes / samples >= confirm_fraction``;
    - ``rejected`` when ``passes / samples < reject_fraction``;
    - ``indeterminate`` otherwise.

    With no candidate to confirm the outcome is ``no_confirmed_candidate``.
    """

    discovery_context_digest: str
    confirmation_context_digest: str
    seed: str
    metric: str
    threshold: float
    samples: int
    confirm_fraction: float
    reject_fraction: float

    def __post_init__(self) -> None:
        if not is_digest(self.discovery_context_digest):
            raise ConfirmationError("discovery context digest must be a well-formed digest")
        if not is_digest(self.confirmation_context_digest):
            raise ConfirmationError("confirmation context digest must be a well-formed digest")
        if self.confirmation_context_digest == self.discovery_context_digest:
            raise ConfirmationError(
                "confirmation must use a fresh context: the confirmation context digest "
                "reuses the discovery context digest"
            )
        if not isinstance(self.seed, str) or not self.seed:
            raise ConfirmationError("confirmation requires a non-empty seed")
        if not isinstance(self.metric, str) or not self.metric:
            raise ConfirmationError("confirmation requires a declared metric name")
        if not isinstance(self.samples, int) or isinstance(self.samples, bool):
            raise ConfirmationError("samples must be an int")
        if self.samples < 1:
            raise ConfirmationError("samples must be at least 1")
        for name in ("threshold", "confirm_fraction", "reject_fraction"):
            value = getattr(self, name)
            if not isinstance(value, float) or isinstance(value, bool):
                raise ConfirmationError(f"{name} must be a float")
        if not 0.0 <= self.reject_fraction <= self.confirm_fraction <= 1.0:
            raise ConfirmationError(
                "require 0 <= reject_fraction <= confirm_fraction <= 1"
            )

    @property
    def spec_digest(self) -> str:
        """Digest of the canonical spec, for pinning the plan in events."""
        return digest(self.to_canonical())

    def to_canonical(self) -> dict:
        return {
            "schemaVersion": CONFIRMATION_SCHEMA_VERSION,
            "discoveryContextDigest": self.discovery_context_digest,
            "confirmationContextDigest": self.confirmation_context_digest,
            "seed": self.seed,
            "metric": self.metric,
            "threshold": self.threshold,
            "samples": self.samples,
            "confirmFraction": self.confirm_fraction,
            "rejectFraction": self.reject_fraction,
        }


def decide_outcome(
    samples: int, passes: int, evaluated: int, confirm_fraction: float, reject_fraction: float
) -> str:
    """Decide the terminal outcome from a completed fresh-sample plan.

    Raises while the plan is unfinished, so a scheduler can never decide a
    confirmation before all planned fresh samples are recorded.
    """
    if evaluated < samples:
        raise ConfirmationError(
            f"confirmation plan is unfinished: {evaluated}/{samples} samples recorded"
        )
    if evaluated > samples:
        raise ConfirmationError(
            f"more evaluations recorded than planned: {evaluated} > {samples}"
        )
    if passes < 0 or passes > evaluated:
        raise ConfirmationError(f"pass count {passes} is inconsistent with {evaluated} evaluations")
    rate = passes / samples
    if rate >= confirm_fraction:
        return "confirmed"
    if rate < reject_fraction:
        return "rejected"
    return "indeterminate"


@dataclass(frozen=True)
class ConfirmationEvaluation:
    """One fresh evaluation the scheduler must run against the shortlisted candidate."""

    request_id: str
    candidate_id: str


@dataclass
class ConfirmationSession:
    """One protected confirmation episode over a frozen shortlist.

    Tracks every fresh request id and pass/fail result, so ids and seeds are
    used exactly once, the sample plan is followed exactly, and the terminal
    outcome is decidable only after the plan completes.
    """

    spec: ConfirmationSpec
    shortlist: tuple[str, ...]
    candidate_id: str | None = None
    started: bool = False
    completed: bool = False
    _evaluated: int = 0
    _passes: int = 0
    _issued: set[str] = field(default_factory=set)
    _recorded: set[str] = field(default_factory=set)

    def __post_init__(self) -> None:
        if not isinstance(self.shortlist, tuple):
            raise ConfirmationError("shortlist must be a tuple")
        if len(set(self.shortlist)) != len(self.shortlist):
            raise ConfirmationError("shortlist must not contain duplicates")
        if self.candidate_id is not None and self.candidate_id not in self.shortlist:
            raise ConfirmationError(
                f"confirmation candidate {self.candidate_id!r} is not in the frozen shortlist"
            )

    def begin(self) -> dict:
        """Return the ``confirmation_started`` payload, exactly once."""
        if self.started:
            raise ConfirmationError("confirmation already started")
        if self.completed:
            raise ConfirmationError("confirmation already completed")
        self.started = True
        return {
            "confirmationContextDigest": self.spec.confirmation_context_digest,
            "seed": self.spec.seed,
            "specDigest": self.spec.spec_digest,
        }

    def next_evaluation(self) -> ConfirmationEvaluation | None:
        """Return the next fresh evaluation to run, or None when the plan is done.

        With no candidate to confirm, no evaluation is ever issued.
        """
        if not self.started:
            raise ConfirmationError("confirmation has not started")
        if self.completed:
            raise ConfirmationError("confirmation already completed")
        if self.candidate_id is None:
            return None
        if self._evaluated >= self.spec.samples:
            return None
        index = self._evaluated + 1
        request_id = f"{self.candidate_id}:confirmation-sample-{index}:{self.spec.seed}"
        if request_id in self._issued:
            raise ConfirmationError(f"confirmation request id would be reused: {request_id}")
        self._issued.add(request_id)
        self._evaluated += 1
        return ConfirmationEvaluation(request_id=request_id, candidate_id=self.candidate_id)

    def record_evaluation_outcome(self, request_id: str, passed: bool) -> None:
        """Record one fresh-sample result, each request id exactly once."""
        if not self.started:
            raise ConfirmationError("confirmation has not started")
        if self.completed:
            raise ConfirmationError("confirmation already completed")
        if request_id not in self._issued:
            raise ConfirmationError(f"unknown confirmation evaluation: {request_id}")
        if request_id in self._recorded:
            raise ConfirmationError(f"confirmation evaluation recorded twice: {request_id}")
        if not isinstance(passed, bool):
            raise ConfirmationError("passed must be a bool")
        self._recorded.add(request_id)
        if passed:
            self._passes += 1

    def complete(self) -> dict:
        """Return the ``confirmation_completed`` payload for the terminal outcome."""
        if not self.started:
            raise ConfirmationError("confirmation has not started")
        if self.completed:
            raise ConfirmationError("confirmation already completed")
        if self.candidate_id is None:
            outcome = "no_confirmed_candidate"
        else:
            outcome = decide_outcome(
                self.spec.samples,
                self._passes,
                len(self._recorded),
                self.spec.confirm_fraction,
                self.spec.reject_fraction,
            )
        self.completed = True
        payload: dict = {"outcome": outcome}
        if outcome == "confirmed":
            payload["candidateId"] = self.candidate_id
        return payload
