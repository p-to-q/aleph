# Model-Relative Coordinate Landmarks

- Status: proposed long-horizon mathematical and computational program
- Program version: `MRC-LANDMARKS/0.1.0`
- Started: 2026-09-27
- Owner roles: research lead, mathematical workstreams, and engineering lead
- Governing issue: [#101 — establish the mathematical discovery systems program](https://github.com/p-to-q/aleph/issues/101)
- Parent scientific plan: [ICLR readable-coordinate program](./iclr-readable-coordinate-program.md)
- Scope: foundations, exact finite computation, search complexity, source identifiability, and the
  gates by which those results may alter Aleph's paper, benchmark, or code

## Decision

Aleph should become a computer-science research program around a precise mathematical object, not a
paper-shaped collection of analogies. Its center is a **model-relative coordinate structure
function**: the best residual description or loss available at each charged coordinate budget for a
fixed decoder, interface, target, coordinate domain, and residual contract. Three things that are currently easy to blur
must then be studied separately:

1. the oracle structure function of the declared coordinate system;
2. the **found curve** obtained from candidates that an actual algorithm evaluated; and
3. the **DiscoveryComplexity** of emitting a coordinate and, separately, obtaining independent
   certification under a frozen verifier budget.

This choice preserves Aleph's original target-first compression path. It does not rename prompt
length as Kolmogorov complexity, and it does not turn mathematical formalization into the whole
project. The intended contribution stack is computer science: definitions that survive hostile
review, exact finite instances, proofs or counterexamples, working search algorithms, complete
systems receipts, protected model experiments, and a public benchmark whose results can be replayed.

The program has three landmark problems:

1. **representation and invariance** — what survives a change of coordinate language, tokenizer,
   interface, or compiler;
2. **description--discovery separation** — why a short coordinate can remain computationally hard
   to find; and
3. **source and leakage identifiability** — what prompt/output behavior can and cannot reveal about
   where the target information came from.

Each landmark has a versioned statement, assumptions, prior-art boundary, mathematical gate,
executable artifact, exact finite instance, long-run compute program, stop rule, falsifier, and
engineering consequence. A theorem without an instance checker is incomplete; a long run without a
defined mathematical quantity is exploratory; and a benchmark score cannot validate either one.

## Non-negotiable boundaries

1. **Readable prompts are not presumed enumerable.** The primary natural-language domain and its
   human eligibility predicate are open experimental objects. Exact enumeration is restricted to a
   separately declared finite coordinate system. A finite toy theorem may inform the open system but
   never certify its global optimum.
2. **Opaque hosted models are empirical oracles, not effective AIT objects.** A service name,
   model alias, request body, and date can pin an empirical condition. They do not provide a complete
   computable decoder description. No constructive Kolmogorov, semimeasure, or universal-simulation
   theorem in this document applies to an opaque hosted service.
3. **Coordinate cost is not search cost.** The bits submitted to a decoder, the decoder's execution,
   all work spent finding the coordinate, the critical dependency path, confirmation work, and the
   decoder/model description remain separate accounts.
4. **A proof assistant checks a formal statement, not research intent.** A Lean kernel can check a
   theorem expressed in Lean. It does not check that JSON data matches the formal object, that a model
   implements the declared decoder, that an English claim is faithful to the theorem, or that an
   experiment was not adaptively selected.
5. **One workstream may not validate itself.** Definition authors do not sign off their own theorem
   translation; search implementers do not certify their own replay receipts; experiment operators do
   not decide which result enters the paper.
6. **Negative answers are results.** A counterexample to invariance, a lower bound against discovery,
   an indeterminate source effect, or failure of a search method remains versioned evidence. No result
   is repaired by changing the object after the run.
7. **Mathematics and product engineering use separate PR gates.** Mathematical agents may produce a
   specification, proof, checker, fixture, or failing test. Changes to the active search engine, API,
   schema, benchmark, Kaggle runtime, or UI land through their own reviewable engineering issues and
   PRs.

## Layered object model

### Declared coordinate system

Version `CoordinateSystem/0.1.0` defines a coordinate system as

\[
\mathfrak C_c=(c,\mathcal D,E,C,\mathcal Y,\ell),
\]

where:

- \(c\) is the pinned empirical run context from the parent plan: model or service revision,
  tokenizer, interface, decoding rule, and runtime version;
- \(\mathcal D\) is the declared legal coordinate domain;
- \(E\) is an injective, computably invertible typed encoding on the theorem-bearing domain;
- \(C(p)=|\operatorname{enc}_{\mathrm{pf}}(E(p))|\) is its charged prefix-free communication cost;
- \(\mathcal Y\) is the output space;
- \(\ell_c(y\mid p)\in[0,+\infty]\) is a named residual, loss, or distortion cost.

Reserve \(\bar c\) for the stronger case in which all five context components have one complete
computable description. Constructive algorithmic-information statements use
\(\mathfrak C_{\bar c}\) and exclude opaque hosted services. A service alias and request manifest may
identify empirical \(c\), but it never becomes \(\bar c\) by notation.

Version `DiscoveryEnvironment/0.1.0` separately defines

\[
\mathfrak E=(\mathfrak C_c,\mathcal A,\mathcal V,\mathcal R),
\]

where \(\mathcal A\) is the searcher's access contract, \(\mathcal V\) is the frozen verifier and
confirmation contract, and \(\mathcal R\) is `ResourceLedger/0.1.0`. Access may expose a finite table,
source, logits, gradients, samples, or black-box query responses. Two algorithms that see different
access do not solve the same discovery problem even if they eventually submit the same \(p\). They do,
however, face the same oracle coordinate structure function when their \(\mathfrak C_c\) is identical.

Every use of \(\ell\) must name its semantics and version. Three useful cases are deliberately not
identified with one another:

1. **Exact finite residual.** A finite system can attach an integer residual code length or an exact
   finite distortion to every \((p,y)\).
2. **Effective probabilistic residual.** For a completely specified stochastic decoder with exact
   finite-output-plus-EOS probabilities,
   \(\ell^{\mathrm{prob}}_{\bar c}(y\mid p)=-\log_2P_{\bar c}(y,\mathrm{EOS}\mid p)\), with
   \(-\log_2 0=+\infty\).
3. **Empirical residual.** A local or hosted run may estimate success, edit loss, execution failure,
   or another versioned \(\ell_c\) from samples. Its estimate and interval are observations, not an
   exact oracle value.

Human readability is an additional eligibility predicate defined for a reader population and
protocol. It can restrict an empirical domain after measurement, but it does not make the natural
language domain finite, decidable, or effectively enumerable.

### Model-Relative Coordinate Structure Function

Version `MRC-SF/0.1.0` defines the central object

\[
\mathsf H_{\mathfrak C_c,y}(r)
=
\inf_{p\in\mathcal D:\,C(p)\le r}
\ell_c(y\mid p),
\]

with \(+\infty\) when the budgeted set is empty. It asks: after charging at most \(r\) coordinate
bits, what is the smallest residual cost available through this decoder and coordinate language?
It is model-relative, interface-relative, residual-relative, and domain-relative. Changing one of
those coordinate-system fields changes the object and requires a new identity. Changing only search
access, scheduling, or verifier budget leaves \(\mathsf H\) unchanged and instead creates a different
discovery environment.

The threshold view is

\[
\mathsf L_{\mathfrak C_c,y}(s)
=
\inf_{p\in\mathcal D:\,\ell_c(y\mid p)\le s}C(p).
\]

For a finite domain with attained minima,

\[
\mathsf H_{\mathfrak C_c,y}(r)\le s
\quad\Longleftrightarrow\quad
\mathsf L_{\mathfrak C_c,y}(s)\le r.
\]

The two-part coordinate score is

\[
\mathsf D_{\mathfrak C_c}(y)
=
\inf_{p\in\mathcal D}
\{C(p)+\ell_c(y\mid p)\}.
\]

On an attained finite instance this equals
\(\min_r\{r+\mathsf H_{\mathfrak C_c,y}(r)\}\) when \(r\) ranges over attainable charged costs.
With the effective probabilistic residual, define under the same exact-output-plus-EOS convention

\[
R_{\bar c,y}(r)
=
\max_{p\in\mathcal D:\,C(p)\le r}
P_{\bar c}(y,\mathrm{EOS}\mid p).
\]

Whenever that maximum is attained,

\[
\mathsf H_{\mathfrak C_{\bar c},y}(r)
=
-\log_2 R_{\bar c,y}(r).
\]

Use `sup` and `inf` for an unattained extended-real version. This is exactly the reliability-curve
reparameterization already written as \(R_y(r)\) in the parent plan, not a new theorem or novelty
claim. It turns \(\mathsf D\) into the charged prompt-plus-Shannon-residual score positioned there.
For opaque hosted \(c\), Aleph observes only an estimated reliability curve and uncertainty; it does
not assert an exact probability function or constructive code. With a reliability threshold
\(P(y,\mathrm{EOS}\mid p)\ge1-\beta\), the threshold length is the corresponding
\(\mathsf L(-\log_2(1-\beta))\). This is a bridge among coordinate budget, reliability, and a
two-part code; it is not a claim that a prompt is a classical algorithmic sufficient statistic.

The scalar function is one declared projection, not permission to hide the other scientific
objectives. For a finite declared coordinate domain \(\mathcal D\) and versioned objective vector
\(\mathbf m(p)\), define the oracle budgeted Pareto antichain

\[
\mathsf P_{\mathfrak C_c,y}(r)
=
\operatorname{Min}_{\preceq}
\{\mathbf m(p):p\in\mathcal D,\ C(p)\le r\}.
\]

Residual, reliability, readability, stability, and channel evidence may appear as separate
coordinates of \(\mathbf m\) or as frozen eligibility constraints. A scalar
\(\mathsf H\) must name which choice it makes. Weighted sums are scheduling policies, not a
definition of the Pareto object, and may miss unsupported nondominated points.

The name “structure function” is intentionally qualified. Classical algorithmic statistics varies
the complexity of a finite set or probabilistic model containing a datum. Aleph varies the cost of a
typed coordinate passed through a fixed decoder and measures its residual for a target. The closest
mathematical anchors are the individual
[algorithmic structure function](https://homepages.cwi.nl/~paulv/papers/structure.pdf) and
[algorithmic rate--distortion](https://homepages.cwi.nl/~paulv/papers/rateieee-it.pdf), but equality
with either object is neither assumed nor needed.

### Found curve

Version `FoundCurve/0.1.0` separates an oracle object from an algorithm's evidence. Let
\(S_{A,B,\omega}\) be the append-only set of coordinates actually evaluated by algorithm \(A\),
under declared resource budget \(B\) and random state \(\omega\). With exact residuals, define

\[
\widehat{\mathsf H}_{A,B,\omega;y}(r)
=
\min_{p\in S_{A,B,\omega}:\,C(p)\le r}
\ell_c(y\mid p).
\]

Adopt the extended-real convention \(\min\varnothing=+\infty\), so the curve is defined even
before the archive contains a candidate at budget \(r\). Because the observed set is a subset of the
legal domain,
\(\mathsf H_{\mathfrak C_c,y}(r)\le
\widehat{\mathsf H}_{A,B,\omega;y}(r)\) whenever the displayed residuals are exact. The gap is
unknown unless the finite domain is exhausted or a sound lower-bound certificate is supplied.

For sampled model behavior, the artifact stores raw observations and simultaneous uncertainty
intervals. The UI or paper may display a provisional point estimate, a conservative confirmed upper
envelope, or an indeterminate region, but none may be silently written back as exact
\(\mathsf H\). Under one append-only trace, a fixed metric implementation, and exact immutable
per-candidate residuals, enlarging the observed coordinate set can only improve or preserve the exact
found curve. Sampled point estimates and confidence envelopes may improve or worsen as evidence
accrues; later confirmation versions and human reclassifications create new derived views without
rewriting raw observations. Independent reruns and model drift are different curves.

### DiscoveryComplexity

Version `DiscoveryComplexity/0.1.0` makes “short to describe,” “easy to emit,” and “cheap to certify”
different axes.
For bounds \((r,s)\), define the goal set

\[
G_{\mathfrak C_c,y}(r,s)
=
\{p\in\mathcal D:C(p)\le r,\ \ell_c(y\mid p)\le s\}.
\]

For an exact finite system, let
\(T^{\mathrm{emit}}_{A,\mathfrak E,y}(r,s;\omega)\) be the search work at which algorithm \(A\)
first emits a member of \(G\), or \(+\infty\). For success quantile \(q\in(0,1)\), define the
algorithm- and access-relative search quantity

\[
\mathsf{DC}^{(q)}_{\mathrm{search},A,\mathfrak E,y}(r,s)
=
\inf\left\{w:
\Pr_{\omega}\!
\left[T^{\mathrm{emit}}_{A,\mathfrak E,y}(r,s;\omega)\le w\right]\ge q
\right\}.
\]

This oracle-scored statistic is exact only where goal membership is exact. For stochastic model
behavior, a search-time hit remains provisional. Let the independent verifier use randomness
\(\zeta\) and at most \(v\) units from the verification account. Define the certified success region

\[
\mathcal B^{(q)}_{\mathrm{cert},A,\mathfrak E,y}(r,s)
=
\left\{(w,v):
\Pr_{\omega,\zeta}\!\left[
\begin{array}{l}
\text{by search work }w,\ A\text{ emitted an eligible }p,\\
\text{and }\mathcal V\text{ certified }p\text{ using verification work }\le v
\end{array}
\right]\ge q
\right\}.
\]

The primary certified report is the nondominated boundary
\(\operatorname{Min}_{\preceq}\mathcal B^{(q)}_{\mathrm{cert}}\), not a hidden sum of search and
verification. When one verification cap \(v_0\) is frozen before the run, the scalar conditional view
is

\[
\mathsf{DC}^{(q)}_{\mathrm{certified},A,\mathfrak E,y}(r,s\mid v_0)
=
\inf\{w:(w,v_0)\in\mathcal B^{(q)}_{\mathrm{cert},A,\mathfrak E,y}(r,s)\}.
\]

Any other scalarization requires a published resource conversion. Total work and verification work
remain separate; critical path is reported alongside the two-dimensional boundary and is never added
to it.

A population version additionally names and freezes a target distribution. An optimization over an
algorithm class is written only after fixing the machine model, access tier, advice, allowed
precomputation, and resource conversion. There is no context-free “discovery complexity of a
prompt.” In particular:

- coordinate length can be small while \(\mathsf{DC}\) is exponential;
- a white-box and a black-box searcher have different access contracts;
- proposer tokens that contain the target are search resources and trace-provenance events, not free
  coordinate bits;
- verification can dominate certification and therefore receives its own cap, axis, and ledger;
- a lucky first hit does not estimate a quantile without repeated, independently seeded trials.

Unqualified `DiscoveryComplexity` names this family of search and certified views, not one scalar.
It is closer in spirit to black-box query complexity, Levin-style search, and logical-depth questions
than to the coordinate structure function itself. Aleph uses those theories as constraints on
definitions and algorithms, not as names for an unproved quantity.

## Six-account resource ledger

Version `ResourceLedger/0.1.0` requires six accounts. They are stored together for comparison but are
not collapsed into one number without a published conversion rule.

| Account | Symbol | What is charged | What it must not impersonate |
| --- | --- | --- | --- |
| coordinate communication | \(C(p)\) | canonical prefix-free encoding of every target-varying field submitted as the final coordinate | model size, search effort, or full rendered-input cost |
| decoder execution | \(T_{\mathrm{dec}}(p)\) | per-call and aggregate target-decoder time, FLOPs proxy, tokens, memory, sampling count, and failures | researcher discovery work or coordinate bits |
| search total work | \(W_{\mathrm{search}}\) | work across every proposer, branch, mutation, evaluator call, retry, cache miss, and failed candidate | elapsed time under parallelism or verification work |
| critical path | \(D_{\mathrm{crit}}\) | longest dependency chain in the search/compute DAG under a declared scheduler model | total work; adding workers cannot shorten serial dependencies |
| verification | \(V_{\mathrm{verify}}\) | fresh samples, tests, proof checking, human judgments, calibration, and independent replay used after proposal | discovery budget or evidence already seen by the searcher |
| model/interface description | \(M_{\mathrm{desc}}(c)\) | canonical byte length and digest of the available checkpoint/service manifest, tokenizer, runtime, interface, decoder policy, and fixed scaffold; \(K_U(\bar c)\) appears only for a complete effective context in theorem statements | a computable estimate of Kolmogorov complexity or a hosted alias |

`W_search` contains component totals for proposal and discovery-time evaluation. The aggregate of
per-call decoder work may be reported next to it, but accounting code must say whether it is nested
inside or added to the total so it is not double-counted. `D_crit` is a derived graph statistic, not
an additive cost. `V_verify` begins only after the candidate set or theorem statement is frozen.
Human formalization time, literature review, and engineering labor are recorded as provenance and
wall-clock fields; they are not converted to FLOPs.

This six-account operational ledger refines the parent plan's four theoretical distinctions rather
than replacing them: coordinate communication maps to \(C(p)\); decoder execution remains separate;
the parent search budget expands into total work plus a derived critical path; model/interface
description operationalizes only an auditable upper-bound manifest around the theoretical
\(K_U(\bar c)\); and independent verification receives its own account. For opaque hosted \(c\),
`M_desc` records only the available request/service manifest with an explicit incomplete/effective
flag. It is never promoted to a complete decoder description.

Every receipt includes:

- object and metric versions;
- target, coordinate-domain, access-tier, and environment digests;
- event identity, parent identities, monotone sequence number, and random-state identity;
- raw resource counters and the rule used to derive any normalized budget;
- cache keys plus hit/miss/replay status;
- first-hit event, final evaluated event, verifier start, and verifier completion;
- total-work DAG and critical-path digest;
- failure, timeout, retry, and excluded-observation records; and
- a canonical artifact hash signed or independently reproduced by a second checker when feasible.

## Immediate executable bootstrap

The full planned finite-search artifact is **Bounded Coordinate Search v0** (`BCS-v0`). It exists to
make the definitions executable before expensive model runs begin. It is not a miniature claim about
the natural-language prompt domain.

**Current implementation status:** PR [#103](https://github.com/p-to-q/aleph/pull/103) merged on
2026-09-27 at commit
[`179194ca2524a0d37f797684010e600c70a65774`](https://github.com/p-to-q/aleph/commit/179194ca2524a0d37f797684010e600c70a65774),
closing issue [#102](https://github.com/p-to-q/aleph/issues/102). The merged `search/bounded/`
artifact names itself `bounded-coordinate-v0` (“Bounded Coordinate v0”). It is the first **BCS R1
bootstrap tranche**, not full `BCS-v0`. It contains one finite
two-landscape system, exhaustive enumeration, width-one beam, one paired seeded hash-priority
baseline, an independent Python reconstruction, and bounded Lean claims for coverage, minimality,
uniqueness, and published representative-frontier observation membership. It does **not** implement
the full fixture family,
the full algorithm matrix, or the threshold-duality and compiler-witness Lean theorems below.

### Full BCS-v0 contract (future completion)

Implementation issue [#102](https://github.com/p-to-q/aleph/issues/102) selected
`search/bounded/`: `search/` is the existing experimental engine, while `bounded` states the finite
claim scope without presenting one implementation as the full future search system. The artifact
must be runnable with the Python standard library before any model dependency is enabled.

The completed `BCS-v0` accepts a finite system manifest that contains:

- an explicit finite coordinate list or a terminating generator with declared cardinality;
- the exact typed encoding and integer communication cost;
- a deterministic finite decoder table or a pure deterministic decoder with a complete truth table;
- a finite target set and exact integer residual/distortion table;
- an access tier controlling which table entries a search method can observe;
- one or more algorithms with frozen seeds and resource limits; and
- a verifier that is independent of the proposal order.

It emits content-addressed artifacts equivalent to:

```text
system.json                 canonical finite-system manifest and digests
coordinates.jsonl          legal coordinates and charged encodings
evaluations.jsonl          append-only attempts, outputs, residuals, failures, lineage
oracle-curve.json           exhaustively computed MRC-SF and threshold view
found-curves/<run>.json     algorithm-conditioned curves at frozen budgets
resource-ledger/<run>.json  six-account totals and event DAG
certificate.json            optimum witnesses and cheaper-prefix exhaustion evidence
check-report.json            independent replay/checker result
```

The exact names are an implementation detail; the semantic separation is not. Serialization uses a
canonical form, stable sorting, explicit integer units, SHA-256 digests, and fail-closed schema
validation. The exhaustive runner and the independent checker must not import the heuristic search
implementation from which they receive an archive.

The future full-BCS minimum algorithms are exhaustive enumeration, seeded random order, beam search,
edit search, island evolution, and a model-guided-mutation adapter that can initially be replaced by a
deterministic fixture proposer. Each algorithm receives the same legal-domain and evaluator boundary.
Exact regret is reported only because this domain is finite and exhaustively checked. The merged
`bounded-coordinate-v0` tranche covers only exhaustive enumeration, width-one beam, and one seeded
hash-priority baseline; it must not be cited as evidence for the remaining algorithms.

### Full threshold/compiler Lean and checker bootstrap (future)

The full `BCS-v0` formal target is intentionally small:

1. a Lean theorem for finite threshold duality,
   \(\mathsf H(r)\le s\leftrightarrow\mathsf L(s)\le r\), under explicit nonempty/attainment
   assumptions; and
2. a compiler-witness theorem stating that a target-independent map satisfying
   \(C_2(g(p))\le C_1(p)+a\) and
   \(\ell_2(y\mid g(p))\le\ell_1(y\mid p)+b\) transfers any witnessed point at \((r,s)\) to one
   at \((r+a,s+b)\).

The merged `bounded-coordinate-v0` Lean project proves its concrete finite coverage,
no-shorter-witness, bounded uniqueness, and published representative-frontier observation-membership
claims. It does not prove
the abstract threshold-duality or compiler-witness statements above; those remain future `BCS-v0`
work.

The future independent BCS checker validates a concrete JSON certificate by enumerating the finite
domain. The Lean proof and checker have different trust boundaries:

- the Lean kernel checks the abstract theorem as encoded, plus the imported logical foundation;
- the independent checker checks canonicalization, hashes, all finite table entries, minima, and the
  claimed witness/counterexample for one concrete instance;
- neither establishes that an LLM, tokenizer, hosted endpoint, or human readability protocol matches
  the finite formal object; and
- a human statement-fidelity review must map the English claim, Lean definitions, and executable
  manifest before the proof can enter the paper.

Full `BCS-v0` is accepted only when a clean environment can run the exhaustive computation, replay
the checker, and run the threshold/compiler Lean build; when a deliberately corrupted cost,
residual, hash, or witness is rejected; and when the generated curve agrees byte-for-byte across two
independent runs. Passing the narrower `bounded-coordinate-v0` checks admits only that R1 bootstrap
tranche. If Lean is unavailable in a runtime such as Kaggle, the prechecked theorem source and proof
receipt travel with the artifact, while the independent finite checker remains runnable. Kaggle never
becomes the proof authority.

## Landmark I — representation and invariance

### Versioned statement

`LANDMARK-RI/0.1.0` asks for the sharp transfer laws between two declared coordinate systems rather
than a universal claim that token lengths are comparable.

Let \(\mathfrak C_1\) and \(\mathfrak C_2\) share a target/output interpretation. A
target-independent compiler \(g:\mathcal D_1\to\mathcal D_2\) has coordinate overhead \(a\) and
residual slack \(b\) when

\[
C_2(g(p))\le C_1(p)+a,
\qquad
\ell_2(y\mid g(p))\le\ell_1(y\mid p)+b
\]

for every declared \((p,y)\). The first theorem target is the curve transfer inequality

\[
\mathsf H_{\mathfrak C_2,y}(r+a)
\le
\mathsf H_{\mathfrak C_1,y}(r)+b
\]

whenever the right-hand infimum is attained, with an epsilon-relaxed form for unattained infima. A
reverse compiler with overhead \((a',b')\) supplies the opposite sandwich. The research question is
which real tokenizer/interface changes admit audited compilers with useful overheads, and where
semantics, readable eligibility, or hidden scaffold make such a compiler impossible.

This is a local compiler theorem. It is not the universal-machine invariance theorem, and no fixed
constant is expected across arbitrary commercial interfaces.

### Assumptions and exclusions

- The compiler is target-independent and fully serialized. A target-specific lookup table is part of
  the coordinate or model description, not a free compiler.
- Source and destination encoders are injective on exact legal objects. Renderer coincidence is not
  object identity.
- Residual preservation is proved or exhaustively checked for the declared system; matching visible
  strings is insufficient when role, token ID, attachment, or stop semantics differ.
- Readable-coordinate transfer additionally preserves the human display object and the frozen
  eligibility protocol. A raw-token compiler does not establish readable invariance.
- Constructive/AIT statements require both decoders and compilers to be effective. Hosted endpoints
  support only empirical conformance tests over a finite panel.
- Model description, fixed scaffold, and full rendered-input cost are reported even when a conditional
  coordinate comparison holds.

### Closest prior art and novelty boundary

- Classical universal-machine invariance motivates additive compiler overhead but does not apply to
  arbitrary prompt interfaces or human-readable subsets.
- Vereshchagin and Vitányi's
  [algorithmic statistics](https://homepages.cwi.nl/~paulv/papers/structure.pdf) and
  [individual rate--distortion](https://homepages.cwi.nl/~paulv/papers/rateieee-it.pdf) establish the
  relevant structure-function landscape and warn against assuming smooth universal curves.
- [Prompting Complexity](https://arxiv.org/abs/2607.06145) is the closest formal model-relative
  shortest-prompt neighbor; [ACR/MiniPrompt](https://arxiv.org/abs/2404.15146) is the closest
  target-first empirical compression neighbor.
- The parent plan's T2c already states a pointwise local compiler bound. Aleph's possible contribution
  here is a checked curve-level contract, a compiler artifact, counterexamples to invalid comparisons,
  and empirical evidence about which practical interfaces admit low-overhead translation—not the
  existence of the elementary inequality.

### Status

- **Adopted lemma:** witness transfer under a declared compiler and pointwise bounds.
- **Theorem target:** attained and epsilon-relaxed curve transfer, threshold transfer, and composition
  of compiler receipts.
- **Open conjecture:** useful real interfaces within one model family admit small, target-independent
  empirical overhead after charging role/scaffold differences. This is empirical and may be false.
- **Explicit non-conjecture:** arbitrary tokenizers or hosted services have a universal additive
  invariance constant.

### Proof and counterexample gate

The landmark advances from `proposed` to `finite_checked` only when:

1. a human proof states domain, attainment, extended-real, and target-independence assumptions;
2. Lean checks the finite witness-transfer theorem and, if implemented, the finite curve corollary;
3. an independent enumerator validates at least one bidirectional compiler instance;
4. a counterexample suite shows failure for a target-dependent compiler, a lossy renderer quotient,
   an uncharged role/scaffold change, and a compiler that preserves strings but not residuals; and
5. an independent reviewer signs the English--formal--executable statement map.

A theorem about the finite abstraction cannot enter the natural-model results section until the
empirical compiler and interface conformance tests pass separately.

### Formal and systems boundary

Lean checks the finite compiler-witness/curve statement over the formal cost and residual functions.
The independent enumerator checks the concrete finite tables and compiler certificate. The
`CompilerReceipt` checks that an empirical run used the claimed source/destination objects and
records translation failures. None of the three proves that a tokenizer implementation, model
runtime, or human readability judgment has the semantics intended by the theorem; those require
conformance tests and human protocol evidence. The receipt must include both system digests, compiler
digest, per-object failures, maximum observed cost/residual slack, and independent-checker digest.

### Algorithm artifact

`coordinate-compiler-v0` is a deterministic artifact containing source/destination system digests,
canonical object mapping, cost proof or exhaustive table, residual-conformance evidence, readable
display mapping where applicable, and composition metadata. BCS uses it to transform a full oracle
curve and checks the predicted sandwich. The production benchmark would later reuse only the receipt
format, not assume that every runtime has such a compiler.

### Finite exact instance

Use a length-delimited binary coordinate domain
\(E_1(p)=1^{|p|}0p\) for all bit strings up to a declared maximum. A second system wraps each
coordinate in one typed role tag with known fixed overhead. A finite decoder table maps coordinates to
finite outputs and exact integer residuals. The forward compiler adds the tag; the reverse compiler
removes it only from valid tagged objects. Exhaustive enumeration computes both structure functions,
their threshold views, and the tight observed overhead.

Four adjacent fixtures deliberately break one assumption at a time. In particular, one compiler
receives the target and substitutes its secret coordinate; another merges two objects that render to
the same visible string; another changes EOS behavior. Each must produce a machine-checkable
counterexample rather than an explanatory paragraph alone.

### Long-run compute

After finite validation, run an empirical compiler matrix across frozen open checkpoints and declared
tokenizer/interface variants:

1. same weights and tokenizer, different role/scaffold placement;
2. same weights, tokenizer versions with an explicit text-level re-encoding compiler;
3. quantized versus reference runtime under one tokenizer;
4. local open runtime versus an OpenAI-compatible server wrapping the same local weights; and
5. opaque hosted endpoints as finite-panel empirical comparisons only.

For each pair, compile the same frozen candidate archive instead of re-searching first. Then run a
separate matched-budget re-search to measure how representation changes DiscoveryComplexity, which is
not implied by curve transfer. Report coordinate cost, full rendered-input cost, output-law drift,
readability preservation, compilation failures, and all six resource accounts.

### Experiment and stop rule

The manifest freezes interface pairs, target panel, candidate archive, compiler version, residual
thresholds, maximum calls, and acceptable empirical conformance error before results are opened. The
run stops when every cell is `complete`, `failed`, `incompatible`, or `indeterminate` under that
manifest. No extra interface is added because the inequality looked weak. Re-search uses a geometric
budget schedule and a fixed maximum; target-wise results remain visible even if aggregate invariance
fails.

### Falsifiers

- A checked finite instance violates the compiler inequality: the formal statement, checker, or
  canonicalization is wrong and the landmark is blocked.
- A supposedly target-independent compiler changes after target inspection: the comparison is
  invalid, not evidence for invariance.
- Real interface differences routinely exceed declared overhead or change feasibility/readability:
  the empirical small-overhead conjecture is rejected.
- A curve looks stable only after dropping failures or charging different scaffold fields: the result
  is a measurement artifact.

### Engineering consequence

If successful, benchmark comparisons gain explicit `CoordinateSystemId`, `CompilerReceipt`,
conditional/full cost views, and a rule for when two runs may share an axis. If unsuccessful, the UI
and leaderboard must facet by tokenizer/interface rather than display one cross-runtime coordinate
length. Either result improves the product; no theorem is required to justify honest faceting.

## Landmark II — description--discovery separation

### Versioned statement

`LANDMARK-DD/0.1.0` asks when a low point on the coordinate structure function is computationally
inaccessible under a declared search interface.

The first exact separation uses a finite black-box equality oracle. Let a secret coordinate
\(S\) be uniform on \(\{0,1\}^k\), and let the decoder return target \(y\) exactly only when
\(p=S\). All legal coordinates have fixed cost \(k\) under the declared fixed-length code. Then a
perfect coordinate of cost \(k\) exists in every instance. Define discovery success here as
receiving a positive oracle response on one of the queried coordinates; a final unqueried guess is
not counted. Any adaptive algorithm that receives only success/failure and makes
\(q\le2^k\) distinct queries therefore succeeds with probability at most \(q/2^k\). If a protocol
allows one additional unqueried final guess, the bound is \((q+1)/2^k\). Under either convention,
description length is \(O(k)\) and median black-box discovery work is \(\Theta(2^k)\).

The long-horizon problem is to characterize how that separation changes under structured feedback,
compositional coordinate languages, gradients/logits, model-guided proposal distributions,
verification noise, parallel search, and shared precomputation. The project seeks upper and lower
bounds on DiscoveryComplexity, not a claim that every hard prompt is logically deep.

### Assumptions and exclusions

- The finite lower bound fixes the black-box equality-only access contract. Reading the decoder table
  or secret is a different problem.
- The secret is sampled independently of the algorithm's advice and precomputation. Any learned prior
  is named in the instance distribution.
- Queries are distinct or repetitions are charged without additional information.
- The verifier is exact in the basic theorem. Noisy generation and statistical confirmation require a
  separate sampling analysis.
- Total work, critical path, and evaluator calls are all retained. Unlimited parallelism may reduce
  depth while leaving exponential work.
- The open readable domain receives no completeness or global-optimum guarantee.

### Closest prior art and novelty boundary

- Levin-style universal search and time-bounded complexity connect program length and execution time;
  Bennett's logical-depth program distinguishes short description from computational history. Aleph's
  DiscoveryComplexity instead charges an external research process under a declared model-access and
  verification contract.
- [Levin Tree Search](https://proceedings.neurips.cc/paper/2018/file/52c5189391854c93e8a0e1326e56c14f-Paper.pdf)
  supplies a policy-relative node-expansion guarantee under exact tree-search assumptions.
- [Universal restart schedules](https://www.cs.utexas.edu/~diz/pubs/speedup.pdf) apply to independent
  Las Vegas restarts, not to a fallible success test or adaptively drifting hosted model.
- Black-box query complexity supplies the basic equality-oracle lower-bound template. The parent
  plan's T1d already states the \(q/n\) opaque-key bound.
- ACR/MiniPrompt, ARCA, GCG, GEPA, TextGrad, and evolutionary prompt optimization are algorithms to
  compare. None by itself defines the description--discovery gap or proves global shortestness.

The basic finite separation is not claimed as a new complexity theorem. Aleph's possible contribution
is the typed DiscoveryComplexity object, a replayable algorithm comparison on both exact and natural
systems, feedback-sensitive separations, and evidence about which search structure closes the gap.

### Status

- **Adopted theorem:** equality-only \(q/2^k\) success bound by exchangeability.
- **Executable theorem target:** exact first-hit distributions for exhaustive, random, beam, and
  mutation methods on finite instances, checked against enumeration.
- **Open theorem target:** a finite compositional family with provable separation between coordinate
  length and discovery under one feedback channel, plus a provable reduction under a richer channel.
- **Empirical hypothesis:** compression continuation with residual repair reduces DiscoveryComplexity
  on structured targets relative to length-matched blind mutation at matched work.

### Proof and counterexample gate

The exact separation is admitted only after:

1. a proof covers adaptive policies, randomized algorithms, repeated-query handling, and the exact
   success event;
2. an exhaustive checker computes the distribution for small \(k\) and agrees with the formula;
3. a model checker or Lean theorem covers at least the finite counting core, or a documented reason
   explains why the independent exhaustive checker is the stronger near-term artifact;
4. fixtures demonstrate that revealing a ranked distance, one secret bit, or the decoder table can
   invalidate the equality-only lower bound; and
5. paper language says `black-box equality-oracle separation`, never `prompts are exponentially hard`
   without the access qualifier.

The empirical search claim requires held-out targets and independent confirmation; finding a single
lucky coordinate cannot satisfy it.

### Formal and systems boundary

Lean may check the finite counting core and the exact implication from the equality-only access
assumptions. The independent enumerator checks complete small-\(k\) first-hit distributions and
algorithm archives. The systems receipt checks what the runner actually exposed, every query and
failure, the event DAG, total work, critical path, and verifier boundary. Neither Lean nor the finite
checker proves that a model API withheld logits, caches, timing, or side information as claimed; an
access-contract audit must establish that. Conversely, a read-back and independently replayed Kaggle
or multi-GPU receipt documents execution and accounting for that pinned run, not general runtime
support or the lower bound.

### Algorithm artifact

`discovery-arena-v0` extends BCS with a common search protocol for:

- exhaustive cost order;
- uniform random without replacement;
- beam search under a declared heuristic;
- local edit search;
- island evolution with full lineage;
- compression continuation plus residual repair; and
- model-guided mutation through a versioned proposer adapter.

Every method emits an append-only event DAG and the same goal-verification event. The arena derives
first-hit distributions, found curves over work, exact regret on finite systems,
\(\mathsf{DC}^{(q)}_{\mathrm{search}}\) at frozen quantiles, the nondominated boundary of
\(\mathcal B^{(q)}_{\mathrm{cert}}\), and conditional
\(\mathsf{DC}^{(q)}_{\mathrm{certified}}(\cdot\mid v_0)\) only for preregistered verification caps.
It reports total work, verification work, and critical path in their separate accounts. Failed
proposals, rejected confirmations, and invalid coordinates stay in the denominator. A method may use
caches only when cache keys include the entire effective evaluator identity and stochastic-sample
semantics.

### Finite exact instance

The first family is `opaque-key-k` for \(k=2,\ldots,k_{\max}\), where \(k_{\max}\) is fixed by the
implementation manifest. BCS exhausts all \(2^k\) coordinates, proves the exact structure function,
and records the complete first-hit distribution under each ordering policy.

The second family is `compositional-key-k`: the correct coordinate has independently checkable
subfields and the evaluator can expose one of three frozen feedback channels—equality only, Hamming
distance, or first-failing component. All three share the same shortest coordinate. The family tests
whether richer information changes discovery without changing description. A deliberately misleading
heuristic fixture supplies a counterexample to the intuition that beam width monotonically improves
finite-budget success.

### Long-run compute

After exact fixtures pass, the arena runs the same method contract on frozen open models and target
panels. The compute ladder is:

1. deterministic fixture proposer, to validate scheduling and receipts;
2. small open checkpoint with exact token log probabilities where available;
3. a second model family and tokenizer;
4. multi-GPU or long-duration island/evolution runs only after cheaper methods and resume semantics
   pass; and
5. hosted proposers or evaluators as portability cells, never as theorem evidence.

Budgets form a preregistered geometric ladder. Each run records proposer/evaluator tokens, calls,
FLOPs proxy, peak memory, monetary cost, failures, total work, critical path, verifier samples, and
model description digest. Shared precomputation is charged once under an explicit amortization panel
and also reported unamortized.

### Experiment and stop rule

For finite systems, stop only on full enumeration or a declared resource failure; exact curves are
not inferred from partial runs. For stochastic search, freeze algorithms, operator schedules, target
splits, seed-generation rule, budget ladder, success quantiles, and maximum compute before inspecting
test results. Run seeds until either the preregistered confidence-width target is met or the fixed
maximum is reached; report `indeterminate` at the cap rather than adding favorable seeds. The final
confirmation namespace is inaccessible to the search process.

Long-running compute is checkpointed by content-addressed event prefix. Resume must reproduce the
same semantic event sequence as an uninterrupted deterministic run, or explicitly branch with a new
run identity for stochastic schedulers. Daily compute allocation may keep the queue busy, but it may
not choose targets or methods from interim leaderboard success.

### Falsifiers

- Exhaustive BCS output disagrees with the closed-form equality-oracle distribution: theorem or code
  is blocked.
- A purported lower bound survives after the fixture exposes extra feedback only because the runner
  ignored that feedback: access contracts are wrong.
- Coordinate length alone predicts discovery equally well across equality-only and structured-feedback
  instances, within the powered range: the proposed feedback-sensitive empirical story is unsupported.
- Compression continuation/residual repair does not improve held-out DiscoveryComplexity or merely
  spends more unreported proposer/evaluator work: the Aleph-specific algorithm hypothesis fails.
- Parallel search reduces wall time but hidden aggregate work grows without bound: only critical-path
  performance improved; no total-work claim is allowed.

### Engineering consequence

The benchmark gains first-hit and discovery-quantile curves, access-tier labels, event-DAG receipts,
separate total-work/critical-path views, and exact regret only on finite fixtures. Kaggle and Cargo
become execution surfaces for the same artifact contract, not places where a leaderboard score is
treated as an oracle minimum. The product can show “shortest found at this search work” without
suggesting “globally shortest” or “easy to discover.”

## Landmark III — source and leakage identifiability

### Versioned statement

`LANDMARK-SI/0.1.0` treats source as a counterfactual property and leakage as a family of tested
reconstruction channels.

**Negative source statement.** If two structural mechanisms induce the same complete
history-conditioned observable kernel under every admissible black-box query, no adaptive algorithm
using only that interface can distinguish them. They may nevertheless assign opposite prompt-channel
and weight-channel source functionals under latent interventions. Single-world prompt/output behavior
therefore does not identify historical information source without structural assumptions or
interventions.

**Positive intervention statement.** A randomized training or checkpoint intervention can identify a
declared policy-level association effect when assignment, exposure mapping, interference, target
sampling, and pair-level uncertainty are specified. It does not identify a context-free number of
“bits from prompt” plus “bits from weights.”

**Channel-relative leakage statement.** For a versioned verifier family
\(\mathcal V=\{v_1,\ldots,v_m\}\), Aleph may report a reconstruction/provenance profile

\[
\Lambda_{\mathcal V}(p,y)
=
(v_1(p,y),\ldots,v_m(p,y)),
\]

plus calibration and null behavior. Passing every member means `not recovered by V at version x`,
not universal non-leakage. Search-trace integrity is a separate predicate because a final prompt can
look innocuous after target text entered through an undeclared proposer, cache, or manual edit.

### Assumptions and exclusions

- The negative theorem quantifies over the complete declared observable transcript, including timing,
  errors, metadata, logits, and state if exposed. Silently omitting a channel invalidates the claim.
- The broad construction allows abstract latent channels. A theorem inside a restricted transformer
  and training class is a stronger open problem.
- Positive source identification is relative to explicit randomized interventions and estimands. A
  famous natural text with one model remains observational evidence.
- Prompt and weight information can be synergistic. Additive source-bit accounting is not assumed.
- A verifier family is finite, versioned, independently calibrated, and explicitly incomplete.
- A hosted model may participate in observational and adversarial tests, but its hidden training
  history and changing service internals are not source ground truth.

### Closest prior art and novelty boundary

- The parent plan's T1--T1d gives the broad observational-equivalence lemma, randomized permutation
  estimand, synergy counterexample, and opaque-key lower bound.
- [Aronow and Samii](https://doi.org/10.1214/16-AOAS1005) supplies the assignment/exposure/estimand
  distinction under interference that the paired-training design must respect.
- [Counterfactual Memorization](https://arxiv.org/abs/2112.12938),
  [Datamodels](https://proceedings.mlr.press/v162/ilyas22a.html), and
  [TRAK](https://proceedings.mlr.press/v202/park23c.html) are closest training-counterfactual and
  attribution foundations; Aleph does not claim to invent counterfactual influence.
- [How Context Attribution Handles What the Model Already Knows](https://arxiv.org/abs/2607.23804)
  is a direct warning that overlapping in-context and in-weight knowledge defeats simple attribution.
- [The Secret Sharer](https://arxiv.org/abs/1802.08232) and controlled canary work establish exposure
  and extraction tests. Copy, reversible encoding, public reference, learned association, and causal
  influence remain different evidence channels.

Aleph's possible contribution is the integration of an explicit identifiability boundary, typed
channel-relative verifier profile, trace integrity, randomized association interventions, and
coordinate discovery—not a universal leakage detector or a new name for memorization.

### Status

- **Proof target:** externally checked broad single-world non-identifiability lemma with adaptive
  transcripts.
- **Adopted counterexample target:** permutation/XOR synergy showing zero marginal information and full
  joint information.
- **Open theorem target:** observationally equivalent mechanisms realized inside one restricted,
  nontrivial transformer/training class without hiding an arbitrary lookup table in channel names.
- **Empirical identification target:** whole-permutation policy effect across independently trained
  sibling pairs.
- **Permanent limitation:** no finite verifier suite establishes universal absence of leakage.

### Proof and counterexample gate

The negative theorem advances only when:

1. the observable sigma-algebra, adaptive policy, structural class, latent interventions, and source
   functional are written without switching between visible and latent interventions;
2. an independent proof checks equality of transcript laws by induction and the two-world error bound;
3. a finite checker enumerates all prompt histories up to a declared horizon for a toy pair of
   mechanisms, confirms observational equality, and confirms intervention-functional disagreement;
4. the synergy instance is computed exactly, including every marginal and joint entropy; and
5. a hostile statement audit lists omitted observables or hidden side channels that would break the
   theorem.

The positive paired experiment cannot borrow validity from that negative theorem. It passes only if
randomization, controls, training receipts, pair-level inference, and the preregistered intervention
contrast are independently validated.

### Formal and systems boundary

The first formal target is the finite observational-kernel construction and transcript-induction
lemma; Lean formalization begins only after the structural-class and observable-history statement
stabilize. The independent checker enumerates the finite kernels, histories, interventions, entropy
tables, and verifier fixtures. The systems receipts bind data generation, randomized assignment,
training, checkpoints, prompts, observables, and pair-level analysis. A kernel proof cannot show that
the neural mechanisms realize the abstract channels, while a successful neural control cannot prove
the universal negative theorem. Statement-fidelity review is therefore mandatory on both sides.

### Algorithm artifact

`source-identifiability-lab-v0` contains three independent components:

- a finite observational-equivalence/counterexample generator;
- a versioned `LeakageVerifierSuite` with identity, substring, deterministic encoding, public-reference,
  semantic/execution recovery, aggregate multi-sample recovery, and explicit null channels; and
- a paired-sibling trainer/evaluator with randomized permutation assignment and held-out certifier.

The suite emits a vector and calibration evidence, never one undocumented `leakage` scalar. Each
verifier declares its decoder side information, candidate visibility, target visibility, thresholds,
false-positive/false-negative estimates, and whether it inspects the full search trace. The paired
runner stores assignment before training, environment and data digests, all checkpoint identities,
and pair-level summaries.

### Finite exact instance

The first source instance has a finite prompt set and finite transcript horizon. Mechanism
\(M_P\) places one response kernel in an abstract prompt channel; \(M_W\) places the same kernel in
an abstract weight channel. Both expose identical observable kernels, while latent prompt
neutralization and matched weight replacement produce different source functionals. The checker
enumerates every reachable history and intervention result.

For finite \(n\), the second instance draws \(\Pi\) uniformly from the permutations of
\(\{1,\ldots,n\}\), draws \(K\) uniformly and independently from \(\{1,\ldots,n\}\), and sets
\(Y=\Pi(K)\). Under exactly those assumptions it verifies
\(I(Y;K)=I(Y;\Pi)=0\) and
\(I(Y;(K,\Pi))=H(Y)\), forbidding naive additive source bits. Adjacent leakage fixtures include
literal copy, base64, a secret-key channel with key absent/present, a public immutable reference, an
execution-equivalent program, and a trace-contaminated final prompt. Each fixture has a declared
expected profile, including cases no finite suite detects.

### Long-run compute

The protected compute ladder is:

1. exact finite mechanisms and verifier fixtures;
2. small independently trained permutation siblings with deterministic target generation;
3. multiple independent sibling pairs and matched absent/wrong-binding/correct-binding worlds;
4. source-aware coordinate search on held-out associations only after controls pass;
5. frozen open-model observational targets for external-validity comparison; and
6. hosted models only as observational/adversarial portability cells.

Training-pair count follows a preregistered pair-level power simulation. Targets, prompts, and samples
within a checkpoint are repeated measurements, not independent training replicates. Every model run
retains data-generation code, assignment seed, training order, optimizer state, checkpoint hashes,
evaluation requests, failures, and the six resource accounts.

### Experiment and stop rule

Freeze the structural estimand, intervention worlds, assignment mechanism, exposure assumptions,
verifier versions, calibration data, target split, pair-level analysis, power target, maximum pairs,
and source-aware search budget before held-out evaluation. Positive and negative controls must reach
their preregistered terminal states before source-aware search begins. At the maximum pair count, an
interval crossing the decision margin is `indeterminate`; it does not trigger more favorable worlds.

Adding a verifier creates a new suite version and may revoke a previous `not recovered by V` label in
the new view without rewriting the historical receipt. Natural-model and hosted observations stop at
the frozen call budget and never upgrade the causal claim.

### Falsifiers

- The finite mechanisms differ on a declared observable history: the claimed observational
  equivalence is false for that class.
- A classifier beats chance only through omitted timing, handle order, cache state, or metadata: the
  run falsifies the completeness of the declared observation contract, not source non-identifiability.
- Randomized positive/negative controls do not recover expected signatures: the paired system is not
  ready to estimate source effects.
- Pair-level effects vanish, reverse, or remain indeterminate under the frozen analysis: the positive
  source contribution fails or narrows.
- Any calibrated verifier reconstructs a candidate labeled universally non-leaking: the label was
  invalid. The system should never emit that universal label in the first place.

### Engineering consequence

The data model replaces one `leakage` number with versioned evidence channels and retains a deprecated
wire alias only during migration. Search traces receive integrity status independent of final-prompt
surface scores. Source claims carry intervention IDs and estimands; hosted and natural runs cannot
populate causal-source fields. The benchmark can rank coordinate search while displaying provenance
profiles, but it cannot rank hidden historical source on unobserved natural models.

## Four mathematical workstreams

The roles below are persistent workstreams, each allowed to branch into several agents. They are not
personality labels. Every branch has a durable output and a reviewer from a different role.

| Workstream | Internal branches | Required output | Cannot approve |
| --- | --- | --- | --- |
| thinking mathematicians | AIT/MDL and structure functions; search/query complexity; causal/source information; representation and counterexample design | versioned definitions, assumption ledger, conjecture graph, toy constructions, proof sketches, closest-prior-art boundary | their own proof translation or an empirical claim |
| computational mathematicians | exhaustive finite computation; independent certificate checker; scaling/long-run scheduler; statistical and resource-accounting analysis | exact tables, counterexample generators, first-hit distributions, long-run manifests, hashes, replay receipts, negative results | theorem correctness or paper promotion |
| proof mathematicians | human proof; Lean formalization; adversarial theorem audit; statement-fidelity comparison | checked theorem source, dependency lock, kernel receipt, independent proof note, formal/English mapping, discovered gaps | model implementation fidelity or experimental validity |
| refiners and translators | claim ledger; CS-paper synthesis; benchmark/runtime translation; public documentation and roadmap | accept/reject matrix for every claim, revised definitions, paper-ready statements, engineering issues, reproducibility package | changing a failed threshold or silently strengthening a result |

The thinking workstream initially has three parallel lines matching the landmarks. The computational
workstream initially has one BCS line and one long-run compute line. The proof workstream starts with
finite threshold/compiler theorems and the source non-identifiability audit. The refiner workstream
does not wait passively: it maintains the dependency graph and removes unsupported prose before the
next run.

Cross-role promotion uses this sequence:

```text
definition/conjecture
  -> hostile counterexample attempt
  -> exact finite computation
  -> human proof or explicit conjecture status
  -> Lean/independent checker where proportionate
  -> protected AI experiment
  -> independent result audit
  -> paper/benchmark/engineering translation
```

A stage may send the object backward. For example, a formalizer may expose a missing finiteness
assumption; an exact enumerator may refute smoothness; a model run may reveal that a residual metric
does not correspond to the theorem object. Backward movement is progress, not schedule failure.

## R0--R4 research rounds

This is the sole normative R0--R4 sequence for issue #101. Surveys and experiment notes may define
work packages, but they must map those packages into these rounds rather than create a competing
five-round order.

### R0 — lay ground and establish evidence lineage

**Question:** Are all objects, costs, access tiers, sources, and trust boundaries precise enough to
run or refute?

**Deliverables:**

- `MRC-SF/0.1.0`, `FoundCurve/0.1.0`, `DiscoveryComplexity/0.1.0`, and
  `ResourceLedger/0.1.0` definitions;
- one evidence card per primary source used in a material claim, including Anthropic, OpenAI,
  DeepMind, Meta/BAIR, formal-proof, AIT, and program-search branches maintained in the research
  ledger; every card separates representation-relative final-witness cost, post-freeze checker cost,
  discovery `ResourceLedger`, statement fidelity, novelty/provenance, typed human intervention, and
  exact checker/artifact identity;
- landmark assumption and falsifier tables;
- BCS-v0 implementation issue plus schema/checker issue;
- minimum Lean bootstrap issue with an explicit trusted-computing-base statement; and
- a claim ledger marking theorem, adopted prior art, conjecture, finite fact, empirical hypothesis,
  fixture, or unsupported idea.

**Acceptance:** an independent reader can derive threshold length and the two-part score from
\(\mathsf H\), distinguish all six accounts, explain why hosted models are excluded from constructive
AIT statements, classify each company case by claim object rather than organization, and identify a
falsifying artifact for every landmark.

### R1 — exact finite truth

**Question:** Does the mathematical object survive complete enumeration, independent checking, and
deliberate counterexamples?

**Deliverables:**

- merged and independently replayed `bounded-coordinate-v0` as the first BCS R1 bootstrap tranche,
  followed by executable full `BCS-v0` and canonical schemas;
- exact structure functions, threshold views, Pareto archives, and certificates for all three
  landmark fixture families;
- independent checker and corruption tests;
- Lean finite threshold/compiler theorem receipts;
- exact opaque-key first-hit distributions and synergy calculations; and
- a counterexample atlas for false smoothness, universal invariance, additive source bits, universal
  non-leakage, and search-completeness intuitions.

**Acceptance:** exhaustive and independently checked results agree; every artifact reproduces from a
clean environment; deliberately corrupted receipts fail; and no natural-language or hosted result is
described as exact finite truth.

### R2 — search algorithms and discovery complexity

**Question:** Which search structure closes the description--discovery gap at matched resources?

**Deliverables:**

- discovery-arena-v0 with enumeration, random, beam, edit, island, compression-continuation, and
  model-guided adapters;
- first-hit, regret, found-curve, work, and critical-path reports;
- exact feedback-channel separations on compositional fixtures;
- frozen open-model development panel and protected test panel;
- resume/replay equivalence and cache-integrity tests; and
- a decision note on which search contribution is strong enough for the CS paper.

**Acceptance:** every algorithm passes through one evaluator/archive boundary, all failures remain in
the denominator, finite regret agrees with exhaustive ground truth, and any claimed improvement
survives held-out targets and independent confirmation at matched work.

### R3 — protected AI and source experiments

**Question:** Which finite insights survive real frozen models, and what source claims become
identified only under intervention?

**Deliverables:**

- frozen open-checkpoint coordinate/compiler matrix;
- independently trained permutation-sibling worlds and control report;
- calibrated versioned verifier suite and trace-integrity analysis;
- readable/raw found curves with uncertainty and DiscoveryComplexity reports;
- portability runs through local, Hugging Face, Kaggle, Cargo-compatible, and bounded hosted
  environments using the same artifact contract; and
- explicit `confirmed`, `rejected`, `indeterminate`, and `runtime_failed` states.

**Acceptance:** protected evidence is inaccessible to discovery, controls behave as preregistered,
training pairs are the inferential blocks, runtime receipts replay, and hosted evidence remains
empirical. A Kaggle hosted pass demonstrates conformance only for the pinned artifact, model identity,
and hosted environment after artifact readback, digest validation, and offline replay. It may emit
`score_eligible` item evidence, but it does not create an `official` benchmark result without the
parent plan's complete-coverage, scientific-activation, and publication gates; it also does not prove
general portability, a theorem, or hidden provenance.

### R4 — refine, write, benchmark, and release

**Question:** Which results jointly support a coherent CS contribution, and which remain a longer
mathematical program?

**Deliverables:**

- paper contribution matrix mapping each claim to theorem, algorithm, systems receipt, and experiment;
- final negative-result and limitations sections;
- immutable benchmark/task/model/run manifests, raw and derived artifacts, and public replay tools;
- one public long-term benchmark entrypoint shared by GitHub, Hugging Face, Kaggle, and Cargo-facing
  documentation;
- paper drafts at mathematical, algorithmic, systems, and empirical levels; and
- a versioned post-paper landmark backlog containing unresolved conjectures and compute queues.

**Acceptance:** no sentence outruns its artifact; a new team can replay finite results and at least two
independent runtime cells; benchmark scores resolve to raw receipts; and the paper remains coherent if
any one positive empirical hypothesis fails.

## Paper contribution and admission matrix

The intended submission is a computer-science paper with mathematics serving the algorithm and
measurement contract. A result enters a primary contribution only through the corresponding gate.

| Candidate contribution | Required mathematical evidence | Required executable evidence | Required systems evidence | Paper outcome on failure |
| --- | --- | --- | --- | --- |
| coordinate structure function | definitions, prior-art boundary, finite duality/two-part relation | BCS exact curves and checker | schema and artifact identities | retain as operational definition, drop stronger theory language |
| representation transfer | compiler theorem and counterexamples | compiler-v0 finite instances | cross-interface receipts and cost views | facet results by interface; report negative invariance result |
| description--discovery separation | equality-oracle bound plus access assumptions | discovery arena and exact first-hit checks | work/critical-path/replay ledger | keep finite theorem; drop broad model-search claim |
| Aleph search method | no false global-optimum theorem; explicit algorithm contract | held-out matched-budget results and ablations | resumable event archive and verifier isolation | present benchmark/system or negative algorithm result, not SOTA claim |
| source boundary | checked observational-equivalence statement | finite mechanism checker | complete observable-contract audit | narrow theorem class or remove source claim |
| positive source effect | intervention estimand and interference assumptions | sibling training and held-out evaluation | data/training/assignment receipts | demote to observational discussion |
| channel-relative leakage | finite-family semantics and permanent limitation | calibrated adversary suite | versioned channel/trace records | publish blind spots; never use universal label |

Lean is evidence for selected kernels of the first, second, and fifth rows. It is not a requirement
that every empirical statistic be formalized, nor a substitute for independent numerical code.

## Benchmark, Kaggle, and the deeper program

The benchmark is valuable only if it exposes the mathematical distinctions rather than flattening
them into one medal score. Its minimum public views are:

- coordinate structure/found curves by target, model, interface, residual, and readable/raw domain;
- search success and DiscoveryComplexity by access tier and resource axis;
- exact-regret tracks restricted to BCS finite systems;
- natural-model tracks labeled best-found with uncertainty;
- channel-relative provenance profiles and trace-integrity status; and
- runtime conformance status for local, Hugging Face, Kaggle, Cargo-compatible, and hosted cells.

A Kaggle run is a useful runtime artifact when it actually evaluates a declared model on the public
benchmark and exports replayable raw receipts. A hosted pass can produce diagnostic aggregates and
`score_eligible` samples; only the parent plan's B3/scientific-activation gate may publish an
`official` result. Kaggle is not the central mathematical object. A medal, public score, or large
monthly inference budget can fund discovery and stress runtime contracts, but cannot erase an
unenumerated domain, an uncontrolled source story, or a missing verifier.

The deeper possibility is that Aleph becomes a laboratory for restricted description systems:
learned decoders supply enormous shared state; small coordinates navigate that state; search methods
discover some coordinates and miss others; and interventions reveal which apparent compression is
copy, reference, association, or interaction. Famous mathematical targets may later serve as
landmarks, but only after contamination, exactness, proof, and source contracts are adequate. Solving
or restating a famous problem is not itself evidence that the system discovered a new method.

## Versioning and durable records

Every definition, theorem statement, finite system, algorithm, verifier suite, target panel, and run
manifest has a semantic version and content digest. Changes follow these rules:

- patch: typo, clarification, or implementation repair that does not change membership, cost,
  residual, access, or estimand;
- minor: backward-compatible new field, verifier, fixture, or optional resource view;
- major: changed domain, encoder, metric semantics, theorem assumptions, access tier, stop rule,
  estimand, or result interpretation.

Derived artifacts name all upstream identities. Historical artifacts are never rewritten to a new
definition. A migration produces a new derived view and records which old fields could not be mapped.
Failed conjectures and invalidated implementations stay in the ledger with the exact counterexample
or bug receipt.

## Immediate next actions

1. Preserve and independently replay merged `bounded-coordinate-v0`, recording it only as the first
   BCS R1 bootstrap tranche.
2. Open and freeze the remaining full-`BCS-v0` manifest, then land its complete fixture/algorithm contracts
   before adding any model adapter.
3. Start the still-future Lean threshold/compiler proofs in parallel, with a statement-fidelity reviewer
   who did not write the definitions.
4. Populate one exact fixture for each landmark and deliberately corrupt each receipt path.
5. Run the discovery arena on finite systems, then permit a small open checkpoint only after exact
   regret and resume/replay gates pass.
6. Keep the active product/benchmark engineering sequence separate; import only versioned contracts
   that pass their research gate.
7. At the end of every round, have the refiner workstream publish an admission matrix: `paper`,
   `benchmark_only`, `engineering_only`, `open_conjecture`, `negative_result`, or `rejected`.

The next artifact after this plan should be executable. Additional prose is justified only when it
changes a definition, assumption, falsifier, or acceptance gate.
