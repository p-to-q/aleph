# Research Briefs

Briefs are self-contained research notes that pressure-test one claim, lineage, product convention, or implementation route.

The Wittgenstein source repository uses lettered briefs and a lineage map to connect Brief -> RFC -> ADR -> exec-plan -> code. This template keeps the mechanism but not the project-specific content.

Use `TEMPLATE.md` for new briefs.

## Sample

```text
Brief A — orchestration prior art
Question: which primitives should we borrow?
Verdict: WORKFLOW.md as contract; runtime deferred.
Feeds: RFC-0001 or ADR-0001 if the choice becomes durable.
```
