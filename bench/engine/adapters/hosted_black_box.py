from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from typing import Any

from .base import ModelAdapter

RETRYABLE_HTTP_STATUSES = {429, 500, 502, 503, 504}


class HostedBlackBoxError(RuntimeError):
    pass


def env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise RuntimeError(f"{name} must be an integer") from exc


def env_float(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        return float(raw)
    except ValueError as exc:
        raise RuntimeError(f"{name} must be a number") from exc


class HostedBlackBoxAdapter(ModelAdapter):
    """OpenAI-compatible black-box adapter for future real M0 runs."""

    def __init__(
        self,
        model_id: str,
        *,
        base_url: str | None = None,
        api_key: str | None = None,
        temperature: float = 0.0,
        max_tokens: int = 512,
        timeout_seconds: int = 90,
        max_retries: int | None = None,
        retry_delay_seconds: float | None = None,
    ):
        super().__init__(model_id=model_id, observation_mode="black_box", temperature=temperature)
        self.base_url = (base_url or os.environ.get("ALEPH_CUSTOM_API_BASE_URL") or "").rstrip("/")
        self.api_key = api_key or os.environ.get("ALEPH_CUSTOM_API_KEY") or ""
        self.max_tokens = max_tokens
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries if max_retries is not None else env_int("ALEPH_CUSTOM_API_MAX_RETRIES", 2)
        self.retry_delay_seconds = (
            retry_delay_seconds
            if retry_delay_seconds is not None
            else env_float("ALEPH_CUSTOM_API_RETRY_DELAY_SECONDS", 1.0)
        )
        if not self.base_url or not self.api_key:
            raise RuntimeError("hosted black-box adapter requires ALEPH_CUSTOM_API_BASE_URL and ALEPH_CUSTOM_API_KEY")

    def _request_for_payload(self, payload: dict[str, Any]) -> urllib.request.Request:
        body = json.dumps(payload).encode("utf-8")
        return urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=body,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )

    def _sleep_before_retry(self) -> None:
        if self.retry_delay_seconds > 0:
            time.sleep(self.retry_delay_seconds)

    def _post_chat_completion(self, payload: dict[str, Any]) -> dict[str, Any]:
        last_error: str | None = None
        for attempt in range(self.max_retries + 1):
            request = self._request_for_payload(payload)
            try:
                with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                    return json.loads(response.read().decode("utf-8"))
            except urllib.error.HTTPError as exc:
                body = exc.read().decode("utf-8", errors="replace")
                last_error = f"HTTP {exc.code}: {body[:500]}"
                if exc.code in RETRYABLE_HTTP_STATUSES and attempt < self.max_retries:
                    self._sleep_before_retry()
                    continue
                raise HostedBlackBoxError(f"hosted black-box request failed: {last_error}") from exc
            except urllib.error.URLError as exc:
                last_error = str(exc.reason)
                if attempt < self.max_retries:
                    self._sleep_before_retry()
                    continue
                raise HostedBlackBoxError(f"hosted black-box request failed: {last_error}") from exc
        raise HostedBlackBoxError(f"hosted black-box request failed: {last_error or 'unknown error'}")

    def generate(
        self,
        prompt: str,
        item: dict[str, Any],
        ladder_prompt: dict[str, Any],
        *,
        seed: int,
        rerun_index: int,
    ) -> str:
        del item, ladder_prompt, seed, rerun_index
        payload = {
            "model": self.model_id,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }
        try:
            data = self._post_chat_completion(payload)
            return data["choices"][0]["message"]["content"].strip()
        except (KeyError, IndexError, TypeError) as exc:
            raise HostedBlackBoxError("hosted black-box response missing choices[0].message.content") from exc
