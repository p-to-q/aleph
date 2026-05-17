# Verification

## Build-environment limitation

An attempted `git clone https://github.com/p-to-q/repo-template.git` failed inside the execution environment with DNS resolution failure during the first scaffold pass. The repository was therefore built from scratch using public template structure and documented conventions, while preserving a source ledger and explicit verification notes.

Later passes used web-accessible source material to inspect the p-to-q template, ARCA/auditing-llms, GCG, Probe Sampling, vec2text, and Aquin references. Research receipts are recorded in `docs/research/research-process.md` and `docs/source-ledger.md`.

## Audit pass 1: file presence

Required root files exist: README, THESIS, LICENSE, NOTICE, CONTRIBUTING, SECURITY, SUPPORT, AGENTS, PROMPT, WORKFLOW, package.json, docs, scripts, apps, packages.

Maintainer pass added or strengthened:

- `THESIS.md`
- `docs/repository-shape.md`
- `docs/open-questions.md`
- `docs/research/implementation-routes.md`
- `docs/decisions/`
- `docs/plans/`

`optional/` was removed to avoid template-shaped noise.

## Audit pass 2: product integrity

The repository preserves these decisions:

- Aleph is the name.
- The core interaction is a compression slider over discrete candidate points.
- The product is a reverse prompt compression workbench, not a generic prompt optimizer.
- The left endpoint is Shortest Found, not a guaranteed global optimum.
- The right endpoint is Explicit Reconstruction, not merely context-window length.
- The frontier is discrete and budget-bounded.
- Leakage score is first-class.
- White-box observations must be labeled honestly.
- Fixture and simulated observations must not be presented as real model evidence.
- Open decisions remain visible in `docs/open-questions.md`.

## Audit pass 3: repository discipline

The maintainer pass shifted the repository from template-adapted to project-native:

- Added a durable thesis.
- Replaced template-profile language with artifact-first repository shape.
- Moved decisions and plans under `docs/`.
- Updated agent read order and workflow contracts.
- Kept p-to-q as tone/source material, not architecture law.
- Kept checks lightweight and runnable without frontend dependencies.

## Audit pass 4: implementation integrity

The React source, static demo, core data contracts, fixtures, API skeleton, local-search API wrapper, docs, archive, decisions, plans, and scripts are present. Repository checks run without installing external packages.

The app remains frontend-led and fixture-backed. `apps/api` now exposes mock generation/scoring routes and a `local_mlx_search` wrapper for the experimental `search/` engine. Real local model search still requires starting `search/server.py` with MLX dependencies and local weights available; deletion ablation, persistence, and production adapters are not implemented yet.

## Audit pass 5: reviewer concerns

- Could the repository confuse prototype reference with product source? Reference screenshots were removed; prototype HTML is clearly archived.
- Could fixture values be mistaken for model evidence? `docs/surfaces.md` and fixture labels mark them as fixture/simulated.
- Could prior art become implementation lock-in? `docs/core-concept.md`, `docs/open-questions.md`, and `docs/research/prior-art.md` define ARCA/GCG as future adapters, not v0 scope.
- Could agents be confused by routes? `docs/repository-shape.md`, `docs/maintenance-routes.md`, and `docs/contributor-map.md` define active and parked surfaces.
- Could the repo be overfit to a template? `optional/` was removed and the thesis now controls the shape.

## Executed checks

```text
npm run lint
# doctor: ok
# check-links: ok
# check-placeholders: ok
# check-maintenance-routes: ok
# check-language: ok
# check-core: ok
# check-contract: ok
# check-fixtures: ok
# check-repo: ok
```

Additional manual checks:

```text
archive screenshots removed: ok
README key phrases: ok
THESIS north-star phrases: ok
fixture parse: ok
JSON schema validation against sample run: ok
core concept settled/open/deferred sections: ok
source ledger/research process present: ok
optional route removed: ok
python3 -m compileall apps/api/aleph_api: ok
PYTHONPATH=apps/api apps/api/.venv/bin/python apps/api/smoke.py: ok
zip integrity: ok
```

## Final maintainer pass

The final pass checked the repository from first principles rather than treating any template as law. The pass made these adjustments:

- Added `docs/strategy.md` for the current Hackathon/long-term path and fallback ladder.
- Added `docs/quality-bar.md` so language, code, and documentation choices have a shared review standard.
- Renamed template-colored maintenance files to project-native names: `docs/maintenance-routes.md`, `scripts/check-maintenance-routes.mjs`, and `scripts/check-placeholders.mjs`.
- Removed `docs/project-scale.md` because it only existed for scaffold continuity and no longer helped the next contributor.
- Moved the run schema from `templates/runs/` to `schemas/` so it reads as an active contract rather than a template remnant.

Final checks run after these edits:

```text
npm run lint: ok
JSON schema validation against sample run: ok
no optional/templates/screenshots dirs: ok
```

## Local verification pass: 2026-05-17

Account E reran the local verification path for the current repository state.

Passed:

```text
npm run demo:check: required path ok; optional local MLX live-smoke ok when search/server.py was running
npm test: ok
npm run lint: ok
npm run build: ok
npm run api:smoke: ok
PYTHONPATH=apps/api apps/api/.venv/bin/python -m compileall apps/api/aleph_api: ok
PYTHONPATH=apps/api apps/api/.venv/bin/python -m pytest apps/api/tests: 14 passed
npm run api:live-smoke with search/server.py running: ok
```

Observed web build:

```text
vite build: ok
dist/assets/index-MgTltu8I.js: 215.38 kB
dist/assets/index-CBMKgqd6.css: 6.14 kB
```

Earlier blocked optional check in the default shell before using `search/.venv/bin/python`:

```text
npm run search:preflight: blocked
missing Python modules: mlx_lm, sentence_transformers, fastapi, uvicorn
cached model found: mlx-community/Qwen3-1.7B-4bit
port_8000: available
```

Verified optional preflight with `search/.venv/bin/python`:

```text
search/.venv/bin/python search/preflight.py: ok
mlx_lm: ok
sentence_transformers: ok
fastapi: ok
uvicorn: ok
port_8000: search health responded 200
```

Interpretation:

- The fixture and mock API demo path is locally verified.
- The React console builds.
- The API smoke test verifies mock search, recoverable local-search failure, and
  a fake live-search-shaped adapter response against the `AlephRun` schema.
- The optional live MLX search route is verified when `search/server.py` is
  running; without the dedicated `search/.venv`, preflight remains blocked in
  the default shell.

Live MLX adapter receipt from `npm run api:live-smoke`:

```text
Account: Account B / Local Search Adapter Implementer
Source mode: white_box
Date: 2026-05-17T08:15:36.860814+00:00
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

## API/local search adapter pass

Account B verified the `apps/api` boundary around the local MLX search
experiment:

```text
npm run api:smoke: ok
npm run search:preflight with .venv: ok
npm run api:live-smoke with search/server.py running: ok
npm run lint: ok
```

Observed live path before token NLL was added to the quick server:

```text
search/server.py model: mlx-community/Qwen3-1.7B-4bit
first warm start: downloaded local model and MiniLM embedding model, then warmed in 161.8s
live smoke search: 5.6s, |y|=10 tokens, 2 candidate points
API observation mode: black_box
selected candidate: search-point-2
```

Notes:

- `search/` remains the live engine experiment.
- `apps/api` remains the product-facing boundary.
- The default `npm run lint` path does not require MLX, model downloads, or a
  running search server.
- The live quick server now attaches token NLL to the explicit/right-end point
  when `theta.score(...)` succeeds. This supports white-box adapter output, not
  a completed white-box UI product.

Observed live white-box path after adding explicit-point token NLL:

```text
search/server.py warm start with cached model: 18.0s
live smoke search: 3.0s, |y|=10 tokens, 3 candidate points
API observation mode: white_box
selected candidate: search-point-3
token NLL present: true
```

Receipt emitted by `npm run api:live-smoke`:

```text
Account: Account B / Local Search Adapter Implementer
Source mode: white_box
Claim supported: apps/api can adapt a live local MLX search response into an AlephRun-compatible white_box response.
Claim not supported: globally shortest prompt, production readiness, or white-box UI completeness.
```

Follow-up UI verification after labeling the live explicit point:

```text
React console mode: local_mlx_search
visible observation mode: WHITE_BOX OBSERVATIONS
visible header badge: TOKEN NLL
visible candidate label: Explicit Reconstruction
visible token panel caption: TOKEN NLL FROM LOCAL ADAPTER OUTPUT
API unavailable banner: absent
```
