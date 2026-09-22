# Platform release policy

Aleph Bench has one public Kaggle identity:

- **name:** `Aleph Bench`
- **URL:** <https://www.kaggle.com/benchmarks/jahyee/aleph-bench>

That page is the long-lived leaderboard. New protocol versions and verified model results are
published there instead of creating another public Aleph benchmark. Git remains the source of truth;
Kaggle and Hugging Face are versioned distribution surfaces.

## Asset roles

| Surface | Visibility | Purpose | May publish a score? |
| --- | --- | --- | --- |
| Canonical Kaggle benchmark | Public | Stable leaderboard and model comparison entry point | Yes, after the publication gate |
| Release task | Private while validating; public only when promoted | One frozen protocol version used by the canonical benchmark | Yes, after promotion |
| Capture canary | Private | Six-call transport, output, usage, and evidence check | No |
| Deployment diagnostic | Private | Runtime, package, SDK, and model-transport diagnosis | No |
| Hugging Face dataset and Space | Public after release | Dataset card, versioned data, receipts, and a reproducible view of verified results | Only verified release results |

Private tasks may use descriptive versioned slugs. They are engineering surfaces, not additional
benchmark brands. A task becoming public does not create a second public benchmark; it is attached to
the canonical benchmark only after promotion.

## Promotion gate

A task or model row can be added to the public leaderboard only when all of the following are true:

1. The frozen dataset, call plan, model mapping, runtime, scorer, and rerun policy are identified by
   immutable versions and digests.
2. Every hosted run is selected by exact task version and exact run ID. Ambiguous or partial evidence
   fails closed.
3. Capture shards form the declared complete, non-overlapping set; the canonical Python 3.13 / UCD
   15.1 replay produces a verified `BenchManifest` and `BenchResult`.
4. Raw outputs, usage, call state, receipts, and release artifacts are retained without overwriting a
   prior attempt.
5. A dedicated publication issue and reviewable PR record validation, limitations, and the model
   identity exposed by the platform.
6. A maintainer performs a live readback after publication and records the public URL, task version,
   displayed model, displayed score, and artifact digests.

A capture receipt, diagnostic scalar, canary result, incomplete shard, mock result, or legacy replay
that fails current gates must never be presented as a current public score.

## Version lifecycle

- Keep the public benchmark URL and plain-language title stable.
- Change the attached release task only for a reviewed protocol release. Protocol changes create a
  new task version; they do not silently rewrite historical meaning.
- Preserve historical receipts and document superseded tasks. Prefer private retention or reversible
  archival controls to deletion.
- Add models to the current release task one at a time or in a predeclared batch. Bind and verify each
  run before scheduling the next batch, and stop on quota, identity, completeness, or evidence drift.
- Mirror only the same verified release to Hugging Face. Platform presentation may differ, but result
  identities and digests must agree with the repository.

## Current boundary

The public Kaggle page currently contains a legacy task and historical results. The v0.2 capture
canary is private and is not a replacement release. The canonical page should keep its identity while
the capture assembler, canonical replay, and publication workflow reach their acceptance gates.

Operational details live in the [Kaggle capture runbook](kaggle-capture-runbook.md) and the
[capture-only/canonical-scoring plan](../plans/kaggle-capture-only-and-canonical-offline-scoring.md).
