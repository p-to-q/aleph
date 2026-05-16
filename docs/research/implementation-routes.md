# Implementation Routes

This file compares plausible implementation paths. It is not a commitment to ship all of them.

## Route A: Fixture-first console

Use stable sample runs to build the full UI before model integration.

- Best for: Hackathon v0, design validation, component development.
- Strength: reliable demo and clear contract.
- Weakness: no real search.
- Status: current path.

## Route B: Hosted black-box search

Call a hosted model repeatedly and score candidate outputs with similarity, leakage, and stability.

- Best for: first real user-facing prototype.
- Strength: easy to integrate; works without logits.
- Weakness: token loss and attribution are behavioral estimates, not white-box observations.
- Likely features: repeated sampling, best-of-n, semantic similarity, leakage score, eval suite.

## Route C: Local white-box scoring

Run an open-weight model where logits are available. Score target likelihood under prompt conditions.

- Best for: token loss, probability microscope, deletion ablation.
- Strength: makes token-level NLL real.
- Weakness: local setup and model choice become heavy.
- Likely features: teacher-forced likelihood, per-token target loss, top-k alternatives, entropy.

## Route D: ARCA-style discrete optimization

Search token prompts of fixed length using coordinate ascent or related discrete optimization.

- Best for: serious shortest-known prompt search.
- Strength: close to the original reverse-prompt problem.
- Weakness: integration complexity; model/tokenizer-specific.
- Likely role: adapter after the run contract stabilizes.

## Route E: GCG-style hard-prompt optimization

Use gradient-informed token search for prompt suffixes or prompt coordinates.

- Best for: open-weight hard-prompt experiments.
- Strength: powerful optimization signal.
- Weakness: adversarial/safety framing may distort Aleph identity; requires model internals.
- Likely role: research adapter, not default product path.

## Route F: Embedding inversion adjacency

Use embedding inversion methods as an adjacent comparison, not core Aleph behavior.

- Best for: explaining what Aleph is not.
- Strength: useful inversion precedent.
- Weakness: solves vector-to-text, not prompt-to-output compression.
- Likely role: research note only.

## Maintainer recommendation

1. Ship Route A.
2. Add Route B for first real runs.
3. Add Route C when token loss must become real.
4. Treat Routes D and E as optional adapters.
5. Keep Route F as adjacent prior art.
