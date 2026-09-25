# Kaggle capture-only and canonical offline scoring plan

Status: proposed  
Tracking issue: [#38](https://github.com/p-to-q/aleph/issues/38)  
Target protocol: Aleph-Bench `0.2.0`  
Last updated: 2026-09-25

## Objective

Make Kaggle useful as a model-execution surface even when its managed image cannot reproduce the
frozen Aleph-Bench v0.2 scoring runtime. Kaggle will capture exact prompts, raw model outputs, usage,
and run identity. A separate Python 3.13 / Unicode Character Database (UCD) 15.1 process will verify
that capture and produce the canonical score.

This plan does not weaken the v0.2 runtime lock, invent a score that Kaggle did not compute, or turn
a transport receipt into leaderboard evidence.

## Observed problem

Aleph-Bench v0.2 pins Python 3.13 and UCD 15.1 because Unicode normalization and classification are
part of the scorer contract. The observed Kaggle image provides Python 3.11 and UCD 14. Its valid
zero-call diagnostic therefore stopped at `runtime_preflight`, before package access or a model
dispatch. That is the correct result for in-process v0.2 scoring, but it also prevents Kaggle from
being used only to collect raw observations.

The runtimes are not interchangeable. A local planning audit found:

- a local comparison of the 1,676 strings currently present in scorer conformance vectors and the
  canonical public S2 items found no score-relevant difference;
- an exhaustive, single-code-point comparison of all 1,114,112 Unicode code points under local
  Python 3.11.9/UCD 14.0 and Python 3.13.2/UCD 15.1 found 829,834 code points with at least one
  observed property difference: 5,116 category differences, 829,834 East Asian Width differences,
  and 62 NFKC differences;
- case folding, NFC, and whitespace classification had no single-code-point differences in that
  comparison, but the comparison did not claim exhaustive multi-code-point normalization coverage.

Those differences touch the v0.2 leakage implementation directly: it uses NFKC, Unicode category,
and East Asian Width. They also produce concrete scorer drift. With the frozen thresholds, prompt
`U+1E030` against target Cyrillic `U+0430` is not disqualified under UCD 14 but is disqualified under
UCD 15.1 after NFKC. A combining-mark example produces normalized-edit similarity `0.666667` under
UCD 14 and `1.0` under UCD 15.1. The current fixtures show that today's checked-in inputs happen to
agree; they do not prove that arbitrary model output will agree. Removing the runtime lock would
silently change the protocol.

The audit scripts currently live outside the repository, so these counts are planning evidence, not
a release receipt. The first proof slice below makes the method, official input digests, and compact
results durable before an implementation or publication claim relies on them.

The existing design already provides the useful separation point: adapters retain the raw decoded
string before normalization, and the verifier can recompute item runs from retained outputs.

A follow-up SDK audit at Kaggle `kaggle-benchmarks` commit
`6df5cef8750afc2b7aad084202575daaa5e49b4c` found that the public `Usage` contract exposes input
tokens, output tokens, input/output cost, and backend latency, but no finish reason. The message and
protobuf serialization paths likewise do not retain a finish reason. Capture schema 1.1 therefore
records a missing finish reason as an explicit diagnostic rather than treating an unavailable SDK
field as a failed run. Missing input/output token counts, a known token-limit finish reason, an
unknown finish reason, or output usage within the frozen near-cap margin remain replay blockers.

## Decision

1. The v0.2 scorer, dataset, normalization, leakage policy, rerun policy, Python 3.13 requirement,
   and UCD 15.1 requirement remain unchanged.
2. A Kaggle capture task may verify frozen file bytes, dispatch a frozen call plan, and retain raw
   responses on a non-canonical Python runtime. It must not execute Unicode normalization, leakage
   scoring, fidelity scoring, AURC, ECL, Elicit, bootstrap aggregation, or ranking.
3. The Kaggle task emits a separately versioned immutable **capture payload**, not a `BenchResult`.
   The payload has no score and is never leaderboard-, release-, or publication-eligible by itself.
4. The downloader preserves the payload and constructs an outer **capture evidence envelope** that
   binds its exact bytes to one task version, one unique exact run, the downloaded archive, and the
   platform readback. It must use the benchmark task-run output endpoint, not infer a backing kernel
   slug.
5. Only a Python 3.13/UCD 15.1 offline command may turn a complete, verified capture set into a v0.2
   `BenchResult`. The existing canonical verifier must then reproduce the complete result from its
   retained raw outputs.
6. Native Kaggle scoring remains a separate future design problem. A portable implementation must
   receive a new protocol, scorer, schema, and runtime-profile identity because the Python 3.13/UCD
   15.1 runtime is part of the frozen v0.2 contract. Exhaustive equivalence may establish numerical
   comparability with v0.2; it cannot relabel the implementation as protocol `0.2.0`. Compatibility
   is never asserted from package version metadata alone.

## Alternatives considered

### Run v0.2 directly on UCD 14

Rejected. The concrete leakage and fidelity counterexamples prove semantic drift even though the
current conformance fixture passes on both runtimes.

### Capture on Kaggle and score under the reference runtime

Selected for the first reliable path. It changes no scorer dependency, keeps the compiled-code trust
boundary off Kaggle, and uses the raw-output/replay separation that v0.2 already requires. Its cost is
that the Kaggle-native scalar is intentionally non-authoritative.

### Certify a portable Unicode 15.1 scorer

Promising follow-up, but not a shortcut. A local capability check indicates that
`unicodedata2==15.1.0` exposes the normalization, category, combining-class, and East Asian Width
APIs needed on Python 3.11; the durable proof and target-Linux validation remain future work.
It does not replace `str.casefold()`, `str.isspace()`, or no-argument `str.split()`, so those semantics
must also be frozen from the reference runtime. A credible profile needs:

- separately versioned scorer-profile, runtime-profile, package, and schema identities while
  preserving the v0.2.0 reference bytes;
- full UCD 15.1 normalization conformance and exhaustive property comparison;
- frozen full-casefold and Python 3.13 whitespace tables with provenance hashes;
- differential full-scorer tests over adversarial multi-code-point strings;
- an audited, hash-pinned wheel/package with license, ABI, architecture, import-path, and no-network
  checks before any model access; and
- a new zero-call Kaggle preflight before a separately authorized six-call run.

The portable profile is a separately identified implementation of protocol 0.2.0, targeting
`aleph-unicode@0.2.0`. Its scorer profile, runtime profile, package, and schema identities remain
separate, and `comparabilityStatus` begins as `unproven`. Only issue #77's canonical zero-mismatch
receipt may authorize a narrowly worded comparability claim. Any mismatch forbids that claim and
keeps its leaderboard isolated. Protocol 0.3.0 is reserved for issue #35's semantic changes; see
[ADR 0006](../decisions/0006-benchmark-version-identity.md).

## Non-negotiable invariants

### Frozen inputs and identities

- Bind protocol version, dataset id/count/digest, prompt ids and order, prompt UTF-8 digests, rerun
  indices, decoding request, call cap, and shard plan before any hosted call.
- Bind owner, task slug, task version, run id, model slug, task definition digest, package digest, and
  observed capture interval in the downloaded evidence chain.
- Hash and retain the exact downloaded task-run archive, embedded task source, and capture-payload
  bytes in the outer evidence envelope. A content-addressed payload detects accidental drift but is
  not a signature, authorization record, or proof of origin by itself.
- Define an explicit Kaggle-to-canonical model identity mapping. A mutable platform slug must not be
  presented as a provider revision that Kaggle did not expose.
- Do not use one task listing to guess whether an ambiguous create request succeeded. Creation is a
  non-idempotent operation and must not be retried automatically.

### Raw-output preservation

- Preserve every string exactly after JSON decoding. Do not trim, case-fold, normalize newlines,
  normalize Unicode, or coerce non-string values.
- Store the exact prompt text as well as its frozen identity. Record a digest and code-point count for
  every retained prompt and output.
- Define a string digest as SHA-256 of
  `json.dumps(value, ensure_ascii=True, allow_nan=False, separators=(",", ":"))` encoded as ASCII,
  rather than ambient UTF-8 error handling. This preserves a lone surrogate returned through escaped
  JSON without crashing a checkpoint write. Mark it explicitly, preserve it in capture evidence, and
  block canonical replay instead of coercing or dropping it.
- Distinguish an empty string, a missing value, a non-string value, an omitted oversized value, and a
  failed call.
- Treat usage fields as observations. Preserve the distinction between missing and integer zero; do
  not synthesize usage from text length.
- Record finish reason when the SDK exposes one. Its absence is a non-blocking observability warning
  only when input/output token counts are present and the observed output is below the frozen
  near-cap threshold; known limit or unknown non-null reasons still block replay.

### Recoverable call state

- Persist `prepared -> dispatching -> returned` (or `failed`) around each dispatch, with attempted,
  completed, and active-call state.
- Use one uniquely named conversation per prompt and rerun. A duplicate conversation, prompt/rerun
  pair, or response row fails verification.
- Never auto-reschedule a partial or ambiguous run. Preserve it for inspection and require an
  explicit new operation for any replacement shard.
- The task-creation command performs one create call. Because creation already starts the generated
  task, it must not be chained with `tasks run`.

### Evidence boundary

- A diagnostic canary proves only the calls named by that canary.
- A capture artifact proves only transport and raw capture under its recorded identities.
- A complete capture set becomes model evidence only after canonical offline scoring and full
  verification. Publication remains a separate, explicitly authorized operation.

## Artifact and trust flow

```text
frozen v0.2 dataset + call plan
  -> zero-call manifest and package checks
  -> Kaggle capture-only task
  -> exact task/version + unique task-run download
  -> immutable task-emitted capture payload
  -> run-bound capture evidence envelope and cross-field verification
  -> complete capture-set assembly
  -> Python 3.13 / UCD 15.1 canonical scoring
  -> v0.2 BenchManifest + BenchResult with retained raw outputs
  -> canonical offline verifier
  -> separately authorized release or publication
```

The trust boundary is deliberately asymmetric: a capture task can run on Python 3.11 because it does
not interpret Unicode for scoring, while the converter must fail closed anywhere other than the
frozen scorer runtime.

## Capture contract

The contract has two layers because code running inside the task may not know the platform-assigned
task-version and run ids.

The task-emitted capture-payload schema should make the absence of a score structural, not
conventional. At minimum it must cover:

- artifact kind and capture schema version;
- target protocol and immutable dataset/package/call-plan identities;
- declared task/source identity, model observation, and capture-runtime observation available inside
  the task;
- requested decoding values and transport retry policy;
- planned, attempted, completed, and active call state;
- shard id, full shard plan digest, and exact `(item, prompt, rerun)` coverage;
- exact prompt text and identity, raw output or explicit omission/failure state, canonical string
  digests, usage, and capture timestamp per row;
- derived diagnostics and a content-addressed artifact id; and
- fixed `leaderboardEligible: false` and `publicationEligible: false` claims.

The outer evidence-envelope schema should preserve the exact payload bytes and add owner, task slug,
server-assigned version, run id, model readback, terminal state, dataset attachments, download time,
archive/source/payload digests, and pagination/reconciliation limits. It must not rewrite the inner
payload to make platform observations look task-observed.

Both schemas must reject score fields. Their verifiers must recompute content identities and every
derivable count or diagnostic rather than trusting redundant values. This detects inconsistency and
drift relative to the retained source archive; it does not authenticate an attacker-controlled
replacement whose ids were recomputed. Publication authority and manual platform readback remain
separate gates.

## Bounded execution ladder

The canonical dataset has 180 non-leaking prompts and v0.2 requires five reruns, for 900 model calls
per model. A full run is not a smoke test and must not be the first hosted operation.

Use these gates in order:

1. zero model calls: generation, schema, package, task-source, downloader, and offline replay tests;
2. six calls: the fixed transport/capture canary, only after its code is merged and separately
   authorized;
3. one predeclared item shard: six non-leaking prompts x five reruns = 30 calls;
4. additional predeclared shards within an operator-confirmed quota envelope; and
5. full 900-call coverage only under a separate run plan and publication issue.

Sharding is part of the frozen, content-addressed call plan, not an ad hoc resume mechanism. The
assembler accepts an exact, non-overlapping union of planned shard rows and fails closed on gaps,
duplicates, policy drift, model drift, or unplanned calls.

## Implementation slices

Each slice has one acceptance gate and should be a separate PR.

### Slice 0: durable Unicode compatibility proof

- Check in a bounded proof harness and compact machine-readable receipt for the Python 3.13/UCD
  15.1 reference, Python 3.11/UCD 14 negative control, and Python 3.11/`unicodedata2` candidate.
- Pin the official Unicode conformance input URLs and SHA-256 digests.
- Pin or provision the exact interpreter builds through version-asserted paths or digest-pinned
  CI/container images, and record full interpreter/platform identity in the receipt.
- Cover the known leakage/fidelity counterexamples and clearly label single-code-point versus
  multi-code-point coverage.

Gate: a clean checkout in the declared proof environments can reproduce the claimed counts and
counterexamples without a model or Kaggle access; the proof changes no frozen scorer or release
artifact.

### Slice 1: capture schema and pure verifier

- Add a strict raw-capture schema and a pure verifier/serializer.
- Prohibit score fields and recompute row counts, coverage, call state, diagnostics, and artifact id.
- Add malformed, duplicate-key, oversized, non-finite, path, and cross-field tests.

Gate: hostile local fixtures cannot be mistaken for a complete capture or a `BenchResult`.

### Slice 2: generated capture task

- Generate an import-safe, self-contained Kaggle task from canonical inputs.
- Verify package bytes and prompt hashes without scorer imports or Unicode interpretation.
- Implement no-retry calls, named-chat isolation, atomic checkpoints, bounded reads/writes, and raw
  output/usage capture.
- Keep generated source checked by a deterministic `--check` command.

Gate: offline fakes prove the task on Python 3.11/UCD 14 and Python 3.13/UCD 15.1 emits identical
capture semantics, while invoking the v0.2 scorer on the former still fails closed.

### Slice 3: exact-run reconciliation

- Generalize or reuse the existing exact task/version/run binding without weakening the diagnostic
  path.
- Download only through Kaggle's task-run output API with source included.
- Validate task, version, dataset attachments, run, model, terminal state, and archive membership
  before accepting a capture artifact.

Gate: zero extra model calls; ambiguous create, multiple matching runs, pagination exhaustion,
identity drift, missing artifact, and archive confusion all fail closed.

### Slice 4: capture-set assembler and canonical replay

- Assemble only the exact predeclared shard union for one canonical model identity and call policy.
- Add a public replay adapter instead of depending on the verifier's private `_ReceiptAdapter`.
- Extend adapter identity validation for Kaggle capture without pretending it is the custom hosted
  HTTP adapter.
- Generate the canonical `BenchManifest` from the frozen call plan alongside `BenchResult`, and
  verify call plan, manifest, and result agree on prompt coverage, generation count, model, seed,
  scoring profile, adapter identity, and raw-response count.
- Score and aggregate only after `validate_scoring_runtime()` succeeds.

Gate: the same complete capture set produces byte-identical canonical numeric fields and a matching
manifest, and both are fully replayed by the existing verifier. Drift from the retained source
archive or frozen call plan in identity, prompt, output, usage, or call state is rejected by the
capture verifier before scoring.

### Slice 5: operator workflow and publication guard

- Add CLI commands for capture verification, set assembly, canonical replay, and read-only status.
- Document quota checks, exact command ordering, evidence retention, interruption handling, and
  no-overwrite output names.
- Make release tooling reject raw capture artifacts as results.

Gate: a new operator can complete the offline fake workflow from a clean checkout without hidden
state or a model credential.

### Slice 6: hosted canary

- Review the exact source and quota immediately before execution.
- Create at most one task version and allow its single creation-triggered run to finish.
- Download and verify the exact run artifact, then replay it under the canonical runtime.

Gate: six planned calls, six uniquely keyed completed rows each retaining its raw string, no retry,
no extra run, exact identities, and a verified `CanaryReplayReceipt` explicitly labeled as
transport-canary-only. It is never a `BenchManifest`, `BenchResult`, leaderboard row, or publication
candidate because it does not cover complete canonical items or the frozen 900-call plan.

## Acceptance gates

### Contract gate

- Capture artifacts and `BenchResult` are distinct schema types.
- A capture contains no score and cannot pass the result verifier or release gate.
- The payload and envelope identities cover every source, run, model, prompt, output, usage, and
  call-state claim, and verification compares them with the retained source archive.

### Runtime portability gate

- Capture-only code has offline coverage on Python 3.11/UCD 14.
- Canonical scoring still rejects Python 3.11/UCD 14.
- Canonical replay succeeds only on Python 3.13/UCD 15.1.

### Raw-preservation gate

Tests cover leading/trailing whitespace, CR/LF variants, NFC/NFD forms, casefold-sensitive text,
emoji/ZWJ sequences, unpaired surrogates, NUL/control characters, empty strings, non-string values,
oversized responses, exceptions, missing usage, zero usage, and interrupted writes. Expected
transformations are asserted only in canonical scorer tests, never in capture tests.

### Binding and recovery gate

- Only one exact task version and one unique exact run are accepted per shard.
- Create is one call; the helper never invokes generic retry or `tasks run`.
- Partial or ambiguous evidence remains inspectable but cannot be assembled or scored as complete.
- Existing diagnostic and legacy receipts remain immutable and retain their original meaning.

### Canonical replay gate

- Complete capture coverage replays deterministically under the frozen scorer.
- Dataset, prompt order, shard plan, model/run identity, raw output, usage, and call-state drift from
  the retained archive or frozen call plan is detected before scoring.
- Generated `BenchManifest`, `BenchResult`, and retained raw-response counts agree and pass the
  existing cross-artifact verifier.
- The final v0.2 result passes the same offline verifier used for non-Kaggle hosted results.

### Publication gate

- No canary, capture receipt, partial shard, or unverified result appears on Kaggle or Hugging Face as
  a benchmark score.
- A public result requires a separate issue, reviewed release artifacts, retained raw evidence,
  matching digests, and a manual platform readback.

## Failure, recovery, and rollback

- Keep the current diagnostic task, its creation journal, and all downloaded evidence unchanged.
- Use new, attempt-specific output paths. Never overwrite a receipt to make a retry look continuous.
- After an ambiguous create, stop and reconcile exact versions/runs before considering any new
  operation. Do not infer success from a slug alone.
- After a partial shard, preserve the artifact and require an explicit decision about a replacement;
  do not fill missing rows automatically.
- Once published, a capture schema version is immutable. Incompatible changes create a new version.
- Rolling back the capture task or assembler cannot alter v0.2 scorer behavior or previously verified
  results.

## Out of scope

- changing v0.2 metrics, Unicode behavior, leakage thresholds, dataset, or rerun policy;
- presenting a Python 3.11 implementation as the Python 3.13 reference runtime; a portable scorer
  may target protocol 0.2.0 only with separate scorer/runtime/package/schema identities and remains
  `comparabilityStatus: unproven` until the issue #77 proof;
- implementing a portable Unicode scorer/profile;
- a full 900-call Kaggle run, cross-model ranking, or public leaderboard;
- publishing to Hugging Face or Kaggle;
- upstream Kaggle CLI, SDK, or service fixes;
- migrating benchmark authority to the standalone repository;
- product UI or `AlephRun` redesign; and
- deleting, rerunning, or reinterpreting existing issue #38 evidence.

## Existing contracts

- [v0.2 scorer contract](../benchmark/02-design-spec.md#versioned-scorer-contract)
- [benchmark implementation contract](../../bench/README.md#protocol-versions)
- [Kaggle diagnostic runbook](../benchmark/kaggle-diagnostic-runbook.md)
- [hosted v0.2 runbook](../benchmark/hosted-m0-runbook.md)
- [legacy Kaggle offline replay](../benchmark/kaggle-runbook.md)
- [frozen protocol config](../../bench/config/frozen_ladder-v0.2.json)
- [v0.2 result schema](../../schemas/v0.2/aleph-bench-result.schema.json)
- [canonical verifier](../../bench/engine/verify.py)
- [current creation-output binder](../../bench/engine/kaggle_creation_output.py)
- [M0 plan](aleph-bench-m0.md)
- [repository workflow](../../WORKFLOW.md)

Primary compatibility references:

- [Python 3.11 `unicodedata` (UCD 14.0)](https://docs.python.org/3.11/library/unicodedata.html)
- [Python 3.13 `unicodedata` (UCD 15.1)](https://docs.python.org/3.13/library/unicodedata.html)
- [`unicodedata2` 15.1.0 release files](https://pypi.org/project/unicodedata2/15.1.0/)
- [Unicode 15.1 normalization conformance data](https://www.unicode.org/Public/15.1.0/ucd/NormalizationTest.txt)
- [Unicode 15.1 case-folding data](https://www.unicode.org/Public/15.1.0/ucd/CaseFolding.txt)
