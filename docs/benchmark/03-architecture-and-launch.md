# Architecture and Launch Plan

This is the technical work: what to build, how it extends the existing `AlephRun` contract, where it
lives, how it multi-homes onto the platforms the community already uses, and a phased milestone plan
with acceptance gates in the repo's existing decision-gate style. It also states, bluntly, how much
work each phase is and where the risks are.

## 1. Reuse, don't rebuild — what already exists

ALEPH-Bench is mostly an *aggregation and packaging* layer over machinery the repo already has:

| Need | Already in repo | Gap to close |
|---|---|---|
| Per-target rate–distortion frontier | `search/aleph_search.py` (`monotone()` staircase) | Generalize from one fixed θ to any adapter; eval a frozen ladder without searching |
| Teacher-forced NLL (Track W) | `Theta.score()` in `search/aleph_search.py` | Expose as a benchmark metric; bits accounting |
| Hardest-token error analysis | `hardest_tokens()` | Surface into the "incompressible" gallery |
| Model adapters | `web/app/api/search` (hosted black-box), `search/server.py` (local MLX white-box), `apps/api` | Add a frozen-ladder eval path and a standardized compressor harness |
| Run contract + schema | `packages/core/src/types.ts`, `schemas/aleph-run.schema.json` | Extend to `BenchItem` / `BenchResult` |
| Fidelity + leakage helpers | `packages/core/src/metrics.ts`, `leakage.ts`, `frontier.ts` | Promote leakage to a gate; add exact/lexical/judge classes; AURC/ECL functionals |
| Honesty discipline | `docs/claim-ledger.md`, `docs/verification.md`, evidence-mode labels | Apply unchanged to leaderboard numbers |

The point: this is weeks of careful engineering on a strong base, not a from-scratch build. The
intellectual core (the rate–distortion frontier of a frozen model) is done and is already articulated
in the live pitch script.

## 2. Data contract: from `AlephRun` to `BenchItem` / `BenchResult`

Keep the architecture rule from [`docs/architecture.md`](../architecture.md): one durable shape, no
parallel hidden models. Add two shapes that compose with `AlephRun`.

```text
BenchItem                      # a frozen unit of the benchmark dataset
├─ id, stratum (S1..S5), language
├─ target: TargetOutput        # reuse existing type
├─ metricClass: exact | lexical | semantic | rubric | execution
├─ ladder: CandidatePoint[]    # Track F: frozen rungs p_0..p_k (reuse CandidatePoint)
├─ judgeSpec? / testSuite?     # S3/S4 scoring assets
├─ split: public | heldout | fresh
├─ canary: "<GUID>"            # contamination probe
└─ provenance, license         # datasheet fields

BenchResult                    # one model's measured outcome on the benchmark
├─ model, decoding, harnessVersion, seed, track: F | O | W, observationMode
├─ perItem: { itemId, frontier: {L, distortion, fidelityVariance}[], ecl_at_tau, elicit_at_k, transferGap?, disqualified? }[]
├─ aggregate: { aurc, aurc_ci, ecl_at_tau_median, cf_median, elicit_at_k, byStratum: {...} }
└─ contamination: { canaryEmitted: bool, publicVsHeldoutGap: number, audit: ... }
```

`BenchResult` is to the leaderboard what `AlephRun` is to the workbench. It is JSON, versioned, and
schema-checked, so a result can leave the harness, land in a dataset, and render on a Space without a
parallel model — the file-first thesis applied to the benchmark.

## 3. Repository layout

Match the existing top-level package style (`packages/*`, `search/`, `docs/*`):

```text
bench/
├─ data/
│  ├─ public/            BenchItem JSON by stratum (+ CANARY in every file)
│  ├─ fresh/             time-gated regenerated items (rolling)
│  └─ heldout/           NOT in git — private split, stored out of band
├─ engine/
│  ├─ frozen_ladder.py   Track F: run a BenchItem ladder through any adapter → frontier
│  ├─ compressor.py      Track O: pinned BYO-compressor harness (budget, refine, seed)
│  ├─ whitebox_mdl.py    Track W: two-part description length from NLL
│  ├─ metrics.py         AURC, ECL@τ, Elicit@k, transfer gap; exact/lexical/semantic/judge/exec
│  └─ leakage_gate.py    LCS / trigram / verbatim-span disqualification
├─ adapters/             reuse: hosted_black_box, local_mlx_white_box, openai_compatible, mock
├─ tasks/
│  ├─ kaggle/            @kbench.task wrappers → Kaggle Community Benchmarks
│  └─ lm_eval/           lm-evaluation-harness task YAML + utils
├─ leaderboard/          Gradio HF Space reading the results dataset
├─ croissant.json        machine-readable dataset metadata
├─ DATASHEET.md          datasheet for datasets
└─ run.py                CLI: aleph-bench run --track F --model X --split public

schemas/aleph-bench-item.schema.json
schemas/aleph-bench-result.schema.json
```

`packages/core` gains the shared TypeScript types so the web workbench can *render* a `BenchResult`
(a leaderboard view is a natural addition to the existing console) without owning scoring truth.

## 4. Multi-home the harness (the adoption strategy)

Do not ship a bespoke runner and hope. Land ALEPH-Bench inside the tools people already run:

- **Standalone**: `pip install aleph-bench`; `aleph-bench run --track F --model gpt-… --split public`.
  Pins versions; emits a schema-valid `BenchResult`; reproducible from a seed.
- **Kaggle Community Benchmarks**: wrap each `BenchItem` as an `@kbench.task` that calls
  `llm.prompt(rung)` and scores with our assertions, group into a Benchmark → native Kaggle
  leaderboard with **free frontier-model access**. Apply for the **Benchmarks Resource Grant** so we
  do not pay per-model API costs (this is the practical unlock for a model-comparison benchmark).
- **lm-evaluation-harness**: a task that runs Track F. Anyone already running lm-eval adds one config
  line; this is also the on-ramp to HF Open LLM Leaderboard surfaces. Highest adoption leverage.
- **Hugging Face**: dataset (public + fresh splits) with a **Croissant** metadata file and a
  `DATASHEET.md`; a Gradio **Space** as the canonical leaderboard reading a results dataset.

**Two leaderboard surfaces, never merged.** The Space renders (1) the **primary black-box, cross-vendor
board** (Track F) — LMArena/LMSYS in spirit, but on the elicitation-efficiency axis — ranking OpenAI /
Anthropic / Google / DeepSeek / Qwen / Grok behaviorally; and (2) an **accompanying, explicitly
`white_box`-labeled table** (Track W) for open-weight models, reporting the bit-level metrics that
closed APIs cannot expose ([`12-platform-feasibility.md`](12-platform-feasibility.md)). The black-box
board is the product and the headline; the white-box table is a rigor anchor shown beside it. Both read
the same `BenchResult` shape (distinguished by `track` and `observationMode`), so they coexist with no
schema fork.

One engine, four front doors. Each front door is where a different community already lives.

## 5. Milestone plan (each gate in the repo's decision-gate idiom)

Phased so that every milestone is independently demonstrable and the project never depends on the next
phase to be honest about the current one.

### M0 — Spec freeze + sanity (smallest credible thing)
- Freeze §02 metric definitions; implement `frozen_ladder.py` + `metrics.py` (AURC/ECL/Elicit) +
  `leakage_gate.py`.
- One stratum (S2 compositional, ~30 items, fresh/non-memorizable) with hand-authored ladders.
- Evaluate 3 models via existing adapters.
- **Gate:** the metric ranks models sensibly and reproducibly from a seed; exact-match ⇒ distortion 0;
  leaking prompts are gated out. A `BenchResult` validates against schema.

### M1 — Benchmark v0 (publishable artifact)
- Full taxonomy v1 (S1–S5), each stratum power-sized for tight CIs; public + private held-out + a
  first fresh split; canary in every file; metric basket with ≥2 embedders; bootstrap CIs.
- Track W on ≥2 open-weight models; first contamination audit.
- **Gate:** a stranger reproduces a leaderboard row from the package; per-stratum + CI reporting;
  public/held-out gap reported; datasheet drafted.

### M2 — Multi-home harness (adoption)
- Kaggle task set + Grant application; lm-eval task; HF dataset (Croissant) + leaderboard Space.
- **Gate:** the same `BenchResult` is producible from the standalone CLI, a Kaggle notebook, and
  lm-eval, and renders on the Space.

### M3 — Community + governance (becomes "the community's")
- BIG-bench-style PR submission flow for new `BenchItem`s with a review checklist; CONTRIBUTING for
  the benchmark; model-submission flow with automated held-out eval; versioning policy + rolling fresh
  split cadence.
- **Gate:** ≥1 external item PR merged and ≥1 external model submission scored end-to-end without a
  maintainer hand-running it.

### M4 — Paper + formal release (authority)
- NeurIPS Datasets & Benchmarks / arXiv writeup (outline in
  [`04-positioning-and-novelty.md`](04-positioning-and-novelty.md)); Croissant + datasheet +
  reproducibility checklist + hosting/licensing/maintenance plan; DOI'd dataset release.
- **Gate:** an external reader can run, cite, and extend the benchmark from the release alone.

## 6. Governance and maintenance (recommendation: maintenance plan)

- **Versioning**: `aleph-bench@MAJOR.MINOR`; any change to metric, ladder, metric-class, gate
  threshold, or split is a version bump recorded in a benchmark changelog; old versions remain
  runnable so historical leaderboard rows stay meaningful.
- **Freshness cadence**: the fresh split rolls on a fixed schedule (e.g., quarterly) with a published
  cutoff date so time-gating is auditable.
- **Submission integrity**: held-out and private splits are run by maintainers; submitters never see
  them; results are signed with harness version + seed.
- **Claims discipline**: leaderboard copy and the paper route through
  [`docs/claim-ledger.md`](../claim-ledger.md); "upper bound, not minimum" and "procedure-relative"
  are non-negotiable framings.

## 7. Risks and mitigations (state them before reviewers do)

| Risk | Why it bites | Mitigation |
|---|---|---|
| **Search-quality confound** (Track O) — a model looks better because the search was better, not the model | Undermines "benchmark *of the model*" | Flagship is Track F (no search); Track O pins+versions the harness and discloses budget; report both |
| **Fidelity metric is gameable / fragile** | Embedding cosine can be hacked or noisy | Metric basket, ≥2 embedders, exact/execution where possible, sensitivity analysis, leakage gate |
| **Canonical-recall = memorization, not elicitation** | S1 could inflate headline | Bounded share; reported separately; never the headline |
| **Contamination of public split** | Inevitable over time | Private + fresh splits; published gap; rolling refresh |
| **"You're just LLMLingua / a leaderboard"** | Novelty challenged | The output-first, model-as-subject, curve-valued framing (doc 04) |
| **Cost of evaluating every model** | Many models × many items × reruns | Kaggle Grant (free model access); Track F is cheap; cache by (model, item, seed) |
| **Maintainer caution** — repo deliberately avoided "just a leaderboard" | Strategic tension (open-questions.md) | Benchmark *strengthens* the workbench (a leaderboard view over `BenchResult`), inherits honesty layer, does not replace the product identity |

## 8. The honest size estimate

- **M0** is a focused engineering spike on existing machinery — the riskiest *design* question (does
  the metric rank models sensibly and survive the leakage gate?) is answered cheaply here.
- **M1** is the real work: dataset construction across five strata with provenance, splits, and CIs.
  Dataset quality, not code, is the dominant cost — as it is for every credible benchmark.
- **M2–M4** are packaging, community process, and writing — high leverage, lower technical risk.

Recommended first action: **build M0** to convert the thesis into a defensible number, then decide
M1 scope with that evidence in hand. This matches the repo's "smallest reviewable change that proves
the object" discipline.
