# Surfaces

Use this file to prevent accidental overpromising.

| Surface | Status | Owner | Evidence | Notes |
|---|---|---|---|---|
| README entrypoint | stable | Maintainer | `README.md` | Short public description. |
| Project thesis | stable | Maintainer | `THESIS.md` | North star for product/research direction. |
| Core concept | stable | Maintainer | `docs/core-concept.md` | Separates settled, open, and deferred decisions. |
| Open questions | active | Maintainer | `docs/open-questions.md` | Unsettled choices and maintainer leanings. |
| Repository shape | stable | Maintainer | `docs/repository-shape.md` | Local decision; template is reference, not law. |
| Maintainer review | active | Maintainer | `docs/maintainer-review.md` | Current judgment and next best changes. |
| Strategy and fallbacks | active | Maintainer | `docs/strategy.md` | Current Hackathon/long-term path and fallback ladder. |
| Quality bar | active | Maintainer | `docs/quality-bar.md` | Review rules for language, code, and documentation. |
| AlephRun data contract | experimental | Maintainer | `packages/core/src/types.ts` | Expected to evolve by explicit migration or decision note. |
| JSON run schema | experimental | Maintainer | `schemas/aleph-run.schema.json` | Mirrors the fixture contract. |
| Fixture run | experimental | Maintainer | `packages/fixtures/src/sample-run.json` | Demo data, not model evidence. |
| Static console demo | experimental | UI owner | `apps/web/static/aleph-atlas-console.html` | Prototype/reference surface. |
| React console | experimental | UI owner | `apps/web/src/main.tsx` | Source scaffold. Requires install/build validation before relying on it. |
| FastAPI API | stub | Backend owner | `apps/api/` | Skeleton only. No model calls yet. |
| Token loss / waveform / attribution panels | simulated fixture | UI/research owner | fixture observations | Useful UI behavior; not real model internals. |
| White-box mode | stub | Research owner | docs only | Requires logits/model internals. |
| ARCA/GCG adapters | future | Research owner | docs only | Not implemented. |
| Research prior art | stable notes | Maintainer | `docs/research/` | Framing and route selection, not implementation lock-in. |
| Archive | archived | Maintainer | `docs/archive/` | Receipts only; not product contract. |

## Status values

- `stable` — users or contributors may rely on it.
- `active` — live planning surface; not implementation evidence.
- `experimental` — feedback wanted; compatibility not promised.
- `simulated fixture` — intentionally fake or fixture-backed for UI demonstration.
- `stub` — visible placeholder; not implemented.
- `future` — planned or possible, no current implementation.
- `archived` — retained as historical receipt.
