<!-- DRAFT application for the Kaggle Benchmarks Resource Grant Program.
     The grant provides increased compute quota and free access to leading models
     (OpenAI, Google, Anthropic, Grok, Qwen, DeepSeek) — the practical unlock for a
     cross-model benchmark. Tighten to Kaggle's form fields at submission. -->

# Kaggle Benchmarks Resource Grant — Application Draft

## Benchmark name
ALEPH-Bench — a rate–distortion benchmark for prompt **elicitation efficiency**.

## One-sentence summary
ALEPH-Bench measures, across models, the *shortest prompt* needed to reproduce a target output at a
required fidelity — an intrinsic, comparable "how few tokens to elicit the behavior" axis that accuracy
leaderboards do not capture and that maps directly to production prompt cost.

## What it evaluates (and why it needs many models)
The benchmark's entire value is **cross-model comparison**: the result is a leaderboard of frontier
models on their elicitation rate–distortion frontiers. That requires running the same frozen prompt
ladders through *every* major model under pinned decoding. Free access to OpenAI, Google, Anthropic,
Grok, Qwen, and DeepSeek models via Kaggle is the single thing that makes a credible, vendor-neutral
board feasible without prohibitive API spend.

## Why it fits Kaggle Community Benchmarks
- It is exactly the "go beyond static accuracy" use case the program targets: a curve-valued,
  multi-dimensional measurement, reproducible and auditable.
- It maps cleanly onto the `@kbench.task` SDK: each `BenchItem` is a task that prompts the model with a
  frozen ladder rung and scores fidelity with built-in/custom assertions; tasks group into a Benchmark →
  native Kaggle leaderboard.
- It produces a genuinely **new** leaderboard axis (prompt-cost efficiency / "降本增效"), of direct
  interest to the developers Kaggle Benchmarks serves.

## Compute / resources requested
- Model-inference quota across the listed providers sufficient for: <N items> × <k paraphrases> ×
  <R reruns> × <M models> for the public split, plus the rolling-fresh split each cycle.
- Notebook compute for the frozen-ladder evaluation (lightweight — no training; black-box inference and
  scoring only).
- (Optional) GPU quota for the white-box Track W on open-weight models (teacher-forced NLL / bits-per-byte).

## Reproducibility & rigor (what we commit to)
- Schema-valid `BenchResult` from a fixed seed; pinned model/decoding/metric versions.
- A hard **leakage gate** (copying disqualified), **meta-evaluated** fidelity metrics (human-correlation
  reported), **bootstrap CIs** on every number, and **per-stratum** reporting.
- A **public + held-out** split with a published contamination gap and canary probe.
- Honest framing: scores are upper bounds and procedure-relative.

## Team & status
<TEAM>. Built on the open-source Aleph reverse-prompt-compression engine (live demo, shared run
contract, hosted black-box + local white-box adapters already implemented). Full design dossier and
rigor argument are public in the repository.

## Intended outcomes
- A public Kaggle leaderboard tracking elicitation efficiency across frontier models.
- A frozen, DOI'd dataset release + an arXiv / NeurIPS Datasets & Benchmarks paper.
- An lm-evaluation-harness task and a Hugging Face mirror so the benchmark runs wherever the community
  already works.

## Links
- Repository / design dossier: <REPO_URL>
- Live engine demo: <DEMO_URL>
- Contact: <EMAIL>
