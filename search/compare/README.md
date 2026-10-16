# Matched-budget comparison (search/compare)

The comparison slice of the MiniPrompt/ACR work: run the raw-coordinate
MiniPrompt scan (`search/miniprompt/`) and Aleph's readable search procedure
(`search/aleph_search.py`) against the same declared targets under matched
declared budgets inside one shared wall-clock envelope, and archive a
digest-bound per-target comparison record. The declaration and evidence rules
live in
[`docs/research/miniprompt-matched-budget-comparison-note.md`](../../docs/research/miniprompt-matched-budget-comparison-note.md).

## Findings vocabulary (fixed by the schema version)

- `rawFound` — the raw receipt's own scan result: acquisition is exact
  teacher-forced all-match plus a matched greedy continuation recorded from raw
  IDs; free-token IDs are the ground truth and decoded text is a declared
  rendering.
- `readableFound` — the minimum-length non-explicit point with
  `epsilon <= tau`, or null.
- `readableBest` — the minimum-epsilon non-explicit point regardless of tau.
- `readableExactMinLength` — minimum length among non-explicit points whose
  recorded output equals the target string (after stripping), or null.
- `explicitBaseline` — the tagged explicit-reconstruction point (the copy
  baseline); it is never a found readable coordinate.

Copy/leakage annotation is recorded on the readable side only, as ratios
(`promptContainsTargetText`, `promptTargetTrigramContainment`) — never as a
leakage verdict. Raw coordinates carry no leakage field.

## Layering

- `config`, `record`, `fixtures` — pure standard library; importable and
  testable without MLX. `record` carries the record builder and the two
  fail-closed verifiers (`verify_readable`, `verify_comparison`).
- `readable.py` — the MLX readable-side runner (opt-in; imports `mlx`/`mlx_lm`
  only in explicit run paths).
- `run.py`, `cli.py` — the instance driver (spawns the heavy steps as bounded,
  resumable subprocesses) and the command line.

## Commands

Run or resume an instance (needs the pinned MLX venv and the cached snapshots):

```bash
search/.venv/bin/python -m search.compare.cli run --instance canary-1p7b \
    --run-dir /tmp/aleph-compare/canary-1p7b --max-seconds 280
# exit 3 means "invocation budget reached"; re-run the same command to resume
```

Verify a record and both side artifacts without MLX or network:

```bash
python3 -m search.compare.cli verify search/compare/receipts/canary-1p7b
```

## Declared conventions (frozen with the schema versions)

- The config declares budgets ascending (`[6, 12, 25, 50]`); the readable arm
  executes them descending, with each smaller budget seeded by compressing the
  previous budget's best prompt (the shipped procedure's carry).
- `envelopeSeconds` plus the declared `ENVELOPE_SLACK_SECONDS=60` bound both
  sides' recorded wall clocks; only completed artifacts (`stoppedBy=complete`)
  are archived, and runs that pause at the envelope boundary are not archived.
- Wall-clock convention: raw = the sum of the receipt's recorded trajectory
  step seconds; readable = the sum of the runner's recorded operation seconds
  (proposal/evaluation/scoring; model load excluded on both sides).
- The measured output generation runs greedy (temperature 0.0); proposal
  generations use the shipped method constants (propose 0.85, compress 0.5,
  refine 0.6, stability 0.8) and every sampled call is seeded from an explicit
  `random.Random` tree rooted at the declared `proposerSeed`.
- Selection compares recorded (4-decimal) similarities — first-strict-max over
  propose/compress candidates, strict-improvement refinement — so the archived
  selection and the staircase `kept` flags are replayable from the archive
  alone without MLX.
- Declared instances: `canary-1p7b` (`hello world`, `jumps over the lazy dog`
  on the pinned 1.7B snapshot) and `canary-4b` (`hello world` on the pinned 4B
  snapshot).

## Receipts

Archived instances with pinned hashes and outcomes:
[`receipts/README.md`](receipts/README.md), [`receipts/MANIFEST.sha256`](receipts/MANIFEST.sha256).

## Tests

`search/tests/test_compare.py` (part of `npm test`; pure standard library, no
MLX) pins the declared fixtures and digests, the strict config parser, the
readable-artifact verifier with tamper probes, the record builder/verifier
against the real archived raw receipt, the staircase mirror of the shipped
selector, the pure runner helpers, and the no-MLX `verify` command. The
readable runner's state machine is additionally exercised end-to-end with
faked model objects (pause/resume, completion, tampered-artifact refusal)
inside the same module.
