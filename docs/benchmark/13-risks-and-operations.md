# Benchmark Risks and Operations

This note reconnects the implementation to the original Aleph intent: make elicitation efficiency legible without letting leaderboard pressure blur the object. It is a field note from external benchmark practice plus a local engineering review.

It is deliberately operational. The point is not to collect citations for their own sake, but to turn common benchmark failure modes into concrete repository and launch rules.

## What mature benchmark work keeps doing

### 1. Standardize the eval object, not just the score

HELM frames mature evaluation as standardized, reproducible, and transparent, with datasets, metrics, model interfaces, result inspection, and leaderboards all living inside one explicit framework. The useful lesson for Aleph-Bench is that the benchmark object is not only the headline number. It is the pinned combination of data, harness, metrics, prompts, and inspection surface.

Implication for Aleph-Bench:

- keep `BenchItem`, `BenchResult`, manifest, audit, bundle, and platform package versioned together;
- treat "same score under a different harness" as a different benchmark run, not the same result;
- preserve inspection artifacts, not just aggregate tables.

### 2. Documentation is part of the benchmark, not post-hoc garnish

Hugging Face dataset card guidance makes the `README.md` and YAML metadata the entry point for how users discover, load, and interpret a dataset. BenchmarkCards argues that standardized benchmark documentation reduces misuse and misinterpretation by making objectives, methodology, data sources, and limitations explicit.

Implication for Aleph-Bench:

- keep the package root `README.md` honest enough to stand alone;
- keep `PLATFORM_LAUNCH_CHECKLIST.md` and `EVALUATION.md` in the release package;
- do not let the public mirror depend on repo-internal context that disappears after extraction.

### 3. Static benchmarks saturate and drift away from the real target

Dynabench's central critique still matters: static benchmarks saturate, challenge sets can be narrow or unstable, and model performance on a leaderboard can drift away from the capability we actually care about. Dynamic or adversarial refresh is one answer; careful strata and periodic refresh are another.

Implication for Aleph-Bench:

- keep the public 30-item S2 seed clearly labeled as seed, not final benchmark truth;
- build the future held-out and time-gated splits before trusting public leaderboard movement too much;
- keep canonical-recall items bounded as one stratum so memorization cannot dominate the headline.

### 4. Leaderboards create incentives, so the protocol itself matters

Recent work on leaderboard incentives formalizes something practitioners already feel: once a benchmark matters, people optimize for the board. That does not make leaderboards useless, but it means the protocol needs to resist "benchmaxxing" and report what is fixed.

Implication for Aleph-Bench:

- pin the frozen ladder, decoding, thresholds, tau, k, and run budget in manifest-level artifacts;
- avoid mixing mock, black-box, and white-box evidence on one board;
- version the leaderboard protocol aggressively, because changing the protocol changes the game.

### 5. Platform convenience is not the same thing as platform truth

Kaggle Benchmarks is opinionated: tasks are notebook-native, a single chosen task feeds the leaderboard, and dataset evaluation is row-wise through `.evaluate(...)`. Hugging Face is similarly opinionated: dataset cards, upload shape, viewer compatibility, and repo metadata all affect whether a dataset is usable.

Implication for Aleph-Bench:

- Kaggle needs a real `%choose` path before we can call it live;
- HF needs real post-upload checks even after local dry-run passes;
- "package check passes locally" is necessary but not sufficient for platform correctness.

## The main benchmark traps for this project

### Research and product traps

`Memorization leakage disguised as compression`
Aleph-Bench is unusually exposed here because the object itself is "how little can you say before the model recovers the target." A benchmark like this becomes untrustworthy immediately if overlap-heavy prompts are allowed to count as compression.

Current posture:

- good: leakage is a gate, not a penalty;
- still needed: continue expanding held-out/fresh splits so the benchmark does not become a public puzzle set.

`One scalar that hides the science`
The industry pattern is to collapse many behaviors into one number too early. For Aleph-Bench that would be especially destructive, because the path matters as much as the left endpoint.

Current posture:

- good: AURC, ECL@tau, and Elicit@k keep the object interpretable;
- still needed: keep per-stratum reporting first-class when real hosted rows arrive.

`Benchmarking the harness instead of the model`
This happens when prompt templates, retries, decoding, or hidden search heuristics change but the board keeps pretending the score is directly comparable.

Current posture:

- good: manifest/audit/bundle/package already pin most of the harness;
- still needed: treat any future prompt-ladder or threshold change as a versioned benchmark revision.

`Public leaderboard pressure blurring evidence modes`
This is the biggest reputation risk. If mock pipeline evidence and hosted black-box evidence start to look visually similar, people will quote the wrong thing.

Current posture:

- good: mock evidence is clearly labeled and kept separate;
- still needed: the first public board should refuse to show mock rows as "models ranked."

### Platform and operations traps

`HF dataset card/config drift`
If the card stops matching the files, the repo may still upload but become confusing or partially unusable.

Current posture:

- fixed in this review: the card now declares both `public_s2_items.jsonl` and `public_s2_prompts.jsonl` as explicit configs;
- added guard: HF dry-run now fails if either file is missing from the card.

`HF viewer quirks around split/config shape`
The Hub docs are clear that dataset metadata controls discovery and display, but community reports show that viewer behavior can still be brittle around split naming and configuration edge cases.

Current posture:

- still needed: after the first real HF upload, manually verify the dataset page, file listing, and viewer behavior instead of trusting local dry-run alone.

`Verification scripts polluting the release package`
This is subtle and easy to miss. A validation script that creates runtime artifacts inside the package can make the next validation fail, or worse, sneak extra files into an upload.

Current posture:

- fixed in this review: `kaggle/api_test_smoke.py` now suppresses and cleans `__pycache__`;
- fixed in this review: `check_platform_package` now fails on unexpected files.

`Kaggle notebook shape mismatch`
Kaggle's own quick start assumes a chosen notebook task, row-wise evaluation, and notebook-generated run/task files. A static scaffold that never becomes a chosen task is not enough.

Current posture:

- good: the package now has a visible `@kbench.task` sketch and API smoke test;
- still needed: the first real Kaggle notebook must wire `.evaluate(..., evaluation_data=df)` and `%choose`.

### Engineering traps

`Doc drift`
Benchmark repos lose trust faster than ordinary product repos when docs lag by even a little, because users are already looking for weak spots.

Current posture:

- fixed in this review: implementation docs now need the current test count reflected;
- ongoing rule: benchmark numbers in prose should come from checked artifacts when possible.

`Closed-world package assumptions not enforced`
If the manifest only checks listed files, stale artifacts can survive unnoticed across local runs.

Current posture:

- fixed in this review: package validation now errors on unexpected files;
- added test coverage: temp packages intentionally fail if a stray file is introduced.

`Infra/security backlog silently becoming benchmark debt`
Dependency advisories in the web app are not benchmark-invalidating, but if ignored long enough they become part of the credibility story.

Current posture:

- known residual: `npm audit` still reports three moderate Next/PostCSS issues through transitive dependencies;
- current choice is correct: do not take the regressive forced downgrade path.

## Assessment of the current benchmark block

### Cleanliness

The benchmark area is now in decent shape conceptually: the contracts are explicit, the evidence modes are separated, the platform package is deterministic, and the launch checklist is honest about what is blocked. That is stronger than many early benchmark repos.

The weakest cleanliness point is not conceptual but workflow-related: the benchmark package is now rich enough that it wants extraction boundaries, but it still lives inside a larger product repo with active unrelated changes. That is manageable for now, but not ideal forever.

### Stability

The benchmark block is substantially more stable after this pass:

- package validation is stricter;
- Kaggle smoke no longer dirties the package;
- HF upload prep checks the card more concretely;
- tests cover both positive and stale-file failure paths.

The remaining instability is external:

- first real HF upload and viewer behavior are still unproven;
- first real Kaggle notebook wiring is still unproven;
- hosted black-box evidence still depends on credentials and platform access.

### Reasonableness relative to the original intent

The implementation still matches the original Aleph idea better than a generic leaderboard would. It keeps the path, keeps leakage honest, preserves explicit reconstruction anchors, and avoids pretending that mock rows are real model results.

That is the right shape. The next risk is not "wrong benchmark idea"; it is "premature public surface before the first real hosted result and platform smoke test."

## Concrete next steps

### Now

1. Get real platform credentials in place.
   HF: obtain an `HF_TOKEN` with dataset repo write access.
   Kaggle: log in to the target account and confirm ownership of the dataset namespace plus benchmark notebook access.
2. Do the first real Hugging Face Dataset upload from the current repo using the prepared script.
3. Create the first Kaggle Dataset mirror and notebook stub, then wire the real `%choose` path.

### Next

1. Run one real hosted black-box M0 evaluation with explicit external model credentials.
2. Publish the real hosted result as a new evidence bundle, without overwriting the mock one.
3. Add a tiny public-facing benchmark status page or README section that says exactly what is live, mirrored, mock, or blocked.

### Later

1. Extract the benchmark into its own public repo after the first real hosted result and at least one successful HF/Kaggle mirror.
2. Keep the current monorepo as the research/workbench parent, but let the public benchmark repo become the stable distribution surface.

Why not split immediately:

- the current package already acts like an extractable artifact;
- the real blockers right now are credentials, first uploads, and first hosted evidence, not repository topology;
- splitting before the first real platform pass risks spending energy on packaging aesthetics before we have the first live proof.

## Sources worth keeping in mind

- HELM README: standardized, reproducible, transparent evaluation with inspection and leaderboards.
- Dynabench paper: benchmark saturation, human-and-model-in-the-loop refresh, and the limits of static test sets.
- Hugging Face dataset cards docs: the dataset card and YAML metadata are the canonical user-facing entry point.
- Hugging Face upload docs: `create_repo` / `upload_folder` are the normal dataset upload path.
- Kaggle Benchmarks quick start: notebook-native `@kbench.task`, `.evaluate(...)`, and `%choose`.
- lm-evaluation-harness task guide: shareable task configuration is part of reproducibility, not just code.
- BenchmarkCards: benchmark documentation reduces misuse and misinterpretation.
- NeurIPS Datasets & Benchmarks track CFP: hosting, code availability, and Croissant metadata are now standard expectations.
- Overfitting meta-analysis and leaderboard-incentives work: public boards shape participant behavior, even when the holdout itself is robust.
