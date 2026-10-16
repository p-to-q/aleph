"""GCG inner loop for MiniPrompt reproduction runs (MLX execution path).

Reimplements the loop in the pinned upstream ``prompt_optimization/gcg.py``
(``locuslab/acr-memorization`` @ ``bf3ba2e7``) on MLX:

- teacher-forced mean cross-entropy over the target tokens; with the empty
  scaffold the sequence is exactly ``[free tokens, target tokens]`` and the
  loss positions are the last free position plus the target prefix positions;
- gradient of the loss with respect to the input embeddings (weights frozen);
- ``topk`` descent-direction candidate tokens per free position, computed as
  ``embed_tokens.as_linear`` of the embedding gradient (the MLX equivalent of
  the upstream one-hot gradient);
- ``batch`` candidates, each mutating one seeded-random free position to a
  seeded-random entry of that position's top-k list;
- best-by-loss selection, early stop when the selected candidate passes both
  the single-sequence solution check (every target token is the argmax of the
  teacher-forced logits — the same fixed evaluation shape as the receipt
  re-check and as upstream's ``check_output_with_hard_tokens``) and the true
  greedy continuation from the raw IDs; a step that passes only the
  teacher-forced check does not stop the scan (4-bit quantized logits are
  evaluation-shape dependent, and the batched candidate forward supplies
  candidate losses only); a best-by-loss iterate is kept as the fallback
  solution exactly as upstream: the solution is the all-match iterate when
  the attempt acquires, otherwise the best-by-loss iterate;
- the attempt's success flag is re-checked on the solution (the same
  single-sequence criterion), so that a restored checkpoint cannot claim an
  acquisition the current evaluation denies, and claimed acquisitions are
  additionally verified by the true greedy continuation from the raw IDs (no
  retokenization).

Declared differences from upstream are listed in
``receipts.DECLARED_DIFFERENCES``; the ones that live in this module are the
``mx.argpartition`` tail (unordered within the top-k set; the pick is uniform
over the set), the seeded Python sampling from ``sampling.py``, and
mini-batch chunking identical to upstream (default ``miniBatch == batch``).
"""

from __future__ import annotations

import hashlib
import os
import time
from typing import Callable, List, Optional

import mlx.core as mx
import mlx.nn as nn
from huggingface_hub import snapshot_download
from mlx_lm import load

from . import sampling
from .config import MiniPromptConfig


class ModelPinError(RuntimeError):
    """The pinned model snapshot is missing or does not match the declaration."""


class AttemptInconsistency(RuntimeError):
    """An acquisition claim and its solution re-check disagree."""


def sha256_file(path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def load_pinned(repo: str, revision: str, weights_digest: str):
    """Load a pinned model snapshot strictly (fail-closed on any pin mismatch)."""
    try:
        snapshot = snapshot_download(repo, revision=revision, local_files_only=True)
    except Exception as exc:  # noqa: BLE001 - fail closed with operator guidance
        raise ModelPinError(
            f"pinned snapshot {repo}@{revision} is not available in the local "
            f"cache ({exc}); fetch it with `huggingface-cli download {repo} "
            f"--revision {revision}` and retry"
        ) from exc
    weights = os.path.join(snapshot, "model.safetensors")
    if not os.path.exists(weights):
        raise ModelPinError(f"pinned snapshot has no model.safetensors: {weights}")
    actual = sha256_file(weights)
    if actual != weights_digest:
        raise ModelPinError(
            f"weights digest mismatch for {repo}@{revision}: "
            f"expected {weights_digest}, found {actual}"
        )
    model, tokenizer = load(snapshot)
    model_meta = {
        "repo": repo,
        "revision": revision,
        "weightsDigest": actual,
        "vocabSize": int(model.args.vocab_size),
    }
    return model, tokenizer, model_meta


def load_pinned_model(config: MiniPromptConfig):
    """Load the model declared by ``config`` strictly (fail-closed on any pin mismatch)."""
    return load_pinned(config.repo, config.revision, config.weights_digest)


def target_token_ids(tokenizer, text: str):
    """Encode the target; returns ``(token_ids, per-token rendering)``."""
    ids = list(tokenizer.encode(text))
    rendering = [tokenizer.decode([token]) for token in ids]
    return ids, rendering


def gcg_step(model, config: MiniPromptConfig, ids, n_free: int, loss_pos: slice, target_mx, step: int) -> dict:
    """One GCG step; returns the selected candidate (selected by batched loss)."""
    started = time.time()
    vocab_size = int(model.args.vocab_size)

    def loss_fn(embeddings):
        logits = model(ids, cache=None, input_embeddings=embeddings)
        log_probs = nn.log_softmax(logits[0, loss_pos].astype(mx.float32), axis=-1)
        target_log_probs = mx.take_along_axis(log_probs, target_mx[:, None], axis=-1).squeeze(-1)
        return -mx.mean(target_log_probs)

    embeddings = model.model.embed_tokens(ids)
    gradient = mx.grad(loss_fn)(embeddings)
    mx.eval(gradient)
    descent = model.model.embed_tokens.as_linear(gradient[0, :n_free])
    ordered = mx.argpartition(-descent, kth=vocab_size - config.topk, axis=-1)
    candidate_rows = ordered[:, -config.topk:].tolist()

    mutations = sampling.step_mutations(config.seed, n_free, config.topk, step, config.batch)
    rows = sampling.apply_mutations(ids[0].tolist(), candidate_rows, mutations)

    losses: List[float] = []
    for start in range(0, config.batch, config.mini_batch):
        chunk = mx.array(rows[start : start + config.mini_batch], dtype=mx.int32)
        logits = model(chunk)
        log_probs = nn.log_softmax(logits[:, loss_pos].astype(mx.float32), axis=-1)
        targets = mx.broadcast_to(target_mx, (chunk.shape[0], target_mx.shape[0]))
        target_log_probs = mx.take_along_axis(log_probs, targets[..., None], axis=-1).squeeze(-1)
        chunk_losses = -mx.mean(target_log_probs, axis=-1)
        mx.eval(chunk_losses)
        losses.extend(chunk_losses.tolist())

    best = min(range(len(losses)), key=lambda index: losses[index])
    return {
        "best_free_ids": rows[best][:n_free],
        "loss": float(losses[best]),
        "candidates": len(rows),
        "seconds": time.time() - started,
    }


def solution_check(model, free_ids: List[int], target_list: List[int]) -> dict:
    """The single-sequence solution check (the acquisition criterion).

    Upstream ``check_output_with_hard_tokens``: every target token is the
    argmax of the teacher-forced logits at the target positions. Evaluated on
    one single-sequence forward — the same fixed shape as the receipt
    re-check — because 4-bit quantized logits are batch-shape dependent (a
    declared difference); the batched candidate forward supplies candidate
    losses only. Returns ``{"matchAll": bool, "matchTokens": int}``.
    """
    loss_pos = slice(len(free_ids) - 1, len(free_ids) - 1 + len(target_list))
    target_mx = mx.array(list(target_list), dtype=mx.int32)
    ids = mx.array([list(free_ids) + list(target_list)], dtype=mx.int32)
    logits = model(ids)
    matched = [bool(flag) for flag in (logits[0, loss_pos].argmax(-1) == target_mx).tolist()]
    return {"matchAll": all(matched), "matchTokens": sum(matched)}


def run_attempt(
    model,
    config: MiniPromptConfig,
    *,
    n_free: int,
    steps_budget: int,
    target_ids: List[int],
    initial_free_ids: List[int],
    resume: Optional[dict] = None,
    on_step: Optional[Callable[[dict], None]] = None,
    should_pause: Optional[Callable[[], bool]] = None,
) -> dict:
    """Run or resume one GCG attempt under the upstream loop semantics.

    Returns ``{"paused": True, "resume": {...}}`` when the pause predicate
    fired, otherwise the completed outcome (``stepsRun``, ``acquired``,
    ``acquiredAtStep``, solution fields, ``wholePromptTokens``, trajectory).
    """
    vocab_size = int(model.args.vocab_size)
    if config.topk > vocab_size:
        raise ValueError(
            f"config.topk ({config.topk}) exceeds the model vocabulary ({vocab_size})"
        )
    if steps_budget < 1:
        raise ValueError("steps_budget must be >= 1")
    target_list = list(target_ids)
    target_mx = mx.array(target_list, dtype=mx.int32)
    loss_pos = slice(n_free - 1, n_free - 1 + len(target_list))

    if resume is None:
        step = 0
        free_ids = list(initial_free_ids)
        best_loss: Optional[float] = None
        best_ids: Optional[List[int]] = None
        solution_source: Optional[str] = None
        solution_loss: Optional[float] = None
        trajectory: List[dict] = []
        last_match_tokens = 0
        last_loss: Optional[float] = None
        acquired_at: Optional[int] = None
    else:
        step = int(resume["step"])
        free_ids = list(resume["freeIds"])
        best_loss = resume["bestLoss"]
        best_ids = list(resume["bestIds"]) if resume["bestIds"] is not None else None
        solution_source = resume["solutionSource"]
        solution_loss = resume["solutionLoss"]
        trajectory = list(resume["trajectory"])
        last_match_tokens = int(resume["lastMatchTokens"])
        last_loss = resume["lastLoss"]
        # a checkpoint may already carry the terminal acquisition; restore it so
        # resuming an acquired attempt never re-runs the acquiring step
        acquired_at = resume.get("acquiredAtStep")
        if acquired_at is not None and not isinstance(acquired_at, int):
            raise ValueError("resume.acquiredAtStep must be an integer or null")

    acquired = acquired_at is not None
    paused = False
    while not acquired and step < steps_budget:
        if should_pause is not None and should_pause():
            paused = True
            break
        ids = mx.array([free_ids + target_list], dtype=mx.int32)
        record = gcg_step(model, config, ids, n_free, loss_pos, target_mx, step)
        free_ids = list(record["best_free_ids"])
        last_loss = record["loss"]
        check = solution_check(model, free_ids, target_list)
        last_match_tokens = check["matchTokens"]
        trajectory.append(
            {
                "step": step,
                "loss": round(record["loss"], 6),
                "matchTokens": last_match_tokens,
                "seconds": round(record["seconds"], 3),
            }
        )
        if check["matchAll"]:
            emitted = greedy_continuation_ids(model, free_ids, target_list)
            if emitted == list(target_list):
                best_ids = list(free_ids)
                solution_source = "acquired"
                solution_loss = record["loss"]
                acquired = True
                acquired_at = step
                step += 1
                if on_step is not None:
                    on_step(
                        {
                            "step": step,
                            "freeIds": free_ids,
                            "bestLoss": best_loss,
                            "bestIds": best_ids,
                            "solutionSource": solution_source,
                            "solutionLoss": solution_loss,
                            "trajectory": trajectory,
                            "lastMatchTokens": last_match_tokens,
                            "lastLoss": last_loss,
                            "acquiredAtStep": acquired_at,
                        }
                    )
                break
            # Teacher-forced all-match without a reproducing greedy
            # continuation: fall through as a regular step and keep scanning.
        if best_loss is None or record["loss"] < best_loss:
            best_loss = record["loss"]
            best_ids = list(free_ids)
            solution_source = "best_by_loss"
            solution_loss = record["loss"]
        step += 1
        if on_step is not None:
            on_step(
                {
                    "step": step,
                    "freeIds": free_ids,
                    "bestLoss": best_loss,
                    "bestIds": best_ids,
                    "solutionSource": solution_source,
                    "solutionLoss": solution_loss,
                    "trajectory": trajectory,
                    "lastMatchTokens": last_match_tokens,
                    "lastLoss": last_loss,
                    "acquiredAtStep": None,
                }
            )

    if paused:
        return {
            "paused": True,
            "resume": {
                "step": step,
                "freeIds": free_ids,
                "bestLoss": best_loss,
                "bestIds": best_ids,
                "solutionSource": solution_source,
                "solutionLoss": solution_loss,
                "trajectory": trajectory,
                "lastMatchTokens": last_match_tokens,
                "lastLoss": last_loss,
                "acquiredAtStep": acquired_at,
            },
        }

    if best_ids is None:
        best_ids = list(free_ids)

    acquired = acquired_at is not None
    if acquired:
        # The acquisition claim (fresh in-loop, or restored from a checkpoint)
        # must survive a re-run of the single-sequence teacher-forced check
        # here; the runner separately re-verifies the greedy continuation on
        # the same shapes, so no claim can rest on a disagreeing evaluation.
        check = solution_check(model, best_ids, target_list)
        if not check["matchAll"]:
            raise AttemptInconsistency(
                "acquisition claim (fresh or restored) disagrees with the "
                "single-sequence solution re-check"
            )

    if solution_loss is None:
        solution_loss = last_loss if last_loss is not None else 0.0

    return {
        "paused": False,
        "stepsRun": step,
        "acquired": acquired,
        "acquiredAtStep": acquired_at,
        "initialFreeIds": list(initial_free_ids),
        "solutionFreeIds": list(best_ids),
        "solutionLoss": round(float(solution_loss), 6),
        "solutionSource": solution_source or "best_by_loss",
        "wholePromptTokens": n_free + len(target_list),
        "trajectory": trajectory,
    }


def greedy_continuation_ids(model, free_ids: List[int], target_list: List[int]) -> List[int]:
    """Greedy continuation from the raw IDs (no retokenization).

    Generates up to ``len(target_list)`` tokens by repeatedly forwarding the
    prefix and taking the argmax at the last position, stopping at the first
    divergence; the emitted IDs are the observable.
    """
    sequence = list(free_ids)
    emitted: List[int] = []
    for target_token in target_list:
        logits = model(mx.array([sequence], dtype=mx.int32))
        next_token = int(mx.argmax(logits[0, -1]).item())
        emitted.append(next_token)
        if next_token != target_token:
            break
        sequence.append(next_token)
    return emitted


def greedy_continuation_check(model, tokenizer, free_ids: List[int], target_ids: List[int]) -> dict:
    """True greedy continuation from the raw IDs (no retokenization)."""
    emitted = greedy_continuation_ids(model, free_ids, target_ids)
    return {
        "ran": True,
        "matched": emitted == list(target_ids),
        "roundtripEqual": list(tokenizer.encode(tokenizer.decode(free_ids))) == list(free_ids),
        "emittedIds": emitted,
        "freeRendering": tokenizer.decode(free_ids),
        "emittedRendering": tokenizer.decode(emitted),
    }
