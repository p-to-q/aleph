# Maintenance Routes

Aleph uses an artifact-first shape and keeps only the routes that make the next change clearer. This file is intentionally practical rather than template-complete.

## Active routes

| Route | Location | Status | Reason |
|---|---|---|---|
| Thesis | `THESIS.md` | active | North star for product, research, and language. |
| Public entrypoint | `README.md` | active | Short project face. |
| Concept boundary | `docs/core-concept.md`, `docs/open-questions.md` | active | Separates settled, open, and deferred claims. |
| Repository shape | `docs/repository-shape.md` | active | Explains why the repo is not a rigid template clone. |
| Engineering docs | `docs/architecture.md`, `docs/surfaces.md`, `docs/engineering-discipline.md` | active | Prevents misplaced logic and overclaims. |
| Research notes | `docs/research/` | active but bounded | Research must change implementation or roadmap. |
| Decisions | `docs/decisions/` | active but sparse | Used only for durable architecture decisions. |
| Plans | `docs/plans/` | active for multi-file work | Used when work spans app, core, docs, and fixtures. |
| Agent delegation | `AGENTS.md`, `PROMPT.md`, `WORKFLOW.md` | active-light | Supports agents without creating an orchestration runtime. |
| Archive | `docs/archive/` | active as receipts | Keeps prototypes and summarized decisions, not screenshots or product source. |

## Parked routes

| Route | Status | Revisit when |
|---|---|---|
| Full RFC process | parked | Research proposals need formal review before implementation. |
| Release archive | parked | The repository has tagged releases or supported versions. |
| Strict GitHub workflows | parked | Maintainers need CodeQL, release automation, or doctrine guardrails. |
| History ledger | parked | Issues/PRs contain decisions not captured elsewhere. |
| CODEOWNERS | parked | Multiple maintainers own review gates. |
| Full agent orchestration | parked | Agent tasks become routine and need labels/handoff enforcement. |

## Cleanup rule

If a route stops helping, remove it or archive it. Unused process is not rigor; it is noise.
