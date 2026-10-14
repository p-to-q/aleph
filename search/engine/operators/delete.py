"""Delete operator: remove one message by index (``proposal_mode`` ``delete``).

Deterministic and code-point level: the message tuple order is the only input
that matters, and content is never inspected, so any Unicode content — CJK,
emoji, combining sequences — is carried through byte-for-byte.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from ._common import OperatorFailure, _check_index, _product, _require_candidate
from ..contracts import Candidate

OPERATOR = "delete"


@dataclass(frozen=True)
class DeleteSpec:
    """Remove ``candidate.messages[index]``; the rest keeps its order."""

    index: int
    operator: str = OPERATOR

    def __post_init__(self) -> None:
        if self.operator != OPERATOR:
            raise OperatorFailure(
                f"delete spec requires operator label {OPERATOR!r}, got {self.operator!r}"
            )
        object.__setattr__(self, "index", _check_index(self.index))

    def to_canonical(self) -> dict[str, Any]:
        return {"operator": OPERATOR, "index": self.index}

    def apply(self, candidate: Candidate) -> Candidate:
        candidate = _require_candidate(candidate)
        messages = candidate.messages
        if self.index >= len(messages):
            raise OperatorFailure(
                f"delete index {self.index} out of range for {len(messages)} messages"
            )
        if len(messages) == 1:
            raise OperatorFailure("delete would empty the candidate")
        return _product(candidate, messages[: self.index] + messages[self.index + 1 :], OPERATOR)


def delete_spec_from_canonical(payload: Mapping[str, Any]) -> DeleteSpec:
    """Rebuild a ``DeleteSpec`` from its canonical form, rejecting unknown fields."""
    if not isinstance(payload, Mapping):
        raise OperatorFailure("delete spec payload must be a mapping")
    unknown = set(payload) - {"operator", "index"}
    if unknown:
        raise OperatorFailure(f"delete spec has unknown fields: {sorted(unknown)}")
    if "operator" not in payload or "index" not in payload:
        raise OperatorFailure("delete spec is missing required field 'operator' or 'index'")
    return DeleteSpec(operator=payload["operator"], index=payload["index"])
