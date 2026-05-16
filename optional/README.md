# Optional Routes

This directory holds routes that are useful for stricter projects but should not be active by default.

Use [`docs/router.md`](../docs/router.md) to decide which routes to keep. If a route is not called, delete it or keep only its README with a disabled note.

## Routes

| Route | Use when |
| --- | --- |
| `decisions/` | ADRs or RFCs are needed. |
| `research/` | Research changes implementation or priorities. |
| `exec-plans/` | Work spans multiple PRs or agents. |
| `history/` | Issue/PR history contains decisions. |
| `release/` | Tagged releases or historical docs need policy. |
| `github/` | Strict workflows should be copied into `.github/`. |
| `agent-rules/` | Cursor or other agent rule files are used. |

## Sample

```text
A standard package may keep only optional/decisions/README.md and delete the rest.
A research-strict repo should keep decisions, research, exec-plans, history, and relevant agent rules.
```
