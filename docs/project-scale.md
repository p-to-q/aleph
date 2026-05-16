# Project Scale

This template has four profiles. They describe the amount of process a project can justify. Choose the smallest profile that keeps the work understandable and safe.

## Aleph routing

Aleph is routed at **`micro`**: one artifact, one demo, a short-lived hackathon experiment on M4 Max. The `standard`, `strict`, and `research-strict` profiles below, and the optional routes they call, are kept as inert template scaffolding only — not active process. See [`project-brief.md`](project-brief.md).

## Profiles

| Profile | Use when | Process budget |
| --- | --- | --- |
| `micro` | The project is one artifact, one small tool, a demo, or a short-lived experiment. | Very low. Keep public files and minimal validation. |
| `standard` | The project has users, reusable code, a site, or a small public surface. | Low. Add issue/PR hygiene, dependency updates, labels, and security/support surfaces. |
| `strict` | The project has compatibility promises, releases, security concerns, multiple maintainers, or long-lived public APIs. | Medium. Add CODEOWNERS, ADRs, release/archive rules, and stricter review gates. |
| `research-strict` | Research, prior art, agent orchestration, or multi-step execution changes engineering direction. | High, but still routed. Add research briefs, RFCs, exec plans, handoff, and history ledger. |

## Rule

```text
Use the smallest profile that protects the project.
Delete every route that the profile does not call.
```

A lightweight repository is not less serious. It is serious about not carrying dead process.

## What each profile should keep

### micro

Keep:

- public files;
- `docs/project-brief.md`;
- `docs/engineering-discipline.md`;
- basic CI and `scripts/doctor.mjs`;
- PR template.

Do not keep by default:

- ADR/RFC;
- research briefs;
- exec plans;
- issue/PR history ledger;
- strict GitHub workflows;
- stack-specific agent rules.

### standard

Keep everything in `micro`, plus:

- issue templates;
- labels;
- Dependabot;
- CodeQL when the language is supported;
- link check;
- `docs/surfaces.md`.

ADR is optional. Use it only for durable decisions.

### strict

Keep everything in `standard`, plus:

- CODEOWNERS with real owners;
- ADR route under `optional/decisions/adrs/`;
- release/archive route when tagged releases or historical docs exist;
- stricter review gates;
- selected workflows from `optional/github/` when someone maintains them.

RFCs remain optional unless design discussion needs a proposal lane.

### research-strict

Keep everything in `strict`, plus:

- research briefs;
- RFCs;
- exec plans;
- handoff briefs;
- issue/PR ledger;
- full human/agent workflow;
- relevant agent rules.

This is the Wittgenstein-like lane: research and agent work leave lineage before they become code.

## Samples

### A one-page project

```text
Profile: micro
Reason: the project has one artifact and no public API.
Action: delete optional/; keep only root health files, project brief, and checks.
```

### A small package

```text
Profile: standard
Reason: users may file issues and dependencies change over time.
Action: keep issue templates, Dependabot, CodeQL, labels; park ADRs until the first durable decision.
```

### A long-lived SDK

```text
Profile: strict
Reason: compatibility and releases matter.
Action: enable ADRs, CODEOWNERS, release/archive notes, and selected strict workflows.
```

### A research/agent repository

```text
Profile: research-strict
Reason: research findings and agent handoffs affect implementation.
Action: keep briefs, RFCs, exec plans, WORKFLOW, handoff, and history ledger.
```
