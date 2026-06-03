<!-- STAGED TEMPLATE for the future `aleph-bench` repo. Datasheet follows Gebru et al.,
     "Datasheets for Datasets". Fill <PLACEHOLDERS> at release. Required by NeurIPS D&B. -->

# Datasheet — ALEPH-Bench

## Motivation

- **Purpose.** Measure *elicitation efficiency* — the shortest prompt a model needs to reproduce a
  target output at a fidelity threshold — as a comparable, intrinsic model property, and as a
  production-cost predictor. No existing benchmark measures prompt-length-at-fixed-fidelity across
  models.
- **Created by.** <AUTHORS / ORG>. Built on the open-source Aleph reverse-prompt-compression workbench.
- **Funding.** <GRANTS — e.g., Kaggle Benchmarks Resource Grant for model access>.

## Composition

- **Instances.** Each instance is a `BenchItem`: a target output `y`, a metric class (exact / lexical /
  semantic / rubric / execution), a frozen prompt **ladder** (rungs from explicit reconstruction to a
  minimal cue, with k paraphrases per rung), a stratum label, a language, a canary GUID, and
  provenance/license.
- **Strata (the declared taxonomy).**
  - **S1 Canonical recall** — famous texts (memorization-prone; **bounded share; reported separately**).
  - **S2 Compositional** — rule-generated, non-memorizable outputs.
  - **S3 Functional/behavioral** — a task/spec scored by held-out cases or a rubric (production-realistic).
  - **S4 Structured** — code / JSON / SQL / regex / tables, scored by execution or schema validation.
  - **S5 Multilingual** — EN + ZH across the above.
- **Counts.** <N per stratum> public; <N> Verified (human-audited); <N> private; <N> rolling-fresh.
  Sample sizes chosen by a power analysis for the target CI width (see paper §experiments).
- **Splits.** `public` · `verified` · `private` (never published) · `fresh` (rolling, time-gated).
- **Labels/targets.** The target output and (for S3/S4) the held-out test suite / rubric. No personal
  data unless explicitly noted per item.
- **Known confounds.** S1 measures memorization, not elicitation — kept bounded and broken out.

## Collection & generation process

- **Generated strata (S2/S4, much of S3).** Programmatically generated *after a dated cutoff* so targets
  are non-memorizable; generators and seeds are released for reproducibility.
- **Curated strata (S1, parts of S5).** Sourced from public-domain / appropriately-licensed texts with
  per-item provenance.
- **Ladder construction.** Each item's ladder is produced offline by a **multi-proposer search**
  (LLM proposer at multiple seeds + extractive compressor + discrete optimizer + human adversarial
  shortening), reduced to the monotone lower envelope, **leakage-gated**, and **human-audited**. The
  construction budget is logged. Ladders are *not* tuned to any leaderboard model.
- **Validation.** Fidelity metrics are meta-evaluated against human ratings on a calibration set;
  reported correlations gate which metric is primary per stratum (see rigor spine, docs/09).

## Preprocessing / cleaning / labeling

- Normalization rules for exact-match (whitespace/case/Unicode) are published and versioned.
- Canary GUID inserted into every public file; a canary-emission probe is part of the contamination audit.

## Uses

- **Intended.** Model comparison on elicitation efficiency; prompt-cost procurement; research on
  description length, transfer, and post-training effects.
- **Out of scope / cautions.** Not a capability/accuracy benchmark; not a claim of globally shortest
  prompts; scores are **procedure-relative** and are **upper bounds**. Do not read S1 scores as general
  elicitation.

## Distribution

- **Where.** Canonical git repo <REPO_URL>; dataset mirror on Hugging Face <HF_URL> with `croissant.json`
  (+ RAI metadata); tasks on Kaggle <KAGGLE_URL>; an lm-evaluation-harness task.
- **License.** Code Apache-2.0; data per-stratum (public-domain or permissive for curated; generated
  strata under <LICENSE>; consider strong copyleft on any scraped subset as a contamination deterrent).
- **DOI.** Zenodo <DOI> for the frozen versioned release.

## Maintenance

- **Maintainers.** <ORG/TEAM>. Contact <EMAIL/ISSUES_URL>.
- **Versioning.** `aleph-bench@MAJOR.MINOR`; any change to metric, ladder, gate threshold, or split is a
  version bump in `CHANGELOG`; old versions stay runnable so historical leaderboard rows remain valid.
- **Freshness.** The `fresh` split rolls on a fixed cadence (<quarterly>) with a published cutoff date.
- **Contributions.** New items by PR with the review checklist in `CONTRIBUTING.md`; private/held-out
  splits are run only by maintainers.

## Limitations (carried with every release)

Upper bound, not minimum · procedure/harness-relative · metric-class dependence · S1 memorization ·
Track O search-quality confound (mitigated by disclosure) · black-box tracks cannot access bits.
