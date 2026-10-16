"""Readable-side runner for matched-budget comparison instances (MLX path).

Runs one declared target through the shipped readable search procedure of
``search/aleph_search.py`` — propose, compress (carry from the larger budget),
NLL-guided refine, stability, explicit reconstruction — under the declared
comparison settings, and writes the ``aleph-comparison-readable/0.1.0``
artifact (``readable.json``) consumed by ``record.verify_readable``.

Declared differences from the shipped procedure (also recorded in every
artifact):

- every stochastic generation is preceded by ``mx.random.seed(...)`` with a
  seed derived from an explicit ``random.Random`` tree rooted at the declared
  ``proposerSeed``, replacing the shipped unseeded process-global RNG, so the
  run is replayable from the declaration and resumable across invocations;
- the declared ladder is the comparison config's budgets executed in
  descending order (the shipped pipeline used ``[6, 12, 25, 50, 100]``);
- recorded similarities are rounded to 4 decimals and every selection
  (first-strict-max over propose/compress candidates, strict-improvement
  refinement) compares the recorded values, so the archived selection is
  replayable from the archive alone without MLX;
- the explicit-reconstruction arm is generated under the declared wrapper
  exactly as the shipped procedure does, and is retained only as the tagged
  copy baseline;
- the shared wall-clock envelope and the digest-bound comparison record are
  comparison declarations around the readable run; the runner records its own
  measured operation seconds (model load excluded, as on the raw side) and
  never tunes after the fact.

The run is resumable: ``readable-state.json`` is written atomically after
every operation, and a paused invocation can be resumed by re-running the
same command. The artifact is written only when the declared sequence
completed inside the envelope plus the declared slack. Exit codes: 0 complete,
1 failure (including an exceeded envelope — never archived), 2 usage, 3 paused
by the time budget.

Command::

    python -m search.compare.readable --instance canary-1p7b \
        --target-key hello-world --run-dir DIR [--max-seconds N]
"""

from __future__ import annotations

import argparse
import platform as platform_module
import random
import re
import time
from importlib import metadata
from pathlib import Path

from search.miniprompt.receipts import read_json, write_json_atomic

from .config import READABLE_SCHEMA
from .record import (
    ENVELOPE_SLACK_SECONDS,
    METRIC_SECONDARY,
    TOOL,
    char_trigram_similarity,
    derive_kept_indices,
    digest,
    prompt_contains_target_text,
    stability_scalar,
    target_trigram_containment,
    verify_readable,
)

STATE_SCHEMA = "aleph-comparison-readable-state/0.1.0"
PROPOSE_TEMPERATURE = 0.85
COMPRESS_TEMPERATURE = 0.5
REFINE_TEMPERATURE = 0.6
DERIVATION = "compare-readable-python-random-v1"
THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL)

DECLARED_DIFFERENCES = (
    "Seeded re-run of the shipped readable search procedure: every stochastic generation is "
    "preceded by mx.random.seed(...) with a seed derived from an explicit random.Random tree "
    "rooted at the declared proposerSeed, replacing the shipped unseeded process-global RNG.",
    "The declared ladder is the comparison config's budgets executed in descending order; the "
    "shipped pipeline used [6, 12, 25, 50, 100].",
    "Recorded similarities are rounded to 4 decimals and every selection (first-strict-max over "
    "propose/compress candidates, strict-improvement refinement) compares the recorded values, "
    "so the archived selection is replayable from the archive alone without MLX.",
    "The explicit-reconstruction arm is generated under the declared wrapper exactly as the "
    "shipped procedure does, and is retained only as the tagged copy baseline.",
    "The shared wall-clock envelope and the digest-bound comparison record are comparison "
    "declarations around the readable run; the runner records its own measured operation seconds "
    "(model load excluded, as on the raw side) and never tunes after the fact.",
)


class ReadableRunError(RuntimeError):
    """The readable run state or artifact violates the declared contract."""


def utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def environment_metadata() -> dict:
    try:
        sentence = metadata.version("sentence-transformers")
    except metadata.PackageNotFoundError:
        sentence = None
    return {
        "python": platform_module.python_version(),
        "mlx": metadata.version("mlx"),
        "mlxLm": metadata.version("mlx-lm"),
        "sentenceTransformers": sentence,
        "platform": platform_module.platform(),
    }


def proposal_seed(config, target_key: str, *parts: object) -> int:
    """A derived per-call sampling seed from the declared proposer-seed tree.

    The declared ``proposerSeed`` is part of the derivation string, so configs
    that differ only in that setting sample differently (and every sampled
    call remains replayable from the declaration).
    """
    rng = random.Random(
        "/".join(
            [
                DERIVATION,
                config.label,
                target_key,
                str(config.readable.proposer_seed),
                *[str(part) for part in parts],
            ]
        )
    )
    return rng.randrange(2 ** 31)


# ---------- proposal parsing (mirrors the shipped proposer, pure helpers) ----------


def clean_line(line: str) -> str:
    line = re.sub(r"^\s*(?:\d+[\.\)]|[-*\u2022])\s*", "", line).strip()
    return line.strip(" \"'`").strip()


def parse_candidates(text: str, n: int):
    """Up to ``n`` candidate lines from one proposal generation (shipped parser)."""
    out, seen = [], set()
    for raw in text.splitlines():
        candidate = clean_line(raw)
        lowered = candidate.lower()
        if len(candidate) < 4 or lowered in seen:
            continue
        if lowered.startswith(("here are", "sure", "prompt", "output", "okay", "these are", "certainly")):
            continue
        seen.add(lowered)
        out.append(candidate)
        if len(out) >= n:
            break
    return out


def hardest_tokens(toks, nll, k: int = 8):
    """The target tokens the prompt fails to carry (shipped NLL ranking)."""
    if not toks or not nll:
        return []
    pairs = sorted(zip(toks, nll), key=lambda pair: -pair[1])
    seen, out = set(), []
    for token, value in pairs:
        word = token.strip()
        lowered = word.lower()
        if len(word) < 2 or lowered in seen or value <= 0.05:
            continue
        seen.add(lowered)
        out.append(word)
        if len(out) >= k:
            break
    return out


def propose_instruction(target: str, budget: int, n: int) -> str:
    return (
        f"I will give you a TARGET text. Output {n} different candidate "
        f"prompts. Each prompt, if given to an AI assistant, should make it "
        f"reproduce the TARGET as closely as possible. Each prompt must be at "
        f"most {budget} words. Prefer naming the work, author, or form so the "
        f"model uses its own knowledge instead of you restating the text. "
        f"Output ONLY the {n} prompts, one per line, no numbering, no "
        f"commentary.\n\nTARGET:\n{target}"
    )


def compress_instruction(target: str, prompt: str, budget: int) -> str:
    return (
        f"Below is a WORKING prompt that already makes an AI reproduce the "
        f"TARGET. Rewrite it to AT MOST {budget} words, keeping only what is "
        f"essential to still reproduce the TARGET — prefer a bare "
        f"work/author/form reference over restating text. Output ONLY the "
        f"shortened prompt.\n\nTARGET:\n{target}\n\nWORKING PROMPT:\n{prompt}"
    )


def refine_instruction(target: str, prompt: str, got: str, budget: int, hard) -> str:
    miss = (
        f"\nThe model reproduced these TARGET words least reliably — fix "
        f"these specifically: {', '.join(hard)}." if hard else ""
    )
    return (
        f"Improve the PROMPT so an AI's output matches the TARGET better. "
        f"Keep it within {budget} words; prefer naming the work/author/form "
        f"over restating content.{miss} Output ONLY the single improved "
        f"prompt, nothing else.\n\nTARGET:\n{target}\n\nCURRENT PROMPT:\n"
        f"{prompt}\n\nWHAT THE MODEL PRODUCED:\n{got[:600]}"
    )


def fallback_prompt(target: str, budget: int) -> str:
    return f"Write the text: {target[: budget * 6]}"


# ---------- evaluator (the pinned model is theta) and metric ----------


class Theta:
    def __init__(self, model, tokenizer, meta):
        self.model = model
        self.tok = tokenizer
        self.meta = meta

    def fmt(self, prompt: str) -> str:
        messages = [{"role": "user", "content": prompt}]
        try:
            return self.tok.apply_chat_template(
                messages, add_generation_prompt=True, tokenize=False, enable_thinking=False
            )
        except TypeError:
            return self.tok.apply_chat_template(messages, add_generation_prompt=True, tokenize=False)

    def gen(self, prompt: str, max_tokens: int, temp: float = 0.0, seed=None) -> str:
        from mlx_lm import generate

        kw = {}
        if temp and temp > 0:
            import mlx.core as mx
            from mlx_lm.sample_utils import make_sampler

            kw["sampler"] = make_sampler(temp=temp)
            if seed is not None:
                mx.random.seed(int(seed))
        out = generate(self.model, self.tok, prompt=self.fmt(prompt), max_tokens=max_tokens, verbose=False, **kw)
        return THINK_RE.sub("", out).strip()

    def ntokens(self, text: str) -> int:
        return len(self.tok.encode(text))

    def score(self, prompt: str, target: str):
        """Teacher-forced per-token NLL of ``target`` given ``prompt`` (shipped form)."""
        import mlx.core as mx
        import mlx.nn as nn

        fmt_ids = self.tok.encode(self.fmt(prompt))
        y_ids = self.tok.encode(target)
        if not y_ids:
            return [], []
        logits = self.model(mx.array([fmt_ids + y_ids]))
        logp = nn.log_softmax(logits[0].astype(mx.float32), axis=-1)
        base = len(fmt_ids)
        toks, nlls = [], []
        for t, tid in enumerate(y_ids):
            lp = float(logp[base + t - 1, tid])
            value = round(-lp, 4)
            if value == 0:
                value = 0.0
            toks.append(self.tok.decode([tid]))
            nlls.append(value)
        return toks, nlls


class Metric:
    """The declared embedding_cosine metric, loaded from the declared model name."""

    def __init__(self, model_name: str):
        from sentence_transformers import SentenceTransformer

        self.encoder = SentenceTransformer(model_name)

    def sim(self, a: str, b: str) -> float:
        import numpy as np

        ea, eb = self.encoder.encode([a, b], normalize_embeddings=True)
        return float(np.dot(ea, eb))


# ---------- state helpers ----------


def _proc_reset() -> dict:
    return {
        "pendingProposals": None,
        "proposalIndex": 0,
        "pendingCompress": None,
        "refineIndex": 0,
        "refineScore": None,
        "pendingRefine": None,
        "stabilityIndex": 0,
    }


def _recorded_total(state: dict) -> float:
    return sum(float(value) for value in state["recordedSeconds"].values())


def _validate_state(state, config, spec) -> None:
    if not isinstance(state, dict) or state.get("schema") != STATE_SCHEMA:
        raise ReadableRunError("readable state has an unexpected schema")
    if state.get("configDigest") != config.digest or state.get("config") != config.to_canonical():
        raise ReadableRunError("refusing to resume: readable state belongs to a different declared config")
    if state.get("instance") != config.label:
        raise ReadableRunError("refusing to resume: readable state belongs to a different instance")
    target = state.get("target") or {}
    if target.get("key") != spec.key or target.get("text") != spec.text:
        raise ReadableRunError("refusing to resume: readable state belongs to a different target")
    if state.get("budgets") != sorted(config.readable.budgets, reverse=True):
        raise ReadableRunError("readable state budgets disagree with the declared ladder")
    for key in ("createdAt", "model", "environment", "recordedSeconds", "evaluations", "points", "proc"):
        if key not in state:
            raise ReadableRunError(f"readable state is missing {key!r}")


def _epsilon_of(similarity: float) -> float:
    value = round(1.0 - float(similarity), 4)
    if value == 0:
        return 0.0
    return value


def _finish_evaluation(state, spec, metric, *, phase, budget, prompt, out, seconds, update_best):
    target_text = spec.text
    similarity = round(min(1.0, max(0.0, float(metric.sim(out, target_text)))), 4)
    evaluation = {
        "index": len(state["evaluations"]),
        "phase": phase,
        "budget": budget,
        "prompt": prompt,
        "promptDigest": digest(prompt),
        "output": out,
        "outputDigest": digest(out),
        "similarity": similarity,
        "similarityNgram3": round(char_trigram_similarity(out, target_text), 4),
        "outputEqualsTarget": out == target_text.strip(),
        "seconds": round(seconds, 4),
        "promptContainsTargetText": prompt_contains_target_text(prompt, target_text),
        "promptTargetTrigramContainment": round(target_trigram_containment(prompt, target_text), 4),
    }
    state["evaluations"].append(evaluation)
    state["recordedSeconds"]["evaluation"] += seconds
    if update_best:
        best = state["currentBest"]
        if best is None or similarity > best["similarity"]:
            state["currentBest"] = {
                "prompt": prompt,
                "similarity": similarity,
                "evaluationIndex": evaluation["index"],
            }


# ---------- the op machine ----------


def _pick_op(state, budgets, config) -> str:
    if state["budgetIndex"] >= len(budgets):
        if not state.get("explicitEvalDone"):
            return "explicit_eval"
        if not state.get("explicitDone"):
            return "explicit_point"
        return "finalize"
    phase = state["budgetPhase"]
    proc = state["proc"]
    if phase == "propose":
        if proc["pendingProposals"] is None:
            return "proposal_call"
        if proc["proposalIndex"] < len(proc["pendingProposals"]):
            return "proposal_eval"
        state["budgetPhase"] = "compress" if state["budgetIndex"] > 0 else "refine"
        return _pick_op(state, budgets, config)
    if phase == "compress":
        if proc["pendingCompress"] is None:
            return "compress_call"
        return "compress_eval"
    if phase == "refine":
        if proc["refineIndex"] >= config.readable.refine_steps:
            state["budgetPhase"] = "stability"
            return _pick_op(state, budgets, config)
        if proc["refineScore"] is None:
            return "refine_score"
        if proc["pendingRefine"] is None:
            return "refine_call"
        return "refine_eval"
    if phase == "stability":
        if proc["stabilityIndex"] < config.readable.stability_runs:
            return "stability_run"
        return "point_build"
    raise ReadableRunError(f"unexpected budget phase {phase!r}")


def _do_op(op, state, config, spec, theta, metric, *, log) -> None:
    budgets = state["budgets"]
    budget_index = state["budgetIndex"]
    budget = budgets[budget_index] if budget_index < len(budgets) else None
    target_text = spec.text
    token_count = state["target"]["tokenCount"]
    max_out = int(token_count * 1.6) + 32
    max_out_explicit = int(token_count * 1.4) + 32
    proc = state["proc"]

    if op == "proposal_call":
        k = config.readable.candidates_per_budget
        started = time.monotonic()
        text = theta.gen(
            propose_instruction(target_text, budget, k),
            max_tokens=60 * k + 80,
            temp=PROPOSE_TEMPERATURE,
            seed=proposal_seed(config, spec.key, "propose", budget_index),
        )
        seconds = time.monotonic() - started
        candidates = parse_candidates(text, k)
        if not candidates:
            candidates = [fallback_prompt(target_text, budget)]
        proc["pendingProposals"] = candidates
        proc["proposalIndex"] = 0
        state["recordedSeconds"]["proposal"] += seconds
        log(f"[readable] budget {budget}: {len(candidates)} proposal(s) parsed")
    elif op == "proposal_eval":
        prompt = proc["pendingProposals"][proc["proposalIndex"]]
        started = time.monotonic()
        out = theta.gen(prompt, max_out, temp=0.0)
        _finish_evaluation(
            state, spec, metric, phase="propose", budget=budget, prompt=prompt, out=out,
            seconds=time.monotonic() - started, update_best=True,
        )
        proc["proposalIndex"] += 1
    elif op == "compress_call":
        carry = state["carryPrompt"]
        if not carry:
            raise ReadableRunError("compress requires a carried prompt from the previous budget")
        started = time.monotonic()
        text = theta.gen(
            compress_instruction(target_text, carry, budget),
            max_tokens=budget * 6 + 60,
            temp=COMPRESS_TEMPERATURE,
            seed=proposal_seed(config, spec.key, "compress", budget_index),
        )
        seconds = time.monotonic() - started
        candidates = parse_candidates(text, 1)
        proc["pendingCompress"] = candidates[0] if candidates else carry
        state["recordedSeconds"]["proposal"] += seconds
    elif op == "compress_eval":
        prompt = proc["pendingCompress"]
        started = time.monotonic()
        out = theta.gen(prompt, max_out, temp=0.0)
        _finish_evaluation(
            state, spec, metric, phase="compress", budget=budget, prompt=prompt, out=out,
            seconds=time.monotonic() - started, update_best=True,
        )
        proc["pendingCompress"] = None
        state["budgetPhase"] = "refine"
    elif op == "refine_score":
        best = state["currentBest"]
        started = time.monotonic()
        toks, nlls = theta.score(best["prompt"], target_text)
        proc["refineScore"] = {"toktext": toks, "toknll": nlls}
        state["recordedSeconds"]["scoring"] += time.monotonic() - started
    elif op == "refine_call":
        best = state["currentBest"]
        score = proc["refineScore"]
        got = state["evaluations"][best["evaluationIndex"]]["output"]
        hard = hardest_tokens(score["toktext"], score["toknll"], 8)
        started = time.monotonic()
        text = theta.gen(
            refine_instruction(target_text, best["prompt"], got, budget, hard),
            max_tokens=budget * 6 + 60,
            temp=REFINE_TEMPERATURE,
            seed=proposal_seed(config, spec.key, "refine", budget_index, proc["refineIndex"]),
        )
        seconds = time.monotonic() - started
        candidates = parse_candidates(text, 1)
        proc["pendingRefine"] = candidates[0] if candidates else best["prompt"]
        state["recordedSeconds"]["proposal"] += seconds
    elif op == "refine_eval":
        prompt = proc["pendingRefine"]
        started = time.monotonic()
        out = theta.gen(prompt, max_out, temp=0.0)
        _finish_evaluation(
            state, spec, metric, phase="refine", budget=budget, prompt=prompt, out=out,
            seconds=time.monotonic() - started, update_best=True,
        )
        proc["pendingRefine"] = None
        proc["refineScore"] = None
        proc["refineIndex"] += 1
    elif op == "stability_run":
        best = state["currentBest"]
        run_index = proc["stabilityIndex"]
        started = time.monotonic()
        out = theta.gen(
            best["prompt"],
            max_out,
            temp=config.readable.stability_temperature,
            seed=proposal_seed(config, spec.key, "stability", budget_index, run_index),
        )
        _finish_evaluation(
            state, spec, metric, phase="stability", budget=budget, prompt=best["prompt"], out=out,
            seconds=time.monotonic() - started, update_best=False,
        )
        proc["stabilityIndex"] += 1
    elif op == "point_build":
        best = state["currentBest"]
        started = time.monotonic()
        toks, nlls = theta.score(best["prompt"], target_text)
        state["recordedSeconds"]["scoring"] += time.monotonic() - started
        stability_similarities = [
            evaluation["similarity"]
            for evaluation in state["evaluations"]
            if evaluation["phase"] == "stability"
            and evaluation["budget"] == budget
            and evaluation["prompt"] == best["prompt"]
        ]
        prompt_ids = list(theta.tok.encode(best["prompt"]))
        evaluation = state["evaluations"][best["evaluationIndex"]]
        point = {
            "budget": budget,
            "evaluationIndex": best["evaluationIndex"],
            "prompt": best["prompt"],
            "promptDigest": digest(best["prompt"]),
            "promptTokenIds": prompt_ids,
            "length": len(prompt_ids),
            "similarity": best["similarity"],
            "epsilon": _epsilon_of(best["similarity"]),
            "output": evaluation["output"],
            "outputDigest": digest(evaluation["output"]),
            "outputEqualsTarget": evaluation["outputEqualsTarget"],
            "toktext": toks,
            "toknll": nlls,
            "stabilitySimilarities": stability_similarities,
            "stability": stability_scalar(stability_similarities),
            "kept": False,
        }
        state["points"].append(point)
        state["carryPrompt"] = best["prompt"]
        state["budgetIndex"] += 1
        state["currentBest"] = None
        state["proc"] = _proc_reset()
        state["budgetPhase"] = "propose" if state["budgetIndex"] < len(budgets) else "explicit"
        log(
            f"[readable] point K~{budget}: |p|={point['length']} sim={point['similarity']:.4f} "
            f"eps={point['epsilon']:.4f} prompt={point['prompt'][:70]!r}"
        )
    elif op == "explicit_eval":
        prompt = config.explicit_wrapper + target_text
        started = time.monotonic()
        out = theta.gen(prompt, max_out_explicit, temp=0.0)
        _finish_evaluation(
            state, spec, metric, phase="explicit", budget=None, prompt=prompt, out=out,
            seconds=time.monotonic() - started, update_best=False,
        )
        state["explicitEvaluationIndex"] = len(state["evaluations"]) - 1
        state["explicitEvalDone"] = True
    elif op == "explicit_point":
        prompt = config.explicit_wrapper + target_text
        started = time.monotonic()
        toks, nlls = theta.score(prompt, target_text)
        state["recordedSeconds"]["scoring"] += time.monotonic() - started
        index = state["explicitEvaluationIndex"]
        evaluation = state["evaluations"][index]
        prompt_ids = list(theta.tok.encode(prompt))
        point = {
            "budget": None,
            "role": "explicit_reconstruction",
            "evaluationIndex": index,
            "prompt": prompt,
            "promptDigest": digest(prompt),
            "promptTokenIds": prompt_ids,
            "length": len(prompt_ids),
            "similarity": evaluation["similarity"],
            "epsilon": _epsilon_of(evaluation["similarity"]),
            "output": evaluation["output"],
            "outputDigest": digest(evaluation["output"]),
            "outputEqualsTarget": evaluation["outputEqualsTarget"],
            "toktext": toks,
            "toknll": nlls,
            "stabilitySimilarities": [],
            "stability": 1.0,
            "kept": False,
        }
        state["points"].append(point)
        state["explicitDone"] = True
        log(f"[readable] explicit baseline: |p|={point['length']} sim={point['similarity']:.4f}")
    else:
        raise ReadableRunError(f"unknown op {op!r}")


def _build_artifact(state, config, spec) -> dict:
    budgets = state["budgets"]
    points = state["points"]
    if len(points) != len(budgets) + 1:
        raise ReadableRunError("artifact requires one point per budget plus the explicit baseline")
    stripped = [{key: value for key, value in point.items() if key != "kept"} for point in points]
    kept = set(derive_kept_indices(stripped))
    final_points = []
    for index, point in enumerate(points):
        entry = dict(point)
        entry["kept"] = index in kept
        final_points.append(entry)

    stopped_at = utc_now()
    wall_clock = round(_recorded_total(state), 1)
    token_count = state["target"]["tokenCount"]
    doc = {
        "schema": READABLE_SCHEMA,
        "tool": dict(TOOL),
        "createdAt": stopped_at,
        "instance": config.label,
        "configDigest": config.digest,
        "target": dict(state["target"]),
        "model": dict(state["model"]),
        "metric": {
            "kind": config.readable.metric_kind,
            "model": config.readable.metric_model,
            "secondary": dict(METRIC_SECONDARY),
        },
        "procedure": {
            "entrypoint": "python -m search.compare.readable",
            "budgets": list(budgets),
            "candidatesPerBudget": config.readable.candidates_per_budget,
            "refineSteps": config.readable.refine_steps,
            "stabilityRuns": config.readable.stability_runs,
            "stabilityTemperature": config.readable.stability_temperature,
            "proposerSeed": config.readable.proposer_seed,
            "generation": {
                "temperature": 0.0,
                "maxOutNonExplicit": int(token_count * 1.6) + 32,
                "maxOutExplicit": int(token_count * 1.4) + 32,
                "template": (
                    "apply_chat_template([{role: user, content: prompt}], "
                    "add_generation_prompt=True, enable_thinking=False, tokenize=False); "
                    "output postprocessing: strip <think> blocks and whitespace"
                ),
            },
            "proposeTemperature": PROPOSE_TEMPERATURE,
            "compressTemperature": COMPRESS_TEMPERATURE,
            "refineTemperature": REFINE_TEMPERATURE,
            "explicitWrapper": config.explicit_wrapper,
            "rngSeeded": True,
            "declaredDifferences": list(DECLARED_DIFFERENCES),
        },
        "environment": dict(state["environment"]),
        "startedAt": state["createdAt"],
        "stoppedAt": stopped_at,
        "wallClockSeconds": wall_clock,
        "stoppedBy": "complete",
        "evaluations": list(state["evaluations"]),
        "points": final_points,
        "result": {
            "complete": True,
            "evaluations": len(state["evaluations"]),
            "points": len(final_points),
        },
    }
    return doc


def run_target(config, spec, run_dir, *, max_seconds=None, log=print) -> int:
    """Run or resume the readable side for one target. See module docstring."""
    run_dir = Path(run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)
    state_path = run_dir / "readable-state.json"
    artifact_path = run_dir / "readable.json"

    if artifact_path.exists():
        doc = read_json(artifact_path)
        errors = verify_readable(doc)
        if errors:
            raise ReadableRunError(f"existing artifact fails verification: {errors[:3]}")
        if doc.get("configDigest") != config.digest or doc.get("instance") != config.label:
            raise ReadableRunError(
                "refusing to report completion: the existing artifact belongs to a different declaration"
            )
        log(f"readable run already complete: {artifact_path}")
        return 0

    budgets = sorted(config.readable.budgets, reverse=True)
    limits = config.envelope_seconds + ENVELOPE_SLACK_SECONDS

    state = read_json(state_path) if state_path.exists() else None
    if state is not None:
        _validate_state(state, config, spec)
        if state.get("phase") == "complete":
            raise ReadableRunError("readable state is complete but the artifact is missing")
        if state.get("phase") == "envelope_exceeded":
            log("readable state records an exceeded envelope; this comparison cannot be archived")
            return 1

    log(f"loading pinned model {config.repo}@{config.revision[:12]}…")
    from search.miniprompt import gcg  # lazy: pulls in the MLX execution path

    model, tokenizer, model_meta = gcg.load_pinned(config.repo, config.revision, config.weights_digest)
    theta = Theta(model, tokenizer, model_meta)
    metric = Metric(config.readable.metric_model)
    environment = environment_metadata()

    if state is None:
        target_ids, target_rendering = gcg.target_token_ids(tokenizer, spec.text)
        now = utc_now()
        state = {
            "schema": STATE_SCHEMA,
            "createdAt": now,
            "updatedAt": now,
            "instance": config.label,
            "config": config.to_canonical(),
            "configDigest": config.digest,
            "target": {
                "key": spec.key,
                "text": spec.text,
                "tokenIds": target_ids,
                "tokenCount": len(target_ids),
                "rendering": target_rendering,
            },
            "model": dict(model_meta),
            "environment": environment,
            "budgets": budgets,
            "budgetIndex": 0,
            "budgetPhase": "propose" if budgets else "explicit",
            "proc": _proc_reset(),
            "currentBest": None,
            "carryPrompt": None,
            "evaluations": [],
            "points": [],
            "explicitEvalDone": False,
            "explicitDone": False,
            "explicitEvaluationIndex": None,
            "recordedSeconds": {"proposal": 0.0, "evaluation": 0.0, "scoring": 0.0},
            "phase": "running",
        }
        write_json_atomic(state_path, state)
        log(f"target {spec.text!r} -> {len(target_ids)} token(s): {target_ids}")
    else:
        if state["model"] != model_meta:
            raise ReadableRunError("readable state model identity differs from the freshly loaded pinned model")

    deadline = None if max_seconds is None else time.monotonic() + float(max_seconds)

    while True:
        total = _recorded_total(state)
        if total > limits:
            state["phase"] = "envelope_exceeded"
            state["updatedAt"] = utc_now()
            write_json_atomic(state_path, state)
            log(f"readable envelope exceeded ({total:.1f}s > {limits}s); this comparison cannot be archived")
            return 1
        if deadline is not None and time.monotonic() > deadline:
            state["updatedAt"] = utc_now()
            write_json_atomic(state_path, state)
            log("readable time budget reached; re-run the same command to resume")
            return 3

        op = _pick_op(state, budgets, config)
        if op == "finalize":
            doc = _build_artifact(state, config, spec)
            if doc["wallClockSeconds"] > limits:
                state["phase"] = "envelope_exceeded"
                state["updatedAt"] = utc_now()
                write_json_atomic(state_path, state)
                log("readable envelope exceeded at completion; this comparison cannot be archived")
                return 1
            errors = verify_readable(doc)
            if errors:
                # never archive an inconsistent artifact: fail closed before writing
                raise ReadableRunError(f"the built artifact failed self-verification: {errors[:3]}")
            write_json_atomic(artifact_path, doc)
            state["phase"] = "complete"
            state["updatedAt"] = utc_now()
            write_json_atomic(state_path, state)
            log(f"readable.json written: {artifact_path} ({len(doc['evaluations'])} evaluations)")
            return 0

        _do_op(op, state, config, spec, theta, metric, log=log)
        state["updatedAt"] = utc_now()
        write_json_atomic(state_path, state)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m search.compare.readable",
        description="Readable-side runner for matched-budget comparison instances (needs the pinned MLX venv).",
    )
    parser.add_argument("--instance", required=True, help="declared comparison instance name")
    parser.add_argument("--target-key", required=True, help="declared target key within the instance")
    parser.add_argument("--run-dir", required=True, help="instance directory (readable-state.json + readable.json)")
    parser.add_argument(
        "--max-seconds",
        type=float,
        default=None,
        help="pause after this many seconds; re-run the same command to resume",
    )
    args = parser.parse_args(argv)

    from . import fixtures

    config = fixtures.instance(args.instance)
    spec = next((target for target in config.targets if target.key == args.target_key), None)
    if spec is None:
        known = ", ".join(target.key for target in config.targets)
        print(f"FAIL: unknown target key {args.target_key!r}; known: {known}")
        return 2
    try:
        return run_target(config, spec, args.run_dir, max_seconds=args.max_seconds)
    except ReadableRunError as exc:
        print(f"FAIL: {exc}")
        return 1


if __name__ == "__main__":
    import sys

    sys.exit(main())
