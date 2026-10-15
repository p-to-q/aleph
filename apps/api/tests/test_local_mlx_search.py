from __future__ import annotations

from aleph_api.models import SearchCandidatePoint, SearchRequest
from aleph_api.services.local_mlx_search import (
    _candidate_from_point,
    _observation_mode,
    _observations,
    _select_candidate,
    _token_loss,
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


def test_token_loss_contract_accepts_only_shape_valid_traces() -> None:
    point = {"toktext": ["A", " small", " place"], "toknll": [0.2, 0.3, 0.4]}
    assert _token_loss([point]) == [
        {"token": "A", "loss": 0.2},
        {"token": " small", "loss": 0.3},
        {"token": " place", "loss": 0.4},
    ]
    assert _observation_mode([point]) == "white_box"

    # loss 0 is a valid boundary; integer losses normalize to float
    boundary = {"toktext": ["A", " b"], "toknll": [0, 1]}
    assert _token_loss([boundary]) == [{"token": "A", "loss": 0.0}, {"token": " b", "loss": 1.0}]


def test_token_loss_contract_fails_closed_to_black_box() -> None:
    cases = [
        {},
        {"toktext": [], "toknll": []},
        {"toktext": ["A"], "toknll": []},
        {"toktext": ["A"], "toknll": [0.1, 0.2]},
        {"toktext": ["A"], "toknll": [-0.1]},
        {"toktext": ["A"], "toknll": [float("inf")]},
        {"toktext": ["A"], "toknll": [float("nan")]},
        {"toktext": [7], "toknll": [0.1]},
        {"toktext": ["A"], "toknll": ["0.1"]},
        {"toktext": "A", "toknll": 0.1},
    ]
    for point in cases:
        assert _token_loss([point]) is None, point
        assert _observation_mode([point]) == "black_box", point

    # an invalid newer point does not shadow an older valid trace
    older = {"toktext": ["A"], "toknll": [0.5]}
    newer_invalid = {"toktext": ["B"], "toknll": [0.1, 0.2]}
    assert _token_loss([older, newer_invalid]) == [{"token": "A", "loss": 0.5}]


def test_observations_omit_token_loss_unless_white_box_trace_is_valid() -> None:
    point = {"toktext": ["A", " b"], "toknll": [0.25, 0.5]}
    payload = _observations([point], _observation_mode([point])).model_dump(exclude_none=True)
    assert payload["mode"] == "white_box"
    assert payload["tokenLoss"] == [{"token": "A", "loss": 0.25}, {"token": " b", "loss": 0.5}]

    black = _observations([{"toktext": [], "toknll": []}], "black_box")
    assert "tokenLoss" not in black.model_dump(exclude_none=True)
