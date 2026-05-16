# Decisions

This folder contains optional decision lanes.

## When you do not need an ADR/RFC

Do not create decision records for routine bug fixes, small docs edits, local refactors, dependency patch bumps, or work whose rationale is fully obvious from the PR.

## When to use an RFC

Use an RFC when you are proposing a design and still want discussion:

- public API shape;
- workflow or label system;
- release process;
- security posture;
- agent/human operating model;
- major dependency or platform choice.

## When to use an ADR

Use an ADR when the decision is accepted and future contributors need to know why:

- accepted architecture path;
- rejected alternative;
- license or policy decision;
- stable public contract;
- governance rule.

## Lightweight rule

Small projects may keep only this README and skip numbered decisions. Larger or agent-heavy projects should enable ADRs and, when design discussion precedes the decision, RFCs.

## Sample

```text
Question: should this package expose a stable plugin API?
Micro: discuss in PR only.
Standard: maybe ADR if the API ships publicly.
Strict: RFC first if maintainers disagree; ADR after decision.
Research-strict: brief if prior art matters, RFC for design, ADR for accepted contract.
```
