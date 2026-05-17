# Thesis

Aleph is an instrument for navigating model-relative description length.

Given a target output, a fixed model, a fixed decoding rule, a fixed metric, and a fixed search budget, Aleph searches for prompts that can reproduce or approximate the target. It does not promise the globally shortest prompt. It shows the best known prompt coordinates discovered under the run conditions, and it makes the path between explicit reconstruction and compressed prompt coordinates observable.

## The image

Borges' Aleph is a point that contains every other point. From one small sphere, the viewer sees seas, dawns, crowds, mirrors, deserts, bodies, letters, and the act of reading itself. The image matters here because a language model also contains a finite, latent library of possible continuations. A prompt is not only an instruction. It is a coordinate that opens one region of that library.

Aleph turns that image into a product surface: paste an output, ask the model-space for coordinates that summon it, then inspect how much information is carried by the prompt, how much is supplied by the model, and where compression begins to fail.

## Confidence posture

Aleph's strongest claim is now stable: reverse prompt search is a real product direction when framed as **shortest known prompt under fixed run conditions**, not as a proof of the globally shortest prompt.

The research pass supports building around this shape:

- ARCA and Reversing LLMs show that output-to-prompt search can be treated as discrete optimization;
- GCG-style hard-prompt search is a future adapter route, not Aleph's identity;
- embedding inversion is adjacent prior art, not the same problem;
- local MLX/Qwen experiments provide adapter evidence for AlephRun-compatible search output;
- fixture and simulated panels are product-shape evidence, not model evidence.

This means the product should become clearer before it becomes broader: one target output, one run contract, one compression path, visible evidence modes, and explicit boundaries around what remains unproven.

## The core claim

The core object is not a better prompt. The core object is a compression path.

```text
target output y
  -> fixed run conditions: model, decoding, metric, budget, leakage mode
  -> candidate prompts p_1...p_n
  -> generated or scored outputs
  -> Pareto frontier over length, fit, stability, leakage, and optional loss
  -> observations that explain the current point
```

A useful Aleph run answers:

- What is the shortest known prompt discovered for this target under these conditions?
- What is the explicit reconstruction baseline?
- Which candidates sit on the Pareto frontier?
- What breaks as the prompt gets shorter?
- Is the prompt really compressing, or is it copying the target?
- Which target tokens are easy or hard for the current prompt to recover?
- Which prompt tokens appear to carry the most signal?

## The mathematical posture

Aleph estimates a model-relative, budget-bounded description length. A concise operating form is:

```text
L*_{theta,d,m,B}(epsilon) = min |p|
  over prompts searched within budget B
  such that m(M_{theta,d}(p), y) >= 1 - epsilon
```

This is deliberately not strict Kolmogorov complexity. Strict Kolmogorov complexity is defined relative to an abstract universal machine. Aleph uses a concrete model, a concrete tokenizer, a decoding rule, a metric, and a finite search procedure. That specificity is a feature, not a weakness: it makes the object buildable, inspectable, and comparable.

## Endpoints

The right endpoint is **Explicit Reconstruction**: a prompt that contains the target output and asks the model to reproduce it. It is a baseline, not a philosophical endpoint and not merely the model context window.

The left endpoint is **Shortest Found**: the strongest short candidate found in the current run. It is not the absolute shortest possible prompt.

The space between them is not smooth. Prompts are discrete token sequences. The path is a set of candidate points, and the slider should snap to those points while preserving the feeling of moving through a compression curve.

## Product identity

Aleph is not a generic prompt-writing assistant. It is a reverse prompt compression workbench.

It should feel like a scientific instrument, not a prompt marketplace:

- primary surface: target input, compression slider, current prompt, model output;
- secondary instruments: Pareto frontier, token loss, waveform, attribution, exposure vectors, loss curve, eval suite;
- honesty layer: fixture/mock/simulated/black-box/white-box modes are visibly labeled;
- research layer: prior art is recorded, but no research route is treated as product identity until implemented.

## User promise

A user should be able to paste a target output and see a navigable compression path. They should understand, within one minute, that Aleph is showing how a model output can be unfolded from prompts of different lengths and reliabilities.

The best user experience is not maximal configuration. It is a legible path:

1. paste target output;
2. choose or accept run settings;
3. generate candidates;
4. drag the compression slider;
5. inspect current prompt and output;
6. use secondary panels only when curious or debugging.

## Developer promise

A developer should be able to read the repository and know where to work without absorbing the full chat history.

The durable implementation contract is `AlephRun`:

```text
TargetOutput + SearchConfig + CandidatePoint[] + ObservationSet
```

Every UI panel, fixture, API route, and future adapter should speak this shape. New fields can be added, but parallel hidden data models should not appear.

## Research posture

Aleph is adjacent to ARCA, GCG, prompt inversion, embedding inversion, and interpretability workbenches. Those are implementation routes and conceptual neighbors, not a substitute for Aleph's product definition.

Research should change the repository only when it changes one of these:

- the run contract;
- the search strategy;
- the scoring or leakage method;
- the UI observations;
- the roadmap;
- a declared limitation.

## Fallback doctrine

Aleph should degrade gracefully. The product thesis should still be understandable if a model adapter, package install, or scoring routine fails. The fallback order is static prototype, fixture run, mock scoring, then real adapter. Each fallback is acceptable only when its mode is visible to the user and documented in the repository.

This protects the Hackathon line without weakening the long-term line: real search can replace fixture data later because both must speak `AlephRun`.

## First build

The first build should be frontend-led and fixture-backed. That is not a compromise; it is the fastest way to make the interaction clear before binding the product to one model runtime.

The first reliable artifact should include:

- target input;
- generated candidate path from fixture or mock search;
- compression slider over candidate points;
- current prompt and model output;
- metrics for length, fit, stability, compression, leakage, and frontier rank;
- Pareto frontier;
- token loss;
- search dial;
- waveform;
- attribution;
- exposure vectors;
- eval suite.

## What must remain unsettled

The repository should preserve freedom where the product is not yet proven:

- first real model adapter;
- default similarity metric;
- scoring weights;
- exact non-leaking constraints;
- whether ARCA/GCG are first-class adapters or imported experiments;
- storage/persistence strategy;
- the final visual style of the public product page.

These should remain explicit open questions, not hidden indecision.

## North star

Aleph should let a person hold one output and rotate it through model space until it reveals its coordinates.
