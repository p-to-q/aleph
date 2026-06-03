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

ITEM_FIELDS = [
    ("item_id", "Bench item id.", "string"),
    ("stratum", "Benchmark stratum.", "string"),
    ("language", "Language code.", "string"),
    ("metric_class", "Primary metric class.", "string"),
    ("target_label", "Human-readable target label.", "string"),
    ("target_text", "Target output text.", "string"),
    ("family", "S2 generator family.", "string"),
    ("canary_guid", "Dataset-level contamination canary, kept out of target and prompt text.", "string"),
    ("license", "Item license.", "string"),
]

PROMPT_FIELDS = [
    ("item_id", "Bench item id.", "string"),
    ("prompt_id", "Frozen ladder prompt id.", "string"),
    ("rung", "Frozen ladder rung.", "integer"),
    ("paraphrase", "Paraphrase index within rung.", "integer"),
    ("label", "Rung label.", "string"),
    ("expected_leakage", "Expected leakage class.", "string"),
    ("tokens", "Regex token count.", "integer"),
    ("disqualified", "Whether the leakage gate disqualifies the prompt.", "boolean"),
    ("lcs_ratio", "Prompt-target LCS ratio.", "number"),
    ("trigram_overlap", "Target trigram overlap.", "number"),
    ("verbatim_span_tokens", "Longest verbatim token span.", "integer"),
    ("prompt", "Prompt text.", "string"),
]


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
- `data/public_s2_items.csv` and `data/public_s2_prompts.csv`: flat tables for Kaggle Dataset preview.
- `data/submission_format.csv`: community benchmark submission shape for prompt outputs.
- `evidence/m0-first-run.json`: deterministic three-model mock BenchResult.
- `evidence/m0-report.md`: generated tables from the mock result JSON.
- `evidence/m0-audit.json`: M0 acceptance-gate receipt.
- `schemas/`: JSON schemas for validating benchmark artifacts.
- `croissant.json`: cross-platform ML dataset metadata.
- `dataset-metadata.json`: Kaggle Dataset metadata.
- `huggingface/upload_dataset.py`: dry-run and optional upload helper for the Hugging Face Dataset repo.
- `kaggle/aleph_bench_m0_task.py`: Kaggle Community Benchmark scaffold using the `llm.prompt(...)` task shape.
- `kaggle/api_test_smoke.py`: local stub harness for the Kaggle API-test I/O contract.
- `PLATFORM_LAUNCH_CHECKLIST.md`: staged launch checklist separating prepared, blocked, and not-yet-run work.

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
python3 bench/results/platform/m0-mock/kaggle/api_test_smoke.py
python3 bench/results/platform/m0-mock/huggingface/upload_dataset.py --dry-run
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


def _platform_launch_checklist() -> str:
    return """# Aleph-Bench M0 Platform Launch Checklist

This checklist is the durable boundary between prepared package work and actual public platform launch. The checked-in M0 package is deterministic mock evidence plus launch scaffolding. It is not a hosted benchmark result.

## Current Status

| Stage | Status | Gate |
| --- | --- | --- |
| Local M0 evidence package | ready | `./aleph-bench package --check bench/results/platform/m0-mock/package-manifest.json` |
| Kaggle API-test preparation | ready | `python3 bench/results/platform/m0-mock/kaggle/api_test_smoke.py` reports 180 sendable prompts and 180 prompt calls |
| Hugging Face Dataset upload preparation | ready | `python3 bench/results/platform/m0-mock/huggingface/upload_dataset.py --dry-run` validates card, manifest, checksums, and upload shape |
| Hugging Face Dataset upload | blocked | requires `HF_TOKEN` and ownership/write access for `p-to-q/aleph-bench-m0` |
| Hugging Face benchmark or leaderboard surface | blocked | requires hosted black-box evidence or an explicit Space/Leaderboard app wired to real result rows |
| Kaggle Dataset upload | blocked | requires Kaggle account ownership for `p-to-q/aleph-bench-m0` |
| Kaggle Community Benchmark notebook run | blocked | requires approved Kaggle Benchmarks notebook/model access and final `%choose` selection |
| Hosted black-box leaderboard evidence | blocked | requires real model access plus new result, manifest, report, and evidence note |

## Hugging Face Path

1. Run local gates:

```bash
./aleph-bench package --check bench/results/platform/m0-mock/package-manifest.json
python3 bench/results/platform/m0-mock/huggingface/upload_dataset.py --dry-run
```

2. Confirm the target repo owner and visibility. The package is configured for `p-to-q/aleph-bench-m0` as a dataset repo.
3. Upload only after tokened access exists:

```bash
HF_TOKEN=... python3 bench/results/platform/m0-mock/huggingface/upload_dataset.py --execute --repo-id p-to-q/aleph-bench-m0
```

4. Post-upload checks:

- root `README.md` renders as a dataset card;
- `data/public_s2_items.jsonl` and `data/public_s2_prompts.jsonl` are visible as dataset files;
- `package-manifest.json` and `checksums.sha256` match this checked-in package;
- the page copy does not present deterministic mock rows as real model ranking.

## Kaggle Path

1. Upload or attach the package as a Kaggle Dataset using `dataset-metadata.json`.
2. Run `python3 kaggle/api_test_smoke.py` inside the attached package path.
3. In the approved Kaggle Benchmarks notebook, wire `aleph_bench_m0_task.py` to `kaggle-benchmarks` with `@kbench.task`, `llm.prompt(...)`, `.evaluate(llm=[...], evaluation_data=df)`, and final `%choose`.
4. Save the notebook version and attach generated task/run files before claiming a Kaggle benchmark launch.

## Evidence Upgrade Gate

Replace the mock evidence only after real hosted rows exist:

```bash
./aleph-bench doctor --model hosted:model-a,hosted:model-b,hosted:model-c
./aleph-bench manifest --model hosted:model-a,hosted:model-b,hosted:model-c --out bench/results/m0-hosted-manifest.json
./aleph-bench run --track F --model hosted:model-a,hosted:model-b,hosted:model-c --split public --seed 0 --cache-dir .cache/aleph-bench/m0-hosted --out bench/results/m0-hosted-run.json
./aleph-bench verify --result bench/results/m0-hosted-run.json --manifest bench/results/m0-hosted-manifest.json
./aleph-bench report --result bench/results/m0-hosted-run.json --out bench/results/m0-hosted-report.md
```
"""


def _hf_upload_readme() -> str:
    return """# Hugging Face Upload Preparation

This directory prepares the M0 package for a Hugging Face Dataset upload. It does not upload anything unless `upload_dataset.py --execute` is used with `HF_TOKEN`.

## Local Dry Run

From the Aleph repository root:

```bash
python3 bench/results/platform/m0-mock/huggingface/upload_dataset.py --dry-run
```

The dry run validates:

- root `README.md` has dataset-card front matter;
- `package-manifest.json` declares the Hugging Face Dataset target;
- every manifest artifact exists and matches its sha256/byte count;
- `checksums.sha256` matches the manifest artifact list;
- required data, schema, evidence, Kaggle, and Hugging Face preparation files are present.

## Actual Upload

After confirming repo ownership and token scope:

```bash
HF_TOKEN=... python3 bench/results/platform/m0-mock/huggingface/upload_dataset.py --execute --repo-id p-to-q/aleph-bench-m0
```

The script creates the dataset repo if needed, then uploads the package folder with `huggingface_hub.upload_folder`.

## Benchmark Boundary

The Hugging Face Dataset upload is a platform distribution step, not a real model leaderboard. A Hugging Face benchmark or leaderboard surface should be created only after hosted black-box rows exist, or as an explicitly labeled mock/demo Space that reads this dataset and refuses to rank models as real evidence.
"""


def _hf_upload_py() -> str:
    return '''"""Hugging Face Dataset upload preparation for Aleph-Bench M0.

Default mode is a local dry run. Real upload requires --execute and HF_TOKEN.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
from typing import Any


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REPO_ID = "p-to-q/aleph-bench-m0"
REQUIRED_FILES = [
    "README.md",
    "EVALUATION.md",
    "PLATFORM_LAUNCH_CHECKLIST.md",
    "package-manifest.json",
    "checksums.sha256",
    "croissant.json",
    "dataset-metadata.json",
    "data/public_s2_items.jsonl",
    "data/public_s2_prompts.jsonl",
    "data/public_s2_items.csv",
    "data/public_s2_prompts.csv",
    "data/submission_format.csv",
    "schemas/aleph-bench-result.schema.json",
    "evidence/m0-first-run.json",
    "evidence/m0-evidence.md",
    "kaggle/aleph_bench_m0_task.py",
    "kaggle/api_test_smoke.py",
    "huggingface/README.md",
    "huggingface/upload_dataset.py",
]


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def expected_checksums(manifest: dict[str, Any]) -> str:
    lines = [f"{artifact['sha256']}  {artifact['path']}" for artifact in manifest["artifacts"]]
    return "\\n".join(lines) + "\\n"


def validate_package(root: Path) -> dict[str, Any]:
    errors: list[str] = []
    manifest_path = root / "package-manifest.json"
    if not manifest_path.exists():
        errors.append("missing package-manifest.json")
        manifest: dict[str, Any] = {"artifacts": [], "targetPlatforms": []}
    else:
        manifest = load_json(manifest_path)

    for relative in REQUIRED_FILES:
        if not (root / relative).exists():
            errors.append(f"missing required file: {relative}")

    readme_path = root / "README.md"
    if readme_path.exists():
        readme = readme_path.read_text(encoding="utf-8")
        if not readme.startswith("---\\n"):
            errors.append("README.md is missing dataset-card YAML front matter")
        if "configs:" not in readme or "data/public_s2_items.jsonl" not in readme:
            errors.append("README.md does not declare the public-s2 data file")

    if "huggingface_dataset" not in manifest.get("targetPlatforms", []):
        errors.append("package manifest does not target huggingface_dataset")
    if manifest.get("evidenceMode") != "mock":
        errors.append("package manifest evidenceMode should remain mock until hosted rows exist")

    for artifact in manifest.get("artifacts", []):
        path = root / artifact["path"]
        if not path.exists():
            errors.append(f"manifest artifact missing: {artifact['path']}")
            continue
        data = path.read_bytes()
        if sha256(data) != artifact["sha256"]:
            errors.append(f"sha256 mismatch: {artifact['path']}")
        if len(data) != artifact["bytes"]:
            errors.append(f"byte count mismatch: {artifact['path']}")

    checksums_path = root / "checksums.sha256"
    if checksums_path.exists() and checksums_path.read_text(encoding="utf-8") != expected_checksums(manifest):
        errors.append("checksums.sha256 does not match manifest artifact list")

    return {
        "status": "failed" if errors else "ok",
        "packageRoot": str(root),
        "repoType": "dataset",
        "repoId": manifest.get("huggingFaceDatasetId", DEFAULT_REPO_ID),
        "artifactCount": len(manifest.get("artifacts", [])),
        "requiredFileCount": len(REQUIRED_FILES),
        "errors": errors,
    }


def upload(root: Path, repo_id: str, private: bool, commit_message: str) -> str:
    token = os.environ.get("HF_TOKEN")
    if not token:
        raise SystemExit("HF_TOKEN is required for --execute")
    try:
        from huggingface_hub import HfApi, upload_folder
    except ImportError as exc:
        raise SystemExit("Install huggingface_hub before --execute") from exc

    api = HfApi(token=token)
    api.create_repo(repo_id=repo_id, repo_type="dataset", private=private, exist_ok=True)
    upload_folder(
        folder_path=str(root),
        repo_id=repo_id,
        repo_type="dataset",
        token=token,
        commit_message=commit_message,
    )
    return f"https://huggingface.co/datasets/{repo_id}"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Validate upload readiness without uploading.")
    parser.add_argument("--execute", action="store_true", help="Create/update the Hugging Face Dataset repo.")
    parser.add_argument("--repo-id", default=DEFAULT_REPO_ID)
    parser.add_argument("--private", action="store_true")
    parser.add_argument("--commit-message", default="Add Aleph-Bench M0 platform package")
    args = parser.parse_args()

    if args.dry_run and args.execute:
        raise SystemExit("Use either --dry-run or --execute, not both")

    report = validate_package(PACKAGE_ROOT)
    report["requestedRepoId"] = args.repo_id
    report["mode"] = "execute" if args.execute else "dry-run"

    if report["errors"]:
        print(json.dumps(report, indent=2, sort_keys=True))
        raise SystemExit(1)

    if args.execute:
        report["url"] = upload(PACKAGE_ROOT, args.repo_id, args.private, args.commit_message)
    else:
        report["url"] = None

    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
'''


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
        "resources": [
            {
                "path": "data/public_s2_items.csv",
                "description": "Flat public S2 item table for Kaggle Dataset preview.",
                "schema": {"fields": _resource_fields(ITEM_FIELDS)},
            },
            {
                "path": "data/public_s2_prompts.csv",
                "description": "Flat frozen-ladder prompt table with leakage-gate measurements.",
                "schema": {"fields": _resource_fields(PROMPT_FIELDS)},
            },
            {
                "path": "data/submission_format.csv",
                "description": "Community benchmark output submission shape.",
                "schema": {
                    "fields": _resource_fields(
                        [
                            ("row_id", "Submission row id.", "string"),
                            ("model_id", "Provider-facing model id.", "string"),
                            ("item_id", "Bench item id.", "string"),
                            ("prompt_id", "Frozen ladder prompt id.", "string"),
                            ("output_text", "Generated model output.", "string"),
                        ]
                    )
                },
            },
        ],
    }


def _resource_fields(fields: list[tuple[str, str, str]]) -> list[dict[str, str]]:
    return [{"name": name, "title": title, "type": kind} for name, title, kind in fields]


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


def _item_rows(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for item in items:
        rows.append(
            {
                "item_id": item["id"],
                "stratum": item["stratum"],
                "language": item["language"],
                "metric_class": item["metricClass"],
                "target_label": item["target"].get("label"),
                "target_text": item["target"]["text"],
                "family": item["provenance"]["parameters"]["family"],
                "canary_guid": item["canaryGuid"],
                "license": item["license"],
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


def _kaggle_task_readme() -> str:
    return """# Kaggle Community Benchmark Scaffold

This directory is a launch scaffold, not checked-in hosted evidence. Kaggle Community Benchmarks run through a notebook/task interface with model access supplied by Kaggle's benchmark program. The M0 task should call each model on the non-leaking frozen-ladder prompts, then score outputs with the same local AURC/ECL/Elicit/leakage code used by `./aleph-bench`.

The included `aleph_bench_m0_task.py` is intentionally minimal and defensive. Kaggle Community Benchmarks use executable Python tasks built around the `kaggle-benchmarks` SDK's `@kbench.task(...)` decorator and `llm.prompt(...)`; this scaffold keeps that shape visible while leaving exact model-access wiring to the approved Kaggle notebook.

- it keeps explicit reconstruction anchors out of submissions;
- it treats model outputs as `black_box` behavioral evidence;
- it does not request or report logits, token NLL, or bits;
- it points maintainers back to the repository verifier before publishing rows.

For the API-test preparation step, run `python3 kaggle/api_test_smoke.py` from this package or from the repository path where it is checked in. The smoke test uses a stub LLM to verify that the task wrapper calls `prompt(...)` once per non-leaking row and emits the exact public submission shape. Passing the smoke test is not hosted model evidence; it only proves the package is ready to be wired into Kaggle's approved notebook.

Before a public Kaggle benchmark launch, replace the placeholder model loop with the exact Kaggle `kaggle-benchmarks` SDK calls used by the approved Resource Grant notebook, save the notebook version, and attach the resulting hosted `BenchResult` plus manifest/report as separate evidence artifacts.
"""


def _kaggle_task_py() -> str:
    return '''"""Aleph-Bench M0 Kaggle Community Benchmark scaffold.

This file is packaged for reviewer inspection. It is not executed by the local
test suite because Kaggle model access is granted inside Kaggle notebooks.
"""

from __future__ import annotations

import json
from pathlib import Path


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
PROMPTS_PATH = PACKAGE_ROOT / "data/public_s2_prompts.jsonl"


# Kaggle notebook wiring sketch (uncomment only inside the approved benchmark
# notebook, where kaggle-benchmarks is installed and model access is available):
#
# import kaggle_benchmarks as kbench
#
# @kbench.task(name="aleph_bench_m0_prompt", store_task=False)
# def aleph_bench_m0_prompt(llm, item_id: str, prompt_id: str, prompt: str) -> dict[str, str]:
#     with kbench.chats.new(f"{item_id}:{prompt_id}"):
#         output = llm.prompt(prompt)
#     return {"item_id": item_id, "prompt_id": prompt_id, "output_text": str(output)}
#
# results = aleph_bench_m0_prompt.evaluate(llm=[kbench.llm], evaluation_data=prompt_dataframe)


def load_sendable_prompts() -> list[dict[str, object]]:
    rows = []
    for line in PROMPTS_PATH.read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        if not row["disqualified"]:
            rows.append(row)
    return rows


def run_black_box_model(model_id: str, llm: object) -> list[dict[str, str]]:
    """Run one Kaggle-provided model over all non-leaking M0 prompts.

    `llm` is expected to be the model object provided by the Kaggle Community
    Benchmarks notebook environment. It should expose a generation method such
    as `prompt(...)`; exact SDK wiring belongs in the submitted Kaggle notebook.
    """

    outputs = []
    for row in load_sendable_prompts():
        output = llm.prompt(str(row["prompt"]))
        outputs.append(
            {
                "row_id": f"{row['item_id']}:{row['prompt_id']}",
                "model_id": model_id,
                "item_id": str(row["item_id"]),
                "prompt_id": str(row["prompt_id"]),
                "output_text": str(output),
            }
        )
    return outputs


def main() -> None:
    raise SystemExit(
        "This scaffold must run inside a Kaggle Community Benchmarks notebook "
        "with approved model access. Locally, use ./aleph-bench package --check."
    )


if __name__ == "__main__":
    main()
'''


def _kaggle_api_test_smoke_py() -> str:
    return '''"""Local smoke test for the Aleph-Bench M0 Kaggle API-test wrapper.

This script deliberately uses a stub LLM. It proves the package-level task I/O
contract before Kaggle-hosted model access exists; it does not produce model
evidence or leaderboard rows.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
import sys


KAGGLE_DIR = Path(__file__).resolve().parent
PACKAGE_ROOT = KAGGLE_DIR.parent
SUBMISSION_PATH = PACKAGE_ROOT / "data/submission_format.csv"
sys.path.insert(0, str(KAGGLE_DIR))

import aleph_bench_m0_task  # noqa: E402


class StubLLM:
    def __init__(self) -> None:
        self.prompts: list[str] = []

    def prompt(self, prompt: str) -> str:
        self.prompts.append(prompt)
        return f"stub-output-{len(self.prompts):03d}"


def load_submission_rows() -> list[dict[str, str]]:
    with SUBMISSION_PATH.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def row_key(row: dict[str, object]) -> tuple[str, str, str]:
    return (str(row["row_id"]), str(row["item_id"]), str(row["prompt_id"]))


def main() -> None:
    expected_rows = load_submission_rows()
    prompts = aleph_bench_m0_task.load_sendable_prompts()
    llm = StubLLM()
    observed_rows = aleph_bench_m0_task.run_black_box_model("stub/model", llm)

    errors: list[str] = []
    if len(prompts) != 180:
        errors.append(f"expected 180 non-leaking prompts, found {len(prompts)}")
    if len(expected_rows) != 180:
        errors.append(f"expected 180 submission rows, found {len(expected_rows)}")
    if len(observed_rows) != len(expected_rows):
        errors.append(f"expected {len(expected_rows)} outputs, found {len(observed_rows)}")
    if len(llm.prompts) != len(expected_rows):
        errors.append(f"expected {len(expected_rows)} prompt() calls, found {len(llm.prompts)}")
    if any(row.get("disqualified") for row in prompts):
        errors.append("load_sendable_prompts returned at least one disqualified prompt")

    expected_keys = [row_key(row) for row in expected_rows]
    observed_keys = [row_key(row) for row in observed_rows]
    if observed_keys != expected_keys:
        errors.append("observed output row order or ids do not match submission_format.csv")

    required_fields = {"row_id", "model_id", "item_id", "prompt_id", "output_text"}
    for index, row in enumerate(observed_rows):
        if set(row) != required_fields:
            errors.append(f"row {index} has fields {sorted(row)}, expected {sorted(required_fields)}")
            break
        if row["model_id"] != "stub/model":
            errors.append(f"row {index} has unexpected model_id {row['model_id']!r}")
            break
        if not row["output_text"]:
            errors.append(f"row {index} has empty output_text")
            break

    report = {
        "status": "failed" if errors else "ok",
        "packageRoot": str(PACKAGE_ROOT),
        "sendablePrompts": len(prompts),
        "submissionRows": len(expected_rows),
        "promptCalls": len(llm.prompts),
        "firstRow": observed_rows[0] if observed_rows else None,
        "errors": errors,
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    if errors:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
'''


def _package_markdown(source_path: Path, *, kind: str) -> bytes:
    text = source_path.read_text(encoding="utf-8")
    if kind == "m0-evidence":
        replacements = {
            "../../bench/results/m0-call-manifest.json": "m0-call-manifest.json",
            "../../bench/results/m0-audit.json": "m0-audit.json",
            "../../bench/results/m0-bundle.json": "m0-bundle.json",
            "../../bench/results/m0-report.md": "m0-report.md",
            "../../bench/results/m0-first-run.json": "m0-first-run.json",
            "../../schemas/aleph-bench-manifest.schema.json": "../schemas/aleph-bench-manifest.schema.json",
            "../../schemas/aleph-bench-audit.schema.json": "../schemas/aleph-bench-audit.schema.json",
            "../../schemas/aleph-bench-bundle.schema.json": "../schemas/aleph-bench-bundle.schema.json",
        }
    elif kind == "hosted-runbook":
        replacements = {
            "../../bench/results/m0-first-run.json": "../evidence/m0-first-run.json",
            "m0-evidence.md": "../evidence/m0-evidence.md",
        }
    else:
        replacements = {}
    for old, new in replacements.items():
        text = text.replace(old, new)
    return _text_bytes(text)


def _build_artifact_bytes() -> dict[str, bytes]:
    data_dir = REPO_ROOT / "bench/data/public/s2"
    result_path = REPO_ROOT / "bench/results/m0-first-run.json"
    items = load_items(data_dir)
    result = _load_json(result_path)
    artifact_bytes: dict[str, bytes] = {
        "README.md": _text_bytes(_hf_readme()),
        "EVALUATION.md": _text_bytes(_evaluation_protocol()),
        "PLATFORM_LAUNCH_CHECKLIST.md": _text_bytes(_platform_launch_checklist()),
        "dataset-metadata.json": _json_bytes(_kaggle_metadata()),
        "data/public_s2_items.jsonl": _jsonl_bytes(items),
        "data/public_s2_prompts.jsonl": _jsonl_bytes(_prompt_rows(items)),
        "data/public_s2_items.csv": _csv_bytes(_item_rows(items), [field[0] for field in ITEM_FIELDS]),
        "data/public_s2_prompts.csv": _csv_bytes(_prompt_rows(items), [field[0] for field in PROMPT_FIELDS]),
        "data/submission_format.csv": _csv_bytes(
            _submission_rows(items),
            ["row_id", "model_id", "item_id", "prompt_id", "output_text"],
        ),
        "huggingface/README.md": _text_bytes(_hf_upload_readme()),
        "huggingface/upload_dataset.py": _text_bytes(_hf_upload_py()),
        "kaggle/README.md": _text_bytes(_kaggle_task_readme()),
        "kaggle/api_test_smoke.py": _text_bytes(_kaggle_api_test_smoke_py()),
        "kaggle/aleph_bench_m0_task.py": _text_bytes(_kaggle_task_py()),
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
    ]:
        artifact_bytes[dest] = (REPO_ROOT / source).read_bytes()
    artifact_bytes["evidence/m0-evidence.md"] = _package_markdown(
        REPO_ROOT / "docs/benchmark/m0-evidence.md",
        kind="m0-evidence",
    )
    artifact_bytes["docs/hosted-m0-runbook.md"] = _package_markdown(
        REPO_ROOT / "docs/benchmark/hosted-m0-runbook.md",
        kind="hosted-runbook",
    )
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
    if path.startswith("huggingface/"):
        return "Hugging Face upload preparation artifact."
    if path.startswith("kaggle/"):
        return "Kaggle Community Benchmark preparation artifact."
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
        "targetPlatforms": ["huggingface_dataset", "kaggle_dataset", "kaggle_community_benchmark", "croissant"],
        "kaggleDatasetId": KAGGLE_ID,
        "huggingFaceDatasetId": HF_ID,
        "artifacts": artifacts,
        "validationCommands": [
            "./aleph-bench verify --audit bench/results/m0-audit.json --bundle bench/results/m0-bundle.json",
            f"./aleph-bench package --check {stable_dataset_path(out_dir / 'package-manifest.json')}",
            f"python3 {stable_dataset_path(out_dir / 'kaggle/api_test_smoke.py')}",
            f"python3 {stable_dataset_path(out_dir / 'huggingface/upload_dataset.py')} --dry-run",
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
