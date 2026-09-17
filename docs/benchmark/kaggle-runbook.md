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
- the immutable v0.1 package receipt's reference tree digest and the observed,
  pinned package-manifest bytes;
- the exact item, prompt, scorer, and scoring-helper byte snapshots used for
  parsing and replay;
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
  --out /tmp/aleph-bench/attempt-2026-09-17T022926Z.json
```

`--max-tokens` is required because the legacy run JSON does not prove the task
invocation argument. The receipt records it under `operatorAssertions` with
`maxTokensSource: operator_asserted_not_present_in_run_json`; it is not promoted
to an observed run fact. The audited task definition has a default parameter,
but that source alone cannot prove that the invocation did not override it.
Supply the value only from contemporaneous operator evidence. This audited task
replay accepts only the task's reviewed `512` cap and a fixed four-token
near-cap margin; changing either could turn the same truncated run from
`blocked` into `valid`, so overrides fail closed.

The package root may be a copied package, but its complete file set and bytes
must match the checked-in immutable v0.1 package receipt. The replay command
never edits that package. The receipt calls the whole-tree value
`referencePackageTreeSha256` because it comes from the immutable v0.1 receipt;
it is not falsely presented as a simultaneous observation of every package
file. The manifest and the four inputs actually parsed or executed are opened
once, length- and digest-checked, and used from those same in-memory snapshots.
The scorer never re-reads an operator-controlled path.

Use a new, attempt-specific output name every time. Existing outputs are never
replaced, including if another process creates the name between validation and
publication. The writer resolves the path once, opens directory components
without following symlinks, rechecks that the opened directory is not the
scorer package, fsyncs the new file, and publishes it with a no-replace link.
This prevents a stale successful receipt from being mistaken for a later failed
attempt.

## Exit status and blocked receipts

The command writes the receipt before deciding its exit status:

- `0`: structurally complete and scalar-replayable, conditional on the recorded
  operator assertion, with no empty, invalid-usage, or near-cap diagnostics;
- `2`: a canonical receipt was written, but at least one output was empty, had
  zero or cap-inconsistent token usage, or was within four tokens of the audited
  `512` cap. The run is operationally blocked and must not be treated as valid
  leaderboard evidence;
- `2` with no receipt: structural or identity failure, including missing,
  duplicate, or unexpected conversations; prompt drift; non-string output;
  duplicate JSON keys; invalid UTC timestamps; package drift; scalar mismatch;
  or an unsafe input/output path.

Whitespace-only output is classified as empty for the diagnostic, while its
original string remains unchanged in `submissionRows[].outputText`. Near-cap is
an explicit conservative heuristic because the retained legacy run does not
include a provider finish reason.

The source must be a regular, non-symlink file and is read once through a
bounded descriptor. The fixed safety limits are 8 MiB for the run JSON, 4,096
Unicode code points per prompt, 8,192 per assistant output, and 262,144 across
all assistant outputs. The retained v16 run is 255,737 bytes, with a 321-code-
point largest prompt, 441-code-point largest output, and 15,436 assistant-output
code points in total, so these limits leave substantial headroom while keeping
the legacy quadratic edit scorer bounded.

## Determinism and artifact identity

Receipt JSON uses UTF-8, sorted keys, two-space indentation, finite numbers
only, and one trailing newline. Its artifact id is the SHA-256 of a compact,
sorted representation of every receipt field except the id itself. Replaying
the same run with the same immutable package and operator assertions
therefore produces identical bytes and the same id. Changing model, task,
dataset, scorer, output, usage, or operator assertions changes the id. The
scoring config digest covers only scorer-owned configuration; it does not
silently absorb operator assertions.

Serialization also rechecks cross-field semantics that JSON Schema alone cannot
express: diagnostics must be exactly derivable from the rows; row,
conversation, and request identities must agree; the two scalar fields must
match inverse AURC; repeated model, canary, dataset, scorer, and config claims
must agree; and all pinned identities must remain the audited values. Recomputing
the content id cannot make a contradictory receipt valid.

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
