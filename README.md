# Aleph

> **Aleph is a reverse prompt search engine.**
>
> Given a target output, a fixed model, a fixed decoding rule, a fixed metric, and a fixed search budget, Aleph searches for the **shortest known prompt coordinates** that can reproduce or approximate the target, then visualizes the compression path from explicit reconstruction to compact prompt coordinates.

Read the full project thesis in [THESIS.md](THESIS.md).

**Live site:** [https://aleph.ptoq.io](https://aleph.ptoq.io)

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

a small place for seeing too much,<br/>
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

Aleph is at `v1.0.1`: a small formal release of the active Next.js launch surface, shared `AlephRun` contract, fixture demos, local MLX evidence traces, a hosted black-box model adapter, and the first release polish pass on navigation, mode selection, and evidence copy.

The release is intentionally honest about evidence:

- Precomputed examples are fixture-backed and labeled as such.
- `spring` and `crush` now include real local MLX token text / token NLL traces, but they are low-fit exploratory runs, not polished success demos.
- Hosted custom API runs call an external OpenAI-compatible model from the server side and return real candidate prompts and outputs as black-box observations.
- Hosted black-box runs do not expose logits or token NLL; token-loss panels only claim model-internal evidence when those fields are present.

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

The repository is intentionally usable without private model credentials.

```bash
npm run lint
npm run test
npm --workspace web run build
```

For the current launch UI:

```bash
./start.sh
```

Open the printed localhost URL and choose a precomputed example, local MLX mode, or hosted custom API mode depending on the environment you have configured.

## Hosted API

The active web app exposes `POST /api/search` as an `AlephRun`-compatible adapter. It can run in three modes:

- `fixture`: precomputed runs from `web/public/aleph-frontier.json`.
- `hosted black-box`: server-side calls to an OpenAI-compatible `/chat/completions` endpoint.
- `local MLX`: optional Apple Silicon search service through `search/server.py`.

Hosted API credentials must stay server-side. Do not use `NEXT_PUBLIC_` for API keys.

```bash
ALEPH_CUSTOM_API_BASE_URL=https://zapi.aicc0.com/v1
ALEPH_CUSTOM_API_MODEL=deepseek-v4-pro
ALEPH_CUSTOM_API_KEY=...
ALEPH_CUSTOM_API_FALLBACK_BASE_URL=https://jiuuij.de5.net/v1
ALEPH_CUSTOM_API_FALLBACK_MODEL=qwen3.6-27b-nothinking
ALEPH_CUSTOM_API_FALLBACK_KEY=...
```

The browser talks to the same-origin route by default:

```bash
NEXT_PUBLIC_CLAUDE_API=
```

Leave `NEXT_PUBLIC_SEARCH_API` unset unless you have a deployed or tunneled local-MLX-compatible service.

The static HTML prototype is available at:

```text
apps/web/static/aleph-atlas-console.html
```

## Short-term plan

The current maintainer strategy is file-first, UI-first, and adapter-honest. If model runtime fails, the fixture path must still communicate the thesis without pretending to be live evidence.


[x] Ship a frontend-led console using fixtures and explicitly labeled observations.
[x] Preserve the compression slider as the main interaction.
[x] Make target input, current prompt, model output, Pareto frontier, token loss, search dial, waveform, attribution, exposure vectors, and eval suite work from one `AlephRun` contract.
[x] Mark every mocked or simulated observation clearly.
[x] Add a server-side hosted black-box API adapter for real prompt/output candidates.
[x] Add real local MLX token traces for `spring` and `crush` fixtures.

## Long-term plan

[x] Add a model-adapter API with hosted black-box and local MLX routes.
[ ] Support repeated sampling, leakage scoring, and Pareto reranking.
[ ] Add teacher-forced likelihood and token-level loss when logits are available.
[ ] Add deletion ablation, prompt-token attribution, non-leaking mode, saved runs, cross-model transfer, and research reports.

## Release gate

Before tagging a release, run:

```bash
npm run lint
npm run test
npm --workspace web run build
npm run api:smoke
apps/api/.venv/bin/python -m pytest apps/api/tests -q
search/.venv/bin/python search/preflight.py
git diff --check
```

For hosted deployments, also run a real `/health` and `/api/search` smoke with server-side API keys configured. The expected hosted observation mode is `black_box`.

## License

Apache-2.0.
