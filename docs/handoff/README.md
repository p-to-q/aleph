# Handoff Briefs

Handoff briefs are issue-specific context packets for humans or agents. They are not permanent doctrine.

Use a handoff brief when:

- an issue requires more context than the body should hold;
- a human delegates to an agent;
- work is split across multiple contributors;
- a task stalled and needs a clean restart.

When the work lands, either delete the brief or move durable content into docs, ADRs, RFCs, issues, or PRs.

## Sample

```text
Handoff: fix link checker false positive
Reads: scripts/check-links.mjs, docs/checks.md
Do: add anchor handling for relative links
Do not: introduce external network fetching
Validation: npm run check:links && npm run check:template
```
