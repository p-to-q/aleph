"""Deterministic candidate operators for hybrid search (PR B).

Four frozen proposal modes get pure, replayable text operators: ``delete``,
``rewrite``, ``repair``, and ``reference``. An operator maps a ``Candidate``
to a new ``Candidate`` carrying the operator's own ``proposal_mode`` label and
the input's placement and role. Operators work at the code-point level and
must not destroy emoji join sequences (ZWJ U+200D / ZWNJ U+200C are never
stripped). Every operator rejects an empty product — no messages at all, or
any message whose content becomes empty — with a typed ``OperatorFailure``.

The ``seed`` proposal mode has no operator here: seeds come from fixtures and
proposal adapters, never from these transforms.

Specs are frozen dataclasses with strict ``*_from_canonical`` parsers, so a
scheduler's frozen configuration can declare them, rebuild them, and replay
them byte-for-byte. Pure standard library; no MLX, no network.
"""

from __future__ import annotations

from typing import Any, Callable, Mapping, Protocol, runtime_checkable

from ._common import OPERATOR_LABELS, OperatorFailure
from ..contracts import Candidate
from .delete import DeleteSpec, delete_spec_from_canonical
from .reference import REFERENCE_AT, ReferenceSpec, reference_spec_from_canonical
from .repair import REPAIR_KINDS, RepairSpec, repair_spec_from_canonical
from .rewrite import REWRITE_TRANSFORMS, RewriteSpec, rewrite_spec_from_canonical

OPERATOR_SCHEMA_VERSION = "aleph-engine-operators/0.1.0"

__all__ = [
    "OPERATOR_LABELS",
    "OPERATOR_SCHEMA_VERSION",
    "OPERATOR_SPEC_BUILDERS",
    "OperatorFailure",
    "OperatorSpec",
    "apply_operator",
    "operator_spec_from_canonical",
    "DeleteSpec",
    "delete_spec_from_canonical",
    "RewriteSpec",
    "rewrite_spec_from_canonical",
    "REWRITE_TRANSFORMS",
    "RepairSpec",
    "repair_spec_from_canonical",
    "REPAIR_KINDS",
    "ReferenceSpec",
    "reference_spec_from_canonical",
    "REFERENCE_AT",
]


@runtime_checkable
class OperatorSpec(Protocol):
    """Structural contract shared by all operator specs."""

    operator: str

    def to_canonical(self) -> dict[str, Any]: ...

    def apply(self, candidate: Candidate) -> Candidate: ...


OPERATOR_SPEC_BUILDERS: dict[str, Callable[[Mapping[str, Any]], OperatorSpec]] = {
    "delete": delete_spec_from_canonical,
    "rewrite": rewrite_spec_from_canonical,
    "repair": repair_spec_from_canonical,
    "reference": reference_spec_from_canonical,
}
"""Strict canonical parsers keyed by operator label, used by the scheduler."""


def operator_spec_from_canonical(payload: Mapping[str, Any]) -> OperatorSpec:
    """Rebuild an operator spec from its canonical form.

    Dispatches on the declared ``operator`` label. Unknown labels — including
    ``seed``, which has no deterministic operator — fail closed.
    """
    if not isinstance(payload, Mapping):
        raise OperatorFailure("operator spec payload must be a mapping")
    if "operator" not in payload:
        raise OperatorFailure("operator spec is missing required field 'operator'")
    label = payload["operator"]
    if not isinstance(label, str) or not label:
        raise OperatorFailure("operator spec 'operator' must be a non-empty str")
    builder = OPERATOR_SPEC_BUILDERS.get(label)
    if builder is None:
        raise OperatorFailure(f"unknown operator: {label!r}")
    return builder(payload)


def apply_operator(spec: Any, candidate: Candidate) -> Candidate:
    """Apply one operator spec to a candidate with typed boundary checks."""
    if not isinstance(spec, OperatorSpec) or spec.operator not in OPERATOR_LABELS:
        raise OperatorFailure(
            f"apply_operator requires an operator spec, got {type(spec).__name__}"
        )
    if not isinstance(candidate, Candidate):
        raise OperatorFailure(
            f"apply_operator requires a Candidate, got {type(candidate).__name__}"
        )
    return spec.apply(candidate)
