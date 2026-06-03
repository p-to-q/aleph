from __future__ import annotations

from pathlib import Path
from typing import Any

from .frozen_ladder import DEFAULT_RERUNS, load_items, stable_dataset_path
from .leakage_gate import DEFAULT_THRESHOLDS, evaluate_leakage
from .metrics import token_count
from .preflight import model_readiness


FIXED_CREATED_AT = "2026-06-03T00:00:00Z"


def build_manifest(
    *,
    data_dir: Path,
    models: list[str],
    split: str = "public",
    seed: int = 0,
    reruns: int = DEFAULT_RERUNS,
    thresholds: dict[str, float | int] | None = None,
) -> dict[str, Any]:
    active_thresholds = dict(DEFAULT_THRESHOLDS if thresholds is None else thresholds)
    items = load_items(data_dir)
    prompts: list[dict[str, Any]] = []
    gated_prompts: list[dict[str, Any]] = []

    for item in items:
        target = item["target"]["text"]
        for ladder in item["frozenLadder"]:
            gate = evaluate_leakage(ladder["prompt"], target, active_thresholds)
            row = {
                "itemId": item["id"],
                "targetLabel": item["target"].get("label"),
                "promptId": ladder["id"],
                "rung": ladder["rung"],
                "paraphrase": ladder["paraphrase"],
                "label": ladder["label"],
                "tokens": token_count(ladder["prompt"]),
                "leakageGate": gate.as_dict(),
            }
            if gate.disqualified:
                gated_prompts.append(row)
            else:
                prompts.append({**row, "prompt": ladder["prompt"]})

    model_rows = [model_readiness(model) for model in models]
    effective_reruns = 1
    return {
        "id": f"aleph-bench-m0-manifest-seed-{seed}",
        "createdAt": FIXED_CREATED_AT,
        "track": "F",
        "split": split,
        "seed": seed,
        "datasetPath": stable_dataset_path(data_dir),
        "itemCount": len(items),
        "modelCount": len(models),
        "models": model_rows,
        "configuredReruns": reruns,
        "effectiveReruns": effective_reruns,
        "promptCount": sum(len(item["frozenLadder"]) for item in items),
        "nonLeakingPromptCount": len(prompts),
        "gatedPromptCount": len(gated_prompts),
        "estimatedGenerations": len(prompts) * len(models) * effective_reruns,
        "leakageThresholds": active_thresholds,
        "prompts": prompts,
        "gatedPrompts": gated_prompts,
        "notes": [
            "Manifest lists only non-leaking prompts that would be sent to model adapters.",
            "Gated prompts are retained as IDs and leakage measurements, without prompt text.",
            "Manifest generation does not call any model and is not model evidence.",
        ],
    }
