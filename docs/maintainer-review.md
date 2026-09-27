# Maintainer Review

This review records the current maintainer judgment about the repository shape and first-round project direction.

## Judgment

Final review conclusion: the current global optimum is not to add more process or force a heavier template. It is to keep the repository artifact-first, define a fallback ladder, make every future runtime adapter conform to the same visible run contract, and keep `docs/state-of-play.md` as the short confidence map for what is settled, implemented, researched, and still open.


Aleph should be an artifact-first research product repository, not a template-first repository and not a pure research dump.

The best shape is:

```text
thesis -> runnable console -> shared run contract -> fixtures -> research receipts -> sparse decisions -> plans
```

The repository should be comfortable for three readers:

- a user who wants to understand the product quickly;
- a developer who wants to make a small correct change;
- an agent that needs boundaries, read order, and validation gates.

## First-round decisions now settled

- The product thesis lives in `THESIS.md`.
- The public README stays short and points to the thesis.
- The p-to-q seed is a reference for tone and discipline, not a rigid scaffold.
- `optional/` is removed; active decisions and plans live in `docs/`.
- The durable implementation object remains `AlephRun`.
- The Hackathon build remains frontend-led and fixture-backed.
- Real model search is adapter work, not a prerequisite for UI/product clarity.
- White-box panels cannot claim truth without logits or internals.
- Typed surface-copy, recoverability, trace-integrity, and source evidence are first-class; no one
  scalar `leakage` field may impersonate them.

## First-round choices still open

Open questions are tracked in `docs/open-questions.md`; active implementation priorities are in
`docs/next-backlog.md`; and `docs/strategy.md` retains historical product-shell fallbacks. The
most important open choices are:

- first PR0-conformant research-grade adapter and archive;
- primary versioned metrics and calibration thresholds;
- first typed copy/recoverability probe suite and thresholds;
- first search strategy;
- persistence strategy;
- console-vs-landing emphasis.

These are intentionally left flexible. Do not resolve them silently in code.

## What to avoid next

- Do not add process because a template has it.
- Do not add model-runtime complexity before the UI contract is coherent.
- Do not represent fixture observations as research evidence.
- Do not hide new product assumptions inside React components.
- Do not expand the archive into a dumping ground.

## Next best changes

1. Land the finite-theory statement map and threshold/compiler checks without rewriting PR #103's
   golden artifact.
2. Implement one PR0-conformant real-model search archive with a six-account ledger and independent
   replay.
3. Reproduce MiniPrompt/ACR behind the same archive and evaluator boundary.
4. Add JSON import with schema validation while preserving `AlephRun` projection identity.
5. Migrate the legacy scalar `leakage` wire field only through a versioned typed-evidence change.

## Review cadence

After every substantial change, ask:

- Did this make the thesis clearer?
- Did this make the artifact more runnable?
- Did this reduce or increase confusion?
- Did this introduce a product claim that belongs in docs first?
- Did this preserve the distinction between settled, open, deferred, simulated, and real?
