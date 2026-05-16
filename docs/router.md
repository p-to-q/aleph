# Router

The Router decides what this repository keeps after it is used as a template.

A route is a coherent set of files that supports one kind of work. A new project should not keep every route. It should keep what it calls, rewrite what is blank, and delete or park what it does not use.

```text
called route     -> keep, customize, validate
uncalled route   -> delete or park under optional/archive or project archive
uncertain route  -> keep README only, mark disabled, revisit later
```

This is how the template stays light.

## Quick choice

| Project shape | Profile |
| --- | --- |
| One artifact, small demo, private scratch, short-lived experiment | `micro` |
| Reusable package, public tool, site, small app | `standard` |
| Long-lived SDK, service, infra, release-bearing or multi-maintainer repo | `strict` |
| Research-driven, agent-assisted, or execution-plan-heavy repo | `research-strict` |

## Route matrix

| Route | Location | Micro | Standard | Strict | Research Strict |
| --- | --- | --- | --- | --- | --- |
| Public window | root health files | keep | keep | keep | keep |
| Basic checks | `scripts/`, `.github/workflows/ci.yml` | keep | keep | keep | keep |
| Issue/PR templates | `.github/ISSUE_TEMPLATE/`, PR template | PR only | keep | keep | keep |
| Dependency/security automation | Dependabot, CodeQL | delete/park if no ecosystem | keep when supported | keep | keep |
| CODEOWNERS | `.github/CODEOWNERS` | optional | optional | keep | keep |
| Decisions | `optional/decisions/` | delete | README only or optional | keep ADR | keep ADR + RFC |
| Research | `optional/research/` | delete | delete | optional | keep |
| Exec plans | `optional/exec-plans/` | delete | optional | keep for multi-slice work | keep |
| History ledger | `optional/history/` | delete | optional | decision-map only | keep ledger |
| Strict workflows | `optional/github/` | delete | optional | copy needed workflows | copy needed workflows |
| Agent rules | `optional/agent-rules/` | optional core only | optional by stack | optional by stack | keep relevant stacks |
| Handoff | `docs/handoff/` | delete or README only | optional | optional | keep |
| Release/archive | `optional/release/` | delete | optional | keep if releases exist | keep if releases exist |

## Apply the Router

Use this prompt with a human reviewer or coding agent:

```text
Read README.md, docs/project-scale.md, and docs/router.md.
Choose one profile: micro, standard, strict, or research-strict.
For every route not called by that profile, delete the route or leave only a README that says it is disabled.
Rewrite all blank templates for this project.
Keep structural templates only when the project will actually use them.
Keep instructional templates only when someone will maintain them.
Do not add process just to signal seriousness.
Run npm run lint after routing.
Update docs/verification.md with the result and any unresolved questions.
```

## Samples

### Micro artifact

```text
Keep: README, LICENSE, NOTICE, CONTRIBUTING, SECURITY, SUPPORT, docs/project-brief.md, docs/engineering-discipline.md, PR template, basic CI.
Delete: optional/decisions, optional/research, optional/exec-plans, optional/history, optional/github, optional/agent-rules.
Maybe: keep docs/surfaces.md if the artifact has stable vs experimental states.
```

### Standard public package

```text
Keep: issue templates, labels, Dependabot, CodeQL when supported, link check, docs/surfaces.md.
Delete: research and exec-plan routes unless work already spans multiple maintainers or agents.
Maybe: keep ADR README only; add ADRs when compatibility, license, or release policy changes.
```

### Strict SDK or service

```text
Keep: CODEOWNERS, optional/decisions/adrs, release/archive route, review gates, decision-map.
Copy from optional/github only the workflows that have an owner.
Delete: unused research briefs and unrelated agent stack rules.
```

### Research-strict agentic repo

```text
Keep: WORKFLOW, AGENTS, PROMPT, docs/handoff, optional/research, optional/decisions, optional/exec-plans, optional/history.
Use: Brief -> RFC -> ADR -> exec plan -> PR when research changes implementation.
Delete: unrelated stack rules, inactive workflows, and any route without a maintainer.
```
