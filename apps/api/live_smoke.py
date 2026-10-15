#!/usr/bin/env python3
"""Optional smoke check for a running local MLX search engine.

This script does not start or install MLX. Start `python3 search/server.py`
first, then run this check to verify the `apps/api` adapter can consume the
live engine response.
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import UTC, datetime
from math import isfinite

from fastapi import HTTPException

from aleph_api.main import search
from aleph_api.models import SearchRequest


DEFAULT_TARGET = "A small place for seeing too much, gently."


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target", default=DEFAULT_TARGET)
    parser.add_argument("--label", default="Live smoke target")
    parser.add_argument("--url", default=os.environ.get("ALEPH_MLX_SEARCH_URL", "http://127.0.0.1:8000/search"))
    args = parser.parse_args()

    previous_url = os.environ.get("ALEPH_MLX_SEARCH_URL")
    os.environ["ALEPH_MLX_SEARCH_URL"] = args.url
    try:
        try:
            run = search(SearchRequest(target_text=args.target, label=args.label, mode="local_mlx_search"))
        except HTTPException as exc:
            print("live-smoke-api: offline")
            print(f"status: {exc.status_code}")
            print(f"detail: {exc.detail}")
            print("next: start `python3 search/server.py` or set ALEPH_MLX_SEARCH_URL")
            sys.exit(2)
    finally:
        if previous_url is None:
            os.environ.pop("ALEPH_MLX_SEARCH_URL", None)
        else:
            os.environ["ALEPH_MLX_SEARCH_URL"] = previous_url

    data = run.model_dump(exclude_none=True)
    assert data["observations"]["mode"] in {"black_box", "white_box"}, data
    assert data["config"]["budget"]["candidates"] == len(data["candidates"]), data
    assert data["selectedCandidateId"] in {candidate["id"] for candidate in data["candidates"]}, data
    token_loss = data["observations"].get("tokenLoss")
    if token_loss is not None:
        assert data["observations"]["mode"] == "white_box", data
        assert isinstance(token_loss, list) and token_loss, data
        for entry in token_loss:
            assert isinstance(entry, dict) and isinstance(entry.get("token"), str), data
            loss = entry.get("loss")
            assert (
                isinstance(loss, (int, float))
                and not isinstance(loss, bool)
                and isfinite(loss)
                and loss >= 0
            ), data
        assert any(candidate["label"] == "Explicit Reconstruction" for candidate in data["candidates"]), data
        token_nll_present = True
        losses = [float(entry["loss"]) for entry in token_loss]
        token_nll_shape = f"entries={len(losses)} min={min(losses):.6g} max={max(losses):.6g}"
    else:
        assert data["observations"]["mode"] == "black_box", data
        token_nll_present = False
        token_nll_shape = "none (black_box)"
    source_mode = data["observations"]["mode"]
    command = f"npm run api:live-smoke -- --url {args.url!r} --target {args.target!r} --label {args.label!r}"

    print("live-smoke-api: ok")
    print(f"model: {data['config']['model']}")
    print(f"observation_mode: {data['observations']['mode']}")
    print(f"candidates: {len(data['candidates'])}")
    print(f"selected: {data['selectedCandidateId']}")
    print(f"token_nll_present: {str(token_nll_present).lower()}")
    print("\nreceipt:")
    print("```text")
    print("Account: Account B / Local Search Adapter Implementer")
    print(f"Source mode: {source_mode}")
    print(f"Date: {datetime.now(UTC).isoformat()}")
    print(f"Command: {command}")
    print(f"Search URL: {args.url}")
    print(f"Model: {data['config']['model']}")
    print(f"Observation mode: {data['observations']['mode']}")
    print(f"Candidate count: {len(data['candidates'])}")
    print(f"Selected candidate id: {data['selectedCandidateId']}")
    print(f"Token NLL present: {str(token_nll_present).lower()}")
    print(f"Token NLL shape: {token_nll_shape}")
    print(f"Claim supported: apps/api can adapt a live local MLX search response into an AlephRun-compatible {source_mode} response.")
    if token_nll_present:
        print("Shape claim: the adapted response carries a non-empty token NLL trace whose entries are {token: str, loss: finite >= 0}.")
    print("Claim not supported: globally shortest prompt, production readiness, or white-box UI completeness.")
    print("```")


if __name__ == "__main__":
    main()
