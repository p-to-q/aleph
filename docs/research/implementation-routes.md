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
- Extension path: candidate generation and mutation loops inspired by APE / PromptAgent / PromptWizard without inheriting their product identity.

## Route C: Local white-box scoring

Run an open-weight model where logits are available. Score target likelihood under prompt conditions.

- Best for: token loss, probability microscope, deletion ablation.
- Strength: makes token-level NLL real.
- Weakness: local setup and model choice become heavy.
- Likely features: teacher-forced likelihood, per-token target loss, top-k alternatives, entropy.
- Current evidence: `search/aleph_search.py` already runs an MLX Qwen evaluator and computes teacher-forced token NLL for precomputed runs.
- Runtime note: Apple Silicon remains the known maintainer route, while upstream MLX now also supports Linux CUDA backend deployments.
- Integration requirement: expose the result through `apps/api` and `AlephRun` before treating it as a product surface.

## Route C1: Local live-search spike

Use the same local MLX model as proposer and evaluator for shallow prompt-frontier search.

- Best for: Hackathon demo credibility and local no-cloud operation.
- Strength: very close to the Aleph thesis because the fixed local model is the decoder.
- Weakness: expensive startup, serialized requests, heuristic proposer, and metric/runtime assumptions live in one script.
- Current status: implemented in `search/server.py` and `search/aleph_search.py`.
- Hardware scope: MLX-backed rather than Apple-Silicon-only; Apple Silicon is the present local path and Linux CUDA is the upstream expansion path.
- Likely role: wrap behind `apps/api` as a `local_mlx_search` adapter.

## Route D: ARCA-style discrete optimization

Search token prompts of fixed length using coordinate ascent or related discrete optimization.

- Best for: serious shortest-known prompt search.
- Strength: close to the original reverse-prompt problem.
- Weakness: integration complexity; model/tokenizer-specific.
- Likely role: adapter after the run contract stabilizes.

## Route D1: Reflective / Pareto prompt search

Use a reflective or evolutionary loop that mutates candidate prompts while ranking them on multiple dimensions.

- Best for: medium-term search quality once the product metrics are stable.
- Strength: aligns with Aleph's frontier object better than single-score optimization.
- Weakness: easy to overfit to a custom score before the score itself is trusted.
- Likely role: research adapter after leakage, stability, and metric semantics are clearer.

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

## Route G: Soft prompt to hard prompt projection

Optimize a continuous prompt or prefix under frozen model weights, then project back into discrete prompts.

- Best for: later research on whether Aleph can bridge continuous optimization and human-readable coordinates.
- Strength: the most direct "backprop over prompt parameters" route.
- Weakness: projected prompts may be unstable, unnatural, or hard to interpret.
- Likely role: future research route, not early product path.

## Maintainer recommendation

1. Ship Route A.
2. Keep Route C1 as the Hackathon live-search engine, but wrap it behind `apps/api`.
3. Add Route B for hosted black-box runs when local setup is too heavy.
4. Promote Route C observations when `AlephRun` has stable white-box fields.
5. Treat Routes D, D1, and E as optional adapters.
6. Keep Route F as adjacent prior art.
7. Park Route G until the discrete product and scoring story are stronger.
