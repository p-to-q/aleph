# PR Draft: Account C UI Boundary and Console Hardening

## Title

`[codex] Harden Account C web console boundary`

## Summary

This PR hardens the React/Vite console around the existing `AlephRun` contract
without adding a new product data model, backend route, search strategy, or UI
dependency.

The main change is structural: the web console now has a clearer boundary
between bootstrapping, run state, API/export transport, display formatting, and
visual panels. This makes the UI easier to simplify later, because features can
be removed from panel composition without rewriting the run contract or touching
`apps/api`, `search`, fixtures, or schemas.

It also makes observation modes more honest in the UI. Fixture, mock,
simulated, black-box, and white-box modes remain visible. Missing observation
arrays render explicit "unavailable for this observation mode" states instead
of blank panels. White-box token NLL, when present in `observations.tokenLoss`,
is surfaced as token-loss data without implying that unrelated panels such as
waveform or attribution are real model internals.

## Why

Account C owns the active React/Vite console, panel composition, visual mode
labels, fixture UI, and slider behavior. The next phase will likely involve
large UI maintenance and feature simplification, so the console needs a stable
interface layer before more visual churn.

Before this work, `main.tsx` had several responsibilities mixed together:

- app bootstrap;
- fixture selection;
- selected candidate state;
- API search fetch;
- JSON export;
- display formatting;
- top-bar composition;
- primary console layout;
- panel orchestration.

That made every UI change feel larger than necessary. This PR separates those
responsibilities while preserving the same `AlephRun -> CandidatePoint ->
ObservationSet` path.

## Files Changed

### `apps/web/src/main.tsx`

Reduced to app bootstrap:

- imports `AlephConsole`;
- calls `useAlephRun()`;
- mounts the app into `#root`.

This keeps `main.tsx` stable and makes future UI restructuring happen in
components or the run-state hook instead of the entrypoint.

### `apps/web/src/components/AlephConsole.tsx`

New console composition component.

Owns the page-level UI assembly:

- `RunHeader`;
- error bar;
- `TargetPanel`;
- `ParetoFrontier`;
- `PromptOutputPanel`;
- `ObservationPanels`.

It receives a `UseAlephRunState` object and passes only the relevant props to
each panel. This creates a clear boundary between state management and visual
composition.

### `apps/web/src/components/RunHeader.tsx`

New top-bar component.

Owns:

- brand mark;
- run mode strip;
- fixture selector;
- search mode selector.

It displays:

- observation mode label;
- token NLL indicator when white-box token-loss data is present;
- leakage/search mode;
- model label.

### `apps/web/src/lib/useAlephRun.ts`

New React hook for run state.

Owns:

- active fixture index;
- active `AlephRun`;
- selected candidate id;
- loading/error state;
- selected search mode;
- target textarea ref;
- fixture switching;
- candidate selection;
- API-backed generation.

It also aborts a previous in-flight search before starting a new one, so quick
Generate clicks do not race stale responses into the UI.

Exports:

- `fixtureOptions`;
- `FixtureOption`;
- `UseAlephRunState`.

### `apps/web/src/lib/runClient.ts`

New web client boundary.

Owns:

- `AppMode`;
- `searchRun(targetText, mode, signal)`;
- `exportRun(run)`.

This keeps fetch, API base URL, abort signals, blob creation, and download
behavior out of visual components.

### `apps/web/src/lib/runView.ts`

New UI display adapter for `AlephRun`, `CandidatePoint`, and `ObservationSet`.

Owns display-only helpers:

- percent formatting;
- mode label formatting;
- observation captions;
- token-loss summary;
- selected candidate lookup;
- selected candidate index;
- endpoint label;
- candidate summary;
- candidate rank;
- slider progress;
- Pareto plot positioning.

This is intentionally not a business-logic layer. It does not define new
product semantics or mutate the run contract.

### `apps/web/src/components/ParetoFrontier.tsx`

Uses `runView` helpers instead of embedding display logic directly in JSX.

Keeps the required distinction between:

- `Shortest Found`;
- intermediate `Compression Path`;
- `Explicit Reconstruction`.

Also keeps discrete candidate navigation via:

- plot dots;
- candidate ribbon;
- range slider.

### `apps/web/src/components/TargetPanel.tsx`

Uses display helpers for observation captions and run mode labels.

Keeps fixture/mock/live status visible near the target input.

### `apps/web/src/components/PromptOutputPanel.tsx`

Uses display helpers for rank and percent formatting.

Keeps current prompt, output, token count, compression, leakage, and candidate
note visible for the selected candidate.

### `apps/web/src/components/ObservationPanels.tsx`

Adds explicit unavailable states for missing observation arrays.

Panels now render a clear no-data state when data is absent:

- token loss;
- waveform;
- attribution;
- loss curve;
- compression exposure;
- eval suite.

Token loss now includes a small summary when token-loss data exists:

- count;
- average loss;
- max loss.

When `observations.mode === "white_box"` and token loss is present, the panel
labels it as token NLL from local adapter output. This reflects the live MLX
receipt without claiming that every observation panel is white-box complete.

### `apps/web/src/styles.css`

Adds styles for:

- candidate ribbon that adapts to fixture candidate counts;
- slider status;
- prompt metadata chips;
- run strip;
- no-data states;
- token-loss summary chips.

### `docs/handoff/account-dispatch.md`

Tightens Account C boundaries:

- Account C may own display labels, selected-candidate state, fixture
  selection, and panel composition.
- New data semantics belong in Account A/D before UI use.
- API/export calls should stay behind a web client boundary.
- Empty observations should render honest unavailable states.
- Components should remain removable without changing `AlephRun` or backend
  route behavior.

### `docs/handoff/2026-05-17-api-wiring.md`

Updates remaining risks and next steps:

- documents that API-sourced runs may omit some observation arrays;
- notes that React now renders no-data states instead of blank panels;
- shifts Account C's next task toward keeping UI state/display mapping isolated
  in `apps/web/src/lib/`.

### `docs/handoff/2026-05-17-account-c-ui-pr-draft.md`

This PR draft.

It exists because the local `/Users/dujiayi/code/aleph` directory currently has
no `.git` metadata or remote, so Codex cannot commit, push, or open a GitHub PR
from this workspace.

## Relationship to Live MLX Round Trip

Account B has a live MLX receipt in
`docs/handoff/2026-05-17-live-mlx-receipt.md`.

That receipt supports this claim:

```text
apps/api can adapt a live local MLX search response into an AlephRun-compatible
white_box response.
```

Observed receipt details:

- model: `mlx-community/Qwen3-1.7B-4bit`;
- observation mode: `white_box`;
- candidate count: `3`;
- selected candidate id: `search-point-3`;
- token NLL present: `true`.

This PR responds to that receipt on the UI side by:

- rendering `white_box observations`;
- showing a token NLL top-bar indicator when token-loss data exists;
- rendering token-loss summary chips;
- keeping unrelated missing panels in "unavailable for this observation mode"
  states.

This PR does not claim:

- globally shortest prompt;
- production-ready local MLX search;
- complete white-box UI;
- real waveform, attribution, exposure, or eval data unless the run provides
  those arrays.

## Account Boundary

This is Account C work.

In scope:

- `apps/web/src`;
- UI composition;
- run-state hook;
- web client wrapper for UI transport;
- display helpers for existing run fields;
- Account C handoff/boundary documentation.

Out of scope:

- `apps/api` behavior changes;
- `search` behavior changes;
- `packages/core/src/types.ts` contract migration;
- fixture/schema edits;
- scoring/leakage/frontier helper changes;
- new dependencies;
- new routes;
- new product claims.

## Validation

Commands run:

```bash
npm --workspace apps/web run build
npm run lint
```

Observed results:

```text
npm --workspace apps/web run build: ok
npm run lint: ok
```

Additional local service check:

```bash
curl -sS http://127.0.0.1:8010/runs/fixture
```

Observed result:

```text
apps/api on port 8010 returned fixture-shaped JSON.
```

Local MLX search server status during this PR draft:

```text
127.0.0.1:8000 was not listening in this shell.
```

So this PR relies on Account B's existing live receipt rather than rerunning the
MLX model path from Account C.

## Risks

- The workspace is not a Git checkout, so this draft has not been committed or
  pushed from Codex.
- The React console has API wiring, but local MLX visual verification still
  needs a running `search/server.py` and API configured with
  `ALEPH_MLX_SEARCH_URL`.
- White-box token loss is now visible when present, but white-box completeness
  is not implied.
- The UI still uses local `apps/web` components. Moving stable shells into
  `packages/ui` should wait until the visual API settles.
- Historical handoff notes may mention earlier file ownership before this
  refactor. The active Account C boundary is now documented in
  `docs/handoff/account-dispatch.md`.

## Suggested Review Focus

Reviewers should check:

- Does `main.tsx` remain only bootstrap?
- Is transport isolated in `runClient.ts`?
- Is run state isolated in `useAlephRun.ts`?
- Are display-only transformations isolated in `runView.ts`?
- Do panels still consume `AlephRun`, `CandidatePoint`, and `ObservationSet`
  rather than inventing a parallel shape?
- Do no-data states preserve honesty without implying backend failure?
- Does the UI preserve `Shortest Found` and `Explicit Reconstruction`?
- Does the white-box token NLL indicator avoid overclaiming?

## Suggested PR Body

```markdown
## Summary

- Split the React console into a stable composition layer, run-state hook, web
  client boundary, and display helpers.
- Added visible unavailable states for missing observation arrays.
- Surfaced white-box token NLL only when token-loss data is present.
- Tightened Account C handoff boundaries for future UI maintenance.

## Why

The next UI phase may simplify or replace panels. This keeps the interface layer
stable so UI changes do not rewrite the run contract, API route behavior, or
fixture/schema ownership.

## Validation

- `npm --workspace apps/web run build`
- `npm run lint`

## Notes

- Account B's live MLX receipt shows a white-box, token-NLL-present response can
  be adapted by `apps/api`.
- This PR does not claim complete white-box UI support or production search
  readiness.
```

## Next Step

If a real Git remote is available, create a branch such as:

```bash
git checkout -b codex/account-c-ui-boundary
```

Then stage this Account C scope explicitly:

```bash
git add \
  apps/web/src/main.tsx \
  apps/web/src/components/AlephConsole.tsx \
  apps/web/src/components/RunHeader.tsx \
  apps/web/src/components/ObservationPanels.tsx \
  apps/web/src/components/ParetoFrontier.tsx \
  apps/web/src/components/PromptOutputPanel.tsx \
  apps/web/src/components/TargetPanel.tsx \
  apps/web/src/lib/runClient.ts \
  apps/web/src/lib/runView.ts \
  apps/web/src/lib/useAlephRun.ts \
  apps/web/src/styles.css \
  docs/handoff/account-dispatch.md \
  docs/handoff/2026-05-17-api-wiring.md \
  docs/handoff/2026-05-17-account-c-ui-pr-draft.md
```

Commit:

```bash
git commit -m "harden account c web console boundary"
```

Open a draft PR with the suggested body above plus this handoff as supporting
detail.
