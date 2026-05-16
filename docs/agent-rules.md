# Agent Rules

<!-- Source note: adapted from Jah-yee/cursor-rules and p-to-q/Wittgenstein
     agent surfaces. These rules are useful for Cursor, Codex, Claude Code,
     human reviewers, and humans operating agents. -->

This file explains how rule files should be used. The goal is not to make the repository more agent-shaped; it is to make agent behavior match the repository's human engineering discipline.

## Rule model

There are three layers:

1. **Core rule** — always applies. It says read before write, make the smallest correct change, validate honestly, and do not hide errors.
2. **Project rule** — applies when a repository has local architecture, style, robustness, testing, or no-refactor constraints.
3. **Stack rule** — applies only when the touched files match a stack, such as React, Node service, or Python service.

If a stack is not present, do not keep the rule active. A route not called by the project should be deleted or parked.

## Cursor usage

The template keeps Cursor-compatible rule seeds in `optional/agent-rules/cursor/` instead of enabling them at the root by default.

To enable them in a real project:

```text
1. Copy relevant files from optional/agent-rules/cursor/project/ to .cursor/rules/.
2. Copy only matching stack files from optional/agent-rules/cursor/stacks/.
3. Put user-rule-core.md in your Cursor User Rules only if you want a personal global rule.
4. Delete rules for stacks or routes that the project does not use.
```

## Human usage

Humans can use the same rules as a review checklist:

```text
Did the change read nearby code first?
Did it extend the existing path rather than creating a parallel system?
Did it avoid drive-by refactors?
Did it keep errors visible?
Did it state validation honestly?
```

## Sample rule selection

```text
micro CLI script:
  keep: 00-core-engineering, 50-no-drive-by-refactor
  delete: frontend-react, backend-service, release/research workflow rules

standard React site:
  keep: core, code-style, testing, frontend-react
  optional: architecture, robustness
  delete: backend-python unless there is a Python service

strict API service:
  keep: core, architecture, robustness, testing, no-drive-by-refactor, backend-service
  add: backend-node or backend-python stack rule

research-strict agentic repo:
  keep: all relevant project rules, WORKFLOW, handoff, research/brief rules
  delete: unrelated stack rules
```
