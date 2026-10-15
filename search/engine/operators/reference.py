"""Reference operator: splice source messages into a candidate (``reference``).

A reference product is the input candidate with declared source messages
prepended, appended, or inserted at a position. The source is carried in the
spec itself, so the operator stays deterministic: same spec, same product.
Reference is the only operator whose product is built from two declared
message sequences; it never invents content.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from ._common import OperatorFailure, _check_index, _product, _require_candidate
from ..contracts import Candidate, ContractViolation, Message, message_from_canonical

OPERATOR = "reference"

REFERENCE_AT = ("prepend", "append", "insert")


@dataclass(frozen=True)
class ReferenceSpec:
    """Splice ``source_messages`` into a candidate.

    ``index`` is only meaningful for ``at="insert"`` (0..len(messages)); for
    ``prepend`` and ``append`` it must be 0 so a spec never carries a
    position that would be silently ignored.
    """

    source_messages: tuple[Message, ...]
    at: str
    index: int = 0
    operator: str = OPERATOR

    def __post_init__(self) -> None:
        if self.operator != OPERATOR:
            raise OperatorFailure(
                f"reference spec requires operator label {OPERATOR!r}, got {self.operator!r}"
            )
        if self.at not in REFERENCE_AT:
            raise OperatorFailure(
                f"unknown reference placement {self.at!r}; available: {list(REFERENCE_AT)}"
            )
        object.__setattr__(self, "index", _check_index(self.index))
        if self.at != "insert" and self.index != 0:
            raise OperatorFailure(
                f"reference index is only used with 'insert', got at={self.at!r} index={self.index}"
            )
        source = self.source_messages
        if not isinstance(source, tuple) or not source:
            raise OperatorFailure("reference requires a non-empty tuple of source messages")
        if not all(isinstance(message, Message) for message in source):
            raise OperatorFailure("reference source must be Message instances")
        if any(not message.content for message in source):
            raise OperatorFailure("reference source messages must have non-empty content")

    def to_canonical(self) -> dict[str, Any]:
        return {
            "operator": OPERATOR,
            "at": self.at,
            "index": self.index,
            "sourceMessages": [message.to_canonical() for message in self.source_messages],
        }

    def apply(self, candidate: Candidate) -> Candidate:
        candidate = _require_candidate(candidate)
        current = candidate.messages
        if self.at == "prepend":
            product = self.source_messages + current
        elif self.at == "append":
            product = current + self.source_messages
        else:
            if self.index > len(current):
                raise OperatorFailure(
                    f"reference insert index {self.index} out of range for {len(current)} messages"
                )
            product = current[: self.index] + self.source_messages + current[self.index :]
        return _product(candidate, product, OPERATOR)


def reference_spec_from_canonical(payload: Mapping[str, Any]) -> ReferenceSpec:
    """Rebuild a ``ReferenceSpec`` from its canonical form, rejecting unknown fields."""
    if not isinstance(payload, Mapping):
        raise OperatorFailure("reference spec payload must be a mapping")
    unknown = set(payload) - {"operator", "at", "index", "sourceMessages"}
    if unknown:
        raise OperatorFailure(f"reference spec has unknown fields: {sorted(unknown)}")
    missing = {"operator", "at", "index", "sourceMessages"} - set(payload)
    if missing:
        raise OperatorFailure(f"reference spec is missing required fields: {sorted(missing)}")
    source = payload["sourceMessages"]
    if not isinstance(source, list) or not source:
        raise OperatorFailure("reference sourceMessages must be a non-empty list")
    parsed: list[Message] = []
    for item in source:
        if not isinstance(item, Mapping):
            raise OperatorFailure("reference sourceMessages items must be mappings")
        try:
            parsed.append(message_from_canonical(item))
        except ContractViolation as exc:
            raise OperatorFailure(f"reference sourceMessages item: {exc}") from exc
    return ReferenceSpec(
        source_messages=tuple(parsed),
        at=payload["at"],
        index=payload["index"],
        operator=payload["operator"],
    )
