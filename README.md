# repo-template

A **Seed** for p-to-q repositories: small enough to start from, disciplined enough to keep.

This repository is a GitHub template and a framework suggestion for p-to-q projects. It gives a project a public surface, a light engineering discipline, a human/agent handoff path, and optional routes for stricter decision and research work.

It is **not** a clone of Wittgenstein's product architecture. It keeps the collaboration traits that made that repository useful: clear entrypoints, small reviewable changes, explicit validation, source-aware decisions, and enough history for future humans and agents to understand why things exist.

```text
clear thesis -> visible artifact -> receipts or limitations -> short docs map -> license
```

That is the p-to-q lightweight mode. Most new projects should begin there.

## Use this template

1. Pick one profile: `micro`, `standard`, `strict`, or `research-strict`.
2. Keep the routes called by that profile.
3. Delete or park every route that is not called.
4. Rewrite blank templates for the project.
5. Run `npm run lint` before publishing the repository.

The template is intentionally file-first. The visible files are the contract; scripts only check that the contract is coherent.

## Four profiles

| Profile | Use when | Default shape |
| --- | --- | --- |
| `micro` | One artifact, demo, note, small internal tool, short-lived experiment. | Public files, README, license, minimal checks, lightweight discipline. |
| `standard` | Reusable package, public tool, small site, multi-file project. | `micro` + issue/PR templates, labels, Dependabot, CodeQL when supported, support/security docs. |
| `strict` | Long-lived package, SDK, service, infra, release-bearing or multi-maintainer repo. | `standard` + CODEOWNERS, ADR route, release/archive discipline, optional doctrine guardrail. |
| `research-strict` | Research-driven, agent-assisted, prior-art-heavy, or execution-plan-heavy repo. | `strict` + RFCs, briefs, exec plans, handoff, full WORKFLOW, issue/PR ledger. |

See [`docs/project-scale.md`](docs/project-scale.md) and [`docs/router.md`](docs/router.md) for the exact route matrix.

## Template forms

This repository uses three kinds of template content:

| Form | Meaning | Examples |
| --- | --- | --- |
| Blank template | A placeholder that must be rewritten before publishing. | [`docs/project-brief.md`](docs/project-brief.md), [`docs/glossary.md`](docs/glossary.md), ADR/RFC templates under [`optional/decisions/`](optional/decisions/). |
| Structural template | A reusable directory or file shape. | [`.github/ISSUE_TEMPLATE/`](.github/ISSUE_TEMPLATE/), [`docs/handoff/`](docs/handoff/), [`templates/router/`](templates/router/). |
| Instructional template | Guidance that should be adapted but mostly kept. | [`docs/engineering-discipline.md`](docs/engineering-discipline.md), [`AGENTS.md`](AGENTS.md), [`WORKFLOW.md`](WORKFLOW.md). |

If a route is not called, remove it. Unused process is not rigor; it is noise.

## Default files

The default face of the repository is deliberately small:

```text
README.md
LICENSE
NOTICE
CODE_OF_CONDUCT.md
CONTRIBUTING.md
SECURITY.md
SUPPORT.md
AGENTS.md
PROMPT.md
WORKFLOW.md
.github/
docs/
scripts/
templates/profiles/
templates/router/
optional/
```

`optional/` contains heavier routes. They are part of the seed, but they are not automatically active in a project.

## Optional routes

| Route | Location | Enable when |
| --- | --- | --- |
| Decisions | [`optional/decisions/`](optional/decisions/) | A change creates durable policy, public API, release, security, or governance consequences. |
| Research | [`optional/research/`](optional/research/) | Prior art or research directly changes implementation or roadmap. |
| Exec plans | [`optional/exec-plans/`](optional/exec-plans/) | Work spans multiple PRs, agents, packages, or maintainers. |
| History | [`optional/history/`](optional/history/) | Existing issues/PRs encode decisions that future contributors need. |
| Release/archive | [`optional/release/`](optional/release/) | The repo has tagged releases or historical docs that should not be silently rewritten. |
| GitHub strict workflows | [`optional/github/`](optional/github/) | You need doctrine guardrails, Dependabot auto-merge, release automation, or strict status labels. |
| Agent rules | [`optional/agent-rules/`](optional/agent-rules/) | Humans use coding agents or Cursor-style rule routing. |

## Samples

### Micro sample

```text
Keep: README, LICENSE, NOTICE, CONTRIBUTING, SECURITY, SUPPORT, basic CI, PR template, docs/engineering-discipline.md.
Rewrite: README, docs/project-brief.md, docs/glossary.md, support/security contacts.
Delete or park: optional/decisions, optional/research, optional/exec-plans, optional/history, release workflow, doctrine guardrail.
```

### Standard sample

```text
Keep: public files, issue templates, labels, Dependabot, CodeQL, link check, docs/surfaces.md.
Use: docs/router.md to delete inactive routes.
ADR/RFC: keep optional/decisions README only unless a durable decision appears.
```

### Strict sample

```text
Keep: CODEOWNERS, ADR route, release/archive route, docs/review-gates.md, optional/github strict workflows when needed.
Use: ADRs for public API, compatibility, license, release, governance, or security decisions.
Delete: research briefs unless research changes implementation.
```

### Research-strict sample

```text
Keep: AGENTS, PROMPT, WORKFLOW, docs/handoff, optional/research, optional/decisions, optional/exec-plans, optional/history.
Use: Brief -> RFC -> ADR -> exec plan -> PR when research changes engineering direction.
Agent rule: GitHub issue + labels + handoff brief is the dispatch contract; a human owns merge.
```

## Human and agent routes

**Human contributor:** read [`docs/contributor-map.md`](docs/contributor-map.md), then [`CONTRIBUTING.md`](CONTRIBUTING.md), then [`docs/engineering-discipline.md`](docs/engineering-discipline.md).

**Agent contributor, or human using an agent:** paste [`PROMPT.md`](PROMPT.md) into the agent and attach a specific issue or handoff brief. [`AGENTS.md`](AGENTS.md) is the longer primer. [`WORKFLOW.md`](WORKFLOW.md) defines the light contract; optional agent rules live under [`optional/agent-rules/`](optional/agent-rules/).

**Maintainer:** choose a profile, route the repository, update CODEOWNERS and contacts, rewrite blank templates, run checks, and record anything unresolved in [`docs/verification.md`](docs/verification.md).

## Checks

Run:

```bash
npm run lint
```

This runs:

```text
scripts/doctor.mjs
scripts/check-links.mjs
scripts/check-template.mjs
scripts/check-router.mjs
```

See [`docs/checks.md`](docs/checks.md), [`docs/review-gates.md`](docs/review-gates.md), and [`docs/verification.md`](docs/verification.md).

## License

The default license is **Apache-2.0**, represented by [`LICENSE`](LICENSE), [`NOTICE`](NOTICE), and `package.json#license`. See [`docs/license-policy.md`](docs/license-policy.md) for exception guidance.

## Sourcing and adaptation

This seed adapts public source material and p-to-q practice rather than mirroring another repository. The strongest source threads are:

- p-to-q organization tone: flat, printable, human-readable interfaces;
- lightweight p-to-q repositories: short public thesis, visible artifact, limitations or receipts;
- Wittgenstein public surfaces: README route split, AGENTS, PROMPT, WORKFLOW, GitHub health files;
- Wittgenstein governance: engineering discipline, labels, CODEOWNERS, ADR/RFC/research lanes;
- Wittgenstein orchestration path: research brief -> handoff -> WORKFLOW -> ADR-0017-style contract;
- `Jah-yee/cursor-rules`: repository-first behavior, smallest correct change, rule routing, no drive-by refactor, stack-specific agent rules.

See [`docs/source-ledger.md`](docs/source-ledger.md) for detailed mapping.
