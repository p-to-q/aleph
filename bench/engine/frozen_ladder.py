from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, pstdev, pvariance
from typing import Any

from .adapters import HostedBlackBoxAdapter, MockAdapter, ModelAdapter
from .leakage_gate import DEFAULT_THRESHOLDS, evaluate_leakage, leakage_score
from .metrics import (
    aurc,
    ecl_at_tau,
    elicit_at_k,
    fidelity,
    monotone_lower_envelope,
    summarize,
    token_count,
)
from .response_cache import ResponseCacheAdapter


DEFAULT_BOOTSTRAP_SAMPLES = 500
DEFAULT_RERUNS = 3
DEFAULT_TAU = 0.9
DEFAULT_K = 3
FIXED_CREATED_AT = "2026-06-03T00:00:00Z"
REPO_ROOT = Path(__file__).resolve().parents[2]


def stable_dataset_path(data_dir: Path) -> str:
    resolved = data_dir.resolve()
    try:
        return resolved.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return data_dir.as_posix()


def load_items(data_dir: Path, *, limit: int | None = None) -> list[dict[str, Any]]:
    items = [json.loads(path.read_text(encoding="utf-8")) for path in sorted(data_dir.glob("*.json"))]
    return items[:limit] if limit is not None else items


def adapter_for_model(model: str) -> ModelAdapter:
    if model.startswith("mock-"):
        return MockAdapter(model)
    if model.startswith("hosted:"):
        return HostedBlackBoxAdapter(model.removeprefix("hosted:"))
    raise ValueError(f"unsupported model id {model!r}; use mock-* or hosted:<model>")


def evaluate_item(
    item: dict[str, Any],
    adapter: ModelAdapter,
    *,
    seed: int,
    tau: float = DEFAULT_TAU,
    k: int = DEFAULT_K,
    reruns: int = DEFAULT_RERUNS,
    thresholds: dict[str, float | int] | None = None,
) -> dict[str, Any]:
    thresholds = dict(DEFAULT_THRESHOLDS if thresholds is None else thresholds)
    target = item["target"]["text"]
    explicit_tokens = max(token_count(item["frozenLadder"][0]["prompt"]), token_count(target), 1)
    configured_reruns = adapter.reruns(reruns)
    candidates: list[dict[str, Any]] = []
    measurements: list[dict[str, Any]] = []
    scored_points: list[dict[str, Any]] = []
    leakage_hits = 0

    for ladder in item["frozenLadder"]:
        prompt = ladder["prompt"]
        gate = evaluate_leakage(prompt, target, thresholds)
        leak = leakage_score(gate)
        if gate.disqualified:
            leakage_hits += 1
            output = ""
            fit = 0.0
            stable = 0.0
            fidelity_variance: float | None = None
            fidelity_stddev: float | None = None
            rerun_count = 0
            note = "Disqualified by leakage gate; excluded from compression metrics."
        else:
            outputs = [
                adapter.generate(prompt, item, ladder, seed=seed, rerun_index=rerun_index)
                for rerun_index in range(configured_reruns)
            ]
            fidelities = [fidelity(target, output, item["metricClass"]) for output in outputs]
            output = outputs[0]
            fit = round(mean(fidelities), 6)
            fidelity_variance = round(pvariance(fidelities), 6)
            fidelity_stddev = round(pstdev(fidelities), 6)
            rerun_count = len(fidelities)
            stable = 1.0 if len(fidelities) == 1 else round(max(0.0, 1.0 - fidelity_stddev), 6)
            note = f"{adapter.observation_mode} evidence; exact-class near misses use normalized edit distance."

        tokens = token_count(prompt)
        compression = round(max(0.0, min(1.0, 1.0 - tokens / explicit_tokens)), 6)
        measurement = {
            "promptId": ladder["id"],
            "rung": ladder["rung"],
            "paraphrase": ladder["paraphrase"],
            "tokens": tokens,
            "rerunCount": rerun_count,
            "fidelityMean": fit if not gate.disqualified else None,
            "fidelityVariance": fidelity_variance,
            "fidelityStdDev": fidelity_stddev,
            "disqualified": gate.disqualified,
            "leakageGate": gate.as_dict(),
        }
        candidate = {
            "id": ladder["id"],
            "label": ladder["label"],
            "prompt": prompt,
            "output": output,
            "tokens": tokens,
            "fit": fit,
            "stability": stable,
            "compression": compression,
            "leakage": leak,
            "note": note,
        }
        point = {
            **candidate,
            "itemId": item["id"],
            "model": adapter.model_id,
            "rung": ladder["rung"],
            "paraphrase": ladder["paraphrase"],
            "distortion": round(1.0 - fit, 6),
            "fidelity": fit,
            "rerunCount": rerun_count,
            "fidelityVariance": fidelity_variance,
            "fidelityStdDev": fidelity_stddev,
            "disqualified": gate.disqualified,
            "leakageGate": gate.as_dict(),
            "evidenceMode": adapter.observation_mode,
        }
        measurements.append(measurement)
        candidates.append(candidate)
        scored_points.append(point)

    frontier = monotone_lower_envelope(scored_points)
    frontier_ids = {point["id"]: index + 1 for index, point in enumerate(frontier)}
    for candidate in candidates:
        if candidate["id"] in frontier_ids:
            candidate["frontierRank"] = frontier_ids[candidate["id"]]
    for point in frontier:
        point["frontierRank"] = frontier_ids[point["id"]]

    selected = frontier[0]["id"] if frontier else candidates[0]["id"]
    non_leaking_points = [point for point in scored_points if not point["disqualified"]]
    item_aurc = aurc(frontier, explicit_tokens)
    item_ecl = ecl_at_tau(frontier, tau)
    item_elicit = elicit_at_k(non_leaking_points, tau, k)
    leakage_hit_rate = round(leakage_hits / len(item["frozenLadder"]), 6)
    aleph_run = {
        "id": f"bench-{item['id']}-{adapter.model_id}",
        "createdAt": FIXED_CREATED_AT,
        "target": item["target"],
        "config": {
            "model": adapter.model_id,
            "decoding": "temperature=0; max_tokens=512",
            "metric": item["metricClass"],
            "budget": {
                "candidates": len(item["frozenLadder"]),
                "maxPromptTokens": explicit_tokens,
                "repeatedSamples": configured_reruns,
            },
            "mode": "non_leaking",
        },
        "candidates": candidates,
        "selectedCandidateId": selected,
        "observations": {
            "mode": adapter.observation_mode,
            "evalSuite": [
                {
                    "name": "leakage gate",
                    "passed": leakage_hits >= 1,
                    "score": leakage_hit_rate,
                    "note": "Rung 0 is expected to be disqualified as the explicit reconstruction anchor.",
                },
                {
                    "name": f"Elicit@{k}",
                    "passed": item_elicit,
                    "score": 1.0 if item_elicit else 0.0,
                    "note": f"Threshold tau={tau}.",
                },
            ],
        },
    }
    return {
        "itemId": item["id"],
        "model": adapter.model_id,
        "alephRun": aleph_run,
        "measurements": measurements,
        "frontier": frontier,
        "metrics": {
            "aurc": item_aurc,
            "eclAtTau": item_ecl,
            "elicitAtK": item_elicit,
            "leakageHitRate": leakage_hit_rate,
        },
    }


def run_benchmark(
    *,
    data_dir: Path,
    models: list[str],
    split: str = "public",
    seed: int = 0,
    tau: float = DEFAULT_TAU,
    k: int = DEFAULT_K,
    reruns: int = DEFAULT_RERUNS,
    bootstrap_samples: int = DEFAULT_BOOTSTRAP_SAMPLES,
    limit: int | None = None,
    cache_dir: Path | None = None,
) -> dict[str, Any]:
    items = load_items(data_dir, limit=limit)
    if not items:
        raise RuntimeError(f"no BenchItems found in {data_dir}")
    canary = items[0]["canaryGuid"]
    item_runs: list[dict[str, Any]] = []
    summaries: list[dict[str, Any]] = []
    evidence_modes: list[str] = []

    for model_index, model in enumerate(models):
        adapter = adapter_for_model(model)
        if cache_dir is not None:
            adapter = ResponseCacheAdapter(adapter, cache_dir, seed=seed)
        evidence_modes.append(adapter.observation_mode)
        runs = [
            evaluate_item(item, adapter, seed=seed, tau=tau, k=k, reruns=reruns)
            for item in items
        ]
        item_runs.extend(runs)
        aurc_values = [run["metrics"]["aurc"] for run in runs]
        ecl_values = [run["metrics"]["eclAtTau"] for run in runs if run["metrics"]["eclAtTau"] is not None]
        elicit_values = [1.0 if run["metrics"]["elicitAtK"] else 0.0 for run in runs]
        leakage_values = [run["metrics"]["leakageHitRate"] for run in runs]
        aurc_mean, aurc_ci = summarize(
            aurc_values,
            seed=seed + 1000 + model_index,
            samples=bootstrap_samples,
        )
        ecl_mean, ecl_ci = summarize(
            [float(value) for value in ecl_values],
            seed=seed + 2000 + model_index,
            samples=bootstrap_samples,
        )
        elicit_mean, elicit_ci = summarize(
            elicit_values,
            seed=seed + 3000 + model_index,
            samples=bootstrap_samples,
        )
        summaries.append(
            {
                "model": adapter.model_id,
                "evidenceMode": adapter.observation_mode,
                "itemCount": len(runs),
                "aurc": aurc_mean,
                "aurcCi95": aurc_ci,
                "eclAtTau": ecl_mean,
                "eclAtTauCi95": ecl_ci,
                "coverageAtTau": round(len(ecl_values) / len(runs), 6),
                "elicitAtK": elicit_mean,
                "elicitAtKCi95": elicit_ci,
                "leakageHitRate": round(mean(leakage_values), 6),
            }
        )

    metric_classes = sorted({item["metricClass"] for item in items})
    return {
        "id": f"aleph-bench-m0-seed-{seed}",
        "createdAt": datetime.fromtimestamp(0, tz=timezone.utc).isoformat().replace("+00:00", "Z"),
        "track": "F",
        "split": split,
        "seed": seed,
        "stratum": "S2",
        "metricClasses": metric_classes,
        "tau": tau,
        "k": k,
        "canaryGuid": canary,
        "config": {
            "datasetPath": stable_dataset_path(data_dir),
            "decoding": "temperature=0 for deterministic mock; hosted adapter uses configured temperature",
            "evidenceModes": sorted(set(evidence_modes)),
            "leakageThresholds": dict(DEFAULT_THRESHOLDS),
            "bootstrapSamples": bootstrap_samples,
            "reruns": reruns,
        },
        "models": summaries,
        "itemRuns": item_runs,
        "notes": [
            "M0 checked-in result uses deterministic mock adapters; it is pipeline evidence, not a real model leaderboard.",
            "Leakage is a gate. Disqualified ladder prompts are excluded from AURC, ECL@tau, and Elicit@k.",
            "AURC is area under the non-leaking rate-distortion staircase; lower is better.",
        ],
    }
