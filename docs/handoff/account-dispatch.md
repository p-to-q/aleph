# Account Dispatch

This document is the current multi-agent split for Aleph. It exists so parallel work stays reviewable and does not create hidden product contracts.

## Maintainer call

The next non-UI line to push is:

```text
search/ live MLX engine -> apps/api adapter -> AlephRun-compatible response
```

`search/` is the strongest research/demo engine. `apps/api` is the stable product surface. The right move is to wrap the former behind the latter.

## Account A: API and Research Steward

Use this account for architecture, API contract, repo hygiene, research framing, and PR integration.

Owns:

- `apps/api/`
- `packages/core/src/types.ts` when API contracts need alignment
- `docs/research/`
- `docs/plans/`
- `docs/decisions/`
- PR review, merge sequencing, and route arbitration

Rules:

- Keep `apps/api` as the product-facing API.
- Treat `search/` as an engine or adapter, not as a second product contract.
- Do not make large UI changes except compatibility hooks.
- Do not strengthen theory claims beyond model-relative, budget-bounded upper bounds.
- Preserve `fixture`, `mock`, `black_box`, `white_box`, and `simulated` labels.
- Run `npm run lint` after repo changes.

Current best task:

- Define the `local_mlx_search` adapter boundary and review the implementation from Account B.

## Account B: Local Search Adapter Implementer

Use this account for non-UI backend implementation after any external account setup is done.

Owns:

- `search/` only where needed to expose a cleaner callable engine
- `apps/api/aleph_api/adapters/`
- `apps/api/aleph_api/services/`
- narrow API models required for `local_mlx_search`
- tests or smoke scripts for the new route

Rules:

- Do not touch `web/` or `apps/web/`.
- Do not change repository theory or roadmap except for a short implementation note if needed.
- Do not add a database.
- Do not require MLX to be installed for `mode=mock` or repo lint to pass.
- Keep local MLX failures recoverable and explicit.
- Return data that can be mapped to `AlephRun`, `CandidatePoint`, and `ObservationSet`.

Current best task:

- Add a `local_mlx_search` adapter or service behind `apps/api`, probably as `POST /api/search` or `POST /api/run`, without changing the frontend.

Acceptance gate:

- `mock` still works with no MLX installed.
- `local_mlx_search` documents how to start the local engine.
- API smoke tests show the route returns candidate points or a clear recoverable error.
- `npm run lint` passes.

## Collaborator: Synthesis and Demo Reviewer

Use collaborators for summaries, demo route checks, and review notes.

Owns:

- reviewing PR descriptions and demo claims
- checking `DEMO.md`, `README.md`, and `docs/verification.md`
- summarizing what changed after each merge
- filing follow-up issues or notes when implementation and narrative drift

Rules:

- Prefer comments and summaries over code changes.
- Do not rewrite architecture or research claims without pointing to the relevant file.
- Call out overclaiming, hidden mock values, and UI/API contract drift.

## Human Maintainer

Owns final product judgment:

- which demo route to present;
- when to merge;
- whether a route graduates from experiment to product surface;
- whether a new dependency or deployment path is acceptable.

## Coordination Rhythm

- Account A keeps `main` coherent.
- Account B works in a focused branch and opens one small PR.
- Collaborator reviews the PR and updates summary docs only when the route is clear.
- If two branches touch the same file, Account A resolves the order.
