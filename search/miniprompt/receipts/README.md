# MiniPrompt reproduction receipts

Archived end-to-end runs of `search/miniprompt/` (declared configurations in
`../fixtures.py`; the scan policy and evidence rules are documented in
`docs/research/miniprompt-reproduction-note.md`). Found prompts are raw
coordinates: free-token IDs are the ground truth and decoded text is a
declared rendering, never a readable prompt.

| Run | Target | Outcome |
|---|---|---|
| `canary-hello-001` | `hello world` | acquired: the scan acquired at n=5, n=4, and n=3 free tokens (steps 34/50/21) and failed at n=2 within the declared 200-step budget, so `numFreeTokens=3`; every acquisition carries an all-match check and a matched greedy-continuation check from raw IDs |
| `control-jumps-001` | `jumps over the lazy dog` | negative/partial control: two declared attempts (n=5 at 60 steps, n=10 at 72 steps) were not acquired; the scan stopped at the declared `maxAttempts` bound |

Verify without MLX or network:

```bash
python3 -m search.miniprompt.cli verify search/miniprompt/receipts/canary-hello-001
python3 -m search.miniprompt.cli verify search/miniprompt/receipts/control-jumps-001
```

`receipt.json` is the archived record (`aleph-miniprompt-receipt/0.1.0`);
`receiptDigest` is the `aleph-canonical/0.2.0` digest of the receipt body and
`configDigest` covers the embedded declared configuration. `cli-output.txt` is the
CLI stdout of the run. `MANIFEST.sha256` pins every file. The strict verifier
replays the scan policy across the recorded outcomes, so a receipt cannot
claim outcomes its own policy could not have produced.
