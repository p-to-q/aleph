from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from .frozen_ladder import DEFAULT_RERUNS, load_items, stable_dataset_path
from .leakage_gate import DEFAULT_THRESHOLDS, evaluate_leakage
from .schema_validation import SchemaValidationError, load_schema, validate


REPO_ROOT = Path(__file__).resolve().parents[2]
HOSTED_REQUIRED_ENV = ["ALEPH_CUSTOM_API_BASE_URL", "ALEPH_CUSTOM_API_KEY"]


def model_readiness(model: str) -> dict[str, Any]:
    if model.startswith("mock-"):
        return {
            "model": model,
            "evidenceMode": "mock",
            "status": "ready",
            "missingEnv": [],
        }
    if model.startswith("hosted:"):
        missing = [name for name in HOSTED_REQUIRED_ENV if not os.environ.get(name)]
        return {
            "model": model.removeprefix("hosted:"),
            "evidenceMode": "black_box",
            "status": "ready" if not missing else "blocked",
            "missingEnv": missing,
        }
    return {
        "model": model,
        "evidenceMode": "unknown",
        "status": "blocked",
        "missingEnv": [],
        "error": "unsupported model id; use mock-* or hosted:<model>",
    }


def preflight(
    *,
    data_dir: Path,
    models: list[str],
    reruns: int = DEFAULT_RERUNS,
    thresholds: dict[str, float | int] | None = None,
) -> dict[str, Any]:
    active_thresholds = dict(DEFAULT_THRESHOLDS if thresholds is None else thresholds)
    item_schema = load_schema(REPO_ROOT / "schemas/aleph-bench-item.schema.json")
    items = load_items(data_dir)
    errors: list[str] = []
    leakage_by_rung = {"0": 0, "1": 0, "2": 0, "3": 0}
    prompt_count = 0
    disqualified_count = 0

    for item in items:
        try:
            validate(item, item_schema)
        except SchemaValidationError as exc:
            errors.append(f"{item.get('id', '<unknown>')}: {exc}")
            continue
        target = item["target"]["text"]
        for ladder in item["frozenLadder"]:
            prompt_count += 1
            gate = evaluate_leakage(ladder["prompt"], target, active_thresholds)
            if gate.disqualified:
                disqualified_count += 1
                leakage_by_rung[str(ladder["rung"])] += 1

    model_rows = [model_readiness(model) for model in models]
    # Current M0 adapters use deterministic temperature=0, so effective reruns
    # are one generation per non-leaking prompt. Keep configuredReruns visible.
    non_leaking_prompt_count = prompt_count - disqualified_count
    estimated_generations = non_leaking_prompt_count * len(models)
    blocked_models = [row for row in model_rows if row["status"] != "ready"]
    status = "ready" if not errors and not blocked_models else "blocked"
    return {
        "status": status,
        "datasetPath": stable_dataset_path(data_dir),
        "itemCount": len(items),
        "promptCount": prompt_count,
        "disqualifiedPromptCount": disqualified_count,
        "nonLeakingPromptCount": non_leaking_prompt_count,
        "leakageByRung": leakage_by_rung,
        "configuredReruns": reruns,
        "effectiveReruns": 1,
        "estimatedGenerations": estimated_generations,
        "models": model_rows,
        "errors": errors,
    }


def format_preflight(report: dict[str, Any]) -> str:
    lines = [
        f"status: {report['status']}",
        f"dataset: {report['datasetPath']}",
        f"items: {report['itemCount']}",
        f"prompts: {report['promptCount']} ({report['nonLeakingPromptCount']} non-leaking, {report['disqualifiedPromptCount']} gated)",
        f"leakage by rung: {json.dumps(report['leakageByRung'], sort_keys=True)}",
        f"estimated generations: {report['estimatedGenerations']} (effective reruns: {report['effectiveReruns']})",
    ]
    for row in report["models"]:
        suffix = ""
        if row.get("missingEnv"):
            suffix = f" missing env: {', '.join(row['missingEnv'])}"
        if row.get("error"):
            suffix = f" error: {row['error']}"
        lines.append(f"model {row['model']} [{row['evidenceMode']}]: {row['status']}{suffix}")
    for error in report["errors"]:
        lines.append(f"error: {error}")
    return "\n".join(lines)
