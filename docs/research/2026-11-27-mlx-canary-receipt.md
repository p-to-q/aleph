# Mainline MLX canary acceptance — 2026-11-27

This receipt completes the local MLX delivery slice of issue #106. A real local
run of the exact pinned checkpoint completed, and its closed bundle replays from
disk. The smoke target is repository-authored `42`; the metrics are declared
surface proxies. This is implementation and accounting evidence, not a model
performance benchmark or a shortest-coordinate result.

## Producing source and runtime

- Producing commit: `8377dd335b5eeb7a33759749d73c9e2adefa396d`;
  tracked and untracked working tree checked clean immediately before execution;
  the runner also reports `gitTrackedDirty: false`.
- Start declared from the actual UTC clock: `2026-11-26T19:02:13Z`
  (2026-11-27 03:02:13 Asia/Shanghai).
- macOS 26.5 arm64, Python 3.13.2, MLX 0.31.2, mlx-lm 0.31.3.
- `mlx-community/Qwen3-1.7B-4bit` at immutable revision
  `3b1b1768f8f8cf8351c712464f906e86c2b8269e`.
- Nine resolved model/tokenizer/config files are hashed in the manifest and
  [runner summary](2026-11-27-mlx-canary-summary.json). The 968,080,210-byte
  weight file matched SHA256
  `0e86d9677e519323849eac1bc272caae88567a481ff188c431f70be543d9995f`
  before execution. The runner does not resolve `main` or substitute a revision.

## Run and retained evidence

```sh
python -m search.engine.canary run \
  --bundle search/engine/receipts/aleph-mlx-canary-20261127 \
  --run-id aleph-mlx-canary-20261127 \
  --created-at 2026-11-26T19:02:13Z
```

Use the pinned MLX environment for this opt-in command. A fresh bundle path is
required; no overwrite or paid/hosted fallback is allowed.

- `status: completed`, `confirmationOutcome: confirmed`.
- Five archived candidates, four projected discovery candidates, one policy-
  excluded explicit-reconstruction control retained in the complete bundle.
- Selected and confirmed candidate:
  `sha256:0ecfd39ac793ef07f09bb3aef692cb0d1ba42d0b48ccd30eecf22e7eea6ec842`.
- Six retained evaluation receipts, two greedy samples each; three deterministic
  proposal calls. This is 12 local sample generations, not six hosted calls.
- All input-token counts sum across every sample. Raw texts, local mlx-lm token
  counts, finish reasons, metric token IDs, and exact coordinate/target token IDs
  are retained for measurement replay. These are local runtime counts, not
  hosted-provider billing evidence.
- The ledger keeps all six accounts separate. Unknown post-run replay/test/human/
  proof counters remain `null`; this external receipt records completed checks
  without rewriting frozen pre-run configuration or historical evidence.
- Stream SHA256:
  `43777d23d6e5ca086266336da64467636f560b8019176f90baf4423c64895886`.

Bundle: [`search/engine/receipts/aleph-mlx-canary-20261127/`](../../search/engine/receipts/aleph-mlx-canary-20261127/).
The runner summary is deliberately outside the closed-world bundle.

## Independent acceptance

Both commands completed with `ok: true`, no errors:

```sh
python3 -m search.engine.canary_evidence search/engine/receipts/aleph-mlx-canary-20261127
python3 -m search.engine.canary verify --bundle search/engine/receipts/aleph-mlx-canary-20261127
```

A separate Python 3.14.7 process with site packages disabled (`-S -B`) also
replayed six evaluations successfully; `mlx` was unavailable and the scheduler
module was not imported. The verifier checks structure, digests, retained-token
proxy arithmetic, sample-usage sums and selected-text consistency. It does not
prove honest execution or independently retokenize with an external tokenizer.
Continuation metric IDs tokenize the stripped sample text; they are not claimed
to be the runtime's original generated-token array.

`npm run lint`, `npm test`, `npm run build`, and `git diff --check` passed on the
source tree. The full test run reports 134 search tests, 475 engine tests with
one opt-in live-test skip, and 17 optional MiniPrompt skips; the additional
adapter/arithmetic subset passed 15 tests. The real canary above was run
explicitly, outside the default test suite.

## Limits and next gate

The historical October receipt remains unchanged; its legacy ledger has
structural-only verification and is not upgraded to new measurement evidence.
Repeated greedy outputs do not establish stochastic stability. The canary does
not claim scientific non-leakage, ECL, portable scorer qualification, full
prefix-free coding cost, or generalization. The legacy public frontier is still
historical. Kaggle #107 remains a separate bounded authorization and receipt
gate; this work neither activates old queues nor publishes to Hugging Face.
