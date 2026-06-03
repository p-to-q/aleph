<!-- STAGED TEMPLATE for the future extracted `aleph-bench` public repo.
     This is NOT the current Aleph product README. It is the front door we launch the
     dedicated benchmark repo with at M1 (see ../07-release-strategy.md). Placeholders
     marked <LIKE_THIS> are filled at extraction. -->

# ALEPH-Bench

**How little do you need to say to a model to get the output you want?**

ALEPH-Bench measures **elicitation efficiency**: for a target output, the *shortest prompt* a model
needs to reproduce it at a required fidelity. It ranks models on a rate–distortion curve — an
intrinsic, comparable description-length property that **accuracy leaderboards cannot see** — and reads
out directly as a production cost: fewer tokens to elicit the behavior you want.

**Leaderboard** · **Paper** · **Dataset (HF)** · **Kaggle** · `pip install aleph-bench`
<br/><sub>Links filled at repo extraction: `<LEADERBOARD_URL>` `<PAPER_URL>` `<HF_DATASET_URL>` `<KAGGLE_URL>` `<PYPI_URL>`</sub>

> A high score means: this model recovers intended outputs from terser prompts — cheaper per call,
> faster to first token, less prompt-engineering and less RL-patching to stay on target.
> It does **not** mean the model is more accurate. Elicitation efficiency is a *different axis*.

## The idea in one formula

For a fixed model `θ`, decoding `d`, distortion metric `D`, target output `y`, and search budget `B`:

```
L̂(y, ε) = min |p|   such that   D( θ_d(p), y ) ≤ ε
```

the fewest prompt tokens that make the model reproduce `y` within distortion `ε`. Sweep `ε` and you get
a **rate–distortion curve** per model; the benchmark's headline metric is the **area under it (AURC)**.
We report an honest **upper bound** ("we have not found shorter"), never a claimed minimum — `K(y|θ)` is
uncomputable.

## Why it matters

| Question accuracy benchmarks answer | Question ALEPH-Bench answers |
|---|---|
| Is the model *right* at a fixed prompt? | How *few tokens* does it need to be told? |
| Capability | Elicitation efficiency / prompt-cost |

For procurement: **for the behaviors your product needs, which model needs the fewest tokens?** That
model is cheaper, faster, and needs less prompt scaffolding — the `ECL@τ` and `ECL$` columns make this
explicit.

## Leaderboard (headline)

| Model | AURC ↓ | ECL@0.9 (tokens) | CF (% of naïve) | Elicit@16 | Transfer gap |
|---|---|---|---|---|---|
| … | … (95% CI) | … | … | … | … |

Sorted by **AURC** (a mean score — stable under adding/removing models, unlike win-rate). The dashboard
shows the dimensions rather than collapsing to one number; per-stratum breakdowns and the
public-vs-held-out contamination gap are in the full board.

## Quickstart

```bash
pip install aleph-bench
# evaluate a model on the public split, Frozen-Ladder track, reproducibly
aleph-bench run --track F --model <model-id> --split public --seed 0 --out result.json
# also runs as a Kaggle Benchmarks task and an lm-evaluation-harness task
```

`result.json` is a schema-valid `BenchResult`: per-item frontiers, AURC with bootstrap CIs, ECL@τ,
Elicit@k, leakage-gate hits, and per-stratum profiles.

## Tracks

The product is a **black-box leaderboard with an accompanying white-box table** — never merged.

- **Track F — Frozen Ladder** *(flagship, all vendors, black-box).* A public, cross-vendor leaderboard
  in the spirit of LMArena, but ranking models on **elicitation efficiency** instead of human
  preference. Every model is scored on the same frozen, audited prompt ladders; no search at evaluation
  → reproducible and immune to search-quality confounds. Built entirely from behavioral signals, so it
  runs against every vendor including those that expose no logprobs. **This is the headline board.**
- **Track O — Open Compression** *(bring-your-own compressor).* Supply a compressor/search under a
  pinned harness; report achieved length–fidelity with budget disclosure and a convergence diagnostic.
  Where ARCA/GCG/LLMLingua-style methods compete.
- **Track W — White-box MDL** *(open weights only; a separate, `white_box`-labeled table).*
  Information-theoretic description length from teacher-forced NLL / bits-per-byte — the most rigorous
  number we can report. Closed APIs cannot expose these, so this table accompanies the leaderboard for
  open-weight models rather than ranking all vendors. See [platform feasibility](../12-platform-feasibility.md).

## Dataset

Five strata, each probing a different decompression ability: **canonical recall**, **compositional**,
**functional/behavioral**, **structured**, **multilingual (EN+ZH)**. Splits: **public**, a human-
validated **Verified** subset, and a never-published **private + rolling-fresh** split for contamination
control. Every public file carries a canary GUID. Full provenance and licensing in
[`DATASHEET.md`](DATASHEET.md). Machine-readable metadata in `croissant.json`.

**Contamination posture:** most targets are generated *fresh* (non-memorizable); canonical-recall is a
bounded, separately-reported stratum (a high score there is memorization, not elicitation). We publish
the public-vs-held-out gap and a contamination audit.

## How a high score is kept honest

- **Leakage gate** — a prompt that quotes the target is *disqualified*, not discounted. Copying is not
  compressing.
- **Metric accuracy is meta-evaluated** — fidelity metrics are validated against human judgment and
  reported with their correlation; execution/exact used wherever the target allows.
- **Correctness floor** — the headline operating point is "shortest prompt that is still correct," not
  "shortest on average."
- **Evidence-mode labels** — black-box rows never display white-box (logit) claims.

See [the rigor spine](../09-metric-validity-and-rigor.md) for the full validity argument.

## Submit

- **A model** → open a submission PR (or run the Kaggle task); held-out/private splits are run by
  maintainers. See [`CONTRIBUTING.md`](CONTRIBUTING.md).
- **A task/stratum item** → PR a `BenchItem` with provenance, license, and metric class (BIG-bench-style
  review). See [`CONTRIBUTING.md`](CONTRIBUTING.md).

## Cite

See [`CITATION.cff`](CITATION.cff). The dataset release is DOI'd via Zenodo.

## Related work (one line)

Prompt-compression work (LLMLingua; *Fundamental Limits of Prompt Compression*) compresses a **given
prompt** and measures a **compressor** or a **theoretical limit**; ALEPH-Bench fixes the **output** and
measures each **model's** frontier as an empirical leaderboard. Full positioning in the paper.

## License

Code: Apache-2.0. Data: per-stratum licensing in [`DATASHEET.md`](DATASHEET.md).
