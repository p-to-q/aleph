# Kaggle capture canary runbook

This runbook executes the fixed six-call Aleph-Bench v0.2 capture canary. Kaggle is only the model
transport and raw-output capture surface: it does not score v0.2. Canonical scoring remains locked
to Python 3.13 / Unicode 15.1 and is not implemented for partial canary evidence.

The task-creation request starts the task. Never follow creation with `tasks run`; that would create
another model run. Never retry an ambiguous creation. Preserve the dispatch journal and reconcile
the exact task version, run, dataset, and quota first.

Additional Task v10 compatibility captures are governed by the reviewed
[finite queue policy](../plans/kaggle-v10-daily-capture-queue.md) and its exact
[`kaggle-capture-queue-v1.json`](../../bench/config/kaggle-capture-queue-v1.json) manifest. The
manual scheduler primitive below is not standing authorization: only the merged single-step queue
controller may select a policy entry, and it may delegate at most one paid POST after every current
gate passes.

Operational note (2026-09-26): v1 is permanently stopped by its retained breaker after two queue
dispatches. Do not invoke it again or clear its root. The
[GPT-only successor](../plans/kaggle-v10-gpt-successor.md) is a contract under review and does not
authorize activation or a paid call until its verifier, activator, controller, tests, merge-SHA
readback, and automation pins are complete. The saved daily automation remains paused.

## Preconditions

- Use a clean checkout of the reviewed benchmark authority branch.
- Use Python 3.13 with `kaggle==2.2.4`, `kagglesdk==0.1.37`, `jupytext==1.19.5`,
  and `nbformat==5.11.1`.
- Build and check the deterministic v0.2 scorer-conformance package.
- Attach exactly one private Kaggle dataset with mount slug
  `aleph-bench-v02-scorer-conformance`; its file paths and bytes must match the package manifest.
  The generated task supports both Kaggle's flat `/kaggle/input/<slug>` layout and its
  fully-qualified `/kaggle/input/datasets/<owner>/<slug>` layout. Resolution is bounded to two
  directory levels and succeeds only when exactly one candidate matches every embedded file hash
  and the closed-world file set.
- Confirm no task named `aleph-bench-v0-2-capture-canary` is queued or running.
- Retain the exact canonical `kaggle_push_once` creation journal for the Task
  version. Additional-model scheduling requires that receipt; a Task URL,
  version number, downloaded notebook, or payload is not a substitute.
- Retain a Model Proxy quota snapshot. The task makes at most six logical calls and the generated
  source disables transport retry.
- The cross-provider capture profile records `reasoning: null` and omits the optional Kaggle
  `reasoning` argument. Kaggle documents that unsupported models reject that argument even when its
  value is `"none"`; provider-default reasoning is therefore an explicit capture-policy choice, not
  an implicit fallback. A future formal numeric release must freeze its own comparability policy.
- Choose a new durable private evidence directory outside the repository and ephemeral directories.

Set `ALEPH_KAGGLE_PY` to the reviewed environment. Verify the complete serializer matrix and run
the source/authority checks with that same interpreter before any remote write; using bare
`python3.13` can silently skip the identity tests when Jupytext is absent:

```bash
export ALEPH_KAGGLE_PY=/absolute/path/to/aleph-kaggle-2.2.4/bin/python
"$ALEPH_KAGGLE_PY" -c \
  "from bench.engine.kaggle_push_once import _verified_client_versions; print(_verified_client_versions())"
"$ALEPH_KAGGLE_PY" bench/tasks/kaggle/generate_v0_2_capture.py --check
"$ALEPH_KAGGLE_PY" -m unittest \
  bench.tests.test_kaggle_capture \
  bench.tests.test_kaggle_capture_task_v0_2 \
  bench.tests.test_kaggle_capture_evidence \
  bench.tests.test_kaggle_push_once \
  bench.tests.test_kaggle_run_once
```

## One-shot creation

Use that reviewed environment and an absolute, new journal path:

```bash
"$ALEPH_KAGGLE_PY" -m bench.engine.kaggle_push_once \
  --task-kind capture \
  --gate six-call \
  --dataset OWNER/aleph-bench-v02-scorer-conformance \
  --journal /absolute/private/evidence/capture-canary/creation/dispatch/push-journal.json
```

The helper validates the exact checked-in generated source, client versions, dataset count, and
latest remote task state. It fsyncs `prepared` and `dispatching` journal states before crossing the
single non-idempotent create boundary. It calls the create API exactly once without Kaggle CLI's
generic retry wrapper.

If the journal state is not `returned`, stop. Do not select a new journal path and do not call the
helper again. A `returned` journal supplies the only authorized task version for read-only status
and evidence download.

### Task-v8 notebook-identity incident

Task v8 was created once and returned before a read-only audit found that Jupytext 1.19.5 had
assigned a random nbformat cell ID. Its immutable creation journal records raw submitted-notebook
SHA-256 `997ba2ce74c6281b7c1e7da4ed33caa40d7d405585728dd99c6a8d05346f9e7c`.
The authenticated exact-version run archive preserves cell ID `5a5b4e4d`; applying that ID to the
unchanged generated source reproduces the journal hash exactly. The archive itself contains the
executed Papermill notebook, so its raw bytes also contain outputs, execution metadata, and timing
data and are not the original create-request bytes. Kaggle's backing `sourceKernelId` is mutable
across Task versions, so a later direct kernel read is not historical authority; only the retained,
hash-bound exact-run archive supports this incident explanation.

This evidence explains the mismatch but does not create a second creation authority. The original
journal remains byte-unchanged, and the scheduler, its repeated source checks, the embedded run-
journal authority, and the later evidence binder continue to reject its random notebook identity.
Task v8 is therefore creation-only evidence: its completed six-call creation run may be retained as
diagnostic history, but no additional model may be scheduled on v8. Do not hand-author a semantic
digest, delete the notebook field, substitute the executed-notebook hash, or add a v8 exception.
Future Task creation uses deterministic positional cell IDs and must pass repeated in-process and
fresh-process notebook-byte checks before the one-shot create boundary. Its v3 creation journal
binds the `jupytext-ipynb-v1-positional-cell-ids` profile, exact notebook digest, and both serializer
package versions. In the affected `jahyee` namespace, Task versions 1 through 8 remain frozen as
creation-only; hand-authoring a v3-shaped receipt for any of them is rejected. Task versions are
owner-scoped, so an independent owner may start the corrected v3 path at version 1. A v2 journal
cannot authorize an added run even if a caller supplies reconstructed source fields. See
[issue #88](https://github.com/p-to-q/aleph/issues/88).

## Exact-run binding

Wait for the returned version to reach a terminal state using read-only status. Then bind and
download its unique run:

```bash
"$ALEPH_KAGGLE_PY" -m bench.engine.kaggle_capture_evidence \
  OWNER/aleph-bench-v0-2-capture-canary \
  --version VERSION \
  --expect-dataset OWNER/aleph-bench-v02-scorer-conformance \
  --output /absolute/private/evidence/capture-canary/creation/bundle
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
and content-addressed binding. An explicit `--run-id` and `--dispatch-journal` must be supplied
together. The current binder accepts only a version-2 dispatch journal carrying verified creation
authority; it does not silently downgrade to a legacy v1 scheduler receipt. The no-journal path is
reserved for retaining the creation-triggered run as diagnostic history while it is still the sole
run on the exact Task version. Unbound evidence-schema 1.0 bundles are always
`assemblyEligible: false`; only an authority-bound bundle can enter a capture set. Historical v1
recovery requires a separate reviewed authority migration.

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

For Task v10, do not invoke this primitive directly. Issue
[#93](https://github.com/p-to-q/aleph/issues/93) adds a finite six-entry policy above it. The queue
controller must revalidate the exact Task/source/creation/run-set/catalog/quota/policy/evidence
state and then call this scheduler no more than once. A held, exhausted, expired, or tripped policy
stays read-only; changing the model or journal path does not bypass that decision.

Run the queue only from the clean checkout at the exact merged controller commit. The checked-in
v1 policy digest is
`221e5b1ce8d8096f364dbadc6ae2fd076f3397b548068e5443d4ccdfc0cde9e3`:

At activation, create the final private control root once, read its numeric POSIX device and inode,
and save those two values in the automation together with the path. They are external activation
pins, not values to recompute on each run. Replacing the pathname must therefore fail before any
trusted receipt read or paid call.

```bash
umask 077
"$ALEPH_KAGGLE_PY" -m bench.engine.kaggle_queue_once \
  --control-root /absolute/private/evidence/capture-canary/v10-queue \
  --expect-control-device ACTIVATION-PINNED-DEVICE \
  --expect-control-inode ACTIVATION-PINNED-INODE \
  --writer-id ORIGINAL-WRITER-HOST-ID \
  --expect-policy-sha256 221e5b1ce8d8096f364dbadc6ae2fd076f3397b548068e5443d4ccdfc0cde9e3 \
  --expect-execution-commit EXACT-MERGED-COMMIT \
  --execution-root /absolute/clean/aleph-checkout
```

The controller first matches the live pathname to the externally saved device/inode, then holds
that directory inode and its identity-bound lock marker under advisory locks for the whole
invocation; a same-root contender returns `held`. A pin mismatch exits without writing a breaker
into the untrusted replacement root. This does not coordinate another host or an unrelated binder
process. Never rename, replace, rotate, copy, or repoint the live control-root pathname while this
policy is active. The one-shot scheduler receives the already-open root descriptor and performs
the creation-journal reads, paid-call claim creation, and every run-journal write relative to that
descriptor with no-follow traversal. Replacing a descendant directory with a symlink cannot move
those barriers outside the activated root. After a dispatch,
poll the exact run read-only. While it is queued/running, do not invoke the binder. Once it is
completed, run the capture-evidence command below with the policy-fixed journal and bundle paths,
wait for its closed-world verification to finish, verify the bundle directory is mode `0700` and
every member is `0600`, and only then invoke the queue controller again. The run-specific
`*-evidence.json` envelope is written last and is the controller's ready marker. Never overlap the
binder and controller. Provider error, an extra run, or platform completion without that complete
Aleph evidence is a permanent breaker, not permission to retry.

The controller compares Kaggle's live run set with the **complete durable local
frontier**: every finalized queue entry plus the one current journal-bound run,
if any. It does not compare a finalized early entry with a partial prefix of
that frontier, because a legitimate later queue run would then look like an
extra run. A run-set identity or terminal-state breaker records bounded
expected and observed details in its failure message so the incident can be
audited without reconstructing it from chat history.

A breaker written by an older controller remains immutable even when a later
controller fixes the defect that caused it. Do not delete, rename, or overwrite
that receipt. Continuing the same remote Task after such an incident requires
a separately reviewed successor policy and authority migration that binds the
old breaker and evidence; see [issue #95](https://github.com/p-to-q/aleph/issues/95).

The binder pins the real output directory, requires it to be owned and empty, explicitly enforces
directory mode `0700` and member mode `0600` independent of ambient `umask`, writes the envelope
last, then reloads the exact closed-world bundle before reporting success. Keep `umask 077` as
defense in depth; a permissive shell default is not part of the evidence contract.

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
  --creation-journal /absolute/private/evidence/capture-canary/creation/dispatch/push-journal.json \
  --journal /absolute/private/evidence/capture-canary/MODEL/dispatch/run-journal.json
```

Before it creates the run journal, the helper strictly parses the retained creation journal and
requires its canonical bytes, returned state, exact owner/Task/version/dataset set, source bytes,
source SHA-256, and deterministic Jupytext notebook SHA-256 to match the current checked-in
generated capture source. It then reads the exact Task version and resolves the source-kernel ID.
When creation acknowledged a positive kernel ID, readback must match it; when creation recorded
`null`, the completed exact-version readback must supply the positive ID. The resolved identity and
the complete canonical creation receipt are content-bound into the run journal.

Any generated capture-source change requires a new one-shot private Task version created with
`kaggle_push_once` before another model may be scheduled. Do not point the current scheduler at an
older immutable Task version, hand-author a replacement receipt, accept source identity from the
payload, or add a historical v7 exception. A mismatch stops before both the dispatch journal and
the paid scheduling call.

After that authority gate, the helper independently resolves the exact canonical model-version id,
reads the complete pre-dispatch run set, rejects unresolved runs, and retains daily and monthly
quota. It then fsyncs `prepared` and `dispatching`, calls the scheduling API once without paid-call
retry, and uses read-only polling to accept exactly one new run id for the requested model and
version. A pre-existing run for the same exact model version is also a hard stop, including a
terminal run. Immediately before creating the run journal, it atomically writes a durable claim
beside the original creation journal, keyed by that receipt, Task version, and model. Concurrent
same-host attempts for the same exact model that share the original receipt therefore cannot both
cross the paid boundary, and selecting another run-journal path does not create another local
claim. Different models still require strict one-at-a-time scheduling. Retain this sidecar claim
even after success or interruption. The current generated source and original receipt bytes
are both revalidated after the final remote run-set read and before the claim is written; drift at
that boundary leaves no claim, run journal, or paid call.

The claim is deliberately not described as a global distributed lock. Separate hosts or copied
creation receipts do not share a local filesystem claim, and Kaggle exposes no idempotency key for
this paid scheduling API. Keep one original creation receipt, one control directory, and one writer
host for a Task version; if that invariant was violated, stop and reconcile the remote run set
read-only.

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

Separating original dispatch journals from closed-world evidence bundles and migrating the old
flat evidence layout are tracked independently in
[issue #83](https://github.com/p-to-q/aleph/issues/83); they are not part of this source-authority
gate.

Bind a scheduled run with both independently retained identities:

```bash
"$ALEPH_KAGGLE_PY" -m bench.engine.kaggle_capture_evidence \
  OWNER/aleph-bench-v0-2-capture-canary \
  --version VERSION \
  --run-id RUN_ID \
  --dispatch-journal /absolute/private/evidence/capture-canary/MODEL/dispatch/run-journal.json \
  --expect-dataset OWNER/aleph-bench-v02-scorer-conformance \
  --output /absolute/private/evidence/capture-canary/MODEL/bundle
```

Do not hand-author aliases or reuse a journal from another run. The runtime-observed slug must be
byte-for-byte equal to the journal's retained `modelProxySlug`; provider guessing, case folding,
punctuation normalization, and suffix stripping remain forbidden.

Keep mutable/original dispatch journals outside the final `bundle/` directory. The binder copies
the exact journal bytes under the run-specific filename named by the evidence envelope. The
closed-world loader intentionally rejects the original `run-journal.json`, a push journal, notes,
or any other extra file beside the envelope-declared members.

## Materialize a retained legacy flat layout

Older operator examples placed the original `run-journal.json` beside its already-bound copy. Do
not delete, move, or rewrite those retained files. Name the exact evidence envelope and copy only
its verified members into a new, nonexistent `bundle/` directory:

```bash
"$ALEPH_KAGGLE_PY" -m bench.engine.kaggle_capture_bundle \
  --evidence /absolute/private/evidence/capture-canary/MODEL/aleph-bench-v0-2-capture-canary-vVERSION-run-RUN_ID-evidence.json \
  --output /absolute/private/evidence/capture-canary/MODEL/bundle
```

The migration accepts exactly one extra `run-journal.json`, requires its bytes to equal the
dispatch-journal copy already bound by the envelope, snapshots and re-verifies every named source
member, writes byte-identical files exclusively, and verifies the destination through the held
directory descriptor pinned immediately after `mkdir`. Any unrelated extra, symlink, hard link,
journal drift, existing destination, directory swap after that pin, or evidence failure stops
without changing an original source file. A failure after destination creation deliberately leaves
that exclusive directory partially or fully populated. Treat it as a retained failure artifact:
do not reuse or overwrite it, and audit its exact path and provenance before any explicit removal.
The helper performs no automatic failure cleanup because portable POSIX path deletion cannot bind
an unlink or rmdir atomically to a previously observed inode.

Portable POSIX `mkdir` cannot atomically return a directory descriptor, and held descriptors do not
exclude another process running under the same UID from changing names or file contents. Keep the
destination parent private from uncooperative same-UID writers for the entire materialization,
including the `mkdir`-to-`open` boundary, writes, readback, and final checks. The helper holds the
opened destination, rechecks destination and parent path identities, then re-reads every member's
exact bytes and stable metadata before reporting success. These are point-in-time fail-closed
checks, not an atomic transaction or a same-UID security boundary.

This is only a layout migration for evidence whose version-2 run journal already carries creation
authority accepted by the current verifier. It never adds authority or changes
`assemblyEligible`. In particular,
the five retained Task-v7 envelopes bind version-1 dispatch journals without creation authority
and cannot be migrated or promoted by this command. Run 3022882 has no evidence envelope and is
outside the migration path. Historical recovery, if ever approved, requires a separate authority
migration review.

The documented nested destination adds one new `bundle/` directory member to the legacy `MODEL/`
directory. Every original flat file retains its bytes, inode, ownership, mode, link count, size,
mtime, and ctime. Access time is controlled by the filesystem and is not benchmark provenance.
The destination copies have new filesystem timestamps; authoritative remote timestamps, hashes,
and the explicit task source path remain in the byte-identical evidence envelope.

## Claim boundary

The capture payload, evidence envelope, and `CaptureSetReceipt` are not scores, benchmark results,
or leaderboard evidence. Load a bundle only by its explicit evidence filename with
`load_verified_capture_bundle`; the loader accepts an exact closed-world directory, rejects
symlinks and hard links, snapshots bounded member bytes, and reruns the full envelope verifier.
`assemble_capture_set_receipt` then compares the exact union with a content-addressed scope plan.
It never selects a latest or best run.

The current internal capture Task/source generation v4 authority defines only the six-call
`transportCanary` scope. A byte-pinned internal generation-v3 plan remains available solely to
reconstruct homogeneous legacy capture schema `1.1.0` evidence as Receipt `1.0.0` under ScopePlan
`1.0.0`; it cannot be mixed with current capture schema `1.2.0`, Receipt `1.1.0`, or ScopePlan
`1.1.0`. This internal generation is not Kaggle's platform Task revision, which is an independent
counter; the exact canonical task slug and creation-authority source identity bind that revision to
the selected internal generation. The current plan's 2,048-token request policy is intentionally
different from the v0.2 hosted decoding cap of 512, so its receipt always has
`canonicalScoringInputEligible: false`, zero complete canonical items, and fixed false
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
