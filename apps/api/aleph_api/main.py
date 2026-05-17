from __future__ import annotations

from fastapi import FastAPI

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
)
from aleph_api.services.candidates import build_candidate_prompts
from aleph_api.services.scoring import compression_ratio, leakage_score, overall_score, similarity_score, token_count

app = FastAPI(title="Aleph API", version="0.1.0")

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
