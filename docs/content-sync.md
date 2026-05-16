# Content Sync

The template has several public truths. They should reinforce each other instead of becoming parallel stories.

## Source surfaces

| Surface | Role |
| --- | --- |
| `README.md` | Short public entrypoint and profile selector. |
| `docs/project-brief.md` | Project-specific purpose, status, audience, and constraints. |
| `docs/router.md` | Which routes are active and which should be deleted. |
| `docs/project-scale.md` | Why the chosen profile is appropriate. |
| `docs/surfaces.md` | Stable, experimental, internal, and archived surfaces. |
| `AGENTS.md` / `PROMPT.md` / `WORKFLOW.md` | Human/agent operating truth when agent work is enabled. |
| `CHANGELOG.md` | Release-facing changes. |
| `optional/history/issue-pr-ledger.md` | Optional historical summary when GitHub issues/PRs encode decisions. |

## Cross-link contract

When one surface changes, check its neighbors:

| Change | Also check |
| --- | --- |
| README changes profile or promise | `docs/project-scale.md`, `docs/router.md`, `docs/surfaces.md` |
| Router changes route behavior | `templates/profiles/`, `checks/profile-matrix.json`, `docs/verification.md` |
| Agent workflow changes | `AGENTS.md`, `PROMPT.md`, `WORKFLOW.md`, `docs/handoff/`, `optional/agent-rules/` |
| License or contribution rule changes | `LICENSE`, `NOTICE`, `CONTRIBUTING.md`, `docs/license-policy.md` |
| New stable public surface | `README.md`, `docs/surfaces.md`, `CHANGELOG.md`, release notes if enabled |
| ADR/RFC route enabled | `optional/decisions/`, `optional/github/workflows/doctrine-guardrail.yml`, `docs/review-gates.md` |
| Research route enabled | `optional/research/`, `optional/exec-plans/`, `optional/history/` |

## Recommended metadata

Projects may add `project.yml` later with:

```yaml
name: project-name
status: experimental
license: Apache-2.0
profile: standard
public_surfaces:
  - README.md
  - packages/core
experimental_surfaces: []
agent_workflow: false
```

Do not add metadata until there is a consumer for it.

## Sample sync rule

```text
If README says a feature is stable, docs/surfaces.md must list it as stable too.
If AGENTS.md names a required read order, PROMPT.md should not contradict it.
If CHANGELOG.md announces a release, docs/project-brief.md should not describe it as unreleased.
If docs/router.md says a route is optional, README should not imply it is mandatory.
```
