# Metric Validity and Rigor

This document is the rigor spine. It exists to guarantee ALEPH-Bench is a *valid, research-grounded
measurement system* and never a "tasteful but subjective" tool. It answers four demands directly:

1. a clear **definition / formula** for what is measured;
2. **metrics that are accurate**, that **balance into a fair score**, that are **multi-dimensional**
   rather than single-axis, and that include the **human-invisible low-level (information-theoretic)
   quantities** that matter;
3. **validity over taste** — every metric choice backed by method and evidence, not preference;
4. **production validity** — the score must predict real-world, low-cost deployability.

Each section names the established literature it stands on, so a reviewer sees research, not opinion.

## 1. The definition (the formula the whole benchmark hangs on)

ALEPH-Bench measures a **model-relative, budget-bounded description length of an output, elicited
through prompts.** For a fixed model `θ`, decoding rule `d`, distortion metric `D`, target output `y`,
and search budget `B`:

```text
Frontier (per item):   f_{θ,y}(L) = min over prompts p found within B, |p| ≤ L,  of  D(θ_d(p), y)
Description length:    L̂_{θ,d,D,B}(y, ε) = min |p|  s.t.  D(θ_d(p), y) ≤ ε
Headline (per item):   AURC_{θ}(y) = (1/L_max) ∫_0^{L_max} f_{θ,y}(L) dL      # area under the curve
```

This is a **lossy rate–distortion** object: rate = prompt length, distortion = `D`. It is *not* strict
Kolmogorov complexity (uncomputable) and *not* a claimed minimum — it is an **upper bound** discovered
under a fixed, versioned procedure ("we have not found shorter"). That honesty is load-bearing and
non-negotiable. The formalism is the same one the repo's engine already prints
([`search/aleph_search.py`](../../search/aleph_search.py)) and that the live pitch script states in
words. It is now also independently grounded: a rate–distortion theory of prompt compression for
black-box LLMs has been derived as a linear program (Nagle et al., *Fundamental Limits of Prompt
Compression*), which gives our axis a peer-reviewed theoretical backbone (and a reference optimum; see
§5 and [`04-positioning-and-novelty.md`](04-positioning-and-novelty.md)).

## 2. Metric accuracy — meta-evaluation, not assumption

A benchmark is only as trustworthy as its distortion metric `D`. We do **not** assume a single
embedding cosine is "accurate"; we **meta-evaluate** every candidate metric the way the NLG-evaluation
field does — by correlation with human judgment, the field's gold standard.

**Protocol (run once per metric version, per stratum):**

```text
1. Build a calibration set: (prompt, model output, target) triples spanning fidelity levels.
2. Collect human fidelity ratings (multiple annotators; report inter-annotator agreement).
3. For each candidate metric D ∈ {exact, lexical(ROUGE-L/edit), semantic(embedder), judge, execution}:
     compute correlation with human ratings using GLOBAL grouping + Pearson  (the configuration
     shown most reliable in NLG meta-evaluation), plus Spearman as a rank check.
4. Select, PER STRATUM, the metric with the highest human correlation as the primary D;
     report the correlation as the metric's validity coefficient.
5. Re-run on any metric/version bump; a metric whose human-correlation is unknown cannot be primary.
```

**Evidence anchors:** trained metrics (COMET, BLEURT) reach ~0.7 Pearson at segment level; unsupervised
BERTScore ~0.6; exact/execution are ~1.0 where applicable. So our per-stratum choice is principled:
**execution/exact where the target admits it** (S2/S4 — the most accurate), **a meta-validated trained
or embedding metric for semantic strata** (S1/S3), and **a judge with published rubric and reported
agreement** only where nothing cheaper correlates with humans. Synthetic-validation proxies (shown to
reach >0.9 meta-correlation in some settings) let us scale calibration without unlimited annotation.

This converts "is your fidelity score accurate?" from an opinion into a **reported number** with a
method behind it. It is the single most important rigor move in the whole benchmark.

**Faithfulness, not just similarity.** Per the prompt-compression-evaluation literature, downstream
similarity alone is insufficient: compression can silently destroy *grounding* (faithfulness drops of
30–50 points are documented). So for content-bearing strata we additionally report a **grounding
check** (claim-level faithfulness, FABLES-style: extract claims from the output, verify each against
the target), separating "looks similar" from "actually preserves the target's information." This is how
we measure **distortion accurately** rather than via one gameable number.

## 3. Balanced, multi-dimensional scoring — without arbitrary weights

The user's requirement — metrics must *balance well and complete the scoring together*, be a
*multi-dimensional core* not a single axis — is exactly where most benchmarks fail (the construct-
validity review flags arbitrary weighting; the benchmark-aggregation literature proves no aggregation
is free of artifacts). Our design follows that literature deliberately:

- **The headline is a mean score, not a win rate.** AURC is a per-item cardinal value averaged over
  items — a **mean-score** aggregate. We avoid **mean win rate / Borda**, which are *set-dependent*
  (adding an irrelevant model can flip ranks — a violation of Independence of Irrelevant Alternatives)
  and which **HELM itself abandoned** for exactly this reason. Mean score is set-independent and
  IIA-stable.
- **The two core axes are balanced by integration, not by weights.** Length and fidelity are not
  fused with hand-picked coefficients; they are jointly accounted for by the **area under the
  rate–distortion curve**. AURC *is* the principled balance of "how short" against "how faithful"
  across the whole budget — there is no `0.45 / 0.25 / 0.2` to argue about.
- **Leakage and correctness are gates, not terms.** Copying disqualifies a point; the correctness
  floor (high-τ operating point) bounds fidelity. Constraints, not weighted penalties — so nothing can
  be "bought" by trading axes.
- **Report a dashboard, resist one number.** Per the aggregation literature's recommendation, we
  publish AURC **with** ECL@τ, Elicit@k, per-stratum profiles, transfer gap, contamination gap, and
  cost — multiple commensurable views, not an over-collapsed scalar. The leaderboard sorts by AURC but
  *shows* the dimensions.
- **Normalize transparently.** Distortion is mapped to [0,1] with documented anchors (0 = exact match;
  1 = the empty/blank-prompt baseline for that item), so cross-item averaging is commensurable — the
  "dynamic-range normalization" the aggregation literature recommends, with the choice documented.
- **Report sensitivity.** We publish how rankings shift when models are added/removed or when the
  metric basket is reweighted — turning the unavoidable aggregation artifacts into a *disclosed*
  property rather than a hidden one.

The result is a scoring system where the balance between dimensions is either **principled (the
integral)** or **constraint-based (the gates)** or **transparently reported (the dashboard)** — never an
arbitrary weight.

## 4. The human-invisible low-level layer (the information-theoretic core)

The user is right that the metrics that matter most are partly **invisible to humans**: not "does this
look right" but the underlying **bits**. ALEPH-Bench makes these first-class in **Track W** (open
weights), where they are the most rigorous numbers we can report:

- **Cross-entropy / NLL** of the target given the prompt — the model's surprise at `y`, in nats/bits.
- **Bits-per-byte (BPB)** = average cross-entropy in base-2 over the target's bytes — the canonical
  information-theoretic LM-evaluation quantity, and the standard bridge between *language modeling and
  compression*. BPB is tokenizer-agnostic, so it is comparable across models with different vocabularies
  (a property token-NLL lacks).
- **Two-part description length**: `DL_θ(y|p) = |p|·c_bits + NLL_θ(y|p)/ln2` — the MDL reading of the
  whole object: prompt code length + residual code length to encode `y`. Minimizing it is literally
  "find the shortest total description of `y` that this model admits."
- **Distortion–rate reference**: Nagle et al.'s LP gives the *optimal* achievable rate at a distortion
  for prompt compression; we can report each model's gap to that optimum as a normalized rigor anchor.

These quantities are why ALEPH-Bench is a measurement, not a vibe: even where a human cannot see why one
prompt is "better," the bits can. Black-box tracks (F/O) cannot access them — which is exactly why the
evidence-mode contract ([`05-metrics-audit.md`](05-metrics-audit.md) §5) keeps them in a separate,
labeled track and never lets a black-box row borrow a bits claim.

## 5. Validity over taste — the four validity checks

To guarantee this is "a valid and rigorous system with sufficient research support," every metric and
the benchmark as a whole pass four named validity checks drawn from measurement theory and the LLM-
benchmark literature:

| Validity type | Question | How ALEPH-Bench satisfies it |
|---|---|---|
| **Construct** | Does it measure elicitation efficiency and *only* that? | The 8 construct-validity recommendations ([`01`](01-research-synthesis.md)); leakage gate + memorization stratification exclude the two confounds. |
| **Criterion (concurrent)** | Do the automatic metrics agree with humans? | The meta-evaluation protocol (§2): reported human-correlation per metric/stratum. |
| **Internal / theoretical** | Is the quantity well-defined and grounded? | The rate–distortion / MDL formalism (§1, §4); the EPFL distortion-rate theory as backbone. |
| **External (predictive)** | Does the score predict real-world value? | The production-cost study (§6). |

A tool that passes construct + criterion + internal + external validity is, by definition, *not* a
matter of taste. That is the bar this document holds the benchmark to.

## 6. Production validity — the score must predict deployability

The final, strongest anti-taste check, and the user's fourth requirement: a model that scores well must
be **genuinely cheaper and easier to deploy**, especially in high-demand, high-barrier production. We
make this a *measured* claim, not a hope:

- **Predictive study**: take a set of real production behaviors; measure each model's actual token spend
  to achieve them in deployment; correlate with the model's benchmark ECL@τ / CF. A high correlation is
  direct **external validity** — the benchmark predicts production cost. (Report the correlation; if it
  is weak, the construct is wrong and we say so.)
- **Cost/latency reporting** ([`06`](06-search-rigor-and-production.md) §B): `ECL$` and `ECL_latency`
  translate the abstract score into money and milliseconds a platform team acts on.
- **Correctness floor**: the headline operating point is "shortest prompt that still clears a
  correctness floor," because production wants short-*and*-correct, not short-on-average.
- **The optimization is transferable**: because Track F measures *decompression of a shared
  description*, a model that wins is one that genuinely needs fewer tokens for the *same* intent — so an
  enterprise can cut prompt length on that model and keep behavior, which is the "降本增效" payoff made
  literal.

If the §6 correlation holds, ALEPH-Bench is simultaneously a valid scientific instrument and a
procurement tool — academic meaning and production usability in one number. That dual validity is the
target the rest of the dossier builds toward.

---

## Sources

- [Measuring what Matters: Construct Validity in LLM Benchmarks](https://arxiv.org/abs/2511.04703)
- [Analyzing and Evaluating Correlation Measures in NLG Meta-Evaluation](https://arxiv.org/html/2410.16834) · [LLM as a Meta-Judge: Synthetic Data for NLP Evaluation Metric Validation](https://arxiv.org/pdf/2603.09403)
- [The Emerging Science of ML Benchmarks — The problem of aggregation](https://mlbenchmarks.org/12-problem-aggregation.html) · [HELM Capabilities (mean score vs win rate)](https://crfm.stanford.edu/2025/03/20/helm-capabilities.html) · [Beyond Arrow: Multi-Criteria Benchmarking](https://arxiv.org/pdf/2602.07593)
- [Bits-per-Byte / information-theoretic LM evaluation](https://www.emergentmind.com/topics/bits-per-byte-bpb) · [Language Modeling Is Compression](https://arxiv.org/abs/2309.10668)
- [Fundamental Limits of Prompt Compression: A Rate–Distortion Framework for Black-Box LLMs](https://arxiv.org/abs/2407.15504)
- [Understanding and Improving Information Preservation in Prompt Compression](https://arxiv.org/abs/2503.19114) · [LLMLingua-2 (faithful task-agnostic compression)](https://arxiv.org/pdf/2403.12968)
