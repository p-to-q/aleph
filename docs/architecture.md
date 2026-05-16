# Architecture

Aleph is a frontend-led research product repository. The first working artifact is the console; the durable contract is the run data shape.

## Layer model

```text
User Surface       apps/web
Developer Surface  packages/core, packages/ui, packages/fixtures, apps/api
Research Surface   docs/research, docs/decisions, docs/plans
Archive Surface    docs/archive
```

## Data flow

```text
TargetOutput
  -> SearchConfig
  -> CandidatePoint[]
  -> selected CandidatePoint
  -> ObservationSet
  -> UI panels
```

All UI panels should consume an `AlephRun` from `packages/core/src/types.ts`. Do not let the React app invent a parallel shape.

```text
AlephRun
├─ id, createdAt
├─ TargetOutput
├─ SearchConfig
│  ├─ model
│  ├─ decoding
│  ├─ metric
│  ├─ budget
│  └─ mode: unrestricted | non_leaking
├─ CandidatePoint[]
└─ ObservationSet
```

## Package boundaries

| Area | Owns | Must not own |
|---|---|---|
| `packages/core` | types, pure metric helpers, frontier helpers, leakage helpers | React state, HTTP, model runtime |
| `packages/fixtures` | stable sample runs | product claims, real model evidence |
| `packages/ui` | reusable panel shells | search strategy, scoring truth |
| `apps/web` | composition, interaction, visual state | hidden business logic or new data contracts |
| `apps/api` | future HTTP service and model adapters | UI rendering |
| `docs/research` | source-backed framing and feasibility | unsupported claims of implementation |

## Component model

```text
TargetInput -> GeneratePath -> CandidatePoint[]
CandidatePoint -> CompressionSlider / ParetoFrontier / PromptOutput
ObservationSet -> TokenLoss / Waveform / Attribution / Exposure / EvalSuite
```

## Adapter model

Future model integrations should use adapters behind the run contract:

- `mock` adapter: deterministic fixture-like runs for UI work;
- `hosted_black_box` adapter: repeated sampling, similarity, leakage, stability;
- `local_white_box` adapter: logits, token NLL, teacher-forced likelihood;
- `arca` adapter: length-scanned discrete optimization;
- `gcg` adapter: hard-prompt optimization when tokenizer/model support is known.

## Stage gates

1. **Fixture gate**: UI works from `packages/fixtures/src/sample-run.json`.
2. **Mock service gate**: `apps/api` can return the same shape over HTTP.
3. **Black-box gate**: candidates and stability come from repeated model calls.
4. **White-box gate**: token loss and probability panels use real logits.
5. **Search adapter gate**: ARCA/GCG/evolutionary routes generate candidates.

Each gate must preserve the same `AlephRun` shape or explicitly migrate it.

## Why frontend-led first

The first goal is to make the product legible: target input, compression path, prompt/output, and observations. A real backend can be swapped from fixture to mock to model-backed without changing the UI contract.

## Why not algorithm-first

ARCA, GCG, and embedding inversion are valuable references, but Aleph's durable product identity is the compression workbench and run contract. Search methods should be adapters, not the whole architecture.
