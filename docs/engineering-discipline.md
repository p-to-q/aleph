# Engineering Discipline

<!-- Source note: adapted from p-to-q/wittgenstein/docs/engineering-discipline.md
     and lightly cross-filled from Jah-yee/cursor-rules. The template keeps
     general discipline and removes project-specific architecture doctrine. -->

This document defines how changes should be made in this repository by humans, coding agents, and humans operating coding agents.

## Core stance

Work inside the repository as a careful maintainer, not as an external code generator. The task is not to produce more code; it is to produce the smallest correct change that fits the existing architecture, behavior, and operational reality.

## Repository-first behavior

### 1. Read before write

Read the smallest set of files that define the surface you are changing. Inspect relevant code, tests, config, docs, nearby examples, and the commands used to validate the work. Do not let a prompt, issue title, old chat, or generic best practice override repository truth.

### 2. Match local patterns before importing outside patterns

Repository conventions win over generic advice unless the local convention is clearly broken for the current task. Extend an existing path before creating a parallel system. Prefer editing existing files over creating new files unless a new file is clearly necessary.

### 3. Identify constraints before implementation

For non-trivial work, briefly write:

1. the actual problem;
2. constraints that are real;
3. behavior that must be preserved;
4. the smallest valid solution;
5. validation to run;
6. what should remain untouched.

Do not begin with broad rewrites or speculative architecture.

## Change discipline

- Make the smallest effective change.
- Preserve existing behavior unless the task requires a change.
- Avoid unrelated cleanup, formatting churn, dependency updates, and file moves.
- Do not widen scope without a concrete reason.
- Do not invent public APIs, behaviors, abstractions, wrappers, dependencies, or requirements that the project does not imply.
- If a larger cleanup is genuinely necessary, propose it explicitly instead of hiding it in the change.

## Architecture discipline

- Prefer simple, explicit, well-bounded design.
- Favor composition over inheritance unless the repository clearly prefers otherwise.
- Keep business logic out of UI, framework glue, transport, entry, and routing layers where practical.
- Keep modules cohesive and interfaces narrow.
- Keep data flow explicit and side effects visible.
- Avoid generic dumping grounds such as `utils`, `helpers`, `common`, or `misc` unless the cross-cutting reason is real and documented.
- Do not abstract early. Every abstraction must solve a present problem.
- Prefer local reasoning over distributed indirection.

## Code style

- Prefer clarity over cleverness.
- Prefer explicitness over magic.
- Prefer flat control flow over deep nesting.
- Use guard clauses and early returns where they improve readability.
- Prefer intention-revealing names; long names are acceptable when they remove ambiguity.
- Keep functions focused and modules cohesive.
- Comments should explain why, constraints, tradeoffs, or non-obvious behavior; do not comment by paraphrasing syntax.
- Make the diff easy to review and easy to roll back.

## Robustness and failure handling

- Do not hide errors.
- Do not silently swallow exceptions unless explicitly justified.
- Preserve meaningful diagnostic information.
- Treat external input as untrusted.
- Validate assumptions at boundaries.
- Make invalid states difficult to represent.
- Keep fallback paths explicit and deliberate.
- Prefer boring, dependable solutions over clever but fragile ones.
- Printability is a feature: prefer states, errors, artifacts, and logs that humans can inspect.

## Testing and validation

Do not claim success without evidence.

Preferred validation order:

1. narrowest relevant test;
2. type check;
3. lint;
4. build;
5. golden or fixture check;
6. broader regression check when needed.

Rules:

- State exactly what you verified.
- Do not imply checks you did not run.
- Add or update tests when behavior changes and tests are appropriate.
- Test behavior rather than implementation trivia where practical.
- If validation was not run, say `Not run` and explain why.
- If confidence is partial, say so clearly.

## Receipts over claims

Do not say something is fixed, faster, safer, supported, or production-ready unless there is evidence: a test, fixture, script, benchmark, release artifact, manual check, or documented limitation.

## Decision traces

Not every change needs an ADR/RFC. But changes to license, security, release, workflow, public API, agent contract, labels, or project doctrine must leave a durable trace.

Use the lightest trace that preserves the reason:

- PR note for a local reversible change;
- `optional/history/decision-map.md` for issue/PR lineage;
- ADR for durable repository decisions;
- RFC/FRC for proposals needing discussion before implementation;
- research brief when an external prior or experiment drives the work.

## Experimental surfaces

Experimental code is allowed. Unmarked experimental code is not. Use `docs/surfaces.md`, issue labels, or README status text to distinguish stable, experimental, research, stub, archived, and unsupported surfaces.

## Stack-specific guidance

Use stack rules only when they match the files being edited. If a route is not called, delete or ignore that route.

- Frontend: keep components focused; keep business logic out of presentation where practical; avoid deeply nested JSX; preserve existing UI behavior unless change is required.
- Backend: keep request handling, business rules, and data access separated where practical; validate inputs at HTTP/RPC/framework boundaries; preserve meaningful errors; consider compatibility, observability, and rollback.
- Python: follow existing project tooling before importing preferences from another Python stack.
- Node/TypeScript: keep type definitions readable and intention-revealing; avoid type machinery that hides the actual behavior.

## Profile-specific expectations

| Profile | Discipline level |
| --- | --- |
| `micro` | Smallest change, honest validation, no surprise public claims. |
| `standard` | Add CI/Dependabot/CodeQL expectations and clear issue/PR hygiene. |
| `strict` | Decision-bearing surfaces need CODEOWNERS attention and usually ADR linkage. |
| `research-strict` | Research must feed issues/RFCs/ADRs/exec plans; agent work needs handoff context. |

## PR quality checklist

- The branch has one purpose.
- The PR body explains what and why.
- Validation is explicit.
- Risks are named.
- Docs changed when public behavior changed.
- Decision-bearing changes reference an ADR/RFC or say why one is not needed.
- The worktree is clean.

## Agent-specific rules

Agents must not:

- create broad rewrites to make a local solution easier;
- invent missing maintainer intent;
- treat generated output as a substitute for tests;
- hide uncertainty;
- introduce new files, routes, or abstractions merely because the agent has a template for them.

Agents should leave a handoff note when work is partial or blocked.

## Sample PR report

```text
Summary: add local link check to CI.
Why: docs-heavy repos need a cheap proof that relative links still resolve.
Validation: npm run check:links passed locally.
Risks: external URLs are not fetched; scheduled link check can be added later.
Next: enable stricter external link checking only if docs become product surface.
```
