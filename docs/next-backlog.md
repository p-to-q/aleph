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

## P1: Aleph-Bench Real Black-Box M0

Goal: replace the checked-in deterministic mock benchmark receipt with a real black-box receipt while preserving the same benchmark schema.

Tasks:

- Choose three hosted models expected to separate on S2 compositional targets.
- Run `./aleph-bench doctor` and require hosted credentials to be ready before the full run.
- Generate and inspect `./aleph-bench manifest` so reviewers can see the exact non-leaking prompts before spending calls.
- Run Track F through `bench/run.py` with server-side OpenAI-compatible credentials and `--cache-dir .cache/aleph-bench/m0-hosted`; the hosted request shape, bounded retry, one-item `black_box` pipeline, and cache reuse are covered by offline local `/chat/completions` tests.
- Run `./aleph-bench verify --result bench/results/m0-hosted-run.json --manifest bench/results/m0-hosted-manifest.json` before updating evidence notes.
- Run `./aleph-bench report --result bench/results/m0-hosted-run.json --out bench/results/m0-hosted-report.md` so evidence tables are generated from the result JSON.
- Keep leakage as a gate and keep AURC as the headline metric.
- Record latency, empty-output failures, and any adapter deviations in `docs/benchmark/m0-evidence.md`.

Acceptance gate:

- `bench/results/m0-first-run.json` or a successor result contains three `black_box` model summaries.
- The result validates against `schemas/aleph-bench-result.schema.json`.
- The evidence note distinguishes real black-box behavior from the existing mock pipeline receipt.

## P1: Clear Next PostCSS Audit Finding

Goal: remove the moderate PostCSS advisory from the Next.js dependency tree without forcing a regressive dependency change.

As of 2026-06-03, npm reports `next@latest` as `16.2.7`, and both `next@16.2.6` and `next@16.2.7` still declare `postcss@8.4.31`. A patch upgrade alone does not clear this advisory.

Tasks:

- Track npm advisory `GHSA-qx2v-qp2m-jg93` for `postcss <8.5.10`.
- Keep the current `next@16.2.6` install valid; it currently pins `postcss@8.4.31`.
- Do not use `npm audit fix --force` unless a checked plan shows it preserves the active `web/` app behavior.
- Recheck after each Next.js upgrade or dependency refresh.
- Record the exact validation commands in release notes once the advisory clears.

Acceptance gate:

- `npm ls postcss` exits cleanly.
- `npm audit --json` no longer reports the PostCSS advisory through Next's dependency tree.
- `npm --workspace web run build` and `npm run lint` pass without a forced downgrade or invalid override.

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

## P2: Research-Phase Mainline

Goal: make the next phase legible now that the first short-term plan is mostly complete.

Tasks:

- Write down the repository's current research program in one place.
- Separate workbench identity from benchmark-only or optimizer-only framings.
- Decide which research families are "near-term route", "future adapter", or "contrast only".
- Keep README, thesis, and backlog aligned with that distinction.

Acceptance gate:

- A new contributor can explain Aleph's next phase without reading chat transcripts.
- The repo has one explicit research-direction document and linked backlog items.

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
