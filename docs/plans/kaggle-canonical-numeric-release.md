# Canonical numeric Kaggle release plan

Status: proposed

Tracking issue: [#59](https://github.com/p-to-q/aleph/issues/59)

Public entry: [Aleph Bench](https://www.kaggle.com/benchmarks/jahyee/aleph-bench)

Reference protocol: `0.2.0`

Portable scorer target: `aleph-unicode@0.2.0` (`comparabilityStatus: unproven` until #77)

Last updated: 2026-09-25

## Outcome

Make the existing **Aleph Bench** page the single long-lived Kaggle execution and leaderboard
entry. A user should be able to see a versioned Task, run it against a supported model, obtain a
real numeric score, inspect its source and execution state, and reproduce the score from public
code and release artifacts.

The same release is represented on three mutually referencing surfaces:

- Today, `p-to-q/aleph@benchmark/source-v0.2` remains the temporary source authority.
  Portable implementation code lands in `p-to-q/aleph-benchmark`, but that repository becomes the
  release authority only after the cutover gate in `p-to-q/aleph-benchmark#1` passes.
- Kaggle is the hosted model-execution and public numeric leaderboard surface.
- Hugging Face is the public dataset, benchmark card, structured result index, and evidence mirror.

The benchmark title remains **Aleph Bench**. Protocol changes are expressed through immutable Task
versions and release identities, not by creating another public benchmark brand.

## Evidence behind this plan

Read [the benchmark platform engineering review](../research/benchmark-platform-engineering.md)
before implementation. It compares the current Aleph/Kaggle evidence with SWE-bench, HELM,
lm-evaluation-harness, LiveBench, Kaggle research/community Tasks, and the current Hugging Face Eval
Results model.

The decisive observations are:

- Kaggle's public numeric result must be produced by the Task run; there is no documented external
  score-backfill path for a Community Benchmark.
- Capture plus Python 3.13 replay is valid independent evidence but cannot by itself populate the
  public numeric leaderboard.
- v0.2.0 defines Python 3.13 and UCD 15.1 as the reference runtime/scorer profile. A Python 3.11 or
  3.12 portable implementation still targets protocol 0.2.0, but must not present itself as that
  reference profile and remains non-comparable until issue #77 proves zero mismatch.
- The official `unicodedata2==15.1.0` CPython 3.11 manylinux x86-64 wheel exists, is Apache-2.0,
  and has published SHA-256
  `a2442a539d1e493486fdbbdf1d08c8f5d4abe51c9b77b7d39df319a96d30abe4`. This makes a
  Kaggle-native scorer plausible, not proven.
- Ambient `str.casefold()`, `str.isspace()`, and no-argument `str.split()` are also scorer inputs.
  Replacing only `unicodedata` is insufficient.
- A provisional local full-code-point probe found matching UCD and built-in string-property digests
  across Python 3.11/3.12 candidates and the Python 3.13 reference, and both candidates passed the
  current 42 fidelity plus 28 leakage checks. It used macOS wheels and incomplete multi-code-point
  coverage, so it selects a promising route but is not release evidence.
- Kaggle CLI 2.2.4's paid `tasks run` path uses generic retry, defaults to the latest Task version,
  and does not return a run id. The exact-version, journaled one-shot scheduler is now merged in
  PR #61 and must remain the only paid-dispatch path.

Current hosted checkpoint on 2026-09-25:

- planning and scheduler gates PR #60 and #61 are merged; the strict capture-set assembler in PR
  #76 / issue #67 is also merged;
- private Task v9 creation run `3089519` returned all 6 declared strings, but creation evidence is
  not assembly-eligible and is not a score;
- exact run `3091209` with `gpt-5.4-nano-2026-03-17` returned 6/6 strings and is
  assembly-eligible capture evidence, not a score;
- exact run `3092711` with `claude-haiku-4-5-20251001` stopped after 3 attempted calls: 2 strings,
  1 timeout, and incomplete coverage. It is not assembly-eligible and is not a score;
- the public page contains one historical v0.1 numeric row. There is no formal hosted v0.2 score;
  and
- no paid run and no Haiku retry is authorized until issue #90 is resolved by a merged, verified
  implementation PR and the hold is explicitly lifted.

## Decision

### Selected route: proved portable scorer

Keep protocol `0.2.0` and its reference scorer bytes immutable. Build a separate portable scorer
and runtime profile that targets `aleph-unicode@0.2.0`, with the same current public dataset, call
plan, metrics, thresholds, aggregation, and five-rerun policy. Give the scorer profile, runtime
profile, package, and schema independent identities. Freeze every Unicode input needed for
equivalent behavior and prove it against the Python 3.13/UCD 15.1 reference.

If every declared compatibility gate passes, the release may say:

> This portable implementation of Aleph-Bench protocol 0.2.0 is numerically comparable to the
> Python 3.13 reference under the published proof contract.

Until issue #77 emits the canonical zero-mismatch receipt, `comparabilityStatus` remains `unproven`.
The proof must precede manifest freeze: it derives a new candidate and `releaseId` that bind the
receipt, that candidate is verified, and only then may it be frozen. A frozen unproven manifest can
never be promoted; later proof must start another candidate/release identity. Any mismatch blocks
comparability and same-leaderboard promotion. Protocol `0.3.0` is reserved for issue #35's changes
to length units, failure denominators, and ECL aggregation; portability alone does not consume that
version. See [ADR 0006](../decisions/0006-benchmark-version-identity.md).

### Retained route: capture plus reference replay

Keep the current capture contract as:

- a six-call transport canary;
- an independent raw-evidence chain;
- a recovery path for platform scorer failures; and
- a reference-replay check for every private release candidate.

A capture artifact remains score- and publication-ineligible by itself.

### Fallback route: hermetic Python 3.13

If portable equivalence cannot be established, investigate a hermetic Python 3.13 runtime inside
Kaggle. This requires separate binary provenance, architecture, loader, no-network, resource, and
execution proofs. It is not the first implementation route and cannot be silently substituted.

## Public topology

```text
Git tag + release manifest
  ├─ protocol, scorer, generator, schemas, tests, digests
  ├─ exact Kaggle Task version and release run identities
  └─ exact Hugging Face dataset revision

Kaggle: jahyee/aleph-bench
  ├─ one active canonical numeric release Task
  ├─ model execution state and numeric scores
  └─ links to Git release and Hugging Face evidence

Hugging Face: Aleph Bench dataset/benchmark
  ├─ versioned public dataset and card
  ├─ release manifest and public-safe results/evidence
  ├─ eval.yaml / structured result records when registration is available
  └─ links to Git release and exact Kaggle Task
```

The Aleph website may render this release, but must not become a fourth manually maintained score
authority.

## Release identity

Add a strict, versioned release identity that binds:

- `benchmarkName`, `releaseId`, `protocolVersion`, `referenceProtocolVersion`, and `targetScorer`;
- scorer profile id/version, runtime profile id/version, package id/version/digest, schema
  id/version, and `comparabilityStatus` plus a nullable proof-receipt digest;
- dataset id, item count, revision, filenames, and digest;
- prompt/call-plan id, 900-row coverage, rerun policy, and digest;
- target-scorer source digest plus normalization, casefold, whitespace, and Unicode profiles;
- exact dependency filenames, sizes, SHA-256 values, licenses, ABI/platform tags, and import paths;
- generated Task source and package digests;
- requested decoding parameters and no-silent-retry policy;
- Git commit/tag;
- Kaggle owner, Task slug, exact version, run id, observed model, and model mapping;
- result, manifest, Task receipt, outer envelope, and public derivative digests; and
- Hugging Face repository and immutable revision.

Every derivable field is recomputed by the verifier. Unknown or ambiguous identity fails closed.

## Portable scoring proof

The first implementation PR after this plan performs zero model calls and does not change v0.2
scorer bytes.

### Inputs

- Python 3.13/UCD 15.1 reference scorer;
- Python 3.11/UCD 14 negative control;
- Python 3.11 plus hash-pinned `unicodedata2==15.1.0` candidate;
- Python 3.12 plus the corresponding pinned candidate;
- official Unicode 15.1 `NormalizationTest.txt`, `CaseFolding.txt`, and `PropList.txt`, each pinned
  by URL and SHA-256;
- generated/frozen Python 3.13 whitespace and casefold data where ambient string behavior would
  otherwise leak into the profile; and
- existing conformance vectors plus known UCD-drift counterexamples.

### Checks

- wheel size, hash, license, ABI/platform tag, import origin, and no-network installation;
- full official normalization conformance;
- exhaustive single-code-point category, combining-class, East Asian Width, casefold, and
  whitespace comparisons;
- bounded adversarial multi-code-point cases covering combining marks, compatibility forms,
  surrogates, controls, variation selectors, emoji/ZWJ, bidi controls, CJK compatibility
  ideographs, and normalization expansion;
- full scorer differential behavior: values, exceptions, limits, leakage decisions, aggregation,
  serialization, and `float.hex()`; and
- byte-stable machine receipts with interpreter, platform, input, code, and output digests.

Gate: Python 3.11 and 3.12 candidates match the Python 3.13 reference for the complete declared
contract. A small fixture-only match is not sufficient.

## Canonical Task contract

Generate a self-contained private release Task from frozen inputs. The checked-in generated source
must have a deterministic `--check` path and an implementation digest covering headers, constants,
dependencies, and executable code.

### Preflight before the first model call

- exact Task source/package/release identity;
- all dataset and call-plan files, counts, ordering, and digests;
- dependency wheel bytes, import origin, runtime profile, and Unicode tables;
- Kaggle SDK capabilities actually used by the generated Task;
- requested model alias/revision shape and decoding parameters;
- writable output path, atomic replace, fsync, file-size and archive limits; and
- absence of prior/ambiguous checkpoint state in the current attempt.

### Execution

- exactly 30 items × 6 non-leaking prompts × 5 reruns = 900 planned calls;
- one unique, fresh chat for every `(item, prompt, rerun)` tuple;
- no hidden context reuse and no automatic retry;
- append-only per-item capture files, plus a small atomic call-state journal;
- exact raw string preservation and explicit non-string/failure states;
- observed usage, limits, latency, and finish reason when exposed by the SDK; and
- scoring only after full, duplicate-free coverage validates.

Do not use SDK timeout plus immediate retry: the current thread timeout cannot prove the timed-out
call stopped. Treat an uncertain timeout as an ambiguous paid call and stop.

### Result

The root Task returns `float(1 - aggregate_aurc)` only after every release gate inside the Task
passes. The Task also stores:

- `release-manifest.json`;
- `run-spec.json`;
- per-call evidence;
- per-item/rerun values and failure taxonomy;
- `bench-manifest.json` and `bench-result.json`;
- `task-receipt.json`; and
- all relevant content digests plus the returned scalar's `float.hex()`.

Any incomplete, invalid, ambiguous, or evidence-write-failed run raises and has no numeric result.
A returned `0.0` may only mean a complete valid run actually scored zero.

## Exact paid-run control plane

PR #61 already implemented `bench.engine.kaggle_run_once`; it is the only permitted paid scheduler,
but it is not usable while the hard hold remains active. It may be used only after issue #90 is
resolved by a merged, verified implementation PR and an explicit decision lifts the hold. It:

1. require explicit owner, Task slug, positive exact version, one exact model slug, and a new
   journal path;
2. read and retain quota, exact-version Task metadata, and the complete pre-dispatch run set;
3. reject any queued/running conflicting run or unresolved prior journal;
4. fsync `prepared` and `dispatching` states before the paid call;
5. construct `ApiBenchmarkTaskSlug.version_number` explicitly;
6. invoke the scheduling API exactly once without generic retry;
7. stop as `ambiguous` on any uncertain response rather than retrying;
8. reconcile the exact-version run-set difference and accept exactly one new matching run id; and
9. retain response, status, run id, and quota-before/after observations without overwriting a prior
   attempt.

The general Kaggle CLI remains useful for read-only status and diagnostics; it is not the release
scheduler.

## Bounded run ladder and budget

"Run the quota fully" means complete the predeclared evidence matrix, not spend the account balance.

1. **0 calls:** portability proof, generated-source check, fake LLM, package, schema, archive,
   replay, and scheduler tests.
2. **6 calls:** transport/capture canary for one model.
3. **30 calls:** one complete item rehearsal.
4. **180–300 calls:** optional wall-time/archive rehearsal only if the 30-call evidence leaves a
   material uncertainty.
5. **900 calls:** one private numeric release candidate.
6. **2 × 900 calls:** a second provider only after the first exact run and independent replay pass.

As of 2026-09-25, issue #67's assembler gate is merged, but run `3092711` activated the timeout
circuit breaker. The controller is in a hard hold: no paid run and no Haiku retry until issue #90
is resolved by a merged, verified implementation PR and an explicit operator decision lifts the
hold. Read-only status, quota, source, and evidence verification may continue.

There is no active target of 8–12 models per day. Any future recurring matrix is a bounded research
plan, not a quota-consumption goal: it requires the #90 stability gate, an explicit model list,
one-at-a-time retained evidence, machine-enforced budgets, and stop-on-first-incomplete behavior.
Historical `$9` daily / `$95` monthly figures are ceilings only and authorize no dispatch.

For full runs, use the observed six-call cost only as a planning estimate:

```text
estimated_900_call_cost = 150 × observed_6_call_cost
```

Before the first 30-call or 900-call run, issue #59 must record a fresh full-run budget and reserve
from live quota and observed canary costs; the canary `$9/$95` ceilings do not authorize that
transition. Retain at least `$2.00` or 20% of the daily quota, whichever is larger, for failure
investigation and required verification. Never blind-rerun a failed 900-call attempt on the same
day.

The first formal RC model order must be proposed again from current compatibility and cost evidence
after the hold is lifted. Historical canary order is not authorization, and Haiku must not be
retried merely because it appeared in an earlier sequence. Canaries never become scores.

## Independent replay and publication

For each private numeric RC:

1. bind one exact Task version, run id, and observed model;
2. download Task-run output with source through the supported endpoint;
3. validate archive membership, paths, counts, sizes, and all inner digests;
4. create the outer platform evidence envelope;
5. replay under the Python 3.13/UCD 15.1 reference;
6. require exact agreement for coverage, leakage decisions, per-item values, aggregates, returned
   scalar, and `float.hex()`;
7. retain quota and public-safety review receipts; and
8. open a dedicated publication issue/PR.

After two cross-provider RCs pass, publish that exact Task version and attach it to the existing
Aleph Bench page. Remove the legacy Task from the active aggregate only after the new Task is visible
and correct. Preserve legacy Task versions and receipts as historical evidence.

The live readback records:

- canonical benchmark URL and title;
- one active canonical Task and exact version;
- model display and canonical mapping;
- displayed numeric score;
- run id and Task/result/release digests;
- aggregation setting;
- Kaggle quota after the operation; and
- matching Git and Hugging Face release identities.

Publication is the last irreversible step. The current CLI has no documented unpublish operation;
attach/detach behavior must be verified in the logged-in UI immediately before promotion.

## Hugging Face release

Use a public versioned dataset repository as the first-class mirror. It should contain:

- dataset card, datasheet, license, citation, intended uses, limitations, contamination and
  maintenance policies;
- immutable public split files with exact revision/digests;
- `eval.yaml` when Hugging Face accepts Aleph into its benchmark registry;
- append-only public result records and release manifests;
- source links to exact Kaggle Task/run and Git release; and
- public-safe per-item evidence when content and provider policies allow it.

When structured Eval Results are available, model-repo `.eval_results/*.yaml` entries must point to
the exact Aleph dataset revision and evidence source. Do not claim Hugging Face's verified badge
until its verification flow actually produced one.

A Space is optional and must read a pinned results revision. It must not contain a second scorer or
invoke models on page load. Manifest drift renders a row stale/unverified rather than silently
recomputing it.

## Implementation PR sequence

### PR A: research and release decision

Status: completed by PR #60; this plan remains amendable when evidence changes.

- check in the external engineering review and this plan;
- correct issue #59's v0.2 naming;
- freeze the selected/fallback routes and public topology.

Gate: reviewers can identify the authority, release identity, protocol boundary, and one acceptance
gate for every later PR.

### PR B: exact one-shot scheduler

Status: completed by PR #61. PR #76 / issue #67 subsequently completed the strict capture-set
assembler dependency.

- implemented and adversarially tested `kaggle_run_once`;
- documented journal reconciliation and the evidence layout.

Gate: fake SDK tests prove one direct paid call, exact version binding, no retry, durable ambiguous
state, and exact new-run-id reconciliation.

### PR C: portable proof harness

- add official Unicode inputs/digests, wheel manifest, proof code, and machine receipts;
- run the declared Python/platform matrix without model calls.

Gate: the complete portable/reference contract matches or the route is explicitly rejected.

### PR D: portable scorer and release identity

- add independently versioned scorer/runtime/package profiles without altering v0.2 bytes or
  changing `referenceProtocolVersion: 0.2.0`;
- add schemas, manifests, serializers, verifiers, and mutation tests.

Gate: profile and release identity are independently reproducible in clean Python 3.11, 3.12, and
3.13 environments.

### PR E: generated numeric Task

- add generator, generated source, package/wheelhouse, fake LLM, failure-injection, checkpoint, and
  archive tests.

Gate: fake execution makes exactly 900 uniquely keyed calls, returns the expected scalar only for a
complete valid run, and emits replayable evidence.

### PR F: private RC and operator workflow

- run the bounded ladder with exact journals;
- retain two cross-provider full RCs and independent reference replay.

Gate: both returned Kaggle scalars and every canonical replay field agree.

### PR G: one public release

- add release artifacts, cards, publication checklist, and limitations;
- promote the exact Task to the existing Kaggle URL;
- publish the matching Hugging Face dataset revision;
- perform and retain live readback.

Gate: GitHub, Kaggle, and Hugging Face show the same release identity and verified numbers.

## Out of scope

- changing the current dataset, prompts, metrics, thresholds, aggregation, or five-rerun policy;
- claiming a global minimum, white-box evidence, or strict Kolmogorov complexity;
- a second public Kaggle benchmark;
- automatic paid runs while the #90 circuit breaker or later numeric-release gates remain closed;
- overwriting or deleting legacy/canary/failed evidence;
- treating a canary, mock, capture, partial shard, failed zero row, or platform `COMPLETED` state as
  a public score; and
- making a beta platform feature the only copy of a release artifact.

## Immediate next action

Resolve issue #90 with a merged, verified implementation PR, then require an explicit hold-lift
decision before any paid dispatch. In parallel, continue the standalone portable-scorer slices and
issue #77 proof with zero model calls. No current artifact is a v0.2 score, and the full 900-call
budget remains gated.
