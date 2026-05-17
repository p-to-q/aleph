# Aleph

> **Aleph is a reverse prompt search engine.**
>
> Given a target output, a fixed model, a fixed decoding rule, a fixed metric, and a fixed search budget, Aleph searches for the **shortest known prompt coordinates** that can reproduce or approximate the target, then visualizes the compression path from explicit reconstruction to compact prompt coordinates.

Read the full project thesis in [THESIS.md](THESIS.md).

## The image

> In Borges' image, the Aleph is a point in space that contains every other point.
> 
> Seen from any angle, it reveals the universe at once: no overlap, no veil, no obstruction.
> 
> In that tiny sphere, the narrator sees：

- the sea, dawn and dusk, and the crowds of the Americas
- a silver spiderweb at the center of a pyramid
- a shattered labyrinth — London
- every mirror in his bedroom
- grapes, snow, tobacco, metal, and steam in a California garden
- the red desert, and every grain of sand
- Beatriz Viterbo in Inverness, and the unreadable letter she wrote to Daneri
- his own face, his own inner body
- every word in the book now being read
- and everything else

Aleph adopts that image for model output space: the model contains a finite library of possible continuations, and a prompt is a coordinate that opens one region of that space.

a small place for seeing too much,

gently.

## What it is

- A target-output-first interface, not a prompt-polishing assistant.
- A compression slider over discrete Pareto candidate points.
- A workbench for prompt length, target fit, stability, leakage, token loss, attribution, and evals.
- A repository shaped for human and agent continuation: clear thesis, visible artifact, receipts, limitations, and small reviewable changes.

## What it is not

- It does not prove a globally shortest prompt.
- It does not equate model-relative description length with strict Kolmogorov complexity.
- It does not claim white-box observations without logits or model internals.
- It does not treat context window length as the right endpoint of the slider.

## Current status

Experimental scaffold. The repository is ready for a Hackathon v0 and leaves room for long-term model adapters, real scoring, non-leaking mode, and future white-box observation panels that require model logits or internals.

## Repository map

```text
THESIS.md             Product and research thesis
web/                  Active Next.js launch surface
apps/web              Archived legacy/reference React/Vite console
apps/api              FastAPI orchestration layer (mock + local MLX search adapter)
search/               Local MLX live-search engine (requires Apple Silicon)
packages/core         Shared AlephRun data contracts and scoring helpers
packages/ui           UI component shells for console panels
packages/fixtures     Sample runs used by the demo and checks
docs/                 Thesis support, strategy, architecture, research, UI, decisions, plans, verification
scripts/              Repository health checks that run without external installs
```

Start with [docs/contributor-map.md](docs/contributor-map.md) if you are joining the project. The current implementation path and fallbacks are in [docs/strategy.md](docs/strategy.md).
For the clearest snapshot of what is settled, implemented, researched, and still open, read [docs/state-of-play.md](docs/state-of-play.md).
Near-term follow-up work lives in [docs/next-backlog.md](docs/next-backlog.md).

## Quick start

The repository is intentionally usable before model integration.

```bash
npm run lint
```

For the current launch UI:

```bash
./start.sh
```

The static HTML prototype is available at:

```text
apps/web/static/aleph-atlas-console.html
```

## Short-term plan

The current maintainer strategy is console-first, fixture-backed, and adapter-ready. If model runtime fails, the static prototype and fixture run must still communicate the thesis.


[x] Ship a frontend-led Hackathon console using fixtures and mock observations.
[x] Preserve the compression slider as the main interaction.
[x] Make target input, current prompt, model output, Pareto frontier, token loss, search dial, waveform, attribution, exposure vectors, and eval suite work from one `AlephRun` contract.
[x] Mark every mocked or simulated observation clearly.

## Long-term plan

[ ] Add a model-adapter API with black-box and local white-box routes.
[ ] Support repeated sampling, leakage scoring, and Pareto reranking.
[ ] Add teacher-forced likelihood and token-level loss when logits are available.
[ ] Add deletion ablation, prompt-token attribution, non-leaking mode, saved runs, cross-model transfer, and research reports.

## License

Apache-2.0.
