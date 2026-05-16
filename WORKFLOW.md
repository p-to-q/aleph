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
