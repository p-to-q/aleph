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

The React source, static demo, core data contracts, fixtures, API skeleton, docs, archive, decisions, plans, and scripts are present. Repository checks run without installing external packages.

The app remains frontend-led and fixture-backed. Real model search, token NLL, deletion ablation, persistence, and adapters are not implemented yet.

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
