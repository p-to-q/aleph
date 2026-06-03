# Beyond v1: What ALEPH-Bench Becomes

This document extrapolates. The previous files define a publishable v1; this one asks what the
benchmark *grows into* if v1 lands — the moves that turn a single leaderboard into a standard, an
instrument, and a small ecosystem. It is deliberately ambitious, and it is labeled as vision, not
commitment, in keeping with the repo's claim discipline.

## 1. The elicitation coefficient as a model spec-sheet number

Today a model is described by parameters, context window, price, and a handful of accuracy scores
(MMLU, GPQA, SWE-bench). None of these answer *"how little do I need to say to this model to get the
behavior I want?"* — yet that question governs real production cost more directly than any accuracy
score.

The endpoint of ALEPH-Bench is a single, citable number that belongs on the spec sheet beside MMLU:

> **Elicitation coefficient** — the typical fraction of a naïve prompt this model needs to reach a
> correctness floor (median CF), with its AURC and per-stratum profile.

If the benchmark reaches the adoption of MMLU/SWE-bench, "model X has an elicitation coefficient of
0.18" becomes a thing people say — meaning X recovers intended behaviors from ~18% of the tokens a
naïve prompt would use. That is the north star: **make prompt-efficiency a first-class, comparable
model property.**

## 2. The orthogonality result — the finding that earns citations

The experiment that would make v1 *land* (see [`04`](04-positioning-and-novelty.md) §6) is a scatter of
accuracy vs AURC across many models. Three possible outcomes, each publishable:

- **Independent** — elicitation efficiency is *not* predicted by accuracy or scale. Then ALEPH-Bench
  measures a genuinely new axis, and capable-but-prompt-hungry vs modest-but-elicitable becomes a real
  procurement distinction. (Most interesting.)
- **Correlated** — efficiency tracks capability. Then it is a cheaper, prompt-length proxy for
  capability — still useful, and a clean scaling-law question.
- **Regime-dependent** — independent within a capability tier, correlated across tiers. Then it refines
  how we read leaderboards.

Any of the three is a result. The forward work is to run it at scale and characterize *which* it is,
across model families, sizes, and post-training recipes.

## 3. Research questions ALEPH-Bench opens

A good benchmark is a question generator. The ones this one opens:

- **Is elicitation efficiency a scaling law?** Does CF fall predictably with parameters / training
  tokens, like loss does?
- **What does post-training do to it?** Does instruction-tuning / RLHF make a model *more* elicitable
  (better at reading terse intent) or *less* (more verbose-prompt-dependent)? A controlled
  base-vs-tuned comparison is a clean paper.
- **Do short coordinates transfer?** The transfer-gap metric becomes a study: is there a *universal*
  minimal description of an output, or is every model's shortest prompt idiosyncratic? When do
  garden-path coordinates (the repo's own observation) generalize?
- **Does benchmark CF predict real production cost?** Validate the procurement claim against real
  deployment token spend — the strongest possible external validity check (construct-validity rec 8).
- **Is there an irreducible floor?** For a given output and model, does ECL approach a stable lower
  bound under heavier search — an empirical estimate of `K(y|θ)` — and how does that floor move with
  scale? This is the white-box MDL track turned into science.

## 4. Spin-off: from benchmark to production tooling

A benchmark that measures elicitation efficiency sits on top of exactly the data a production
**prompt-optimizer** needs. Natural spin-offs, in increasing ambition:

- **An elicitation-aware compressor** — use the benchmark's per-model frontiers to compress a
  customer's prompts *for their chosen model*, with the leakage gate and correctness floor built in.
  This is LLMLingua re-grounded on a per-model, fidelity-floored objective.
- **A model-procurement advisor** — given a customer's target behaviors, recommend the model with the
  lowest `ECL$` for *those* behaviors, not the highest MMLU. The benchmark is the engine; this is the
  product.
- **A "compile your prompt" service** — the Aleph workbench, already a compression instrument, becomes
  a tool that takes a desired behavior and emits the shortest prompt that holds it on a target model,
  with a measured fidelity guarantee. The benchmark provides the evaluation backbone that makes such a
  guarantee credible.

The dependency arrow matters: **the benchmark must exist and be trusted first**; the tools inherit its
credibility. This is the right order — measurement before optimization, exactly the order the repo's
thesis already prefers ("make the object legible first").

## 5. A live division (contamination's long game)

Public splits decay as models train on them. The LiveBench / LiveCodeBench answer is a **rolling fresh
division**: each quarter, regenerate compositional/structured/functional targets after a dated cutoff
and score models only on targets postdating their training. ALEPH-Bench is unusually well-suited to
this because most of its targets are *generated*, not scraped — freshness is cheap. The long-term shape
is a **frozen, citable v1** (stable for comparison and papers) plus a **live leaderboard** (always
contamination-clean), the same dual structure that keeps SWE-bench and LiveBench both relevant.

## 6. Coverage growth (the comprehensiveness long game)

v1 ships five strata; the axis is extensible without changing the metric:

- **Modalities** — elicitation of images / audio / structured tool-call sequences (Kaggle's SDK
  already supports multimodal I/O), measuring "how short a prompt summons this artifact."
- **Multi-turn** — the shortest *dialogue* that elicits a target behavior, not just the shortest single
  prompt — closer to how agents are actually steered.
- **Languages** — extend the EN+ZH base to a broad multilingual frontier; elicitation efficiency by
  language is itself a finding (does a model compress its lower-resource languages worse?).
- **Domains** — code, legal, medical, financial output families, each a stratum, each a procurement
  segment.

Each addition is a PR-able stratum under the same AURC/ECL contract — the HELM "scenario grid" pattern,
grown by the community rather than the maintainers.

## 7. The north star (one paragraph)

ALEPH-Bench should become the standard way to ask, and answer, *"how little do you need to say to this
model?"* — a number on every model's spec sheet, an axis every procurement decision can read, a science
instrument for studying what a frozen model already knows, and the trusted measurement layer beneath a
new generation of prompt-compression tooling. It starts as the natural next step from a workbench that
already computes the curve, and it ends — if it lands — as the place the field looks to compare models
on the one axis the accuracy leaderboards cannot see: **the cost, in words, of being understood.**
