# Source Ledger

- Index version: `SOURCE-INDEX/0.3.0`
- Evidence cutoff: 2026-09-27
- Scope: compact navigation index for sources that materially change Aleph's definitions, baselines,
  evidence rules, or implementation choices

This repository is an adapted product/research scaffold, not a verbatim mirror of any source. This
ledger is a compact index, not an exhaustive literature review. URLs are the primary pages or
artifacts inspected at the evidence cutoff; the word “primary” records provenance, not permanence,
independent replication, or a stable external interface. Every transferred claim remains bounded by
the cited version, artifact, method, and evidence limitation below.

## p-to-q repository template

Source: https://github.com/p-to-q/repo-template

Observed:

- clear thesis -> visible artifact -> receipts or limitations -> short docs map -> license;
- file-first repository surface;
- profile selection exists, but the template itself says unused routes should be removed or parked;
- optional decisions, research, exec plans, history, release, strict workflows, and agent rules;
- repository-first agent behavior and explicit validation.

Aleph adaptation:

- use p-to-q as a tone and discipline reference, not a binding architecture;
- choose an artifact-first product-lab shape;
- keep thesis, public entrypoint, contracts, research notes, sparse decisions, plans, and lightweight agent delegation;
- remove the `optional/` directory so active material is not hidden behind template scaffolding;
- park release, strict workflow, full RFC, CODEOWNERS, and history routes.

## Compact research and implementation index

| Source | URL | Aleph use |
|---|---|---|
| ACR / MiniPrompt | https://arxiv.org/abs/2404.15146 | Closest empirical predecessor and mandatory white-box target-first baseline; its heuristic best found is not an oracle minimum. |
| Prompting Complexity | https://arxiv.org/abs/2607.06145 | Closest formal neighbor; its definitions and bounds do not supply Aleph's human protocol, search system, or provenance interpretation. |
| ARCA paper | https://arxiv.org/abs/2303.04381 | Lower-level fixed-length raw-coordinate optimization comparator, not the closest predecessor. |
| `auditing-llms` repository | https://github.com/ejones313/auditing-llms | Concrete Reversing LLMs path for an audited ARCA comparator where compatible. |
| GCG paper | https://arxiv.org/abs/2307.15043 | Lower-level raw-token optimizer and MiniPrompt component, not a substitute for the mandatory MiniPrompt comparison. |
| `llm-attacks` repository | https://github.com/llm-attacks/llm-attacks | GCG implementation reference whose tokenizer, access, batch-cost, and success assumptions must remain visible. |
| Probe Sampling paper | https://arxiv.org/abs/2403.01251 | Possible future acceleration route for candidate search. |
| vec2text repository | https://github.com/vec2text/vec2text | Adjacent inversion work; clarifies what Aleph is not. |
| Text Embeddings Reveal Almost As Much As Text | https://arxiv.org/abs/2310.06816 | Embedding inversion reference; adjacent but not prompt-coordinate search. |
| Aquin | https://www.aquin.app/ | UI/instrumentation inspiration: token attribution, loss, exposure, evals. |

## Mathematical and causal anchors

| Source | Primary URL inspected | Aleph use | Evidence boundary |
| --- | --- | --- | --- |
| Algorithmic statistics and the structure function | https://homepages.cwi.nl/~paulv/papers/structure.pdf | Defines the classical structure-function landscape that constrains Aleph's model-relative analogy. | Universal-machine, finite-set, and incomputability results are not equalities for a tokenizer, hosted model, or human-readable prompt domain. |
| Individual algorithmic rate-distortion | https://homepages.cwi.nl/~paulv/papers/rateieee-it.pdf | Connects description budget to distortion for an individual object and motivates a budget-indexed curve. | Classical algorithmic distortion inherits universal-machine and effectiveness assumptions that Aleph must not smuggle into empirical model runs. |
| Levin Tree Search | https://proceedings.neurips.cc/paper/2018/file/52c5189391854c93e8a0e1326e56c14f-Paper.pdf | Gives a policy-relative search guarantee that helps state when tree-search work can be bounded. | The guarantee depends on a declared tree, policy, goal test, and node-expansion cost; it does not apply unchanged to open, noisy prompt search. |
| Universal restart schedules | https://www.cs.utexas.edu/~diz/pubs/speedup.pdf | Supplies the classical comparison for unknown Las Vegas runtime distributions. | The result assumes independent restarts and a sound success test; adaptive provider drift or fallible verification breaks that interpretation. |
| Interference and exposure mappings | https://doi.org/10.1214/16-AOAS1005 | Provides causal-design language for assignment, exposure, interference, and estimands in paired source experiments. | Identifiability follows only under the declared assignment and exposure conditions; observational model outputs alone do not identify source. |
| Counterfactual Memorization | https://arxiv.org/abs/2112.12938 | Defines an example-level counterfactual training intervention for measuring memorization. | The estimand requires retraining worlds and is not recoverable from a single deployed checkpoint or prompt/output trace. |
| Datamodels | https://proceedings.mlr.press/v162/ilyas22a.html | Models how training-subset membership predicts model behavior and motivates explicit intervention receipts. | A predictive datamodel is an approximation over a chosen subset distribution, not a universal historical attribution oracle. |
| TRAK | https://proceedings.mlr.press/v202/park23c.html | Supplies scalable training-data attribution estimates and useful empirical baselines. | Attribution scores depend on approximation and model/task choices; they do not by themselves identify causal information source. |
| The Secret Sharer | https://arxiv.org/abs/1802.08232 | Defines exposure and planted-canary tests for unintended memorization. | Canary extraction detects a controlled channel; it neither proves universal non-leakage nor explains every natural target. |

## Mathematics, computing, and AI systems

This is the compact primary-source ledger for the long-horizon program, not a replacement for the
comparison in [`research/math-computation-ai-systems.md`](research/math-computation-ai-systems.md).
Entries record the system mechanism Aleph is borrowing or testing and the boundary on what that
source establishes.

| Source | Primary URL inspected | System evidence used by Aleph | Evidence boundary |
| --- | --- | --- | --- |
| Syntax-Guided Synthesis (SyGuS) | https://people.csail.mit.edu/rishabh/papers/sygusFMCAD13.pdf | A synthesis problem can make the candidate language and semantic specification explicit, enabling solver comparison. | Aleph's stochastic model behavior and human readability are not a complete logical specification; the analogy must be tested, not asserted. |
| DreamCoder | https://people.csail.mit.edu/asolar/papers/EllisWNSMHCST21.pdf | Search, learned recognition, and library learning can jointly build reusable abstractions for compact programs. | Learned abstractions and MDL-style preferences do not prove globally minimal prompts or human-readable coordinates. |
| FunSearch | https://www.nature.com/articles/s41586-023-06924-6 | LLM proposals, evolutionary selection, a program database, and executable scoring form a discovery loop over program space. | The method assumes an efficient, informative evaluator and a suitable program skeleton; open-ended text quality lacks that oracle. |
| AlphaEvolve | https://storage.googleapis.com/deepmind-media/DeepMind.com/Blog/alphaevolve-a-gemini-powered-coding-agent-for-designing-advanced-algorithms/AlphaEvolve.pdf | Multi-model program editing plus parallel evaluators extends evaluator-backed search to larger code and multiple objectives. | Its reported discoveries do not establish Aleph's construct; evaluator misspecification and compute accounting remain first-class risks. |
| AlphaGeometry | https://www.nature.com/articles/s41586-023-06747-5 | Synthetic theorem generation trains a neural guide that proposes auxiliary constructions for a symbolic deduction engine. | The formal geometry language is restricted, and translation from an informal problem is outside the symbolic proof guarantee. |
| AlphaProof | https://www.nature.com/articles/s41586-025-09833-y | Reinforcement learning and proof search operate against a formal proof environment with mechanically checkable terminal states. | Competition performance under a translated formal task is not evidence for unrestricted research mathematics or Aleph's search objective. |
| LeanDojo / ReProver | https://arxiv.org/abs/2306.15626 | A reproducible Lean environment, premise retrieval, and proof search expose interfaces between models and a formal checker. | Kernel acceptance covers the encoded theorem and dependencies, not the fidelity of an informal-to-formal translation. |
| Meta AutoformBot / Atlas | [execution overlay `1592d6a`](https://github.com/facebookresearch/autoform-bot/tree/1592d6a28bd316fde0101e271ed787a989dc66be) / [main framework `afaf215`](https://github.com/facebookresearch/autoform-bot/tree/afaf215ea63c2cc39fb1fb5492743129110ff6e0) / [formal library](https://github.com/facebookresearch/atlas-lean) | The opt-in execution overlay implements the orchestrated dependency-DAG/worktree flow; default main intentionally omits autonomous orchestration, while Atlas exposes the public formal library. | Replaying a bounded workflow depends on provider/model availability and compute; compilation checks formal statements, while semantic faithfulness and mathematical quality still require separate review. |
| Formal Mathematics Statement Curriculum Learning | https://cdn.openai.com/papers/Formal_Mathematics_Statement_Curriculum_Learning__ICML_2022.pdf | Statement curriculum, expert iteration, Lean proof search, and a formal benchmark separate proposal from checking. | Benchmark success is conditional on the formal statements, split, environment, and search budget. |
| Scaling LLM Test-Time Compute Optimally | https://arxiv.org/abs/2408.03314 | Search and verifier-guided allocation can outperform indiscriminate best-of-N at matched inference budgets. | Results are model-, task-, and verifier-dependent; “thinking longer” is not one reproducible intervention. |
| PRM800K / process supervision | https://arxiv.org/abs/2305.20050 | Step-level human labels and process reward models provide a route for evaluating intermediate reasoning rather than final answers alone. | A learned process reward is a fallible proxy, not a proof checker or human-readability measure. |
| Prover-Verifier Games | https://cdn.openai.com/prover-verifier-games-improve-legibility-of-llm-outputs/legibility.pdf | Optimizing for a weaker verifier can improve the tradeoff between task performance and human checkability. | The reported arithmetic task and evaluator population do not validate Aleph's readability construct; Aleph still needs independent raters and decoys. |
| OpenAI First Proof submissions | https://openai.com/index/first-proof-submissions/ | Released research-level proof attempts expose manual interaction, best-of-few selection, community feedback, correction, and unresolved states. | OpenAI explicitly describes the sprint as not cleanly controlled; the collection receives no categorical review grade, and an attempt under review is not a formal certificate. |
| OpenAI AI as a Scientific Collaborator | https://cdn.openai.com/pdf/f4b4a5da-b2de-418d-9fcd-6b293e9dc157/oai_ai-as-a-scientific-collaborator_jan-2026.pdf | Case studies expose hybrid workflows across literature search, natural-language reasoning, computation, formal tools, and expert validation. | The report is a curated company account using non-public model/runtime components; each mathematical result still needs its cited paper, artifact, and independent novelty/correctness review. |
| OpenAI GPT-f | [project page](https://openai.com/index/generative-language-modeling-for-automated-theorem-proving/) / [paper](https://arxiv.org/abs/2009.03393) | Transformer-guided Metamath search produced shorter proofs of known theorems, some accepted into the main library. | Accepted formal proofs support checker-relative witness claims; they do not make the theorem new or expose an end-to-end replay of the original model and search. |
| OpenAI expert-led science cases | [official account](https://openai.com/index/accelerating-science-gpt-5/) / [report](https://cdn.openai.com/pdf/4a25f921-e4e0-479a-9b38-5367b47e8fd0/early-science-acceleration-experiments-with-gpt-5.pdf) | Curated cases distinguish proposal, literature work, computation, expert repair, and validation, including a correct rediscovery whose attribution was initially missed. | The collection is not a systematic sample and explicitly does not show an autonomous research system; correctness, novelty, and attribution stay separate. |
| OpenAI unit-distance disproof | https://openai.com/index/model-disproves-discrete-geometry-conjecture/ | A released informal proof, external mathematical checks, and human-authored companion remarks show an expert-reviewed open-problem output. | The proof is not a formal certificate, and the internal generator, complete search trace, and harness are not replayable. |
| OpenAI Ten Advances | [official account](https://openai.com/index/ten-advances-in-mathematics/) / [Lean certificates](https://github.com/openai/ten-proofs) | Ten claimed open-problem results have public Lean 4.32 certificates and a Comparator checking route. | Formal certificates check frozen Lean statements, not informal-statement equivalence or the closed Astra discovery run; discovery and verification receive separate evidence grades. |
| Anthropic Fermat's Last Theorem formalization | [technical account](https://www.anthropic.com/research/formalizing-fermats-last-theorem) / [proof artifact](https://github.com/anthropics/fermats-last-theorem) | A multi-agent internal-model run followed a known proof route; the public artifact pins Lean/Mathlib, states the theorem exactly, audits axioms, and documents comparator and additional-kernel checks. | The final encoded proof is replayable, but the reported six-billion-token generation system is not end-to-end public; this is formalization, not discovery of FLT, and kernel replay does not settle informal correspondence or explanatory quality. |
| Anthropic/Fable Jacobian counterexample | [independent mathematical exposition](https://terrytao.wordpress.com/2026/07/21/a-digestion-of-the-jacobian-conjecture-counterexample/) / [community Lean](https://github.com/alerad/alpoge-lean) | The explicit three-variable polynomial witness separates an exactly checkable counterexample from the model process; the community formalization is an independent artifact. | Dimension two remains open. Do not attribute the community Lean repository to Anthropic or convert the public witness into a replayable Fable discovery run. |
| Anthropic zeta lower bound | [technical account](https://www.anthropic.com/research/riemann-zeta) / [formal artifact](https://github.com/anthropics/formal-math) | The 67.2 percent lower-bound claim exposes a 31-million-token multi-agent search, failed ideas, literature work, expert assessment, and a separate Lean certificate. | This is a related new theorem, not a proof or disproof of the Riemann hypothesis; partial process material is not the complete discovery trace. |
| Anthropic HAWK key recovery | [technical account](https://www.anthropic.com/research/discovering-cryptographic-weaknesses) / [artifact](https://github.com/anthropics/cryptography-research-demo) | HAWK-256 supplies an end-to-end executable key-recovery case and a public research artifact, alongside roughly 60 hours and USD 100,000 of reported discovery work. | Larger HAWK parameters remain impractical to attack; upstream code is not an Aleph-independent replay receipt until pinned and run. |
| Anthropic reduced-round AES | [technical account](https://www.anthropic.com/research/discovering-cryptographic-weaknesses) / [artifact](https://github.com/anthropics/cryptography-research-demo) | The Möbius-Bridge method reports a 200--800x improvement for a seven-round AES-128 attack and exposes reduced computational artifacts. | It does not break full ten-round AES; the roughly `2^105` chosen-plaintext assumption makes a complete attack infeasible, so the main claim is not an end-to-end executable full attack. |
| miniF2F | https://github.com/openai/miniF2F/tree/v1 | A frozen branch of cross-system formal statements illustrates versioned theorem-proving evaluation. | The repository is archived and the task begins after formalization; natural-language translation and current ecosystem support are outside its score. |
| HELM | https://github.com/stanford-crfm/helm | Typed scenarios, adapters, requests, raw outputs, metrics, and aggregates support transparent, replayable evaluation. | A framework run is only as valid as its frozen task, model identity, environment, and missing/failure policy. |
| MLX v0.32.2 Linux backends | [tagged setup](https://github.com/ml-explore/mlx/blob/v0.32.2/setup.py) / [maintainer CUDA announcement](https://github.com/ml-explore/mlx/discussions/2422) | The tagged package exposes Linux CPU plus CUDA 12/13 variants, so the experimental engine is not inherently macOS-only. | Upstream availability does not prove Aleph adapter parity. The announcement lists missing CUDA operations and performance cliffs; Linux needs its own pinned conformance run before support is claimed. |

Company reports are retained here only when they expose a method, artifact, or failure boundary that
changes Aleph's design. They are not substituted for peer-reviewed method papers, independent
replication, or Aleph's own experiments.

## Runtime and publication boundary

Kaggle, Hugging Face, and GitHub are not three benchmark definitions. The repository's versioned
protocol and artifacts are authoritative. Kaggle can supply hosted-runtime and quota evidence;
Hugging Face can publish immutable data/release revisions; GitHub can expose code, decisions, and
checksums. A hosted task is evidence only after readback and replay, and successful execution alone
does not activate a scientific score or validate a mathematical claim.

## Conversation artifacts

The conversation produced product decisions, logo directions, UI prototypes, and architecture choices. They are summarized in `docs/archive/conversation-record.md` and kept as prototype HTML under `docs/archive/prototypes/`.

Reference screenshots were removed in the second repository pass to avoid confusing visual research with durable product source.
