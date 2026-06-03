# Aleph-Bench M0 Platform Launch Checklist

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
