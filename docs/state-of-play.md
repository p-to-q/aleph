# State of Play

This is the current confidence map for Aleph after the Hackathon, PR0 research contract, frontier
repair and regeneration, bounded-coordinate bootstrap, and the engine/research wave (#109–#114). Use
it when asking: what is true, what is implemented, what is only researched, and what should happen
next?

## Core hypothesis

Aleph starts from a modern model-output surface and runs the prompt problem backward:

```text
given target output y
and declared model / decoding / metric / domain / reliability conditions
search under a declared algorithm / budget / seed / tokenizer
for the shortest confirmed prompt coordinates found
that reproduce or approximate y
then show the path back to explicit reconstruction
```

This is a product/research hypothesis with enough evidence to build around, but not enough evidence to claim a global optimum or universal theory of shortest prompts.

## What Is Settled

| Claim | Confidence | Why |
|---|---:|---|
| Aleph is a reverse prompt compression workbench, not a prompt-polishing assistant. | high | Settled in `THESIS.md`, `docs/core-concept.md`, and `docs/claim-ledger.md`. |
| The right baseline is **Explicit Reconstruction**. | high | It anchors surface-copy and recoverability controls and prevents context-window length from becoming a fake endpoint. |
| The left endpoint is **Shortest Found** `L_hat`, not oracle `L*` or "the shortest possible prompt." | high | The found statistic is archive-, algorithm-, budget-, seed-, tokenizer-, and confirmation-relative. |
| `AlephRun` is the exchange contract. | high | Types, schema, fixtures, API adapter, and UI surfaces converge on it. |
| Fixture and simulated observations must be labeled. | high | This is a repository rule and a product honesty rule. |
| White-box claims require logits or model internals. | high | Research and verification agree; local MLX NLL can support adapter output, not broad product claims. |

## What Is Implemented

| Area | Current state | Source |
|---|---|---|
| Active launch UI | Next.js app in `web/`, started by `start.sh`. | `web/app/page.tsx`, `start.sh` |
| Archived workbench UI | Vite/React console is retained only as a historical reference. | `apps/web/src/main.tsx`, `docs/archive/legacy-frontend.md` |
| Product run contract | `AlephRun`, candidates, observations, metrics, a legacy surface-copy field, and frontier helpers; it is a projection, not the full research archive. | `packages/core/src/types.ts`, `schemas/aleph-run.schema.json` |
| Fixtures | Multiple demo runs with explicit fixture/simulated modes. | `packages/fixtures/src/` |
| API boundary | FastAPI mock route and local MLX adapter wrapper. | `apps/api/` |
| Local live search spike | MLX/Qwen route can produce AlephRun-compatible adapter output when a local MLX setup is running; Apple Silicon is the known maintainer path and Linux CUDA is now an upstream MLX backend path. | `search/`, `docs/verification.md` |
| Frontier correctness and regeneration | PR #100 preserves real observed candidates instead of fabricated repeated-length coordinates; the public MLX frontier has since been regenerated from actual evaluations — every displayed point re-measured under one declared procedure and linked by canonical digest to a per-point receipt (`web/public/aleph-frontier.receipts.json`), with linkage enforced by `scripts/check-public-frontier.mjs`. | `packages/core/src/frontier.ts`, `search/aleph_search.py`, `search/frontier_receipts.py` |
| Exact finite bootstrap | PR #103 adds exhaustive bounded-coordinate ground truth, independent Python replay, receipts, and scoped Lean checks. It is the first BCS R1 tranche, not full BCS or a real-model result. | `search/bounded/` |
| Engine artifact kernel | PR #109 (PR A): canonical serialization, typed proposal/evaluation contracts, append-only run bundle with materialized views, a pure replay adapter, and an independent fail-closed verifier; fixture-driven, no model calls. | `search/engine/` |
| Hybrid-Pareto search slice | PR #113/#114 (PR B): protected single-use confirmation, deterministic operators, a budget-reserved hybrid scheduler under a frozen declared config, and a measurement-lossless `AlephRun` projection with verifier attestation; end-to-end runs are deterministic fixtures; the pinned MLX canary is still open (PR C). | `search/engine/` |
| Strict run import | The file-first round trip has both halves: `search/engine/import_aleph_run.py` loads a run bundle (full replay verification, then the projection is re-derived from the stream) or a single `aleph-run.json` file (canonical bytes, strict schema, artifact-ref digests, exporter invariants). Read-only and fail-closed; a standalone file import is labeled `replay_verified=false` unless it is anchored to a verified bundle. The product open-file flow (`web/app/lib/run-file.ts` plus open/save controls) opens the same projection files in the app — schema plus static invariants, candidate identity and selected candidate preserved, projection labeling — while digest and replay verification stay engine-side. | `search/engine/import_aleph_run.py`; `web/app/lib/run-file.ts` |
| MiniPrompt/ACR reproduction (raw-coordinate baseline) | Method-level reproduction of the pinned upstream scan and GCG loop on MLX under a frozen declared config (`search/miniprompt/`): resumable receipted runs, an MLX-free fail-closed receipt verifier, and raw-coordinate labeling; the archived canary acquired `hello world` at 3 free tokens (n=5/4/3 acquired, n=2 failed in 200 steps) and a negative/partial control is archived alongside. | `search/miniprompt/`, `search/miniprompt/receipts/` |
| Research formalization and practice review | PR #110–#112: leakage-channel and description-length formalizations, related-work cards, the engine/benchmark practice review, and the structural-decision research gate. | `docs/research/` |
| Repo checks | Lightweight lint/check suite protects claims, fixtures, links, language, and schema. | `npm run lint` |

## Research Converted Into Product Shape

| Research input | Converted into |
|---|---|
| p-to-q file-first repository discipline | Artifact-first repo, small docs map, lightweight checks, sparse decisions. |
| ACR/MiniPrompt and Prompting Complexity | Closest empirical baseline and formal neighbor; they prevent novelty claims for bare target-first shortest-prompt search. The MiniPrompt baseline is now reproduced method-level on MLX (`search/miniprompt/`) with archived canary and control receipts. |
| ARCA / GCG direction | Lower-level raw-coordinate comparators or proposal components, not the closest baseline or product identity. |
| vec2text / embedding inversion | Recorded as adjacent inversion work, explicitly not Aleph's core task. |
| Aquin-style instrumentation | Inspired token loss, attribution, exposure, eval, and observation panels, with mode labels. |
| Local MLX spike | Wrapped behind `apps/api` as experimental adapter evidence rather than exposed as product architecture; hardware scope follows MLX rather than a product-only Apple Silicon assumption. |
| P2 adapter evidence contract | Typed token NLL channel: schema-pinned entry shape, fail-closed local adapter (`black_box` on malformed traces), measured-vs-fixture labels, and a live local MLX receipt. |

## Researched But Not Yet Converted

| Topic | Current status | Acceptance gate |
|---|---|---|
| Metric contract | PR0 settles the vector/missingness boundary; target-family metrics and calibration remain open. | Implement versioned metric manifests and named projections without replacing raw observations. |
| Typed copy/recoverability evidence | PR0 rejects one universal leakage scalar; implementation is not yet stable. | Freeze a finite versioned probe suite, nulls, power targets, channel thresholds, and trace-integrity checks. |
| Hosted black-box adapter | Implemented through the Next.js `/api/search` route with server-side OpenAI-compatible credentials and fallback configuration. | Keep returned candidates as `AlephRun` and mark observations `black_box`. |
| Stable model-internal evidence contract | Token NLL now has a recorded contract: schema-pinned entry shape, fail-closed adapter, measured-vs-fixture labels, and a live receipt (`docs/research/token-nll-evidence-note.md`). The hosted path cannot carry the channel; broader panel wiring and attribution stay open. | Extend the same typed-channel pattern to further model-internal fields only under explicit white-box requirements. |
| Deletion ablation / prompt-token attribution | UI-shaped, not real. | Compute from model internals or repeated behavioral probes and label source mode. |
| Persistence (database layer) | File-first round trip shipped: per-run bundles stay the system of record (strict engine import/export), and the product open-file flow now opens/saves projection files with the selected candidate preserved; a database remains deferred. | No gate pending at the file layer (met by the product open/save wiring); revisit the database only under the recorded triggers. |
| Permanent frontend path | settled | `web/` is the active launch path; `apps/web/` is archived reference material. |

## Interface Cleanliness

The interface story is understandable but still split across two histories:

- `web/` is the current launch/demo surface.
- `apps/web/` is archived reference material and no longer part of the terminal-facing launch path.
- The product object should remain simple: target output, run settings, candidate path, selected prompt/output, and observations.
- Secondary panels should stay useful, but they should not obscure the main compression path.

The next UI cleanup should make one screen answer:

```text
What target am I compressing?
Which candidate am I looking at?
Why is it shorter or better?
What evidence is real, fixture, simulated, black-box, or white-box?
What should I try next?
```

## Next Correct Move

The next phase should start from executable research contracts rather than more surface area:

1. Done: the finite bootstrap now carries the threshold/compiler statement map with independent
   Python checks and scoped Lean theorems (PR #108; issues #102/#105 closed).
2. Real-model evidence for the search line: the archive, separated proposal/evaluation roles, fresh
   confirmation, the six-account ledger, and independent replay are merged as the fixture-driven
   PR B slice (#109/#113); the pinned open-weight MLX canary (PR C) is implemented with its PR open
   (#118), and the public MLX frontier has been regenerated from actual evaluations with per-point
   receipts (`search/frontier_receipts.py`).
3. Done (first tranche): MiniPrompt/ACR is reproduced method-level behind the same boundary
   (`search/miniprompt/`, archived receipts under `search/miniprompt/receipts/`, gate note
   `docs/research/miniprompt-reproduction-note.md`); matched-budget comparisons against
   Aleph's readable search remain the follow-up.
4. Done: the product open-file flow (`web/app/lib/run-file.ts` plus open/save controls) returns a
   saved run to the app with its selected candidate intact and labels it a projection; the strict
   engine importer (`search/engine/import_aleph_run.py`) remains the verification surface.
5. Promote hosted/Kaggle/Hugging Face evidence only after pinned artifact readback and offline replay.

## One-Sentence Status

Aleph has a stable thesis, repaired observed-frontier semantics, an exact finite/Lean bootstrap, product
model adapters, and a clear evidence boundary; the main unresolved work is real-model engine evidence
(the pinned MLX canary) under the merged search archive, typed recoverability evidence,
matched-budget baseline comparisons (the MiniPrompt raw-coordinate baseline is now reproduced and
receipted), and cross-platform replay.
