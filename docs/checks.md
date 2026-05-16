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
scripts/check-repo.mjs
```

## What these checks prove

- Required repository files exist.
- Local Markdown links resolve.
- Template placeholders are not left in active files.
- Maintenance route language matches the current artifact-first shape.
- The sample run fixture has enough candidates and observation data.
- Reference screenshots are not kept in the archive.
- `optional/` is not active as a template leftover.
- `THESIS.md`, `docs/open-questions.md`, `docs/strategy.md`, `docs/quality-bar.md`, and `docs/repository-shape.md` are present.

## What these checks do not prove

- The React app builds; that requires `npm install` and `npm run build`.
- Any real model search is implemented.
- Token loss, attribution, or waveform values are real model internals.
- External URLs are still live.

Record broader checks in `docs/verification.md`.
