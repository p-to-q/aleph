from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from .adapters.base import AdapterMode


class CandidatePrompt(BaseModel):
    id: str
    label: str
    prompt: str
    kind: Literal["explicit", "summary", "keywords", "coordinate", "minimal"]


class CandidateRequest(BaseModel):
    target_text: str = Field(min_length=1)
    mode: AdapterMode = "mock"
    candidate_count: int = Field(default=5, ge=3, le=8)


class CandidateResponse(BaseModel):
    mode: AdapterMode
    explicit_prompt: str
    candidates: list[CandidatePrompt]


class GenerateRequest(BaseModel):
    prompt: str = Field(min_length=1)
    mode: AdapterMode = "mock"
    target_text: str | None = None
    model: str = "Qwen/Qwen3-8B-MLX-4bit"
    max_tokens: int = Field(default=256, ge=1, le=2048)
    temperature: float = Field(default=0.6, ge=0, le=2)
    enable_thinking: bool = False


class GenerateResponse(BaseModel):
    mode: AdapterMode
    model: str
    output: str


class ScoreRequest(BaseModel):
    target_text: str = Field(min_length=1)
    prompt: str = Field(min_length=1)
    output: str = Field(min_length=1)
    mode: AdapterMode = "mock"
    explicit_prompt: str | None = None
    reliability: float | None = Field(default=None, ge=0, le=1)


class ScoreResponse(BaseModel):
    mode: AdapterMode
    token_count: int
    explicit_token_count: int
    compression_ratio: float
    similarity: float
    leakage_score: float
    reliability: float | None = None
    overall_score: float
