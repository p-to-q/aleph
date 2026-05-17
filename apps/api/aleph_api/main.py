from __future__ import annotations

import json
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from aleph_api.adapters.base import GenerationConfig
from aleph_api.adapters.mock import MockAdapter
from aleph_api.adapters.openai_compat import OpenAICompatibleAdapter
from aleph_api.models import (
    CandidateRequest,
    CandidateResponse,
    GenerateRequest,
    GenerateResponse,
    ScoreRequest,
    ScoreResponse,
    SearchRequest,
    SearchResponse,
)
from aleph_api.services.candidates import build_candidate_prompts
from aleph_api.services.local_mlx_search import run_search
from aleph_api.services.scoring import compression_ratio, leakage_score, overall_score, similarity_score, token_count

from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Aleph API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

ADAPTERS = {
    "mock": MockAdapter(),
    "local_openai": OpenAICompatibleAdapter(),
}


@app.get("/health")
def health() -> dict[str, object]:
    return {
        "status": "ok",
        "version": "0.1.0",
        "modes": list(ADAPTERS.keys()),
        "search_modes": ["mock", "local_mlx_search"],
        "default_model": "Qwen/Qwen3-8B-MLX-4bit",
    }


@app.post("/api/candidates", response_model=CandidateResponse)
def candidates(request: CandidateRequest) -> CandidateResponse:
    explicit_prompt, candidate_prompts = build_candidate_prompts(request.target_text, request.candidate_count)
    return CandidateResponse(
        mode=request.mode,
        explicit_prompt=explicit_prompt,
        candidates=candidate_prompts,
    )


@app.post("/api/generate", response_model=GenerateResponse)
def generate(request: GenerateRequest) -> GenerateResponse:
    adapter = ADAPTERS[request.mode]
    output = adapter.generate(
        request.prompt,
        GenerationConfig(
            mode=request.mode,
            model=request.model,
            max_tokens=request.max_tokens,
            temperature=request.temperature,
            enable_thinking=request.enable_thinking,
        ),
        target_text=request.target_text,
    )
    return GenerateResponse(mode=request.mode, model=request.model, output=output)


@app.post("/api/score", response_model=ScoreResponse)
def score(request: ScoreRequest) -> ScoreResponse:
    explicit_prompt = request.explicit_prompt or f"Reproduce the following output exactly:\n\n{request.target_text.strip()}"
    similarity = similarity_score(request.target_text, request.output)
    compression = compression_ratio(request.prompt, explicit_prompt)
    leakage = leakage_score(request.prompt, request.target_text)
    total_score = overall_score(
        similarity=similarity,
        compression=compression,
        leakage=leakage,
        reliability=request.reliability,
    )

    return ScoreResponse(
        mode=request.mode,
        token_count=token_count(request.prompt),
        explicit_token_count=token_count(explicit_prompt),
        compression_ratio=compression,
        similarity=similarity,
        leakage_score=leakage,
        reliability=request.reliability,
        overall_score=total_score,
    )


@app.post("/api/search", response_model=SearchResponse, response_model_exclude_none=True)
def search(request: SearchRequest) -> SearchResponse:
    return run_search(request)


_FIXTURE_PATH = Path(__file__).parent.parent.parent.parent / "packages" / "fixtures" / "src" / "sample-run.json"


@app.get("/runs/fixture")
def runs_fixture() -> JSONResponse:
    """Return the sample fixture run as an AlephRun-shaped object. Mode: fixture."""
    data = json.loads(_FIXTURE_PATH.read_text(encoding="utf-8"))
    return JSONResponse(content=data)
