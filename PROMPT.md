# Prompt for Coding Agents

Paste this into a coding agent when delegating Aleph work:

```text
You are working on Aleph, a reverse prompt compression workbench.

The repository is the source of truth. Read first:
1. README.md
2. THESIS.md
3. docs/core-concept.md
4. docs/open-questions.md
5. docs/repository-shape.md
6. docs/contributor-map.md
7. docs/surfaces.md
8. docs/architecture.md
9. packages/core/src/types.ts when changing implementation or fixtures

Rules:
- Make the smallest effective change.
- Do not do drive-by refactors.
- Do not create routes, abstractions, dependencies, wrappers, or workflows unless clearly necessary.
- Preserve the distinction between fixture/mock/simulated/black-box/white-box observations.
- Do not represent Aleph as proving the globally shortest prompt.
- Do not change license, security, workflow, data contract, repository shape, or architecture doctrine without calling it out.
- If a change is decision-bearing, update docs and propose or reference a decision note.
- Run the narrowest useful validation. If you cannot run it, say so plainly.
- End with summary, validation, risks, and next step.
```
