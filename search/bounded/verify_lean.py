from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import tempfile
from collections.abc import Mapping, Sequence
from pathlib import Path

from .generate_lean import render_frontier, render_problem
from .model import ProblemManifest, sha256_json, write_json


HERE = Path(__file__).resolve().parent
LEAN_ROOT = HERE / "lean"
DEFAULT_MANIFEST = HERE / "problem.json"
DEFAULT_RECEIPT = HERE / "results" / "receipt.json"
DEFAULT_ARCHIVE = HERE / "results" / "candidates.jsonl"
DEFAULT_OUTPUT = HERE / "results" / "lean-verification.json"
LEAN_VERSION_PATTERN = re.compile(r"Lean \(version ([0-9]+(?:\.[0-9]+)*)[,)]")
FORBIDDEN_PROOF_PATTERN = re.compile(r"\b(?:sorry|admit|axiom)\b")
PUBLIC_THEOREM_PATTERN = re.compile(
    r"^(?:theorem|lemma)\s+([A-Za-z_][A-Za-z0-9_']*)",
    re.MULTILINE,
)
AXIOM_DEPENDENCY_PATTERN = re.compile(
    r"^'([^']+)' depends on axioms: \[([^]]*)\]$"
)
NO_AXIOM_DEPENDENCY_PATTERN = re.compile(
    r"^'([^']+)' does not depend on any axioms$"
)
PROOF_SOURCES = (
    Path("BoundedCoordinate.lean"),
    Path("BoundedCoordinate/GeneratedProblem.lean"),
    Path("BoundedCoordinate/GeneratedFrontier.lean"),
    Path("BoundedCoordinate/Basic.lean"),
)
EXPECTED_PUBLIC_THEOREM_AXIOMS: dict[str, tuple[str, ...]] = {
    "BoundedCoordinate.token_mem_alphabet": ("propext",),
    "BoundedCoordinate.coordinate_mem_coordinatesOfLength": (
        "propext",
        "Quot.sound",
    ),
    "BoundedCoordinate.coordinate_mem_coordinatesUpTo_of_length_le": (
        "propext",
        "Quot.sound",
    ),
    "BoundedCoordinate.observe_mem_observationsUpTo_of_length_le": (
        "propext",
        "Quot.sound",
    ),
    "BoundedCoordinate.witness_has_length_four": (),
    "BoundedCoordinate.compositional_witness_reconstructs": (),
    "BoundedCoordinate.opaque_witness_reconstructs": (),
    "BoundedCoordinate.compositional_has_no_witness_of_length_le_three": (
        "propext",
        "Quot.sound",
    ),
    "BoundedCoordinate.opaque_has_no_witness_of_length_le_three": (
        "propext",
        "Quot.sound",
    ),
    "BoundedCoordinate.compositional_bounded_witness_is_unique": (
        "propext",
        "Quot.sound",
    ),
    "BoundedCoordinate.opaque_bounded_witness_is_unique": (
        "propext",
        "Quot.sound",
    ),
    "BoundedCoordinate.compositional_published_frontier_is_observed": (
        "propext",
        "Quot.sound",
    ),
    "BoundedCoordinate.opaque_published_frontier_is_observed": (
        "propext",
        "Quot.sound",
    ),
}


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def public_theorem_names() -> tuple[str, ...]:
    names = tuple(
        f"BoundedCoordinate.{name}"
        for relative in PROOF_SOURCES
        for name in PUBLIC_THEOREM_PATTERN.findall(
            (LEAN_ROOT / relative).read_text(encoding="utf-8")
        )
    )
    if len(names) != len(set(names)):
        raise ValueError("duplicate public Lean theorem declaration")
    declared = set(names)
    expected = set(EXPECTED_PUBLIC_THEOREM_AXIOMS)
    if declared != expected:
        missing = sorted(declared - expected)
        stale = sorted(expected - declared)
        raise ValueError(
            "public Lean theorem inventory changed; update the axiom contract "
            f"(missing expectations={missing}, stale expectations={stale})"
        )
    return names


def render_axiom_audit(theorem_names: Sequence[str]) -> str:
    commands = "\n".join(f"#print axioms {name}" for name in theorem_names)
    return f"import BoundedCoordinate\n\n{commands}\n"


def parse_axiom_audit_output(
    output: str,
    theorem_names: Sequence[str],
) -> dict[str, tuple[str, ...]]:
    expected = set(theorem_names)
    found: dict[str, tuple[str, ...]] = {}
    for line in output.splitlines():
        dependency_match = AXIOM_DEPENDENCY_PATTERN.fullmatch(line)
        no_dependency_match = NO_AXIOM_DEPENDENCY_PATTERN.fullmatch(line)
        if dependency_match is not None:
            name = dependency_match.group(1)
            dependencies = tuple(
                item.strip()
                for item in dependency_match.group(2).split(",")
                if item.strip()
            )
        elif no_dependency_match is not None:
            name = no_dependency_match.group(1)
            dependencies = ()
        else:
            continue
        if name in found:
            raise ValueError(f"duplicate axiom-audit result for {name}")
        found[name] = dependencies

    missing = sorted(expected - set(found))
    unexpected = sorted(set(found) - expected)
    if missing or unexpected:
        raise ValueError(
            "incomplete Lean axiom audit "
            f"(missing={missing}, unexpected={unexpected})"
        )
    return {name: found[name] for name in theorem_names}


def audit_public_theorem_axioms(lake: Path) -> dict[str, tuple[str, ...]]:
    theorem_names = public_theorem_names()
    source = render_axiom_audit(theorem_names)
    with tempfile.TemporaryDirectory(prefix=".axiom-audit-", dir=LEAN_ROOT) as temp_dir:
        audit_path = Path(temp_dir) / "AxiomAudit.lean"
        audit_path.write_text(source, encoding="utf-8")
        result = subprocess.run(
            [str(lake), "env", "lean", str(audit_path)],
            cwd=LEAN_ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
    actual = parse_axiom_audit_output(
        "\n".join(part for part in (result.stdout, result.stderr) if part),
        theorem_names,
    )
    mismatches = {
        name: {
            "expected": list(EXPECTED_PUBLIC_THEOREM_AXIOMS[name]),
            "actual": list(actual[name]),
        }
        for name in theorem_names
        if actual[name] != EXPECTED_PUBLIC_THEOREM_AXIOMS[name]
    }
    if mismatches:
        raise SystemExit(f"unexpected Lean axiom dependencies: {mismatches}")
    return actual


def expected_lean_receipt(
    manifest: ProblemManifest,
    *,
    lean_version: str,
    public_theorem_axioms: Mapping[str, Sequence[str]] | None = None,
    receipt_path: Path = DEFAULT_RECEIPT,
    archive_path: Path = DEFAULT_ARCHIVE,
) -> dict[str, object]:
    generated_path = LEAN_ROOT / "BoundedCoordinate" / "GeneratedProblem.lean"
    generated_frontier_path = (
        LEAN_ROOT / "BoundedCoordinate" / "GeneratedFrontier.lean"
    )
    generated_current = generated_path.read_text(encoding="utf-8") == render_problem(manifest)
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    candidate_archive = [
        json.loads(line)
        for line in archive_path.read_text(encoding="utf-8").splitlines()
        if line
    ]
    rendered_frontier = render_frontier(
        manifest,
        receipt,
        candidate_archive,
        receipt_file_sha256=_sha256_file(receipt_path),
        archive_file_sha256=_sha256_file(archive_path),
    )
    generated_frontier_current = (
        generated_frontier_path.read_text(encoding="utf-8") == rendered_frontier
    )
    source_hashes = {
        str(relative): _sha256_file(LEAN_ROOT / relative) for relative in PROOF_SOURCES
    }
    forbidden_hits = {
        str(relative): sorted(
            set(
                FORBIDDEN_PROOF_PATTERN.findall(
                    (LEAN_ROOT / relative).read_text(encoding="utf-8")
                )
            )
        )
        for relative in PROOF_SOURCES
    }
    toolchain = (LEAN_ROOT / "lean-toolchain").read_text(encoding="utf-8").strip()
    theorem_names = public_theorem_names()
    axiom_source = render_axiom_audit(theorem_names)
    theorem_axioms = public_theorem_axioms or EXPECTED_PUBLIC_THEOREM_AXIOMS
    if set(theorem_axioms) != set(theorem_names):
        raise ValueError("Lean axiom receipt does not cover every public theorem")
    normalized_axioms = {
        name: list(theorem_axioms[name]) for name in theorem_names
    }
    return {
        "schemaVersion": "bounded-coordinate-lean-verification/v0",
        "problemId": manifest.problem_id,
        "manifestContentSha256": manifest.manifest_hash,
        "toolchain": toolchain,
        "leanVersion": lean_version,
        "generatedProblemCurrent": generated_current,
        "generatedFrontierCurrent": generated_frontier_current,
        "forbiddenProofDeclarations": forbidden_hits,
        "axiomAudit": {
            "method": "lean_print_axioms_exact_dependency_match_v0",
            "auditSourceContentSha256": hashlib.sha256(
                axiom_source.encode("utf-8")
            ).hexdigest(),
            "publicTheoremCount": len(theorem_names),
            "publicTheoremAxioms": normalized_axioms,
            "expectedDependenciesMatched": True,
        },
        "sourceContentSha256": source_hashes,
        "projectContentSha256": sha256_json(
            {
                "lakefile": _sha256_file(LEAN_ROOT / "lakefile.toml"),
                "lakeManifest": _sha256_file(LEAN_ROOT / "lake-manifest.json"),
                "leanToolchain": _sha256_file(LEAN_ROOT / "lean-toolchain"),
                "sources": source_hashes,
            }
        ),
        "compiled": True,
        "provedClaims": [
            "declared_witness_reconstructs_in_both_decoders",
            "all_coordinates_of_length_at_most_three_fail_in_both_decoders",
            "the_bounded_exact_witness_is_unique_through_length_four_in_both_decoders",
            "published_frontier_observations_are_unchanged_members_of_the_bounded_enumeration",
        ],
        "scope": "generated_finite_model_and_published_frontier_membership_not_python_algorithm_verification",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Build and receipt the bounded Lean proof.")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--receipt", type=Path, default=DEFAULT_RECEIPT)
    parser.add_argument("--archive", type=Path, default=DEFAULT_ARCHIVE)
    parser.add_argument("--lake", type=Path, default=Path("lake"))
    parser.add_argument("--out", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    manifest = ProblemManifest.from_path(args.manifest)
    generated_path = LEAN_ROOT / "BoundedCoordinate" / "GeneratedProblem.lean"
    if generated_path.read_text(encoding="utf-8") != render_problem(manifest):
        raise SystemExit("generated Lean definitions are stale")
    generated_frontier_path = (
        LEAN_ROOT / "BoundedCoordinate" / "GeneratedFrontier.lean"
    )
    receipt = json.loads(args.receipt.read_text(encoding="utf-8"))
    candidate_archive = [
        json.loads(line)
        for line in args.archive.read_text(encoding="utf-8").splitlines()
        if line
    ]
    rendered_frontier = render_frontier(
        manifest,
        receipt,
        candidate_archive,
        receipt_file_sha256=_sha256_file(args.receipt),
        archive_file_sha256=_sha256_file(args.archive),
    )
    if generated_frontier_path.read_text(encoding="utf-8") != rendered_frontier:
        raise SystemExit("generated Lean frontier definitions are stale")
    for relative in PROOF_SOURCES:
        source = (LEAN_ROOT / relative).read_text(encoding="utf-8")
        if FORBIDDEN_PROOF_PATTERN.search(source):
            raise SystemExit(f"forbidden proof placeholder in {relative}")

    version_result = subprocess.run(
        [str(args.lake), "env", "lean", "--version"],
        cwd=LEAN_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    version_output = version_result.stdout.strip()
    match = LEAN_VERSION_PATTERN.search(version_output)
    if match is None:
        raise SystemExit(f"could not parse Lean version: {version_output}")
    lean_version = match.group(1)
    expected_version = (LEAN_ROOT / "lean-toolchain").read_text(encoding="utf-8").strip().rsplit("v", 1)[-1]
    if lean_version != expected_version:
        raise SystemExit(
            f"Lean version {lean_version} does not match pinned toolchain {expected_version}"
        )

    build_result = subprocess.run(
        [str(args.lake), "build"],
        cwd=LEAN_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    public_theorem_axioms = audit_public_theorem_axioms(args.lake)
    receipt = expected_lean_receipt(
        manifest,
        lean_version=lean_version,
        public_theorem_axioms=public_theorem_axioms,
        receipt_path=args.receipt,
        archive_path=args.archive,
    )
    write_json(args.out, receipt)
    print(build_result.stdout.strip() or "lake build: ok")
    print(
        "bounded-coordinate Lean verification: ok "
        f"project_sha256={receipt['projectContentSha256']}"
    )


if __name__ == "__main__":
    main()
