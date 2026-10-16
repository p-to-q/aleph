# MiniPrompt/ACR reproduction (search/miniprompt)

Method-level reproduction of the MiniPrompt length scan and the GCG inner loop
of `locuslab/acr-memorization` (pinned `bf3ba2e7`) on MLX, under the declared
interface conditions in
[`docs/research/miniprompt-reproduction-note.md`](../../docs/research/miniprompt-reproduction-note.md).

Found prompts are **raw coordinates**: free-token IDs are the ground truth and
decoded text is a declared rendering, never a readable prompt. Receipts carry
the raw-coordinate labeling, and no readable-prompt or human-eligibility claim
is made for found prompts.

## Layering

- `config`, `scan`, `sampling`, `receipts` — pure standard library; importable
  and testable without MLX.
- `gcg`, `runner` — the MLX execution path; imported only by explicit run
  commands (and the opt-in MLX test module). The pinned snapshot, its weights
  digest, and the declared config are re-checked fail-closed at load time.

## Commands

Run (needs the pinned MLX venv and the cached snapshot):

```bash
search/.venv/bin/python -m search.miniprompt.cli run --preset canary-hello --run-dir /tmp/miniprompt-canary --max-seconds 420
# exit 3 means "paused by the time budget"; re-run the same command to resume
```

Verify a receipt without MLX or network:

```bash
python3 -m search.miniprompt.cli verify /tmp/miniprompt-canary
```

Declared presets live in `fixtures.py` (`canary-hello`,
`control-jumps-partial`, `pin4b-hello-smoke`, `canary-42`, `canary-hamlet-line`,
`pin4b-jumps-smoke`); a run directory holds `state.json` (resumable
checkpoint, written atomically after every step) and `receipt.json` (the
archived record). Receipts are self-verified before they are written.

## Tests

- Pure tests: `search/tests/test_miniprompt.py` (part of `npm test`).
- MLX smoke tests: `search/miniprompt/tests/test_gcg_mlx.py` (skipped without
  MLX; run them with the pinned venv as in the module docstring).
