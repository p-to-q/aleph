from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .schema_validation import load_schema, validate


REPO_ROOT = Path(__file__).resolve().parents[2]


def _ci(value: dict[str, float] | None) -> str:
    if value is None:
        return "n/a"
    return f"{value['low']}-{value['high']}"


def _num(value: Any) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, float):
        return f"{value:.6f}".rstrip("0").rstrip(".")
    return str(value)


def load_result(result_path: Path) -> dict[str, Any]:
    result = json.loads(result_path.read_text(encoding="utf-8"))
    validate(result, load_schema(REPO_ROOT / "schemas/aleph-bench-result.schema.json"))
    return result


def model_summary_table(result: dict[str, Any]) -> str:
    lines = [
        "| Model | Evidence | AURC | 95% CI | ECL@tau | 95% CI | Coverage@tau | Elicit@k | Leakage hits |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for model in result["models"]:
        lines.append(
            " | ".join(
                [
                    f"| {model['model']}",
                    model["evidenceMode"],
                    _num(model["aurc"]),
                    _ci(model["aurcCi95"]),
                    _num(model["eclAtTau"]),
                    _ci(model["eclAtTauCi95"]),
                    _num(model["coverageAtTau"]),
                    _num(model["elicitAtK"]),
                    f"{_num(model['leakageHitRate'])} |",
                ]
            )
        )
    return "\n".join(lines)


def per_item_table(result: dict[str, Any]) -> str:
    models = [model["model"] for model in result["models"]]
    by_item: dict[str, dict[str, dict[str, Any]]] = {}
    for run in result["itemRuns"]:
        by_item.setdefault(run["itemId"], {})[run["model"]] = run["metrics"]

    header = "| Item | " + " | ".join(models) + " |"
    align = "|---|" + "|".join("---:" for _ in models) + "|"
    lines = [header, align]
    for item_id in sorted(by_item):
        cells = []
        for model in models:
            metrics = by_item[item_id][model]
            cells.append(f"{metrics['aurc']:.3f} / {metrics['eclAtTau']}")
        lines.append(f"| {item_id} | " + " | ".join(cells) + " |")
    return "\n".join(lines)


def render_markdown_report(result: dict[str, Any]) -> str:
    evidence_modes = sorted({model["evidenceMode"] for model in result["models"]})
    lines = [
        "# Aleph-Bench Result Report",
        "",
        f"- Result id: `{result['id']}`",
        f"- Track: `{result['track']}`",
        f"- Split: `{result['split']}`",
        f"- Stratum: `{result['stratum']}`",
        f"- Seed: `{result['seed']}`",
        f"- Tau: `{result['tau']}`",
        f"- K: `{result['k']}`",
        f"- Evidence modes: `{', '.join(evidence_modes)}`",
        "",
        "Lower AURC and ECL are better. This report is generated from the result JSON; it does not add evidence beyond that file.",
        "",
        "## Model Summary",
        "",
        model_summary_table(result),
        "",
        "## Per-Item Receipt",
        "",
        "Cells are `AURC / ECL@tau`.",
        "",
        per_item_table(result),
        "",
    ]
    return "\n".join(lines)


def render_report_file(result_path: Path) -> str:
    return render_markdown_report(load_result(result_path))
