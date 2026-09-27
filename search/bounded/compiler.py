from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping

from .finite_theory import (
    Coordinate,
    FiniteSystem,
    TheoryManifest,
    _exact_keys,
    _nat,
    _object,
    _strict_json_loads,
    _string,
    check_ft01_threshold_duality,
    check_ft02_structure_monotonicity,
    check_ft03_threshold_monotonicity,
    check_ft04_two_part_identity,
    check_ft05_archive_upper_bound,
    check_ft06_append_only_archive_monotonicity,
    check_ft07_suite_subset_implication,
    check_ft08_pareto_soundness,
    check_ft09_pareto_completeness,
    inf_add,
    inf_le,
    is_prefix_free,
    kraft_sum,
    pareto_frontier,
    sha256_json,
    structure,
    threshold,
    two_part_by_cost_levels,
    two_part_direct,
)


RECEIPT_SCHEMA_VERSION = "finite-theory-receipt/v0"
THEORY_ID = "finite-theory-v0"
PROTECTED_BASELINE_SOURCE_COMMIT = "179194ca2524a0d37f797684010e600c70a65774"
PROTECTED_BASELINE_POLICY = "exact-file-sha256/v0"
HERE = Path(__file__).resolve().parent
DEFAULT_MANIFEST = HERE / "theory" / "manifest.json"
DEFAULT_STATEMENT_MAP = HERE / "theory" / "statement-map.json"
DEFAULT_RECEIPT = HERE / "theory" / "results" / "receipt.json"
PROTECTED_BASELINE_PATHS = (
    "search/__init__.py",
    "search/bounded/README.md",
    "search/bounded/__init__.py",
    "search/bounded/generate_lean.py",
    "search/bounded/lean/BoundedCoordinate.lean",
    "search/bounded/lean/BoundedCoordinate/Basic.lean",
    "search/bounded/lean/BoundedCoordinate/GeneratedFrontier.lean",
    "search/bounded/lean/BoundedCoordinate/GeneratedProblem.lean",
    "search/bounded/lean/lake-manifest.json",
    "search/bounded/lean/lakefile.toml",
    "search/bounded/lean/lean-toolchain",
    "search/bounded/model.py",
    "search/bounded/problem.json",
    "search/bounded/results/candidates.jsonl",
    "search/bounded/results/lean-verification.json",
    "search/bounded/results/receipt.json",
    "search/bounded/results/verification.json",
    "search/bounded/run.py",
    "search/bounded/verify.py",
    "search/bounded/verify_lean.py",
    "search/tests/test_bounded_coordinate.py",
)


@dataclass(frozen=True)
class CoordinateCompiler:
    id: str
    source_system_id: str
    destination_system_id: str
    source_system_content_sha256: str
    destination_system_content_sha256: str
    cost_overhead_bits: int
    residual_slack: int
    mapping: tuple[tuple[str, str], ...]
    declared_content_sha256: str

    @classmethod
    def from_mapping(
        cls,
        value: object,
        *,
        systems: Mapping[str, FiniteSystem],
        path: str = "compiler",
    ) -> "CoordinateCompiler":
        raw = _object(value, path)
        _exact_keys(
            raw,
            {
                "id",
                "sourceSystemId",
                "destinationSystemId",
                "sourceSystemContentSha256",
                "destinationSystemContentSha256",
                "costOverheadBits",
                "residualSlack",
                "mapping",
                "contentSha256",
            },
            path,
        )
        compiler_id = _string(raw["id"], f"{path}.id")
        source_id = _string(raw["sourceSystemId"], f"{path}.sourceSystemId")
        destination_id = _string(
            raw["destinationSystemId"],
            f"{path}.destinationSystemId",
        )
        if source_id not in systems or destination_id not in systems:
            raise ValueError(f"{path} names an unknown source or destination system")
        source = systems[source_id]
        destination = systems[destination_id]
        source_digest = _string(
            raw["sourceSystemContentSha256"],
            f"{path}.sourceSystemContentSha256",
        )
        destination_digest = _string(
            raw["destinationSystemContentSha256"],
            f"{path}.destinationSystemContentSha256",
        )
        if source_digest != source.content_sha256:
            raise ValueError(f"{path} has a stale source-system digest")
        if destination_digest != destination.content_sha256:
            raise ValueError(f"{path} has a stale destination-system digest")
        mapping_raw = _object(raw["mapping"], f"{path}.mapping")
        source_ids = [point.id for point in source.coordinates]
        if set(mapping_raw) != set(source_ids):
            raise ValueError(f"{path}.mapping must cover the source domain exactly")
        destination_ids = {point.id for point in destination.coordinates}
        mapping: list[tuple[str, str]] = []
        for source_coordinate_id in source_ids:
            destination_coordinate_id = _string(
                mapping_raw[source_coordinate_id],
                f"{path}.mapping.{source_coordinate_id}",
            )
            if destination_coordinate_id not in destination_ids:
                raise ValueError(f"{path}.mapping has an out-of-domain destination")
            mapping.append((source_coordinate_id, destination_coordinate_id))
        declared_digest = _string(raw["contentSha256"], f"{path}.contentSha256")
        digest_payload = {key: raw[key] for key in raw if key != "contentSha256"}
        if declared_digest != sha256_json(digest_payload):
            raise ValueError(f"{path}.contentSha256 does not match compiler content")
        compiler = cls(
            compiler_id,
            source_id,
            destination_id,
            source_digest,
            destination_digest,
            _nat(raw["costOverheadBits"], f"{path}.costOverheadBits"),
            _nat(raw["residualSlack"], f"{path}.residualSlack"),
            tuple(mapping),
            declared_digest,
        )
        compiler.validate(source, destination)
        return compiler

    @property
    def content_sha256(self) -> str:
        return sha256_json(self.to_json(include_content_sha256=False))

    def to_json(self, *, include_content_sha256: bool = True) -> dict[str, object]:
        result: dict[str, object] = {
            "id": self.id,
            "sourceSystemId": self.source_system_id,
            "destinationSystemId": self.destination_system_id,
            "sourceSystemContentSha256": self.source_system_content_sha256,
            "destinationSystemContentSha256": self.destination_system_content_sha256,
            "costOverheadBits": self.cost_overhead_bits,
            "residualSlack": self.residual_slack,
            "mapping": dict(self.mapping),
        }
        if include_content_sha256:
            result["contentSha256"] = self.content_sha256
        return result

    def destination_id(self, source_coordinate_id: str) -> str:
        for source_id, destination_id in self.mapping:
            if source_id == source_coordinate_id:
                return destination_id
        raise ValueError(f"compiler {self.id!r} does not cover {source_coordinate_id!r}")

    def validate(
        self,
        source: FiniteSystem,
        destination: FiniteSystem,
    ) -> None:
        if self.declared_content_sha256 != self.content_sha256:
            raise ValueError("compiler content digest mismatch")
        if source.id != self.source_system_id or destination.id != self.destination_system_id:
            raise ValueError("compiler systems disagree with the supplied systems")
        if source.content_sha256 != self.source_system_content_sha256:
            raise ValueError("compiler source-system digest mismatch")
        if destination.content_sha256 != self.destination_system_content_sha256:
            raise ValueError("compiler destination-system digest mismatch")
        if source.targets != destination.targets:
            raise ValueError("compiler systems must use the same ordered target set")
        source_mapping_ids = [source_id for source_id, _ in self.mapping]
        if (
            len(source_mapping_ids) != len(set(source_mapping_ids))
            or len(source_mapping_ids) != len(source.coordinates)
            or set(source_mapping_ids)
            != {point.id for point in source.coordinates}
        ):
            raise ValueError("compiler mapping does not cover the source domain")
        destination_ids = {point.id for point in destination.coordinates}
        for source_id, destination_id in self.mapping:
            if destination_id not in destination_ids:
                raise ValueError("compiler mapping leaves the destination domain")
            source_point = source.coordinate(source_id)
            destination_point = destination.coordinate(destination_id)
            if (
                destination_point.charged_bit_cost
                > source_point.charged_bit_cost + self.cost_overhead_bits
            ):
                raise ValueError("compiler understates its charged-cost overhead")
            for target in source.targets:
                if (
                    destination_point.residual(target)
                    > source_point.residual(target) + self.residual_slack
                ):
                    raise ValueError("compiler understates its targetwise residual slack")


def compiler_witness_transfer(
    compiler: CoordinateCompiler,
    source: FiniteSystem,
    destination: FiniteSystem,
    source_coordinate_id: str,
    target: str,
) -> Coordinate:
    """FC-01: transfer one source witness with the declared additive bounds."""
    compiler.validate(source, destination)
    if target not in source.targets:
        raise ValueError(f"unknown target: {target!r}")
    source_point = source.coordinate(source_coordinate_id)
    destination_point = destination.coordinate(
        compiler.destination_id(source_coordinate_id)
    )
    if (
        destination_point.charged_bit_cost
        > source_point.charged_bit_cost + compiler.cost_overhead_bits
        or destination_point.residual(target)
        > source_point.residual(target) + compiler.residual_slack
    ):
        raise AssertionError("validated compiler failed witness transfer")
    return destination_point


def check_fc01_witness_transfer(
    compiler: CoordinateCompiler,
    source: FiniteSystem,
    destination: FiniteSystem,
) -> bool:
    compiler.validate(source, destination)
    return all(
        compiler_witness_transfer(
            compiler,
            source,
            destination,
            point.id,
            target,
        ).id
        == compiler.destination_id(point.id)
        for point in source.coordinates
        for target in source.targets
    )


def check_fc02_curve_transfer(
    compiler: CoordinateCompiler,
    source: FiniteSystem,
    destination: FiniteSystem,
) -> bool:
    """FC-02: transfer finite structure and threshold witnesses."""
    compiler.validate(source, destination)
    for target in source.targets:
        max_cost = max(
            (point.charged_bit_cost for point in source.coordinates),
            default=0,
        )
        for budget in range(max_cost + 2):
            if not inf_le(
                structure(
                    destination.coordinates,
                    target,
                    budget + compiler.cost_overhead_bits,
                ),
                inf_add(
                    structure(source.coordinates, target, budget),
                    compiler.residual_slack,
                ),
            ):
                return False
        max_residual = max(
            (point.residual(target) for point in source.coordinates),
            default=0,
        )
        for residual_limit in range(max_residual + 2):
            if not inf_le(
                threshold(
                    destination.coordinates,
                    target,
                    residual_limit + compiler.residual_slack,
                ),
                inf_add(
                    threshold(source.coordinates, target, residual_limit),
                    compiler.cost_overhead_bits,
                ),
            ):
                return False
    return True


def compose_compilers(
    first: CoordinateCompiler,
    second: CoordinateCompiler,
    source: FiniteSystem,
    intermediate: FiniteSystem,
    destination: FiniteSystem,
    *,
    compiler_id: str,
) -> CoordinateCompiler:
    """FC-03: compose mappings and add both declared bounds."""
    first.validate(source, intermediate)
    second.validate(intermediate, destination)
    if first.destination_system_id != second.source_system_id:
        raise ValueError("compiler endpoints are not composable")
    mapping = tuple(
        (
            source_id,
            second.destination_id(intermediate_id),
        )
        for source_id, intermediate_id in first.mapping
    )
    draft = CoordinateCompiler(
        id=_string(compiler_id, "compiler_id"),
        source_system_id=source.id,
        destination_system_id=destination.id,
        source_system_content_sha256=source.content_sha256,
        destination_system_content_sha256=destination.content_sha256,
        cost_overhead_bits=first.cost_overhead_bits + second.cost_overhead_bits,
        residual_slack=first.residual_slack + second.residual_slack,
        mapping=mapping,
        declared_content_sha256="",
    )
    composed = CoordinateCompiler(
        id=draft.id,
        source_system_id=draft.source_system_id,
        destination_system_id=draft.destination_system_id,
        source_system_content_sha256=draft.source_system_content_sha256,
        destination_system_content_sha256=draft.destination_system_content_sha256,
        cost_overhead_bits=draft.cost_overhead_bits,
        residual_slack=draft.residual_slack,
        mapping=draft.mapping,
        declared_content_sha256=draft.content_sha256,
    )
    composed.validate(source, destination)
    return composed


def check_fc03_composition(
    first: CoordinateCompiler,
    second: CoordinateCompiler,
    source: FiniteSystem,
    intermediate: FiniteSystem,
    destination: FiniteSystem,
) -> bool:
    composed = compose_compilers(
        first,
        second,
        source,
        intermediate,
        destination,
        compiler_id=f"{first.id}+{second.id}",
    )
    return (
        composed.cost_overhead_bits
        == first.cost_overhead_bits + second.cost_overhead_bits
        and composed.residual_slack
        == first.residual_slack + second.residual_slack
        and all(
            composed.destination_id(source_id)
            == second.destination_id(first.destination_id(source_id))
            for source_id, _ in first.mapping
        )
    )


def check_fc04_zero_slack_threshold_sandwich(
    forward: CoordinateCompiler,
    reverse: CoordinateCompiler,
    source: FiniteSystem,
    destination: FiniteSystem,
) -> bool:
    """FC-04: directional bounds; threshold sandwich only at zero slack."""
    forward.validate(source, destination)
    reverse.validate(destination, source)
    if forward.residual_slack != 0 or reverse.residual_slack != 0:
        raise ValueError("the threshold sandwich requires zero residual slack both ways")
    if not (
        check_fc02_curve_transfer(forward, source, destination)
        and check_fc02_curve_transfer(reverse, destination, source)
    ):
        return False
    for target in source.targets:
        max_residual = max(
            (
                point.residual(target)
                for point in source.coordinates + destination.coordinates
            ),
            default=0,
        )
        for residual_limit in range(max_residual + 2):
            source_threshold = threshold(
                source.coordinates,
                target,
                residual_limit,
            )
            destination_threshold = threshold(
                destination.coordinates,
                target,
                residual_limit,
            )
            if not inf_le(
                destination_threshold,
                inf_add(source_threshold, forward.cost_overhead_bits),
            ):
                return False
            if not inf_le(
                source_threshold,
                inf_add(destination_threshold, reverse.cost_overhead_bits),
            ):
                return False
    return True


def parse_manifest_compilers(
    compiler_records: tuple[str, ...],
    systems: Mapping[str, FiniteSystem],
) -> tuple[CoordinateCompiler, ...]:
    compilers = tuple(
        CoordinateCompiler.from_mapping(
            json.loads(record),
            systems=systems,
            path=f"manifest.compilers[{index}]",
        )
        for index, record in enumerate(compiler_records)
    )
    if len({compiler.id for compiler in compilers}) != len(compilers):
        raise ValueError("manifest.compilers contains duplicate IDs")
    return compilers


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _artifact_binding(path: Path) -> dict[str, object]:
    source = path.read_bytes()
    parsed = _strict_json_loads(source.decode("utf-8"))
    return {
        "fileSha256": hashlib.sha256(source).hexdigest(),
        "contentSha256": sha256_json(parsed),
    }


def _protected_baseline(repository_root: Path) -> dict[str, object]:
    files = []
    for relative_path in PROTECTED_BASELINE_PATHS:
        path = repository_root / relative_path
        if not path.is_file():
            raise ValueError(f"protected baseline file is missing: {relative_path}")
        files.append(
            {
                "path": relative_path,
                "sha256": _sha256_file(path),
            }
        )
    if len(files) != 21:
        raise AssertionError("protected baseline inventory must contain exactly 21 files")
    payload = {
        "sourceCommit": PROTECTED_BASELINE_SOURCE_COMMIT,
        "policy": PROTECTED_BASELINE_POLICY,
        "fileCount": len(files),
        "files": files,
    }
    return {**payload, "contentSha256": sha256_json(payload)}


def _encoding_evidence(system: FiniteSystem) -> dict[str, object]:
    codes = [point.code_bits for point in system.coordinates]
    kraft = kraft_sum(codes)
    inversion = next(
        (
            [left.id, right.id]
            for left in system.coordinates
            for right in system.coordinates
            if len(left.payload_bits) < len(right.payload_bits)
            and left.charged_bit_cost > right.charged_bit_cost
        ),
        None,
    )
    return {
        "systemId": system.id,
        "coordinateCount": len(system.coordinates),
        "prefixFree": is_prefix_free(codes),
        "injective": len(codes) == len(set(codes)),
        "losslessRendering": len({point.rendering for point in system.coordinates})
        == len(system.coordinates),
        "kraft": {
            "numerator": kraft.numerator,
            "denominator": kraft.denominator,
        },
        "rawChargedOrderInversionWitness": inversion,
    }


def _system_evidence(system: FiniteSystem) -> dict[str, object]:
    targets: dict[str, object] = {}
    for target in system.targets:
        max_cost = max(
            (point.charged_bit_cost for point in system.coordinates),
            default=0,
        )
        max_residual = max(
            (point.residual(target) for point in system.coordinates),
            default=0,
        )
        targets[target] = {
            "maxCost": max_cost,
            "maxResidual": max_residual,
            "structure": [
                {
                    "budget": budget,
                    "value": structure(system.coordinates, target, budget),
                }
                for budget in range(max_cost + 2)
            ],
            "threshold": [
                {
                    "residualLimit": residual_limit,
                    "value": threshold(
                        system.coordinates,
                        target,
                        residual_limit,
                    ),
                }
                for residual_limit in range(max_residual + 2)
            ],
            "twoPart": {
                "direct": two_part_direct(system.coordinates, target),
                "byDeclaredCostLevels": two_part_by_cost_levels(
                    system.coordinates,
                    target,
                ),
            },
        }
    frontier = pareto_frontier(system.coordinates)
    return {
        "systemId": system.id,
        "targets": targets,
        "pareto": {
            "policy": "first-source-occurrence-per-vector/v0",
            "candidateIds": [point.id for point in frontier],
            "objectiveVectors": [list(point.objective_vector) for point in frontier],
        },
    }


def _archive_evidence(manifest: TheoryManifest) -> list[dict[str, object]]:
    archives: list[dict[str, object]] = []
    for archive in manifest.archives:
        system = manifest.system(archive.system_id)
        archives.append(
            {
                "archiveId": archive.id,
                "systemId": archive.system_id,
                "coordinateIds": list(archive.coordinate_ids),
                "isDomainSubset": all(
                    check_ft05_archive_upper_bound(system, archive, target)
                    for target in manifest.targets
                ),
            }
        )
    return archives


def _suite_evidence(manifest: TheoryManifest) -> list[dict[str, object]]:
    subset_relations: list[dict[str, object]] = []
    for larger in manifest.suites:
        for subset in manifest.suites:
            if (
                subset.id != larger.id
                and set(subset.check_ids).issubset(larger.check_ids)
            ):
                subset_relations.append(
                    {
                        "subsetSuiteId": subset.id,
                        "largerSuiteId": larger.id,
                        "outcomesChecked": len(manifest.verification_outcomes),
                        "implicationHolds": check_ft07_suite_subset_implication(
                            larger,
                            subset,
                            manifest.verification_outcomes,
                        ),
                    }
                )
    return subset_relations


def _compiler_evidence(
    compilers: tuple[CoordinateCompiler, ...],
    systems: Mapping[str, FiniteSystem],
) -> list[dict[str, object]]:
    evidence = []
    for compiler in compilers:
        source = systems[compiler.source_system_id]
        destination = systems[compiler.destination_system_id]
        evidence.append(
            {
                "compilerId": compiler.id,
                "sourceSystemId": source.id,
                "destinationSystemId": destination.id,
                "costOverheadBits": compiler.cost_overhead_bits,
                "residualSlack": compiler.residual_slack,
                "sourceCoverage": set(dict(compiler.mapping))
                == {point.id for point in source.coordinates},
                "destinationMembership": set(dict(compiler.mapping).values()).issubset(
                    {point.id for point in destination.coordinates}
                ),
                "targetIndependent": all(
                    isinstance(destination_id, str)
                    for _, destination_id in compiler.mapping
                ),
                "costBound": all(
                    destination.coordinate(destination_id).charged_bit_cost
                    <= source.coordinate(source_id).charged_bit_cost
                    + compiler.cost_overhead_bits
                    for source_id, destination_id in compiler.mapping
                ),
                "residualBound": check_fc01_witness_transfer(
                    compiler,
                    source,
                    destination,
                ),
            }
        )
    return evidence


def _composition_evidence(
    compilers: tuple[CoordinateCompiler, ...],
    systems: Mapping[str, FiniteSystem],
) -> list[dict[str, object]]:
    evidence = []
    for first in compilers:
        for second in compilers:
            if first.destination_system_id != second.source_system_id:
                continue
            source = systems[first.source_system_id]
            intermediate = systems[first.destination_system_id]
            destination = systems[second.destination_system_id]
            composed = compose_compilers(
                first,
                second,
                source,
                intermediate,
                destination,
                compiler_id=f"{first.id}+{second.id}",
            )
            evidence.append(
                {
                    "firstCompilerId": first.id,
                    "secondCompilerId": second.id,
                    "sourceSystemId": source.id,
                    "destinationSystemId": destination.id,
                    "mapping": dict(composed.mapping),
                    "costOverheadBits": composed.cost_overhead_bits,
                    "residualSlack": composed.residual_slack,
                    "valid": check_fc03_composition(
                        first,
                        second,
                        source,
                        intermediate,
                        destination,
                    ),
                }
            )
    return evidence


def _append_only_pairs(
    manifest: TheoryManifest,
) -> Iterable[tuple[object, object]]:
    for old in manifest.archives:
        for new in manifest.archives:
            if (
                old.id != new.id
                and old.system_id == new.system_id
                and len(old.coordinate_ids) <= len(new.coordinate_ids)
                and new.coordinate_ids[: len(old.coordinate_ids)]
                == old.coordinate_ids
            ):
                yield old, new


def _suite_subset_pairs(
    manifest: TheoryManifest,
) -> Iterable[tuple[object, object]]:
    for larger in manifest.suites:
        for subset in manifest.suites:
            if (
                larger.id != subset.id
                and set(subset.check_ids).issubset(larger.check_ids)
            ):
                yield larger, subset


def _composable_compilers(
    compilers: tuple[CoordinateCompiler, ...],
) -> Iterable[tuple[CoordinateCompiler, CoordinateCompiler]]:
    for first in compilers:
        for second in compilers:
            if first.destination_system_id == second.source_system_id:
                yield first, second


def _nonempty_all(values: Iterable[bool]) -> bool:
    seen = False
    for value in values:
        seen = True
        if not value:
            return False
    return seen


def _statement_check_values(
    manifest: TheoryManifest,
    compilers: tuple[CoordinateCompiler, ...],
) -> dict[str, bool]:
    systems = {system.id: system for system in manifest.systems}
    return {
        "FT-01": all(
            check_ft01_threshold_duality(system, target)
            for system in manifest.systems
            for target in manifest.targets
        ),
        "FT-02": all(
            check_ft02_structure_monotonicity(system, target)
            for system in manifest.systems
            for target in manifest.targets
        ),
        "FT-03": all(
            check_ft03_threshold_monotonicity(system, target)
            for system in manifest.systems
            for target in manifest.targets
        ),
        "FT-04": all(
            check_ft04_two_part_identity(system, target)
            for system in manifest.systems
            for target in manifest.targets
        ),
        "FT-05": all(
            check_ft05_archive_upper_bound(
                systems[archive.system_id],
                archive,
                target,
            )
            for archive in manifest.archives
            for target in manifest.targets
        ),
        "FT-06": _nonempty_all(
            check_ft06_append_only_archive_monotonicity(
                systems[old.system_id],
                old,
                new,
                target,
            )
            for old, new in _append_only_pairs(manifest)
            for target in manifest.targets
        ),
        "FT-07": _nonempty_all(
            check_ft07_suite_subset_implication(
                larger,
                subset,
                manifest.verification_outcomes,
            )
            for larger, subset in _suite_subset_pairs(manifest)
        ),
        "FT-08": all(
            check_ft08_pareto_soundness(system.coordinates)
            for system in manifest.systems
        ),
        "FT-09": all(
            check_ft09_pareto_completeness(system.coordinates)
            for system in manifest.systems
        ),
        "FC-01": all(
            check_fc01_witness_transfer(
                compiler,
                systems[compiler.source_system_id],
                systems[compiler.destination_system_id],
            )
            for compiler in compilers
        ),
        "FC-02": all(
            check_fc02_curve_transfer(
                compiler,
                systems[compiler.source_system_id],
                systems[compiler.destination_system_id],
            )
            for compiler in compilers
        ),
        "FC-03": _nonempty_all(
            check_fc03_composition(
                first,
                second,
                systems[first.source_system_id],
                systems[first.destination_system_id],
                systems[second.destination_system_id],
            )
            for first, second in _composable_compilers(compilers)
        ),
        "FC-04": _nonempty_all(
            check_fc04_zero_slack_threshold_sandwich(
                first,
                second,
                systems[first.source_system_id],
                systems[first.destination_system_id],
            )
            for first, second in _composable_compilers(compilers)
            if first.source_system_id == second.destination_system_id
            and first.residual_slack == 0
            and second.residual_slack == 0
        ),
    }



def build_receipt(
    manifest: TheoryManifest,
    *,
    manifest_path: Path,
    statement_map_path: Path,
    repository_root: Path,
) -> dict[str, object]:
    """Build a deterministic calculator receipt without importing the verifier."""
    statement_map = _strict_json_loads(
        statement_map_path.read_text(encoding="utf-8")
    )
    statement_map_object = _object(statement_map, "statement map")
    if statement_map_object.get("theoryId") != THEORY_ID:
        raise ValueError("statement map has an unexpected theory ID")
    statements = statement_map_object.get("statements")
    if not isinstance(statements, list):
        raise ValueError("statement map statements must be an array")
    systems = {system.id: system for system in manifest.systems}
    compilers = parse_manifest_compilers(manifest.compiler_records, systems)
    checks = _statement_check_values(manifest, compilers)
    statement_ids = [
        _string(_object(item, "statement")["id"], "statement.id")
        for item in statements
    ]
    if statement_ids != list(checks):
        raise ValueError("statement map IDs or order disagree with executable checks")
    statement_checks = []
    for statement in statements:
        statement_object = _object(statement, "statement")
        statement_id = str(statement_object["id"])
        statement_checks.append(
            {
                "id": statement_id,
                "pythonCheck": _string(
                    statement_object.get("pythonCheck"),
                    f"{statement_id}.pythonCheck",
                ),
                "passed": checks[statement_id],
            }
        )
    return {
        "schemaVersion": RECEIPT_SCHEMA_VERSION,
        "theoryId": THEORY_ID,
        "fixtureId": manifest.id,
        "manifest": _artifact_binding(manifest_path),
        "statementMap": _artifact_binding(statement_map_path),
        "protectedBaseline": _protected_baseline(repository_root),
        "encodingEvidence": [
            _encoding_evidence(system) for system in manifest.systems
        ],
        "systemEvidence": [
            _system_evidence(system) for system in manifest.systems
        ],
        "archiveEvidence": _archive_evidence(manifest),
        "suiteEvidence": _suite_evidence(manifest),
        "compilerEvidence": _compiler_evidence(compilers, systems),
        "compositionEvidence": _composition_evidence(compilers, systems),
        "statementChecks": statement_checks,
        "scope": {
            "finiteExactIntegersOnly": True,
            "noneMeansPositiveInfinity": True,
            "fullDeclaredDomainsOnly": True,
            "claimsOpenLlmPromptSearch": False,
            "claimsKolmogorovComplexity": False,
            "claimsTokenizerInvariance": False,
            "claimsNaturalLanguageIntentVerification": False,
        },
    }


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build the deterministic Finite Theory v0 calculator receipt."
    )
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument(
        "--statement-map",
        type=Path,
        default=DEFAULT_STATEMENT_MAP,
    )
    parser.add_argument("--out", type=Path, default=DEFAULT_RECEIPT)
    args = parser.parse_args()
    repository_root = Path(__file__).resolve().parents[2]
    manifest = TheoryManifest.from_path(args.manifest)
    receipt = build_receipt(
        manifest,
        manifest_path=args.manifest,
        statement_map_path=args.statement_map,
        repository_root=repository_root,
    )
    _write_json(args.out, receipt)
    print(args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
