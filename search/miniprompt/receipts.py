"""Receipts and run state for MiniPrompt reproduction runs (pure standard library).

A receipt is the archived record for one scan: the declared configuration and
its canonical digest, the pinned model identity, the target token IDs, every
attempt (nFree, step budget, outcome, trajectory, solution IDs, and — for
claimed acquisitions — the greedy-continuation check recorded from raw IDs),
and the scan result under the upstream policy. ``receiptDigest`` is the
``aleph-canonical/0.2.0`` digest of the receipt body (everything except the
digest field).

Every receipt labels found prompts as raw coordinates: free-token IDs are the
ground truth and decoded text is a declared rendering, never a readable
prompt. ``verify_receipt`` re-checks a receipt without MLX or network: the
canonical digest, the strict configuration parse, the scan-policy replay
across recorded outcomes, and the acquisition evidence chain (all-match plus
the greedy-continuation check).

Run state (``state.json``) checkpoints an in-progress scan so runs are
resumable; it is written atomically after every GCG step.
"""

from __future__ import annotations

import json
import math
import os
import re
import tempfile
from pathlib import Path
from typing import List, Optional

from search.engine.canonical import digest, is_digest

from .config import MiniPromptConfig, ConfigError, config_from_canonical, loads_strict
from .scan import STOP_COLLISION, ScanPolicyError, replay_outcomes

RECEIPT_SCHEMA = "aleph-miniprompt-receipt/0.1.0"
STATE_SCHEMA = "aleph-miniprompt-run-state/0.1.0"
TOOL = {"name": "search/miniprompt", "version": "0.1.0"}

RAW_VIEW_VIEW = "raw"
RAW_VIEW_LABEL = (
    "raw coordinate: free-token IDs are the ground truth; decoded text is a "
    "declared rendering, not a readable prompt"
)

# Declared differences of the MLX reproduction from the pinned upstream loop;
# recorded in every receipt so the archive is self-describing.
DECLARED_DIFFERENCES = (
    "MLX with 4-bit quantized weights instead of the upstream torch bf16 stack; "
    "gradients are taken with respect to input embeddings only (weights frozen).",
    "Candidate top-k uses mx.argpartition (unordered tail) with a uniform pick "
    "over the same top-k set as torch.topk.",
    "The acquisition criterion is the conjunction of the single-sequence "
    "teacher-forced all-match (upstream check_output_with_hard_tokens, on the "
    "fixed single-sequence shape of the receipt re-check) and the true greedy "
    "continuation from the raw IDs, both checked in-loop at the claiming step; "
    "4-bit quantized logits are evaluation-shape dependent (batch and sequence "
    "length), so batched forwards supply candidate losses only.",
    "Free-token initialization and per-step mutation draws use explicit Python "
    "random.Random derivations (sampling.py) instead of the process-global RNG, "
    "so attempts are deterministic and resumable.",
    "Declared Aleph-side bounds: stepsHardCap caps the step budget after growth; "
    "maxAttempts limits the number of GCG attempts.",
    "Only the upstream empty scaffold is declared; scaffolded layouts are a "
    "future declared extension.",
)

_CREATED_AT = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")


def _is_int(value) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _is_finite_number(value) -> bool:
    return (
        not isinstance(value, bool)
        and isinstance(value, (int, float))
        and math.isfinite(float(value))
    )


def raw_view_block() -> dict:
    """The mandatory raw-coordinate labeling carried by every receipt."""
    return {
        "view": RAW_VIEW_VIEW,
        "label": RAW_VIEW_LABEL,
        "note": "No readable-prompt or human-eligibility claim is made for found prompts.",
    }


def receipt_body(receipt: dict) -> dict:
    """The receipt without its digest field (what ``receiptDigest`` covers)."""
    return {key: value for key, value in receipt.items() if key != "receiptDigest"}


def build_receipt(
    *,
    config: MiniPromptConfig,
    model: dict,
    environment: dict,
    target: dict,
    attempts: List[dict],
    result: dict,
    created_at: str,
) -> dict:
    """Assemble a receipt and attach its canonical ``receiptDigest``."""
    body = {
        "schema": RECEIPT_SCHEMA,
        "tool": dict(TOOL),
        "createdAt": created_at,
        "config": config.to_canonical(),
        "configDigest": config.digest,
        "target": target,
        "model": model,
        "environment": environment,
        "procedure": {
            "implementation": dict(TOOL),
            "declaredDifferences": list(DECLARED_DIFFERENCES),
        },
        "rawView": raw_view_block(),
        "attempts": attempts,
        "result": result,
    }
    receipt = dict(body)
    receipt["receiptDigest"] = digest(body)
    return receipt


def result_from_policy(policy_state, attempts: List[dict]) -> dict:
    """The scan result summary derived from a finished policy state."""
    acquired_ns = [
        attempt.get("nFree")
        for attempt in attempts
        if isinstance(attempt, dict)
        and attempt.get("acquired") is True
        and _is_int(attempt.get("nFree"))
    ]
    return {
        "success": bool(policy_state.success),
        "numFreeTokens": policy_state.running_max,
        "stopReason": policy_state.stop_reason,
        "scanTerminated": policy_state.stop_reason == STOP_COLLISION,
        "attempts": policy_state.attempts,
        "smallestAcquiredNFree": min(acquired_ns, default=None),
    }


def read_json(path):
    """Read JSON fail-closed (duplicate object keys are rejected)."""
    return loads_strict(Path(path).read_text(encoding="utf-8"))


def write_json_atomic(path, data) -> None:
    """Atomically write indented JSON (temp file + replace)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def load_receipt(path) -> dict:
    return read_json(path)


def _verify_attempt(attempt, position: int, target_ids: Optional[list], errors: List[str]) -> Optional[bool]:
    """Validate one attempt record; returns its ``acquired`` flag when valid."""
    where = f"attempts[{position}]"
    if not isinstance(attempt, dict):
        errors.append(f"{where}: expected a mapping")
        return None

    def err(message: str) -> None:
        errors.append(message)

    known_attempt_fields = {
        "index", "nFree", "stepsBudget", "stepsRun", "acquired", "acquiredAtStep",
        "initialFreeIds", "solutionFreeIds", "solutionLoss", "solutionSource",
        "wholePromptTokens", "trajectory", "greedy",
    }
    for key in sorted(set(attempt) - known_attempt_fields):
        err(f"{where}: unknown field {key!r}")

    index = attempt.get("index")
    if not _is_int(index) or index != position:
        err(f"{where}.index: expected {position}")

    n_free = attempt.get("nFree")
    if not _is_int(n_free) or n_free < 1:
        err(f"{where}.nFree: expected an integer >= 1")
        n_free = None
    steps_budget = attempt.get("stepsBudget")
    if not _is_int(steps_budget) or steps_budget < 1:
        err(f"{where}.stepsBudget: expected an integer >= 1")
        steps_budget = None
    steps_run = attempt.get("stepsRun")
    if not _is_int(steps_run) or steps_run < 1:
        err(f"{where}.stepsRun: expected an integer >= 1")
        steps_run = None
    elif steps_budget is not None and steps_run > steps_budget:
        err(f"{where}.stepsRun: exceeds the step budget")

    acquired = attempt.get("acquired")
    if not isinstance(acquired, bool):
        err(f"{where}.acquired: expected a boolean")
        acquired = None

    acquired_at = attempt.get("acquiredAtStep")
    greedy = attempt.get("greedy")
    if acquired is True:
        if steps_run is not None and acquired_at != steps_run - 1:
            err(f"{where}.acquiredAtStep: expected {steps_run - 1} for an acquired attempt")
        elif steps_run is None and not _is_int(acquired_at):
            err(f"{where}.acquiredAtStep: expected an integer for an acquired attempt")
        if (
            not isinstance(greedy, dict)
            or greedy.get("ran") is not True
            or greedy.get("matched") is not True
            or greedy.get("roundtripEqual") is not True
        ):
            err(f"{where}.greedy: claimed acquisitions require a matched greedy-continuation check")
        else:
            for key in sorted(set(greedy) - {"ran", "matched", "roundtripEqual", "emittedIds", "freeRendering", "emittedRendering"}):
                err(f"{where}.greedy: unknown field {key!r}")
            if target_ids is not None and greedy.get("emittedIds") != target_ids:
                err(f"{where}.greedy.emittedIds: does not reproduce the target token IDs")
        if attempt.get("solutionSource") != "acquired":
            err(f"{where}.solutionSource: expected 'acquired'")
    elif acquired is False:
        if acquired_at is not None:
            err(f"{where}.acquiredAtStep: expected null for a non-acquired attempt")
        if greedy is not None:
            err(f"{where}.greedy: expected null for a non-acquired attempt")
        if attempt.get("solutionSource") != "best_by_loss":
            err(f"{where}.solutionSource: expected 'best_by_loss'")

    for name in ("initialFreeIds", "solutionFreeIds"):
        ids = attempt.get(name)
        if not isinstance(ids, list) or any(not _is_int(token) or token < 0 for token in ids):
            err(f"{where}.{name}: expected a list of non-negative integers")
        elif n_free is not None and len(ids) != n_free:
            err(f"{where}.{name}: length does not match nFree")

    solution_loss = attempt.get("solutionLoss")
    if not _is_finite_number(solution_loss):
        err(f"{where}.solutionLoss: expected a finite number")

    whole = attempt.get("wholePromptTokens")
    if not _is_int(whole) or whole < 1:
        err(f"{where}.wholePromptTokens: expected an integer >= 1")
    elif n_free is not None and target_ids is not None and whole != n_free + len(target_ids):
        err(f"{where}.wholePromptTokens: expected nFree + target token count")

    trajectory = attempt.get("trajectory")
    if not isinstance(trajectory, list) or not trajectory:
        err(f"{where}.trajectory: expected a non-empty list of step records")
    elif steps_run is not None and len(trajectory) != steps_run:
        err(f"{where}.trajectory: length does not match stepsRun")
    else:
        for step_index, step in enumerate(trajectory):
            if not isinstance(step, dict):
                err(f"{where}.trajectory[{step_index}]: expected a mapping")
                break
            for key in sorted(set(step) - {"step", "loss", "matchTokens", "seconds"}):
                err(f"{where}.trajectory[{step_index}]: unknown field {key!r}")
            if step.get("step") != step_index:
                err(f"{where}.trajectory[{step_index}].step: expected {step_index}")
            if not _is_finite_number(step.get("loss")):
                err(f"{where}.trajectory[{step_index}].loss: expected a finite number")
            match = step.get("matchTokens")
            if not _is_int(match) or match < 0 or (target_ids is not None and match > len(target_ids)):
                err(f"{where}.trajectory[{step_index}].matchTokens: expected an integer in [0, target token count]")
            seconds = step.get("seconds")
            if not _is_finite_number(seconds) or float(seconds) < 0:
                err(f"{where}.trajectory[{step_index}].seconds: expected a finite number >= 0")
        if acquired is True and target_ids is not None and isinstance(trajectory[-1], dict):
            last = trajectory[-1]
            if last.get("matchTokens") != len(target_ids):
                err(f"{where}.trajectory: an acquired attempt must end with a full match")
            if _is_finite_number(last.get("loss")) and _is_finite_number(solution_loss):
                if abs(float(last["loss"]) - float(solution_loss)) > 1e-6:
                    err(f"{where}.solutionLoss: does not match the acquisition step loss")

    return acquired


def verify_receipt(receipt) -> List[str]:
    """Fail-closed receipt verification without MLX; returns error strings."""
    errors: List[str] = []

    def err(message: str) -> None:
        errors.append(message)

    if not isinstance(receipt, dict):
        return ["receipt: expected a JSON object"]

    required_fields = (
        "schema", "tool", "createdAt", "config", "configDigest", "target", "model",
        "environment", "procedure", "rawView", "attempts", "result", "receiptDigest",
    )
    unknown = sorted(key for key in receipt if key not in required_fields)
    missing = sorted(key for key in required_fields if key not in receipt)
    for key in unknown:
        err(f"receipt: unknown field {key!r}")
    for key in missing:
        err(f"receipt: missing field {key!r}")
    if missing or unknown:
        return errors

    if receipt["schema"] != RECEIPT_SCHEMA:
        err(f"schema: expected {RECEIPT_SCHEMA!r}")
    if receipt["tool"] != TOOL:
        err("tool: does not match the declaring tool")
    if not isinstance(receipt["createdAt"], str) or not _CREATED_AT.match(receipt["createdAt"]):
        err("createdAt: expected an RFC 3339 UTC second-precision timestamp")

    config: Optional[MiniPromptConfig] = None
    try:
        config = config_from_canonical(receipt["config"])
    except ConfigError as exc:
        err(f"config: {exc}")
    if config is not None and receipt["configDigest"] != config.digest:
        err("configDigest: does not match the embedded config digest")
    if not is_digest(receipt["configDigest"]):
        err("configDigest: not a sha256 digest")

    if not is_digest(receipt["receiptDigest"]):
        err("receiptDigest: not a sha256 digest")
    else:
        try:
            recomputed = digest(receipt_body(receipt))
        except Exception as exc:  # fail-closed: the body must be canonicalizable
            err(f"receiptDigest: receipt body is not canonicalizable: {exc}")
            recomputed = None
        if recomputed is not None and recomputed != receipt["receiptDigest"]:
            err("receiptDigest: does not match the receipt body digest")

    raw_view = receipt["rawView"]
    if not isinstance(raw_view, dict) or raw_view.get("view") != RAW_VIEW_VIEW or raw_view.get("label") != RAW_VIEW_LABEL:
        err("rawView: missing the declared raw-coordinate labeling")
    else:
        for key in sorted(set(raw_view) - {"view", "label", "note"}):
            err(f"rawView: unknown field {key!r}")

    model = receipt["model"]
    if not isinstance(model, dict):
        err("model: expected a mapping")
    else:
        for key in sorted(set(model) - {"repo", "revision", "weightsDigest", "vocabSize"}):
            err(f"model: unknown field {key!r}")
        for key in ("repo", "revision", "weightsDigest"):
            value = model.get(key)
            if not isinstance(value, str) or not value:
                err(f"model.{key}: expected a non-empty string")
        if not is_digest(model.get("weightsDigest")):
            err("model.weightsDigest: not a sha256 digest")
        vocab = model.get("vocabSize")
        if not _is_int(vocab) or vocab < 1:
            err("model.vocabSize: expected an integer >= 1")
        if config is not None:
            if model.get("repo") != config.repo:
                err("model.repo: differs from the declared config")
            if model.get("revision") != config.revision:
                err("model.revision: differs from the declared config")
            if model.get("weightsDigest") != config.weights_digest:
                err("model.weightsDigest: differs from the declared config")

    environment = receipt["environment"]
    if not isinstance(environment, dict):
        err("environment: expected a mapping")
    else:
        for key in sorted(set(environment) - {"python", "mlx", "mlxLm", "platform"}):
            err(f"environment: unknown field {key!r}")
        for key in ("python", "mlx", "mlxLm", "platform"):
            value = environment.get(key)
            if not isinstance(value, str) or not value:
                err(f"environment.{key}: expected a non-empty string")

    procedure = receipt["procedure"]
    if not isinstance(procedure, dict):
        err("procedure: expected a mapping")
    else:
        for key in sorted(set(procedure) - {"implementation", "declaredDifferences"}):
            err(f"procedure: unknown field {key!r}")
        if procedure.get("implementation") != TOOL:
            err("procedure.implementation: does not match the declaring tool")
        differences = procedure.get("declaredDifferences")
        if (
            not isinstance(differences, list)
            or not differences
            or any(not isinstance(item, str) or not item for item in differences)
        ):
            err("procedure.declaredDifferences: expected a non-empty list of strings")

    target = receipt["target"]
    target_ids: Optional[list] = None
    if not isinstance(target, dict):
        err("target: expected a mapping")
    else:
        for key in sorted(set(target) - {"text", "tokenIds", "tokenCount", "rendering"}):
            err(f"target: unknown field {key!r}")
        if config is not None and target.get("text") != config.target:
            err("target.text: differs from the declared config")
        token_ids = target.get("tokenIds")
        if not isinstance(token_ids, list) or not token_ids or any(
            not _is_int(token) or token < 0 for token in token_ids
        ):
            err("target.tokenIds: expected a non-empty list of non-negative integers")
        else:
            target_ids = token_ids
        if not isinstance(token_ids, list) or target.get("tokenCount") != len(token_ids):
            err("target.tokenCount: does not match tokenIds")
        rendering = target.get("rendering")
        if not isinstance(rendering, list) or any(not isinstance(item, str) for item in rendering):
            err("target.rendering: expected a list of strings")
        elif isinstance(token_ids, list) and len(rendering) != len(token_ids):
            err("target.rendering: length does not match tokenIds")

    attempts = receipt["attempts"]
    flags: List[Optional[bool]] = []
    if not isinstance(attempts, list) or not attempts:
        err("attempts: expected a non-empty list")
    else:
        for position, attempt in enumerate(attempts):
            flags.append(_verify_attempt(attempt, position, target_ids, errors))

    if isinstance(attempts, list) and attempts and config is not None and target_ids is not None:
        if all(isinstance(flag, bool) for flag in flags):
            try:
                specs, policy = replay_outcomes(config, len(target_ids), [bool(flag) for flag in flags])
            except ScanPolicyError as exc:
                err(f"attempts: {exc}")
            else:
                for position, spec in enumerate(specs):
                    attempt = attempts[position]
                    if attempt.get("nFree") != spec.n_free:
                        err(f"attempts[{position}].nFree: expected {spec.n_free} from the scan policy")
                    if attempt.get("stepsBudget") != spec.steps_budget:
                        err(f"attempts[{position}].stepsBudget: expected {spec.steps_budget} from the scan policy")
                if policy.next_spec() is not None:
                    err("attempts: recorded outcomes leave the scan unfinished")
                else:
                    expected_result = result_from_policy(policy.state, attempts)
                    result = receipt["result"]
                    if not isinstance(result, dict):
                        err("result: expected a mapping")
                    else:
                        for key in expected_result:
                            if key not in result:
                                err(f"result.{key}: missing")
                        for key in result:
                            if key not in expected_result:
                                err(f"result: unknown field {key!r}")
                        for key, expected in expected_result.items():
                            if key in result and result[key] != expected:
                                err(f"result.{key}: expected {expected!r}, got {result[key]!r}")

    return errors
