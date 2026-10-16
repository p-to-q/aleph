# MiniPrompt Matched-Budget Comparison Note

Status: gate note for the matched-budget comparison slice of the MiniPrompt/ACR baseline work —
acceptance gate 6 of the reproduction note
([miniprompt-reproduction-note.md](miniprompt-reproduction-note.md)) — recorded under the
structural decision research gate in [research-process.md](research-process.md) **before** the
comparison module lands. Access date for all sources below: 2026-10-16 (UTC). The module and the
archived instances land in the same pull request as this note.

## Question

The reproduction note's acceptance gate 6 asks for "a small declared target set (including at
least one negative/partial control) [archived] so the paper tranche can compare MiniPrompt-found
raw prompts against Aleph readable search at matched declared budgets". The iclr plan's prior-art
table adds that the paper "must report the readable-versus-raw gap". This slice answers the
smallest honest form of that question:

Given two existing prompt-search arms — the raw-coordinate MiniPrompt/ACR scan
(`search/miniprompt/`) and Aleph's readable search procedure (`search/aleph_search.py`) — on the
same pinned model and the same declared targets, what do the two views find when both run under
search settings and budgets that are frozen in advance, inside one shared wall-clock envelope,
with the pairing archived as a digest-bound record?

## Design (frozen before any comparison run)

- **Declaration first.** `ComparisonConfig` (`search/compare/config.py`, schema
  `aleph-comparison-config/0.1.0`) freezes, per instance: the pinned model identity (repo +
  revision + weights digest), the targets with the exact expected raw-side preset config digests,
  the readable-side settings (budgets, candidates per budget, refine steps, stability runs and
  temperature, proposer seed, metric), the shared `envelopeSeconds`, the reproduction threshold
  tau, and the explicit wrapper. Parsing is strict and fail-closed (unknown fields, wrong types,
  duplicated budgets or presets, non-declared metric kinds, malformed digests all rejected), and
  the record embeds the exact mapping with its `aleph-canonical/0.2.0` digest.
- **Matched requirement regime.** Both sides freeze their search settings in advance and run
  inside one shared wall-clock envelope (`envelopeSeconds = 1800`) plus the declared
  one-operation slack (`ENVELOPE_SLACK_SECONDS = 60`); there is no post-hoc tuning, and runs that
  pause at the boundary are not archived (only `stoppedBy = complete` artifacts can be recorded).
- **Wall-clock convention (declared).** Raw side: the sum of the receipt's recorded trajectory
  step seconds. Readable side: the sum of the runner's recorded operation seconds
  (proposal/evaluation/scoring; model load excluded on both sides). Both are checked against
  `envelope + slack` by the record builder at build time and re-derived by the verifier from the
  archived artifacts.
- **Readable arm.** A seeded re-run of the shipped procedure: the declared budgets execute
  descending (100-style ladder replaced by the config's `[6, 12, 25, 50]`), each smaller budget
  carried by compressing the previous best; `k = 3` candidates per budget via one proposal call;
  first-strict-max selection; one NLL-guided refinement step per budget; three stability
  generations at temperature 0.8; then the explicit-reconstruction arm generated under the
  declared wrapper. Every sampled generation is seeded from an explicit `random.Random` tree
  rooted at the declared `proposerSeed` (replacing the shipped procedure's unseeded global RNG),
  and all selections compare the recorded 4-decimal similarities, so the archived selection and
  the staircase `kept` flags are replayable from the archive alone without MLX. The budgets are
  word-count targets for the propose/compress/refine instructions (as in the shipped procedure;
  its per-budget loop applies no length filter — the word-count filter lives only in the separate
  `propose_ladder` batch path, which this arm does not use), so retained points are selected by
  recorded similarity and can exceed their target when the model does; every point records its
  observed token length.
- **Raw arm.** The declared presets run unchanged (`canary-hello`, `control-jumps-partial`,
  `pin4b-hello-smoke`), each receipt carrying the all-match plus greedy-continuation evidence
  chain; the record re-checks the preset digests against the frozen expectations.
- **Findings vocabulary (fixed by `aleph-comparison-record/0.1.0`).** `rawFound` (the raw scan's
  own result; acquisition = exact teacher-forced all-match with matched greedy continuation),
  `readableFound` (min length among non-explicit points with `epsilon <= tau`), `readableBest`
  (min epsilon regardless of tau), `readableExactMinLength` (min length among non-explicit points
  whose recorded output equals the target), `explicitBaseline` (the tagged copy point).
- **Copy/leakage discipline.** Readable-side copy evidence is recorded as ratios only
  (`promptContainsTargetText`, `promptTargetTrigramContainment`), never as a leakage verdict; raw
  coordinates carry no leakage field (token IDs are the ground truth, decoded text is a declared
  rendering).
- **Instances declared now.** `canary-1p7b` (`hello world`, `jumps over the lazy dog` on the
  pinned `mlx-community/Qwen3-1.7B-4bit` snapshot) and `canary-4b` (`hello world` on the pinned
  `mlx-community/Qwen3-4B-4bit` snapshot, using the new bounded `pin4b-hello-smoke` preset).

## Tranche 2 — extended declared target set (declared 2026-10-16 UTC, before any run)

Same module, same conventions, same schemas: this tranche extends the declared target set with three
new frozen raw-side presets and two new comparison instances. It is a declaration extension, not a
structural change (the structural gate note is the tranche-1 section above), and no existing
instance, preset, or archived receipt is modified.

- `canary-42` (1.7B, target `42`): the numeric/minimal stratum under the upstream-default scan
  surface (`stepsInitial=200`, `maxAttempts=8`, `stepsHardCap=4000`; the feasibility receipt
  acquired this target at step 87/240 of a single 5-free-token run).
- `canary-hamlet-line` (1.7B, target `to be, or not to be`): the natural-short stratum under a
  declared tighter cap (`maxAttempts=6`, `stepsHardCap=2000`); acquired or partial, the scan
  result is archived as-is.
- `pin4b-jumps-smoke` (4B, target `jumps over the lazy dog`): mirrors the 1.7B control's declared
  bounds (`stepsInitial=60`, `maxAttempts=2`, `stepsHardCap=1000`) so the negative/partial control
  exists at both pinned scales.

Instances: `canary-1p7b-set2` (targets `forty-two`, `hamlet-line`) and `canary-4b-set2` (target
`lazy-dog`), each with the same declared readable settings, envelope (`1800` s plus the declared
`60` s slack), and `tau=0.05` as the tranche-1 instances. Freeze order: this section, the presets,
the instances, and their digest pins land before any tranche-2 run; runs use the pinned venv with
`HF_HUB_OFFLINE=1` and the single-writer driver discipline, and only completed artifacts
(`stoppedBy=complete`) are archived.

Non-claims carry over unchanged: no ranking, no leakage verdict, no memorization-causality, no
transfer claim; copy proxies stay ratios-only on the readable side, and the raw side carries no
leakage field. No new external sources were needed for this declaration-only extension.

Post-declaration note (2026-10-16 UTC): the first tranche-2 runs exposed raw-arm
criterion-evaluation bugs (4-bit quantized logits are evaluation-shape dependent: a batched
all-match that the single-sequence forward denies, and a teacher-forced all-match that the true
greedy continuation does not reproduce) and one over-strong receipt-evidence rule (a rendering
roundtrip requirement on a claim evaluated on raw IDs). All were fixed before any tranche-2
receipt was archived — see the post-canary fixes section of
[miniprompt-reproduction-note.md](miniprompt-reproduction-note.md) — the declarations above are
unchanged, and all tranche-2 receipts are generated under the fixed conjunction criterion and
evidence rule.

## Sources inspected

| Source (accessed 2026-10-16) | Location | F — what was observed | I — interpretation | U — use here |
|---|---|---|---|---|
| Shipped readable search procedure (primary, in-repo) | `search/aleph_search.py`; frontier procedure declarations in `search/frontier_receipts.py` | The shipped pipeline proposes with the pinned model itself, compresses down a descending ladder `[6, 12, 25, 50, 100]`, refines with teacher-forced NLL-hardest tokens, runs stability generations at 0.8, and appends an explicit-reconstruction arm under a fixed wrapper; method constants: propose 0.85, compress 0.5, refine 0.6; output generation 0.0. Frontier receipts re-measure carried-over prompts and declare no search budget. | The readable arm here is a seeded re-run of exactly this procedure under declared budgets; unlike the frontier receipts, its search budget is rooted and seeded, which is what makes a matched-budget pairing possible. | The readable arm's frozen declaration and the declared-differences list. |
| MiniPrompt/ACR reproduction (primary, in-repo) | `search/miniprompt/`, `search/miniprompt/receipts/`, [miniprompt-reproduction-note.md](miniprompt-reproduction-note.md) | Method-level reproduction of the pinned upstream scan and GCG loop on MLX with receipts, a no-MLX fail-closed verifier, and raw-coordinate labeling; archived canary and negative/partial control. | The raw arm is exact-or-nothing by construction (all-match plus greedy continuation), with no readable semantics. | The raw side of every pairing; its preset digests are frozen in the comparison configs. |
| iclr plan prior-art table (in-repo) | [../plans/iclr-readable-coordinate-program.md](../plans/iclr-readable-coordinate-program.md) (relation notes on Evil Twins, logit2prompt, ALPACA AGAINST VICUNA, RG-PT families) | Prior art already fixes: the readable/raw gap exists in the literature; the paper must report it; matched-budget comparisons are a planned requirement, not a novelty claim. | This slice is measurement infrastructure for an already-surveyed question — the structural risk is in the pairing/envelope conventions, not in the search methods. | Scope control: no novelty is claimed for either arm or for the comparison idea. |
| "Prompts have evil twins" (external primary source) | ACL Anthology `aclanthology.org/2024.emnlp-main.4/`; arXiv `2311.07064` v3 (2024-10-06), EMNLP 2024 Main; fetched snapshots and hashes in `/tmp/compare-sources/` | Abstract: many natural-language prompts can be replaced by prompts "unintelligible to humans" that "provably elicit similar behavior in language models"; the twins transfer between models; found by solving a maximum-likelihood problem. | The closest external statement that interchangeable obfuscated/readable prompt pairs exist; it studies behavior replacement and transfer, not budget-matched search comparisons under one envelope. | Motivation for reporting both views side by side; explicitly not a comparator for the numbers here. |
| "How Should a Prompt Optimizer Spend a Tight Budget?" (external, adjacent practice) | arXiv `2610.05671` v3 (2026-10-09); fetched snapshot in `/tmp/compare-sources/` | BudgetAPO: existing optimizers assume hundreds to thousands of model calls; under tight budgets multi-stage pipelines exhaust budgets and single-stage methods compare on fixed minibatches; proposes a noise-adaptive single-stage allocation rule. | Budget handling is an active concern in prompt optimization, but this line allocates one optimizer's own calls; no external source checked here pairs a raw-coordinate arm and a readable arm under one shared declared wall-clock envelope. | Adjacent practice only; supports the decision to declare and enforce budgets explicitly. |

A targeted search for direct analogues ("matched budget", "equal number of model calls", raw vs
natural-language prompt search) surfaced budget-aware optimizer allocation and cost-optimization
practice but no directly analogous pairing under a shared declared work envelope in the checked
sources; the structural element in this slice is the pairing/record envelope, and the note claims
nothing beyond it.

Source snapshots and sha256 (all fetched 2026-10-16; full manifest at
`/tmp/compare-sources/MANIFEST.sha256`):

- `evil-twins-aclanthology.html` `df72b98f0353c5b2fbcc26263bdef57ba4da4daf91e023ca1a61dba2d9414bd2`
- `evil-twins-arxiv-2311.07064-abs.html` `2b0c6891e34ad08aa8f2022a620df6f44cf11d19d8075cfed60a7e612bd7fe72`
- `budgetapo-arxiv-abs.html` `c95b1c81219b07dcb3a14b289793e9fa462d888cd0d5c23ad5be45ab03b9db34`

## Comparison results

### Tranche 1 (2026-10-16 UTC)

Both instances ran on the pinned snapshots and are archived under
`search/compare/receipts/`; both records and all side artifacts verify with the no-MLX command
(`python3 -m search.compare.cli verify …`). Recorded work seconds stayed far below the shared
envelope on every side (raw 86.8–161.1 s; readable 27.9–42.9 s of 1800 s).

| Instance / target | Raw side | Readable side |
|---|---|---|
| `canary-1p7b` `hello world` | **acquired**: `nFree=3` (n=5/4/3 in 34/50/21 steps; n=2 failed in 200 steps), `wholePromptTokens=5`, greedy continuation matched | best ε=0.5793 at `\|p\|=12` (no point ≤ τ=0.05); the shortest kept point is the copy-including "hello world by ernest hemingway" (`\|p\|=8`, ratios recorded) |
| `canary-1p7b` `jumps over the lazy dog` | **not acquired** under the declared control budgets (n=5/60, n=10/72; `max_attempts`) | best ε=0.1940 at `\|p\|=5` ("dog jumping over lazy dog", a paraphrase; ratios recorded); no point ≤ τ=0.05 |
| `canary-4b` `hello world` | **acquired**: `nFree=3` (n=5/4/3 in 21/17/30 steps), `wholePromptTokens=5` | best ε=0.5055 at `\|p\|=6` ("hello world - classic programming example"); no point ≤ τ=0.05 |

Observed (recorded, not interpreted beyond the record): the 1.7B proposer returned a single
parsable candidate on five of the eight declared budget calls (propose counts 1; the rest 3) — the
evaluation ledger records exactly what happened — while the 4B proposer returned all three on its
four calls; on `hello world` the 4B readable run ended slightly better (ε 0.5055) than the 1.7B
run (ε 0.5793) under the same declared procedure; the raw side's canary trajectories re-produce
the archived 2026-10-15 receipt's step pattern and acquisition points exactly across runs, while
recorded work seconds vary with machine load (161.1–196.1 s for the same 1.7B canary scan across
the runs of 2026-10-16 vs 185.6 s in the archived receipt) — timing noise in the recorded per-step
seconds, not in the deterministic content (steps, losses, token IDs).

### Tranche 2 (2026-10-16 UTC)

Both instances ran on the pinned snapshots under the same declared readable settings,
envelope, and τ=0.05, and are archived under `search/compare/receipts/canary-1p7b-set2` and
`search/compare/receipts/canary-4b-set2`; every record and side artifact verifies standalone
with the no-MLX command, and all cross-side identity checks recomputed true. Recorded work
seconds again stayed far below the shared envelope (raw 103.2–659.0 s; readable 27.9–38.1 s
of 1800 s).

| Instance / target | Raw side | Readable side |
|---|---|---|
| `canary-1p7b-set2` `42` | **acquired**: `nFree=5` (n=5 in 32 steps; n=4 failed in 200), `wholePromptTokens=7`, greedy continuation matched | best ε=0.3953 at `\|p\|=15`; no point ≤ τ=0.05 |
| `canary-1p7b-set2` `to be, or not to be` | **acquired**: `nFree=6` (ladder n=10/9/8/7/6 acquired in 75/57/64/240/51 steps; n=5 failed in 200), `wholePromptTokens=13`, greedy continuation matched | best ε=0.2351 at `\|p\|=42`; no point ≤ τ=0.05 |
| `canary-4b-set2` `jumps over the lazy dog` | **acquired**: `nFree=10` (n=5 failed in 60; n=10 in 48 steps), `wholePromptTokens=16`, greedy continuation matched; rendering roundtrip flag recorded `false` (a recorded fact, not a condition — see the post-canary fixes section of the reproduction note) | best ε=0.1901 at `\|p\|=24`; no point ≤ τ=0.05 |

Observed (recorded): the hamlet-line scan needed six attempts (n=5 failed; the bound
descended 10→6, with every acquisition satisfying the full conjunction criterion), and the
4B acquisition is the recorded case behind the rendering-roundtrip evidence fix; the
hamlet-line raw side's 659.0 s of recorded work reflects that six-attempt ladder, still well
inside the envelope.

## Interpretation and non-claims

- At canary scale the two views are complementary in the expected extreme: the raw coordinate is
  **exact but opaque** (3 free-token IDs — a declared rendering, no readable semantics, no leakage
  field), while the readable view is **legible but approximate** (ε 0.19–0.58 with prompts a human
  can read), and the explicit baseline remains the τ=0 anchor of the front.
- **No global or ranking claim.** This is a canary-scale slice (2 instances, 3 target pairs, one
  declared procedure, one pinned stack, one machine). It does not rank the methods, does not
  estimate their population behavior, and is not a benchmark.
- **No leakage verdict** anywhere: the readable copy proxies are recorded as ratios only, and the
  raw side makes no readability or leakage claim at all.
- **No memorization-causality and no transfer claim** (unchanged from the reproduction note).
- The matched-budget envelope bounds *recorded work seconds*, not wall time across resumptions —
  the convention is declared above, and both sides record it symmetrically.

## Declared differences of the readable arm from the shipped procedure

Recorded in every readable artifact (`procedure.declaredDifferences`): seeded per-call
generations from an explicit `random.Random` tree (the shipped pipeline used the unseeded global
RNG; seeding is required for replay and resume); the comparison ladder `[6, 12, 25, 50]` executed
descending (shipped `[6, 12, 25, 50, 100]`); recorded 4-decimal similarities drive selection so
the archive is replayable without MLX; the explicit arm is generated (as shipped) and retained
only as the tagged copy baseline; the shared wall-clock envelope and digest-bound record are
comparison declarations around the run.

## Structural effect (what this PR lands)

- A new package `search/compare/` (pure parts `config`, `record`, `fixtures`; MLX path
  `readable.py`; driver `run.py`; CLI `cli.py`) with three frozen schemas
  (`aleph-comparison-config/0.1.0`, `aleph-comparison-readable/0.1.0`,
  `aleph-comparison-record/0.1.0`) and two fail-closed verifiers, both MLX-free and
  network-free.
- Committed receipts for both instances with pinned hashes
  (`search/compare/receipts/`, `MANIFEST.sha256`).
- A small backward-compatible refactor of `search/miniprompt/gcg.py`
  (`load_pinned(repo, revision, weights_digest)` plus the existing config wrapper) and the new
  bounded `pin4b-hello-smoke` preset with the 4B pin (revision `4dcb3d10…`, weights digest
  `e240c0bd…`, re-hashed on the maintainer tree 2026-10-16 and matching the frontier-receipt
  pin), so the second pinned model is loadable by anything that pins through that loader.
- No new dependencies; MLX stays out of the default test path; no product surface, engine bundle
  format, or canonicalization change.
- Tranche-2 extension (2026-10-16/17 UTC): the three new frozen raw-side presets and two declared
  instances above, archived end to end under
  `search/compare/receipts/{canary-1p7b-set2,canary-4b-set2}` with a refreshed `MANIFEST.sha256`,
  plus the post-canary fixes in `search/miniprompt/` (single-sequence criterion, greedy-conjunction
  acquisition, recorded rendering-roundtrip flag) with their regression tests — see the
  reproduction note's post-canary fixes section.

## Acceptance gates

1. A strict comparison config, a pure record/verifier pair, and a resumable instance driver exist
   with pure tests in `npm test` (declared fixtures and digests pinned; readable-artifact tamper
   probes; record build/verify against the real archived raw receipt; the runner's state machine
   exercised end-to-end with faked model objects).
2. Two declared instances are archived end to end with full digest binding, and the committed
   copies verify standalone with the no-MLX command.
3. Independent verification (fresh clone; independent recomputation of digests and selection,
   tamper probes, and a deterministic re-run of one readable target) is recorded in the
   pull-request thread.
4. `npm run lint` and `npm test` stay green; MLX stays out of the default test path; zero new
   dependencies.
5. Conventions are recorded, not implied: wall-clock convention, envelope and slack, budget
   order, seeding, method constants, selection semantics, and non-archival of boundary-paused
   runs.
6. No ranking, leakage-verdict, memorization-causality, or transfer claims; ratios only where
   declared.
