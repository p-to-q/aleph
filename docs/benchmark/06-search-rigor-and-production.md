# Search Rigor (Local Minima) and Production Alignment

Two engineering-grade demands shape this document:

1. **Compress the prompt as far as possible without distortion, without getting trapped in a local
   minimum.** A benchmark whose scores reflect *search luck* rather than *model capability* is
   invalid. We must show our numbers are not local-minimum artifacts.
2. **Smaller and more production-adaptable is better.** The benchmark should measure the thing
   production teams actually pay for: fewer tokens to elicit the intended behavior, at acceptable
   cost and latency.

This is where ALEPH-Bench earns the word "engineering."

## Part A — The local-minimum problem, and how the design defeats it

### A.1 Why it is a real threat

Searching for the shortest prompt is non-convex and discrete. The repo's current engine
([`search/aleph_search.py`](../../search/aleph_search.py)) does a sensible but *greedy* hill-climb:
propose candidates, keep the best, NLL-guided refine, and "carry" the best longer-budget prompt down
to the next-smaller budget via `compress()`. Greedy descent over prompt text can stall: a model might
*actually* admit a 9-token coordinate, but the search only finds a 15-token one and reports 15. If
that stall is uneven across models, the leaderboard measures the searcher, not the models. This is the
single most important validity risk for any search-based compression benchmark, and the user is right
to insist on it.

### A.2 The structural answer: move search off the comparison path

The three-track design (see [`02-design-spec.md`](02-design-spec.md)) is, in part, a direct answer to
local minima:

- **Track F (Frozen Ladder) — the flagship — is local-minimum-immune by construction.** There is *no
  search at evaluation time*. Every model is scored on the *same* pre-optimized ladder of prompts.
  The hard search happens **once, offline, per item**, with a heavy multi-method budget, and the
  result is frozen and human-audited. Cross-model comparison therefore never depends on per-model
  search quality — exactly as MMLU's comparison never depends on who wrote the question. The
  local-minimum problem is confined to *dataset construction*, where we can spend unlimited budget and
  audit the result, instead of contaminating *every leaderboard row*.
- **Track O (Open Compression)** is where search is intrinsic and unavoidable. Here we do not pretend
  local minima are absent — we **certify convergence and disclose budget** (A.4).
- **Track W (White-box MDL)** uses likelihood- and gradient-guided search (ARCA / GCG-style), which
  has a far smoother objective than black-box text hill-climbing and is much less prone to stalling;
  and for scoring a *given* candidate it needs no search at all (teacher-forced NLL is a direct
  measurement).

### A.3 Monotonicity = an honest upper bound that only improves

The engine's `monotone()` lower-envelope is not a cosmetic smoothing; it is the formal guarantee that
makes the number honest. The reported frontier is the **best-known** distortion at each length, taken
over *all* attempts. Therefore:

- more search can only ever **lower** the reported frontier — never inflate it;
- the benchmark reports an **upper bound** on the true minimal length ("we have not found shorter"),
  never a claimed minimum — preserving the repo's core honesty posture;
- a model is never *penalized* by extra search; it can only be *helped*, so spending more construction
  budget is strictly safe.

### A.4 The convergence-certification protocol (for ladder construction and Track O)

To claim a length is near-optimal rather than a local-minimum artifact, the construction pipeline and
Track O both run and **report** a saturation test:

```text
1. Diverse proposers — generate candidates from independent sources so failure modes do not correlate:
     (a) LLM proposer at several temperatures and multiple random seeds;
     (b) an extractive compressor (LLMLingua-style) on a known-working longer prompt;
     (c) a discrete optimizer (ARCA / GCG) for open-weight construction;
     (d) human adversarial shortening attempts (construction only).
2. Multi-restart — N independent restarts per length budget; keep the lower envelope across all.
3. Saturation diagnostic — plot best-found distortion vs cumulative budget. Declare a length
   "converged" only when the best-found has not improved for K consecutive restarts.
4. Report convergence — every Track-O score ships a CONVERGED / UNDER-CONVERGED flag and the budget
   spent. An under-converged row is shown as a soft upper bound, not a hard claim.
```

This converts "did the search get stuck?" from an unanswerable worry into a **published diagnostic**.
It mirrors how SWE-bench makes an agentic, search-bearing setup trustworthy: not by pretending the
search is perfect, but by pinning, disclosing, and versioning it.

### A.5 Why the Frozen Ladder is fair even though it is fixed

A natural objection: "if you freeze prompts, you might pick prompts that suit model A and not model
B." Three mitigations make Track F fair:

- **k paraphrase ladders per item** — multiple surface forms at each length; we report the best rung
  per length across paraphrases, so a single unlucky phrasing cannot sink a model.
- **Construction is model-blind to the leaderboard set** — ladders are optimized against a *reference*
  decoder and audited for genericity, not tuned to any leaderboard model.
- **Track O exists precisely for "my model prefers a different short prompt"** — if a model can find
  its *own* shorter coordinate, Track O is where it gets credit. F measures decompression of a shared
  description; O measures self-compression. Reporting both removes the objection.

## Part B — Production alignment: the benchmark as a procurement instrument

### B.1 The metric *is* the production quantity

`ECL@τ` — "tokens to reach fidelity τ" — is not an abstract score. It is, literally, **how many
prompt tokens you must spend in production to make this model produce the behavior you want**. That
makes ALEPH-Bench a procurement tool, not just a science result:

> For the behaviors your product needs, which model needs the fewest tokens to be told? That model is
> cheaper per call, faster (shorter prompts → fewer prefill tokens → lower TTFT), and needs less
> prompt-engineering and less RL-on-top to stay on target.

This is the "降本增效" thesis made into a number a procurement or platform team can act on.

### B.2 Cost- and latency-normalized variants

Token count is the primitive; production cares about money and milliseconds. The benchmark therefore
reports, alongside raw `ECL@τ`:

```text
ECL$        = ECL@τ × input_price_per_token        # money to elicit the behavior, per call
ECL_latency = ECL@τ × per_token_prefill_cost       # prompt-prefill contribution to latency
Elicit@budget$  = fidelity achievable for a fixed *dollar* budget, not a fixed token budget
```

A model with a higher per-token price but a much lower `ECL@τ` can still be the cheaper production
choice — a tradeoff no accuracy leaderboard surfaces and that ALEPH-Bench makes explicit.

### B.3 "Without distortion" — the fidelity floor is a hard constraint, not a soft average

Production teams do not want "20% shorter at 1.5 points worse on average"; they want "as short as
possible *while still correct*." The benchmark encodes this the way production does:

- the primary operating point is **ECL@τ with τ high** (e.g. 0.95 / exact / all tests pass), i.e. the
  shortest prompt that still clears a *correctness floor*, not the shortest on average;
- distortion is reported **per item with its variance**, so a method that is short-but-occasionally-
  wrong is visible, not averaged away (the lesson from "Compression Method Matters" / the CRI work);
- for structured/functional strata, the floor is **objective** (tests pass, schema validates) — there
  is no "soft" distortion to hide behind.

### B.4 A production-realism stratum (the SWE-bench provenance lesson)

SWE-bench's authority comes from **real-world provenance**: real GitHub issues, real PRs, real tests.
ALEPH-Bench should add, beyond the literary/synthetic strata, a **production-realism stratum (S3+)**
drawn from real prompt→output artifacts: real task specifications, real API request/response pairs,
real structured-output contracts (redacted/licensed). Targets here are *behaviors a real system was
actually asked to produce*, scored by held-out cases. This is what makes "production-adaptable" more
than a slogan — the benchmark's hardest stratum looks like the prompts teams actually ship.

### B.5 Smaller is better — but the floor keeps it honest

The user's instinct — "压得越小越好" — is exactly the optimization the benchmark rewards, with one
guardrail: smaller is better **only down to the correctness floor and only without leakage**. The AURC
integral rewards buying fidelity cheaply across the whole budget; the leakage gate forbids buying it
by copying; the high-τ operating point forbids buying it by accepting wrong answers. "Smallest prompt
that is still correct and still genuinely compressing" is the precise target — and it is a *model*
property the leaderboard can rank.

## Part C — What this adds to the engine (for the implementers)

Concretely, turning the workbench engine into a benchmark-grade search asks for:

- a **multi-proposer construction harness** (LLM + extractive + discrete-optimizer + human) feeding one
  lower-envelope, used **offline** to build Track F ladders;
- a **saturation/convergence diagnostic** emitted with every Track-O run;
- a **cost/latency table** (per-model token price + prefill cost) so `ECL$` and `ECL_latency` are
  computed alongside `ECL@τ`;
- a **correctness-floor operating point** wired into the metric layer (high-τ / tests-pass), not just
  the average AURC.

None of this requires new science — it is disciplined engineering on top of the existing
`aleph_search.py` and adapter boundary, which is exactly the kind of work to hand to a strong coding
model once this spec is frozen.
