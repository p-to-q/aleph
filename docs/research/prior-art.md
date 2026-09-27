# Prior Art and Relationship

Aleph has real technical neighbors, but it should not be collapsed into any one of them. This file records relationships and boundaries.

## Computer-science center of gravity

Aleph is being developed as a computer-science system, not as a collection of mathematical anecdotes.
Its closest methodological domains are:

| CS domain | Aleph question | Evidence Aleph eventually owes |
| --- | --- | --- |
| program synthesis | Can a target behavior act as a partial specification for a compact prompt program? | typed search space, proposal operators, exhaustive finite cases, counterexamples, and regret against an oracle where possible |
| formal methods and theorem proving | Which claims or finite invariants can be represented as machine-checkable statements? | pinned statement, proof term or certificate, trusted-base declaration, replay, and an independent statement-fidelity review |
| test-time compute and search | Which allocation of proposals, revisions, branches, and verifier calls improves discovery at fixed budget? | complete budget ledger, matched-compute baselines, failure-inclusive scaling curves, and stop rules |
| prompt optimization | Which white-box, black-box, evolutionary, and textual-feedback operators search the coordinate space? | common evaluator/archive boundary, ablations, and no hidden target access |
| benchmark science and reproducible systems | Which claims survive frozen data, model/runtime drift, and independent replay? | immutable releases, sample evidence, uncertainty, environment/model identity, and artifact readback |
| HCI and checkability | Can a human detect errors and understand why a compact coordinate relates to its target? | independent rater protocol, decoys, abstention, reliability, and a performance/checkability tradeoff |

Mathematical problems are valuable because they expose search, specification, verification, and
interface failures sharply. They do not turn a company demonstration into Aleph's contribution. The
system-level synthesis is in
[`math-computation-ai-systems.md`](math-computation-ai-systems.md), and the staged research roles and
gates are in
[`model-relative-coordinate-landmarks.md`](../plans/model-relative-coordinate-landmarks.md).

## Closest direct neighbors: ACR/MiniPrompt and Prompting Complexity

[Adversarial Compression Ratio and MiniPrompt](https://arxiv.org/abs/2404.15146) already formulate
the target-first shortest-input problem, treat the model as a decompressor, and use GCG plus
prompt-length search on arbitrary target strings. [Prompting Complexity](https://arxiv.org/abs/2607.06145)
is the closest formal neighbor: it studies shortest plausible prompts relative to a fixed language
model and gives exact, soft, and behavioral variants plus coding-style bounds.

Why this matters for Aleph:

- Aleph cannot claim novelty for target-first search, the model-as-decompressor interpretation,
  shortest-input compression, or the bare model-relative minimum.
- MiniPrompt is the mandatory closest white-box empirical baseline, with its paper configuration and
  an audited adapter reported separately.
- Aleph must earn its contribution through the readable-versus-raw measurement contract, full
  observed paths, independent confirmation, reproducible budget accounting, provenance channels, and
  controlled source interventions.

Boundary:

- MiniPrompt's heuristic best found is not an oracle minimum, its teacher-forced success is not
  sampled reliability, and its free-token count omits fixed scaffolding. Aleph must reproduce rather
  than silently repair the published baseline, then label its audited extension separately.
- Prompting Complexity supplies a direct formal neighbor, not Aleph's human-readability protocol,
  search system, empirical laws, or source interpretation.

## Lower-level fixed-output optimization: ARCA

ARCA formulates auditing as discrete fixed-output optimization. The public `auditing-llms` repository
includes a **Reversing LLMs** path with a configurable prompt length.

Why this matters for Aleph:

- It supplies a compatible gradient-ranked coordinate-substitution comparator.
- It helps audit fixed-length white-box search behavior and target-likelihood screening.

Boundary:

- ARCA is a lower-level raw-coordinate comparator, not the closest predecessor and not a substitute
  for the mandatory MiniPrompt baseline.
- Its access, CUDA, seed, trace, and teacher-forced-versus-generation assumptions must be explicit.

## Black-box prompt optimization families

Automatic Prompt Engineer, PromptAgent, PromptWizard, and related search systems optimize prompts through generate-score-mutate loops rather than direct white-box likelihood search.

Why this matters for Aleph:

- It gives a practical route for hosted black-box runs.
- It supports an iterative candidate loop before full white-box scoring is stable.
- It reinforces that prompt search can be productively staged without claiming global optimality.

Boundary:

- These systems usually optimize task performance, not model-relative description length.
- Aleph should borrow the loop shape, not inherit a generic prompt-engineering identity.

## Textual-gradient optimization

TextGrad treats optimization over prompts or other text variables as an automatic-differentiation-style loop, where LLMs provide textual feedback that acts like gradients over a computation graph.

Why this matters for Aleph:

- It gives a useful computational metaphor for prompt-space optimization without requiring literal numeric gradients everywhere.
- It reinforces the idea that Aleph may eventually optimize not only prompts but other text-bearing parts of a run.
- It strengthens the bridge between workbench UI language and deeper optimizer design.

Boundary:

- TextGrad is a general framework for textual optimization over compound AI systems.
- Aleph still has a narrower object: shortest-known prompt coordinates for target outputs under fixed run conditions.

## Reflective and Pareto optimizers

GEPA and related reflective optimizers treat prompt optimization as a multi-objective search problem and use feedback to evolve candidates.

Why this matters for Aleph:

- Aleph's workbench is naturally Pareto-shaped.
- Shortness, recoverability, stability, human evidence, and versioned copy-channel violations should
  remain visible tradeoffs; the complete provenance profile must not be collapsed into one number.
- Reflective mutation is a plausible route for future search adapters.

Boundary:

- Aleph should not depend on a full optimization framework to justify its product shape.
- This is a route for future search quality, not a requirement for v0/v1.

## Mathematical discovery and verification systems

The relevant family is not a single model. It is a set of system decompositions that combine learned
proposal, structured search, executable or formal feedback, large compute budgets, and human
interpretation.

- **Program-search systems.** [FunSearch](https://www.nature.com/articles/s41586-023-06924-6)
  and [AlphaEvolve](https://storage.googleapis.com/deepmind-media/DeepMind.com/Blog/alphaevolve-a-gemini-powered-coding-agent-for-designing-advanced-algorithms/AlphaEvolve.pdf)
  search in code space under executable evaluators. Their power depends on a well-specified candidate
  language and an evaluator that is cheap and faithful enough to drive search.
- **Neural-symbolic and formal proof systems.** [AlphaGeometry](https://www.nature.com/articles/s41586-023-06747-5),
  [AlphaProof](https://www.nature.com/articles/s41586-025-09833-y),
  [LeanDojo/ReProver](https://arxiv.org/abs/2306.15626), and OpenAI's
  [statement-curriculum prover](https://cdn.openai.com/papers/Formal_Mathematics_Statement_Curriculum_Learning__ICML_2022.pdf)
  use a learned proposer or guide around a symbolic or kernel-checked environment. They separate
  generative breadth from a narrower correctness oracle.
- **Research-assistant and autoformalization cases.** OpenAI's
  [First Proof submissions](https://openai.com/index/first-proof-submissions/) and Anthropic's
  [Fermat formalization artifact](https://github.com/anthropics/fermats-last-theorem) expose two
  different review surfaces: manually selected natural-language attempts with ongoing community
  feedback and unresolved states, and a large formal artifact for a known proof route that can be
  replayed against a pinned Lean theorem. First Proof receives no categorical review grade;
  the FLT artifact checks its encoded result but does not make the closed generation run reproducible.

The cases must be read through three separate predicates:

1. **description:** did the system produce a candidate explanation, program, construction, or proof?
2. **discovery:** is the result new relative to a documented literature and baseline search, rather
   than a rediscovery or reformulation?
3. **verification:** which exact executable predicate or formal statement was checked, by which
   checker, under which assumptions and trusted base?

These predicates do not imply one another. A Lean kernel can validate a proof of an encoded theorem
without establishing that the theorem is a faithful formalization of the intended natural-language
claim. An evaluator can certify a construction's score while missing a property absent from its
specification. Expert approval can support a mathematical argument without supplying an independent,
machine-checkable certificate.

Why this matters for Aleph:

- A finite coordinate world can be treated as a synthesis problem and exhaustively enumerated before
  open prompt search is trusted.
- Search should emit candidate programs/prompts plus evaluator receipts, not polished prose alone.
- Formalization is useful for selected invariants and certificates, but the paper cannot outsource
  construct validity or novelty to Lean.
- Long runs should be justified by a verifier or evaluator ladder and report the six
  `ResourceLedger/0.1.0` accounts. Proposer calls, discovery-time evaluation, and retries remain
  typed search-work children; human refinement remains provenance and wall-clock metadata rather
  than an invented additive cost account.

Boundary:

- Aleph does not claim mathematical discovery merely because a model generated a proof-like text.
- Aleph does not claim formal verification until a pinned artifact replays, and even then states the
  statement-fidelity and trusted-base boundary.
- These systems motivate architecture and experiments; their headline results are not the empirical
  evidence for Aleph's own claims.

## GCG and hard-prompt optimization

Greedy Coordinate Gradient searches over discrete token sequences using gradient-informed candidate selection. It is relevant as a lower-level raw-coordinate comparator, especially for open-weight models.

Why this matters for Aleph:

- It can become a comparator or proposal adapter for optimized raw-token candidate generation.
- It gives a concrete route for searching token prompts rather than only generating heuristic candidates.

Boundary:

- GCG is usually framed around adversarial suffixes and safety attacks.
- Aleph should not inherit the safety/attack identity unless a future mode explicitly does so.
- Integration depends on tokenizer/model support and compute budget, and it does not replace the
  mandatory variable-length MiniPrompt comparison.

## Probe Sampling and accelerated prompt optimization

Probe Sampling uses a smaller draft model to filter prompt candidates for GCG-like optimization when the draft model is similar enough to the target model.

Why this matters for Aleph:

- It suggests a future speed path for expensive search.
- It reinforces the need to record model, decoding, metric, and budget with every run.

Boundary:

- Not v0 scope.

## Soft and continuous prompt methods

Prompt tuning, prefix tuning, and related continuous-prompt methods optimize prompt-like parameters while keeping the model weights frozen.

Why this matters for Aleph:

- They give the strongest technical reading of "prompt is a parameter."
- They offer a future path for continuous search followed by projection into discrete prompts.

Boundary:

- Aleph's user-facing object is still a discrete prompt coordinate and visible compression path.
- Continuous prompt optimization should remain a future adapter until it can be related back to the product honestly.

## Reverse Prompt Engineering and Language Model Inversion

Reverse Prompt Engineering attempts to recover an original hidden prompt from outputs. Embedding inversion attempts to reconstruct text from dense embeddings.

Why this matters for Aleph:

- These fields share the broader inversion theme.
- They help explain what Aleph is not.

Boundary:

- Aleph does not promise to recover the original hidden prompt.
- Aleph searches for a usable prompt coordinate for a target output under fixed model conditions.

## Garden-path-like prompt coordinates

Garden path sentences are locally or temporarily ambiguous sentences that can
lead a reader or parser into an initial wrong analysis before later material
forces reanalysis. Li, Ji, and Li (2025) study whether LLMs can analyze these
sentences across English and Chinese, and report that LLMs show garden-path
effects in syntactic analysis while differing across languages and between
syntax and semantics.

Why this matters for Aleph:

- Custom API search sometimes surfaces very short, strange prompts that steer a
  model toward the target output without reading like ordinary instructions.
- These prompts may be useful model-relative coordinates because they exploit
  learned associations, parsing priors, or temporary ambiguity-like cues.
- They are especially relevant near the left side of the slider, where prompts
  may stop looking like human summaries.

Boundary:

- Aleph should call this **garden-path-like prompt behavior**, not formal garden
  path syntax, unless the prompt is itself a sentence with a clear ambiguity and
  disambiguating region.
- In black-box Custom API mode, Aleph can observe successful outputs but cannot
  prove a model-internal reanalysis path.

## Aquin-style instrumentation

Aquin's public site uses a strong instrumentation language: causal trace, circuit attribution, inherited signal, loss curves, exposure vectors, layer scans, and eval suites.

Why this matters for Aleph:

- It validates the direction of a readable, observable model workbench.
- It offers useful UI primitives for secondary panels.

Boundary:

- Aleph should translate these into compression-specific panels: token loss, prompt attribution, compression exposure, eval suite, waveform, and search dial.
- Aleph should not claim mechanistic interpretability without real model internals.

## Benchmark systems and public runtimes

[HELM](https://github.com/stanford-crfm/helm), `lm-evaluation-harness`, LiveBench, and other maintained
evaluation systems show why scenarios, adapters, rendered requests, model revisions, item-level
outputs, metrics, and aggregates must remain separable. Their engineering patterns inform Aleph's
release and replay contracts; no external leaderboard defines the readable-coordinate construct.

Kaggle is a hosted execution environment and quota-bearing scheduler for Aleph Bench. A Kaggle pass
becomes portability evidence only after output retrieval, checksum validation, and offline replay. It
is not a mathematical oracle, a scientific definition, or an official benchmark result by itself.
GitHub and Hugging Face are durable code/data/publication surfaces; all three must point to the same
versioned scientific artifacts rather than maintain independent truths.
