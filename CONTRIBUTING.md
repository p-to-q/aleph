# Contributing

This repository uses a p-to-q-style contribution flow: small branches, explicit validation, and durable records for durable decisions.

## Branch flow

1. Start from `main`.
2. Create one branch per logical change.
3. Keep the PR reviewable in one sitting.
4. Rebase or update before final validation.
5. Do not push directly to `main`.

## Before opening a PR

- Read `docs/engineering-discipline.md`.
- Confirm the issue or PR explains the problem, not just the patch.
- Run the narrowest useful checks.
- Update docs when public behavior, workflow, labels, or support expectations change.
- Reference an ADR/RFC when changing a decision-bearing surface.

## PR body expectations

Every PR should include:

- **What changed**
- **Why it changed**
- **Validation** — exact commands run, or a plain statement that validation was not run
- **Risks** — compatibility, security, workflow, docs, migration, release
- **Follow-up** — if anything remains intentionally deferred

## License

Unless stated otherwise, contributions are accepted under Apache-2.0, matching `LICENSE`.
