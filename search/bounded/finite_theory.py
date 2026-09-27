from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


THEORY_SCHEMA_VERSION = "finite-theory-manifest/v0"
ENCODING_KIND = "typed-fixed-width-length-prefix/v0"
InfinityNat = int | None
MAX_MANIFEST_BYTES = 2_000_000
MAX_IDENTIFIER_LENGTH = 512
MAX_BIT_STRING_LENGTH = 4_096
MAX_LENGTH_WIDTH = 16
MAX_COLLECTION_ITEMS = 10_000
MAX_COORDINATES_PER_SYSTEM = 512
MAX_ROLE_TAGS = 512
MAX_THEORY_GRID_CELLS = 1_000_000
MAX_THEORY_SCALAR = 1_024
MAX_THEORY_WORK = 1_000_000
MAX_EVIDENCE_PAIRS = 10_000


def canonical_json(value: object) -> str:
    """Return the canonical UTF-8 JSON spelling used by scientific digests."""
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_json(value: object) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _strict_json_loads(source: str) -> object:
    def object_hook(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"duplicate JSON object key: {key!r}")
            result[key] = value
        return result

    def reject_constant(value: str) -> object:
        raise ValueError(f"non-finite JSON number is forbidden: {value}")

    return json.loads(
        source,
        object_pairs_hook=object_hook,
        parse_constant=reject_constant,
    )


def _object(value: object, path: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{path} must be an object")
    return value


def _exact_keys(value: Mapping[str, Any], expected: set[str], path: str) -> None:
    actual = set(value)
    if actual != expected:
        raise ValueError(
            f"{path} keys mismatch; missing={sorted(expected - actual)}, "
            f"extra={sorted(actual - expected)}"
        )


def _string(value: object, path: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{path} must be a non-empty string")
    if len(value) > MAX_IDENTIFIER_LENGTH:
        raise ValueError(f"{path} exceeds the maximum string length")
    return value


def _nat(value: object, path: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{path} must be a non-negative exact integer")
    if value > MAX_THEORY_SCALAR:
        raise ValueError(f"{path} exceeds the finite-theory scalar limit")
    return value


def _bits(value: object, path: str, *, allow_empty: bool = True) -> str:
    if not isinstance(value, str) or any(bit not in "01" for bit in value):
        raise ValueError(f"{path} must be a bit string")
    if not allow_empty and not value:
        raise ValueError(f"{path} must not be empty")
    if len(value) > MAX_BIT_STRING_LENGTH:
        raise ValueError(f"{path} exceeds the bit-string limit")
    return value


def _unique_strings(
    value: object,
    path: str,
    *,
    allow_empty: bool = False,
) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise ValueError(f"{path} must be an array")
    if len(value) > MAX_COLLECTION_ITEMS:
        raise ValueError(f"{path} exceeds the finite collection limit")
    result = tuple(
        _string(item, f"{path}[{index}]") for index, item in enumerate(value)
    )
    if not allow_empty and not result:
        raise ValueError(f"{path} must not be empty")
    if len(set(result)) != len(result):
        raise ValueError(f"{path} must not contain duplicates")
    return result


def _is_prefix(left: str, right: str) -> bool:
    return len(left) <= len(right) and right.startswith(left)


def inf_le(left: InfinityNat, right: InfinityNat) -> bool:
    """Order naturals extended by None as positive infinity."""
    if right is None:
        return True
    if left is None:
        return False
    return left <= right


def inf_add(value: InfinityNat, amount: int) -> InfinityNat:
    _nat(amount, "amount")
    return None if value is None else value + amount


@dataclass(frozen=True)
class EncodingSpec:
    length_width: int
    role_tags: tuple[tuple[str, str], ...]

    @classmethod
    def from_mapping(cls, value: object, path: str) -> "EncodingSpec":
        raw = _object(value, path)
        _exact_keys(raw, {"kind", "lengthWidth", "roleTags"}, path)
        if raw["kind"] != ENCODING_KIND:
            raise ValueError(f"{path}.kind must be {ENCODING_KIND!r}")
        width = _nat(raw["lengthWidth"], f"{path}.lengthWidth")
        if width == 0:
            raise ValueError(f"{path}.lengthWidth must be positive")
        if width > MAX_LENGTH_WIDTH:
            raise ValueError(f"{path}.lengthWidth exceeds the safe encoding limit")
        tags_raw = _object(raw["roleTags"], f"{path}.roleTags")
        if not tags_raw:
            raise ValueError(f"{path}.roleTags must not be empty")
        if len(tags_raw) > MAX_ROLE_TAGS:
            raise ValueError(f"{path}.roleTags exceeds the finite collection limit")
        if len(tags_raw) > MAX_COLLECTION_ITEMS:
            raise ValueError(f"{path}.roleTags exceeds the finite collection limit")
        tags = tuple(
            sorted(
                (
                    _string(role, f"{path}.roleTags key"),
                    _bits(tag, f"{path}.roleTags.{role}", allow_empty=False),
                )
                for role, tag in tags_raw.items()
            )
        )
        tag_values = [tag for _, tag in tags]
        for index, left in enumerate(tag_values):
            for right in tag_values[index + 1 :]:
                if _is_prefix(left, right) or _is_prefix(right, left):
                    raise ValueError(f"{path}.roleTags must be prefix-free")
        return cls(width, tags)

    def role_tag(self, role: str) -> str:
        for declared_role, tag in self.role_tags:
            if declared_role == role:
                return tag
        raise ValueError(f"unknown encoding role: {role!r}")

    def encode(self, role: str, payload_bits: str) -> str:
        payload = _bits(payload_bits, "payload_bits")
        maximum_length = (1 << self.length_width) - 1
        if len(payload) > maximum_length:
            raise ValueError(
                f"payload length {len(payload)} exceeds {maximum_length} for "
                f"a {self.length_width}-bit length field"
            )
        return (
            self.role_tag(role)
            + format(len(payload), f"0{self.length_width}b")
            + payload
        )

    def render(self, role: str, payload_bits: str) -> str:
        _bits(payload_bits, "payload_bits")
        self.role_tag(role)
        return f"{role}:{payload_bits}"

    def to_json(self) -> dict[str, object]:
        return {
            "kind": ENCODING_KIND,
            "lengthWidth": self.length_width,
            "roleTags": dict(self.role_tags),
        }


@dataclass(frozen=True)
class Coordinate:
    id: str
    role: str
    payload_bits: str
    code_bits: str
    charged_bit_cost: int
    rendering: str
    residuals: tuple[tuple[str, int], ...]
    objectives: tuple[tuple[str, int], ...]

    @classmethod
    def from_mapping(
        cls,
        value: object,
        *,
        encoding: EncodingSpec,
        targets: Sequence[str],
        objective_names: Sequence[str],
        path: str,
    ) -> "Coordinate":
        raw = _object(value, path)
        _exact_keys(
            raw,
            {
                "id",
                "role",
                "payloadBits",
                "codeBits",
                "chargedBitCost",
                "rendering",
                "residuals",
                "objectives",
            },
            path,
        )
        coordinate_id = _string(raw["id"], f"{path}.id")
        role = _string(raw["role"], f"{path}.role")
        payload = _bits(raw["payloadBits"], f"{path}.payloadBits")
        code = _bits(raw["codeBits"], f"{path}.codeBits", allow_empty=False)
        expected_code = encoding.encode(role, payload)
        if code != expected_code:
            raise ValueError(f"{path}.codeBits does not match the declared encoding")
        cost = _nat(raw["chargedBitCost"], f"{path}.chargedBitCost")
        if cost != len(expected_code):
            raise ValueError(f"{path}.chargedBitCost must charge every encoded bit")
        rendering = _string(raw["rendering"], f"{path}.rendering")
        if rendering != encoding.render(role, payload):
            raise ValueError(f"{path}.rendering is not the lossless declared rendering")
        residuals_raw = _object(raw["residuals"], f"{path}.residuals")
        if set(residuals_raw) != set(targets):
            raise ValueError(f"{path}.residuals must cover every target exactly")
        residuals = tuple(
            (target, _nat(residuals_raw[target], f"{path}.residuals.{target}"))
            for target in targets
        )
        objectives_raw = _object(raw["objectives"], f"{path}.objectives")
        if set(objectives_raw) != set(objective_names):
            raise ValueError(f"{path}.objectives must cover the objective vector exactly")
        objectives = tuple(
            (name, _nat(objectives_raw[name], f"{path}.objectives.{name}"))
            for name in objective_names
        )
        objective_map = dict(objectives)
        if (
            "charged_bit_cost" in objective_map
            and objective_map["charged_bit_cost"] != cost
        ):
            raise ValueError(f"{path}.objectives.charged_bit_cost disagrees with cost")
        for target, residual in residuals:
            name = f"{target}_residual"
            if name in objective_map and objective_map[name] != residual:
                raise ValueError(f"{path}.objectives.{name} disagrees with residual")
        return cls(
            coordinate_id,
            role,
            payload,
            code,
            cost,
            rendering,
            residuals,
            objectives,
        )

    def residual(self, target: str) -> int:
        for target_id, value in self.residuals:
            if target_id == target:
                return value
        raise ValueError(f"coordinate {self.id!r} has no residual for {target!r}")

    @property
    def objective_vector(self) -> tuple[int, ...]:
        return tuple(value for _, value in self.objectives)

    def to_json(self) -> dict[str, object]:
        return {
            "id": self.id,
            "role": self.role,
            "payloadBits": self.payload_bits,
            "codeBits": self.code_bits,
            "chargedBitCost": self.charged_bit_cost,
            "rendering": self.rendering,
            "residuals": dict(self.residuals),
            "objectives": dict(self.objectives),
        }


def is_prefix_free(code_words: Sequence[str]) -> bool:
    words = tuple(code_words)
    if len(words) != len(set(words)):
        return False
    return all(
        not _is_prefix(left, right)
        for left_index, left in enumerate(words)
        for right_index, right in enumerate(words)
        if left_index != right_index
    )


def kraft_sum(code_words: Iterable[str]) -> Fraction:
    total = Fraction(0, 1)
    for index, code_word in enumerate(code_words):
        code = _bits(code_word, f"code_words[{index}]", allow_empty=False)
        total += Fraction(1, 1 << len(code))
    return total


@dataclass(frozen=True)
class FiniteSystem:
    id: str
    targets: tuple[str, ...]
    objective_names: tuple[str, ...]
    encoding: EncodingSpec
    coordinates: tuple[Coordinate, ...]
    declared_content_sha256: str

    @classmethod
    def from_mapping(
        cls,
        value: object,
        *,
        targets: Sequence[str],
        objective_names: Sequence[str],
        path: str,
    ) -> "FiniteSystem":
        raw = _object(value, path)
        _exact_keys(raw, {"id", "encoding", "coordinates", "contentSha256"}, path)
        declared_digest = _string(raw["contentSha256"], f"{path}.contentSha256")
        digest_payload = {key: raw[key] for key in raw if key != "contentSha256"}
        if declared_digest != sha256_json(digest_payload):
            raise ValueError(f"{path}.contentSha256 does not match system content")
        encoding = EncodingSpec.from_mapping(raw["encoding"], f"{path}.encoding")
        coordinates_raw = raw["coordinates"]
        if not isinstance(coordinates_raw, list):
            raise ValueError(f"{path}.coordinates must be an array")
        if len(coordinates_raw) > MAX_COORDINATES_PER_SYSTEM:
            raise ValueError(f"{path}.coordinates exceeds the finite collection limit")
        coordinates = tuple(
            Coordinate.from_mapping(
                item,
                encoding=encoding,
                targets=targets,
                objective_names=objective_names,
                path=f"{path}.coordinates[{index}]",
            )
            for index, item in enumerate(coordinates_raw)
        )
        ids = [coordinate.id for coordinate in coordinates]
        codes = [coordinate.code_bits for coordinate in coordinates]
        renderings = [coordinate.rendering for coordinate in coordinates]
        if len(ids) != len(set(ids)):
            raise ValueError(f"{path}.coordinates contains duplicate IDs")
        if len(codes) != len(set(codes)):
            raise ValueError(f"{path}.coordinates has a non-injective encoding")
        if len(renderings) != len(set(renderings)):
            raise ValueError(f"{path}.coordinates has lossy duplicate renderings")
        if not is_prefix_free(codes):
            raise ValueError(f"{path}.coordinates is not prefix-free")
        if kraft_sum(codes) > 1:
            raise ValueError(f"{path}.coordinates violates the finite Kraft inequality")
        return cls(
            _string(raw["id"], f"{path}.id"),
            tuple(targets),
            tuple(objective_names),
            encoding,
            coordinates,
            declared_digest,
        )

    @property
    def content_sha256(self) -> str:
        return sha256_json(
            {
                "id": self.id,
                "encoding": self.encoding.to_json(),
                "coordinates": [point.to_json() for point in self.coordinates],
            }
        )

    def coordinate(self, coordinate_id: str) -> Coordinate:
        for coordinate in self.coordinates:
            if coordinate.id == coordinate_id:
                return coordinate
        raise ValueError(f"system {self.id!r} has no coordinate {coordinate_id!r}")


@dataclass(frozen=True)
class Archive:
    id: str
    system_id: str
    coordinate_ids: tuple[str, ...]

    @classmethod
    def from_mapping(
        cls,
        value: object,
        *,
        systems: Mapping[str, FiniteSystem],
        path: str,
    ) -> "Archive":
        raw = _object(value, path)
        _exact_keys(raw, {"id", "systemId", "coordinateIds"}, path)
        system_id = _string(raw["systemId"], f"{path}.systemId")
        if system_id not in systems:
            raise ValueError(f"{path}.systemId is unknown")
        coordinate_ids = _unique_strings(
            raw["coordinateIds"],
            f"{path}.coordinateIds",
            allow_empty=True,
        )
        domain_ids = {point.id for point in systems[system_id].coordinates}
        if not set(coordinate_ids).issubset(domain_ids):
            raise ValueError(f"{path}.coordinateIds contains an out-of-domain ID")
        return cls(_string(raw["id"], f"{path}.id"), system_id, coordinate_ids)


@dataclass(frozen=True)
class VerifierSuite:
    id: str
    check_ids: tuple[str, ...]

    @classmethod
    def from_mapping(cls, value: object, path: str) -> "VerifierSuite":
        raw = _object(value, path)
        _exact_keys(raw, {"id", "checkIds"}, path)
        return cls(
            _string(raw["id"], f"{path}.id"),
            _unique_strings(raw["checkIds"], f"{path}.checkIds", allow_empty=True),
        )


def structure(
    coordinates: Iterable[Coordinate],
    target: str,
    budget: int,
) -> InfinityNat:
    _nat(budget, "budget")
    feasible = [
        point.residual(target)
        for point in coordinates
        if point.charged_bit_cost <= budget
    ]
    return min(feasible) if feasible else None


def threshold(
    coordinates: Iterable[Coordinate],
    target: str,
    residual_limit: int,
) -> InfinityNat:
    _nat(residual_limit, "residual_limit")
    feasible = [
        point.charged_bit_cost
        for point in coordinates
        if point.residual(target) <= residual_limit
    ]
    return min(feasible) if feasible else None


def two_part_direct(
    coordinates: Iterable[Coordinate],
    target: str,
) -> InfinityNat:
    values = [
        point.charged_bit_cost + point.residual(target)
        for point in coordinates
    ]
    return min(values) if values else None


def two_part_by_cost_levels(
    coordinates: Iterable[Coordinate],
    target: str,
) -> InfinityNat:
    points = tuple(coordinates)
    values: list[int] = []
    for budget in sorted({point.charged_bit_cost for point in points}):
        residual = structure(points, target, budget)
        if residual is not None:
            values.append(budget + residual)
    return min(values) if values else None


def _target(system: FiniteSystem, target: str) -> None:
    if target not in system.targets:
        raise ValueError(f"unknown target {target!r} for system {system.id!r}")


def check_ft01_threshold_duality(system: FiniteSystem, target: str) -> bool:
    _target(system, target)
    max_cost = max((point.charged_bit_cost for point in system.coordinates), default=0)
    max_residual = max((point.residual(target) for point in system.coordinates), default=0)
    if (max_cost + 2) * (max_residual + 2) > MAX_THEORY_GRID_CELLS:
        raise ValueError("FT-01 exhaustive grid exceeds the finite work limit")
    return all(
        inf_le(structure(system.coordinates, target, budget), residual_limit)
        == inf_le(threshold(system.coordinates, target, residual_limit), budget)
        for budget in range(max_cost + 2)
        for residual_limit in range(max_residual + 2)
    )


def check_ft02_structure_monotonicity(
    system: FiniteSystem,
    target: str,
) -> bool:
    _target(system, target)
    max_cost = max((point.charged_bit_cost for point in system.coordinates), default=0)
    values = [
        structure(system.coordinates, target, budget)
        for budget in range(max_cost + 2)
    ]
    return all(inf_le(later, earlier) for earlier, later in zip(values, values[1:]))


def check_ft03_threshold_monotonicity(
    system: FiniteSystem,
    target: str,
) -> bool:
    _target(system, target)
    max_residual = max((point.residual(target) for point in system.coordinates), default=0)
    values = [
        threshold(system.coordinates, target, residual_limit)
        for residual_limit in range(max_residual + 2)
    ]
    return all(inf_le(later, earlier) for earlier, later in zip(values, values[1:]))


def check_ft04_two_part_identity(system: FiniteSystem, target: str) -> bool:
    _target(system, target)
    return two_part_direct(system.coordinates, target) == two_part_by_cost_levels(
        system.coordinates,
        target,
    )


def check_ft05_archive_upper_bound(
    system: FiniteSystem,
    archive: Archive,
    target: str,
) -> bool:
    _target(system, target)
    if archive.system_id != system.id:
        raise ValueError("archive and system IDs disagree")
    subset = tuple(system.coordinate(item) for item in archive.coordinate_ids)
    max_cost = max((point.charged_bit_cost for point in system.coordinates), default=0)
    return all(
        inf_le(
            structure(system.coordinates, target, budget),
            structure(subset, target, budget),
        )
        for budget in range(max_cost + 2)
    )


def check_ft06_append_only_archive_monotonicity(
    system: FiniteSystem,
    old: Archive,
    new: Archive,
    target: str,
) -> bool:
    _target(system, target)
    if old.system_id != system.id or new.system_id != system.id:
        raise ValueError("archive and system IDs disagree")
    if new.coordinate_ids[: len(old.coordinate_ids)] != old.coordinate_ids:
        raise ValueError("new archive is not an append-only extension")
    old_points = tuple(system.coordinate(item) for item in old.coordinate_ids)
    new_points = tuple(system.coordinate(item) for item in new.coordinate_ids)
    max_cost = max((point.charged_bit_cost for point in new_points), default=0)
    return all(
        inf_le(
            structure(new_points, target, budget),
            structure(old_points, target, budget),
        )
        for budget in range(max_cost + 2)
    )


def suite_accepts(
    suite: VerifierSuite,
    passed_check_ids: Iterable[str],
) -> bool:
    passed = frozenset(passed_check_ids)
    return all(check_id in passed for check_id in suite.check_ids)


def check_ft07_suite_subset_implication(
    larger: VerifierSuite,
    subset: VerifierSuite,
    outcomes: Iterable[Iterable[str]],
) -> bool:
    if not set(subset.check_ids).issubset(larger.check_ids):
        raise ValueError("the declared subset suite is not a subset")
    return all(
        not suite_accepts(larger, outcome) or suite_accepts(subset, outcome)
        for outcome in outcomes
    )


def dominates(left: Coordinate, right: Coordinate) -> bool:
    if len(left.objective_vector) != len(right.objective_vector):
        raise ValueError("objective vectors have different dimensions")
    return all(
        left_value <= right_value
        for left_value, right_value in zip(
            left.objective_vector,
            right.objective_vector,
        )
    ) and any(
        left_value < right_value
        for left_value, right_value in zip(
            left.objective_vector,
            right.objective_vector,
        )
    )


def pareto_frontier(coordinates: Sequence[Coordinate]) -> tuple[Coordinate, ...]:
    """Keep the first source object for each nondominated objective vector."""
    if len(coordinates) > MAX_COORDINATES_PER_SYSTEM:
        raise ValueError("Pareto input exceeds the finite work limit")
    first_by_vector: dict[tuple[int, ...], Coordinate] = {}
    for coordinate in coordinates:
        first_by_vector.setdefault(coordinate.objective_vector, coordinate)
    representatives = tuple(first_by_vector.values())
    return tuple(
        candidate
        for candidate in representatives
        if not any(
            dominates(other, candidate)
            for other in representatives
            if other is not candidate
        )
    )


def check_ft08_pareto_soundness(coordinates: Sequence[Coordinate]) -> bool:
    return all(
        candidate in coordinates
        and not any(
            dominates(other, candidate)
            for other in coordinates
            if other is not candidate
        )
        for candidate in pareto_frontier(coordinates)
    )


def check_ft09_pareto_completeness(coordinates: Sequence[Coordinate]) -> bool:
    frontier = pareto_frontier(coordinates)
    frontier_vectors = [point.objective_vector for point in frontier]
    nondominated_vectors = {
        candidate.objective_vector
        for candidate in coordinates
        if not any(
            dominates(other, candidate)
            for other in coordinates
            if other is not candidate
        )
    }
    if (
        set(frontier_vectors) != nondominated_vectors
        or len(frontier_vectors) != len(set(frontier_vectors))
    ):
        return False
    return all(
        next(point for point in frontier if point.objective_vector == vector)
        is next(point for point in coordinates if point.objective_vector == vector)
        for vector in nondominated_vectors
    )


def _validate_theory_work(manifest: "TheoryManifest") -> None:
    target_count = len(manifest.targets)
    max_coordinates = max(
        (len(system.coordinates) for system in manifest.systems),
        default=0,
    )
    max_cost = max(
        (
            coordinate.charged_bit_cost
            for system in manifest.systems
            for coordinate in system.coordinates
        ),
        default=0,
    )
    max_residual = max(
        (
            coordinate.residual(target)
            for system in manifest.systems
            for coordinate in system.coordinates
            for target in manifest.targets
        ),
        default=0,
    )
    max_suite_width = max(
        (len(suite.check_ids) for suite in manifest.suites),
        default=0,
    )
    archive_pair_count = len(manifest.archives) ** 2
    suite_pair_count = len(manifest.suites) ** 2
    compiler_pair_count = len(manifest.compiler_records) ** 2
    if suite_pair_count > MAX_EVIDENCE_PAIRS:
        raise ValueError("verifier-suite pair count exceeds the evidence limit")
    if compiler_pair_count > MAX_EVIDENCE_PAIRS:
        raise ValueError("compiler pair count exceeds the evidence limit")
    system_work = sum(
        len(system.coordinates) ** 2
        + target_count
        * max(1, len(system.coordinates))
        * (max_cost + 2)
        * (max_residual + 2)
        for system in manifest.systems
    )
    archive_work = (
        archive_pair_count
        * max(1, target_count)
        * max(1, max_coordinates)
        * (max_cost + 2)
    )
    suite_work = (
        suite_pair_count
        * max(1, len(manifest.verification_outcomes))
        * max(1, max_suite_width)
    )
    compiler_work = (
        compiler_pair_count
        * max(1, target_count)
        * max(1, max_coordinates)
        * (max_cost + max_residual + 4)
    )
    total_work = system_work + archive_work + suite_work + compiler_work
    if total_work > MAX_THEORY_WORK:
        raise ValueError(
            "finite-theory work estimate exceeds the executable limit "
            f"({total_work} > {MAX_THEORY_WORK})"
        )


@dataclass(frozen=True)
class TheoryManifest:
    id: str
    targets: tuple[str, ...]
    objective_names: tuple[str, ...]
    systems: tuple[FiniteSystem, ...]
    archives: tuple[Archive, ...]
    suites: tuple[VerifierSuite, ...]
    verification_outcomes: tuple[tuple[str, ...], ...]
    compiler_records: tuple[str, ...]

    @classmethod
    def from_path(cls, path: Path) -> "TheoryManifest":
        source = path.read_bytes()
        if len(source) > MAX_MANIFEST_BYTES:
            raise ValueError("finite-theory manifest exceeds the byte limit")
        return cls.from_mapping(_strict_json_loads(source.decode("utf-8")))

    @classmethod
    def from_mapping(cls, value: object) -> "TheoryManifest":
        raw = _object(value, "manifest")
        _exact_keys(
            raw,
            {
                "schemaVersion",
                "id",
                "targets",
                "objectiveNames",
                "systems",
                "archives",
                "verifierSuites",
                "verificationOutcomes",
                "compilers",
            },
            "manifest",
        )
        if raw["schemaVersion"] != THEORY_SCHEMA_VERSION:
            raise ValueError("unsupported finite-theory schemaVersion")
        targets = _unique_strings(raw["targets"], "manifest.targets")
        objective_names = _unique_strings(
            raw["objectiveNames"],
            "manifest.objectiveNames",
        )
        systems_raw = raw["systems"]
        if not isinstance(systems_raw, list) or not systems_raw:
            raise ValueError("manifest.systems must be a non-empty array")
        if len(systems_raw) > MAX_COLLECTION_ITEMS:
            raise ValueError("manifest.systems exceeds the finite collection limit")
        systems = tuple(
            FiniteSystem.from_mapping(
                item,
                targets=targets,
                objective_names=objective_names,
                path=f"manifest.systems[{index}]",
            )
            for index, item in enumerate(systems_raw)
        )
        system_map = {system.id: system for system in systems}
        if len(system_map) != len(systems):
            raise ValueError("manifest.systems contains duplicate IDs")
        archives_raw = raw["archives"]
        if not isinstance(archives_raw, list):
            raise ValueError("manifest.archives must be an array")
        if len(archives_raw) > MAX_COLLECTION_ITEMS:
            raise ValueError("manifest.archives exceeds the finite collection limit")
        archives = tuple(
            Archive.from_mapping(
                item,
                systems=system_map,
                path=f"manifest.archives[{index}]",
            )
            for index, item in enumerate(archives_raw)
        )
        suites_raw = raw["verifierSuites"]
        if not isinstance(suites_raw, list):
            raise ValueError("manifest.verifierSuites must be an array")
        if len(suites_raw) > MAX_COLLECTION_ITEMS:
            raise ValueError("manifest.verifierSuites exceeds the finite collection limit")
        suites = tuple(
            VerifierSuite.from_mapping(
                item,
                f"manifest.verifierSuites[{index}]",
            )
            for index, item in enumerate(suites_raw)
        )
        if len({item.id for item in archives}) != len(archives):
            raise ValueError("manifest.archives contains duplicate IDs")
        if len({item.id for item in suites}) != len(suites):
            raise ValueError("manifest.verifierSuites contains duplicate IDs")
        outcomes_raw = raw["verificationOutcomes"]
        if not isinstance(outcomes_raw, list):
            raise ValueError("manifest.verificationOutcomes must be an array")
        if len(outcomes_raw) > MAX_COLLECTION_ITEMS:
            raise ValueError(
                "manifest.verificationOutcomes exceeds the finite collection limit"
            )
        outcomes = tuple(
            _unique_strings(
                item,
                f"manifest.verificationOutcomes[{index}]",
                allow_empty=True,
            )
            for index, item in enumerate(outcomes_raw)
        )
        declared_check_ids = {
            check_id for suite in suites for check_id in suite.check_ids
        }
        if any(
            not set(outcome).issubset(declared_check_ids)
            for outcome in outcomes
        ):
            raise ValueError("manifest.verificationOutcomes contains an unknown check ID")
        compilers_raw = raw["compilers"]
        if not isinstance(compilers_raw, list):
            raise ValueError("manifest.compilers must be an array")
        if len(compilers_raw) > MAX_COLLECTION_ITEMS:
            raise ValueError("manifest.compilers exceeds the finite collection limit")
        compiler_records = tuple(
            canonical_json(_object(item, f"manifest.compilers[{index}]"))
            for index, item in enumerate(compilers_raw)
        )
        manifest = cls(
            _string(raw["id"], "manifest.id"),
            targets,
            objective_names,
            systems,
            archives,
            suites,
            outcomes,
            compiler_records,
        )
        _validate_theory_work(manifest)
        return manifest

    def system(self, system_id: str) -> FiniteSystem:
        for system in self.systems:
            if system.id == system_id:
                return system
        raise ValueError(f"unknown system: {system_id!r}")

    def archive(self, archive_id: str) -> Archive:
        for archive in self.archives:
            if archive.id == archive_id:
                return archive
        raise ValueError(f"unknown archive: {archive_id!r}")

    def suite(self, suite_id: str) -> VerifierSuite:
        for suite in self.suites:
            if suite.id == suite_id:
                return suite
        raise ValueError(f"unknown verifier suite: {suite_id!r}")
