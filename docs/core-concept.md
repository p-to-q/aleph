# Core Concept

This file separates what is settled from what is still open. It exists to prevent chat history, design exploration, or fixture data from hardening into false product facts.

## Settled

1. **Name**: the project is called **Aleph**.
2. **Primary object**: a target output `y`, not an instruction-writing task.
3. **Core action**: reverse search for prompts that can reproduce or approximate `y` under fixed conditions.
4. **Core claim**: Aleph defines a search-independent oracle `L*` under declared model, decoding,
   metric, domain, and reliability conditions, while a run reports **Shortest Found** `L_hat` under
   its algorithm, budget, seed, tokenizer, archive, and confirmation protocol.
5. **Core interface**: a compression path controlled primarily by a slider, with selectable Pareto points as the underlying data model.
6. **Left endpoint**: **Shortest Found** — the best short candidate discovered in the current run.
7. **Right endpoint**: **Explicit Reconstruction** — a prompt that directly contains the target output, used as a baseline.
8. **Middle structure**: a discrete Pareto frontier over prompt length, fit, stability, typed
   provenance/recoverability evidence, and optionally NLL; no undocumented scalar composite is the
   scientific default.
9. **Required workbench surfaces**: target input, search setup, compression slider, Pareto frontier, current prompt, model output, dashboard metrics, token loss, search dial, waveform, attribution, exposure vectors, and eval suite.
10. **Required honesty rule**: fixture or simulated observations must be visibly labeled as fixture or simulated.
11. **Required evidence rule**: any compression claim must report the applicable versioned
    surface-copy, recoverability, trace-integrity, and causal-source evidence without treating them as
    interchangeable.
12. **Repository shape**: artifact-first product lab. The p-to-q seed is a reference, not a rigid template.

## Governing PR0 supersession

The [readable-coordinate PR0 contract](plans/iclr-readable-coordinate-program.md) supersedes older
repository prose that presented a single composite score, one scalar `leakage` value, or ARCA as the
closest neighbor. The settled research contract is:

- preserve versioned metric and evidence vectors; any scalar scheduler or UI projection must be
  named, derivable, and never replace the scientific record;
- treat the legacy n-gram `leakage` field only as a surface-copy proxy during migration, while
  keeping prompt recoverability, extraction, trace integrity, training influence, and causal-source
  effects as separately scoped channels;
- maintain readable and raw-coordinate views as separate certified views over one append-only
  archive; and
- reproduce ACR/MiniPrompt as the mandatory closest empirical baseline and treat Prompting
  Complexity as the closest formal neighbor. ARCA and GCG are lower-level raw-coordinate
  comparators, not substitutes for that baseline.

## Open for discussion

These are not settled and should not be represented as product facts until implemented or ratified in an ADR.

- Which existing or new adapter first satisfies the PR0 research-grade archive, accounting,
  confirmation, and independent-replay contract.
- Which versioned fit metrics and calibrated thresholds should be primary for each target family;
  no choice authorizes an undocumented composite.
- Whether teacher-forced token loss is included in v1 or remains a white-box-only v2 feature.
- Which finite surface-copy and recoverability probes, thresholds, and calibration sets define each
  channel-qualified tested-noncopy mode; no finite suite establishes universal non-leakage.
- How the mandatory MiniPrompt reproduction and lower-level ARCA/GCG comparator adapters should be
  scheduled behind the shared archive/evaluator contract.
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

Aleph turns a target output into a navigable observed compression path: from explicit reconstruction
to the shortest confirmed prompt coordinate found under declared run conditions.
