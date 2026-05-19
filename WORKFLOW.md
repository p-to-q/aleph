# Workflow

Aleph uses a lightweight workflow:

```text
thesis -> issue or plan -> small PR -> validation -> decision note only if durable
```

This file is a contract, not a daemon. It does not require an orchestration runtime.

## Sources of truth

1. Repository files.
2. Issues and PRs when the repository is on GitHub.
3. `docs/decisions/` for durable decisions.
4. `docs/plans/` for work spanning multiple files or phases.
5. Handoff briefs for temporary context.

Chat transcripts are not durable unless summarized into one of those surfaces.

## GitHub iteration rule

Default all non-trivial work to:

```text
issue -> branch -> small PR -> validation -> merge
```

Use an issue or a checked-in plan before implementation when the work changes a user-visible surface, repository governance, paths, architecture, permissions, deployment behavior, or research claims. The issue should name the acceptance gate, expected validation, and known out-of-scope work.

Use a direct commit only for tiny documentation typo fixes or emergency repair. If a hotfix lands without a prior issue, create or update an issue/PR note afterward so the durable record still exists.

PRs should stay small enough to review in one sitting. Split cleanup, product behavior, and research claims unless they are tightly coupled by the acceptance gate.

## Production surface (`https://aleph.ptoq.io`)

The launch app is `web/`, deployed by Vercel with **root directory = `web/`**.
Favicon, canonical URL, and Open Graph metadata live in `web/app/layout.tsx`
and static assets in `web/public/`; they reach the live site after **merge to
the connected branch + successful deploy**, not via one-off Vercel dashboard
uploads.

After a user-visible `web/` change merges, verify on the canonical site (hard
refresh):

- page source includes `<link rel="icon" href="...aleph-logo.png">` (or
  equivalent from Next metadata)
- shared-link preview image resolves when testing Open Graph
- `/health` still returns `200`

## Dispatch rule

A task is ready for an agent only when it has:

- a concrete acceptance gate;
- files to read first;
- clear out-of-scope boundaries;
- validation expectations;
- no unresolved product decision blocking implementation.

## Decision rule

Use decision notes only when a change affects public contracts, architecture, governance, license, research framing, long-term compatibility, or the `AlephRun` data shape.

## Cleanup rule

If agent workflow stops being maintained, keep `PROMPT.md` for manual delegation and rewrite this file to match reality.
