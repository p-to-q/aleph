from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .adapters import ModelAdapter


class ResponseCacheAdapter(ModelAdapter):
    """Persistent per-call cache for resumable hosted benchmark runs."""

    def __init__(self, wrapped: ModelAdapter, cache_dir: Path, *, seed: int):
        super().__init__(
            model_id=wrapped.model_id,
            observation_mode=wrapped.observation_mode,
            temperature=wrapped.temperature,
        )
        self.wrapped = wrapped
        self.cache_dir = cache_dir
        self.seed = seed
        self.cache_hits = 0
        self.cache_misses = 0

    def reruns(self, configured: int) -> int:
        return self.wrapped.reruns(configured)

    def _cache_key(
        self,
        prompt: str,
        item: dict[str, Any],
        ladder_prompt: dict[str, Any],
        *,
        rerun_index: int,
    ) -> str:
        payload = {
            "model": self.model_id,
            "observationMode": self.observation_mode,
            "temperature": self.temperature,
            "seed": self.seed,
            "rerunIndex": rerun_index,
            "itemId": item["id"],
            "promptId": ladder_prompt["id"],
            "prompt": prompt,
            "target": item["target"]["text"],
        }
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    def _path_for_key(self, key: str) -> Path:
        return self.cache_dir / self.model_id.replace("/", "_") / f"{key}.json"

    def generate(
        self,
        prompt: str,
        item: dict[str, Any],
        ladder_prompt: dict[str, Any],
        *,
        seed: int,
        rerun_index: int,
    ) -> str:
        key = self._cache_key(prompt, item, ladder_prompt, rerun_index=rerun_index)
        path = self._path_for_key(key)
        if path.exists():
            self.cache_hits += 1
            cached = json.loads(path.read_text(encoding="utf-8"))
            return str(cached["output"])

        self.cache_misses += 1
        output = self.wrapped.generate(
            prompt,
            item,
            ladder_prompt,
            seed=seed,
            rerun_index=rerun_index,
        )
        path.parent.mkdir(parents=True, exist_ok=True)
        record = {
            "key": key,
            "model": self.model_id,
            "observationMode": self.observation_mode,
            "seed": self.seed,
            "rerunIndex": rerun_index,
            "itemId": item["id"],
            "promptId": ladder_prompt["id"],
            "output": output,
        }
        path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return output
