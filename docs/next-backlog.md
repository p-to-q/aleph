# Next Backlog

This file turns the post-Hackathon state into small reviewable work. Promote an item to a GitHub issue when someone is ready to own it.

## P0: Make The Active Surface Unambiguous

Goal: one obvious place to change the product UI.

Tasks:

- Keep `web/` as the active app.
- Keep `apps/web/` archived and out of the root workspace.
- Keep `docs/state-of-play.md`, `docs/surfaces.md`, and `README.md` aligned with the decision.

Acceptance gate:

- A new contributor can answer "where do I edit the UI?" from README plus contributor map.
- `npm run lint` passes.

## P0: Clean Mainline And Branch State

Goal: make GitHub look like the repository we mean to maintain.

Tasks:

- Merge or close `codex/publish-aleph-explorer-update`.
- Delete already-merged remote branches when no longer needed.
- Decide what to do with the divergent local `main` snapshot before using it for future work.
- Keep PRs small enough that review comments map to one concern.

Acceptance gate:

- `origin/main` is the clear default base.
- No branch exists only because the Hackathon rush forgot it.

## P1: First Research-Grade Replayable Run

Status: product hosted-black-box and local-MLX loops exist. Their historical outputs are not a
PR0-conformant research archive.

Goal: produce one pinned open-weight run with a complete research bundle and a lossless selected-view
`AlephRun` projection that links to that bundle by stable content identity.

Tasks:

- separate proposal and evaluation roles and prohibit target-copy fallback;
- record every candidate, failure, retry, lineage edge, exact tokenizer cost, model revision, and
  resource delta before deriving a frontier;
- freeze a shortlist, run protected fresh confirmation, and independently replay the bundle;
- export `AlephRun` through an explicit candidate-to-observation projection map and retain a stable
  link to the complete archive/event bundle.

Acceptance gate:

- one real non-fixture open-weight canary produces a versioned bundle, even if its scientific result
  is negative;
- replay and corruption tests pass; the UI projection preserves the selected candidate and every
  referenced observation exactly. It need not embed the complete research archive, but its bundle
  reference must resolve and verify.

## P1: Metric And Typed-Evidence Implementation

Status: PR0 supersedes the old composite/scalar decision. Target-family calibration and implementation
remain open.

Goal: implement the versioned metric vector and finite evidence channels without collapsing them.

Tasks:

- freeze target-family fidelity metrics, calibration sets, intervals, and explicit missingness;
- version surface-copy, deterministic-decoding, public-reference, recoverability, and trace-integrity
  channels with declared side information and nulls;
- add empty prompt, explicit reconstruction, paraphrase, entity/number, base64/hex, hidden-key, and
  contaminated-trace cases;
- permit a scalar only as a named scheduler/UI projection over the preserved vector.

Acceptance gate:

- every paper-facing value resolves to one implementation/version and raw observation;
- passing a finite suite is labeled only relative to that suite and its thresholds.

## P1: File-First Run Import/Export

Goal: make the product match the repository thesis.

Tasks:

- Keep export working for `AlephRun`.
- Add JSON import with schema validation.
- Show invalid-file errors clearly.
- Add at least one fixture import smoke path.

Acceptance gate:

- A saved run can leave the app, return to the app, and preserve selected candidate semantics.

## P2: Adapter Evidence Contract

Goal: make token loss and attribution real only when evidence supports them.

Tasks:

- Decide which `ObservationSet` fields are required for token NLL.
- Separate white-box adapter output from simulated UI panels.
- Add a local MLX receipt that covers token NLL shape.
- Defer deletion ablation until the scoring route can compute it honestly.

Acceptance gate:

- UI labels make it impossible to confuse simulated panels with model internals.
- White-box output can be validated through schema or typed tests.

## P2: Research Route Review

Status: completed at the route-selection level by PR0, prior-art, and the landmark/system program.

Goal: turn only accepted routes into separately audited adapters.

Tasks:

- reproduce MiniPrompt/ACR as the mandatory closest empirical baseline;
- add ARCA/GCG as lower-level raw-coordinate comparators where compatible;
- keep probe sampling conditional on a measured optimization bottleneck;
- keep embedding inversion as contrast material unless it changes the product path.

Acceptance gate:

- Each route ends as one of: implement next, keep as adapter candidate, reject for now, or needs more evidence.

## P2: Research-Phase Mainline — completed

Status: PR0, `model-relative-coordinate-landmarks.md`, and
`math-computation-ai-systems.md` now make the next phase legible.

Follow-up:

- open small implementation issues for finite theory, the replayable real-model engine, and later
  source/leakage experiments;
- keep README, thesis, state-of-play, and backlog synchronized as gates land.

Acceptance gate:

- a new contributor can explain Aleph's next phase without reading chat transcripts;
- every implementation issue names one acceptance gate and the governing research contract.

## P2: White-box / Black-box Evidence Split

Goal: let both evidence modes grow without confusing users or contributors.

Tasks:

- Define which dashboard metrics are always behavioral and which require internals.
- Keep target NLL, token loss, and deletion ablation behind explicit white-box requirements.
- Keep black-box repeated sampling, judge variance, and cost/latency visible as behavioral evidence.
- Record the split in docs before extending UI panels further.

Acceptance gate:

- A reader can tell which observations are measured from logits, which are inferred from outputs, and which are still fixture/simulated.

## P2: Workbench Information Architecture

Goal: make the product feel like an output-to-prompt workbench rather than a single slider demo.

Tasks:

- Clarify the role of the slider relative to candidate cards, dashboard metrics, and evidence panels.
- Keep target output, current prompt, current output, and frontier position visible at a glance.
- Define a simple/research split only if it reduces confusion rather than adding mode noise.
- Verify that left/right endpoint explanations support the product thesis without overclaiming theoretical limits.

Acceptance gate:

- One screen answers what the target is, what the current candidate is, how good it is, and what the next exploration move should be.

## P2: UI Information Architecture Pass

Goal: make the interface answer the next-step question without reading docs.

Tasks:

- Make target, selected candidate, evidence mode, and next action visible at a glance.
- Reduce duplicate explanatory copy inside the app.
- Keep secondary panels useful but subordinate to the compression path.
- Verify desktop and mobile screenshots before merging visual changes.

Acceptance gate:

- A new user can tell what is real, what is simulated, and what to do next within one minute.
