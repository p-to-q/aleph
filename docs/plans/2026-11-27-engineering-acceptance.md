# Engineering acceptance and GitHub closeout — 2026-11-27

The repository and GitHub are the durable record for this work. Baseline Aleph
main: `96da20a`; standalone benchmark remote main: `d70cb6f`. Local uncommitted
migration work in the benchmark checkout and unrelated Aleph files are preserved.

## Gates and order

1. **Evidence accounting (#141, #142).** New ledgers distinguish unreported
   counters from declared zero; explicit `samples: 0` stays zero rather than
   inventing a sample. Version the derivation and preserve legacy sealed replay.
   Missing confirmation-work counters follow the same rule. Racing-skipped
   candidates export an unmeasured reason. Pin single-metric/top-1 scope.
   Validate semantic regressions, engine suite, lint, app tests/build and API tests.
2. **Mainline real-model canary (#106).** Adapt the unmerged #118 work onto the
   corrected mainline, keep proposal/evaluation separate, run a pinned local MLX
   model, archive new receipts, and verify them without loading the model.
   This is a smoke target, not evidence of population-level method superiority.
3. **Standalone benchmark (#29; benchmark #1/#12).** Work from remote main in a
   clean checkout; complete missing extraction/packaging and check source identity,
   deterministic generation, Unicode semantics and protocol verification. Do not
   overwrite the dirty migration checkout or declare authority before its gates.
4. **GitHub closeout.** Deliver each gate through a small PR with exact-head
   validation. Reconcile stale status/issue dependencies. Prune only demonstrably
   merged branches; preserve unique work and intentional benchmark authority refs.

## Accounting decision

Choose issue #141 option 2: `ResourceLedger/0.2.0` propagates unreported counters
as JSON `null`; sums containing an unreported contribution remain unknown.
`ResourceLedger/0.1.0` retains historical replay, including its zero defaults and
sample fallback. A legacy verification is byte-identity evidence, not a claim
that its accounting is complete. Receipt-specific metadata remains allowed;
a misspelled counter cannot satisfy the canonical name. New runs use 0.2.0.
No old evidence file is silently rewritten or relabelled.

For #142, record `not_evaluated_after_racing_stop`, following the budget-rationed
promotion distinction in [practice review §3](../research/engine-and-benchmark-practice-review.md).
Evaluated below-threshold candidates retain the existing `dominated` reason.
The `hybrid-pareto-v0` name denotes single-metric shortlist ordering and fresh
confirmation of the top-ranked entry; a multi-objective frontier remains deferred.

## Boundaries

No paid hosted requests, Kaggle model calls or revived v10 capture queues. #107
remains gated by its six-call one-shot policy and the real-model acceptance gate.
Preserve the existing public HF snapshot and Kaggle benchmark identity. Reference
CPython 3.13 / UCD 15.1 is not equivalent to an unproved portable scorer. No Rust
or Cargo release is inferred from an ambiguous dictated platform name. Do not
close research gates or publish a formal release solely because software tests pass.

## Acceptance record

Implementation and test results are recorded in the corresponding PRs and the
final closeout note; unchecked gates stay open with one concrete next action.
