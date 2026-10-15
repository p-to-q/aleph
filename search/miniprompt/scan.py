"""MiniPrompt length scan policy (pure standard library).

Reimplements the scan in the pinned upstream
``prompt_optimization/miniprompt.py`` (``locuslab/acr-memorization`` @
``bf3ba2e7``):

- start at ``nFreeStart`` free tokens;
- on success: the upper bound becomes the successful length and the scan
  descends to length - 1 (the step budget is kept);
- on failure: the lower bound becomes the failed length, the scan grows by
  ``nFreeIncrement``, and the step budget is multiplied by ``stepMultiplier``
  and truncated to an integer (exactly upstream);
- terminate when the next length would reach the upper bound or the lower
  bound; ``maxFreeTokens == -1`` resolves the upper bound to ``5 x`` the
  target-token count before the first attempt (upstream ``max_tokens=-1``);
- ``numFreeTokens`` is the upper bound at termination: the smallest successful
  count when the scan succeeds, the resolved cap otherwise.

Declared Aleph-side bounds on top of the upstream policy (both part of the
frozen configuration): ``stepsHardCap`` caps the step budget after growth, and
``maxAttempts`` stops the scan when the attempt count reaches it
(``stopReason == "max_attempts"``).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Tuple

STOP_COLLISION = "collision"
STOP_MAX_ATTEMPTS = "max_attempts"


class ScanPolicyError(ValueError):
    """Recorded attempt outcomes are inconsistent with the scan policy."""


@dataclass(frozen=True)
class AttemptSpec:
    index: int
    n_free: int
    steps_budget: int


@dataclass
class ScanState:
    n_free: int
    running_max: int
    running_min: int
    steps_budget: int
    attempts: int = 0
    success: bool = False
    done: bool = False
    stop_reason: Optional[str] = None


class ScanPolicy:
    """The upstream scan policy as an explicit state machine."""

    def __init__(self, config, target_token_count: int):
        self._increment = config.n_free_increment
        self._multiplier = float(config.step_multiplier)
        self._max_attempts = config.max_attempts
        self._hard_cap = config.steps_hard_cap
        self._target_token_count = target_token_count
        self.state = ScanState(
            n_free=config.n_free_start,
            running_max=config.max_free_tokens,
            running_min=0,
            steps_budget=min(config.steps_initial, config.steps_hard_cap),
        )

    def next_spec(self) -> Optional[AttemptSpec]:
        """The next attempt to run, or ``None`` when the scan is finished."""
        state = self.state
        if state.done:
            return None
        if state.attempts >= self._max_attempts:
            state.done = True
            state.stop_reason = STOP_MAX_ATTEMPTS
            return None
        if state.running_max == -1:
            state.running_max = self._target_token_count * 5
        return AttemptSpec(index=state.attempts, n_free=state.n_free, steps_budget=state.steps_budget)

    def record(self, acquired: bool) -> bool:
        """Fold one attempt outcome in; returns ``True`` when the scan continues."""
        state = self.state
        if state.done:
            raise ScanPolicyError("cannot record an outcome after the scan is done")
        if acquired:
            state.running_max = state.n_free
            state.success = True
            new_n = state.n_free - 1
        else:
            state.running_min = state.n_free
            new_n = state.n_free + self._increment
            state.steps_budget = min(int(state.steps_budget * self._multiplier), self._hard_cap)
        state.attempts += 1
        if new_n >= state.running_max or new_n <= state.running_min:
            state.done = True
            state.stop_reason = STOP_COLLISION
            return False
        state.n_free = new_n
        return True

    def to_snapshot(self) -> dict:
        state = self.state
        return {
            "nFree": state.n_free,
            "runningMax": state.running_max,
            "runningMin": state.running_min,
            "stepsBudget": state.steps_budget,
            "attempts": state.attempts,
            "success": state.success,
            "done": state.done,
            "stopReason": state.stop_reason,
        }

    @classmethod
    def from_snapshot(cls, config, target_token_count: int, snapshot: dict) -> "ScanPolicy":
        """Reconstruct a policy from a stored snapshot (caller validates it)."""
        policy = cls(config, target_token_count)
        policy.state = ScanState(
            n_free=snapshot["nFree"],
            running_max=snapshot["runningMax"],
            running_min=snapshot["runningMin"],
            steps_budget=snapshot["stepsBudget"],
            attempts=snapshot["attempts"],
            success=snapshot["success"],
            done=snapshot["done"],
            stop_reason=snapshot["stopReason"],
        )
        return policy


def replay_outcomes(config, target_token_count: int, acquired_flags: List[bool]) -> Tuple[List[AttemptSpec], ScanPolicy]:
    """Replay recorded attempt outcomes through a fresh policy.

    Returns ``(specs, policy)`` where ``specs`` are the attempt specs the
    policy produces for each recorded outcome. The caller decides whether the
    scan is finished by calling ``policy.next_spec()`` once more.
    """
    policy = ScanPolicy(config, target_token_count)
    specs: List[AttemptSpec] = []
    for index, acquired in enumerate(acquired_flags):
        spec = policy.next_spec()
        if spec is None:
            raise ScanPolicyError(
                f"recorded outcome {index} exceeds the policy's attempt bound"
            )
        specs.append(spec)
        policy.record(acquired)
    return specs, policy
