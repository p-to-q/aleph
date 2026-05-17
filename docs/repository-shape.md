# Repository Shape

Aleph borrows the useful part of the p-to-q seed: clear thesis, visible artifact, receipts or limitations, short docs map, license, and small reviewable changes. It does not try to obey the template as a rigid architecture.

## Maintainer decision

Use an **artifact-first product lab** shape:

```text
root public files       public face and delegation contracts
THESIS.md               durable product/research thesis
apps/                   runnable artifacts
web/                    current Next.js launch surface
packages/               shared code contracts
packages/fixtures       stable demo data
docs/                   architecture, research, UI, decisions, plans, verification
scripts/                lightweight checks
```

The previous `optional/` template route has been removed. Decisions and plans now live under `docs/decisions/` and `docs/plans/` because they are active project material, not template leftovers.

## Active surfaces

| Surface | Why it exists |
|---|---|
| `THESIS.md` | The product/research north star. |
| `README.md` | Short public entrypoint. |
| `docs/core-concept.md` | Settled/open/deferred split. |
| `docs/architecture.md` | How implementation pieces fit. |
| `docs/surfaces.md` | What is stable, experimental, simulated, stub, future, or archived. |
| `docs/repository-governance.md` | Post-Hackathon path, naming, branch, and claim cleanup rules. |
| `docs/research/` | Source-backed research that changes implementation or roadmap. |
| `docs/decisions/` | Durable decisions. Sparse by design. |
| `docs/plans/` | Multi-file execution plans. |
| `AGENTS.md` and `PROMPT.md` | Safe delegation to agents. |
| `WORKFLOW.md` | Lightweight work contract, not a runtime. |

## Parked ideas

Do not add these until the trigger is real:

- release archive and changelog discipline;
- CODEOWNERS;
- full RFC process;
- strict label automation;
- doctrine guardrails;
- user/team account docs;
- production deployment docs;
- model-provider-specific integration guide.

## Upgrade triggers

Add more process only when it removes confusion:

- public API compatibility matters;
- multiple maintainers need review ownership;
- releases are tagged and supported;
- research proposals repeatedly alter implementation;
- agent handoff becomes routine rather than occasional;
- a real model adapter creates operational/security obligations.

## Rule of thumb

If a file cannot help a new human or agent make a better next change, remove it, archive it, or rewrite it.
