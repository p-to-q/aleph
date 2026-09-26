from __future__ import annotations

from aleph_api.models import SearchCandidatePoint, SearchRequest
from aleph_api.services.local_mlx_search import (
    _candidate_from_point,
    _select_candidate,
    run_search,
)


TARGET = "A small place for seeing too much, gently."


def _candidate(candidate_id: str) -> SearchCandidatePoint:
    return SearchCandidatePoint(
        id=candidate_id,
        role="candidate",
        label="Observed Candidate",
        prompt="Recover the target from a compact coordinate.",
        output=TARGET,
        tokens=7,
        fit=0.9,
        stability=0.8,
        compression=0.7,
        leakage=0.1,
    )


def test_unlabeled_first_point_is_not_promoted_to_shortest_found_or_ranked() -> None:
    point = {
        "prompt": "Recover the gentle Aleph line.",
        "output": "A small place for seeing too much.",
        "length": 5,
        "similarity": 0.82,
        "stability": 0.91,
    }
    candidate = _candidate_from_point(
        point,
        index=0,
        explicit_tokens=12,
        target_text=TARGET,
        adapter="local_mlx_search",
    )

    assert candidate.label == "Observed Candidate 1"
    assert candidate.role == "candidate"
    assert candidate.frontierRank is None
    assert "frontierRank" not in candidate.model_dump(exclude_none=True)

    reordered = _candidate_from_point(
        point,
        index=6,
        explicit_tokens=12,
        target_text=TARGET,
        adapter="local_mlx_search",
    )
    assert reordered.id == candidate.id


def test_explicit_reconstruction_role_propagates_without_array_position_or_label() -> None:
    candidate = _candidate_from_point(
        {
            "role": "explicit_reconstruction",
            "prompt": f"Repeat the following text exactly:\n\n{TARGET}",
            "output": TARGET,
            "length": 12,
            "similarity": 1.0,
            "stability": 1.0,
        },
        index=4,
        explicit_tokens=12,
        target_text=TARGET,
        adapter="local_mlx_search",
    )

    assert candidate.label == "Explicit Reconstruction"
    assert candidate.role == "explicit_reconstruction"
    assert candidate.frontierRank is None


def test_mock_search_serializes_explicit_role_and_omits_derived_rank() -> None:
    response = run_search(SearchRequest(target_text=TARGET, label="Test target", mode="mock"))
    payload = response.model_dump(exclude_none=True)

    explicit = [
        candidate
        for candidate in payload["candidates"]
        if candidate.get("role") == "explicit_reconstruction"
    ]
    assert len(explicit) == 1
    assert explicit[0]["label"] == "Explicit Reconstruction"
    assert all("frontierRank" not in candidate for candidate in payload["candidates"])
    assert [candidate["id"] for candidate in payload["candidates"]] == [
        point["candidateId"] for point in payload["observations"]["lossCurve"]
    ]


def test_selection_tie_breaks_by_candidate_id_independent_of_input_order() -> None:
    first = _candidate("candidate-z")
    second = _candidate("candidate-a")

    assert _select_candidate([first, second]) == "candidate-a"
    assert _select_candidate([second, first]) == "candidate-a"
