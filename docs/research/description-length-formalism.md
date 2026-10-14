# Description-Length Formalism

Status: research draft (stage 1, 2026-10-15). Companion to
`compression-definition.md` and `leakage-formalization.md`.

Everything below is stated for a **fixed** target `y`, model `theta`, decoding
rule `d`, metric `m`, and (where applicable) a search algorithm `A` with
budget `B`. The object of Aleph is the pair of quantities, never one of them
alone.

## 1. Two quantities, one object

Notation follows `compression-definition.md` and `../claim-ledger.md`.

**Definition (oracle value).**
`L*_{theta,d,m}(y; epsilon, beta)` = the minimum prompt length over the
declared coordinate domain such that `rho(p; y, epsilon) >= 1 - beta`, where
`rho(p; y, epsilon) = Pr_{Z ~ M_{theta,d}(. | p)}[m(Z, y) >= 1 - epsilon]`.
For deterministic decoding, `rho` is a zero-or-one special case. This is a
*defined minimum*, not a number any finite procedure is promised to output.

**Definition (found value).**
`L̂_{A,B,omega}(y; epsilon, beta)` = the minimum prompt length over prompts
actually observed in the run of `A` (budget `B`, random state `omega`) whose
**protected confirmation** supports `rho(p; y, epsilon) >= 1 - beta`. This is
the repository's `L_hat`: the shortest protected-confirmed candidate in the
observed archive. "Shortest Found" in the product is `L̂` for the actual
engine; it is honest *by construction*, and it is the only value Aleph ever
claims.

**Proposition.** `L̂_{A,B,omega}(y; epsilon, beta) >= L*_{theta,d,m}(y;
epsilon, beta)` for every `A, B, omega` (search set ⊆ all prompts), with
equality only when the run observes an oracle-achieving prompt and confirms
it.

**Proposition.** `L̂` is non-increasing in `B` and non-decreasing in
`epsilon`; `L*` is non-increasing in `epsilon`. Both are immediate from
feasible-set monotonicity.

**Proposition (incompleteness is the default).** No fixed `A` and finite `B`
guarantee `L̂_{A,B,omega} = L*` across all targets for a non-trivial model:
otherwise `A` would solve a semi-computable minimization uniformly
(section 7). So the gap `L̂ − L*` is not an implementation bug; it is the
object itself. Reporting `L̂` without implying `L*` is the repository's
standing rule (`../claim-ledger.md`: a finite search does not estimate or prove
`L*` without an additional theorem).

## 2. Relation to Kolmogorov complexity

Fix a prefix machine `U`; `K(x) = min{|q| : U(q) = x}`.

**Definition (model-relative description).** For deterministic decoding
(greedy `d`, fixed temperature 0), `K_M(y) = min { |p| : M_{theta,d}(p) = y
exactly }`, infinity if no prompt yields `y` exactly.

**Theorem (one-sided bound, two-part code).** For every total-recursive `M`
whose program is `prog(M)` with `K(M) ≤ |prog(M)|`:
`K(y) ≤ K_M(y) + |prog(M)| + O(1)`. Proof sketch: feed `U` a program that
embeds `prog(M)`, reads a shortest exact prompt `p` (length `K_M(y)`), runs
`M` on it, and prints the output. Hence the model-relative quantity is an
*upper bound* on the universal quantity up to the model's own complexity.

The same bound in token units is stated by the prompting-complexity paper:
`K(x) ≤ Ψ_f(x) · log2 T + O(1)`, where `Ψ_f` is the exact shortest-prompt
length under deterministic decoding, `T` the tokenizer vocabulary size, and
the model/tokenizer/decoding rule are absorbed into the constant
(Cosma, arXiv:2607.06145, section 4; see section 3 for the full comparison).

**Asymmetry (no matching lower bound).** There is no general
`K_M(y) ≤ K(y) + c` with a universal constant: a fixed model can have `y`
memorized (then `K_M(y) ≈ log |y|` via a numeric cache pointer) while `K(y)`
is maximal. The direction that survives universally is universal → model via
the two-part code with the *prompt search algorithm* as the middle program:
for found values with exact fit (`m(·, y) = 1`, deterministic decoding),

`K(y) ≤ L̂_{A,B,omega}(y; epsilon, beta) · log2 T + |prog(A)| + O(log B)`,

absorbing the model into the constant. This is the precise sense in which
Aleph measures *model-relative description length*: every found prompt is a
witness that `K(y)` sits below that prompt length plus the costs of the model
and the search, and nothing more.

**Refuted intuition (recorded, with counterexample).** "Shorter prompts
concentrate on rarer structure, so `L*` is close to `K`." Refuted: a model
that ignores all prompts except a lookup table has `K_M` constant on every
memorized target, independent of `K`. The model prior can inject arbitrarily
much description into the channel; Aleph measures the joint object, not `K`.

## 3. Positioning vs Prompting Complexity (arXiv:2607.06145)

Cosma's *Prompting Complexity* (2026) is the closest formal neighbor and the
mandatory comparison point. For a fixed instruction-tuned LM `f` it defines:

- **prompting complexity** `Ψ_f(t)` — the shortest *plausible* prompt
  (nucleus-sampling-filtered, human-readable text) whose deterministic
  decoding (`τ = 0`) produces `t` exactly; infinity if unreachable;
- **soft prompting complexity** `Ψ_f^{ε,d}(t)` — the shortest prompt whose
  output is within distance `ε` of `t` under a distance `d`;
- **behavioral prompting complexity** `Ψ_f(B)` — the shortest prompt whose
  output lands in a judge-defined acceptance set `B`;
- **prompting distance** `d_Ψ` — distance between texts via their shortest
  approximate prompts;
- a **prompting probability** semimeasure and a **weak coding theorem**
  (`−log_T P_f(t) − |t| ≤ −log_T m_f(t) = Ψ_f(t) − log_T Z_f(t) ≤ Ψ_f(t)`)
  linking prompt length, preimage multiplicity, and ordinary model
  probability;
- two negative/structural results: **failure of invariance** (no
  model-independent constant relates `Ψ_f` and `Ψ_g`), and a counting bound
  that highly prompt-compressible texts are exponentially rare.

Aleph's object overlaps with `Ψ_f` and `Ψ_f^{ε,d}` and deliberately differs in
five ways, which together are the positioning of this repository:

1. **Reliability.** `Ψ_f` is exact-match under deterministic decoding.
   Aleph's `L*` is defined through `rho(p; y, epsilon) ≥ 1 - beta` over
   stochastic decoding, with the deterministic case as a special case.
2. **Found value as the reportable object.** The paper notes that practical
   optimizers "can be viewed as algorithms for finding upper bounds on
   relaxed prompting complexity." Aleph makes that an explicit, replayable
   first-class object: `L̂_{A,B,omega}` with protected confirmation, plus the
   archive that supports it. `Ψ_f` is computable by enumeration in principle
   but infeasible; Aleph never claims to output it.
3. **Leakage dimension.** `Ψ_f` has no leakage constraint; a copying prompt
   is a legal witness. Aleph types the carrier role explicitly
   (`leakage-formalization.md`) and treats explicit reconstruction as a
   baseline endpoint, not a shortest prompt.
4. **Evidence infrastructure.** Aleph's quantities are pinned to append-only
   event streams, typed receipts, a six-account ledger, and an independent
   verifier (`search/engine/`, PR #109), so every reported `L̂` is replayable
   byte-identically.
5. **Product surface.** The compression path (discrete Pareto staircase from
   Shortest Found to Explicit Reconstruction) is the workbench object;
   `Ψ_f` has no path/staircase notion.

Adopted vocabulary: the paper's `c`-prompt-compressible texts
(`Ψ_f(t) ≤ |t| − c`), prompt-incompressible targets, and the preimage/selector
view of shortest prompts are used in this document where they apply.

## 4. How budget B and epsilon enter

- `epsilon` enters as the distortion level: at `epsilon = 0` (exact
  reproduction) the object is discrete and the staircase is steep; as
  `epsilon` grows, plateau structure appears (different `y` share fits).
- `B` enters only through `L̂`: it bounds the *discovery work*, not the
  defined minimum. `W_search` (engine account) is the ledger realization of
  `B`. The budget belongs to `L̂`, not `L*`
  (`compression-definition.md`).
- **Proposition (budget-relative monotonicity).** For nested algorithms
  `A ⊆ A'` at equal cost accounting, `L̂_A(B,epsilon) ≥ L̂_A'(B,epsilon)`.
  Trivial; kept because budget normalization across algorithms is the only
  way to make `L̂` comparable.

## 5. Pareto staircase and discreteness

**Theorem (finite language).** If the coordinate domain is finite (alphabet
`Sigma` with a length bound, as in bounded-coordinate-v0) and `m` is
computable given an evaluation oracle, then `L*(y; epsilon, beta)` and the
full leakage-augmented Pareto frontier are computable by enumeration
(exponential in the domain). Proof: existence of the finite search space;
enumeration evaluates every point once. This is the "finite truth" rung of
the research ladder: the v0 problem has alphabet size 4 and max coordinate
length 4, so its domain has `4^0 + 4^1 + 4^2 + 4^3 + 4^4 = 341` strings, and
shortestness is Lean-verified (`search/bounded/results/lean-verification.json`
records 13 public theorems; PR #103, PR #108).

**Conjecture (basin discreteness, general language).** In the full token
language the set of feasible prompts decomposes into basins separated by
non-smooth transitions, so that the achievable frontier remains locally
discrete; garden-path behavior (`garden-path-prompts.md`) is the observed
signature. Open; testing plan: measure fit as a function of single-token
edits along paths between found candidates on a pinned model.

**Definition (staircase).** The compression path displayed in the product is
the ordered set of frontier points from `L̂` (left endpoint) to explicit
reconstruction (right endpoint). It is a *set of attained points*, not a
continuous curve; the slider snaps to points by design
(`compression-definition.md`).

## 6. Witness cost vs discovery cost (the Lean/AlphaProof separation)

**Definition (discovery complexity).** `D_A(y, epsilon)` = the minimal
`W_search` budget at which `A` first evaluates a prompt with
`m >= 1 - epsilon` and length `≤ L̂_A(B, epsilon)` for `B` large; infinity if
never.

**Claim (empirical, external evidence).** AlphaProof produces very short
formal witnesses (Lean proofs) while consuming enormous training and
test-time search (DeepMind, Nature 2026, s41586-025-09833-y); FunSearch's
discovered programs are short relative to the evolutionary search that found
them (Nature 2024). The separation "description length of the witness ≪
discovery work" is the empirical backbone of the six-account ledger: `C(p)`
(coordinate cost) and `V_verify` (certification cost) are small, `W_search`
is the expensive account.

**Conjecture C4.** There exist target families where `D_A(y, epsilon)` grows
super-polynomially in `1/epsilon` while `L*(y; epsilon, beta)` stays bounded.
Falsifiable on finite languages by measuring `W_search` of several
algorithms; a positive answer justifies reporting discovery cost as a
first-class scientific quantity rather than a footnote.

**Mapping to accounts.** `C(p)` = prefix-free coordinate cost + tokenizer
view; `T_dec` = decoder calls/samples; `W_search` = all search work incl.
failures; `D_crit` = longest event-DAG dependency path; `V_verify` =
post-freeze sampling/replay/proofs; `M_desc(c)` = model/interface manifest.
See #106 for exact ledger semantics.

## 7. Computability conditions

- Finite coordinate domain + computable `m`: `L*` and the frontier computable
  (exponential).
- Infinite domain, computable `m`, **deterministic decoding** (`rho` in
  `{0,1}`), enumerable search: `L*` is semi-computable from above (enumerate
  prompts in length order; `L* ≤ min so far`), not computable in general, by
  the same diagonal argument that makes `K` non-computable. Under stochastic
  decoding `rho` is not computable by enumeration, and the claim does not
  apply.
- `m` itself a non-computable judge (e.g. arbitrary human proxy): no
  computability claim survives; the object degrades to the found value plus
  the judge manifest. This is why judge-based metrics must be declared as
  such in the run manifest.

## 8. Open questions

1. (C1, C3, C4) as in `leakage-formalization.md` and above.
2. Sharpness of the two-part bound: can the constant be made usefully small
   for pinned models by measuring `|prog(M)|` concretely? (Measuring a
   learned model's program length is not meaningful for trained weights —
   recorded as an open methodological problem, not attempted.)
3. Does `L̂` concentrate as `epsilon → 0` on family-structured targets (i.e.
   is the found value a stable estimator across random restarts)? Empirical
   question for stage 2.
4. Cross-model transfer of found coordinates (stage 2+ experiment; no claim
   yet).
5. Relation between the weak-coding-theorem multiplicity term `Z_f(t)` and
   Aleph's leakage vector: when many near-copying prompts generate the same
   target, does preimage multiplicity concentrate on carriers? Open; a
   positive answer would connect section 3's `Z_f(t)` to
   `leakage-formalization.md`.
