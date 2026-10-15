# Receipt: MLX GCG feasibility probe for the MiniPrompt reproduction (2026-10-15)

This receipt records the bounded feasibility probe behind
[miniprompt-reproduction-note.md](miniprompt-reproduction-note.md). It is evidence for
*mechanics and cost* only: no compression, memorization, or baseline-performance claim is made,
and no comparison with upstream numbers is implied.

## Environment

- Host: macOS 26.5 (arm64); probe window 2026-10-15T22:07Z–22:26Z (UTC).
- Python 3.13.2 in `/Users/dujiayi/code/aleph/search/.venv`; mlx 0.31.2; mlx-lm 0.31.3;
  transformers 5.8.1; MLX device GPU.
- Model: `mlx-community/Qwen3-1.7B-4bit`, revision
  `3b1b1768f8f8cf8351c712464f906e86c2b8269e`, weights blob
  `sha256:0e86d9677e519323849eac1bc272caae88567a481ff188c431f70be543d9995f` (local HF cache;
  loaded via `mlx_lm.load`, vocabulary 151936, input embedding is `QuantizedEmbedding`).
- Upstream reference for the loop being probed: `locuslab/acr-memorization` @
  `bf3ba2e7bf224482928fba42cd79c295796c0237`, `prompt_optimization/gcg.py` and
  `miniprompt.py` (sources and hashes in the note; evidence copies under
  `/tmp/acr-repro-sources/`).

## Script and evidence files

All under `/private/tmp/aleph-miniprompt/`; hashes in `MANIFEST.sha256` (sha256):

| File | sha256 |
|---|---|
| `probe_gcg_mlx.py` | `0f3f0d61e6eaf33cb69025e65e23bf1e89e3a5576b937d01fc45b35865008c37` |
| `greedy_check.py` | `3c62ea2e5ede47253ac417548e33ff16f726cba9f42b22d4e92f8c45ffded124` |
| `probe-1.json` / `probe-1.log` | `55c2a7b3aabffb4f03d49a8b4f43614d413c7beea5fb9df28859a665892710f2` / `9a83d832378ecb72488c6ab259b380b8bec0c011bfc50443668ce18cfd3e0076` |
| `probe-2.json` / `probe-2.log` | `207447eda0f3d78c492d8fa8bc33053be6d4097393443354d35c83724e747515` / `d6a14852f4847cae239459a485c164a0d616369c51b4086e41de106a99f6bd60` |
| `probe-3.json` / `probe-3.log` | `bf81c0fae6b7aa2398c9f96ce288a360d82deae58460df11d22196ba34c0833f` / `93471023dc454d87f7bda2779a76f089fff27ac73bc94e402d7fb33a6c119a58` |
| `probe-4.log` (partial) | `ac76788574f64e007bb11b108c05522ed17a79c2bfcabc430cfec380933dad8c` |
| `probe-5.json` / `probe-5.log` | `f8cc32e801757f23a5b2dc35224488c94572f63d6aadd2ba1b7da34633a97bd9` / `5b5e4341d153de1e5c22c4a5b77f78af560efa4ca23fab7da9a1e23df357b08e` |
| `greedy-check.json` | `2c9a52d793987f59c316ab3c51544bbc9e821c8d112d2600419a0d1f4ade27d9` |

The probe script mirrors the upstream GCG loop: teacher-forced mean cross-entropy over target
tokens; gradient with respect to the input embeddings; `topk=250` descent-direction candidate
tokens per free position; `batch=100` candidates each mutating one random free position;
best-by-loss selection; early stop on all-match teacher-forced argmax. Differences from
upstream, declared: MLX instead of torch; the gradient is taken with respect to the embedding
table output and `embed_tokens.as_linear` produces the per-vocabulary descent scores
(equivalent to the upstream one-hot gradient); free tokens are initialized from a seeded MLX RNG
(`seed=42`).

## Runs

| Run | Command (evidence dir; venv python) | Result |
|---|---|---|
| probe-1 | `probe_gcg_mlx.py --steps 12 --batch 100 --out probe-1.json` | target `jumps over the lazy dog` (IDs `[73, 11793, 916, 279, 15678, 5562]`), 5 free tokens; loss 5.3717 → 2.5775; match 2/6 → 4/6 mid-run → 3/6 at step 11; mean 1.378 s/step. |
| probe-2 | `probe_gcg_mlx.py --steps 200 --batch 100 --out probe-2.json` | same target; final loss 1.4563; match 4/6; no acquisition in 200 steps; mean 1.179 s/step. |
| probe-3 | `probe_gcg_mlx.py --target 42 --steps 240 --batch 100 --out probe-3.json` | **acquired at step 87** (88 steps run, early stop); free IDs `[113822, 115719, 118027, 104922, 97102]`; mean 0.814 s/step; total 1.5 min including load. |
| probe-5 | `probe_gcg_mlx.py --target "hello world" --steps 200 --batch 100 --out probe-5.json` | **acquired at step 10** (11 steps run, early stop); free IDs `[95513, 112369, 5846, 31774, 106998]`; mean 0.892 s/step; total 27 s including load. |
| probe-4 | `probe_gcg_mlx.py --target "jumps over the lazy dog" --n-free 10 --steps 240 --batch 100 --out probe-4.json` | **partial (recorded as such)**: reached step 224 with match 5/6 (loss ≈ 0.96–1.04, ≈1.5–1.8 s/step) when the tool call hit its time budget and the runner was killed; no JSON was written, only the partial log. |
| greedy-check | `greedy_check.py probe-3.json probe-5.json` | For both acquisitions: true greedy continuation from the raw IDs (no retokenization) emits exactly the target IDs (`[19, 17]` → `42`; `[14990, 1879]` → `hello world`); `encode(decode(ids)) == ids` held for both. |

Additional recorded observations:

- Gradient flow through the quantized stack works: every step produced finite gradients and the
  iterate was updated (aggregate loss decreased; per-step upticks occur because each candidate
  mutates one random position).
- The two acquired prompts decode to non-semantic fragments (mixed Chinese/English token
  pieces); IDs are the ground truth. This is the expected shape of a raw optimum and feeds the
  raw-versus-readable separation in the note.
- Target provenance: `jumps over the lazy dog` is the upstream config default target; `42` is
  the repository's canary smoke target; `hello world` is a generic phrase. The 6-token target
  resisted 200–224 steps at both 5 and 10 free tokens, while the 2-token targets were acquired
  in 11–88 steps — a difficulty signal for scan-budget planning, nothing more.
- Aggregate wall time ≈ 13–14 minutes across runs, including model loads (≈ 2–3 s each).

## Re-run instructions

```
cd /private/tmp/aleph-miniprompt
/Users/dujiayi/code/aleph/search/.venv/bin/python probe_gcg_mlx.py --steps 12 --batch 100 --out probe-1-rerun.json
/Users/dujiayi/code/aleph/search/.venv/bin/python greedy_check.py probe-3.json probe-5.json
```

Expected: a JSON trajectory whose loss decreases and whose match improves or holds; exact values
depend on the recorded library versions. The hashes above pin the original artifacts.

## Kill / hygiene note

The probe-4 run exceeded a single tool-call budget and was killed at the boundary. The worker
was checked immediately afterwards (`pgrep -fl probe_gcg_mlx` → no process; the stale runner was
gone), and a leak re-check is part of the slice's verification. This is recorded here because it
directly shaped the phase-2 requirement that runs be resumable; it is not hidden.
