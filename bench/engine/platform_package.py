from __future__ import annotations

import csv
import hashlib
import io
import json
from pathlib import Path
from typing import Any

from .frozen_ladder import load_items, stable_dataset_path
from .leakage_gate import DEFAULT_THRESHOLDS, evaluate_leakage
from .metrics import token_count
from .schema_validation import load_schema, validate


REPO_ROOT = Path(__file__).resolve().parents[2]
FIXED_CREATED_AT = "2026-06-03T00:00:00Z"
PACKAGE_ID = "aleph-bench-m0-mock-platform-package"
DEFAULT_PACKAGE_DIR = REPO_ROOT / "bench/results/platform/m0-mock"
KAGGLE_ID = "p-to-q/aleph-bench-m0"
HF_ID = "p-to-q/aleph-bench-m0"


def _json_bytes(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _text_bytes(value: str) -> bytes:
    return value.encode("utf-8")


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _csv_bytes(rows: list[dict[str, Any]], fieldnames: list[str]) -> bytes:
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({name: row.get(name, "") for name in fieldnames})
    return buffer.getvalue().encode("utf-8")


def _jsonl_bytes(rows: list[dict[str, Any]]) -> bytes:
    return "\n".join(json.dumps(row, sort_keys=True) for row in rows).encode("utf-8") + b"\n"


def _relative(path: Path) -> str:
    return stable_dataset_path(path)


def _hf_readme() -> str:
    return """---
pretty_name: Aleph-Bench M0
language:
- en
license: cc0-1.0
size_categories:
- n<1K
task_categories:
- text-generation
tags:
- benchmark
- prompt-compression
- reverse-prompt-search
- synthetic
- aleph-bench
configs:
- config_name: public-s2
  data_files:
  - split: test
    path: data/public_s2_items.jsonl
---

# Aleph-Bench M0

Aleph-Bench M0 is a small frozen-ladder benchmark seed set for comparing how much non-leaking prompt coordinate length a model needs to reproduce synthetic target outputs.

This package is platform-ready seed data and mock pipeline evidence. It is not a real model leaderboard. The checked-in model rows are deterministic mock adapters used to prove the evaluation pipeline, schemas, leakage gate, metrics, bootstrap confidence intervals, reproducibility checks, and evidence packaging.

## Contents

- `data/public_s2_items.jsonl`: 30 S2 compositional BenchItems.
- `data/public_s2_prompts.jsonl`: 240 frozen-ladder prompt rows, including gated explicit reconstruction anchors.
- `data/submission_format.csv`: community benchmark submission shape for prompt outputs.
- `evidence/m0-first-run.json`: deterministic three-model mock BenchResult.
- `evidence/m0-report.md`: generated tables from the mock result JSON.
- `evidence/m0-audit.json`: M0 acceptance-gate receipt.
- `schemas/`: JSON schemas for validating benchmark artifacts.
- `croissant.json`: cross-platform ML dataset metadata.
- `dataset-metadata.json`: Kaggle Dataset metadata.

## Evaluation

Leakage is a gate, not a penalty. Explicit reconstruction prompts are retained as right-endpoint anchors and excluded from compression metrics when gated. The headline score is AURC, the area under the monotone non-leaking rate-distortion staircase; lower is better. ECL@tau and Elicit@k are reported as secondary metrics.

Run validation from the Aleph repository root:

```bash
./aleph-bench verify --audit bench/results/m0-audit.json --bundle bench/results/m0-bundle.json
./aleph-bench package --check bench/results/platform/m0-mock/package-manifest.json
```

Hosted black-box results require server-side OpenAI-compatible credentials and should produce their own result, manifest, report, and evidence note. Black-box rows report generated text behavior only; they do not report logits, token NLL, or white-box observations.

## Responsible Use

The targets are rule-generated synthetic English strings with a shared canary GUID stored as metadata, not as target text. The package is meant for benchmark procedure review and community reproduction, not for claims about globally shortest prompts or real model ranking until hosted black-box rows are produced.
"""


def _evaluation_protocol() -> str:
    return """# Aleph-Bench M0 Platform Evaluation Protocol

This package is ready to publish as a Hugging Face Dataset or Kaggle Dataset. It is also ready for a community benchmark dry run because it includes the seed data, prompt rows, schemas, mock evidence, and verification commands.

## Evidence Boundary

- The included model rows are deterministic mock evidence.
- They prove the benchmark pipeline, not model quality.
- Hosted black-box rows must use the same S2 items, frozen ladder, leakage thresholds, tau, k, and AURC/ECL/Elicit definitions.
- Do not report logits, token NLL, bits, or white-box claims for hosted black-box rows.

## Submission Shape

Use `data/submission_format.csv` as the public output shape:

```text
row_id,model_id,item_id,prompt_id,output_text
```

`prompt_id` must refer to a non-leaking prompt from `data/public_s2_prompts.jsonl`. Gated explicit reconstruction prompts are present for auditability but should not be submitted as compression candidates.

## Local Verification

From the Aleph repository root:

```bash
./aleph-bench verify --audit bench/results/m0-audit.json --bundle bench/results/m0-bundle.json
./aleph-bench package --check bench/results/platform/m0-mock/package-manifest.json
npm run lint
npm run test
```

## Hosted Evidence Upgrade

Before replacing the mock evidence note with real black-box rows:

```bash
./aleph-bench doctor --model hosted:model-a,hosted:model-b,hosted:model-c
./aleph-bench manifest --model hosted:model-a,hosted:model-b,hosted:model-c --out bench/results/m0-hosted-manifest.json
./aleph-bench run --track F --model hosted:model-a,hosted:model-b,hosted:model-c --split public --seed 0 --cache-dir .cache/aleph-bench/m0-hosted --out bench/results/m0-hosted-run.json
./aleph-bench verify --result bench/results/m0-hosted-run.json --manifest bench/results/m0-hosted-manifest.json
./aleph-bench report --result bench/results/m0-hosted-run.json --out bench/results/m0-hosted-report.md
```
"""


def _kaggle_metadata() -> dict[str, Any]:
    return {
        "title": "Aleph-Bench M0",
        "id": KAGGLE_ID,
        "subtitle": "Frozen-ladder prompt-compression seed benchmark with mock pipeline evidence",
        "description": (
            "Aleph-Bench M0 contains 30 rule-generated S2 compositional targets, "
            "frozen-ladder prompts, JSON schemas, and deterministic mock evidence. "
            "It is a benchmark procedure package, not a real model leaderboard."
        ),
        "isPrivate": False,
        "licenses": [{"name": "CC0-1.0"}],
        "keywords": [
            "benchmark",
            "prompt-compression",
            "reverse-prompt-search",
            "synthetic-data",
            "llm-evaluation",
        ],
    }


def _croissant_metadata(artifact_names: list[str]) -> dict[str, Any]:
    distributions = [
        {
            "@type": "cr:FileObject",
            "@id": name,
            "name": name,
            "contentUrl": name,
            "encodingFormat": _encoding_for(name),
        }
        for name in artifact_names
        if name.startswith("data/") or name.startswith("schemas/") or name.startswith("evidence/")
    ]
    return {
        "@context": {
            "@language": "en",
            "sc": "https://schema.org/",
            "cr": "http://mlcommons.org/croissant/",
            "dct": "http://purl.org/dc/terms/",
        },
        "@type": "sc:Dataset",
        "dct:conformsTo": "http://mlcommons.org/croissant/1.1",
        "name": "Aleph-Bench M0",
        "description": (
            "A frozen-ladder prompt-compression benchmark seed package with 30 S2 "
            "synthetic targets, schemas, and deterministic mock pipeline evidence."
        ),
        "url": f"https://huggingface.co/datasets/{HF_ID}",
        "sameAs": [f"https://www.kaggle.com/datasets/{KAGGLE_ID}"],
        "version": "m0",
        "dateCreated": "2026-06-03",
        "datePublished": "2026-06-03",
        "creator": {"@type": "sc:Organization", "name": "p-to-q"},
        "publisher": {"@type": "sc:Organization", "name": "p-to-q"},
        "license": "https://spdx.org/licenses/CC0-1.0.html",
        "sdLicense": "https://spdx.org/licenses/CC0-1.0.html",
        "inLanguage": ["en"],
        "keywords": [
            "benchmark",
            "prompt compression",
            "reverse prompt search",
            "synthetic data",
            "LLM evaluation",
        ],
        "isLiveDataset": False,
        "distribution": distributions,
        "recordSet": [
            {
                "@type": "cr:RecordSet",
                "@id": "public_s2_items",
                "name": "public_s2_items",
                "description": "Thirty public S2 compositional BenchItems.",
                "data": [{"source": {"fileObject": "data/public_s2_items.jsonl"}}],
            },
            {
                "@type": "cr:RecordSet",
                "@id": "public_s2_prompts",
                "name": "public_s2_prompts",
                "description": "Frozen-ladder prompt rows and leakage-gate measurements.",
                "data": [{"source": {"fileObject": "data/public_s2_prompts.jsonl"}}],
            },
        ],
    }


def _encoding_for(name: str) -> str:
    if name.endswith(".jsonl"):
        return "application/jsonl"
    if name.endswith(".json"):
        return "application/json"
    if name.endswith(".csv"):
        return "text/csv"
    if name.endswith(".md"):
        return "text/markdown"
    return "text/plain"


def _prompt_rows(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in items:
        family = item["provenance"]["parameters"]["family"]
        target = item["target"]["text"]
        for ladder in item["frozenLadder"]:
            gate = evaluate_leakage(ladder["prompt"], target, DEFAULT_THRESHOLDS)
            rows.append(
                {
                    "item_id": item["id"],
                    "target_label": item["target"].get("label"),
                    "stratum": item["stratum"],
                    "language": item["language"],
                    "family": family,
                    "metric_class": item["metricClass"],
                    "prompt_id": ladder["id"],
                    "rung": ladder["rung"],
                    "paraphrase": ladder["paraphrase"],
                    "label": ladder["label"],
                    "expected_leakage": ladder.get("expectedLeakage"),
                    "tokens": token_count(ladder["prompt"]),
                    "disqualified": gate.disqualified,
                    "lcs_ratio": gate.lcsRatio,
                    "trigram_overlap": gate.trigramOverlap,
                    "verbatim_span_tokens": gate.verbatimSpanTokens,
                    "prompt": ladder["prompt"],
                }
            )
    return rows


def _submission_rows(items: list[dict[str, Any]]) -> list[dict[str, str]]:
    rows = []
    for item in items:
        for ladder in item["frozenLadder"]:
            if ladder["rung"] == 0:
                continue
            rows.append(
                {
                    "row_id": f"{item['id']}:{ladder['id']}",
                    "model_id": "",
                    "item_id": item["id"],
                    "prompt_id": ladder["id"],
                    "output_text": "",
                }
            )
    return rows


def _model_rows(result: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "model": row["model"],
            "evidence_mode": row["evidenceMode"],
            "item_count": row["itemCount"],
            "aurc": row["aurc"],
            "aurc_ci95_low": row["aurcCi95"]["low"],
            "aurc_ci95_high": row["aurcCi95"]["high"],
            "ecl_at_tau": row["eclAtTau"],
            "coverage_at_tau": row["coverageAtTau"],
            "elicit_at_k": row["elicitAtK"],
            "leakage_hit_rate": row["leakageHitRate"],
        }
        for row in result["models"]
    ]


def _item_metric_rows(result: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for run in result["itemRuns"]:
        rows.append(
            {
                "item_id": run["itemId"],
                "model": run["model"],
                "aurc": run["metrics"]["aurc"],
                "ecl_at_tau": run["metrics"]["eclAtTau"],
                "elicit_at_k": run["metrics"]["elicitAtK"],
                "leakage_hit_rate": run["metrics"]["leakageHitRate"],
            }
        )
    return rows


def _build_artifact_bytes() -> dict[str, bytes]:
    data_dir = REPO_ROOT / "bench/data/public/s2"
    result_path = REPO_ROOT / "bench/results/m0-first-run.json"
    items = load_items(data_dir)
    result = _load_json(result_path)
    artifact_bytes: dict[str, bytes] = {
        "README.md": _text_bytes(_hf_readme()),
        "EVALUATION.md": _text_bytes(_evaluation_protocol()),
        "dataset-metadata.json": _json_bytes(_kaggle_metadata()),
        "data/public_s2_items.jsonl": _jsonl_bytes(items),
        "data/public_s2_prompts.jsonl": _jsonl_bytes(_prompt_rows(items)),
        "data/submission_format.csv": _csv_bytes(
            _submission_rows(items),
            ["row_id", "model_id", "item_id", "prompt_id", "output_text"],
        ),
        "data/mock_model_summary.csv": _csv_bytes(
            _model_rows(result),
            [
                "model",
                "evidence_mode",
                "item_count",
                "aurc",
                "aurc_ci95_low",
                "aurc_ci95_high",
                "ecl_at_tau",
                "coverage_at_tau",
                "elicit_at_k",
                "leakage_hit_rate",
            ],
        ),
        "data/mock_item_metrics.csv": _csv_bytes(
            _item_metric_rows(result),
            ["item_id", "model", "aurc", "ecl_at_tau", "elicit_at_k", "leakage_hit_rate"],
        ),
    }
    for source, dest in [
        ("schemas/aleph-bench-item.schema.json", "schemas/aleph-bench-item.schema.json"),
        ("schemas/aleph-bench-result.schema.json", "schemas/aleph-bench-result.schema.json"),
        ("schemas/aleph-bench-manifest.schema.json", "schemas/aleph-bench-manifest.schema.json"),
        ("schemas/aleph-bench-audit.schema.json", "schemas/aleph-bench-audit.schema.json"),
        ("schemas/aleph-bench-bundle.schema.json", "schemas/aleph-bench-bundle.schema.json"),
        ("schemas/aleph-bench-platform-package.schema.json", "schemas/aleph-bench-platform-package.schema.json"),
        ("bench/results/m0-first-run.json", "evidence/m0-first-run.json"),
        ("bench/results/m0-call-manifest.json", "evidence/m0-call-manifest.json"),
        ("bench/results/m0-audit.json", "evidence/m0-audit.json"),
        ("bench/results/m0-bundle.json", "evidence/m0-bundle.json"),
        ("bench/results/m0-report.md", "evidence/m0-report.md"),
        ("docs/benchmark/m0-evidence.md", "evidence/m0-evidence.md"),
        ("docs/benchmark/hosted-m0-runbook.md", "docs/hosted-m0-runbook.md"),
    ]:
        artifact_bytes[dest] = (REPO_ROOT / source).read_bytes()
    artifact_bytes["croissant.json"] = _json_bytes(_croissant_metadata(sorted(artifact_bytes)))
    return artifact_bytes


def _artifact_rows(artifact_bytes: dict[str, bytes]) -> list[dict[str, Any]]:
    rows = []
    for path in sorted(artifact_bytes):
        role = path.split("/", 1)[0] if "/" in path else "metadata"
        rows.append(
            {
                "role": role,
                "path": path,
                "sha256": _sha256(artifact_bytes[path]),
                "bytes": len(artifact_bytes[path]),
                "encodingFormat": _encoding_for(path),
                "note": _note_for(path),
            }
        )
    return rows


def _note_for(path: str) -> str:
    if path == "README.md":
        return "Hugging Face dataset card with YAML metadata."
    if path == "dataset-metadata.json":
        return "Kaggle Dataset metadata."
    if path == "croissant.json":
        return "Croissant JSON-LD metadata for cross-platform discovery."
    if path.startswith("data/"):
        return "Platform-facing benchmark data table."
    if path.startswith("schemas/"):
        return "JSON Schema validation artifact."
    if path.startswith("evidence/"):
        return "Mock evidence artifact or generated evidence note."
    return "Platform package documentation."


def _checksums_text(artifacts: list[dict[str, Any]]) -> bytes:
    lines = [f"{artifact['sha256']}  {artifact['path']}" for artifact in artifacts]
    return ("\n".join(lines) + "\n").encode("utf-8")


def expected_platform_manifest(out_dir: Path) -> tuple[dict[str, Any], dict[str, bytes], bytes]:
    artifact_bytes = _build_artifact_bytes()
    artifacts = _artifact_rows(artifact_bytes)
    manifest = {
        "id": PACKAGE_ID,
        "createdAt": FIXED_CREATED_AT,
        "packageKind": "platform_release",
        "evidenceMode": "mock",
        "root": stable_dataset_path(out_dir),
        "targetPlatforms": ["huggingface_dataset", "kaggle_dataset", "croissant"],
        "kaggleDatasetId": KAGGLE_ID,
        "huggingFaceDatasetId": HF_ID,
        "artifacts": artifacts,
        "validationCommands": [
            "./aleph-bench verify --audit bench/results/m0-audit.json --bundle bench/results/m0-bundle.json",
            f"./aleph-bench package --check {stable_dataset_path(out_dir / 'package-manifest.json')}",
            "npm run lint",
            "npm run test",
        ],
        "notes": [
            "This package is platform-ready seed data and deterministic mock pipeline evidence.",
            "It is not a real model leaderboard.",
            "Hosted black-box results must produce their own result, manifest, report, and evidence note.",
        ],
    }
    checksum_bytes = _checksums_text(artifacts)
    return manifest, artifact_bytes, checksum_bytes


def write_platform_package(out_dir: Path) -> dict[str, Any]:
    manifest, artifact_bytes, checksum_bytes = expected_platform_manifest(out_dir)
    schema = load_schema(REPO_ROOT / "schemas/aleph-bench-platform-package.schema.json")
    validate(manifest, schema)
    for relative_path, content in artifact_bytes.items():
        path = out_dir / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    (out_dir / "checksums.sha256").write_bytes(checksum_bytes)
    (out_dir / "package-manifest.json").write_bytes(_json_bytes(manifest))
    return manifest


def check_platform_package(manifest_path: Path) -> dict[str, Any]:
    errors: list[str] = []
    schema = load_schema(REPO_ROOT / "schemas/aleph-bench-platform-package.schema.json")
    manifest = _load_json(manifest_path)
    try:
        validate(manifest, schema)
    except Exception as exc:
        errors.append(f"{manifest_path}: {exc}")
    out_dir = manifest_path.parent
    expected, expected_bytes, expected_checksums = expected_platform_manifest(out_dir)
    if manifest != expected:
        errors.append("package manifest does not match current deterministic package contents")
    for artifact in expected["artifacts"]:
        path = out_dir / artifact["path"]
        if not path.exists():
            errors.append(f"missing artifact: {artifact['path']}")
            continue
        data = path.read_bytes()
        if _sha256(data) != artifact["sha256"] or len(data) != artifact["bytes"]:
            errors.append(f"artifact changed: {artifact['path']}")
        if data != expected_bytes[artifact["path"]]:
            errors.append(f"artifact content is stale: {artifact['path']}")
    checksums_path = out_dir / "checksums.sha256"
    if not checksums_path.exists():
        errors.append("missing checksums.sha256")
    elif checksums_path.read_bytes() != expected_checksums:
        errors.append("checksums.sha256 does not match current package artifacts")
    return {
        "status": "ok" if not errors else "failed",
        "packageManifest": stable_dataset_path(manifest_path),
        "artifactCount": len(expected["artifacts"]),
        "targetPlatforms": expected["targetPlatforms"],
        "errors": errors,
    }


def format_package_check(report: dict[str, Any]) -> str:
    lines = [
        f"status: {report['status']}",
        f"package: {report['packageManifest']}",
        f"artifacts: {report['artifactCount']}",
        f"target platforms: {', '.join(report['targetPlatforms'])}",
    ]
    for error in report["errors"]:
        lines.append(f"error: {error}")
    return "\n".join(lines)
