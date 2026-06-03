# ALEPH-Bench

> A rate–distortion benchmark for **elicitation efficiency**: how few prompt tokens a model needs to
> regenerate a target output at a given fidelity. The leaderboard ranks *models*, not compressors,
> on an intrinsic, model-relative description-length axis that is orthogonal to accuracy.

This folder is the design dossier for turning Aleph's core object — the per-target compression path
`L̂_θ(ε) = min |p| s.t. d(θ(p), y) ≤ ε` — into a published, community-runnable benchmark. It is a
**proposal**, not yet a settled product fact. Read it alongside [`THESIS.md`](../../THESIS.md),
[`docs/core-concept.md`](../core-concept.md), and [`docs/claim-ledger.md`](../claim-ledger.md): the
benchmark must inherit Aleph's honesty discipline (upper bound, not minimum; model-relative, not
Kolmogorov; labeled evidence) rather than discard it under leaderboard pressure.

## Why this exists

Aleph already computes, for a *fixed* model θ, the rate–distortion frontier of prompts that
regenerate a target `y` (see [`search/aleph_search.py`](../../search/aleph_search.py) and the live
pitch script in [`web/public/aleph-frontier.json`](../../web/public/aleph-frontier.json), which
already frames this as "a hard, comparable measure of how much a model already knows"). A benchmark
is the natural next step: **hold the procedure fixed and vary the model.** What was an instrument for
inspecting one model becomes a yardstick for comparing many.

The construct has a direct economic reading, which is the reason to build it:

> A model that recovers intent from a terser prompt needs fewer prompt tokens to hit a target
> behavior — less few-shot scaffolding, less prompt-patching, less RL-on-top to force the output you
> already wanted. Elicitation efficiency *is* cost efficiency. ALEPH-Bench makes it measurable and
> comparable across models.

## The one-line novelty

Every existing prompt-compression line of work (LLMLingua and successors, "instruction-following
under compression", gist/ICAE) **fixes the model and compresses a given prompt, then measures
degradation** — it evaluates a *compressor*. ALEPH-Bench **fixes the target output and searches for
the minimal prompt, then measures the frontier per model** — it evaluates *the model's intrinsic
description length*. The axis is reversed (output-first), the subject is the model, and the score is a
rate–distortion *curve*, not a single compression ratio. See
[`04-positioning-and-novelty.md`](04-positioning-and-novelty.md).

## What we recommend (headline)

1. **Measure a curve, not a weighted sum.** Replace the current ad-hoc objective
   `fit·0.45 + stability·0.25 + compression·0.2 − leakage·0.1`
   ([`packages/core/src/metrics.ts`](../../packages/core/src/metrics.ts)) — which is a textbook
   construct-validity failure (arbitrary weights, confounded axes) — with the **area under the
   elicitation rate–distortion curve (AURC)** plus interpretable duals **ECL@τ** ("tokens to reach
   fidelity τ") and **Elicit@k** ("fidelity at a k-token budget"). Parameter-free headline, readable
   columns. See [`02-design-spec.md`](02-design-spec.md).
2. **Make leakage a hard gate, not a soft penalty.** A prompt that quotes the target is not
   compressing it. Disqualify any frontier point above a published copy-overlap threshold instead of
   subtracting `0.1·leakage`. This is the difference between an instrument and a benchmark.
3. **Ship a black-box leaderboard, with an accompanying white-box table.** The product is *Frozen
   Ladder* (Track F) — a public, cross-vendor **black-box leaderboard in the spirit of LMArena / LMSYS
   Chatbot Arena**, but ranking models on elicitation efficiency instead of human preference. It runs
   against every vendor (OpenAI / Anthropic / Google / DeepSeek / Qwen / Grok) because it uses only
   behavioral signals — the only signals closed APIs expose. Beside it sits a *separate,
   `white_box`-labeled* table (Track W, open-weights only: teacher-forced NLL / bits-per-byte) and an
   *Open Compression* division (Track O) for method submissions. The black-box board is the headline;
   the white-box table never merges into it. See [`12-platform-feasibility.md`](12-platform-feasibility.md)
   for why this split is forced by API reality, and SWE-bench (Verified vs Pro) for the precedent.
4. **Fix the dataset's construct validity.** The five canonical English texts in
   [`search/targets.py`](../../search/targets.py) measure *verbatim memorization of canon*, which
   confounds elicitation with "was this in pretraining." Keep them as one bounded stratum and add
   compositional, functional/behavioral, structured-output, and multilingual strata, plus a private
   held-out split and a time-gated fresh split for contamination control.
5. **Meet the community in its existing tools.** Multi-home the harness: a standalone
   `aleph-bench` package, a **Kaggle Community Benchmarks** task set (Kaggle now hosts exactly this,
   with free frontier-model access and a Resource Grant program), an **lm-evaluation-harness** task
   (the de-facto standard and HF Open LLM Leaderboard backend), and an **HF leaderboard Space + a
   Croissant-documented dataset**. Adoption comes from being runnable inside tools people already
   use, not from a bespoke runner.
6. **Earn trust the way credible benchmarks do.** Canary GUID, a never-published private split,
   bootstrap confidence intervals on every number, per-stratum breakdowns, an error-analysis gallery
   of "incompressible" targets, a contamination audit, a datasheet, and a maintenance plan. These are
   what make reviewers and the community comfortable. See [`01-research-synthesis.md`](01-research-synthesis.md).

## Document map

| File | What it answers |
|---|---|
| [`01-research-synthesis.md`](01-research-synthesis.md) | The research phase. What the strongest and most community-driven benchmarks actually do; the minimum bar; the eight construct-validity recommendations; contamination practice; how Kaggle / HF / lm-eval host benchmarks. Directly answers *(a) how to be comprehensive* and *(b) what makes the community comfortable and impressed*. |
| [`02-design-spec.md`](02-design-spec.md) | The benchmark itself: construct, three tracks, the rate–distortion metric family, the hard leakage gate, the fidelity-metric basket, the dataset taxonomy and strata, contamination defenses, and statistics. Includes the attempt to *break past* current best practice. |
| [`03-architecture-and-launch.md`](03-architecture-and-launch.md) | The technical work and how much of it: extended data contract, repo layout, reference engine, multi-home harness, a phased milestone plan with acceptance gates, governance, and risks. |
| [`04-positioning-and-novelty.md`](04-positioning-and-novelty.md) | Related work and the rebuttals to "aren't you just LLMLingua / inversion / another leaderboard?", the theory anchor (Language Modeling Is Compression, MDL, algorithmic rate–distortion), the novelty claims, and a paper outline. |
| [`05-metrics-audit.md`](05-metrics-audit.md) | Audit of every original Aleph instrument (`fit`, `stability`, `compression`, `leakage`, `nll`, `tokenLoss`, `waveform`, `attribution`, `lossCurve`, `exposureVectors`, `evalSuite`): **keep / adapt / drop / add**, split by **white-box vs black-box (Custom API)** evidence, plus the final per-track metric set and the evidence-mode contract. |
| [`06-search-rigor-and-production.md`](06-search-rigor-and-production.md) | How the design defeats **local minima** in compression search (the Frozen Ladder is local-minimum-immune by construction; Track O certifies convergence), and how the benchmark aligns to **production**: `ECL@τ` as a cost/latency procurement metric, the correctness floor, and a production-realism stratum. |
| [`07-release-strategy.md`](07-release-strategy.md) | The repo/hosting decision (**git-first dedicated repo, staged; HF/Kaggle as mirrors**), the SWE-bench authority template mapped to us, and the academic + engineering launch checklist. |
| [`08-forward-roadmap.md`](08-forward-roadmap.md) | The extrapolation: the **elicitation coefficient** as a spec-sheet number, the orthogonality result, the research questions opened, production-tooling spin-offs, a live division, and the north star. |
| [`09-metric-validity-and-rigor.md`](09-metric-validity-and-rigor.md) | The rigor spine: the formal definition; **metric accuracy via meta-evaluation** (human correlation); **balanced multi-dimensional scoring without arbitrary weights** (mean-score/IIA, dashboard, sensitivity); the **information-theoretic low-level layer** (NLL / bits-per-byte / two-part code); the four validity checks; and **production (external) validity**. |
| [`10-m0-engineering-spec.md`](10-m0-engineering-spec.md) | A **provisional "seed" build-spec** for the first reference implementation (M0): interfaces, schemas, metric pseudocode, a 30-item seed, acceptance gate, and marked `⚠ OPEN` uncertainties — meant to be handed to a coding model, rethought, and optimized. |
| [`11-paper-skeleton.md`](11-paper-skeleton.md) | A section-by-section arXiv / NeurIPS Datasets & Benchmarks scaffold: abstract, formalism, design, dataset, experiments (incl. the orthogonality and production-validity studies), limitations, and reproducibility. |
| [`12-platform-feasibility.md`](12-platform-feasibility.md) | **What is actually measurable on Kaggle and against closed APIs.** Per-vendor logprob reality (Claude exposes none; OpenAI/Gemini only generated-token, not teacher-forced; open weights full); the measurability matrix; why Track F is 100% capturable cross-vendor and Track W is open-weights-only; and the "behavioral shadow" (resampling) that estimates likelihood without logprobs. |
| [`launch-kit/`](launch-kit/) | Staged front matter for the future extracted public repo: a polished public [`README`](launch-kit/README.md), [`DATASHEET`](launch-kit/DATASHEET.md), [`CONTRIBUTING`](launch-kit/CONTRIBUTING.md), [`CITATION.cff`](launch-kit/CITATION.cff), and a [Kaggle grant application draft](launch-kit/kaggle-grant-application.md). |

## Implementation (the built artifact)

The design above is realized in code. M0 (Track F, Frozen Ladder) is implemented and passing:

- [`bench/`](../../bench/README.md) — the engine (frozen ladder, leakage gate, metrics, audit, bundle,
  manifest, verify, adapters), 30 S2 seed items, schemas, CLI (`./aleph-bench`), and a deterministic
  **mock** M0 result with audit/bundle receipts. All M0 acceptance gates pass; 27 unit tests pass.
- [`m0-evidence.md`](m0-evidence.md) — the first-run evidence note (mock model summary, per-item table,
  the resolved open-question choices, and the honest "this is mock pipeline evidence, not a real
  leaderboard" framing).
- [`hosted-m0-runbook.md`](hosted-m0-runbook.md) — how to run real black-box models once
  `ALEPH_CUSTOM_API_*` credentials exist.
- Platform export (`aleph-bench package`) produces the HF Dataset / Kaggle Dataset / Croissant delivery
  package, plus a Kaggle Community Benchmark scaffold and stubbed API-test smoke gate — see
  [`12-platform-feasibility.md`](12-platform-feasibility.md) and
  [`bench/results/platform/m0-mock/package-manifest.json`](../../bench/results/platform/m0-mock/package-manifest.json).

## Claims posture (read before quoting any number)

ALEPH-Bench introduces new public claims. Per [`docs/claim-ledger.md`](../claim-ledger.md), none are
settled until evidence exists. The honest framing:

- We report an **upper bound** on the shortest prompt ("we have not found shorter"), never a minimum.
  `K(y|θ)` is uncomputable; the benchmark measures a *budget-bounded, procedure-relative* estimate.
- A score is **relative to the fixed harness** (proposer, budget, decoding, metric, version). Change
  the harness and you change the number; that is why the harness is pinned and versioned.
- High scores on the **canonical-recall stratum** indicate memorization, not elicitation, and are
  reported separately so they cannot inflate the headline.
- Embedding-based fidelity is **one labeled metric class among several**, not ground truth; results
  are reported under a metric basket with sensitivity analysis.

If a future change would upgrade any of these to a stronger claim, route it through the claim ledger
before it reaches a leaderboard or paper.
