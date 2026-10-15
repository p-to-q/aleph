"""Repair operator: deterministic structural repair of one message (``repair``).

Each repair kind is a pinned, purely textual normalization:

- ``normalize_line_endings``: CRLF and lone CR become LF;
- ``strip_zero_width``: remove invisible zero-width separators U+200B,
  U+2060, and U+FEFF — never U+200D/U+200C, because emoji join sequences
  (for example the family emoji) depend on them;
- ``remove_control_chars``: remove C0/C1 control code points except LF, TAB,
  and CR;
- ``collapse_blank_lines``: collapse every run of blank lines (lines that are
  empty or contain only spaces/tabs) to a single blank line.

A repair whose result is empty fails closed with ``OperatorFailure``.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Any, Mapping

from ._common import OperatorFailure, _check_index, _product, _require_candidate
from ..contracts import Candidate, Message

OPERATOR = "repair"

REPAIR_KINDS = (
    "normalize_line_endings",
    "strip_zero_width",
    "remove_control_chars",
    "collapse_blank_lines",
)

_ZERO_WIDTH_SEPARATORS = frozenset("\u200b\u2060\ufeff")
_CONTROL_CHARS_KEPT = frozenset("\n\t\r")
_BLANK_LINE_RUN = re.compile(r"\n[ \t]*\n(?:[ \t]*\n)+")


def _repair_text(repair: str, content: str) -> str:
    if repair == "normalize_line_endings":
        return content.replace("\r\n", "\n").replace("\r", "\n")
    if repair == "strip_zero_width":
        return "".join(ch for ch in content if ch not in _ZERO_WIDTH_SEPARATORS)
    if repair == "remove_control_chars":
        return "".join(
            ch for ch in content if ch in _CONTROL_CHARS_KEPT or unicodedata.category(ch) != "Cc"
        )
    if repair == "collapse_blank_lines":
        return _BLANK_LINE_RUN.sub("\n\n", content)
    raise OperatorFailure(f"unknown repair kind: {repair!r}")


@dataclass(frozen=True)
class RepairSpec:
    """Apply one named structural repair to ``candidate.messages[index].content``."""

    index: int
    repair: str
    operator: str = OPERATOR

    def __post_init__(self) -> None:
        if self.operator != OPERATOR:
            raise OperatorFailure(
                f"repair spec requires operator label {OPERATOR!r}, got {self.operator!r}"
            )
        object.__setattr__(self, "index", _check_index(self.index))
        if self.repair not in REPAIR_KINDS:
            raise OperatorFailure(
                f"unknown repair kind {self.repair!r}; available: {list(REPAIR_KINDS)}"
            )

    def to_canonical(self) -> dict[str, Any]:
        return {"operator": OPERATOR, "index": self.index, "repair": self.repair}

    def apply(self, candidate: Candidate) -> Candidate:
        candidate = _require_candidate(candidate)
        messages = candidate.messages
        if self.index >= len(messages):
            raise OperatorFailure(
                f"repair index {self.index} out of range for {len(messages)} messages"
            )
        repaired = _repair_text(self.repair, messages[self.index].content)
        product = (
            messages[: self.index]
            + (Message(role=messages[self.index].role, content=repaired),)
            + messages[self.index + 1 :]
        )
        return _product(candidate, product, OPERATOR)


def repair_spec_from_canonical(payload: Mapping[str, Any]) -> RepairSpec:
    """Rebuild a ``RepairSpec`` from its canonical form, rejecting unknown fields."""
    if not isinstance(payload, Mapping):
        raise OperatorFailure("repair spec payload must be a mapping")
    unknown = set(payload) - {"operator", "index", "repair"}
    if unknown:
        raise OperatorFailure(f"repair spec has unknown fields: {sorted(unknown)}")
    missing = {"operator", "index", "repair"} - set(payload)
    if missing:
        raise OperatorFailure(f"repair spec is missing required fields: {sorted(missing)}")
    return RepairSpec(operator=payload["operator"], index=payload["index"], repair=payload["repair"])
