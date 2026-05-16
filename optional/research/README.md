# Research

Research docs are optional. Use them when the project makes technical bets that should be pressure-tested before they become implementation work.

A research note should feed one of three outcomes:

1. no action — useful context, no change;
2. RFC/ADR — decision-worthy proposal;
3. exec plan or issue — concrete implementation slice.

Avoid research docs that become orphaned essays. Each note should state what it changes or what it deliberately does not change.

## Sample

```text
Research question: should we adopt an external orchestration runtime?
Verdict: adopt the repo-root WORKFLOW contract, not the runtime.
Output: update WORKFLOW.md; open RFC only if a contributor proposes a concrete runtime.
```
