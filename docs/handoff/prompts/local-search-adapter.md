# Prompt: Local Search Adapter

Paste this into the second coding account when delegating the non-UI backend line.

```text
You are working on Aleph, a reverse prompt compression workbench.

Your task is backend-only: wrap the existing `search/` MLX live-search experiment behind `apps/api`, without touching UI code.

Read first:
1. README.md
2. THESIS.md
3. docs/core-concept.md
4. docs/architecture.md
5. docs/plans/hackathon-v0.md
6. docs/research/implementation-routes.md
7. docs/handoff/account-dispatch.md
8. apps/api/README.md
9. apps/api/aleph_api/main.py
10. search/server.py
11. search/aleph_search.py
12. packages/core/src/types.ts

Goal:
Create a narrow `local_mlx_search` backend path that lets `apps/api` call or adapt the `search/` engine and return a product-friendly response that can be mapped into `AlephRun`.

Recommended implementation path:
1. Inspect the current `search/server.py` response shape: `key`, `label`, `targetTokens`, `evalModel`, `points`.
2. Add API request/response models in `apps/api/aleph_api/models.py` only as needed.
3. Add a service or adapter under `apps/api/aleph_api/` that maps search points to candidate-like objects.
4. Expose one route, preferably `POST /api/search`, unless the existing API shape clearly points to a better name.
5. Keep `mock` mode working without MLX, model downloads, or sentence-transformers installed.
6. If the local search engine is not running or MLX is unavailable, return a clear recoverable error.
7. Document how to run the route in `apps/api/README.md`.

Hard boundaries:
- Do not edit `web/` or `apps/web/`.
- Do not add a database.
- Do not make `npm run lint` depend on MLX or model availability.
- Do not claim global shortest prompts or strict Kolmogorov complexity.
- Do not change `packages/core/src/types.ts` unless absolutely necessary; if you do, explain why.
- Do not remove `search/`; wrap it.

Validation:
- Run `npm run lint`.
- Run `python3 -m compileall apps/api/aleph_api`.
- If FastAPI dependencies are available, start the API and smoke-test:
  - `GET /health`
  - existing `POST /api/candidates`
  - existing `POST /api/generate` in `mock` mode
  - new local search route in failure/fallback mode if MLX is unavailable
- If you can run the local MLX engine, include one successful sample response.

End with:
Status: done | partial | blocked
Scope: files touched and why
Validation: commands run and results
Risks: behavior, compatibility, migration, security, docs
Next step: one concrete action
```
