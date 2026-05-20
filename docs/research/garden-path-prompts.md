# Garden-Path-Like Prompts

Date: 2026-05-20

This note records a research-adjacent observation for Aleph's left-side prompt
coordinates. It is not an implementation claim and should not be treated as a
verified metric.

## Linguistic baseline

A garden path sentence is a sentence with local or temporary ambiguity. During
incremental reading, the reader or parser initially forms a plausible but wrong
analysis, then later material forces reanalysis.

Li, Ji, and Li (2025) define garden path sentences as sentences with local or
temporary syntactic or semantic ambiguity, and study whether large language
models can analyze them across English and Chinese. Their paper emphasizes that
the garden path effect is tied to temporary ambiguity, disambiguation, and
reanalysis. It also reports that LLMs show garden-path effects similar to human
processing in syntactic analysis; English disambiguation is stronger than
Chinese; and LLM syntactic and semantic analysis accuracies can diverge.

Classic examples include:

- `The horse raced past the barn fell.`
- `While the man hunted the deer ran into the woods.`
- Direct-object / sentential-complement forms, where an early noun phrase looks
  like an object before later material forces a complement reading.

## Aleph observation

Custom API search sometimes finds very short or strange prompts that appear to
work less like ordinary instructions and more like local ambiguity triggers.
They can look too compressed, elliptical, or misleading to a human reader, yet
still steer the model toward a target output. This is relevant to the left side
of the slider because the strongest compression candidates may operate as
model-specific cues rather than as fully human-readable summaries.

Aleph should describe these as **garden-path-like prompt coordinates**, not as
strict garden path sentences.

The distinction matters:

- A strict garden path sentence is a sentence-level linguistic object with a
  temporary syntactic or semantic ambiguity and a later disambiguating region.
- A garden-path-like prompt coordinate may be fragmentary, symbolic, or
  under-specified. It may exploit a model's learned associations or parsing
  priors without containing the full linguistic structure of a garden path
  sentence.
- In black-box Custom API mode, Aleph can observe that a prompt worked for a
  target output, but it cannot prove the model-internal reanalysis path.

## Product implication

The left edge of the slider should remain honest:

- left of Shortest Found is an unknown compression zone, not a verified
  candidate region;
- some found short prompts may be human-weird but model-effective;
- Custom API may expose garden-path-like prompt behavior, but the UI should not
  claim formal garden path syntax without sentence-level evidence.

Useful UI language:

```text
Some Custom API searches surface garden-path-like prompts: short, strange cues
that steer the model toward y without being ordinary summaries. Treat them as
model-specific compression coordinates, not proven linguistic garden path
sentences.
```

## Sources

- Qi Li, Yue Ji, and Hongzheng Li. 2025. "Can Large Language Models Analyze
  Garden Path Sentences? -- An Empirical Study based on Cross-Lingual Data."
  Chinese Computational Linguistics 2025. https://aclanthology.org/2025.ccl-1.43.pdf
- Thomas G. Bever. 1970. "The cognitive basis for linguistic structures." Cited
  in Li et al. (2025) as the origin of the garden path sentence framing.
- Christianson et al. (2001), Futrell et al. (2019), Hu et al. (2020), Irwin et
  al. (2023), Li et al. (2024), Amouyal et al. (2025), and related work cited by
  Li et al. (2025) on human and model processing of garden path sentences.
