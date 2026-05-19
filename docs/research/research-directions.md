# Research Directions

This file turns Aleph's prior-art scan into a forward-looking research map. It is not a promise to implement every route. It is a way to decide what belongs in the product, what belongs in adapters, and what belongs only in research notes.

## Why this file exists

Aleph has moved past the first question of "is this only a metaphor?" The answer is now strong enough to proceed:

- reverse prompt search is a real technical direction;
- the product thesis is stable enough to build around;
- the next challenge is not more surface area, but a clearer mainline.

That mainline should answer:

1. What is Aleph's core product object?
2. Which research families are closest to that object?
3. Which routes should change the near-term roadmap?
4. Which routes should stay as future adapters or contrast material?

## Aleph's own mainline

Aleph should keep treating **compression path** as the primary object.

```text
target output
  -> run conditions
  -> candidate prompts
  -> generated/scored outputs
  -> frontier over shortness, fit, stability, leakage, and optional loss
  -> observations that explain the current point
```

This means the project should not collapse into any single one of these:

- a benchmark only;
- a prompt optimizer only;
- a local-model demo only;
- an interpretability dashboard only;
- a hosted API wrapper only.

The product identity is narrower and stronger:

> Aleph is an output-to-prompt compression workbench.

## Six research families

### 1. Fixed-output reverse prompting

Closest examples: ARCA / `auditing-llms`, especially the "Reversing LLMs" path.

What this contributes:

- validates the "target output -> prompt search" direction;
- supports length-scanned search over prompt coordinates;
- makes white-box target likelihood a credible future score, not a speculative idea.

What Aleph should take:

- reverse search is real;
- prompt length should be a first-class search variable;
- future adapters may optimize toward fixed outputs directly.

What Aleph should not inherit:

- optimization method as product identity;
- paper framing as the only valid route.

### 2. Hard-prompt discrete optimization

Closest examples: GCG, related hard-prompt search, and targeted output induction work such as poem-targeting experiments.

What this contributes:

- a route for directly searching token prompts;
- evidence that short, strange, non-natural prompts can still act as usable coordinates.

What Aleph should take:

- hard-prompt search is a serious future adapter;
- human-readable prompts and raw coordinates should be treated as separate modes if both are ever exposed.

What Aleph should not inherit:

- jailbreak/attack identity as default product framing;
- an assumption that the shortest coordinate must remain readable.

### 3. Black-box prompt optimization

Closest examples: APE, PromptAgent, PromptWizard, TextGrad-style loops, evolutionary prompt search, and other generate-score-mutate systems.

What this contributes:

- practical search loops when logits are unavailable;
- a product-friendly path for hosted models;
- a way to improve candidate quality before deeper white-box work lands.
- a gradient-like metaphor for improving prompts even when the underlying system is not differentiable end-to-end.

What Aleph should take:

- generate -> evaluate -> mutate -> repeat is a valid v1 search loop;
- black-box routes can support real user-visible runs before full white-box instrumentation is stable.

What Aleph should not inherit:

- "better task prompt" framing as the whole project;
- hidden eval weights that turn the system into a generic prompt engineer.

### 4. Pareto and reflective optimization

Closest examples: GEPA and other multi-objective or reflection-driven optimizers.

What this contributes:

- a natural way to treat shortness, fit, stability, and leakage as a frontier instead of a single score;
- a reminder that Aleph should expose tradeoffs rather than flattening them.

What Aleph should take:

- Pareto ranking belongs in the workbench;
- multi-objective search is closer to the product than single-score optimization;
- reflection-driven candidate mutation is a credible medium-term route.

What Aleph should not inherit:

- optimizer branding as the product story;
- a requirement to adopt a full framework before the run contract is stable.

### 5. Soft / continuous prompt methods

Closest examples: prompt tuning, prefix tuning, and other frozen-model continuous prompt methods.

What this contributes:

- the strongest technical support for "prompt is a parameter";
- a future bridge between continuous optimization and discrete prompt coordinates.

What Aleph should take:

- the analogy to backprop is real in the continuous setting;
- soft-prompt methods can become a research route for projection into human or token prompts later.

What Aleph should not inherit:

- a requirement that v0/v1 be gradient-first;
- the assumption that a continuous optimum cleanly projects into a meaningful discrete prompt.

### 6. Prompt inversion and representation inversion

Closest examples: Reverse Prompt Engineering, embedding inversion, language model inversion, and `vec2text`.

What this contributes:

- a clear neighboring field for comparison;
- useful evaluation ideas for similarity, reconstruction, and black-box recovery.

What Aleph should take:

- inversion is adjacent prior art worth citing;
- some metrics and attack/recovery protocols may be reusable.

What Aleph should not inherit:

- the claim that Aleph is recovering the original hidden prompt;
- vector-to-text inversion as the central product route.

## What is now missing from the repository

The repository already has a stable thesis, a visible run contract, and a credible first UI. What is still under-specified is the post-Hackathon research phase.

The main missing pieces are:

- a shared statement of which research families matter now versus later;
- a clearer distinction between product mainline and adapter candidates;
- issue-ready research questions that go beyond "keep polishing the launch surface";
- a roadmap for turning black-box, white-box, and hybrid evidence into stable product observations.

## Near-term research program

The next round should not try to solve everything. It should narrow into four tracks.

### Track A. Workbench quality

Goal: make the product object legible and trustworthy.

Focus:

- dashboard language for ordinary users versus research mode;
- explicit leakage handling;
- stable candidate/frontier semantics;
- clearer left/right endpoint explanations.

### Track B. Scoring contract

Goal: decide what makes a candidate "better" in Aleph.

Focus:

- composite metric design;
- leakage score definition;
- stability/reproducibility measurement;
- when target NLL becomes a required field versus optional evidence.

### Track C. First real search loops

Goal: move from fixtures to repeatable real runs without overclaiming.

Focus:

- hosted black-box candidate generation and evaluation;
- local MLX/Qwen scoring and shallow search;
- file-first import/export of `AlephRun` artifacts;
- adapter honesty in the UI.

### Track D. Deeper research adapters

Goal: keep harder methods in reach without forcing them into v1.

Focus:

- ARCA-style fixed-length prompt search;
- GCG-style hard-prompt search;
- reflective/Pareto optimization;
- soft-prompt-to-hard-prompt projection;
- non-leaking mode and deletion ablation.

## Recommended output types

Different insights belong in different files.

Use:

- `README.md` for the short public phase and promise;
- `THESIS.md` for the durable product/research north star;
- `docs/research/*.md` for source-backed framing and route selection;
- `docs/open-questions.md` for real unresolved choices;
- `docs/next-backlog.md` for issue-ready work;
- `docs/decisions/` only when a route becomes settled enough to constrain implementation.

## Current maintainer recommendation

1. Keep Aleph's core identity as a compression workbench, not a generic optimizer.
2. Treat reverse fixed-output search as the closest research family.
3. Treat Pareto / leakage / stability as first-class product concerns, not polish.
4. Let hosted black-box and local white-box routes coexist as evidence modes.
5. Park ARCA/GCG/soft-prompt work as explicit future adapters until the run contract and scoring story are more stable.
