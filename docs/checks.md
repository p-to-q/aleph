# Checks

The root lint command is intentionally lightweight and can run without installing frontend dependencies:

```bash
npm run lint
```

It runs:

```text
scripts/doctor.mjs
scripts/check-links.mjs
scripts/check-placeholders.mjs
scripts/check-maintenance-routes.mjs
scripts/check-language.mjs
scripts/check-core.mjs
scripts/check-contract.mjs
scripts/check-fixtures.mjs
scripts/check-repo.mjs
```

## What these checks prove

- Required repository files exist.
- Local Markdown links resolve.
- Template placeholders are not left in active files.
- Maintenance route language matches the current artifact-first shape.
- Glossary, claim ledger, and active-doc claim language preserve settled terminology and avoid unguarded overclaims.
- Core helpers preserve expected Pareto frontier, leakage score, and compression ratio behavior.
- Core enum contracts stay aligned with `schemas/aleph-run.schema.json`.
- AlephRun fixture JSON files validate against `schemas/aleph-run.schema.json`.
- Fixture runs preserve enough candidate points, the explicit reconstruction baseline, shortest-found endpoint, selected candidate, observation mode, and non-leaking leakage threshold.
- The fixture manifest indexes every fixture run exactly once and keeps id, label, mode, and observation mode aligned.
- Reference screenshots are not kept in the archive.
- `optional/` is not active as a template leftover.
- `THESIS.md`, `docs/open-questions.md`, `docs/strategy.md`, `docs/quality-bar.md`, and `docs/repository-shape.md` are present.

## What these checks do not prove

- The React app builds; that requires `npm install` and `npm run build`.
- Hosted model credentials are present, external providers are reachable, or a live model returns good candidates.
- Token loss, attribution, or waveform values are real model internals.
- External URLs are still live.

Record broader checks in `docs/verification.md`.

## Release gate

Before a formal release, run:

```bash
npm run lint
npm run test
npm --workspace web run build
npm run api:smoke
apps/api/.venv/bin/python -m pytest apps/api/tests -q
search/.venv/bin/python search/preflight.py
git diff --check
```

Also run a server-configured hosted smoke against `/health` and `/api/search`
when the release depends on hosted black-box mode. A passing hosted smoke proves
the adapter can return real prompt/output candidates as `black_box`
observations; it does not prove token NLL, logits, or a globally shortest
prompt.

## API smoke

The API adapter boundary has an additional smoke check:

```bash
npm run api:smoke
```

It validates `mode=mock` and a fake live-search response against
`schemas/aleph-run.schema.json`, checks the Shortest Found and Explicit
Reconstruction endpoints, and verifies that `local_mlx_search` fails
recoverably when `search/server.py` is not running. It requires the local API
Python environment but does not require MLX or a live model.

## Demo readiness

Before demo freeze, run:

```bash
npm run demo:check
```

It runs the required fixture/mock path (`npm test`, `npm run lint`,
`npm run build`, `npm run api:smoke`, API compile, and API pytest), then tries
`search/preflight.py` with `search/.venv/bin/python` when available as an
optional local-MLX check. If
`http://127.0.0.1:8000/health` is reachable, it also runs
`npm run api:live-smoke`. Blocked optional checks mean local MLX mode is
unavailable in that shell. If preflight is ok but live smoke is blocked, start
`search/server.py`; if preflight is blocked, set up `search/.venv`. Either case
does not invalidate the fixture/mock demo path.
