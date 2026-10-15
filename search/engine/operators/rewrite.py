"""Rewrite operator: deterministic textual rewrite of one message (``rewrite``).

No model is consulted: a rewrite is one named, purely textual transform with a
pinned definition, so the same spec and candidate always produce the same
product. All transforms are Unicode-aware and code-point level:

- ``strip``: remove leading/trailing Unicode whitespace;
- ``collapse_whitespace``: collapse every whitespace run (including newlines)
  to a single space, then strip edges;
- ``dedent``: ``textwrap.dedent``, then strip edges;
- ``lowercase``: ``str.lower`` (locale-independent; CJK and emoji are inert).

A transform whose result is empty fails closed with ``OperatorFailure``.
"""

from __future__ import annotations

import re
import textwrap
from dataclasses import dataclass
from typing import Any, Mapping

from ._common import OperatorFailure, _check_index, _product, _require_candidate
from ..contracts import Candidate, Message

OPERATOR = "rewrite"

REWRITE_TRANSFORMS = ("strip", "collapse_whitespace", "dedent", "lowercase")

_WHITESPACE_RUN = re.compile(r"\s+")


def _transform(transform: str, content: str) -> str:
    if transform == "strip":
        return content.strip()
    if transform == "collapse_whitespace":
        return _WHITESPACE_RUN.sub(" ", content).strip()
    if transform == "dedent":
        return textwrap.dedent(content).strip()
    if transform == "lowercase":
        return content.lower()
    raise OperatorFailure(f"unknown rewrite transform: {transform!r}")


@dataclass(frozen=True)
class RewriteSpec:
    """Replace ``candidate.messages[index].content`` with a named transform."""

    index: int
    transform: str
    operator: str = OPERATOR

    def __post_init__(self) -> None:
        if self.operator != OPERATOR:
            raise OperatorFailure(
                f"rewrite spec requires operator label {OPERATOR!r}, got {self.operator!r}"
            )
        object.__setattr__(self, "index", _check_index(self.index))
        if self.transform not in REWRITE_TRANSFORMS:
            raise OperatorFailure(
                f"unknown rewrite transform {self.transform!r}; "
                f"available: {list(REWRITE_TRANSFORMS)}"
            )

    def to_canonical(self) -> dict[str, Any]:
        return {"operator": OPERATOR, "index": self.index, "transform": self.transform}

    def apply(self, candidate: Candidate) -> Candidate:
        candidate = _require_candidate(candidate)
        messages = candidate.messages
        if self.index >= len(messages):
            raise OperatorFailure(
                f"rewrite index {self.index} out of range for {len(messages)} messages"
            )
        rewritten = _transform(self.transform, messages[self.index].content)
        product = (
            messages[: self.index]
            + (Message(role=messages[self.index].role, content=rewritten),)
            + messages[self.index + 1 :]
        )
        return _product(candidate, product, OPERATOR)


def rewrite_spec_from_canonical(payload: Mapping[str, Any]) -> RewriteSpec:
    """Rebuild a ``RewriteSpec`` from its canonical form, rejecting unknown fields."""
    if not isinstance(payload, Mapping):
        raise OperatorFailure("rewrite spec payload must be a mapping")
    unknown = set(payload) - {"operator", "index", "transform"}
    if unknown:
        raise OperatorFailure(f"rewrite spec has unknown fields: {sorted(unknown)}")
    missing = {"operator", "index", "transform"} - set(payload)
    if missing:
        raise OperatorFailure(f"rewrite spec is missing required fields: {sorted(missing)}")
    return RewriteSpec(
        operator=payload["operator"], index=payload["index"], transform=payload["transform"]
    )
