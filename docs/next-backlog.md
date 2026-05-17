# Next Backlog

This file turns the post-Hackathon state into small reviewable work. Promote an item to a GitHub issue when someone is ready to own it.

## P0: Make The Active Surface Unambiguous

Goal: one obvious place to change the product UI.

Tasks:

- Decide whether `web/` remains the active app, moves under `apps/web`, or replaces the Vite console.
- Update the root workspace only after the path decision.
- Archive or delete the inactive UI path after useful pieces are migrated.
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

## P1: First Real Run Loop

Goal: replace one fixture path with a real black-box or local adapter path without changing UI data shape.

Tasks:

- Choose hosted black-box or local adapter as the first repeatable run route.
- Return candidates, selected candidate, and observations as `AlephRun`.
- Make failure modes visible in the UI and API response.
- Record a verification receipt in `docs/verification.md`.

Acceptance gate:

- One command can produce a non-fixture `AlephRun`.
- The UI can load it without a parallel model.

## P1: Metric And Leakage Decision

Goal: stop treating scoring as a vague placeholder.

Tasks:

- Compare exact/edit distance, char n-gram, embedding similarity, LLM judge, and composite scoring.
- Define leakage with n-gram overlap plus copy ratio first; consider entity-copy limits separately.
- Add tests for edge cases: empty prompt, explicit reconstruction, paraphrase, named entities, numbers.
- Record the chosen default in a decision note if it affects the run contract or public claims.

Acceptance gate:

- Candidate ranking can be explained from visible sub-scores.
- Non-leaking mode has a testable rule, even if it remains conservative.

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

Goal: use research to widen the implementation horizon without smuggling it into product claims.

Tasks:

- Revisit ARCA and Reversing LLMs for fixed-length prompt search.
- Revisit GCG/nanoGCG for hard-prompt optimization risk and integration cost.
- Revisit probe sampling only if optimization speed becomes the bottleneck.
- Keep embedding inversion as contrast material unless it changes the product path.

Acceptance gate:

- Each route ends as one of: implement next, keep as adapter candidate, reject for now, or needs more evidence.

## P2: UI Information Architecture Pass

Goal: make the interface answer the next-step question without reading docs.

Tasks:

- Make target, selected candidate, evidence mode, and next action visible at a glance.
- Reduce duplicate explanatory copy inside the app.
- Keep secondary panels useful but subordinate to the compression path.
- Verify desktop and mobile screenshots before merging visual changes.

Acceptance gate:

- A new user can tell what is real, what is simulated, and what to do next within one minute.
