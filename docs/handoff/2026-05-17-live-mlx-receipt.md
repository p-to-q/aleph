# Handoff: Live MLX Search Receipt — 2026-05-17

## Objective

Verify that the optional local MLX search engine can run locally and that
`apps/api` can adapt its live `/search` response into an `AlephRun`-compatible
response.

## Account

Account B / Local Search Adapter Implementer, reviewed under Account A contract
rules.

## Preparation

```text
python3 -m venv search/.venv
search/.venv/bin/python -m pip install --upgrade pip
search/.venv/bin/python -m pip install -r search/requirements.txt
ALEPH_PY=search/.venv/bin/python npm run search:preflight
search/.venv/bin/python -u search/server.py
```

Preflight result:

```text
architecture: arm64
python_executable: /Users/dujiayi/code/aleph/search/.venv/bin/python
mlx_lm: ok
sentence_transformers: ok
fastapi: ok
uvicorn: ok
numpy: ok
cached_models:
- mlx-community/Qwen3-1.7B-4bit
port_8000: available
preflight: ok
```

Search server health:

```text
{"ok":true,"model":"mlx-community/Qwen3-1.7B-4bit"}
```

## Live Receipt

```text
Account: Account B / Local Search Adapter Implementer
Source mode: white_box
Date: 2026-05-17T07:16:11.586870+00:00
Command: npm run api:live-smoke -- --url 'http://127.0.0.1:8000/search' --target 'A small place for seeing too much, gently.' --label 'Live smoke target'
Search URL: http://127.0.0.1:8000/search
Model: mlx-community/Qwen3-1.7B-4bit
Observation mode: white_box
Candidate count: 3
Selected candidate id: search-point-3
Token NLL present: true
Claim supported: apps/api can adapt a live local MLX search response into an AlephRun-compatible white_box response.
Claim not supported: globally shortest prompt, production readiness, or white-box UI completeness.
```

Second receipt after restarting `search/server.py`:

```text
Account: Account B / Local Search Adapter Implementer
Source mode: white_box
Date: 2026-05-17T07:40:37.809308+00:00
Command: npm run api:live-smoke -- --url 'http://127.0.0.1:8000/search' --target 'A small place for seeing too much, gently.' --label 'Live smoke target'
Search URL: http://127.0.0.1:8000/search
Model: mlx-community/Qwen3-1.7B-4bit
Observation mode: white_box
Candidate count: 3
Selected candidate id: search-point-3
Token NLL present: true
Claim supported: apps/api can adapt a live local MLX search response into an AlephRun-compatible white_box response.
Claim not supported: globally shortest prompt, production readiness, or white-box UI completeness.
```

## Validation

```text
npm run api:live-smoke: ok
npm run api:live-smoke after server restart: ok
```

## Risks

- This receipt proves one local live round trip only.
- It does not prove search quality, production readiness, or global minimality.
- White-box UI completeness still needs visual verification in `apps/web`.

## Next Action

Use the running local search server to verify the `apps/web` local MLX mode and
confirm whether token-loss values render correctly in the console.
