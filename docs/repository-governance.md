# Repository Governance

This note closes the first Hackathon pass and names the repository rules for the next phase. It is intentionally small: governance should remove ambiguity, not become a second product.

## Current repo state

Aleph has one durable product contract and two runnable frontend histories:

| Surface | Status | Rule |
|---|---|---|
| `web/` | active app | Current Next.js launch surface. Use this for product UI work unless a migration note says otherwise. |
| `apps/web/` | legacy/reference console | Vite console that proves the `AlephRun` workbench shape. Keep it as a reference until its useful pieces move into `web/` or it is archived. |
| `apps/api/` | active API boundary | Owns `/runs/fixture`, mock search, and the local MLX adapter wrapper. |
| `search/` | experimental local adapter | Real local-model spike. Keep claims scoped to the local setup and emitted receipts. |
| `packages/core` | stable-ish contract layer | Owns `AlephRun`, `CandidatePoint`, `ObservationSet`, metrics, leakage, and frontier helpers. |
| `packages/fixtures` | fixture data | Demo data only; never use fixture numbers as research evidence. |

The active UI path is temporarily outside the root npm workspace. That is acceptable for the current post-Hackathon state, but it should not remain implicit.

## Naming rules

- Project name: **Aleph**.
- Core object: `AlephRun`.
- Candidate terminology: **Shortest Found**, **Explicit Reconstruction**, and discrete `CandidatePoint` path.
- Mode terminology: `fixture`, `mock`, `simulated`, `black_box`, `white_box`.
- Avoid naming any candidate or adapter as globally shortest, proven, or white-box unless the data actually supports it.

## Path rules

- Put shared product contracts in `packages/core`, not inside a frontend app.
- Put stable demo data in `packages/fixtures`.
- Put temporary design receipts in `docs/archive/` only when they are no longer active contracts.
- Put agent handoffs in `docs/handoff/` only while they are still useful for coordination; summarize durable decisions elsewhere.
- Do not add new top-level app folders unless `docs/repository-shape.md` is updated in the same change.

## GitHub state

As of the post-Hackathon cleanup on 2026-05-18:

- PRs #2 through #7 are merged.
- PR #1 is closed.
- There are no open issues.
- `origin/codex/demo-readiness-contracts` and `origin/feat/launch-page-and-extreme-states` are merged into `origin/main` and may be deleted once no one needs their branch names.
- `codex/publish-aleph-explorer-update` contains the current Next.js launch update and should be merged or replaced by a mainline equivalent before the next product pass.

## Permission and claim rules

- Do not claim white-box observations without logits or model internals.
- Local MLX receipts may support local adapter behavior, not general model claims.
- Simulated token-loss, waveform, attribution, and exposure panels must remain visibly labeled.
- Security, support, conduct, and contribution files are minimal public-facing contracts; keep them short until the project has real external users.

## Next governance moves

1. Merge or close `codex/publish-aleph-explorer-update`.
2. Decide whether `web/` replaces `apps/web/`, or whether the Next.js app moves under `apps/web`.
3. Add `web/` to the root workspace only after deciding the app layout.
4. Convert active handoff notes into either `docs/strategy.md`, `docs/roadmap.md`, or issues, then archive stale handoffs.
5. Open a small set of issues for the next phase instead of keeping roadmap intent only in prose.
