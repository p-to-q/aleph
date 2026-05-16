# Workflow Contract

<!-- Source note: adapted from p-to-q/wittgenstein WORKFLOW.md, which was
     shaped by Brief K's review of OpenAI Symphony-style orchestration.
     This template keeps the contract idea and removes Wittgenstein-specific
     codec/modality routing. -->

This file describes how humans, issues, PRs, and coding agents cooperate. It is a contract, not a daemon. A human can execute it manually; an automation can implement it later.

## Why this file exists

Wittgenstein added `WORKFLOW.md` after research on orchestration prior art concluded that the useful import was **a repo-root issue/agent contract**, not a mandatory runtime. The same idea is useful here:

- GitHub Issues remain the source of truth for work;
- labels say whether work is dispatchable;
- handoff briefs bound the context;
- review capacity limits concurrency;
- the runtime stays optional.

## Sources of truth

1. GitHub Issues track work and open questions.
2. Pull Requests carry reviewable implementation.
3. ADRs/RFCs carry durable decisions when needed.
4. Handoff briefs carry temporary context for a specific issue or migration.
5. Chat transcripts are not durable unless summarized into one of the above.

## Issue dispatch

A task is agent-eligible only if all of these are true:

- it has a concrete acceptance gate;
- it is not primarily a debate, support request, tracker, or blocked decision;
- the expected change fits in one review sitting;
- the relevant docs or handoff brief are linked.

Suggested agent-eligible labels:

- `status/ready`
- `size/xs`, `size/s`, `size/m`
- `slice/docs`, `slice/tests`, `slice/implementation`, `slice/infra`

Labels that should usually exclude automatic agent dispatch:

- `status/blocked`
- `status/needs-decision`
- `type/discussion`
- `type/tracker`
- `type/governance`
- `type/horizon-spike`
- `size/l`, `size/xl`

## Workspace discipline

- One issue = one branch/workspace.
- One branch = one logical change.
- Rebase or update from `main` before final validation.
- Never push directly to `main`.
- A worktree must be clean before handoff or PR.

## Handoff briefs

Use `docs/handoff/TEMPLATE.md` for complex issues, multi-agent work, or any task where context would otherwise live in chat.

A good handoff brief contains:

- target issue/PR;
- current state;
- files to read first;
- invariant constraints;
- acceptance gates;
- explicit out-of-scope work;
- known risks.

## Concurrency

Default max concurrent agent tasks: 2.

This is a review-capacity limit, not a compute limit. Raise it only when CODEOWNERS and maintainers can actually review the resulting PRs.

## Runtime

No runtime is required. A future project may map this contract to Symphony, GitHub Actions, a shell script, or a custom orchestrator.

### Sample manual dispatch

```text
1. Pick an issue with status/ready and size/s.
2. Confirm it has no exclusion label.
3. Create a branch or worktree.
4. Paste PROMPT.md into the agent.
5. Attach the issue body and docs/handoff/<slug>.md if present.
6. Review the resulting PR like any human PR.
```


## Route cleanup

When a repository does not use agent dispatch, keep `PROMPT.md` as a manual prompt if helpful and delete or park the rest of the workflow route. Do not leave labels, handoff briefs, or orchestration instructions active when no one will maintain them.

### Sample cleanup prompt

```text
This project is standard, not research-strict.
Keep AGENTS.md and PROMPT.md for occasional agent use.
Delete or park docs/handoff, WORKFLOW runtime notes, research briefs, and RFCs unless a maintainer names a current use.
Run npm run lint after cleanup.
```
