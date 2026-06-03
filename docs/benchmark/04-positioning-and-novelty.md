# Positioning, Novelty, and the Paper

A benchmark is judged as much on *why it is different* as on how it is built. This document states the
novelty precisely, rebuts the challenges a reviewer or a Hacker News thread will raise, anchors the
idea in established theory, and sketches the paper. It extends the repo's existing prior-art discipline
([`docs/research/prior-art.md`](../research/prior-art.md),
[`docs/research/research-directions.md`](../research/research-directions.md)).

## 1. The novelty in one sentence

> Existing work measures **accuracy at a fixed prompt** (capability benchmarks) or **degradation of a
> given prompt under compression** (prompt-compression work). ALEPH-Bench measures the **minimum
> prompt length at fixed fidelity**, output-first, as a **per-model rate–distortion frontier** — an
> intrinsic, comparable description-length property of the model itself.

Three things are simultaneously different: the **axis** (length-at-fidelity, not fidelity-at-length),
the **subject** (the model, not an external compressor), and the **score type** (a curve summarized by
a parameter-free functional, not a single ratio or accuracy).

## 2. Rebuttals to the obvious challenges

### "Isn't this just LLMLingua / prompt compression?"
No — the direction and the subject are inverted. LLMLingua and its successors take a *given* prompt and
compress it with an external compressor (a small LM that drops low-information tokens), then measure how
much task performance survives. The object under evaluation is **the compressor**, the model is held
roughly fixed, and the result is a compression ratio at a tolerated drop (~20× at ~1.5 points). We fix
the *target output*, search for the shortest prompt, and the object under evaluation is **the model's
own description length** of that output. LLMLingua could be *one entry in our Track O*; it cannot be the
benchmark, because it does not produce a per-model frontier over targets.

### "Didn't *Fundamental Limits of Prompt Compression* (Nagle et al., 2407.15504) already do the rate–distortion theory?"
That paper is the closest theoretical neighbor, and it *helps* us: it derives the distortion–rate
function for prompt compression of black-box LLMs as a linear program — a peer-reviewed backbone for the
"rate–distortion of prompts" axis. But it (a) compresses an **input query/context**, not a path to a
target **output**; (b) computes a **theoretical optimum / lower bound** for a *compressor*, not an
**empirical leaderboard of models**; (c) is **query-aware compression** evaluated against the optimum,
not a per-model elicitation frontier. We are complementary: their LP optimum can serve as a **reference
upper bound** for our Track O ("how close is this compressor to information-theoretic optimal?"), while
ALEPH-Bench answers the *different* question their theory does not — *which model* needs the fewest
tokens to reproduce a given output, measured empirically and comparably. Citing them strengthens our
rigor; it does not pre-empt our benchmark.

### "Isn't this the 'instruction-following under compression' benchmark (2512.17920)?"
No. That work applies a *fixed exogenous* compression to instructions and measures *degradation*,
separating constraint-compliance from semantic accuracy along a "U-curve." The model is the subject but
the compression is external and the axis is *robustness to a given squeeze*. ALEPH-Bench makes
compression *endogenous and per-model* (each model induces its own frontier) and the axis is *how short
the prompt can get*, not how gracefully a model tolerates someone else's truncation. Their constraint
vs. semantic split is a good idea we can borrow inside the S3/S4 metric classes; the benchmark question
is different.

### "Isn't this prompt inversion / vec2text / LM inversion?"
No. Inversion recovers a *hidden original* prompt from outputs or embeddings and is judged by how well
it matches that original. We make no claim about any original prompt; we search for *a* usable short
coordinate for a target output. Adjacent field, different goal — the repo already records this boundary.

### "Isn't this just another leaderboard / Goodhart bait?"
The leakage gate, the bounded contaminated stratum, the private + fresh splits, the white-box MDL
anchor, and the upper-bound framing are specifically the anti-Goodhart machinery. And the construct is
*orthogonal* to accuracy, so it does not duplicate MMLU/Arena — it adds an axis (efficiency) those
cannot see. A model can top Arena and still be prompt-hungry; ALEPH-Bench is where that shows up.

### "The score depends on your search — so it measures your searcher, not the model."
True for Track O, which is why the **flagship is Track F** (a frozen ladder, no search at eval time:
identical inputs for all models, exactly like every other benchmark), and why **Track W** grounds the
number in the model's own likelihood. Track O pins and versions the harness and discloses budget, the
same way agentic benchmarks (SWE-bench) make a search-bearing setup reproducible.

### "Memorized famous texts just measure pretraining exposure."
Correct, and that is why canonical recall (S1) is a *bounded, separately-reported* stratum, not the
headline, and why S2–S4 use *freshly generated, non-memorizable* targets. The benchmark explicitly
distinguishes "knows it" from "can be elicited efficiently in general."

## 3. Theory anchor

ALEPH-Bench is the operational, *backwards* reading of an established idea: **language modeling is
compression**. A model that predicts well compresses well; training minimizes a description length
(the MDL principle), and a transformer can be read as approximating conditional Kolmogorov complexity
up to additive constants. The usual direction compresses *data into weights*. ALEPH-Bench runs it the
other way: with weights frozen, how short a *prompt* re-compresses a given output? The quantity

```text
L̂_θ(y, ε) = min |p|  s.t.  distortion(θ(p), y) ≤ ε
```

is a budget-bounded, model-relative estimate of `K(y|θ)` — a **lossy** description length, i.e. a point
on a **rate–distortion** curve (rate = prompt length, distortion = 1 − fidelity). Algorithmic
rate–distortion theory already studies exactly this object for individual data under Kolmogorov
complexity; ALEPH-Bench is its empirical, per-model, comparative instantiation. The recent **KoLMogorov
Test** (compression by code generation) is a precedent that "compression as a benchmark" is a
legitimate, publishable framing — we differ by compressing *via prompts into a frozen model's output
space* rather than via generated programs.

This anchor is what elevates the benchmark from "a clever leaderboard" to "an empirical measurement of a
theoretical quantity," and it is why Track W (white-box MDL) matters out of proportion to its model
coverage: it ties the behavioral leaderboard to the information-theoretic object.

## 4. Novelty claims (what we would assert in the paper)

1. A **new evaluation axis** for LLMs — elicitation efficiency / model-relative prompt description
   length — orthogonal to accuracy-style benchmarks, with a direct cost-efficiency interpretation.
2. A **curve-valued, parameter-free metric** (AURC) with interpretable duals (ECL@τ, Elicit@k) and a
   **leakage validity gate**, avoiding the arbitrary-weighted-sum trap the construct-validity
   literature flags.
3. A **three-track design** (Frozen Ladder / Open Compression / White-box MDL) that cleanly separates
   the model's decompression ability from search quality, and grounds the behavioral score in
   information theory.
4. A **transfer measurement** distinguishing universal short descriptions from model-specific
   garden-path coordinates — a phenomenon no current leaderboard reports.
5. A **contamination-resistant corpus** that exploits the benchmark's structural advantage: many
   targets can be generated fresh, so the targets themselves are non-memorizable.

## 5. Paper outline (NeurIPS Datasets & Benchmarks / arXiv)

1. **Introduction** — prompt engineering is folklore; we measure it as a curve. The cost-efficiency
   motivation. The orthogonal-axis claim.
2. **The construct** — elicitation efficiency; model-relative description length; rate–distortion
   framing; upper-bound honesty; relation to *Language Modeling Is Compression* and MDL.
3. **Benchmark design** — three tracks; AURC/ECL/Elicit and the leakage gate; the metric basket; the
   five strata and sampling; contamination strategy.
4. **The dataset** — provenance, splits (public/private/fresh), datasheet, Croissant, license.
5. **Experiments** — N frontier + open models across strata; per-stratum + CI results; Track W on
   open weights; transfer-gap analysis; the contamination audit and public/held-out gap.
6. **Analysis** — what is incompressible and why (error gallery); is elicitation efficiency correlated
   with or independent of accuracy/scale?; do short coordinates transfer?
7. **Limitations** — procedure-relative, upper bound, metric dependence, S1 memorization, Track O
   confound.
8. **Release & maintenance** — harness multi-homing, submission/governance, versioning, fresh-split
   cadence.

## 6. The headline result that would make this land

One figure carries the paper: **per-model elicitation rate–distortion curves on one axis** (prompt
length vs distortion), frontier models dominating or crossing each other, with the orthogonality scatter
beside it (accuracy on x, AURC on y) showing that elicitation efficiency is *not* predicted by
accuracy. If that scatter shows real spread — capable-but-prompt-hungry models separating from
modest-but-elicitable ones — the benchmark has found something the existing leaderboards cannot see, and
the cost-efficiency story becomes concrete: *for the behavior you want, which model needs the fewest
tokens to be told?*

---

## Sources

- [LLMLingua: Compressing Prompts for Accelerated Inference](https://arxiv.org/abs/2310.05736) · [LongLLMLingua](https://arxiv.org/abs/2310.06839) · [Prompt Compression: A Survey](https://arxiv.org/html/2410.12388v2)
- [Instruction-Following Under Compression (separating constraint compliance from semantic accuracy)](https://arxiv.org/pdf/2512.17920)
- [Language Modeling Is Compression (Delétang et al.)](https://arxiv.org/abs/2309.10668)
- [The KoLMogorov Test: Compression by Code Generation](https://arxiv.org/html/2503.13992v1)
- [Algorithmic rate–distortion for individual data](https://arxiv.org/pdf/cs/0609121)
- [Radio: Rate-Distortion Optimization for LLM Compression](https://arxiv.org/pdf/2505.03031)
- Repo prior art: [`docs/research/prior-art.md`](../research/prior-art.md) (ARCA, GCG, TextGrad, GEPA, vec2text, garden-path-like prompts)
