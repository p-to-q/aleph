# ALEPH-Bench Design Specification

This is the benchmark itself: the construct, the metric, the tracks, the data, and the contamination
strategy. It is written to satisfy the eight construct-validity recommendations in
[`01-research-synthesis.md`](01-research-synthesis.md) and to push one step past current best practice
where we can defend it.

## 1. The construct (recommendation 1: define the phenomenon)

> **Elicitation efficiency.** For a target output `y` drawn from a corpus, the number of prompt tokens
> a model `θ` requires to regenerate `y` to within a fidelity threshold, under a fixed decoding rule
> and search procedure.

Formally, per item, ALEPH-Bench estimates the **elicitation rate–distortion frontier**

```text
f_{θ,y}(L) = min over prompts p found by the fixed procedure, with |p| ≤ L,
             of   distortion( θ(p), y )
```

where `distortion = 1 − fidelity ∈ [0, 1]`. This is the same object
[`search/aleph_search.py`](../../search/aleph_search.py) already computes per target via its
`monotone()` lower-envelope staircase; the benchmark aggregates it across a corpus and across models.

The construct ultimately requires an explicit, provider-comparable definition of `|p|`. The v0.2
scorer change below does **not** settle that length/token contract; that work remains tracked in
[#35](https://github.com/p-to-q/aleph/issues/35). Until it lands, measurements made with the interim
length proxy must not be presented as tokenizer-comparable evidence across scripts or providers.

**What a high score means:** the model reconstructs intended outputs from terser prompts — it shares
more prior with the user and needs less instruction to hit a target behavior.
**What it does not mean:** that the model is more accurate, more capable, or safer. Elicitation
efficiency is *orthogonal* to accuracy (a capable model can still be prompt-hungry, and a modest model
can be highly elicitable on its in-distribution outputs). It is also an **upper bound** on the true
minimal description length, never a minimum — `K(y|θ)` is uncomputable.

**Anti-construct (recommendation 2: measure only the phenomenon).** Two confounds must be actively
excluded, because each can masquerade as elicitation:

- **Leakage / copying.** A prompt that quotes `y` has not compressed it. Handled by a hard gate (§4).
- **Verbatim memorization.** Reproducing a famous text from a 3-token name is recall of pretraining,
  not general elicitation. Handled by stratification and separate reporting (§5), and by
  non-memorizable fresh targets (§6).

## 2. The metric family (recommendations 2, 6, 8)

We deliberately **reject a single weighted-sum score**. The repo's
`fit·0.45 + stability·0.25 + compression·0.2 − leakage·0.1`
([`packages/core/src/metrics.ts`](../../packages/core/src/metrics.ts)) is fine for ordering UI cards
but is a construct-validity anti-pattern for a benchmark: the weights are arbitrary, and it fuses
axes that should be reported separately. ALEPH-Bench measures a curve and summarizes it with
parameter-free and interpretable functionals.

Given an item's measured frontier `f(L)` over `L ∈ [0, L_max]` (with `L_max = |explicit
reconstruction prompt|`, the natural right anchor):

### Primary headline — AURC (Area Under the Rate–distortion Curve)

```text
AURC_i(θ) = (1 / L_max) · ∫_0^{L_max} f_{θ,i}(L) dL          # mean distortion across the length budget
AURC(θ)   = mean_i AURC_i(θ)        with bootstrap 95% CI over items
```

Lower is better. Parameter-free (no weights, no threshold). It rewards models that buy more fidelity
per token across the *whole* budget, which is exactly the construct. Because `f` is the monotone
staircase, the integral is a trivial sum of rectangles.

### Interpretable duals — for the leaderboard table

- **ECL@τ** (Elicitation Compression Length): the smallest `L` with `f(L) ≤ 1 − τ`, e.g. τ = 0.9.
  "Tokens to reach 90% fidelity." The design target is the median over items, normalized by `|y|` to
  give a **compression factor** `CF = ECL@τ / L_max` ("you needed X% of the naïve prompt"). This is
  not yet the v0.2 aggregate contract: the current implementation reports mean ECL over successful
  items plus `coverageAtTau`. Choosing the treatment of unreachable items, aggregation statistic,
  and normalization is an unresolved part of
  [issue #35](https://github.com/p-to-q/aleph/issues/35), so ECL is not yet a defensible headline.
- **Elicit@k**: fidelity (or success rate at `f ≤ 1 − τ`) at a fixed tiny budget `k ∈ {8, 16, 32}`
  tokens. A crisp "can it do it in ≤16 tokens?" column that non-specialists can read.
- **Transfer gap** (a metric current leaderboards do not report): for the prompt achieving ECL@τ on
  the model under test, the fidelity drop when that same prompt is decoded by a fixed *reference*
  model. Small gap ⇒ a universal short description; large gap ⇒ a model-specific "garden-path"
  coordinate (the repo already studies this; see [`docs/research/garden-path-prompts.md`](../research/garden-path-prompts.md)).

### Versioned scorer contract

The unversioned M0 dataset and evidence files are the immutable **v0.1** record. v0.1 used a soft
normalized-edit score under the name `exact`. Those bytes and their historical interpretation remain
together; newer code must not regenerate v0.1 evidence or rescore it in place.

**v0.2 is a breaking protocol.** Its dataset and schemas use v0.2 namespaces. Every generated v0.2
result and platform package carries `protocolVersion: "0.2.0"` and is written to a user-selected path,
not a frozen v0.1 location. Missing, mixed, and different protocol versions are rejected before
scoring, and v0.1 and v0.2 scores are not directly comparable.

A v0.2 adapter captures the model's raw decoded output as a string before normalization. It must not
trim leading or trailing whitespace or coerce a non-string value. The item then selects one of exactly
three implemented metric classes:

- `exact` is binary equality of the raw decoded Python string code-point sequences. It performs no
  Unicode, newline, case, or whitespace normalization.
- `normalized_edit_similarity` first maps CRLF and lone CR to LF and normalizes to NFC. It then
  computes code-point Levenshtein similarity as
  `1 − distance / max(target_length, output_length)`. Case, whitespace, punctuation, and order remain
  significant.
- `unicode_char_ngram` normalizes to NFC, case-folds, normalizes to NFC again, collapses Unicode
  whitespace, then computes multiset Jaccard similarity over code-point trigrams. Punctuation, symbols,
  and ZWJ code points are retained.

Unsupported metric classes fail closed; there is no semantic, judge, execution, or legacy-edit
fallback in v0.2. The scorer and its generated platform copy share
[conformance vectors](../../bench/conformance/scorer-v0.2.json) for Unicode, newline, empty-string,
punctuation, emoji, and ZWJ cases.

Unicode behavior is part of the protocol, not an ambient runtime choice. v0.2 pins Python 3.13 and
Unicode Character Database 15.1.0 in the scoring profile and rejects a different runtime before
scoring.

The canonical public input is identified as `aleph-bench-v0.2-public-s2`, with an exact 30-item
count and a length-framed filename-and-content SHA-256 in the frozen protocol config. The runner
checks all three before any model call. Results repeat that identity and declare
`evaluationScope: "canonical"`; library-only limited diagnostics declare `"smoke"` and are not
full-release evidence. The release CLI has no `--limit` and exposes no overrides for track, split,
stratum, `tau`, `k`, reruns, bootstrap samples, dataset identity, or leakage thresholds.

### Reporting (recommendations 6, 7)

- **Uncertainty on every number**: bootstrap CIs over items; for stochastic decoding, `n` reruns per
  point with mean fidelity and variance; flag high-variance frontier points rather than hiding them.
- **Per-stratum breakdown**: never report only the aggregate; canonical-recall is always broken out.
- **Error analysis**: ship an "incompressible targets" gallery — the items each model cannot get below
  a fidelity threshold at any short length, with the hardest target tokens (the repo's
  `hardest_tokens()` already surfaces these from NLL).

## 3. The three tracks

Different rigor/realism tradeoffs deserve different divisions, flagship first. This mirrors SWE-bench
(Verified vs Pro) and HELM (scenario grid): hedge instead of forcing one regime.

**The product is a black-box leaderboard, with an accompanying white-box table.** The headline surface
is **Track F — a public, cross-vendor black-box leaderboard in the spirit of LMArena / LMSYS Chatbot
Arena**, except it ranks models on **elicitation efficiency** (AURC / ECL@τ / Elicit@k) rather than
human preference. It is built entirely from behavioral signals, because that is all closed APIs expose
([`12-platform-feasibility.md`](12-platform-feasibility.md)), and it is the only board that ranks all
vendors together. **Track W** is a *separate, explicitly `white_box`-labeled table* shown alongside it
for open-weight models only — the information-theoretic rigor anchor — and is **never merged into the
black-box ranking**. Track O sits between them for method submissions. Build and ship the black-box
board first; the white-box table accompanies it.

### Track F — Frozen Ladder (flagship, procedure-fixed and score-replayable)

The dataset ships, per item, a **frozen prompt ladder** audited by maintainers:

```text
p_0  Explicit Reconstruction   contains y verbatim        (right anchor, L_max, leaking by design)
p_1  Descriptive               paraphrastic instructions   (no quoting)
p_2  Compressed concept        names work/author/form/spec
p_3  Minimal cue               the shortest hand-found seed (left anchor)
```

Every model receives the *identical* ladder; we run each rung through θ under fixed decoding and
measure fidelity → the model's frontier points. **No search at evaluation time**, so Track F has a
small, reviewable procedure and retained outputs can be rescored offline. Hosted provider outputs are
not deterministic from a seed: aliases, deployments, and serving stacks can change even at
temperature zero. Track F is cheap, contamination-auditable, and straightforward to host on
Kaggle/lm-eval. This is the public leaderboard. `p_0` is excluded from compression claims (it leaks by
construction); it exists only to anchor `L_max` and to show the model *can* reproduce `y` at all.

*Why this is fair despite a fixed ladder:* all models compress against the same rungs, exactly as all
benchmarks use the same fixed inputs. To reduce prompt-form bias we ship **k paraphrase ladders per
item** and report the best rung per length across paraphrases.

### Track O — Open Compression (bring-your-own compressor, agentic)

The submitter supplies a **compressor** `C` (the model itself, an LLMLingua-style squeezer, an ARCA /
GCG / evolutionary search) run under a **pinned, published harness**: fixed budget `B` (candidates,
max tokens, refinement steps), fixed decoding, fixed fidelity metric, fixed seed. `C` emits a short
prompt per target; then a decoder model regenerates. Two sub-modes:

- **O-self** — θ both compresses and decompresses (the current Aleph engine — "the model compressing
  itself"). Measures *self-knowledge*: can a model find a short coordinate into its own output space?
- **O-xfer** — `C` compresses, a *different fixed* model decodes. Measures whether compressions
  **transfer** across models — a probe of universality vs idiosyncrasy.

Track O is where method innovation competes (this is the home for the repo's deferred ARCA/GCG
adapters). It is more powerful and more confounded than Track F; like SWE-bench's agent division, we
make it reproducible by pinning and versioning the harness and **requiring compute/budget disclosure**
alongside every score. Submissions report `(achieved L, fidelity)` points → same AURC/ECL functionals.

### Track W — White-box MDL (rigor anchor, open-weights only)

Using teacher-forced NLL (already computed by `Theta.score()` in
[`search/aleph_search.py`](../../search/aleph_search.py)), Track W replaces noisy embedding fidelity
with an information-theoretic quantity: the **two-part description length** of `y` under θ given a
prompt,

```text
DL_θ(y | p) = |p| · c_bits   +   NLL_θ(y | p) / ln 2        # bits: prompt code + residual to encode y
ECL_W(y)    = min_p DL_θ(y | p)                              # minimum total description length found
```

This is the MDL reading of the Aleph object and connects the leaderboard directly to *Language
Modeling Is Compression* and algorithmic rate–distortion (see
[`04-positioning-and-novelty.md`](04-positioning-and-novelty.md)). It is the most defensible number we
can report, but only for models that expose logits, so it is an anchor track rather than the flagship.

## 4. The leakage gate (hard constraint, not a soft term)

Copying is the dominant way to *fake* elicitation, so we treat it as a validity gate. v0.2 publishes
the dual-channel unit `unicode_dual_channel_v1`. Both channels map CRLF and lone CR to LF, apply
NFKC, case-fold, and apply NFKC again. The lexical channel keeps Latin-like letter/number runs
together, emits wide/full-width letters and numbers such as CJK code points individually, and keeps
punctuation and symbols. The boundary-insensitive skeleton channel compares non-space code points
directly, catching copies hidden by word splitting or punctuation insertion.

Shared normalization removes controls, format characters, surrogates, variation selectors, and emoji
skin-tone modifiers. It deliberately preserves private-use (`Co`) and unassigned (`Cn`) code points
so opaque copied payloads are not erased. The conservative skeleton is not a UTS #39 confusable
skeleton; cross-script, same-script, and multi-code-point visual confusables remain a manual
contamination-audit limitation.

A measured frontier point is **disqualified** if its prompt's overlap with `y` reaches any published
threshold, or if its raw prompt trips the frozen fail-closed Unicode policy:

```text
DISQUALIFY p if  failClosedReason(p) != null
            or   lcsRatio(p, y) >= 0.65
            or   targetTrigramRecall(p, y) >= 0.50
            or   verbatimSpanUnits(p, y) >= 16
            or   skeletonLcsRatio(p, y) >= 0.80
            or   skeletonTargetTrigramRecall(p, y) >= 0.80
            or   skeletonVerbatimSpanUnits(p, y) >= 32
```

`lcsRatio` is longest-common-subsequence length divided by the target's unit length;
`targetTrigramRecall` is the occurrence-weighted share of target unit trigrams also present in the
prompt (repeated trigrams retain their multiplicity); and
`verbatimSpanUnits` is the longest contiguous shared span in those units. The three `skeleton*`
fields apply the same computations and higher thresholds to the code-point skeleton. Receipts record
all six measurements, all six thresholds, `unit`, and `failClosedReason`; the latter is
`bidi_control`, `cjk_compatibility_ideograph`, or `null`. Targets containing either fail-closed class
are invalid benchmark items. The removed v0.1 names `trigramOverlap` and `verbatimSpanTokens` are not
v0.2 aliases. Prompt, target, and decoded-output scorer inputs are capped
at 16,384 code points; normalized text is capped at 32,768 code points; and each edit/LCS input pair
is rejected before allocation if its length product exceeds 1,000,000 cells. These three frozen
limits prevent NFKC compatibility expansion from bypassing the resource bound.

This generalizes [`packages/core/src/leakage.ts`](../../packages/core/src/leakage.ts) from a score
into a gate. Thresholds are published and versioned. The explicit-reconstruction rung `p_0` is the one
sanctioned exception (it is *defined* as leaking and is excluded from compression claims). Reporting a
gate rather than a penalty means a leaking prompt cannot quietly buy headline score — it simply does
not count, which is far easier to defend to reviewers.

> **Implementation note.** [`bench/engine/leakage_gate.py`](../../bench/engine/leakage_gate.py) keeps a
> ``leakage_score`` helper that returns a 0–1 proximity-to-leakage value per candidate. This is a
> *diagnostic field surfaced on each candidate* (so the per-item table can show "how close was this
> prompt to the gate?"). It is never folded into AURC, ECL@τ, Elicit@k, or any aggregate metric — the
> only thing that affects scoring is the hard ``disqualified`` boolean. The docstring on
> ``leakage_score`` repeats this constraint so future contributors do not accidentally promote it back
> to a penalty.

> **AURC normalizer.** The ``aurc(frontier, normalizer_tokens)`` function in
> [`bench/engine/metrics.py`](../../bench/engine/metrics.py) rescales measured-length budgets into ``[0, 1]``
> using the explicit-reconstruction prompt length (or the target text length if it is larger):
> ``max(token_count(rung0_prompt), token_count(target), 1)``. This matches the ``L_max`` anchor in §2
> above. Beyond that anchor the curve is held at its last distortion value so a model that never
> reaches the target within budget degrades smoothly rather than disappearing. The current
> ``token_count`` proxy is not the final cross-provider contract; see issue #35 above.

## 5. Dataset taxonomy (recommendations 2, 3, 4)

Coverage is a **declared stratified taxonomy**, each stratum probing a different decompression
ability. The current `search/targets.py` is exactly one stratum (canonical recall), kept but bounded.

| Stratum | Target type | Fidelity metric class | Why it is in the benchmark | Contamination posture |
|---|---|---|---|---|
| **S1 Canonical recall** | Famous texts (Borges, Gettysburg…) | `exact` / Unicode lexical (planned) | The "shared cultural prior" extreme; the demo's strength | High by nature → **bounded share, reported separately** |
| **S2 Compositional** | Rule-generated outputs (primes table, constrained haiku, derived sequences) | v0.2: `normalized_edit_similarity` | Reconstruction from *generative rules*, not recall | **Freshly generated → non-memorizable** |
| **S3 Functional / behavioral** | A *task/spec*, scored by held-out test cases or a rubric ("respond to inputs like these, this way") | rubric / test-suite (planned) | The enterprise case: recover the *task* from a terse prompt | Fresh specs; private split |
| **S4 Structured** | Code, JSON, SQL, regex, tables | execution / schema-validate (planned) | Objective, checkable fidelity; resists gaming | Fresh → non-memorizable |
| **S5 Multilingual** | EN + ZH (extensible) targets across S1–S4 | declared class; language-aware coverage | Tests language-independence of elicitation; leverages repo's existing CJK + cross-lingual work | Mixed |

Sampling (recommendation 3): each stratum drawn by a **documented protocol** with a target item count
chosen by a power analysis for tight CIs (recommendation 6), not by convenience. Reused sources
(recommendation 4) are documented with provenance and license in a source ledger, mirroring the repo's
existing [`docs/source-ledger.md`](../source-ledger.md) habit.

**The fidelity-metric basket (recommendation 2/8).** A single embedding cosine (the repo's current
MiniLM metric) is too fragile and gameable for a benchmark. Each item *declares* its metric class.
v0.2 implements only the three versioned classes in §2: binary `exact`,
`normalized_edit_similarity`, and `unicode_char_ngram`. The S2 release uses
`normalized_edit_similarity`.

Semantic metrics with multiple pinned embedders, rubric/LLM-judge metrics with agreement reporting,
and execution/schema metrics remain possible future protocol additions for S1/S3/S4. They are design
directions, not aliases accepted by the v0.2 scorer. Adding one requires a new versioned contract and
conformance evidence.

Mixing metric classes *within* one aggregate is itself a confound, so the headline AURC is reported
**per metric class** and only then combined with documented normalization.

## 6. Contamination strategy (recommendation 5)

All four industry layers, ordered by strength, adapted to our structural advantage that many targets
can be generated fresh:

1. **Private held-out split** — a never-published set per stratum, run only at submission time. The
   single most persuasive defense (SWE-bench Pro). The public/private score gap is reported as the
   contamination indicator.
2. **Time-gated fresh split** — for S2/S3/S4, regenerate items after a dated cutoff and score models
   only on items postdating their training cutoff (LiveBench / LiveCodeBench). Targets are
   non-memorizable because they did not exist at training time.
3. **Canary GUID** in every public file + a "can the model emit the canary?" probe (BIG-bench).
   Detects leakage; does not prevent it.
4. **Leakage gate** (§4) — prevents the *prompt* from smuggling the target.
5. **Published contamination audit** — we run the SWE-bench-style self-audit (does the model reproduce
   our gold prompts / targets verbatim from a neutral query?) and publish it. Auditing your own
   benchmark is the strongest trust signal available.

## 7. Statistics and honesty surface (recommendations 6, 7, 8)

- **Bootstrap CIs** over items on every reported number; "preliminary" labels for models with few
  items or high variance (Chatbot Arena practice).
- **Decoding is part of the spec**: temperature and max tokens are pinned and reported. The protocol
  seed is a bootstrap/cache logical coordinate; the portable hosted adapter does not send it to the
  provider. Hosted prompts run five times even at temperature zero to measure provider-side
  nondeterminism, and stochastic points carry variance.
- **Capture precedes normalization**: every rerun records the raw decoded string before a declared
  metric transforms it; transport, adapters, and caches do not trim or stringify it.
- **Unicode runtime is pinned**: v0.2 records and enforces Python 3.13 and Unicode Character Database
  15.1.0.
- **Sensitivity analysis**: headline robustness to embedder choice and decoding temperature is
  reported, not assumed.
- **Limitations section** travels with every results release, and new public claims route through
  [`docs/claim-ledger.md`](../claim-ledger.md) before publication.

## 8. What we are deliberately *not* doing (scope discipline)

- Not claiming the global-minimal prompt or strict Kolmogorov complexity (upper bound only).
- Not collapsing the benchmark to one number with hidden weights.
- Not treating S1 canonical recall as the headline — it is the most contaminated stratum.
- Not shipping a bespoke runner when an lm-eval task + Kaggle task reach more of the community.
- Not letting fixture/simulated panels enter a leaderboard number — only labeled measured evidence.
- Not claiming v0.2 solves length/token comparability; that is the separate acceptance gate in
  [issue #35](https://github.com/p-to-q/aleph/issues/35).
- Not claiming the current successful-item mean ECL is the design's normalized-median statistic;
  unreachable-item and aggregation semantics remain open in issue #35.
- Not claiming the v0.2 scorer-conformance package is a complete Kaggle evaluator. It is integration
  staging without submission I/O, model execution, AURC/ECL aggregation, or leaderboard hosting.

The implementation that realizes this spec, and how much of it to build first, is in
[`03-architecture-and-launch.md`](03-architecture-and-launch.md).
