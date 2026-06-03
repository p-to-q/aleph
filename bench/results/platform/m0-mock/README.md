---
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
- `kaggle/aleph_bench_m0_task.py`: Kaggle Community Benchmark scaffold using the `llm.prompt(...)` task shape.
- `kaggle/api_test_smoke.py`: local stub harness for the Kaggle API-test I/O contract.

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
