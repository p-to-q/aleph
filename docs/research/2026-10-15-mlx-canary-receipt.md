# MLX canary receipt — one real local run (PR C of #106)

Date: 2026-10-15 · Branch: `codex/mlx-canary` · Producing commit: `c7f51f9`
(full `c7f51f9cf2a869b1f125ce51ad263054e7436319`, rebased onto `925e6a1`,
`gitTrackedDirty: false`) · Bundle: `search/engine/receipts/aleph-mlx-canary-001/`

**Claim: supported.** The on-disk run bundle described here was produced by one
real local run of the pinned model, and it re-verifies from disk under an
MLX-free interpreter. Per #106 PR C, success means the artifact verifies — it
is not a claim that the model found a strong coordinate, and a negative canary
outcome would also have been acceptable.

## Setup

- Host: macOS arm64 (MacBook-Pro-7.local), Metal available.
- Runtime: Python 3.13.2 (`search/.venv`), mlx 0.31.2, mlx-lm 0.31.3 — the
  pinned versions, enforced fail-closed before the run.
- Model: `mlx-community/Qwen3-1.7B-4bit` @
  `3b1b1768f8f8cf8351c712464f906e86c2b8269e`, resolved from the local Hugging
  Face cache. The resolver never resolves `main` and never substitutes
  another revision.
- Target: repository-authored smoke target `"42"` (word-spelled seeds),
  `observationMode: black_box`.

## Run

Command (from the repository root):

```text
search/.venv/bin/python -m search.engine.canary run \
    --bundle search/engine/receipts/aleph-mlx-canary-001 \
    --created-at 2026-10-15T11:21:00Z
```

`createdAt` is a caller-declared string; the kernel never reads the wall clock.

Result: `status: completed` · `confirmationOutcome: confirmed` ·
`selectedCandidateId = confirmedCandidateId =`
`sha256:0ecfd39ac793ef07f09bb3aef692cb0d1ba42d0b48ccd30eecf22e7eea6ec842`.

Projected candidates (four discovery-evaluated candidates; ids truncated to
8 hex — full ids in `exports/aleph-run.json`):

| candidate | label | greedy continuation | fit | stability | compression | leakage |
| --- | --- | --- | --- | --- | --- | --- |
| `0ecfd39a…` (selected) | Delete | `Twenty-one plus twenty-one is: … **21 + 21 = 42** …` | 1 | 1 | 0.222222 | 0 |
| `e825eccb…` | Seed | `21 + 21 = 42` | 1 | 1 | 0.105263 | 0 |
| `8855c417…` | Seed | `42` | 1 | 1 | 0.090909 | 0 |
| `c6a0d4bc…` | Reference | `42` | 1 | 1 | 0.066667 | 0 |

The `explicit_reconstruction` control (`sha256:edb942e1…`) is policy-excluded
from the projection and listed in `omittedCandidateIds` with reason
`policy_excluded`; it stays in the linked bundle.

Digests (all `sha256:`):

- stream `e006520961ce3ae2ff2322f1c8179bb8ba6636c5851243ed591ee96e44b67e77`
- materialized: archive `16511e86c29a801573b49b25d2dc62f0434d17fa2e1ee7a0a1c357241c0dec31`,
  confirmation `66f5c030b415079b3d727a0bc9ce303d1c0b0b90d4dfaecbb2e977f7036e420d`,
  resource-ledger `901fc8432d31bd19c6f6dcf8e38b239f65dc6bfb6ff5b6847b412c126a7301bf`,
  views `16bc2389c9b74e6975c0d36b18fb9d5a462045278d0f96c1f44ffa500ee84961`
- projection `c82da1ca9c2c6c1a2497c7daa315db6104c26a53cff34411f6fefc00a9f15893`
- exports: `aleph-run.json` `e4a5699788f63100a676531ce4402876e819247019d943d157d7891141a81577`,
  `aleph-run-projection.json` `1dada714aa65bca51faf61151ef9e4edf5b0abd1ba60289c11c29113e7a45dea`

Resolved file digests (9 files incl. `model.safetensors`) are recorded in
`manifest.json` and `verify.json`; e.g. `tokenizer.json`
`aeb13307a71acd8fe81861d94ad54ab689df773318809eed3cbe794b4492dae4`.

## Independent verification

```text
python3 -m search.engine.canary verify --bundle search/engine/receipts/aleph-mlx-canary-001
```

Run with system Python 3.10.9 and MLX absent
(`importlib.util.find_spec("mlx") is None`): `ok: true`, `errors: []`,
matching stream and materialized digests (see `verify.json` in the bundle).

## Notes

- Canary metrics are declared surface proxies, not the research metric
  contract.
- Engine suite on this tree: `Ran 432 tests … OK (skipped=4)` — 3
  Node-dependent JCS differential skips plus the opt-in live test
  (`ALEPH_RUN_MLX_CANARY=1` gates the live run).
- Default CI needs no Metal; this receipt and its bundle are the durable
  research artifact for the run. Re-verify from disk with any MLX-free
  Python; the live run itself reproduces only on the pinned Apple Silicon
  host and local snapshot.
