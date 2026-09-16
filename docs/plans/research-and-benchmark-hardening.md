# Aleph Research and Benchmark Hardening Plan

Status: active research plan  
Date: 2026-09-17  
Owner role: research lead and engineering lead  
Tracking issue: [#29](https://github.com/p-to-q/aleph/issues/29)

## Objective

Turn Aleph from a convincing reverse-prompt prototype into a credible research instrument whose
claims, measurements, software, benchmark releases, and product surfaces all describe the same
object.

The immediate goal is not to add another panel or publish a larger leaderboard. It is to establish a
measurement contract that can survive hostile review, prove it with a small real-model pilot, and
then harden the product and standalone benchmark around that evidence.

## Role and responsibilities

The research lead is responsible for:

- defining the construct before choosing a metric;
- separating measured facts, engineering receipts, hypotheses, and product metaphors;
- preregistering the important pilot choices before looking at model rankings;
- treating prompt leakage, memorization, tokenizer effects, and ladder-author effects as possible
  confounds rather than footnotes;
- refusing public model-ranking claims until real-model evidence and replay artifacts exist.

The engineering lead is responsible for:

- keeping one canonical source for each contract and release artifact;
- making runs replayable from pinned data, code, configuration, model identity, and raw outputs;
- preserving `AlephRun`, `CandidatePoint`, and `ObservationSet` as the product exchange boundary;
- making CI exercise the same gates maintainers cite in release notes;
- reducing scope when a new abstraction does not improve validity, reproducibility, or the user
  journey.

The two roles share one rule: **a polished artifact is not evidence of the claim it illustrates**.

## Evidence inspected in this pass

Repository evidence:

- the public thesis, architecture, research process, state of play, quality bar, verification notes,
  core types, scoring helpers, API tests, and current GitHub issue/PR state;
- the `codex/m0-implementation` benchmark branch and the later
  `claude/hardcore-turing-a706f5` worktree, inspected read-only because it contains uncommitted user
  work;
- the standalone `p-to-q/aleph-benchmark` repository and its M0 platform snapshot;
- prior Aleph and p-to-q discussion recovered from ChatGPT history, used as context but not treated
  as a source of technical truth;
- current p-to-q comparators: Murmur, Wittgenstein, and Matter, especially their CI, golden/e2e
  receipts, failure paths, and architecture checks.

External standards and primary references:

- [HELM](https://crfm.stanford.edu/helm/) for prompt-level transparency, reproducibility, scenarios,
  and multi-metric reporting;
- [Inspect Evals contribution standards](https://github.com/UKGovernmentBEIS/inspect_evals/blob/main/CONTRIBUTING.md)
  for reference-result comparison, transcript inspection, uncertainty, tests, and manual end-to-end
  verification;
- [lm-evaluation-harness task configuration](https://github.com/EleutherAI/lm-evaluation-harness/blob/main/docs/task_guide.md)
  for versioned, shareable evaluation configuration and logged samples;
- [Kaggle Benchmarks documentation](https://www.kaggle.com/docs/benchmarks) for the platform's
  robustness, reproducibility, transparency, task, and benchmark contracts;
- [Hugging Face dataset cards](https://huggingface.co/docs/hub/datasets-cards) for limitations,
  provenance, responsible use, and discoverable data configuration;
- [Measuring what Matters](https://arxiv.org/abs/2511.04703) for construct-validity discipline in LLM
  benchmarks;
- [Do All Languages Cost the Same?](https://aclanthology.org/2023.emnlp-main.614/) and
  [Language Model Tokenizers Introduce Unfairness Between Languages](https://arxiv.org/abs/2305.15425)
  for the operational and multilingual consequences of tokenizer choice;
- [Fundamental Limits of Prompt Compression](https://arxiv.org/abs/2407.15504) for a genuine
  rate-distortion treatment of hard-prompt compression;
- [ARCA](https://arxiv.org/abs/2303.04381) and
  [GEPA](https://arxiv.org/abs/2507.19457) as stronger search routes whose budgets and optimization
  behavior must remain distinct from a frozen prompt ladder.

## Baseline verdict

Aleph's thesis and honesty language are stronger than its current experimental depth. The main
repository is understandable, builds, and has useful contract checks. Aleph-Bench has a thoughtful
design dossier, a substantial mock pipeline, and serious platform packaging work. The weak point is
the bridge between those artifacts and the scientific claims.

This pass found three different benchmark truth surfaces:

1. benchmark source and research documents on an Aleph development branch/worktree;
2. generated Kaggle/Hugging Face platform packages;
3. the public `p-to-q/aleph-benchmark` repository, which currently contains one imported snapshot.

The standalone repository is not yet a self-reproducing source repository: it has one import commit,
no repository license, no CI, local absolute-path links in its README, and mock evidence rather than
real cross-model results. The active worktree is more advanced, but it is unmerged and contains
uncommitted changes. Until one source is declared authoritative, changes can be correct in one copy
and stale in another.

The main Aleph baseline passed on Node 22.20.0:

```text
npm run lint
npm test
npm --workspace web run build
git diff --check
```

That is useful but narrower than the repository's release-gate language. GitHub CI currently runs
only `npm run lint`; it does not install the web lockfile, build the Next.js app, run the FastAPI
tests, or exercise a real adapter smoke path.

## Critical findings

### P0 — the measured length is not the claimed token length

The M0 benchmark's `token_count()` counts ASCII alphanumeric spans with
`[A-Za-z0-9]+`. The product core uses whitespace splitting. Neither is a model tokenizer, and the M0
counter assigns no meaningful units to Chinese or many other scripts.

Therefore current M0 values are not defensibly "prompt tokens" across models. They are a local proxy
for English word-like spans. This affects AURC, ECL@tau, Elicit@k, compression ratios, and every cost
interpretation built on them.

Required correction:

- rename the existing unit honestly while results still use it;
- record a provider/model tokenizer identity where available;
- report at least two axes:
  - a model-neutral length such as UTF-8 bytes or Unicode scalar count for cross-model comparison;
  - provider-reported/model-tokenizer input tokens for operational cost;
- never combine the axes into one headline without a declared interpretation;
- add Latin, CJK, punctuation-heavy, code, and empty-string conformance cases.

### P0 — Frozen Ladder does not estimate an intrinsic shortest prompt

Track F evaluates a small human-authored set of prompts. It does not search prompt space at evaluation
time. The measured object is therefore closer to:

> model response efficiency on this frozen, authored ladder under this decoding and scorer

than to:

> the model's intrinsic description length for the target

This distinction is not cosmetic. Ladder wording, information sufficiency, formatting conventions,
opaque item identifiers, and paraphrase quality can change ranks.

Required correction:

- name Track F as a frozen-ladder behavioral measurement;
- reserve "shortest found" and search-bounded description-length language for a budgeted search
  track;
- estimate ladder-author variance with independently authored or generated-and-reviewed ladders;
- add a prompt-order and paraphrase sensitivity report;
- test whether removing opaque item IDs changes results;
- keep Track W as a separate white-box information-theoretic table rather than implying that Track F
  is its black-box equivalent.

### P0 — the metric labels and estimators need sharper semantics

M0's `metricClass: "exact"` returns a normalized edit-distance score after any mismatch. That is a
useful graded metric, but it is not exact match. The current model summary also averages ECL only over
items that reach the threshold and reports coverage separately; ranking by the conditional mean alone
can make a low-coverage model look artificially efficient.

Required correction:

- split `exact_match` from `normalized_edit_similarity` or rename the M0 class;
- publish the parsing and normalization policy as part of the protocol version;
- make coverage a ranking gate or use a documented censored estimator;
- bootstrap at the independent sampling unit and cluster by generator family when items share a
  template;
- report paired per-item differences for model comparisons, not only overlapping marginal CIs;
- add scorer metamorphic tests: identity, empty output, added punctuation, row permutation, Unicode
  normalization, longer-but-worse prompts, and all-failed items.

### P0 — benchmark authority is split

The product repository, the public benchmark repository, and generated platform packages currently
blur source, build output, and distribution mirror.

Required decision:

- **recommended:** make `p-to-q/aleph-benchmark` the canonical benchmark source after it can generate
  its own platform package; keep Aleph as the product/workbench and consume versioned benchmark
  releases;
- until extraction is complete, declare the Aleph branch as the source and the standalone repository
  as a generated preview mirror;
- never hand-edit generated platform packages without updating their source and digest;
- preserve the dirty benchmark worktree until its owner resolves or commits it.

### P1 — verification claims exceed CI enforcement

Aleph's current CI protects documentation and lightweight contract checks, but not the complete
release path. The stronger p-to-q comparators enforce more of their stated contract:

- Murmur runs lint, typecheck, unit, e2e, worker, build-audit, and local-stack smoke paths;
- Wittgenstein runs boundary checks, unit and golden tests, deterministic reviewer receipts, and
  Python smokes;
- Matter runs architecture checks, type generation, unit tests, build, and Playwright e2e.

Aleph should not copy their workflow size blindly, but its CI should enforce the gates its own README
calls mandatory.

Minimum target:

```text
repository checks
+ core/schema/fixture tests
+ web dependency install and production build
+ FastAPI compile and unit tests
+ mock adapter smoke
```

Optional MLX and paid hosted checks should remain explicit, non-default receipts.

### P1 — real evidence remains too thin for a leaderboard

The standalone benchmark release correctly labels its rows as mock evidence. The later worktree has
Kaggle receipts, but those receipts are not yet part of a clean, canonical release. A public ranking
should wait for a controlled pilot with raw response logs, replay, model version identity, decoding
parameters, length units, latency/cost, failures, and paired uncertainty.

## Governing principles

1. **Name the operation, not the aspiration.** A frozen ladder, a search run, and a white-box score
   are different measurements.
2. **Dual-axis length reporting.** Cross-model description length and provider cost are related but
   not identical.
3. **Evidence modes are types.** `mock`, `fixture`, `black_box`, `white_box`, and future search modes
   must not share an unlabeled ranking surface.
4. **Raw samples before aggregates.** Every aggregate must be traceable to prompts, outputs, scorer
   version, and failure records.
5. **Paired comparisons by default.** Models are evaluated on the same items; analysis should use
   that pairing.
6. **Failures stay in the denominator.** Coverage, timeouts, refusals, and invalid outputs are part of
   the result.
7. **Protocol changes create versions.** Changing ladders, normalization, leakage thresholds,
   decoding, token units, or scorer semantics changes the benchmark version.
8. **Generated releases are closed-world artifacts.** Unexpected files fail package verification;
   generated packages are reproducible from source.
9. **Small proof before public surface.** A five-model pilot with audited samples is more valuable
   than a broad mock leaderboard.
10. **Product and benchmark remain coupled by files, not hidden code.** Versioned run/result files are
    the integration boundary.
11. **Real-world validation complements unit tests.** Replay and scorer tests do not replace manual
    review of sampled transcripts and the end-user path.
12. **Negative results are first-class.** If ranks are unstable, ladder-sensitive, or weakly related
    to production cost, publish that result and revise the construct.

## Long-range implementation

### M0 — authority and claim freeze

Deliverables:

- ADR naming the canonical benchmark source, generated mirrors, and release flow;
- issue set for length units, scorer semantics, CI, and real pilot;
- temporary wording change from intrinsic/minimal language to frozen-ladder behavioral language
  where the current implementation cannot support the stronger claim;
- clean disposition of the active benchmark branch/worktree without overwriting uncommitted work.

Acceptance gate:

- a contributor can identify the one source file for every schema, scorer, dataset row, and platform
  artifact;
- no mock number appears as a model ranking;
- all local and public links resolve outside the maintainer's machine.

### M1 — measurement contract v0.2

Deliverables:

- explicit `LengthMeasurement` metadata with unit, tokenizer/provider identity, and value;
- exact-match and edit-similarity scorers with separate names;
- coverage-safe ECL reporting;
- Unicode-aware leakage and length conformance tests;
- protocol manifest pinning data, prompts, scorer, decoding, retries, and model identity.

Acceptance gate:

- the same result can be independently recomputed from raw outputs;
- Chinese, English, code, punctuation, and empty cases have non-ambiguous length semantics;
- no chart labels a word proxy as model tokens.

### M2 — seed validity study

Deliverables:

- independent review of every S2 target and ladder for information sufficiency;
- at least two independently authored ladder variants for a study subset;
- prompt-order, paraphrase, item-ID, formatting, and threshold sensitivity analyses;
- family-clustered uncertainty and a documented sampling unit;
- a short threat-to-validity report with go/no-go criteria.

Acceptance gate:

- model ordering is not dominated by a single ladder author, opaque identifier, or generator family;
- any instability is visible in the report rather than averaged away.

### M3 — real paired pilot

Start small: three open-weight models with pinned revisions and up to two hosted models with explicit
version receipts. Use a preregistered subset and budget.

Deliverables:

- raw request/response records with secrets removed;
- retries, refusals, timeouts, invalid outputs, cost, and latency;
- model-neutral and model-tokenizer length axes;
- paired item-level estimates and confidence intervals;
- a blinded manual transcript review sample;
- a decision: continue, redesign the ladder, or reject the construct.

Acceptance gate:

- at least two independent people can replay the scorer and reproduce aggregates;
- the observed ranks remain directionally stable under declared reasonable scorer and ladder
  perturbations;
- no public release if the construct fails this gate.

### M4 — product engineering floor

Deliverables:

- CI that installs, tests, builds, and runs the mock API path;
- JSON import with schema validation and round-trip preservation of selected-candidate semantics;
- one browser smoke path from target input to loaded/exported `AlephRun`;
- a visible evidence legend shared by imported runs and live runs;
- runtime failures represented as data, not only banners.

Acceptance gate:

- a clean checkout passes the documented default gate;
- an exported run can leave the app, re-enter it, and retain its evidence mode and selected point;
- optional model services can fail without breaking the fixture path.

### M5 — standalone benchmark release

Deliverables:

- canonical source repository with license, contribution guide, citation, security posture, CI, and
  release tags;
- source-driven generation of Kaggle, Hugging Face, Croissant, and report artifacts;
- no absolute local paths;
- real hosted evidence bundle separate from mock pipeline receipts;
- protocol-versioned changelog and migration notes.

Acceptance gate:

- the standalone repository reproduces its release package without cloning a hidden parent tree;
- Kaggle/Hugging Face pages are manually checked after upload;
- release digests, raw samples, and aggregate tables agree.

### M6 — research expansion

Only after M3 succeeds:

- Track O: budget-matched search comparison across heuristic, reflective/Pareto, ARCA-like, and
  hard-prompt routes;
- Track W: teacher-forced NLL/two-part-code analysis for open-weight models;
- fresh and held-out item generation with contamination controls;
- multilingual strata with tokenizer-fertility reporting;
- cross-model transfer and garden-path-coordinate studies;
- external-validity study against actual prompt cost, latency, and task success.

## First issue sequence

1. **P0: Declare Aleph-Bench authority and release topology.**
2. **P0: Replace ambiguous token proxies with explicit dual-axis length measurements.**
3. **P0: Split exact match from normalized edit similarity and make ECL coverage-safe.**
4. **P1: Expand Aleph CI to the documented default release gate.**
5. **P1: Run and audit a preregistered real-model pilot.**
6. **P1: Make the standalone benchmark source self-reproducing.**
7. **P2: Add file-first run import and one browser round-trip.**
8. **P2: Decide whether Track F survives sensitivity testing before adding more strata.**

Each issue should have one acceptance gate, named validation commands, and explicit out-of-scope
work. Do not combine the repository extraction, metric rewrite, public launch, and product UI into one
PR.

## Stop conditions

Pause public benchmark expansion if any of these hold:

- rank order changes materially under reasonable ladder paraphrases;
- the length axis cannot be interpreted consistently across compared models;
- coverage drives the apparent efficiency ranking;
- scorer choices explain more variance than model identity;
- raw-output replay does not reproduce published aggregates;
- the standalone repository cannot reproduce its own package;
- real pilot evidence contradicts the production-cost interpretation.

These are not project failures. They are evidence that the current operationalization needs to
change.

## Out of scope for the first hardening cycle

- a large public leaderboard;
- claims of global shortest prompts or strict Kolmogorov complexity;
- new UI panels unrelated to the target → candidate path → evidence loop;
- ARCA/GCG/GEPA integration before the fixed-procedure pilot is valid;
- a database, accounts, billing, or new deployment topology;
- merging or rewriting the dirty benchmark worktree without its owner's disposition.
