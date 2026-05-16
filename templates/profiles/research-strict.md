# Research Strict Profile

Use when research and/or human-agent collaboration is central to delivery.

This profile merges the earlier `research` and `agent-heavy` ideas into one mode.

## Keep active

- strict profile
- research briefs
- RFC lane
- exec plans
- `AGENTS.md`
- `PROMPT.md`
- `WORKFLOW.md`
- `docs/handoff/`
- issue/PR ledger
- template checks

## Rules

- A research note must feed one of: no-action, issue, RFC, ADR, implementation plan, docs update, or archive decision.
- A handoff brief is the bounded context for complex issue or agent work.
- Max concurrent agent work should match maintainer review capacity.
- Agent tasks must avoid blocked, discussion, tracker, governance, and oversized umbrella issues unless a human explicitly scopes them.

## Sample

```text
A model/tooling repo should use research-strict:
1. brief states the question and prior art;
2. RFC proposes the implementation;
3. ADR records durable decisions;
4. exec plan slices the work;
5. handoff brief gives an agent exactly what to read;
6. PR reports validation, risks, and next step.
```

## Router note

After choosing `research-strict`, run the checklist in `docs/router.md`. Delete uncalled routes instead of leaving unused process active.

### Sample

```text
Profile: research-strict
Action: keep matching routes, rewrite blank templates, delete route files that the project will not maintain.
```
