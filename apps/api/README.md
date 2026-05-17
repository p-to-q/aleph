# Aleph API

FastAPI orchestration layer for Aleph v0.

Current v0 endpoints:

- `GET /health`
- `POST /api/candidates`
- `POST /api/generate`
- `POST /api/score`

Adapter modes:

- `mock`
- `local_openai`

The intended local-model path is `mlx_lm.server` exposing an OpenAI-compatible
endpoint. Configure it with:

```text
ALEPH_OPENAI_BASE_URL=http://127.0.0.1:8080/v1
ALEPH_OPENAI_API_KEY=none
```

If the local model is unavailable, keep the frontend alive by using `mode=mock`.

## Relationship to `search/`

`search/` is the current live-search experiment: it proves that a local MLX
model can propose, generate, and score a frontier. `apps/api` is the stable
product API surface. Keep new frontend work pointed at `apps/api`; wrap or
adapt `search/` behind this API instead of teaching the UI a second backend
contract.
