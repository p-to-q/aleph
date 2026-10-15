# Token NLL Shape Receipt — local MLX adapter run, 2026-10-15

Evidence artifact for the P2 adapter evidence contract
([token-nll-evidence-note.md](token-nll-evidence-note.md)): one live local run of the adapter
path. Not a benchmark result; not a prompt-quality, leakage, or shortest-prompt claim. Source
mode: `white_box`.

## Environment

- Model: `mlx-community/Qwen3-1.7B-4bit`, pinned revision
  `3b1b1768f8f8cf8351c712464f906e86c2b8269e`.
- Engine: `search/server.py` under the pinned MLX venv (`mlx` 0.31.2, `mlx-lm` 0.31.3); warm
  from cache in 22.7 s; searches 21.4 s and 19.2 s.
- Adapter: `apps/api` on branch `codex/adapter-evidence-contract`, code state `d4e5145` (includes
  the negative-zero normalization).
- Target: `A small place for seeing too much, gently.` (10 target tokens).
- Captured: 2026-10-15T21:35:34Z (receipt timestamp from the smoke output).

## Command and observed result

```bash
python search/server.py    # pinned MLX venv
npm run api:live-smoke -- --url 'http://127.0.0.1:8000/search' \
  --target 'A small place for seeing too much, gently.' --label 'Token NLL shape receipt'
```

Output of `live-smoke-normalized.txt`, sha256
`c8a4adb26977059b0507d64fa826b5527a479110078175b5deaabe447d25c09b`:

~~~text
live-smoke-api: ok
model: mlx-community/Qwen3-1.7B-4bit
observation_mode: white_box
candidates: 3
selected: candidate-21402feb0d89
token_nll_present: true

receipt:
```text
Account: Account B / Local Search Adapter Implementer
Source mode: white_box
Date: 2026-10-15T21:35:34.902851+00:00
Command: npm run api:live-smoke -- --url 'http://127.0.0.1:8000/search' --target 'A small place for seeing too much, gently.' --label 'Token NLL shape receipt'
Search URL: http://127.0.0.1:8000/search
Model: mlx-community/Qwen3-1.7B-4bit
Observation mode: white_box
Candidate count: 3
Selected candidate id: candidate-21402feb0d89
Token NLL present: true
Token NLL shape: entries=10 min=0 max=0
Claim supported: apps/api can adapt a live local MLX search response into an AlephRun-compatible white_box response.
Shape claim: the adapted response carries a non-empty token NLL trace whose entries are {token: str, loss: finite >= 0}.
Claim not supported: globally shortest prompt, production readiness, or white-box UI completeness.
```
~~~

Raw wire capture of the same engine run (`raw-search-response-normalized.json`, sha256
`051a7457ee9f4e697fbca6c20f06f95582f7da23a50d6583fff3fe6af77a76cd`): the
explicit-reconstruction point is the only one carrying a trace, and the engine's raw float32
values are saturated negative zeros, which the adapter normalizes to `0.0` before emitting the
projection:

```json
"label": "Explicit Reconstruction", "toktext": ["A", " small", " place", " for", " seeing", " too", " much", ",", " gently", "."],
"toknll": [-0.0, -0.0, -0.0, -0.0, -0.0, -0.0, -0.0, -0.0, -0.0, -0.0]
```

An earlier capture in the same directory (`live-smoke.txt`, sha256
`cf868ab0b0d90658a5529cb5675ea92f980f79c6eee49f6eddf4715c3624708c`) predates the normalization
and shows `Token NLL shape: entries=10 min=-0 max=-0`; it is the observation that motivated the
fix. The candidate set varies per run (5 candidates in that capture, 3 here), so counts are
recorded per capture, not as constants.

## Claims

- Supported: the adapter consumes a live local MLX search response and emits a `white_box`
  response whose non-empty token NLL trace satisfies the recorded shape — one entry per decoded
  token, finite loss ≥ 0, normalized to positive zero.
- Not supported: globally shortest prompt, prompt quality, leakage evidence, production
  readiness, white-box UI completeness, or anything beyond this one local environment.

## Evidence files (host-local; sha256)

- `/tmp/aleph-token-nll-receipt/live-smoke-normalized.txt` —
  `c8a4adb26977059b0507d64fa826b5527a479110078175b5deaabe447d25c09b`
- `/tmp/aleph-token-nll-receipt/raw-search-response-normalized.json` —
  `051a7457ee9f4e697fbca6c20f06f95582f7da23a50d6583fff3fe6af77a76cd`
- `/tmp/aleph-token-nll-receipt/server-normalized.log` —
  `55c08d8e4e42fb74fe2f8dff6377b91627e67723b700054cfd2e319e9cda4faf`
- Pre-normalization captures: `live-smoke.txt`
  `cf868ab0b0d90658a5529cb5675ea92f980f79c6eee49f6eddf4715c3624708c`,
  `raw-search-response.json`
  `b85b8ef11e933e5a6dfa2606be8cb801bb365666385991c8d00327d0e1b445ce`,
  `server.log`
  `9b717b1e66541630a7c94f8a441ab0c96abda708cf56a3b67f58a031b6c98a44`.

## Verify

```bash
python search/server.py    # pinned MLX venv, same model revision
npm run api:live-smoke -- --url 'http://127.0.0.1:8000/search' \
  --target 'A small place for seeing too much, gently.'
```

The contract checks run without MLX: `node scripts/check-contract.mjs`,
`node scripts/check-fixtures.mjs`, `node scripts/check-run-file.mjs`, and the `apps/api` tests.
