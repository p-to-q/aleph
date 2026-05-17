# Handoff: API Wiring — 2026-05-17

## Objective

Wire `apps/web` frontend to `apps/api`, making the "Generate Compression Path" button actually call the search API.

## Files touched

- `apps/web/src/main.tsx` — React state for run, mode select, loading/error, `searchRun()` fetch, `exportRun()` download
- `apps/web/src/components/TargetPanel.tsx` — textarea ref, generate/export buttons with loading state, mode caption
- `apps/web/src/components/ParetoFrontier.tsx` — candidate-ribbon pills, slider-status, mode badge
- `apps/web/src/components/PromptOutputPanel.tsx` — prompt-meta tokens/compression/leak chips
- `apps/web/src/components/ObservationPanels.tsx` — mode badge on every panel
- `apps/web/src/styles.css` — error-bar, mode-select, button-row, candidate-ribbon, slider-status, prompt-meta, topbar-right
- `apps/web/.env.local` — `VITE_API_BASE=http://127.0.0.1:8010`
- `apps/api/aleph_api/main.py` — added CORS middleware, `/runs/fixture` endpoint
- `apps/api/pyproject.toml` — added `[project.optional-dependencies] test = ["pytest","httpx"]`
- `apps/api/tests/test_scoring.py` — pytest tests for scoring functions + `/runs/fixture` endpoint

## Validation

- `npm run build` — passes (204 kB JS bundle)
- `npm run lint` — all 8 checks pass
- `PYTHONPATH=apps/api apps/api/.venv/bin/python apps/api/smoke.py` — passes

## How to run end-to-end (mock mode, no model needed)

```bash
# Terminal 1: API
cd /Users/dujiayi/code/aleph
PYTHONPATH=apps/api apps/api/.venv/bin/python -m uvicorn aleph_api.main:app --app-dir apps/api --port 8010

# Terminal 2: Frontend
npm run dev
# → http://localhost:5173
```

Paste any text, select "mock" mode, click "Generate Compression Path". The UI will swap from fixture data to live mock results with proper mode labels.

## How to run with local MLX search

```bash
# Terminal 1: MLX search engine
source search/.venv/bin/activate
python3 search/preflight.py
python3 search/server.py   # → http://localhost:8000

# Terminal 2: API (pointing at search engine)
ALEPH_MLX_SEARCH_URL=http://127.0.0.1:8000/search \
PYTHONPATH=apps/api apps/api/.venv/bin/python -m uvicorn aleph_api.main:app --app-dir apps/api --port 8010

# Terminal 3: Frontend
npm run dev
```

Select "local mlx" mode in the UI and generate.

## Remaining risks

- `waveform`, `attribution`, `exposureVectors`, and `evalSuite` may be absent for API-sourced runs. The React console now renders visible no-data states instead of blank panels.
- Keep `apps/web/.env.local.example` aligned with the active API port and env var name.
- Python tests in `apps/api/tests/test_scoring.py` require `pytest` and `httpx` (`pip install -e ".[test]"`). Not yet wired to `npm test`.

## Next step

**Agent B/Backend:** Verify `local_mlx_search` round-trip. Start `search/server.py` and confirm whether token loss flows through to `apps/web` observation panels.

**Agent C/UI:** Keep UI state and display mapping isolated in `apps/web/src/lib/` so future feature cuts do not require API, fixture, or schema changes. Token loss panel from live search shows real tokens - validate display.

**Agent D/Fixtures:** Add second fixture (suggest: Gettysburg Address or Babel paragraph). Validate with `npm run lint`.

**Agent E/Demo:** Update `DEMO.md` to add `apps/web + apps/api` as the primary demo surface. Keep `web/` (Next.js) as the deployed reference.
