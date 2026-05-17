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

- Keep the `/api/search` response contract aligned with `AlephRun`, review Account B live-search receipts, and decide whether any new runtime evidence changes docs or surface status.

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

- Run a real `local_mlx_search` round-trip through `apps/api`, capture the response shape and any recoverable failure, and tighten the adapter only where the live engine differs from the smoke-tested contract.

Acceptance gate:

- `mock` still works with no MLX installed.
- `local_mlx_search` documents how to start the local engine.
- API smoke tests show the route returns candidate points or a clear recoverable error.
- A live receipt, when MLX is available, names model, observation mode, candidate count, selected candidate, and whether token NLL was present.
- `npm run lint` passes.

## Account C: Web Console Integrator

Use this account for the active React/Vite console and user-facing workbench flow.

Owns:

- `apps/web/`
- `packages/ui/`
- UI-only fixture wiring from `packages/fixtures`
- visual mode labels, slider behavior, and panel composition

Rules:

- Do not touch `apps/api/` or `search/`.
- Do not invent a parallel run shape; consume `AlephRun`, `CandidatePoint`, and `ObservationSet`.
- Keep UI-facing adapters thin: display labels, selected-candidate state, fixture selection, and panel composition are okay; new data semantics belong in Account A/D before UI use.
- Isolate API/export calls behind a web client boundary instead of mixing transport code into visual components.
- Keep fixture, mock, simulated, black-box, and white-box labels visible.
- Preserve `Shortest Found` and `Explicit Reconstruction` as distinct endpoints.
- Empty observation arrays should render honest "unavailable for this mode" states rather than implying failed or missing evidence.
- Do not add dependencies unless the existing app cannot express the interaction without them.

Current best task:

- Keep the console split around the existing `AlephRun` path: `main.tsx` as mount/bootstrap, a console composition component, a run-state hook, a thin run client, and display helpers.

Start when:

- Immediately, if working only from fixtures.
- After Account A names a stable endpoint, if wiring live API calls.

Stop and converge when:

- UI needs a new field in `AlephRun`.
- API behavior differs from the fixture shape.
- The console can no longer run with fixture data alone.

Acceptance gate:

- `npm run lint` passes.
- Fixture-only console still renders the compression path.
- Any API integration has a fixture fallback and visible mode label.
- Components can be simplified or removed without changing the `AlephRun` contract or backend route behavior.

## Account D: Run Artifact and Fixture Steward

Use this account for sample runs, schemas, JSON import/export, and contract checks.

Owns:

- `packages/fixtures/`
- `schemas/`
- `packages/core/src/*` helper checks, except API-driven type changes owned by Account A
- `scripts/check-*.mjs` when validating contract behavior

Rules:

- Do not change product theory to fit fixture data.
- Mark sample, fixture, mock, and simulated values clearly.
- Keep generated or measured demo outputs separate from hand-authored contract fixtures.
- Coordinate with Account A before changing `packages/core/src/types.ts`.

Current best task:

- Add a second small `AlephRun` fixture with a different target style, then validate it against the schema/check scripts.

Start when:

- Immediately, as long as `packages/core/src/types.ts` is unchanged.
- After Account A lands a contract migration, if schema or fixture fields need alignment.

Stop and converge when:

- A fixture needs a new field or enum value.
- A schema change would force UI/API edits.
- A check starts requiring optional runtime dependencies.

Acceptance gate:

- `npm run lint` passes without frontend or model installs.
- Fixture values remain explicitly non-evidence unless generated by a documented run.
- Schema, fixtures, and core helper checks agree.

## Account E: Demo Narrative and Verification Reviewer

Use this account for public demo flow, verification notes, and claim hygiene.

Owns:

- `DEMO.md`
- `docs/verification.md`
- `docs/checks.md`
- review notes on `README.md` when demo claims drift from implementation

Rules:

- Prefer tightening claims over adding new features.
- Do not claim real model evidence unless the artifact and command receipt exist.
- Keep fallback language explicit: fixture-only, mock API, local MLX, hosted black-box, or white-box.
- Do not rewrite architecture decisions; point to Account A when a decision is needed.

Current best task:

- Reconcile the demo script with the current repository paths and active surfaces, then record the latest lint/check output.

Start when:

- After Account B has either a working route or a clear recoverable failure mode.
- Earlier, if the demo script is blocking parallel contributors from knowing what is true.

Stop and converge when:

- A demo claim depends on unmerged API/search work.
- README or thesis language would need to change.
- Verification needs evidence from a branch you cannot run.

Acceptance gate:

- Demo steps match runnable repository paths.
- Verification names exactly which checks ran and what they do not prove.
- No fixture or simulated observation is framed as model-internal evidence.

## Account F: Core Utility and Scoring Guard

Use this account for small pure-code improvements that protect scoring, leakage, frontier, and candidate ordering behavior.

Owns:

- `packages/core/src/metrics.ts`
- `packages/core/src/leakage.ts`
- `packages/core/src/frontier.ts`
- `packages/core/src/candidates.ts`
- focused helper checks in `scripts/`

Rules:

- Keep helpers pure and dependency-free.
- Do not add model runtime, HTTP, React state, or fixture-specific shortcuts.
- Treat scoring as UI ordering unless Account A promotes a service-level objective.
- Do not change `types.ts` without Account A coordination.

Current best task:

- Expand lightweight checks around leakage edge cases, explicit reconstruction, and frontier ties.

Start when:

- Immediately, if changing only pure helpers and checks.

Stop and converge when:

- A scoring change would alter API response semantics.
- A helper starts encoding product assumptions not already present in docs.
- Tests disagree with fixture expectations.

Acceptance gate:

- `npm test` and `npm run lint` pass.
- Helper behavior remains explainable from `docs/quality-bar.md` and `docs/strategy.md`.

## Account G: Terminology and Claim Guard

Use this account for glossary coverage, claim hygiene, and lightweight language checks that do not require API, UI, fixture, or helper changes.

Owns:

- `docs/glossary.md`
- `docs/claim-ledger.md`
- language-only guardrails in `docs/quality-bar.md`
- focused terminology checks in `scripts/check-*.mjs`

Rules:

- Do not change product theory; preserve the terms already settled in `THESIS.md` and `docs/core-concept.md`.
- Do not touch `apps/`, `packages/core/`, `packages/fixtures/`, or `schemas/`.
- Do not rewrite demo narrative or verification receipts; point Account E at drift instead.
- Keep checks lightweight and dependency-free.
- Prefer catching overclaims and missing canonical terms over enforcing writing style.

Current best task:

- Maintain a claim ledger that maps settled claims to evidence and drift owners, then keep terminology checks aligned with that ledger.

Start when:

- Immediately, if the change is documentation/check-only and avoids account-owned implementation paths.

Stop and converge when:

- A term needs a new product meaning.
- A claim depends on model/runtime evidence.
- A check would force large copy rewrites outside glossary or quality-bar language.

Acceptance gate:

- `npm run lint` passes.
- Glossary covers the settled Aleph terms used by contributors.
- Claim ledger identifies evidence and account ownership for public claims.
- Active docs keep forbidden claims either absent or explicitly framed as limitations.

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

- Account A keeps `main` coherent and resolves contract conflicts.
- Account B works the local-search/API adapter path in one focused branch.
- Accounts C, D, E, F, and G can run in parallel if they stay inside their ownership boundaries.
- Account G absorbs terminology and overclaim drift before Account E turns implementation state into demo narrative.
- Collaborator reviews PR descriptions, demo claims, and handoff summaries only when the route is clear.
- If two branches touch the same file, Account A resolves the order.

## Parallel Work Windows

Use these windows to decide when to start work rather than waiting for every other account.

| Window | Accounts | Good work | Wait for convergence when |
|---|---|---|---|
| Now | C, D, F, G | fixture UI polish, fixture/schema checks, pure helper checks, terminology guardrails | a change needs `types.ts`, API fields, or product-theory changes |
| After A names the API boundary | B, C, D | route implementation, API wiring, schema alignment | route responses drift from `AlephRun` |
| After B has a smoke result | C, E | API fallback UI, demo script, verification notes | smoke output is unclear or unmerged |
| Demo freeze | A, C, E | final route choice, claim audit, fallback rehearsal | any claim depends on unavailable runtime |

## Convergence Gates

Converge immediately when one of these happens:

- `packages/core/src/types.ts` needs to change.
- An endpoint returns data that cannot map cleanly to `AlephRun`.
- UI code needs to know whether data is fixture, mock, black-box, white-box, or simulated but the source does not say.
- `npm run lint` fails on a branch that is otherwise ready.
- Demo language claims real search, logits, token loss, or model internals without a command receipt.

## Merge Order

Prefer this order when multiple branches are ready:

1. Account F pure helper checks.
2. Account D fixtures and schema alignment.
3. Account G terminology and claim guardrails.
4. Account B adapter route.
5. Account A contract review and integration.
6. Account C UI wiring to the stable contract.
7. Account E demo and verification cleanup.

This order keeps low-risk contract protections under the higher-risk runtime work, then lets narrative follow evidence.
