# Execution runbook: local smoke to larger validation

## Current local route

Use a clean Git source and retain its exact commit. Run `npm ci`, `npm run lint`,
`npm test`, `npm run build` and `npm audit --omit=optional`. Run the built app,
check `/health`, fixture selection, file import/export and unavailable-backend
notices. These checks do not call a model provider.

For the pinned Apple Silicon model smoke, follow
[the live canary receipt](../research/2026-11-27-mlx-canary-receipt.md). Use the
pinned MLX/model snapshot, a new output directory, and explicit timestamp:

```bash
search/.venv/bin/python -m search.engine.canary run --bundle /absolute/new/bundle --created-at YYYY-MM-DDTHH:MM:SSZ
python3 -m search.engine.canary verify --bundle /absolute/new/bundle
python3 -m search.engine.canary_evidence /absolute/new/bundle
```

Run verification again in a separate interpreter with no model runtime. Retain
model/source/tokenizer identities, raw outputs, usage, event stream and projection.
The existing smoke target `42` only checks plumbing and bounded arithmetic.

## Standalone benchmark route

Clone `p-to-q/aleph-benchmark` at the recorded staging tag. Use CPython 3.13 /
UCD 15.1.0 on POSIX and write output outside the source:

```bash
python3.13 -I -S -B scripts/accept-local.py > ../acceptance.json
```

Require clean source, all explicit acceptance steps, skip counts, conformance
vectors and the pinned package-tree digest. Staging acceptance is not authority
cutover, an installed-wheel release, or a model score.

## One fresh Kaggle small diagnostic

Issue #107 owns the next hosted transition after #106. Check current SDK/catalog,
free quota and absence of active paid automation. Freeze a fresh source/notebook,
model mapping, decoding, call budget, policy and runtime. Preserve at least
max($2,20% of DAILY) and 20% of MONTHLY. Never enable paid overage or paid compute.
Fsync a unique one-shot dispatch journal before task creation. Creation can run
the notebook: do not also invoke `tasks run`, retry an ambiguous create, or use a
new journal to bypass the one-run limit. Complete path: one proposer, four
discovery calls, one fresh protected confirmation. Capture exact task version/run,
raw outputs, usage, quota before/after and a closed archive. Verify offline before
claiming completion. Every failure is retained and stops the run. No public score
or HF numeric update follows from this diagnostic.

The 2026-11-27 authorization has now been consumed by one task/run. See the
[terminal receipt](evidence/kaggle-107-terminal.json): empty prompts are rejected
by this model path. No confirmation completed. Do not rerun the dated runner.
Before another authorization, choose and version a provider-compatible null
control: a shared, non-target-bearing scaffold changes the experimental context
and must be declared and costed for every candidate, not silently substituted
only for the failed control. Alternatively predeclare the null baseline as
unsupported for a model and use an appropriate comparison design. Validate the
actual serialized request shape offline before the next hosted run.

## Larger-scale admission

Freeze a finite target set, controls, metrics, decoding, model versions and
confirmation rules before execution. First one item/model, then a declared small
batch, then a larger pre-budgeted matrix. Require complete evidence and reserve
at each boundary; missing usage stays unknown. Estimate cost from measured small
runs and obtain fresh authorization for spending beyond free allocations.
Implementations already available are the engine, protected confirmation, raw
receipts, offline replay and standalone acceptance. Portable scorer/cross-runtime
proof, full source authority transition, H2 publication, representative multi-model
validation and scientific power/calibration remain separate unfinished gates.
Never scale by waking an expired v10 controller.
