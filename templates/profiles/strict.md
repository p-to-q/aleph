# Strict Profile

Use for long-lived products, SDKs, infrastructure, or repositories with multiple maintainers.

## Keep active

- standard profile
- CODEOWNERS
- selected strict workflows from `optional/github/`
- release/archive route when the project publishes releases
- decision map
- ADR lane for durable decisions

## Rules

- Decision-bearing surfaces require explicit review.
- Public API, security, release, license, workflow, label, and agent-contract changes should name a decision trace.
- Green CI is necessary but not sufficient for doctrine-bearing work.

## Sample

```text
A public SDK should use strict:
- CODEOWNERS catches ownership-sensitive changes.
- ADRs explain breaking API or release policy decisions.
- The optional doctrine guardrail warns when durable surfaces change without rationale.
```

## Router note

After choosing `strict`, run the checklist in `docs/router.md`. Delete uncalled routes instead of leaving unused process active.

### Sample

```text
Profile: strict
Action: keep matching routes, rewrite blank templates, delete route files that the project will not maintain.
```
