# Benchmark release records and Kaggle harness plan

Status: proposed

Owners: Aleph Bench maintainers

Related issues: [#38](https://github.com/p-to-q/aleph/issues/38),
[#55](https://github.com/p-to-q/aleph/issues/55), and
[#59](https://github.com/p-to-q/aleph/issues/59)

Research basis:
[model-release benchmark engineering survey](../research/model-release-benchmark-engineering.md)

Last updated: 2026-09-25

## Outcome

Produce one public, replayable Aleph Bench result whose complete identity survives changes to
Kaggle, Hugging Face, GitHub presentation, model aliases, and scorer packaging.

The public user should see a simple system:

```text
Aleph Bench release
  → one exact hosted Task version
  → model runs with explicit state
  → verified scores with evidence
```

The implementation underneath must keep four immutable or append-only record classes. Kaggle is the
hosted execution surface, not the only evidence store. The current source authority is
`p-to-q/aleph@benchmark/source-v0.2`; the target post-cutover release authority is
`p-to-q/aleph-benchmark` after `p-to-q/aleph-benchmark#1` passes.

## Authority model

```text
GitHub semantic release
  ├─ protocol, data, scorer, schemas, conformance and release manifest
  ├─ append-only run/result/event index
  └─ source digests for generated public notes

Kaggle: jahyee/aleph-bench
  ├─ one stable public benchmark identity
  ├─ exact numeric Task version and hosted model runs
  └─ logs/output bundle and leaderboard scalar

Hugging Face
  ├─ exact public dataset revision and card
  ├─ public-safe evidence/result records
  └─ eval.yaml / model result adapters when available
```

The website may render these records. It does not own a fourth score table.

## Four record classes

### 1. ReleaseManifest

The release manifest defines benchmark semantics. It is frozen before any formal release run and
does not grow when another model is evaluated.

Post-cutover candidate identity (do not emit this standalone-authority shape before the cutover):

```json
{
  "schemaId": "aleph-benchmark-release",
  "schemaVersion": "1.0.0",
  "kind": "aleph-benchmark-release",
  "releaseId": "aleph-bench-release-<digest-prefix>",
  "benchmark": {
    "canonicalId": "p-to-q/aleph-bench",
    "title": "Aleph Bench",
    "protocolVersion": "0.2.0",
    "referenceProtocolVersion": "0.2.0",
    "targetScorer": "aleph-unicode@0.2.0",
    "comparabilityStatus": "unproven",
    "comparabilityReceiptSha256": null
  },
  "dataset": {
    "id": "...",
    "revision": "...",
    "itemCount": 30,
    "sha256": "..."
  },
  "callPlan": {
    "plannedCalls": 900,
    "promptCount": 180,
    "reruns": 5,
    "sha256": "...",
    "retryPolicy": "no-silent-retry-v1"
  },
  "scorer": {
    "scorerProfileId": "...",
    "scorerProfileVersion": "...",
    "sourceSha256": "...",
    "runtimeProfileId": "...",
    "runtimeProfileVersion": "...",
    "unicodeProfile": "...",
    "conformanceReceiptSha256": "..."
  },
  "package": {
    "id": "...",
    "packageVersion": "...",
    "sha256": "..."
  },
  "source": {
    "githubRepository": "p-to-q/aleph-benchmark",
    "implementationCommit": "...",
    "releaseTag": "..."
  },
  "migrationProvenance": {
    "sourceRepository": "p-to-q/aleph",
    "sourceCommit": "...",
    "purpose": "temporary-source-import-only"
  },
  "kaggle": {
    "benchmark": "jahyee/aleph-bench",
    "task": "jahyee/<task>",
    "taskVersion": 0,
    "taskSourceSha256": "..."
  },
  "huggingFace": {
    "datasetRepository": "...",
    "taskId": "aleph_bench_0_2"
  },
  "artifacts": [],
  "policies": {
    "scoreEligibility": "...",
    "modelIdentity": "...",
    "retention": "...",
    "privacy": "..."
  }
}
```

The manifest excludes model run ids and scores. Adding a model appends run and result records; it
does not mutate the semantic release.

The example above is an `unproven` pre-release candidate. Issue #77 must complete before freeze. A
zero-mismatch proof derives a new candidate with a new `releaseId`, `comparabilityStatus: "proven"`,
and the bound proof-receipt digest. That new candidate is independently verified and only then
frozen. A frozen `unproven` manifest stays unproven forever; later proof must derive and freeze a new
candidate/release identity. This uses the existing ReleaseManifest plus its bound artifact and does
not create a fifth record class.

In this explicitly post-cutover example, `source.githubRepository` is the standalone implementation
and release authority. Before `p-to-q/aleph-benchmark#1` passes, the Aleph source branch remains the
temporary source authority and no manifest may falsely claim the standalone cutover. Historical
import provenance, when retained after cutover, belongs only in the separate `migrationProvenance`
record.

Avoid circular hashes. `source.implementationCommit` identifies the already-existing source tree
used to build the release; it is not the later commit or tag that publishes this manifest. The
semantic manifest digest binds the Task/package inputs and stable target repository names only. A
later publication envelope and `result_published` event bind the exact HF commit, GitHub release
assets, and other immutable public locators. Those publication locators never get written back into
the self-hashed manifest.

### 2. RunReceipt

Every attempt gets a receipt, including preflight rejection, skipped scheduling, lost responses,
platform errors, incomplete evidence, and valid completion.

A receipt is an immutable snapshot, not a mutable status file. Later knowledge about the same
`attemptId` creates a new receipt whose `supersedes` points to the prior receipt. An explicit retry
uses a new `attemptId` and points `attemptOf` to the earlier attempt instead. The two lineage fields
must not be conflated.

Required fields:

- `receiptId`, `releaseId`, `attemptId`, optional `attemptOf` and `supersedes`;
- dispatch journal digest and quota before/after;
- Kaggle owner, Task, exact version, run id and platform state;
- requested canonical model slug, Kaggle internal version id and proxy slug;
- runtime-observed provider/model identity and mapping status;
- decoding, reasoning, tools, chat-template/system-prompt hashes and output cap;
- planned, dispatched, returned, valid and scored call counts;
- timestamps, usage, finish reasons and bounded failure summaries;
- source, output archive, sample ledger, inner receipt and envelope digests;
- platform, evidence, protocol and publication states; and
- a verifier-derived eligibility decision, never a hand-authored boolean.

### 3. ResultRecord

A result record exists only after complete coverage, model identity, artifact integrity and
independent replay pass.

It binds:

- `resultId`, `releaseId` and `receiptId`;
- metric id, direction and unit;
- exact decimal scalar and `float.hex()`;
- denominator, coverage and bootstrap method;
- item/rerun/aggregate digests;
- independent replay environment and verifier commit;
- public-safe evidence identity and planned stable relative location.

Publication happens after verification, so exact GitHub, Kaggle and HF immutable locators belong in
the publication envelope and `result_published` event. They are not backfilled into a verified
ResultRecord.

Incomplete, failed, ambiguous or withdrawn attempts have a RunReceipt and no ResultRecord.

### 4. RegistryEvent

Lifecycle change is an append-only event, not an edit of old evidence. Each event carries the prior
event digest.

Event types:

```text
release_frozen
task_bound
run_dispatched
run_bound
run_failed
evidence_downloaded
result_verified
result_published
release_superseded
release_retired
result_withdrawn
surface_drift_detected
surface_drift_resolved
artifact_tombstoned
```

`current.json`, the website leaderboard and recommended aliases are derived indexes.

## Kaggle runtime harness

The Kaggle Task must be small at the entry point and strict at every boundary. It has five stages.

```text
Task preflight
  → call plan and sample ledger
  → isolated model execution
  → deterministic scoring and aggregation
  → atomic evidence bundle + numeric return
```

### Stage A: zero-call preflight

Before opening or invoking a model chat, validate:

- embedded release id and implementation digest;
- Task source/package digest and exact attached dataset closed-world file set;
- Python, architecture, Unicode and dependency profile;
- dependency filenames, sizes, hashes, licenses, tags and import origins;
- dataset item count/order/digest, call-plan count/order/digest and scorer digest;
- canonical requested model mapping and supported SDK capabilities;
- decoding/output/reasoning parameters and no-silent-retry controller state;
- writable output directory, atomic replace, fsync, file and archive caps; and
- absence of unresolved state for the current attempt namespace.

Any failure writes a small typed blocked receipt where possible, raises, and returns no scalar.

### Stage B: durable sample ledger

Every planned call is keyed by content, not an operator run name:

```text
releaseId
× observed model revision
× itemId
× promptId
× rerunIndex
× requestConfigSha256
```

Before dispatch, persist an append-only or atomic call-ahead state. After return, retain the exact raw
string, usage, finish reason, timestamps, model actor, and response hash before normalization.

Attempt status:

```text
prepared
dispatching
ambiguous
returned
validated
scored
failed
```

Failure class:

```text
transport
rate_limit
platform
model_refusal
content_filter
parse
scorer
timeout_uncertain
incomplete
evidence_write
identity
```

An uncertain timeout is not automatically retried: the original call may still be executing or
billed. A retry is a new attempt with explicit lineage after operator review.

### Stage C: isolated execution

- Exactly one fresh chat for every `(item, prompt, rerun)` tuple.
- No context reuse, implicit fallback model, prompt rewriting, or hidden transport retry.
- Model handler and chat template identity are retained like BFCL and LiveCodeBench adapters.
- A provider response is never trimmed or coerced before raw capture.
- Empty, non-string, missing-usage, explicit-limit, near-cap and unknown-finish cases remain typed
  evidence and stop formal score eligibility.

### Stage D: scoring and aggregation

- Score only after complete, duplicate-free coverage passes.
- The portable scorer must already have passed its declared reference compatibility proof.
- Normalization, leakage, item metrics and aggregation remain independently replayable.
- Infrastructure/scorer failures return no numeric result; they are not inserted as zero.
- A numeric `0.0` is allowed only for a complete valid run whose verified metric is exactly zero.

### Stage E: evidence bundle

The Task atomically writes:

```text
run-bundle/
├── release-manifest.json
├── run-spec.json
├── run-receipt.json
├── samples.jsonl
├── responses.jsonl
├── failures.jsonl
├── items.jsonl
├── metrics.json
├── environment.json
├── task-receipt.json
└── manifest.sha256
```

Only after the bundle is durable and internally verified does the root Task return
`float(1 - aggregate_aurc)`.

## Hosted scheduling control plane

`bench.engine.kaggle_run_once` is the only approved additional-model scheduler. It already:

- requires exact owner, Task, positive version and canonical model-version slug;
- resolves and retains the platform model version id and proxy slug;
- snapshots Task, full run set and daily/monthly quota;
- rejects unresolved active runs;
- fsyncs the no-retry barrier;
- sends one direct schedule request with explicit `version_number`;
- validates skipped/redirected/contradictory responses; and
- accepts exactly one matching new run id by run-set difference.

Future work may add a read-only `reconcile-journal` operation. It must never resend the paid request.

## Lifecycle states

### Release

```text
DRAFT → CANDIDATE → FROZEN → ACTIVE → SUPERSEDED → RETIRED
```

`FROZEN` locks protocol, dataset, scorer, call plan and Task source. `SUPERSEDED` and `RETIRED`
releases remain reproducible.

### Run

```text
PREPARED
  → DISPATCHING
  → DISPATCHED_UNBOUND
  → BOUND
  → QUEUED
  → RUNNING
  → PLATFORM_COMPLETED
  → EVIDENCE_DOWNLOADED
  → REPLAY_VERIFIED
  → PUBLICATION_APPROVED
  → PUBLISHED
```

Terminal non-success states remain visible:

```text
PRECHECK_REJECTED
AMBIGUOUS_DISPATCH
PLATFORM_ERRORED
INCOMPLETE_COVERAGE
EVIDENCE_MISSING
EVIDENCE_CORRUPT
MODEL_IDENTITY_AMBIGUOUS
SOURCE_DRIFT
REPLAY_MISMATCH
POLICY_REJECTED
WITHDRAWN
```

Kaggle `Completed` is a platform state, not Aleph verification.

## Independent version axes

Never use a lone label such as `v2` for all of these:

1. `protocolVersion`: scoring and eligibility semantics;
2. scorer profile id/version: one implementation of those semantics;
3. runtime profile id/version: interpreter, Unicode provider, ABI, and platform contract;
4. package id/version/digest: the closed executable artifact;
5. schema id/version: the record contract, independent of benchmark semantics;
6. `datasetRevision`: exact items and references;
7. `harnessVersion`: model handlers, prompts, runtime and orchestration;
8. `run/attempt`: one model execution lineage; and
9. `platformRevision`: Kaggle Task version, HF commit, GitHub publication envelope.

Scoring semantic changes bump the protocol. Data corrections bump the dataset revision. Handler
fixes bump the harness. Runtime ports keep the referenced protocol and receive new scorer,
runtime, package, and schema identities. Old results are not overwritten; comparability is explicit
and starts as `unproven`. Issue #77 must derive a new, proven candidate/release identity before
freeze. A frozen unproven manifest cannot be promoted.

## Public notes generated from the manifest

Every surface shows:

- stable name `Aleph Bench` and one-sentence purpose;
- protocol, release id and manifest digest;
- dataset/scorer/runtime profile and score direction;
- exact comparability group and active/superseded/retired state;
- coverage and the statement `missing / failed / unverified ≠ 0`;
- model identity status;
- GitHub, Kaggle and HF cross-links;
- last successful surface readback; and
- known limitations, contamination posture and failure notes.

### GitHub

GitHub is the canonical specification and record index. Before cutover, that source is
`p-to-q/aleph@benchmark/source-v0.2`; after `p-to-q/aleph-benchmark#1` passes, it is the standalone
repository. A release contains the manifest, publication envelope, checksums, frozen source
package, SBOM and provenance. Human release notes are useful but not the only copy because they
remain editable. Where supported, use immutable releases and artifact attestations; keep exact
files and digests as the contract.

### Kaggle

The existing `Aleph Bench` page is the only public execution entry. Its notes identify the exact
release and Task version, planned calls, score formula, runtime profile, no-silent-retry policy,
complete-coverage gate, and evidence path. Legacy v0.2 capture is labeled `capture only / not a
score`. A failed run has no scalar, not a false zero.

The generated Task header embeds release id, Git commit, dataset/scorer/call-plan digests, runtime
support boundary and failure policy.

### Hugging Face

The dataset card includes the benchmark definition, license, citation, intended use, limitations,
exact GitHub release and Kaggle Task/version. `eval.yaml` uses a stable task id and migration table.
Every result carries exact dataset commit, source, notes and release id. Until HF verification is
actually granted, the repository is described as a community mirror.

Aleph controls its own result dataset. Optional PRs to vendor model repositories are distribution,
not the sole evidence copy.

## Retention

- **Permanent small records:** release manifests, run receipts, result records, envelopes,
  checksums, schemas and registry/drift events.
- **Permanent published evidence:** public-safe sample evidence, Task source, replay outputs and
  leaderboard snapshots for published rows.
- **Restricted evidence:** provider raw outputs, full logs and usage remain encrypted in at least
  two independent stores when policy permits. If deletion is required, retain the digest, reason,
  approver, timestamp and tombstone.
- **Disposable cache:** CI scratch space, duplicate downloads and regenerable web assets. A cache is
  never the only evidence copy.

## Read-only stability monitoring

The recurring monitor is read-only by default and does not spend model quota.

1. Verify Git tag/commit, release assets, checksums, SBOM and provenance.
2. Read the exact Kaggle Task version, public state, run set, model states, Task source/archive
   digest and leaderboard version.
3. Read the exact HF dataset commit, `eval.yaml`, files and leaderboard result metadata.
4. Join surfaces: each public score has exactly one ResultRecord; each result has one receipt/run;
   all release, dataset, scorer, model and digest identities agree.
5. Append a hashed `surface-readback/<timestamp>.json`; never overwrite an older readback.
6. On drift, append `surface_drift_detected` and mark derived presentation stale. Do not rerun a
   model or silently edit a public score.
7. After repair, append `surface_drift_resolved` with the before/after evidence.

Severity:

- Critical: Task source/version, score, release digest or exact HF revision mismatch.
- Major: public row/evidence disappears or model identity becomes ambiguous.
- Warning: human-readable page notes lag the generated manifest fragment.
- Info: display name changes while immutable identity remains intact.

## Engineering and design quality bar

The public experience should hide internal staging vocabulary without hiding evidence.

```text
README
  1. What Aleph Bench measures
  2. Reproduce a released score
  3. Evaluate a model
  4. Verify evidence
  5. Understand limitations
```

CLI commands should be verbs over explicit artifacts: `release verify`, `run plan`, `run once`,
`run reconcile`, `result replay`, `surface readback`. Every command supports `--help`, fails with a
typed human-readable message, writes machine-readable receipts, refuses overwrite, and documents
whether it can spend quota or mutate a public surface.

Code should separate:

```text
protocol/
runner/
models/
platforms/kaggle/
platforms/huggingface/
publish/
```

This is a target boundary, not authorization for a drive-by directory refactor. Move code only when
a contract is implemented and tests prove behavior unchanged.

## Implementation sequence

### P0-A: record contracts

- Add JSON Schemas for ReleaseManifest, RunReceipt, ResultRecord and RegistryEvent.
- Add closed-world serializers/verifiers, cross-field derivation and mutation tests.
- Add one example containing an explicit failed/N/A receipt and no ResultRecord.

Gate: an invalid identity, impossible state, false zero, incomplete coverage or digest drift fails
closed.

### P0-B: portable runtime proof

- Complete the Python 3.11/3.12/3.13 Unicode/scorer proof already specified in #59.
- Retain official source/wheel hashes and Linux x86-64 evidence.

Gate: the portable implementation of protocol 0.2.0 matches the reference contract or is rejected;
no package or hosted smoke alone authorizes a new candidate to declare `proven`, and proof must
precede manifest freeze.

### P0-C: numeric Kaggle harness

- Generate the self-contained Task and fake-LLM fixtures.
- Implement durable sample ledger, failure injection, evidence bundle and replay.
- Test exactly 900 unique calls and no scalar on every incomplete path.

Gate: a complete fake run returns the expected scalar and replays byte-for-byte; all injected
failures return no score and retain a typed receipt.

### P0-D: one real hosted gold run

- Run the zero/6/30/optional rehearsal ladder.
- Use the one-shot exact-version scheduler and budget gate.
- Execute one low-cost full private model run only after all earlier gates pass.
- Download, replay and independently verify before publication.

Gate: one real model has a complete, exact-identity, Kaggle-hosted score that the public artifacts
reproduce.

### P1: cross-provider and public release

- Verify a second provider.
- Freeze the semantic release and generate all page/card note fragments.
- Publish the exact HF revision and promote the existing Kaggle entry.
- Retain live readback and activate read-only stability monitoring.

Gate: GitHub, Kaggle and HF expose the same release identity and neither missing nor failed rows are
presented as zero.

### P2: usability and adoption

- Add clean-wheel packaging and supported environment matrix.
- Reduce the public README to the five-step path.
- Add community contribution workflow for result records without granting scorer authority.
- Add held-out/fresh and multilingual validity studies through new releases, never by mutating the
  current denominator.

## Budget rule

Do not “use all quota” by repeating an unknown failure. Spend only on a predeclared evidence matrix:

```text
free preflight
→ 6-call transport canary
→ 30-call item rehearsal
→ optional wall-time/archive rehearsal
→ 900-call private release candidate
→ second provider after replay passes
```

Every paid step must answer a new uncertainty about provider, handler, runtime, archive size or full
protocol behavior. Daily monitoring remains read-only unless a new release/model coverage plan explicitly
authorizes a run.

## Completion gate

This plan is complete only when one public Aleph Bench row is:

- executed on Kaggle against an exact model version;
- numerically valid under a frozen release manifest;
- complete rather than partial or cap-saturated;
- independently replayed from retained raw evidence;
- represented by one RunReceipt and one ResultRecord;
- mirrored at an exact HF revision;
- linked from the existing public Kaggle entry and GitHub release; and
- live-read back with matching identities and digests.
