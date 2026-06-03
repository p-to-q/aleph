# Paper Skeleton — ALEPH-Bench

A section-by-section scaffold for the arXiv / NeurIPS Datasets & Benchmarks submission. Each section
lists its claim, the content, and the figures/tables, so the paper can be drafted in parallel with the
build. Target venue: **NeurIPS Datasets & Benchmarks (Evaluations & Datasets) Track** — which now
requires a Croissant file, datasheet, and reproducibility checklist, all of which the launch kit
already provides.

**Working title.** *ALEPH-Bench: Measuring How Little You Need to Say — A Rate–Distortion Benchmark for
Prompt Elicitation Efficiency.*

## Abstract (≤200 words)

Benchmarks measure whether a model is *right* at a fixed prompt. We measure how *little* you must say to
make it right: for a fixed target output, the shortest prompt a model needs to reproduce it at a
fidelity threshold. We formalize this as a per-model **rate–distortion frontier** (rate = prompt length,
distortion = 1 − fidelity) and summarize it with a parameter-free **AURC** and interpretable duals
(**ECL@τ**, **Elicit@k**). ALEPH-Bench evaluates models **output-first** and **black-box**, with a hard
**leakage gate** (copying ≠ compressing), **meta-evaluated** fidelity metrics, contamination-controlled
**public/held-out/fresh** splits, and a white-box **MDL** track grounded in bits-per-byte. Across <M>
models and <N> items in five strata we find <key result: e.g., elicitation efficiency is largely
independent of accuracy>, and that benchmark ECL predicts real production token cost (r=<…>). Scores are
honest upper bounds on the model-relative description length. We release the data (DOI), a versioned
harness (pip / Kaggle / lm-eval), and a public leaderboard.

## 1. Introduction

- **Claim.** Prompt-efficiency is a first-class, measurable model property, orthogonal to accuracy, with
  direct production-cost meaning — and nothing measures it.
- Folklore framing of prompt engineering → the inversion: *given the output, how little must I say?*
- The economic hook: fewer tokens to elicit intended behavior = lower cost, lower latency, less
  prompt-patching/RL. (The "降本增效" argument, made measurable.)
- Contributions list (mirrors [`04`](04-positioning-and-novelty.md) §4): the axis; the curve-valued
  parameter-free metric + leakage gate; the three-track design; the transfer metric; the contamination-
  resistant corpus; the empirical findings.
- **Fig 1**: the money figure — per-model rate–distortion curves on one axis + the accuracy×AURC scatter.

## 2. Background and related work

- Rate–distortion / MDL / *Language Modeling Is Compression*; algorithmic rate–distortion. The benchmark
  is the *backwards, comparative, empirical* instantiation.
- Prompt compression (LLMLingua family; gist/ICAE) — compresses a *given prompt*, evaluates a
  *compressor*. **Fundamental Limits of Prompt Compression** (Nagle et al.) — a *theoretical* distortion-
  rate limit for compressing *queries*. We differ: output-first, per-model, empirical leaderboard.
- Instruction-following-under-compression — exogenous compression, robustness axis; we search the
  minimal prompt, endogenous frontier.
- Inversion (vec2text / LM inversion) — recovers a hidden prompt; we don't.
- Benchmark methodology: construct validity (445-benchmark review); aggregation/social choice; SWE-bench
  / LiveBench contamination practice.
- **Table 1**: ALEPH-Bench vs prior work on {what's compressed, subject, output of measurement, model
  fixed?, cross-model?, metric type}.

## 3. The construct and formalism

- Definition: `L̂(y,ε) = min |p| s.t. D(θ_d(p),y) ≤ ε`; frontier `f(L)`; `AURC = (1/L_max)∫ f`.
- Upper-bound honesty; procedure-relativity; the `monotone` lower-envelope guarantee (more search only
  improves; never a claimed minimum).
- Distortion classes and the **bits** reading (Track W): two-part description length `|p|·c + NLL/ln2`,
  bits-per-byte.
- What the construct excludes by design: leakage (gate) and memorization (stratification).

## 4. Benchmark design

- **Three tracks**: Frozen Ladder (flagship, no eval-time search → local-minimum-immune), Open
  Compression (BYO compressor, pinned harness, convergence-certified), White-box MDL (open weights).
- **Metric family**: AURC (mean score, IIA-stable — *not* win rate, per §aggregation), ECL@τ, Elicit@k,
  CF, transfer gap; **leakage gate** and **correctness floor** as constraints; dashboard reporting +
  sensitivity (no arbitrary weights).
- **Metric accuracy**: the meta-evaluation protocol; per-stratum metric selection by human correlation;
  faithfulness/grounding beyond similarity.
- **Fig 2**: a single item's ladder → frontier → AURC, worked end-to-end.

## 5. The dataset

- Five strata (S1–S5) and the *why* of each; sampling protocol + power analysis for CI width.
- Construction pipeline (the SWE-bench-style argument): fresh-generate → multi-proposer compress →
  leakage-gate + convergence-certify → human audit; budget logged; not tuned to leaderboard models.
- Splits: public / **Verified** (human-audited) / private / rolling-fresh; canary GUID; licensing.
- **Table 2**: per-stratum counts, metric classes, contamination posture, languages.

## 6. Experiments

- Models: <M> across families/sizes/open-vs-closed/base-vs-tuned.
- **6.1 Leaderboard**: AURC + duals + CIs, per-stratum; S1 reported separately.
- **6.2 Orthogonality**: accuracy (MMLU/Arena) vs AURC scatter — the headline finding.
- **6.3 Track W (open weights)**: bits/description-length frontiers; gap to the EPFL distortion-rate
  reference.
- **6.4 Transfer**: universal vs model-specific (garden-path) short prompts; transfer-gap distribution.
- **6.5 Contamination**: public-vs-held-out gap; canary-emission audit.
- **6.6 Production validity**: correlation of ECL@τ with measured real deployment token cost.
- **6.7 Search rigor**: convergence diagnostics for Track O; ladder near-optimality evidence.
- Figures: leaderboard; orthogonality scatter; per-stratum profiles; transfer histogram; cost-correlation.

## 7. Analysis / discussion

- Is elicitation efficiency a scaling law? Does instruction-tuning/RLHF raise or lower it?
- The incompressible-targets gallery (error analysis): *what* models cannot compress, and why (hardest
  target tokens from NLL).
- Metric sensitivity (embedder choice, temperature, gate thresholds).

## 8. Limitations

Upper bound, not minimum · procedure/harness-relative · metric-class dependence · S1 memorization ·
Track O search-quality confound (disclosed) · black-box tracks cannot access bits · embedding/judge
fidelity is meta-validated but imperfect.

## 9. Ethics, licensing, reproducibility

- No sensitive personal data (or documented per item); RAI metadata in Croissant.
- Licensing per stratum; contamination-deterrent licensing on scraped subsets.
- Reproducibility checklist: seeds, pinned versions, harness, DOI'd data, public/held-out protocol.

## 10. Conclusion

Elicitation efficiency is a measurable, comparable, production-relevant axis the field has been missing;
ALEPH-Bench makes it a standard, honestly-bounded number — *the cost, in words, of being understood.*

---

### Appendices (release artifacts, already drafted in the launch kit)

- A. Datasheet ([`launch-kit/DATASHEET.md`](launch-kit/DATASHEET.md)).
- B. Full metric definitions + meta-evaluation results ([`09`](09-metric-validity-and-rigor.md)).
- C. Construction pipeline + convergence protocol ([`06`](06-search-rigor-and-production.md)).
- D. Harness/reproducibility ([`03`](03-architecture-and-launch.md), [`10`](10-m0-engineering-spec.md)).
- E. Per-model, per-stratum tables; prompts and canary; contamination audit.
