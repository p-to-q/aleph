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
| Automatic Prompt Engineer | https://github.com/keirp/automatic_prompt_engineer | Public prompt-optimization loop that generates and selects instructions with LLM help. | Useful black-box search shape; do not collapse Aleph into generic instruction optimization. |
| PromptWizard | https://github.com/microsoft/PromptWizard | Task-aware prompt optimization framework with agent-style prompt improvement loops. | Reinforces generate/score/mutate route for hosted black-box work. |
| TextGrad | https://arxiv.org/abs/2406.07496 and https://github.com/zou-group/textgrad | Treats optimization over textual variables as automatic "differentiation" via textual feedback over computation graphs. | Important metaphor and route shape for Aleph; useful for black-box/hybrid optimization framing, but broader than target-output compression. |
| GEPA | https://github.com/CerebrasResearch/gepa | Reflective text evolution with Pareto-style optimization signals and DSPy integration. | Supports Aleph's multi-objective frontier framing; future adapter candidate, not current identity. |
| Prompt Tuning / Prefix Tuning | https://aclanthology.org/2021.emnlp-main.243/ and https://aclanthology.org/2021.acl-long.353/ | Continuous prompt parameters can be optimized while model weights stay frozen. | Strongest technical reading of "prompt is a parameter"; future soft-prompt research route. |
| Reverse Prompt Engineering | https://aclanthology.org/2025.emnlp-main.1333/ | Black-box reverse-prompt recovery from outputs is now an explicit neighboring research line. | Useful contrast: Aleph seeks a usable coordinate for a target output, not recovery of an original hidden prompt. |
| vec2text / embedding inversion | https://github.com/vec2text/vec2text and https://arxiv.org/abs/2310.06816 | Embedding inversion reconstructs text from vector representations; related but solves a different inversion problem. | Keep as adjacent prior art; do not conflate with prompt-coordinate search. |
| Aquin | https://www.aquin.app/ | Instrumentation language: Observe & Find, Simulate & Fix, Debug & Improve, token attribution, loss curves, exposure vectors, evals. | Use as UI/instrumentation inspiration; translate safety/model-debug panels into compression-specific panels. |

## Settled conclusions from research

- Aleph is technically plausible as a staged system.
- The v0 product should be frontend-led and fixture-backed so the core interaction is legible before model integration.
- The real long-term core is a run contract: target + config + candidates + observations.
- White-box claims require logits or model internals; otherwise panels must be black-box, fixture, or simulated.
- Leakage scoring is mandatory because explicit reconstruction can otherwise masquerade as compression.
- ARCA/GCG are implementation candidates, not product identity.
- Black-box prompt optimization families are useful route shapes, not Aleph's final framing.
- TextGrad is especially relevant as a metaphor for prompt-space optimization, but Aleph should keep its narrower target-output identity.
- Pareto / reflective optimization is a stronger fit for Aleph than single-score prompt improvement.
- Soft-prompt methods support the parameter analogy, but should remain future research until they can be related back to discrete prompt coordinates honestly.
- The repository should be artifact-first, not template-first.
- The current `search/` spike is real local-model evidence for the thesis: a fixed MLX Qwen model can propose prompts, generate outputs, score a frontier, and bake measured examples for the demo.
- MLX's upstream runtime surface now includes Apple Silicon and Linux CUDA paths, so Aleph's local white-box route should be described as MLX-backed rather than Apple-Silicon-only.
- That spike should be treated as an experiment engine, not as the stable product API contract.

## Implementation implications

- `packages/core` owns the shared types and pure helpers.
- `packages/fixtures` provides stable demo data.
- `apps/web` consumes `AlephRun` and should not invent its own data model.
- `apps/api` is the stable product API surface and should wrap model/search engines rather than exposing experimental backend shapes directly to the UI.
- `search/` is the current local MLX live-search experiment and is wrapped behind `apps/api` through the `local_mlx_search` adapter. It remains optional until local setup and runtime evidence are available; Apple Silicon is the known maintainer path and Linux CUDA is now the upstream MLX expansion path.
- Future adapters should be pluggable: `mock`, `hosted_black_box`, `local_openai`, `local_white_box`, `arca`, `gcg`.
- Future research-only or adapter candidates now explicitly include reflective/Pareto search and soft-prompt projection.
- Open questions belong in `docs/open-questions.md`, not in hidden assumptions.

## Current gaps

- A real local MLX search runtime exists in `search/`, and `apps/api` has a `local_mlx_search` wrapper that maps live-search-shaped output into `AlephRun`. Current local verification still depends on the optional `search/.venv` MLX environment.
- The demo uses embedding similarity when available with a char-ngram fallback, but the default product metric is not yet settled.
- `search/` computes token-level NLL for precomputed runs, but the product API does not yet expose a stable white-box observation contract.
- No deletion ablation is implemented.
- No persistence layer is chosen.
- The post-Hackathon research mainline was previously implicit; it now needs to stay synchronized across README, research docs, and backlog.

These gaps belong in roadmap or issues, not in hidden assumptions.
