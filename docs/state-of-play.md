# State of Play

This is the current confidence map for Aleph after the Hackathon, PR0 research contract, frontier
repair, and bounded-coordinate bootstrap. Use it when asking: what is true, what is implemented, what
is only researched, and what should happen next?

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
| Frontier correctness repair | PR #100 preserves real observed candidates instead of fabricated repeated-length coordinates; the historical public MLX export remains invalid until regenerated from receipts. | `packages/core/src/frontier.ts`, `search/aleph_search.py` |
| Exact finite bootstrap | PR #103 adds exhaustive bounded-coordinate ground truth, independent Python replay, receipts, and scoped Lean checks. It is the first BCS R1 tranche, not full BCS or a real-model result. | `search/bounded/` |
| Repo checks | Lightweight lint/check suite protects claims, fixtures, links, language, and schema. | `npm run lint` |

## Research Converted Into Product Shape

| Research input | Converted into |
|---|---|
| p-to-q file-first repository discipline | Artifact-first repo, small docs map, lightweight checks, sparse decisions. |
| ACR/MiniPrompt and Prompting Complexity | Closest empirical baseline and formal neighbor; they prevent novelty claims for bare target-first shortest-prompt search. |
| ARCA / GCG direction | Lower-level raw-coordinate comparators or proposal components, not the closest baseline or product identity. |
| vec2text / embedding inversion | Recorded as adjacent inversion work, explicitly not Aleph's core task. |
| Aquin-style instrumentation | Inspired token loss, attribution, exposure, eval, and observation panels, with mode labels. |
| Local MLX spike | Wrapped behind `apps/api` as experimental adapter evidence rather than exposed as product architecture; hardware scope follows MLX rather than a product-only Apple Silicon assumption. |

## Researched But Not Yet Converted

| Topic | Current status | Acceptance gate |
|---|---|---|
| Metric contract | PR0 settles the vector/missingness boundary; target-family metrics and calibration remain open. | Implement versioned metric manifests and named projections without replacing raw observations. |
| Typed copy/recoverability evidence | PR0 rejects one universal leakage scalar; implementation is not yet stable. | Freeze a finite versioned probe suite, nulls, power targets, channel thresholds, and trace-integrity checks. |
| Hosted black-box adapter | Implemented through the Next.js `/api/search` route with server-side OpenAI-compatible credentials and fallback configuration. | Keep returned candidates as `AlephRun` and mark observations `black_box`. |
| Stable model-internal evidence contract | Partially evidenced by local NLL, not product-stable. | Expose token NLL and related fields through a documented `ObservationSet` migration. |
| Deletion ablation / prompt-token attribution | UI-shaped, not real. | Compute from model internals or repeated behavioral probes and label source mode. |
| Persistence | Not chosen. | JSON import/export first; database only after saved-run workflow proves useful. |
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

1. Extend the merged finite bootstrap with the threshold/compiler statement map and independent checks.
2. Implement one PR0-conformant real-model search archive with separate proposal/evaluation roles,
   exact tokenizer accounting, fresh confirmation, a six-account ledger, and independent replay.
3. Reproduce MiniPrompt/ACR behind the same archive and evaluator boundary.
4. Add JSON import for `AlephRun` so the product remains file-first without confusing the projection
   with the scientific archive.
5. Promote hosted/Kaggle/Hugging Face evidence only after pinned artifact readback and offline replay.

## One-Sentence Status

Aleph has a stable thesis, repaired observed-frontier semantics, an exact finite/Lean bootstrap, product
model adapters, and a clear evidence boundary; the main unresolved work is a PR0-conformant real-model
archive/search algorithm, typed recoverability evidence, mandatory baselines, persistence, and
cross-platform replay.
