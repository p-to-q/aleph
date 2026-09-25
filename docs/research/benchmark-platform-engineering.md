# Benchmark platform engineering review

Status: research note

Date: 2026-09-23

Identity correction: 2026-09-25

Scope: public benchmark authority, execution, evidence, and reproducibility

## Question

How should Aleph Bench combine academic validity with production-grade benchmark engineering so one
release can be inspected in GitHub, executed on Kaggle, indexed on Hugging Face, and reproduced
without silently changing its meaning?

This note records two research rounds. The first starts from observed Aleph/Kaggle failures. The
second compares current public benchmark systems and their implementation contracts. It does not
claim that every external system is equally applicable to Aleph.

## Round 1: what the current Aleph/Kaggle evidence says

The runtime mismatch is not simply "Python is old". Aleph-Bench v0.2 makes Python 3.13 and UCD 15.1
the reference runtime/scorer profile, while private Task v9 observed Python 3.12.10 and UCD 15.0.
The scorer uses normalization, case folding, whitespace behavior, Unicode category, and East Asian
Width. A runtime that imports successfully can therefore still change leakage decisions and scores.

The current hosted checkpoint is deliberately score-free:

- Task v9 creation run `3089519` returned all 6 declared strings but creation evidence is not
  assembly-eligible;
- exact GPT-5.4 nano run `3091209` returned 6/6 strings and is assembly-eligible capture evidence;
- exact Haiku run `3092711` attempted 3 calls, retained 2 strings, timed out once, and stopped with
  incomplete coverage; and
- none of these runs performs canonical scoring or creates a leaderboard row.

The public page contains one historical v0.1 numeric row and no formal hosted v0.2 score. PR #60
(plan), PR #61 (one-shot scheduler), and PR #76 / issue #67 (strict capture-set assembler) are
complete. The Haiku timeout activates a hard hold: no paid run and no Haiku retry until issue #90
is resolved by a merged, verified implementation PR and an explicit decision lifts the hold.

Three platform facts determine the next design:

1. A Kaggle Community Benchmark obtains its displayed numeric result from the Task execution. The
   public cookbook supports `float` and `int` returns, but does not document an external score
   backfill API.
2. Creating a Task can itself execute the bottom-level `.run(kbench.llm)`. A later `tasks run` may
   duplicate calls.
3. Kaggle CLI 2.2.4 schedules paid Task runs through a retry wrapper, does not put an exact version
   in its `ApiBenchmarkTaskSlug`, and does not return the new run id in the scheduling response.
   PR #61 therefore added the journaled exact-version one-shot control plane; it remains the only
   permitted paid-dispatch path after the current hold is explicitly lifted.

The consequence is narrow: capture plus canonical off-platform replay remains the independent
evidence and recovery path, but a public Kaggle score requires an in-Task scorer whose behavior has
been proven against the reference scorer.

### Provisional portability evidence

A read-only local probe produced useful evidence but does not satisfy the release gate:

- the official `unicodedata2==15.1.0` macOS wheels under Python 3.11 and 3.12, and Python 3.13's
  standard-library UCD 15.1, produced the same streamed digest
  `5d4ab34679e385e642f75812c4914a032c54e2a197c715d7e4cfa4fbab6fa566` over category,
  East Asian Width, combining class, bidi class, NFC, and NFKC for all 1,114,112 code points;
- built-in `casefold` and `isspace` produced the same single-code-point digest
  `7535168c65de44dea4fed65d10573d7541268c8b64d69eceaccbe967c542dba0` on those three
  interpreters; and
- the Python 3.11 and 3.12 candidates passed the current 42 fidelity and 28 leakage checks.

This is a route-selection result, not a release proof. It used macOS wheels rather than the Kaggle
manylinux binary; it did not run the full multi-code-point Unicode normalization suite; it bypassed
the v0.2 runtime gate temporarily; and it produced no checked-in profile or machine receipt.

The target wheel is a native CPython 3.11, x86-64, glibc 2.17+ artifact. The first portable release
must state that support boundary. It must not imply Linux ARM64 support without a separately audited
build or a table-only implementation. Python's whitespace behavior also differs from simply using
Unicode `White_Space` (notably U+001C through U+001F), so a portable scorer needs frozen Python 3.13
semantics rather than a naive `PropList.txt` substitution.

## Round 2: external systems

| System | Public shape | Engineering contract worth borrowing | Important limit |
| --- | --- | --- | --- |
| SWE-bench | GitHub harness, Hugging Face datasets, public leaderboard | Layered Docker images, per-instance isolation, timeouts, gold-patch validation, per-instance logs, run ids, explicit cache levels | Its Docker-heavy isolation is not available inside a Kaggle Community Task; its run-id cache can reuse stale results if prediction content changes |
| HELM | GitHub/PyPI framework plus generated suites and web leaderboards | Typed scenario, adapter, request, response, per-instance statistic, and summary layers; inspectable prompts and responses | HELM entered maintenance mode in 2026; Aleph should borrow contracts, not adopt another large framework |
| lm-evaluation-harness | GitHub package, YAML Tasks, Hugging Face datasets/results | Shareable Task config plus code commit, explicit seeds, model/task/plugin separation, config validation, sample logging, result artifact output | General harness flexibility does not replace Aleph's frozen rate-distortion and leakage semantics |
| LiveBench | GitHub harness, dated releases, Hugging Face question/answer artifacts, website leaderboard | Time-versioned releases, objective scoring, public/private split, explicit `$ERROR$` handling, resume/retry controls, datasheet and maintenance plan | Its default three retries and "persistent failure is incorrect" rule conflict with Aleph's no-silent-retry evidence policy |
| Kaggle MMLU research benchmark | One Kaggle benchmark page, versioned Task, dataset, notebook, 60+ model rows and confidence intervals | The visible v7 Task retains raw response, predicted answer, correctness, subject and category; exceptions are re-raised rather than converted to a low score | Research Benchmarks may have platform integration not exposed to Community Tasks. MMLU's final aggregation is not fully expressed by the visible per-row function, so Aleph cannot assume the same hidden layer |
| Hugging Face Eval Results | Benchmark dataset repo, model-repo `.eval_results`, dataset leaderboard, optional verified result | `eval.yaml` registers Task identity; result YAML links dataset revision, value and source; verified/community/source badges separate provenance classes; dataset- and model-centric APIs | The feature is explicitly work in progress and official registration is allow-listed; canonical evidence must remain portable outside the Hub |
| Open LLM Leaderboard | Historical Space, request state, score dataset, per-model detail datasets | Separate request status, aggregate score, and instance-level detail artifacts | It retired when its benchmark set became obsolete. A maintained benchmark needs a lifecycle and retirement policy, not only a launch checklist |

### What the mature systems have in common

- **One semantic release, several surfaces.** Code, data, execution, results, and presentation may
  live in different systems, but a run is meaningful only when their versions are bound together.
- **Instance evidence precedes aggregation.** Per-instance predictions, logs, and failure states are
  retained before a headline score is computed.
- **Configuration is data.** Seeds, prompts, decoding, dataset revision, scorer, environment, and
  harness revision are materialized rather than left in an operator's shell history.
- **Failure is typed.** A missing, timed-out, invalid, filtered, or incomplete response is not
  interchangeable with a valid answer scoring zero.
- **Reproduction includes a reference check.** Gold patches, conformance vectors, example Tasks, or
  verified result tokens test the evaluator itself before a new model row is trusted.
- **Leaderboards need lifecycle governance.** Dataset refresh, contamination, model alias drift,
  saturation, deprecation, and retired Tasks are part of the scientific contract.

### What Aleph should not copy

- Do not inherit a harness's retry or cache defaults merely because they improve throughput.
- Do not collapse raw observations, per-item metrics, aggregate metrics, and presentation values
  into one untyped JSON object.
- Do not let a Space, notebook, website, or platform UI become the only copy of the protocol.
- Do not accept a provider or platform display name as an immutable model revision.
- Do not publish a zero when execution failed; a failed release run must have no numeric result.
- Do not claim exact cross-runtime equivalence from a small regression fixture or package version.

## Design rules for Aleph Bench

### 1. One release identity

Every public surface should carry one machine-readable release identity containing at least:

- benchmark and protocol version;
- runtime/scorer profile;
- dataset id, count, revision, and digest;
- call-plan and decoding digests;
- generated Task source and dependency digests;
- task owner, slug, exact version, run id, and platform model observation;
- canonical model mapping and its confidence/limitations;
- manifest, result, and evidence-envelope digests; and
- Git commit plus Kaggle and Hugging Face URLs.

The identity is content-bound. A friendly title such as **Aleph Bench** stays stable while the
protocol and release identity change explicitly.

### 2. Different authorities, mutual references

| Surface | Authority | Required cross-reference |
| --- | --- | --- |
| GitHub | Current temporary source authority: `p-to-q/aleph@benchmark/source-v0.2`; target release authority: `p-to-q/aleph-benchmark` only after its #1 cutover gate | Exact Kaggle Task/version and Hugging Face dataset revision |
| Kaggle | Hosted model execution and the single public numeric leaderboard | Git commit/release identity and Hugging Face evidence index |
| Hugging Face | Public dataset, benchmark card, structured result index, selected public-safe evidence | Git release manifest and exact Kaggle Task/run source |
| Aleph website | Human-readable explanation and links, not a fourth source of scores | Render the same release manifest or link to its authorities |

"Unified" therefore means the same name, semantics, version, model identity, score, and digests. It
does not mean copying mutable values by hand into four unrelated pages.

### 3. Reference scorer plus portable profile

Keep v0.2.0 immutable as the Python 3.13/UCD 15.1 reference. A Kaggle-compatible scorer should be a
separately identified portable candidate targeting protocol 0.2.0 when its dataset, prompts,
metrics, thresholds, aggregation, eligibility, and rerun policy are unchanged. Its identity must
bind `protocolVersion: 0.2.0`, `referenceProtocolVersion: 0.2.0`,
`targetScorer: aleph-unicode@0.2.0`, and independent scorer-profile, runtime-profile, package, and
schema identities. It begins with `comparabilityStatus: unproven`; only the checked-in exhaustive
equivalence proof in issue #77 may derive a new candidate/release identity that binds the proof
receipt. That candidate is verified before freeze. A frozen unproven manifest is never promoted.

Protocol 0.3.0 is reserved for issue #35's semantic changes to length units, failure denominators,
and ECL aggregation. The historical `0.3.0-provisional` value inside the frozen string-semantics
inputs remains an immutable source label, not a protocol or comparability claim. See
[ADR 0006](../decisions/0006-benchmark-version-identity.md).

The proof must cover more than `unicodedata2.normalize`:

- the hash-pinned `unicodedata2==15.1.0` wheel and license;
- Unicode normalization, category, combining class, and East Asian Width inputs;
- frozen case-fold and whitespace tables used instead of ambient Python behavior;
- exhaustive single-code-point properties plus bounded adversarial multi-code-point tests;
- the complete Aleph scorer, leakage decisions, aggregation, and serialized numeric fields; and
- Python 3.11/Kaggle, Python 3.12, and Python 3.13 reference executions.

Any mismatch blocks the comparability claim and public promotion.

### 4. Generated, fail-closed release Task

The release Task should be generated from frozen inputs and verified with a `--check` command. It
should perform all immutable preflight checks before the first model call, isolate every call in a
uniquely named fresh chat, checkpoint small per-item files atomically, and compute the scalar only
after all 900 declared calls are complete.

An exception, non-string response, ambiguous model identity, missing required usage, near-cap output,
duplicate/missing call, scorer mismatch, or evidence-write failure must prevent a numeric return.
`0.0` remains a valid model result only for a complete, valid run whose score is actually zero.

### 5. Evidence before presentation

The Task emits an inner receipt because it cannot know every server-assigned identity. An exact-run
downloader then creates an outer envelope containing the Task version, run id, model readback,
downloaded source/archive digests, and quota observations. Independent reference replay must match
the Task scalar, `float.hex()`, item metrics, aggregate metrics, and content digests.

Public raw outputs require a separate content, privacy, and license review. Public-safe evidence may
be a redacted derivative, but it must never overwrite canonical retained evidence.

### 6. Current Hugging Face route

Prefer a versioned Aleph Bench dataset repository over a hand-maintained leaderboard-only Space:

- dataset card and datasheet;
- `eval.yaml` when the benchmark-registration gate is available;
- versioned public dataset and release-manifest files;
- structured result records with dataset revision and source URL;
- optional embedded leaderboard/API consumption; and
- a Space only when a richer visualization adds information beyond the dataset leaderboard.

Until Hugging Face's beta registration and verification paths accept Aleph, publish the same files
and schema without claiming an official or verified badge.

## Implementation consequences

1. Keep the corrected v0.2/version-axis wording synchronized across plans and issue bodies.
2. Add the portable scorer in the standalone repository without claiming that this alone completes
   the global authority cutover; `p-to-q/aleph-benchmark#1` owns that transition.
3. Complete issue #77's proof and derive a proven candidate/release identity before manifest freeze.
4. Keep PR #61's one-shot scheduler and PR #76/#67's strict assembler as mandatory controls.
5. Resolve issue #90 with a merged, verified implementation PR and explicitly lift the hold before
   any paid scheduling.
6. Build and validate a private numeric release candidate before consuming full-run quota.
7. Promote only an exact verified Task version to the existing Kaggle URL.
8. Mirror the same release identity to a public Hugging Face dataset and cross-link every surface.
9. Treat saturation, protocol replacement, and retirement as explicit future release events.

## Primary sources

- [Kaggle Benchmarks documentation](https://www.kaggle.com/docs/benchmarks)
- [Kaggle Benchmarks cookbook](https://github.com/Kaggle/kaggle-benchmarks/blob/ci/cookbook.md)
- [Kaggle CLI benchmark commands](https://github.com/Kaggle/kaggle-cli/blob/main/docs/benchmarks.md)
- [Kaggle MMLU benchmark](https://www.kaggle.com/benchmarks/open-benchmarks/mmlu)
- [Kaggle MMLU Task v7](https://www.kaggle.com/benchmarks/tasks/benchmarkler/mmlu-task/7)
- [SWE-bench evaluation harness](https://github.com/SWE-bench/SWE-bench/blob/main/docs/reference/harness.md)
- [HELM](https://github.com/stanford-crfm/helm)
- [lm-evaluation-harness Task guide](https://github.com/EleutherAI/lm-evaluation-harness/blob/main/docs/task_guide.md)
- [LiveBench](https://github.com/LiveBench/LiveBench)
- [Hugging Face Eval Results](https://huggingface.co/docs/hub/eval-results)
- [Hugging Face benchmark leaderboard data](https://huggingface.co/docs/hub/leaderboard-data-guide)
- [Open LLM Leaderboard retirement discussion](https://huggingface.co/spaces/open-llm-leaderboard/open_llm_leaderboard/discussions/1135)
- [`unicodedata2` 15.1.0 release](https://pypi.org/project/unicodedata2/15.1.0/)
