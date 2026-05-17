# Services

Current service modules:

- `candidates.py` builds deterministic candidate prompts for mock and v0 API flows.
- `scoring.py` owns simple token, similarity, compression, leakage, and ordering helpers.
- `local_mlx_search.py` adapts the `search/` live MLX experiment into an `AlephRun`-compatible response.

`search/` remains an engine experiment. Service modules in `apps/api` are the
product-facing boundary and must keep local MLX failures recoverable. Run the
boundary smoke check from the repository root:

```bash
npm run api:smoke
```
