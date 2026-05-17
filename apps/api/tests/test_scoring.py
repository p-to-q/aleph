"""Tests for aleph_api.services.scoring and the /runs/fixture endpoint."""
from __future__ import annotations

import pytest

from aleph_api.services.scoring import (
    compression_ratio,
    leakage_score,
    overall_score,
    similarity_score,
    token_count,
)


# ---------------------------------------------------------------------------
# token_count
# ---------------------------------------------------------------------------

def test_token_count_empty():
    assert token_count("") == 0
    assert token_count("   ") == 0


def test_token_count_words():
    assert token_count("hello world") == 2
    assert token_count("  three word sentence  ") == 3


# ---------------------------------------------------------------------------
# compression_ratio
# ---------------------------------------------------------------------------

def test_compression_ratio_full():
    explicit = "Reproduce the following output exactly: " + "x " * 20
    short = "x"
    ratio = compression_ratio(short, explicit)
    assert 0.0 <= ratio <= 1.0
    assert ratio > 0.8


def test_compression_ratio_same_length():
    text = "hello world foo bar"
    assert compression_ratio(text, text) == pytest.approx(0.0, abs=1e-6)


def test_compression_ratio_zero_explicit():
    assert compression_ratio("anything", "") == 0.0


def test_compression_ratio_clamped():
    # candidate longer than explicit → clamped to 0
    assert compression_ratio("very long prompt text here and more words", "short") == 0.0


# ---------------------------------------------------------------------------
# leakage_score
# ---------------------------------------------------------------------------

def test_leakage_score_empty():
    assert leakage_score("", "target text") == 0.0
    assert leakage_score("prompt", "") == 0.0


def test_leakage_score_high_when_verbatim():
    target = "Prompt is a coordinate in the model's library."
    prompt = f"Reproduce exactly: {target}"
    score = leakage_score(prompt, target)
    assert score > 0.7, f"Expected high leakage, got {score}"


def test_leakage_score_low_when_unrelated():
    target = "The cat sat on the mat."
    prompt = "Describe the function of neural network activations."
    score = leakage_score(prompt, target)
    assert score < 0.2, f"Expected low leakage, got {score}"


def test_leakage_score_clamped():
    target = "hello world"
    prompt = "hello world hello world hello world"
    score = leakage_score(prompt, target)
    assert 0.0 <= score <= 1.0


# ---------------------------------------------------------------------------
# overall_score
# ---------------------------------------------------------------------------

def test_overall_score_clamped():
    score = overall_score(similarity=1.0, compression=1.0, leakage=0.0, reliability=1.0)
    assert 0.0 <= score <= 1.0


def test_overall_score_high_leakage_penalized():
    base = overall_score(similarity=0.8, compression=0.5, leakage=0.0, reliability=0.8)
    with_leakage = overall_score(similarity=0.8, compression=0.5, leakage=1.0, reliability=0.8)
    assert with_leakage < base


def test_overall_score_no_reliability_uses_default():
    score = overall_score(similarity=0.5, compression=0.5, leakage=0.0, reliability=None)
    assert 0.0 <= score <= 1.0


# ---------------------------------------------------------------------------
# /runs/fixture endpoint
# ---------------------------------------------------------------------------

def test_runs_fixture_returns_aleph_run_shape():
    from fastapi.testclient import TestClient
    from aleph_api.main import app

    client = TestClient(app)
    response = client.get("/runs/fixture")
    assert response.status_code == 200
    data = response.json()
    assert "id" in data
    assert "candidates" in data
    assert "observations" in data
    assert data["observations"]["mode"] == "fixture"
    assert len(data["candidates"]) > 0
