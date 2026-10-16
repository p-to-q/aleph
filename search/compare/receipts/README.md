# Matched-budget comparison receipts

Archived matched-budget comparison instances of `search/compare/` (declared
configurations in `../fixtures.py`; the declaration and evidence rules are in
[`docs/research/miniprompt-matched-budget-comparison-note.md`](../../../docs/research/miniprompt-matched-budget-comparison-note.md)).

Each instance directory holds `comparison.json` (the digest-bound
`aleph-comparison-record/0.1.0` record) and, per target,
`targets/<key>/raw/{receipt.json, cli-output.txt}` (the raw-coordinate scan under
its declared preset) plus `targets/<key>/{readable.json, readable.cli-output.txt}`
(the `aleph-comparison-readable/0.1.0` readable-side artifact). Raw found prompts
are raw coordinates — token IDs are the ground truth and decoded text is a
declared rendering — and carry no leakage field; readable points carry copy
ratios only (`promptContainsTargetText`, `promptTargetTrigramContainment`), never
a leakage verdict.

| Instance | Model | Target | Raw outcome | Readable best |
|---|---|---|---|---|
| `canary-1p7b` | Qwen3-1.7B-4bit | `hello world` | acquired: `nFree=3` (n=5/4/3 in 34/50/21 steps; n=2 failed in 200), `wholePromptTokens=5` | min-ε point `\|p\|=12`, ε=0.5793; no point ≤ τ=0.05 |
| `canary-1p7b` | Qwen3-1.7B-4bit | `jumps over the lazy dog` | not acquired under the declared control budgets (n=5/60, n=10/72; `max_attempts`) | min-ε point `\|p\|=5`, ε=0.1940 |
| `canary-4b` | Qwen3-4B-4bit | `hello world` | acquired: `nFree=3` (n=5/4/3 in 21/17/30 steps), `wholePromptTokens=5` | min-ε point `\|p\|=6`, ε=0.5055; no point ≤ τ=0.05 |
| `canary-1p7b-set2` | Qwen3-1.7B-4bit | `42` | acquired: `nFree=5` (n=5 in 32 steps; n=4 failed in 200), `wholePromptTokens=7` | min-ε point `\|p\|=15`, ε=0.3953; no point ≤ τ=0.05 |
| `canary-1p7b-set2` | Qwen3-1.7B-4bit | `to be, or not to be` | acquired: `nFree=6` (n=10/9/8/7/6 acquired in 75/57/64/240/51 steps; n=5 failed in 200), `wholePromptTokens=13` | min-ε point `\|p\|=42`, ε=0.2351; no point ≤ τ=0.05 |
| `canary-4b-set2` | Qwen3-4B-4bit | `jumps over the lazy dog` | acquired: `nFree=10` (n=5 failed in 60; n=10 in 48 steps), `wholePromptTokens=16`; rendering roundtrip flag recorded `false` | min-ε point `\|p\|=24`, ε=0.1901; no point ≤ τ=0.05 |

Recorded totals: `canary-1p7b` `rawAcquired=1/2`, `readableFoundUnderTau=0/2`;
`canary-4b` `rawAcquired=1/1`, `readableFoundUnderTau=0/1`; `canary-1p7b-set2`
`rawAcquired=2/2`, `readableFoundUnderTau=0/2`; `canary-4b-set2` `rawAcquired=1/1`,
`readableFoundUnderTau=0/1`.

Verify without MLX or network:

```bash
python3 -m search.compare.cli verify search/compare/receipts/canary-1p7b
python3 -m search.compare.cli verify search/compare/receipts/canary-4b
python3 -m search.compare.cli verify search/compare/receipts/canary-1p7b-set2
python3 -m search.compare.cli verify search/compare/receipts/canary-4b-set2
```

`receiptDigest` is the `aleph-canonical/0.2.0` digest of the record body; every
side artifact and the declared config are referenced by digest and re-verified:
the raw receipts by their own fail-closed verifier (scan-policy replay plus the
all-match/greedy-continuation evidence chain), the readable artifacts by the
comparison verifier (evaluation sequence and budget structure, per-budget
first-strict-max selection, staircase `kept` flags, stability runs, copy ratios),
and the cross-side identity assertions and findings are recomputed. `cli-output.txt`
files are the captured output of the runs. `MANIFEST.sha256` pins every file in
this directory.
