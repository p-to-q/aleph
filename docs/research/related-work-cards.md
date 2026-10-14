# Related Work Cards (CS mainline)

Status: research draft (stage 1, 2026-10-15). Each card: representative papers
(web-verified 2026-10-15), object and method, evidence regime, relation to
Aleph, read status. Read status is honest: `read` = full paper read with
notes; `skimmed` = abstract/intro plus public materials; `deferred` =
scheduled. No claim in this file is a product claim. This file is the
paper-facing citation card set; `prior-art.md` remains the product-facing
neighbor list.

## C1. Output-to-prompt inversion (reverse prompting)

- ARCA — *Automatically Auditing LLMs via Discrete Optimization*, Jones et
  al., ICML 2023, arXiv:2303.04381. **Object**: recover prompts that steer a
  model to a target output via coordinate-ascent over prompt tokens with
  white-box logits. **Relation**: validates that output→prompt search is a
  real optimization problem; Aleph's budget-bounded black-box workbench is
  complementary (ARCA needs logits). **Status**: read.
- *Extracting Prompts by Inverting LLM Outputs*, Morris et al., EMNLP 2024
  (aclanthology 2024.emnlp-main.819). Output-to-prompt inversion as a
  practical task. **Status**: skimmed.
- *GPT, But Backwards: Exactly Inverting Language Model Outputs*,
  arXiv:2507.01693 (2025). Exact-inversion angle. **Status**: skimmed.
- *Reverse Prompt Engineering: A Zero-Shot, Genetic Algorithm Approach to
  Language Model Inversion*, EMNLP 2025 (2025.emnlp-main.1333). Black-box
  genetic route. **Status**: deferred.
- *PTP: Previous-Token Prediction based LLM Inversion for Near-Exact Prompt
  Reconstruction*, arXiv:2607.29378 (2026). **Status**: deferred.

Take-away: the family exists and is growing; Aleph's difference is measuring
the *length/fit/leakage* trade-off surface (the compression path), not only
recovering one prompt.

## C2. Minimal prompting and prompting complexity

- **Prompting Complexity: Shortest Prompts for Texts and Behaviors in LLMs**,
  Cosma, arXiv:2607.06145 (2026). **Object**: for a fixed instruction-tuned
  LM, the shortest *plausible* prompt that elicits a text/behavior under
  deterministic decoding — the closest prior-art object to Aleph's `L*`.
  **Contents**: exact `Ψ_f(t)`, soft `Ψ_f^{ε,d}(t)`, behavioral `Ψ_f(B)`,
  prompting distance `d_Ψ`; failure of the invariance theorem (two LMs need
  not assign complexities within any additive constant); a counting bound
  that highly prompt-compressible texts are exponentially rare; the bound
  `K(x) ≤ Ψ_f(x)·log2 T + O(1)`; prompting probability `m_f` and a weak
  coding theorem `−log_T P_f(t) − |t| ≤ −log_T m_f(t) = Ψ_f(t) − log_T
  Z_f(t) ≤ Ψ_f(t)`; a research agenda (estimating `Ψ` black-box, instruction
  following, judge sensitivity, jailbreak incompressibility). **Relation**:
  direct collision; Aleph adds (a) reliability `beta` via `rho ≥ 1−beta`
  under stochastic decoding, (b) budget-bounded found values `L̂` as the
  honest product quantity, (c) the leakage dimension as a first-class
  constraint, (d) the Pareto staircase/path as the product surface,
  (e) replayable measurement infrastructure. **Status**: read (full text;
  folded into `description-length-formalism.md` §3).
- *Fundamental Limits of Prompt Compression: A Rate-Distortion Framework for
  Black-Box Language Models*, Girish et al., NeurIPS 2024,
  arXiv:2407.15504. Rate-distortion theory for soft prompts compressing
  context; not reverse search but the cleanest theory neighbor for
  length↔distortion trade-offs. **Status**: skimmed.
- **MiniPrompt / ACR** — the repository's canonical reference is
  *Rethinking LLM Memorization through the Lens of Adversarial Compression*,
  Schwarzschild et al., NeurIPS 2024, arXiv:2404.15146 (also card C9): a
  fixed-length suffix optimizes a target string's compression ratio with
  teacher-forced logits; the mandatory closest white-box baseline
  (`prior-art.md`, `docs/open-questions.md` #4). **Name disambiguation:** the ACL
  2024 paper *MinPrompt: Graph-based Minimal Prompt Data Augmentation for
  Few-shot QA* (Cui et al., arXiv:2310.05007) is a few-shot data-augmentation
  method and is **not** the intended reference; all repo citations mean
  Schwarzschild et al. **Status**: read (Schwarzschild); not cited (Cui).

## C3. Hard-prompt discrete optimization

- *Universal and Transferable Adversarial Attacks on Aligned Language Models*
  (GCG), Zou et al., 2023, arXiv:2307.15043; nanoGCG follow-ups.
  **Relation**: future hard-prompt adapter candidate; deliberately not
  Aleph's product identity. **Status**: read.
- ARCA (C1) doubles as the fixed-output optimization route.

## C4. Reflective / gradient-like prompt optimizers

- *TextGrad: Automatic "Differentiation" via Text*, Yuksekgonul et al.,
  NeurIPS 2024, arXiv:2406.07496. Textual backprop metaphor for compound
  systems. **Relation**: computational metaphor for proposal/feedback loops;
  not a length-measuring instrument. **Status**: read.
- *GEPA: Reflective Prompt Evolution Can Outperform Reinforcement Learning*,
  Agrawal et al., ICLR 2026, arXiv:2507.19457. Reflective prompt evolution
  benchmark suite. **Relation**: adapter candidate and a benchmark family to
  compare against in stage 2+. **Status**: skimmed.
- *Large Language Models as Optimizers* (OPRO), Yang et al., ICLR 2024,
  arXiv:2309.03409. Meta-prompt optimization lineage. **Status**: deferred.

## C5. Program synthesis and discovery search

- *Mathematical discoveries from program search with large language models*
  (FunSearch), Romera-Paredes et al., Nature 625:468–475 (2024). Short
  discovered programs, huge evolutionary search — the witness/discovery
  separation Aleph adopts as a measurement principle. **Status**: read.
- *AlphaEvolve: A coding agent for scientific and algorithmic discovery*,
  Novikov et al., Google DeepMind, arXiv:2506.13131 (2025). Coding-agent
  discovery loop with verification. **Status**: skimmed.

## C6. Formal methods and theorem proving

- *The Lean 4 Theorem Prover and Programming Language*, de Moura & Ullrich,
  CADE-28 (2021). Toolchain reference (pinned 4.34.1 in this repo).
  **Status**: tooling read.
- *Olympiad-level formal mathematical reasoning with reinforcement learning*
  (AlphaProof + AlphaGeometry2), Google DeepMind, Nature (2026),
  s41586-025-09833-y. Short Lean witnesses; massive RL training and
  test-time search; silver-medal standard on IMO 2024. **Status**: read.
- *Solving olympiad geometry without human demonstrations* (AlphaGeometry),
  Trinh et al., Nature (2024), s41586-023-06747-5. **Status**: read.
- Terence Tao et al., the equational theories project (2024): a 57-day
  human–AI collaboration producing 22M+ formalized implications, using
  Claude/ChatGPT for Lean formalization (Tao's blog; project GitHub;
  collaborative paper). **Status**: skimmed (blog + repo); paper scheduled.

## C7. Evidence regimes in AI-for-math (case cards)

These come from the 2026-09 internal research pass in the main thread. They
are evidence *regime* references for our own measurement design, not claims
about what any lab achieved. **Not yet re-verified against primary sources;
do not cite in the paper before that pass.**

- **DeepMind / Lean regime**: generator (RL-trained prover) → search
  (best-first / RL rollout) → verifier (Lean kernel) → human consumption
  (formal library). Clear separation of short witness from discovery compute.
  Sources: AlphaProof/AlphaGeometry2 papers (C6). Confidence: high.
- **OpenAI regime (four distinct evidence standards)**: (1) verified formal
  proofs, (2) verified computation, (3) novel theorems with human review,
  (4) expert-checked counterexamples to open problems — treated as separate
  standards, never merged into "AI solved math". Primary route for
  re-verification: OpenAI, "Sharing AI progress in mathematics"
  (openai.com/index/sharing-ai-progress-in-mathematics/).
  Confidence: medium-high (regime structure matches the public page;
  item-level mapping pending).
- **Anthropic regime (three strong-case types)**: open-problem
  counterexamples, new theorems, formalized/computational advances —
  separated by verification strength. Primary routes for re-verification:
  the Jacobian-conjecture counterexample announcement (July 2026) and the
  independent Lean 4 verification records on Zenodo (e.g. "An Independent
  Lean 4 Verification of the Alpöge–Fable Counterexample").
  Confidence: medium (primary-source pass pending).

Rule: keep these regimes separated; no "AI solved math" conflation
(`docs/research/math-computation-ai-systems.md`).

## C8. Benchmark science and reproducibility

- *Holistic Evaluation of Language Models* (HELM), Liang et al.,
  arXiv:2211.09110 (2022). Prompt-level transparency, multi-metric reporting,
  reproducibility. **Status**: read.
- EleutherAI `lm-evaluation-harness` — versioned task configs, logged samples
  (repo + CITATION file). **Status**: tooling read.
- UK AISI Inspect / `inspect_evals` — eval framework with contribution
  standards (reference results, transcript inspection, uncertainty).
  **Status**: tooling read.
- *Measuring What Matters: Construct Validity in Large Language Model
  Benchmarks*, Bean et al., NeurIPS 2025 D&B, arXiv:2511.04703.
  Construct-validity discipline. **Status**: read.
- Kaggle Benchmarks documentation — platform robustness/reproducibility/task
  contracts. **Status**: tooling read (L4 audit).
- *Do All Languages Cost the Same? Tokenization in the Era of Commercial
  Language Models*, Petrov et al., EMNLP 2023 (2023.emnlp-main.614).
  Tokenizer-fairness confound for length measurements. **Status**: read.

## C9. Information theory, MDL, and memorization

- Cover & Thomas, *Elements of Information Theory* (textbook;
  rate-distortion chapter).
- Grünwald, *The Minimum Description Length Principle*, MIT Press (2007)
  (two-part codes).
- Li & Vitányi, *An Introduction to Kolmogorov Complexity and Its
  Applications* (prefix machines; semi-computability).
- *Quantifying Memorization Across Neural Language Models*, Carlini et al.,
  ICLR 2023, arXiv:2202.07646. **Status**: read.
- *Rethinking LLM Memorization through the Lens of Adversarial Compression*,
  Schwarzschild et al., NeurIPS 2024, arXiv:2404.15146. **Status**: read
  (also the C2 MiniPrompt/ACR reference).

## C10. Readability and instrument design (light)

- Aquin-style instrumentation language (public site; repo `prior-art.md`) —
  the product honesty layer's vocabulary (mode labels, loss curves,
  attribution panels). **Status**: site review done.
- Repo-internal comparators (Murmur/Wittgenstein/Matter CI and
  golden-receipt practices) — engineering standards, not citations.

## Reconciliation note

Done this session: (1) MiniPrompt reconciled — the repo's citation is
Schwarzschild et al. 2404.15146; the ACL 2024 MinPrompt 2310.05007 is a
different paper and is not cited; (2) Prompting Complexity (2607.06145) fully
read and folded into `description-length-formalism.md` §3 with an explicit
positioning paragraph. Remaining before the paper cites C7: re-verify the
OpenAI/Anthropic case cards against the primary routes pinned in C7.
