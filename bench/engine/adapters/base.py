from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class ModelAdapter:
    model_id: str
    observation_mode: str
    temperature: float = 0.0

    def reruns(self, configured: int) -> int:
        return 1 if self.temperature == 0 else max(1, configured)

    def generate(
        self,
        prompt: str,
        item: dict[str, Any],
        ladder_prompt: dict[str, Any],
        *,
        seed: int,
        rerun_index: int,
    ) -> str:
        raise NotImplementedError

