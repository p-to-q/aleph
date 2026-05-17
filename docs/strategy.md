# Strategy

This file records the maintainer-level path decision after the final review pass. It is intentionally practical: keep the current main line strong, define fallbacks, and leave room for ambition without letting speculation become product fact.

## Current global optimum

The best current path is:

```text
frontend-led console
  -> shared AlephRun contract
  -> fixture-backed candidate path
  -> clear slider / prompt / output loop
  -> secondary observation panels
  -> JSON import/export
  -> black-box adapter
  -> white-box scoring when logits are available
```

This path maximizes the chance of a Hackathon demo that works while preserving the long-term research surface.

## Why this is better than model-first

A model-first build can fail for reasons unrelated to the product thesis: runtime setup, hardware, latency, tokenization, model quality, API access, cost, or prompt search instability.

A console-first build proves the interaction before the runtime is chosen. It also forces all later adapters to speak the same `AlephRun` contract instead of leaking provider-specific shapes into the UI.

## Hackathon line

### Primary route

Ship the console with fixture data and clear fixture labels.

Must be visible:

- target output input;
- compression slider over candidate points;
- current prompt and model output;
- metrics for length, fit, stability, compression, leakage, and NLL when available;
- Pareto frontier;
- token loss;
- search dial;
- waveform;
- attribution;
- exposure vectors;
- eval suite.

### Fallback ladder

Use the first fallback that preserves the thesis.

| Risk | Fallback | What remains true |
|---|---|---|
| Legacy console review needed | Inspect `apps/web/static/aleph-atlas-console.html` | The historical visual thesis is still demonstrable. |
| Model runtime fails | Use `packages/fixtures/src/sample-run.json` | The compression path and UI contract still work. |
| Real scoring is noisy | Mark scoring as `mock` or `fixture` | The honesty layer remains intact. |
| Token loss is unavailable | Show simulated token-loss panel with visible mode label | The panel shape is validated without white-box claims. |
| Search produces weak candidates | Keep explicit reconstruction plus heuristic candidates | The endpoints and slider semantics remain correct. |
| Demo time is short | Show one polished Borges-coordinate run | The product identity is stronger than a broad but fragile demo. |

### Hackathon non-goals

- No global-shortest claim.
- No hidden white-box claims.
- No production account system.
- No database unless JSON export/import is already stable.
- No ARCA/GCG integration unless it is isolated behind an adapter boundary.

## Long-term line

### v1: Black-box workbench

- Real model adapter behind API boundary.
- Candidate generation and scoring services.
- Repeated sampling for stability.
- Leakage scoring.
- JSON import/export and saved run files.

### v2: White-box probability microscope

- Teacher-forced likelihood for models with logits.
- Token-level target loss.
- Deletion ablation.
- Prompt-token attribution.
- Loss curves from real search steps.

### v3: Search adapters

- ARCA-style length scanning.
- GCG/nanoGCG-style hard prompt optimization.
- Evolutionary or beam-style prompt search.
- Probe-sampling-inspired acceleration.
- Adapter comparison in the same `AlephRun` shape.

### v4: Research product

- Cross-model transfer.
- Non-leaking benchmark suite.
- Run gallery.
- Exported research cards.
- Batch mode for output families.

## Small modifications worth doing next

These are local optima that improve the whole system without forcing hard product decisions:

1. ~~Split `apps/web/src/main.tsx` into components.~~ Done: `main.tsx` is now a pure composition layer; logic lives in `useAlephRun`, `runClient`, `runView`.
2. Add run JSON import (export already ships).
3. ~~Add a mock `/runs` API that returns the fixture shape.~~ Done: `/runs/fixture` returns `sample-run.json`.
4. Add tiny tests for `paretoFrontier`, `leakageScore`, and `compressionRatio`.
5. ~~Add a visible mode badge to every observation panel.~~ Done: every `Panel` carries an `observationBadge`.
6. ~~Add one second fixture with a different target style.~~ Done: `gettysburg-run.json` (Lincoln) and `non-leaking-run.json` ship alongside the Borges fixture.
7. Add a candidate comparison view before adding any heavy search backend.

## Decision gates

A new feature should pass at least one gate:

- It makes the compression path clearer.
- It makes the artifact more runnable.
- It protects against overclaiming.
- It keeps future adapters interchangeable.
- It gives human/agent contributors a smaller next change.

If a change does none of these, defer it.
