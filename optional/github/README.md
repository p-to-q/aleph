# Optional GitHub Routes

This directory stores workflows and issue templates that are intentionally not active in the default Seed.

Copy files from here into `.github/` only when the project calls the route and someone will maintain it.

## Contents

| File | Enable when |
| --- | --- |
| `workflows/doctrine-guardrail.yml` | Doctrine-bearing docs exist and ADR/RFC references should be nudged. |
| `workflows/release.yml` | The project publishes tagged GitHub releases. |
| `workflows/auto-merge-dependabot.yml` | Dependabot patch/minor updates may be auto-merged after checks. |
| `workflows/status-labeler.yml` | The issue queue is large enough to justify status automation. |
| `ISSUE_TEMPLATE/governance-note.md` | Governance discussions should have a structured entrypoint. |
| `ISSUE_TEMPLATE/horizon-spike.md` | Research spikes need hypothesis, kill criteria, and timebox. |

## Sample

```text
Strict library:
  copy workflows/release.yml
  copy workflows/doctrine-guardrail.yml
  leave horizon-spike disabled

Research-strict repo:
  copy governance-note and horizon-spike issue templates
  copy doctrine guardrail if ADR/RFC route is enabled
```
