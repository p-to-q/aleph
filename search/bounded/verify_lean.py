from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path

from .generate_lean import render_problem
from .model import ProblemManifest, sha256_json, write_json


HERE = Path(__file__).resolve().parent
LEAN_ROOT = HERE / "lean"
DEFAULT_MANIFEST = HERE / "problem.json"
DEFAULT_OUTPUT = HERE / "results" / "lean-verification.json"
LEAN_VERSION_PATTERN = re.compile(r"Lean \(version ([0-9]+(?:\.[0-9]+)*)[,)]")
FORBIDDEN_PROOF_PATTERN = re.compile(r"\b(?:sorry|admit|axiom)\b")
PROOF_SOURCES = (
    Path("BoundedCoordinate.lean"),
    Path("BoundedCoordinate/GeneratedProblem.lean"),
    Path("BoundedCoordinate/Basic.lean"),
)


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def expected_lean_receipt(
    manifest: ProblemManifest,
    *,
    lean_version: str,
) -> dict[str, object]:
    generated_path = LEAN_ROOT / "BoundedCoordinate" / "GeneratedProblem.lean"
    generated_current = generated_path.read_text(encoding="utf-8") == render_problem(manifest)
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
    return {
        "schemaVersion": "bounded-coordinate-lean-verification/v0",
        "problemId": manifest.problem_id,
        "manifestContentSha256": manifest.manifest_hash,
        "toolchain": toolchain,
        "leanVersion": lean_version,
        "generatedProblemCurrent": generated_current,
        "forbiddenProofDeclarations": forbidden_hits,
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
        ],
        "scope": "generated_finite_formal_model_not_python_receipt_or_frontier_verification",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Build and receipt the bounded Lean proof.")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--lake", type=Path, default=Path("lake"))
    parser.add_argument("--out", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    manifest = ProblemManifest.from_path(args.manifest)
    generated_path = LEAN_ROOT / "BoundedCoordinate" / "GeneratedProblem.lean"
    if generated_path.read_text(encoding="utf-8") != render_problem(manifest):
        raise SystemExit("generated Lean definitions are stale")
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
    receipt = expected_lean_receipt(manifest, lean_version=lean_version)
    write_json(args.out, receipt)
    print(build_result.stdout.strip() or "lake build: ok")
    print(
        "bounded-coordinate Lean verification: ok "
        f"project_sha256={receipt['projectContentSha256']}"
    )


if __name__ == "__main__":
    main()
