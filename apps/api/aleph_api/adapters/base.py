from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol

AdapterMode = Literal["mock", "local_openai"]


@dataclass(frozen=True)
class GenerationConfig:
    mode: AdapterMode
    model: str
    max_tokens: int = 256
    temperature: float = 0.6
    enable_thinking: bool = False


class ModelAdapter(Protocol):
    mode: AdapterMode

    def generate(self, prompt: str, config: GenerationConfig, *, target_text: str | None = None) -> str: ...
