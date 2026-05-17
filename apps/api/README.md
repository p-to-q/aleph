# Aleph API

FastAPI orchestration layer for Aleph v0.

Current v0 endpoints:

- `GET /health`
- `POST /api/candidates`
- `POST /api/generate`
- `POST /api/score`
- `POST /api/search`

Adapter modes:

- `mock`
- `local_openai`

Search adapter modes:

- `mock`
- `local_mlx_search`

The intended local-model path is `mlx_lm.server` exposing an OpenAI-compatible
endpoint. Configure it with:

```text
ALEPH_OPENAI_BASE_URL=http://127.0.0.1:8080/v1
ALEPH_OPENAI_API_KEY=none
```

If the local model is unavailable, keep the frontend alive by using `mode=mock`.

## Local MLX search route

`POST /api/search` wraps the live-search experiment in `search/` and returns an
`AlephRun`-like response with `target`, `config`, `candidates`,
`selectedCandidateId`, and `observations`.

Mock mode requires no MLX packages or model downloads:

```bash
curl -s http://127.0.0.1:8010/api/search \
  -H 'Content-Type: application/json' \
  -d '{"target_text":"A small place for seeing too much, gently.","mode":"mock"}'
```

For the real local route, run the MLX search experiment separately, then point
the API at it:

```bash
source search/.venv/bin/activate
python3 search/preflight.py
python3 search/server.py
ALEPH_MLX_SEARCH_URL=http://127.0.0.1:8000/search uvicorn aleph_api.main:app --app-dir apps/api --port 8010
curl -s http://127.0.0.1:8010/api/search \
  -H 'Content-Type: application/json' \
  -d '{"target_text":"A small place for seeing too much, gently.","mode":"local_mlx_search"}'
```

If the search engine is not running, the API returns `503` with a recoverable
message explaining how to start `search/server.py` or switch back to `mock`.

## Smoke checks

The API includes a dependency-light smoke script that exercises the service
mapping without requiring `pytest`, `httpx`, MLX, or a running model:

```bash
PYTHONPATH=apps/api apps/api/.venv/bin/python apps/api/smoke.py
```

Run it with any Python environment that has the API dependencies installed. It
verifies that `mode=mock` returns an `AlephRun`-compatible response, that
`local_mlx_search` fails recoverably when the local search engine is absent, and
that a live-search-shaped response maps into candidate points plus observations.

From the repository root:

```bash
npm run api:smoke
```

Optional HTTP smoke, still without MLX:

```bash
PYTHONPATH=apps/api apps/api/.venv/bin/python -m uvicorn aleph_api.main:app --host 127.0.0.1 --port 8010
curl -s http://127.0.0.1:8010/health
curl -s http://127.0.0.1:8010/api/search \
  -H 'Content-Type: application/json' \
  -d '{"target_text":"A small place for seeing too much, gently.","mode":"mock"}'
curl -s -i http://127.0.0.1:8010/api/search \
  -H 'Content-Type: application/json' \
  -d '{"target_text":"A small place for seeing too much, gently.","mode":"local_mlx_search"}'
```

Expected result: health returns `200`, mock search returns `200`, and
`local_mlx_search` returns a recoverable `503` unless `search/server.py` is
running.

When `search/server.py` is running, verify the live adapter path:

```bash
npm run search:preflight
npm run api:live-smoke
```

This optional check calls the API adapter directly against
`ALEPH_MLX_SEARCH_URL` or `http://127.0.0.1:8000/search` and reports the model,
observation mode, candidate count, selected candidate, and whether token NLL is
present. It also prints a fenced receipt block for handoff notes. Paste that
receipt into `docs/handoff/` or the PR description before upgrading any demo or
product claim based on a live local run.

## Relationship to `search/`

`search/` is the current live-search experiment: it proves that a local MLX
model can propose, generate, and score a frontier. `apps/api` is the stable
product API surface. Keep new frontend work pointed at `apps/api`; wrap or
adapt `search/` behind this API instead of teaching the UI a second backend
contract.
