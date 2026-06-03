# Aleph-Bench M0 Plan

This plan records the repository boundary change for the first benchmark artifact. It exists because M0 adds schemas, core types, seed data, engine code, and benchmark evidence.

## Intent

Aleph-Bench compares models by asking how much prompt coordinate length each model needs to reproduce a fixed target under a fixed ladder, metric, decoding rule, leakage gate, and budget.

The M0 target is deliberately narrow:

- Track F, Frozen Ladder.
- One public split.
- One stratum, S2 compositional synthetic targets.
- Thirty seed items.
- A deterministic mock three-model result that proves the pipeline, schemas, leakage gate, and metrics are runnable.
- A hosted black-box adapter path for future real-model runs when server-side credentials exist.

## Boundary

M0 extends the existing `AlephRun` contract instead of replacing it. A benchmark result is an aggregate over many `AlephRun` objects:

```text
BenchItem
  -> frozen ladder prompts
  -> per-model AlephRun
  -> non-leaking frontier
  -> per-item metrics
  -> BenchResult model summaries
```

The aggregate layer is necessary because Aleph-Bench compares model families across items, but individual item runs still use `TargetOutput`, `CandidatePoint`, `SearchConfig`, and `ObservationSet`.

## Acceptance Gate

- `schemas/aleph-bench-item.schema.json` and `schemas/aleph-bench-result.schema.json` exist.
- `packages/core/src/bench.ts` exports `BenchItem`, `BenchResult`, and related types.
- `bench/data/public/s2/` contains 30 schema-shaped S2 items with a shared canary GUID.
- `bench/engine/` can evaluate a frozen ladder with a leakage gate, per-prompt rerun variance receipts, AURC, ECL@tau, Elicit@k, bootstrap 95% CIs, and deterministic mock adapters.
- `bench/run.py` can emit a schema-valid result.
- `bench/results/m0-first-run.json` records the deterministic three-model mock run.
- `docs/benchmark/m0-evidence.md` states what was measured, what is mock evidence, what separated, and what remains to run with real black-box models.
- `aleph-bench doctor` reports dataset validity, leakage-gate distribution, hosted adapter readiness, and estimated generation count before a real black-box run.
- `aleph-bench manifest` writes a schema-valid no-call review artifact listing non-leaking prompts and gated anchors before spending hosted model calls.
- `aleph-bench run --cache-dir ...` can reuse completed adapter responses so hosted runs are resumable.
- `aleph-bench verify` audits dataset, result, manifest, and canonical `AlephRun` contract consistency before a reviewer reads benchmark numbers.
- `aleph-bench report` renders model and per-item markdown tables from a schema-valid result JSON.
- `aleph-bench audit` checks the original M0 acceptance gates, including dataset integrity, canonical `AlephRun` validation, seed 0 reproducibility, seed 1 rank stability, non-overlapping AURC CIs, IIA, leakage gating, and evidence-note honesty phrases.
- `schemas/aleph-bench-audit.schema.json` and `bench/results/m0-audit.json` record the generated acceptance-gate receipt for the checked-in mock result.
- `schemas/aleph-bench-bundle.schema.json` and `bench/results/m0-bundle.json` record file digests for the checked-in mock evidence bundle.
- `python3 -m unittest discover bench/tests`, `npm run test`, and `npm run lint` pass.

## Out Of Scope

- Public leaderboard claims.
- Global shortest-prompt claims.
- White-box or token-loss claims without logits.
- Treating mock results as model evidence.
- ARCA, GCG, or soft-prompt adapters.
- UI changes for benchmark browsing.
