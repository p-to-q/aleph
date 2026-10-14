"""Shared helpers for the deterministic candidate operators (PR B).

Operators map a ``Candidate`` to a new ``Candidate`` whose ``proposal_mode`` is
the operator's own frozen label. Common rules live here so each operator
enforces them identically:

- input must be a ``Candidate``;
- every product keeps the input placement and candidate role;
- an empty product fails closed: no messages at all, or any message whose
  content is empty, raises ``OperatorFailure`` (whitespace-only content is
  kernel-legal and is therefore preserved);
- indices are plain non-negative integers, never bools.

Pure standard library. No MLX, no network, no randomness, no clock.
"""

from __future__ import annotations

from typing import Any

from ..contracts import Candidate, Message

OPERATOR_LABELS = ("delete", "rewrite", "repair", "reference")
"""Frozen operator labels; each doubles as the product's ``proposal_mode``."""


class OperatorFailure(ValueError):
    """Typed failure raised when an operator cannot produce a valid product."""


def _require_candidate(candidate: Any) -> Candidate:
    if not isinstance(candidate, Candidate):
        raise OperatorFailure(
            f"operators apply to Candidate instances, got {type(candidate).__name__}"
        )
    return candidate


def _check_index(value: Any) -> int:
    """Return ``value`` as a validated operator index, failing closed on junk."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise OperatorFailure(f"operator index must be an int, got {value!r}")
    if value < 0:
        raise OperatorFailure(f"operator index must be >= 0, got {value}")
    return value


def _product(
    candidate: Candidate, messages: tuple[Message, ...], operator: str
) -> Candidate:
    """Build the operator-labeled product or fail closed on an empty one."""
    if not messages:
        raise OperatorFailure(f"{operator} would empty the candidate")
    for message in messages:
        if not isinstance(message, Message):
            raise OperatorFailure(f"{operator} product messages must be Message instances")
        if not message.content:
            raise OperatorFailure(f"{operator} would leave a message with empty content")
    return Candidate(
        messages=messages,
        placement=candidate.placement,
        proposal_mode=operator,
        role=candidate.role,
    )
