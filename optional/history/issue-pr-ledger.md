# Issue and PR Ledger

This is not a copy of all GitHub history. It is a seed ledger of patterns observed in Wittgenstein that this template should preserve.

## Why this exists

Wittgenstein's useful history is spread across issues, PRs, ADRs, briefs, handoff docs, and workflow changes. A template should not dump that history, but it should keep the **reasons** certain surfaces exist.

## Observed issue patterns

| Pattern | Example signal | Why it mattered | Template response |
| --- | --- | --- | --- |
| Research backlog | Second-pass research backlog and training-stack re-audit issues | Research needed to change issue priority, acceptance gates, ADR/RFC input, or archive decisions rather than remain as notes | Keep `optional/research/briefs/`, `slice/research`, and brief -> RFC/ADR/issue conventions. |
| Maintainer re-audit | Low-confidence implementation ledger and post-merge review loops | Green CI was not enough; merged work could still need truth-surface reconciliation | Add `docs/review-gates.md`, `optional/history/decision-map.md`, and final verification review. |
| Owner review | Model-owner review packs and specialist review issues | Some work requires domain ownership separate from implementation | CODEOWNERS and issue templates distinguish owner review from code tasks. |
| Infrastructure receipts | DVC/GPU CI, experiment tracking, lazy weight fetch, publish tarball checks | Infra claims need runnable evidence, not status prose | Keep receipts language in engineering discipline and template checks. |
| Research-derived implementation | Eval harness and training issues carried research lineage | Implementation needed to cite the brief or decision that justified it | Preserve labels as contracts and the research-derived lane. |
| Tracker vs action | Some issues waited on external events | Auto-running those issues would violate their semantics | Keep tracker labels and exclude them from agent dispatch. |
| Orchestration sourcing | Brief K -> handoff -> WORKFLOW -> ADR-0017 | WORKFLOW came from OpenAI Symphony-shaped orchestration prior art, adopted as contract not runtime | Preserve sourcing inside `WORKFLOW.md` and keep runtime optional. |

## Observed PR patterns

| Pattern | Example signal | Why it mattered | Template response |
| --- | --- | --- | --- |
| Truth-surface refresh | Maintainer truth surface refresh and training DVC status clarification | Documentation had to converge after implementation moved | Keep content-sync and surfaces docs. |
| Small validation PRs | Codec error tests and dry-run stabilization | Small PRs with acceptance gates were easier to review | Keep PR validation checklist and smallest-effective-change discipline. |
| Release and packaging checks | Publish tarball and release workflow PRs | Release confidence needed package-level receipts | Include release workflow placeholder and changelog discipline. |
| Agent/Codex delivery foundations | Agent-named PRs and handoff surfaces | Agent work needed explicit read order and reporting rules | Keep AGENTS/PROMPT/WORKFLOW/handoff as first-class files. |
| Dependabot grouped updates | Multiple grouped dependency PRs | Routine updates should not consume maintainer attention | Keep Dependabot grouping and conservative auto-merge. |

## Ledger maintenance

Use `scripts/sync-github-ledger.mjs` as a starting point for a real sync script. The first version is intentionally dependency-free and prints the exact `gh` commands to run rather than assuming every project has GitHub CLI configured.

## Sample ledger entry

```text
Pattern: maintainer re-audit
Source: issue or PR URL
Finding: CI passed, but truth surfaces drifted
Action: update docs/surfaces.md and add a review-gate checklist item
```
