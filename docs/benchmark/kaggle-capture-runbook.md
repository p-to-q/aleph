# Kaggle capture canary runbook

This runbook executes the fixed six-call Aleph-Bench v0.2 capture canary. Kaggle is only the model
transport and raw-output capture surface: it does not score v0.2. Canonical scoring remains locked
to Python 3.13 / Unicode 15.1 and is not implemented for partial canary evidence.

The task-creation request starts the task. Never follow creation with `tasks run`; that would create
another model run. Never retry an ambiguous creation. Preserve the dispatch journal and reconcile
the exact task version, run, dataset, and quota first.

## Preconditions

- Use a clean checkout of the reviewed benchmark authority branch.
- Use Python 3.13 with `kaggle==2.2.4`, `kagglesdk==0.1.37`, and `jupytext==1.19.5`.
- Build and check the deterministic v0.2 scorer-conformance package.
- Attach exactly one private Kaggle dataset with mount slug
  `aleph-bench-v02-scorer-conformance`; its file paths and bytes must match the package manifest.
  The generated task supports both Kaggle's flat `/kaggle/input/<slug>` layout and its
  fully-qualified `/kaggle/input/datasets/<owner>/<slug>` layout. Resolution is bounded to two
  directory levels and succeeds only when exactly one candidate matches every embedded file hash
  and the closed-world file set.
- Confirm no task named `aleph-bench-v0-2-capture-canary` is queued or running.
- Retain a Model Proxy quota snapshot. The task makes at most six logical calls and the generated
  source disables transport retry.
- The cross-provider capture profile records `reasoning: null` and omits the optional Kaggle
  `reasoning` argument. Kaggle documents that unsupported models reject that argument even when its
  value is `"none"`; provider-default reasoning is therefore an explicit capture-policy choice, not
  an implicit fallback. A future formal numeric release must freeze its own comparability policy.
- Choose a new durable private evidence directory outside the repository and ephemeral directories.

The generated source must be exact before any remote write:

```bash
python3.13 bench/tasks/kaggle/generate_v0_2_capture.py --check
python3.13 -m unittest \
  bench.tests.test_kaggle_capture \
  bench.tests.test_kaggle_capture_task_v0_2 \
  bench.tests.test_kaggle_capture_evidence \
  bench.tests.test_kaggle_push_once
```

## One-shot creation

Set `ALEPH_KAGGLE_PY` to the reviewed environment and use an absolute, new journal path:

```bash
"$ALEPH_KAGGLE_PY" -m bench.engine.kaggle_push_once \
  --task-kind capture \
  --gate six-call \
  --dataset OWNER/aleph-bench-v02-scorer-conformance \
  --journal /absolute/private/evidence/capture-canary/push-journal.json
```

The helper validates the exact checked-in generated source, client versions, dataset count, and
latest remote task state. It fsyncs `prepared` and `dispatching` journal states before crossing the
single non-idempotent create boundary. It calls the create API exactly once without Kaggle CLI's
generic retry wrapper.

If the journal state is not `returned`, stop. Do not select a new journal path and do not call the
helper again. A `returned` journal supplies the only authorized task version for read-only status
and evidence download.

## Exact-run binding

Wait for the returned version to reach a terminal state using read-only status. Then bind and
download its unique run:

```bash
"$ALEPH_KAGGLE_PY" -m bench.engine.kaggle_capture_evidence \
  OWNER/aleph-bench-v0-2-capture-canary \
  --version VERSION \
  --expect-dataset OWNER/aleph-bench-v02-scorer-conformance \
  --output /absolute/private/evidence/capture-canary
```

If the journal records a positive `sourceKernelId`, also pass
`--source-kernel-id SOURCE_KERNEL_ID`. For the creation-triggered run, omitting `--run-id` keeps the
original exactly-one-run rule. Once a reviewed operator deliberately adds model runs to the same
task version, every evidence download must pass the independently retained `--run-id RUN_ID`; the
binder selects that exact ID and still rejects missing or duplicate matches.

The binder must retain the original archive, exact capture payload, and evidence envelope without
overwriting existing files. A successful six-call transport canary has six planned, attempted,
completed, and returned rows; no active call; exact prompt and output strings; token usage for each
row; `captureComplete: true`; and `canonicalReplayEligible: true`. Any partial, duplicate, missing-
usage, near-token-cap, unknown-finish, dataset-drift, or source-drift state is evidence of that
failure, not authorization to rerun.

Kaggle's task-run API may return only the model basename (for example, `gemini-3.7-flash`) while
the runtime actor and ATIF preserve the provider-qualified slug (`google/gemini-3.7-flash`). The
binder accepts only this exact suffix relationship and retains both raw values; a different
provider-qualified slug still fails closed.

Some official catalog entries use different scheduled and Model Proxy slugs. This is not a reason
to normalize names. For a run created by `kaggle_run_once`, pass its exact reconciled journal with
`--dispatch-journal`. The binder verifies the journal's owner, task, version, run, scheduled model,
numeric catalog IDs, and exact `modelProxySlug`, then retains an exact byte-for-byte journal copy
and content-addressed binding. Without that journal, only the existing exact basename and frozen
`model@revision` relationship are accepted.

Catalog-bound envelopes use evidence schema `1.1.0`; unbound envelopes continue to use `1.0.0`.
The verifier accepts both versions, but `1.0.0` cannot contain a `modelCatalogBinding`. The optional
field is absent, never `null`.

`kagglesdk==0.1.37` also drops `tzinfo` while deserializing Benchmark API timestamps whose service
semantics are UTC. The binder restores UTC only for those typed SDK `datetime` values; arbitrary
timestamp strings still pass through strict offset-aware validation.

## Add one model to an existing exact version

Task creation starts its first model run. For every deliberately added model after that, use the
reviewed one-shot scheduler. Do not use `kaggle benchmarks tasks run`: Kaggle CLI 2.2.4 targets the
latest version, retries the paid schedule request, and does not return the new run id.

First list the platform's canonical model-version slugs without scheduling anything:

```bash
"$ALEPH_KAGGLE_PY" -m kaggle benchmarks tasks models
```

Then provide the exact Task version from the retained creation journal and a new absolute journal
path:

```bash
"$ALEPH_KAGGLE_PY" -m bench.engine.kaggle_run_once \
  --owner OWNER \
  --task aleph-bench-v0-2-capture-canary \
  --version VERSION \
  --model CANONICAL-MODEL-VERSION \
  --journal /absolute/private/evidence/capture-canary/MODEL/run-journal.json
```

The helper independently resolves the exact canonical model-version id, reads the exact Task and
complete pre-dispatch run set, rejects unresolved runs, and retains daily and monthly quota. It then
fsyncs `prepared` and `dispatching`, calls the scheduling API once without paid-call retry, and uses
read-only polling to accept exactly one new run id for the requested model and version.

Only `state: "reconciled"` authorizes evidence download with that retained run id. These states do
not authorize another schedule request:

- `ambiguous`: the request may have reached Kaggle, or the response/run-set identity contradicted;
- `not_scheduled`: Kaggle explicitly skipped the request; and
- `returned_unreconciled`: the paid request returned, but its unique run id was not yet proved.

A reconciled journal has exactly one of two scheduler-authored success shapes: either the schedule
response is present and `dispatchFailure` is absent, or the response was lost, `dispatchFailure`
retains that transport exception, and the final successful read-only observation proves one exact
new run equal to `reconciliation.run`. The binder accepts both shapes. It still rejects
`responseFailure`, a non-null terminal `failure`, any non-reconciled state, and any mismatch in the
task, run, model, or catalog record. It also replays the journal's run-set proof: preflight IDs must
be ordered and unique, read failures may precede recovery, every successful observation's
`newRuns` must equal its exact delta from preflight, and the final `runIds` must be precisely
preflight plus the bound run.

Do not delete or overwrite a failed or ambiguous journal. It is the permanent attempt receipt.
Quota movement is supporting evidence, not run identity; an unavailable quota-after read does not
erase an otherwise unique exact-version run binding.

Bind a scheduled run with both independently retained identities:

```bash
"$ALEPH_KAGGLE_PY" -m bench.engine.kaggle_capture_evidence \
  OWNER/aleph-bench-v0-2-capture-canary \
  --version VERSION \
  --run-id RUN_ID \
  --dispatch-journal /absolute/private/evidence/capture-canary/MODEL/run-journal.json \
  --expect-dataset OWNER/aleph-bench-v02-scorer-conformance \
  --output /absolute/private/evidence/capture-canary/MODEL
```

Do not hand-author aliases or reuse a journal from another run. The runtime-observed slug must be
byte-for-byte equal to the journal's retained `modelProxySlug`; provider guessing, case folding,
punctuation normalization, and suffix stripping remain forbidden.

## Claim boundary

The capture payload, evidence envelope, and `CaptureSetReceipt` are not scores, benchmark results,
or leaderboard evidence. Load a bundle only by its explicit evidence filename with
`load_verified_capture_bundle`; the loader accepts an exact closed-world directory, rejects
symlinks and hard links, snapshots bounded member bytes, and reruns the full envelope verifier.
`assemble_capture_set_receipt` then compares the exact union with a content-addressed scope plan.
It never selects a latest or best run.

The current generated authority defines only the six-call `transportCanary` scope. Its 2,048-token
request policy is intentionally different from the v0.2 hosted decoding cap of 512, so its receipt
always has `canonicalScoringInputEligible: false`, zero complete canonical items, and fixed false
leaderboard/result/publication flags. The checked-in canonical authority registry is empty: even a
synthetic 900-row set and a self-consistent model mapping remain ineligible until a separate review
adds the exact formal 512-token scope-plan id, request-policy digest, and content-addressed model-
mapping id. Do not hand-author those values or reinterpret the current full-shard-plan digest.

`serialize_capture_set_receipt` checks schema, content identity, and internal consistency only. A
serialized receipt is not authoritative on its own because it does not carry the full scope-plan
body or the retained bundle bytes. Before scorer use, call `verify_capture_set_receipt` with the
exact bundles, scope plan, and model mapping; it reassembles the receipt and compares every field.

A later reviewed canonical replay must consume an exact registered `canonicalFull` receipt under
Python 3.13 / UCD 15.1 and produce a separately verified `BenchManifest` and `BenchResult`. A public
Kaggle or Hugging Face score still requires the separate publication gate.
