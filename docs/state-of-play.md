# State of Play

This is the current confidence map for Aleph after the Hackathon and research pass. Use it when asking: what is true, what is implemented, what is only researched, and what should happen next?

## Core hypothesis

Aleph starts from a modern model-output surface and runs the prompt problem backward:

```text
given target output y
and fixed model / decoding / metric / budget
search for the shortest known prompt coordinates
that reproduce or approximate y
then show the path back to explicit reconstruction
```

This is a product/research hypothesis with enough evidence to build around, but not enough evidence to claim a global optimum or universal theory of shortest prompts.

## What Is Settled

| Claim | Confidence | Why |
|---|---:|---|
| Aleph is a reverse prompt compression workbench, not a prompt-polishing assistant. | high | Settled in `THESIS.md`, `docs/core-concept.md`, and `docs/claim-ledger.md`. |
| The right baseline is **Explicit Reconstruction**. | high | It makes leakage visible and prevents context-window length from becoming a fake endpoint. |
| The left endpoint is **Shortest Found**, not "the shortest possible prompt." | high | The search is model-relative, metric-bound, and budget-bound. |
| `AlephRun` is the exchange contract. | high | Types, schema, fixtures, API adapter, and UI surfaces converge on it. |
| Fixture and simulated observations must be labeled. | high | This is a repository rule and a product honesty rule. |
| White-box claims require logits or model internals. | high | Research and verification agree; local MLX NLL can support adapter output, not broad product claims. |

## What Is Implemented

| Area | Current state | Source |
|---|---|---|
| Active launch UI | Next.js app in `web/`, started by `start.sh`. | `web/app/page.tsx`, `start.sh` |
| Reference workbench UI | Vite/React console remains as a reference and fallback. | `apps/web/src/main.tsx` |
| Run contract | `AlephRun`, candidates, observations, metrics, leakage, frontier helpers. | `packages/core/src/types.ts`, `schemas/aleph-run.schema.json` |
| Fixtures | Multiple demo runs with explicit fixture/simulated modes. | `packages/fixtures/src/` |
| API boundary | FastAPI mock route and local MLX adapter wrapper. | `apps/api/` |
| Local live search spike | MLX/Qwen route can produce AlephRun-compatible adapter output when local setup is running. | `search/`, `docs/verification.md` |
| Repo checks | Lightweight lint/check suite protects claims, fixtures, links, language, and schema. | `npm run lint` |

## Research Converted Into Product Shape

| Research input | Converted into |
|---|---|
| p-to-q file-first repository discipline | Artifact-first repo, small docs map, lightweight checks, sparse decisions. |
| ARCA / Reversing LLMs direction | Treated as proof that reverse prompt search is a real implementation route, not a v0 identity. |
| GCG / nanoGCG direction | Parked as a future hard-prompt adapter, not product positioning. |
| vec2text / embedding inversion | Recorded as adjacent inversion work, explicitly not Aleph's core task. |
| Aquin-style instrumentation | Inspired token loss, attribution, exposure, eval, and observation panels, with mode labels. |
| Local MLX spike | Wrapped behind `apps/api` as experimental adapter evidence rather than exposed as product architecture. |

## Researched But Not Yet Converted

| Topic | Current status | Acceptance gate |
|---|---|---|
| Default metric | Researched and discussed, not settled. | Choose composite/exact/embedding/judge strategy and record the decision. |
| Non-leaking mode | Concept settled, enforcement not stable. | Define copy-ratio/ngram/entity thresholds and test them. |
| Hosted black-box adapter | Planned route, not implemented. | Return real model candidates as `AlephRun` without UI-specific shapes. |
| Stable white-box observation contract | Partially evidenced by local NLL, not product-stable. | Expose token NLL and related fields through a documented `ObservationSet` migration. |
| Deletion ablation / prompt-token attribution | UI-shaped, not real. | Compute from model internals or repeated behavioral probes and label source mode. |
| Persistence | Not chosen. | JSON import/export first; database only after saved-run workflow proves useful. |
| Permanent frontend path | Open after Hackathon. | Decide whether `web/` remains active, moves under `apps/web`, or replaces the Vite console. |

## Interface Cleanliness

The interface story is understandable but still split across two histories:

- `web/` is the current launch/demo surface.
- `apps/web/` is the earlier contract-driven console and should be treated as reference until migrated or archived.
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

The next phase should not start with heavier theory or more routes. It should start with one stabilizing product pass:

1. Decide and document the permanent frontend path.
2. Make the active UI show the compression path and evidence modes more plainly than the launch shell does today.
3. Add JSON import for `AlephRun` so the repo becomes file-first in the product, not only in docs.
4. Add a hosted black-box adapter spike only after the UI and `AlephRun` path are unambiguous.
5. Turn the remaining researched-but-not-converted items into issues or small plans.

## One-Sentence Status

Aleph has a stable thesis, a credible run contract, fixture and local-adapter evidence, and a clear honesty layer; the main unresolved work is choosing the permanent frontend path and converting researched routes into one small real-run loop.
