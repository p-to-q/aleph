#!/usr/bin/env python3
"""Smoke-check the Aleph API boundary without requiring MLX or a live model."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from fastapi import HTTPException

from aleph_api.main import health, search
from aleph_api.models import SearchRequest
from aleph_api.services import local_mlx_search


TARGET = "A small place for seeing too much, gently."
ROOT = Path(__file__).resolve().parents[2]
SCHEMA = __import__("json").loads((ROOT / "schemas" / "aleph-run.schema.json").read_text(encoding="utf-8"))


def main() -> None:
    health_data = health()
    assert "mock" in health_data["search_modes"], health_data
    assert "local_mlx_search" in health_data["search_modes"], health_data

    mock = search(SearchRequest(target_text=TARGET, label="Smoke target", mode="mock"))
    mock_data = _run_payload(mock)
    _assert_aleph_run("mock search", mock_data)
    assert mock_data["observations"]["mode"] == "mock", mock_data
    assert mock_data["target"]["text"] == TARGET, mock_data
    assert mock_data["config"]["budget"]["candidates"] == len(mock_data["candidates"]), mock_data
    assert mock_data["candidates"][0]["label"] == "Shortest Found", mock_data
    assert any(candidate["label"] == "Explicit Reconstruction" for candidate in mock_data["candidates"]), mock_data
    assert mock_data["selectedCandidateId"] in {candidate["id"] for candidate in mock_data["candidates"]}, mock_data

    previous_url = os.environ.get("ALEPH_MLX_SEARCH_URL")
    os.environ["ALEPH_MLX_SEARCH_URL"] = "http://127.0.0.1:9/search"
    try:
        try:
            search(SearchRequest(target_text=TARGET, label="Smoke target", mode="local_mlx_search"))
        except HTTPException as exc:
            local_status = exc.status_code
            local_detail = str(exc.detail)
        else:
            raise AssertionError("local_mlx_search unexpectedly succeeded without a local search engine")
    finally:
        if previous_url is None:
            os.environ.pop("ALEPH_MLX_SEARCH_URL", None)
        else:
            os.environ["ALEPH_MLX_SEARCH_URL"] = previous_url

    assert local_status == 503, local_detail
    assert "mode=mock" in local_detail, local_detail
    assert "search/server.py" in local_detail, local_detail

    previous_post_json = local_mlx_search._post_json
    local_mlx_search._post_json = _fake_live_search
    try:
        live = search(SearchRequest(target_text=TARGET, label="Smoke target", mode="local_mlx_search"))
    finally:
        local_mlx_search._post_json = previous_post_json

    live_data = live.model_dump()
    live_data = _run_payload(live)
    _assert_aleph_run("fake live search", live_data)
    assert live_data["observations"]["mode"] == "white_box", live_data
    assert live_data["config"]["model"] == "mlx-community/Qwen3-smoke-4bit", live_data
    assert live_data["config"]["budget"]["candidates"] == 2, live_data
    assert live_data["config"]["budget"]["timeLimitSeconds"] == 0.12, live_data
    assert live_data["candidates"][0]["label"] == "Shortest Found", live_data
    assert live_data["candidates"][0]["frontierRank"] == 1, live_data
    assert live_data["candidates"][1]["label"] == "Explicit Reconstruction", live_data
    assert live_data["candidates"][1]["nll"] == 0.3, live_data
    assert live_data["observations"]["tokenLoss"][0]["token"] == "A", live_data

    print("smoke-api: ok")


def _run_payload(response: object) -> dict[str, Any]:
    return response.model_dump(exclude_none=True)  # type: ignore[attr-defined]


def _assert_aleph_run(name: str, run: dict[str, Any]) -> None:
    errors: list[str] = []
    _validate_value(SCHEMA, run, name, errors)
    _check_run_invariants(name, run, errors)
    if errors:
        raise AssertionError("\n".join(errors))


def _resolve_ref(ref: str) -> dict[str, Any]:
    current: Any = SCHEMA
    for part in ref.removeprefix("#/").split("/"):
        current = current[part]
    return current


def _type_name(value: object) -> str:
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "object"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int) and not isinstance(value, bool):
        return "integer"
    if isinstance(value, float):
        return "number"
    if isinstance(value, str):
        return "string"
    if value is None:
        return "null"
    return type(value).__name__


def _validate_value(definition: dict[str, Any], value: Any, path: str, errors: list[str]) -> None:
    if "$ref" in definition:
        _validate_value(_resolve_ref(definition["$ref"]), value, path, errors)
        return

    if "enum" in definition and value not in definition["enum"]:
        errors.append(f"{path}: expected one of {definition['enum']}, got {value!r}")

    expected_type = definition.get("type")
    if expected_type:
        actual = _type_name(value)
        if expected_type == "number":
            if actual not in {"integer", "number"}:
                errors.append(f"{path}: expected number, got {actual}")
                return
        elif actual != expected_type:
            errors.append(f"{path}: expected {expected_type}, got {actual}")
            return

    if isinstance(value, int | float):
        if "minimum" in definition and value < definition["minimum"]:
            errors.append(f"{path}: below minimum {definition['minimum']}")
        if "maximum" in definition and value > definition["maximum"]:
            errors.append(f"{path}: above maximum {definition['maximum']}")

    if expected_type == "object":
        properties = definition.get("properties", {})
        for key in definition.get("required", []):
            if key not in value:
                errors.append(f"{path}: missing required property {key}")
        if definition.get("additionalProperties") is False:
            for key in value:
                if key not in properties:
                    errors.append(f"{path}: unexpected property {key}")
        for key, property_definition in properties.items():
            if key in value:
                _validate_value(property_definition, value[key], f"{path}.{key}", errors)

    if expected_type == "array":
        for index, item in enumerate(value):
            _validate_value(definition["items"], item, f"{path}[{index}]", errors)


def _check_run_invariants(name: str, run: dict[str, Any], errors: list[str]) -> None:
    candidates = run.get("candidates", [])
    selected = run.get("selectedCandidateId")
    if run.get("config", {}).get("budget", {}).get("candidates") != len(candidates):
        errors.append(f"{name}: candidate budget should match candidate count")
    if selected not in {candidate.get("id") for candidate in candidates}:
        errors.append(f"{name}: selected candidate missing")
    if not any(candidate.get("label") == "Shortest Found" for candidate in candidates):
        errors.append(f"{name}: Shortest Found label missing")
    if not any(candidate.get("label") == "Explicit Reconstruction" for candidate in candidates):
        errors.append(f"{name}: Explicit Reconstruction label missing")


def _fake_live_search(url: str, payload: dict[str, object]) -> dict[str, object]:
    assert url.endswith("/search"), url
    assert payload["text"] == TARGET, payload
    return {
        "key": "custom",
        "label": payload["label"],
        "targetTokens": 9,
        "evalModel": "mlx-community/Qwen3-smoke-4bit",
        "elapsed": 0.12,
        "points": [
            {
                "epsilon": 0.18,
                "prompt": "Recover the gentle Aleph line.",
                "length": 5,
                "similarity": 0.82,
                "stability": 0.91,
                "output": "A small place for seeing too much.",
            },
            {
                "epsilon": 0.01,
                "prompt": f"Repeat the following text exactly:\n\n{TARGET}",
                "length": 12,
                "similarity": 0.99,
                "stability": 1.0,
                "output": TARGET,
                "toktext": ["A", " small", " place"],
                "toknll": [0.2, 0.3, 0.4],
                "label": "Explicit Reconstruction",
            },
        ],
    }


if __name__ == "__main__":
    main()
