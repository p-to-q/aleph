# Research Process

This file records how inspected research currently changes Aleph's product and technical direction.
The repository-wide versioned compact index is [`docs/source-ledger.md`](../source-ledger.md); it is
not a complete bibliography or a claim that all referenced methods are implemented.

## Research questions

1. Is reverse prompt search a real technical direction or only a metaphor?
2. Which existing methods are closest to Aleph's target behavior?
3. Which parts should become v0 product surfaces, and which should remain future adapters?
4. How should the repository preserve research without turning uncertain ideas into product facts?
5. Which repository conventions help future humans and agents without freezing Aleph into template noise?
6. Which contribution is computer science, and which mathematical examples are only stress tests or
   evidence cases?
7. When does a system merely describe a candidate, when does it discover a result, and what exactly
   has been verified?
8. How should test-time compute, search, formal checking, and human review be budgeted and recorded as
   separate interventions?
9. Which finite cases can be exhaustively enumerated or kernel-checked before expensive open search?
10. What evidence shows that a formal statement faithfully represents the informal claim that Aleph
    intends to study?

## Current research program

Aleph's paper-level center of gravity is computer science: program synthesis, formal methods and
theorem proving, test-time search, prompt optimization, benchmark science, reproducible systems, and
human checkability. Mathematical landmark problems are demanding environments in which those systems
can be understood; company demonstrations are case studies, not the citation spine or the paper's
scientific definition.

The synthesis of those systems is maintained in
[`math-computation-ai-systems.md`](math-computation-ai-systems.md). The staged, multi-role research
program and its proof/search/compute gates are maintained in
[`model-relative-coordinate-landmarks.md`](../plans/model-relative-coordinate-landmarks.md). The
larger readable-coordinate program remains the source of truth for estimands, falsification gates, and
the implementation sequence.

## Sources inspected

| Source | URL | What was observed | Effect on Aleph |
|---|---|---|---|
| p-to-q `repo-template` | https://github.com/p-to-q/repo-template | File-first seed; visible files are the contract; delete or park unused routes; lightweight mode is clear thesis, visible artifact, receipts/limitations, short docs map, license. | Keep the tone, not the rigid profile. Add `THESIS.md`, preserve checks, remove `optional/`, move decisions/plans into `docs/`. |
| p-to-q `AGENTS.md` | https://raw.githubusercontent.com/p-to-q/repo-template/main/AGENTS.md | Repository-first agent behavior, small reviewable changes, explicit validation, no hidden architectural decisions. | Strengthen `AGENTS.md`, `PROMPT.md`, and `engineering-discipline.md`. |
| p-to-q `WORKFLOW.md` | https://raw.githubusercontent.com/p-to-q/repo-template/main/WORKFLOW.md | Workflow is a contract, not a mandatory runtime; chat transcripts are not durable unless summarized. | Keep workflow lightweight and move decisions into docs, not raw chat. |
| ACR / MiniPrompt | https://arxiv.org/abs/2404.15146 | Directly operationalizes target-first shortest-input compression, the model-as-decompressor view, GCG search across prompt lengths, and memorization experiments. | Treat MiniPrompt as the mandatory closest white-box empirical baseline; Aleph cannot claim novelty for the bare reverse-search or compression-ratio object. |
| Prompting Complexity | https://arxiv.org/abs/2607.06145 | Directly formalizes fixed-model shortest plausible prompts, including exact, soft, and behavioral variants and coding-style bounds. | Treat it as the closest formal neighbor; Aleph must contribute an operational human-readable construct, working estimation, search, and provenance-aware interpretation. |
| ARCA paper | https://arxiv.org/abs/2303.04381 | Auditing can be formulated as discrete fixed-output optimization over prompts/outputs. | Keep ARCA as a lower-level fixed-length raw-coordinate comparator, not the closest empirical predecessor or product identity. |
| `ejones313/auditing-llms` | https://github.com/ejones313/auditing-llms | Includes a Reversing LLMs path that produces prompts for fixed outputs and exposes `--prompt_length`. | Informs an audited `arca` comparator where compatible; it does not replace the mandatory MiniPrompt reproduction. |
| Formal Mathematics Statement Curriculum Learning | https://cdn.openai.com/papers/Formal_Mathematics_Statement_Curriculum_Learning__ICML_2022.pdf | A language model proposes Lean tactics inside proof search; successful proofs become training data through expert iteration, while the Lean kernel checks the formal artifact. | Separate proposal, search, learning, and checking in Aleph's event model; a checked formal statement still needs a statement-fidelity review. |
| OpenAI o1 reasoning report | https://openai.com/index/learning-to-reason-with-llms/ | Reported gains depend on both learned reasoning behavior and test-time allocation, including sampling, consensus, reranking, and generated tests. | Treat compute and selection policy as experimental variables, not an unnamed property of a model. |
| Prover-Verifier Games | https://cdn.openai.com/prover-verifier-games-improve-legibility-of-llm-outputs/legibility.pdf | Optimizing only for correctness can reduce human legibility; training against a weaker verifier can improve the performance/checkability tradeoff. | Human checkability is a measured construct with its own protocol, not a synonym for correctness or model score. |
| OpenAI First Proof submissions | https://openai.com/index/first-proof-submissions/ | Natural-language research proof attempts involved manual interaction and best-of-few selection; later community feedback caused one initially favored attempt to be reclassified as incorrect, while other attempts remained under review. | Record released outputs and per-attempt review status without assigning the collection one categorical review grade; do not relabel a plausible or selected proof as verified. |
| OpenAI proof/research evidence regimes | [GPT-f](https://openai.com/index/generative-language-modeling-for-automated-theorem-proving/) / [expert-led cases](https://openai.com/index/accelerating-science-gpt-5/) / [unit-distance](https://openai.com/index/model-disproves-discrete-geometry-conjecture/) / [Ten Advances](https://openai.com/index/ten-advances-in-mathematics/) | Known-theorem proof search, expert-led collaboration, informal expert-reviewed discovery, and formally certified discovery expose different objects and selection processes. | Store regime, final object, checker, statement fidelity, novelty, and discovery provenance independently; never inherit an organization-level “solved math” label. |
| Anthropic Fermat formalization artifact | https://github.com/anthropics/fermats-last-theorem | The released Lean repository formalizes a known proof route and exposes the exact theorem, pinned toolchain, axiom audit, proof path, comparator, and additional-kernel checking route. | The final formal artifact is replayable; the reported internal-model, multi-agent generation run is not end-to-end reproducible, and kernel acceptance does not settle informal-statement fidelity. |
| Anthropic mathematical evidence regimes | [zeta](https://www.anthropic.com/research/riemann-zeta) / [cryptography](https://www.anthropic.com/research/discovering-cryptographic-weaknesses) / [Jacobian exposition](https://terrytao.wordpress.com/2026/07/21/a-digestion-of-the-jacobian-conjecture-counterexample/) | Explicit counterexample, related new theorem, known-proof formalization, executable attack, and infeasible full-scale computational argument require different validators. | Split HAWK from AES, separate the community Jacobian formalization from Anthropic, and never call zeta progress a solution to the Riemann hypothesis. |
| FunSearch | https://www.nature.com/articles/s41586-023-06924-6 | LLM-generated programs are evolved under an executable evaluator; the discovered program can be shorter and more interpretable than the construction it generates. | A strong pattern for compute-backed discovery when candidates have an objective, executable verifier; it does not transfer automatically to subjective prompt quality. |
| Discovery-compute separation | [FunSearch](https://www.nature.com/articles/s41586-023-06924-6) / [AlphaProof](https://www.nature.com/articles/s41586-025-09833-y) | A few-line program may follow roughly a million proposals; a short Lean proof may follow large-scale RL, tree search, and tens to hundreds of TPU-days of target-specific adaptation. | Final witness length, post-freeze checker cost, and discovery work are separate projections of one typed resource ledger. |
| AlphaGeometry | https://www.nature.com/articles/s41586-023-06747-5 | Neural auxiliary-construction proposals guide a symbolic deduction engine trained on synthetic theorems and proofs. | Keep learned proposal and symbolic verification distinct, and record the restricted formal language and translation boundary. |
| AlphaEvolve | https://storage.googleapis.com/deepmind-media/DeepMind.com/Blog/alphaevolve-a-gemini-powered-coding-agent-for-designing-advanced-algorithms/AlphaEvolve.pdf | An evolutionary controller edits programs and receives one or more automated evaluator signals; the evaluator is both the enabling mechanism and a scope limitation. | Use evaluator-backed program search as a systems analogue, while testing evaluator misspecification and charging all proposal/evaluation compute. |
| GCG paper | https://arxiv.org/abs/2307.15043 | Greedy/gradient search can automatically produce raw token strings that steer target outputs and underlies MiniPrompt's optimizer. | Keep GCG as a lower-level fixed-length raw comparator or proposal component; do not inherit its attack identity or treat it as the mandatory variable-length baseline. |
| `llm-attacks` repo | https://github.com/llm-attacks/llm-attacks | The public GCG implementation exposes batched gradient-guided token substitution and tokenizer/model constraints. | Freeze its snapshot and make tokenizer, access, batch-cost, and success semantics explicit in any comparator. |
| Probe Sampling paper | https://arxiv.org/abs/2403.01251 | GCG can be accelerated with draft-model filtering when draft and target predictions are similar. | Potential v2/v3 optimization path, not Hackathon scope. |
| Automatic Prompt Engineer | https://github.com/keirp/automatic_prompt_engineer | Public prompt-optimization loop that generates and selects instructions with LLM help. | Useful black-box search shape; do not collapse Aleph into generic instruction optimization. |
| PromptWizard | https://github.com/microsoft/PromptWizard | Task-aware prompt optimization framework with agent-style prompt improvement loops. | Reinforces generate/score/mutate route for hosted black-box work. |
| TextGrad | https://arxiv.org/abs/2406.07496 and https://github.com/zou-group/textgrad | Treats optimization over textual variables as automatic "differentiation" via textual feedback over computation graphs. | Important metaphor and route shape for Aleph; useful for black-box/hybrid optimization framing, but broader than target-output compression. |
| GEPA | https://github.com/CerebrasResearch/gepa | Reflective text evolution with Pareto-style optimization signals and DSPy integration. | Supports Aleph's multi-objective frontier framing; future adapter candidate, not current identity. |
| Prompt Tuning / Prefix Tuning | https://aclanthology.org/2021.emnlp-main.243/ and https://aclanthology.org/2021.acl-long.353/ | Continuous prompt parameters can be optimized while model weights stay frozen. | Strongest technical reading of "prompt is a parameter"; future soft-prompt research route. |
| Reverse Prompt Engineering | https://aclanthology.org/2025.emnlp-main.1333/ | Black-box reverse-prompt recovery from outputs is now an explicit neighboring research line. | Useful contrast: Aleph seeks a usable coordinate for a target output, not recovery of an original hidden prompt. |
| Garden path sentences and LLMs | https://aclanthology.org/2025.ccl-1.43.pdf | Garden path sentences have local or temporary ambiguity that can force reanalysis; Li, Ji, and Li (2025) find LLMs show garden-path effects in syntactic analysis, with cross-lingual differences between English and Chinese. | Adds a cautious lens for Custom API short prompts that appear strange but model-effective: call them garden-path-like prompt coordinates, not proven garden path sentences. See `docs/research/garden-path-prompts.md`. |
| vec2text / embedding inversion | https://github.com/vec2text/vec2text and https://arxiv.org/abs/2310.06816 | Embedding inversion reconstructs text from vector representations; related but solves a different inversion problem. | Keep as adjacent prior art; do not conflate with prompt-coordinate search. |
| Aquin | https://www.aquin.app/ | Instrumentation language: Observe & Find, Simulate & Fix, Debug & Improve, token attribution, loss curves, exposure vectors, evals. | Use as UI/instrumentation inspiration; translate safety/model-debug panels into compression-specific panels. |

## Settled conclusions from research

- Aleph is technically plausible as a staged system.
- The v0 product should be frontend-led and fixture-backed so the core interaction is legible before model integration.
- The real long-term core is a run contract: target + config + candidates + observations.
- White-box claims require logits or model internals; otherwise panels must be black-box, fixture, or simulated.
- The earlier single `leakage` score is superseded as a scientific construct. Existing n-gram overlap
  is a versioned surface-copy proxy; copy/code probes, public reference, corpus trace, training
  influence, extractability, association effect, self-citation, and trace integrity remain distinct
  evidence channels.
- ACR/MiniPrompt is the closest empirical collision and mandatory white-box baseline; Prompting
  Complexity is the closest formal neighbor. ARCA/GCG remain lower-level raw-coordinate comparators,
  not Aleph's identity or substitute baselines.
- The readable-versus-raw choice is partially settled: both are required views over one append-only
  observed archive. The product may default to readable coordinates, but raw coordinates are a
  mandatory comparator rather than deferred future work.
- Black-box prompt optimization families are useful route shapes, not Aleph's final framing.
- TextGrad is especially relevant as a metaphor for prompt-space optimization, but Aleph should keep its narrower target-output identity.
- Pareto / reflective optimization is a stronger fit for Aleph than single-score prompt improvement.
- Soft-prompt methods support the parameter analogy, but should remain future research until they can be related back to discrete prompt coordinates honestly.
- Mathematical-discovery systems are a relevant prior-art family, but the Aleph paper remains a
  computer-science paper about synthesis, search, verification, reproducibility, and checkable
  interaction. Mathematics supplies hard instances and possible formal artifacts, not borrowed
  prestige.
- **Description**, **discovery**, and **verification** are different states. A generated explanation
  can describe a candidate; novelty requires a documented comparison against prior knowledge; and a
  verifier certifies only a declared proposition or executable predicate under stated assumptions.
- Formal proof checking does not establish that the encoded statement matches the intended informal
  claim. Statement translation, trusted computing base, imports, axioms, and checker version remain
  part of the evidence boundary.
- Test-time compute is not a scalar badge. Proposal count, search topology, verifier calls, retries,
  human selection, wall time, and hardware/provider cost must be recorded separately.
- Garden-path-like prompt coordinates are a useful observation for the left side
  of the slider, especially in Custom API search, but Aleph should not claim
  formal garden path syntax without sentence-level ambiguity evidence.
- The repository should be artifact-first, not template-first.
- The current `search/` spike is implementation evidence that a fixed MLX Qwen model can propose and
  evaluate candidates. Its historical exported frontier is invalid as performance evidence because
  `monotone()` fabricated repeated length coordinates. PR #100 repaired that mutation in code. Keep
  the old export immutable as an invalid historical artifact, and generate a new receipt-backed
  artifact from real evaluations before citing any point or score.
- MLX v0.32.2 exposes Linux CPU and CUDA package variants in its official setup, and the maintainer's
  CUDA announcement documents both a working `mlx-lm` path and missing operations. Aleph should call
  the engine MLX-backed rather than Apple-Silicon-only, while treating Linux CUDA as an upstream
  capability that still requires an Aleph-specific conformance receipt rather than assumed parity.
- That spike should be treated as an experiment engine, not as the stable product API contract.

## Implementation implications

- `packages/core` owns the shared types and pure helpers.
- `packages/fixtures` provides stable demo data.
- `apps/web` consumes `AlephRun` and should not invent its own data model.
- `apps/api` is the stable product API surface and should wrap model/search engines rather than exposing experimental backend shapes directly to the UI.
- `search/` is the current local MLX live-search experiment and is wrapped behind `apps/api` through
  the `local_mlx_search` adapter. It remains optional until local setup and runtime evidence are
  available; Apple Silicon is the verified maintainer path, while upstream Linux CUDA support at MLX
  v0.32.2 remains unverified for this adapter and must not be advertised as Aleph runtime parity.
- Future adapters should be pluggable: `mock`, `hosted_black_box`, `local_openai`,
  `local_white_box`, `miniprompt`, `arca`, `gcg`; `miniprompt` is a mandatory closest-baseline
  reproduction, while ARCA/GCG are compatible lower-level comparators.
- Future research-only or adapter candidates now explicitly include reflective/Pareto search and soft-prompt projection.
- Open questions belong in `docs/open-questions.md`, not in hidden assumptions.
- The immediate foundations should be cheap and checkable: one finite exhaustive enumerator and one
  small Lean target before any claim depends on large autonomous runs.
- GitHub, Hugging Face, and Kaggle are publication and runtime-evidence surfaces. A successful hosted
  job demonstrates portability only after artifact readback; it does not define the scientific
  construct or by itself validate a benchmark score.

## Current gaps

- A real local MLX search runtime exists in `search/`, and `apps/api` has a `local_mlx_search` wrapper that maps live-search-shaped output into `AlephRun`. Current local verification still depends on the optional `search/.venv` MLX environment.
- The demo uses embedding similarity when available with a char-ngram fallback, but the default product metric is not yet settled.
- `search/` computes token-level NLL for precomputed runs, but the product API does not yet expose a stable white-box observation contract.
- No deletion ablation is implemented.
- No persistence layer is chosen.
- The post-Hackathon research mainline was previously implicit; it now needs to stay synchronized across README, research docs, and backlog.
- PR [#103](https://github.com/p-to-q/aleph/pull/103) merged on 2026-09-27 at
  [`179194ca2524a0d37f797684010e600c70a65774`](https://github.com/p-to-q/aleph/commit/179194ca2524a0d37f797684010e600c70a65774),
  adding `bounded-coordinate-v0` under `search/bounded/` and closing issue
  [#102](https://github.com/p-to-q/aleph/issues/102). It supplies exact shortest-coordinate ground
  truth for one finite synthetic two-landscape world as the first BCS R1 bootstrap tranche, not full
  `BCS-v0`, the full algorithm family, a compiler study, or real-model calibration.
- The merged tranche's bounded Lean project proves coverage, no shorter witness, bounded uniqueness,
  and published representative-frontier observation membership for its generated finite model. It
  does not prove the planned
  threshold-duality/compiler theorems, verify the Python frontier-selection implementation, or
  exercise a statement-fidelity protocol on an Aleph claim.
- No long-run compute study yet publishes all six `ResourceLedger/0.1.0` accounts, typed human
  provenance, and a stable discovery scaling curve.
- PR #100 fixed the frontier mutation bug in code, but the historical MLX-derived public frontier
  JSON remains invalid until every displayed point is linked to an actual evaluation and the artifact
  is regenerated with receipts.

These gaps belong in roadmap or issues, not in hidden assumptions.
