# M0 Engineering Spec — DRAFT / SEED (not law)

> **Status: provisional draft (a "seed", not a finished spec).** This is a first proposed path —
> the kind of thing you would hand to a strong coding model (Codex) to discuss, push back on, and
> re-think before implementing. It deliberately preserves the *original Aleph thinking* and marks its
> own **uncertainties** with `⚠ OPEN` so contributors treat it as a starting point to optimize, not a
> frozen contract. If a better structure emerges while building, take it — and update this file.
>
> Reading order before touching code: [`02-design-spec.md`](02-design-spec.md) (what to measure),
> [`05-metrics-audit.md`](05-metrics-audit.md) (which metrics survive black-box),
> [`09-metric-validity-and-rigor.md`](09-metric-validity-and-rigor.md) (how to keep it valid),
> [`06-search-rigor-and-production.md`](06-search-rigor-and-production.md) (local-minima + production),
> [`12-platform-feasibility.md`](12-platform-feasibility.md) (what is actually measurable on Kaggle /
> closed APIs — read this before assuming any logprob is available).
>
> **Note to the implementer (this doc is written to be read by you, human or Codex):** the boundary in
> §1.5 is the one architectural decision you must not blur. Everything else in this file is a seed to
> optimize; §1.5 and the three invariants at the end are the load-bearing constraints.
>
> **Current implementation boundary.** This seed predates the versioned scorer. Operational commands
> live in [`bench/README.md`](../../bench/README.md). In v0.2, Track F, public/S2, thresholds, reruns,
> bootstrap samples, and canonical dataset identity are frozen; the CLI intentionally has no
> `--track`, `--split`, or diagnostic `--limit` override. The unversioned v0.1 evidence is immutable
> and its `audit`, `bundle`, and `package` commands are check-only.

## 0. The original thought, preserved

The seed idea, in the repo's own words ([`web/public/aleph-frontier.json`](../../web/public/aleph-frontier.json)):
*every output `y` has a shortest-prompt length at distortion ε; push ε→0 and it approaches `K(y|θ)`;
between the identity prompt and that limit is a real rate–distortion curve.* M0's only job is to turn
that, for the **first time, across more than one model**, into an offline-score-replayable number with a confidence
interval. Nothing in M0 should overreach that.

## 1. Goal and non-goals of M0

**Goal.** The smallest artifact that proves the metric is real: evaluate the **Frozen Ladder (Track F)**
on **one stratum** across **3 models** and emit a schema-valid `BenchResult` with **AURC + ECL@τ +
Elicit@k**, a **leakage gate**, and **bootstrap CIs** — deterministic for mock fixtures and
recomputable from retained hosted outputs.

**Non-goals (defer past M0).** Full 5-stratum dataset; private/fresh splits; Track O search harness;
Track W white-box (unless an MLX model is trivially available); HF/Kaggle hosting; the leaderboard UI.
M0 answers one question only: *does the metric rank models sensibly and survive the leakage gate?*

## 1.5 Product framing — the boundary to build to (do not blur)

ALEPH-Bench has **two surfaces, and they are never merged**:

- **The primary product is a black-box, cross-vendor leaderboard (Track F).** It is in the spirit of
  LMArena / LMSYS Chatbot Arena — a public leaderboard ranking closed frontier models (OpenAI,
  Anthropic/Claude, Google/Gemini, DeepSeek, Qwen, Grok) — except the axis is **elicitation efficiency**
  (AURC / ECL@τ / Elicit@k) instead of human preference. This is THE headline result, THE thing that
  ships to Kaggle, and the only board that ranks all vendors together. It is built **entirely from
  behavioral metrics** (text in, text out), because that is all the closed APIs expose
  ([`12-platform-feasibility.md`](12-platform-feasibility.md)).
- **Accompanying it is a separate, explicitly White-box-labeled table (Track W).** It reports the
  information-theoretic bit-level metrics (teacher-forced NLL, bits-per-byte, two-part description
  length) for **open-weight models only** (Qwen / DeepSeek / Llama), run where logits are readable
  (a Kaggle GPU notebook or local MLX). It is a *rigor anchor shown alongside* the leaderboard, with a
  visible `white_box` label — **never folded into the black-box ranking** (different evidence, different
  models, incommensurable across vendors).

For M0, you build **only the black-box leaderboard path (Track F)**. Track W may be a labeled stub but
is not on the M0 critical path. The data contract (`BenchResult.track` ∈ {F, O, W} +
`observationMode`) must already be able to *carry* a white-box row so the two surfaces coexist later
without a schema migration — that is the only Track-W obligation in M0.

## 2. Scope of the M0 dataset (seed)

- **Stratum: S2 compositional** (rule-generated, non-memorizable) — chosen so the proof is not
  contaminated by S1 memorization. `⚠ OPEN`: S2 vs a tiny S1+S2 mix to show the *contrast* (memorized
  vs general) might be more convincing for a first result. Builder's call.
- **~30 items**, each with a **frozen ladder** of 4 rungs `p_0..p_3` (explicit → descriptive →
  concept → minimal cue) and **k=2 paraphrases per rung**. `⚠ OPEN`: 30 may be too few for tight CIs;
  treat as a floor, scale if cheap.
- Each item declares its **metric class** (S2 → mostly `exact`/`execution`; some `lexical`).
- Each item carries a **canary GUID** and **provenance**.

`⚠ OPEN`: ladders for M0 may be hand-authored to move fast; the multi-proposer construction pipeline
([`06`](06-search-rigor-and-production.md) §C) is an M1 concern. Document that M0 ladders are
hand-seeded so no one mistakes them for optimized frontiers.

## 3. Data shapes (extend the existing contract — do not invent a parallel one)

Reuse `CandidatePoint` / `TargetOutput` from [`packages/core/src/types.ts`](../../packages/core/src/types.ts).
Add (TypeScript types in `packages/core`, mirrored as JSON Schema in `schemas/`):

```ts
type Stratum = "S1" | "S2" | "S3" | "S4" | "S5";
type MetricClass = "exact" | "lexical" | "semantic" | "rubric" | "execution";

type BenchItem = {
  id: string; stratum: Stratum; language: "en" | "zh";
  target: TargetOutput;
  metricClass: MetricClass;
  ladder: { rung: 0|1|2|3; paraphrases: string[] }[];   // frozen prompts; rung 0 = explicit (leaky anchor)
  canary: string; provenance: string; license: string;
};

type FrontierPoint = { length: number; distortion: number; fidelity: number; fidelityVar?: number; disqualified?: boolean };

type BenchResult = {
  model: string; decoding: { temperature: number; maxTokens: number; seed: number };
  harnessVersion: string; track: "F"; observationMode: "black_box";
  perItem: { itemId: string; frontier: FrontierPoint[]; eclAtTau?: number; elicitAtK: Record<string, number>; transferGap?: number }[];
  aggregate: {
    aurc: number; aurcCI: [number, number];
    eclAtTauMedian: number; cfMedian: number; elicitAtK: Record<string, number>;
    byStratum: Record<Stratum, { aurc: number; aurcCI: [number, number] }>;
  };
};
```

`⚠ OPEN`: field names are a proposal; align them with whatever the engine already emits to minimize
glue. The *only* hard rule (from [`docs/architecture.md`](../architecture.md)): one shape, no hidden
parallel model.

## 4. The metric layer (pseudocode — the part to get exactly right)

```python
# distortion in [0,1]; 0 = exact, 1 = empty-prompt baseline for this item (documented anchors).
def distortion(output, target, metric_class):  # see 09 §2 for accuracy/meta-eval requirements
    if metric_class == "exact":      return 0.0 if normalize(output) == normalize(target) else 1.0
    if metric_class == "execution":  return 1.0 - tests_passed_ratio(output, target.test_suite)
    if metric_class == "lexical":    return 1.0 - rougeL(output, target)
    if metric_class == "semantic":   return 1.0 - cosine(embed(output), embed(target))   # embedder pinned+versioned
    ...

LEAK = lambda p, y: lcs_ratio(p,y) > D_LCS or trigram_overlap(p,y) > D_TRI or has_span(p,y,M)

def item_frontier(model, item):
    pts = []
    for rung in item.ladder:                       # NO SEARCH at eval time — this is Track F
        for p in rung.paraphrases:
            if rung.rung != 0 and LEAK(p, item.target.text):   # rung 0 (explicit) is the sanctioned leaky anchor
                continue                                        # disqualified: copying ≠ compressing
            outs = [model.generate(p, seed=s) for s in SEEDS]   # n reruns for stability/variance
            d = mean(distortion(o, item.target.text, item.metricClass) for o in outs)
            pts.append(FrontierPoint(length=ntokens(p), distortion=d,
                                     fidelity=1-d, fidelityVar=var(...)))
    return monotone_lower_envelope(pts)            # reuse search/aleph_search.py::monotone — honest upper bound

def aurc(frontier, L_max):                         # area under rate–distortion curve, normalized
    return integral_stepwise(frontier, 0, L_max) / L_max     # lower is better; parameter-free

def ecl_at_tau(frontier, tau):                     # tokens to reach fidelity ≥ tau
    return min((pt.length for pt in frontier if pt.fidelity >= tau), default=None)

# aggregate over items: mean AURC (a MEAN SCORE — IIA-stable, not win-rate) + bootstrap 95% CI
```

`⚠ OPEN`: thresholds `D_LCS, D_TRI, M`, `SEEDS` count, `tau` (0.9? exact?), and `c_bits` (Track W) are
**knobs to calibrate**, not constants to hardcode. Put them in a versioned config and record the chosen
values in `BenchResult.harnessVersion`. `⚠ OPEN`: for `exact`/`execution`, `fidelityVar` is ~0 and
multiple seeds are wasteful — gate reruns on metric class.

## 5. Adapters (reuse what exists)

- `hosted_black_box` — the existing Next.js `/api/search` path / an OpenAI-compatible client
  ([`README.md`](../../README.md) Hosted API). The 3 M0 models go through this.
- `mock` — deterministic adapter for tests (no network).
- `⚠ OPEN`: pick 3 models with *different* expected behavior (e.g., a frontier model, a mid, a small)
  so a sensible metric should *separate* them — that separation is the M0 success signal.

## 6. Acceptance gate (how we know M0 worked)

M0 is done when **all** hold (mirrors the repo's decision-gate style):

```text
[ ] exact target == output  ⇒ distortion 0.0, fidelity 1.0      (no drift; the metric plan's first rule)
[ ] a prompt that quotes the target is DISQUALIFIED, not scored  (leakage gate works)
[ ] each of 3 models yields a schema-valid BenchResult under the fixed procedure, with retained raw
    outputs that reproduce its published scores offline
[ ] AURC ranks the 3 models, and the ranking is STABLE across 2 reruns (different seeds) within CI
[ ] removing one model does NOT change the relative order of the other two   (IIA sanity — 09 §3)
[ ] per-stratum + bootstrap CI are reported; no single fused weighted number anywhere
[ ] a one-screen result note explains what the number means and its limits (upper bound, procedure-relative)
```

`⚠ OPEN`: the IIA check is trivial for one stratum/mean-score (it holds by construction) — keep it as a
regression guard for when Track O / win-rate-like views are added later.

## 7. Suggested file targets (align with [`03-architecture-and-launch.md`](03-architecture-and-launch.md))

```text
bench/engine/frozen_ladder.py     # item_frontier, monotone reuse
bench/engine/metrics.py           # distortion basket, aurc, ecl_at_tau, elicit_at_k, bootstrap CI
bench/engine/leakage_gate.py      # LCS / trigram / span
bench/data/public/s2/*.json       # ~30 BenchItem seeds (+ canary)
bench/run.py                      # aleph-bench run --model X --seed 0 --out RESULT
schemas/aleph-bench-item.schema.json, schemas/aleph-bench-result.schema.json
packages/core/src/bench.ts        # shared types (so web can later render a BenchResult)
bench/tests/                      # exact-match, leakage-gate, AURC-monotonicity, schema-validity, IIA
```

## 8. What to hand back for the M1 decision

After M0, return: the 3-model AURC table with CIs, the per-item frontiers, the leakage-gate hit rate,
and a one-paragraph read on **did the metric separate the models sensibly?** That evidence — not a
guess — decides M1 scope (dataset scale, strata, splits). This is the repo's "smallest reviewable change
that proves the object" discipline applied to a benchmark.

---

### A note to whoever implements this (human or Codex)

This spec is a **seed**. The original idea is sound and is preserved in §0; the *engineering* around it
is a proposal with marked uncertainties. You are explicitly invited to restructure §3–§7 if you find a
cleaner path, **as long as** you keep three invariants that are not negotiable because they are what
makes the benchmark valid rather than tasteful:

1. **One data shape, no hidden parallel model** (the repo's architecture rule).
2. **Leakage is a gate, fidelity-accuracy is meta-evaluated, the headline is a mean score** (the rigor
   spine, [`09`](09-metric-validity-and-rigor.md)).
3. **Every number is an honest upper bound, labeled by evidence mode** (the repo's claim discipline).

Everything else is yours to optimize.
