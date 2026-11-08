# Evidence boundary audit — 2026-11-08

## Decision before implementation

Keep Aleph's target-output-first compression workbench, discrete candidate path, and shared
`AlephRun` exchange contract. The existing thesis already calls for readable and raw-coordinate
views; MiniPrompt and its explicitly declared scaffold extension are compatible adapters, not a
reason to replace the product. The next useful change is to enforce the existing evidence
contracts at their actual consumer boundaries.

This audit starts at `1b62990911b35a5557cd321499d002fa8a5f44b5` (the local canonical-parser
hardening branch), with merged scaffold extension `68fa212` underneath. Author identity is not
evidence of who introduced a bug. Existing local `.gitignore`, `--output`, and `.kaggle-bench/`
changes are outside this work.

## Reproduced failures and repair slices

1. **Scaffold acquisition:** the GCG winner slices the prefix instead of the free-token window;
   target loss offsets omit the middle scaffold; final greedy confirmation drops both scaffold
   arrays. Fix those boundaries and test with independently causal target positions plus a
   complete runner handoff. Keep raw-token coordinates and archived receipts intact.
2. **Local token evidence:** candidate mean NLL bypasses the validated trace used by the observation
   mode. Invalid, mismatched, boolean, negative, non-finite, or overflowing losses can still leak
   into the response or crash serialization. Derive NLL from the same validated point trace and
   test the complete adapter response, including JSON serialization.
3. **Hosted evidence:** Explicit Reconstruction is currently copied into a black-box result with
   perfect scores without generation; per-candidate fallback can mix models while declaring the
   primary model. Measure every candidate, pin one connection for the whole successful run, and
   discard partial primary candidates if a complete fallback run is needed. Measure stability
   from two samples and label it as pairwise output agreement, not confirmed population reliability.
4. **Run identity:** browser file import accepts duplicate candidate IDs, making selection
   ambiguous. Reject duplicates at browser and engine standalone import boundaries and retain
   valid file round trips.
5. **Comparison reuse:** a completed comparison record was verified against its embedded
   configuration but not against the configuration requested by the current command. A verified
   `canary-1p7b` record could therefore be reported as a completed `canary-4b` run when the same
   directory was reused. Require the requested configuration digest before accepting reuse.

These are repairs of existing contracts, with no new runtime dependency, route, data format, or
architecture. Each implementation slice should remain independently reviewable before merge.

## Acceptance gate

No successful result may silently change the coordinate being optimized, fabricate a model
observation, relabel a different model's outputs, publish invalid token evidence, or ambiguously
resolve the selected candidate. Existing valid fixtures and raw-coordinate behavior still work.

## Validation

Baseline before changes: `npm run lint`, `npm test` (115 search tests, 449 engine tests; 15 optional
MLX tests skipped), and `npm --workspace web run build` pass. This passing baseline does not cover
the reproduced boundary failures.

Add focused offline regressions that fail on the original behavior, then run lint, the complete
offline suite, API tests/smoke, and the production web build. Hosted tests use stubbed transport;
no credentials or real model calls are needed. Record final results below after verification.

## Out of scope and remaining evidence

No optimizer expansion, UI redesign, dependency additions, benchmark submission, paid inference,
training, automatic deployment, or regeneration of historical model receipts. Existing scaffold
receipts predate these repairs; offline tests alone cannot upgrade them to corrected real-model
evidence. The pinned real-model engine canary and typed-evidence migration remain their own gates.

## Execution results

- Fixed the three scaffold coordinate boundaries and added MLX-free execution regressions.
- Made local candidate NLL derive from the same validated per-point trace as token-loss evidence;
  malformed traces now fail closed without leaking invalid values or crashing JSON serialization.
- Made hosted runs measure Explicit Reconstruction through the model, use two samples for pairwise
  stability, rerun the complete candidate set on one fallback model, and record the model actually
  used.
- Kept each candidate's two samples concurrent and candidates sequential, with a 55-second total
  budget inside the route's 60-second host limit. A successful primary run makes 10 model calls;
  fallback after a partial primary run discards those outputs and makes up to 10 additional calls.
  Added the stubbed hosted route regression to `npm test` and corrected its expected four primary
  requests when one sample pair fails concurrently.
- Rejected duplicate candidate IDs in browser and engine file import paths.
- Guarded matched-budget comparison receipt reuse by the requested configuration digest.
- Validation passed: `npm run lint`, `npm test` (119 search tests, 450 engine tests, 15 optional
  MLX tests skipped), `npm --workspace web run build`, `apps/api/.venv/bin/python -m pytest
  apps/api/tests/test_local_mlx_search.py -q` (23 passed), and focused comparison/MiniPrompt tests
  (53 passed).
- Final local checks also passed `apps/api/.venv/bin/python -m pytest apps/api/tests -q` (41
  passed) and `npm run api:smoke`. `npm run search:preflight` remains intentionally blocked on
  this machine because the search environment lacks `mlx_lm`, `sentence_transformers`, `fastapi`,
  `uvicorn`, and `numpy`; no real-model canary was attempted.

## Review follow-up

- Asserted the complete serialized token-loss trace for finite extreme NLL cases.
- Added a MiniPrompt scoring-rule identity to checkpoints and receipts. Progressed legacy scaffold
  runs with middle tokens are refused so old and corrected loss trajectories cannot be mixed;
  legacy empty-scaffold checkpoints remain resumable.
- Reserved 20 seconds for hosted fallback plus 5 seconds for scoring when configured, and routed
  cleaned empty samples through the same full-run fallback path.
- Resolved `next/server` from the importing route's workspace and report strict comparison-record
  parse errors as contextual `RunInstanceError`s.
- Strengthened regressions for pairwise stability, empty-output recovery, fallback budget recovery,
  extreme token-loss serialization, checkpoint compatibility, and duplicate-key comparison files.
- Added missing docstrings on changed complex functions to satisfy the review coverage gate.
- Bounded hosted similarity inputs at 4,096 target characters and 8,192 cleaned output characters;
  oversized trimmed targets return 413 before model calls, and the custom API UI checks the trimmed
  target before submission without letting raw leading whitespace truncate it.
- Validation passed: `npm run lint`, `npm test` (129 search tests, 450 engine tests, 17 optional MLX
  tests skipped), `npm --workspace web run build`, `apps/api/.venv/bin/python -m pytest
  apps/api/tests -q` (41 passed), and `npm run api:smoke`.
- Required canonical `candidateRole` and `identityVersion` alongside `candidateId`; missing or null
  identity fields now fail closed for both ordinary candidates and Explicit Reconstruction. Candidate
  records now participate in the writer-derived required-field regression matrix.
- Rejected malformed JSON and non-object/array API bodies with 400 responses, and non-string
  `target_text` or `label` values with 422. Applied the 4,096-character target limit to trimmed
  Unicode code points in both the route and UI, with bounded counting for oversized inputs. Rejected
  progressed prefix-only legacy checkpoints through `run_scan`, and verified the valid comparison
  receipt before the stale-receipt mutation.
- Latest validation passed: `npm run lint`, `npm test` (132 search tests, 450 engine tests, 17
  optional MLX tests skipped), `npm run build --workspace web`, `apps/api/.venv/bin/python -m pytest
  apps/api/tests` (43 passed), `npm run api:smoke`, `node scripts/check-hosted-search.mjs`, and
  `git diff --check`.
