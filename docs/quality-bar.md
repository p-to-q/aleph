# Quality Bar

Aleph should improve by becoming clearer, more runnable, and more honest. Do not optimize the repository merely because optimization is possible.

## Definition of an 80-point repository

A contributor should be able to answer these within minutes:

1. What is Aleph?
2. What is settled?
3. What is still open?
4. What can I run now?
5. Which data shape connects UI, fixtures, and future APIs?
6. Which observations are real, fixture, mock, simulated, black-box, or white-box?
7. What should I not claim yet?
8. What is the next smallest useful change?

## Local quality rules

### Product language

Use:

- shortest known prompt;
- fixed model / decoding / metric / budget;
- explicit reconstruction baseline;
- compression path;
- candidate point;
- Pareto frontier;
- leakage score;
- observation mode.

Avoid:

- globally shortest prompt;
- true Kolmogorov complexity;
- context window as semantic endpoint;
- white-box language without logits;
- fixture values as evidence.

### Code shape

- UI panels consume `AlephRun`; they should not invent parallel data models.
- Search, scoring, leakage, frontier, and observation logic belong outside visual components.
- New runtime adapters must return the same candidate/observation shape as fixtures.
- Mock data must be easy to delete or replace.

### Docs shape

- Durable claims belong in `THESIS.md`, `docs/core-concept.md`, or `docs/decisions/`.
- Work plans belong in `docs/plans/`.
- Research receipts belong in `docs/research/`.
- Old prototypes belong in `docs/archive/` and should not be treated as source files.
- If a document exists only for continuity and no longer helps, remove it.

## Review checklist

Before merging a meaningful change, ask:

- Did the change preserve the target-output-first product identity?
- Did it keep the slider tied to discrete candidates?
- Did it preserve the explicit reconstruction and shortest-found endpoints?
- Did it keep leakage visible?
- Did it label mock/simulated data?
- Did it reduce confusion for the next contributor?
- Did it avoid committing to unresolved research choices?

## Useful restraint

The right repository is not the one with the most documents, components, or adapters. It is the one where the next correct move is obvious.
