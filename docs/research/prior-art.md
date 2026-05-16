# Prior Art and Relationship

Aleph has real technical neighbors, but it should not be collapsed into any one of them. This file records relationships and boundaries.

## Closest: ARCA / `auditing-llms`

ARCA formulates model auditing as discrete optimization and searches for prompts/outputs that match target behavior. The public `auditing-llms` repository includes a **Reversing LLMs** path described as producing prompts that find a fixed output, with `--prompt_length` exposed as a variable.

Why this matters for Aleph:

- It validates the engineering version of reverse prompt search.
- It suggests length scanning over prompt length is a real route.
- It supports future white-box scoring based on target log-likelihood.

Boundary:

- ARCA is an optimization method. Aleph is a product workbench and data contract for viewing the compression path.
- ARCA is not required for Hackathon v0.

## GCG and hard-prompt optimization

Greedy Coordinate Gradient searches over discrete token sequences using gradient-informed candidate selection. It is relevant to future hard-prompt search, especially for open-weight models.

Why this matters for Aleph:

- It can become an adapter for optimized candidate generation.
- It gives a concrete route for searching token prompts rather than only generating heuristic candidates.

Boundary:

- GCG is usually framed around adversarial suffixes and safety attacks.
- Aleph should not inherit the safety/attack identity unless a future mode explicitly does so.
- Integration depends on tokenizer/model support and compute budget.

## Probe Sampling and accelerated prompt optimization

Probe Sampling uses a smaller draft model to filter prompt candidates for GCG-like optimization when the draft model is similar enough to the target model.

Why this matters for Aleph:

- It suggests a future speed path for expensive search.
- It reinforces the need to record model, decoding, metric, and budget with every run.

Boundary:

- Not v0 scope.

## Reverse Prompt Engineering and Language Model Inversion

Reverse Prompt Engineering attempts to recover an original hidden prompt from outputs. Embedding inversion attempts to reconstruct text from dense embeddings.

Why this matters for Aleph:

- These fields share the broader inversion theme.
- They help explain what Aleph is not.

Boundary:

- Aleph does not promise to recover the original hidden prompt.
- Aleph searches for a usable prompt coordinate for a target output under fixed model conditions.

## Aquin-style instrumentation

Aquin's public site uses a strong instrumentation language: causal trace, circuit attribution, inherited signal, loss curves, exposure vectors, layer scans, and eval suites.

Why this matters for Aleph:

- It validates the direction of a readable, observable model workbench.
- It offers useful UI primitives for secondary panels.

Boundary:

- Aleph should translate these into compression-specific panels: token loss, prompt attribution, compression exposure, eval suite, waveform, and search dial.
- Aleph should not claim mechanistic interpretability without real model internals.
