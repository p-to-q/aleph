# Leakage Formalization

Status: research draft (stage 1, 2026-10-15). Companion to
`compression-definition.md` and `description-length-formalism.md`.

This file formalizes the leakage object and its measurement. It defines
surface-copy proxies as one typed channel among many and never as a general
leakage or provenance score. Product thresholds remain open (section 9);
the vocabulary follows `docs/claim-ledger.md` and `docs/open-questions.md` ("3. Leakage
score").

## 1. Object and problem

Given a target output `y`, a fixed model `theta`, a decoding rule `d`, and a
metric `m`, a candidate prompt `p` may achieve high fit for two very different
reasons:

- **coordinate role**: `p` locates a region of `theta`'s continuation library
  whose typical output is close to `y` (compression);
- **carrier role**: `p` contains enough of `y` itself that the model only has
  to echo, join, or lightly rewrite copied spans (leakage).

The leakage question is: how much of `p`'s fit is explained by material copied
from `y`, rather than by coordinate information?

## 2. Definitions (surface-copy proxies)

Let `chars(p)`, `toks(p)` denote the character sequence and token sequence of
`p` under the pinned tokenizer `tau` (special tokens included).

**Definition (copy ratios).** `CR_char(p,y) = LCS_char(p,y) / |chars(y)|` and
`CR_tok(p,y) = LCS_tok(p,y) / |toks(y)|`, where `LCS` is the length of a
longest common subsequence. Both lie in `[0,1]`, are asymmetric
(`CR(p,y) != CR(y,p)` in general), and are monotone under insertions into `p`.
For `|y| = 0` define `CR = 0`.

**Definition (n-gram overlap).** For `n >= 1`,
`O_n(p,y) = |n-grams(p) ∩ n-grams(y)| / |n-grams(y)|` (denominator 0 ⇒
`O_n = 0`). This is the empirical probability that a uniformly sampled n-gram
of `y` also occurs in `p`.

**Definition (leakage vector).**
`ℓ(p,y) = (CR_char, CR_tok, O_1, O_2, O_3, O_4, ENT_overlap)`, where
`ENT_overlap` is the fraction of token-level named-entity/number spans of `y`
that appear verbatim in `p`. The vector is deliberately multi-scale: a single
scalar cannot separate verbatim copy (`CR_char ≈ 1`), structural paraphrase
(low `CR_char`, high `O_4`), and rare-span reuse (low everything except
`ENT_overlap`).

**Definition (leakage-aware effective length).**
`|p|_eff(ℓ) = |p| − λ · leaked(p,y)`, with `leaked = max(CR_char, CR_tok, O_4)`
and a fixed `λ ∈ [0,1]` declared in the run manifest. This is a measurement
convention, **not** a theorem; different `λ` only rescale the penalty and must
be declared, never implied.

**Scope note.** Every component of `ℓ` measures surface overlap between `p`
and `y`. The vector is a **surface-copy proxy suite**, one typed channel of
the provenance contract — it is not a general leakage score, and it must not
be relabeled as one (see section 3 and `docs/open-questions.md` #3).

## 3. Typed channels (which kind of leakage is this?)

`docs/open-questions.md` #3 and `docs/claim-ledger.md` require the channels that can make
a prompt look strong for different reasons to remain typed separately:

- **surface copy** — verbatim or near-verbatim spans of `y` in `p`
  (measured by `CR_char`, `CR_tok`, `O_n`);
- **semantic recovery** — `p` paraphrases `y`'s meaning without surface
  overlap (not measured by `ℓ`; needs a semantic judge, declared as such);
- **deterministic encoding** — `p` encodes `y` through a declared
  transformation (e.g. compressed, obfuscated, or language-translated
  payload); requires a reconstructor to be declared and tested;
- **public reference / corpus trace** — `p` names a retrievable source that
  contains `y` (URL, citation, dataset identifier);
- **training influence / memorization** — unobservable in black-box mode;
- **extractability, association effect, self-citation, search-trace
  integrity** — separate channels per `docs/open-questions.md` #3.

The scalar `leaked` may constrain or schedule search only; the full channel
vector remains the scientific artifact. Universal "non-leaking" language is
prohibited (`docs/open-questions.md` #3).

## 4. Information-theoretic grounding

The vector `ℓ` is a computable proxy, not the information-theoretic quantity
itself.

**Theorem (two-part code, sketch).** For any computable copy/remainder
decomposition `y = copy ⊕ r` where `copy` is a substring-span reuse of `p`, the
prefix complexity satisfies
`K(y) ≤ K(p) + K(r) + K(decomposer) + O(1)`. Proof sketch: a program that
(1) prints `p`, (2) prints `r`, (3) runs the (fixed, explicitly programmed)
decomposer to interleave the spans. Hence a candidate that copies `c`
characters of `y` explains at most that two-part cost, and the residual `r` is
the part that still demands coordinate information.

**Fact (semi-computability).** `K` is upper semi-computable but not computable
(Li & Vitányi, textbook). Consequently the *minimal* two-part code length over
all decompositions is upper semi-computable but not computable in general; the
greedy maximal-common-substring decomposition used by `CR_char` is computable
and is a conservative upper bound on the minimal decomposition. No black-box
observable certifies the minimal one. This is the formal reason leakage must
remain a *reported measurement*, never a claimed optimum.

**Note (interpretation).** n-gram overlap is not a lower bound on mutual
information `I(p; y)`: a prompt can share little surface text with `y` while
still being highly informative about it (garden-path prompts, see
`garden-path-prompts.md`), and share much surface text while the model
independently memorized `y` (Schwarzschild et al. 2024; Carlini et al. 2023).
In black-box mode, `ℓ` is the only honest surface observable; logit access
would allow the stronger estimator in section 8.

## 5. What leakage does to the length object

Use the notation of `compression-definition.md`: for fixed model `theta`,
decoding `d`, metric `m`, target `y`,

```text
rho(p; y, epsilon) = Pr_{Z ~ M_{theta,d}(. | p)}[m(Z, y) >= 1 - epsilon]

L*_{theta,d,m}(y; epsilon, beta) = min |p|
  over all prompts in the declared coordinate domain
  such that rho(p; y, epsilon) >= 1 - beta
```

For deterministic decoding, `rho` is a zero-or-one special case. Write
`L*` for the unconstrained value and `L*_{ℓ≤δ}` for the same minimum with the
additional constraint `leaked(p,y) ≤ δ` (same model, decoding, metric, target).

**Proposition (feasible-set inclusion).** `L*_{ℓ≤δ}(y; epsilon, beta) ≥
L*(y; epsilon, beta)` for all `δ`: the leakage constraint only removes
feasible prompts.

**Theorem (copy makes the free endpoint degenerate).** If the metric tolerates
reproduction — i.e. the explicit-reconstruction prompt `copy(y)` lies in the
declared coordinate domain and satisfies
`rho(copy(y); y, epsilon) ≥ 1 − beta` — then
`L*(y; epsilon, beta) ≤ |copy(y)|`. For the canonical
explicit-reconstruction template, which contains `y` verbatim,
`CR_char(copy(y), y) = 1` and `leaked ≈ 1`. In words: without a
leakage constraint the free minimum is dominated by carriers, not coordinates.
This is the formal restatement of "explicit reconstruction is a baseline, and
a leaky shortest prompt is a fake left endpoint" (`compression-definition.md`).

**Conjecture C1 (gap growth).** For natural target families and standard fit
metrics, the gap `L*_{ℓ≤δ}(y; epsilon, beta) − L*(y; epsilon, beta)` grows
with `|y|` when `δ` is fixed and `epsilon` is small. Rationale: the coordinate
description of `y` costs at least the model-relative structure of `y`, while a
carrier scales with `|y|` only through the metric's tolerance. No proof yet;
it is falsifiable on finite languages where both values are computable
(`search/bounded/` machinery).

## 6. Mechanisms and confounds

- **Verbatim copy / quoting**: high `CR_char`, high `O_n`. Channel: surface
  copy.
- **Structural paraphrase**: low `CR_char`, moderate `O_4`. Channel: semantic
  recovery (only detectable by a declared semantic judge).
- **Entity/number reuse**: isolated `ENT_overlap` spikes. Channel: surface
  copy on the entity span.
- **Garden-path steering**: low `ℓ`, high fit; see `garden-path-prompts.md`.
  This is the pattern a leakage-aware workbench must be able to *distinguish*,
  because it is the only low-`ℓ` pattern.
- **Memorization**: unobservable in black-box mode; a low-`ℓ`, high-fit
  candidate on a widely memorized target is indistinguishable from a genuine
  coordinate without logits. White-box follow-up: teacher-forced NLL
  comparison against a leakage-removed control (section 8).
- **Tokenizer confound**: every overlap metric is tokenizer-relative; the
  pinned `tau` must be declared in the run manifest (engine contract).
  CJK/emoji/whitespace normalization cases are covered by the engine test
  suite (`search/engine/tests/test_canonical.py`).

## 7. Measurement protocol (adversarial leakage suite)

For any frozen candidate archive, compute `ℓ` per candidate and compare
against two controls with identical length distribution: (a) random prompts
over the pinned vocabulary; (b) explicit reconstruction of the same `y`.
A candidate is **leakage-explained** if its fit advantage over the
random-prompt control disappears after conditioning on `ℓ` (linear regression
of fit on `ℓ` components within the same length stratum; this is a descriptive
protocol, not a hypothesis test with model assumptions — report residuals,
not p-values). Decision: leakage-explained candidates may sit on the discovery
archive but never on a leakage-constrained frontier.

**Engine mapping (planned, #106 PR B).** Leakage scoring runs *after*
`search_frozen`, on the frozen archive, as a separately reserved `W_search`
sub-account, and its outputs are append-only events. Protected confirmation
never sees leakage scores before its own freeze, so leakage measurement cannot
steer discovery. The verifier keeps this enforceable: confirmation may only
evaluate the frozen shortlist.

## 8. White-box extensions (requires logits; not product claims)

With logits, define token-level leakage of `p` relative to `y` as the
difference between the teacher-forced NLL of `y` given `p` and given the
leakage-removed prompt `p \ copy-spans`, i.e. how much of the likelihood is
supplied by copied spans. This is a computable, model-internal estimator that
dominates the string proxies in principle. It stays a research measurement
until a local adapter exposes it; per `docs/claim-ledger.md`, no white-box label
without logits or model internals.

## 9. Open questions

1. (C1) Gap growth above.
2. (C2) A single scalar cannot separate all four patterns in section 6 —
   prove or refute that any fixed finite vector `ℓ` admits two prompts with
   identical `ℓ` but different carrier/coordinate decomposition. Conjectured
   true by counting argument (no proof yet).
3. (C3) Is `L*_{ℓ≤δ}(y; epsilon, beta)` attained on the discrete Pareto
   staircase when the language is finite? (True for bounded-coordinate-v0 by
   enumeration; open for the full token language.)
4. Default thresholds for "leakage-constrained mode" (product decision,
   deliberately left open here; proposed starting point `δ = 0.2` on `leaked`,
   pending a decision note in `docs/`).
