# AGENTS.md

This file is the long-form operating guide for coding agents and humans who delegate work to agents.

It is adapted from Wittgenstein's `AGENTS.md` and cross-filled with repository-first discipline from `Jah-yee/cursor-rules`. Project-specific codec doctrine has been replaced by a general repository discipline contract.

## Operating thesis

The repository is the source of truth. Prompts can start work, but durable contracts live in code, docs, tests, issues, PRs, and decision records.

An agent should optimize for:

1. small, reviewable changes;
2. explicit validation;
3. no hidden architectural decisions;
4. no claims without receipts;
5. useful handoff notes when work stalls;
6. route deletion when a template lane is not called.

## Read order

Before editing, read only the smallest relevant set:

1. `README.md` — project route and status.
2. `docs/project-scale.md` — current profile.
3. `docs/router.md` — what files/routes are active.
4. `docs/contributor-map.md` — where things live.
5. `docs/engineering-discipline.md` — change discipline.
6. `docs/agent-rules.md` — optional stack/Cursor rules.
7. `CONTRIBUTING.md` — branch and PR rules.
8. `WORKFLOW.md` — issue/agent dispatch rules when agent orchestration is in scope.
9. Any linked `docs/handoff/*.md` or issue body.
10. ADR/RFC/brief only if the task touches a decision-bearing surface.

## Non-negotiables

- Do not invent context that is not in the repo, issue, PR, or handoff brief.
- Do not silently change public API, license, release, security, workflow, agent contract, or label semantics.
- Do not claim tests passed unless you ran them.
- Do not mix unrelated refactors into a feature or fix.
- Do not use generated code as a substitute for a design decision.
- Do not add new machinery to signal seriousness.
- When blocked, leave a precise handoff note with files read, changes made, validation run, and next decision needed.

## Decision-bearing surfaces

Treat these as requiring maintainer attention and, for strict projects, ADR/RFC linkage:

- `LICENSE`, `NOTICE`, `SECURITY.md`, `SUPPORT.md`, `CODE_OF_CONDUCT.md`;
- `CONTRIBUTING.md`, `AGENTS.md`, `PROMPT.md`, `WORKFLOW.md`;
- `.github/CODEOWNERS`, `.github/workflows/*`, issue/PR templates, label files;
- `docs/engineering-discipline.md`, `docs/agent-rules.md`, `docs/router.md`, `docs/labels.md`, `optional/decisions/**`;
- public APIs, schemas, protocol files, release processes, and anything documented as stable.

## Router behavior

If the task is template adoption or repo cleanup:

```text
1. Choose profile: micro, standard, strict, or research-strict.
2. Keep the routes called by that profile.
3. Delete, park, or disable uncalled routes.
4. Rewrite blank templates for the target project.
5. Keep structural templates only when the workflow exists.
6. Keep instructional templates only when maintainers will maintain them.
```

## Handoff format

When you stop, write:

```text
Status: done | partial | blocked
Scope: files touched and why
Validation: commands run and results, or "not run" with reason
Risks: behavior, compatibility, migration, security, docs
Next step: one concrete action for the next human or agent
```
