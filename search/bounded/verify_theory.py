from __future__ import annotations

"""Independent reconstruction and Lean audit for ``finite-theory-v0``.

This module intentionally does not import :mod:`finite_theory` or
:mod:`compiler`.  The duplication is a trust boundary: a defect in the
calculator must not automatically become a verifier invariant.
"""

import argparse
import hashlib
import itertools
import json
import os
import re
import subprocess
import tempfile
from fractions import Fraction
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


HERE = Path(__file__).resolve().parent
REPOSITORY_ROOT = HERE.parents[1]
THEORY_ROOT = HERE / "theory"
LEAN_ROOT = HERE / "lean"
DEFAULT_MANIFEST = THEORY_ROOT / "manifest.json"
DEFAULT_STATEMENT_MAP = THEORY_ROOT / "statement-map.json"
DEFAULT_RECEIPT = THEORY_ROOT / "results" / "receipt.json"
DEFAULT_VERIFICATION = THEORY_ROOT / "results" / "verification.json"
DEFAULT_LEAN_VERIFICATION = THEORY_ROOT / "results" / "lean-verification.json"

MANIFEST_SCHEMA = "finite-theory-manifest/v0"
STATEMENT_MAP_SCHEMA = "finite-theory-statement-map/v0"
RECEIPT_SCHEMA = "finite-theory-receipt/v0"
VERIFICATION_SCHEMA = "finite-theory-verification/v0"
LEAN_VERIFICATION_SCHEMA = "finite-theory-lean-verification/v0"
ENCODING_KIND = "typed-fixed-width-length-prefix/v0"
PROTECTED_SOURCE_COMMIT = "179194ca2524a0d37f797684010e600c70a65774"

MAX_JSON_BYTES = 2_000_000
MAX_IDENTIFIER_LENGTH = 512
MAX_BIT_STRING_LENGTH = 4_096
MAX_LENGTH_WIDTH = 16
MAX_COLLECTION_ITEMS = 10_000
MAX_COORDINATES_PER_SYSTEM = 512
MAX_ROLE_TAGS = 512
MAX_THEORY_SCALAR = 1_024
MAX_THEORY_WORK = 1_000_000
MAX_EVIDENCE_PAIRS = 10_000


PROTECTED_FILES: dict[str, str] = {
    "search/__init__.py": "daa65e247d006dcf55e13ada332215d2384f9287fb258f18f94d18ca6196315b",
    "search/bounded/README.md": "1323fd3ffc388a9e4bd644653d547bed52c9dadfdb0948a03c67f8500ada9092",
    "search/bounded/__init__.py": "0d11c3bdcffe8ddf082a4435f1591c0ec31c1119098a7aaa6955919c1d3ca1cc",
    "search/bounded/generate_lean.py": "fbf00da31793399cfeec7807ae8c4faff9422dea4fa31fced62c1b387c302262",
    "search/bounded/lean/BoundedCoordinate.lean": "fd5b1690981f13d018f272a9a78f54943b4e27abacf2421a0fb928a6021bd986",
    "search/bounded/lean/BoundedCoordinate/Basic.lean": "b26ccaeeaa74292680f6c401e8800d8c17da0598aba8a56b36d4a36526eac667",
    "search/bounded/lean/BoundedCoordinate/GeneratedFrontier.lean": "e09f5debdc468212f0a673a0feba4bf89a34167d3e0b844d12c9ce8af76ab53b",
    "search/bounded/lean/BoundedCoordinate/GeneratedProblem.lean": "06b4ddf2af7f9a97609c9a940f251a5367b20ea9f91daa5b43ba29c041a0b7bc",
    "search/bounded/lean/lake-manifest.json": "18e2960aa611b114b820e90fef81ff3555325f9ff6e198011d5dcd00dacf2235",
    "search/bounded/lean/lakefile.toml": "8dd2a9db8c709478b11cdf442955bcf0257eff7400a092eef9365867458687e7",
    "search/bounded/lean/lean-toolchain": "d5edba4e4b8faad9c1baeadb265716d20d03be4d1a2647dc5e35b0c0325bea7b",
    "search/bounded/model.py": "70e57a4c1298c7d1449444190dd21f9fb684e31c4358cd423b69be4f18423760",
    "search/bounded/problem.json": "6822ce4c80b720e9148e5f9c5af9679655eb4b7659c941b5d9ee460067b80408",
    "search/bounded/results/candidates.jsonl": "273b5a53eab00a484bf77c71c78fa6eb76f92302492cb0633b6cfeb702b29ebe",
    "search/bounded/results/lean-verification.json": "59cf47fa3f4cca59a3a697f57fbfe42aded7ded255bc31e045cc5363058aebfa",
    "search/bounded/results/receipt.json": "ae4bacf3739d3015cf0c71ccbe7c9da249d29a7ac0514c79173ec23d3c89bc7b",
    "search/bounded/results/verification.json": "6a9906d2776009a95bf50a6a7737981eb5d9e8a60d6e99a5bf082ce968a655f8",
    "search/bounded/run.py": "ccfc331f2e4243fc9ca5ea43c6654afd8790039f4bfbb4fca2bc6828c90845ba",
    "search/bounded/verify.py": "0537ad21f8975dd467c493f42a047127222a62b465c021de2688b84c4fa41552",
    "search/bounded/verify_lean.py": "effe1c6daf30a8caa813d19ae52ddee7da3762a0f16f817d818a58e500341b8d",
    "search/tests/test_bounded_coordinate.py": "0db2eb29284dd4c62a8190e5af03735d0f4e05e5acea4ed87e87c85214f873f6",
}

# Filled after the statement map has received an independent review.  Keeping
# this separate from the receipt prevents a coordinated map+receipt rewrite
# from becoming self-authenticating.
EXPECTED_STATEMENT_MAP_FILE_SHA256 = "faaeb6f11a6333f34fd9e31257b2907bde70c0f9e0261ed5e759abeb74489d54"


STATEMENT_CONTRACT: dict[str, tuple[str, str, str]] = {
    "FT-01": (
        "check_ft01_threshold_duality",
        "BoundedCoordinate.FiniteTheory",
        "BoundedCoordinate.FiniteTheory.finite_threshold_duality",
    ),
    "FT-02": (
        "check_ft02_structure_monotonicity",
        "BoundedCoordinate.FiniteTheory",
        "BoundedCoordinate.FiniteTheory.structure_monotone",
    ),
    "FT-03": (
        "check_ft03_threshold_monotonicity",
        "BoundedCoordinate.FiniteTheory",
        "BoundedCoordinate.FiniteTheory.threshold_monotone",
    ),
    "FT-04": (
        "check_ft04_two_part_identity",
        "BoundedCoordinate.FiniteTheory",
        "BoundedCoordinate.FiniteTheory.two_part_identity",
    ),
    "FT-05": (
        "check_ft05_archive_upper_bound",
        "BoundedCoordinate.FiniteTheory",
        "BoundedCoordinate.FiniteTheory.archive_upper_bound",
    ),
    "FT-06": (
        "check_ft06_append_only_archive_monotonicity",
        "BoundedCoordinate.FiniteTheory",
        "BoundedCoordinate.FiniteTheory.append_only_archive_monotone",
    ),
    "FT-07": (
        "check_ft07_suite_subset_implication",
        "BoundedCoordinate.FiniteTheory",
        "BoundedCoordinate.FiniteTheory.suite_inclusion",
    ),
    "FT-08": (
        "check_ft08_pareto_soundness",
        "BoundedCoordinate.FiniteTheory",
        "BoundedCoordinate.FiniteTheory.pareto_sound",
    ),
    "FT-09": (
        "check_ft09_pareto_completeness",
        "BoundedCoordinate.FiniteTheory",
        "BoundedCoordinate.FiniteTheory.pareto_complete",
    ),
    "FC-01": (
        "check_fc01_witness_transfer",
        "BoundedCoordinate.Compiler",
        "BoundedCoordinate.Compiler.compiler_witness_transfer",
    ),
    "FC-02": (
        "check_fc02_curve_transfer",
        "BoundedCoordinate.Compiler",
        "BoundedCoordinate.Compiler.compiler_structure_threshold_transfer",
    ),
    "FC-03": (
        "check_fc03_composition",
        "BoundedCoordinate.Compiler",
        "BoundedCoordinate.Compiler.compiler_composition",
    ),
    "FC-04": (
        "check_fc04_zero_slack_threshold_sandwich",
        "BoundedCoordinate.Compiler",
        "BoundedCoordinate.Compiler.zero_slack_threshold_sandwich",
    ),
}


def _axioms(*names: str) -> tuple[str, ...]:
    return tuple(sorted(names))


EXPECTED_PUBLIC_THEOREM_AXIOMS: dict[str, tuple[str, ...]] = {
    theorem: (
        _axioms("propext", "Classical.choice", "Quot.sound")
        if statement_id in {"FT-01", "FT-02", "FT-03", "FT-04", "FT-05", "FT-06", "FC-02", "FC-04"}
        else _axioms()
        if statement_id == "FT-07"
        else _axioms("propext")
        if statement_id == "FT-08"
        else _axioms("propext", "Quot.sound")
    )
    for statement_id, (_, _, theorem) in STATEMENT_CONTRACT.items()
}

LEAN_SOURCES: dict[str, Path] = {
    "BoundedCoordinate.FiniteTheory": Path("BoundedCoordinate/FiniteTheory.lean"),
    "BoundedCoordinate.Compiler": Path("BoundedCoordinate/Compiler.lean"),
}
FORBIDDEN_PROOF_PATTERN = re.compile(r"\b(?:sorry|admit|axiom)\b")
PUBLIC_THEOREM_PATTERN = re.compile(
    r"^[ \t]*(?:@\[[^\]\n]+\][ \t]*)*"
    r"(?:(?:protected|noncomputable)[ \t]+)*"
    r"(?:theorem|lemma)[ \t]+([A-Za-z_][A-Za-z0-9_']*)",
    re.MULTILINE,
)
LEAN_VERSION_PATTERN = re.compile(r"Lean \(version ([0-9]+(?:\.[0-9]+)*)[,)]")
AXIOM_DEPENDENCY_PATTERN = re.compile(r"^'([^']+)' depends on axioms: \[([^]]*)\]$")
NO_AXIOM_DEPENDENCY_PATTERN = re.compile(r"^'([^']+)' does not depend on any axioms$")


def canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_json(value: object) -> str:
    return sha256_bytes(canonical_json(value).encode("utf-8"))


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def rendered_json_bytes(value: object) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    ).encode("utf-8")


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = rendered_json_bytes(value)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            prefix=f".{path.name}.",
            suffix=".tmp",
            dir=path.parent,
            delete=False,
        ) as temporary:
            temporary.write(payload)
            temporary.flush()
            os.fsync(temporary.fileno())
            temporary_path = Path(temporary.name)
        os.replace(temporary_path, path)
        temporary_path = None
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def strict_json(path: Path) -> object:
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"JSON input must be a regular non-symlink file: {path}")
    if path.stat().st_size > MAX_JSON_BYTES:
        raise ValueError(f"JSON input exceeds {MAX_JSON_BYTES} bytes: {path}")

    def object_hook(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"duplicate JSON object key: {key!r}")
            result[key] = value
        return result

    def reject_constant(value: str) -> object:
        raise ValueError(f"non-finite JSON number is forbidden: {value}")

    def reject_float(value: str) -> object:
        raise ValueError(f"floating-point JSON number is forbidden: {value}")

    return json.loads(
        path.read_text(encoding="utf-8"),
        object_pairs_hook=object_hook,
        parse_constant=reject_constant,
        parse_float=reject_float,
    )


def object_value(value: object, path: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{path} must be an object")
    return value


def exact_keys(value: Mapping[str, Any], expected: set[str], path: str) -> None:
    actual = set(value)
    if actual != expected:
        raise ValueError(
            f"{path} keys mismatch; missing={sorted(expected - actual)}, extra={sorted(actual - expected)}"
        )


def string_value(value: object, path: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{path} must be a non-empty string")
    if len(value) > MAX_IDENTIFIER_LENGTH:
        raise ValueError(f"{path} exceeds the string length limit")
    return value


def nat_value(value: object, path: str) -> int:
    if type(value) is not int or value < 0:  # bool is intentionally rejected
        raise ValueError(f"{path} must be a non-negative exact integer")
    if value > MAX_THEORY_SCALAR:
        raise ValueError(f"{path} exceeds the finite scalar limit")
    return value


def bit_string(value: object, path: str, *, allow_empty: bool = True) -> str:
    if not isinstance(value, str) or any(bit not in "01" for bit in value):
        raise ValueError(f"{path} must be a bit string")
    if not allow_empty and not value:
        raise ValueError(f"{path} must not be empty")
    if len(value) > MAX_BIT_STRING_LENGTH:
        raise ValueError(f"{path} exceeds the bit-string length limit")
    return value


def unique_strings(value: object, path: str, *, allow_empty: bool = False) -> list[str]:
    if not isinstance(value, list):
        raise ValueError(f"{path} must be an array")
    if len(value) > MAX_COLLECTION_ITEMS:
        raise ValueError(f"{path} exceeds the finite collection limit")
    result = [string_value(item, f"{path}[{index}]") for index, item in enumerate(value)]
    if not allow_empty and not result:
        raise ValueError(f"{path} must not be empty")
    if len(result) != len(set(result)):
        raise ValueError(f"{path} must not contain duplicates")
    return result


def is_prefix(left: str, right: str) -> bool:
    return len(left) <= len(right) and right.startswith(left)


def prefix_free(words: Sequence[str]) -> bool:
    return len(words) == len(set(words)) and all(
        not is_prefix(left, right)
        for left_index, left in enumerate(words)
        for right_index, right in enumerate(words)
        if left_index != right_index
    )


def kraft_sum(words: Iterable[str]) -> Fraction:
    return sum((Fraction(1, 1 << len(word)) for word in words), start=Fraction(0, 1))


def inf_le(left: int | None, right: int | None) -> bool:
    if right is None:
        return True
    if left is None:
        return False
    return left <= right


def inf_add(value: int | None, amount: int) -> int | None:
    return None if value is None else value + amount


def protected_baseline(repository_root: Path) -> dict[str, object]:
    files = []
    errors = []
    root = repository_root.resolve()
    for relative, expected in sorted(PROTECTED_FILES.items()):
        path = repository_root / relative
        try:
            if path.is_symlink() or not path.is_file():
                raise ValueError("not a regular non-symlink file")
            if not path.resolve().is_relative_to(root):
                raise ValueError("resolves outside repository root")
            actual = sha256_file(path)
            if actual != expected:
                raise ValueError(f"expected {expected}, got {actual}")
            files.append({"path": relative, "sha256": actual})
        except (OSError, ValueError) as error:
            errors.append(f"protected baseline mismatch at {relative}: {error}")
    if errors:
        raise ValueError("; ".join(errors))
    payload = {
        "sourceCommit": PROTECTED_SOURCE_COMMIT,
        "policy": "exact-file-sha256/v0",
        "fileCount": len(files),
        "files": files,
    }
    return {**payload, "contentSha256": sha256_json(payload)}


def validate_work_budget(manifest: Mapping[str, Any]) -> None:
    targets = manifest["targets"]
    systems = manifest["systems"]
    archives = manifest["archives"]
    suites = manifest["verifierSuites"]
    outcomes = manifest["verificationOutcomes"]
    compilers = manifest["compilers"]
    target_count = len(targets)
    max_coordinates = max(
        (len(system["coordinates"]) for system in systems),
        default=0,
    )
    max_cost = max(
        (
            coordinate["chargedBitCost"]
            for system in systems
            for coordinate in system["coordinates"]
        ),
        default=0,
    )
    max_residual = max(
        (
            coordinate["residuals"][target]
            for system in systems
            for coordinate in system["coordinates"]
            for target in targets
        ),
        default=0,
    )
    max_suite_width = max(
        (len(suite["checkIds"]) for suite in suites),
        default=0,
    )
    archive_pair_count = len(archives) * len(archives)
    suite_pair_count = len(suites) * len(suites)
    compiler_pair_count = len(compilers) * len(compilers)
    if suite_pair_count > MAX_EVIDENCE_PAIRS:
        raise ValueError("verifier-suite pair count exceeds the evidence limit")
    if compiler_pair_count > MAX_EVIDENCE_PAIRS:
        raise ValueError("compiler pair count exceeds the evidence limit")
    system_work = sum(
        len(system["coordinates"]) ** 2
        + target_count
        * max(1, len(system["coordinates"]))
        * (max_cost + 2)
        * (max_residual + 2)
        for system in systems
    )
    archive_work = (
        archive_pair_count
        * max(1, target_count)
        * max(1, max_coordinates)
        * (max_cost + 2)
    )
    suite_work = (
        suite_pair_count
        * max(1, len(outcomes))
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


def parse_manifest(raw_value: object) -> dict[str, Any]:
    raw = object_value(raw_value, "manifest")
    exact_keys(
        raw,
        {
            "schemaVersion", "id", "targets", "objectiveNames", "systems",
            "archives", "verifierSuites", "verificationOutcomes", "compilers",
        },
        "manifest",
    )
    if raw["schemaVersion"] != MANIFEST_SCHEMA:
        raise ValueError("unsupported finite-theory schemaVersion")
    theory_id = string_value(raw["id"], "manifest.id")
    targets = unique_strings(raw["targets"], "manifest.targets")
    objectives = unique_strings(raw["objectiveNames"], "manifest.objectiveNames")
    systems_raw = raw["systems"]
    if not isinstance(systems_raw, list) or not systems_raw:
        raise ValueError("manifest.systems must be a non-empty array")
    if len(systems_raw) > MAX_COLLECTION_ITEMS:
        raise ValueError("manifest.systems exceeds the finite collection limit")
    systems: list[dict[str, Any]] = []
    for system_index, system_value in enumerate(systems_raw):
        path = f"manifest.systems[{system_index}]"
        system_raw = object_value(system_value, path)
        exact_keys(system_raw, {"id", "encoding", "coordinates", "contentSha256"}, path)
        encoding_raw = object_value(system_raw["encoding"], f"{path}.encoding")
        exact_keys(encoding_raw, {"kind", "lengthWidth", "roleTags"}, f"{path}.encoding")
        if encoding_raw["kind"] != ENCODING_KIND:
            raise ValueError(f"{path}.encoding.kind is unsupported")
        width = nat_value(encoding_raw["lengthWidth"], f"{path}.encoding.lengthWidth")
        if width == 0 or width > MAX_LENGTH_WIDTH:
            raise ValueError(f"{path}.encoding.lengthWidth is outside the declared bounds")
        tags_raw = object_value(encoding_raw["roleTags"], f"{path}.encoding.roleTags")
        if not tags_raw or len(tags_raw) > MAX_ROLE_TAGS:
            raise ValueError(f"{path}.encoding.roleTags has invalid cardinality")
        tags = {
            string_value(role, f"{path}.encoding.roleTags key"): bit_string(
                tag, f"{path}.encoding.roleTags.{role}", allow_empty=False
            )
            for role, tag in tags_raw.items()
        }
        if not prefix_free(list(tags.values())):
            raise ValueError(f"{path}.encoding.roleTags is not prefix-free")
        coordinates_raw = system_raw["coordinates"]
        if not isinstance(coordinates_raw, list):
            raise ValueError(f"{path}.coordinates must be an array")
        if len(coordinates_raw) > MAX_COORDINATES_PER_SYSTEM:
            raise ValueError(f"{path}.coordinates exceeds the quadratic-work limit")
        coordinates: list[dict[str, Any]] = []
        for coordinate_index, coordinate_value in enumerate(coordinates_raw):
            coordinate_path = f"{path}.coordinates[{coordinate_index}]"
            coordinate = object_value(coordinate_value, coordinate_path)
            exact_keys(
                coordinate,
                {"id", "role", "payloadBits", "codeBits", "chargedBitCost", "rendering", "residuals", "objectives"},
                coordinate_path,
            )
            coordinate_id = string_value(coordinate["id"], f"{coordinate_path}.id")
            role = string_value(coordinate["role"], f"{coordinate_path}.role")
            if role not in tags:
                raise ValueError(f"{coordinate_path}.role is undeclared")
            payload = bit_string(coordinate["payloadBits"], f"{coordinate_path}.payloadBits")
            if len(payload) > (1 << width) - 1:
                raise ValueError(f"{coordinate_path}.payloadBits exceeds the length field")
            code = bit_string(coordinate["codeBits"], f"{coordinate_path}.codeBits", allow_empty=False)
            expected_code = tags[role] + format(len(payload), f"0{width}b") + payload
            if code != expected_code:
                raise ValueError(f"{coordinate_path}.codeBits does not match the declared encoding")
            cost = nat_value(coordinate["chargedBitCost"], f"{coordinate_path}.chargedBitCost")
            if cost != len(code):
                raise ValueError(f"{coordinate_path}.chargedBitCost does not charge the full code")
            rendering = string_value(coordinate["rendering"], f"{coordinate_path}.rendering")
            if rendering != f"{role}:{payload}":
                raise ValueError(f"{coordinate_path}.rendering is lossy or noncanonical")
            residuals_raw = object_value(coordinate["residuals"], f"{coordinate_path}.residuals")
            if set(residuals_raw) != set(targets):
                raise ValueError(f"{coordinate_path}.residuals must cover every target exactly")
            residuals = {
                target: nat_value(residuals_raw[target], f"{coordinate_path}.residuals.{target}")
                for target in targets
            }
            objectives_raw = object_value(coordinate["objectives"], f"{coordinate_path}.objectives")
            if set(objectives_raw) != set(objectives):
                raise ValueError(f"{coordinate_path}.objectives must cover every objective exactly")
            objective_values = {
                name: nat_value(objectives_raw[name], f"{coordinate_path}.objectives.{name}")
                for name in objectives
            }
            if objective_values.get("charged_bit_cost", cost) != cost:
                raise ValueError(f"{coordinate_path}.objectives disagrees with charged cost")
            for target in targets:
                if objective_values.get(f"{target}_residual", residuals[target]) != residuals[target]:
                    raise ValueError(f"{coordinate_path}.objectives disagrees with residuals")
            coordinates.append(
                {
                    "id": coordinate_id, "role": role, "payloadBits": payload,
                    "codeBits": code, "chargedBitCost": cost, "rendering": rendering,
                    "residuals": residuals, "objectives": objective_values,
                }
            )
        for field in ("id", "codeBits", "rendering"):
            values = [coordinate[field] for coordinate in coordinates]
            if len(values) != len(set(values)):
                raise ValueError(f"{path}.coordinates has duplicate {field}")
        codes = [coordinate["codeBits"] for coordinate in coordinates]
        if not prefix_free(codes):
            raise ValueError(f"{path}.coordinates is not prefix-free")
        if kraft_sum(codes) > 1:
            raise ValueError(f"{path}.coordinates violates the finite Kraft inequality")
        digest_payload = {key: system_raw[key] for key in system_raw if key != "contentSha256"}
        declared_digest = string_value(system_raw["contentSha256"], f"{path}.contentSha256")
        if declared_digest != sha256_json(digest_payload):
            raise ValueError(f"{path}.contentSha256 is stale")
        systems.append(
            {
                "id": string_value(system_raw["id"], f"{path}.id"),
                "coordinates": coordinates,
                "contentSha256": declared_digest,
            }
        )
    system_by_id = {system["id"]: system for system in systems}
    if len(system_by_id) != len(systems):
        raise ValueError("manifest.systems contains duplicate IDs")

    archives_raw = raw["archives"]
    if not isinstance(archives_raw, list) or len(archives_raw) > MAX_COLLECTION_ITEMS:
        raise ValueError("manifest.archives must be a bounded array")
    archives: list[dict[str, Any]] = []
    for index, archive_value in enumerate(archives_raw):
        path = f"manifest.archives[{index}]"
        archive = object_value(archive_value, path)
        exact_keys(archive, {"id", "systemId", "coordinateIds"}, path)
        system_id = string_value(archive["systemId"], f"{path}.systemId")
        if system_id not in system_by_id:
            raise ValueError(f"{path}.systemId is unknown")
        coordinate_ids = unique_strings(archive["coordinateIds"], f"{path}.coordinateIds", allow_empty=True)
        domain_ids = {coordinate["id"] for coordinate in system_by_id[system_id]["coordinates"]}
        if not set(coordinate_ids).issubset(domain_ids):
            raise ValueError(f"{path}.coordinateIds leaves the declared domain")
        archives.append({"id": string_value(archive["id"], f"{path}.id"), "systemId": system_id, "coordinateIds": coordinate_ids})
    if len({archive["id"] for archive in archives}) != len(archives):
        raise ValueError("manifest.archives contains duplicate IDs")

    suites_raw = raw["verifierSuites"]
    if not isinstance(suites_raw, list) or len(suites_raw) > MAX_COLLECTION_ITEMS:
        raise ValueError("manifest.verifierSuites must be a bounded array")
    suites: list[dict[str, Any]] = []
    for index, suite_value in enumerate(suites_raw):
        path = f"manifest.verifierSuites[{index}]"
        suite = object_value(suite_value, path)
        exact_keys(suite, {"id", "checkIds"}, path)
        suites.append({"id": string_value(suite["id"], f"{path}.id"), "checkIds": unique_strings(suite["checkIds"], f"{path}.checkIds", allow_empty=True)})
    if len({suite["id"] for suite in suites}) != len(suites):
        raise ValueError("manifest.verifierSuites contains duplicate IDs")
    check_ids = {check_id for suite in suites for check_id in suite["checkIds"]}
    outcomes_raw = raw["verificationOutcomes"]
    if not isinstance(outcomes_raw, list) or len(outcomes_raw) > MAX_COLLECTION_ITEMS:
        raise ValueError("manifest.verificationOutcomes must be a bounded array")
    outcomes = [unique_strings(outcome, f"manifest.verificationOutcomes[{index}]", allow_empty=True) for index, outcome in enumerate(outcomes_raw)]
    if any(not set(outcome).issubset(check_ids) for outcome in outcomes):
        raise ValueError("manifest.verificationOutcomes contains an unknown check ID")

    compilers_raw = raw["compilers"]
    if not isinstance(compilers_raw, list) or len(compilers_raw) > MAX_COLLECTION_ITEMS:
        raise ValueError("manifest.compilers must be a bounded array")
    compilers: list[dict[str, Any]] = []
    for index, compiler_value in enumerate(compilers_raw):
        path = f"manifest.compilers[{index}]"
        compiler = object_value(compiler_value, path)
        exact_keys(
            compiler,
            {"id", "sourceSystemId", "destinationSystemId", "sourceSystemContentSha256", "destinationSystemContentSha256", "costOverheadBits", "residualSlack", "mapping", "contentSha256"},
            path,
        )
        source_id = string_value(compiler["sourceSystemId"], f"{path}.sourceSystemId")
        destination_id = string_value(compiler["destinationSystemId"], f"{path}.destinationSystemId")
        if source_id not in system_by_id or destination_id not in system_by_id:
            raise ValueError(f"{path} names an unknown system")
        source = system_by_id[source_id]
        destination = system_by_id[destination_id]
        if compiler["sourceSystemContentSha256"] != source["contentSha256"] or compiler["destinationSystemContentSha256"] != destination["contentSha256"]:
            raise ValueError(f"{path} has a stale system digest")
        mapping_raw = object_value(compiler["mapping"], f"{path}.mapping")
        source_ids = [coordinate["id"] for coordinate in source["coordinates"]]
        if set(mapping_raw) != set(source_ids):
            raise ValueError(f"{path}.mapping must cover the source domain exactly")
        destination_ids = {coordinate["id"] for coordinate in destination["coordinates"]}
        mapping: dict[str, str] = {}
        for source_coordinate_id in source_ids:
            destination_coordinate_id = string_value(mapping_raw[source_coordinate_id], f"{path}.mapping.{source_coordinate_id}")
            if destination_coordinate_id not in destination_ids:
                raise ValueError(f"{path}.mapping leaves the destination domain")
            mapping[source_coordinate_id] = destination_coordinate_id
        overhead = nat_value(compiler["costOverheadBits"], f"{path}.costOverheadBits")
        slack = nat_value(compiler["residualSlack"], f"{path}.residualSlack")
        digest_payload = {key: compiler[key] for key in compiler if key != "contentSha256"}
        digest = string_value(compiler["contentSha256"], f"{path}.contentSha256")
        if digest != sha256_json(digest_payload):
            raise ValueError(f"{path}.contentSha256 is stale")
        source_points = {coordinate["id"]: coordinate for coordinate in source["coordinates"]}
        destination_points = {coordinate["id"]: coordinate for coordinate in destination["coordinates"]}
        for source_coordinate_id, destination_coordinate_id in mapping.items():
            source_point = source_points[source_coordinate_id]
            destination_point = destination_points[destination_coordinate_id]
            if destination_point["chargedBitCost"] > source_point["chargedBitCost"] + overhead:
                raise ValueError(f"{path} understates charged-cost overhead")
            if any(destination_point["residuals"][target] > source_point["residuals"][target] + slack for target in targets):
                raise ValueError(f"{path} understates residual slack")
        compilers.append(
            {
                "id": string_value(compiler["id"], f"{path}.id"),
                "sourceSystemId": source_id, "destinationSystemId": destination_id,
                "sourceSystemContentSha256": source["contentSha256"],
                "destinationSystemContentSha256": destination["contentSha256"],
                "costOverheadBits": overhead, "residualSlack": slack,
                "mapping": mapping, "contentSha256": digest,
            }
        )
    if len({compiler["id"] for compiler in compilers}) != len(compilers):
        raise ValueError("manifest.compilers contains duplicate IDs")
    manifest = {
        "schemaVersion": MANIFEST_SCHEMA,
        "id": theory_id,
        "targets": targets,
        "objectiveNames": objectives,
        "systems": systems,
        "systemById": system_by_id,
        "archives": archives,
        "verifierSuites": suites,
        "verificationOutcomes": outcomes,
        "compilers": compilers,
    }
    validate_work_budget(manifest)
    return manifest


def parse_statement_map(raw_value: object) -> dict[str, Any]:
    raw = object_value(raw_value, "statementMap")
    exact_keys(raw, {"schemaVersion", "theoryId", "statements"}, "statementMap")
    if raw["schemaVersion"] != STATEMENT_MAP_SCHEMA:
        raise ValueError("unsupported statement-map schemaVersion")
    theory_id = string_value(raw["theoryId"], "statementMap.theoryId")
    if theory_id != "finite-theory-v0":
        raise ValueError("statement map has an unexpected theory ID")
    statements_raw = raw["statements"]
    if not isinstance(statements_raw, list) or len(statements_raw) != len(STATEMENT_CONTRACT):
        raise ValueError("statement map must contain exactly 13 statements")
    statements = []
    for index, statement_value in enumerate(statements_raw):
        path = f"statementMap.statements[{index}]"
        statement = object_value(statement_value, path)
        exact_keys(statement, {"id", "claim", "assumptions", "pythonCheck", "leanModule", "leanTheorem", "scope", "review"}, path)
        statement_id = string_value(statement["id"], f"{path}.id")
        claim = string_value(statement["claim"], f"{path}.claim")
        assumptions = unique_strings(statement["assumptions"], f"{path}.assumptions", allow_empty=True)
        python_check = string_value(statement["pythonCheck"], f"{path}.pythonCheck")
        lean_module = string_value(statement["leanModule"], f"{path}.leanModule")
        lean_theorem = string_value(statement["leanTheorem"], f"{path}.leanTheorem")
        scope = string_value(statement["scope"], f"{path}.scope")
        review = object_value(statement["review"], f"{path}.review")
        exact_keys(review, {"status", "reviewer", "independence"}, f"{path}.review")
        if review["status"] != "approved":
            raise ValueError(f"{path}.review.status must be approved")
        reviewer = string_value(review["reviewer"], f"{path}.review.reviewer")
        if review["independence"] != "did_not_author_definitions":
            raise ValueError(f"{path}.review.independence is not sufficient")
        expected = STATEMENT_CONTRACT.get(statement_id)
        if expected != (python_check, lean_module, lean_theorem):
            raise ValueError(f"{path} does not match the fixed theorem/check contract")
        statements.append(
            {
                "id": statement_id, "claim": claim, "assumptions": assumptions,
                "pythonCheck": python_check, "leanModule": lean_module,
                "leanTheorem": lean_theorem, "scope": scope,
                "review": {"status": "approved", "reviewer": reviewer, "independence": "did_not_author_definitions"},
            }
        )
    if [statement["id"] for statement in statements] != list(STATEMENT_CONTRACT):
        raise ValueError("statement map IDs are missing, duplicated, or out of canonical order")
    if len({statement["pythonCheck"] for statement in statements}) != len(statements):
        raise ValueError("statement map reuses a Python check")
    if len({statement["leanTheorem"] for statement in statements}) != len(statements):
        raise ValueError("statement map reuses a Lean theorem")
    return {"schemaVersion": STATEMENT_MAP_SCHEMA, "theoryId": theory_id, "statements": statements}


def coordinate_by_id(system: Mapping[str, Any], coordinate_id: str) -> dict[str, Any]:
    for coordinate in system["coordinates"]:
        if coordinate["id"] == coordinate_id:
            return coordinate
    raise ValueError(f"unknown coordinate {coordinate_id!r} in {system['id']!r}")


def structure_value(
    coordinates: Iterable[Mapping[str, Any]],
    target: str,
    budget: int,
) -> int | None:
    feasible = [
        coordinate["residuals"][target]
        for coordinate in coordinates
        if coordinate["chargedBitCost"] <= budget
    ]
    return min(feasible) if feasible else None


def threshold_value(
    coordinates: Iterable[Mapping[str, Any]],
    target: str,
    residual_limit: int,
) -> int | None:
    feasible = [
        coordinate["chargedBitCost"]
        for coordinate in coordinates
        if coordinate["residuals"][target] <= residual_limit
    ]
    return min(feasible) if feasible else None


def two_part_direct(
    coordinates: Iterable[Mapping[str, Any]],
    target: str,
) -> int | None:
    values = [
        coordinate["chargedBitCost"] + coordinate["residuals"][target]
        for coordinate in coordinates
    ]
    return min(values) if values else None


def two_part_by_cost_levels(
    coordinates: Sequence[Mapping[str, Any]],
    target: str,
) -> int | None:
    values = []
    for budget in sorted({coordinate["chargedBitCost"] for coordinate in coordinates}):
        residual = structure_value(coordinates, target, budget)
        if residual is not None:
            values.append(budget + residual)
    return min(values) if values else None


def objective_vector(
    coordinate: Mapping[str, Any],
    objective_names: Sequence[str],
) -> tuple[int, ...]:
    return tuple(coordinate["objectives"][name] for name in objective_names)


def strictly_dominates(
    left: Mapping[str, Any],
    right: Mapping[str, Any],
    objective_names: Sequence[str],
) -> bool:
    left_vector = objective_vector(left, objective_names)
    right_vector = objective_vector(right, objective_names)
    return all(
        left_value <= right_value
        for left_value, right_value in zip(left_vector, right_vector)
    ) and any(
        left_value < right_value
        for left_value, right_value in zip(left_vector, right_vector)
    )


def pareto_representatives(
    coordinates: Sequence[dict[str, Any]],
    objective_names: Sequence[str],
) -> list[dict[str, Any]]:
    first_by_vector: dict[tuple[int, ...], dict[str, Any]] = {}
    for coordinate in coordinates:
        first_by_vector.setdefault(objective_vector(coordinate, objective_names), coordinate)
    representatives = list(first_by_vector.values())
    return [
        candidate
        for candidate in representatives
        if not any(
            strictly_dominates(other, candidate, objective_names)
            for other in representatives
            if other is not candidate
        )
    ]


def compiler_curve_transfer(
    compiler: Mapping[str, Any],
    source: Mapping[str, Any],
    destination: Mapping[str, Any],
    targets: Sequence[str],
) -> tuple[bool, int]:
    cases = 0
    for target in targets:
        max_cost = max(
            (coordinate["chargedBitCost"] for coordinate in source["coordinates"]),
            default=0,
        )
        for budget in range(max_cost + 2):
            cases += 1
            if not inf_le(
                structure_value(
                    destination["coordinates"],
                    target,
                    budget + compiler["costOverheadBits"],
                ),
                inf_add(
                    structure_value(source["coordinates"], target, budget),
                    compiler["residualSlack"],
                ),
            ):
                return False, cases
        max_residual = max(
            (
                coordinate["residuals"][target]
                for coordinate in source["coordinates"]
            ),
            default=0,
        )
        for residual_limit in range(max_residual + 2):
            cases += 1
            if not inf_le(
                threshold_value(
                    destination["coordinates"],
                    target,
                    residual_limit + compiler["residualSlack"],
                ),
                inf_add(
                    threshold_value(
                        source["coordinates"],
                        target,
                        residual_limit,
                    ),
                    compiler["costOverheadBits"],
                ),
            ):
                return False, cases
    return True, cases


def composable_pairs(
    manifest: Mapping[str, Any],
) -> Iterable[tuple[dict[str, Any], dict[str, Any]]]:
    for first in manifest["compilers"]:
        for second in manifest["compilers"]:
            if first["destinationSystemId"] == second["sourceSystemId"]:
                yield first, second


def opposite_pairs(
    manifest: Mapping[str, Any],
) -> Iterable[tuple[dict[str, Any], dict[str, Any]]]:
    for forward in manifest["compilers"]:
        for reverse in manifest["compilers"]:
            if (
                forward["sourceSystemId"]
                == reverse["destinationSystemId"]
                and forward["destinationSystemId"]
                == reverse["sourceSystemId"]
            ):
                yield forward, reverse


def compose_mapping(
    first: Mapping[str, Any],
    second: Mapping[str, Any],
    source: Mapping[str, Any],
) -> dict[str, str]:
    return {
        coordinate["id"]: second["mapping"][
            first["mapping"][coordinate["id"]]
        ]
        for coordinate in source["coordinates"]
    }


def validate_composed_bounds(
    first: Mapping[str, Any],
    second: Mapping[str, Any],
    source: Mapping[str, Any],
    destination: Mapping[str, Any],
    targets: Sequence[str],
) -> tuple[dict[str, str], bool]:
    mapping = compose_mapping(first, second, source)
    overhead = first["costOverheadBits"] + second["costOverheadBits"]
    slack = first["residualSlack"] + second["residualSlack"]
    valid = True
    for source_id, destination_id in mapping.items():
        source_point = coordinate_by_id(source, source_id)
        destination_point = coordinate_by_id(destination, destination_id)
        valid = (
            valid
            and destination_point["chargedBitCost"]
            <= source_point["chargedBitCost"] + overhead
        )
        valid = valid and all(
            destination_point["residuals"][target]
            <= source_point["residuals"][target] + slack
            for target in targets
        )
    return mapping, valid


def zero_slack_sandwich(
    forward: Mapping[str, Any],
    reverse: Mapping[str, Any],
    source: Mapping[str, Any],
    destination: Mapping[str, Any],
    targets: Sequence[str],
) -> bool:
    forward_ok, _ = compiler_curve_transfer(forward, source, destination, targets)
    reverse_ok, _ = compiler_curve_transfer(reverse, destination, source, targets)
    if not forward_ok or not reverse_ok:
        return False
    if forward["residualSlack"] != 0 or reverse["residualSlack"] != 0:
        return True
    for target in targets:
        max_residual = max(
            (
                coordinate["residuals"][target]
                for coordinate in source["coordinates"]
                + destination["coordinates"]
            ),
            default=0,
        )
        for residual_limit in range(max_residual + 2):
            source_threshold = threshold_value(
                source["coordinates"],
                target,
                residual_limit,
            )
            destination_threshold = threshold_value(
                destination["coordinates"],
                target,
                residual_limit,
            )
            if not inf_le(
                destination_threshold,
                inf_add(source_threshold, forward["costOverheadBits"]),
            ):
                return False
            if not inf_le(
                source_threshold,
                inf_add(destination_threshold, reverse["costOverheadBits"]),
            ):
                return False
    return True


def encoding_evidence(system: Mapping[str, Any]) -> dict[str, object]:
    coordinates = system["coordinates"]
    codes = [coordinate["codeBits"] for coordinate in coordinates]
    kraft = kraft_sum(codes)
    inversion = next(
        (
            [left["id"], right["id"]]
            for left in coordinates
            for right in coordinates
            if len(left["payloadBits"]) < len(right["payloadBits"])
            and left["chargedBitCost"] > right["chargedBitCost"]
        ),
        None,
    )
    return {
        "systemId": system["id"],
        "coordinateCount": len(coordinates),
        "prefixFree": prefix_free(codes),
        "injective": len(codes) == len(set(codes)),
        "losslessRendering": len(
            {coordinate["rendering"] for coordinate in coordinates}
        )
        == len(coordinates),
        "kraft": {
            "numerator": kraft.numerator,
            "denominator": kraft.denominator,
        },
        "rawChargedOrderInversionWitness": inversion,
    }


def system_evidence(
    system: Mapping[str, Any],
    targets: Sequence[str],
    objective_names: Sequence[str],
) -> dict[str, object]:
    coordinates = system["coordinates"]
    target_evidence: dict[str, object] = {}
    for target in targets:
        max_cost = max(
            (coordinate["chargedBitCost"] for coordinate in coordinates),
            default=0,
        )
        max_residual = max(
            (coordinate["residuals"][target] for coordinate in coordinates),
            default=0,
        )
        target_evidence[target] = {
            "maxCost": max_cost,
            "maxResidual": max_residual,
            "structure": [
                {
                    "budget": budget,
                    "value": structure_value(coordinates, target, budget),
                }
                for budget in range(max_cost + 2)
            ],
            "threshold": [
                {
                    "residualLimit": residual_limit,
                    "value": threshold_value(
                        coordinates,
                        target,
                        residual_limit,
                    ),
                }
                for residual_limit in range(max_residual + 2)
            ],
            "twoPart": {
                "direct": two_part_direct(coordinates, target),
                "byDeclaredCostLevels": two_part_by_cost_levels(
                    coordinates,
                    target,
                ),
            },
        }
    frontier = pareto_representatives(coordinates, objective_names)
    return {
        "systemId": system["id"],
        "targets": target_evidence,
        "pareto": {
            "policy": "first-source-occurrence-per-vector/v0",
            "candidateIds": [coordinate["id"] for coordinate in frontier],
            "objectiveVectors": [
                list(objective_vector(coordinate, objective_names))
                for coordinate in frontier
            ],
        },
    }


def append_pairs(
    manifest: Mapping[str, Any],
) -> Iterable[tuple[dict[str, Any], dict[str, Any]]]:
    for old in manifest["archives"]:
        for new in manifest["archives"]:
            if (
                old is not new
                and old["systemId"] == new["systemId"]
                and len(old["coordinateIds"]) <= len(new["coordinateIds"])
                and new["coordinateIds"][: len(old["coordinateIds"])]
                == old["coordinateIds"]
            ):
                yield old, new


def suite_pairs(
    manifest: Mapping[str, Any],
) -> Iterable[tuple[dict[str, Any], dict[str, Any]]]:
    for larger in manifest["verifierSuites"]:
        for subset in manifest["verifierSuites"]:
            if (
                larger is not subset
                and set(subset["checkIds"]).issubset(larger["checkIds"])
            ):
                yield larger, subset


def nonempty_all(values: Iterable[bool]) -> bool:
    seen = False
    for value in values:
        seen = True
        if not value:
            return False
    return seen


def statement_check_values(manifest: Mapping[str, Any]) -> dict[str, bool]:
    targets = manifest["targets"]
    systems = manifest["systems"]
    system_by_id = manifest["systemById"]

    ft01 = True
    ft02 = True
    ft03 = True
    ft04 = True
    for system in systems:
        coordinates = system["coordinates"]
        for target in targets:
            max_cost = max(
                (coordinate["chargedBitCost"] for coordinate in coordinates),
                default=0,
            )
            max_residual = max(
                (coordinate["residuals"][target] for coordinate in coordinates),
                default=0,
            )
            ft01 = ft01 and all(
                inf_le(structure_value(coordinates, target, budget), residual)
                == inf_le(threshold_value(coordinates, target, residual), budget)
                for budget in range(max_cost + 2)
                for residual in range(max_residual + 2)
            )
            structure_curve = [
                structure_value(coordinates, target, budget)
                for budget in range(max_cost + 2)
            ]
            threshold_curve = [
                threshold_value(coordinates, target, residual)
                for residual in range(max_residual + 2)
            ]
            ft02 = ft02 and all(
                inf_le(later, earlier)
                for earlier, later in zip(
                    structure_curve,
                    structure_curve[1:],
                )
            )
            ft03 = ft03 and all(
                inf_le(later, earlier)
                for earlier, later in zip(
                    threshold_curve,
                    threshold_curve[1:],
                )
            )
            ft04 = ft04 and (
                two_part_direct(coordinates, target)
                == two_part_by_cost_levels(coordinates, target)
            )

    ft05 = all(
        all(
            inf_le(
                structure_value(
                    system_by_id[archive["systemId"]]["coordinates"],
                    target,
                    budget,
                ),
                structure_value(
                    [
                        coordinate_by_id(
                            system_by_id[archive["systemId"]],
                            coordinate_id,
                        )
                        for coordinate_id in archive["coordinateIds"]
                    ],
                    target,
                    budget,
                ),
            )
            for budget in range(
                max(
                    (
                        coordinate["chargedBitCost"]
                        for coordinate in system_by_id[archive["systemId"]][
                            "coordinates"
                        ]
                    ),
                    default=0,
                )
                + 2
            )
        )
        for archive in manifest["archives"]
        for target in targets
    )
    ft06 = nonempty_all(
        all(
            inf_le(
                structure_value(
                    [
                        coordinate_by_id(
                            system_by_id[new["systemId"]],
                            coordinate_id,
                        )
                        for coordinate_id in new["coordinateIds"]
                    ],
                    target,
                    budget,
                ),
                structure_value(
                    [
                        coordinate_by_id(
                            system_by_id[old["systemId"]],
                            coordinate_id,
                        )
                        for coordinate_id in old["coordinateIds"]
                    ],
                    target,
                    budget,
                ),
            )
            for budget in range(
                max(
                    (
                        coordinate_by_id(
                            system_by_id[new["systemId"]],
                            coordinate_id,
                        )["chargedBitCost"]
                        for coordinate_id in new["coordinateIds"]
                    ),
                    default=0,
                )
                + 2
            )
        )
        for old, new in append_pairs(manifest)
        for target in targets
    )
    ft07 = nonempty_all(
        all(
            not set(larger["checkIds"]).issubset(outcome)
            or set(subset["checkIds"]).issubset(outcome)
            for outcome in manifest["verificationOutcomes"]
        )
        for larger, subset in suite_pairs(manifest)
    )
    ft08 = True
    ft09 = True
    for system in systems:
        coordinates = system["coordinates"]
        frontier = pareto_representatives(
            coordinates,
            manifest["objectiveNames"],
        )
        ft08 = ft08 and all(
            representative
            is coordinate_by_id(system, representative["id"])
            and not any(
                strictly_dominates(
                    other,
                    representative,
                    manifest["objectiveNames"],
                )
                for other in coordinates
                if other is not representative
            )
            for representative in frontier
        )
        nondominated_vectors = {
            objective_vector(candidate, manifest["objectiveNames"])
            for candidate in coordinates
            if not any(
                strictly_dominates(
                    other,
                    candidate,
                    manifest["objectiveNames"],
                )
                for other in coordinates
                if other is not candidate
            )
        }
        frontier_vectors = [
            objective_vector(candidate, manifest["objectiveNames"])
            for candidate in frontier
        ]
        ft09 = ft09 and (
            set(frontier_vectors) == nondominated_vectors
            and len(frontier_vectors) == len(set(frontier_vectors))
            and all(
                next(
                    coordinate
                    for coordinate in coordinates
                    if objective_vector(
                        coordinate,
                        manifest["objectiveNames"],
                    )
                    == vector
                )
                is next(
                    coordinate
                    for coordinate in frontier
                    if objective_vector(
                        coordinate,
                        manifest["objectiveNames"],
                    )
                    == vector
                )
                for vector in frontier_vectors
            )
        )

    fc01 = all(
        all(
            coordinate_by_id(
                system_by_id[compiler["destinationSystemId"]],
                destination_id,
            )["residuals"][target]
            <= coordinate_by_id(
                system_by_id[compiler["sourceSystemId"]],
                source_id,
            )["residuals"][target]
            + compiler["residualSlack"]
            for source_id, destination_id in compiler["mapping"].items()
            for target in targets
        )
        for compiler in manifest["compilers"]
    )
    fc02 = all(
        compiler_curve_transfer(
            compiler,
            system_by_id[compiler["sourceSystemId"]],
            system_by_id[compiler["destinationSystemId"]],
            targets,
        )[0]
        for compiler in manifest["compilers"]
    )
    fc03 = nonempty_all(
        validate_composed_bounds(
            first,
            second,
            system_by_id[first["sourceSystemId"]],
            system_by_id[second["destinationSystemId"]],
            targets,
        )[1]
        for first, second in composable_pairs(manifest)
    )
    fc04 = nonempty_all(
        zero_slack_sandwich(
            first,
            second,
            system_by_id[first["sourceSystemId"]],
            system_by_id[first["destinationSystemId"]],
            targets,
        )
        for first, second in opposite_pairs(manifest)
        if first["residualSlack"] == 0
        and second["residualSlack"] == 0
    )
    return {
        "FT-01": ft01,
        "FT-02": ft02,
        "FT-03": ft03,
        "FT-04": ft04,
        "FT-05": ft05,
        "FT-06": ft06,
        "FT-07": ft07,
        "FT-08": ft08,
        "FT-09": ft09,
        "FC-01": fc01,
        "FC-02": fc02,
        "FC-03": fc03,
        "FC-04": fc04,
    }


def build_expected_receipt(
    *,
    raw_manifest: object,
    manifest: Mapping[str, Any],
    manifest_path: Path,
    raw_statement_map: object,
    statement_map: Mapping[str, Any],
    statement_map_path: Path,
    repository_root: Path,
) -> dict[str, object]:
    checks = statement_check_values(manifest)
    if not all(checks.values()):
        failed = sorted(
            statement_id
            for statement_id, passed in checks.items()
            if not passed
        )
        raise ValueError(f"independent statement checks failed: {failed}")
    archive_evidence = []
    for archive in manifest["archives"]:
        system = manifest["systemById"][archive["systemId"]]
        subset = [
            coordinate_by_id(system, coordinate_id)
            for coordinate_id in archive["coordinateIds"]
        ]
        max_cost = max(
            (
                coordinate["chargedBitCost"]
                for coordinate in system["coordinates"]
            ),
            default=0,
        )
        is_upper_bound = all(
            inf_le(
                structure_value(
                    system["coordinates"],
                    target,
                    budget,
                ),
                structure_value(subset, target, budget),
            )
            for target in manifest["targets"]
            for budget in range(max_cost + 2)
        )
        archive_evidence.append(
            {
                "archiveId": archive["id"],
                "systemId": archive["systemId"],
                "coordinateIds": archive["coordinateIds"],
                "isDomainSubset": is_upper_bound,
            }
        )
    declared_suite_evidence = [
        {
            "subsetSuiteId": subset["id"],
            "largerSuiteId": larger["id"],
            "outcomesChecked": len(manifest["verificationOutcomes"]),
            "implicationHolds": all(
                not set(larger["checkIds"]).issubset(outcome)
                or set(subset["checkIds"]).issubset(outcome)
                for outcome in manifest["verificationOutcomes"]
            ),
        }
        for larger, subset in suite_pairs(manifest)
    ]
    compiler_evidence = []
    for compiler in manifest["compilers"]:
        source = manifest["systemById"][compiler["sourceSystemId"]]
        destination = manifest["systemById"][
            compiler["destinationSystemId"]
        ]
        source_ids = {
            coordinate["id"] for coordinate in source["coordinates"]
        }
        destination_ids = {
            coordinate["id"] for coordinate in destination["coordinates"]
        }
        compiler_evidence.append(
            {
                "compilerId": compiler["id"],
                "sourceSystemId": source["id"],
                "destinationSystemId": destination["id"],
                "costOverheadBits": compiler["costOverheadBits"],
                "residualSlack": compiler["residualSlack"],
                "sourceCoverage": set(compiler["mapping"]) == source_ids,
                "destinationMembership": set(
                    compiler["mapping"].values()
                ).issubset(destination_ids),
                "targetIndependent": all(
                    isinstance(destination_id, str)
                    for destination_id in compiler["mapping"].values()
                ),
                "costBound": all(
                    coordinate_by_id(
                        destination,
                        destination_id,
                    )["chargedBitCost"]
                    <= coordinate_by_id(
                        source,
                        source_id,
                    )["chargedBitCost"]
                    + compiler["costOverheadBits"]
                    for source_id, destination_id in compiler[
                        "mapping"
                    ].items()
                ),
                "residualBound": all(
                    coordinate_by_id(
                        destination,
                        destination_id,
                    )["residuals"][target]
                    <= coordinate_by_id(
                        source,
                        source_id,
                    )["residuals"][target]
                    + compiler["residualSlack"]
                    for source_id, destination_id in compiler[
                        "mapping"
                    ].items()
                    for target in manifest["targets"]
                ),
            }
        )
    composition_evidence = []
    for first, second in composable_pairs(manifest):
        source = manifest["systemById"][first["sourceSystemId"]]
        destination = manifest["systemById"][
            second["destinationSystemId"]
        ]
        mapping, valid = validate_composed_bounds(
            first,
            second,
            source,
            destination,
            manifest["targets"],
        )
        composition_evidence.append(
            {
                "firstCompilerId": first["id"],
                "secondCompilerId": second["id"],
                "sourceSystemId": source["id"],
                "destinationSystemId": destination["id"],
                "mapping": mapping,
                "costOverheadBits": first["costOverheadBits"]
                + second["costOverheadBits"],
                "residualSlack": first["residualSlack"]
                + second["residualSlack"],
                "valid": valid,
            }
        )
    return {
        "schemaVersion": RECEIPT_SCHEMA,
        "theoryId": statement_map["theoryId"],
        "fixtureId": manifest["id"],
        "manifest": {
            "fileSha256": sha256_file(manifest_path),
            "contentSha256": sha256_json(raw_manifest),
        },
        "statementMap": {
            "fileSha256": sha256_file(statement_map_path),
            "contentSha256": sha256_json(raw_statement_map),
        },
        "protectedBaseline": protected_baseline(repository_root),
        "encodingEvidence": [
            encoding_evidence(system) for system in manifest["systems"]
        ],
        "systemEvidence": [
            system_evidence(
                system,
                manifest["targets"],
                manifest["objectiveNames"],
            )
            for system in manifest["systems"]
        ],
        "archiveEvidence": archive_evidence,
        "suiteEvidence": declared_suite_evidence,
        "compilerEvidence": compiler_evidence,
        "compositionEvidence": composition_evidence,
        "statementChecks": [
            {
                "id": statement["id"],
                "pythonCheck": statement["pythonCheck"],
                "passed": checks[statement["id"]],
            }
            for statement in statement_map["statements"]
        ],
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


PYTHON_CHECKS = [
    "strict_json_schema",
    "protected_baseline_bytes",
    "encoding_and_cost",
    "finite_curves",
    "archives",
    "verifier_suites",
    "pareto",
    "compiler_bounds",
    "compiler_composition",
    "statement_map_bijection",
    "receipt_exact_reconstruction",
]


def build_python_verification(
    *,
    manifest: Mapping[str, Any],
    manifest_path: Path,
    statement_map: Mapping[str, Any],
    statement_map_path: Path,
    receipt: object,
    receipt_path: Path,
    expected_receipt: Mapping[str, Any],
    errors: Sequence[str] = (),
) -> dict[str, object]:
    all_errors = list(errors)
    actual_receipt_bytes = receipt_path.read_bytes()
    expected_receipt_bytes = rendered_json_bytes(expected_receipt)
    if actual_receipt_bytes != expected_receipt_bytes:
        all_errors.append(
            "receipt bytes differ from independent deterministic reconstruction"
        )
        if isinstance(receipt, dict):
            for key in expected_receipt:
                if canonical_json(receipt.get(key)) != canonical_json(
                    expected_receipt[key]
                ):
                    all_errors.append(f"receipt mismatch at top-level field: {key}")
            for key in receipt:
                if key not in expected_receipt:
                    all_errors.append(
                        f"receipt has unexpected top-level field: {key}"
                    )
        else:
            all_errors.append("receipt must be an object")
    return {
        "schemaVersion": VERIFICATION_SCHEMA,
        "theoryId": statement_map["theoryId"],
        "fixtureId": manifest["id"],
        "verified": not all_errors,
        "errors": sorted(set(all_errors)),
        "checks": PYTHON_CHECKS,
        "manifestFileSha256": sha256_file(manifest_path),
        "statementMapFileSha256": sha256_file(statement_map_path),
        "receiptFileSha256": sha256_file(receipt_path),
        "receiptContentSha256": sha256_json(receipt),
        "protectedBaselineContentSha256": expected_receipt[
            "protectedBaseline"
        ]["contentSha256"],
        "verifierSourceSha256": sha256_file(Path(__file__)),
        "verifierScope": (
            "independent_standard_library_reconstruction_not_Lean_"
            "or_English_semantics_verification"
        ),
    }


def public_theorem_names() -> tuple[str, ...]:
    names = tuple(
        f"{module}.{name}"
        for module, relative in LEAN_SOURCES.items()
        for name in PUBLIC_THEOREM_PATTERN.findall(
            (LEAN_ROOT / relative).read_text(encoding="utf-8")
        )
    )
    if len(names) != len(set(names)):
        raise ValueError("duplicate public Lean theorem declaration")
    expected = {
        theorem for _, _, theorem in STATEMENT_CONTRACT.values()
    }
    if set(names) != expected:
        raise ValueError(
            "public Lean theorem inventory changed "
            f"(missing={sorted(expected - set(names))}, "
            f"unexpected={sorted(set(names) - expected)})"
        )
    return names


def render_axiom_audit(theorem_names: Sequence[str]) -> str:
    imports = "\n".join(
        f"import {module}" for module in LEAN_SOURCES
    )
    commands = "\n".join(
        f"#check {name}\n#print axioms {name}" for name in theorem_names
    )
    return f"{imports}\n\n{commands}\n"


def parse_axiom_audit_output(
    output: str,
    theorem_names: Sequence[str],
) -> dict[str, tuple[str, ...]]:
    expected = set(theorem_names)
    found: dict[str, tuple[str, ...]] = {}
    lines = output.splitlines()
    index = 0
    while index < len(lines):
        line = lines[index]
        record = line
        if line.startswith("'") and " depends on axioms: [" in line:
            while not record.rstrip().endswith("]"):
                index += 1
                if index >= len(lines):
                    raise ValueError("truncated multiline Lean axiom-audit result")
                continuation = lines[index]
                if continuation.startswith("'"):
                    raise ValueError("interleaved multiline Lean axiom-audit result")
                record += " " + continuation.strip()
        dependency_match = AXIOM_DEPENDENCY_PATTERN.fullmatch(record)
        no_dependency_match = NO_AXIOM_DEPENDENCY_PATTERN.fullmatch(line)
        if dependency_match is not None:
            name = dependency_match.group(1)
            dependencies = tuple(
                sorted(
                    item.strip()
                    for item in dependency_match.group(2).split(",")
                    if item.strip()
                )
            )
        elif no_dependency_match is not None:
            name = no_dependency_match.group(1)
            dependencies = ()
        else:
            if line.startswith("'") and "axiom" in line:
                raise ValueError(f"malformed Lean axiom-audit result: {record}")
            index += 1
            continue
        if name in found:
            raise ValueError(f"duplicate axiom-audit result for {name}")
        found[name] = dependencies
        index += 1
    missing = sorted(expected - set(found))
    unexpected = sorted(set(found) - expected)
    if missing or unexpected:
        raise ValueError(
            "incomplete Lean axiom audit "
            f"(missing={missing}, unexpected={unexpected})"
        )
    return {name: found[name] for name in theorem_names}


def build_lean_verification(
    *,
    lake: Path,
    statement_map: Mapping[str, Any],
    statement_map_path: Path,
    protected_content_sha256: str,
) -> dict[str, object]:
    source_hashes = {
        module: {
            "path": str(relative),
            "fileSha256": sha256_file(LEAN_ROOT / relative),
        }
        for module, relative in LEAN_SOURCES.items()
    }
    forbidden_hits = {
        str(relative): sorted(
            set(
                FORBIDDEN_PROOF_PATTERN.findall(
                    (LEAN_ROOT / relative).read_text(encoding="utf-8")
                )
            )
        )
        for relative in LEAN_SOURCES.values()
    }
    if any(forbidden_hits.values()):
        raise ValueError(
            f"forbidden proof declarations found: {forbidden_hits}"
        )
    theorem_names = public_theorem_names()
    mapped_names = tuple(
        statement["leanTheorem"]
        for statement in statement_map["statements"]
    )
    if set(mapped_names) != set(theorem_names):
        raise ValueError("statement map does not cover the public theorem inventory")

    version_result = subprocess.run(
        [str(lake), "env", "lean", "--version"],
        cwd=LEAN_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    version_output = "\n".join(
        part for part in (version_result.stdout, version_result.stderr) if part
    )
    version_match = LEAN_VERSION_PATTERN.search(version_output)
    if version_match is None:
        raise ValueError("could not parse the Lean version")
    lean_version = version_match.group(1)
    expected_version = (
        (LEAN_ROOT / "lean-toolchain")
        .read_text(encoding="utf-8")
        .strip()
        .rsplit("v", 1)[-1]
    )
    if lean_version != expected_version or lean_version != "4.34.1":
        raise ValueError(
            f"Lean version {lean_version} does not match pinned 4.34.1"
        )
    for relative in LEAN_SOURCES.values():
        subprocess.run(
            [str(lake), "env", "lean", str(relative)],
            cwd=LEAN_ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
    subprocess.run(
        [str(lake), "build", "BoundedCoordinate.Compiler"],
        cwd=LEAN_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )

    audit_source = render_axiom_audit(theorem_names)
    with tempfile.TemporaryDirectory(
        prefix=".finite-theory-axiom-audit-",
        dir=LEAN_ROOT,
    ) as temporary_directory:
        audit_path = Path(temporary_directory) / "AxiomAudit.lean"
        audit_path.write_text(audit_source, encoding="utf-8")
        audit_result = subprocess.run(
            [str(lake), "env", "lean", str(audit_path)],
            cwd=LEAN_ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
    actual_axioms = parse_axiom_audit_output(
        "\n".join(
            part
            for part in (audit_result.stdout, audit_result.stderr)
            if part
        ),
        theorem_names,
    )
    mismatches = {
        name: {
            "expected": list(EXPECTED_PUBLIC_THEOREM_AXIOMS[name]),
            "actual": list(actual_axioms[name]),
        }
        for name in theorem_names
        if actual_axioms[name] != EXPECTED_PUBLIC_THEOREM_AXIOMS[name]
    }
    if mismatches:
        raise ValueError(f"unexpected Lean axiom dependencies: {mismatches}")
    compiled_modules = [
        {
            "module": module,
            "path": str(relative),
            "fileSha256": source_hashes[module]["fileSha256"],
        }
        for module, relative in LEAN_SOURCES.items()
    ]
    project_payload = {
        "lakefile": sha256_file(LEAN_ROOT / "lakefile.toml"),
        "lakeManifest": sha256_file(LEAN_ROOT / "lake-manifest.json"),
        "leanToolchain": sha256_file(LEAN_ROOT / "lean-toolchain"),
        "sources": source_hashes,
        "statementMap": sha256_file(statement_map_path),
    }
    return {
        "schemaVersion": LEAN_VERIFICATION_SCHEMA,
        "theoryId": statement_map["theoryId"],
        "toolchain": (
            LEAN_ROOT / "lean-toolchain"
        ).read_text(encoding="utf-8").strip(),
        "leanVersion": lean_version,
        "compiledModules": compiled_modules,
        "statementMapFileSha256": sha256_file(statement_map_path),
        "forbiddenProofDeclarations": forbidden_hits,
        "axiomAudit": {
            "method": "lean-print-axioms-exact-match/v0",
            "auditSourceContentSha256": sha256_bytes(
                audit_source.encode("utf-8")
            ),
            "mappedTheoremCount": len(theorem_names),
            "publicTheoremAxioms": {
                name: list(actual_axioms[name]) for name in theorem_names
            },
            "expectedDependenciesMatched": True,
        },
        "protectedBaselineContentSha256": protected_content_sha256,
        "projectContentSha256": sha256_json(project_payload),
        "compiled": True,
        "scope": (
            "encoded_finite_propositions_only_not_Python_English_intent_"
            "tokenizers_readability_or_LLM_runtime"
        ),
    }


def failure_verification(error: Exception) -> dict[str, object]:
    return {
        "schemaVersion": VERIFICATION_SCHEMA,
        "theoryId": None,
        "fixtureId": None,
        "verified": False,
        "errors": [f"{type(error).__name__}: {error}"],
        "checks": [],
        "verifierSourceSha256": sha256_file(Path(__file__)),
        "verifierScope": (
            "independent_standard_library_reconstruction_not_Lean_"
            "or_English_semantics_verification"
        ),
    }


def failure_lean_verification(error: Exception) -> dict[str, object]:
    return {
        "schemaVersion": LEAN_VERIFICATION_SCHEMA,
        "theoryId": None,
        "compiled": False,
        "errors": [f"{type(error).__name__}: {error}"],
        "scope": (
            "encoded_finite_propositions_only_not_Python_English_intent_"
            "tokenizers_readability_or_LLM_runtime"
        ),
    }


def validate_cli_paths(args: argparse.Namespace) -> None:
    input_paths = {
        args.manifest.resolve(),
        args.statement_map.resolve(),
        args.receipt.resolve(),
    }
    output_paths = [args.out.resolve()]
    if not args.no_lean:
        output_paths.append(args.lean_out.resolve())
    if len(output_paths) != len(set(output_paths)):
        raise ValueError("verification output paths must be distinct")
    collisions = sorted(
        str(path) for path in output_paths if path in input_paths
    )
    if collisions:
        raise ValueError(
            "verification outputs must not overwrite inputs: "
            + ", ".join(collisions)
        )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Independently reconstruct and audit Finite Theory v0."
    )
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument(
        "--statement-map",
        type=Path,
        default=DEFAULT_STATEMENT_MAP,
    )
    parser.add_argument("--receipt", type=Path, default=DEFAULT_RECEIPT)
    parser.add_argument("--out", type=Path, default=DEFAULT_VERIFICATION)
    parser.add_argument(
        "--lean-out",
        type=Path,
        default=DEFAULT_LEAN_VERIFICATION,
    )
    parser.add_argument("--lake", type=Path, default=Path("lake"))
    parser.add_argument(
        "--no-lean",
        action="store_true",
        help="Run only the independent Python reconstruction.",
    )
    args = parser.parse_args()
    try:
        validate_cli_paths(args)
    except ValueError as error:
        print(f"finite-theory independent reconstruction: failed ({error})")
        return 2
    try:
        raw_manifest = strict_json(args.manifest)
        manifest = parse_manifest(raw_manifest)
        if sha256_file(args.statement_map) != EXPECTED_STATEMENT_MAP_FILE_SHA256:
            raise ValueError(
                "statement map bytes differ from the independently reviewed digest"
            )
        raw_statement_map = strict_json(args.statement_map)
        statement_map = parse_statement_map(raw_statement_map)
        receipt = strict_json(args.receipt)
        expected_receipt = build_expected_receipt(
            raw_manifest=raw_manifest,
            manifest=manifest,
            manifest_path=args.manifest,
            raw_statement_map=raw_statement_map,
            statement_map=statement_map,
            statement_map_path=args.statement_map,
            repository_root=REPOSITORY_ROOT,
        )
        verification = build_python_verification(
            manifest=manifest,
            manifest_path=args.manifest,
            statement_map=statement_map,
            statement_map_path=args.statement_map,
            receipt=receipt,
            receipt_path=args.receipt,
            expected_receipt=expected_receipt,
        )
        write_json(args.out, verification)
        if not verification["verified"]:
            if not args.no_lean:
                write_json(
                    args.lean_out,
                    failure_lean_verification(
                        ValueError(
                            "Lean audit skipped because independent receipt "
                            "verification failed"
                        )
                    ),
                )
            print("finite-theory independent reconstruction: failed")
            return 1
        if not args.no_lean:
            lean_verification = build_lean_verification(
                lake=args.lake,
                statement_map=statement_map,
                statement_map_path=args.statement_map,
                protected_content_sha256=expected_receipt[
                    "protectedBaseline"
                ]["contentSha256"],
            )
            write_json(args.lean_out, lean_verification)
        print(
            "finite-theory independent reconstruction: ok "
            f"receipt_sha256={verification['receiptFileSha256']}"
        )
        return 0
    except (
        OSError,
        ValueError,
        json.JSONDecodeError,
        subprocess.CalledProcessError,
    ) as error:
        write_json(args.out, failure_verification(error))
        if not args.no_lean:
            write_json(args.lean_out, failure_lean_verification(error))
        print("finite-theory independent reconstruction: failed")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
