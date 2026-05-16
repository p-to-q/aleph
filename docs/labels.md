# Label Taxonomy

Labels are contracts, not decorations. A label should tell humans, agents, and automation what kind of work this is and how it may move.

This file is adapted from Wittgenstein's label discipline and simplified for a template repository.

## Type labels

- `type/bug` — broken expected behavior.
- `type/feature` — new capability or user-facing improvement.
- `type/question` — needs answer, not implementation yet.
- `type/discussion` — open-ended design or community discussion.
- `type/governance` — workflow, labels, policy, license, security, release, or decision-lane change.
- `type/tracker` — tracks external state; not directly actionable.
- `type/horizon-spike` — time-boxed exploration with kill criteria.

## Status labels

- `status/needs-triage` — needs first maintainer pass.
- `status/ready` — actionable now.
- `status/blocked` — blocked by a named dependency.
- `status/needs-decision` — requires maintainer decision or ADR/RFC.
- `status/in-progress` — work is active.
- `status/needs-review` — implementation exists and awaits review.

## Priority labels

- `priority/p0` — must resolve before current release or mainline gate.
- `priority/p1` — high priority after the current mainline gate.
- `priority/p2` — important but not current-mainline blocking.

## Size labels

- `size/xs` — tiny docs/config/test fix.
- `size/s` — small scoped change.
- `size/m` — medium multi-file change.
- `size/l` — large implementation or coordination.
- `size/xl` — umbrella or program-level work.

## Slice labels

- `slice/docs`
- `slice/tests`
- `slice/implementation`
- `slice/infra`
- `slice/release`
- `slice/research`
- `slice/receipts`

## Stage labels

Use stage labels only when a project has distinct work streams. For small projects, skip them.

- `stage/cross-cutting` — shared schema, CLI, manifest, dependency, or infrastructure work.
- `stage/governance` — workflow, labels, doctrine governance, or maintainer process.

## Special labels

- `research-derived` — the issue or PR originates from a research brief and cites the brief section.
- `documentation` — general documentation improvement.
- `dependencies` — dependency update.

## Agent dispatch convention

Agent-eligible issues should usually have `status/ready`, a size no larger than `size/m`, and a concrete slice. Do not auto-dispatch `type/discussion`, `type/tracker`, `type/governance`, `type/horizon-spike`, `status/blocked`, or `status/needs-decision`.
