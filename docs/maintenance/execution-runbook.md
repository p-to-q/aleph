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

For the earlier 318-test SOURCE-bound checkpoint, check out exact implementation
`30edf95d3378b1ed5bd8c4608d24e0aedf861916` in a fresh standalone clone and run:

```bash
python3.13 -I -S -B scripts/accept-local.py --evidence-dir ../acceptance-evidence
```

The external directory must be new and its parent must exist. Retain its exact
stage output, `SOURCE.json`, `package/` and `receipt.json`; verify source identity
and cleanliness at both ends and equality of SOURCE's package digest with the
actual export. The [318-test acceptance record](evidence/benchmark-source-governance.json)
identifies the tested source and immutable release-asset digest. The older staging
tag remains its own checkpoint and does not provide this newer evidence option.

For the E5 generated-task source checkpoint, use exact implementation
`62058a8b813a071d2dfbf4708b5a7081a6e67a1f` and the same command with a new
external evidence directory. Its [388-test acceptance record](evidence/benchmark-generated-task-source.json)
binds SOURCE, the unchanged scorer package and 38 retained original files.
Keep `generated-source/` with the raw stage logs: it contains the two task files,
strict receipt schema and E5 provenance receipt. The original parent schema is
mechanically reconstructed from four identity constant rebindings. Tests use
fake SDKs and a credential-free child process with network operations denied;
local Unix creation/binding remains available for filesystem boundary tests.
This is offline source validation. Hosted Python/SDK, decoding, portable scorer
qualification and fresh execution authorization are still required before
running those task files on Kaggle.

## Kaggle diagnostic contract — authorization consumed

The following contract records the completed one-shot attempt, not authorization
to create another Task or retry its failed control.


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

## Offline request-shape admission

The pinned SDK audit is available without another Task or model call. Use a
separate optional environment, not the product environment:

```bash
uv venv --python 3.13 /absolute/new/audit-env
uv pip install --python /absolute/new/audit-env/bin/python 'kaggle-benchmarks==0.6.3' 'openai==3.16.2'
/absolute/new/audit-env/bin/python -I -B scripts/audit-kaggle-request-shape.py --output /absolute/new/request-audit.json
```

Exit 2 means blocked admission; exit 0 means only that the audited request shapes
were preserved, not that a provider accepted them. The command uses a fresh
credential-free child, temporary home, socket/DNS guard and in-memory HTTP
transport. It exercises the real ModelProxy factory, Aleph adapter and OpenAI
serializer; its response is explicitly mocked. It never invokes `run_diagnostic`,
creates a Task, authenticates, or enables another run.

The [source-bound local receipt](evidence/kaggle-request-shape-audit.json) captured
three mock requests and zero network/model calls. Empty candidate text became
`content: null`. The default ModelProxy factory also set `support_temperature`
to false, so requested `temperature=0` became JSON null, including the
confirmation-shaped probe. The discovery/confirmation seeds remained 107/108.
This is a macOS SDK-wire audit, not Linux hosted qualification; the original
hosted run did not retain its wire request or effective provider temperature.
Treat that temperature as unknown. Do not infer deterministic decoding from the
configuration field or silently flip the SDK capability flag. A future policy
must declare supported effective decoding and a faithful control before fresh
bounded execution authorization.

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

## Historical publication status before another release

H1's historical card/Croissant correction is complete; use the
[anonymous snapshot auditor](hf-h1-readback.md) and retained byte-level result
before repeating a historical publication task. Standalone PR #29 now supplies
the independently reviewed offline HF/Croissant wrapper (423 tests / four expected
skips; actual directory/config loading 30/240 rows). H2 still requires a reviewed
release identity, installed-distribution and portable/platform qualification,
explicit authority transition, and authenticated publication with readback.
This progression grants no new Kaggle execution authorization.
