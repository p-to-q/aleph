from __future__ import annotations

import hashlib
import itertools
import json
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from types import MappingProxyType
from typing import Any, Iterable, Iterator, Mapping, Sequence


SCHEMA_VERSION = "bounded-coordinate-problem/v0"
RECEIPT_VERSION = "bounded-coordinate-receipt/v0"


def canonical_json(value: object) -> str:
    """Serialize a scientific object for hashing, without presentation whitespace."""
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_json(value: object) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )


def _require_exact_keys(value: Mapping[str, Any], expected: set[str], path: str) -> None:
    actual = set(value)
    if actual != expected:
        missing = sorted(expected - actual)
        extra = sorted(actual - expected)
        raise ValueError(f"{path} keys mismatch; missing={missing}, extra={extra}")


def _require_bit_string(value: object, path: str, *, length: int | None = None) -> str:
    if not isinstance(value, str) or any(char not in "01" for char in value):
        raise ValueError(f"{path} must be a bit string")
    if length is not None and len(value) != length:
        raise ValueError(f"{path} must have length {length}")
    return value


def _deep_freeze(value: Any) -> Any:
    if isinstance(value, dict):
        return MappingProxyType({key: _deep_freeze(item) for key, item in value.items()})
    if isinstance(value, list):
        return tuple(_deep_freeze(item) for item in value)
    return value


@dataclass(frozen=True)
class ProblemManifest:
    raw: Mapping[str, Any]
    manifest_hash: str
    problem_id: str
    alphabet: tuple[str, ...]
    target: str
    max_coordinate_tokens: int
    compositional_chunks: Mapping[str, str]
    opaque_witness: tuple[str, ...]
    opaque_fallback: str

    @classmethod
    def from_path(cls, path: Path) -> "ProblemManifest":
        raw = json.loads(path.read_text(encoding="utf-8"))
        return cls.from_mapping(raw)

    @classmethod
    def from_mapping(cls, raw: object) -> "ProblemManifest":
        if not isinstance(raw, dict):
            raise ValueError("manifest must be an object")
        raw = json.loads(canonical_json(raw))
        _require_exact_keys(
            raw,
            {
                "schemaVersion",
                "id",
                "alphabet",
                "target",
                "maxCoordinateTokens",
                "cost",
                "fit",
                "landscapes",
            },
            "manifest",
        )
        if raw["schemaVersion"] != SCHEMA_VERSION:
            raise ValueError(f"unsupported schemaVersion: {raw['schemaVersion']!r}")
        problem_id = raw["id"]
        if not isinstance(problem_id, str) or not problem_id:
            raise ValueError("manifest.id must be a non-empty string")
        alphabet_raw = raw["alphabet"]
        if not isinstance(alphabet_raw, list) or not alphabet_raw:
            raise ValueError("manifest.alphabet must be a non-empty array")
        if any(not isinstance(token, str) or not token for token in alphabet_raw):
            raise ValueError("manifest.alphabet tokens must be non-empty strings")
        alphabet = tuple(alphabet_raw)
        if len(set(alphabet)) != len(alphabet):
            raise ValueError("manifest.alphabet tokens must be unique")
        target = _require_bit_string(raw["target"], "manifest.target")
        if not target:
            raise ValueError("manifest.target must be non-empty")
        max_tokens = raw["maxCoordinateTokens"]
        if isinstance(max_tokens, bool) or not isinstance(max_tokens, int) or max_tokens < 0:
            raise ValueError("manifest.maxCoordinateTokens must be a non-negative integer")
        cost = raw["cost"]
        if cost != {"unit": "coordinate_token", "formula": "len(tokens)"}:
            raise ValueError("manifest.cost must use the v0 coordinate-token contract")
        fit = raw["fit"]
        if fit != {
            "id": "aligned_exact_bit_matches_v1",
            "denominator": "max_target_output_length",
            "missingOrExtraPositionsMismatch": True,
        }:
            raise ValueError("manifest.fit must match the v1 aligned-bit contract")
        landscapes = raw["landscapes"]
        if not isinstance(landscapes, dict) or set(landscapes) != {"compositional", "opaque"}:
            raise ValueError("manifest.landscapes must define compositional and opaque")
        cls._validate_compositional(landscapes["compositional"], alphabet)
        cls._validate_opaque(landscapes["opaque"], alphabet, target, max_tokens)
        compositional_chunks = MappingProxyType(
            dict(landscapes["compositional"]["chunks"])
        )
        opaque_witness = tuple(landscapes["opaque"]["witness"])
        opaque_fallback = landscapes["opaque"]["fallback"]
        return cls(
            raw=_deep_freeze(raw),
            manifest_hash=sha256_json(raw),
            problem_id=problem_id,
            alphabet=alphabet,
            target=target,
            max_coordinate_tokens=max_tokens,
            compositional_chunks=compositional_chunks,
            opaque_witness=opaque_witness,
            opaque_fallback=opaque_fallback,
        )

    @staticmethod
    def _validate_compositional(value: object, alphabet: tuple[str, ...]) -> None:
        if not isinstance(value, dict):
            raise ValueError("compositional landscape must be an object")
        _require_exact_keys(value, {"type", "chunks"}, "compositional")
        if value["type"] != "chunk_concat":
            raise ValueError("compositional.type must be chunk_concat")
        chunks = value["chunks"]
        if not isinstance(chunks, dict) or set(chunks) != set(alphabet):
            raise ValueError("compositional.chunks must cover the alphabet exactly")
        chunk_lengths = {
            len(_require_bit_string(chunks[token], f"compositional.chunks.{token}"))
            for token in alphabet
        }
        if len(chunk_lengths) != 1 or next(iter(chunk_lengths)) == 0:
            raise ValueError("compositional chunks must have one positive fixed length")

    @staticmethod
    def _validate_opaque(
        value: object,
        alphabet: tuple[str, ...],
        target: str,
        max_tokens: int,
    ) -> None:
        if not isinstance(value, dict):
            raise ValueError("opaque landscape must be an object")
        _require_exact_keys(value, {"type", "witness", "fallback"}, "opaque")
        if value["type"] != "exact_lookup":
            raise ValueError("opaque.type must be exact_lookup")
        witness = value["witness"]
        if (
            not isinstance(witness, list)
            or not witness
            or len(witness) > max_tokens
            or any(token not in alphabet for token in witness)
        ):
            raise ValueError("opaque.witness must be a non-empty in-alphabet coordinate")
        fallback = _require_bit_string(value["fallback"], "opaque.fallback", length=len(target))
        if fallback == target:
            raise ValueError("opaque.fallback must not reconstruct the target")


@dataclass(frozen=True)
class PublicSearchSpace:
    alphabet: tuple[str, ...]
    max_coordinate_tokens: int

    @classmethod
    def from_manifest(cls, manifest: ProblemManifest) -> "PublicSearchSpace":
        return cls(
            alphabet=manifest.alphabet,
            max_coordinate_tokens=manifest.max_coordinate_tokens,
        )

    @property
    def content_hash(self) -> str:
        return sha256_json(
            {
                "alphabet": list(self.alphabet),
                "maxCoordinateTokens": self.max_coordinate_tokens,
            }
        )


@dataclass(frozen=True)
class CandidateObservation:
    id: str
    landscape: str
    coordinate: tuple[str, ...]
    length: int
    output: str
    matches: int
    target_length: int
    output_length: int
    comparison_length: int
    exact: bool

    @property
    def fit(self) -> float:
        return self.matches / self.comparison_length

    def to_json(self) -> dict[str, object]:
        return {
            "id": self.id,
            "landscape": self.landscape,
            "coordinate": list(self.coordinate),
            "length": self.length,
            "output": self.output,
            "matches": self.matches,
            "targetLength": self.target_length,
            "outputLength": self.output_length,
            "comparisonLength": self.comparison_length,
            "fit": self.fit,
            "exact": self.exact,
        }


def coordinates_of_length(alphabet: Sequence[str], length: int) -> Iterator[tuple[str, ...]]:
    if length < 0:
        raise ValueError("coordinate length must be non-negative")
    yield from itertools.product(alphabet, repeat=length)


def all_coordinates(alphabet: Sequence[str], max_length: int) -> Iterator[tuple[str, ...]]:
    if max_length < 0:
        raise ValueError("max_length must be non-negative")
    for length in range(max_length + 1):
        yield from coordinates_of_length(alphabet, length)


def bounded_domain_size(
    alphabet_size: int,
    max_length: int,
    *,
    stop_after: int | None = None,
) -> int:
    if alphabet_size <= 0:
        raise ValueError("alphabet_size must be positive")
    if max_length < 0:
        raise ValueError("max_length must be non-negative")
    if stop_after is not None and stop_after < 0:
        raise ValueError("stop_after must be non-negative")
    if alphabet_size == 1:
        exact = max_length + 1
        return exact if stop_after is None or exact <= stop_after else stop_after + 1

    total = 0
    term = 1
    for _ in range(max_length + 1):
        total += term
        if stop_after is not None and total > stop_after:
            return stop_after + 1
        term *= alphabet_size
    return total


def decode(manifest: ProblemManifest, landscape: str, coordinate: Sequence[str]) -> str:
    if landscape not in {"compositional", "opaque"}:
        raise ValueError(f"unknown landscape: {landscape}")
    coordinate_tuple = tuple(coordinate)
    if len(coordinate_tuple) > manifest.max_coordinate_tokens:
        raise ValueError("coordinate exceeds the declared length bound")
    if any(token not in manifest.alphabet for token in coordinate_tuple):
        raise ValueError("coordinate contains a token outside the declared alphabet")
    if landscape == "compositional":
        return "".join(manifest.compositional_chunks[token] for token in coordinate_tuple)
    return (
        manifest.target
        if coordinate_tuple == manifest.opaque_witness
        else manifest.opaque_fallback
    )


def aligned_matches(target: str, output: str) -> int:
    return sum(
        1
        for index in range(max(len(target), len(output)))
        if index < len(target) and index < len(output) and target[index] == output[index]
    )


def candidate_id(manifest: ProblemManifest, landscape: str, coordinate: Sequence[str]) -> str:
    identity = {
        "manifestContentSha256": manifest.manifest_hash,
        "landscape": landscape,
        "coordinate": list(coordinate),
    }
    return f"candidate-{sha256_json(identity)}"


def evaluate(
    manifest: ProblemManifest,
    landscape: str,
    coordinate: Sequence[str],
) -> CandidateObservation:
    coordinate_tuple = tuple(coordinate)
    output = decode(manifest, landscape, coordinate_tuple)
    matches = aligned_matches(manifest.target, output)
    comparison_length = max(len(manifest.target), len(output))
    return CandidateObservation(
        id=candidate_id(manifest, landscape, coordinate_tuple),
        landscape=landscape,
        coordinate=coordinate_tuple,
        length=len(coordinate_tuple),
        output=output,
        matches=matches,
        target_length=len(manifest.target),
        output_length=len(output),
        comparison_length=comparison_length,
        exact=output == manifest.target,
    )


def enumerate_landscape(
    manifest: ProblemManifest,
    landscape: str,
) -> list[CandidateObservation]:
    return [
        evaluate(manifest, landscape, coordinate)
        for coordinate in all_coordinates(manifest.alphabet, manifest.max_coordinate_tokens)
    ]


def observed_frontier(
    observations: Iterable[CandidateObservation],
) -> list[CandidateObservation]:
    """Select strict length/fit improvements without rewriting observations."""
    best_by_length: dict[int, CandidateObservation] = {}
    for observation in observations:
        incumbent = best_by_length.get(observation.length)
        key = (-Fraction(observation.matches, observation.comparison_length), observation.id)
        if incumbent is None or key < (
            -Fraction(incumbent.matches, incumbent.comparison_length),
            incumbent.id,
        ):
            best_by_length[observation.length] = observation
    frontier: list[CandidateObservation] = []
    best_fit = Fraction(-1, 1)
    for observation in sorted(best_by_length.values(), key=lambda item: item.length):
        observation_fit = Fraction(observation.matches, observation.comparison_length)
        if observation_fit > best_fit:
            frontier.append(observation)
            best_fit = observation_fit
    return frontier


def exact_optimum(observations: Iterable[CandidateObservation]) -> CandidateObservation:
    exact = [observation for observation in observations if observation.exact]
    if not exact:
        raise ValueError("bounded domain contains no exact witness")
    return min(exact, key=lambda item: (item.length, item.id))


def budget_value_curve(
    observations: Iterable[CandidateObservation],
    max_budget: int,
) -> list[dict[str, object]]:
    """Return budget/witness records; never impersonate them as observations."""
    archive = list(observations)
    curve = []
    for budget in range(max_budget + 1):
        eligible = [item for item in archive if item.length <= budget]
        if not eligible:
            continue
        witness = min(
            eligible,
            key=lambda item: (
                -Fraction(item.matches, item.comparison_length),
                item.length,
                item.id,
            ),
        )
        curve.append(
            {
                "coordinateTokenBudget": budget,
                "witnessCandidateId": witness.id,
                "witnessLength": witness.length,
                "matches": witness.matches,
                "targetLength": witness.target_length,
                "outputLength": witness.output_length,
                "comparisonLength": witness.comparison_length,
                "fit": witness.fit,
                "exact": witness.exact,
            }
        )
    return curve
