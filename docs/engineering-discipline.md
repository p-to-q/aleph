# Engineering Discipline

Aleph should be developed as a careful research product, not as an accumulation of impressive-looking panels.

## Core stance

The repository is the source of truth. Chat history, screenshots, and prototype HTML are useful receipts, but durable behavior must live in code, docs, fixtures, tests, schemas, and ADRs.

## Change rules

- Make the smallest effective change.
- Read nearby code and docs before editing.
- Match local patterns before importing new frameworks or abstractions.
- Do not add a route, panel, dependency, or workflow just to signal seriousness.
- Do not represent mock, fixture, or simulated observations as real model internals.
- Keep business logic in `packages/core` or service layers, not hidden inside UI components.
- Prefer explicit data contracts over implicit prop shapes.
- If a change affects the public product definition, data contract, repository shape, license, security, or workflow, update docs and consider a decision note.

## Validation rules

State exactly what was run. Do not claim tests, builds, or research checks passed unless they did.

Preferred order:

1. narrow fixture or schema check;
2. type/lint check when dependencies are available;
3. repository lint;
4. build check;
5. manual UI review;
6. research/source review when claims changed.

## Experimental surfaces

Experimental code is allowed. Unmarked experimental code is not. Use `docs/surfaces.md` and fixture labels to keep this clear.

## Design rule

The main product line is:

```text
Target Output -> Compression Path -> Current Prompt -> Model Output -> Observations
```

Every UI panel should support that line. Panels that do not support it should stay archived or deferred.
