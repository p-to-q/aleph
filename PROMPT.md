# Agent Prompt

Paste this into a coding agent when delegating work in this repository.

```text
You are working in a p-to-q-style repository. The repository is the source of truth; chat history is not.

Before editing, read:
1. README.md
2. docs/project-scale.md
3. docs/router.md
4. docs/contributor-map.md
5. docs/engineering-discipline.md
6. CONTRIBUTING.md
7. WORKFLOW.md when the task involves issue/agent coordination
8. Any issue, PR, or docs/handoff brief explicitly linked by the human.

Rules:
- Make the smallest effective change.
- Read nearby code, tests, config, and docs before editing.
- Match local patterns before importing outside best practices.
- Do not do drive-by refactors.
- Do not create files, routes, abstractions, wrappers, or dependencies unless clearly necessary.
- If a route is not called by the selected profile, delete it or leave only a disabled README; do not leave dead process active.
- Do not change license, security, release, workflow, agent contract, labels, public API, or architecture doctrine without calling it out.
- If a change is decision-bearing, reference or propose an ADR/RFC.
- Run the narrowest useful validation. If you cannot run it, say so plainly.
- End with: summary, validation, risks, and next step.
```
