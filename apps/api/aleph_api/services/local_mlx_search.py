from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from hashlib import sha1
from typing import Any
from urllib import error, request

from fastapi import HTTPException

from aleph_api.models import (
    SearchBudget,
    SearchCandidatePoint,
    SearchConfig,
    SearchObservations,
    SearchRequest,
    SearchResponse,
    SearchTarget,
)
from aleph_api.services.candidates import build_candidate_prompts
from aleph_api.services.scoring import leakage_score, similarity_score, token_count

DEFAULT_SEARCH_URL = "http://127.0.0.1:8000/search"
MOCK_MODEL = "mock"


def run_search(request_body: SearchRequest) -> SearchResponse:
    if request_body.mode == "mock":
        return _mock_search(request_body)
    return _local_mlx_search(request_body)


def _local_mlx_search(request_body: SearchRequest) -> SearchResponse:
    search_url = os.environ.get("ALEPH_MLX_SEARCH_URL", DEFAULT_SEARCH_URL)
    payload = {
        "text": request_body.target_text,
        "label": request_body.label,
    }
    raw = _post_json(search_url, payload)

    if isinstance(raw.get("error"), str):
        raise HTTPException(
            status_code=503,
            detail=f"Local MLX search failed recoverably: {raw['error']}",
        )

    points = raw.get("points")
    if not isinstance(points, list) or not points:
        raise HTTPException(status_code=502, detail="Local MLX search returned no frontier points.")

    return _to_search_response(
        request_body=request_body,
        raw=raw,
        points=points,
        adapter="local_mlx_search",
        observation_mode=_observation_mode(points),
    )


def _post_json(url: str, payload: dict[str, object]) -> dict[str, Any]:
    body = json.dumps(payload).encode("utf-8")
    req = request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with request.urlopen(req, timeout=180) as response:
            data = json.loads(response.read().decode("utf-8"))
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise HTTPException(status_code=502, detail=f"Local MLX search server error: {detail}") from exc
    except error.URLError as exc:
        raise HTTPException(
            status_code=503,
            detail=(
                "Local MLX search engine is unavailable. Start `python3 search/server.py`, "
                "set ALEPH_MLX_SEARCH_URL if needed, or use mode=mock."
            ),
        ) from exc
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=502, detail="Local MLX search returned invalid JSON.") from exc

    if not isinstance(data, dict):
        raise HTTPException(status_code=502, detail="Local MLX search returned an unsupported response shape.")
    return data


def _mock_search(request_body: SearchRequest) -> SearchResponse:
    explicit_prompt, candidate_prompts = build_candidate_prompts(request_body.target_text, candidate_count=5)
    points: list[dict[str, object]] = []

    for index, candidate in enumerate(candidate_prompts):
        output = request_body.target_text if candidate.kind == "explicit" else _mock_output(request_body.target_text, index)
        similarity = similarity_score(request_body.target_text, output)
        prompt_tokens = token_count(candidate.prompt)
        points.append(
            {
                "label": candidate.label,
                "prompt": candidate.prompt,
                "output": output,
                "length": prompt_tokens,
                "similarity": round(similarity, 4),
                "stability": 1.0 if candidate.kind == "explicit" else 0.72,
                "epsilon": round(1.0 - similarity, 4),
            }
        )
    points.sort(key=lambda point: int(point.get("length") or 0))

    return _to_search_response(
        request_body=request_body,
        raw={
            "key": "mock",
            "label": request_body.label or "Mock local search",
            "targetTokens": token_count(request_body.target_text),
            "evalModel": MOCK_MODEL,
            "points": points,
        },
        points=points,
        adapter="mock",
        observation_mode="mock",
        explicit_prompt=explicit_prompt,
    )


def _mock_output(target_text: str, index: int) -> str:
    words = target_text.strip().split()
    if not words:
        return ""
    keep = max(8, int(len(words) * (0.8 - index * 0.12)))
    return " ".join(words[:keep]).strip()


def _to_search_response(
    *,
    request_body: SearchRequest,
    raw: dict[str, Any],
    points: list[dict[str, Any]],
    adapter: str,
    observation_mode: str,
    explicit_prompt: str | None = None,
) -> SearchResponse:
    target_text = request_body.target_text.strip()
    explicit = explicit_prompt or _explicit_prompt_from_points(points, target_text)
    explicit_tokens = max(1, _point_length({"prompt": explicit, "length": token_count(explicit)}))
    candidates = [
        _candidate_from_point(
            point,
            index=index,
            explicit_tokens=explicit_tokens,
            target_text=target_text,
            adapter=adapter,
        )
        for index, point in enumerate(points)
    ]
    selected = _select_candidate(candidates)

    return SearchResponse(
        id=_run_id(target_text, adapter),
        createdAt=datetime.now(UTC).isoformat(),
        target=SearchTarget(text=target_text, label=request_body.label or _optional_string(raw.get("label"))),
        config=SearchConfig(
            model=str(raw.get("evalModel") or MOCK_MODEL),
            decoding="greedy",
            metric="embedding" if adapter == "local_mlx_search" else "mock_similarity",
            budget=SearchBudget(
                candidates=len(candidates),
                maxPromptTokens=max((candidate.tokens for candidate in candidates), default=0),
                repeatedSamples=1,
                timeLimitSeconds=_optional_float(raw.get("elapsed")),
            ),
        ),
        candidates=candidates,
        selectedCandidateId=selected,
        observations=_observations(points, observation_mode),
    )


def _candidate_from_point(
    point: dict[str, Any],
    *,
    index: int,
    explicit_tokens: int,
    target_text: str,
    adapter: str,
) -> SearchCandidatePoint:
    prompt = str(point.get("prompt") or "")
    output = str(point.get("output") or "")
    length = _point_length(point)
    measured_fit = similarity_score(target_text, output)
    fit = 1.0 if measured_fit == 1.0 else _bounded_float(point.get("similarity"), default=measured_fit)
    stability = _bounded_float(point.get("stability"), default=1.0)
    avg_nll = _average_nll(point.get("toknll"))
    label = _point_label(point, index=index)
    if index == 0 and label != "Explicit Reconstruction":
        label = "Shortest Found"

    return SearchCandidatePoint(
        id=f"search-point-{index + 1}",
        label=label,
        prompt=prompt,
        output=output,
        tokens=length,
        fit=fit,
        stability=stability,
        compression=max(0.0, min(1.0, 1 - (length / explicit_tokens))),
        leakage=leakage_score(prompt, target_text),
        nll=avg_nll,
        frontierRank=index + 1,
        note=_candidate_note(adapter, avg_nll),
    )


def _explicit_prompt_from_points(points: list[dict[str, Any]], target_text: str) -> str:
    if points:
        last_prompt = points[-1].get("prompt")
        if isinstance(last_prompt, str) and target_text[:80] in last_prompt:
            return last_prompt
    return f"Reproduce the following output exactly:\n\n{target_text}"


def _select_candidate(candidates: list[SearchCandidatePoint]) -> str:
    if not candidates:
        return ""
    best = max(
        candidates,
        key=lambda candidate: (
            candidate.fit * 0.55
            + candidate.stability * 0.2
            + candidate.compression * 0.2
            - candidate.leakage * 0.1
        ),
    )
    return best.id


def _point_label(point: dict[str, Any], *, index: int) -> str:
    raw = point.get("label")
    if isinstance(raw, str) and raw:
        return raw
    if index == 0:
        return "Shortest Found"
    return f"Frontier Point {index + 1}"


def _candidate_note(adapter: str, avg_nll: float | None) -> str:
    if adapter == "mock":
        return "Mock search point; values are deterministic and not model evidence."
    if avg_nll is None:
        return "Mapped from local MLX live-search point."
    return "Mapped from local MLX point with token NLL."


def _observations(points: list[dict[str, Any]], mode: str) -> SearchObservations:
    token_loss = _token_loss(points)
    return SearchObservations(
        mode=mode,
        tokenLoss=token_loss,
        lossCurve=[
            {
                "step": index + 1,
                "loss": round(
                    float(point["epsilon"]) if point.get("epsilon") is not None
                    else 1.0 - float(point.get("similarity") or 0.0),
                    4,
                ),
                "candidateId": f"search-point-{index + 1}",
            }
            for index, point in enumerate(points)
        ],
        evalSuite=[
            {
                "name": "recoverable_adapter",
                "passed": True,
                "note": "Search response was adapted behind apps/api.",
            }
        ],
    )


def _token_loss(points: list[dict[str, Any]]) -> list[dict[str, object]] | None:
    for point in reversed(points):
        tokens = point.get("toktext")
        losses = point.get("toknll")
        if isinstance(tokens, list) and isinstance(losses, list) and len(tokens) == len(losses):
            return [
                {"token": str(token), "loss": float(loss)}
                for token, loss in zip(tokens, losses, strict=False)
            ]
    return None


def _observation_mode(points: list[dict[str, Any]]) -> str:
    return "white_box" if _token_loss(points) else "black_box"


def _run_id(target_text: str, adapter: str) -> str:
    digest = sha1(f"{adapter}:{target_text}".encode("utf-8")).hexdigest()[:12]
    return f"search-{digest}"


def _point_length(point: dict[str, Any]) -> int:
    raw = point.get("length")
    if isinstance(raw, int) and raw >= 0:
        return raw
    return token_count(str(point.get("prompt") or ""))


def _bounded_float(value: object, *, default: float) -> float:
    if isinstance(value, int | float):
        return max(0.0, min(1.0, float(value)))
    return max(0.0, min(1.0, default))


def _optional_float(value: object) -> float | None:
    if isinstance(value, int | float):
        return float(value)
    return None


def _optional_string(value: object) -> str | None:
    return value if isinstance(value, str) else None


def _average_nll(value: object) -> float | None:
    if not isinstance(value, list) or not value:
        return None
    numeric = [float(item) for item in value if isinstance(item, int | float)]
    if not numeric:
        return None
    return round(sum(numeric) / len(numeric), 4)
