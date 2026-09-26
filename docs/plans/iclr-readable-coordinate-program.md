# ICLR Research Program: Aleph Coordinates and Source Attribution

- Status: proposed research program; no empirical claim is validated yet
- Started: 2026-09-26
- Last reviewed: 2026-09-27
- Owner role: research lead and engineering lead
- Decision scope: the scientific mainline for Aleph after the current prototype

## Executive decision

Aleph should keep its original scientific object: for a target text and fixed model interface, map
the shortest-known **prompt coordinates** that reliably elicit the target and expose the whole
compression path from explicit reconstruction toward those coordinates. The repository later made
human-readable and raw-token search explicit alternative modes rather than declaring either one the
only valid object. This research program promotes the human-readable frontier to the primary
empirical slice while retaining the raw frontier and the strange garden-path coordinates that first
made Aleph interesting. The appearance of closely aligned prompting-complexity theory does not
justify changing the question merely to look different.

It does change the contribution bar. A bare shortest-prompt definition is no longer enough. Aleph has
to turn the object into an empirical science and a working system:

1. measure readability through people independently of target-model scores rather than equating it
   with token likelihood;
2. build a real budgeted search algorithm, an observed nondominated archive, and statistically valid
   per-candidate confirmation decisions;
3. measure fidelity, stability, readability, and information channel without collapsing them into a
   hidden scalar;
4. explain whether a short readable prompt works by copying, public reference, learned association,
   or other model-mediated structure;
5. establish reproducible empirical laws across targets, exposure, models, and search budgets.

The paper has one primary object and two linked evidence programs:

> **Accessibility:** What is the shortest known prompt coordinate that reliably elicits target
> \(y\) from a fixed model, and what is lost when we require that coordinate to remain human-readable?

> **Interpretation:** When that coordinate works, what information channel makes it work, and what
> can be identified only after intervention?

The discrete model-relative compression path is the primary object; its readable frontier is the
primary empirical claim and its raw frontier is an essential comparator. Counterfactual source
attribution is the interpretive and causal layer that prevents “short” from being mistaken for “the
model supplied the information.” None replaces the others.

Working title:

> **When Is a Prompt a Coordinate? Readable Prompt Complexity and Counterfactual Source Attribution**

This plan is deliberately a claim boundary, not a claim of success. Either evidence program may be
narrowed if its decisive pilot fails. In particular, Pilot B may demote source attribution without
changing the primary compression-path object; prior-art pressure alone is not a reason to abandon
Aleph's original direction.

## Research role, north star, and operating principles

The owner role is not “paper writer” or “demo maintainer.” It is a combined research and engineering
lead accountable for turning a compelling question into a falsifiable construct, a working method,
and replayable public evidence. The north star is:

> Given a target and a pinned model interface, produce an auditable archive of actual prompt
> coordinates from Explicit Reconstruction toward the shortest confirmed readable and raw
> coordinates found, with enough evidence to distinguish accessibility, copying, reference, and
> controlled learned association.

Decisions follow these principles, in order:

1. **Preserve the question; raise the evidence bar.** Prior art changes novelty claims and baselines,
   not the repository's history or primary object.
2. **Define before optimizing.** Freeze run context, cost, distortion, readability, provenance, and
   confirmation semantics before tuning search against them.
3. **Observed artifacts before curves.** Store real candidates, outputs, failures, lineage, and
   receipts; derive product projections without fabricating intermediate points.
4. **Adapt on discovery, confirm on protected evidence.** Search traces are provisional until fresh
   fixed-checkpoint samples and protocol-specific human judgments pass simultaneous bounds.
5. **Intervene before attributing cause.** Natural-model source stories remain observational;
   counterfactual source claims require randomized training or checkpoint interventions.
6. **Keep channels separate.** Surface copy, encoded copy, public reference, learned association,
   semantic similarity, and trace contamination are not synonyms and do not belong in one opaque
   leakage score.
7. **Pay for every advantage.** Record proposer access, target exposure, logits/gradients, tokens,
   model calls, FLOPs estimates, wall time, human effort, and failed evaluations.
8. **Make negative results durable.** Failed candidates, failed pilots, inaccessible targets, and
   method regressions stay in the artifact record and constrain later claims.
9. **Prefer portable contracts to one runtime.** Local open checkpoints establish inspectable
   evidence; hosted and Kaggle runs test portability, never substitute service drift for a pinned
   scientific condition.
10. **Land one acceptance gate at a time.** Research decisions, measurement fixes, artifact kernel,
    search, human protocol, and causal source work remain reviewable rather than arriving as one
    untestable rewrite.

## Original Aleph lineage

The repository shows an independent public line before Prompting Complexity appeared, but it does
**not** predate the closest empirical compression work. In particular, Adversarial Compression Ratio
and MiniPrompt were published in 2024. Aleph's history protects the integrity of its own decisions; it
does not establish priority for target-first shortest-prompt search or the model-as-decompressor view:

- [commit `b5303e8`](https://github.com/p-to-q/aleph/commit/b5303e8c03ce8f7d802421d80b5c04153fe83887),
  published 2026-05-16 UTC, defined target-first model-relative description length, the compression
  path, the explicit-reconstruction baseline, and the question “is the prompt compressing or copying?”;
- [commit `0f8b5a6`](https://github.com/p-to-q/aleph/commit/0f8b5a61b327e38dffb1e5ea8e94136d6030a94d),
  published later that day, added a running local Qwen/MLX reverse-search prototype and readable
  coordinates such as work, author, passage, and form references;
- [commit `2650844`](https://github.com/p-to-q/aleph/commit/2650844f5106ceacb26cae9382b3187247704d87),
  published 2026-05-19 UTC, made human-readable versus raw token coordinates an explicit research
  choice;
- [commit `0faf286`](https://github.com/p-to-q/aleph/commit/0faf286b34316a4a7cac2de2ae98215f9c180c55),
  published 2026-05-20 UTC, recorded short, strange, garden-path-like coordinates as a distinct
  phenomenon rather than treating every short string as the same kind of prompt.

[Prompting Complexity](https://arxiv.org/abs/2607.06145) was submitted to arXiv on 2026-07-07. The
dates show only that Aleph publicly articulated these ideas before the cited arXiv submission and
protect the repository's conceptual history; without stronger archival evidence they do not establish
independent invention or priority over
[ACR/MiniPrompt](https://arxiv.org/abs/2404.15146), work that may have existed privately, or the broad
compression interpretation, and they do not remove the obligation to cite and exceed both published
lines.

Aleph's settled original object was already richer than one scalar minimum: a discrete model-relative
compression path, honest shortest-found and explicit-reconstruction endpoints, stability, leakage,
target-token evidence, and a user-facing research instrument. Human-readable versus raw search first
appeared as an open design choice, with a maintainer preference for readable-by-default rather than a
claim that raw coordinates were irrelevant. The ICLR route should formalize and validate that full
object rather than rewriting its history around either mode.

The early MLX artifact in [commit `523fc8f`](https://github.com/p-to-q/aleph/commit/523fc8f28dd7ab17fb07062c76c3181156006e97)
contains useful hypothesis-generating contrasts: a 21-token Gettysburg prompt reached reported
embedding similarity 0.9981, a 19-token Dickens prompt 0.94, and a 14-token named Hamlet coordinate
0.7422, while an 8-token Borges reference for a newly written Borges-themed paragraph reached only
0.7214. These are not paper results: the search was tiny, the similarity metric was permissive, and
the `monotone()` bug fabricated repeated length coordinates. They motivate a matched experiment on
canonical passage, paraphrase, same-style novel composition, and high-entropy control; they must not
be cited as validated performance.

## Why the current framing is not submission-ready

An ICLR-level submission needs an original question, a well-defined estimand, a method that runs,
and evidence capable of falsifying the central claim. Aleph currently has a strong metaphor and a
promising product interface, but it does not yet have that contribution stack.

The immediate reject reasons are:

1. **The empirical core already has a direct predecessor.**
   [Rethinking LLM Memorization through the Lens of Adversarial Compression](https://arxiv.org/abs/2404.15146)
   defines
   \(\operatorname{ACR}(M,y)=|y|/\min\{|x|:M(x)=y\}\), treats the model as a decompressor, and uses
   GCG plus length search in MiniPrompt to find short inputs for arbitrary target strings. Famous
   quotations, post-cutoff/random controls, Wikipedia text, unlearning, and paraphrase experiments
   mean Aleph cannot claim novelty for target-first reverse search, shortest prompt, token-ratio
   compression, or using that compression as evidence of memorization.
2. **The bare definition also has a direct theoretical neighbor.** [Prompting Complexity](https://arxiv.org/abs/2607.06145)
   independently formalizes the shortest plausible prompt producing a target under a fixed language
   model, including exact, soft, and behavioral versions and the model-relative
   Kolmogorov-complexity analogy. Aleph can retain the question, but must contribute the operational
   construct, algorithm, experiments, and interpretation that the definition leaves open.
3. **Stronger adjacent theory.** [Fundamental Limits of Prompt Compression](https://arxiv.org/abs/2407.15504)
   formalizes black-box hard-prompt compression through rate-distortion and derives an optimization
   procedure. Aleph's current `L*` language is not yet a theorem or a stronger construction.
4. **Unidentified source.** A successful prompt-output pair does not reveal whether the prompt
   encoded the answer or activated knowledge in the weights. Recent
   [context-attribution work](https://arxiv.org/abs/2607.23804) reports that existing attribution
   methods fail to separate in-context from in-weight contributions when those sources overlap.
5. **No working research algorithm.** The current demo proposes a handful of candidates and reports
   a display frontier. It does not implement a budget-matched, provenance-aware optimizer with
   raw traces and independent validation.
6. **No causal ground truth for source.** Natural targets are the primary domain for the accessibility
   claim, but famous texts cannot establish whether a model recovered a target from the prompt,
   pretraining, or both. Synthetic associations complement the natural study by identifying a
   randomized mapping-specific `AssociationEffect`; they do not reveal a universal latent source and
   do not replace natural targets.
7. **Measurement contracts disagree.** Length, leakage, stability, and frontier semantics differ
   across the local engine, API, core package, and web surface.

The practical implication is a strengthening of the original line:

- the full model-relative compression path remains the primary object, with readable and raw branches;
- `Shortest Found` remains an algorithm-conditioned upper bound;
- a readable-coordinate frontier replaces an unsupported one-dimensional smooth curve;
- surface-copy leakage becomes one channel in a richer provenance profile;
- paired counterfactual model worlds explain a controlled subset of why coordinates work;
- the search engine is evaluated both as an estimator of readable prompting complexity and as a
  method for finding association-selective coordinates.

## Novelty boundary

| Neighbor | What it already establishes | What Aleph must add |
| --- | --- | --- |
| [Adversarial Compression Ratio / MiniPrompt](https://arxiv.org/abs/2404.15146) and [code `bf3ba2e`](https://github.com/locuslab/acr-memorization/tree/bf3ba2e7bf224482928fba42cd79c295796c0237) | Target-first shortest-input compression, the model-as-decompressor interpretation, GCG plus prompt-length search, and memorization experiments on famous, random/post-cutoff, Wikipedia, paraphrase, and unlearning targets | Independently measured readable-versus-raw frontiers, stochastic reliability and fresh confirmation, full discrete compression paths and breakpoint analysis, portable receipts, finite provenance channels, and causal paired-training source estimands |
| [Prompting Complexity](https://arxiv.org/abs/2607.06145) | Fixed-model shortest plausible prompts, soft/behavioral variants, counting bounds, and a weak model-dependent coding theorem | A human-scored readability/link contract, working estimators, real search, empirical laws, and provenance-aware interpretation |
| [The Value of a Prompt](https://arxiv.org/abs/2608.16438) | LLM-relative value of a given prompt through target log-likelihood gain and, for thinking models, a randomized computation-aware description-length construction | Search for shortest typed coordinates and their observed frontier, independently measured human readability, the readable/raw gap, public replay artifacts, and controlled source intervention; probability/computation-aware prompt value is not claimed as new |
| [Fundamental Limits of Prompt Compression](https://arxiv.org/abs/2407.15504) | Rate-distortion limits for compressing an existing input prompt | Target-first reverse search and controlled association-selective contrasts under paired-checkpoint interventions |
| [LLMLingua](https://aclanthology.org/2023.emnlp-main.825/), [LLMLingua-2](https://aclanthology.org/2024.findings-acl.57/), and [discrete RL compression](https://arxiv.org/abs/2308.08758) | Budgeted deletion or rewriting of an existing long prompt while preserving downstream task utility | Target-first synthesis when no source prompt is privileged, plus a readability/provenance frontier rather than compression ratio alone |
| [ARCA](https://arxiv.org/abs/2303.04381) and [GCG](https://arxiv.org/abs/2307.15043) | Discrete fixed-output or target-string optimization | Length/source constraints, paired-model evaluation, and provenance-aware search |
| [Prompts Have Evil Twins](https://aclanthology.org/2024.emnlp-main.4/) and [Evil twins are not that evil](https://aclanthology.org/2025.blackboxnlp-1.3/) | Raw prompts that approximate a natural prompt's output distribution and transfer across models; fluency constraints and length-penalized compression as a direction; and post-hoc expert identification of influential tokens in opaque autoprompts across six models | Preregistered, population-specific measurement of both surface intelligibility and target linkage, exact-target readable/raw paths, and confirmation under a pinned run context; neither functionally equivalent raw prompts nor human analysis of their tokens is new |
| [Language Model Inversion / logit2prompt](https://arxiv.org/abs/2311.13647), [output2prompt](https://aclanthology.org/2024.emnlp-main.819/), and [Reverse Prompt Engineering](https://aclanthology.org/2025.emnlp-main.1333/) | Recovering an original or semantically similar hidden prompt from logits or multiple observed outputs, including black-box transfer | Finding any shorter coordinate for a declared target rather than recovering its historical prompt; inversion methods remain explicit neighboring baselines on compatible synthetic tasks |
| [GEPA](https://arxiv.org/abs/2507.19457) and [TextGrad](https://arxiv.org/abs/2406.07496) | Strong general prompt optimization procedures | A source-attribution objective, adversarial leakage tests, and target-specific reverse-search evidence |
| [FluentPrompt](https://aclanthology.org/2023.findings-emnlp.733/), [MePO](https://aclanthology.org/2026.eacl-long.38/), and [BayesPrompt](https://arxiv.org/abs/2608.17866) | Fluency-constrained or merit-guided optimization and LM-prior notions of natural prompts | Independent human measurement of surface intelligibility and target-link legibility; LM probability or an LLM judge remains only a discovery surrogate |
| [What Makes a Good Natural Language Prompt?](https://aclanthology.org/2025.acl-long.292/) | A broad taxonomy of prompt properties and an attempted judge calibration | A narrow, behaviorally observable construct with a declared reader population, reference-game outcome, uncertainty, and frozen certification use |
| [RG-PT](https://papers.neurips.cc/paper_files/paper/2025/hash/38853020527b0f84187870114ff7a686-Abstract-Conference.html), Pareto Testing, and Learn-Then-Test | Selection of short/reliable members from a finite prompt-template family with formal false-discovery control and a reliability graph | Open variable-length discovery followed by a frozen finite selection problem; Aleph must reuse or compare valid multiple-testing selection rather than claim reliable shortest-prompt selection as new |
| [Probing for Knowledge Attribution](https://arxiv.org/abs/2602.22787) | Hidden-state probes for context-versus-weight knowledge attribution | Black-box-compatible interventions, known randomized assignment, and reverse-search integration |
| [How Context Attribution Handles What the Model Already Knows](https://arxiv.org/abs/2607.23804) | Controlled evidence that context attribution does not separate overlapping in-context and in-weight knowledge | Target-conditioned reverse search plus a working intervention-based source-separation method |
| [Counterfactual Memorization](https://arxiv.org/abs/2112.12938) and [Quantifying Memorization Across Neural Language Models](https://arxiv.org/abs/2202.07646) | Training-example influence and extractable memorization | Prompt-conditioned source effects and optimization for compact, model-mediated elicitation |
| [Causal Estimation of Memorisation Profiles](https://aclanthology.org/2024.acl-long.834/) | Causal training-instance memorization effects and difference-in-differences estimation | A randomized prompt-by-association factorial under permutation interference plus source-aware search; Aleph does not claim to invent causal or DiD memorization estimation |
| [ALPACA AGAINST VICUNA](https://aclanthology.org/2025.naacl-long.421/) | Black-box LLM-agent optimization of low-overlap instructions that elicit memorized training text | Minimum-length readable/raw archives, independent confirmation, and intervention-grounded source contrasts rather than another extraction attack |
| [Probabilistic extraction](https://aclanthology.org/2025.naacl-long.469/) and [dynamic soft prompting](https://aclanthology.org/2024.emnlp-main.546/) | Sampling-aware extraction probability and adaptive soft-prompt elicitation of memorized text | A discrete human-legible coordinate construct, matched raw comparator, and complete cost--reliability frontier |
| [The Secret Sharer](https://arxiv.org/abs/1802.08232) and [Copyright Traps](https://proceedings.mlr.press/v235/meeus24a.html) | Random canaries, exposure, extraction, and randomized causal memorization tests | Association-selective prompt discovery rather than another canary detector |
| [Memorization Sinks](https://proceedings.mlr.press/v267/ghosal25a.html) | Sequence identifiers that activate isolated memorized content | A matched counterfactual estimand and search frontier for compact selectors |
| [GPTs Don't Keep Secrets](https://aclanthology.org/2023.trustnlp-1.21/) and [DBS](https://proceedings.mlr.press/v162/shen22e.html) | Recovery or inversion of planted backdoor triggers | Human-readable coordinate discovery, explicit trigger-recovery baselines, and transfer across independently trained replicas |
| [RAVEN](https://aclanthology.org/2023.tacl-1.38/) and [PlagBench](https://aclanthology.org/2025.naacl-long.384/) | Copying, paraphrase, and plagiarism measurement | A calibrated prompt-side adversary suite tied to controlled parameter exposure |
| [Datamodels](https://proceedings.mlr.press/v162/ilyas22a.html) and [TRAK](https://proceedings.mlr.press/v202/park23c.html) | Prediction of model behavior under training-set counterfactuals and scalable training-data attribution | Target-prompt interaction effects under randomized association interventions; these remain white-box controlled baselines, not black-box ground truth |
| [DATE-LM](https://arxiv.org/abs/2507.09424) and [DataDignity/FakeWiki](https://arxiv.org/abs/2605.05687) | Broad LLM data-attribution benchmarking and controlled fictional-document provenance with paraphrase, retro-source, anti-document, and transformed queries | Coordinate search tied to association-selective interventions; no claim of first attribution benchmark or first controlled provenance corpus |
| [Data Portraits](https://arxiv.org/abs/2303.03919) and [Data Provenance Initiative](https://arxiv.org/abs/2310.16787) | Corpus membership sketches, dataset lineage, license, and source audits | Behavioral accessibility and influence remain distinct from corpus trace; Aleph imports their evidence rather than inferring it from a prompt |
| [Functional Memorization in Code LMs](https://arxiv.org/abs/2606.12764) | Exposed/reference checkpoint contrasts and execution-equivalent memorization missed by text similarity | Execution-based recoverability channels and the readable/raw coordinate path; no claim that semantic-copy detection itself is new |
| [TrojanStego](https://aclanthology.org/2025.emnlp-main.1386/), [covert-channel capacity](https://aclanthology.org/2024.findings-emnlp.971/), and [OWL](https://aclanthology.org/2025.emnlp-main.1314/) | Natural-text steganography, covert channels, and cross-lingual recall | A versioned, explicitly incomplete prompt-recoverability suite with per-channel evidence and search-trace integrity |
| [Source-aware training](https://arxiv.org/abs/2404.01019) | Models explicitly trained to associate knowledge with source identifiers and cite them | Attribution without assuming the evaluated model was trained to self-report provenance |

The paper is not novel merely because it uses a new weighted leakage score, renames prompting
complexity, or replaces MiniPrompt's optimizer. Its defensible contribution stack is:

1. a human protocol measured independently of the target model's scores for **readable prompt
   coordinates**, including an explicit readable-versus-raw frontier;
2. a working reverse-search algorithm that estimates the shortest-readable frontier under finite
   budget with independent confirmation;
3. empirical laws of target accessibility across text type, model, tokenizer, exposure, and search
   compute;
4. an explicit source-identifiability boundary and controlled intervention protocol;
5. a calibrated provenance profile that distinguishes copying, reversible encoding, public
   reference, learned association, and search contamination;
6. evidence across targets, exposure levels, seeds, and model scales.

The closest collision is direct, not cosmetic. ACR/MiniPrompt already operationalizes target-first
shortest-input search and the model-as-decompressor account; Prompting Complexity independently asks
for the shortest plausible prompt and supplies stronger theory. Aleph must treat MiniPrompt as the
minimum white-box empirical baseline, cite Prompting Complexity as the formal neighbor, and compete on
what neither jointly establishes: a reader-population-specific human protocol independent of target
model scores, readable and raw archives over a full observed path, stochastic/fresh confirmation,
budgeted replayable estimation, calibrated information channels, and paired causal source
interventions. The paper must not claim novelty for the bare minimization problem, target-first search,
compression ratio, or the decompressor metaphor. ALPACA AGAINST VICUNA also means the project cannot
claim that optimizing low-overlap black-box prompts to elicit memorized text is new. Aleph's bar is the
coordinate measurement contract, human/raw separation, reliable compression-path science, and
controlled source interpretation.

## Research questions and falsifiable hypotheses

### RQ1 — readable accessibility

For a fixed model and target, what is the shortest prompt that remains readable to people and reliably
elicits the target?

**H1:** Readable-coordinate length varies systematically with measured target familiarity and frozen
exposure proxies in natural models, and cannot be explained by target length, model likelihood, or
surface overlap alone. Claims about causal exposure are restricted to controlled training worlds.

### RQ2 — frontier estimation

Can a practical algorithm estimate the readable length-fidelity-stability frontier better than
existing fixed-output and general prompt optimizers at matched compute?

**H2:** A readability-aware reverse-search algorithm improves confirmed best-found length or
discovery rate on held-out targets while preserving independent human readability and confirmation
success.

### RQ3 — identifiability

Can prompt-borne and parameter-borne contribution be identified from a single fixed model's
prompt-output behavior?

**H3:** No. Without interventions or additional assumptions, two latent source accounts can induce
the same observable conditional distribution while assigning opposite source explanations.

This is a theorem target. It must be established before any empirical source-estimator result is
interpreted as identified, even though the plan specifies both objects before implementation.

### RQ4 — controlled source separation

Can paired model interventions recover a known randomized association effect for target bindings,
and can that signal improve reverse search?

**H4:** Under randomized whole-permutation assignment, a counterfactual paired-model estimator has a
larger preregistered association-assignment effect for coordinate prompts than for explicit-copy,
partial-copy, and unrelated controls on held-out target associations. At matched compute, the
source-aware variant has a larger preregistered confirmed-discovery rate than a source-unaware
searcher. Edge-specific interpretation remains conditional on the stated exposure-sufficiency and
interference assumptions.

The exact success threshold must be preregistered after a calibration split and before the held-out
test is inspected.

### RQ5 — external validity

Do the readable frontier and controlled source effects predict anything useful on naturally occurring
texts and behaviors?

**H5:** Accessibility rankings and adversarial failure modes satisfy a preregistered rank-correlation
or prediction criterion on natural targets, while natural-target source results remain explicitly
observational and conditional on measured exposure proxies rather than treated as causal ground truth.

## Parallel subresearch workstreams

The program stays one project, but the missing evidence is investigated in parallel and reconciled
before implementation choices become contracts.

| Workstream | Question | Durable output | Gate into implementation |
| --- | --- | --- | --- |
| formal foundations | What exactly is measured, and what follows from algorithmic information, rate-distortion, MDL, and finite Pareto theory? | definitions, propositions, counterexamples, proof notes | symbols have one meaning; borrowed theorems and original claims are separated |
| human construct validity | Can people independently judge surface intelligibility and target-link legibility across languages and coordinate types? | rubric, decoy-generation protocol, rater study, reliability report | calibrated tasks and uncertainty rule pass a pilot without target-model assistance |
| reverse-search algorithms | Which white-box, black-box, evolutionary, textual-gradient, and compression methods actually search the relevant space? | pinned implementation audit, unified adapters, budget ledger, ablation matrix | every baseline runs through the same evaluator/archive boundary |
| provenance and source | Can copying, reversible encoding, public reference, learned association, and trace contamination be distinguished without pretending to read hidden causes? | versioned adversary suite, source scope lemma, paired intervention design | controls recover expected signatures before open search begins |
| benchmark science | Which target strata, splits, uncertainty procedures, and contamination checks make the empirical claims falsifiable? | target manifest, preregistration, power simulation, analysis code | pilot endpoints and stop rules are frozen before final evidence |
| reproducibility and runtime | Which artifact and adapter contracts survive local open models, hosted APIs, Kaggle, and public Hugging Face release? | schemas, conformance fixtures, environment locks, replay receipts, failure taxonomy | offline replay and two independent runtimes produce contract-equivalent artifacts |

No workstream may silently redefine another. In particular, an optimizer's language-model score
cannot certify the human construct, a public leaderboard cannot certify causal source, and a hosted
success screenshot cannot replace a replayable run artifact.

## Long-horizon mathematical and computational program

The first paper is not the boundary of Aleph. The repository should accumulate a small set of
landmark problems whose solutions, counterexamples, and computational tools improve understanding of
model-relative coordinates even when they do not fit the current submission. Each problem receives a
versioned statement, assumptions, proof or counterexample status, closest prior art, executable finite
case, and an explicit note on which engineering decision it changes.

1. **Representation and invariance.** Which parts of coordinate length survive a changed tokenizer,
   typed interface, universal code, or fixed scaffold, and which comparisons are necessarily
   conditional on shared decoder state?
2. **Stochastic description.** How do exact-success probability, thought/random tapes, computation
   time, residual code, and human readability combine without conflating prompt value, MDL, Levin
   complexity, and researcher search cost?
3. **Computability and search.** What finite-domain regret, reachability, non-starvation, lower bounds,
   or certificates can be proved for variable-length search, and what discovery gap is irreducible in
   an open prompt language?
4. **Frontier geometry.** Which staircase, duality, and Pareto facts follow from discreteness alone,
   and which apparent smooth laws are empirical regularities requiring falsification across targets
   and models?
5. **Information-source interaction.** When are prompt and weights identifiable only jointly, when
   does source decompose only relative to an intervention, and which controlled worlds distinguish
   association, exposure, duplicate-source interaction, and retrieval?
6. **Channel-relative leakage.** What can a finite decoder family rule out, how should side
   information and covert shared state be charged, and what impossibility results constrain any claim
   of universal non-leakage?

The mathematical track is allowed to end in a negative theorem or a sharper definition. It is not
allowed to turn an appealing analogy into a claimed result. Proof notes, machine-checked finite
enumerations, counterexample generators, and failed conjectures are first-class research artifacts.

## Formal objects

### Run context and outcome

For empirical runs, let

\[
c=(\theta,\tau,\iota,d,v)
\]

contain the model or service revision \(\theta\), tokenizer \(\tau\), interface \(\iota\), decoding
rule \(d\), and runtime version \(v\). The interface includes system and developer prompts, chat
template, tool and safety policy, and message serialization. The decoding rule includes sampling,
stop rules, maximum output length, and random-seed policy. A hosted-service identifier can pin an
empirical condition but is not an effective description from which a universal machine can simulate
the decoder. The algorithmic-complexity relation below therefore uses \(\bar c\), a complete
computable description of all five components, and excludes opaque hosted APIs.

The free context \(\bar c\) is target-independent across the declared panel. Any target-varying
system text, attachment, retrieval result, tool payload, reference, demonstration, or optimized random
seed is part of the typed coordinate \(p\) and is encoded and charged by \(C_{\tau,\iota}(p)\); it is
never a second free argument to the evaluator. A run that cannot serialize such a field into \(p\) is
outside the benchmark contract. Random seeds are either frozen before targets/candidates are seen and
averaged under that law, or serialized as part of the coordinate; a target-selected free seed is
prohibited.

Let \(\mathcal P_\iota\) be the interface-specific domain of legal prompt objects. A prompt \(p\) is
not merely a visible string: it includes every controllable message role, placement, token sequence,
attachment reference, and tool declaration admitted by the frozen interface. Let
\(\operatorname{ser}_\iota(p)\) be its published canonical serialization and
\(\operatorname{render}_\iota(p)\) the complete model input after fixed system/developer scaffolding
and chat templating.

The primary readable-coordinate experiment uses a narrower declared domain
\(\mathcal P_\iota^{\mathrm{text}}\subset\mathcal P_\iota\): exactly one controllable visible text
message in a fixed role and position, with system/developer messages, tool declarations, attachments,
and every non-content field held constant. Every member has a lossless published display
\(\operatorname{disp}_\iota(p)\) shown identically to annotators. Tokenizer-decoded strange strings
remain eligible for the raw view, but non-displayable token objects, attachments, role changes, and
tool schemas are outside the primary comparison. Extending readability to those objects requires a
separate modality-specific instrument; it cannot inherit the text protocol by notation alone.

For prompt \(p\in\mathcal P_\iota\), target \(y\), and distortion \(\delta\), define stochastic success

\[
\rho_{c,\delta}(p;y,\epsilon)
=
\Pr_{Z\sim Q_c(\cdot\mid p)}[\delta(y,Z)\le\epsilon].
\]

Every distortion \(\delta\) is named and versioned. The primary text experiment preregisters exact
reproduction \(\delta_{\mathrm{exact}}\); edit, semantic, or execution-based distortion is a separate
regime with its own blind calibration and can never appear as a silent fallback.

For formal comparisons define a total computable typed encoder
\(E_{\tau,\iota}:\mathcal P_\iota\to\mathcal A_{\tau,\iota}^*\) that is strictly injective over exact
legal prompt objects and has a computable decoder included in \(\bar c\). No renderer-equivalence
quotient is taken: two legal objects with different lossless displays, field bytes, or submitted token
identifiers remain distinct even if a particular renderer happens to produce the same model input.
The encoder preserves exact submitted token identifiers for raw-token fields instead of
decode--retokenize, tags message roles and structure, and length-delimits every
candidate-controlled attachment or tool payload that can affect the model. External referenced bytes
are included in \(p\). The only exception is a separately named conditional-reference regime in
which a frozen target-independent corpus and retriever are included in \(\bar c\), while \(p\)
contains the immutable object digest and complete retrieval key; the full rendered-input cost remains
a required report. Use the conditional coordinate cost

\[
C_{\tau,\iota}(p)
=\left|\operatorname{enc}_{\mathrm{pf}}(E_{\tau,\iota}(p))\right|,
\]

where \(\operatorname{enc}_{\mathrm{pf}}\) is a published self-delimiting encoding of the typed symbol
sequence. Below, \(C_\tau\) abbreviates \(C_{\tau,\iota}\) only because \(\iota\) is fixed by \(c\).
Define a separate injective rendered-input encoder \(E^{\mathrm{full}}_{\tau,\iota}\) over the exact
final token stream and any non-token payload bytes, and report
\(C^{\mathrm{full}}_{\tau,\iota}(p)=
|\operatorname{enc}_{\mathrm{pf}}(E^{\mathrm{full}}_{\tau,\iota}
(\operatorname{render}_\iota(p)))|\). The difference exposes fixed scaffold or side-information
subsidy; cross-interface compression claims use full cost unless a conditional comparison is named.
Report tokenizer tokens, UTF-8 bytes, and Unicode scalar counts as separate operational views. Raw
token count is not invariant to tokenizer or placement and must not be treated as Kolmogorov
complexity.

When \(c,\delta,\epsilon,\beta\), or readability thresholds are suppressed later, they are fixed by
the surrounding preregistered regime rather than silently changed.

### Readability contract

Readability is not the target model assigning high next-token probability to a prompt. That definition
is circular, model-dependent, and can disagree with human comprehension. It is also not one scalar
notion of surface fluency. Fix a two-stage human protocol \(H=(H_{\mathrm{surf}},H_{\mathrm{link}})\)
before testing targets. The primary protocol is defined only on
\(\mathcal P_\iota^{\mathrm{text}}\), and annotators see the lossless
\(\operatorname{disp}_\iota(p)\), never a hidden structured prompt object.

The target-blind surface stage asks a reader for a free response about whether
\(\operatorname{disp}_\iota(p)\) is linguistically intelligible as an instruction, reference,
compressed cue, elliptical phrase, or other communicative object. A separately assigned coder applies
the frozen rubric, so the estimand averages over both declared populations and the assignment policy:

\[
r_{\mathrm{surf},H}(p)
=
\Pr_{a\sim\mathcal R_{\mathrm{surf}},\,k\sim\mathcal C,\,J_H}
\left[Y^{\mathrm{surf}}_{a,k,J_H}\!\left(\operatorname{disp}_\iota(p)\right)=1\right].
\]

The link stage asks whether the prompt is a legible coordinate for this target, using a preregistered
matched-target choice or explanation task:

\[
r_{\mathrm{link},H}(p,y)
=
\Pr_{a\sim\mathcal R_{\mathrm{link}}}
\left[a\text{ correctly links }\operatorname{disp}_\iota(p)\text{ to }y\right].
\]

Link-stage annotators may see the preregistered balanced target alternatives needed by the task but
never model outputs, search scores, source assignments, or algorithm identity. Decoy generation and
difficulty calibration are frozen before final targets. This distinction matters: `Genesis 1:1–3`
can be a readable citation, while a fluent sentence can still fail to identify the intended target.

Report the following nominal coordinate types rather than pretending they form one ordinal scale:

- a natural-language instruction;
- a public reference or citation;
- a compressed but explainable natural-language cue;
- an elliptical or garden-path-like cue;
- an opaque/raw token coordinate.

The protocol must publish its rubric, raters, agreement, language coverage, and uncertainty rule.
Automated naturalness scores may triage candidates but may not certify readability. Let
\(\boldsymbol\eta=(\eta_{\mathrm{surf}},\eta_{\mathrm{link}})\). For the oracle object define

\[
\mathcal P^{\mathrm{read}}_{H,\boldsymbol\eta}(y)
=
\left\{p\in\mathcal P_\iota^{\mathrm{text}}:
r_{\mathrm{surf},H}(p)\ge\eta_{\mathrm{surf}},
r_{\mathrm{link},H}(p,y)\ge\eta_{\mathrm{link}}
\right\}.
\]

A held-out lower confidence bound is the empirical certification rule for membership, not the
definition of the population property. The raw-coordinate mode remains a separate frontier rather
than being silently discarded.

#### Human measurement protocol

`H` is shorthand for versioned components, not one undifferentiated panel:

\[
H=(\mathcal R,\mathcal C,I_{\mathrm{surf}},I_{\mathrm{link}},D,S_H,J_H,E,A_H),
\]

where \(\mathcal R\) is the intended reader population, \(\mathcal C\) is the target-blind coder
population, \(I\) are the two instruments, \(D\) is the decoy-panel generator, \(S_H\) is the reader
and item sampling design, \(J_H\) is coder assignment and adjudication, \(E\) is the exclusion policy,
and \(A_H\) is the frozen analysis and uncertainty rule. Following the interpretation-centered view
of the [Standards for Educational and Psychological Testing](https://www.testingstandards.net/uploads/7/6/6/4/76643089/standards_2014edition.pdf),
the project validates a score interpretation for a declared population, use, and condition; it does
not declare that “the test” is universally valid.

The default instrument is behavioral rather than a relevance Likert scale:

1. **Surface intelligibility.** Show only `disp_iota(p)`. Ask the reader to explain in one sentence what a
   sender may be asking, citing, or pointing to, with `CANNOT TELL` available. A second target-blind
   coder applies a frozen rubric to the free response. Success requires a coherent explanation that
   is supported by the visible prompt and does not rely on a private codebook. Preserve the raw
   response, coder labels, and disagreement; a third coder may adjudicate without overwriting them.
2. **Target-link legibility.** Show `disp_iota(p)`, one target excerpt, and three matched decoys in randomized
   order. The primary outcome is correct four-alternative forced choice, whose nominal chance rate is
   0.25. Ask confidence, `ambiguous/none`, and prior familiarity separately after the primary
   response. Link raters are blind to model output, search score, algorithm, and source assignment,
   but cannot correctly be called target-blind because the alternatives are visible.

Public-reference coordinates require a preregistered regime. `closed_book` asks what kind of public
reference the prompt expresses without external resolution. `lookup_allowed` records query, time,
and resolution result. The two regimes are never pooled. The intended reader population—such as
fluent adult readers in the prompt language—and any domain-expert stratum are declared before the
pilot. Language, expertise, and familiarity may be modeled, but an inconvenient subgroup is not
removed after observing outcomes.

Always publish the full surface/link table:

| surface | link | interpretation |
| --- | --- | --- |
| pass | pass | strict readable coordinate |
| pass | fail | intelligible but not a legible coordinate for this target |
| fail | pass | opaque, garden-path-like, or familiarity-mediated coordinate |
| fail | fail | neither construct established |

Only the first cell enters strict readable prompting complexity. Keeping all four cells prevents the
strict conjunction from deleting the raw or garden-path phenomenon that motivated the project.
Model-generation success is a third independent axis and never substitutes for either human stage.

Each target receives two independently constructed decoy panels. Candidate decoys cover, where
possible: a nearby passage from the same work or author; a topic/style/genre/length match with the
wrong content; and a high lexical or embedding neighbor with a deliberately wrong entity or fact.
Language, format, and excerpt length are matched, with a default design tolerance of 10 percent in
the declared token unit. Direct titles, filenames, author fields, and other option-only shortcuts are
removed. Latin-square or blocked randomization balances answer position, and panel identity is
estimated rather than ignored.

Embedding retrieval and adversarial filtering may propose hard decoys but cannot certify them. A
human pilot checks per-option choice rates, entropy, position effect, and panel effect, and includes:

- an information-free prompt, which should expose formatting or option-position shortcuts;
- an explicit reconstruction and a public-reference anchor, which test that the task is solvable;
- a misleading prompt designed to favor a declared wrong option;
- frozen A/B panels whose hashes are recorded before confirmation.

The instrument pilot spans coordinate types and difficulty before any final-target judgment. A
planning starting point is roughly 120 prompts and five judgments per item per stage for rubric and
decoy debugging; this is not evidence that five raters can confirm a candidate. Each rater sees at
most one candidate for a target, sessions are capped at a declared item count, 10--15 percent of items
are frozen anchors, and about 10 percent are hidden repeats. Familiarity is asked after the response
to avoid priming. Consent/language screens, latency checks, anchor rules, compensation, and every
exclusion are preregistered and written to an append-only audit.

For candidate `i` and judgment `j`, the simplest fixed-sample design uses

\[
X^{\mathrm{surf}}_{ij}\sim\operatorname{Bernoulli}(\theta^{\mathrm{surf}}_i),
\qquad
X^{\mathrm{link}}_{ij}\sim\operatorname{Bernoulli}(\theta^{\mathrm{link}}_i).
\]

Strict confirmation requires simultaneous lower bounds above both policy thresholds. Values such as
\(\eta_{\mathrm{surf}}=.80\) and \(\eta_{\mathrm{link}}=.70\) are reasonable *design starting
points*, not literature-derived constants. An exact-binomial planning calculation with one-sided
\(\alpha=.025\) per constraint illustrates the cost: at `n=30`, passing those thresholds requires
at least 29 surface and 27 link successes; at `n=60`, at least 55 and 50. Those designs have poor
power for true rates .90 and .80. Roughly 115 surface judgments or 155 link judgments are needed for
about .8 power under those example alternatives. The exact values must be regenerated from the
frozen candidate count, thresholds, multiplicity rule, and pilot-estimated dependence.

Consequently, every candidate admitted to `Shortest Confirmed` must independently meet the frozen
fixed-sample or sequential stopping rule, with approximately 120--160 judgments per stage as the
current conservative planning range for a small sentinel set. A target-population hierarchical model
is a secondary analysis and cannot promote an under-sampled individual candidate into the confirmed
set; such candidates remain descriptive or `indeterminate`. Multiple judgments from one rater are
not independent Bernoulli trials. A stage-specific sensitivity model includes candidate, rater,
target, judgment-level panel, and familiarity effects, for example, for
\(k\in\{\mathrm{surf},\mathrm{link}\}\),

\[
\operatorname{logit}\Pr(X^k_{ij}=1)
=\mu_k+a^k_i+u^k_j+v^k_{\mathrm{target}(i)}+w^k_{\mathrm{panel}(i,j)}
+\gamma_k\,\mathrm{familiarity}_{ij}.
\]

If judgments arrive adaptively, use a frozen alpha ledger and time-uniform confidence sequences. An
example operational schedule begins at 30, adds batches of 10, stops by 160, passes only when the
lower sequence crosses the threshold, fails only when the upper sequence falls below it, and otherwise
returns `indeterminate`. The schedule is illustrative until preregistered; ordinary fixed-`n`
intervals cannot be repeatedly inspected and retain their original coverage.

Reliability reporting includes vote distributions, positive and negative agreement, percent
agreement, nominal Krippendorff alpha with a bootstrap interval, overlap count, hidden-repeat
intra-rater agreement, and representative disagreements. Link reporting prioritizes accuracy,
confusion matrix, and position/panel/familiarity effects because the correct option is defined.
Reliability is not construct validity: low agreement triggers rubric and heterogeneity analysis, not
post hoc annotator deletion, while high agreement cannot prove the intended construct.

Perplexity, embedding similarity, FKGL-style formulas, automated readability metrics, and LLM judges
are discovery surrogates only. Human-evaluation research repeatedly finds that ratings depend on
construct definition, reader population, task framing, and power; see
[MetricEval](https://aclanthology.org/2023.emnlp-main.676/),
[reference-game evaluation](https://aclanthology.org/2020.scil-1.16/),
[intrinsic task-based referring-expression evaluation](https://aclanthology.org/2024.acl-long.389/),
[distractor-evaluation review](https://aclanthology.org/2025.bea-1.5/), and
[human-rating power analysis](https://aclanthology.org/2026.findings-eacl.223/). The final report follows
the disclosure checklist in [Illusions of the Gold Standard](https://aclanthology.org/2026.acl-long.635/):
instructions, construct rationale, interface, recruitment, demographics, compensation, ethics/IRB
status, quality controls, exclusions, sample and rater counts, power, uncertainty, and agreement.

### Oracle construct versus found statistic

The primary search-independent target parameter is readable prompting complexity

\[
L^{\mathrm{read}}_{c,H,\delta}(y;\epsilon,\beta,\boldsymbol\eta)
=
\min_{p\in\mathcal P^{\mathrm{read}}_{H,\boldsymbol\eta}(y)} C_\tau(p)
\]

subject to

\[
\rho_{c,\delta}(p;y,\epsilon)\ge 1-\beta.
\]

All minimum objects in this plan take value \(+\infty\) when the feasible set is empty. Because the
charged code lengths are natural numbers, every nonempty feasible cost set has a least element even
when the prompt domain is countably infinite.

This preserves Aleph's original question without assuming that every short readable coordinate is the
same information channel. A stricter tested-noncopy variant adds channel-specific constraints
\(\ell_j(p,y)\le t_j^{\mathrm{copy}}\) for every member of a finite, versioned copy-reconstruction suite
\(\mathcal V_{\mathrm{copy}}\), defined below. It must be named
\(L^{\mathrm{read,\mathcal V_{copy}}}\), not presented as universal non-leakage. Public-reference
resolution is a separate provenance channel and does not make a readable coordinate “copying.”

Keep the unconstrained raw-token comparator explicit:

\[
L^{\mathrm{raw}}_{c,\delta}(y;\epsilon,\beta)
=
\min_{p\in\mathcal P_\iota^{\mathrm{text}}} C_\tau(p)
\quad\text{subject to}\quad
\rho_{c,\delta}(p;y,\epsilon)\ge 1-\beta.
\]

Here `raw` means that human readability is unconstrained, not that the search may change roles,
tools, attachments, or other interface fields. An all-interface minimum over \(\mathcal P_\iota\)
may be reported separately as \(L^{\mathrm{raw,all}}\), but it is not subtracted from the readable
text-message minimum.

The difference

\[
G^{\mathrm{read}}_{c,H,\delta}
(y;\epsilon,\beta,\boldsymbol\eta)
=
L^{\mathrm{read}}_{c,H,\delta}(y;\epsilon,\beta,\boldsymbol\eta)
-L^{\mathrm{raw}}_{c,\delta}(y;\epsilon,\beta)
\]

This gap is defined only when \(L^{\mathrm{raw}}<+\infty\). If raw is finite and readable is infinite,
the gap is \(+\infty\); if raw is infinite, report the target as inaccessible under the regime and the
gap as undefined, avoiding the indeterminate \(+\infty-(+\infty)\).

When defined, it is a **readability gap** relative to the declared human protocol, not a universal interpretability
constant. It makes the repository's early readable-versus-raw research choice measurable instead of
discarding raw coordinates or quietly calling them prompts.

Rerun reliability is already represented by \(\rho_{c,\delta}\) under one fixed run context. If the
study also claims stability under benign perturbations, freeze a nuisance distribution \(\nu(c)\)
over declared interface, formatting, or decoding changes and define the higher-is-better quantity

\[
s_{c,\nu,\delta}(p;y,\epsilon)
=
\Pr_{\widetilde c\sim\nu(c),\,Z\sim Q_{\widetilde c}(\cdot\mid p)}
[\delta(y,Z)\le\epsilon].
\]

Because stability appears in the headline frontier, \(\nu\) is mandatory and must be frozen before
Pilot A. Runs without a scientifically defensible nuisance distribution are diagnostic only and may
not enter the paper's stability axis or source-selective constraints; an ad hoc transform of a few
samples is never an acceptable substitute.

The scalar minimum is one projection of a richer object. For a finite evaluated archive \(S\), fix a
metric manifest \(m\) that names every estimator, evidence split, and metric version, and define
the threshold-normalized copy violation

\[
v_{\mathcal V_{\mathrm{copy}}}(p,y)
=
\max_{j\in\mathcal V_{\mathrm{copy}}}
\frac{\ell_j(p,y)-t_j^{\mathrm{copy}}}{\sigma_j},
\]

where \(t_j^{\mathrm{copy}}\) and positive calibration scale \(\sigma_j\) are preregistered per channel below.
The public-reference channel is excluded. Define the objective map

\[
g_m(p;y)
=
\big(C_\tau(p),1-\widehat\rho_{c,\delta}(p),1-\widehat r_{\mathrm{surf},H}(p),
1-\widehat r_{\mathrm{link},H}(p,y),
1-\widehat s_{c,\nu,\delta}(p),
\widehat v_{\mathcal V_{\mathrm{copy}}}(p,y)\big).
\]

Because most discovered candidates do not receive human confirmation, this map is deliberately
partial on the full archive. Let

\[
S_m^{\mathrm{complete}}(y)=\{p\in S:g_m(p;y)\in\mathbb R^6\}.
\]

Candidates outside this set remain in the append-only archive with `unknown` components; missing
values are never imputed as passes, failures, or favorable extremes. Let the confirmed-metric Pareto
candidate set and its objective image be

\[
\mathcal P_{S,m}(y)=\{p\in S_m^{\mathrm{complete}}(y):\nexists q\in S_m^{\mathrm{complete}}(y)
\text{ with }g_m(q;y)\preceq g_m(p;y)\text{ and at least one strict coordinate}\},
\qquad
\mathcal F_{S,m}(y)=\{g_m(p;y):p\in\mathcal P_{S,m}(y)\}.
\]

\(\mathcal P_{S,m}\) is the scientific candidate archive view; \(\mathcal F_{S,m}\) is its objective
image. Both express a multidimensional partial order, not a canonical path. The complete
\(\widehat{\boldsymbol\ell}_{\mathcal V}\) provenance profile remains attached to every candidate and
is never collapsed for scientific reporting. Discovery may maintain a separately named
\(g_m^{\mathrm{sur}}\) and \(\mathcal P_{S,m}^{\mathrm{sur}}\) using frozen proxies, but neither is
called the readable or confirmed scientific frontier.

This is a point-estimate observed front, not certified Pareto membership. Under a conservative
Cartesian-envelope reporting rule for simultaneous minimization intervals \([L_{pj},U_{pj}]\), label
\(q\) as certified-dominating \(p\) when \(U_{qj}\le L_{pj}\) for every objective and
\(U_{qk}<L_{pk}\) for at least one. Label \(p\) certified-nondominated when every other \(q\) has
some objective with \(L_{qj}>U_{pj}\); label all remaining cases `unresolved`. These are sufficient
display rules, not necessary conditions: an exact tie or a correlated joint confidence region may
certify more than marginal Cartesian separation. The report preserves the three conservative states
instead of converting uncertainty into a crisp frontier.

For a user-facing slider over the complete scientific view, preregister a projection rule
\(\Phi(p;y)\): a total lexicographic key whose named constraint violations, objective directions and
order, missing-value policy, and final canonical-candidate-hash tie-break are all published. For
length budget \(b\), let \(E_b=\{p\in\mathcal P_{S,m}(y):C_\tau(p)\le b\}\) and select

\[
p_b=
\begin{cases}
\bot,&E_b=\varnothing,\\
\text{the unique }\Phi\text{-minimum of }E_b,&E_b\ne\varnothing.
\end{cases}
\]

The initial \(\bot\) state is shown as “no eligible observation,” not as a candidate. Define
\(\Gamma_{S,\Phi}\) as the ordered sequence of *actual candidates* selected when \(p_b\)
changes across observed budgets. The archive is the scientific object; \(\Gamma\) is a declared
visualization projection. A cumulative best-at-budget value may repeat between breakpoints, but it
must never be emitted as a newly measured prompt coordinate.

For searcher \(A\), search budget \(B\), random state \(\omega\), and a frozen candidate set
\(S^{\mathrm{freeze}}_{A,B,\omega}\), define the simultaneous confirmation set

\[
\widehat{\mathcal C}^{\mathrm{conf}}
=
\left\{p\in S^{\mathrm{freeze}}_{A,B,\omega}:
\underline\rho_{c,\delta}(p)\ge1-\beta,
\underline r_{\mathrm{surf},H}(p)\ge\eta_{\mathrm{surf}},
\underline r_{\mathrm{link},H}(p,y)\ge\eta_{\mathrm{link}}
\right\},
\]

where all lower bounds come from the fresh or anytime-valid simultaneous procedure below. The
measurable confirmed statistic is

\[
\widehat L^{\mathrm{read,conf}}_{c,H,\delta,A,B,\omega}
=
\min_{p\in\widehat{\mathcal C}^{\mathrm{conf}}}C_\tau(p),
\]

with value \(+\infty\) if the set is empty. On the simultaneous-coverage event,

\[
L^{\mathrm{read}}_{c,H,\delta}(y;\epsilon,\beta,\boldsymbol\eta)
\le
\widehat L^{\mathrm{read,conf}}_{c,H,\delta,A,B,\omega}.
\]

Thus a confirmed `Shortest Found` is a high-confidence constructive upper bound, not an estimator
proven close to a global minimum. A search-time best based on surrogates or point estimates is labeled
`provisional`, never `confirmed`. Search budget belongs to the found statistic. It must not be inserted
into the oracle object and then described as resource-bounded Kolmogorov complexity: decoder execution
cost and researcher search cost are different resources.

The same simultaneous intervals also define an honest shortest interval inside the frozen archive.
Let

\[
\widehat{\mathcal C}^{\mathrm{possible}}
=
\left\{p\in S^{\mathrm{freeze}}_{A,B,\omega}:
\overline\rho_{c,\delta}(p)\ge1-\beta,
\overline r_{\mathrm{surf},H}(p)\ge\eta_{\mathrm{surf}},
\overline r_{\mathrm{link},H}(p,y)\ge\eta_{\mathrm{link}}
\right\}
\]

contain candidates whose upper bounds have not ruled out any required threshold, and let
\(L_S^*=\min\{C_\tau(p):p\in S^{\mathrm{freeze}}_{A,B,\omega}\text{ is population-feasible}\}\).
Define

\[
L_{\mathrm{lb}}=\min_{p\in\widehat{\mathcal C}^{\mathrm{possible}}}C_\tau(p),\qquad
L_{\mathrm{ub}}=\min_{p\in\widehat{\mathcal C}^{\mathrm{conf}}}C_\tau(p),
\]

with \(+\infty\) for an empty set. On the simultaneous-coverage event,
\(L_{\mathrm{lb}}\le L_S^*\le L_{\mathrm{ub}}\). This is an archive-scoped interval, not a global
lower bound. It becomes global only with an exhaustive cheaper-prefix witness or a sound structural
lower-bound oracle; unresolved cheaper candidates remain explicit in the certificate.

For one append-only trace with a fixed feasibility predicate, increasing budget can only improve or
preserve the descriptive best-found cost. Independently confirmed sets can change as evidence accrues;
independent reruns, changed seeds, service drift, and later human reclassification are different
experiments and do not inherit monotonicity.

### Relation to ACR and MiniPrompt

Under an identical admissible token domain, fixed scaffold/placement, tokenizer and length unit,
deterministic decoding, exact output-plus-EOS convention, and matched legal-token policy, the ACR
denominator is the same base optimization object as
\(L^{\mathrm{raw}}\), up to the declared prompt-cost code:

\[
\operatorname{ACR}(M,y)
=
\frac{|y|}{\min_x\{|x|:M(x)=y\}}.
\]

Aleph therefore adopts ACR as prior art rather than redescribing the reciprocal ratio as a new
definition. Its extensions are explicit and separately ablated: stochastic success probability,
prefix-free and multi-view prompt cost, a human-measured readable subset with a raw comparator,
observed multiobjective archives and path breakpoints, finite-budget/restart uncertainty, independent
confirmation, trace/provenance constraints, and paired source interventions. MiniPrompt's
GCG-plus-length-search result is a heuristic shortest found point, not proof of the denominator's
global optimum and not causal evidence that the target came from training weights. These limitations
motivate Aleph's measurement contract; they do not diminish MiniPrompt's priority as the closest
empirical baseline.

When those interface conditions differ, the quantities are only related conditional code lengths,
not equal denominators. In particular, Aleph's primary raw view ranges over one visible text-message
domain, while ACR implementations may optimize arbitrary token IDs inside fixed wrappers.

### Relation to algorithmic rate-distortion

For a universal machine \(U\), define conditional individual algorithmic rate-distortion

\[
r_U(y,\epsilon\mid \bar c)
=
\min_{z:\delta(y,z)\le\epsilon} K_U(z\mid \bar c).
\]

Also define \(r_U(y,\epsilon)=\min_{z:\delta(y,z)\le\epsilon}K_U(z)\).

For a fixed computable deterministic decoder \(f_{\bar c}\), define

\[
L^{\mathrm{read,det}}_{\bar c,H,\delta}
(y;\epsilon,\boldsymbol\eta)
=
\min_{p\in\mathcal P^{\mathrm{read}}_{H,\boldsymbol\eta}(y)}
\left\{C_\tau(p):\delta(y,f_{\bar c}(p))\le\epsilon\right\}.
\]

Then

\[
r_U(y,\epsilon\mid \bar c)
\le
L^{\mathrm{read,det}}_{\bar c,H,\delta}
(y;\epsilon,\boldsymbol\eta)+O(1).
\]

The universal machine can invert the typed prefix-free prompt code and simulate the fixed decoder
supplied as conditional information. Without conditioning on the run context, the corresponding
bound is

\[
r_U(y,\epsilon)
\le
K_U(\bar c)
+L^{\mathrm{read,det}}_{\bar c,H,\delta}
(y;\epsilon,\boldsymbol\eta)+O(1).
\]

This second form makes the hidden subsidy from weights, tokenizer, interface, and decoding rule
explicit. A famous target can have a one-token coordinate not because its intrinsic information
vanished, but because much of the effective description sits in \(\bar c\). The reverse inequality
does not generally hold because an arbitrary shortest program need not be expressible through the
model's prompt interface, much less through its human-readable subset. A low-complexity target may
also be outside the decoder image. Aleph is therefore a restricted, interpreter-relative code length,
not an estimator of universal Kolmogorov complexity and not covered by a cross-model invariance
theorem.

Four different resources must remain separate in notation and artifacts:

1. \(C_\tau(p)\): the prefix-free communication cost of the prompt;
2. execution cost of running \(f_{\bar c}\), relevant to a Levin-style resource-bounded analogue;
3. researcher search budget \(B\), which changes only the best-found statistic;
4. \(K_U(\bar c)\), the description supplied by the fixed model and interface in the unconditional
   comparison.

\(K_U(\bar c)\) is not computable. Operational comparisons therefore report a named, canonical
serialization length for the checkpoint, runtime, tokenizer, and interface bundle only as an
auditable computable upper bound, never as measured Kolmogorov complexity. A panel may additionally
amortize that full-stack description over a frozen target set, but the panel and amortization rule
must be fixed before observing results.

Calling \(\widehat L_{A,B}\) “resource-bounded Kolmogorov complexity” would collapse items 2 and 3.
Calling prompt length alone an MDL score would omit the decoder/model description and residual code.
For an effective stochastic decoder and exact finite output including EOS, a legitimate conditional
two-part score and its one-part mixture counterpart are

\[
D_c(y)=\min_p\{C_\tau(p)-\log_2P_c(y\mid p)\},\qquad
J_c(y)=-\log_2\sum_p2^{-C_\tau(p)}P_c(y\mid p)\le D_c(y).
\]

If \(R_y(r)=\max_{C_\tau(p)\le r}P_c(y\mid p)\), then
\(D_c(y)=\min_r\{r-\log_2R_y(r)\}\), while
\(L_\beta(y)=\min\{r:R_y(r)\ge1-\beta\}\). This is the precise bridge between the reliability
frontier and MDL-style accounting. Prompt value as a likelihood gain is prior art; after charging the
coordinate, the corresponding net gain is that value minus \(C_\tau(p)\). The honest connection to
algorithmic statistics is the study of a complexity--fit tradeoff, not a claim that a prompt is an
algorithmic sufficient statistic.

There are two other useful but limited analogies. First, model weights and the pinned interface act
like shared decoder state: a short prompt measures communication conditional on that state. This is
related in spirit to rate-distortion with side information, but it is not a Wyner--Ziv theorem. The
searcher normally also knows or queries the model, Aleph studies individual targets rather than an
i.i.d. source, and no joint source/side-information distribution has been specified. A future
population-level extension may define one; the current paper should not borrow a Shannon rate from
the analogy. Second, the
[smallest grammar problem](https://doi.org/10.1109/TIT.2005.850116) also seeks a compact generative
description for one string and is computationally hard. Its grammar is part of the code, whereas
Aleph supplies a learned decoder for free and restricts the visible code to prompts. It is useful
complexity context, not a baseline that can emit model-relative coordinates.

This places Aleph near individual algorithmic rate-distortion without claiming equality or
universality. The relevant theoretical anchors are the individual rate-distortion and
structure-function results of
[Vereshchagin and Vitányi](https://homepages.cwi.nl/~paulv/papers/rateieee-it.pdf) and
[algorithmic statistics](https://homepages.cwi.nl/~paulv/papers/structure.pdf), not an informal claim
that token length approximates strict Kolmogorov complexity. Their results also warn against assuming
a universal smooth frontier: individual structure and rate-distortion functions can have widely
varying shapes. Aleph must measure breakpoints rather than draw an interpolated law into existence.

The stochastic object needs a different argument. For an effective decoder distribution and a
prefix-coded prompt mixture, T2b below supplies an exact-output probability-mass bound. Approximate
success mass over a distortion ball does not by itself identify one reconstructible output; it needs
ball-size, a canonical representative, or verifier/search accounting. A target-selected random seed
is never free: freeze the seed distribution or charge the selected tape. A hosted model name or API
revision is not a complete effective decoder description. Hosted APIs remain valid empirical
contexts, but only open, fully specified runtimes support these constructive inequalities.

### Randomized association intervention and exposure extension

The source layer uses independently trained permutation-sibling model pairs. In pair \(r\), one model
is trained under permutation \(\Pi_r^A\) and the other under an edge-disjoint matched permutation
\(\Pi_r^B\). Both see the same key and target marginals, templates, optimizer schedule, and exposure
counts; only the pairing changes. Write \(\theta(\Pi,s)=\mathcal M(\Pi,s)\) for the checkpoint
produced by the frozen training procedure with training randomness \(s\). An exposed association is
\(a=(i,j,z)\), where \(z\in\{A,B\}\) and \(\Pi_r^z(i)=j\). Let
\(\theta_{ra}^{+}=\theta(\Pi_r^z,s_r^z)\) and
\(\theta_{ra}^{-}=\theta(\Pi_r^{\neg z},s_r^{\neg z})\). Positive and
negative are therefore association-relative roles, not globally fixed checkpoints.

Because both siblings see every controlled target, this design identifies **mapping-specific
accessibility** or **association-selective elicitation**. It does not identify whether target `y`
entered the weights at all, how many documents supplied it, or which natural document was its unique
source. Claims about target exposure require a third independently trained world in which the
controlled corpus and target are absent. The stronger design is a **nested three-world by
two-coordinate experiment**: absent/matched-dummy, present/wrong-binding, and present/correct-binding
worlds, each crossed with neutral versus coordinate prompt. Correct versus wrong binding to \(y\) is
undefined when \(y\) was never exposed, so this is not advertised as a full \(2\times2\times2\)
factorial. It separates generic exposure, association binding, and prompt elicitation without
pretending to decompose hidden information into additive bits.

For a nonempty target with \(n_\tau(y)\ge1\), fix a numerical floor \(0<\lambda<1\) before any run
and define the higher-is-better clipped target-token average log-likelihood

\[
U_\lambda(c,p,y)
=
\frac{1}{n_\tau(y)}
\sum_{t=1}^{n_\tau(y)}
\log_2\max\!\left\{
P_{\theta_c}\!\left(y_t\mid\operatorname{render}_{\iota_c}(p),y_{<t}\right),\lambda
\right\}.
\]

Below, \(U\) abbreviates this frozen \(U_\lambda\). It is bounded in
\([\log_2\lambda,0]\), so every displayed expectation and contrast is real and integrable. Report
the clipping rate. An unclipped score is only a separately named secondary metric when every evaluated
target-token probability is strictly positive and its absolute expectation is finite. This is a
target-token score, not a claim that one realized target is a proper-scoring-rule experiment. Exact
or thresholded generation success is a secondary behavioral outcome; semantic similarity is only
supporting evidence for natural targets.
When paired siblings share tokenizer, interface, scaffold, and every non-checkpoint context field,
later expressions abbreviate \(U(c,p,y)\) as \(U(\theta,p,y)\). Otherwise the full run context is
mandatory.

The four-cell randomized factorial interaction is valid only for a controlled prompt grammar with an
explicit coordinate slot. This is not an observational difference-in-differences design and invokes
no parallel-trends assumption. Preregister a mechanical template \(T(s)\), an association-specific
coordinate value \(s_a\), and a length- and syntax-matched neutral value \(s_\varnothing\). Then set
\(p_{a1}=T(s_a)\) and \(p_{a0}=T(s_\varnothing)\). No researcher-written, post-hoc deletion is
allowed. Define

\[
\mu_{ec}
=
\mathbb E_{r,z,i}
\left[U\!\left(\theta_{ra}^{e},p_{ac},y_a\right)\right],
\quad e,c\in\{0,1\},
\]

with \(e=1\) for the association-positive sibling, \(e=0\) for the association-negative sibling,
\(c=1\) for \(T(s_a)\), and \(c=0\) for \(T(s_\varnothing)\). The expectation is over the preregistered
randomization distribution of whole permutations and independently trained model pairs; within each
pair draw \(z\) uniformly from \(\{A,B\}\), draw \(i\) uniformly from \([n]\), set
\(j=\Pi_r^z(i)\), and let \(a=(i,j,z)\). Any declared template randomization is then averaged under
its frozen law. Thus the four cells and \(\psi_r\) below use exactly the same uniform weighting over
the \(2n\) exposed associations.

Report the four cells and the distinct contrasts:

\[
\Delta_{\mathrm{coord}}^+ = \mu_{11}-\mu_{10},
\qquad
\Delta_{\mathrm{coord}}^- = \mu_{01}-\mu_{00},
\]

\[
I_{\mathrm{pair}}
=
\mu_{11}-\mu_{10}-\mu_{01}+\mu_{00},
\qquad
\Delta_{\mathrm{pair}}^{\mathrm{coord}}=\mu_{11}-\mu_{01}.
\]

The association-relative signed neutral contrast cancels under the balanced design and is therefore
not a drift diagnostic. Preserve physical sibling labels \(A,B\) and report instead

\[
W_{\mathrm{neutral}}^{\mathrm{abs}}
=\mathbb E_{r,j}\left|
U(\theta_r^A,T(s_\varnothing),y_j)-U(\theta_r^B,T(s_\varnothing),y_j)
\right|,
\]

where \(j\) is uniform over the \(n\) controlled targets, plus the full signed per-target distribution
under the same preregistered weights. Exposure drift
requires the exposure-zero world; this magnitude captures only nonspecific sibling disagreement.
Train independent same-mapping replicas and report \(W_{\mathrm{same-map}}^{\mathrm{abs}}\) as the
ordinary training-seed baseline. A between-mapping excess or ratio is labeled only “excess
nonspecific disagreement,” because it still does not identify a semantic source mechanism.

\(I_{\mathrm{pair}}\) is an association-selective elicitation contrast under the controlled grammar.
It is not an additive decomposition of “information in the prompt” and “information in the weights,”
nor a count of bits stored in parameters. A positive result says that the target-specific slot changes
target accessibility differently across the two trained association worlds.
\(\Delta_{\mathrm{pair}}^{\mathrm{coord}}\) is the raw sibling contrast with the coordinate present.

An arbitrary prompt found by open search has no mechanically defined \(p_0\). For a frozen candidate
in that regime, report the preregistered direct sibling contrast

\[
D_{ra}(p)
=
U(\theta_{ra}^{+},p,y_a)-U(\theta_{ra}^{-},p,y_a).
\]

Do not retrofit a four-cell interpretation by manually removing whichever phrase looks important
after search.

For one fixed trained pair \(r\), preregister a target-blind Markov kernel
\(\mathcal N(dp_0\mid m(p))\) before open search. The matching summary \(m(p)\) contains only the
listed nonsemantic features—charged length bin, frozen syntax class, coordinate type, locale, and
Unicode/token-shape strata—and may not depend on association \(a\), target \(y_a\), checkpoint
identity, or model outputs. Any additional stratum must be frozen and justified as target-blind.
Define the centered candidate-level contrast

\[
A_{ra}^{\mathrm{open}}(p)
=D_{ra}(p)-\mathbb E_{p_0\sim\mathcal N(\cdot\mid m(p))}D_{ra}(p_0).
\]

Report raw \(D_{ra}(p)\) as well; centering reduces but does not eliminate generic checkpoint drift.
This is the contrast used by a target-specific selective-length object. A separate algorithm-level
transfer estimand is

\[
\Psi_A^{\mathrm{open}}
=
\mathbb E_{(r,a)\sim\mathcal G_{\mathrm{test}}}
\left[A_{ra}^{\mathrm{open}}(p_a^{\mathrm{freeze}})\right],
\]

where \(p_a^{\mathrm{freeze}}\) is produced by frozen searcher \(A\) from target \(y_a\) and its
declared discovery evidence before the test training pair is queried. The fixed-pair length and the
cross-replica transfer effect are different estimands and are reported separately.

The independent training pair, not each nested association or generation sample, is the unit of the
training intervention. Target-level results improve precision and describe heterogeneity but cannot
manufacture independent training replications. Candidate prompts must be frozen and re-evaluated on
unseen same-mapping replicas and assignment-flip replicas so that model-seed fingerprints are not
mistaken for association structure.

Primary inference for the mean estimand \(\Psi_{\mathcal G}\) follows the whole-permutation assignment
mechanism with a compatible randomization test or pair-level mean procedure; it does not treat edges
or targets as independently randomized. A pair-level sign test is a separate robust analysis of the
median or \(\Pr(\psi_r>0)\), not evidence about the mean. With only three independent pairs, that
exact two-sided sign test has minimum attainable `p=.25`; at least six pairs are required even to make
`p<.05` attainable. The actual pair count for the mean analysis is set by simulation from pilot
pair-level variance and a preregistered minimum effect. Any edge-level direct-effect interpretation
additionally states an exposure-sufficiency assumption and bounded-interference sensitivity analysis.
Merely swapping the display labels `A/B` leaves the symmetric \(\psi_r\) unchanged and is not a valid
randomization test. A sign-flipping assignment test requires the design to randomize permutations into
fixed training-seed/hardware slots and, under an appropriate sharp null, reassign mapping to slot.
Otherwise use independent-pair inference and report the small-\(R\) limitation.

### Typed provenance, tested recoverability, and trace integrity

`Provenance` is an umbrella in product language, not one scientific variable. Every schema, metric,
panel, and claim uses one of these typed objects:

| type | question | admissible evidence |
| --- | --- | --- |
| `CorpusTrace` | Did a string or document occur in a declared corpus? | immutable training manifest, content hash, Data Portrait, or documented dataset lineage |
| `TrainingInfluence` | Did inclusion of a training unit change model behavior? | randomized subsets, leave-out/retraining, Datamodels, TRAK, or another declared approximation |
| `EvidenceSupport` | Which candidate documents support the answer? | retrieval plus entailment, anti-document and conflict controls; not automatically historical source |
| `PromptRecoverability` | Can a frozen system recover the target from the prompt without calling the evaluated model? | declared reconstructor, side information, nulls, budget, and calibrated utility |
| `Extractability` | Can the evaluated model be induced to generate the target? | prefix, MiniPrompt, probabilistic extraction, and independently replayed generations |
| `AssociationEffect` | Does a coordinate selectively activate a randomized training binding? | permutation siblings, matched null coordinates, and pair-level intervention analysis |
| `SelfCitation` | Which source does the model claim? | source-aware training or generated citation, calibrated against assignment and never assumed faithful |

These are not interchangeable. `CorpusTrace` does not prove `TrainingInfluence`; `EvidenceSupport` is
not necessarily historical source; `PromptRecoverability` is not model-mediated accessibility; and
`SelfCitation` is not causal attribution. Natural-model work may combine observations from these
types, but only controlled interventions identify `AssociationEffect`.

A successful target-conditioned coordinate necessarily carries target-selection information because
the search itself sees \(y\). Tested noncopy therefore cannot mean \(I(P;Y)=0\) or “no system can
recover the target.” It is a decoder-class-relative channel policy: copy/code decoders may be
prohibited, while declared semantic, public-reference, or model-mediated resolution may be allowed,
with every side-information source charged. A title or citation can have high
`PromptRecoverability` without being classified as surface or encoded copy.

Every `TrainingInfluence` claim names its intervention unit: document, duplicate-equivalence cluster,
semantic work, or corpus. If behavior is present whenever either duplicate \(d_1\) or \(d_2\) is in
training, full-set leave-one-out influence is zero for both although joint removal changes behavior;
a Shapley allocation may instead split credit. No single-document estimate is silently promoted to a
unique work-level source. Natural-data studies therefore publish duplicate clusters and joint-removal
or interaction controls.

The current n-gram overlap is a **surface-copy proxy**. It does not detect paraphrase, translation,
transliteration, base64, cipher text, acrostics, identifiers, or model-assisted reconstruction.

Define recoverability relative to a finite, versioned prompt-only probe suite
\(\mathcal V=\{(R_j,z_j,u_j):j=1,\ldots,m\}\) fixed before final targets are inspected. Each entry
records executable code, weights, decoding settings, declared side information \(z_j\), stochastic
budget, and bounded utility \(u_j\). Let

\[
\ell_j(p,y)
=
\mathbb E_\xi[u_j(R_j(p;z_j,\xi),y)],
\qquad
\boldsymbol\ell_{\mathcal V}(p,y)
=(\ell_1(p,y),\ldots,\ell_m(p,y)).
\]

Every adversary's code, resources, training data, checkpoints, side information, and stochastic budget
must be frozen. Target-constant reconstructors, target identifiers that index a hidden lookup table,
and learned models with undeclared target exposure are invalid because they contribute the answer
rather than recover it from the prompt. Different suite components create different tested claims:

- surface class: normalized lexical and substring copying;
- semantic class: paraphrase and translation recovery;
- code class: deterministic decoding of base64, ciphers, acrostics, and structured encodings;
- public-reference class: resolution of titles, citations, names, and other human-legible indexes;
- learned class: a frozen reconstructor whose training corpus has been audited for evaluation-target
  exposure and that has no access to the evaluated target model.

The minimum suite instantiates more than obvious text transforms. It includes style-transfer and
cross-lingual translation/back-translation recovery; secret-key vocabulary partitions, synonym-choice
and sampling-seed channels; single-generation and multi-generation/majority decoding; a
title/citation resolver; and execution equivalence for code or structured behavioral targets. A
high-level embedding or general LLM judge cannot replace these executable channel-specific probes.
The suite includes a deliberately cheating reconstructor with hidden target lookup as a positive
control and must reject it when its undeclared side information is removed.

The utilities need not share a numerical scale. For each component, publish its matched-null baseline,
calibration curve, false-positive rate, power, adversarial failures, and preregistered threshold
\(t_j^{\mathrm{copy}}\). If the search scheduler uses normalized violation, freeze a positive scale \(\sigma_j\)
from the calibration distribution. Tested-noncopy membership requires simultaneous channelwise bounds
\(\overline\ell_j(p,y)\le t_j^{\mathrm{copy}}\) for every \(j\in\mathcal V_{\mathrm{copy}}\). If a scalar is
needed only for scheduling, use a declared threshold-normalized maximum violation; never take the raw
maximum of incomparable utilities.

A finite suite cannot upper-bound every possible reconstructor: passing it supports only “no tested
copy reconstructor in suite version \(\mathcal V_{\mathrm{copy}}\) exceeded its declared threshold.”
“Non-leaking” is allowed only as shorthand with suite version and thresholds attached.

A one-time-pad counterexample makes the boundary concrete: if \(p=E_k(y)\) with an undeclared key
\(k\) stored in model state or interface scaffolding, then a prompt-only probe can see a string
independent of \(y\) while the keyed evaluator reconstructs \(y\) exactly. No finite prompt-only suite
rules out such shared-state channels. The typed interface encoding, full rendered-input accounting,
and lineage-complete trace audit are therefore part of the evidence rather than bookkeeping extras.

Report empty-prompt and matched-null performance for every learned or reference resolver so that
target knowledge supplied by the reconstructor is not credited to the prompt. Preserve every channel
as a provenance/recoverability profile; a public reference is scientifically different from base64
even if both permit reconstruction, and reference resolution is not a copy violation by default.

Search-process contamination is not a function of the final prompt. Define a separate predicate
\(\operatorname{TraceIntegrity}(\mathcal T)\) over the complete run transcript \(\mathcal T\). It
fails if target fragments enter candidates through an undeclared fallback, cache, demonstration,
manual edit, cross-split state, or unlogged proposer output. A candidate can pass every tested-copy
channel and still fail trace integrity; both states must remain visible in the archive.

Calibration ablates target-independent versus hidden-lookup decoders, free versus charged decoder
side information, exact-copy blocking followed by style-transfer recovery, low textual similarity
with execution-equivalent code, secret-key absent versus present, and single output versus repeated
aggregate recovery. This is the empirical meaning of “tested noncopy”; expanding the suite can revoke
that label for a previous candidate without rewriting its original receipt.

## Theorem and proposition targets

The paper's primary novelty is empirical and algorithmic; it does not need to manufacture a theorem
about the coordinate frontier. T1 is a scope lemma for the source layer, not a substitute for the
paired experiment. T1b--T4 are formal backbone and claim control unless a stronger result is actually
proved.

### T1 — single-world source non-identifiability

Source must be a counterfactual property, not a label attached after the fact. A visible prompt
contrast under a stable declared interface is query-identifiable, but it measures input sensitivity
rather than historical information origin. At query \(t\), let \(O_t\) be the complete declared
observable response tuple: generated output \(Z_t\), returned logits or log-probabilities, status and
error fields, and every normalized metadata field exposed to the searcher. Timing is excluded only
when the interface explicitly normalizes and withholds it; otherwise it is part of \(O_t\). Let
\(H_{t-1}=(p_1,O_1,\ldots,p_{t-1},O_{t-1})\), and write the observable process kernel as
\(Q_M(dO_t\mid H_{t-1},p_t)\).

Fix a structural model \(M\), a latent prompt-channel neutralization
\(I_P^{\mathrm{latent}}\), and a checkpoint/training-world replacement \(I_W\) that substitutes a
matched reference state while holding the declared observation interface fixed.
\(I_P^{\mathrm{latent}}\) is not the ordinary visible intervention `do(P=p0)` and is not available as
a black-box query.
For a controlled one-query baseline history and an observable process kernel \(R\), fix a bounded
declared utility \(u\) of the output projection and define
\(\mathcal U(R;p,y)=\mathbb E_R[u(Z,y)\mid p]\). Write
\(U_M(p,y)=\mathcal U(Q_M;p,y)\). For a controlled prompt \(p\), define a source functional such as

\[
\mathsf S_M(p,y)
=
\left(
U_M(p,y)-U_{I_P^{\mathrm{latent}}(M)}(p,y),
U_M(p,y)-U_{I_W(M)}(p,y)
\right).
\]

This functional is relative to the declared \((I_P^{\mathrm{latent}},I_W,Q_0,u)\); it is not a
context-free label for natural historical source. There is a simple scope lemma in a broad
two-channel structural class. Let \(Q_0\) be a neutral history-conditioned observable process law and
let \(Q\) be another such law that is nondegenerate relative to the declared utility:
for at least one \((p,y)\), \(U_Q(p,y)\ne U_{Q_0}(p,y)\). Construct
\(M_P=(R_P=Q,R_W=Q_0,g\text{ selects }R_P)\) and
\(M_W=(R_P=Q_0,R_W=Q,g\text{ selects }R_W)\). In \(M_P\), latent prompt-channel neutralization
replaces selected \(Q\) by \(Q_0\) while checkpoint replacement is inert; in \(M_W\), checkpoint
replacement changes selected \(Q\) to \(Q_0\) while latent prompt neutralization is inert. Both mechanisms implement
exactly \(Q(dO_t\mid H_{t-1},p_t)\) for every reachable history and prompt. Under the declared
interventions their functionals are

\[
\mathsf S_{M_P}(p,y)=(U_Q(p,y)-U_{Q_0}(p,y),0),\qquad
\mathsf S_{M_W}(p,y)=(0,U_Q(p,y)-U_{Q_0}(p,y)).
\]

Latent prompt-channel neutralization changes observed utility only in \(M_P\); matched weight
replacement changes observed utility only in \(M_W\). Therefore their source functionals differ at
an intervention-relevant input even though no adaptive interaction through the declared black-box
interface distinguishes them. If
\(U_Q(p,y)=U_{Q_0}(p,y)\) for every admissible \((p,y)\), there is no nonzero source contrast to
identify and the conclusion is intentionally silent.

The adaptive version follows by induction on the transcript: equality of the complete
history-conditioned kernels above implies that any possibly randomized prompt policy measurable with
respect to \(H_{t-1}\) induces the same joint transcript law. If a preregistered binary source label
is opposite in the two mechanisms, then for any binary classifier
\(\widehat s(H_T)\in\{0,1\}\) the sum of its errors under the two worlds is one, so its worst-case
error is at least \(1/2\). An abstention, if allowed operationally, is counted as an error for this
bound.

This lemma is a generic identification boundary, not a headline novelty claim. Its broad channel
class is intentionally weak. A stronger theorem would realize both mechanisms inside one declared
transformer/training class without hiding an arbitrary lookup table in the channel definitions.
Unless that stronger construction is proved, the paper states only the broad lemma and uses the
paired intervention below for positive empirical identification. In either case it must:

- state the adaptive transcript sigma-algebra and counterfactual source functional;
- state the structural class in which the two constructions live;
- identify exactly which randomized training or checkpoint interventions restore partial
  identification;
- distinguish causal non-identifiability from ordinary estimator error.

### T1b — identification under randomized permutation siblings

Let \(n\ge2\), let \(\Omega_n\) be the set of all bijections from \(n\) keys to \(n\) targets, let
\(\Pi\in\Omega_n\), let \(s\) collect all training randomness, and let
\(\theta(\Pi,s)=\mathcal M(\Pi,s)\) be the checkpoint produced by the frozen training procedure. For
any possible edge \((k_i,y_j)\), define \(p_{ij,1}=T(s_{ij})\) and
\(p_{ij,0}=T(s_\varnothing)\) using the same mechanical grammar as the four-cell design. Then

\[
Y_{ijq}(\Pi,s)
=
U\!\left(\theta(\Pi,s),p_{ij,q},y_j\right),
\qquad
\Delta_{ij}(\Pi,s)=Y_{ij1}(\Pi,s)-Y_{ij0}(\Pi,s).
\]

The assignment mechanism samples complete permutations; it does not assign \(n\) independent edge
treatments. Other edges may affect \(Y_{ijq}\) through shared parameters, so a potential outcome
indexed only by whether edge \((i,j)\) is present is not well defined without an exposure assumption.
This follows the experimental-design distinction between assignment, exposure mapping, and estimand
under interference made explicit by
[Aronow and Samii](https://doi.org/10.1214/16-AOAS1005); the neural setting does not make shared-
parameter interference disappear.

For independent training replicate \(r\), draw an edge-disjoint sibling pair
\((\Pi_r^A,\Pi_r^B)\sim\mathcal G\) and train both checkpoints. Training randomness is independent of
the sampled assignments unless a frozen coupling is explicitly part of \(\mathcal G\). Define the
symmetric pair statistic

\[
\psi_r
=
\frac{1}{2n}\sum_{i=1}^n
\left[
\Delta_{i,\Pi_r^A(i)}(\Pi_r^A,s_r^A)
-\Delta_{i,\Pi_r^A(i)}(\Pi_r^B,s_r^B)
+\Delta_{i,\Pi_r^B(i)}(\Pi_r^B,s_r^B)
-\Delta_{i,\Pi_r^B(i)}(\Pi_r^A,s_r^A)
\right].
\]

The primary causal estimand is the whole-permutation policy effect

\[
\Psi_{\mathcal G}
=
\mathbb E_{(\Pi^A,\Pi^B)\sim\mathcal G,\,s^A,s^B}[\psi_r].
\]

It asks whether coordinates belonging to a checkpoint's own randomized mapping have larger prompt
increments than those coordinates in the matched sibling. It remains defined under arbitrary
cross-association interference, but it is not an association-level direct effect.
Under the same uniform weighting over the \(2n\) exposed associations used in the four-cell
definition, \(I_{\mathrm{pair}}=\mathbb E[\psi_r]=\Psi_{\mathcal G}\); they are two presentations of
one population estimand, not independent evidence. Any alternative weighting must be named.

Under the stronger exposure-sufficiency assumption

\[
\Delta_{ij}(\Pi,s)
=
\widetilde\Delta_{ij}\!\left(\mathbf 1\{\Pi(i)=j\},s\right),
\]

\(\Psi_{\mathcal G}\) reduces to an average edge-exposure effect. Under the bounded-deviation
assumption

\[
\left|\Delta_{ij}(\Pi,s)-
\widetilde\Delta_{ij}(\mathbf 1\{\Pi(i)=j\},s)\right|\le\gamma
\]

for every admissible cell, the displayed four-term statistic differs from its exposure-sufficient
counterpart by at most \(2\gamma\). Report that sensitivity interval rather than claiming point
identification. Near-neighbor keys and targets stress-test the exposure mapping.

The independently trained sibling pair is the inferential block. Targets, prompts, and generation
samples are repeated measurements nested inside it. Power and uncertainty over training randomness
use pair-level summaries such as \(\psi_r\); three training pairs can establish feasibility but not a
credible asymptotic population claim.

### T1c — a synergy counterexample to additive source bits

Let \(\Pi\) be a uniformly random permutation on \(n\) targets, let key \(K\) be uniform and
independent, and let \(Y=\Pi(K)\). Then \(I(Y;K)=0\) and \(I(Y;\Pi)=0\), while
\(I(Y;(K,\Pi))=H(Y)=\log_2 n\). Neither marginal source predicts the target, yet the pair determines
it; “pure synergy” is only a secondary interpretation relative to a declared partial-information
decomposition satisfying marginal/joint consistency. This elementary
counterexample prohibits an additive accounting of “bits from the prompt” and “bits from the
weights.” It motivates interaction contrasts and partial-information analyses, but does not by itself
select one unique decomposition or establish a new information-theoretic measure.

### T1d — opaque-key discovery lower bound

Let the correct coordinate be uniformly distributed among \(n\) opaque nonce keys, and let a query
reveal only whether the submitted key is correct for the target. For an integer
\(0\le q\le n\), an adaptive algorithm with no side information that makes at most \(q\) distinct
queries discovers the key with probability at most \(q/n\). If \(0\le q<n\) and, after \(q\)
failures, it may output one additional unqueried guess, its success probability is at most
\((q+1)/n\). Exchangeability proves the bound: conditional on every failure,
the hidden key remains uniform over the unqueried keys. Therefore the opaque-key arm validates source
controls, enumeration, and query accounting; it cannot demonstrate semantic reverse discovery.
Algorithmic value must come from a compositional-key arm or declared informative feedback.

### T2 — adopted constructive bound and accounting corollary

For any declared prompt class \(\mathcal D\subseteq\mathcal P_\iota\), define

\[
L^{\mathrm{det}}_{\bar c,\mathcal D,\delta}(y;\epsilon)
=\min_{p\in\mathcal D:\,\delta(y,f_{\bar c}(p))\le\epsilon}C_\tau(p).
\]

For a fully specified computable deterministic run context and a prefix-free, computably invertible
typed prompt code,

\[
r_U(y,\epsilon\mid\bar c)
\le L^{\mathrm{det}}_{\bar c,\mathcal D,\delta}(y;\epsilon)+O(1),
\]

and, unconditionally,

\[
r_U(y,\epsilon)
\le K_U(\bar c)
+L^{\mathrm{det}}_{\bar c,\mathcal D,\delta}(y;\epsilon)+O(1).
\]

The proof is constructive: a uniform interpreter decodes \(E_{\tau,\iota}(p)\), simulates the declared
decoder, and emits its reconstruction; the unconditional program additionally carries a
self-delimiting description of \(\bar c\). Under the fixed representations, the additive constant may
depend on the chosen universal machine and uniform interpreters but not on \(p\), \(y\), or
\(\bar c\). Choosing \(\mathcal D=\mathcal P^{\mathrm{read}}_{H,\boldsymbol\eta}(y)\) gives the
readable corollary but no stronger algorithmic-complexity relation; it only restricts witnesses.
Exclude stochastic decoding and opaque hosted APIs from this deterministic theorem. T2b handles a
separate effective exact-output stochastic case. Do not claim the reverse bound without a
bounded-overhead compiler from arbitrary programs into admissible prompts.

This is not a novelty claim. Prompting Complexity defines shortest prompts and gives a weak
model-dependent coding theorem under its self-delimitation assumption; it does not state this
conditional \(K_U(\cdot\mid\bar c)\) upper bound. Aleph uses the elementary constructive simulation
argument here with an explicitly charged prefix-free typed code rather than relying on chat
delimiters to make variable-length payloads prefix-free. Aleph's contribution is to carry the
accounting into a human-measured lossy construct, make the model/interface subsidy explicit, and keep
decoder execution cost separate from researcher search cost.

### T2b — stochastic exact-output mixture bound

Let \(0\le\beta<1\). From the complete effective run description \(\bar c\), require one uniform
procedure to enumerate the exact legal prompt domain, decode its one-codeword-per-object prefix code,
and approximate the finite-output-plus-EOS probabilities \(P_{\bar c}(z\mid p)\). Use the convention
\(-\log_2 0=+\infty\). Kraft's inequality then holds, and define

\[
Q_{\bar c}(z)=\sum_p2^{-C_\tau(p)}P_{\bar c}(z\mid p),\qquad
D_{\bar c}^{\mathrm{Sh}}(z)=\min_p\left\{C_\tau(p)+
\left\lceil-\log_2P_{\bar c}(z\mid p)\right\rceil\right\}.
\]

Then \(Q_{\bar c}\) is a lower-semicomputable semimeasure uniformly from \(\bar c\), and the coding
theorem gives

\[
K_U(z\mid\bar c)\le-\log_2Q_{\bar c}(z)+O(1)
\le D_{\bar c}^{\mathrm{Sh}}(z)+O(1).
\]

Define
\(L^{\mathrm{exact}}_{\bar c,\beta}(y)=
\min\{C_\tau(p):P_{\bar c}(y,\mathrm{EOS}\mid p)\ge1-\beta\}\),
with \(+\infty\) for an empty set. Consequently, if exact success includes EOS, then

\[
K_U(y\mid\bar c)
\le L^{\mathrm{exact}}_{\bar c,\beta}(y)-\log_2(1-\beta)+O(1).
\]

This standard mixture-code corollary is formal positioning, not a novelty claim. It requires an
effective open runtime, exact finite-output/EOS semantics, the charged typed prompt code, and a frozen
randomness law. A high probability assigned only to a distortion ball does not yield the same
single-string bound. For any \(p\) satisfying
\(P_{\bar c}(\{z:\delta(y,z)\le\epsilon\}\mid p)\ge1-\beta\), if that ball is effectively
enumerable and \(1\le|\{z:\delta(y,z)\le\epsilon\}|\le N<\infty\), the same argument gives the
weaker constructive bound
\(r_U(y,\epsilon\mid\bar c)\le C_\tau(p)-\log_2(1-\beta)+\log_2N+O(1)\).
Without the feasible-witness condition and reconstruction or cardinality accounting, no
corresponding claim is made.

### T2c — local compiler invariance, not universal invariance

Let \(g:\mathcal D_1\to\mathcal D_2\) be a target-independent computable translation between two
declared prompt domains. Suppose it preserves the relevant output law or, more narrowly, every
preregistered feasibility decision, and
\(C_2(g(p))\le C_1(p)+a\) for every \(p\in\mathcal D_1\). Then the corresponding restricted oracle
minima satisfy \(L_2^*(y)\le L_1^*(y)+a\). If a reverse translation has overhead \(b\), then also
\(L_1^*(y)\le L_2^*(y)+b\); whenever both minima are finite this is equivalent to
\(-b\le L_2^*(y)-L_1^*(y)\le a\). The readable version additionally requires the translations to
preserve the declared human-eligibility predicate. This is the only invariance available across
tokenizers or interfaces without stronger assumptions: it is local to published compilers and their
overheads, not the universal-machine invariance theorem.

### T3 — budget monotonicity under an append-only trace

For any fixed feasibility predicate \(F\), define

\[
\widehat L^{\mathrm{found}}(S,F)
=
\min_{p\in S:F(p)=1}C_\tau(p),
\]

with \(+\infty\) for an empty feasible set. If
\(S_{A,B_1,\omega}\subseteq S_{A,B_2,\omega}\) and \(F\) is held fixed, then

\[
\widehat L^{\mathrm{found}}(S_{A,B_2,\omega},F)
\le
\widehat L^{\mathrm{found}}(S_{A,B_1,\omega},F).
\]

This does not compare independent reruns, changed seeds, model drift, or candidates reclassified by
additional validation samples.

There is one deliberately narrow consistency result. If the admissible prompt domain is finite, the
decoder and feasibility predicate are deterministic, the candidate archive is append-only, and the
search schedule is complete (every admissible prompt is eventually evaluated), then there exists a
finite budget \(B^*\) after which \(\widehat L^{\mathrm{found}}\) equals the restricted oracle
minimum. An exhaustive toy model can test this contract. Compression continuation, evolutionary
search, and proposer-driven search receive no such guarantee merely from being run longer. A
stochastic search obtains an almost-sure asymptotic discovery statement only after proving persistent
exploration over the finite domain; that statement says nothing useful about practical finite-budget
regret. Human and stochastic feasibility additionally require statistical confirmation, so exhaustive
candidate enumeration alone does not reveal the population oracle exactly.

No open-domain transcript can certify a globally shortest prompt unless it rules out every cheaper
legal candidate or invokes a sound structural lower-bound oracle. If a cheaper candidate remains
unqueried, two evaluators can agree on the whole transcript and differ only by making that candidate
feasible. Global-shortest language is therefore prohibited outside exhaustive or lower-bounded
domains.

### T4 — finite threshold paths and Pareto sets

For a finite archive of candidates with complete finite objective vectors, with every other
constraint and estimator held fixed, define

\[
D_S^*(b)=\min_{p\in S:\,C_\tau(p)\le b}d(p),\qquad
L_S^*(\epsilon)=\min_{p\in S:\,d(p)\le\epsilon}C_\tau(p).
\]

When the minima are attained, \(D_S^*(b)\le\epsilon\) if and only if
\(L_S^*(\epsilon)\le b\). Both generalized-inverse views are non-increasing staircases with
breakpoints among observed values. More precisely, any finite list of cost--distortion points whose
integer code lengths satisfy Kraft's inequality and whose distortion values are attainable under the
fixed \(\delta\) can be realized by an abstract prefix code and decoder; arbitrary values additionally
require a purpose-built output space and distortion function. Therefore discreteness alone gives no
smoothness, convexity, or diminishing-returns law. A finite
nonempty complete candidate set has a finite nonempty Pareto archive. With two or more objectives it
is a partial order, not a canonical one-dimensional path; weighted sums can miss unsupported
nondominated points. Use epsilon constraints or enumerate nondominated candidates for analysis. Only
the preregistered projection \(\Gamma_{S,\Phi}\) is called a compression path in the interface.

For a deterministic finite candidate set, every nondominated **objective vector** can be recovered by an
epsilon-constraint problem when the other objective bounds are set to that point's values and ties
are resolved with the declared secondary objectives. Distinct candidates with duplicate vectors are
not all recovered under one fixed tie-break. This is why Aleph uses feasibility thresholds
instead of a hidden weighted sum. It does **not** imply that successive projected points are connected
by one edit, that the archive is convex, that all breakpoints are found under finite search, or that
the frontier is stable under a changed tokenizer or run context. Preserve two different graph
objects: the candidate-lineage DAG records how search moved, while \(\Gamma_{S,\Phi}\) is a
cost-ordered view over observed candidates. Neither may be rendered as a smooth interpolated curve or
promoted to the unknown oracle frontier.

## Readable-coordinate benchmark

Natural pretrained models and natural texts are the primary evidence domain for the accessibility
claim. Build matched target groups that separate canonicality from surface content:

1. a canonical exact passage that has a public title, author, or conventional reference;
2. a meaning-preserving paraphrase of that passage;
3. a newly authored composition matched for topic, style, length, and language;
4. an entropy-matched synthetic or token-permuted control.

Add structured outputs, executable behaviors with tests, and multilingual target groups only after the
text protocol is stable. Every target records provenance, rights status, contamination audit, language,
token counts under every evaluated tokenizer, and the transformations connecting its matched group.

This design gives a sharper falsifiable prediction than “familiar targets are easier.” Under strict
exact reproduction, canonical passages should admit shorter readable coordinates than their matched
paraphrases and novel compositions if the model exposes public-reference structure. Under semantic
distortion, that gap should shrink. High-entropy controls should approach explicit reconstruction.
Failure of these ordered predictions is informative and must remain in the result.

For each target, report the whole observed path: coordinate type, length, fidelity, stability,
surface readability, target-link legibility, provenance profile, tested copy, token-level residuals, and breakpoints at
which particular target spans fail. Human-readable and raw branches share evaluation metrics but not
mutation constraints or certification labels.

### Accessibility search baselines

Budget-match methods by target-model forward passes or estimated FLOPs and separately report proposer
tokens, evaluated tokens, wall-clock, and peak memory. Call count alone does not fairly compare
gradient methods, local mutations, and expensive proposer models.

- identity/Explicit Reconstruction and target-prefix or suffix controls;
- random and length-stratified enumeration;
- deletion and substitution hill climbing;
- LLMLingua-family and discrete-RL prompt compressors initialized from the same explicit or
  human-authored long prompt, with target-copy provenance reported rather than hidden;
- beam or evolutionary search;
- MiniPrompt/ACR as the mandatory closest white-box target-first length-search baseline;
- ARCA/GCG-style white-box optimization where compatible;
- Reverse Prompt Engineering-style recovery, labeled `RPE-adapted` because Aleph searches for any
  short coordinate rather than the unknown original prompt;
- ALPACA AGAINST VICUNA-style low-overlap black-box rejection sampling for memorized targets;
- dynamic soft-prompt extraction as a non-readable white-box ceiling where compatible;
- a strong general text optimizer such as GEPA or TextGrad;
- EvoPrompt-style population search, and MIPROv2 only as a controller over a finite operator or
  template menu rather than as an open-text searcher;
- Aleph compression-continuation with residual repair.

No reviewed implementation is the Aleph searcher. The reproducibility study freezes both the paper
configuration and the exact code snapshot because several current repositories have moved beyond the
published algorithm:

| system and frozen snapshot | what the implementation actually contributes | what Aleph must not inherit |
| --- | --- | --- |
| [ACR/MiniPrompt `bf3ba2e`](https://github.com/locuslab/acr-memorization/tree/bf3ba2e7bf224482928fba42cd79c295796c0237) | GCG-based exact-target optimization across prompt lengths and an empirical adversarial-compression baseline | deterministic greedy success treated as reliability, heuristic best-found treated as a minimum, white-box-only scope, and compression treated as identified source or memorization ground truth |
| [ARCA `04b9306`](https://github.com/ejones313/auditing-llms/tree/04b9306f17b01df1afd8f637038928bafd654115) | gradient-ranked, exact-forward reranked coordinate substitution for fixed-length target search | hard-coded CUDA placement, no complete seed/trace, and teacher-forced success standing in for sampled generation |
| [GCG `098262e`](https://github.com/llm-attacks/llm-attacks/tree/098262edf85f807224e70ecd87b9d83716bf6b73) | batched top-gradient token substitution and a strong raw-token white-box baseline | fixed suffix length, tokenizer-specific silent errors, jailbreak-specific success rules, and one batch counted as one ordinary query |
| [RPE `894df3d`](https://github.com/hanklee97121/RPE_Reverse_Prompt_Engineering/tree/894df3dc717621e461ba03a74fc7d346b391fea1) | output-conditioned candidate generation and iterative critique/rewrite | hard-coded five-candidate loops, unbounded format retries, floating model aliases, or the false label `crossover` for independent rewrites |
| [TextGrad `75e912e`](https://github.com/zou-group/textgrad/tree/75e912e210864b61999781778cdf756d4468120f) | textual feedback propagated through a declared computation graph and whole-string rewrites | test inspection during optimization, optional validation, incomplete cache keys, or a single greedy path as a frontier |
| [GEPA `d771eb2`](https://github.com/gepa-ai/gepa/tree/d771eb21b5dd3228bc3f567293d2ccfc423fc900) | resumable runs, lineage, explicit metric-call budgets, proposal traces, and split-aware caches | `valset=trainset` fallback, caching one stochastic draw as repeated evidence, and conflating instance-wise illumination with Aleph's metric Pareto archive |
| [EvoPrompt `94caff3`](https://github.com/beeevita/EvoPrompt/tree/94caff336555df99acc5c338c7930c40cc550ad9) | population selection plus GA/DE-style LLM rewrites | prompt-only cache keys, generations mislabeled as compute, repeated full-dev adaptation, and incomplete RNG checkpoints |
| [DSPy/MIPROv2 `8de96ea`](https://github.com/stanfordnlp/dspy/tree/8de96eaa999976f98b7cdd3c5778bc1eb10769c4) | TPE over finite instruction/demo/operator choices | order-dependent split defaults, `seed=0` overwrite, ephemeral studies, or treating a finite proposal pool as open-text optimization |

The MiniPrompt adapter needs special care because it is both the closest baseline and a source of
measurement traps. At the frozen commit, `minimize_prompt` begins at five free tokens, increases
failed lengths by five while expanding the optimization steps, and only after a success decrements
length one token at a time. Each length receives one stochastic initialization. A failed GCG run is
therefore not evidence that the length is infeasible, skipped intermediate lengths may contain a
solution, and the returned value is a heuristic constructive upper bound. Its success check is
teacher-forced per-token argmax; the separately logged free generation is capped at 20 new tokens and
does not decide success. The reported ratio counts only free tokens, omitting fixed system/input/chat
scaffolding, so some experiments are conditional compression even when displayed as absolute ACR.
The search also permits opaque/special tokens and offers no readable branch. Aleph's reproduction
must preserve the published baseline while adding a clearly labeled audited adapter: multiple
restarts and budget curves, true-generation replay in a fresh process, an explicit legal-token set,
complete side-information accounting, and failure-inclusive uncertainty. It may not silently change
the baseline and still call the result a paper replication.

This audit produces a positive architecture decision: borrow GEPA's recoverability and lineage ideas;
make MiniPrompt the closest white-box empirical baseline; use ARCA/GCG as lower-level fixed-length raw
comparators; expose TextGrad, EvoPrompt, RPE-adapted, and GEPA through proposal adapters; and let
MIPROv2-style SMBO choose only finite operator policies.
Aleph owns the variable-length archive, eligibility predicates, confirmation boundary, and scientific
receipts. Every imported baseline manifest freezes repository SHA, local patch hash, container digest,
model and tokenizer revisions, chat-template bytes, metric revision, and dataset-split hashes.

Budget matching uses access tiers, not a misleading universal query count:

1. black-box readable methods;
2. black-box unrestricted methods;
3. logits-access methods;
4. gradient-access methods.

Every arm receives a preregistered vector budget

\[
B=(B_{\mathrm{eval,call}},B_{\mathrm{eval,tok}},B_{\mathrm{prop,call}},B_{\mathrm{prop,tok}},
B_{\mathrm{backward,tok}},B_{\mathrm{human}},B_{\mathrm{wall}}),
\]

so unlimited proposer compute cannot hide behind a matched evaluator count. Within black-box tiers the
primary matching unit is target-evaluator input-plus-output tokens with a call cap; within logits tiers
it is teacher-forced target-evaluator token-equivalents; within gradient tiers it is the declared
forward-plus-backward proxy below. Tolerances are frozen per tier, and comparisons across tiers are
reported as access tradeoffs rather than “matched compute.” Human confirmation is held equal or
reported separately and is never paid from model-call budget.

For each physical model (i), record forward token-equivalents (T_{f,i}), backward
token-equivalents (T_{b,i}), and, only when parameter count (P_i) is known, the declared dense-model
proxy

\[
F_{\mathrm{proxy}}=\sum_i(2P_iT_{f,i}+4P_iT_{b,i}).
\]

This is an accounting proxy, not a profiler measurement. Hosted-model FLOPs remain `unknown` rather
than inferred. Every receipt separately records provider requests, completions, task rollouts,
input/output/cached-input tokens, proposer/evaluator/target roles, wall time, GPU-seconds, peak memory,
retries, failures, and actual billed cost when available. A batched gradient step and one API request
therefore cannot be called matched compute merely because each increments a counter once.
Each batch element contributes its prefill, teacher-forced target, and decoded tokens to
\(T_{f,i}\); cached prefixes are reported separately. A backward pass contributes its differentiated
tokens once to \(T_{b,i}\), while the forward work that produced its activations remains in
\(T_{f,i}\), preventing either omission or double-counting. Gradient candidate reranking and sampled
generation are additional forward work, not free consequences of one optimizer step.

Implement the model-dependent nucleus-plausibility domain proposed by Prompting Complexity as a
formal construct baseline. On the same candidates, compare its membership with the two-stage human
protocol, the resulting frontier changes, and each construct's predictive validity for held-out human
judgments and search transfer. This is necessary because “human-readable prompt plus practical
search” otherwise risks being only an implementation of that paper's stated agenda.

Each method receives the same target information allowed by its declared access regime. Report a
separate access-matched comparison when a method requires logits or gradients.

## Controlled source-attribution benchmark

### Association construction

The benchmark needs ground truth that natural text cannot provide.

1. Sample high-entropy target strings or structured sequences that are extremely unlikely to occur in
   pretraining.
2. Pair each target with a natural-looking key, an opaque key, and a compositional key.
3. Draw two deranged key-target permutations for each sibling pair. Both models see every key, every
   target, the same templates, token marginals, exposure counts, optimizer steps, and batch schedule;
   only the key-target pairing changes.
4. Vary exposure count, target entropy, key length, compositionality, and interference from near-neighbor
   keys.
5. Preserve evaluation-held-out association groups for calibration, search development, and final
   certification. “Held out” here means unused for method development, not absent from the controlled
   training exposure that creates the source intervention.

A permutation-sibling design is preferable to “fine-tuned versus untouched base” or a simple
half-split. Model A learns permutation \(\pi_A\), Model B learns a matched derangement \(\pi_B\), and
assignments flip across training seeds. This controls key frequency, target frequency, compute, and
generic fine-tuning drift while giving every association an exposed and association-negative world.
Checkpoint selection rules must be frozen on development associations and may not depend on test
target performance.

### Orthogonal split contract

The benchmark records four distinct axes that must never be collapsed into one ambiguous `train/test`
field:

| Axis | Development use | Final-certification rule |
| --- | --- | --- |
| controlled exposure | all declared associations are assigned within a training permutation | exposure and assignment receipts are immutable |
| detector calibration | choose adversary thresholds and operating points | disjoint association group; no threshold changes afterward |
| search development | tune operators, budgets, prompts, and hyperparameters | final group becomes visible to the frozen algorithm only when its run starts |
| certification | none | fixed-checkpoint accessibility uses fresh generations and raters on that checkpoint; source-population claims use unseen trained pairs in a separate transfer analysis; neither feeds back to search |

Templates, target generators, human-rater pools, training seeds, search seeds, and decoding seeds each
receive their own split identifiers. “Untouched” is prohibited unless the document states which axis
was untouched.

### Prompt classes with known expectations

Each held-out target must include at least:

- exact target copy;
- partial prefix and suffix copy;
- paraphrase and translation;
- encoded copy: base64, substitution cipher, acrostic, transliteration;
- exposed natural key;
- exposed opaque key;
- key plus misleading payload;
- matched wrong-association key;
- generic reconstruction instruction;
- unrelated prompt.

These classes test both the source estimator and the prompt-only adversary suite.

### Model stages

Use open checkpoints with reproducible tokenizers and training access. Exact model families are an
implementation decision, but the evidence ladder should be:

1. **toy exhaustive model:** a tiny finite vocabulary where the global prompt optimum can be enumerated;
2. **small paired checkpoints:** enough capacity to learn controlled associations over multiple
   training seeds;
3. **second family or scale:** tests whether results are architecture- or size-specific;
4. **natural pretrained checkpoints:** primary evidence for accessibility, observational external
   validity only for causal source claims;
5. **closed hosted models:** optional demonstration, never causal source ground truth.

### Source-search and attribution baselines

All accessibility methods above remain in the source-search comparison, now budget-matched by paired
evaluator compute. Add source-specific controls:

- key-only oracle;
- trigger-inversion methods represented by DBS and the search procedure from GPTs Don't Keep Secrets;
- the unconstrained Aleph searcher without sibling information;
- Aleph's source-aware constrained variant.

The known correct key is an **oracle ceiling/control**, not a baseline a discovery method is expected
to beat. Primary comparisons are against methods that do not receive the hidden mapping. A successful
source-discovery claim must recover useful coordinates when the mapping is hidden and must transfer to
independently trained same-mapping replicas; merely returning an enumerated planted key is trigger
recovery, not a new contribution.

Source and provenance baselines must include unigram/trigram overlap, edit distance, embedding
similarity, a frozen language-model judge, control-model likelihood, canary exposure or extraction
scores where applicable, probabilistic discoverable extraction, Min-K%-style likelihood signals,
QUIP-style corpus grounding where the reference corpus is legally available, and representative
context-attribution methods. In controlled open-weight stages, add Datamodels/TRAK-style
training-counterfactual attribution when compute permits and label it as a white-box baseline rather
than black-box evidence. This comparison answers whether paired intervention adds anything beyond
existing memorization, contamination, grounding, or attribution signals.

The proposer may see the target, but prompt-copy channels must be evaluated by independent probes and
the held-out paired model. Proposer and evaluator calls require separate ledgers.

## Discovery and confirmation contract

Candidate discovery, threshold calibration, and final confirmation use the orthogonal split contract
above. Repeatedly searching and reporting the best score on the same model and samples creates
winner's curse and is not acceptable evidence.

The default design is sample splitting: after discovery, freeze a bounded set of candidates and run a
one-shot confirmation on fresh generations from the same fixed checkpoint plus protocol-specific
human raters. Surface raters are target-blind. Link raters see only the preregistered balanced target
alternatives and remain blind to model output, algorithm, source assignment, and search score.
Family-wise error across frozen candidates and primary constraints is controlled by a preregistered
procedure. If confirmation data must be reused or sample allocation is adaptive, replace ordinary
fixed-sample intervals with time-uniform confidence sequences or e-values and log alpha allocation
across candidates, constraints, and stopping times. Changing only a decoding seed does not erase
adaptive selection.

An independently trained replica changes \(c\) and therefore cannot certify a fixed-checkpoint
\(L^{\mathrm{read}}_{c,H,\delta}\). Same-mapping and assignment-flip replicas are a separate transfer
or source-population analysis, required only for claims over training randomness and analyzed with the
trained pair as the inferential block.

The search evaluation separates domain size from source-access tier:

- **closed world:** a finite admissible key grammar can be enumerated, providing the true frontier and
  exact regret;
- **open world:** the candidate language is not exhaustively enumerable at experimental budget;
- **role-labeled selective compression:** the evaluator exposes association-relative positive and
  negative roles, so the task tests compression under a known intervention contrast, not hidden-
  mapping discovery;
- **pair-blind discovery:** the searcher receives the target and an unordered checkpoint pair, emits a
  prompt plus predicted orientation, and never receives held-out mapping labels. Discovery is scored
  only on unseen targets and same-mapping training replicas. Endpoint order and handles are randomized,
  latency and error fields are normalized, and cross-target caches are cleared so transport metadata
  cannot reveal the hidden orientation.

Opaque nonce keys are useful for source validation but may be undiscoverable in open search.
Compositional keys are required to test genuine reverse discovery.

### Certification semantics

Under the default fresh-confirmation regime, candidate selection, one candidate-selection rule per
target, thresholds, and endpoints are frozen before any confirmation observation is collected.
Simultaneous fixed-sample intervals cover every candidate and constraint that can enter the final
claim. Search-time intervals remain descriptive and may not be relabeled as certification.

If the project instead uses sequential confirmation, each candidate-constraint hypothesis \(h\)
receives a predictable error budget \(\alpha_h\) before its first confirmation observation, with

\[
\sum_h \alpha_h\le\alpha_{\mathrm{conf}}.
\]

Let \(\vartheta_h\) be the population parameter indexed by candidate-constraint hypothesis \(h\).
Maintain a confidence sequence \([L_{h,t},U_{h,t}]\) satisfying

\[
\Pr\!\left(\forall t\ge1:\vartheta_h\in[L_{h,t},U_{h,t}]\right)
\ge 1-\alpha_h.
\]

Candidates introduced online receive alpha through a preregistered summable spending schedule before
their first confirmation sample. Bernoulli generation success can use exact or mixture confidence
sequences; bounded human and adversary scores need bounded-score sequences. Target log likelihood
requires preregistered clipping, finite-moment/tail assumptions with a valid robust estimator, or is
reported as descriptive even under fixed sampling; fixed sample size alone does not create coverage
for an unbounded score. Repeated outputs
from one checkpoint quantify decoding uncertainty only, not training uncertainty.

Every stochastic threshold has either a preregistered indifference margin or a finite sampling cap
with mandatory `indeterminate`. Exact classification cannot have uniformly finite sample complexity as
the true parameter approaches the boundary, and a confidence-sequence rule need not terminate on the
boundary. For a frozen archive, the certifier reports simultaneous lower/upper archive-relative
shortest-cost bounds and the unresolved cheaper candidates; only exhaustive-prefix or separately
proved structural evidence can upgrade that interval to a global certificate.

## Readable-coordinate search and source-aware variant

The first working method serves Aleph's original object. It must search one archive and derive
readable/raw views for a fixed target model before the source intervention is added. The paired-model method is a controlled
variant, not a replacement for that core search.

### A. Readability-aware reverse search

Use an append-only candidate archive and epsilon constraints rather than a hidden scalar score. Seed
the archive with explicit reconstruction, target-free generic instructions, human-authored
descriptions and references, length-stratified random prompts, and the outputs of each comparison
optimizer. During discovery, a frozen readability surrogate may reject obviously malformed strings,
but only the two-stage human protocol on the confirmation split establishes membership in
\(\mathcal P^{\mathrm{read}}_{H,\boldsymbol\eta}(y)\).

The Aleph-specific search hypothesis is **compression continuation with residual repair**, inherited
from the early MLX prototype rather than a generic evolutionary loop:

1. start from Explicit Reconstruction or another long feasible coordinate;
2. compress it by deletion, abstraction, bibliographic-reference substitution, or raw-token edits;
3. identify what the shorter prompt no longer recovers, using target-token NLL when logits exist or
   aligned output-error spans in black-box mode;
4. add back the smallest cue that repairs the residual;
5. use each feasible shorter coordinate as the seed for the next budget;
6. preserve every branch and breakpoint in the archive instead of rewriting a monotone curve.

This turns Aleph's question “what fails first as the prompt shrinks?” into an algorithm and an
analysis. Ablate continuation, residual localization, repair, readable/raw branching, and each
mutation family separately.

The search loop is multiobjective:

```text
seed append-only archive with controls and budget-matched baseline candidates
for each discovery round:
  select parents from the observed nondominated set and uncertain boundary
  mutate by deletion, abstraction, reference substitution, recombination, and raw-token edits
  reject only malformed or exact-duplicate prompts without evaluator calls
  evaluate the fixed target model and record every output, cost, failure, and random seed
  run the frozen Pilot A prompt-recoverability suite on every survivor
  append candidate lineage and provisional metrics; never rewrite an observation
freeze a bounded candidate set before confirmation
confirm with fresh model samples and protocol-specific blinded raters
return the observed nondominated archive with per-candidate confirmation labels
```

The first implementable policy is `hybrid-pareto-v0`, a black-box variable-length search. It begins
with three seed families—Explicit Reconstruction, target-to-description readable seeds, and
empty/random/null controls—and selects parents by length niche and archive scarcity rather than one
global score. Its frozen operator schedule contains `delete_token`, `delete_span`,
`compress_rewrite`, `reference_substitute`, and `repair_insert`; a later white-box access tier may add
`token_substitute`. Operators declare required capabilities, proposal mode, and expected length
effect; they do not declare a candidate's scientific readable/raw/tested-noncopy membership. A
weighted acquisition score may schedule work but may not replace the archive's partial order.

Pareto elitism is not complete: the only path to a better coordinate can pass through a presently
dominated or infeasible bridge. `hybrid-pareto-v0` therefore reserves a frozen exploration share for
an all-candidate reservoir or full-support proof queue, and one-replicate screening cannot permanently
discard a near-threshold candidate without the declared racing rule. `levin-edit-v0` receives a
theorem-backed reachability receipt only for deterministic tree search with a finite action set, a
deterministically recognizable goal set, and a proper path policy \(\pi\) satisfying
\(\pi(n_0)=1\) and \(\pi(n)=\sum_{n'\in\mathcal C(n)}\pi(n')\); some goal must have positive policy
mass. Expanding nodes in increasing \(d_0(n)/\pi(n)\) order, with no state merging or only the
Markovian state cuts specified by
[Orseau et al.](https://proceedings.neurips.cc/paper/2018/file/52c5189391854c93e8a0e1326e56c14f-Paper.pdf),
LevinTS expands at most
\(\min_{n\in\mathcal N^g}d_0(n)/\pi(n)\) nodes before a goal. This is a node-expansion bound, not a
bound on evaluator calls, wall time, money, confirmation, or global prompt optimality; stochastic LLM
rewrites are outside it. `luby-restart-v0` is theorem-backed only for independent restarts of a Las
Vegas procedure whose returned answers are always correct. In the discrete-time setting of
[Luby, Sinclair, and Zuckerman](https://www.cs.utexas.edu/~diz/pubs/speedup.pdf), the universal
schedule has expected runtime \(O(\ell_A\log\ell_A)\), where \(\ell_A\) is the infimum expected
runtime over restart strategies. No restart guarantee is claimed for a noisy or fallible success
test. Fixed-pool bandit or Pareto-identification methods begin only after the candidate set is
content-addressed and frozen; they control selection/estimation error inside that pool, never the open
discovery gap.

Evaluation is staged. One cheap discovery replicate screens a valid proposal; only candidates capable
of changing the provisional archive receive additional discovery replicates. When the search budget
is exhausted, the searcher content-addresses and freezes its bounded shortlist, cannot modify it, and
has no read access to the confirmation namespace. A separate certifier
uses fresh request identities, decoding randomness, generation samples, and blinded human judgments.
If none pass, the valid result is `no confirmed candidate`, not the best failed candidate. ARCA/GCG
may supply proposals or NLL screening in their declared access tier, but every final candidate passes
sampled-generation confirmation. Only a candidate entering the readable view must also pass both
human thresholds; raw candidates retain descriptive human results without being rejected for
unreadability.

Minimum mechanism ablations are fixed before Pilot A:

- deletion-only, rewrite-only, repair-only, and the full operator set;
- fixed-length substitution versus variable-length editing;
- scalar parent scheduling versus the metric Pareto archive;
- current-best parent versus length-niche/Pareto sampling;
- one-shot evaluation versus adaptive discovery racing;
- sampled-generation-only versus target-NLL screening where logits exist;
- target-copy filter off, surface-only, and the complete versioned channel vector;
- Explicit Reconstruction, human-readable description, and random-restart seed families;
- same-model self-compression versus an external proposer and model-independent mutations;
- one, three, and five search seeds; readable versus raw branches; and naive best-validation versus
  independent confirmation.

Report confirmed shortest-found cost, confirmed discovery rate, confirmation failure rate,
archive hypervolume under a frozen reference box, discovery probability across
search seeds, error/timeout rate, and calls/tokens/FLOPs-proxy cost curves. In the toy finite domain,
also report regret to the exact optimum. On open domains, a union-of-all-methods best-known value may
be reported only as a descriptive reference, never as the unknown oracle.

There is no canonical “area under” a vector budget. If an anytime area is used within one access tier,
the preregistration freezes one resource axis, linear or log measure, normalization interval, and
no-discovery value; otherwise the area is omitted. Jointly report prompt cost, discovery probability
over restarts, proposal-policy surprisal or reach receipt where defined, and actual expansions so a
short coordinate is not mistaken for an easy-to-find coordinate.

This algorithm must expose at least two views: a readable frontier and a raw-coordinate frontier. The
primary output is not one weighted winner but the observed nondominated archive with per-candidate
confirmation labels, its declared
\(\Gamma_{S,\Phi}\) projection, and
\(\widehat L^{\mathrm{read,conf}}_{c,H,\delta,A,B,\omega}\). Search can use the target to propose
candidates, but that access is part of the method and its target-bearing proposer tokens are charged
and checked by \(\operatorname{TraceIntegrity}(\mathcal T_{A,B,\omega})\).

The original same-model proposer/evaluator setup is a scientifically interesting **self-compression
arm**, not merely an implementation mistake. It confounds proposal quality with evaluation if used
alone, so compare it against a frozen external proposer and model-independent mutation operators.
Never let the evaluator's target access or a fallback target slice pass unlogged into a supposedly
noncopying candidate.

### B. Controlled source-aware search

In a permutation-sibling benchmark, add constraints that favor association-selective coordinates. For
the following **role-labeled selective-compression** object, positive and negative roles are supplied
to the evaluator; its result cannot be reported as hidden-mapping discovery. The pair-blind task must
instead search an unordered pair, predict orientation, and use a held-out mapping label only in the
certifier. For
association \(a\) in fixed pair \(r\), run contexts \(c_{ra}^+\) and \(c_{ra}^-\), negative-world success ceiling \(q_-\), source-contrast threshold
\(\kappa\), channel thresholds \(\boldsymbol t^{\mathrm{copy}}\), and stability floor \(\zeta\).
The sibling contexts share \(\tau\), \(\iota\), \(\mathcal P_\iota^{\mathrm{text}}\), rendering,
and all evaluation fields; they differ only in the declared checkpoint/training world. This makes the
shared prompt domain and \(C_\tau\) well-defined. Define the open-search oracle object

\[
L^{\mathrm{sel,open}}_{c_{ra}^+,c_{ra}^-,H,\delta,\mathcal V_{\mathrm{copy}}}
\left(y_a;\epsilon,\beta,\boldsymbol\eta,q_-,\kappa,\boldsymbol t^{\mathrm{copy}},\zeta\right)
=
\min_p C_\tau(p)
\]

subject to

\[
p\in\mathcal P^{\mathrm{read}}_{H,\boldsymbol\eta}(y_a),\quad
\rho_{c_{ra}^+,\delta}(p;y_a,\epsilon)\ge 1-\beta,\quad
\rho_{c_{ra}^-,\delta}(p;y_a,\epsilon)\le q_-,
\]

\[
A_{ra}^{\mathrm{open}}(p)\ge\kappa,\quad
\ell_j(p,y_a)\le t_j^{\mathrm{copy}}\ \forall j\in\mathcal V_{\mathrm{copy}},\quad
s_{c_{ra}^+,\nu,\delta}(p;y_a,\epsilon)\ge\zeta.
\]

For an explicit-slot candidate value \(s\), define the pair- and association-level quantity

\[
A_{ra}^{\mathrm{slot}}(s)=
\left[U(\theta_{ra}^{+},T(s),y_a)-U(\theta_{ra}^{+},T(s_\varnothing),y_a)\right]
-\left[U(\theta_{ra}^{-},T(s),y_a)-U(\theta_{ra}^{-},T(s_\varnothing),y_a)\right].
\]

Define the clipped teacher-forced product
\(\widetilde P^{\mathrm{TF},\lambda}_\theta(y_{a,1:n}\mid p)
=\prod_{t=1}^n\max\{P_\theta(y_{a,t}\mid p,y_{a,<t}),\lambda\}\). With the shared
tokenizer/rendering contract,
\(n_\tau(y_a)A_{ra}^{\mathrm{slot}}(s)\) is the log of its ratio-of-ratios:

\[
\log_2
\frac{\widetilde P^{\mathrm{TF},\lambda}_{+}(y_{a,1:n}\mid T(s))
/\widetilde P^{\mathrm{TF},\lambda}_{+}(y_{a,1:n}\mid T(s_\varnothing))}
{\widetilde P^{\mathrm{TF},\lambda}_{-}(y_{a,1:n}\mid T(s))
/\widetilde P^{\mathrm{TF},\lambda}_{-}(y_{a,1:n}\mid T(s_\varnothing))}.
\]

If clipping never activates this is the ordinary teacher-forced target-prefix likelihood
ratio-of-ratios. It omits EOS unless EOS is explicitly added to \(U\), and is a model-comparison
effect rather than full sequence-generation probability, mutual information, or a count of
parameter-resident bits.

The explicit-slot analogue constrains \(p=T(s)\) with
\(A_{ra}^{\mathrm{slot}}(s)\ge\kappa\) and is labeled \(L^{\mathrm{sel,slot}}\).
\(I_{\mathrm{pair}}\) and \(\Psi_{\mathcal G}\) remain population aggregates and never substitute for
a candidate-level constraint. Each threshold appears in the notation because each changes the
feasible set. Trace integrity is deliberately absent from both oracle objects because it is a
property of a search run, not of prompt \(p\).

For a frozen finite-budget archive, let
\(\operatorname{Cert}^{\mathrm{sel}}(p;\epsilon,\beta,\boldsymbol\eta,q_-,\kappa,
\boldsymbol t^{\mathrm{copy}},\zeta)\) denote the simultaneous confirmation rule containing the corresponding
lower and upper bounds. The measurable found statistic is

\[
\widehat L^{\mathrm{sel,open,conf}}_{
c_{ra}^+,c_{ra}^-,H,\delta,\mathcal V_{\mathrm{copy}},A,B,\omega}
\left(y_a;\epsilon,\beta,\boldsymbol\eta,q_-,\kappa,\boldsymbol t^{\mathrm{copy}},\zeta\right)
=
\min_{\substack{
p\in S^{\mathrm{freeze}}_{A,B,\omega}:\\
\operatorname{Cert}^{\mathrm{sel}}(p;\cdot)=1,\\
\operatorname{TraceIntegrity}(\mathcal T[p])=1
}}
C_\tau(p).
\]

Here \(\mathcal T[p]\) is the lineage-closed subtranscript containing every ancestor candidate,
proposer and evaluator call, cache read, fallback, and manual action that could affect \(p\).

An empty feasible set has value \(+\infty\) as a preregistered decision loss. Report the confirmed
discovery indicator and, separately, best-found cost conditional on discovery. Failure to discover in
an open heuristic search is not a censored observation of the unknown oracle length and creates no
lower bound on it.

Discovery may allocate samples adaptively near constraint boundaries, but those intervals are
provisional. The label `confirmed` is reserved for a frozen candidate that passes the independent
confirmation design or an explicitly anytime-valid procedure. A fallback that copies target text is
an explicit reconstruction control and may never silently enter the tested-noncopy archive.

## Metrics and statistical analysis

### Primary accessibility metrics

- confirmed readable-coordinate discovery rate at fixed target-model compute;
- conditional shortest confirmed found cost among discoveries, paired with the unconditional discovery
  indicator; \(+\infty\) may be used only as a preregistered decision loss;
- the full observed nondominated archive with per-candidate confirmation labels, not only a selected
  point;
- confirmed compression gain against explicit reconstruction;
- the readable-versus-raw found gap under matched search budgets;
- search regret against the exhaustive optimum in a finite toy domain;
- cross-run, cross-model, and cross-tokenizer rank stability of target accessibility;
- failure-inclusive coverage.

The primary method comparison is Aleph versus the strongest non-oracle reverse-search baseline at
matched compute. The headline claim is about improved confirmed discovery and shortest-found cost,
not about a statistically certified dominance relation or the source classifier.

### Secondary source metrics

- pair-level whole-permutation policy effect \(\Psi_{\mathcal G}\) and its sensitivity bounds;
- source-separation AUROC and AUPRC over preregistered prompt classes;
- calibration error and false-positive rate at the preregistered operating point;
- explicit-slot interaction \(I_{\mathrm{pair}}\), fixed-pair contrast
  \(A_{ra}^{\mathrm{open}}(p)\), and cross-replica transfer \(\Psi_A^{\mathrm{open}}\);
- source-selective coordinate discovery-rate difference between the constrained variant and the
  strongest non-oracle source-unaware baseline;
- transfer of frozen candidates to unseen same-mapping and assignment-flip training replicas.

### Secondary metrics

- exact-match generation probability;
- target-token NLL and per-token exposure gap;
- semantic similarity for natural targets;
- query count, proposed tokens, evaluated tokens, forward/backward compute, wall-clock, hardware
  time, and peak memory;
- archive diversity and candidate lineage depth;
- cross-seed and cross-checkpoint rank stability;
- cross-model prompt transfer matrices, reported as external validity rather than provenance truth.

### Statistical rules

- use paired per-target comparisons for algorithms evaluated on the same fixed checkpoint and target;
- keep all timeouts, invalid outputs, refusals, and exhausted searches in the denominator;
- separate training, search, validation, and target-group seeds;
- use cluster or hierarchical bootstrap when targets share templates or generators;
- correct or control the family of primary comparisons declared in advance;
- report distributions and intervals, not only aggregate means;
- freeze thresholds on calibration data before evaluating held-out targets;
- publish negative and null results;
- analyze every randomly assigned target under intention-to-treat; never condition the primary result
  on the exposed model already passing a success screen;
- treat an independently randomized and trained sibling pair as the inferential cluster for claims
  over training interventions;
- treat associations, candidates, templates, and decoding samples as repeated measurements nested
  inside that pair rather than independent causal replicates;
- construct uncertainty from the appropriate level: target comparisons for fixed-model search,
  pair-level summaries for training randomness, and fresh samples or anytime-valid sequences for
  adaptive confirmation;
- isolate training-pair, search-seed, human-rater, and decoding uncertainty rather than pooling them.

## Decisive pilot and stop conditions

The pilots are not a leaderboard. They separately test whether Aleph's original empirical object can
be measured and whether the source layer earns its place in the same paper.

Before either pilot starts, every numbered advance condition is compiled into a frozen decision
record naming its estimand/statistic, inferential unit, direction, minimum effect or equivalence
margin, uncertainty and multiplicity rule, missing/excluded/failure treatment, and
`pass|fail|indeterminate` mapping. Thresholds may be selected on a disjoint calibration/development
split but never after viewing held-out outcomes. Undefined or indeterminate conditions do not pass.
The Pilot A method endpoint is a lexicographic hurdle: confirmed discovery must meet its frozen
noninferiority margin \(m_D\), then paired cost reduction on jointly discovered targets must exceed
\(m_C\); if the joint set is too small under the frozen rule, the result is indeterminate. Mandatory
diagnostic reports do not count as gates merely because they were produced.

### Pilot A — readable coordinates and the compression path

Use preregistered matched target tetrads wherever possible:

1. a canonical public-domain passage with recognizable work, author, passage, or form coordinates;
2. a meaning-preserving paraphrase;
3. a newly authored or procedurally generated coherent text matched for topic, style, and length;
4. an entropy-matched or randomly permuted negative control.

An obscure passage from the same work is a useful optional fifth stratum, but it is not smuggled into
the tetrad.

Run at least one reproducible open model family at two scales in feasibility, then require a second
family before the full claim. Compare exact reproduction and declared semantic-distortion regimes.
Budget-match enumeration where possible, deletion/substitution search, beam/evolutionary search,
MiniPrompt/ACR, ARCA/GCG-compatible methods, Reverse Prompt Engineering, and a strong general
optimizer. Freeze the searcher before final targets are revealed to it; use target-blind surface
raters, balanced-decoy link raters blinded to model and search metadata, and fresh model samples for
confirmation.

Pilot A advances only if:

1. the implementation recovers the exact optimum in the finite toy domain;
2. the failure-inclusive comparison against the single development-frozen strongest non-oracle
   baseline passes the \((m_D,m_C)\) lexicographic decision rule at matched primary compute;
3. every selected candidate passes fresh generation bounds and the simultaneous ceilings of the
   versioned \(\mathcal V_{\mathrm{copy}}\) suite; this supports tested-noncopy only, not universal
   absence of copying;
4. the preregistered frontier-distance and coordinate-type-distribution statistics exceed their
   calibration-frozen minimum effects for readable versus raw views;
5. accessibility rank stability across search seeds and the model-scale replication statistic pass
   their named lower-bound or equivalence rules;
6. continuation, residual localization, and repair each pass their compute-matched ablation contrast,
   establishing which component—not a different GCG implementation or more compute—accounts for gain.

Regardless of advancement, Pilot A must report with uncertainty the canonical/paraphrase/novel
ordering and its failures, token-level residual and breakpoint analysis, disagreement with the
Prompting Complexity nucleus-plausibility baseline, and comparative predictive validity of the human
protocol. These reports can falsify interpretation, but their mere existence is not a pass condition.

If the optimizer does not beat existing methods, Aleph may still be a useful measurement workbench,
but it cannot claim a new search method. If human-readable coordinates collapse to title lookup only,
the empirical scope must narrow rather than hiding that result. If the human protocol does not change
scientific conclusions relative to nucleus plausibility and residual repair does not beat existing
optimizers, the work is a benchmark or replication—not a new readable-complexity construct.

### Pilot B — controlled source interpretation

Use small open checkpoints with an enumerable closed-world grammar, matched permutation siblings,
high-entropy targets and grammar-generated pseudo-facts, exposure levels such as
\(\{1,4,16,64\}\), and the orthogonal split contract. The number of independently trained sibling
pairs is set by simulation on a preregistered minimum effect; three pairs are feasibility evidence,
not inferential evidence. A planning target such as 256 associations per pair improves within-pair
precision but does not replace independent pairs.

Pilot B advances only if:

1. the lower confidence bound for the whole-permutation policy effect exceeds its frozen minimum and
   the control-family contrast passes its multiplicity-adjusted rule on held-out associations;
2. same-mapping and assignment-flip replica effects pass the frozen pair-level transfer/equivalence
   rule with independently trained pair as the inferential unit;
3. every provenance channel meets its separately frozen power and false-positive operating point;
4. pair-blind source-aware discovery exceeds the single development-frozen strongest non-oracle
   baseline by the preregistered failure-inclusive discovery margin at matched compute; the known-key
   oracle remains a ceiling only;
5. the unseen-replica orientation and effect statistic passes its frozen threshold, with endpoint
   metadata side channels masked as specified above.

The randomized analysis remains intention-to-treat. A secondary “association learned” subset may
explain mechanism but cannot replace the randomized denominator.

Narrow or stop the source claim if separation is near chance outside calibration, generic fine-tuning
drift dominates the contrast, results reverse across training pairs, a simpler leakage or trigger
baseline performs equivalently, or the natural-target story requires observational evidence to be
presented as causal truth. Failure of Pilot B does not erase a successful Pilot A; it removes or
demotes the source-attribution contribution.

A rigorous negative result may still support a workshop or measurement paper, but it should not be
repackaged as the full ICLR claim.

## Public benchmark and runtime contract

Research validity and public portability share artifacts but have different gates. The existing
**Aleph Bench** remains the one long-term public benchmark entry and may publish diagnostic, smoke,
and portability runs while the research protocols mature. It must not promote those runs into an
official scientific ranking until the corresponding target, prompt, scorer, and analysis release is
frozen. Kaggle job completion is runtime evidence; it is not by itself a benchmark result.

The implementation survey yields a compositional design rather than a repository to copy wholesale:

| system | practice Aleph adopts | boundary or failure Aleph records |
| --- | --- | --- |
| [HELM](https://github.com/stanford-crfm/helm) | typed run specification through scenario, adapter, request, executor, metric, per-instance evidence, and aggregate | file-existence resume and incompletely locked environments are insufficient for billable hosted calls; HELM is also in maintenance mode |
| [lm-evaluation-harness](https://github.com/EleutherAI/lm-evaluation-harness) | versioned YAML tasks, rendered prompt/chat-template identity, sample logs, model revision, environment and Git metadata | a general response cache and retry loop are not an exactly-once ledger for Kaggle or paid providers |
| [Open LLM Leaderboard](https://github.com/huggingface/leaderboards) | separate request/status, per-model details, aggregate, and model-revision surfaces | leaderboards need explicit retirement, supersession, and contamination policy rather than a permanent mutable score table |
| [BIG-bench](https://github.com/google/BIG-bench) and [BBH](https://github.com/suzgunmirac/BIG-Bench-Hard) | task-as-directory, schema, README, canary, and versioned exemplars | their task packaging alone does not cover modern provider failure, billing, or resume ambiguity |
| [LiveBench](https://github.com/LiveBench/LiveBench) | dated releases, item replacement/removal, provider/cost/latency artifacts, and question-level recovery | unpinned upstream datasets, doc/code drift, or converting persistent infrastructure error to a wrong answer violate Aleph's evidence boundary |
| [Dynabench](https://github.com/mlcommons/dynabench) | persistent rounds, snapshots, queues, deployment state, and raw-output locations | platform state is not the scientific score contract |
| [FastChat](https://github.com/lm-sys/FastChat), [Arena-Rank](https://github.com/lmarena/arena-rank), and [Arena methods](https://arena.ai/blog/ranking-method) | explicit conversation templates, deployment identity, duplicates/flags, uncertainty, and public change policy | the old FastChat Arena code is historical evidence, not the current production implementation |
| [Arena-Hard-Auto](https://github.com/lmarena/arena-hard-auto) | answer/judgment separation, frozen judge/template/parser, and swapped-order judgments when an LLM judge is used | an LLM judge does not establish human readability or causal source |
| [BFCL](https://github.com/ShishirPatil/gorilla/tree/main/berkeley-function-call-leaderboard) | generate, persist, offline-evaluate, and score as separate phases; item-level errata and decode/error events | benchmark-specific handlers must still emit Aleph's shared receipts and release identity |

The missing layer is one semantic release identity shared by GitHub, Hugging Face, and Kaggle.
`BenchmarkRelease` binds protocol, dataset revision and digest, prompt package, scorer and
normalization, runner commit, allowed runtime-profile manifest, and hosted task source into one
**core release digest**. `benchmark-release.json` is the immutable scientific payload. Compute
`release_digest` over a named canonical UTF-8 JSON/path/newline serialization, excluding only its own
digest field. Late-bound publication identifiers, lifecycle, supersession, retirement, and errata are
excluded and recorded as append-only, content-digested events that point back to the core digest.
Changing data, prompt, scorer, normalization, or aggregation semantics always creates a new core
release; an erratum can annotate or supersede an immutable release but never rewrite it.

Minimum public artifact shape:

```text
release/
  benchmark-release.json
  runtime-profiles.json
  checksums.sha256
  lifecycle-events.jsonl
  publication/<platform>.json
runs/<run_id>/
  run.json
  attempts.jsonl
  samples.jsonl
  aggregate.json
  publication/<platform>.json
```

`benchmark-release.json` records schema/release identifiers; protocol identifier and digest; dataset
repository, immutable revision, digest, and item count; prompt-template and rendered-contract digest;
scorer identifier, digest, and normalization; runner commit, supported Python/runtime profile, and
lock digest; and intended hosted profile and task-source digest. Release lifecycle
(`draft|published|superseded|retired`) is separate from result status
(`diagnostic|partial|failed|official`). Release-level publication envelopes record immutable
GitHub/Hugging Face/Kaggle identifiers, readback timestamps, checksums, and verification status.

`run.json` binds `release_digest`, deployment digest, requested and observed model-identity policy,
generation configuration, sample/replicate manifest, exact resolved environment, and aggregate inputs
into `run_digest`. Public score rows are keyed by `(release_digest, run_digest)`. Each run-level or
release-level publication envelope references its parent digest and has its own checksum.

Call the semantic work identity

```text
LogicalEvaluationKey = (release_digest, deployment_digest, phase_namespace, sample_id,
                        logical_replicate_id, rendered_request_digest,
                        generation_config_digest)
```

Define `AttemptKey=(LogicalEvaluationKey, attempt_index)`. `AttemptEvent` is append-only and keyed by
`(AttemptKey,event_sequence)`; provider request and idempotency identifiers are stored separately.
Each attempt records timestamps, requested and observed model identities, generation settings,
token/latency/cost receipts, response digest, evidence location, and independent decisions:
`failure_class`, `retriable`, tri-state `billable=yes|no|unknown`,
`remote_effect=none|completed|unknown`, and `score_eligible`. Stable failure families include
`preflight.*`, `platform.startup`, `platform.timeout`, `platform.artifact_missing`,
`provider.rate_limit`, `provider.timeout`, `provider.auth`, `provider.content_filter`,
`provider.server`, `response.empty`, `response.malformed`, `response.identity_mismatch`,
`evidence.write`, `evidence.integrity`, `scorer.parse`, `scorer.contract`, and
`publication.readback`. Infrastructure failure is never silently scored as model failure.

Resume is content-keyed, checksum-verified, and atomically committed. The dispatcher permits at most
one in-flight automatic dispatch per logical key and at most one dispatch per `AttemptKey`; local
commits are idempotent. A retry creates the next attempt index only after a terminal retriable failure
for which duplicate remote effect is excluded, or reuses a persisted provider idempotency key. An
unknown remote effect enters reconciliation and is not automatically retried. Exactly-once remote
effect is claimed only when a persisted provider idempotency key or authoritative provider readback
proves one completion.

Platform-specific publication rules are:

- **Kaggle:** repository-generated, standard-library-first task source; one identifiable logical call
  at a time; preattached content-addressed assets; controller-managed quota and retrieval; no package
  installation or undeclared network dependency in the billable path. “Hosted pass” requires task
  completion, downloaded-artifact readback, checksum validation, and offline aggregate replay.
  Hosted completion proves runtime only. `official` additionally requires complete declared coverage
  and observed model identity satisfying the frozen deployment policy; alias-only or unknown identity
  remains diagnostic.
- **Hugging Face:** one canonical dataset/release entry with immutable revision and content digest;
  clearly separated releases, requests/status, sample details, and aggregate results; dataset card
  with protocol, license/datasheet, deployment-identity policy, failure/coverage definitions, and
  reproduction command; staging, readback, and verification after push. Public rows undergo
  secret/PII review; restricted provider traces publish only allowed fields and digests.
- **GitHub:** Aleph Bench is the canonical human entry. Each release links its exact Hugging Face
  revision and Kaggle task version and ships checksums, lock/dependency snapshot, changelog, errata,
  and support matrix. Internal queue and diagnostic names stay in maintainer docs rather than the
  public title or primary command.

The supported-runtime claim begins with Python 3.10--3.13 plus an explicit Kaggle profile. Every
promised cell needs CI or a hosted receipt, while an offline fixture/golden replay checks scoring
without any model quota. Reports always include numerator, denominator, missing and excluded counts,
raw versus display metrics, and `diagnostic`, `partial`, `failed`, or `official` status.

This benchmark track runs in parallel with the research sequence:

1. **B0 — semantic release and attempts:** JSON Schemas for `BenchmarkRelease` and `AttemptEvent`,
   lifecycle/errata rules, failure taxonomy, canonical serialization/checksum scope, golden digest
   fixtures on Python 3.10--3.13 and the Kaggle profile, and content-keyed atomic resume. B0 and PR 2
   share one artifact identity/schema kernel rather than inventing parallel formats.
2. **B1 — runtime conformance:** rendered-prompt, deployment, and environment receipts; Python support
   matrix; offline replay; one real Kaggle execution that invokes a declared model/deployment on at
   least one non-fixture item and, after downloaded-artifact readback, yields score-eligible sample
   evidence and a replayable aggregate.
3. **B2 — cross-platform publication:** staged GitHub/Hugging Face/Kaggle publication followed by
   readback of the same `release_digest` and, for public result rows, the same `run_digest` and
   aggregate checksum, with links in all three directions.
4. **B3 — scientific activation:** verified B0--B2 receipts and a passing PR 5 decision are required
   before a new result-status event may mark a run `official` or enter it in a maintained scientific
   leaderboard. Protocol freeze alone permits a preregistered run, not an official result. B3 never
   relabels a pre-gate diagnostic run or rewrites the core release.

## Current implementation gaps

This is the code-level delta between the prototype and the research instrument.

### Search engine

`search/aleph_search.py` is a useful prototype but not an experimental implementation:

- model choices and budgets are hard-coded;
- only the confounded self-proposer/evaluator arm exists; no frozen external or model-independent
  proposer arm is implemented;
- the proposal fallback copies a target slice;
- proposal budgets are words while reported lengths are tokenizer tokens;
- the embedding metric silently becomes a character n-gram metric when loading fails;
- seeds, model revisions, raw proposals, evaluator calls, cost, retries, and failures are not recorded;
- stability is an ad hoc transform of three similarities;
- leakage is not enforced inside the search loop;
- baselines are not budget matched.

There is also a correctness bug in `monotone()`: when a shorter candidate remains best at a later
length, the function copies that candidate and overwrites its measured length with the later length.
That creates a pseudo-candidate whose prompt/output and objective coordinate came from different
observations. A cumulative value function may repeat the best value at larger *budgets*, but those
points must be labeled as budget thresholds, not emitted as measured candidate coordinates.

### Frontier and provenance

- `packages/core/src/frontier.ts` computes dominance only over tokens, fit, and stability even though
  the thesis requires declared recoverability and copy-channel constraints.
- core, Python API, web API, and client code implement different copy proxies and even different
  denominators under the same `leakage` label.
- current scalar candidate weights cannot recover every nondominated point.
- uncertainty and statistical certification are absent from frontier membership.

### Run contract

`CandidatePoint.tokens` does not identify its tokenizer or length unit. `SearchBudget` does not
separate proposer, evaluator, and validation calls or token/compute cost. `AlephRun` is still the
correct product exchange boundary, but it should not be stretched into the raw scientific trace.

The research engine should write an immutable research artifact first, then export a documented view
into `AlephRun` for the product.

## Engineering architecture

The research code should be small, typed, and independent of the web application.

```text
research/readable_coordinates/
  schemas/          versioned configs, events, candidates, and result manifests
  targets/          natural, authored, synthetic, and toy target manifests
  evaluators/       NLL, generation, surface, semantic, and code adversaries
  search/           archives, operators, schedulers, and baselines
  readability/      human protocol, frozen surrogate, and blind judgments
  interventions/    association generation, paired training, and source estimands
  analysis/         preregistered metrics, intervals, tables, and figures
  exporters/        explicit conversion from research results to AlephRun
  tests/            toy oracles, metamorphic tests, and failure-path tests
```

Core interfaces:

- `SearchSpaceSpec`: `finite_enumerable|countable_grammar|heuristic_open`, canonicalizer/legal-grammar
  hashes, optional cardinality and cost cap, enumerator digest, and declared structural assumptions;
- `ProposalKernel`: seed-determinism, branching/support declaration, path log-probability or derivation
  witness, exploration floor, and restart schedule;
- `CertificationSpec`: `archive|finite_universe|assumption_backed` scope, universe digest where
  applicable, alpha, epsilon/indifference margins, thresholds, fixed-budget or fixed-confidence mode,
  and missing/indeterminate policy;
- `ShortestCertificate`: `exact|interval|no_confirmed_candidate|globally_infeasible|indeterminate`,
  lower and upper cost,
  witness, unresolved cheaper candidates, simultaneous-coverage receipt, evidence digest,
  `complete_below_cost` plus its enumeration or lower-bound-oracle digest, and
  `none|exhaustive_prefix|exhaustive_universe|assumption_backed` globality;
- `TargetRecord`: immutable target text, rights, language, transformation family, split, and generator
  provenance;
- `AssociationAssignment`: key, target identifier, permutation, exposure, and controlled-source split;
- `SearchRun`: fixed model context, target, algorithm, budgets, and split identities;
- `ModelPair`: sibling A/B revisions, both assignment maps, and training receipts; positive/negative
  roles are derived per association;
- `CandidateEvent`: immutable prompt, parent lineage, operator, and proposal cost;
- `EvaluationEvent`: model, decoding seed, score, output, failure, and resource usage;
- `ProvenanceProbeResult`: probe class, version, reconstructed output, null baseline, and calibrated
  score;
- `BudgetLedger`: proposer, evaluator, validator, tokens, time, retries, and failures;
- `ObservedArchive`: every raw candidate and its provisional measurements;
- `ConfirmationState`: frozen candidate set, simultaneous bounds, decisions, and rejection reasons;
- `RunManifest`: hashes and revisions sufficient to replay or audit the run.

Certificate validation enforces \(L_{\mathrm{lower}}\le L^*\le L_{\mathrm{upper}}\) on the declared
simultaneous-coverage event. A finite upper endpoint requires a confirmed witness at exactly that
cost, and `exact` requires equal finite endpoints. `archive` evidence can never set global scope. A
global lower endpoint above the legal minimum requires exhaustive exclusion of every cheaper legal
candidate or a checkable assumption-backed proof; `globally_infeasible` additionally requires an
exhaustive-universe or proof-backed \(+\infty\) upper endpoint. Heuristic open search may still emit
the honest but weak global interval from the legal cost floor to the confirmed shortest found.

Human evidence has its own minimum schemas rather than free-form spreadsheets:

- `ProtocolManifest`: construct/stage, locale, intended population, lookup policy, instructions/UI/rubric
  hashes, choice and abstain policy, thresholds, alpha family/allocation, fixed or sequential sample
  plan, stopping rule, analysis hash, ethics/IRB status, compensation, freeze time, and manifest hash;
- `DecoyPanel`: target/options, decoy strata and matching features, constructors/reviewers, position
  schedule, pilot choice counts, option entropy, position/panel effects, freeze time, and panel hash;
- `JudgmentEvent`: pseudonymous rater, candidate/target/stage/panel, option order, raw response and free
  paraphrase, coder labels, correctness, ambiguity, confidence, post-response familiarity, latency,
  anchor/repeat flags, protocol/UI hashes, exclusion flag/reason, and timestamp;
- `AnalysisReceipt`: raw/missing/excluded counts, estimator and interval/sequence version, alpha
  allocation and stopping time, pass/fail/indeterminate state, agreement method/interval/overlap,
  variance components and familiarity strata, plus data/code/environment hashes.

Judgment events are append-only. Adjudication and exclusion add records; they do not edit the source
response. Public release uses privacy-preserving rater identifiers and follows the declared consent
and data-retention policy.

Required engineering properties:

- append-only JSONL events plus a content-addressed manifest;
- exact code, data, model, tokenizer, and environment revisions;
- deterministic toy tests and seed-explicit stochastic tests;
- no silent metric fallback;
- failures represented as data;
- resumable runs with duplicate-call protection;
- bounded retries and timeouts;
- closed-world artifact validation;
- human-readable config and one-command local smoke test;
- exporter tests proving that product views do not mutate scientific measurements.

The implementation boundary is deliberately narrower than a framework. Four protocols and one
post-search certifier are sufficient:

```python
class Operator(Protocol):
    id: str
    capabilities: frozenset[str]
    length_effect: Literal["fixed", "decrease", "increase", "variable"]
    proposal_mode: Literal["text", "raw_token", "explicit_copy"]
    def propose(self, parents, target, observations, rng, backend) -> ProposalBatch: ...

class Evaluator(Protocol):
    def evaluate(self, candidate, request, context, ledger) -> EvaluationReceipt: ...

class Archive(Protocol):
    def consider(self, candidate, receipts) -> ArchiveDelta: ...
    def select_parents(self, policy, rng) -> Sequence[Candidate]: ...

class Searcher(Protocol):
    def run(self, spec, operators, evaluator, archive, ledger) -> SearchResult: ...

class Certifier(Protocol):
    def confirm(self, frozen_shortlist, confirmation_spec) -> ConfirmationState: ...
```

`Candidate` is immutable and content-addressed over canonical message serialization, role/placement,
and UTF-8 bytes—not only rendered text. Operators propose but cannot score against the target model.
The archive never calls a model, and a candidate missing an objective cannot dominate a fully observed
candidate in the empirical materialization; that candidate remains `unknown` and may later change the
front. One append-only archive yields derived readable, raw, and explicit-copy views. The searcher cannot address the
confirmation store; `AlephRun` is an exported product projection, never the research database.

The append-only kernel recognizes at least these events:

```text
proposal_created
budget_reserved
evaluation_started
evaluation_completed | evaluation_failed
budget_committed
candidate_rejected | candidate_promoted
archive_changed
search_frozen
confirmation_completed
```

Materialized state must be reconstructable from those events. A stochastic cache entry represents one
observation and cannot be replayed as a new independent replicate. Its key includes run-context hash,
canonical candidate bytes, example and phase namespace, model/provider revision, tokenizer and chat
template hash, decoding configuration and seed, metric/evaluator revision, and requested sample
identity. Discovery, validation, and confirmation have disjoint namespaces. Failed and rejected calls
still consume and preserve receipts; retries are bounded and explicitly charged.

## Reviewable implementation sequence

Each step has one acceptance gate and should land independently.

### PR 0 — research decision record

Land this plan, its prior-art boundary, the proposed estimands, stop conditions, and prohibited
claims. No product or metric behavior changes.

Acceptance: a reviewer can state the paper claim, its closest collisions, and what would falsify it.

### PR 1 — measurement correctness

- remove pseudo-candidate coordinates from `monotone()`;
- separate observed candidate points from cumulative budget value functions;
- assign canonical names to existing copy and provenance proxies;
- add adversarial and metamorphic regression tests;
- correct public language that treats the found statistic as the oracle construct.

Acceptance: every displayed candidate is a real evaluated candidate, and every metric name resolves to
one implementation and version.

### PR 2 — research artifact kernel

Add versioned manifests, append-only candidate/evaluation events, separate budget ledgers, and a toy
finite evaluator with exhaustive ground truth.

Acceptance: exhaustive toy search defines ground truth and heuristic search reports regret against it.
Given one committed event log, uninterrupted materialization, interruption plus resume, and exporter
replay produce the same canonical semantic state and aggregate without reissuing model calls.

### PR 3 — core provisional search

Implement compression continuation, residual localization and repair, one append-only archive with
derived raw, tested-noncopy, and `surrogate_readable/provisional` views, length-aware operators, an
exploration reservoir, the exhaustive toy enumerator, and the minimum Pilot A recoverability suite:
surface copy, deterministic encodings, and public-reference classification with frozen nulls and
versions. Use a development/smoke panel disjoint from Pilot A's held-out panel.

Acceptance: the exhaustive enumerator recovers the toy optimum while every heuristic reports its own
success and regret; a real open-checkpoint smoke run produces only genuine observed points; the panel
yields a replayable union archive and provisional views; the minimum suite catches planted positives
without a hidden target lookup; and mechanism ablations separately remove continuation, residual
localization, and repair. No PR 3 candidate may enter the scientific `readable` view.

### PR 3a — mandatory closest-baseline adapter

Add the pinned MiniPrompt/ACR reproduction and audited adapter through the shared evaluator, ledger,
and archive boundary. Additional ARCA/GCG/RPE/GEPA/TextGrad/EvoPrompt adapters land separately rather
than making one “baseline-complete” mega-PR.

Acceptance: published and audited MiniPrompt modes are distinguishable, budget and legal-token
differences are explicit, failures remain in the denominator, and sampled-generation replay is
independent of teacher-forced screening.

### PR 4 — readability and independent confirmation

Add the annotation rubric, target-blind surface workflow, balanced-decoy link workflow, frozen
discovery surrogate, fresh confirmation path, and simultaneous uncertainty rules.

Acceptance: an adaptive discovery run cannot read or overwrite confirmation evidence, and the report
distinguishes provisional, rejected, indeterminate, and confirmed candidates. This is the first PR
permitted to emit human-confirmed `readable` membership.

### PR 5 — preregistered Pilot A decision gate

Freeze the accessibility hypotheses, target panel, primary endpoints, baseline budgets, exclusions,
and analysis; run Pilot A and publish the result even if negative.

Acceptance: an external reader can replay the natural-target analysis and decide whether the search,
readability-construct, and accessibility gates passed. Source engineering does not begin until this
decision is recorded, unless maintainers explicitly choose a separate measurement-paper fallback.

### PR 5b — source claim-boundary proof note

Freeze and externally check the source non-identifiability statement, symbols, latent versus visible
interventions, nondegenerate condition, counterexample construction, adaptive-transcript argument,
synergy/lower-bound propositions, and estimands.

Acceptance: a reviewer can reproduce the proofs and state exactly which quantities are identified or
nonidentified. No PR 6+ result may be interpreted as source attribution before this gate passes.

### PR 6 — paired-model intervention

Add deterministic target generation, permutation siblings, matched training configs, and four-cell
evaluation.

Acceptance: positive and negative controls recover their expected source signatures without using the
search algorithm.

### PR 7 — expanded typed-evidence suite and calibration

Extend the Pilot A minimum into semantic, cross-lingual, covert-key, multi-generation, execution,
learned prompt-recoverability, corpus-trace, evidence-support, influence, attribution, and
self-citation baselines with held-out calibration. Do not rename these distinct evidence types
`leakage`.

Acceptance: calibration and test reports include power, false positives, thresholds, and known blind
spots.

### PR 8 — source-aware search

Implement the observed source-selective archive with per-candidate confirmation labels, constraint
scheduler, mutations, baselines, and matched-call runner.

Acceptance: a fully replayable controlled run includes trigger-inversion baselines, transfer replicas,
and every failure.

### PR 9 — preregistered Pilot B and scaling decision

Freeze source hypotheses, primary endpoints, exclusions, and analysis; run Pilot B and publish the
result even if negative.

Acceptance: an external reader can rerun Pilot B from raw artifacts and independently decide whether
the source contribution gates passed and whether it belongs in the same paper.

The B0--B2 runtime/publication track may proceed in parallel, including bounded hosted conformance
runs. Broad model scaling, an `official` scientific leaderboard, or a polished paper narrative waits
for the relevant Pilot A gate; source-attribution ranking or claims wait for Pilot B. Infrastructure
readiness is not held hostage to the causal study, but neither may diagnostic scores be relabeled.

## Claims policy

Allowed now:

- Aleph is a target-first reverse prompt workbench.
- `Shortest Found` is the best candidate observed under recorded run conditions; it is provisional
  unless it passes the declared independent confirmation rule.
- current fixture and mock paths demonstrate product shape, not scientific performance.
- current leakage metrics are surface-copy proxies.
- source attribution is a proposed research program.
- this program proposes to extend ACR/MiniPrompt and Prompting Complexity toward human-measured
  coordinates, complete observed paths, reliable confirmation, and source-aware interpretation; none
  of those extensions is claimed as implemented evidence yet.

Not allowed until validated:

- Aleph estimates strict Kolmogorov complexity;
- Aleph invented target-first shortest-prompt search, the model-as-decompressor interpretation,
  adversarial compression ratio, or GCG length search;
- a found prompt is globally shortest;
- a single-model output reveals how much information came from weights;
- low n-gram overlap proves non-leakage;
- the compression frontier is universally smooth, convex, or one-dimensional;
- fixture, synthetic, local-host, or hosted black-box evidence proves the full paper claim;
- a natural text's provenance is known without controlled intervention.

## Paper-shaped completion criteria

### Core accessibility submission

The accessibility paper is ready to draft as a full ICLR submission only when it has:

1. a working readability-aware reverse-search algorithm, not a fixture-backed demonstration;
2. a validated observed archive with readable and raw nondominated views plus declared
   compression-path projections over a preregistered target panel;
3. the two-stage human-readable-coordinate protocol and statistically valid independent confirmation;
4. budget-matched search baselines including MiniPrompt/ACR, toy-domain exact regret, and decisive
   ablations;
5. empirical accessibility results across target strata, model scale, and a second model family;
6. immutable public raw artifacts, failure receipts, and a replayable analysis;
7. an honest natural-target external-validity section;
8. a limitations section covering readability dependence, reference-model choice, evaluator
   dependence, target-seeing optimization, open-domain discovery gaps, and hosted-runtime drift;
9. negative-result handling that does not move thresholds, exclusions, or the paper's object.

### Combined accessibility-plus-source submission

A combined paper additionally requires:

1. a checked proof and precise intervention-relative assumption boundary for source
   non-identifiability;
2. a controlled benchmark with audited randomized assignment, a declared `AssociationEffect`
   estimand, calibrated typed-evidence suite, and independently trained pair-level inference;
3. evidence that pair-blind source-aware search adds value beyond trigger inversion and simpler
   controls at matched access and compute;
4. natural-target source discussion explicitly labeled observational.

Failure of Pilot B removes source language from the title, abstract, and primary contributions but
does not block a successful core accessibility submission. Until the relevant list is satisfied,
Aleph is a promising research prototype with a sharper question, not an ICLR-ready result.
