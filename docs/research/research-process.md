# Research Process

This file records the research that currently shapes Aleph. It is a source ledger for product and technical direction, not a claim that all referenced methods are implemented.

## Research questions

1. Is reverse prompt search a real technical direction or only a metaphor?
2. Which existing methods are closest to Aleph's target behavior?
3. Which parts should become v0 product surfaces, and which should remain future adapters?
4. How should the repository preserve research without turning uncertain ideas into product facts?
5. Which repository conventions help future humans and agents without freezing Aleph into template noise?

## Sources inspected

| Source | URL | What was observed | Effect on Aleph |
|---|---|---|---|
| p-to-q `repo-template` | https://github.com/p-to-q/repo-template | File-first seed; visible files are the contract; delete or park unused routes; lightweight mode is clear thesis, visible artifact, receipts/limitations, short docs map, license. | Keep the tone, not the rigid profile. Add `THESIS.md`, preserve checks, remove `optional/`, move decisions/plans into `docs/`. |
| p-to-q `AGENTS.md` | https://raw.githubusercontent.com/p-to-q/repo-template/main/AGENTS.md | Repository-first agent behavior, small reviewable changes, explicit validation, no hidden architectural decisions. | Strengthen `AGENTS.md`, `PROMPT.md`, and `engineering-discipline.md`. |
| p-to-q `WORKFLOW.md` | https://raw.githubusercontent.com/p-to-q/repo-template/main/WORKFLOW.md | Workflow is a contract, not a mandatory runtime; chat transcripts are not durable unless summarized. | Keep workflow lightweight and move decisions into docs, not raw chat. |
| ARCA paper | https://arxiv.org/abs/2303.04381 | Auditing can be formulated as discrete optimization over prompts/outputs; sparse discrete search can be attacked with ARCA. | Treat ARCA as closest white-box optimization reference, but not v0 scope. |
| `ejones313/auditing-llms` | https://github.com/ejones313/auditing-llms | Includes a Reversing LLMs path that produces prompts for fixed outputs and exposes `--prompt_length`. | Confirms reverse-search direction is implementable; informs future `arca` adapter. |
| GCG paper | https://arxiv.org/abs/2307.15043 | Greedy/gradient search can automatically produce token suffixes that steer outputs. | Keep GCG as future hard-prompt-search adapter; do not inherit the attack identity. |
| `llm-attacks` repo | https://github.com/llm-attacks/llm-attacks | Official GCG repo; includes a demo and later `nanogcg` note. | Document integration risk and avoid premature adapter commitment. |
| Probe Sampling paper | https://arxiv.org/abs/2403.01251 | GCG can be accelerated with draft-model filtering when draft and target predictions are similar. | Potential v2/v3 optimization path, not Hackathon scope. |
| vec2text / embedding inversion | https://github.com/vec2text/vec2text and https://arxiv.org/abs/2310.06816 | Embedding inversion reconstructs text from vector representations; related but solves a different inversion problem. | Keep as adjacent prior art; do not conflate with prompt-coordinate search. |
| Aquin | https://www.aquin.app/ | Instrumentation language: Observe & Find, Simulate & Fix, Debug & Improve, token attribution, loss curves, exposure vectors, evals. | Use as UI/instrumentation inspiration; translate safety/model-debug panels into compression-specific panels. |

## Settled conclusions from research

- Aleph is technically plausible as a staged system.
- The v0 product should be frontend-led and fixture-backed so the core interaction is legible before model integration.
- The real long-term core is a run contract: target + config + candidates + observations.
- White-box claims require logits or model internals; otherwise panels must be black-box, fixture, or simulated.
- Leakage scoring is mandatory because explicit reconstruction can otherwise masquerade as compression.
- ARCA/GCG are implementation candidates, not product identity.
- The repository should be artifact-first, not template-first.
- The current `search/` spike is real local-model evidence for the thesis: a fixed MLX Qwen model can propose prompts, generate outputs, score a frontier, and bake measured examples for the demo.
- That spike should be treated as an experiment engine, not as the stable product API contract.

## Implementation implications

- `packages/core` owns the shared types and pure helpers.
- `packages/fixtures` provides stable demo data.
- `apps/web` consumes `AlephRun` and should not invent its own data model.
- `apps/api` is the stable product API surface and should wrap model/search engines rather than exposing experimental backend shapes directly to the UI.
- `search/` is the current local MLX live-search experiment and is wrapped behind `apps/api` through the `local_mlx_search` adapter. It remains optional until local setup and runtime evidence are available.
- Future adapters should be pluggable: `mock`, `hosted_black_box`, `local_openai`, `local_white_box`, `arca`, `gcg`.
- Open questions belong in `docs/open-questions.md`, not in hidden assumptions.

## Current gaps

- A real local MLX search runtime exists in `search/`, and `apps/api` has a `local_mlx_search` wrapper that maps live-search-shaped output into `AlephRun`. Current local verification still depends on the optional `search/.venv` MLX environment.
- The demo uses embedding similarity when available with a char-ngram fallback, but the default product metric is not yet settled.
- `search/` computes token-level NLL for precomputed runs, but the product API does not yet expose a stable white-box observation contract.
- No deletion ablation is implemented.
- No persistence layer is chosen.

These gaps belong in roadmap or issues, not in hidden assumptions.
