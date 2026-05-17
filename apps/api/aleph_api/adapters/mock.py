from __future__ import annotations

from .base import AdapterMode, GenerationConfig, ModelAdapter


class MockAdapter(ModelAdapter):
    mode: AdapterMode = "mock"

    def generate(self, prompt: str, config: GenerationConfig, *, target_text: str | None = None) -> str:
        if target_text:
            trimmed = target_text.strip()
            if len(trimmed) <= 220:
                return trimmed
            return f"{trimmed[:180].rstrip()} ..."

        compact_prompt = " ".join(prompt.strip().split())
        if len(compact_prompt) <= 220:
            return f"[mock output] {compact_prompt}"
        return f"[mock output] {compact_prompt[:180].rstrip()} ..."
