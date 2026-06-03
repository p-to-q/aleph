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
- text2text-generation
tags:
- benchmark
- prompt-compression
- reverse-prompt-search
- elicitation-efficiency
- rate-distortion
- synthetic
- aleph-bench
version: 0.1.0
milestone: m0
configs:
- config_name: public-s2-items
  data_files:
  - split: test
    path: data/public_s2_items.jsonl
- config_name: public-s2-prompts
  data_files:
  - split: test
    path: data/public_s2_prompts.jsonl
---

# Aleph-Bench M0

> [!WARNING]
> The model rows under `evidence/` are **deterministic mock pipeline outputs**, not real model
> evaluations. This release distributes the benchmark **dataset and procedure** (M0 = milestone 0).
> Real cross-vendor model rows are gated on Kaggle Benchmarks Resource Grant model access; do not
> cite numbers from `evidence/mock_*.csv` as a model leaderboard.

Aleph-Bench M0 is a small frozen-ladder benchmark seed set for comparing how much non-leaking prompt coordinate length a model needs to reproduce synthetic target outputs. **Version**: `m0`. **Evidence mode**: `mock` (no real model rows yet).

The construct is **elicitation efficiency**: fix the target output, then search for the shortest non-leaking prompt that regenerates it. Lower AURC means the model reaches the target with fewer prompt tokens.

## Contents

### Dataset (`data/`)

- `public_s2_items.jsonl` (30 rows): S2 compositional BenchItems with target text, frozen ladder, canary GUID, provenance.
- `public_s2_prompts.jsonl` (240 rows): every frozen-ladder prompt, with leakage-gate measurements and a `disqualified` flag.
- `public_s2_items.csv` / `public_s2_prompts.csv`: flat preview tables for the Kaggle Dataset page.
- `submission_format.csv` (180 rows): the public output shape (`row_id,model_id,item_id,prompt_id,output_text`) restricted to non-leaking prompts.

### Mock evidence (`evidence/`)

- `mock_model_summary.csv` / `mock_item_metrics.csv`: deterministic mock-adapter rows. **Pipeline evidence only**, never to be cited as model rankings.
- `m0-first-run.json`: the full mock `BenchResult` (3 mock models, 30 items).
- `m0-report.md`: pre-rendered tables for the mock result.
- `m0-audit.json` / `m0-bundle.json` / `m0-call-manifest.json` / `m0-evidence.md`: acceptance-gate receipt, bundle digest manifest, no-call prompt manifest, and evidence note.

### Metadata, schemas, and platform scaffolding

- `schemas/`: JSON Schemas validating items, prompts, results, audit, bundle, manifest, and the platform package itself.
- `croissant.json`: MLCommons Croissant 1.1 metadata with `RecordSet` for items and prompts.
- `dataset-metadata.json`: Kaggle Dataset metadata with per-CSV field schemas.
- `huggingface/`: Hugging Face upload preparation (dry-run + optional `--execute`).
- `kaggle/`: Kaggle Community Benchmark task scaffold, vendored scorer, output-scoring helper, and I/O smoke test.
- `PLATFORM_LAUNCH_CHECKLIST.md`: staged launch gates separating prepared, blocked, and not-yet-run work.

## How to evaluate

A Kaggle notebook (or any local runner) can score outputs against the frozen ladder **without cloning the Aleph repository** — the scorer is vendored in `kaggle/`:

```python
import csv, json
from pathlib import Path

# 1) Load the non-leaking prompts (180 of 240).
prompts = [json.loads(line) for line in Path("data/public_s2_prompts.jsonl").read_text().splitlines()]
non_leaking = [row for row in prompts if not row["disqualified"]]

# 2) Generate outputs (replace with your model call). Submission shape is documented in
#    data/submission_format.csv and must contain row_id, model_id, item_id, prompt_id, output_text.
submission = [{"row_id": f"{r['item_id']}:{r['prompt_id']}",
               "model_id": "my-model",
               "item_id": r["item_id"],
               "prompt_id": r["prompt_id"],
               "output_text": my_model(r["prompt"])} for r in non_leaking]

# 3) Score with the vendored AURC / ECL@tau / Elicit@k implementation.
import sys; sys.path.insert(0, "kaggle")
from score_outputs import score_submission
result = score_submission(items_path="data/public_s2_items.jsonl",
                          prompts_path="data/public_s2_prompts.jsonl",
                          submission_rows=submission,
                          model_id="my-model")
print(result["aggregate"])
```

Leakage is a gate, not a penalty. Explicit reconstruction prompts (rung 0) are excluded from compression metrics. AURC is the area under the monotone non-leaking rate-distortion staircase; lower is better. ECL@tau and Elicit@k are interpretable duals.

For deeper validation (schema check + bundle digest + acceptance audit) clone the Aleph repository and run:

```bash
./aleph-bench verify --audit bench/results/m0-audit.json --bundle bench/results/m0-bundle.json
./aleph-bench package --check bench/results/platform/m0-mock/package-manifest.json
```

Hosted black-box results require server-side OpenAI-compatible credentials and should produce their own result, manifest, report, and evidence note. Black-box rows report generated text behavior only; they do not report logits, token NLL, or white-box observations. Native Anthropic / Gemini adapters are M1 scope; M0 cross-vendor coverage requires an OpenAI-compatible proxy (OpenRouter, LiteLLM, ...).

## Citation

A versioned citation (with author list, DOI, and venue) will accompany the first hosted-evidence release. For now, please cite as:

```bibtex
@misc{alephbench_m0_2026,
  title  = {Aleph-Bench M0: A Frozen-Ladder Prompt-Compression Benchmark (Procedure Release)},
  author = {Aleph-Bench Maintainers},
  year   = {2026},
  note   = {Procedure release, mock pipeline evidence; cross-vendor model rows pending Kaggle Benchmarks Resource Grant},
  url    = {https://huggingface.co/datasets/p-to-q/aleph-bench-m0}
}
```

The canonical CITATION template lives at `docs/benchmark/launch-kit/CITATION.cff` in the upstream repository; it will be finalized with the first real evidence release.

## Responsible Use

The targets are rule-generated synthetic English strings with a shared canary GUID stored as metadata, not as target text. The package is meant for benchmark procedure review and community reproduction, not for claims about globally shortest prompts or real model ranking until hosted black-box rows exist. Any `aurc / eclAtTau / elicitAtK` number sourced from `evidence/` is mock pipeline evidence with `evidenceMode = mock`, and downstream summaries (blog posts, slides, leaderboards) must preserve that label.
"""


def _evaluation_protocol() -> str:
    return """# Aleph-Bench M0 Platform Evaluation Protocol

This package is ready to publish as a Hugging Face Dataset or Kaggle Dataset. It is also ready for a community benchmark dry run because it includes the seed data, prompt rows, schemas, mock evidence, a vendored scorer, and verification commands.

## Evidence Boundary

- The included model rows are deterministic mock evidence and live under `evidence/mock_*.csv` (not under `data/`). Hugging Face and Kaggle dataset previews therefore do not render them as a leaderboard.
- They prove the benchmark pipeline, not model quality.
- Hosted black-box rows must use the same S2 items, frozen ladder, leakage thresholds, tau, k, and AURC/ECL/Elicit definitions.
- Do not report logits, token NLL, bits, or white-box claims for hosted black-box rows.

## Submission Shape

Use `data/submission_format.csv` as the public output shape:

```text
row_id,model_id,item_id,prompt_id,output_text
```

`prompt_id` must refer to a non-leaking prompt from `data/public_s2_prompts.jsonl`. Gated explicit reconstruction prompts are present for auditability but should not be submitted as compression candidates.

## Where the scorer lives

This package is **self-contained for scoring**. You do not need to clone the Aleph repository to compute AURC / ECL@tau / Elicit@k on a `submission_format.csv` of outputs:

- `kaggle/_scoring.py` is a vendored copy of the pure-function metric helpers from `bench/engine/metrics.py` and `bench/engine/leakage_gate.py`. It has no third-party dependencies (standard library only).
- `kaggle/score_outputs.py` reads the items JSONL, prompts JSONL, and a submission row sequence (CSV path or in-memory list) and emits a `BenchResult`-compatible JSON.
- `kaggle/api_test_smoke.py` exercises both the I/O contract and the scorer end-to-end against a stub LLM; passing the smoke test means a Kaggle notebook will be able to call `score_submission(...)` against real outputs without further glue.

A full repository-side verification (schema, bundle, audit, manifest) still requires the Aleph repo:

```bash
git clone https://github.com/p-to-q/aleph
cd aleph
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

`ALEPH_CUSTOM_API_BASE_URL` expects an OpenAI-compatible `/chat/completions` endpoint. For cross-vendor coverage (Anthropic, Gemini), point it at an OpenAI-compatible proxy such as OpenRouter or LiteLLM; native Anthropic / Gemini adapters are M1 scope.
"""


def _platform_launch_checklist() -> str:
    return """# Aleph-Bench M0 Platform Launch Checklist

This checklist is the durable boundary between prepared package work and actual public platform launch. The checked-in M0 package is deterministic mock evidence plus launch scaffolding. It is not a hosted benchmark result.

## Current Status

| Stage | Status | Gate |
| --- | --- | --- |
| Local M0 evidence package | ready | `./aleph-bench package --check bench/results/platform/m0-mock/package-manifest.json` |
| Kaggle API-test preparation | ready | `python3 bench/results/platform/m0-mock/kaggle/api_test_smoke.py` reports 180 sendable prompts, 180 prompt calls, end-to-end scoring within bounds |
| Hugging Face Dataset upload preparation | ready | `python3 bench/results/platform/m0-mock/huggingface/upload_dataset.py --dry-run` validates card, manifest, checksums, mock-csv location, and upload shape |
| Vendored scorer self-test | ready | `python3 bench/results/platform/m0-mock/kaggle/api_test_smoke.py` exits 0 with `aurc` in `[0, 1]` and a monotone frontier |
| Croissant 1.1 metadata validation | ready | `pip install mlcroissant && python3 bench/run.py validate-croissant bench/results/platform/m0-mock/croissant.json` reports `status: ok` with both record sets streaming |
| Mock-CSV layout audit | ready | mock evaluation rows live under `evidence/` (not `data/`), so HF / Kaggle previews do not render them as a leaderboard |
| HF / Kaggle account ownership decision | pending | confirm owner of `p-to-q/aleph-bench-m0` on both platforms (personal account vs org) before any `--execute` upload |
| Kaggle Benchmarks Resource Grant submission | pending | submit `docs/benchmark/launch-kit/kaggle-grant-application.md` to Kaggle; track approval id |
| Fresh-clone reproducibility check | pending | on a clean machine: `git clone … && ./aleph-bench package --check …` reproduces every checksum |
| HF dataset card render check | blocked-after-upload | after upload, confirm mock-evidence callout is above the fold and `evidence/mock_*.csv` is not shown as a data preview |
| Kaggle dataset render check | blocked-after-upload | after upload, confirm Data tab shows only `data/*` and treats `evidence/*` as supplementary files |
| Announcement copy boundary | pending | blog / tweet / slide deck frames the release as "procedure release, model rows pending Grant" — never as a leaderboard |
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

- root `README.md` renders as a dataset card with the mock-evidence callout above the fold;
- `data/public_s2_items.jsonl` and `data/public_s2_prompts.jsonl` are visible as dataset files;
- `evidence/mock_*.csv` are visible as supplementary files (not as a data preview / leaderboard);
- `package-manifest.json` and `checksums.sha256` match this checked-in package;
- the page copy does not present deterministic mock rows as real model ranking.

## Kaggle Path

1. Upload or attach the package as a Kaggle Dataset using `dataset-metadata.json`.
2. Run `python3 kaggle/api_test_smoke.py` inside the attached package path (verifies I/O contract and the vendored scorer end-to-end).
3. In the approved Kaggle Benchmarks notebook, wire `aleph_bench_m0_task.py` to `kaggle-benchmarks` with `@kbench.task`, `llm.prompt(...)`, `.evaluate(llm=[...], evaluation_data=df)`, and final `%choose`.
4. After collecting outputs, score them with `kaggle/score_outputs.py` (which uses the vendored `kaggle/_scoring.py`) to produce a `BenchResult` JSON.
5. Save the notebook version and attach generated task/run files before claiming a Kaggle benchmark launch.

## Kaggle Benchmarks Resource Grant

The grant application draft lives at `docs/benchmark/launch-kit/kaggle-grant-application.md` in the upstream repository. Before a public Kaggle Community Benchmark launch:

1. Finalize the application draft (replace any placeholder fields).
2. Submit through the Kaggle Benchmarks Resource Grant program.
3. Track the approval id; record it in the next iteration of this checklist.
4. Until the grant is approved, the Kaggle Community Benchmark stage stays `blocked`.

## Announcement boundary

When announcing this release publicly:

- frame it as a **procedure release**, not a leaderboard;
- never use language like "we ranked GPT vs Claude vs Gemini" — no real model rows exist yet;
- always pair any `aurc / eclAtTau / elicitAtK` number with the `evidenceMode = mock` label.

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
    "evidence/mock_model_summary.csv",
    "evidence/mock_item_metrics.csv",
    "kaggle/aleph_bench_m0_task.py",
    "kaggle/api_test_smoke.py",
    "kaggle/_scoring.py",
    "kaggle/score_outputs.py",
    "huggingface/README.md",
    "huggingface/upload_dataset.py",
]
FORBIDDEN_FILES = [
    "data/mock_model_summary.csv",
    "data/mock_item_metrics.csv",
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
    for relative in FORBIDDEN_FILES:
        if (root / relative).exists():
            errors.append(
                f"forbidden file present: {relative} (mock evidence must live under evidence/, "
                "not data/, so HF / Kaggle previews don't render it as a leaderboard)"
            )

    readme_path = root / "README.md"
    if readme_path.exists():
        readme = readme_path.read_text(encoding="utf-8")
        if not readme.startswith("---\\n"):
            errors.append("README.md is missing dataset-card YAML front matter")
        if "configs:" not in readme:
            errors.append("README.md does not declare dataset configs")
        if "data/public_s2_items.jsonl" not in readme:
            errors.append("README.md does not declare the public-s2 item file")
        if "data/public_s2_prompts.jsonl" not in readme:
            errors.append("README.md does not declare the public-s2 prompt file")
        if "deterministic mock pipeline outputs" not in readme:
            errors.append(
                "README.md is missing the mock-evidence boundary banner ('deterministic mock pipeline outputs')"
            )

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


def _croissant_field(
    record_id: str,
    name: str,
    description: str,
    data_type: str,
    file_object: str,
    column: str,
) -> dict[str, Any]:
    return {
        "@type": "cr:Field",
        "@id": f"{record_id}/{name}",
        "name": name,
        "description": description,
        "dataType": data_type,
        "source": {
            "fileObject": {"@id": file_object},
            "extract": {"column": column},
        },
    }


def _items_record_set_fields() -> list[dict[str, Any]]:
    record_id = "public_s2_items"
    file_object = "data/public_s2_items.csv"
    return [
        _croissant_field(record_id, "item_id", "Bench item id.", "sc:Text", file_object, "item_id"),
        _croissant_field(record_id, "stratum", "Benchmark stratum (S1..S5).", "sc:Text", file_object, "stratum"),
        _croissant_field(record_id, "language", "ISO 639-1 language code.", "sc:Text", file_object, "language"),
        _croissant_field(record_id, "metric_class", "Primary fidelity metric class.", "sc:Text", file_object, "metric_class"),
        _croissant_field(record_id, "target_label", "Short target label for cold reading.", "sc:Text", file_object, "target_label"),
        _croissant_field(record_id, "target_text", "Target output text.", "sc:Text", file_object, "target_text"),
        _croissant_field(record_id, "family", "Synthetic family (alpha/beta/gamma).", "sc:Text", file_object, "family"),
        _croissant_field(record_id, "canary_guid", "Dataset-level contamination canary GUID.", "sc:Text", file_object, "canary_guid"),
        _croissant_field(record_id, "license", "Item license.", "sc:Text", file_object, "license"),
    ]


def _prompts_record_set_fields() -> list[dict[str, Any]]:
    record_id = "public_s2_prompts"
    file_object = "data/public_s2_prompts.csv"
    return [
        _croissant_field(record_id, "item_id", "Bench item id.", "sc:Text", file_object, "item_id"),
        _croissant_field(record_id, "prompt_id", "Frozen ladder prompt id.", "sc:Text", file_object, "prompt_id"),
        _croissant_field(record_id, "rung", "Frozen ladder rung (0..3).", "sc:Integer", file_object, "rung"),
        _croissant_field(record_id, "paraphrase", "Paraphrase index within rung.", "sc:Integer", file_object, "paraphrase"),
        _croissant_field(record_id, "label", "Human-readable rung label.", "sc:Text", file_object, "label"),
        _croissant_field(record_id, "expected_leakage", "Expected leakage class.", "sc:Text", file_object, "expected_leakage"),
        _croissant_field(record_id, "tokens", "Regex token count of the prompt.", "sc:Integer", file_object, "tokens"),
        _croissant_field(record_id, "disqualified", "Whether the leakage gate disqualifies the prompt.", "sc:Boolean", file_object, "disqualified"),
        _croissant_field(record_id, "lcs_ratio", "Prompt-target LCS ratio.", "sc:Float", file_object, "lcs_ratio"),
        _croissant_field(record_id, "trigram_overlap", "Target trigram overlap.", "sc:Float", file_object, "trigram_overlap"),
        _croissant_field(record_id, "verbatim_span_tokens", "Longest verbatim token span.", "sc:Integer", file_object, "verbatim_span_tokens"),
        _croissant_field(record_id, "prompt", "Prompt text.", "sc:Text", file_object, "prompt"),
    ]


def _croissant_metadata(artifact_hashes: dict[str, str]) -> dict[str, Any]:
    distributions = [
        {
            "@type": "cr:FileObject",
            "@id": name,
            "name": name,
            "contentUrl": name,
            "encodingFormat": _encoding_for(name),
            "sha256": artifact_hashes[name],
        }
        for name in sorted(artifact_hashes)
        if name.startswith("data/") or name.startswith("schemas/") or name.startswith("evidence/")
    ]
    cite_as = (
        "Aleph-Bench Maintainers (2026). Aleph-Bench M0: A Frozen-Ladder Prompt-Compression "
        "Benchmark (Procedure Release). https://huggingface.co/datasets/" + HF_ID
    )
    return {
        "@context": {
            "@language": "en",
            "@vocab": "https://schema.org/",
            "citeAs": "cr:citeAs",
            "column": "cr:column",
            "conformsTo": "dct:conformsTo",
            "cr": "http://mlcommons.org/croissant/",
            "data": {"@id": "cr:data", "@type": "@json"},
            "dataType": {"@id": "cr:dataType", "@type": "@vocab"},
            "dct": "http://purl.org/dc/terms/",
            "examples": {"@id": "cr:examples", "@type": "@json"},
            "extract": "cr:extract",
            "field": "cr:field",
            "fileObject": "cr:fileObject",
            "fileProperty": "cr:fileProperty",
            "fileSet": "cr:fileSet",
            "format": "cr:format",
            "includes": "cr:includes",
            "isLiveDataset": "cr:isLiveDataset",
            "jsonPath": "cr:jsonPath",
            "key": "cr:key",
            "md5": "cr:md5",
            "parentField": "cr:parentField",
            "path": "cr:path",
            "rai": "http://mlcommons.org/croissant/RAI/",
            "recordSet": "cr:recordSet",
            "references": "cr:references",
            "regex": "cr:regex",
            "repeated": "cr:repeated",
            "replace": "cr:replace",
            "sc": "https://schema.org/",
            "separator": "cr:separator",
            "source": "cr:source",
            "subField": "cr:subField",
            "transform": "cr:transform",
        },
        "@type": "sc:Dataset",
        "conformsTo": "http://mlcommons.org/croissant/1.1",
        "name": "Aleph-Bench M0",
        "description": (
            "A frozen-ladder prompt-compression benchmark seed package with 30 S2 "
            "synthetic targets, schemas, and deterministic mock pipeline evidence."
        ),
        "url": f"https://huggingface.co/datasets/{HF_ID}",
        "sameAs": [f"https://www.kaggle.com/datasets/{KAGGLE_ID}"],
        "version": "0.1.0",
        "dateCreated": "2026-06-03",
        "datePublished": "2026-06-03",
        "creator": {"@type": "sc:Organization", "name": "p-to-q"},
        "publisher": {"@type": "sc:Organization", "name": "p-to-q"},
        "license": "https://spdx.org/licenses/CC0-1.0.html",
        "sdLicense": "https://spdx.org/licenses/CC0-1.0.html",
        "citeAs": cite_as,
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
                "field": _items_record_set_fields(),
            },
            {
                "@type": "cr:RecordSet",
                "@id": "public_s2_prompts",
                "name": "public_s2_prompts",
                "description": "Frozen-ladder prompt rows and leakage-gate measurements.",
                "field": _prompts_record_set_fields(),
            },
        ],
    }


def _encoding_for(name: str) -> str:
    if name.endswith(".jsonl"):
        return "application/jsonlines"
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

This directory is a launch scaffold, not checked-in hosted evidence. Kaggle Community Benchmarks run through a notebook/task interface with model access supplied by Kaggle's benchmark program. The M0 task should call each model on the non-leaking frozen-ladder prompts, then score outputs with the vendored AURC/ECL/Elicit/leakage code shipped here so a Kaggle notebook does **not** need to clone the Aleph repository.

## Files

- `aleph_bench_m0_task.py` — scaffold/template. `import`-safe (no third-party deps) and prints a friendly notebook-only message when executed as `__main__` rather than crashing. The `@kbench.task` wiring is documented inline; uncomment it in the approved Kaggle notebook.
- `_scoring.py` — vendored copy of the pure metric functions from `bench/engine/metrics.py` and `bench/engine/leakage_gate.py` (standard library only). This is the *source of truth* for scoring inside Kaggle; do not edit it by hand — regenerate the package from the Aleph repo.
- `score_outputs.py` — given a submission row sequence (CSV path or list of dicts) plus the items/prompts JSONL files, produces a `BenchResult`-compatible JSON. Use this in the Kaggle notebook after `.evaluate(...)` returns.
- `api_test_smoke.py` — local end-to-end smoke test. Verifies I/O shape (one `prompt(...)` call per non-leaking row, correct submission CSV), then runs the vendored scorer against the stub outputs and asserts `aurc ∈ [0, 1]`, a monotone non-leaking frontier, and that rung-0 prompts are gated.

## Boundary

- it keeps explicit reconstruction anchors out of submissions;
- it treats model outputs as `black_box` behavioral evidence;
- it does not request or report logits, token NLL, or bits;
- it points maintainers back to the repository verifier before publishing rows.

## How it slots into a Kaggle notebook

```python
import kaggle_benchmarks as kbench
from aleph_bench_m0_task import aleph_bench_m0_prompt, prompt_dataframe
from score_outputs import score_submission

results = aleph_bench_m0_prompt.evaluate(llm=[kbench.llm], evaluation_data=prompt_dataframe())
submission = [row for row in results]  # adapt to the SDK's return shape
bench_result = score_submission(
    items_path="../data/public_s2_items.jsonl",
    prompts_path="../data/public_s2_prompts.jsonl",
    submission_rows=submission,
    model_id="kaggle/<model>",
)
```

## Local smoke

Run `python3 kaggle/api_test_smoke.py` from this directory. The smoke test uses a stub LLM to verify the I/O contract and the vendored scorer. Passing the smoke test is not hosted model evidence; it only proves the package is ready to be wired into Kaggle's approved notebook.

Before a public Kaggle benchmark launch, finalize the Resource Grant application (`docs/benchmark/launch-kit/kaggle-grant-application.md`), replace the placeholder model loop with the exact Kaggle `kaggle-benchmarks` SDK calls used by the approved notebook, save the notebook version, and attach the resulting hosted `BenchResult` plus manifest/report as separate evidence artifacts.
"""


def _kaggle_task_py() -> str:
    return '''"""Aleph-Bench M0 Kaggle Community Benchmark scaffold / template.

This file is a *template*. It is `import`-safe and uses only the standard
library so the package smoke test can load it; the `@kbench.task` wiring is
documented inline and meant to be uncommented inside an approved Kaggle
Benchmarks notebook where the `kaggle-benchmarks` SDK and model access are
available. Running this file directly (`python3 aleph_bench_m0_task.py`)
prints a friendly notebook-only message and exits 0 rather than crashing.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Callable


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
PROMPTS_PATH = PACKAGE_ROOT / "data/public_s2_prompts.jsonl"


# ---------------------------------------------------------------------------
# Kaggle notebook wiring sketch (uncomment INSIDE the approved benchmark
# notebook, where kaggle-benchmarks is installed and model access is available):
# ---------------------------------------------------------------------------
#
# import kaggle_benchmarks as kbench
#
# @kbench.task(name="aleph_bench_m0_prompt", store_task=False)
# def aleph_bench_m0_prompt(llm, item_id: str, prompt_id: str, prompt: str) -> dict[str, str]:
#     with kbench.chats.new(f"{item_id}:{prompt_id}"):
#         output = llm.prompt(prompt)
#     return {"item_id": item_id, "prompt_id": prompt_id, "output_text": str(output)}
#
# results = aleph_bench_m0_prompt.evaluate(llm=[kbench.llm], evaluation_data=prompt_dataframe())
#
# After collecting `results`, score them with score_outputs.score_submission(...)
# (the vendored AURC / ECL@tau / Elicit@k pipeline lives in `_scoring.py`).


def load_sendable_prompts() -> list[dict[str, Any]]:
    """Return the 180 non-leaking ladder prompts from the packaged JSONL."""

    rows: list[dict[str, Any]] = []
    for line in PROMPTS_PATH.read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        if not row["disqualified"]:
            rows.append(row)
    return rows


def prompt_dataframe() -> list[dict[str, Any]]:
    """Minimal row-oriented evaluation data suitable for `kbench.task.evaluate`.

    Kaggle Benchmarks accepts any dataframe-like iterable; for local notebooks
    without pandas, the list-of-dicts shape works as drop-in input.
    """

    return [
        {
            "item_id": str(row["item_id"]),
            "prompt_id": str(row["prompt_id"]),
            "prompt": str(row["prompt"]),
        }
        for row in load_sendable_prompts()
    ]


def run_black_box_model(model_id: str, llm: Any) -> list[dict[str, str]]:
    """Run one Kaggle-provided model over all non-leaking M0 prompts.

    `llm` is expected to be the model object provided by the Kaggle Community
    Benchmarks notebook environment. It must expose a `prompt(...)` method
    (string in, string out); exact SDK wiring belongs in the submitted Kaggle
    notebook.
    """

    if not hasattr(llm, "prompt") or not callable(getattr(llm, "prompt")):
        raise TypeError("llm must expose a callable `prompt(str) -> str`")

    outputs: list[dict[str, str]] = []
    prompt_fn: Callable[[str], Any] = llm.prompt
    for row in load_sendable_prompts():
        output = prompt_fn(str(row["prompt"]))
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


def main() -> int:
    sendable = load_sendable_prompts()
    print(
        f"Aleph-Bench M0 task scaffold. {len(sendable)} non-leaking prompts ready. "
        "This file is a template: wire it into an approved Kaggle Community Benchmarks "
        "notebook (see the commented @kbench.task block at the top), then score outputs "
        "with score_outputs.score_submission(...).",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
'''


def _kaggle_api_test_smoke_py() -> str:
    return '''"""Local smoke test for the Aleph-Bench M0 Kaggle API-test wrapper.

This script deliberately uses a stub LLM. It proves two contracts before any
hosted Kaggle model access exists:

  1. The I/O contract: aleph_bench_m0_task.run_black_box_model produces one
     submission row per non-leaking ladder prompt, with the exact public
     submission shape.
  2. The vendored scorer contract: score_outputs.score_submission consumes
     those rows, returns a schema-shaped BenchResult, and emits well-formed
     metric values (aurc in [0, 1], monotone non-leaking frontier, rung-0
     prompts gated by the leakage gate).

Neither contract produces model evidence or leaderboard rows.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
import shutil
import sys


KAGGLE_DIR = Path(__file__).resolve().parent
PACKAGE_ROOT = KAGGLE_DIR.parent
SUBMISSION_PATH = PACKAGE_ROOT / "data/submission_format.csv"
ITEMS_PATH = PACKAGE_ROOT / "data/public_s2_items.jsonl"
PROMPTS_PATH = PACKAGE_ROOT / "data/public_s2_prompts.jsonl"


def cleanup_runtime_cache() -> None:
    shutil.rmtree(KAGGLE_DIR / "__pycache__", ignore_errors=True)


cleanup_runtime_cache()
sys.dont_write_bytecode = True
sys.path.insert(0, str(KAGGLE_DIR))

import aleph_bench_m0_task  # noqa: E402
import score_outputs  # noqa: E402


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


def _check_metric_invariants(bench_result: dict, errors: list[str]) -> None:
    aggregate = bench_result.get("aggregate") or {}
    aurc = aggregate.get("aurc")
    if aurc is None or not (0.0 <= float(aurc) <= 1.0):
        errors.append(f"aggregate.aurc out of [0,1]: {aurc!r}")

    item_runs = bench_result.get("itemRuns") or []
    if not item_runs:
        errors.append("score_submission returned no itemRuns")
        return

    for run in item_runs:
        item_id = run.get("itemId")
        frontier = run.get("frontier") or []
        previous_distortion: float | None = None
        previous_tokens: int | None = None
        for point in frontier:
            tokens = int(point["tokens"])
            distortion = float(point["distortion"])
            if previous_tokens is not None and tokens < previous_tokens:
                errors.append(f"{item_id}: frontier tokens not monotone non-decreasing")
                break
            if previous_distortion is not None and distortion > previous_distortion + 1e-9:
                errors.append(f"{item_id}: frontier distortion not monotone non-increasing")
                break
            previous_tokens = tokens
            previous_distortion = distortion

        leakage_hit_rate = run.get("metrics", {}).get("leakageHitRate")
        if leakage_hit_rate is None or float(leakage_hit_rate) < 0.25 - 1e-9:
            errors.append(
                f"{item_id}: leakage hit rate {leakage_hit_rate!r} below 0.25 — rung-0 anchors should be gated"
            )


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

    bench_result = score_outputs.score_submission(
        items_path=str(ITEMS_PATH),
        prompts_path=str(PROMPTS_PATH),
        submission_rows=observed_rows,
        model_id="stub/model",
    )
    _check_metric_invariants(bench_result, errors)
    aggregate_aurc = bench_result.get("aggregate", {}).get("aurc")

    report = {
        "status": "failed" if errors else "ok",
        "packageRoot": str(PACKAGE_ROOT),
        "sendablePrompts": len(prompts),
        "submissionRows": len(expected_rows),
        "promptCalls": len(llm.prompts),
        "scoredItems": len(bench_result.get("itemRuns") or []),
        "aggregateAurc": aggregate_aurc,
        "firstRow": observed_rows[0] if observed_rows else None,
        "errors": errors,
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    if errors:
        raise SystemExit(1)


if __name__ == "__main__":
    try:
        main()
    finally:
        cleanup_runtime_cache()
'''


def _kaggle_scoring_py() -> str:
    return '''"""Vendored scoring helpers for Aleph-Bench M0.

This module is a self-contained copy of the pure functions in
`bench/engine/metrics.py` and `bench/engine/leakage_gate.py`. It uses only the
Python standard library so a Kaggle notebook can compute AURC / ECL@tau /
Elicit@k without cloning the upstream Aleph repository.

Do not edit this file by hand — regenerate the package from the Aleph repo
with `./aleph-bench package --out-dir bench/results/platform/m0-mock`.
"""

from __future__ import annotations

import random
import re
from dataclasses import dataclass
from statistics import mean
from typing import Any, Iterable


TOKEN_RE = re.compile(r"[A-Za-z0-9]+")

DEFAULT_LEAKAGE_THRESHOLDS: dict[str, float | int] = {
    "lcsRatio": 0.65,
    "trigramOverlap": 0.5,
    "verbatimSpanTokens": 16,
}


# ---------------------------------------------------------------------------
# Fidelity / distortion / frontier
# ---------------------------------------------------------------------------


def token_count(text: str) -> int:
    return len(TOKEN_RE.findall(text))


def normalized_text(text: str) -> str:
    return " ".join(TOKEN_RE.findall(text.lower()))


def levenshtein(a: str, b: str) -> int:
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    previous = list(range(len(b) + 1))
    for i, char_a in enumerate(a, start=1):
        current = [i]
        for j, char_b in enumerate(b, start=1):
            insert = current[j - 1] + 1
            delete = previous[j] + 1
            replace = previous[j - 1] + (0 if char_a == char_b else 1)
            current.append(min(insert, delete, replace))
        previous = current
    return previous[-1]


def exact_fidelity(target: str, output: str) -> float:
    """Exact-class fidelity: 1.0 on exact equality; normalized edit distance otherwise."""

    if target == output:
        return 1.0
    target_norm = normalized_text(target)
    output_norm = normalized_text(output)
    if not target_norm and not output_norm:
        return 1.0
    if not target_norm or not output_norm:
        return 0.0
    distance = levenshtein(target_norm, output_norm)
    scale = max(len(target_norm), len(output_norm))
    return round(max(0.0, 1.0 - distance / scale), 6)


def char_ngram_fidelity(target: str, output: str, n: int = 3) -> float:
    def grams(value: str) -> set[str]:
        clean = normalized_text(value)
        if len(clean) < n:
            return {clean} if clean else set()
        return {clean[i : i + n] for i in range(len(clean) - n + 1)}

    target_grams = grams(target)
    output_grams = grams(output)
    if not target_grams and not output_grams:
        return 1.0
    if not target_grams or not output_grams:
        return 0.0
    return round(len(target_grams & output_grams) / len(target_grams | output_grams), 6)


def fidelity(target: str, output: str, metric_class: str) -> float:
    if metric_class == "exact":
        return exact_fidelity(target, output)
    if metric_class == "lexical":
        return char_ngram_fidelity(target, output)
    return exact_fidelity(target, output)


def distortion(target: str, output: str, metric_class: str) -> float:
    return round(1.0 - fidelity(target, output, metric_class), 6)


def monotone_lower_envelope(points: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    by_length: dict[int, dict[str, Any]] = {}
    for point in points:
        if point.get("disqualified"):
            continue
        length = int(point["tokens"])
        current = by_length.get(length)
        if current is None or point["distortion"] < current["distortion"]:
            by_length[length] = point

    envelope: list[dict[str, Any]] = []
    best_distortion: float | None = None
    for point in sorted(by_length.values(), key=lambda item: (item["tokens"], item["distortion"])):
        if best_distortion is None or point["distortion"] < best_distortion:
            best_distortion = point["distortion"]
            frontier_point = dict(point)
            frontier_point["frontierRank"] = len(envelope) + 1
            envelope.append(frontier_point)
    return envelope


def aurc(frontier: list[dict[str, Any]], normalizer_tokens: int) -> float:
    """Area under the rate-distortion staircase; lower is better.

    `normalizer_tokens` is the right-hand budget anchor (the explicit
    reconstruction prompt length, or the target text length if it is larger;
    matches `frozen_ladder.py:evaluate_item`'s `explicit_tokens`).
    """

    if not frontier:
        return 1.0
    normalizer = max(1, normalizer_tokens)
    area = 0.0
    previous_x = 0.0
    current_distortion = frontier[0]["distortion"]
    for point in sorted(frontier, key=lambda item: item["tokens"]):
        x = max(previous_x, min(1.0, point["tokens"] / normalizer))
        area += (x - previous_x) * current_distortion
        current_distortion = point["distortion"]
        previous_x = x
    area += max(0.0, 1.0 - previous_x) * current_distortion
    return round(max(0.0, min(1.0, area)), 6)


def ecl_at_tau(frontier: list[dict[str, Any]], tau: float) -> int | None:
    hits = [point["tokens"] for point in frontier if point["fidelity"] >= tau]
    return min(hits) if hits else None


def elicit_at_k(frontier: list[dict[str, Any]], tau: float, k: int) -> bool:
    shortest = sorted(frontier, key=lambda item: item["tokens"])[:k]
    return any(point["fidelity"] >= tau for point in shortest)


def ci95(values: list[float], *, seed: int, samples: int) -> dict[str, float] | None:
    if not values:
        return None
    if len(values) == 1:
        value = round(values[0], 6)
        return {"low": value, "high": value}
    rng = random.Random(seed)
    boot = []
    for _ in range(samples):
        draw = [values[rng.randrange(len(values))] for _ in values]
        boot.append(mean(draw))
    boot.sort()
    low_index = int(0.025 * (len(boot) - 1))
    high_index = int(0.975 * (len(boot) - 1))
    return {"low": round(boot[low_index], 6), "high": round(boot[high_index], 6)}


def summarize(values: list[float], *, seed: int, samples: int) -> tuple[float | None, dict[str, float] | None]:
    if not values:
        return None, None
    return round(mean(values), 6), ci95(values, seed=seed, samples=samples)


# ---------------------------------------------------------------------------
# Leakage gate (diagnostics + gate)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class LeakageGateResult:
    disqualified: bool
    lcsRatio: float
    trigramOverlap: float
    verbatimSpanTokens: int
    thresholds: dict[str, float | int]

    def as_dict(self) -> dict[str, object]:
        return {
            "disqualified": self.disqualified,
            "lcsRatio": self.lcsRatio,
            "trigramOverlap": self.trigramOverlap,
            "verbatimSpanTokens": self.verbatimSpanTokens,
            "thresholds": dict(self.thresholds),
        }


def leakage_tokens(text: str) -> list[str]:
    return TOKEN_RE.findall(text.lower())


def _lcs_length(a: list[str], b: list[str]) -> int:
    if not a or not b:
        return 0
    previous = [0] * (len(b) + 1)
    for token_a in a:
        current = [0]
        for j, token_b in enumerate(b, start=1):
            if token_a == token_b:
                current.append(previous[j - 1] + 1)
            else:
                current.append(max(previous[j], current[j - 1]))
        previous = current
    return previous[-1]


def _longest_common_span(a: list[str], b: list[str]) -> int:
    best = 0
    previous = [0] * (len(b) + 1)
    for token_a in a:
        current = [0]
        for j, token_b in enumerate(b, start=1):
            value = previous[j - 1] + 1 if token_a == token_b else 0
            current.append(value)
            best = max(best, value)
        previous = current
    return best


def _ngrams(values: list[str], n: int) -> set[tuple[str, ...]]:
    return {tuple(values[i : i + n]) for i in range(max(0, len(values) - n + 1))}


def evaluate_leakage(
    prompt: str,
    target: str,
    thresholds: dict[str, float | int] | None = None,
) -> LeakageGateResult:
    active = dict(DEFAULT_LEAKAGE_THRESHOLDS if thresholds is None else thresholds)
    prompt_tokens = leakage_tokens(prompt)
    target_tokens = leakage_tokens(target)
    if not prompt_tokens or not target_tokens:
        return LeakageGateResult(False, 0.0, 0.0, 0, active)

    lcs_ratio = _lcs_length(prompt_tokens, target_tokens) / len(target_tokens)
    target_trigrams = _ngrams(target_tokens, 3)
    prompt_trigrams = _ngrams(prompt_tokens, 3)
    trigram_overlap = (
        len(target_trigrams & prompt_trigrams) / len(target_trigrams) if target_trigrams else 0.0
    )
    span = _longest_common_span(prompt_tokens, target_tokens)
    disqualified = (
        lcs_ratio >= float(active["lcsRatio"])
        or trigram_overlap >= float(active["trigramOverlap"])
        or span >= int(active["verbatimSpanTokens"])
    )
    return LeakageGateResult(
        disqualified=disqualified,
        lcsRatio=round(lcs_ratio, 6),
        trigramOverlap=round(trigram_overlap, 6),
        verbatimSpanTokens=span,
        thresholds=active,
    )


def leakage_score(result: LeakageGateResult) -> float:
    """Diagnostic-only score in [0, 1]. Never folded into AURC; the gate
    (`result.disqualified`) is the only thing that affects scoring."""

    span_score = min(1.0, result.verbatimSpanTokens / int(result.thresholds["verbatimSpanTokens"]))
    return round(max(result.lcsRatio, result.trigramOverlap, span_score), 6)
'''


def _kaggle_score_outputs_py() -> str:
    return '''"""Score a Kaggle / local submission against the M0 frozen ladder.

Inputs:
- items JSONL (`data/public_s2_items.jsonl`)
- prompts JSONL (`data/public_s2_prompts.jsonl`)
- submission rows (CSV path or list of dicts with row_id, model_id, item_id, prompt_id, output_text)

Output: a `BenchResult`-compatible dict (subset of the strict schema; intended
for community use, not as a substitute for `./aleph-bench verify`).
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from statistics import mean
from typing import Any, Iterable

KAGGLE_DIR = Path(__file__).resolve().parent
if str(KAGGLE_DIR) not in sys.path:
    sys.path.insert(0, str(KAGGLE_DIR))

import _scoring  # noqa: E402


DEFAULT_TAU = 0.9
DEFAULT_K = 3
DEFAULT_BOOTSTRAP_SAMPLES = 500
DEFAULT_SEED = 0


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _load_submission_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _index_outputs(
    submission_rows: Iterable[dict[str, Any]],
    *,
    valid_prompt_keys: set[tuple[str, str]],
    expected_model_id: str,
) -> dict[tuple[str, str], str]:
    outputs: dict[tuple[str, str], str] = {}
    for row in submission_rows:
        item_id = str(row["item_id"]) if "item_id" in row else None
        prompt_id = str(row["prompt_id"]) if "prompt_id" in row else None
        row_id = str(row.get("row_id") or "")
        row_model_id = str(row.get("model_id") or "")
        text = str(row.get("output_text") or "")
        if item_id is None or prompt_id is None:
            raise ValueError(f"submission row missing item_id/prompt_id: {row!r}")
        key = (item_id, prompt_id)
        expected_row_id = f"{item_id}:{prompt_id}"
        if row_id and row_id != expected_row_id:
            raise ValueError(f"submission row_id mismatch: expected {expected_row_id!r}, found {row_id!r}")
        if row_model_id and row_model_id != expected_model_id:
            raise ValueError(
                f"submission model_id mismatch: expected {expected_model_id!r}, found {row_model_id!r}"
            )
        if key not in valid_prompt_keys:
            raise ValueError(f"submission row references unknown or gated prompt: {expected_row_id}")
        if key in outputs:
            raise ValueError(f"duplicate submission row: {expected_row_id}")
        outputs[key] = text
    return outputs


def _index_prompts(prompt_rows: list[dict[str, Any]]) -> dict[tuple[str, str], dict[str, Any]]:
    return {(str(row["item_id"]), str(row["prompt_id"])): row for row in prompt_rows}


def score_submission(
    *,
    items_path: str | Path,
    prompts_path: str | Path,
    submission_rows: Iterable[dict[str, Any]] | str | Path,
    model_id: str,
    tau: float = DEFAULT_TAU,
    k: int = DEFAULT_K,
    bootstrap_samples: int = DEFAULT_BOOTSTRAP_SAMPLES,
    seed: int = DEFAULT_SEED,
    leakage_thresholds: dict[str, float | int] | None = None,
) -> dict[str, Any]:
    items_path = Path(items_path)
    prompts_path = Path(prompts_path)
    items = _load_jsonl(items_path)
    prompt_rows = _load_jsonl(prompts_path)
    if isinstance(submission_rows, (str, Path)):
        submission_rows = _load_submission_rows(Path(submission_rows))
    prompt_index = _index_prompts(prompt_rows)
    valid_prompt_keys = {
        key for key, row in prompt_index.items() if not bool(row.get("disqualified"))
    }
    outputs = _index_outputs(
        submission_rows,
        valid_prompt_keys=valid_prompt_keys,
        expected_model_id=model_id,
    )
    thresholds = dict(_scoring.DEFAULT_LEAKAGE_THRESHOLDS if leakage_thresholds is None else leakage_thresholds)

    item_runs: list[dict[str, Any]] = []
    aurc_values: list[float] = []
    ecl_values: list[float] = []
    elicit_values: list[float] = []
    leakage_values: list[float] = []
    metric_classes: set[str] = set()

    for item in items:
        target = item["target"]["text"]
        metric_class = item["metricClass"]
        metric_classes.add(metric_class)
        explicit_prompt = item["frozenLadder"][0]["prompt"]
        explicit_tokens = max(
            _scoring.token_count(explicit_prompt), _scoring.token_count(target), 1
        )
        scored_points: list[dict[str, Any]] = []
        leakage_hits = 0
        for ladder in item["frozenLadder"]:
            prompt_text = ladder["prompt"]
            key = (str(item["id"]), str(ladder["id"]))
            packed_prompt = prompt_index.get(key)
            gate = _scoring.evaluate_leakage(prompt_text, target, thresholds)
            disqualified = bool((packed_prompt or {}).get("disqualified", gate.disqualified))
            if disqualified:
                leakage_hits += 1
                fid = 0.0
            elif key not in outputs:
                fid = 0.0
            else:
                fid = _scoring.fidelity(target, outputs[key], metric_class)
            tokens = _scoring.token_count(prompt_text)
            scored_points.append(
                {
                    "id": ladder["id"],
                    "tokens": tokens,
                    "fidelity": fid,
                    "distortion": round(1.0 - fid, 6),
                    "disqualified": disqualified,
                    "rung": ladder["rung"],
                    "paraphrase": ladder["paraphrase"],
                }
            )
        frontier = _scoring.monotone_lower_envelope(scored_points)
        item_aurc = _scoring.aurc(frontier, explicit_tokens)
        item_ecl = _scoring.ecl_at_tau(frontier, tau)
        non_leaking = [point for point in scored_points if not point["disqualified"]]
        item_elicit = _scoring.elicit_at_k(non_leaking, tau, k)
        leakage_hit_rate = round(leakage_hits / max(1, len(scored_points)), 6)
        aurc_values.append(item_aurc)
        if item_ecl is not None:
            ecl_values.append(float(item_ecl))
        elicit_values.append(1.0 if item_elicit else 0.0)
        leakage_values.append(leakage_hit_rate)
        item_runs.append(
            {
                "itemId": item["id"],
                "model": model_id,
                "frontier": frontier,
                "metrics": {
                    "aurc": item_aurc,
                    "eclAtTau": item_ecl,
                    "elicitAtK": item_elicit,
                    "leakageHitRate": leakage_hit_rate,
                },
            }
        )

    aurc_mean, aurc_ci = _scoring.summarize(aurc_values, seed=seed + 1000, samples=bootstrap_samples)
    ecl_mean, ecl_ci = _scoring.summarize(ecl_values, seed=seed + 2000, samples=bootstrap_samples)
    elicit_mean, elicit_ci = _scoring.summarize(
        elicit_values, seed=seed + 3000, samples=bootstrap_samples
    )

    return {
        "id": f"aleph-bench-m0-{model_id}",
        "track": "F",
        "split": "public",
        "seed": seed,
        "stratum": "S2",
        "metricClasses": sorted(metric_classes),
        "tau": tau,
        "k": k,
        "canaryGuid": items[0]["canaryGuid"] if items else None,
        "config": {
            "datasetPath": str(items_path),
            "decoding": "user-supplied; this scorer consumes pre-generated outputs",
            "evidenceModes": ["black_box"],
            "leakageThresholds": thresholds,
            "bootstrapSamples": bootstrap_samples,
            "reruns": 1,
        },
        "models": [
            {
                "model": model_id,
                "evidenceMode": "black_box",
                "itemCount": len(item_runs),
                "aurc": aurc_mean,
                "aurcCi95": aurc_ci,
                "eclAtTau": ecl_mean,
                "eclAtTauCi95": ecl_ci,
                "coverageAtTau": round(len(ecl_values) / max(1, len(item_runs)), 6),
                "elicitAtK": elicit_mean,
                "elicitAtKCi95": elicit_ci,
                "leakageHitRate": round(mean(leakage_values) if leakage_values else 0.0, 6),
            }
        ],
        "aggregate": {
            "aurc": aurc_mean,
            "aurcCi95": aurc_ci,
            "eclAtTau": ecl_mean,
            "elicitAtK": elicit_mean,
        },
        "itemRuns": item_runs,
        "notes": [
            "Computed by the vendored kaggle/score_outputs.py scorer.",
            "For full schema validation and audit, re-run ./aleph-bench verify in the upstream Aleph repository.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--items-path", default=str(KAGGLE_DIR.parent / "data/public_s2_items.jsonl"))
    parser.add_argument("--prompts-path", default=str(KAGGLE_DIR.parent / "data/public_s2_prompts.jsonl"))
    parser.add_argument("--submission-csv", required=True)
    parser.add_argument("--model-id", required=True)
    parser.add_argument("--out", default=None)
    parser.add_argument("--tau", type=float, default=DEFAULT_TAU)
    parser.add_argument("--k", type=int, default=DEFAULT_K)
    parser.add_argument("--bootstrap-samples", type=int, default=DEFAULT_BOOTSTRAP_SAMPLES)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    args = parser.parse_args()

    result = score_submission(
        items_path=args.items_path,
        prompts_path=args.prompts_path,
        submission_rows=args.submission_csv,
        model_id=args.model_id,
        tau=args.tau,
        k=args.k,
        bootstrap_samples=args.bootstrap_samples,
        seed=args.seed,
    )
    payload = json.dumps(result, indent=2, sort_keys=True) + "\\n"
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(payload, encoding="utf-8")
        print(f"wrote {args.out}")
    else:
        print(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
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
            "../../bench/engine/adapters/hosted_black_box.py": (
                "https://github.com/p-to-q/aleph/blob/main/bench/engine/adapters/hosted_black_box.py"
            ),
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
        "kaggle/_scoring.py": _text_bytes(_kaggle_scoring_py()),
        "kaggle/score_outputs.py": _text_bytes(_kaggle_score_outputs_py()),
        "kaggle/api_test_smoke.py": _text_bytes(_kaggle_api_test_smoke_py()),
        "kaggle/aleph_bench_m0_task.py": _text_bytes(_kaggle_task_py()),
        "evidence/mock_model_summary.csv": _csv_bytes(
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
        "evidence/mock_item_metrics.csv": _csv_bytes(
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
    artifact_hashes = {name: _sha256(data) for name, data in artifact_bytes.items()}
    artifact_bytes["croissant.json"] = _json_bytes(_croissant_metadata(artifact_hashes))
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
    allowed_files = {artifact["path"] for artifact in expected["artifacts"]}
    allowed_files.update({"checksums.sha256", "package-manifest.json"})
    for path in sorted(out_dir.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(out_dir).as_posix()
        if relative not in allowed_files:
            errors.append(f"unexpected package file: {relative}")
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
