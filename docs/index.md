# Documentation Index

This directory is the active documentation face of `repo-template`. It should stay small. Heavy routes live under `optional/` until the project calls them.

## Start here

1. [`project-brief.md`](project-brief.md) — rewrite this first for the new project.
2. [`project-scale.md`](project-scale.md) — choose `micro`, `standard`, `strict`, or `research-strict`.
3. [`router.md`](router.md) — keep called routes and delete uncalled routes.
4. [`engineering-discipline.md`](engineering-discipline.md) — shared rules for humans and agents.
5. [`verification.md`](verification.md) — record checks and unresolved questions before publishing.

## Active docs

| File | Purpose |
| --- | --- |
| [`agent-rules.md`](agent-rules.md) | Explains how optional agent rules are selected and copied. |
| [`checks.md`](checks.md) | Local template checks and route/profile checks. |
| [`content-sync.md`](content-sync.md) | Keeps README, docs, agent prompts, and optional routes from drifting apart. |
| [`contributor-map.md`](contributor-map.md) | Reading order for humans and maintainers. |
| [`engineering-discipline.md`](engineering-discipline.md) | Repository-first engineering behavior. |
| [`glossary.md`](glossary.md) | Project vocabulary; rewrite for the new project. |
| [`labels.md`](labels.md) | Label meanings as collaboration contracts. |
| [`license-policy.md`](license-policy.md) | Apache-2.0 default and exception handling. |
| [`review-gates.md`](review-gates.md) | UI review, route/profile review, final verification. |
| [`router.md`](router.md) | Route selection and deletion rules. |
| [`source-ledger.md`](source-ledger.md) | Source and adaptation notes for this seed. |
| [`surfaces.md`](surfaces.md) | Stable, experimental, internal, and archived surfaces. |
| [`template-forms.md`](template-forms.md) | Blank, structural, and instructional template forms. |

## Optional routes

Optional content is stored outside `docs/` so the active documentation stays light:

| Route | Location |
| --- | --- |
| ADRs and RFCs | [`../optional/decisions/`](../optional/decisions/) |
| Research briefs | [`../optional/research/`](../optional/research/) |
| Exec plans | [`../optional/exec-plans/`](../optional/exec-plans/) |
| Issue/PR history | [`../optional/history/`](../optional/history/) |
| Release/archive | [`../optional/release/`](../optional/release/) |
| Strict GitHub workflows | [`../optional/github/`](../optional/github/) |
| Agent rules | [`../optional/agent-rules/`](../optional/agent-rules/) |

## Sample

```text
A standard package should usually read:
README -> docs/project-brief -> docs/project-scale -> docs/router -> docs/engineering-discipline -> docs/verification.

It can ignore optional/research and optional/exec-plans until research or multi-slice work appears.
```
