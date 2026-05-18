# Agent Instructions

Aleph is an artifact-first research product repository: ambitious, file-first, source-aware, and intentionally small enough to keep moving.

## Operating thesis

The repository is the source of truth. Chat history and prototype screenshots are not durable unless summarized into docs, code, fixtures, schemas, issues, PRs, or decisions.

## Read order

Read the smallest relevant set before editing:

1. `README.md`
2. `THESIS.md`
3. `docs/core-concept.md`
4. `docs/open-questions.md`
5. `docs/repository-shape.md`
6. `docs/contributor-map.md`
7. `docs/surfaces.md`
8. `docs/architecture.md`
9. `packages/core/src/types.ts` when changing app/API/fixtures
10. `docs/research/research-process.md` when changing research claims
11. `WORKFLOW.md` only when the task involves issue/agent coordination

## Non-negotiables

- Make the smallest reviewable change.
- Do not invent architecture when a contract already exists in `packages/core` or `docs/`.
- Keep UI panels wired through `AlephRun`, `CandidatePoint`, and `ObservationSet`.
- Preserve the distinction between **Shortest Found**, **Explicit Reconstruction**, and **non-leaking mode**.
- Mark fixture, mock, and simulated values clearly.
- Do not claim white-box observations without real logits or model internals.
- Do not perform drive-by refactors.
- Do not add dependencies, workflows, or routes unless the repository clearly needs them.
- Run `npm run lint` after changes when the environment supports Node 20+.

## GitHub discipline

- For non-trivial user-visible, governance, architecture, path, deployment, permission, or research-claim changes, work through an issue or checked-in plan before implementation, then a small PR before merge.
- Keep PRs reviewable: one acceptance gate, explicit validation, and clear out-of-scope notes.
- If an emergency fix bypasses a prior issue, backfill the issue or PR notes so the repository remains the durable record.
- Do not use chat history as the only roadmap or decision log.

## Creative mandate

Be willing to propose stranger, better ideas, but do not smuggle them into the product as facts. Put unsettled ideas in `docs/open-questions.md`, a decision note, or a plan.

## Handoff format

End partial work with:

```text
Status: done | partial | blocked
Scope: files touched and why
Validation: commands run and results, or not run with reason
Risks: behavior, compatibility, migration, security, docs
Next step: one concrete action
```
