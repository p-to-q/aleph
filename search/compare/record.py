"""Comparison records and readable-side artifacts (pure standard library).

A comparison record binds, per target, the raw-side receipt (an
``aleph-miniprompt-receipt/0.1.0`` document verified by its own fail-closed
verifier) and the readable-side artifact (``aleph-comparison-readable/0.1.0``)
by digest-only references, records the frozen declared configuration and the
measured wall-clock, re-checks the cross-side identity assertions, and
derives the declared findings. ``verify_comparison`` re-derives everything
derivable without MLX, the model, or the network: canonical digests, the raw
receipt's policy replay (via the MiniPrompt verifier), the readable
evaluation ledger, the staircase derivation, the copy-annotation proxies, and
the declared selection rules.

Declared findings (fixed by the schema version):

- ``rawFound``: the raw receipt's own scan result (acquisition / free-token
  count / the recorded whole-prompt token count, declared scaffold tokens
  included); an acquisition is exact teacher-forced all-match with a matched
  greedy continuation recorded in the receipt.
- ``readableFound``: the minimum-length non-explicit point with
  ``epsilon <= tau`` (ties: lower epsilon, then earlier point), or null.
- ``readableBest``: the minimum-epsilon non-explicit point regardless of tau.
- ``readableExactMinLength``: minimum length among non-explicit points whose
  output equals the target string (after stripping), or null.
- ``explicitBaseline``: the tagged explicit-reconstruction point (the copy
  baseline), never a found readable coordinate.

Copy/leakage annotation on readable evaluations is recorded as ratios
(``promptContainsTargetText``, ``promptTargetTrigramContainment``), never as
a leakage verdict. Raw coordinates declare no leakage field: free-token IDs
are the ground truth and decoded text is a declared rendering.
"""

from __future__ import annotations

import math
import re
from pathlib import Path
from typing import List, Optional

from search.engine.canonical import digest, is_digest
from search.miniprompt.config import loads_strict
from search.miniprompt.receipts import verify_receipt

from .config import READABLE_SCHEMA, RECORD_SCHEMA, ComparisonConfig, config_from_canonical

TOOL = {"name": "search/compare", "version": "0.1.0"}

# A completed run may cross the declared envelope by one operation boundary
# plus process teardown; the slack is declared, recorded wall-clocks are
# checked against envelope + slack, and runs that pause at the boundary are
# not archived.
ENVELOPE_SLACK_SECONDS = 60

# |(1 - similarity) - epsilon| bound for separately rounded pairs (the same
# tolerance the frontier receipts use).
EPSILON_TOLERANCE = 1.2e-4

METRIC_SECONDARY = {
    "kind": "char_trigram_overlap",
    "formula": "lowercased char-3-gram sets, Jaccard |intersection|/|union|",
}

_CREATED_AT = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
_RUN_ID = re.compile(r"^[a-z0-9][a-z0-9-]*$")


class ComparisonError(RuntimeError):
    """A side artifact or cross-check violates the declared comparison contract."""


def _is_int(value) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _is_finite_number(value) -> bool:
    return (
        not isinstance(value, bool)
        and isinstance(value, (int, float))
        and math.isfinite(float(value))
    )


def _is_non_negative_zero(value) -> bool:
    """True when ``value`` is not negative zero (``-0.0`` normalizes out)."""
    return not (isinstance(value, float) and value == 0.0 and math.copysign(1.0, value) < 0)


def _char_trigrams(text: str):
    lowered = text.lower()
    return {lowered[i : i + 3] for i in range(max(0, len(lowered) - 2))}


def char_trigram_similarity(a: str, b: str) -> float:
    """The declared char-trigram Jaccard similarity (aleph_search ngram branch)."""
    grams_a, grams_b = _char_trigrams(a), _char_trigrams(b)
    return len(grams_a & grams_b) / len(grams_a | grams_b) if grams_a and grams_b else 0.0


def _normalize_text(text: str) -> str:
    return " ".join(text.lower().split())


def prompt_contains_target_text(prompt: str, target: str) -> bool:
    """Declared copy proxy: the normalized target text appears in the normalized prompt."""
    target_norm = _normalize_text(target)
    return bool(target_norm) and target_norm in _normalize_text(prompt)


def target_trigram_containment(prompt: str, target: str) -> float:
    """Declared copy proxy: fraction of the target's char-3-grams present in the prompt."""
    target_grams = _char_trigrams(target)
    if not target_grams:
        return 0.0
    return len(target_grams & _char_trigrams(prompt)) / len(target_grams)


def stability_scalar(similarities: List[float]) -> float:
    """The declared stability statistic over recorded (rounded) similarities."""
    if len(similarities) < 2:
        return 1.0
    import statistics

    spread = statistics.pstdev([float(value) for value in similarities])
    return round(max(0.0, 1.0 - min(1.0, spread * 4)), 3)


def _observed_point_key(point: dict):
    """A total, input-order-independent tie-break over one observed point."""
    import json

    return (
        point["epsilon"],
        str(point.get("prompt") or ""),
        str(point.get("output") or ""),
        json.dumps(point, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str),
    )


def derive_kept_indices(points: List[dict]) -> List[int]:
    """Independent mirror of ``observed_length_distortion_frontier`` (kept indices).

    Same semantics as the shipped selector in ``search/aleph_search.py``: among
    non-explicit points, one deterministic best per observed length (minimum
    key), then the strictly-improving staircase by ``(length, key)``; the
    explicit-reconstruction baseline is appended when not already kept.
    """
    for index, point in enumerate(points):
        length = point.get("length")
        if not _is_int(length) or length < 0:
            raise ComparisonError(f"points[{index}].length must be a non-negative integer")
        epsilon = point.get("epsilon")
        if (
            isinstance(epsilon, bool)
            or not isinstance(epsilon, (int, float))
            or not math.isfinite(float(epsilon))
            or epsilon < 0
        ):
            raise ComparisonError(f"points[{index}].epsilon must be a finite non-negative number")

    explicit = [i for i, p in enumerate(points) if p.get("role") == "explicit_reconstruction"]
    candidates = [i for i, p in enumerate(points) if p.get("role") != "explicit_reconstruction"]

    by_length = {}
    for i in candidates:
        j = by_length.get(points[i]["length"])
        if j is None or _observed_point_key(points[i]) < _observed_point_key(points[j]):
            by_length[points[i]["length"]] = i

    kept: List[int] = []
    best_epsilon = math.inf
    for i in sorted(by_length.values(), key=lambda k: (points[k]["length"], _observed_point_key(points[k]))):
        if points[i]["epsilon"] < best_epsilon:
            kept.append(i)
            best_epsilon = points[i]["epsilon"]

    if explicit:
        baseline = min(explicit, key=lambda k: (points[k]["length"], _observed_point_key(points[k])))
        if not any(points[baseline] == points[j] for j in kept):
            kept.append(baseline)
    return kept


def readable_findings(points: List[dict], tau: float) -> dict:
    """The declared selection rules over recorded readable points."""
    candidates = [i for i, p in enumerate(points) if p.get("role") != "explicit_reconstruction"]
    explicit = [i for i, p in enumerate(points) if p.get("role") == "explicit_reconstruction"]

    found: Optional[dict] = None
    eligible = [i for i in candidates if points[i]["epsilon"] <= tau]
    if eligible:
        i = min(eligible, key=lambda k: (points[k]["length"], points[k]["epsilon"], k))
        found = {
            "pointIndex": i,
            "length": points[i]["length"],
            "epsilon": points[i]["epsilon"],
            "similarity": points[i]["similarity"],
            "prompt": points[i]["prompt"],
            "outputEqualsTarget": points[i].get("outputEqualsTarget"),
        }

    best: Optional[dict] = None
    if candidates:
        i = min(candidates, key=lambda k: (points[k]["epsilon"], points[k]["length"], k))
        best = {
            "pointIndex": i,
            "length": points[i]["length"],
            "epsilon": points[i]["epsilon"],
            "similarity": points[i]["similarity"],
        }

    exact_min: Optional[int] = None
    exacts = [i for i in candidates if points[i].get("outputEqualsTarget") is True]
    if exacts:
        exact_min = min(points[i]["length"] for i in exacts)

    baseline: Optional[dict] = None
    if explicit:
        i = min(explicit, key=lambda k: (points[k]["length"], k))
        baseline = {
            "pointIndex": i,
            "length": points[i]["length"],
            "epsilon": points[i]["epsilon"],
        }

    return {
        "readableFound": found,
        "readableBest": best,
        "readableExactMinLength": exact_min,
        "explicitBaseline": baseline,
    }


def _recorded_whole_prompt_tokens(receipt: dict, n_free: int) -> int:
    """The acquisition's recorded whole-prompt count, cross-checked.

    Every attempt records ``wholePromptTokens`` as
    ``|prefix| + nFree + |mid| + |target|`` (the declared scaffold accounting),
    so a scaffolded run counts its scaffold tokens as well. The summary adopts
    that recorded count instead of re-deriving ``nFree + |target|`` — a
    derivation that is only the empty-scaffold value — and re-derives the count
    from the receipt's own scaffold block and target count so that a
    disagreement fails closed instead of one side silently winning.
    """
    attempts = receipt.get("attempts")
    if not isinstance(attempts, list) or not attempts:
        raise ComparisonError("raw receipt records no attempts")
    recorded = set()
    for attempt in attempts:
        if not isinstance(attempt, dict):
            raise ComparisonError("raw receipt records a non-mapping attempt")
        if attempt.get("acquired") is True and attempt.get("nFree") == n_free:
            recorded.add(attempt.get("wholePromptTokens"))
    if not recorded:
        raise ComparisonError("raw receipt records no acquired attempt at the smallest count")
    if len(recorded) != 1:
        raise ComparisonError("raw receipt records conflicting whole-prompt counts")
    whole = recorded.pop()
    if not _is_int(whole) or whole < 1:
        raise ComparisonError("raw receipt records a non-integer whole-prompt count")

    prefix_count = mid_count = 0
    scaffold = receipt.get("scaffold")
    if scaffold is not None:
        if not isinstance(scaffold, dict):
            raise ComparisonError("raw receipt scaffold block is not a mapping")
        prefix_ids = scaffold.get("prefixIds")
        mid_ids = scaffold.get("midIds")
        if not isinstance(prefix_ids, list) or not isinstance(mid_ids, list):
            raise ComparisonError("raw receipt scaffold token IDs are not lists")
        prefix_count, mid_count = len(prefix_ids), len(mid_ids)
    expected = prefix_count + n_free + mid_count + receipt["target"]["tokenCount"]
    if whole != expected:
        raise ComparisonError(
            "raw receipt whole-prompt count disagrees with its recorded scaffold and target"
        )
    return whole


def raw_side_summary(receipt: dict) -> dict:
    """Factual raw-side summary derived from a verified receipt.

    ``wholePromptTokens`` is the acquisition's recorded count adopted through
    ``_recorded_whole_prompt_tokens``; the empty-scaffold receipts in the
    archive record ``nFree + |target|`` exactly, so their summaries are
    unchanged, while a scaffolded receipt now reports its whole prompt.
    """
    result = receipt["result"]
    acquired = bool(result["success"])
    n_free = result["smallestAcquiredNFree"]
    if acquired and not _is_int(n_free):
        raise ComparisonError("raw receipt claims success without a smallest acquired count")
    return {
        "success": acquired,
        "numFreeTokens": result["numFreeTokens"],
        "stopReason": result["stopReason"],
        "attempts": result["attempts"],
        "smallestAcquiredNFree": n_free,
        "wholePromptTokens": _recorded_whole_prompt_tokens(receipt, n_free) if acquired else None,
    }


def raw_found(receipt: dict) -> dict:
    summary = raw_side_summary(receipt)
    return {
        "acquired": summary["success"],
        "nFree": summary["smallestAcquiredNFree"],
        "wholePromptTokens": summary["wholePromptTokens"],
        "fidelity": "exact_all_match_greedy_verified" if summary["success"] else None,
    }


def readable_side_summary(doc: dict, config: ComparisonConfig) -> dict:
    findings = readable_findings(doc["points"], config.reproduction_threshold_tau)
    found = findings["readableFound"]
    return {
        "stoppedBy": doc["stoppedBy"],
        "evaluations": len(doc["evaluations"]),
        "points": len(doc["points"]),
        "bestEpsilon": findings["readableBest"]["epsilon"] if findings["readableBest"] else None,
        "foundLengthUnderTau": found["length"] if found else None,
    }


def load_json_strict(path) -> object:
    """Read JSON fail-closed: duplicate object keys are rejected."""
    return loads_strict(Path(path).read_text(encoding="utf-8"))


def _resolve_ref(base_dir, ref: str) -> Path:
    """Resolve a record-internal relative reference, failing closed on escapes."""
    if not isinstance(ref, str) or not ref:
        raise ComparisonError("reference must be a non-empty string")
    relative = Path(ref)
    if relative.is_absolute() or ".." in relative.parts:
        raise ComparisonError(f"reference escapes the comparison directory: {ref!r}")
    base = Path(base_dir).resolve()
    resolved = (base / relative).resolve()
    if resolved != base and base not in resolved.parents:
        raise ComparisonError(f"reference escapes the comparison directory: {ref!r}")
    return resolved


def _cross_checks(config, spec, receipt, doc, wc_raw, wc_read):
    """Derive the cross-side identity assertions (values recorded and re-checked).

    Wall clocks are required finite numbers: the raw side is the sum of the
    receipt's recorded trajectory seconds, the readable side is the artifact's
    recorded ``wallClockSeconds``; both must fit the shared envelope plus the
    declared one-operation slack. The readable procedure settings must equal
    the declared ladder settings (the artifact records the descending
    execution order of the declared budgets).
    """
    checks = {
        "modelIdentityEqual": (
            receipt["model"]["repo"] == config.repo
            and receipt["model"]["revision"] == config.revision
            and receipt["model"]["weightsDigest"] == config.weights_digest
            and doc["model"]["repo"] == config.repo
            and doc["model"]["revision"] == config.revision
            and doc["model"]["weightsDigest"] == config.weights_digest
        ),
        "targetTextEqual": (
            receipt["config"]["target"] == spec.text
            and doc["target"]["text"] == spec.text
        ),
        "targetKeyMatches": doc["target"]["key"] == spec.key,
        "targetIdsEqual": receipt["target"]["tokenIds"] == doc["target"]["tokenIds"],
        "rawConfigDigestFrozen": receipt["configDigest"] == spec.raw_config_digest,
        "readableConfigDigestMatches": doc["configDigest"] == config.digest,
        "readableInstanceMatches": doc["instance"] == config.label,
        "readableComplete": doc["stoppedBy"] == "complete" and doc["result"]["complete"] is True,
        "readableSettingsMatch": (
            doc["procedure"]["budgets"] == sorted(config.readable.budgets, reverse=True)
            and doc["procedure"]["candidatesPerBudget"] == config.readable.candidates_per_budget
            and doc["procedure"]["refineSteps"] == config.readable.refine_steps
            and doc["procedure"]["stabilityRuns"] == config.readable.stability_runs
            and doc["procedure"]["stabilityTemperature"] == config.readable.stability_temperature
            and doc["procedure"]["proposerSeed"] == config.readable.proposer_seed
            and doc["procedure"]["explicitWrapper"] == config.explicit_wrapper
            and doc["metric"]["kind"] == config.readable.metric_kind
            and doc["metric"]["model"] == config.readable.metric_model
        ),
        "rawWallClockWithinEnvelope": float(wc_raw) <= config.envelope_seconds + ENVELOPE_SLACK_SECONDS,
        "readableWallClockWithinEnvelope": float(wc_read) <= config.envelope_seconds + ENVELOPE_SLACK_SECONDS,
    }
    return checks


def raw_wall_clock_seconds(receipt) -> float:
    """The declared raw-side wall clock: the receipt's recorded trajectory seconds."""
    total = 0.0
    for attempt in receipt["attempts"]:
        for step in attempt["trajectory"]:
            total += float(step["seconds"])
    return total


def build_comparison_record(*, config, targets, created_at, base_dir) -> dict:
    """Assemble a comparison record, failing closed on any violation.

    ``targets`` is a list of ``{"key", "raw": {"receipt", "wallClockSeconds"},
    "readable": {"doc", "wallClockSeconds"}}`` payloads in declared order; the
    builder validates both sides with their own verifiers, enforces the
    cross-checks, and derives the findings before anything is written.
    """
    if not isinstance(created_at, str) or not _CREATED_AT.match(created_at):
        raise ComparisonError("createdAt must be an RFC 3339 UTC second-precision timestamp")
    if not isinstance(targets, list) or [payload.get("key") for payload in targets] != [
        spec.key for spec in config.targets
    ]:
        raise ComparisonError("target payloads must match the declared config order exactly")

    blocks = []
    for spec, payload in zip(config.targets, targets):
        receipt = payload["raw"]["receipt"]
        doc = payload["readable"]["doc"]
        wc_raw = payload["raw"].get("wallClockSeconds")
        wc_read = payload["readable"].get("wallClockSeconds")

        errors = verify_receipt(receipt)
        if errors:
            raise ComparisonError(f"{spec.key}: raw receipt failed verification: {errors[:3]}")
        errors = verify_readable(doc)
        if errors:
            raise ComparisonError(f"{spec.key}: readable artifact failed verification: {errors[:3]}")
        for side, wall_clock in (("raw", wc_raw), ("readable", wc_read)):
            if wall_clock is None or not _is_finite_number(wall_clock) or float(wall_clock) < 0:
                raise ComparisonError(f"{spec.key}: {side} wallClockSeconds must be a finite number >= 0")

        checks = _cross_checks(config, spec, receipt, doc, wc_raw, wc_read)
        failed = sorted(key for key, value in checks.items() if value is False)
        if failed:
            raise ComparisonError(f"{spec.key}: cross-checks failed: {', '.join(failed)}")

        cli_output_ref = f"targets/{spec.key}/raw/cli-output.txt"
        if not (Path(base_dir) / cli_output_ref).is_file():
            cli_output_ref = None

        findings = dict(readable_findings(doc["points"], config.reproduction_threshold_tau))
        findings["rawFound"] = raw_found(receipt)
        ordered = {
            "rawFound": findings["rawFound"],
            "readableFound": findings["readableFound"],
            "readableBest": findings["readableBest"],
            "readableExactMinLength": findings["readableExactMinLength"],
            "explicitBaseline": findings["explicitBaseline"],
        }
        blocks.append(
            {
                "key": spec.key,
                "text": spec.text,
                "targetDigest": digest(spec.text),
                "raw": {
                    "view": "raw",
                    "receiptRef": f"targets/{spec.key}/raw/receipt.json",
                    "cliOutputRef": cli_output_ref,
                    "receiptDigest": receipt["receiptDigest"],
                    "configDigest": receipt["configDigest"],
                    "wallClockSeconds": (None if wc_raw is None else round(float(wc_raw), 1)),
                    "summary": raw_side_summary(receipt),
                },
                "readable": {
                    "view": "readable",
                    "artifactRef": f"targets/{spec.key}/readable.json",
                    "artifactDigest": digest(doc),
                    "configDigest": doc["configDigest"],
                    "wallClockSeconds": (None if wc_read is None else round(float(wc_read), 1)),
                    "summary": readable_side_summary(doc, config),
                },
                "crossChecks": checks,
                "findings": ordered,
            }
        )

    totals = {
        "targets": len(blocks),
        "rawAcquired": sum(1 for block in blocks if block["findings"]["rawFound"]["acquired"]),
        "readableFoundUnderTau": sum(
            1 for block in blocks if block["findings"]["readableFound"] is not None
        ),
    }
    body = {
        "schema": RECORD_SCHEMA,
        "tool": TOOL,
        "createdAt": created_at,
        "config": config.to_canonical(),
        "configDigest": config.digest,
        "targets": blocks,
        "totals": totals,
    }
    record = dict(body)
    record["receiptDigest"] = digest(body)
    return record


def verify_readable(doc) -> List[str]:
    """Fail-closed verification of one readable-side artifact (no MLX, no network)."""
    errors: List[str] = []

    def err(message: str) -> None:
        errors.append(message)

    if not isinstance(doc, dict):
        return ["readable: expected a JSON object"]
    required = (
        "schema", "tool", "createdAt", "instance", "configDigest", "target", "model",
        "metric", "procedure", "environment", "startedAt", "stoppedAt",
        "wallClockSeconds", "stoppedBy", "evaluations", "points", "result",
    )
    unknown = sorted(key for key in doc if key not in required)
    missing = sorted(key for key in required if key not in doc)
    for key in unknown:
        err(f"readable: unknown field {key!r}")
    for key in missing:
        err(f"readable: missing field {key!r}")
    if unknown or missing:
        return errors

    if doc["schema"] != READABLE_SCHEMA:
        err(f"readable.schema: expected {READABLE_SCHEMA!r}, got {doc['schema']!r}")
    if doc["tool"] != TOOL:
        err("readable.tool: does not match the declaring tool")
    for field in ("createdAt", "startedAt", "stoppedAt"):
        value = doc[field]
        if not isinstance(value, str) or not _CREATED_AT.match(value):
            err(f"readable.{field}: expected an RFC 3339 UTC second-precision timestamp")
    if not isinstance(doc["instance"], str) or not _RUN_ID.match(doc["instance"]):
        err("readable.instance: expected a run identifier")
    if not is_digest(doc["configDigest"]):
        err("readable.configDigest: not a sha256 digest")
    if doc["stoppedBy"] != "complete":
        err("readable.stoppedBy: expected 'complete' (partial runs are never archived)")

    target = doc["target"]
    token_count: Optional[int] = None
    if not isinstance(target, dict):
        err("readable.target: expected a mapping")
    else:
        for key in sorted(set(target) - {"key", "text", "tokenIds", "tokenCount", "rendering"}):
            err(f"readable.target: unknown field {key!r}")
        for key in ("key", "text"):
            value = target.get(key)
            if not isinstance(value, str) or not value:
                err(f"readable.target.{key}: expected a non-empty string")
        token_ids = target.get("tokenIds")
        if not isinstance(token_ids, list) or not token_ids or any(
            not _is_int(token) or token < 0 for token in token_ids
        ):
            err("readable.target.tokenIds: expected a non-empty list of non-negative integers")
        else:
            token_count = len(token_ids)
            if target.get("tokenCount") != token_count:
                err("readable.target.tokenCount: does not match tokenIds")
        rendering = target.get("rendering")
        if not isinstance(rendering, list) or any(not isinstance(item, str) for item in rendering):
            err("readable.target.rendering: expected a list of strings")
        elif token_count is not None and len(rendering) != token_count:
            err("readable.target.rendering: length does not match tokenIds")

    model = doc["model"]
    if not isinstance(model, dict):
        err("readable.model: expected a mapping")
    else:
        for key in sorted(set(model) - {"repo", "revision", "weightsDigest", "vocabSize"}):
            err(f"readable.model: unknown field {key!r}")
        for key in ("repo", "revision", "weightsDigest"):
            value = model.get(key)
            if not isinstance(value, str) or not value:
                err(f"readable.model.{key}: expected a non-empty string")
        if not is_digest(model.get("weightsDigest")):
            err("readable.model.weightsDigest: not a sha256 digest")
        vocab = model.get("vocabSize")
        if not _is_int(vocab) or vocab < 1:
            err("readable.model.vocabSize: expected an integer >= 1")

    metric = doc["metric"]
    if not isinstance(metric, dict):
        err("readable.metric: expected a mapping")
    else:
        for key in sorted(set(metric) - {"kind", "model", "secondary"}):
            err(f"readable.metric: unknown field {key!r}")
        if metric.get("kind") != "embedding_cosine":
            err("readable.metric.kind: expected 'embedding_cosine'")
        if not isinstance(metric.get("model"), str) or not metric.get("model"):
            err("readable.metric.model: expected a non-empty string")
        secondary = metric.get("secondary")
        if not isinstance(secondary, dict) or secondary.get("kind") != METRIC_SECONDARY["kind"] or secondary.get(
            "formula"
        ) != METRIC_SECONDARY["formula"]:
            err("readable.metric.secondary: does not match the declared secondary metric")

    procedure = doc["procedure"]
    procedure_budgets: Optional[list] = None
    candidates_per_budget: Optional[int] = None
    refine_steps: Optional[int] = None
    stability_runs: Optional[int] = None
    if not isinstance(procedure, dict):
        err("readable.procedure: expected a mapping")
    else:
        known = {
            "entrypoint", "budgets", "candidatesPerBudget", "refineSteps", "stabilityRuns",
            "stabilityTemperature", "proposerSeed", "generation", "proposeTemperature",
            "compressTemperature", "refineTemperature", "explicitWrapper", "rngSeeded",
            "declaredDifferences",
        }
        for key in sorted(set(procedure) - known):
            err(f"readable.procedure: unknown field {key!r}")
        if not isinstance(procedure.get("entrypoint"), str) or not procedure.get("entrypoint"):
            err("readable.procedure.entrypoint: expected a non-empty string")
        budgets = procedure.get("budgets")
        if (
            not isinstance(budgets, list)
            or not budgets
            or any(not _is_int(item) or item < 1 for item in budgets)
            or budgets != sorted(budgets, reverse=True)
            or len(set(budgets)) != len(budgets)
        ):
            err("readable.procedure.budgets: expected a descending list of unique integers >= 1")
        else:
            procedure_budgets = budgets
        for key, minimum in (
            ("candidatesPerBudget", 1),
            ("refineSteps", 0),
            ("stabilityRuns", 1),
        ):
            value = procedure.get(key)
            if not _is_int(value) or value < minimum:
                err(f"readable.procedure.{key}: expected an integer >= {minimum}")
            elif key == "candidatesPerBudget":
                candidates_per_budget = value
            elif key == "refineSteps":
                refine_steps = value
            else:
                stability_runs = value
        if not _is_finite_number(procedure.get("stabilityTemperature")):
            err("readable.procedure.stabilityTemperature: expected a finite number")
        seed = procedure.get("proposerSeed")
        if not _is_int(seed) or seed < 0:
            err("readable.procedure.proposerSeed: expected an integer >= 0")
        for key in ("proposeTemperature", "compressTemperature", "refineTemperature"):
            if not _is_finite_number(procedure.get(key)):
                err(f"readable.procedure.{key}: expected a finite number")
        generation = procedure.get("generation")
        if not isinstance(generation, dict):
            err("readable.procedure.generation: expected a mapping")
        else:
            for key in sorted(set(generation) - {"temperature", "maxOutNonExplicit", "maxOutExplicit", "template"}):
                err(f"readable.procedure.generation: unknown field {key!r}")
            if generation.get("temperature") != 0.0:
                err("readable.procedure.generation.temperature: expected 0.0")
            if not isinstance(generation.get("template"), str) or not generation.get("template"):
                err("readable.procedure.generation.template: expected a non-empty string")
            if token_count is not None:
                if generation.get("maxOutNonExplicit") != int(token_count * 1.6) + 32:
                    err("readable.procedure.generation.maxOutNonExplicit: does not match the declared formula")
                if generation.get("maxOutExplicit") != int(token_count * 1.4) + 32:
                    err("readable.procedure.generation.maxOutExplicit: does not match the declared formula")
        wrapper = procedure.get("explicitWrapper")
        if not isinstance(wrapper, str) or not wrapper:
            err("readable.procedure.explicitWrapper: expected a non-empty string")
        if procedure.get("rngSeeded") is not True:
            err("readable.procedure.rngSeeded: expected true")
        differences = procedure.get("declaredDifferences")
        if (
            not isinstance(differences, list)
            or not differences
            or any(not isinstance(item, str) or not item for item in differences)
        ):
            err("readable.procedure.declaredDifferences: expected a non-empty list of strings")

    environment = doc["environment"]
    if not isinstance(environment, dict):
        err("readable.environment: expected a mapping")
    else:
        for key in sorted(set(environment) - {"python", "mlx", "mlxLm", "sentenceTransformers", "platform"}):
            err(f"readable.environment: unknown field {key!r}")
        for key in ("python", "mlx", "mlxLm", "platform"):
            value = environment.get(key)
            if not isinstance(value, str) or not value:
                err(f"readable.environment.{key}: expected a non-empty string")
        sentence = environment.get("sentenceTransformers")
        if sentence is not None and (not isinstance(sentence, str) or not sentence):
            err("readable.environment.sentenceTransformers: expected a string or null")

    wall_clock = doc["wallClockSeconds"]
    if not _is_finite_number(wall_clock) or float(wall_clock) < 0:
        err("readable.wallClockSeconds: expected a finite number >= 0")

    target_text = target.get("text") if isinstance(target, dict) else None
    target_stripped = target_text.strip() if isinstance(target_text, str) else None

    evaluations = doc["evaluations"]
    if not isinstance(evaluations, list) or not evaluations:
        err("readable.evaluations: expected a non-empty list")
        evaluations = []
    valid_evaluations = True
    for position, evaluation in enumerate(evaluations):
        where = f"readable.evaluations[{position}]"
        if not isinstance(evaluation, dict):
            err(f"{where}: expected a mapping")
            valid_evaluations = False
            continue
        known = {
            "index", "phase", "budget", "prompt", "promptDigest", "output", "outputDigest",
            "similarity", "similarityNgram3", "outputEqualsTarget", "seconds",
            "promptContainsTargetText", "promptTargetTrigramContainment",
        }
        for key in sorted(set(evaluation) - known):
            err(f"{where}: unknown field {key!r}")
        if evaluation.get("index") != position:
            err(f"{where}.index: expected {position}")
        phase = evaluation.get("phase")
        if phase not in ("propose", "compress", "refine", "stability", "explicit"):
            err(f"{where}.phase: unexpected phase {phase!r}")
            valid_evaluations = False
        budget = evaluation.get("budget")
        if phase == "explicit":
            if budget is not None:
                err(f"{where}.budget: expected null for the explicit arm")
                valid_evaluations = False
        elif not _is_int(budget) or budget < 1:
            err(f"{where}.budget: expected an integer >= 1")
            valid_evaluations = False
        prompt = evaluation.get("prompt")
        if not isinstance(prompt, str) or not prompt:
            err(f"{where}.prompt: expected a non-empty string")
        else:
            try:
                if evaluation.get("promptDigest") != digest(prompt):
                    err(f"{where}.promptDigest: mismatch")
            except Exception as exc:  # noqa: BLE001 - fail closed on uncanonicalizable text
                err(f"{where}.promptDigest: not canonicalizable: {exc}")
        output = evaluation.get("output")
        if not isinstance(output, str):
            err(f"{where}.output: expected a string")
        else:
            try:
                if evaluation.get("outputDigest") != digest(output):
                    err(f"{where}.outputDigest: mismatch")
            except Exception as exc:  # noqa: BLE001
                err(f"{where}.outputDigest: not canonicalizable: {exc}")
        similarity = evaluation.get("similarity")
        if not _is_finite_number(similarity) or not 0.0 <= float(similarity) <= 1.0:
            err(f"{where}.similarity: expected a finite number in [0, 1]")
            valid_evaluations = False
        ngram = evaluation.get("similarityNgram3")
        if not _is_finite_number(ngram) or not 0.0 <= float(ngram) <= 1.0:
            err(f"{where}.similarityNgram3: expected a finite number in [0, 1]")
        elif isinstance(output, str) and isinstance(target_text, str):
            recomputed = char_trigram_similarity(output, target_text)
            if abs(float(ngram) - recomputed) > 1e-4:
                err(f"{where}.similarityNgram3: does not match the recorded output and target")
        equals = evaluation.get("outputEqualsTarget")
        if not isinstance(equals, bool) or (isinstance(output, str) and target_stripped is not None and equals != (output == target_stripped)):
            err(f"{where}.outputEqualsTarget: does not match the recorded output and target")
        seconds = evaluation.get("seconds")
        if not _is_finite_number(seconds) or float(seconds) < 0:
            err(f"{where}.seconds: expected a finite number >= 0")
        if isinstance(prompt, str) and isinstance(target_text, str):
            if evaluation.get("promptContainsTargetText") != prompt_contains_target_text(prompt, target_text):
                err(f"{where}.promptContainsTargetText: does not match the recorded strings")
            containment = evaluation.get("promptTargetTrigramContainment")
            recomputed_containment = target_trigram_containment(prompt, target_text)
            if not _is_finite_number(containment) or abs(float(containment) - recomputed_containment) > 1e-4:
                err(f"{where}.promptTargetTrigramContainment: does not match the recorded strings")

    points = doc["points"]
    if not isinstance(points, list) or not points:
        err("readable.points: expected a non-empty list")
        points = []
    for position, point in enumerate(points):
        where = f"readable.points[{position}]"
        if not isinstance(point, dict):
            err(f"{where}: expected a mapping")
            continue
        known = {
            "budget", "role", "evaluationIndex", "prompt", "promptDigest", "promptTokenIds",
            "length", "similarity", "epsilon", "output", "outputDigest", "outputEqualsTarget",
            "toktext", "toknll", "stabilitySimilarities", "stability", "kept",
        }
        for key in sorted(set(point) - known):
            err(f"{where}: unknown field {key!r}")
        role = point.get("role")
        budget = point.get("budget")
        if role == "explicit_reconstruction":
            if budget is not None:
                err(f"{where}.budget: expected null for the explicit point")
        elif role is not None:
            err(f"{where}.role: unexpected role {role!r}")
        elif not _is_int(budget) or budget < 1:
            err(f"{where}.budget: expected an integer >= 1")
        evaluation_index = point.get("evaluationIndex")
        if not _is_int(evaluation_index) or not 0 <= evaluation_index < len(evaluations):
            err(f"{where}.evaluationIndex: expected a valid evaluation index")
        prompt = point.get("prompt")
        if not isinstance(prompt, str) or not prompt:
            err(f"{where}.prompt: expected a non-empty string")
        else:
            try:
                if point.get("promptDigest") != digest(prompt):
                    err(f"{where}.promptDigest: mismatch")
            except Exception as exc:  # noqa: BLE001
                err(f"{where}.promptDigest: not canonicalizable: {exc}")
        token_ids = point.get("promptTokenIds")
        if not isinstance(token_ids, list) or any(not _is_int(token) or token < 0 for token in token_ids):
            err(f"{where}.promptTokenIds: expected a list of non-negative integers")
        length = point.get("length")
        if not _is_int(length) or length < 1:
            err(f"{where}.length: expected an integer >= 1")
        elif isinstance(token_ids, list) and length != len(token_ids):
            err(f"{where}.length: does not match promptTokenIds")
        output = point.get("output")
        if not isinstance(output, str):
            err(f"{where}.output: expected a string")
        else:
            try:
                if point.get("outputDigest") != digest(output):
                    err(f"{where}.outputDigest: mismatch")
            except Exception as exc:  # noqa: BLE001
                err(f"{where}.outputDigest: not canonicalizable: {exc}")
        similarity = point.get("similarity")
        epsilon = point.get("epsilon")
        if not _is_finite_number(similarity) or not 0.0 <= float(similarity) <= 1.0:
            err(f"{where}.similarity: expected a finite number in [0, 1]")
        if not _is_finite_number(epsilon) or float(epsilon) < 0:
            err(f"{where}.epsilon: expected a finite number >= 0")
        else:
            if not _is_non_negative_zero(epsilon):
                err(f"{where}.epsilon: negative zero is normalized out")
            if _is_finite_number(similarity) and abs((1.0 - float(similarity)) - float(epsilon)) > EPSILON_TOLERANCE:
                err(f"{where}: epsilon and similarity are inconsistent")
        equals = point.get("outputEqualsTarget")
        if not isinstance(equals, bool) or (
            isinstance(output, str)
            and target_stripped is not None
            and equals != (output == target_stripped)
        ):
            err(f"{where}.outputEqualsTarget: does not match the recorded output and target")
        if _is_int(evaluation_index) and 0 <= evaluation_index < len(evaluations):
            evaluation = evaluations[evaluation_index]
            if isinstance(evaluation, dict):
                if evaluation.get("prompt") != prompt:
                    err(f"{where}.evaluationIndex: does not point at an evaluation of this prompt")
                if evaluation.get("output") != output:
                    err(f"{where}: output does not match the linked evaluation")
                if evaluation.get("similarity") != similarity:
                    err(f"{where}: similarity does not match the linked evaluation")
                if evaluation.get("budget") != budget:
                    err(f"{where}: budget does not match the linked evaluation")
        toktext = point.get("toktext")
        toknll = point.get("toknll")
        if not isinstance(toktext, list) or any(not isinstance(token, str) for token in toktext):
            err(f"{where}.toktext: expected a list of strings")
        elif token_count is not None and len(toktext) != token_count:
            err(f"{where}.toktext: length does not match the target token count")
        if not isinstance(toknll, list) or any(not _is_finite_number(loss) for loss in toknll):
            err(f"{where}.toknll: expected a list of finite numbers")
        else:
            for loss in toknll:
                if not _is_non_negative_zero(loss):
                    err(f"{where}.toknll: negative zero is normalized out")
            if isinstance(toktext, list) and len(toknll) != len(toktext):
                err(f"{where}: toktext and toknll length mismatch")
        stability_similarities = point.get("stabilitySimilarities")
        if not isinstance(stability_similarities, list) or any(
            not _is_finite_number(value) or not 0.0 <= float(value) <= 1.0
            for value in stability_similarities
        ):
            err(f"{where}.stabilitySimilarities: expected a list of finite numbers in [0, 1]")
        stability = point.get("stability")
        if not _is_finite_number(stability) or not 0.0 <= float(stability) <= 1.0:
            err(f"{where}.stability: expected a finite number in [0, 1]")
        elif isinstance(stability_similarities, list) and all(
            _is_finite_number(value) for value in stability_similarities
        ):
            if stability != stability_scalar(stability_similarities):
                err(f"{where}.stability: does not match the recorded stability runs")
        if not isinstance(point.get("kept"), bool):
            err(f"{where}.kept: expected a boolean")

    # ---- derivation of points from the evaluation ledger ----
    if (
        valid_evaluations
        and isinstance(evaluations, list)
        and evaluations
        and procedure_budgets is not None
        and candidates_per_budget is not None
        and refine_steps is not None
        and stability_runs is not None
    ):
        counts = {}
        for evaluation in evaluations:
            if not isinstance(evaluation, dict):
                continue
            key = (evaluation.get("phase"), evaluation.get("budget"))
            counts[key] = counts.get(key, 0) + 1
        expected_sequence = []
        for position, budget in enumerate(procedure_budgets):
            proposes = counts.get(("propose", budget), 0)
            if not 1 <= proposes <= candidates_per_budget:
                err(f"readable.evaluations: propose count for budget {budget} is {proposes}")
            expected_sequence.extend([("propose", budget)] * proposes)
            if position > 0:
                expected_sequence.append(("compress", budget))
                if counts.get(("compress", budget), 0) != 1:
                    err(f"readable.evaluations: expected one compress evaluation for budget {budget}")
            for phase, expected in (("refine", refine_steps), ("stability", stability_runs)):
                if counts.get((phase, budget), 0) != expected:
                    err(
                        f"readable.evaluations: {phase} count for budget {budget} is "
                        f"{counts.get((phase, budget), 0)}, expected {expected}"
                    )
                expected_sequence.extend([(phase, budget)] * expected)
        expected_sequence.append(("explicit", None))
        if counts.get(("explicit", None), 0) != 1:
            err("readable.evaluations: expected exactly one explicit evaluation")
        if len(evaluations) == len(expected_sequence):
            for position, ((phase, budget), evaluation) in enumerate(zip(expected_sequence, evaluations)):
                if not isinstance(evaluation, dict):
                    continue
                if evaluation.get("phase") != phase or evaluation.get("budget") != budget:
                    err(f"readable.evaluations[{position}]: does not follow the declared search structure")
        else:
            err(
                f"readable.evaluations: {len(evaluations)} entries do not match the declared "
                f"search structure ({len(expected_sequence)})"
            )

        # points: one per budget, derived by first-strict-max + refinement.
        by_budget = {}
        for point in points:
            if not isinstance(point, dict) or point.get("role") == "explicit_reconstruction":
                continue
            by_budget.setdefault(point.get("budget"), []).append(point)
        if sorted(by_budget) != sorted(procedure_budgets):
            err("readable.points: budgets do not cover exactly the declared ladder")
        for budget in procedure_budgets:
            entries = by_budget.get(budget) or []
            if len(entries) != 1:
                err(f"readable.points: expected exactly one point for budget {budget}")
                continue
            point = entries[0]
            candidate_evaluations = [
                evaluation
                for evaluation in evaluations
                if isinstance(evaluation, dict)
                and evaluation.get("budget") == budget
                and evaluation.get("phase") in ("propose", "compress")
            ]
            best = None
            for evaluation in candidate_evaluations:
                if best is None or evaluation.get("similarity") > best.get("similarity"):
                    best = evaluation
            for evaluation in evaluations:
                if (
                    isinstance(evaluation, dict)
                    and evaluation.get("budget") == budget
                    and evaluation.get("phase") == "refine"
                ):
                    if best is not None and evaluation.get("similarity") > best.get("similarity"):
                        best = evaluation
            if best is None:
                err(f"readable.points: no evaluations to derive the point for budget {budget}")
                continue
            if point.get("prompt") != best.get("prompt") or point.get("similarity") != best.get("similarity"):
                err(f"readable.points: point for budget {budget} does not match its derivation")
            stability_values = [
                evaluation.get("similarity")
                for evaluation in evaluations
                if isinstance(evaluation, dict)
                and evaluation.get("phase") == "stability"
                and evaluation.get("budget") == budget
                and evaluation.get("prompt") == point.get("prompt")
            ]
            if stability_values != point.get("stabilitySimilarities"):
                err(f"readable.points: stability runs for budget {budget} do not match")

        explicit_points = [point for point in points if isinstance(point, dict) and point.get("role") == "explicit_reconstruction"]
        if len(explicit_points) != 1:
            err("readable.points: expected exactly one explicit-reconstruction point")
        elif len(evaluations) >= 1:
            explicit_point = explicit_points[0]
            wrapper = procedure.get("explicitWrapper")
            index = explicit_point.get("evaluationIndex")
            if _is_int(index) and 0 <= index < len(evaluations):
                evaluation = evaluations[index]
                if isinstance(evaluation, dict) and isinstance(wrapper, str) and isinstance(target_text, str):
                    if evaluation.get("phase") != "explicit" or evaluation.get("prompt") != wrapper + target_text:
                        err("readable.points: explicit point does not match the declared wrapper arm")

    # kept flags: independent re-derivation of the shipped staircase.
    if points and all(isinstance(point, dict) for point in points) and all(
        isinstance(point, dict) and isinstance(point.get("kept"), bool) for point in points
    ):
        try:
            stripped = [{key: value for key, value in point.items() if key != "kept"} for point in points]
            derived = set(derive_kept_indices(stripped))
        except ComparisonError as exc:
            err(f"readable.points: kept-flag derivation failed: {exc}")
        else:
            recorded = {i for i, point in enumerate(points) if point.get("kept") is True}
            if derived != recorded:
                err("readable.points: kept flags do not match the declared staircase derivation")

    result = doc["result"]
    if not isinstance(result, dict):
        err("readable.result: expected a mapping")
    else:
        expected_result = {
            "complete": True,
            "evaluations": len(evaluations) if isinstance(evaluations, list) else None,
            "points": len(points) if isinstance(points, list) else None,
        }
        for key in expected_result:
            if key not in result:
                err(f"readable.result.{key}: missing")
        for key in result:
            if key not in expected_result:
                err(f"readable.result: unknown field {key!r}")
        for key, expected in expected_result.items():
            if key in result and result[key] != expected:
                err(f"readable.result.{key}: expected {expected!r}, got {result[key]!r}")

    return errors


def _verify_comparison_block(err, config, spec, block, base_dir) -> Optional[dict]:
    """Check one record target block; returns recomputed findings when possible."""
    block_fields = ("key", "text", "targetDigest", "raw", "readable", "crossChecks", "findings")
    where = f"targets[{spec.key}]"
    if not isinstance(block, dict):
        err(f"{where}: expected a mapping")
        return None
    for key in sorted(key for key in block if key not in block_fields):
        err(f"{where}: unknown field {key!r}")
    for key in sorted(key for key in block_fields if key not in block):
        err(f"{where}: missing field {key!r}")
    if not all(key in block for key in block_fields):
        return None

    if block["text"] != spec.text:
        err(f"{where}.text: differs from the declared target")
    try:
        target_digest = digest(spec.text)
    except Exception as exc:  # noqa: BLE001 - fail closed on uncanonicalizable text
        err(f"{where}.targetDigest: target is not canonicalizable: {exc}")
        target_digest = None
    if target_digest is not None and block["targetDigest"] != target_digest:
        err(f"{where}.targetDigest: does not match the declared target text")

    receipt = None
    wc_raw = None
    raw_block = block["raw"]
    raw_fields = ("view", "receiptRef", "cliOutputRef", "receiptDigest", "configDigest", "wallClockSeconds", "summary")
    if not isinstance(raw_block, dict):
        err(f"{where}.raw: expected a mapping")
        raw_block = None
    else:
        for key in sorted(key for key in raw_block if key not in raw_fields):
            err(f"{where}.raw: unknown field {key!r}")
        for key in sorted(key for key in raw_fields if key not in raw_block):
            err(f"{where}.raw: missing field {key!r}")
        if not all(key in raw_block for key in raw_fields):
            raw_block = None
    if raw_block is not None:
        if raw_block["view"] != "raw":
            err(f"{where}.raw.view: expected 'raw'")
        receipt_ref = f"targets/{spec.key}/raw/receipt.json"
        if raw_block["receiptRef"] != receipt_ref:
            err(f"{where}.raw.receiptRef: expected {receipt_ref!r}")
        cli_ref = raw_block["cliOutputRef"]
        if cli_ref is not None:
            expected_cli = f"targets/{spec.key}/raw/cli-output.txt"
            if cli_ref != expected_cli:
                err(f"{where}.raw.cliOutputRef: expected {expected_cli!r} or null")
            else:
                try:
                    cli_exists = _resolve_ref(base_dir, cli_ref).is_file()
                except ComparisonError as exc:
                    err(f"{where}.raw.cliOutputRef: {exc}")
                else:
                    if not cli_exists:
                        err(f"{where}.raw.cliOutputRef: file missing")
        try:
            receipt = load_json_strict(_resolve_ref(base_dir, raw_block["receiptRef"]))
        except Exception as exc:  # noqa: BLE001 - unreadable or invalid artifact
            err(f"{where}.raw: receipt unreadable ({exc})")
        else:
            for message in verify_receipt(receipt):
                err(f"{where}.raw receipt: {message}")
            if receipt.get("receiptDigest") != raw_block["receiptDigest"]:
                err(f"{where}.raw.receiptDigest: does not match the receipt")
            if receipt.get("configDigest") != spec.raw_config_digest:
                err(f"{where}.raw receipt: configDigest differs from the declared preset digest")
            if raw_block["configDigest"] != spec.raw_config_digest:
                err(f"{where}.raw.configDigest: expected the declared preset digest")
            try:
                wc_raw = round(raw_wall_clock_seconds(receipt), 1)
            except Exception as exc:  # noqa: BLE001 - fail closed on malformed trajectories
                err(f"{where}.raw: trajectory seconds unreadable ({exc})")
                wc_raw = None
            if wc_raw is not None and raw_block["wallClockSeconds"] != wc_raw:
                err(f"{where}.raw.wallClockSeconds: expected {wc_raw!r}")
            try:
                expected_summary = raw_side_summary(receipt)
            except Exception as exc:  # noqa: BLE001
                err(f"{where}.raw.summary: cannot be derived ({exc})")
            else:
                if raw_block["summary"] != expected_summary:
                    err(f"{where}.raw.summary: does not match the derived summary")

    doc = None
    wc_read = None
    readable_block = block["readable"]
    readable_fields = ("view", "artifactRef", "artifactDigest", "configDigest", "wallClockSeconds", "summary")
    if not isinstance(readable_block, dict):
        err(f"{where}.readable: expected a mapping")
        readable_block = None
    else:
        for key in sorted(key for key in readable_block if key not in readable_fields):
            err(f"{where}.readable: unknown field {key!r}")
        for key in sorted(key for key in readable_fields if key not in readable_block):
            err(f"{where}.readable: missing field {key!r}")
        if not all(key in readable_block for key in readable_fields):
            readable_block = None
    if readable_block is not None:
        if readable_block["view"] != "readable":
            err(f"{where}.readable.view: expected 'readable'")
        artifact_ref = f"targets/{spec.key}/readable.json"
        if readable_block["artifactRef"] != artifact_ref:
            err(f"{where}.readable.artifactRef: expected {artifact_ref!r}")
        try:
            doc = load_json_strict(_resolve_ref(base_dir, readable_block["artifactRef"]))
        except Exception as exc:  # noqa: BLE001
            err(f"{where}.readable: artifact unreadable ({exc})")
        else:
            for message in verify_readable(doc):
                err(f"{where}.readable artifact: {message}")
            try:
                recomputed_digest = digest(doc)
            except Exception as exc:  # noqa: BLE001
                err(f"{where}.readable.artifactDigest: artifact is not canonicalizable: {exc}")
                recomputed_digest = None
            if recomputed_digest is not None and readable_block["artifactDigest"] != recomputed_digest:
                err(f"{where}.readable.artifactDigest: does not match the artifact")
            if readable_block["configDigest"] != config.digest:
                err(f"{where}.readable.configDigest: expected the declared config digest")
            wall = doc.get("wallClockSeconds")
            if not _is_finite_number(wall) or float(wall) < 0:
                err(f"{where}.readable: artifact wallClockSeconds is invalid")
            else:
                wc_read = round(float(wall), 1)
                if readable_block["wallClockSeconds"] != wc_read:
                    err(f"{where}.readable.wallClockSeconds: expected {wc_read!r}")
            try:
                expected_summary = readable_side_summary(doc, config)
            except Exception as exc:  # noqa: BLE001
                err(f"{where}.readable.summary: cannot be derived ({exc})")
            else:
                if readable_block["summary"] != expected_summary:
                    err(f"{where}.readable.summary: does not match the derived summary")

    if receipt is not None and doc is not None and wc_raw is not None and wc_read is not None:
        try:
            expected_checks = _cross_checks(config, spec, receipt, doc, wc_raw, wc_read)
        except Exception as exc:  # noqa: BLE001 - fail closed on structurally unusable artifacts
            err(f"{where}.crossChecks: cannot be recomputed ({exc})")
            expected_checks = None
        else:
            recorded_checks = block["crossChecks"]
            if recorded_checks != expected_checks:
                err(f"{where}.crossChecks: do not match the recomputation")
            else:
                for key, value in sorted(recorded_checks.items()):
                    if value is not True:
                        err(f"{where}.crossChecks.{key}: recorded {value!r}")

    expected_findings: Optional[dict] = None
    if receipt is not None and doc is not None:
        try:
            expected_findings = dict(readable_findings(doc["points"], config.reproduction_threshold_tau))
            expected_findings["rawFound"] = raw_found(receipt)
        except Exception as exc:  # noqa: BLE001
            err(f"{where}.findings: cannot be recomputed ({exc})")
            expected_findings = None
        else:
            if block["findings"] != expected_findings:
                err(f"{where}.findings: do not match the recomputation")
    return expected_findings


def verify_comparison(record, base_dir) -> List[str]:
    """Fail-closed verification of one comparison record and its side artifacts.

    Re-derives everything derivable without MLX, the model, or the network:
    both side artifacts are re-verified by their own fail-closed verifiers, the
    cross-side checks and findings are recomputed, all declared digests are
    recomputed, and every recorded value must equal its recomputation. Returns
    error strings (empty means verified).
    """
    errors: List[str] = []

    def err(message: str) -> None:
        errors.append(message)

    if not isinstance(record, dict):
        return ["record: expected a JSON object"]

    required = ("schema", "tool", "createdAt", "config", "configDigest", "targets", "totals", "receiptDigest")
    for key in sorted(key for key in record if key not in required):
        err(f"record: unknown field {key!r}")
    for key in sorted(key for key in required if key not in record):
        err(f"record: missing field {key!r}")
    if set(record) != set(required):
        return errors

    if record["schema"] != RECORD_SCHEMA:
        err(f"record.schema: expected {RECORD_SCHEMA!r}, got {record['schema']!r}")
    if record["tool"] != TOOL:
        err("record.tool: does not match the declaring tool")
    if not isinstance(record["createdAt"], str) or not _CREATED_AT.match(record["createdAt"]):
        err("record.createdAt: expected an RFC 3339 UTC second-precision timestamp")

    config = None
    try:
        config = config_from_canonical(record["config"])
    except Exception as exc:  # noqa: BLE001 - fail closed on any parse failure
        err(f"record.config: {exc}")
    if config is not None and record["configDigest"] != config.digest:
        err("record.configDigest: does not match the embedded config digest")
    if not is_digest(record["configDigest"]):
        err("record.configDigest: not a sha256 digest")

    if not is_digest(record["receiptDigest"]):
        err("record.receiptDigest: not a sha256 digest")
    else:
        body = {key: value for key, value in record.items() if key != "receiptDigest"}
        try:
            recomputed = digest(body)
        except Exception as exc:  # noqa: BLE001 - fail closed on uncanonicalizable bodies
            err(f"record.receiptDigest: record body is not canonicalizable: {exc}")
        else:
            if recomputed != record["receiptDigest"]:
                err("record.receiptDigest: does not match the record body digest")

    if config is None:
        return errors

    blocks = record["targets"]
    if (
        not isinstance(blocks, list)
        or [block.get("key") if isinstance(block, dict) else None for block in blocks]
        != [spec.key for spec in config.targets]
    ):
        err("record.targets: expected one block per declared target, in declared order")
        return errors

    totals = {"targets": len(blocks), "rawAcquired": 0, "readableFoundUnderTau": 0}
    for spec, block in zip(config.targets, blocks):
        findings = _verify_comparison_block(err, config, spec, block, base_dir)
        if findings is not None:
            if findings.get("rawFound", {}).get("acquired") is True:
                totals["rawAcquired"] += 1
            if findings.get("readableFound") is not None:
                totals["readableFoundUnderTau"] += 1

    if record["totals"] != totals:
        err(f"record.totals: expected {totals!r}, got {record['totals']!r}")

    return errors
