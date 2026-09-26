from __future__ import annotations

import argparse
from pathlib import Path
from fractions import Fraction
from typing import Callable, Iterable, Sequence

from .model import (
    RECEIPT_VERSION,
    CandidateObservation,
    ProblemManifest,
    PublicSearchSpace,
    all_coordinates,
    bounded_domain_size,
    budget_value_curve,
    enumerate_landscape,
    evaluate,
    exact_optimum,
    observed_frontier,
    sha256_file,
    sha256_json,
    write_json,
)


HERE = Path(__file__).resolve().parent
DEFAULT_MANIFEST = HERE / "problem.json"
DEFAULT_RECEIPT = HERE / "results" / "receipt.json"
LANDSCAPES = ("compositional", "opaque")
PRIORITY_POLICY_SEED = 1729
SHA256_PRIORITY_POLICY = "sha256_priority_without_replacement_v0"
DEFAULT_MAX_CANDIDATE_COUNT = 100_000


Evaluator = Callable[[Sequence[str]], CandidateObservation]


def matched_search_budget(search_space: PublicSearchSpace) -> int:
    """Match the number of evaluator calls made by width-one beam search."""
    return len(search_space.alphabet) * search_space.max_coordinate_tokens


def sha256_priority_sample(
    search_space: PublicSearchSpace,
    coordinates: list[tuple[str, ...]],
    *,
    budget: int,
    seed: int,
) -> list[tuple[str, ...]]:
    if budget < 0 or budget > len(coordinates):
        raise ValueError("priority-sampling budget exceeds the bounded domain")
    return sorted(
        coordinates,
        key=lambda coordinate: (
            sha256_json(
                {
                    "policy": SHA256_PRIORITY_POLICY,
                    "seed": seed,
                    "searchSpaceContentSha256": search_space.content_hash,
                    "coordinate": list(coordinate),
                }
            ),
            coordinate,
        ),
    )[:budget]


def _first_hit(observations: Iterable[CandidateObservation]) -> int | None:
    for index, observation in enumerate(observations, start=1):
        if observation.exact:
            return index
    return None


def exhaustive_run(
    landscape: str,
    archive: list[CandidateObservation],
) -> dict[str, object]:
    first_hit = _first_hit(archive)
    return {
        "id": f"{landscape}:exhaustive",
        "landscape": landscape,
        "policy": "length_then_lexicographic_exhaustive_v0",
        "evaluationBudget": len(archive),
        "seed": None,
        "evaluationCandidateIds": [item.id for item in archive],
        "lineage": [],
        "firstHitEvaluationOrdinal": first_hit,
        "success": first_hit is not None,
        "candidateEvaluatorCalls": len(archive),
        "logicalAdaptiveRounds": 1,
    }


def beam_run(
    search_space: PublicSearchSpace,
    landscape: str,
    evaluator: Evaluator,
    *,
    beam_width: int = 1,
) -> dict[str, object]:
    if beam_width <= 0:
        raise ValueError("beam_width must be positive")
    beams: list[tuple[str, ...]] = [()]
    evaluated: list[CandidateObservation] = []
    lineage: list[dict[str, object]] = []
    first_hit: int | None = None

    for depth in range(1, search_space.max_coordinate_tokens + 1):
        children: list[tuple[str, ...]] = []
        observations_by_coordinate: dict[tuple[str, ...], CandidateObservation] = {}
        for parent in beams:
            for token in search_space.alphabet:
                child = parent + (token,)
                observation = evaluator(child)
                children.append(child)
                observations_by_coordinate[child] = observation
                evaluated.append(observation)
                lineage.append(
                    {
                        "candidateId": observation.id,
                        "parentCoordinate": list(parent),
                        "operator": f"append:{token}",
                        "depth": depth,
                    }
                )
                if first_hit is None and observation.exact:
                    first_hit = len(evaluated)
        children.sort(
            key=lambda coordinate: (
                -Fraction(
                    observations_by_coordinate[coordinate].matches,
                    observations_by_coordinate[coordinate].comparison_length,
                ),
                coordinate,
            )
        )
        beams = children[:beam_width]

    return {
        "id": f"{landscape}:beam-{beam_width}",
        "landscape": landscape,
        "policy": "fit_guided_beam_v0",
        "beamWidth": beam_width,
        "evaluationBudget": len(evaluated),
        "seed": None,
        "evaluationCandidateIds": [item.id for item in evaluated],
        "lineage": lineage,
        "firstHitEvaluationOrdinal": first_hit,
        "success": first_hit is not None,
        "candidateEvaluatorCalls": len(evaluated),
        "logicalAdaptiveRounds": search_space.max_coordinate_tokens,
    }


def priority_run(
    search_space: PublicSearchSpace,
    landscape: str,
    evaluator: Evaluator,
    *,
    budget: int,
    seed: int,
) -> dict[str, object]:
    coordinates = list(
        all_coordinates(search_space.alphabet, search_space.max_coordinate_tokens)
    )[1:]
    sampled_coordinates = sha256_priority_sample(
        search_space,
        coordinates,
        budget=budget,
        seed=seed,
    )
    sampled = [evaluator(coordinate) for coordinate in sampled_coordinates]
    first_hit = _first_hit(sampled)
    return {
        "id": f"{landscape}:priority-{budget}-seed-{seed}",
        "landscape": landscape,
        "policy": SHA256_PRIORITY_POLICY,
        "evaluationBudget": budget,
        "seed": seed,
        "evaluationCandidateIds": [item.id for item in sampled],
        "lineage": [],
        "firstHitEvaluationOrdinal": first_hit,
        "success": first_hit is not None,
        "candidateEvaluatorCalls": len(sampled),
        "logicalAdaptiveRounds": 1 if sampled else 0,
    }


def build_receipt(
    manifest: ProblemManifest,
    *,
    max_candidate_count: int = DEFAULT_MAX_CANDIDATE_COUNT,
) -> dict[str, object]:
    if max_candidate_count <= 0:
        raise ValueError("max_candidate_count must be positive")
    archives: dict[str, list[CandidateObservation]] = {}
    landscape_results: dict[str, dict[str, object]] = {}
    search_runs: list[dict[str, object]] = []

    search_space = PublicSearchSpace.from_manifest(manifest)
    domain_size = bounded_domain_size(
        len(search_space.alphabet),
        search_space.max_coordinate_tokens,
    )
    if domain_size > max_candidate_count:
        raise ValueError(
            "bounded domain has "
            f"{domain_size} candidates per landscape, exceeding the explicit "
            f"limit {max_candidate_count}"
        )
    matched_budget = matched_search_budget(search_space)
    for landscape in LANDSCAPES:
        archive = enumerate_landscape(manifest, landscape)
        archives[landscape] = archive
        optimum = exact_optimum(archive)
        frontier = observed_frontier(archive)
        evaluator = lambda coordinate, current=landscape: evaluate(
            manifest,
            current,
            coordinate,
        )
        landscape_runs = [
            exhaustive_run(landscape, archive),
            beam_run(search_space, landscape, evaluator),
            priority_run(
                search_space,
                landscape,
                evaluator,
                budget=matched_budget,
                seed=PRIORITY_POLICY_SEED,
            ),
        ]
        additional_policy_work = sum(
            int(run["candidateEvaluatorCalls"])
            for run in landscape_runs
            if run["policy"] != "length_then_lexicographic_exhaustive_v0"
        )
        landscape_results[landscape] = {
            "candidateCount": len(archive),
            "archiveContentSha256": sha256_json([item.to_json() for item in archive]),
            "exactShortestWithinBound": {
                "candidateId": optimum.id,
                "coordinate": list(optimum.coordinate),
                "length": optimum.length,
            },
            "representativeFrontier": {
                "policy": "best_per_length_then_strict_fit_improvements_v0",
                "sameObjectiveTieBreak": "candidate_id_code_unit_ascending",
                "candidateIds": [item.id for item in frontier],
            },
            "budgetValueCurve": budget_value_curve(
                archive,
                manifest.max_coordinate_tokens,
            ),
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
    comp_beam = next(item for item in search_runs if item["id"] == "compositional:beam-1")
    opaque_beam = next(item for item in search_runs if item["id"] == "opaque:beam-1")
    return {
        "schemaVersion": RECEIPT_VERSION,
        "problemId": manifest.problem_id,
        "manifestContentSha256": manifest.manifest_hash,
        "runPolicy": {
            "landscapes": list(LANDSCAPES),
            "coordinateOrder": "length_then_lexicographic",
            "searchSpaceContentSha256": search_space.content_hash,
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
        "candidateArchive": [
            item.to_json()
            for landscape in LANDSCAPES
            for item in archives[landscape]
        ],
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


def main() -> None:
    parser = argparse.ArgumentParser(description="Run exact bounded coordinate search.")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--out", type=Path, default=DEFAULT_RECEIPT)
    parser.add_argument(
        "--max-candidate-count",
        type=int,
        default=DEFAULT_MAX_CANDIDATE_COUNT,
        help="Fail before enumeration if one landscape exceeds this many candidates.",
    )
    args = parser.parse_args()

    manifest = ProblemManifest.from_path(args.manifest)
    receipt = build_receipt(manifest, max_candidate_count=args.max_candidate_count)
    write_json(args.out, receipt)
    print(
        "bounded-coordinate: "
        f"{len(receipt['candidateArchive'])} observations, "
        f"content_sha256={sha256_json(receipt)}, "
        f"file_sha256={sha256_file(args.out)}"
    )


if __name__ == "__main__":
    main()
