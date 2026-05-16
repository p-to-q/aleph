# Source Ledger

This repository is an adapted product/research scaffold, not a verbatim mirror of any source. The ledger records what was inspected and how it shaped Aleph.

## p-to-q repository template

Source: https://github.com/p-to-q/repo-template

Observed:

- clear thesis -> visible artifact -> receipts or limitations -> short docs map -> license;
- file-first repository surface;
- profile selection exists, but the template itself says unused routes should be removed or parked;
- optional decisions, research, exec plans, history, release, strict workflows, and agent rules;
- repository-first agent behavior and explicit validation.

Aleph adaptation:

- use p-to-q as a tone and discipline reference, not a binding architecture;
- choose an artifact-first product-lab shape;
- keep thesis, public entrypoint, contracts, research notes, sparse decisions, plans, and lightweight agent delegation;
- remove the `optional/` directory so active material is not hidden behind template scaffolding;
- park release, strict workflow, full RFC, CODEOWNERS, and history routes.

## Research and implementation sources

| Source | URL | Aleph use |
|---|---|---|
| ARCA paper | https://arxiv.org/abs/2303.04381 | Closest white-box/discrete-optimization reference for reverse prompt search. |
| `auditing-llms` repository | https://github.com/ejones313/auditing-llms | Concrete Reversing LLMs command path with `--prompt_length`. |
| GCG paper | https://arxiv.org/abs/2307.15043 | Future hard-prompt optimization adapter, not product identity. |
| `llm-attacks` repository | https://github.com/llm-attacks/llm-attacks | Official GCG implementation reference and integration cautions. |
| Probe Sampling paper | https://arxiv.org/abs/2403.01251 | Possible future acceleration route for candidate search. |
| vec2text repository | https://github.com/vec2text/vec2text | Adjacent inversion work; clarifies what Aleph is not. |
| Text Embeddings Reveal Almost As Much As Text | https://arxiv.org/abs/2310.06816 | Embedding inversion reference; adjacent but not prompt-coordinate search. |
| Aquin | https://www.aquin.app/ | UI/instrumentation inspiration: token attribution, loss, exposure, evals. |

## Conversation artifacts

The conversation produced product decisions, logo directions, UI prototypes, and architecture choices. They are summarized in `docs/archive/conversation-record.md` and kept as prototype HTML under `docs/archive/prototypes/`.

Reference screenshots were removed in the second repository pass to avoid confusing visual research with durable product source.
