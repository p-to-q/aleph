# Execution Plans

Execution plans are optional. Use them when a change is too large for one PR but already decided enough to implement.

- `active/` — current plans.
- `archived/` — old or superseded plans retained as receipts.

A plan should be more concrete than an RFC and less noisy than a sequence of disconnected issues.

## Sample

```text
Plan: migrate documentation site
Slices:
1. inventory current docs
2. define stable/experimental surfaces
3. move docs and preserve redirects
4. run link check and UX review
Done when: docs build, links pass, early adopter can find quickstart in <60s
```
