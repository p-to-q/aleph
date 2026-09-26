from __future__ import annotations

import argparse
import hashlib
import itertools
import json
from fractions import Fraction
from pathlib import Path
from typing import Mapping, Sequence

from .model import ProblemManifest, sha256_file, sha256_json, write_json


HERE = Path(__file__).resolve().parent
DEFAULT_MANIFEST = HERE / "problem.json"
DEFAULT_RECEIPT = HERE / "results" / "receipt.json"
DEFAULT_ARCHIVE = HERE / "results" / "candidates.jsonl"
DEFAULT_VERIFICATION = HERE / "results" / "verification.json"
LANDSCAPES = ("compositional", "opaque")
PRIORITY_POLICY_SEED = 1729
RECEIPT_VERSION = "bounded-coordinate-receipt/v0"
VERIFICATION_VERSION = "bounded-coordinate-verification/v0"
SHA256_PRIORITY_POLICY = "sha256_priority_without_replacement_v0"
DEFAULT_MAX_CANDIDATE_COUNT = 100_000


def _matched_search_budget(manifest: ProblemManifest) -> int:
    return len(manifest.alphabet) * manifest.max_coordinate_tokens


def _search_space_content_hash(manifest: ProblemManifest) -> str:
    return _canonical_hash(
        {
            "alphabet": list(manifest.alphabet),
            "maxCoordinateTokens": manifest.max_coordinate_tokens,
        }
    )


def _independent_decode(
    manifest: ProblemManifest,
    landscape: str,
    coordinate: Sequence[str],
) -> str:
    if landscape == "compositional":
        return "".join(manifest.compositional_chunks[token] for token in coordinate)
    return (
        manifest.target
        if tuple(coordinate) == manifest.opaque_witness
        else manifest.opaque_fallback
    )


def _canonical_json(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _canonical_hash(value: object) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _archive_jsonl_bytes(records: list[dict[str, object]]) -> bytes:
    return "".join(f"{_canonical_json(record)}\n" for record in records).encode("utf-8")


def _candidate_json(
    manifest: ProblemManifest,
    landscape: str,
    coordinate: tuple[str, ...],
) -> dict[str, object]:
    output = _independent_decode(manifest, landscape, coordinate)
    matches = sum(
        1
        for index in range(max(len(manifest.target), len(output)))
        if index < len(manifest.target)
        and index < len(output)
        and manifest.target[index] == output[index]
    )
    identity = {
        "manifestContentSha256": manifest.manifest_hash,
        "landscape": landscape,
        "coordinate": list(coordinate),
    }
    return {
        "id": f"candidate-{_canonical_hash(identity)}",
        "landscape": landscape,
        "coordinate": list(coordinate),
        "length": len(coordinate),
        "output": output,
        "matches": matches,
        "targetLength": len(manifest.target),
        "outputLength": len(output),
        "comparisonLength": max(len(manifest.target), len(output)),
        "fit": matches / max(len(manifest.target), len(output)),
        "exact": output == manifest.target,
    }


def _archive(manifest: ProblemManifest, landscape: str) -> list[dict[str, object]]:
    return [
        _candidate_json(manifest, landscape, coordinate)
        for length in range(manifest.max_coordinate_tokens + 1)
        for coordinate in itertools.product(manifest.alphabet, repeat=length)
    ]


def _frontier(archive: list[dict[str, object]]) -> list[dict[str, object]]:
    best_by_length: dict[int, dict[str, object]] = {}
    for point in archive:
        length = int(point["length"])
        incumbent = best_by_length.get(length)
        key = (
            -Fraction(int(point["matches"]), int(point["comparisonLength"])),
            str(point["id"]),
        )
        if incumbent is None or key < (
            -Fraction(int(incumbent["matches"]), int(incumbent["comparisonLength"])),
            str(incumbent["id"]),
        ):
            best_by_length[length] = point
    result = []
    best_fit = Fraction(-1, 1)
    for point in sorted(best_by_length.values(), key=lambda item: int(item["length"])):
        point_fit = Fraction(int(point["matches"]), int(point["comparisonLength"]))
        if point_fit > best_fit:
            result.append(point)
            best_fit = point_fit
    return result


def _budget_curve(
    archive: list[dict[str, object]],
    max_budget: int,
) -> list[dict[str, object]]:
    result = []
    for budget in range(max_budget + 1):
        eligible = [point for point in archive if int(point["length"]) <= budget]
        witness = min(
            eligible,
            key=lambda point: (
                -Fraction(int(point["matches"]), int(point["comparisonLength"])),
                int(point["length"]),
                str(point["id"]),
            ),
        )
        result.append(
            {
                "coordinateTokenBudget": budget,
                "witnessCandidateId": witness["id"],
                "witnessLength": witness["length"],
                "matches": witness["matches"],
                "targetLength": witness["targetLength"],
                "outputLength": witness["outputLength"],
                "comparisonLength": witness["comparisonLength"],
                "fit": witness["fit"],
                "exact": witness["exact"],
            }
        )
    return result


def _first_hit(points: Sequence[Mapping[str, object]]) -> int | None:
    for index, point in enumerate(points, start=1):
        if point["exact"] is True:
            return index
    return None


def _exhaustive_run(
    landscape: str,
    archive: list[dict[str, object]],
) -> dict[str, object]:
    first_hit = _first_hit(archive)
    return {
        "id": f"{landscape}:exhaustive",
        "landscape": landscape,
        "policy": "length_then_lexicographic_exhaustive_v0",
        "evaluationBudget": len(archive),
        "seed": None,
        "evaluationCandidateIds": [point["id"] for point in archive],
        "lineage": [],
        "firstHitEvaluationOrdinal": first_hit,
        "success": first_hit is not None,
        "candidateEvaluatorCalls": len(archive),
        "logicalAdaptiveRounds": 1,
    }


def _beam_run(
    manifest: ProblemManifest,
    landscape: str,
) -> dict[str, object]:
    beams: list[tuple[str, ...]] = [()]
    evaluated: list[dict[str, object]] = []
    lineage = []
    first_hit: int | None = None
    for depth in range(1, manifest.max_coordinate_tokens + 1):
        children = []
        observations_by_coordinate = {}
        for parent in beams:
            for token in manifest.alphabet:
                child = parent + (token,)
                point = _candidate_json(manifest, landscape, child)
                children.append(child)
                observations_by_coordinate[child] = point
                evaluated.append(point)
                lineage.append(
                    {
                        "candidateId": point["id"],
                        "parentCoordinate": list(parent),
                        "operator": f"append:{token}",
                        "depth": depth,
                    }
                )
                if first_hit is None and point["exact"] is True:
                    first_hit = len(evaluated)
        children.sort(
            key=lambda item: (
                -Fraction(
                    int(observations_by_coordinate[item]["matches"]),
                    int(observations_by_coordinate[item]["comparisonLength"]),
                ),
                item,
            )
        )
        beams = children[:1]
    return {
        "id": f"{landscape}:beam-1",
        "landscape": landscape,
        "policy": "fit_guided_beam_v0",
        "beamWidth": 1,
        "evaluationBudget": len(evaluated),
        "seed": None,
        "evaluationCandidateIds": [point["id"] for point in evaluated],
        "lineage": lineage,
        "firstHitEvaluationOrdinal": first_hit,
        "success": first_hit is not None,
        "candidateEvaluatorCalls": len(evaluated),
        "logicalAdaptiveRounds": manifest.max_coordinate_tokens,
    }


def _priority_run(
    manifest: ProblemManifest,
    landscape: str,
    budget: int,
) -> dict[str, object]:
    coordinates = [
        coordinate
        for length in range(1, manifest.max_coordinate_tokens + 1)
        for coordinate in itertools.product(manifest.alphabet, repeat=length)
    ]
    ranked_coordinates = sorted(
        coordinates,
        key=lambda coordinate: (
            _canonical_hash(
                {
                    "policy": SHA256_PRIORITY_POLICY,
                    "seed": PRIORITY_POLICY_SEED,
                    "searchSpaceContentSha256": _search_space_content_hash(manifest),
                    "coordinate": list(coordinate),
                }
            ),
            coordinate,
        ),
    )
    sampled_coordinates = ranked_coordinates[:budget]
    sampled = [
        _candidate_json(manifest, landscape, coordinate)
        for coordinate in sampled_coordinates
    ]
    first_hit = _first_hit(sampled)
    return {
        "id": f"{landscape}:priority-{budget}-seed-{PRIORITY_POLICY_SEED}",
        "landscape": landscape,
        "policy": SHA256_PRIORITY_POLICY,
        "evaluationBudget": budget,
        "seed": PRIORITY_POLICY_SEED,
        "evaluationCandidateIds": [point["id"] for point in sampled],
        "lineage": [],
        "firstHitEvaluationOrdinal": first_hit,
        "success": first_hit is not None,
        "candidateEvaluatorCalls": len(sampled),
        "logicalAdaptiveRounds": 1 if sampled else 0,
    }


def independently_rebuild_receipt(
    manifest: ProblemManifest,
    *,
    max_candidate_count: int = DEFAULT_MAX_CANDIDATE_COUNT,
    archive_path: str = DEFAULT_ARCHIVE.name,
) -> dict[str, object]:
    if max_candidate_count <= 0:
        raise ValueError("max_candidate_count must be positive")
    domain_size = sum(
        len(manifest.alphabet) ** length
        for length in range(manifest.max_coordinate_tokens + 1)
    )
    if domain_size > max_candidate_count:
        raise ValueError(
            "bounded domain has "
            f"{domain_size} candidates per landscape, exceeding the explicit "
            f"limit {max_candidate_count}"
        )
    all_archives = {landscape: _archive(manifest, landscape) for landscape in LANDSCAPES}
    landscape_results = {}
    search_runs = []
    matched_budget = _matched_search_budget(manifest)
    for landscape in LANDSCAPES:
        archive = all_archives[landscape]
        exact = [point for point in archive if point["exact"] is True]
        optimum = min(exact, key=lambda point: (int(point["length"]), str(point["id"])))
        landscape_runs = [
            _exhaustive_run(landscape, archive),
            _beam_run(manifest, landscape),
            _priority_run(manifest, landscape, matched_budget),
        ]
        additional_policy_work = sum(
            int(run["candidateEvaluatorCalls"])
            for run in landscape_runs
            if run["policy"] != "length_then_lexicographic_exhaustive_v0"
        )
        landscape_results[landscape] = {
            "candidateCount": len(archive),
            "archiveContentSha256": sha256_json(archive),
            "exactShortestWithinBound": {
                "candidateId": optimum["id"],
                "coordinate": optimum["coordinate"],
                "length": optimum["length"],
            },
            "representativeFrontier": {
                "policy": "best_per_length_then_strict_fit_improvements_v0",
                "sameObjectiveTieBreak": "candidate_id_code_unit_ascending",
                "candidateIds": [point["id"] for point in _frontier(archive)],
            },
            "budgetValueCurve": _budget_curve(archive, manifest.max_coordinate_tokens),
            "executionAccounting": {
                "certificateArchiveEvaluatorCalls": len(archive),
                "additionalPolicyEvaluatorCalls": additional_policy_work,
                "totalCandidateEvaluatorCalls": len(archive) + additional_policy_work,
                "archiveReusedByExhaustivePolicy": True,
            },
        }
        search_runs.extend(landscape_runs)

    comp_shortest = landscape_results["compositional"]["exactShortestWithinBound"]
    opaque_shortest = landscape_results["opaque"]["exactShortestWithinBound"]
    comp_beam = next(run for run in search_runs if run["id"] == "compositional:beam-1")
    opaque_beam = next(run for run in search_runs if run["id"] == "opaque:beam-1")
    candidate_archive = [
        point
        for landscape in LANDSCAPES
        for point in all_archives[landscape]
    ]
    archive_bytes = _archive_jsonl_bytes(candidate_archive)
    return {
        "schemaVersion": RECEIPT_VERSION,
        "problemId": manifest.problem_id,
        "manifestContentSha256": manifest.manifest_hash,
        "runPolicy": {
            "landscapes": list(LANDSCAPES),
            "coordinateOrder": "length_then_lexicographic",
            "searchSpaceContentSha256": _search_space_content_hash(manifest),
            "policyInputBoundary": "alphabet_max_tokens_and_evaluator_callback_only",
            "domainGuard": {
                "computedCandidateCountPerLandscape": domain_size,
                "maxCandidateCountPerLandscape": max_candidate_count,
            },
            "matchedEvaluationBudget": matched_budget,
            "prioritySeed": PRIORITY_POLICY_SEED,
            "workAccounting": {
                "candidateEvaluatorCalls": "actual_calls_for_the_named_policy",
                "logicalAdaptiveRounds": "policy_dependency_depth_with_unbounded_parallelism",
                "firstHitEvaluationOrdinal": "ordinal_in_deterministic_evaluator_call_order",
                "evaluationCandidateIds": "deterministic_call_order_not_wall_clock",
                "certificateBoundary": "archive_materialization_is_reused_by_exhaustive_and_separate_from_other_policies",
            },
            "timingFields": "excluded_for_byte_stability",
        },
        "candidateArchive": {
            "format": "canonical-jsonl/v0",
            "path": archive_path,
            "count": len(candidate_archive),
            "contentSha256": _canonical_hash(candidate_archive),
            "fileSha256": hashlib.sha256(archive_bytes).hexdigest(),
        },
        "landscapeResults": landscape_results,
        "searchRuns": search_runs,
        "claims": {
            "sameExactShortestLength": comp_shortest["length"] == opaque_shortest["length"],
            "sameExactWitness": comp_shortest["coordinate"] == opaque_shortest["coordinate"],
            "beamDiscoveryGap": {
                "compositionalFirstHitEvaluationOrdinal": comp_beam[
                    "firstHitEvaluationOrdinal"
                ],
                "opaqueFirstHitEvaluationOrdinal": opaque_beam[
                    "firstHitEvaluationOrdinal"
                ],
                "compositionalSuccess": comp_beam["success"],
                "opaqueSuccess": opaque_beam["success"],
            },
        },
        "claimScope": {
            "domain": "finite_synthetic",
            "generalization": "constructive_existence_example_only",
            "llmEvidence": False,
            "pythonVerifier": "independent_reconstruction_with_shared_manifest_parser",
        },
    }


def verify_receipt_data(
    manifest: ProblemManifest,
    receipt: object,
    *,
    max_candidate_count: int = DEFAULT_MAX_CANDIDATE_COUNT,
    archive_path: str = DEFAULT_ARCHIVE.name,
) -> list[str]:
    if not isinstance(receipt, dict):
        return ["receipt must be an object"]
    expected = independently_rebuild_receipt(
        manifest,
        max_candidate_count=max_candidate_count,
        archive_path=archive_path,
    )
    if receipt == expected:
        return []
    errors = ["receipt differs from an independent deterministic reconstruction"]
    for key in expected:
        if receipt.get(key) != expected[key]:
            errors.append(f"mismatch at top-level field: {key}")
    for key in receipt:
        if key not in expected:
            errors.append(f"unexpected top-level field: {key}")
    return errors


def verify_archive_data(
    manifest: ProblemManifest,
    receipt: object,
    candidate_archive: object,
) -> list[str]:
    if not isinstance(receipt, dict) or not isinstance(receipt.get("candidateArchive"), dict):
        return ["receipt candidateArchive metadata must be an object"]
    if not isinstance(candidate_archive, list) or not all(
        isinstance(point, dict) for point in candidate_archive
    ):
        return ["candidate archive must be a list of objects"]
    expected = [
        point
        for landscape in LANDSCAPES
        for point in _archive(manifest, landscape)
    ]
    errors = []
    if candidate_archive != expected:
        errors.append("candidate archive differs from independent deterministic reconstruction")
    metadata = receipt["candidateArchive"]
    archive_bytes = _archive_jsonl_bytes(candidate_archive)
    if metadata.get("count") != len(candidate_archive):
        errors.append("candidate archive count does not match receipt metadata")
    if metadata.get("contentSha256") != _canonical_hash(candidate_archive):
        errors.append("candidate archive content hash does not match receipt metadata")
    if metadata.get("fileSha256") != hashlib.sha256(archive_bytes).hexdigest():
        errors.append("candidate archive file hash does not match receipt metadata")
    return errors


def build_verification(
    manifest: ProblemManifest,
    receipt: object,
    candidate_archive: object,
    *,
    receipt_file_sha256: str,
    archive_file_sha256: str,
    max_candidate_count: int = DEFAULT_MAX_CANDIDATE_COUNT,
    archive_path: str = DEFAULT_ARCHIVE.name,
) -> dict[str, object]:
    errors = verify_receipt_data(
        manifest,
        receipt,
        max_candidate_count=max_candidate_count,
        archive_path=archive_path,
    )
    errors.extend(verify_archive_data(manifest, receipt, candidate_archive))
    if (
        isinstance(receipt, dict)
        and isinstance(receipt.get("candidateArchive"), dict)
        and receipt["candidateArchive"].get("fileSha256") != archive_file_sha256
    ):
        errors.append("candidate archive bytes do not match the receipt file hash")
    return {
        "schemaVersion": VERIFICATION_VERSION,
        "problemId": manifest.problem_id,
        "manifestContentSha256": manifest.manifest_hash,
        "receiptContentSha256": sha256_json(receipt),
        "receiptFileSha256": receipt_file_sha256,
        "archiveFileSha256": archive_file_sha256,
        "verified": not errors,
        "verifierScope": "independent_python_reconstruction_with_shared_manifest_parser_not_formal_verification",
        "checks": [
            "manifest_contract",
            "candidate_identity_and_measurements",
            "archive_content_digest",
            "external_candidate_archive",
            "bounded_exact_optimum",
            "observation_preserving_representative_frontier",
            "coordinate_budget_witness_separation",
            "search_trace_and_lineage",
            "declared_claims",
        ],
        "errors": errors,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Independently verify a bounded-coordinate receipt.")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--receipt", type=Path, default=DEFAULT_RECEIPT)
    parser.add_argument("--archive", type=Path, default=DEFAULT_ARCHIVE)
    parser.add_argument("--out", type=Path, default=DEFAULT_VERIFICATION)
    parser.add_argument(
        "--max-candidate-count",
        type=int,
        default=DEFAULT_MAX_CANDIDATE_COUNT,
        help="Fail before reconstruction if one landscape exceeds this many candidates.",
    )
    args = parser.parse_args()

    manifest = ProblemManifest.from_path(args.manifest)
    receipt = json.loads(args.receipt.read_text(encoding="utf-8"))
    try:
        archive_reference = args.archive.relative_to(args.receipt.parent).as_posix()
    except ValueError as error:
        raise SystemExit("--archive must be inside the receipt directory") from error
    candidate_archive = [
        json.loads(line)
        for line in args.archive.read_text(encoding="utf-8").splitlines()
        if line
    ]
    verification = build_verification(
        manifest,
        receipt,
        candidate_archive,
        receipt_file_sha256=sha256_file(args.receipt),
        archive_file_sha256=sha256_file(args.archive),
        max_candidate_count=args.max_candidate_count,
        archive_path=archive_reference,
    )
    write_json(args.out, verification)
    if verification["errors"]:
        for error in verification["errors"]:
            print(f"error: {error}")
        raise SystemExit(1)
    print(
        "bounded-coordinate verification: ok "
        f"content_sha256={verification['receiptContentSha256']} "
        f"file_sha256={verification['receiptFileSha256']}"
    )


if __name__ == "__main__":
    main()
