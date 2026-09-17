# Kaggle run receipt replay

This runbook covers one narrow operation: turning a completed legacy Kaggle
Benchmarks `*.run.json` into a canonical, detailed Aleph receipt without making
model or network calls. It does not create or update a Kaggle task, schedule a
model run, or turn the legacy result into Aleph-Bench v0.2 evidence.

## Why this exists

The deployed legacy task returns one `float`, because that is the value Kaggle
uses for its leaderboard. Kaggle's downloaded run JSON still retains the named
conversations, raw assistant strings, and request usage. The scalar therefore
did not destroy the raw observations, but Aleph previously had no checked-in,
strict way to turn them into a replayable receipt.

`kaggle-replay` fills that gap. It binds the receipt to:

- the exact run JSON bytes;
- the supported task name, version `3`, description, and audited definition
  digest `93020f8ac90bd37e3711b6ad233443fc5e7f1ec4f047a8930f1bbf31039f6e02`;
- Kaggle model slug;
- the immutable v0.1 platform package tree and manifest;
- item, prompt, scorer, and scoring-helper file digests;
- the legacy scoring configuration; and
- an explicit operator assertion about the generation cap used for diagnostics.

It then extracts exactly one named conversation for each of the 180 sendable
prompts, preserves each raw assistant string byte-for-byte after JSON decoding,
replays the immutable packaged scorer, and requires Kaggle's scalar to equal
`1 - AURC` within `1e-12`.

## Command

Download the completed task's `.run.json`, then run:

```bash
./aleph-bench kaggle-replay \
  --run-json /path/to/aleph_bench_frozen_ladder.run.json \
  --package-root bench/results/platform/m0-mock \
  --max-tokens 512 \
  --out /tmp/aleph-bench/kaggle-receipt.json
```

`--max-tokens` is required because the legacy run JSON does not prove the task
invocation argument. The receipt records it under `operatorAssertions` with
`maxTokensSource: operator_asserted_not_present_in_run_json`; it is not promoted
to an observed run fact. The audited task definition has a default parameter,
but that source alone cannot prove that the invocation did not override it.
Supply the value only from contemporaneous operator evidence. The default
near-cap margin is four tokens; override it only when reproducing an explicitly
documented diagnostic policy:

```bash
  --saturation-margin-tokens 4
```

The package root may be a copied package, but its complete file set and bytes
must match the checked-in immutable v0.1 package receipt. The replay command
never edits that package.

## Exit status and blocked receipts

The command writes the receipt before deciding its exit status:

- `0`: structurally complete, scalar-replayable, with no empty or near-cap
  output diagnostics;
- `2`: a canonical receipt was written, but at least one output was empty or
  within the configured margin of `max_tokens`, so the run is operationally
  blocked and must not be treated as valid leaderboard evidence;
- `2` with no receipt: structural or identity failure, including missing,
  duplicate, or unexpected conversations; prompt drift; non-string output;
  non-finite JSON; package drift; or scalar mismatch.

Whitespace-only output is classified as empty for the diagnostic, while its
original string remains unchanged in `submissionRows[].outputText`. Near-cap is
an explicit conservative heuristic because the retained legacy run does not
include a provider finish reason.

## Determinism and artifact identity

Receipt JSON uses UTF-8, sorted keys, two-space indentation, finite numbers
only, and one trailing newline. Its artifact id is the SHA-256 of a compact,
sorted representation of every receipt field except the id itself. Replaying
the same run with the same immutable package and operator assertions
therefore produces identical bytes and the same id. Changing model, task,
dataset, scorer, output, usage, or operator assertions changes the id. The
scoring config digest covers only scorer-owned configuration; it does not
silently absorb operator assertions.

The strict schema is
[`schemas/v0.2/aleph-bench-kaggle-receipt.schema.json`](../../schemas/v0.2/aleph-bench-kaggle-receipt.schema.json).
The schema's own version is `0.2.0`; the receipt explicitly records its source
score protocol as `0.1-legacy`.

## Evidence boundary

This command recovers inspectability for the existing legacy run. It does not
make v0.1 and v0.2 scores comparable and does not satisfy the v0.2 hosted
adapter identity or five-rerun contract.

The observed Kaggle image for the preserved run used Python 3.11, whereas the
v0.2 Unicode scorer fails closed unless it runs on Python 3.13 with Unicode
database 15.1. A future v0.2 Kaggle canary must check that runtime before any
model calls. Do not bypass the runtime check or silently rescore v0.2 with the
host interpreter's Unicode tables.
