<!-- STAGED TEMPLATE for the future `aleph-bench` repo. -->

# Contributing to ALEPH-Bench

Two kinds of contribution, each with a documented, reviewable path. The community-driven model is
deliberate: a benchmark becomes the field's when contributing to it is first-class, the way BIG-bench's
identity *is* its PR-based task submission.

## A. Submit a model (get on the leaderboard)

1. Run the public split reproducibly:
   ```bash
   aleph-bench run --track F --model <model-id> --split public --seed 0 --out result.json
   ```
   (or run the Kaggle Benchmarks task, which provides free model access.)
2. Open a **Model Submission PR** adding `submissions/<model-id>/result.json` plus a short **model card**
   (provider, version, decoding settings, date, any caveats).
3. CI validates the `BenchResult` against the schema and re-runs a sample for reproducibility.
4. Maintainers run the **held-out / private split** (you never see it) and publish the public-vs-held-out
   gap alongside your row. A large gap flags contamination/overfitting.

**Rules.** Pin the model version and decoding. No tuning on the held-out/private split (it is
inaccessible by design). Report, don't hide, failure cases.

## B. Submit a task / stratum item (grow the benchmark)

1. Add a `BenchItem` JSON under `bench/data/public/<stratum>/` with: target, **metric class**, a frozen
   **ladder** (rungs + paraphrases), **canary GUID**, **provenance**, and **license**.
2. Open a **Task PR**. The review checklist (a reviewer must be able to check every box):

   - [ ] **Construct fit** — does this measure *elicitation* (model recovers the output), not
         memorization or formatting compliance?
   - [ ] **Metric class is right** — objective (exact/execution) preferred; if semantic/rubric, the
         metric is meta-validated (human correlation reported) for this content type.
   - [ ] **Ladder quality** — rungs are non-leaking below `p_0`; lengths are near-optimal (construction
         budget + method disclosed); `p_0` is the only sanctioned leaky anchor.
   - [ ] **Leakage-gated** — no rung below `p_0` quotes the target above threshold.
   - [ ] **Contamination posture** — generated-fresh, or provenance + license documented; canary present.
   - [ ] **Provenance & license** — source and rights are stated and compatible.
   - [ ] **Reproducible** — generator/seed included for synthetic items.

3. At least one maintainer + one community reviewer approve before merge (BIG-bench-style).

## Principles every contribution must respect

- **One data shape.** Use the published `BenchItem` / `BenchResult` schema; no parallel formats.
- **Honesty.** Scores are upper bounds and procedure-relative; never phrase a result as a proven minimum
  or a capability claim.
- **Evidence modes.** Black-box submissions never report white-box (logit/NLL) quantities.
- **Validity over taste.** A metric you cannot meta-evaluate against humans cannot be the primary metric
  for a content-bearing item.

## Development

```bash
pip install -e ".[dev]"
pytest bench/tests           # exact-match, leakage-gate, AURC-monotonicity, schema, IIA
aleph-bench lint             # schema + canary + provenance checks
```

By contributing you agree to the repository licenses (code Apache-2.0; data per stratum).
