"""Pinned MLX canary adapter for Aleph run bundles (PR C).

This is the opt-in, real-model adapter of the #106 canary. It stays outside
the standard-library kernel: MLX and mlx-lm are imported lazily inside
functions, and the kernel, scheduler, exporter, and verifier never import this
module. The default test suite and CI never need Metal; the live canary runs
separately on an Apple Silicon host with

    model:    mlx-community/Qwen3-1.7B-4bit
    revision: 3b1b1768f8f8cf8351c712464f906e86c2b8269e
    mlx:      0.31.2
    mlx-lm:   0.31.3

Pinning rules, all fail-closed (``MlxPinError``):

- the snapshot is resolved from the exact pinned-revision directory of the
  local Hugging Face cache; a missing snapshot is an error, ``main`` is never
  resolved, and another cached revision is never substituted;
- the imported mlx/mlx-lm versions must equal the declared pins;
- the snapshot must carry config, tokenizer, and weight files; the resolved
  file list (path, bytes, sha256) is recorded for the run manifest and receipt.

The canary evaluator's metrics are declared surface proxies for artifact
plumbing, not the research metric contract: ``fit`` and ``leakage`` are token
multiset recalls (how much of the smoke target is reproduced in the greedy
continuation / literally present in the coordinate), ``stability`` is the
share of planned samples identical to the first, and ``compression`` is
``target_tokens / (target_tokens + coordinate_tokens)``. Values are rounded to
6 decimals so canonical bundles stay byte-stable.

Everything except the lazy MLX calls is pure standard library and importable
without MLX installed.
"""

from __future__ import annotations

import hashlib
from collections import Counter
from pathlib import Path
from typing import Any, Sequence

from ..contracts import (
    AdapterIdentity,
    Candidate,
    EvaluationReceipt,
    EvaluationRequest,
    evaluation_receipt,
)
from ..ledger import CoordinateCost

PINNED_MODEL = "mlx-community/Qwen3-1.7B-4bit"
PINNED_REVISION = "3b1b1768f8f8cf8351c712464f906e86c2b8269e"
PINNED_MLX_VERSION = "0.31.2"
PINNED_MLX_LM_VERSION = "0.31.3"

_REQUIRED_SNAPSHOT_FILES = ("config.json", "tokenizer.json", "tokenizer_config.json")
_OPTIONAL_SNAPSHOT_FILES = (
    "special_tokens_map.json",
    "added_tokens.json",
    "vocab.json",
    "merges.txt",
    "generation_config.json",
)


class MlxCanaryError(RuntimeError):
    """Base error of the pinned MLX canary."""


class MlxPinError(MlxCanaryError):
    """Raised when the pinned snapshot or runtime does not match the pin."""


class MlxUnavailableError(MlxCanaryError):
    """Raised when MLX is not installed in the running interpreter."""


def pinned_snapshot_path(cache_root: Path | None = None) -> Path:
    """Return the exact expected path of the pinned snapshot in the HF cache."""
    hub = Path(cache_root).expanduser() if cache_root is not None else Path.home() / ".cache" / "huggingface" / "hub"
    return hub / f"models--{PINNED_MODEL.replace('/', '--')}" / "snapshots" / PINNED_REVISION


def resolve_pinned_snapshot(cache_root: Path | None = None) -> Path:
    """Resolve the pinned revision directory, failing closed.

    The exact revision directory is required. A missing snapshot is an error:
    the canary never resolves ``main``, never downloads, and never silently
    substitutes another cached revision.
    """
    snapshot = pinned_snapshot_path(cache_root)
    if not snapshot.is_dir():
        raise MlxPinError(
            f"pinned MLX snapshot is missing: {snapshot}; resolve revision "
            f"{PINNED_REVISION} of {PINNED_MODEL} into the local cache first "
            "(the canary never resolves main or substitutes another revision)"
        )
    missing = [name for name in _REQUIRED_SNAPSHOT_FILES if not (snapshot / name).is_file()]
    if not any(path.is_file() for path in snapshot.glob("*.safetensors")):
        missing.append("model weights (*.safetensors)")
    if missing:
        raise MlxPinError(f"pinned snapshot is incomplete: missing {missing} in {snapshot}")
    return snapshot


def _sha256_file(path: Path) -> str:
    digest_value = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest_value.update(chunk)
    return f"sha256:{digest_value.hexdigest()}"


def snapshot_files(snapshot: Path) -> tuple[dict[str, Any], ...]:
    """Return content records (path, bytes, sha256) of the resolved snapshot files."""
    snapshot = Path(snapshot)
    if not snapshot.is_dir():
        raise MlxPinError(f"snapshot directory does not exist: {snapshot}")
    missing = [name for name in _REQUIRED_SNAPSHOT_FILES if not (snapshot / name).is_file()]
    weights = sorted(path.name for path in snapshot.glob("*.safetensors") if path.is_file())
    if not weights:
        missing.append("model weights (*.safetensors)")
    if missing:
        raise MlxPinError(f"snapshot is incomplete: missing {missing} in {snapshot}")
    names = list(_REQUIRED_SNAPSHOT_FILES)
    names += [name for name in _OPTIONAL_SNAPSHOT_FILES if (snapshot / name).is_file()]
    names += weights
    names += sorted(path.name for path in snapshot.glob("*.safetensors.index.json") if path.is_file())
    records: list[dict[str, Any]] = []
    for name in dict.fromkeys(names):
        path = snapshot / name
        records.append({"path": name, "bytes": path.stat().st_size, "sha256": _sha256_file(path)})
    return tuple(records)


def check_pinned_versions(mlx_version: str, mlx_lm_version: str) -> None:
    """Fail closed unless the runtime exactly matches the declared pin."""
    problems = []
    if mlx_version != PINNED_MLX_VERSION:
        problems.append(f"mlx {mlx_version!r} != pinned {PINNED_MLX_VERSION!r}")
    if mlx_lm_version != PINNED_MLX_LM_VERSION:
        problems.append(f"mlx-lm {mlx_lm_version!r} != pinned {PINNED_MLX_LM_VERSION!r}")
    if problems:
        raise MlxPinError(
            "runtime does not match the canary pin: "
            + "; ".join(problems)
            + " (install the pinned versions; the canary never substitutes a different runtime)"
        )


def _import_mlx() -> tuple[Any, Any]:
    try:
        import mlx.core as mx
        import mlx_lm
    except ImportError as error:
        raise MlxUnavailableError(
            "MLX runtime is not available in this interpreter: install mlx "
            f"{PINNED_MLX_VERSION} and mlx-lm {PINNED_MLX_LM_VERSION} on an Apple Silicon host; "
            "the standard-library kernel, exporter, and verifier do not need MLX"
        ) from error
    return mx, mlx_lm


def require_pinned_runtime() -> tuple[Any, Any]:
    """Import MLX lazily and fail closed unless it matches the pin."""
    mx, mlx_lm = _import_mlx()
    versions = (getattr(mx, "__version__", None), getattr(mlx_lm, "__version__", None))
    if not all(isinstance(value, str) for value in versions):
        raise MlxPinError("cannot read mlx/mlx-lm versions to check the pin")
    check_pinned_versions(versions[0], versions[1])
    return mx, mlx_lm


def _multiset_recall(needle: Sequence[int], haystack: Sequence[int]) -> float:
    """Share of needle tokens covered by the multiset intersection (0..1)."""
    if not needle:
        raise MlxCanaryError("metric target tokens must be non-empty")
    counts_needle = Counter(int(token) for token in needle)
    counts_hay = Counter(int(token) for token in haystack)
    covered = sum(min(count, counts_hay.get(token, 0)) for token, count in counts_needle.items())
    return covered / len(needle)


def canary_metrics(
    *,
    target_tokens: Sequence[int],
    coordinate_tokens: Sequence[int],
    continuation_token_lists: Sequence[Sequence[int]],
) -> dict[str, float]:
    """Declared canary surface metrics; see the module docstring for definitions."""
    target = [int(token) for token in target_tokens]
    coordinate = [int(token) for token in coordinate_tokens]
    continuations = [[int(token) for token in item] for item in continuation_token_lists]
    if not target:
        raise MlxCanaryError("target tokens must be non-empty")
    if not continuations:
        raise MlxCanaryError("at least one continuation is required")
    fit = _multiset_recall(target, continuations[0])
    stability = sum(1 for item in continuations if item == continuations[0]) / len(continuations)
    compression = len(target) / (len(target) + len(coordinate))
    leakage = _multiset_recall(target, coordinate)
    return {
        "fit": round(fit, 6),
        "stability": round(stability, 6),
        "compression": round(compression, 6),
        "leakage": round(leakage, 6),
    }


def canary_coordinate_text(candidate: Candidate) -> str:
    """Declared coordinate text of a candidate (mirrors the exporter's prompt render)."""
    messages = candidate.messages
    if len(messages) == 1:
        return messages[0].content
    return "\n\n".join(f"{message.role}: {message.content}" for message in messages)


def render_candidate_prompt(tokenizer: Any, candidate: Candidate) -> tuple[list[int], str]:
    """Render one frozen candidate with the pinned chat template flags."""
    messages = [{"role": message.role, "content": message.content} for message in candidate.messages]
    token_ids = tokenizer.apply_chat_template(
        messages, tokenize=True, add_generation_prompt=True, enable_thinking=False
    )
    rendered = tokenizer.apply_chat_template(
        messages, tokenize=False, add_generation_prompt=True, enable_thinking=False
    )
    return [int(token) for token in token_ids], str(rendered)


def canary_coordinate_cost(
    candidate: Candidate,
    *,
    tokenizer: Any,
    tokenizer_view: str,
    tokenizer_digest: str,
    target_tokens: int,
) -> CoordinateCost:
    """``C(p)`` for one candidate under the pinned tokenizer view.

    ``coordinate_tokens`` counts the bare coordinate text, not the rendered
    evaluator input, which is recorded separately. Continuation tokens are not
    yet known when the archive records ``C(p)`` (they are carried by the
    evaluation receipt's resource use), so they are recorded as 0 here.
    """
    text = canary_coordinate_text(candidate)
    coordinate_ids = [int(token) for token in tokenizer.encode(text, add_special_tokens=False)]
    coordinate_bytes = len(text.encode("utf-8"))
    rendered_ids, rendered_text = render_candidate_prompt(tokenizer, candidate)
    if len(rendered_ids) < len(coordinate_ids):
        raise MlxCanaryError("rendered evaluator input is shorter than the bare coordinate; cannot record C(p)")
    return CoordinateCost(
        tokenizer_view=tokenizer_view,
        tokenizer_digest=tokenizer_digest,
        coordinate_tokens=len(coordinate_ids),
        coordinate_utf8_bytes=coordinate_bytes,
        full_rendered_tokens=len(rendered_ids),
        full_rendered_utf8_bytes=len(rendered_text.encode("utf-8")),
        target_tokens=int(target_tokens),
        continuation_tokens=0,
        prefix_free_bits=None,
    )


class MlxCanaryEvaluationAdapter:
    """Pinned evaluator: fresh greedy generations scored by declared surface metrics."""

    def __init__(
        self,
        *,
        identity: AdapterIdentity,
        model: Any,
        tokenizer: Any,
        target_text: str,
        tokenizer_view: str,
        tokenizer_digest: str,
        max_new_tokens: int,
        samples: int,
        temperature: float = 0.0,
    ) -> None:
        if not isinstance(max_new_tokens, int) or isinstance(max_new_tokens, bool) or max_new_tokens < 1:
            raise MlxCanaryError("max_new_tokens must be a positive int")
        if not isinstance(samples, int) or isinstance(samples, bool) or samples < 1:
            raise MlxCanaryError("samples must be a positive int")
        from mlx_lm import stream_generate
        from mlx_lm.sample_utils import make_sampler

        self._identity = identity
        self._model = model
        self._tokenizer = tokenizer
        self._target_text = target_text
        self._tokenizer_view = tokenizer_view
        self._tokenizer_digest = tokenizer_digest
        self._max_new_tokens = max_new_tokens
        self._samples = samples
        self._stream_generate = stream_generate
        self._sampler = make_sampler(temp=temperature)
        self._target_tokens = [
            int(token) for token in self._tokenizer.encode(target_text, add_special_tokens=False)
        ]
        if not self._target_tokens:
            raise MlxCanaryError("smoke target tokenizes to nothing under the pinned tokenizer")

    @property
    def identity(self) -> AdapterIdentity:
        return self._identity

    def evaluate(self, request: EvaluationRequest) -> EvaluationReceipt:
        token_ids, _rendered = render_candidate_prompt(self._tokenizer, request.candidate)
        texts: list[str] = []
        output_tokens = 0
        prompt_tokens = 0
        finish_reason: str | None = None
        for _ in range(self._samples):
            parts: list[str] = []
            last = None
            for response in self._stream_generate(
                self._model,
                self._tokenizer,
                token_ids,
                max_tokens=self._max_new_tokens,
                sampler=self._sampler,
            ):
                parts.append(response.text)
                last = response
            if last is None:
                raise MlxCanaryError("generation produced no response")
            texts.append("".join(parts).strip())
            output_tokens += int(last.generation_tokens)
            prompt_tokens = int(last.prompt_tokens)
            if last.finish_reason is not None:
                finish_reason = str(last.finish_reason)
        if not texts[0]:
            raise MlxCanaryError(
                f"empty continuation for candidate {request.candidate.candidate_id}; "
                "refusing to record an empty observation"
            )
        coordinate_tokens = [
            int(token)
            for token in self._tokenizer.encode(canary_coordinate_text(request.candidate), add_special_tokens=False)
        ]
        continuation_token_lists = [
            [int(token) for token in self._tokenizer.encode(text, add_special_tokens=False)]
            for text in texts
        ]
        metrics = canary_metrics(
            target_tokens=self._target_tokens,
            coordinate_tokens=coordinate_tokens,
            continuation_token_lists=continuation_token_lists,
        )
        outputs: dict[str, Any] = {"text": texts[0], "greedy": True}
        if finish_reason is not None:
            outputs["finishReason"] = finish_reason
        return evaluation_receipt(
            request_id=request.request_id,
            adapter=self._identity,
            candidate_id=request.candidate.candidate_id,
            metrics=metrics,
            resource_use={
                "inputTokens": prompt_tokens,
                "outputTokens": output_tokens,
                "samples": self._samples,
                "providerReportedTokens": prompt_tokens + output_tokens,
            },
            outputs=outputs,
        )
