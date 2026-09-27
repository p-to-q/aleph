# Thesis

Aleph is an instrument for navigating model-relative description length.

Given a target output and declared model, decoding, metric, domain, and reliability conditions, Aleph
defines an oracle coordinate length `L*`. An executable search additionally declares its algorithm,
budget, seed, tokenizer, archive, and confirmation protocol, then reports the shortest found
coordinate `L_hat`. It does not promote `L_hat` to a global optimum.

## The image

Borges' Aleph is a point that contains every other point. From one small sphere, the viewer sees
seas, dawns, crowds, mirrors, deserts, bodies, letters, and the act of reading itself. The image
matters here because a fixed language model and decoding rule induce a distribution over possible
continuations. A prompt is not only an instruction; it is a coordinate that changes that
distribution.

Aleph turns that image into a product surface: paste an output, ask the model-space for coordinates
that summon it, then inspect which declared surface-copy, recoverability, public-reference, and
model-mediated channels are supported, what the run can reproduce, and what remains unidentified.

## Confidence posture

Aleph's strongest claim is now stable: reverse prompt search is a real product direction when a run
reports **Shortest Found under declared conditions** and keeps it distinct from the oracle `L*`.

The research pass supports building around this shape:

- ACR/MiniPrompt is the closest empirical predecessor and mandatory target-first compression
  baseline;
- Prompting Complexity is the closest formal neighbor for fixed-model shortest plausible prompts;
- ARCA and GCG are lower-level raw-coordinate optimizers and possible comparators, not Aleph's
  closest predecessor or product identity;
- embedding inversion is adjacent prior art, not the same problem;
- local MLX/Qwen experiments provide adapter evidence, but their historical frontier is not
  performance evidence until regenerated from an append-only observation archive;
- fixture and simulated panels are product-shape evidence, not model evidence.

This means the product should become clearer before it becomes broader: one target output, one run contract, one compression path, visible evidence modes, and explicit boundaries around what remains unproven.

## The core claim

The core object is not a better prompt. The core object is a compression path.

```text
target output y
  -> frozen coordinate system, model interface, decoding, and metric vector
  -> searcher, budget, random state, and complete event trace
  -> append-only candidate and observation archive
  -> confirmed multidimensional Pareto views
  -> typed surface-copy, recoverability, trace-integrity, and source evidence
```

A useful Aleph run answers:

- What is the shortest confirmed prompt found for this target under these conditions?
- What is the explicit reconstruction baseline?
- Which candidates sit on the Pareto frontier?
- What breaks as the prompt gets shorter?
- Which declared channels treat the prompt as surface copy, recoverable encoding, public reference,
  or model-mediated coordinate?
- Which target tokens are easy or hard for the current prompt to recover?
- Which prompt tokens appear to carry the most signal?

## The mathematical posture

Aleph defines a search-independent model-relative oracle object. In simplified notation:

```text
rho(p; y, epsilon) =
  Pr_{Z ~ M_{theta,d}(. | p)}[m(Z, y) >= 1 - epsilon]

L*_{theta,d,m}(y; epsilon, beta) = min |p|
  over all prompts in the declared coordinate domain
  such that rho(p; y, epsilon) >= 1 - beta
```

For deterministic decoding, `rho` is a zero-or-one special case.

An executable run reports a different, algorithm-conditioned found statistic:

```text
L_hat_{A,B,omega}(y; epsilon, beta) = min |p|
  over prompts actually observed by searcher A under budget B and random state omega
  whose protected confirmation supports rho(p; y, epsilon) >= 1 - beta
```

Budget belongs to the found statistic, not the oracle construct. Conditional on the declared
simultaneous-coverage event, a protected-confirmed result whose population reliability meets the
declared threshold constructively upper-bounds `L*`; the event's stated coverage controls the
confidence of that claim. Search-time point estimates remain provisional. Only exhaustive coverage
or a sound cheaper-prefix certificate
closes the optimality gap. This is deliberately not strict Kolmogorov complexity. Strict Kolmogorov
complexity is defined relative to an abstract universal machine. Aleph freezes a concrete model
interface, tokenizer, decoding rule, metric family, coordinate domain, and code-length convention.
That specificity makes the object executable and inspectable, but does not create universal-machine
invariance or a computable estimate of Kolmogorov complexity.

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
- the versioned metric vector or a typed copy/recoverability/provenance channel;
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
- metrics for length, fit, stability, compression, typed evidence channels, and frontier rank;
- Pareto frontier;
- token loss;
- search dial;
- waveform;
- attribution;
- exposure vectors;
- eval suite.

## What must remain unsettled

The repository should preserve freedom where the product is not yet proven:

- first PR0-conformant research-grade model adapter with a complete archive, resource ledger, and
  independent replay boundary;
- default versioned fidelity metrics and calibration thresholds for each target family;
- any named scheduler or UI projection over the preserved metric vector;
- the first finite, versioned tested-copy/recoverability suite and its channel-qualified thresholds;
- how the mandatory MiniPrompt baseline and lower-level ARCA/GCG comparators share one archive and
  evaluator boundary;
- storage/persistence strategy;
- the final visual style of the public product page.

These should remain explicit open questions, not hidden indecision.

## North star

Aleph should let a person hold one output and rotate it through model space until it reveals its coordinates.
