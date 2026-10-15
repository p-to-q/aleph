# Benchmark statistical-significance practice review (Aleph-Bench policy)

**Date:** 2026-10-15 · **Scope:** the statistical-significance reporting policy for Aleph-Bench
scores — *which tests, sample sizes, and aggregation*
([`engine-and-benchmark-practice-review.md`](engine-and-benchmark-practice-review.md) §8 item 3).
**Why:** this closes the statistical-significance half of the prior-art review's high-priority
packaging row (`kbench` interop design remains the sibling-owned half); the v0.2 bench documents
already *promise* uncertainty ("bootstrap CIs over items") without a defined
method, and `research-process.md` records the gap verbatim: "Statistical-significance reporting
policy for Aleph-Bench scores is not defined."

Evidence tags: **F** = fact observed in a primary source (fetched 2026-10-15; byte hashes in
Sources); **I** = interpretation/decision for Aleph; **U** = open question. Nothing here changes
science claims; it changes release practice for the benchmark line.

## 1. What the tree already promises (F — `benchmark/source-v0.2` docs)

| Where | Promise (as written) |
|---|---|
| `02-design-spec.md` §2, §7 | `AURC(θ) = mean_i AURC_i(θ) with bootstrap 95% CI over items`; "**Uncertainty on every number**: bootstrap CIs over items; for stochastic decoding, `n` reruns per point with mean fidelity and variance"; "preliminary" labels for models with few items or high variance; decoding pinned and reported (hosted prompts run five times even at temperature zero) |
| `05-metrics-audit.md` (verdict table; Track F contract) | `stability` becomes the per-point CI on fidelity, not a fused score term; the contract prints `headline: AURC ↓ (+ bootstrap 95% CI)` |
| `07-release-strategy.md` §3 | `results.json` rows carry "bootstrap CIs", coverage (`missing / failed / unverified ≠ 0`), and the identity block |
| `09-metric-validity-and-rigor.md` | the rigor spine (validity checks, dashboard aggregation) — **no significance-policy section yet** |

The 01 §5 checklist addendum treats the BetterBench significance-or-uncertainty row as "already
satisfied by item 5's bootstrap CIs". **The gap** (§8 item 3): the docs say *bootstrap CI over
items* but never fix **which test** compares two models (**paired vs unpaired**), the resampling
parameters (unit, stratification, count, seed), the **minimum sample size** for a claim, or the
**multiplicity** rule across cells and strata. §2 answers those; §3 fixes the policy.

## 2. Primary sources

### 2.1 BetterBench (arXiv:2411.12990v1, NeurIPS 2024 Datasets & Benchmarks) — the community-standard requirement

- **F.** Its assessment criteria include implementation item 8, "Statistical significance or
  uncertainty quantification of benchmark results is reported", and full checklist item 17,
  "Report statistical significance of benchmark results for at least one model": "Benchmark
  developers run statistical significance tests on the benchmark results. They report results for,
  e.g., more than one random seed, and provide variance bounds. In cases where the benchmark is
  perfectly deterministic, this should be explicitly stated." (0/5/10/15 rubric; 15 = tests run
  *and* variance bounds or other uncertainty estimations).
- **F.** Their audit of 24 benchmarks: an average score of **5.62 (of 15)** on reporting
  statistical significance — among the weakest criteria — and "14 out of 24 benchmarks did not
  perform multiple evaluations of the same model or report statistical significance or uncertainty
  of results." Their discussion frames the user need precisely: without intra-model variance
  (re-runs), observed inter-model differences cannot be separated from noise; they recommend
  multiple seeds/sampling and reporting **mean and variance**.
- **I.** Make uncertainty a *release gate*, not an appendix: the field's own best-practice
  framework scores "reported uncertainty" and most benchmarks fail it; Aleph-Bench can be on the
  right side of that criterion from v0.2 onward.

### 2.2 Miller, "Adding Error Bars to Evals" (arXiv:2411.00640v1) — the statistical framework ("which tests")

- **F.** Five recommendations: (1) standard errors of the mean via the CLT; (2) **clustered**
  standard errors when questions are drawn in related groups; (3) reduce noise by resampling
  answers and reading next-token probabilities, without treating repeats as independent draws;
  (4) "conducting statistical inference on the question-level **paired** differences, rather than
  the population-level summary statistics"; (5) **power analysis** to determine whether an eval
  (or a subsample) can test a hypothesis of interest.
- **F.** On the interval method: "we regard bootstrapping as unnecessary **unless a complicated
  sampling scheme or estimator is being used**" — the CLT variance form is the reference for
  simple means over independent questions; bootstrap remains the general tool outside that case.
  On cluster adjustment: real evals showed clustered standard errors "over 3X larger than naive
  standard errors" (Table 4). Reporting format: include **the number of questions**, report each
  score with its **standard error in parentheses**, 95% CI = mean ± 1.96·SE; for comparisons,
  report the paired difference with its CI and the item-level correlation.
- **I.** Aleph-Bench headline statistics (AURC; `ECL@τ`/`CF`; `Elicit@k`) are composed estimators
  over a searched frontier — the "complicated estimator" carve-out — and items within one stratum
  are not independent of other strata — so intervals come from **item-level resampling**
  (stratified when strata exist), comparisons from **paired by-item inference**, with CLT closed
  forms as cross-checks for plain means.

### 2.3 Dodge et al., "Show Your Work" (arXiv:1909.03004v1) — reporting under search budgets

- **F.** Single test-set point comparisons are unreliable for model comparison: the winner flips
  with the **search budget**; the paper recommends reporting performance **as a function of
  budget** (expected best-found validation performance vs trials), with means still the most
  informative statistic when variance bands overlap. For max-over-budget statistics, their
  estimator "has strictly less error than using the bootstrap".
- **I.** Aleph-Bench headlines are **fixed-budget, declared-procedure** statistics (budget `B` is
  part of the item contract), so bootstrap intervals over items are sound; the caution binds only
  for best-of-an-unbounded-search framing (e.g., Track O convergence diagnostics): those are
  reported as budget curves, never as a bootstrapped maximum in a release table.

### 2.4 lm-evaluation-harness (implementation convention; the shape we mirror)

- **F.** The harness computes uncertainty per metric via **bootstrap** by default:
  `bootstrap_iters: int = 100000`; `stderr_for_metric` dispatches to `bootstrap_stderr` (standard
  deviation of bootstrap replicates) for a curated bootstrappable-metric list, aggregates subtask
  stderrs for groups, and ships values with their stderr in `results.json` (`bootstrap_iters=0`
  disables).
- **I.** Mirror the shape — stderr/CI alongside every value in `results.json`, bootstrap over the
  evaluation units — with our declared unit (item), declared stratification (stratum), and
  declared parameters (count, seed).

## 3. The policy (I — decisions, grounded in §2)

**P1 — Unit and variance components.** Resampling unit = **item**; when strata exist, resampling
is **stratified by stratum** (stratum = cluster, per Miller §2.2). Per-item scores average over
reruns first; reruns are never independent draws. Report two variance components: cross-item and
within-item (rerun / provider nondeterminism — the existing `stability` handling becomes the
per-point CI). **Stochastic decoding requires k ≥ 2 recorded reruns** for a cell to carry interval
claims; deterministic decoding is stated explicitly (BetterBench item 17).

**P2 — Every reported number carries an interval.** 95% CI via **stratified item-level
bootstrap**; release runs pin **B = 100,000** resamples (matching the lm-eval default) and the RNG
seed; exploratory tables may use B ≥ 10,000. Each `results.json` cell carries: value, `ci_low`,
`ci_high`, `ci_method` (`bootstrap-percentile`), `resamples`, `seed`, `n_items`, `n_clusters`,
`label`. For plain item-mean cells, the CLT standard error is computed as a closed-form
cross-check and reported.

**P3 — Comparisons are paired (the "which tests" core).** All models run the same frozen item
set, so cross-model claims use **item-level paired differences**: bootstrap the mean of
`s_A,i - s_B,i`; claim a difference only when the 95% CI excludes 0; report Δ, SE, CI, and the
item-level correlation. **Overlapping marginal CIs are never used as a test** (the naive reading
of overlapping CIs is exactly the failure mode Miller's framework fixes). Comparisons across
non-identical item subsets fall back to the unpaired standard error and are labeled as such.

**P4 — Sample sizes.** Every cell reports `n_items` (and `n_clusters`). A cell (or stratum) with
**n < 30 items** is labeled `preliminary` and excluded from significance claims (Chatbot Arena
practice, already promised in `02`). The v0.2 public S2 split has an exact 30-item count, so it
meets the threshold. Release notes publish the **minimum detectable effect** at the released n
(power analysis, Miller rec. 5) so readers see what the data can and cannot support; new strata
are power-sized before carrying claims (`03-architecture-and-launch.md` gate).

**P5 — Multiplicity.** Pre-declare the **primary family** (headline `AURC` per track; for v0.2,
the single S2 stratum). Within the family, apply **Holm correction** across pairwise claims; the
rest of the dashboard (`ECL@τ`, `CF`, `Elicit@k`, per-stratum views, transfer/contamination gaps)
stays `exploratory` unless separately pre-declared. Ranking sensitivity (promised in `09` §3) is
the disclosure companion: ranks shown with intervals, claims only via the paired test.

**P6 — Aggregation.** Per-stratum numbers are first-class and always shown; the headline is the
**macro-average over strata** with stratified bootstrap. `S1` (canonical recall) never folds into
the headline (existing rule). Where the aggregation statistic is still open (`ECL@τ` treatment of
unreachable items — issue #35), the cell stays `exploratory`. Coverage is reported per cell; cells
with coverage gaps beyond the declared set cannot carry `primary` labels.

**P7 — Determinism and honest phrasing.** A fully deterministic track says so explicitly instead
of reporting empty uncertainty (BetterBench item 17). Never phrase a CI-includes-0 result as "no
difference": the statement is "indistinguishable from noise at this n", with the released minimum
detectable effect quantifying what would have been detectable (the same discipline as the
`indeterminate` outcome in the confirmation protocol).

## 4. Structural effect

- **Fold the executable policy into the bench docs** (companion slice on
  `benchmark/source-v0.2`): a new section in `09-metric-validity-and-rigor.md` (the rigor spine),
  one-line pointers in `02-design-spec.md` §7 and `07-release-strategy.md` §3, and the
  `results.json` field list from P2.
- **Record shape:** the added fields are release-record constraints; their canonical home is
  `03-architecture-and-launch.md` §2 plus `schemas/v0.2`. If the released-result schema must
  change, that is a separate recorded decision (U); this note fixes the policy and the field list
  only.
- No engine change, no new dependency, no new process.

## 5. Open (U)

- Percentile bootstrap vs BCa vs normal-approximation intervals — decide from empirical coverage
  of the first v0.2 release; the policy requires only "bootstrap over items with declared
  parameters".
- Exact release resample count/seed coordination with cache keying (reruns and caches are protocol
  coordinates).
- Minimum-detectable-effect table format for release notes.
- `kbench` interop (separate §8 item) must respect this policy when the Kaggle surface is
  designed.

## Sources (fetched 2026-10-15, byte-verified)

- **BetterBench** — Reuel, Hardy, Smith, Lamparth, Hardy, Kochenderfer, "BetterBench: Assessing AI
  Benchmarks, Uncovering Issues, and Establishing Best Practices", arXiv:2411.12990v1 (20 Nov
  2024; NeurIPS 2024 Datasets & Benchmarks Track) — `https://arxiv.org/pdf/2411.12990`, sha256
  `10fac252d3edb959821e3cdc43071e8d61d32bd061e065e6a6dece6af3eedb0e` (805,390 B); project site `https://betterbench.stanford.edu`.
- **Adding Error Bars to Evals** — Evan Miller (Anthropic), arXiv:2411.00640v1 (1 Nov 2024) —
  `https://arxiv.org/pdf/2411.00640`, sha256 `22570aaf1313c7ab8861d2373f0e8e90c160f6c69c8960aecbb4733c48b22149` (330,983 B).
- **Show Your Work** — Dodge, Gururangan, Card, Schwartz, Smith, arXiv:1909.03004v1 (Sep 2019) —
  `https://arxiv.org/pdf/1909.03004`, sha256 `5cac75c527c93689e95509c01ae68721ac96ea5ec1f41aad7a5cd6b330326ce7` (526,202 B).
- **lm-evaluation-harness** — `lm_eval/api/metrics.py`, sha256 `f4794761c3f53fc036336e79c65dca355ea26a8d4cb00b27155ea2ab4846dbb2` (20,788 B), and
  `lm_eval/evaluator.py`, sha256 `581e7767820aaa8503e6b23682360a6dbcd0c0f8e5b50b53e3f282c64b5bc986` (30,396 B) — raw `main` snapshots from
  `https://github.com/EleutherAI/lm-evaluation-harness`.
- **arXiv API verification** — `http://export.arxiv.org/api/query?id_list=2411.12990,2411.00640,1909.03004`
  (all v1; titles/authors confirmed) sha256 `8365a8ba5aa75e0a881bca5dff3ac140e01610ff86ef5d80a6d55c545708352f` (6,908 B).
