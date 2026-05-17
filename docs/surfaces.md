# Surfaces

Use this file to prevent accidental overpromising.

| Surface | Status | Owner | Evidence | Notes |
|---|---|---|---|---|
| README entrypoint | stable | Maintainer | `README.md` | Short public description. |
| Project thesis | stable | Maintainer | `THESIS.md` | North star for product/research direction. |
| Core concept | stable | Maintainer | `docs/core-concept.md` | Separates settled, open, and deferred decisions. |
| Open questions | active | Maintainer | `docs/open-questions.md` | Unsettled choices and maintainer leanings. |
| State of play | active | Maintainer | `docs/state-of-play.md` | Current confidence map: settled, implemented, researched, open, and next. |
| Next backlog | active | Maintainer | `docs/next-backlog.md` | Issue-ready follow-up work with acceptance gates. |
| Repository shape | stable | Maintainer | `docs/repository-shape.md` | Local decision; template is reference, not law. |
| Repository governance | active | Maintainer | `docs/repository-governance.md` | Post-Hackathon cleanup rules for active paths, naming, branches, and claims. |
| Maintainer review | active | Maintainer | `docs/maintainer-review.md` | Current judgment and next best changes. |
| Strategy and fallbacks | active | Maintainer | `docs/strategy.md` | Current Hackathon/long-term path and fallback ladder. |
| Quality bar | active | Maintainer | `docs/quality-bar.md` | Review rules for language, code, and documentation. |
| AlephRun data contract | experimental | Maintainer | `packages/core/src/types.ts` | Expected to evolve by explicit migration or decision note. |
| JSON run schema | experimental | Maintainer | `schemas/aleph-run.schema.json` | Mirrors the fixture contract. |
| Fixture run | experimental | Maintainer | `packages/fixtures/src/sample-run.json` | Demo data, not model evidence. |
| Static console demo | archived | UI owner | `apps/web/static/aleph-atlas-console.html` | Prototype/reference surface kept as historical receipt. |
| Next.js launch surface | stable | UI owner | `web/app/page.tsx` | Current launch/demo app, started by `start.sh` on port 3000. |
| React/Vite console | archived | UI owner | `apps/web/src/main.tsx` | Legacy Hackathon console: fixture selector, mode select, API search wired, Pareto slider, token-loss panel, export. Archived as reference only. |
| FastAPI API | experimental | Backend owner | `apps/api/` | Mock generation/scoring and `/api/search` exist; local MLX search requires a separate `search/server.py` process. |
| Token loss / waveform / attribution panels | simulated fixture | UI/research owner | fixture observations | Useful UI behavior; not real model internals. |
| Local MLX search wrapper | experimental | Backend/research owner | `apps/api/aleph_api/services/local_mlx_search.py`, `search/server.py`, `npm run api:live-smoke` | Adapter boundary exists; real runs depend on local MLX setup and model availability. |
| White-box mode | experimental adapter output | Research owner | `search/aleph_search.py`, `search/server.py`, `apps/api/aleph_api/services/local_mlx_search.py` | Live local search can return token NLL for the explicit/right-end point and the API can label that response `white_box`; product panels are not integrated end-to-end. |
| ARCA/GCG adapters | future | Research owner | docs only | Not implemented. |
| Research prior art | stable notes | Maintainer | `docs/research/` | Framing and route selection, not implementation lock-in. |
| Archive | archived | Maintainer | `docs/archive/` | Receipts only; not product contract. |

## Status values

- `stable` — users or contributors may rely on it.
- `active` — live planning surface; not implementation evidence.
- `experimental` — feedback wanted; compatibility not promised.
- `reference` — useful prior implementation or fallback, but not the active product path.
- `simulated fixture` — intentionally fake or fixture-backed for UI demonstration.
- `stub` — visible placeholder; not implemented.
- `future` — planned or possible, no current implementation.
- `archived` — retained as historical receipt.
