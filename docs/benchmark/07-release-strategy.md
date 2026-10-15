# Release Strategy: Repository, Hosting, and the Path to Authority

This document answers a direct question — *new remote repo, or no commit anywhere and upload straight
to Kaggle / Hugging Face later?* — and then generalizes it into a plan for reaching SWE-bench-grade
authority. The short version:

> **The git repository is the source of truth and must exist publicly and early; Kaggle and Hugging
> Face are distribution mirrors, not the home.** Do not build uncommitted and "upload later." Do build
> in the Aleph repo now, then extract to a dedicated public `aleph-bench` repository once the metric
> is proven — and mirror from there to HF (dataset) and Kaggle (tasks).

## 1. The decision, with reasoning

### Recommended: staged — `bench/` in this repo now → dedicated public repo at M1 → mirror to HF/Kaggle

| Option | What it means | Verdict |
|---|---|---|
| **A. New public repo immediately** | Spin up `aleph-bench` before the metric is proven | Premature. A benchmark's first impression is its credibility; launching with a half-formed metric and no results invites a weak first read. SWE-bench launched *with* a paper, a working harness, and a leaderboard — not a stub. |
| **B. Build in this repo, extract later** *(recommended)* | Develop `bench/` beside the engine it reuses; cut a standalone public repo at M1 | Keeps provenance and git history; reuses adapters/contract; lets the design move fast under the existing lint/checks; then launches the dedicated repo with a strong first impression. |
| **C. No commit; upload to Kaggle/HF later** | Skip git; push files to platforms | **Reject.** This throws away the single most important trust artifact a benchmark has. |

### Why git-first, and why a *dedicated* repo

- **Provenance is the trust artifact.** Researchers and serious adopters read the repository: its
  history, its issues, its PRs, its CI, its release tags. SWE-bench, BIG-bench, lm-evaluation-harness,
  HELM, LiveBench, LiveCodeBench are **all standalone git repos**. None are "a zip uploaded to a
  platform." A benchmark with no auditable history reads as unserious, regardless of how good the data
  is. Option C forfeits this.
- **A benchmark needs its own issues, PRs, releases, CI, and citation.** BIG-bench's community
  identity *is* its PR-based task submission. That requires a repo whose top-level identity is the
  benchmark — not a `docs/benchmark/` folder inside a product repo, where external contributors cannot
  cleanly file "a new task" without wading through the product.
- **Hugging Face and Kaggle are distribution, not source.** HF hosts the *dataset* (with Croissant
  metadata) and the *leaderboard Space*; Kaggle hosts the *tasks* and runs models for free. Both pull
  from, or mirror, the canonical repo. They are how people *consume* the benchmark; the repo is how
  people *audit and extend* it. You want both, fed from one source of truth.
- **Why not extract on day one (Option A):** the metric and strata are still moving (see the M0 gate).
  Extracting prematurely fragments effort and risks a weak public debut. Build close to the engine
  until M0/M1 prove the number ranks models sensibly; then launch the dedicated repo as a *deliberate*
  event with a README, first results, and a paper draft.

### The concrete topology

```text
                 canonical source of truth
   ┌───────────────────────────────────────────────┐
   │  github.com/<org>/aleph-bench   (extracted @M1) │
   │  engine · data(public+fresh) · tasks · harness  │
   │  schemas · DATASHEET · croissant.json · CITATION │
   └───────────────────────────────────────────────┘
        │ mirror            │ mirror            │ task adapter
        ▼                   ▼                   ▼
   HF dataset+Space    Kaggle Benchmarks   lm-eval-harness task
   (Croissant, leaderboard)  (free models, grant)  (de-facto standard runner)
        │
        ▼
   arXiv / NeurIPS D&B paper  (cites the repo + DOI'd dataset release)
```

Until M1, `aleph-bench` lives as `bench/` in this repo (the layout in
[`03-architecture-and-launch.md`](03-architecture-and-launch.md)). The extraction is a clean
`git filter-repo` of `bench/` + `docs/benchmark/` + the relevant `schemas/`, preserving history.

## 2. The authority template — what SWE-bench actually did, and our analog

SWE-bench is the right model to study because it reached *both* academic (ICLR 2024) and engineering
(industry-standard leaderboard) authority. Its construction, distilled, and mapped to us:

| SWE-bench move | Why it created authority | ALEPH-Bench analog |
|---|---|---|
| **Real-world provenance** — 2,294 tasks from real GitHub issues+PRs across 12 well-maintained repos | "Not toy problems" — face validity | The **production-realism stratum** (S3+): real task specs / API pairs / output contracts, not only literary texts ([`06`](06-search-rigor-and-production.md) §B.4) |
| **A construction *pipeline*, not hand-curation** — scrape ~90k PRs → attribute filter → execution filter | Scales, and the filtering rules *are* the quality argument | A **generation+search+audit pipeline**: fresh-generate targets → multi-proposer compress → leakage-gate + convergence-certify → human audit ([`06`](06-search-rigor-and-production.md) §C) |
| **Objective, execution-based verification** — fail-to-pass tests in a per-instance Docker image | No subjective grading to argue about | **Execution / schema / held-out-test** fidelity for S3/S4; exact-match for S1/S2 — objective wherever possible |
| **A human-validated gold subset** — SWE-bench *Verified* (500 human-checked) | Removes "is the task even valid?" doubt | A **Verified split**: human-audited ladders + targets, the cleanest public subset |
| **A private held-out set** — SWE-bench *Pro* (proprietary, legally inaccessible) | Structural contamination immunity; the 81%→46% gap proved it mattered | Our **private + fresh splits**; report the public/held-out gap as the contamination indicator ([`02`](02-design-spec.md) §6) |
| **A reproducible harness + public leaderboard + submission flow** | Anyone can run it and be ranked | Multi-homed harness (package + Kaggle + lm-eval) + HF Space leaderboard + PR/submission governance ([`03`](03-architecture-and-launch.md)) |
| **A paper that names the construct and the limits** | Citable; honest about scope | The paper outline in [`04-positioning-and-novelty.md`](04-positioning-and-novelty.md) |

The throughline: **authority comes from objective verification + real provenance + a disclosed
construction pipeline + a contamination story + a runnable harness + an honest paper.** It does *not*
come from a clever metric alone. Our metric is the novelty; these six are the cost of being believed.

## 3. Raising to academic + engineering release level — the checklist

Concrete artifacts the canonical repo must carry at launch (these are also exactly what NeurIPS
Datasets & Benchmarks now requires; cross-checked against the BetterBench minimum-QA checklist,
arXiv:2411.12990):

- `README` with the construct, the leaderboard, and a 60-second "what a high score means / does not
  mean."
- `DATASHEET.md` (datasheets-for-datasets), `croissant.json` (machine-readable metadata + RAI), and a
  per-stratum **license** statement.
- A **versioned, seeded harness** that reproduces any leaderboard row; pinned model/decoding/metric
  versions; a `CITATION.cff` and a Zenodo **DOI** for the dataset release.
- A **replicate-results script** — one explicit command per release that regenerates the released
  tables/figures from raw results plus pinned versions.
- **Public + Verified + private/fresh splits**, a published **contamination audit**, and CIs on every
  number.
- A `CONTRIBUTING` describing **task submission by PR** (BIG-bench-style) and **model submission** with
  automated held-out eval.
- A named **contact person** and a **maintained feedback channel** (issues/discussions or
  equivalent) for benchmark users.
- A **maintenance plan**: version policy, fresh-split cadence, who runs the private split, and a
  quick-start usability re-check each release cycle (at least yearly).
- A `LIMITATIONS` section and a claims ledger entry — upper bound, procedure-relative, metric-class
  dependence.
- A **released-result artifact set** — results table, per-sample records, identity chain, and a
  one-command replication path (shape below).

If the repo has all of these on launch day, it is simultaneously a credible open-source benchmark and
a submittable Datasets & Benchmarks paper. That dual-readiness is the target.

### Released-result artifact set — harness-conventional shape (2026-10-15)

A release is not just a row on a leaderboard; it is a set of files a third party can audit and
re-score without talking to us. Following harness conventions (lm-evaluation-harness writes a
`results.json` via `--output_path` and per-sample logs via `--log_samples`; Kaggle and Hugging Face
keep run outputs and dataset revisions downloadable), every released result publishes — at stable
relative paths in both the release repository and its mirrors — the following set. It applies
prospectively from the v0.2 protocol line onward; the checked-in v0.1 M0 delivery package remains
immutable and check-only.

| Publishes | What it is | Convention it follows |
|---|---|---|
| `results.json` | The released table: one record per model × track × stratum — scalar (`AURC`) and duals (`ECL@τ`, `Elicit@k`), bootstrap CIs, coverage (`missing / failed / unverified ≠ 0`), and the identity block (release id, protocol/scorer/dataset digests, decoding, seeds). Aggregates only. | lm-eval `results.json` |
| `samples.jsonl` | The per-sample view: one record per item × model × ladder point (rung, paraphrase, prompt digest, measured length, raw decoded output, fidelity summary, leakage-gate decision) — the public face of the run's sample ledger, sufficient to re-derive the table without model calls. | lm-eval sample logs (`--log_samples`) |
| `release-manifest.json`, `run-receipt.json`, `manifest.sha256` | The identity chain: frozen release manifest, run receipt(s) with source/output/sample-ledger/envelope digests, and checksums. Exact platform locators (GitHub tag, Kaggle Task/version/run, HF revision) live in the publication envelope, not inside verified records. | Our record classes ([records plan](../plans/benchmark-release-records-and-kaggle-harness.md)) |
| `REPRODUCE.md` (+ script) | One explicit command per released table, pinned toolchain versions, expected digests. If the published set alone cannot regenerate the released table, the result is not out of draft. | The replicate-results requirement above |

Rules: no release-local re-specification of record fields — the execution-side bundle layout (for
example `responses.jsonl`, `failures.jsonl`, `environment.json`) remains the archival source in the
records plan, and result field constraints live in
[`03-architecture-and-launch.md`](03-architecture-and-launch.md) §2 plus `schemas/v0.2`; raw model
outputs are published only where the stratum license permits (public-safe evidence otherwise); the
set is append-only (later knowledge creates a superseding receipt or a new result, never an edit of a
published artifact). Survey basis: lm-evaluation-harness README and Kaggle Benchmarks documentation,
fetched 2026-10-15 (recorded in the practice review §5); the v0.1 platform package under
[`../../bench/results/platform/m0-mock`](../../bench/results/platform/m0-mock) is the layout
precedent.

## 4. Naming, org, and license

- **Name**: `aleph-bench` (engine/repo) measuring the **Elicitation–Compression frontier**; headline
  metric **AURC**, procurement metric **ECL@τ**. Keep "Aleph" — it carries the existing thesis and the
  Borges image, and ties the benchmark to its origin instrument.
- **Org**: a dedicated org or the existing `p-to-q` org; a neutral org reads as more "community" than a
  personal account (a small but real trust signal — see how benchmarks favor lab/org homes).
- **License**: code **Apache-2.0** (matches this repo); **data** licensed per stratum with provenance
  in a source ledger; consider **strong copyleft** on any scraped-source stratum as a contamination
  deterrent (the SWE-bench Pro tactic).

## 5. The recommendation in one line

Build `bench/` here now; proof the metric at M0/M1; then launch a **dedicated public `aleph-bench`
repo** as the source of truth, and mirror it to **HF (dataset + leaderboard Space)** and **Kaggle
(tasks + free models, apply for the grant)**, with **lm-eval** as the standard runner and an **arXiv /
NeurIPS D&B** paper citing a **DOI'd** release. Git first, platforms second, paper to seal it.
