# Checks

This repository uses lightweight template checks, not project-specific golden tests.

Wittgenstein-style projects may add true golden fixtures later, but this seed should not imply that every repository needs them. The default checks only verify that the template is coherent after routing.

## Commands

```bash
npm run doctor
npm run check:links
npm run check:template
npm run check:router
npm run lint
```

## What they check

| Command | Purpose |
| --- | --- |
| `npm run doctor` | Required public files, license consistency, core docs. |
| `npm run check:links` | Relative Markdown links across active and optional content. |
| `npm run check:template` | Profile matrix and README sample sections. |
| `npm run check:router` | Router/profile docs and optional route locations. |
| `npm run lint` | All of the above. |

## Template matrix

[`checks/profile-matrix.json`](../checks/profile-matrix.json) records the minimum files promised by each profile. It is a seed-level contract, not a complete project test plan.

## Golden tests

Use true golden tests only when the project produces outputs that should be stable byte-for-byte or semantically over time. Examples:

```text
rendered artifact snapshots
compiled package surfaces
CLI output fixtures
schema validation examples
research receipt summaries
```

Keep those project-specific tests in the project that needs them. Do not keep a `goldens/` directory just to look rigorous.

## Sample

```text
After routing a standard project:
1. Delete unused optional routes.
2. Update checks/profile-matrix.json only if the profile promises changed.
3. Run npm run lint.
4. Record the result in docs/verification.md.
```
