# Metric Audit: From Workbench Instruments to Benchmark Metrics

The Aleph workbench already ships a rich instrument panel. A benchmark cannot inherit all of it
uncritically: some instruments are **white-box only** (they need logits, so they cannot run against a
vendor Custom API), and some are **cosmetic/simulated** (they were UI behavior, never measurements).
This document audits every original instrument, classifies it by the evidence it actually requires,
and decides — instrument by instrument — what the benchmark **keeps, adapts, drops, or adds**. It is
the concrete answer to: *which of our original metrics survive contact with a black-box,
multi-vendor leaderboard?*

The governing fact, stated once: **ALEPH-Bench's flagship subject is the vendor Custom API
(black-box).** Most frontier models (OpenAI, Anthropic, Google, DeepSeek, Qwen-hosted, Grok) expose
*behavior*, not logits. So the benchmark's core metrics must be **behavioral** — computable from
prompts in and text out. White-box quantities become a separate, clearly-labeled rigor track
(Track W) for open weights only. This is not a compromise; it is the honest evidence split the repo
already encodes in `ObservationMode` (`fixture | mock | black_box | white_box | simulated`).

## 1. The original instrument inventory (exact names)

From [`packages/core/src/types.ts`](../../packages/core/src/types.ts) and the live fixtures:

**Per-candidate metrics** (`CandidatePoint`): `tokens`, `fit`, `stability`, `compression`,
`leakage`, `nll`, `frontierRank`.

**Observation panels** (`ObservationSet`, carrying an `ObservationMode`): `tokenLoss`, `waveform`,
`attribution`, `lossCurve`, `exposureVectors`, `evalSuite`.

**Glossary concepts** ([`docs/glossary.md`](../glossary.md)) worth promoting: *leakage score*,
*token loss*, *inherent signal* ("the part of the output unfolded from model knowledge rather than
copied from the prompt"), *model-relative description length*.

[`docs/surfaces.md`](../surfaces.md) is blunt about three of these today: "Token loss / waveform /
attribution panels — **simulated fixture** … Useful UI behavior; not real model internals." That
honesty is exactly the line a benchmark must hold.

## 2. The classification axis

Every instrument is scored on two questions:

- **Evidence requirement** — can it be measured from a black-box API (behavioral), or does it need
  logits/internals (white-box), or is it cosmetic (a visualization with no measured ground truth)?
- **Construct value** — does it measure *elicitation efficiency* (the benchmark's phenomenon), or
  something adjacent, or nothing comparable across models?

```text
Evidence:   black-box behavioral   |   white-box internal   |   cosmetic / simulated
Value:      core construct          |   rigor anchor          |   product-only (not a metric)
```

## 3. The verdict table (keep / adapt / drop / add)

| Original instrument | What it is | Evidence required | Benchmark verdict | Becomes |
|---|---|---|---|---|
| `fit` | similarity of output to target | **black-box** | **KEEP → core** | Fidelity; `distortion = 1 − fit`. Split into the metric-class basket (exact / lexical / semantic / rubric / execution) per item, not one cosine. |
| `tokens` / `compression` | prompt length / ratio vs explicit | **black-box** | **KEEP → core** | The rate axis. Drives `ECL@τ`, `Elicit@k`, and AURC's x-axis. Report raw token length, not just a ratio. |
| `stability` | rerun variance of fit | **black-box** | **KEEP → adapt** | Reported as *uncertainty on the fidelity*, not a fused score term. Becomes the per-point CI; high variance flags an unreliable frontier point. |
| `leakage` | prompt-vs-target overlap | **black-box** | **KEEP → promote** | From a `−0.1·` penalty to a **hard disqualification gate** (LCS / trigram / verbatim-span). Copying is excluded, not discounted. |
| `evalSuite` | behavioral pass/fail checks | **black-box** | **KEEP → core for S3/S4** | The functional/structured fidelity metric: held-out test cases, schema/parse, execution. This is our SWE-bench-style objective signal. |
| `frontierRank` | Pareto rank among candidates | **black-box** (derived) | **KEEP → internal** | Used to build the monotone frontier; not a reported leaderboard number. |
| `nll` | teacher-forced target NLL | **white-box** | **MOVE → Track W** | The information-theoretic core of the MDL track; the cleanest number we can report, open-weights only. |
| `tokenLoss` | per-token target loss + alternatives | **white-box** (today simulated) | **MOVE → Track W** | Real per-token NLL from `Theta.score()`; powers the *incompressible-tokens* error analysis. Never reported for black-box models. |
| `lossCurve` | loss over steps | **ambiguous** | **SPLIT** | Two distinct objects were conflated: (a) **white-box NLL curve** → Track W; (b) **search-convergence curve** (best-found distortion vs budget) → a Track-O *diagnostic*, not a score. See [`06-search-rigor-and-production.md`](06-search-rigor-and-production.md). |
| `attribution` | prompt-token importance / Δloss-if-removed | **white-box** (today simulated) | **DEFER → Track W research** | Deletion ablation needs internals or many behavioral probes; optional analysis, never a headline metric. |
| `waveform` | output "waveform" visualization | **cosmetic / simulated** | **DROP from benchmark** | No measured ground truth, not comparable across models. Stays in the product UI; never a leaderboard number. |
| `exposureVectors` | Aquin-style "exposure" panel | **cosmetic / simulated** | **DROP from benchmark** | Inspired UI language; no construct validity as a metric. Product-only. |

### New metrics the benchmark must add (not in the original surface)

| New metric | Why it did not exist before | Evidence |
|---|---|---|
| **AURC** (area under the elicitation rate–distortion curve) | The workbench showed *one* run's frontier; a benchmark needs a single comparable scalar per model. | black-box |
| **ECL@τ** / **CF** (tokens / % of explicit to reach fidelity τ) | The product never asked "how few tokens to reach a fixed fidelity across a corpus." | black-box |
| **Elicit@k** (fidelity at a k-token budget) | A crisp procurement number ("can it do it in ≤16 tokens?"). | black-box |
| **Transfer gap** (fidelity drop when the same short prompt is decoded by a reference model) | The repo *studied* model-specific garden-path cues but never measured their universality. | black-box |
| **Contamination gap** (public vs held-out fidelity; canary-emission probe) | No cross-model benchmark existed, so no contamination surface existed. | black-box |
| **Search convergence** (did Track-O search saturate?) | The workbench searched once; a benchmark must certify the number is not a local-minimum artifact. | black-box diagnostic |
| **Cost / latency normalization** (ECL × $/token, × latency) | Product framing; the benchmark targets production economics. | black-box |

## 4. The final metric set, split by track

This is the contract a leaderboard renders. Every number is tagged with the evidence mode that
produced it, exactly as `ObservationMode` already requires — a black-box leaderboard row never
borrows a white-box claim.

```text
Track F — Frozen Ladder  (black_box; flagship, all vendors)
  headline:   AURC ↓        (+ bootstrap 95% CI)
  table:      ECL@0.9, CF (median %), Elicit@{8,16,32}, transfer gap
  gates:      leakage gate (disqualify), contamination gap (public vs heldout)
  per-stratum: S1..S5 broken out; S1 (canonical recall) never folded into the headline

Track O — Open Compression  (black_box; BYO compressor, pinned harness)
  same functionals on achieved (|p|, fidelity) points
  required:   budget disclosure + search-convergence diagnostic

Track W — White-box MDL  (white_box; open weights only)
  headline:   ECL_W = min_p [ |p|·c_bits + NLL_θ(y|p)/ln2 ]   (two-part description length, bits)
  analysis:   per-token NLL → incompressible-tokens gallery
```

## 5. The evidence-mode contract (honoring the repo's discipline)

The benchmark inherits, unchanged, the rule from [`docs/claim-ledger.md`](../claim-ledger.md) and
`ObservationMode`:

- A **black-box** leaderboard number is computed only from prompts and generated text. It may *never*
  display token-loss, NLL, or attribution as if measured — those require `white_box`.
- A **white-box** number (Track W) is labeled as such and is only available for models that expose
  logits (local MLX today; open-weights generally).
- **Fixture / simulated** panels (`waveform`, `exposureVectors`, today's `tokenLoss`/`attribution`)
  are **not benchmark metrics** and cannot enter a leaderboard. They remain product instruments.
- Every reported number ships with its **metric-class** and **evidence-mode** tag, so a reader always
  knows whether a score came from exact match, an embedder, a judge, execution, or model internals.

## 6. Elevating "inherent signal" vs leakage — the construct's heart

The glossary's *inherent signal* — "the part of the output unfolded from model knowledge rather than
copied from the prompt" — is not a side concept; it **is** what the benchmark measures. Elicitation
efficiency is high exactly when the *model* supplies the output and the *prompt* only supplies a short
coordinate. This gives a clean two-sided framing the leaderboard can state plainly:

```text
high inherent signal  +  gated leakage   →  real elicitation (the model knew it; you just pointed)
low  inherent signal  (prompt carries y) →  leakage, disqualified (you dictated it; no compression)
```

The leakage gate (§02-design-spec §4) and the inherent-signal framing are the same coin: the gate
*enforces* what inherent signal *describes*. Reporting them together is what stops the benchmark from
rewarding a model for being dictated to.

## 7. One-paragraph summary for the skeptic

We kept exactly the instruments that survive a black-box API — fidelity, length, rerun-variance,
leakage, behavioral evals — and turned them into a curve (AURC) with a hard anti-copying gate. We
moved the logit-dependent instruments (token loss, NLL, attribution) into a separate, labeled
white-box track for open weights, where they are the most rigorous number we can offer. We dropped
the cosmetic panels (waveform, exposure) from the benchmark entirely; they were never measurements.
And we added the things a *cross-model* benchmark needs that a single-run workbench never did: a
comparable scalar, contamination and transfer gaps, search-convergence certification, and a
production cost mapping. Nothing white-box is ever claimed of a black-box model; nothing simulated
ever enters a score.
