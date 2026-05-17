from __future__ import annotations

import json
import os
from urllib import error, request

from fastapi import HTTPException

from .base import AdapterMode, GenerationConfig, ModelAdapter


class OpenAICompatibleAdapter(ModelAdapter):
    mode: AdapterMode = "local_openai"

    def __init__(self) -> None:
        self.base_url = os.environ.get("ALEPH_OPENAI_BASE_URL", "http://127.0.0.1:8080/v1").rstrip("/")
        self.api_key = os.environ.get("ALEPH_OPENAI_API_KEY", "none")

    def generate(self, prompt: str, config: GenerationConfig, *, target_text: str | None = None) -> str:
        payload = {
            "model": config.model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": config.max_tokens,
            "temperature": config.temperature,
        }

        body = json.dumps(payload).encode("utf-8")
        req = request.Request(
            f"{self.base_url}/chat/completions",
            data=body,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
            method="POST",
        )

        try:
            with request.urlopen(req, timeout=120) as response:
                data = json.loads(response.read().decode("utf-8"))
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise HTTPException(status_code=502, detail=f"Local model server error: {detail}") from exc
        except error.URLError as exc:
            raise HTTPException(
                status_code=503,
                detail="Local OpenAI-compatible model endpoint is unavailable. Start mlx_lm.server or use mode=mock.",
            ) from exc

        choices = data.get("choices") or []
        if not choices:
            raise HTTPException(status_code=502, detail="Local model server returned no choices.")

        message = choices[0].get("message") or {}
        content = message.get("content")

        if isinstance(content, str):
            return content

        if isinstance(content, list):
            parts = [part.get("text", "") for part in content if isinstance(part, dict)]
            return "".join(parts).strip()

        raise HTTPException(status_code=502, detail="Local model server returned an unsupported content format.")
