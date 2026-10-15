"""Scan runner for MiniPrompt reproduction runs (MLX execution path).

Drives the frozen scan policy (``scan.py``) over GCG attempts (``gcg.py``),
checkpointing run state after every step so a run survives tool-call time
budgets and crashes and can be resumed exactly. On completion it writes the
receipt (``receipts.py``) and the final state.

Run directories contain ``state.json`` (checkpoint; resumable and transient)
and ``receipt.json`` (the archived record, built only after the receipt passes
self-verification).
"""

from __future__ import annotations

import platform as platform_module
import time
from importlib import metadata
from pathlib import Path

from . import gcg, receipts, sampling
from .config import MiniPromptConfig
from .receipts import STATE_SCHEMA, read_json, write_json_atomic
from .scan import ScanPolicy, ScanPolicyError


class RunStateError(RuntimeError):
    """Run state is missing, malformed, or belongs to a different declaration."""


def utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def environment_metadata() -> dict:
    return {
        "python": platform_module.python_version(),
        "mlx": metadata.version("mlx"),
        "mlxLm": metadata.version("mlx-lm"),
        "platform": platform_module.platform(),
    }


def _validate_state_envelope(state, config: MiniPromptConfig) -> None:
    if not isinstance(state, dict) or state.get("schema") != STATE_SCHEMA:
        raise RunStateError("run state has an unexpected schema")
    if state.get("configDigest") != config.digest or state.get("config") != config.to_canonical():
        raise RunStateError("refusing to resume: run state belongs to a different declared config")
    for key in ("model", "environment", "target", "scan", "attempts"):
        if key not in state:
            raise RunStateError(f"run state is missing {key!r}")


def _validated_policy(state, config: MiniPromptConfig, target_token_count: int) -> ScanPolicy:
    """Rebuild the policy from recorded outcomes and validate the snapshot."""
    try:
        replayed = ScanPolicy(config, target_token_count)
        for position, attempt in enumerate(state["attempts"]):
            spec = replayed.next_spec()
            if (
                spec is None
                or attempt.get("nFree") != spec.n_free
                or attempt.get("stepsBudget") != spec.steps_budget
            ):
                raise ScanPolicyError(f"recorded attempt {position} disagrees with the scan policy")
            replayed.record(bool(attempt.get("acquired")))
        if replayed.to_snapshot() != state["scan"]:
            # the crash window between the last record and the next attempt spec
            replayed.next_spec()
            if replayed.to_snapshot() != state["scan"]:
                raise ScanPolicyError("scan snapshot disagrees with the policy replay")
        return ScanPolicy.from_snapshot(config, target_token_count, state["scan"])
    except (ScanPolicyError, KeyError, TypeError, ValueError) as exc:
        raise RunStateError(f"run state scan snapshot is inconsistent: {exc}") from exc


def _attempt_record(current: dict, outcome: dict, greedy) -> dict:
    return {
        "index": current["index"],
        "nFree": current["nFree"],
        "stepsBudget": current["stepsBudget"],
        "stepsRun": outcome["stepsRun"],
        "acquired": outcome["acquired"],
        "acquiredAtStep": outcome["acquiredAtStep"],
        "initialFreeIds": outcome["initialFreeIds"],
        "solutionFreeIds": outcome["solutionFreeIds"],
        "solutionLoss": outcome["solutionLoss"],
        "solutionSource": outcome["solutionSource"],
        "wholePromptTokens": outcome["wholePromptTokens"],
        "trajectory": outcome["trajectory"],
        "greedy": greedy,
    }


def _finalize(config: MiniPromptConfig, run_dir: Path, state: dict, log) -> None:
    policy = ScanPolicy.from_snapshot(config, len(state["target"]["tokenIds"]), state["scan"])
    result = receipts.result_from_policy(policy.state, state["attempts"])
    receipt = receipts.build_receipt(
        config=config,
        model=state["model"],
        environment=state["environment"],
        target=state["target"],
        attempts=state["attempts"],
        result=result,
        created_at=utc_now(),
    )
    errors = receipts.verify_receipt(receipt)
    if errors:
        # Never archive an inconsistent receipt: fail closed before writing.
        raise RunStateError(f"the built receipt failed self-verification: {errors[:3]}")
    write_json_atomic(run_dir / "receipt.json", receipt)
    state["lastStop"] = "complete"
    state["updatedAt"] = utc_now()
    write_json_atomic(run_dir / "state.json", state)
    log(
        f"receipt written: {run_dir / 'receipt.json'} (success={result['success']} "
        f"numFreeTokens={result['numFreeTokens']} attempts={result['attempts']} "
        f"stopReason={result['stopReason']})"
    )


def run_scan(config: MiniPromptConfig, run_dir, *, max_seconds=None, log=print) -> int:
    """Run or resume a declared scan. Returns 0 complete, 3 paused."""
    run_dir = Path(run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)
    state_path = run_dir / "state.json"
    receipt_path = run_dir / "receipt.json"

    if receipt_path.exists():
        receipt = read_json(receipt_path)
        result = receipt.get("result") or {}
        log(f"run already complete: {receipt_path} (success={result.get('success')})")
        return 0

    state = read_json(state_path) if state_path.exists() else None
    if state is not None:
        _validate_state_envelope(state, config)

    log(f"loading pinned model {config.repo}@{config.revision[:12]}…")
    model, tokenizer, model_meta = gcg.load_pinned_model(config)
    if config.topk > model_meta["vocabSize"]:
        raise RunStateError(
            f"config.topk ({config.topk}) exceeds the model vocabulary ({model_meta['vocabSize']})"
        )

    if state is None:
        target_ids, target_rendering = gcg.target_token_ids(tokenizer, config.target)
        created_at = utc_now()
        policy = ScanPolicy(config, len(target_ids))
        state = {
            "schema": STATE_SCHEMA,
            "createdAt": created_at,
            "updatedAt": created_at,
            "config": config.to_canonical(),
            "configDigest": config.digest,
            "model": model_meta,
            "environment": environment_metadata(),
            "target": {
                "text": config.target,
                "tokenIds": target_ids,
                "tokenCount": len(target_ids),
                "rendering": target_rendering,
            },
            "scan": policy.to_snapshot(),
            "attempts": [],
            "current": None,
            "lastStop": None,
        }
        write_json_atomic(state_path, state)
        log(f"target {config.target!r} -> {len(target_ids)} token(s): {target_ids}")
    else:
        target_ids = list(state["target"]["tokenIds"])
        if state["model"] != model_meta:
            raise RunStateError("run state model identity differs from the freshly loaded pinned model")
        policy = _validated_policy(state, config, len(target_ids))

    deadline = None if max_seconds is None else time.monotonic() + float(max_seconds)

    while True:
        current = state["current"]
        if current is None:
            spec = policy.next_spec()
            state["scan"] = policy.to_snapshot()
            state["updatedAt"] = utc_now()
            if spec is None:
                write_json_atomic(state_path, state)
                _finalize(config, run_dir, state, log)
                return 0
            current = {
                "index": spec.index,
                "nFree": spec.n_free,
                "stepsBudget": spec.steps_budget,
                "step": 0,
                "initialFreeIds": sampling.initial_free_ids(config.seed, spec.n_free, model_meta["vocabSize"]),
                "freeIds": None,
                "bestLoss": None,
                "bestIds": None,
                "solutionSource": None,
                "solutionLoss": None,
                "trajectory": [],
                "lastMatchTokens": 0,
                "lastLoss": None,
            }
            current["freeIds"] = list(current["initialFreeIds"])
            state["current"] = current
            state["lastStop"] = None
            write_json_atomic(state_path, state)
            log(f"attempt {spec.index}: n_free={spec.n_free} steps_budget={spec.steps_budget}")
        else:
            spec = policy.next_spec()
            if (
                spec is None
                or spec.index != current["index"]
                or spec.n_free != current["nFree"]
                or spec.steps_budget != current["stepsBudget"]
            ):
                raise RunStateError("run state current attempt disagrees with the scan policy")

        if deadline is not None and time.monotonic() > deadline and current["step"] > 0:
            state["lastStop"] = "time_budget"
            state["updatedAt"] = utc_now()
            write_json_atomic(state_path, state)
            log(
                f"time budget reached; attempt {current['index']} paused at step "
                f"{current['step']} — re-run the same command to resume"
            )
            return 3

        def _on_step(step_state):
            current.update(step_state)
            state["updatedAt"] = utc_now()
            write_json_atomic(state_path, state)

        resume = None
        if current["step"] > 0 or current["trajectory"]:
            resume = {
                "step": current["step"],
                "freeIds": current["freeIds"],
                "bestLoss": current["bestLoss"],
                "bestIds": current["bestIds"],
                "solutionSource": current["solutionSource"],
                "solutionLoss": current["solutionLoss"],
                "trajectory": current["trajectory"],
                "lastMatchTokens": current["lastMatchTokens"],
                "lastLoss": current["lastLoss"],
            }

        outcome = gcg.run_attempt(
            model,
            config,
            n_free=current["nFree"],
            steps_budget=current["stepsBudget"],
            target_ids=target_ids,
            initial_free_ids=current["initialFreeIds"],
            resume=resume,
            on_step=_on_step,
            should_pause=None if deadline is None else lambda: time.monotonic() > deadline,
        )

        if outcome["paused"]:
            current.update(outcome["resume"])
            state["lastStop"] = "time_budget"
            state["updatedAt"] = utc_now()
            write_json_atomic(state_path, state)
            log(
                f"time budget reached; attempt {current['index']} paused at step "
                f"{current['step']} — re-run the same command to resume"
            )
            return 3

        acquired = outcome["acquired"]
        greedy = None
        if acquired:
            greedy = gcg.greedy_continuation_check(model, tokenizer, outcome["solutionFreeIds"], target_ids)
            attempt_record = _attempt_record(current, outcome, greedy)
            if not greedy["matched"]:
                # Fail closed: keep the inconsistent record on disk for audit,
                # but never continue or receipt it as a claimed acquisition.
                state["attempts"].append(attempt_record)
                state["current"] = None
                state["lastStop"] = "inconsistent_greedy_check"
                state["updatedAt"] = utc_now()
                write_json_atomic(state_path, state)
                raise RunStateError(
                    "all-match acquisition did not reproduce under true greedy continuation; "
                    "the attempt was recorded and the run was stopped"
                )
        else:
            attempt_record = _attempt_record(current, outcome, greedy)

        state["attempts"].append(attempt_record)
        state["current"] = None
        policy.record(acquired)
        state["scan"] = policy.to_snapshot()
        state["updatedAt"] = utc_now()
        write_json_atomic(state_path, state)
        log(
            f"attempt {attempt_record['index']}: acquired={acquired} "
            f"steps={attempt_record['stepsRun']} solutionLoss={attempt_record['solutionLoss']}"
        )
