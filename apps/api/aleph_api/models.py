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


SearchAdapterMode = Literal["mock", "local_mlx_search"]


class SearchRequest(BaseModel):
    target_text: str = Field(min_length=8)
    mode: SearchAdapterMode = "mock"
    label: str | None = None


class SearchTarget(BaseModel):
    text: str
    label: str | None = None


class SearchBudget(BaseModel):
    candidates: int
    maxPromptTokens: int
    repeatedSamples: int
    timeLimitSeconds: float | None = None


class SearchConfig(BaseModel):
    model: str
    decoding: str
    metric: str
    budget: SearchBudget
    mode: Literal["unrestricted", "non_leaking"] = "unrestricted"


class SearchCandidatePoint(BaseModel):
    id: str
    label: str
    prompt: str
    output: str
    tokens: int
    fit: float
    stability: float
    compression: float
    leakage: float
    nll: float | None = None
    frontierRank: int | None = None
    note: str | None = None


class SearchObservations(BaseModel):
    mode: Literal["fixture", "mock", "black_box", "white_box", "simulated"]
    tokenLoss: list[dict[str, object]] | None = None
    lossCurve: list[dict[str, object]] | None = None
    evalSuite: list[dict[str, object]] | None = None


class SearchResponse(BaseModel):
    id: str
    createdAt: str
    target: SearchTarget
    config: SearchConfig
    candidates: list[SearchCandidatePoint]
    selectedCandidateId: str
    observations: SearchObservations
