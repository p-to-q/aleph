# Mathematics, Computation, and AI Systems

- Status: evidence-graded technical survey and research-system design note
- Evidence cutoff: 2026-09-27
- Scope: computer-science methods for mathematical discovery, proof, formalization, and checkable
  human--AI collaboration
- Claim status: this document defines research routes and evidence rules; it does not report Aleph
  experimental results

## Executive answer

The reviewed systems do not support the story that a single language model simply “became a
mathematician.” They support the following testable systems claim:

> Mathematical progress becomes more reliable when proposal generation, search, execution,
> verification, formalization, and expert judgment are separated into explicit roles and connected by
> replayable artifacts.

The balance differs by laboratory.

- Anthropic's 2026 evidence spans **four different claim objects**: an explicit Jacobian
  counterexample, a new zeta-function theorem related to but not resolving the Riemann hypothesis,
  large-scale formalization of a known FLT proof route, and computational cryptanalysis with both an
  executable HAWK case and an infeasible full-scale reduced-round AES case. Their validators and
  reproducibility levels cannot be inherited from one another
  ([zeta account](https://www.anthropic.com/research/riemann-zeta),
  [cryptography account](https://www.anthropic.com/research/discovering-cryptographic-weaknesses),
  [FLT artifact](https://github.com/anthropics/fermats-last-theorem)).
- OpenAI likewise exposes **four evidence regimes** rather than one “AI solved math” claim: GPT-f
  searches formal proofs of known theorems; expert-led collaborations combine model proposals and
  human validation; First Proof releases selected informal attempts with per-problem review states;
  and newer autonomous open-problem results split again between informal expert review and public
  Lean certificates. None of these makes the closed discovery harness independently reproducible
  ([GPT-f](https://openai.com/index/generative-language-modeling-for-automated-theorem-proving/),
  [First Proof](https://openai.com/index/first-proof-submissions/),
  [Ten Advances](https://openai.com/index/ten-advances-in-mathematics/)).
- Google DeepMind has published several distinct **generator--search--verifier systems**.
  AlphaGeometry couples learned construction proposals to symbolic deduction; FunSearch and
  AlphaEvolve evolve executable programs under automated evaluators; AlphaProof treats interaction
  with Lean as a reinforcement-learning environment. These are different systems for different
  mathematical objects, not one universal “AI mathematician” method
  ([AlphaGeometry code](https://github.com/google-deepmind/alphageometry),
  [FunSearch paper and artifacts](https://www.nature.com/articles/s41586-023-06924-6),
  [AlphaEvolve white paper](https://storage.googleapis.com/deepmind-media/DeepMind.com/Blog/alphaevolve-a-gemini-powered-coding-agent-for-designing-advanced-algorithms/AlphaEvolve.pdf),
  [AlphaProof paper](https://www.nature.com/articles/s41586-025-09833-y)).
- Meta, the Lean ecosystem, and Berkeley-associated work provide reusable infrastructure around
  headline systems: proof-state search, open theorem-proving environments, versioned libraries,
  compute-aware inference, contamination-resistant splits, and interfaces that let people inspect
  what was actually proved
  ([HTPS](https://arxiv.org/abs/2205.11491),
  [LeanDojo/ReProver](https://arxiv.org/abs/2306.15626),
  [compute-optimal test-time search](https://arxiv.org/abs/2408.03314),
  [Mathlib](https://github.com/leanprover-community/mathlib4)).

For Aleph, the conclusion is not “turn into a pure-mathematics project.” Aleph remains a computer
science system and benchmark whose mathematical layer makes its objects precise, supplies finite
ground truth, exposes impossibility boundaries, and produces certificates. Kaggle is a portability
and operations surface. It cannot substitute for the search algorithm, the mathematical object, or
the evidence artifact.

## Evidence discipline

### Evidence is a claim-specific vector

Every system claim should be recorded on four independent axes. Evidence on one axis does not resolve
another.

| Axis | Question | Claim-appropriate evidence for the axis |
| --- | --- | --- |
| `A` artifact | What durable object is public? | Pinned source, weights, data, raw traces, outputs, environment, and licenses |
| `V` validity | Why should the result be accepted? | Exact checker or executable oracle where available, or a calibrated preregistered statistical/human protocol, plus specification and semantic review |
| `R` reproducibility | Can an independent group regenerate the result? | One-command replay under a declared budget from public inputs and models |
| `P` provenance | Can we reconstruct how the artifact was selected? | Append-only proposals, failures, retries, human interventions, costs, and selection rules |

The following evidence tags describe *claims*, not organizations:

- **`M` mechanically checked:** a pinned checker accepts a precisely identified formal object.
- **`X` executable:** a public program or construction satisfies a public executable test.
- **`E` empirical:** a preregistered or fully specified experiment supports a statistical claim.
- **`H` expert reviewed:** named domain experts assessed the informal mathematical meaning.
- **`O` output released:** final answers, proofs, programs, or scored candidates are public.
- **`S` self-reported:** the producing organization reports an outcome, but the generative run cannot
  be independently replayed.

`M` is not automatically stronger than `H` for every question. A Lean kernel can establish that a
formal term inhabits a formal proposition; it cannot by itself establish that the proposition is the
intended translation of an informal problem. Lean's own community guidance therefore treats expert
confirmation of the statement's correspondence as a necessary step when the claim is not already a
known Mathlib statement
([Lean community verification guidance](https://github.com/leanprover-community/leanprover-community.github.io/blob/lean4/templates/did_you_prove_it.md)).

### Artifact packaging levels and local replay

This survey uses `REP-0`--`REP-4` to classify the **contents of one named public artifact package at
the evidence cutoff**. These labels are deliberately different from the normative research rounds
`R0`--`R4` in
[`MRC-LANDMARKS/0.1.0`](../plans/model-relative-coordinate-landmarks.md#r0--r4-research-rounds).
The latter govern project progression; `REP-*` describes what the released package makes available,
not whether an Aleph maintainer happened to run it successfully.

| Level | Minimum public material | Packaging claim |
| --- | --- | --- |
| `REP-0` report only | Narrative, aggregate score, or selected examples | Reported outcome only |
| `REP-1` inspectable output | Final proofs/programs/answers and problem statements | The released object can be inspected; generation is unknown |
| `REP-2` checkable output | `REP-1` plus pinned checker/evaluator and a declared runnable verification path | The package identifies the object, checker, and verification command; actual execution is recorded separately |
| `REP-3` partial-regeneration package | Method, partial code/data, and enough public components to rerun a reduced or representative experiment | The package targets a bounded reproduction, not the original scaled run |
| `REP-4` end-to-end-regeneration package | Public code, models/weights or stable APIs, inputs, configs, raw traces, environment, seeds, and declared compute sufficient to repeat the main run | The package targets independent end-to-end regeneration under the stated tolerance |

Every Aleph evidence card carries a separate field
`localReplayStatus ∈ {not_recorded, blocked, failed, passed}`. `passed` requires a linked command,
environment, artifact digest, and receipt; `blocked` or `failed` requires the failure boundary. A
local pass does not upgrade `REP-*`, and a local failure does not automatically downgrade it: either
may motivate a new packaging audit. Unless this document links an Aleph replay receipt, the status is
`not_recorded`.

There is no packaging level for “the paper is detailed enough that we could probably reimplement
it.” That may be a detailed specification, but it is not a released regeneration package.

### The 2026 closed-system boundary

As of the evidence cutoff:

- OpenAI's First Proof generator is described as an **internal model**; its model checkpoint, complete
  harness, search trace, and controlled rerun configuration are not public. The released attempts are
  `O/S` evidence at `REP-1`. Expert and community feedback is part of the reported process, but the
  selected attempts are not a controlled, independently replayable expert-evaluation artifact
  ([OpenAI's own process disclosure](https://openai.com/index/first-proof-submissions/)).
- Anthropic released a highly checkable FLT Lean repository, including pinned versions and multiple
  verification routes, so the *final formal artifact* is `M/O` at `REP-2`. The primary Lean-kernel
  build is supplemented by `nanoda` 0.4.13, a second independent Lean-kernel implementation, but the
  published run applies four disclosed patches: one adds progress output and three accelerate
  definitional-equality search. The authors state that none changes a typing rule; this is not an
  untouched second implementation. The reported generation used
  a general-purpose internal research model and a Claude-Code-based multi-agent harness at a scale of
  roughly six billion output tokens; its released *generation package* is `REP-0`
  ([Anthropic account](https://www.anthropic.com/research/formalizing-fermats-last-theorem),
  [repository verification instructions](https://github.com/anthropics/fermats-last-theorem)).
- AlphaProof publishes methods, pseudocode, public benchmark statements, and example proof displays,
  but its code-availability section
  offers a server-side interactive tool rather than the training and inference system. The paper also
  describes bespoke training at a scale beyond most academic groups and multi-day test-time
  reinforcement learning. The paper reports Lean-kernel checking and named expert judging; without a
  public one-command replay package for the generated proofs, this survey records `O/H/S` at
  `REP-1`. There is no released generated-proof checker package at `REP-2`, and the training/inference
  package is `REP-0`
  ([paper, data, and code-availability statements](https://www.nature.com/articles/s41586-025-09833-y)).
- AlphaEvolve publishes a white paper and mathematical-result notebook, while the official launch
  offered an early-access program. The evolutionary architecture is specified; the production system,
  model service, distributed controller, and complete trial histories are not released. The named
  result notebook is `REP-1`; the production-system description is `REP-0`
  ([official account](https://deepmind.google/blog/alphaevolve-a-gemini-powered-coding-agent-for-designing-advanced-algorithms/),
  [white paper](https://storage.googleapis.com/deepmind-media/DeepMind.com/Blog/alphaevolve-a-gemini-powered-coding-agent-for-designing-advanced-algorithms/AlphaEvolve.pdf)).

These boundaries are not accusations. They determine which results Aleph may cite as inspiration,
which systems it may compare against, and which experiments it can honestly reproduce.

## Case-level evidence: discovery is not one regime

The unit of evidence is a claim object, not a laboratory or model family. “AI solved mathematics”
collapses at least the final witness, its checker, the discovery process, statement fidelity,
novelty, and human intervention. The cases below therefore assign tags to the named object only.

### OpenAI: four regimes, with two validation forms inside the fourth

| Regime | Claim object and process | Evidence reading | Boundary for Aleph |
| --- | --- | --- | --- |
| `OA-1` formal proof search: GPT-f (2020) | A transformer-guided Metamath prover found shorter proofs of known theorems; OpenAI reports that several were accepted into the main Metamath library. | Accepted proof objects are `M/H/S`; the original model/search run is `S` and below end-to-end replay. | This is witness search and proof compression, not discovery of a new theorem. A short accepted proof says nothing by itself about search work. ([project page](https://openai.com/index/generative-language-modeling-for-automated-theorem-proving/), [paper](https://arxiv.org/abs/2009.03393)) |
| `OA-2` expert-led research collaboration (2025) | Curated cases combine model proposals, literature work, computation, expert correction, and final human validation; the report includes both new contributions and a rediscovered argument whose prior source was initially missed. | Named outputs are `O/H/S` at `REP-1`; the collection is not a systematic evaluation. | Correctness, novelty, and attribution require separate fields. The source explicitly says the model did not autonomously run research projects. ([official account](https://openai.com/index/accelerating-science-gpt-5/), [report](https://cdn.openai.com/pdf/4a25f921-e4e0-479a-9b38-5367b47e8fd0/early-science-acceleration-experiments-with-gpt-5.pdf)) |
| `OA-3` open informal attempts: First Proof (2026) | Ten natural-language research-proof attempts used human retry suggestions, cross-model review, clarification, and best-of-few selection. One initially favored attempt was later judged incorrect; others retained per-problem review states. | The released collection is `O/S`, `REP-1`. An individual attempt may add `H` only when its named review status supports that claim; the whole collection never inherits one review grade. | Keep every attempt, reversal, and intervention. “Selected,” “plausible,” “under review,” and “correct” are different states. ([process and attempts](https://openai.com/index/first-proof-submissions/)) |
| `OA-4a` autonomous open-problem output with informal expert checking: unit-distance disproof (2026) | A released proof gives infinitely many counterexamples to the conjectured `n^(1+o(1))` unit-distance bound; external mathematicians checked the argument and wrote companion remarks. | Final argument `O/H/S`, `REP-1`; generator and full discovery harness are not public. | An expert-reviewed informal proof is not a machine certificate or a replayable discovery algorithm. ([official account](https://openai.com/index/model-disproves-discrete-geometry-conjecture/)) |
| `OA-4b` autonomous open-problem output with formal certificates: Ten Advances (2026) | OpenAI reports ten results found by an internal Astra version, roughly USD 2,000 of discovery tokens at Sol API rates, later human/model manuscript preparation, and one Lean certificate per result. | Public certificate package `REP-2`, with `M/O/S`, a pinned Lean 4.32 build, and Comparator route; discovery-process package `REP-0`. | A Lean certificate checks its formal statement, not the equivalence of that statement to the informal problem, and does not replay closed-model discovery. ([official account](https://openai.com/index/ten-advances-in-mathematics/), [Lean repository](https://github.com/openai/ten-proofs)) |

### Anthropic: counterexample, theorem, formalization, and computation are distinct

| Regime | Claim object and process | Evidence reading | Boundary for Aleph |
| --- | --- | --- | --- |
| `AN-1` explicit counterexample: Jacobian | A public polynomial map over three variables has constant nonzero Jacobian determinant while mapping three rational points to one image, refuting the conjecture in dimension three and above. Tao supplied an independent mathematical exposition; a community Lean project is separate from Anthropic. | The explicit witness is `X/O/H`; the community formalization, if independently rebuilt, is a separate `M/O` artifact. The Fable discovery process is `S`. | The two-dimensional Jacobian conjecture remains open. Never attribute the community Lean artifact to Anthropic. ([Tao exposition](https://terrytao.wordpress.com/2026/07/21/a-digestion-of-the-jacobian-conjecture-counterexample/), [community Lean](https://github.com/alerad/alpoge-lean)) |
| `AN-2` related new theorem: zeta zeros (2026) | A 31-million-output-token run, including an initial 650 failed ideas and a later roughly 60-agent search, improved a lower bound from 41.6% to 67.2%; Anthropic mathematicians and outside experts examined it, and an official Lean artifact is public. | Final claim `M/O/H/S`; formal artifact package `REP-2`. Discovery traces are partial, not the complete 31-million-token run; `localReplayStatus=not_recorded`. | This does not prove or disprove the Riemann hypothesis, and Anthropic explicitly says the technique is not expected to do so. ([technical account](https://www.anthropic.com/research/riemann-zeta), [formal artifact](https://github.com/anthropics/formal-math)) |
| `AN-3a` known-proof formalization: FLT (2026) | A multi-agent internal-model run formalized an existing proof route into a very large pinned Lean project with comparator, axiom audit, and additional-kernel routes. | Final artifact `M/O`, package `REP-2`; generation is `S`, package `REP-0`; `localReplayStatus=not_recorded`. | The contribution is formalization and proof engineering, not discovery of Fermat's Last Theorem or a new proof route. ([account](https://www.anthropic.com/research/formalizing-fermats-last-theorem), [artifact](https://github.com/anthropics/fermats-last-theorem)) |
| `AN-3b` executable computational advance: HAWK (2026) | The reported HAWK-256 key-recovery attack runs end to end; the public repository contains HAWK code, while discovery took about 60 hours and an estimated USD 100,000 in API cost. | Demonstration `X/O/E/H`; the public bounded method/artifact package is `REP-3`; `localReplayStatus=not_recorded`. Discovery remains `S` with a `REP-0` process package. | Larger HAWK parameter sets remain impractical to attack; the result is specific to HAWK and not a break of lattice cryptography generally. ([account](https://www.anthropic.com/research/discovering-cryptographic-weaknesses), [code](https://github.com/anthropics/cryptography-research-demo)) |
| `AN-3c` computational advance without full-scale execution: reduced-round AES (2026) | A new meet-in-the-middle method is reported to improve attacks on seven-round AES-128 by roughly 200--800 times after up to a billion model-output tokens and hundreds of human validation hours. | Method and reduced artifacts are `E/O/H/S`, not a full-attack `X` claim. | It does not attack full ten-round AES; the assumed roughly `2^105` chosen plaintexts make the complete attack impractical. ([account](https://www.anthropic.com/research/discovering-cryptographic-weaknesses), [code](https://github.com/anthropics/cryptography-research-demo)) |

### DeepMind and Lean: short witnesses can require enormous discovery work

- **FunSearch:** the Nature system samples on the order of one million programs through parallel
  evolutionary islands, yet may return a concise function of only a few lines. The public repository
  omits the production language model, untrusted-code sandbox, and distributed stack. The final
  program can be `X/O/E`; the public reference package is `REP-3`, while the production discovery
  package is `REP-0`
  ([paper](https://www.nature.com/articles/s41586-023-06924-6),
  [repository](https://github.com/google-deepmind/funsearch)).
- **AlphaProof:** the paper reports roughly 80,000 TPU-days for main RL, search sweeps from two TPU
  minutes to twelve TPU hours per problem, and target-specific test-time RL measured in tens to
  hundreds of TPU-days per problem. Its reward charges each tactic and therefore encourages short
  proof branches, but that short proof term is the result of training, formalization, tree search,
  and target-specific adaptation. The final Lean witness and discovery cost are different objects
  ([paper](https://www.nature.com/articles/s41586-025-09833-y)).

These examples justify three analytical projections, not three new budget accounts:

\[
L_R(w)=\left|\operatorname{encode}_R(w)\right|,
\qquad
C_{\mathrm{check}}(w,V)=\operatorname{work}(V(w)),
\qquad
C_{\mathrm{discover}}(\rho)=\operatorname{project}(\mathcal R_\rho).
\]

Here `R` is a frozen representation, `V` is a declared checker, and
\(\mathcal R_\rho\) is the normative
`ResourceLedger/0.1.0` for run `rho`. Operationally, `L_R` maps to coordinate communication,
`C_check` maps to post-freeze verification, and `C_discover` reports decoder execution, total search
work, critical path, and typed human provenance without adding unlike units. This is the engineering
form of the central separation: a tiny proof, program, prompt, or counterexample may be easy to check
after it is found while remaining expensive to discover.

## A system decomposition for AI mathematics

Let a task be

\[
\tau=(\mathcal C,\mathcal S,V,H,B),
\]

where `C` is the candidate language, `S` is the specification, `V` is a family of evaluators, `H` is
the declared human role, and `B` is the full resource budget. A research system should expose four
**runtime interfaces**. These are event-producing software boundaries, not the four persistent
research workstreams defined later. One workstream may implement or audit several interfaces, and one
interface may receive contributions from several workstreams.

### 1. Generator

The generator proposes a candidate object:

\[
c_t \sim G_\theta(\,\cdot\mid \mathcal S,A_t,f_t,r_t\,),
\]

where `A_t` is the current archive, `f_t` is evaluator feedback, and `r_t` is explicit randomness.
The object may be a prompt, proof step, auxiliary construction, program, conjecture, formal
statement, or experiment. A language model is one possible generator; templates, enumerators,
mutators, and humans are others.

### 2. Search and scheduler

The searcher decides what to expand, how much compute to spend, and what to retain:

\[
(q_t,b_t)=\pi(A_t,\mathcal R_t),\qquad
A_{t+1}=\operatorname{update}(A_t,c_t,V(c_t),\mathcal R_{t+1}).
\]

Here \(\mathcal R_t\) is a resource ledger, not just an iteration counter. Parallel sampling,
sequential
revision, beam/tree search, evolutionary islands, premise retrieval, curriculum generation, and
multi-agent task DAGs are search policies. The language model and the search policy must not be
reported as one opaque “reasoning” component.

### 3. Verifier and evaluator family

There is no universal verifier. The evaluator type determines the claim:

1. **Kernel checker:** exact relative to a formal statement and trusted computing base, as in Lean.
2. **Executable oracle:** deterministic tests, exhaustive finite enumeration, SAT/SMT checks, or
   independently recomputed mathematical predicates.
3. **Statistical evaluator:** repeated samples and confidence procedures for stochastic behavior.
4. **Learned verifier:** a reward or process model; useful for ranking, but fallible and subject to
   distribution shift or gaming.
5. **Human protocol:** experts or declared reader populations judge meaning, interestingness,
   readability, or correspondence that a mechanical checker does not establish.

Calling all five “verification” launders different uncertainties. OpenAI's PRM work, for example,
released step-level human labels and compared process with outcome supervision, but its reward model
remains learned rather than a proof kernel
([Let's Verify Step by Step](https://arxiv.org/abs/2305.20050),
[PRM800K artifacts](https://github.com/openai/prm800k)).

### 4. Human role

Humans may author the problem, choose the representation, formalize the statement, write seed code,
select attempts, suggest retries, repair ambiguity, judge semantic correspondence, assess novelty,
or write the exposition. Each intervention changes the experiment. It must be a typed event, not a
sentence in acknowledgements.

This decomposition explains many apparent differences between systems. AlphaGeometry uses a learned
generator for auxiliary constructions and a symbolic deduction engine; FunSearch uses an LLM
generator inside an evolutionary program search with executable scoring; AlphaProof learns a proof
policy inside a Lean environment; First Proof uses a long-horizon internal generator plus substantial
human selection and expert review. Their headline scores are not commensurable until these roles and
budgets are separated.

The runtime executes in two isolated stages, but both stages write to one six-account ledger:

| Isolated stage | Permitted flow | Six-account mapping |
| --- | --- | --- |
| discovery, before proposal freeze | Generator and Searcher may consume discovery-time evaluator feedback; all candidates, failures, cache events, and human interventions remain append-only | `C(p)` and `M_desc(c)` identify the coordinate and pinned system; decoder calls populate `T_dec`; proposal and discovery-evaluation work populate `W_search`; dependency depth populates `D_crit` |
| confirmation, after proposal freeze | Evaluator and Human receive the frozen candidate set through a fresh confirmation path; no result may be written back into discovery or used to replace a candidate | Fresh tests, samples, proof checks, and judgments populate `V_verify`; any fresh decoder execution is also recorded in `T_dec` with the nesting rule declared |

Stage isolation therefore does not create a second accounting system. The receipt stage-labels every
event, pins `C(p)` and `M_desc(c)` across the boundary, and states whether decoder work is nested in
`W_search` or `V_verify` so no call is counted twice. Typed human interventions remain provenance,
not a seventh resource account.

## `ResourceLedger/0.1.0`: six accounts and three cost views

This survey does not redefine Aleph's accounting contract. The normative
[`ResourceLedger/0.1.0`](../plans/model-relative-coordinate-landmarks.md#six-account-resource-ledger)
keeps six accounts together for comparison and forbids collapsing them without a published resource
conversion.

| Account | Symbol | What is charged | Boundary |
| --- | --- | --- | --- |
| coordinate communication | \(C(p)\) | Canonical prefix-free encoding of every target-varying field in the submitted coordinate | Not model size, search work, or full rendered-input cost |
| decoder execution | \(T_{\mathrm{dec}}(p)\) | Per-call and aggregate target-decoder work, tokens, memory, samples, latency, and failures | Not researcher discovery work or coordinate bits |
| search total work | \(W_{\mathrm{search}}\) | Every proposer, branch, mutation, discovery-time evaluator, retry, cache miss, and failed candidate | Not elapsed time under parallelism or post-freeze verification |
| critical path | \(D_{\mathrm{crit}}\) | Longest dependency chain in the search/compute DAG under a declared scheduler model | A derived graph statistic, never an additive cost |
| verification | \(V_{\mathrm{verify}}\) | Fresh samples, tests, proof checks, human judgments, calibration, and independent replay after proposal freeze | Not evidence already consumed by the searcher |
| model/interface description | \(M_{\mathrm{desc}}(c)\) | Canonical byte length and digest of the available checkpoint or service manifest, tokenizer, runtime, interface, decoder policy, and fixed scaffold | Not a computable estimate of Kolmogorov complexity; a hosted alias is incomplete |

`W_search` includes proposal and discovery-time evaluation. If aggregate decoder work is also rolled
into it, the receipt must declare that nesting so `T_dec` is not added twice. `V_verify` begins only
after the candidate set or theorem statement is frozen. Human formalization, literature review, and
engineering labor remain typed provenance and wall-clock fields: they matter, but are not a seventh
account and are not converted to FLOPs. This boundary keeps AlphaProof's manual IMO formalization and
Anthropic's source-proof interpretation visible without inventing a false common unit
([AlphaProof methods](https://www.nature.com/articles/s41586-025-09833-y),
[Anthropic artifact](https://github.com/anthropics/fermats-last-theorem)).

### Conditional coordinate cost

Under the parent plan's
[`Run context and outcome`](../plans/iclr-readable-coordinate-program.md#run-context-and-outcome)
contract, the conditional context \(\bar c\) is fixed and target-independent across the declared
panel. Every target-varying system message, attachment, retrieval result, tool payload,
demonstration, reference, or optimized random seed belongs to the typed coordinate \(p\) and is
charged by \(C(p)\). “Free
scaffold” means only that a shared scaffold is supplied as named conditional context; it does not mean
that the scaffold, model, or interface disappears from the scientific account. Their serialization
and digests remain in \(M_{\mathrm{desc}}(c)\).

A conditional-reference regime is valid only when its corpus and retriever were frozen independently
of every target. The coordinate must still carry the immutable object digest and complete retrieval
key. Otherwise the referenced bytes are part of \(p\). A target-specific lookup table is side
information, not compression.

### Full rendered-input cost

Every run also reports

\[
C^{\mathrm{full}}(p)=
\left|\operatorname{enc}_{\mathrm{pf}}
\bigl(E^{\mathrm{full}}(\operatorname{render}(p))\bigr)\right|,
\]

where the injective encoder covers the exact final token stream and any non-token payload bytes. The
gap between \(C(p)\) and \(C^{\mathrm{full}}(p)\) exposes the fixed-scaffold or side-information
subsidy. Cross-interface compression claims use full cost unless they explicitly name a conditional
comparison. Token count, UTF-8 bytes, and Unicode scalar count remain separate operational views.

### `Shortest Found` is a constructive upper bound

With deterministic decoding and an exact feasibility checker, a witnessed candidate of cost \(r\)
is a constructive upper bound on the corresponding threshold length in that fixed coordinate system.
With stochastic decoding or human-measured eligibility, a freshly confirmed candidate
constructively upper-bounds the corresponding threshold length only conditional on a declared
simultaneous-coverage event that entails candidate feasibility; the event's stated coverage controls
the confidence of that claim. Search-time point estimates remain provisional and later evidence may
change the confirmed view. In either regime, the found curve is algorithm-, budget-, and
random-state-conditioned. It is not a global optimum, an
unbiased estimator of the oracle curve, or evidence that an unvisited shorter coordinate does not
exist. Exhausting the declared finite domain or supplying a sound cheaper-prefix certificate can
close the remaining optimality gap once feasibility evidence is valid; neither substitutes for
candidate-feasibility evidence. FunSearch and AlphaEvolve are useful here because their population mechanics make
discovery work visible; their closed production scale does not change the accounting rule
([FunSearch repository](https://github.com/google-deepmind/funsearch),
[AlphaEvolve white paper](https://storage.googleapis.com/deepmind-media/DeepMind.com/Blog/alphaevolve-a-gemini-powered-coding-agent-for-designing-advanced-algorithms/AlphaEvolve.pdf)).

## Related-work taxonomy: the computer-science mainline

### Program synthesis and inductive synthesis

Syntax-guided synthesis separates a semantic correctness specification from a grammar defining the
candidate program space. This is the clean classical neighbor for Aleph's typed prompt language: a
search space is meaningful only after its legal syntax, semantics, and verifier are declared
([SyGuS](https://people.csail.mit.edu/rishabh/papers/sygusFMCAD13.pdf)). DreamCoder adds neural-guided
search and learned reusable abstractions: a wake--sleep loop alternates solving tasks with compressing
solutions into a library and improving the search policy
([DreamCoder](https://people.csail.mit.edu/asolar/papers/EllisWNSMHCST21.pdf)).

Aleph should borrow the separation of **grammar, semantics, search, and learned library**, not claim
that prompts are literally ordinary programs. A prompt's semantics are mediated by a stochastic,
versioned model, so its verifier requires repeated behavioral evidence rather than only symbolic
execution.

### Program search and prompt optimization

FunSearch expresses candidate discoveries as short Python functions, samples mutations with a
language model, evaluates them automatically, and retains high-scoring programs in an evolutionary
population. Its public repository is deliberately partial: it includes the evolutionary algorithm
and result/evaluation artifacts, but not the language models, untrusted-code sandbox, or distributed
production infrastructure
([paper](https://www.nature.com/articles/s41586-023-06924-6),
[repository disclosure](https://github.com/google-deepmind/funsearch)). AlphaEvolve generalizes the
object from a small function to larger code changes and supports multiple metrics, rich context, and
expensive evaluators; it still requires the user to supply a machine-gradeable evaluation function
([white paper](https://storage.googleapis.com/deepmind-media/DeepMind.com/Blog/alphaevolve-a-gemini-powered-coding-agent-for-designing-advanced-algorithms/AlphaEvolve.pdf)).

The transferable idea is not “ask an LLM for discoveries.” It is a closed loop with immutable
candidates, executable feedback, population diversity, and a budget ledger. Aleph's candidate object
is a prompt coordinate rather than a program, and its evaluator is multi-objective and partly
statistical/human. That makes evaluator separation more important, not less.

### Neural theorem proving and formal methods

Lean turns theorem proving into interaction with typed proof states and a small trusted kernel.
Mathlib supplies a large, versioned dependency library
([Lean 4 system paper](https://doi.org/10.1007/978-3-030-79876-5_37),
[Mathlib](https://github.com/leanprover-community/mathlib4)). HTPS combines a learned policy with
proof-state tree search and Lean checking
([HTPS](https://arxiv.org/abs/2205.11491)). LeanDojo makes the environment, benchmark, data,
retrieval model, and prover available; its `novel_premises` split specifically prevents near-duplicate
proofs from straddling train and test when they rely on the same premise
([LeanDojo paper](https://arxiv.org/abs/2306.15626),
[ReProver code and models](https://github.com/lean-dojo/ReProver)).

AlphaProof scales this pattern through autoformalization, AlphaZero-style reinforcement learning,
tree search, and problem-specific test-time reinforcement learning. The paper publishes benchmarks,
pseudocode, and selected proof displays, while the production learner and proof-generation harness
remain server-side and compute-intensive
([AlphaProof](https://www.nature.com/articles/s41586-025-09833-y)). AlphaGeometry uses a narrower but
publicly runnable neuro-symbolic design: a language model proposes auxiliary constructions and a
symbolic engine derives the proof. Code, a checkpoint, tests, and pinned dependencies are public,
but the release is an inference/reference implementation rather than a reproduction of training or
the internal optimized infrastructure; its README says internal parallelization was removed and notes
that changing language-model scores can change reported outcomes
([AlphaGeometry repository](https://github.com/google-deepmind/alphageometry)).

The formal-methods lesson is double-edged: kernel checking establishes validity relative to a formal
statement and trusted base, but only after the intended statement has been formalized correctly. Aleph
should use formal tools for its own finite
theorems, schema invariants, and certificates without pretending that arbitrary natural-language
targets have thereby been formalized.

### Test-time search and verifiers

Berkeley/DeepMind work on compute-optimal test-time scaling separates parallel verifier-guided search
from sequential revision and shows that the useful allocation depends on base-model competence and
problem difficulty. Its reported efficiency gains are conditional on the studied model, verifier,
benchmark, and difficulty estimator, not a universal inference law
([paper](https://arxiv.org/abs/2408.03314)). OpenAI's process-supervision work provides a complementary
lesson: intermediate-step labels can train a better selector on the studied MATH distribution, but a
process reward model is still a learned proxy and its grading code can reject correct answers or admit
incorrect ones
([paper](https://arxiv.org/abs/2305.20050),
[repository caveat and data](https://github.com/openai/prm800k)).

Proposal and confirmation are two **isolated execution stages**, each with a stage-specific control
cap. They are not the complete budget taxonomy, a replacement two-number budget, or a second
accounting model. The proposal cap constrains discovery events recorded in `T_dec`, `W_search`, and
`D_crit`; the confirmation cap constrains `V_verify` and any fresh decoder calls, with nesting
declared. Both map onto the same six-account `ResourceLedger/0.1.0`. Search may use cheap learned or
heuristic surrogates; paper claims must use the protected evaluator appropriate to the claim.
Adaptive compute is a method to test, not a license to give the favored method more calls.

### Benchmark contamination and data lineage

Mathematical benchmarks are unusually vulnerable to public solutions, near-duplicates, library
leakage, and model-family overfitting. GSM1k commissioned new problems matched to GSM8k and found
model-dependent performance gaps, illustrating why public benchmark accuracy alone cannot identify
reasoning or memorization
([GSM1k study](https://arxiv.org/abs/2405.00332)). LeanDojo found that similar theorems can have
identical proofs and introduced a novel-premise split; it also states that contamination is possible
for closed-model baselines trained after public proofs were online
([LeanDojo](https://arxiv.org/abs/2306.15626)).

Aleph's benchmark must therefore version target provenance, publication time, model cutoff
uncertainty, transformation families, and semantic-neighbor groups. A random row split is not enough.
Fresh or private confirmation items improve contamination resistance but reduce public replay, so the
public artifact should release the generator and delayed evaluation receipts after the protected gate
rather than silently mixing discovery and test.

### Reproducible systems and human checkability

Meta's 2026 AutoformBot paper treats textbook formalization as a distributed software-engineering
problem: an orchestrator creates a dependency DAG, workers operate in isolated worktrees, Lean builds
gate merges, and reviewers check faithfulness and quality. The public repository draws a narrower
boundary: its default `main` branch explicitly omits autonomous orchestration, while an opt-in
`execution` branch carries the execution overlay. The framework and resulting Atlas library are
public
([AutoformBot main](https://github.com/facebookresearch/autoform-bot/tree/afaf215ea63c2cc39fb1fb5492743129110ff6e0),
[execution overlay](https://github.com/facebookresearch/autoform-bot/tree/1592d6a28bd316fde0101e271ed787a989dc66be),
[Atlas](https://github.com/facebookresearch/atlas-lean),
[paper](https://arxiv.org/abs/2605.29955)). Those artifacts support bounded framework and library
reproduction. They do not reproduce the original Atlas-scale run end to end: provider model/API
behavior, the full production compute state, and complete original run traces are not a pinned public
package. LeanArchitect addresses another neglected artifact: a
human-readable blueprint linking informal mathematical structure to formal declarations
([LeanArchitect](https://doi.org/10.4230/LIPIcs.ITP.2026.25)).

The lesson for Aleph is not to imitate thousands of agents. It is to keep a checkable interface
between intent, machine state, and public artifacts. A candidate frontier needs the equivalent of a
proof blueprint: lineage, target relationship, evaluator receipts, failure reasons, and a human-readable
explanation that never overwrites the scientific record.

## Representative system matrix

The matrix applies the claim tags and `REP-*` packaging levels defined above. A level applies only to
the named artifact package, not automatically to every result reported by the same project. No row
below links an Aleph-local replay receipt, so every row has `localReplayStatus=not_recorded`.
`ungraded` means the row names a capability family or moving collection rather than one
cutoff-specific package; it must be frozen to a revision and declared run before receiving a
`REP-*` level.

| System | Candidate and decomposition | Verification and human boundary | Public evidence | Artifact package | Aleph lesson |
| --- | --- | --- | --- | --- | --- |
| Anthropic FLT (2026) | Multi-agent Lean formalization following an existing proof route; plan DAG and large-scale code generation | Lean kernel, theorem comparator, and `nanoda` 0.4.13 as a second independent Lean-kernel implementation with four disclosed patches: one progress-output patch and three definitional-equality speedups; humans establish source route and correspondence | Final artifact `M/O`; generation claims `S`; public Apache-2.0 repository | Final formal artifact `REP-2`; internal generation package `REP-0` | Separate formalization from discovery; disclose checker patches and publish generation work separately |
| OpenAI First Proof (2026) | Internal long-horizon model; several attempts, retry suggestions, cross-model review, human selection | Expert/community feedback is part of the reported process; one favored attempt was later reclassified incorrect | `O/S`; attempts and prompt examples released | `REP-1`; checkpoint, harness, full traces, and controlled evaluation unavailable | Preserve all attempts and reversals; never turn human-selected best-of-few into an autonomous score |
| OpenAI PRM800K (2023) | Generator samples MATH solutions; learned process reward model ranks steps/solutions | Human step labels train a fallible verifier; answer grader has documented false accept/reject risk | `E/O`; labels, splits, samples, evaluation code public | Dataset/evaluation `REP-3`; original frontier models not public | Treat learned verifiers as discovery surrogates and version their failure envelope |
| DeepMind FunSearch (2023) | LLM mutates a small function; evolutionary islands retain programs under executable score | Machine evaluator establishes the declared property/score; experts interpret novelty and mathematical meaning | `X/O/E`; results and partial implementation public | Public reference package `REP-3`; production discovery package `REP-0` | Search over executable representations when a suitable evaluator exists; log the entire population |
| DeepMind AlphaEvolve (2025) | LLM ensemble writes diffs; distributed evolutionary controller samples a program database; multi-metric evaluators score code | Executable evaluator plus application-specific expert review | `X/O/S`; white paper and result notebook | Named result notebook `REP-1`; production-system description `REP-0`; no public production-agent package | Evolve candidate-generating algorithms where direct object search is weak; do not borrow closed-system scale claims |
| DeepMind AlphaGeometry (2024) | Neural model proposes auxiliary constructions; symbolic DD+AR engine searches deductions | Symbolic proof engine checks the formal geometry language; humans formalize natural problems and judge scope | `M/X/O/E`; code, checkpoint, tests, and data public | Released inference/reference system `REP-3`; training and internal optimized infrastructure are not reproduced | A narrow formal domain can make generator proposals and symbolic checking complementary |
| DeepMind AlphaProof (2025/26) | Autoformalization, proof network, tree search, main RL, and problem-specific test-time RL in Lean | Paper reports Lean-kernel checks and named expert judging of official IMO solutions | `O/H/S`; paper, pseudocode, benchmarks, and selected proof displays | `REP-1`; neither generated proofs nor training/inference have a public one-command replay package | Record formalization provenance and verifier claims; server access is not reproducible training or proof replay |
| Meta HTPS (2022) | Neural policy and value guidance with hyper-tree proof search | Lean/Metamath check formal proofs | `M/E/O`; paper and a Lean plugin/model route were announced | Named paper/output package `REP-1`; the private infrastructure is not packaged | Tree-search state, policy, and checker receipts belong in separate interfaces |
| Meta AutoformBot/Atlas (2026) | Paper-reported orchestrator, dependency DAG, isolated workers, reviewers, and merge queue; public `main` omits autonomous orchestration and the execution overlay is opt-in | Lean build plus LLM/human-facing faithfulness and quality checks | Public framework/library `M/O`; reported scaled run `S` | Public bounded-component package `REP-3`; Atlas-scale generation package `REP-0` | Treat research as a replayable repository workflow; machine compilation does not replace semantic-faithfulness review |
| LeanDojo/ReProver (2023+) | Premise retriever + tactic generator + best-first interaction with Lean | Lean proof state and kernel; novel-premise benchmark reduces shortcut leakage | `M/E/O`; toolkit, data, models, benchmarks public | `ungraded`: this row aggregates moving toolkit, data, model, and benchmark artifacts rather than one pinned run package | Freeze one repository/model/data revision and bounded command before assigning a package level; report any non-replayable published number separately |
| Berkeley/DeepMind test-time scaling (2024/25) | Difficulty-conditioned allocation between parallel verifier search and sequential revision | Learned PRM/ORM on MATH, not a proof checker | `E`; paper-level method and results | Named paper/result package `REP-1`; any third-party reimplementation is a separately graded artifact | Adapt budget by difficulty only through a frozen policy and report the same total ledger for every method |
| Lean/Mathlib/comparator | Formal term, dependency graph, kernel, and independent comparison of challenge and solution statements | Tiny trusted kernel plus explicit axioms; humans still own informal correspondence | `M/O`; open code and libraries | `ungraded`: this is a capability family, not one named cutoff-specific certificate package | Grade each frozen theorem package separately; certificates need a declared trusted base, exact target identity, and no hidden weakening |

## What the systems actually say about mathematical work

### They combine mathematics and computation at different layers

The systems do not reveal one settled recipe. They occupy at least eight regimes:

1. **Known mathematics, new formal artifact:** Anthropic FLT and large textbook formalization turn
   existing arguments into machine-checkable libraries.
2. **Known theorem, new or shorter formal proof:** GPT-f searches proof objects without claiming a
   new theorem.
3. **Formal proof discovery:** HTPS, LeanDojo, AlphaProof, and OpenAI Ten Advances search or emit
   proof objects whose terminal states are exact relative to a frozen statement.
4. **Explicit counterexample:** the Jacobian and unit-distance cases expose compact witnesses whose
   exact or expert validation differs from reproducing their discovery.
5. **New informal theorem with later formalization:** Anthropic's zeta result separates research
   search, expert mathematical review, and a later Lean certificate.
6. **Finite or executable object discovery:** FunSearch, AlphaEvolve, and HAWK search programs or
   constructions whose outputs
   are scored by task-specific executable evaluators.
7. **Computational argument without a feasible full run:** reduced-round AES combines symbolic,
   asymptotic, and reduced-scale evidence without an executable full attack.
8. **Neuro-symbolic or open informal research:** AlphaGeometry uses a learned component where symbolic deduction
   needs creative branch proposals.
   First Proof and expert collaborations use language models, literature, tools, multiple attempts,
   and mathematicians; correctness and novelty remain socially and technically expensive to validate.

The resulting systems abstraction is not a larger end-to-end model. It is a **typed boundary between
creative proposal and claim-appropriate checking**, plus a search process that retains enough failed
work to understand how the result arose.

### They do not eliminate mathematical taste

Automatic evaluators have the most direct claim scope when the task already has a crisp predicate:
type-check this proof, count this finite construction, pass this exact test, or minimize this runtime.
They do not by themselves decide
which definitions matter, which conjecture is fruitful, whether a formalization captures the intended
idea, whether a proof explains anything, or whether a result is genuinely new. AlphaProof's own
discussion identifies theory building and mathematical taste as beyond its present competition-math
setting
([AlphaProof discussion](https://www.nature.com/articles/s41586-025-09833-y)).

That boundary supports the user's proposed roles: some agents should think about definitions and
counterexamples; some should run finite computation; some should construct and check proofs; a final
integration role should decide which objects change the CS paper or system. It does not support a
single undifferentiated swarm.

## Failure modes and claims Aleph may not borrow

### Formalization failures

- A proof of the wrong, weakened, vacuous, or differently scoped statement can pass a kernel.
- Hidden axioms, unsafe escape hatches, or changed definitions can make a nominally checked result
  irrelevant to the intended challenge.
- A mechanically valid proof can be unreadable or scientifically unilluminating.

Therefore Aleph must record theorem identity, permitted axioms, dependency hashes, trusted computing
base, and a separate semantic-correspondence review. Anthropic's comparator and independent-kernel
checks are useful patterns, not proof that every generated intermediate name has its intended meaning
([FLT artifact limitations](https://github.com/anthropics/fermats-last-theorem)).

### Search and evaluator failures

- Optimizing a proxy can discover evaluator bugs, weak test cases, reward-model blind spots, or
  representation tricks rather than mathematics.
- Best-of-`n` scores conceal the cost and selection rule if failed candidates disappear.
- A verifier trained on the same distribution as the generator can share its errors.
- An executable score may certify feasibility without certifying optimality, novelty, or explanatory
  value.
- A searcher can overfit a public target, checker, or benchmark while generalizing poorly.

Aleph may borrow the loop shape from FunSearch or AlphaEvolve, but not their result scale, evaluator
quality, or discovery claims. Its leakage/readability surrogates are not theorem checkers.

### Benchmark and data failures

- Public mathematical solutions may be present in pretraining data.
- Random theorem splits can leak nearly identical proof skeletons and premises.
- A recent benchmark reduces but does not automatically eliminate contamination or human selection
  bias.
- Private tests make gaming harder but also make independent replay incomplete.

No Aleph score may be called contamination-free merely because the target is absent from one searched
corpus. The artifact must distinguish known trace evidence, temporal evidence, controlled synthetic
assignment, and unknown pretraining exposure.

### Non-borrowable claims

Aleph must not infer any of the following from the cited systems:

1. that a short prompt is a proof, program, or sufficient explanation;
2. that a passed learned verifier is mechanically correct;
3. that a Lean-checked term proves the intended informal statement without a correspondence check;
4. that formalizing a known theorem is discovery of the theorem;
5. that a published output makes its generator reproducible;
6. that a closed internal model's result identifies the algorithm needed to reproduce it;
7. that more test-time compute monotonically helps every task or base model;
8. that a found coordinate is globally shortest;
9. that a low-copy coordinate proves the target came from model weights;
10. that competition-math performance establishes research-level theory formation;
11. that an executable construction is novel until literature and expert checks are complete;
12. that a company-reported open-problem advance is independent evidence of its own system design.

## Direct consequences for Aleph

### 1. Let `R2` qualify the search contribution and `R4` admit the paper

The intended submission is a computer-science paper; mathematics supplies definitions, finite exact
cases, counterexamples, bounds, and certificates. `R0` and `R1` must not pre-commit its primary
category. The normative `R2` gate answers the narrower question of whether an **algorithmic search
contribution** survives held-out, matched-resource comparison. A positive answer requires a declared
search method to improve a frozen discovery endpoint with confirmation; a negative answer remains a
publishable search result but cannot be promoted into an algorithm claim.

Only `R4` synthesizes all `R0`--`R3` evidence and admits the paper category. At that gate the
submission may be:

- **algorithmic**, only if the `R2` search gate passed;
- **measurement**, if the construct, protocol, uncertainty, and finite calibration are the durable
  result;
- **systems**, if the artifact kernel, replay boundary, and cross-runtime portability are the main
  advance; or
- a combination, only when each named component passes its own gate.

If an algorithm fails to improve on simple baselines, the paper must not be described as an algorithm
paper. It may still be a measurement, systems, or informative negative-results paper. In no case does
formal mathematics replace the executable CS artifact.

### 2. Make the four runtime interfaces enforceable

The research kernel should make these boundaries enforceable:

```text
Generator -> immutable CandidateEvent
Searcher  -> parent choice + BudgetReservation
Evaluator -> typed EvaluationReceipt
Human     -> typed InterventionEvent or JudgmentEvent
```

An operator must not write evaluator scores. A learned discovery surrogate must not access protected
confirmation data. A human edit or selection must create a new event. These runtime constraints align
with the repository's proposed `Operator`, `Evaluator`, `Archive`, `Searcher`, and `Certifier`
contracts.

### 3. Make the six-account ledger executable

Every result manifest should separately report `C(p)`, `T_dec(p)`, `W_search`, `D_crit`, `V_verify`,
and `M_desc(c)`, including their raw component counters and any nesting rule. It must also report
`C_full(p)`, the conditional/full comparison mode, and every target-varying field included in `p`.
Formalization source, transformations, human interventions, and unresolved correspondence risks are
provenance records rather than a seventh resource account. The public product may project a compact
view, but the scientific artifact preserves the complete ledger and event DAG.

### 4. Use a verifier hierarchy, not one `score`

Aleph needs typed evaluator identifiers and claim scopes:

- `exact_finite_oracle_v1` for exhaustively enumerable toy worlds;
- `kernel_check_v1` for formal theorem artifacts;
- `behavioral_confirmation_v1` for repeated model outcomes;
- versioned surface-copy and reversible-code probes;
- frozen human readability/link protocols;
- learned similarity or judge scores labeled **discovery only** unless separately calibrated.

No candidate is “verified” without naming which layer accepted which proposition.

### 5. Preserve complete search provenance

Population methods are useful only when the population survives. Aleph's append-only archive should
retain rejected prompts, invalid outputs, evaluator failures, timeouts, duplicate calls, selection
decisions, and all model/provider revisions. A final frontier is a derived view, not the database.

### 6. Treat formalization as an experimental stage

Formal methods can certify finite search theorems, frontier invariants, certificate validation, and
controlled source lemmas. Natural target meaning and readability remain separate human constructs.
When a theorem is formalized, Aleph should store the informal statement, formal statement, translation
author, reviewer, dependency pins, and comparison test.

### 7. Build contamination-aware benchmark families

Group splits by source work, semantic family, transformation lineage, public-reference identity, and
association assignment. Maintain a temporal/fresh stream for portability checks, but release delayed
receipts so external readers can audit the evaluation. Report unknown exposure as unknown.

### 8. Publish evidence cards with every headline result

Each result page should display the `A/V/R/P` vector, evaluator class, six accounts, human role, and
replay command. Kaggle or hosted runs add a runtime receipt; they do not upgrade a fixture or
self-reported result into scientific evidence.

### 9. Separate three kinds of “landmark”

- **Mathematical landmark:** a theorem, counterexample, or construction that changes understanding.
- **Computational landmark:** a search or verification method that materially changes reachable
  candidates under matched resources.
- **Aleph landmark:** a target whose exact or certified prompt-coordinate landscape reveals a stable
  phenomenon about model-relative description.

Famous problems are useful only when they instantiate a precise gate. Their fame is not an evaluation
metric.

## Three bounded reproduction work packages

These packages deliberately fit on modest public hardware. They are subordinate to the normative
`R0`--`R4` sequence below, not an alternative roadmap. Exact claims apply only to the declared finite
domain; none of the packages enumerates or optimizes human readability.

### Work package F1 — exact prompt-coordinate landscape

**Question.** Can the Aleph archive, frontier, and certificate machinery recover a known discrete
coordinate landscape without inventing points?

**Restricted domain.** Define a versioned toy decoder with a finite alphabet, canonical scaffold,
and maximum coordinate length `k` such that the complete legal universe is at most roughly `10^5`
candidates. Use target families with planted direct-copy, reversible-code, conditional-reference,
compositional, and unreachable cases. Eligibility is a versioned syntactic predicate; it is not a
claim about human readability.

**Methods.** Exhaustive enumeration establishes the restricted optimum and nondominated set. Compare
uniform random search, length-first enumeration, beam search, an evolutionary archive, and a declared
finite-domain search adapter under identical resource contracts.

**Receipts.** Emit every candidate, objective, failure, seed, parent, and all six resource accounts.
Report both `C(p)` and `C_full(p)`. Verify archive replay, resume equivalence, permutation invariance,
lower/upper certificate rules, and exporter non-mutation.

**Pass gate.** Exhaustive enumeration and an independent checker agree on the restricted optimum;
every heuristic reports discovery rate and regret against it; no method emits a candidate that was not
evaluated. The result makes no global claim about natural-language coordinates or readability.

**Scheduling.** F1 is the mandatory BCS-style finite-truth package in `R1` and a prerequisite for
finite-regret claims in `R2`.

### Work package F2 — evaluator-grounded program discovery

**Question.** How do executable representation, population search, and evaluator feedback change
discovery under a public proposal model and matched work?

**Restricted domain.** Choose a small cap-set, admissible-set, or graph-construction instance whose
restricted optimum is obtainable by enumeration or a separately checked solver. Pin the public
FunSearch evaluator and restrict candidate programs to a safe grammar or sandboxed expression
language. The search space and resource cap are finite.

**Methods.** Compare random grammar sampling, enumerative synthesis, mutation-only evolution, an open
model proposal kernel, and the same open model without population feedback. Match evaluator calls and
report invalid programs in the denominator. The public FunSearch repository supplies evaluators and a
single-threaded evolutionary reference while explicitly documenting the production pieces it omits
([repository](https://github.com/google-deepmind/funsearch)).

**Receipts.** Store program bytes, parents, model/config revision, execution-sandbox result, score,
the six resource accounts, and restricted-optimum gap. Independently recompute the mathematical
predicate for every promoted candidate.

**Pass gate.** The framework reaches or correctly fails to reach the restricted optimum and states,
with intervals over seeds, whether population feedback or model proposal changes time-to-optimum at
matched work. A failure to beat enumerative or random baselines is valid negative evidence.

**Scheduling.** F2 is an optional transfer study inside `R2`. Its delay or failure must not block the
BCS finite program, the discovery arena, the `R2` contribution decision, or the paper mainline.

### Work package F3 — proof search plus semantic-correspondence audit

**Question.** How much confidence comes from proof search, from the Lean kernel, and from humans
checking that the formal statement matches the intended problem?

**Restricted suite.** Build a pinned Lean 4/Mathlib micro-suite of 30--50 short theorems. Include
clean statements, deliberately weakened or vacuous translations, near-duplicate premises, and a
`novel_premises`-style held-out group. Freeze a finite tactic grammar and per-theorem step/call budget.
The formal search space is bounded; the human correspondence judgment is an empirical protocol, not
an enumerable readability optimum.

**Methods.** Compare deterministic tactic enumeration, retrieval plus best-first search using public
LeanDojo/ReProver components, and an optional open general model with the same Lean interaction
budget. A separate blinded review checks informal--formal correspondence; reviewers do not see which
method produced the proof.

**Receipts.** Record the informal statement, formal theorem hash, imported premises, every tactic and
goal state, kernel result, all six resource accounts, and correspondence judgment. Keep
`proved_formal_statement` and `faithful_to_informal_statement` as separate outcomes.

**Pass gate.** All accepted formal proofs replay under the pinned kernel; the evaluation catches the
planted weakened or vacuous statements; novel-premise performance and contamination risks are
reported separately; no kernel pass is described as semantic success without the correspondence
gate.

**Scheduling.** The checker and corrupted-statement fixtures support `R1`; the blinded semantic audit
and any model-assisted extension belong in `R3`.

## Normative `R0`--`R4` program

The sole normative round sequence is
[`MRC-LANDMARKS/0.1.0`](../plans/model-relative-coordinate-landmarks.md#r0--r4-research-rounds).
This survey only maps its evidence review and work packages onto those gates.

| Round | Normative purpose | This survey's contribution |
| --- | --- | --- |
| `R0` | Lay ground and establish evidence lineage | Claim-specific evidence cards, the generator/search/verifier/human decomposition, CS related-work taxonomy, and terminology aligned to `ResourceLedger/0.1.0` |
| `R1` | Establish exact finite truth | Mandatory F1 restricted-domain enumeration and certificates; F3 checker and corruption-fixture bootstrap |
| `R2` | Evaluate search algorithms and DiscoveryComplexity | Matched-work discovery arena and the decision whether an algorithmic search contribution passes its own gate; optional F2 transfer study |
| `R3` | Run protected AI and source experiments | Frozen real-model confirmation, human protocols, source interventions, runtime receipts, and the semantic-audit extension of F3 |
| `R4` | Refine, write, benchmark, and release | Paper-admission matrix, claim graph, negative results, public replay artifacts, evidence cards, and one long-term GitHub/Hugging Face/Kaggle/Cargo-facing entrypoint |

F2 is deliberately non-blocking. `R2` acceptance depends on the normative discovery arena and its
matched-work, held-out, independently confirmed evidence, not on reproducing a DeepMind task. The
rounds' deliverables and acceptance conditions remain owned by the landmark plan; this document must
not fork them.

## Four research workstreams for the proposed “mathematicians”

The user's role split is productive if every workstream has a typed output. These are ownership,
review, and promotion responsibilities across research rounds; they are not aliases for the
Generator, Searcher, Evaluator, and Human runtime interfaces. The mapping is many-to-many: for
example, the computational workstream may implement all four runtime interfaces, while the proof and
refiner workstreams audit evaluator semantics and human-intervention records without becoming runtime
components.

| Role | Owns | Must deliver | Must not do |
| --- | --- | --- | --- |
| Thinking mathematician | Definitions, examples, conjectures, abstraction choice, failure cases | Problem statements, assumption maps, counterexamples, proof sketches | Turn aesthetic conviction into an empirical claim |
| Computational mathematician | Enumeration, simulation, AI-guided and non-model search, proposal policies, verifier adapters, numerical bounds, counterexample generation | Executable programs, matched-budget algorithms and ablations, independent checks, model/data cards, resource curves, raw results | Hide failed runs, conflate generator and search quality, or report floating-point evidence as a theorem |
| Formal mathematician | Theorem statements, proof terms, trusted-base review, certificate checking | Pinned formal artifacts and correspondence notes | Equate kernel acceptance with intended informal meaning |
| Refiner/integrator | Claim graph, paper framing, product projection, next-round decision | Evidence table, removals, accepted claims, issue-ready plan | Smooth over conflicts between artifacts for narrative convenience |

AI/search is an internal branch of the computational role, not a fifth approval role. Parallel
subagents may fill branches within each of the four workstreams, but the integration gate is serial:
definitions freeze before comparison, discovery freezes before confirmation, and confirmation
freezes before narrative. A runtime event never gains approval authority merely from the workstream
that produced it.

## Decision for the project, benchmark, Kaggle, and the paper

The durable order is:

1. **Aleph project:** a research instrument for model-relative prompt coordinates, with a mathematical
   and computational landmark program behind it.
2. **Aleph benchmark:** the public, stable protocol and artifact set for measuring search, frontier,
   readability, leakage channels, and confirmation under fixed conditions.
3. **Paper:** a computer-science contribution whose primary category---algorithm, measurement,
   systems, or a justified combination---is admitted by the `R4` synthesis gate after `R2` has made
   the narrower search-contribution decision. Finite ground truth and mathematical results strengthen
   the claim boundary and may become separate proof notes.
4. **Kaggle:** a hosted reproducibility and portability harness that can demonstrate one pinned
   artifact/model run in a constrained external environment after output readback, digest validation,
   and offline replay. It is not the source of the scientific object, a proof of general portability,
   or evidence of global optimality.
5. **Long-horizon possibility:** an artifact-first laboratory in which prompts, programs, conjectures,
   proofs, counterexamples, and human explanations can be proposed by different agents and accepted
   only by claim-appropriate verifiers.

This order preserves Aleph's original compression-path question while giving the mathematics enough
depth to be real and the computing enough structure to be reproducible.

## Primary-source index

This local list is a selective navigation aid; evidentiary claims above cite their source locally.
The repository-wide [`docs/source-ledger.md`](../source-ledger.md) is a versioned **compact index**,
not a complete bibliography, a permanence guarantee for its URLs, or evidence that every linked
artifact was locally replayed.

### Synthesis and program discovery

- [Syntax-Guided Synthesis](https://people.csail.mit.edu/rishabh/papers/sygusFMCAD13.pdf)
- [DreamCoder](https://people.csail.mit.edu/asolar/papers/EllisWNSMHCST21.pdf)
- [FunSearch paper](https://www.nature.com/articles/s41586-023-06924-6) and
  [official repository](https://github.com/google-deepmind/funsearch)
- [AlphaEvolve white paper](https://storage.googleapis.com/deepmind-media/DeepMind.com/Blog/alphaevolve-a-gemini-powered-coding-agent-for-designing-advanced-algorithms/AlphaEvolve.pdf)

### Theorem proving and formalization

- [Lean 4](https://doi.org/10.1007/978-3-030-79876-5_37) and
  [Mathlib](https://github.com/leanprover-community/mathlib4)
- [HTPS](https://arxiv.org/abs/2205.11491)
- [LeanDojo/ReProver paper](https://arxiv.org/abs/2306.15626) and
  [official implementation](https://github.com/lean-dojo/ReProver)
- [AlphaGeometry](https://github.com/google-deepmind/alphageometry)
- [AlphaProof](https://www.nature.com/articles/s41586-025-09833-y)
- [AutoformBot main](https://github.com/facebookresearch/autoform-bot/tree/afaf215ea63c2cc39fb1fb5492743129110ff6e0),
  [execution overlay](https://github.com/facebookresearch/autoform-bot/tree/1592d6a28bd316fde0101e271ed787a989dc66be), and
  [Atlas](https://github.com/facebookresearch/atlas-lean)
- [LeanArchitect](https://doi.org/10.4230/LIPIcs.ITP.2026.25)

### Test-time verification and evaluation integrity

- [Let's Verify Step by Step](https://arxiv.org/abs/2305.20050) and
  [PRM800K](https://github.com/openai/prm800k)
- [Scaling LLM Test-Time Compute Optimally](https://arxiv.org/abs/2408.03314)
- [GSM1k contamination study](https://arxiv.org/abs/2405.00332)

### 2026 system evidence cards

- [OpenAI First Proof](https://openai.com/index/first-proof-submissions/)
- [OpenAI AI as a Scientific Collaborator](https://cdn.openai.com/pdf/f4b4a5da-b2de-418d-9fcd-6b293e9dc157/oai_ai-as-a-scientific-collaborator_jan-2026.pdf)
- [Anthropic FLT technical account](https://www.anthropic.com/research/formalizing-fermats-last-theorem)
  and [public proof artifact](https://github.com/anthropics/fermats-last-theorem)
