#!/usr/bin/env python3
"""Regenerate the public MLX frontier from actual evaluations, with receipts.

The public artifact ``web/public/aleph-frontier.json`` predates the PR #100
frontier-mutation repair (commit ``c2cbda0``) and is not valid performance
evidence until every displayed point is linked to an actual evaluation and the
artifact is regenerated with receipts (``docs/research/research-process.md``,
"Current gaps"; ``docs/open-questions.md``, "Search strategy"). This tool
re-measures every displayed coordinate under one declared procedure, writes
per-point receipts, and emits a fresh measured-targets file:

    python search/frontier_receipts.py run
    python search/finalize.py --no-merge
    python search/add_pitch.py
    node scripts/check-public-frontier.mjs

Design:

- A receipt is the evaluation record for one measured point: target digest,
  prompt, model repo + revision + weights digest, metric description, procedure
  constants, the raw outputs (generated text, token trace, stability run
  similarities), the observed coordinates, and the historical values it
  replaces. ``receiptDigest`` is the ``aleph-canonical/0.2.0`` digest of the
  receipt body (everything except ``receiptDigest``) and is recomputed
  independently by the Node checker through ``scripts/aleph-canonical.mjs``.
- A displayed artifact point carries ``receiptDigest``, so artifact and
  receipts are linked by digest, not by position.
- Prompt coordinates are carried over unmodified from the historical export;
  only the evaluation is fresh. Historical numbers are preserved per receipt
  under ``supersedes`` for audit and are never reused as evidence.
- ``run`` is resumable: receipts are checkpointed after every measured point
  and re-running skips points that already have a receipt (unless ``--force``).
- ``verify`` re-checks the checked-in artifact against the checked-in receipts
  and does not import MLX.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import platform
import re
import statistics
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(HERE))

from search.engine.canonical import digest, is_digest  # noqa: E402
from aleph_search import (  # noqa: E402
    Metric,
    Theta,
    _observed_point_key,
    observed_length_distortion_frontier,
)
from targets import TARGETS  # noqa: E402

SCHEMA_VERSION = "aleph-frontier-receipts/0.1.0"
TOOL_VERSION = "0.1.0"
DEFAULT_ARTIFACT = REPO_ROOT / "web" / "public" / "aleph-frontier.json"
DEFAULT_RECEIPTS = REPO_ROOT / "web" / "public" / "aleph-frontier.receipts.json"
DEFAULT_OUT = HERE / "frontier.json"

EXPLICIT_WRAPPER = (
    "Repeat the following text exactly, verbatim, with no preamble, quotes, "
    "or commentary:\n\n"
)
CJK_METRIC_PREFIX = "cjk_char_trigram_overlap_for_fit"

# The measured fields a displayed point must share with its receipt. This is
# the same observation allowlist that scripts/check-public-frontier.mjs uses
# for duplicate fingerprints; keep the two lists in sync.
MEASURED_FIELDS = (
    "epsilon", "prompt", "similarity", "stability", "length", "output",
    "toktext", "toknll",
)
MEASURED_OPTIONAL_FIELDS = ("embeddingSimilarity",)

# Declared stability procedure, unchanged from search/aleph_search.py: three
# stochastic generations at temperature 0.8, similarity spread mapped by
# ``1 - min(1, 4*pstdev)``. The raw similarities are recorded per receipt.
STABILITY_TEMPERATURE = 0.8
STABILITY_RUNS = 3

EPSILON_TOLERANCE = 1.2e-4  # |(1 - similarity) - epsilon| bound for rounded pairs


def _utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _finite_number(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def load_json(path) -> object:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def save_json(path, data) -> None:
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def observation_fields(value: dict) -> dict:
    """Extract the measured observation subset shared by points and receipts."""
    out = {}
    for field in MEASURED_FIELDS:
        if field not in value:
            raise KeyError(field)
        out[field] = value[field]
    for field in MEASURED_OPTIONAL_FIELDS:
        if field in value:
            out[field] = value[field]
    return out


def target_texts(artifact: list) -> dict:
    """Recover each measured target's text y from its artifact entry.

    English entries store no separate target text; their explicit baseline
    prompt is the fixed wrapper plus y, verified against search/targets.py.
    CJK entries declare no separate target text; their explicit baseline
    prompt is y verbatim (the receipts record this convention).
    """
    texts = {}
    for entry in artifact:
        key = entry.get("key")
        if key == "pitch":
            continue
        explicit = [p for p in entry.get("points", []) if p.get("role") == "explicit_reconstruction"]
        if len(explicit) != 1:
            raise SystemExit(f"target {key!r}: expected exactly one explicit baseline, found {len(explicit)}")
        prompt = explicit[0]["prompt"]
        if str(entry.get("metric") or "").startswith(CJK_METRIC_PREFIX):
            text = prompt
        else:
            if not prompt.startswith(EXPLICIT_WRAPPER):
                raise SystemExit(f"target {key!r}: explicit prompt does not start with the declared wrapper")
            text = prompt[len(EXPLICIT_WRAPPER):]
        if key in TARGETS and text != TARGETS[key]["text"]:
            raise SystemExit(f"target {key!r}: recovered text does not match search/targets.py")
        texts[key] = text
    return texts


def stability_scalar(similarities: list) -> float:
    """The declared stability statistic over raw similarities."""
    if len(similarities) < 2:
        return 1.0
    spread = statistics.pstdev(similarities)
    return round(max(0.0, 1.0 - min(1.0, spread * 4)), 3)


def receipt_body(receipt: dict) -> dict:
    return {key: value for key, value in receipt.items() if key != "receiptDigest"}


def with_digest(receipt: dict) -> dict:
    """Return ``receipt`` with ``receiptDigest`` recomputed over its body."""
    body = receipt_body(receipt)
    fresh = dict(body)
    fresh["receiptDigest"] = digest(body)
    return fresh


def selection_status(points: list) -> dict:
    """Per-index (kept, reason) mirroring observed_length_distortion_frontier.

    The shared selector stays the source of truth for what is displayed; this
    mirror only produces the audit reasons recorded on filtered receipts.
    ``annotate_consistency`` guards the two from drifting apart.
    """
    status = {}
    explicit_idx = [i for i, p in enumerate(points) if p.get("role") == "explicit_reconstruction"]
    candidate_idx = [i for i, p in enumerate(points) if p.get("role") != "explicit_reconstruction"]
    by_length = {}
    for i in candidate_idx:
        j = by_length.get(points[i]["length"])
        if j is None or _observed_point_key(points[i]) < _observed_point_key(points[j]):
            if j is not None:
                status[j] = (False, f"duplicate observed length {points[j]['length']}: deterministic tie-break kept another candidate")
            by_length[points[i]["length"]] = i
        else:
            status[i] = (False, f"duplicate observed length {points[i]['length']}: deterministic tie-break")
    best_epsilon = math.inf
    best_length = None
    for i in sorted(by_length.values(), key=lambda k: (points[k]["length"], _observed_point_key(points[k]))):
        if points[i]["epsilon"] < best_epsilon:
            status[i] = (True, None)
            best_epsilon = points[i]["epsilon"]
            best_length = points[i]["length"]
        else:
            status[i] = (False, f"epsilon {points[i]['epsilon']} does not strictly improve on epsilon {best_epsilon} kept at length {best_length}")
    if explicit_idx:
        baseline = min(explicit_idx, key=lambda k: (points[k]["length"], _observed_point_key(points[k])))
        status[baseline] = (True, None)
        for i in explicit_idx:
            if i != baseline:
                status[i] = (False, f"not the retained explicit baseline (the baseline at length {points[baseline]['length']} was chosen)")
    return status


def annotate_consistency(points: list, kept: list, status: dict) -> None:
    """Assert the status mirror selects exactly what the shared selector returns."""
    mirrored = [points[i] for i, (chosen, _) in status.items() if chosen]

    def signature(values):
        return sorted(json.dumps(p, ensure_ascii=False, sort_keys=True, default=str) for p in values)

    if len(kept) != len(mirrored) or signature(kept) != signature(mirrored):
        raise SystemExit("selection mirror drift: status annotations do not match observed_length_distortion_frontier")


def measure_point(theta, metric_fit, metric_embed, target_text, old_point, runs=STABILITY_RUNS):
    """Re-measure one displayed coordinate under the declared procedure."""
    prompt = old_point["prompt"]
    y_tokens = theta.ntokens(target_text)
    is_explicit = old_point.get("role") == "explicit_reconstruction"
    max_tokens = expected_max_tokens(y_tokens, is_explicit)
    started = time.time()
    output = theta.gen(prompt, max_tokens)
    similarity = metric_fit.sim(output, target_text)
    similarities = [
        round(metric_fit.sim(theta.gen(prompt, max_tokens, temp=STABILITY_TEMPERATURE), target_text), 4)
        for _ in range(runs)
    ]
    toktext, toknll = theta.score(prompt, target_text)
    toknll = [0.0 if value == 0 else value for value in toknll]
    observation = {
        "epsilon": round(1.0 - similarity, 4),
        "prompt": prompt,
        "similarity": round(similarity, 4),
        "stability": stability_scalar(similarities),
        "length": theta.ntokens(prompt),
        "output": output,
        "toktext": list(toktext),
        "toknll": toknll,
    }
    if metric_embed is not None:
        observation["embeddingSimilarity"] = round(metric_embed.sim(output, target_text), 4)
    measurement = {
        "generationSeconds": round(time.time() - started, 1),
        "maxTokens": max_tokens,
        "stabilityRuns": runs,
        "stabilityTemperature": STABILITY_TEMPERATURE,
        "stabilitySimilarities": similarities,
    }
    return observation, measurement


def procedure_block(max_tokens: int) -> dict:
    """Declared procedure constants shared by fresh measurements and reuse checks."""
    return {
        "entrypoint": "search/frontier_receipts.py run",
        "toolVersion": TOOL_VERSION,
        "generation": {
            "temperature": 0.0,
            "maxTokens": max_tokens,
            "template": "Qwen chat template, user role, enable_thinking=false, add_generation_prompt",
        },
        "stability": {
            "runs": STABILITY_RUNS,
            "temperature": STABILITY_TEMPERATURE,
            "statistic": "1 - min(1, 4*pstdev(similarities)), rounded to 3 decimals",
        },
        "trace": "teacher-forced per-token NLL of the target under the prompt",
    }


def expected_max_tokens(y_tokens: int, explicit: bool) -> int:
    return int(y_tokens * 1.4) + 32 if explicit else int(y_tokens * 1.6) + 32


def reuse_conflict(receipt: dict, model_meta: dict, procedure_meta: dict):
    """Explain why a checkpointed receipt cannot be reused, or return None.

    Resumable runs must never mix receipts measured under a different model
    snapshot or declared procedure into a published file: the run-level
    ``models``/procedure metadata would then describe an environment that did
    not measure every point.
    """
    if receipt.get("model") != model_meta:
        return "was measured under a different model snapshot"
    if receipt.get("procedure") != procedure_meta:
        return "was measured under a different declared procedure"
    return None


def build_receipt(target_key, target_digest, repo_meta, metric_meta, observation, measurement, old_point):
    receipt = {
        "target": target_key,
        "targetDigest": target_digest,
        "promptDigest": digest(observation["prompt"]),
        "model": repo_meta,
        "metric": metric_meta,
        "procedure": procedure_block(measurement["maxTokens"]),
        "measuredAt": _utc_now(),
        "supersedes": {
            "epsilon": old_point["epsilon"],
            "similarity": old_point["similarity"],
            "stability": old_point["stability"],
            "length": old_point["length"],
            "outputIdentical": observation["output"] == old_point["output"],
        },
        "measurement": measurement,
    }
    receipt.update(observation)
    receipt["outputDigest"] = digest(observation["output"])
    return receipt


def model_metadata(repo: str) -> dict:
    """Resolve the pinned model revision and weights digest from the local cache."""
    from huggingface_hub import snapshot_download
    path = Path(snapshot_download(repo, local_files_only=True))
    weights = Path(os.path.realpath(path / "model.safetensors"))
    candidate = weights.name
    if re.fullmatch(r"[0-9a-f]{64}", candidate):
        weights_digest = "sha256:" + candidate
    else:
        hasher = hashlib.sha256()
        with open(weights, "rb") as handle:
            for chunk in iter(lambda: handle.read(1 << 22), b""):
                hasher.update(chunk)
        weights_digest = "sha256:" + hasher.hexdigest()
    return {"repo": repo, "revision": path.name, "weightsDigest": weights_digest}


def environment_metadata() -> dict:
    def version(package: str):
        try:
            from importlib.metadata import version as package_version
            return package_version(package)
        except Exception:
            return None

    return {
        "python": platform.python_version(),
        "mlx": version("mlx"),
        "mlxLm": version("mlx-lm"),
        "sentenceTransformers": version("sentence-transformers"),
        "platform": platform.platform(),
    }


def metric_descriptor(entry: dict) -> dict:
    if str(entry.get("metric") or "").startswith(CJK_METRIC_PREFIX):
        return {
            "fit": {
                "kind": "char_trigram_overlap",
                "declared": True,
                "formula": "lowercased char-3-gram sets, Jaccard |intersection|/|union|",
            },
            "trace": {"kind": "teacher_forced_nll"},
        }
    return {
        "fit": {"kind": "embedding_cosine", "declared": True, "model": "sentence-transformers/all-MiniLM-L6-v2"},
        "trace": {"kind": "teacher_forced_nll"},
    }


def compute_counts(receipts: list) -> dict:
    displayed = [r for r in receipts if r.get("status") == "displayed"]
    outputs_identical = sum(1 for r in receipts if (r.get("supersedes") or {}).get("outputIdentical") is True)
    epsilon_identical = sum(
        1 for r in receipts if _json_equal(r.get("epsilon"), (r.get("supersedes") or {}).get("epsilon"))
    )
    return {
        "evaluated": len(receipts),
        "displayed": len(displayed),
        "filtered": len(receipts) - len(displayed),
        "outputsIdentical": outputs_identical,
        "epsilonIdentical": epsilon_identical,
    }


def _json_equal(a, b) -> bool:
    if isinstance(a, bool) or isinstance(b, bool):
        return type(a) is type(b) and a == b
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return float(a) == float(b)
    if isinstance(a, str) or isinstance(b, str):
        return a == b
    if isinstance(a, list) and isinstance(b, list):
        return len(a) == len(b) and all(_json_equal(x, y) for x, y in zip(a, b))
    if isinstance(a, dict) and isinstance(b, dict):
        return set(a) == set(b) and all(_json_equal(a[k], b[k]) for k in a)
    return a == b


def verify_payloads(artifact, doc) -> list:
    """Re-check artifact <-> receipts linkage.

    Mirrors ``scripts/check-public-frontier.mjs``: displayed-point linkage is
    digest-based (``receiptDigest`` over the receipt body in
    ``aleph-canonical/0.2.0`` form), measured fields must be identical between
    point and receipt, displayed receipts must be referenced exactly once and
    filtered receipts must not be referenced at all.
    """
    errors = []

    def err(message: str) -> None:
        errors.append(message)

    if not isinstance(artifact, list):
        return ["artifact: expected a list"]
    if not isinstance(doc, dict):
        return ["receipts: expected an object"]
    if doc.get("schemaVersion") != SCHEMA_VERSION:
        err(f"receipts.schemaVersion: expected {SCHEMA_VERSION!r}")
    run = doc.get("run")
    if not isinstance(run, dict):
        err("receipts.run: expected an object")
        run = {}
    receipts = doc.get("receipts")
    if not isinstance(receipts, list):
        return errors + ["receipts.receipts: expected a list"]

    by_digest = {}
    for index, receipt in enumerate(receipts):
        where = f"receipts[{index}]"
        if not isinstance(receipt, dict):
            err(f"{where}: expected an object")
            continue
        receipt_digest = receipt.get("receiptDigest")
        if not is_digest(receipt_digest):
            err(f"{where}.receiptDigest: expected a sha256: digest")
        elif receipt_digest in by_digest:
            err(f"{where}.receiptDigest: duplicate receipt digest")
        else:
            by_digest[receipt_digest] = receipt
        try:
            computed = digest(receipt_body(receipt))
        except Exception as exc:
            computed = None
            err(f"{where}: receipt body has no canonical form: {exc}")
        if computed is not None and computed != receipt_digest:
            err(f"{where}.receiptDigest: mismatch (recomputed {computed})")
        if not isinstance(receipt.get("target"), str) or not receipt.get("target"):
            err(f"{where}.target: expected a non-empty string")
        if not is_digest(receipt.get("targetDigest")):
            err(f"{where}.targetDigest: expected a sha256: digest")
        if receipt.get("status") not in ("displayed", "filtered"):
            err(f"{where}.status: expected 'displayed' or 'filtered'")
        for field in ("procedure", "measurement", "supersedes"):
            if not isinstance(receipt.get(field), dict):
                err(f"{where}.{field}: expected an object")
        if not isinstance(receipt.get("measuredAt"), str):
            err(f"{where}.measuredAt: expected a timestamp string")
        model = receipt.get("model")
        if not isinstance(model, dict):
            err(f"{where}.model: expected an object")
        else:
            if not isinstance(model.get("repo"), str) or not model.get("repo"):
                err(f"{where}.model.repo: expected a non-empty string")
            if not isinstance(model.get("revision"), str) or not model.get("revision"):
                err(f"{where}.model.revision: expected a non-empty string")
            if not is_digest(model.get("weightsDigest")):
                err(f"{where}.model.weightsDigest: expected a sha256: digest")
        try:
            if receipt.get("promptDigest") != digest(receipt.get("prompt")):
                err(f"{where}.promptDigest: mismatch")
        except Exception as exc:
            err(f"{where}.promptDigest: not canonicalizable: {exc}")
        try:
            if receipt.get("outputDigest") != digest(receipt.get("output")):
                err(f"{where}.outputDigest: mismatch")
        except Exception as exc:
            err(f"{where}.outputDigest: not canonicalizable: {exc}")
        epsilon = receipt.get("epsilon")
        similarity = receipt.get("similarity")
        if _finite_number(epsilon) and _finite_number(similarity) and abs((1.0 - similarity) - epsilon) > EPSILON_TOLERANCE:
            err(f"{where}: epsilon/similarity are inconsistent")
        stability = receipt.get("stability")
        if not _finite_number(stability) or not 0.0 <= float(stability) <= 1.0:
            err(f"{where}.stability: expected a finite number in [0, 1]")
        length = receipt.get("length")
        if isinstance(length, bool) or not isinstance(length, int) or length < 0:
            err(f"{where}.length: expected a non-negative integer")
        toktext = receipt.get("toktext")
        toknll = receipt.get("toknll")
        if not isinstance(toktext, list) or any(not isinstance(token, str) for token in toktext):
            err(f"{where}.toktext: expected a list of strings")
        if not isinstance(toknll, list) or any(not _finite_number(loss) for loss in toknll):
            err(f"{where}.toknll: expected a list of finite numbers")
        if isinstance(toktext, list) and isinstance(toknll, list) and len(toktext) != len(toknll):
            err(f"{where}: toktext and toknll length mismatch")
        embedding = receipt.get("embeddingSimilarity")
        if embedding is not None and (not _finite_number(embedding) or not 0.0 <= float(embedding) <= 1.0):
            err(f"{where}.embeddingSimilarity: expected a finite number in [0, 1]")

    referenced = {}
    for entry_index, entry in enumerate(artifact):
        if not isinstance(entry, dict):
            continue
        key = entry.get("key")
        if key == "pitch":
            continue
        if not isinstance(entry.get("evalModel"), str) or not entry.get("evalModel"):
            err(f"frontier[{entry_index}].evalModel: measured targets must declare the evaluation model")
        for point_index, point in enumerate(entry.get("points") or []):
            where = f"frontier[{entry_index}].points[{point_index}]"
            if not isinstance(point, dict):
                continue
            receipt_digest = point.get("receiptDigest")
            if not is_digest(receipt_digest):
                err(f"{where}.receiptDigest: expected a sha256: digest")
                continue
            receipt = by_digest.get(receipt_digest)
            if receipt is None:
                err(f"{where}.receiptDigest: does not resolve to a receipt")
                continue
            if receipt_digest in referenced:
                err(f"{where}: receipt already referenced by {referenced[receipt_digest]}")
                continue
            referenced[receipt_digest] = where
            if receipt.get("status") != "displayed":
                err(f"{where}: references a receipt with status {receipt.get('status')!r}")
            if receipt.get("target") != key:
                err(f"{where}: receipt target {receipt.get('target')!r} does not match {key!r}")
            model = receipt.get("model") if isinstance(receipt.get("model"), dict) else {}
            if isinstance(entry.get("evalModel"), str) and model.get("repo") != entry.get("evalModel"):
                err(f"{where}: receipt model repo {model.get('repo')!r} does not match evalModel")
            try:
                point_fields = observation_fields(point)
                receipt_fields = observation_fields(receipt)
            except KeyError as exc:
                err(f"{where}: missing measured field {exc}")
                continue
            if set(point_fields) != set(receipt_fields):
                err(f"{where}: measured field set differs from the receipt")
            else:
                for field in point_fields:
                    if not _json_equal(point_fields[field], receipt_fields[field]):
                        err(f"{where}: displayed {field} differs from its receipt")

    for receipt_digest, receipt in by_digest.items():
        if receipt.get("status") == "displayed" and receipt_digest not in referenced:
            err(f"receipts: displayed receipt {receipt_digest} is not referenced by any artifact point")

    if run:
        if run.get("complete") is not True:
            err("receipts.run.complete: expected true for a published receipts file")
        run_targets = run.get("targets")
        if not isinstance(run_targets, list) or not all(isinstance(item, str) for item in run_targets):
            err("receipts.run.targets: expected a list of target keys")
        else:
            measured_keys = {
                entry.get("key") for entry in artifact if isinstance(entry, dict) and entry.get("key") != "pitch"
            }
            if set(run_targets) != measured_keys:
                err("receipts.run.targets: does not cover exactly the measured artifact targets")
            for receipt_digest, receipt in by_digest.items():
                if receipt.get("target") not in run_targets:
                    err(f"receipts: receipt {receipt_digest} target is not in run.targets")
        counts = run.get("counts")
        if not isinstance(counts, dict):
            err("receipts.run.counts: expected an object")
        else:
            expected = compute_counts([r for r in receipts if isinstance(r, dict)])
            for field, value in expected.items():
                if counts.get(field) != value:
                    err(f"receipts.run.counts.{field}: expected {value}")
    return errors


def run_main(args) -> int:
    artifact = load_json(args.artifact)
    if not isinstance(artifact, list):
        raise SystemExit("artifact: expected a top-level list")
    receipts_path = Path(args.receipts)
    doc = load_json(receipts_path) if receipts_path.exists() else None
    if doc is None:
        doc = {
            "schemaVersion": SCHEMA_VERSION,
            "run": {
                "tool": {"path": "search/frontier_receipts.py", "version": TOOL_VERSION},
                "startedAt": _utc_now(),
                "models": {},
                "notes": [
                    "Every displayed point is re-measured under the declared procedure recorded on its receipt; prompt coordinates are carried over unmodified from the historical export.",
                    "Historical displayed values are preserved per receipt under `supersedes`; they are superseded evidence, never reused.",
                    "Receipts are linked from artifact points by `receiptDigest`, an aleph-canonical/0.2.0 digest of the receipt body; scripts/check-public-frontier.mjs recomputes it independently.",
                ],
                "complete": False,
            },
            "receipts": [],
        }
    elif doc.get("schemaVersion") != SCHEMA_VERSION:
        raise SystemExit(f"receipts: unsupported schemaVersion {doc.get('schemaVersion')!r}")

    run = doc["run"]
    receipts = doc["receipts"]
    index = {(r.get("target"), r.get("promptDigest")): i for i, r in enumerate(receipts)}

    measured_keys = [entry["key"] for entry in artifact if entry.get("key") != "pitch"]
    entries = {entry["key"]: entry for entry in artifact}
    keys = measured_keys if not args.targets else [part.strip() for part in args.targets.split(",") if part.strip()]
    unknown = [key for key in keys if key not in entries]
    if unknown:
        raise SystemExit(f"unknown target(s): {unknown}")

    texts = target_texts(artifact)
    thetas = {}
    fits = {}
    embeds = {}
    budget = int(args.max_points or 0)
    deadline = time.time() + int(args.time_budget) if int(args.time_budget or 0) > 0 else None
    produced = 0
    stopped = False

    for key in keys:
        entry = entries[key]
        repo = entry["evalModel"]
        target_text = texts[key]
        cjk = str(entry.get("metric") or "").startswith(CJK_METRIC_PREFIX)
        if key not in fits:
            fits[key] = Metric("ngram" if cjk else "embed")
            embeds[key] = Metric("embed") if cjk else None
        if repo not in thetas:
            thetas[repo] = Theta(repo)
            run.setdefault("models", {})[repo] = model_metadata(repo)
            run["environment"] = environment_metadata()
            save_json(receipts_path, doc)
        theta = thetas[repo]
        metric_fit = fits[key]
        metric_embed = embeds[key]
        y_tokens = theta.ntokens(target_text)
        if y_tokens != entry.get("targetTokens"):
            raise SystemExit(
                f"target {key!r}: tokenizer counts {y_tokens} target tokens, artifact declares {entry.get('targetTokens')}; investigate before publishing"
            )
        for old_point in entry["points"]:
            prompt_digest = digest(old_point["prompt"])
            existing = index.get((key, prompt_digest))
            if existing is not None and not args.force:
                explicit = old_point.get("role") == "explicit_reconstruction"
                conflict = reuse_conflict(
                    receipts[existing],
                    run["models"][repo],
                    procedure_block(expected_max_tokens(y_tokens, explicit)),
                )
                if conflict is not None:
                    raise SystemExit(
                        f"target {key!r}: checkpointed receipt for prompt length {old_point['length']} "
                        f"{conflict}; re-run with --force after investigating"
                    )
                continue
            if budget and produced >= budget:
                stopped = True
                break
            if deadline is not None and time.time() > deadline:
                stopped = True
                break
            observation, measurement = measure_point(theta, metric_fit, metric_embed, target_text, old_point)
            if observation["length"] != old_point["length"]:
                raise SystemExit(
                    f"target {key!r}: measured prompt length {observation['length']} != displayed {old_point['length']}; investigate before publishing"
                )
            receipt = build_receipt(key, digest(target_text), run["models"][repo], metric_descriptor(entry), observation, measurement, old_point)
            if existing is None:
                receipts.append(receipt)
                index[(key, prompt_digest)] = len(receipts) - 1
            else:
                receipts[existing] = receipt
            produced += 1
            run["updatedAt"] = _utc_now()
            save_json(receipts_path, doc)
            print(
                f"[{key}] {old_point.get('role') or 'candidate'} |p|={observation['length']} "
                f"eps={observation['epsilon']} sim={observation['similarity']} stab={observation['stability']} "
                f"gen={measurement['generationSeconds']}s outputIdentical={receipt['supersedes']['outputIdentical']}",
                flush=True,
            )
        if stopped:
            break

    missing = [
        (key, digest(point["prompt"]))
        for key in measured_keys
        for point in entries[key]["points"]
        if (key, digest(point["prompt"])) not in index
    ]
    if missing:
        run["updatedAt"] = _utc_now()
        save_json(receipts_path, doc)
        print(f"[incomplete] {len(missing)} point(s) still need receipts; {produced} measured this call", flush=True)
        return 0

    fresh_entries = []
    for key in measured_keys:
        entry = entries[key]
        fresh_points = []
        receipt_indexes = []
        for old_point in entry["points"]:
            receipt_index = index[(key, digest(old_point["prompt"]))]
            fresh = observation_fields(receipts[receipt_index])
            for extra in ("label", "role", "evidence"):
                if extra in old_point:
                    fresh[extra] = old_point[extra]
            fresh_points.append(fresh)
            receipt_indexes.append(receipt_index)
        kept = observed_length_distortion_frontier(fresh_points)
        status = selection_status(fresh_points)
        annotate_consistency(fresh_points, kept, status)
        for position, receipt_index in enumerate(receipt_indexes):
            chosen, reason = status[position]
            receipt = {
                field: value
                for field, value in receipts[receipt_index].items()
                if field not in ("status", "filterReason", "receiptDigest")
            }
            receipt["status"] = "displayed" if chosen else "filtered"
            if not chosen:
                receipt["filterReason"] = reason
            receipts[receipt_index] = with_digest(receipt)
        for point in kept:
            point["receiptDigest"] = receipts[index[(key, digest(point["prompt"]))]]["receiptDigest"]
        fresh_entry = {field: entry[field] for field in ("key", "label", "targetTokens", "evalModel")}
        if "metric" in entry:
            fresh_entry["metric"] = entry["metric"]
        fresh_entry["points"] = kept
        fresh_entries.append(fresh_entry)

    run["targets"] = list(measured_keys)
    run["complete"] = True
    run["completedAt"] = _utc_now()
    run["updatedAt"] = _utc_now()
    run["counts"] = compute_counts(receipts)
    save_json(receipts_path, doc)
    out_path = Path(args.out)
    save_json(out_path, fresh_entries)
    print(f"[complete] {len(fresh_entries)} target(s); counts={run['counts']}", flush=True)
    print(f"[write] {receipts_path}", flush=True)
    print(f"[write] {out_path}", flush=True)
    print("next: python search/finalize.py --no-merge && python search/add_pitch.py && node scripts/check-public-frontier.mjs", flush=True)
    return 0


def verify_main(args) -> int:
    receipts_path = Path(args.receipts)
    if not receipts_path.exists():
        print(f"frontier receipts check failed: missing {receipts_path}")
        return 1
    artifact = load_json(args.artifact)
    doc = load_json(receipts_path)
    errors = verify_payloads(artifact, doc)
    if errors:
        print("frontier receipts check failed:")
        for error in errors:
            print(f"- {error}")
        return 1
    counts = compute_counts([r for r in doc.get("receipts", []) if isinstance(r, dict)])
    print(
        f"frontier receipts ok ({counts['evaluated']} receipts; "
        f"{counts['displayed']} displayed, {counts['filtered']} filtered; "
        f"{counts['outputsIdentical']} identical outputs)"
    )
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Regenerate the public MLX frontier with per-point receipts.")
    sub = parser.add_subparsers(dest="command", required=True)

    run_parser = sub.add_parser("run", help="re-measure displayed points and write receipts")
    run_parser.add_argument("--artifact", default=str(DEFAULT_ARTIFACT))
    run_parser.add_argument("--receipts", default=str(DEFAULT_RECEIPTS))
    run_parser.add_argument("--out", default=str(DEFAULT_OUT))
    run_parser.add_argument("--targets", default="", help="comma-separated subset for a bounded run")
    run_parser.add_argument("--force", action="store_true", help="re-measure points that already have receipts")
    run_parser.add_argument("--max-points", type=int, default=0, help="stop after this many new measurements")
    run_parser.add_argument("--time-budget", type=int, default=0, help="stop after this many seconds (0 = no limit)")
    run_parser.set_defaults(handler=run_main)

    verify_parser = sub.add_parser("verify", help="re-check the artifact against the receipts (no MLX)")
    verify_parser.add_argument("--artifact", default=str(DEFAULT_ARTIFACT))
    verify_parser.add_argument("--receipts", default=str(DEFAULT_RECEIPTS))
    verify_parser.set_defaults(handler=verify_main)

    args = parser.parse_args(argv)
    return args.handler(args)


if __name__ == "__main__":
    raise SystemExit(main())
