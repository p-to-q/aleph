# Kaggle deployment diagnostic

This runbook covers one diagnostic-only task:
`aleph_bench_deployment_diagnostic_2048_none`. It separates Kaggle runtime, attached-package,
model-transport, output, and usage-capture failures before any canonical Aleph-Bench v0.2 run is
allowed. It does not calculate a benchmark score and must not be attached to a leaderboard.

## Why a separate task exists

The retained legacy task returned one inverse-AURC float after 180 calls. Its downloaded run still
contained detailed conversations and usage, but the root result made operational failures look like
one opaque number. It also used a Python 3.11 Kaggle image, while the v0.2 scorer fails closed unless
Python 3.13 and Unicode database 15.1.0 are both present.

The deployment canary makes those concerns independent:

1. runtime compatibility, before any model or package access;
2. exact scorer-conformance package identity;
3. Kaggle SDK/model transport capability;
4. six fixed prompt calls and isolated chat capture; and
5. non-empty output, token usage, cost/latency when exposed, and conservative output-cap diagnostics.

The scorer-conformance package remains byte-stable and still contains no model execution. The
canary is generated as a sibling task under `bench/tasks/kaggle/`.

## Immutable task contract

- registered task name: `aleph_bench_deployment_diagnostic_2048_none`, version `1`;
- Kaggle task slug: `aleph-bench-deployment-diagnostic-2048-none`;
- result type: `dict`, never `float` or `int`;
- prompts, in order: `s2-001-r1-p0`, `s2-001-r1-p1`, `s2-002-r1-p0`,
  `s2-002-r1-p1`, `s2-003-r1-p0`, `s2-003-r1-p1`;
- one fresh chat named `item_id:prompt_id` for every attempted call;
- `seed=0`, `temperature=0`, `reasoning="none"`;
- 2,048 requested output tokens per call, 12,288 maximum across all six;
- one transport attempt per logical prompt, with the supported SDK retry
  controller set to zero retries and verified before the first call; and
- stop after the first empty, invalid-usage, near-cap, non-string, oversized, or failed response.

Changing any of these requires a new task version and regenerated definition digest. Never replace
the literal prompt-id tuple with `head(6)`, a slice, or input-order discovery.

## Repository checks

Run these with Python 3.13 / UCD 15.1.0:

```bash
python3 bench/tasks/kaggle/generate_v0_2_diagnostic.py --check
python3 -m unittest bench.tests.test_kaggle_diagnostic_v0_2
python3 -m unittest bench.tests.test_kaggle_diagnostic_receipt_v0_2
python3 -m unittest bench.tests.test_kaggle_push_once
python3 -m unittest bench.tests.test_kaggle_creation_output
```

The generator reads the canonical v0.2 items and current scorer-conformance package bytes. It fails
if any selected prompt changes rung, paraphrase, leakage class, text, or identity. The checked-in
task is self-contained so Kaggle CLI can convert the one Python file to a notebook.

## Staged Kaggle operation

Do not run these commands from an unmerged branch. Task creation is execution: Kaggle runs the
file's bottom-level `.run(kbench.llm)` while creating a task version. A later model run executes it
again. Never chain task creation and `tasks run`, and never assume task creation used zero model
calls.

Kaggle CLI `2.2.4` wraps its task-creation request in a generic automatic retry. Task creation is not
known to be idempotent, so a lost response could create or execute more than one version. For this
canary, do **not** use `kaggle benchmarks tasks push`. The repository's one-shot helper writes and
fsyncs a dispatch journal before making exactly one direct creation request. The journal is the
retry barrier: keep it permanently, use a unique reviewed path for each approved operation, and do
not work around a stopped operation by choosing another path.

### Client and quota gate

Use one dedicated Python 3.13 environment for both Kaggle CLI commands and the repository helpers.
The reviewed client matrix is `kaggle==2.2.4`, `kagglesdk==0.1.37`, and `jupytext==1.19.5`.
Set `ALEPH_KAGGLE_PY` to that environment's absolute Python path; do not validate one `kaggle`
executable and run the helpers with a different bare `python3`:

```bash
export ALEPH_KAGGLE_PY=/absolute/path/to/aleph-kaggle-2.2.4/bin/python
"$ALEPH_KAGGLE_PY" -m kaggle --version
"$ALEPH_KAGGLE_PY" -m pip show kaggle kagglesdk jupytext
"$ALEPH_KAGGLE_PY" -m kaggle benchmarks --help
```

The retained version readback must match the matrix above. The one-shot helper repeats this check
and exits before authentication or any remote request when Python or a client package drifts.
Release `2.2.4` does **not** yet contain the `kaggle benchmarks quota` command documented on Kaggle
CLI's main branch. Do not confuse the
top-level `kaggle quota` GPU/TPU-hours report with Model Proxy inference spend. If the installed
release lists `benchmarks quota`, retain that output before and after creation; otherwise retain the
Model Proxy balance from Kaggle's authenticated UI. A creation must not proceed when neither method
is available.

The one-shot helper returns after the server acknowledges creation; it does not poll. Its journal
has four possible states:

| State | Meaning | Operator action |
|---|---|---|
| `prepared` | The durable journal exists but the create call was not entered | Stop; retain the journal and review before authorizing any new operation |
| `dispatching` | The request boundary was crossed or may be crossed | Treat the outcome as ambiguous; reconcile task versions, source kernels, and quota; never retry automatically |
| `ambiguous` | Dispatch or response validation raised after the boundary | Treat the server operation as possibly accepted; reconcile it; never retry automatically |
| `returned` | Kaggle acknowledged one exact task version | Use only that version for status and artifact download; `sourceKernelId` may remain `null` when Kaggle does not expose it |

An existing journal always blocks the helper, including after a process restart. Its source and
notebook hashes, gate, dataset attachment, client versions, and returned task version make the
operation auditable. Kaggle `2.2.4` can omit the source-kernel ID from a successful create
acknowledgement while the backing notebook is still being created. A response that still binds the
exact task/version is `returned`, not ambiguous; the later exact-version readback records the
source kernel when Kaggle exposes it.

Use a single operator and serialize all UI, CLI, and repository-helper actions for this task slug.
Immediately before writing the journal, the helper performs a retryable read of the latest remote
task version and records its version, state, source kernel, and datasets. It fails before dispatch if
that state is queued, running, or unknown. This closes the ordinary pending-version case but cannot
make Kaggle's create API idempotent or eliminate a race with an uncoordinated operator on another
machine. Reconcile every `dispatching` or `ambiguous` journal against remote versions and quota
before authorizing anything else.

Before either gate, set `ALEPH_KAGGLE_EVIDENCE_DIR` to an absolute, operator-controlled, durable
private directory outside the Git repository. Do not use `/tmp`, an ephemeral runner, or a path that
cleanup jobs can remove. The directory contains the only automatic retry barrier as well as raw
model output, so keep it access-controlled and backed up; never commit it:

```bash
export ALEPH_KAGGLE_EVIDENCE_DIR=/absolute/private/persistent/aleph-kaggle-diagnostic
mkdir -p "$ALEPH_KAGGLE_EVIDENCE_DIR/zero-call"
mkdir -p "$ALEPH_KAGGLE_EVIDENCE_DIR/six-call"
chmod 700 "$ALEPH_KAGGLE_EVIDENCE_DIR"
```

### Zero-prompt-call gate

First create the diagnostic **without** a dataset attachment. This creation execution is the
zero-call gate; do not schedule a separate model run:

```bash
"$ALEPH_KAGGLE_PY" -m bench.engine.kaggle_push_once \
  --gate zero-call \
  --journal "$ALEPH_KAGGLE_EVIDENCE_DIR/zero-call/push-journal.json"
```

The helper accepts only the current generator-exact source. Do not delete or edit its journal. If
the state is not `returned`, stop and reconcile it; no later command in this section is authorized.
For a returned journal, copy its exact `response.version`; do not infer a version from the latest
task. Polling status is read-only:

```bash
"$ALEPH_KAGGLE_PY" -m kaggle benchmarks tasks status \
  aleph-bench-deployment-diagnostic-2048-none
```

After creation reaches a terminal state, download and validate the unique task run for that exact
version. Replace `OWNER` and `VERSION` only with the returned identity. The helper refuses to choose
when the exact version has zero or multiple runs:

```bash
"$ALEPH_KAGGLE_PY" -m bench.engine.kaggle_creation_output \
  OWNER/aleph-bench-deployment-diagnostic-2048-none \
  --version VERSION \
  --gate zero-call \
  --expect-no-datasets \
  --output "$ALEPH_KAGGLE_EVIDENCE_DIR/zero-call"
```

If `response.sourceKernelId` in the returned journal is a positive integer, the command **must**
also include `--source-kernel-id SOURCE_KERNEL_ID`. Omit that argument only when the journal recorded
`null`; if a separately retained exact-version readback later supplies a positive ID, pass that
value instead. A separately retained `--run-id RUN_ID` may also be supplied as a cross-check. Neither
argument authorizes choosing among multiple runs: the exact version must still have exactly one run.

The command refuses non-terminal task or run state, task/version/run/dataset drift, an ambiguous run
set, unsafe or oversized zip content, an invalid receipt, and existing output files. Exit `0` proves
the missing package blocked in `package_preflight` with no active, attempted, or completed model
call. A valid `runtime_preflight` receipt with zero calls is retained with exit `2`: it proves no
model dispatch occurred, but it also proves the runtime is incompatible and the package gate was
never reached. Exit `1` means the artifact could not be bound or validated. Stop on either non-zero
exit. Also stop if Model Proxy balance changed or any named per-prompt conversation exists. A
`COMPLETED` task state alone is not evidence, and `tasks run` must not be used to repeat this gate.

### Six-call canary

Only after that gate is audited, build the exact v0.2 scorer-conformance package and upload it as a
**private** Kaggle dataset whose mount slug is `aleph-bench-v02-scorer-conformance`. The repository
package checker must pass before upload. Re-check and retain Model Proxy balance, then create one
new diagnostic version with that exact private dataset attached:

```bash
"$ALEPH_KAGGLE_PY" -m bench.engine.kaggle_push_once \
  --gate six-call \
  --dataset OWNER/aleph-bench-v02-scorer-conformance \
  --journal "$ALEPH_KAGGLE_EVIDENCE_DIR/six-call/push-journal.json"
```

If and only if the journal is `returned`, wait for terminal status and bind the exact returned
version, unique task run, and dataset while downloading its creation output:

```bash
"$ALEPH_KAGGLE_PY" -m bench.engine.kaggle_creation_output \
  OWNER/aleph-bench-deployment-diagnostic-2048-none \
  --version VERSION \
  --gate six-call \
  --expect-dataset OWNER/aleph-bench-v02-scorer-conformance \
  --output "$ALEPH_KAGGLE_EVIDENCE_DIR/six-call"
```

Apply the same source-kernel rule as the zero-call gate: pass the journal's positive
`response.sourceKernelId` with `--source-kernel-id`, and omit it only when the journal recorded
`null` and no separately retained exact-version readback supplies a positive value.

That creation is the one reviewed canary and may make all six model calls. Do **not** follow it with
`tasks run`: that can repeat the task and spend up to six additional logical calls. Audit the saved
creation archive, strict receipt, metadata, named conversations, assertion outcome, and post-creation
Model Proxy balance before any other hosted action. Stop after this creation even when it succeeds.

The task file's bottom-level `.run(kbench.llm)` creates a benchmark task run during creation. Kaggle
CLI `2.2.4` exposes that same run through `tasks status`, `tasks log`, and `tasks download`. The
repository downloader uses the supported benchmark task-run output endpoint, scopes the list request
to the exact task version, filters listed runs to that requested identity, and validates the one
unique selected run before downloading by its positive run ID. It does not use the backing-kernel
output endpoint, which may be
forbidden even to the task owner. If automation cannot retain the creation receipt and raw rows, use
the authenticated Task Details UI only for reconciliation, classify the canary as inconclusive, and
stop. Never schedule another run merely to make the artifact easier to fetch.

The task also writes `aleph-bench-v0.2-kaggle-diagnostic-receipt.json` in the Kaggle working
directory. The creation-output helper retains the original zip, extracted receipt, and binding
metadata without overwriting older evidence. Keep those files with the push journal, Model Proxy
balance snapshots, and exact package dataset version. A receipt copied separately can also be
verified from a Python 3.13 / UCD 15.1.0 checkout:

```bash
"$ALEPH_KAGGLE_PY" -m bench.engine.kaggle_diagnostic_receipt \
  /path/to/aleph-bench-v0.2-kaggle-diagnostic-receipt.json
```

The command checks the schema, content address, exact definition and implementation identities,
canonical prompt order, output hashes, usage totals, derived diagnostics, and call-state semantics.
The receipt is content-addressed but not signed.

## Zero-call gate

Kaggle's `Task.run` creates one root task chat before calling the task function. Runtime observation
is the first action inside Aleph's diagnostic helper. If either required runtime value differs, the
helper:

- does not read the attached package;
- does not invoke the `llm` object;
- does not create any per-prompt named chat;
- records `attempted=0`, `completed=0`, and `diagnosticScalar=null`; and
- returns a schema-valid blocked dictionary.

The empty SDK-created root chat is expected and does not count as a model call. The wrapper records a
Kaggle assertion that passes only when the receipt is `complete`; a blocked dictionary is therefore
retained for diagnosis while `run.passed` is false. Kaggle may still show a completed execution
state because execution and assertion outcome are distinct. Read the receipt, assertion, and named
conversations together; the absence of a leaderboard number is intentional.

## Compatible-runtime path

After the runtime passes, the task verifies exact bytes for the package manifest, checksum list,
public item JSONL, and vendored scoring core. It also reselects all six prompt IDs from the attached
JSONL and requires every embedded field and prompt digest to match. Package absence or drift blocks
with zero calls.

Only then does the task inspect the model object's SDK signature and transport type. The standard
Kaggle OpenAI-compatible proxy receives `extra_api_params={"max_tokens": 2048}`; the official GenAI
transport receives `{"max_output_tokens": 2048}`. Unknown transports and SDKs lacking explicit
`reasoning`, `seed`, `temperature`, or `extra_api_params` support block with zero calls. The
preflight also sets the OpenAI client retry count to zero or verifies the GenAI retry controller's
single-attempt state. If that transport policy cannot be changed and read back, the task blocks
before opening a prompt chat.

Before every chat open, the receipt records a `prepared` call. Immediately before `llm.prompt`, it
records `dispatching` and increments `attempted`; after a normal return it records `returned`, the
raw row, and `completed`. Each transition atomically replaces the receipt. A hard interruption can
therefore leave an explicit in-flight boundary instead of silently losing a possibly consumed call.
`attempted` means the dispatch boundary was entered, not that provider billing is proven. Any
non-null `activeCall`, or any blocked receipt with `attempted > 0`, requires manual review and must
not be automatically rerun. Costs use decimal strings so a Kaggle dictionary result cannot lose
integer precision through protobuf `Struct` conversion.

## Reading the result

| Receipt state | Calls | Meaning | Next action |
|---|---:|---|---|
| `blocked`, `runtime_mismatch` | 0 | Kaggle image cannot run the v0.2 scorer | Do not call a model; wait for a compatible image or design a separately versioned scorer profile |
| `blocked`, package reason | 0 | Attachment is missing or not the reviewed package | Only after the retained strict receipt independently proves zero attempts, fix the attachment and authorize a new one-shot creation with a new reviewed journal; never use stock `tasks push` or `tasks run` |
| `blocked`, model/SDK reason | 0 | Model identity or transport contract is unavailable | Update and review the task integration before spending calls |
| `blocked`, chat/call failure | 0–6 | Chat lifecycle or proxy failed; call-ahead state shows the last safe boundary | Inspect `activeCall`, the failed prompt, logs, named chats, and quota; do not automatically rerun |
| `blocked`, empty/usage/near-cap reason | 1–6 | Transport returned structurally inadequate evidence | Adjust a newly versioned diagnostic policy; never relabel this receipt |
| `complete` | 6 | This six-call capture path worked | Review raw rows and usage; this still does **not** authorize a full v0.2 run |

Kaggle's root conversation may be empty because every prompt deliberately runs in a separate named
chat. In Compare Outputs, select the six `item_id:prompt_id` conversations. Do not add a seventh root
model call merely to populate that view.

## Evidence boundary

Every receipt, including `complete`, fixes these fields:

```text
evidenceMode: none
protocolConformant: false
leaderboardEligible: false
publicationEligible: false
diagnosticScalar: null
```

The diagnostic has one run per six prompts, not the canonical 30-item ladder and five-rerun v0.2
contract. It cannot establish AURC, ECL@tau, Elicit@k, a model ranking, or Shortest Found. It cannot
be uploaded as Hugging Face model evidence, attached to the public Aleph-Bench leaderboard, or used
to unlock a 180- or 900-call job without a separate reviewed acceptance gate.

The strict receipt schema is
[`schemas/v0.2/aleph-bench-kaggle-diagnostic-receipt.schema.json`](../../schemas/v0.2/aleph-bench-kaggle-diagnostic-receipt.schema.json).
Repository-side verification additionally recomputes the content address and checks ordering,
digests, counts, call state, usage totals, and derived diagnostics; JSON Schema alone is not the
acceptance gate.
Legacy 180-row recovery remains a different operation documented in
[`kaggle-runbook.md`](kaggle-runbook.md).
