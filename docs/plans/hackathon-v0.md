# Hackathon v0 Execution Plan

## Goal

Ship a credible Aleph workbench that turns one target output into a visible compression path:

```text
target output -> candidate prompts -> model outputs -> scores -> ranked path
```

The Hackathon win condition is not "best search." It is a runnable instrument that makes the Aleph thesis legible without overclaiming.

## Product spine

The v0 artifact must make these ideas obvious:

- `Aleph` is about prompt coordinates for an output, not generic prompting help.
- `Shortest Found` is a discovered candidate, not a global optimum.
- `Explicit Reconstruction` is the right endpoint baseline.
- The core object is a `Compression Path`, not one prompt.
- The visible metrics are `Closeness`, `Compression`, `Reliability`, and `Copying`.
- `Pareto Map` is the professional view; a simpler path view can sit on top.

## Stack choice

### Chosen v0 stack

- frontend: existing React/Vite app in `apps/web`
- API: FastAPI in `apps/api`
- local model route: `mlx-lm` on Apple Silicon
- default local model target: `Qwen/Qwen3-8B-MLX-4bit`

### Why this is the right local optimum

- FastAPI + Pydantic is a strong fit for nested `AlephRun`-style request/response bodies and gives schema + docs for free.
- `mlx-lm` is the Apple-Silicon-native runtime and already supports both a Python API and an OpenAI-compatible local server.
- Qwen3 8B 4-bit is a realistic local model size for a Mac-based Hackathon while preserving enough quality to make the path meaningful.
- The repo already has a React/Vite scaffold, so switching to a different frontend framework in v0 would slow the product line without clarifying the thesis.

## Architecture decision

### v0 backend shape

Use FastAPI as the stable orchestration layer, not as a monolithic model runtime process.

```text
web console
  -> FastAPI request/response contract
  -> adapter boundary
     -> mock adapter
     -> local OpenAI-compatible adapter
        -> mlx_lm.server
```

### Why this is better than directly embedding MLX first

- It preserves a fast fallback when local runtime setup fails.
- It keeps the API contract stable while model/runtime choices change.
- It makes later black-box adapters and white-box routes easier to add.
- It optimizes for both Hackathon speed and long-term interchangeability.

### v0 adapter policy

- first adapter: `mock`
- second adapter: local OpenAI-compatible model endpoint backed by `mlx_lm.server`
- do not block frontend work on local model availability

## v0 scope

### Must ship

- target output input
- candidate prompt generation
- generated output preview
- similarity scoring
- token/length scoring
- leakage/copying scoring
- candidate ranking
- dashboard summary
- visible path view: slider, list, or Pareto-first view
- explicit mode labels for `fixture`, `mock`, and `black_box`

### Nice to have if time remains

- second fixture with a different target style
- JSON import/export for `AlephRun`
- simple candidate comparison view
- optional stability estimate via repeated generation

### Explicitly out of scope for v0

- full fine-tuning
- full GCG
- full ARCA
- cross-model transfer
- complex database or accounts
- strict white-box gradient explanations
- strong mechanistic or globally optimal claims

## API slice for v0

Build these first:

1. `POST /api/candidates`
2. `POST /api/generate`
3. `POST /api/score`

Recommended contract shape:

- `POST /api/candidates`
  - input: target text, optional adapter mode, optional candidate count
  - output: candidate prompts with enough metadata to render cards immediately
- `POST /api/generate`
  - input: prompt, adapter mode, model settings
  - output: generated text plus visible observation mode
- `POST /api/score`
  - input: target text, prompt, output
  - output: `token_count`, `compression_ratio`, `similarity`, `leakage_score`, and a single UI ordering score

Do not make the first API return a full real `AlephRun`. Build the smaller pieces first, then compose them into a run.

## Scoring policy

Use simple, inspectable scoring in v0:

- `Closeness`: text similarity over target vs output
- `Compression`: candidate prompt length relative to explicit reconstruction
- `Reliability`: optional repeated-run consistency; if unavailable, expose as unavailable or mock
- `Copying`: prompt-vs-target leakage score

The scoring layer should be honest and legible before it is sophisticated.

## Fallback ladder

Use the first fallback that keeps the product truthful:

1. `mlx_lm.server` with local Qwen3 8B 4-bit
2. mock FastAPI adapter with deterministic outputs
3. fixture-only front-end path using `packages/fixtures`

If the model route fails, the demo must degrade in capability, not in clarity.

## Six-hour execution order

### Hour 1

- lock the API contract
- upgrade fixture/mode labels if needed
- keep frontend reading mock data

### Hour 2

- implement `POST /api/candidates`
- implement `POST /api/score`
- keep generation mocked if model integration is not ready

### Hour 3

- implement `POST /api/generate`
- wire local adapter mode to an OpenAI-compatible endpoint
- keep `mock` as the default safe path

### Hour 4

- connect frontend workbench to the API
- ship `Target`, `Dashboard`, `Candidate Cards`, and `Output Preview`

### Hour 5

- refine scoring
- rank candidates
- make the path view feel coherent

### Hour 6

- polish wording and honesty labels
- rehearse the narrative
- verify the fallback path still works

## Narrative to protect

The demo explanation should stay simple:

1. Paste an output.
2. Aleph searches for prompts that could recreate it.
3. Move across the path from shorter prompts to more explicit ones.
4. Watch how fit, compression, reliability, and copying change.

## Definition of done

- `npm run lint` succeeds
- the React console can render a believable compression path
- the FastAPI app exposes the first three v0 endpoints
- at least one adapter mode works end-to-end
- local model failure does not kill the demo
- the repository does not claim more than the implementation proves
