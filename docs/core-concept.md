# Core Concept

This file separates what is settled from what is still open. It exists to prevent chat history, design exploration, or fixture data from hardening into false product facts.

## Settled

1. **Name**: the project is called **Aleph**.
2. **Primary object**: a target output `y`, not an instruction-writing task.
3. **Core action**: reverse search for prompts that can reproduce or approximate `y` under fixed conditions.
4. **Core claim**: Aleph estimates the **shortest known prompt** under a fixed model, decoding strategy, metric, and search budget. It does not claim the global optimum.
5. **Core interface**: a compression path controlled primarily by a slider, with selectable Pareto points as the underlying data model.
6. **Left endpoint**: **Shortest Found** — the best short candidate discovered in the current run.
7. **Right endpoint**: **Explicit Reconstruction** — a prompt that directly contains the target output, used as a baseline.
8. **Middle structure**: a discrete Pareto frontier over prompt length, fit, stability, leakage, and optionally NLL.
9. **Required workbench surfaces**: target input, search setup, compression slider, Pareto frontier, current prompt, model output, dashboard metrics, token loss, search dial, waveform, attribution, exposure vectors, and eval suite.
10. **Required honesty rule**: fixture or simulated observations must be visibly labeled as fixture or simulated.
11. **Required leakage rule**: any claim of compression must be checked against copy/leakage behavior.
12. **Repository shape**: artifact-first product lab. The p-to-q seed is a reference, not a rigid template.

## Open for discussion

These are not settled and should not be represented as product facts until implemented or ratified in an ADR.

- Which model adapter is first: local open-weight model, hosted black-box model, or both.
- Which similarity metric becomes the default: embedding similarity, exactness, edit distance, LLM judge, or composite metric.
- Whether teacher-forced token loss is included in v1 or remains a white-box-only v2 feature.
- How strict non-leaking mode should be: longest common substring, n-gram overlap, copy ratio, entity-copy limits, or a composite leakage score.
- Whether ARCA/GCG-style search is integrated directly or treated as an external adapter.
- Whether saved runs need persistence in the Hackathon build.
- Whether the UI should privilege a research-console layout or a more user-facing launch/product page once the demo stabilizes.

## Deferred or explicitly out of scope for v0

- Proving the globally shortest prompt.
- Equating Aleph's model-relative description length with strict Kolmogorov complexity.
- Full mechanistic interpretability claims without model internals.
- User accounts, team workspaces, billing, or production persistence.
- A general-purpose prompt-polishing assistant.
- Treating context window length as the semantic right endpoint of the slider.

## Product sentence

Aleph turns a target output into a navigable compression path: from explicit reconstruction to the shortest known prompt coordinate discovered under fixed model conditions.
