# Metric and Backend Workflow Plan

## Status

Active plan. This is the next path after the v1.0.3 runtime-framing release.

## Problem

Dashboard values are currently a mix of:

- candidate data returned by a run or fixture;
- frontend-derived values such as leakage, compression, and rank;
- fixture values that may have been precomputed with older scoring logic;
- visual projections such as the frontier basin.

That is acceptable only when clearly labeled. It is not good enough for the next
research/product pass because users naturally read the dashboard as measured
evidence.

The most visible symptom is fit drift: when the prompt/output text displayed to
the user has not changed, the fit and epsilon values should not move. More
generally, exact target/output equality must always score as fit `1.0` and
distortion `0.0`.

## Goals

- Make every dashboard number traceable to a run field, deterministic frontend
  derivation, or explicitly labeled visual projection.
- Improve fit metrics so exact text equality is stable and obvious.
- Move candidate-level metrics toward the backend/adapter boundary instead of
  recomputing them differently in each UI surface.
- Preserve fixture, hosted black-box, and local MLX evidence boundaries.

## Work Tracks

### 1. Better Experiment Paths

- Treat each run as a durable artifact: target, prompts, outputs, scores,
  adapter mode, model, decoding, and budget.
- Add a simple route for repeated black-box samples so stability can be measured
  rather than filled with a default.
- Keep local MLX as the white-box path for token NLL and future score deltas.

### 2. Better Metrics

- Add normalized exact-match handling before lexical or embedding metrics.
- Split displayed fit into at least two ideas when data supports it:
  semantic fit and exact/sequence fit.
- Keep leakage separate from fit; do not let copied target text masquerade as
  compression quality.
- Record the metric name/version in the run so fixtures can be refreshed or
  compared honestly.

### 3. Better JSON and Backend Workflow

- Return candidate metrics from the backend in the `AlephRun` shape wherever
  possible.
- Add an evidence/source label per metric when a value is fixture-backed,
  backend-measured, frontend-derived, or projected.
- Stop sorting or interpolating candidate metrics in ways that decouple the
  visible prompt/output from its score.
- Add backend tests for exact-match scoring, CJK scoring, leakage, compression,
  and selected-candidate ranking.

## First Acceptance Gate

- Exact target/output equality scores fit `1.0` in both the Next.js hosted route
  and FastAPI scoring service.
- The explorer displays metrics for the same discrete candidate as the visible
  prompt/output.
- Dashboard copy marks fixture/projection evidence clearly enough that a user
  does not read a projected basin as measured model parameters.

