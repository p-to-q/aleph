# Frontier Receipts Practice Note

Status: gate note for the frontier regeneration slice (new on-disk format plus public artifact
surface), recorded under the structural decision research gate in
[research-process.md](research-process.md). Access date for all sources below: 2026-10-15.

## Question

Four recorded requirements say the historical public MLX frontier must not supply evidence until
every displayed point is regenerated from actual evaluations:

- [research-directions.md](research-directions.md) Track C: "The historical MLX frontier is not
  performance evidence; it must not be reused until every displayed point is regenerated from
  actual observations under the repaired frontier semantics."
- [open-questions.md](../open-questions.md) "Search strategy": "supplies no valid performance
  point until repaired and regenerated."
- [research-process.md](research-process.md) "Current gaps": "remains invalid until every
  displayed point is linked to an actual evaluation and the artifact is regenerated with
  receipts."
- [iclr-readable-coordinate-program.md](../plans/iclr-readable-coordinate-program.md): "predates
  that repair and remains invalid until regenerated from actual evaluations and receipts"; a
  cumulative value function may repeat the best value at larger *budgets*, but "those points must
  be labeled as budget thresholds, not emitted as measured candidate coordinates."

What on-disk shape makes one displayed point verifiable against one real evaluation, and what
prior art should that shape follow instead of inventing new vocabulary?

## Sources inspected

| Source (accessed 2026-10-15) | Location | F — what was observed | I — interpretation | U — use here |
|---|---|---|---|---|
| in-toto/SLSA attestation mapping (surveyed in this repository) | [engine-and-benchmark-practice-review.md](engine-and-benchmark-practice-review.md); original URLs recorded there | Attestations bind a digest-matched subject to a predicate; provenance separates the frozen definition from run evidence. | Bind claims to artifacts by digest, never by position; keep the definition/run split explicit. | A receipt references its prompt and target by digest; artifact points link to receipts by `receiptDigest`, independent of order. |
| Engine bundle receipts (PR A/B, on main) | `search/engine/` (`EvaluationReceipt`, `verify.json`, `manifest.json`) | Every state change is a typed receipt; the append-only stream is the authority; materialized views are disposable projections. | A consumer-facing artifact should cite receipts rather than re-encode the archive. | The sidecar carries the evaluation record; the displayed artifact stays a projection whose points summarize raw outputs as observed fields plus digests. |
| ADR 0006 `aleph-canonical/0.2.0` and the JS recomputation surface | `docs/decisions/0006-canonical-json-jcs-alignment.md`; `scripts/aleph-canonical.mjs` | Canonical bytes are an exact JCS-aligned text form; the Node module recomputes digests with `node:crypto` only. | Receipt self-digests need an independent recomputation surface, not producer trust. | `receiptDigest`, `promptDigest`, and `outputDigest` are recomputed in `scripts/check-public-frontier.mjs` through `aleph-canonical.mjs` (Node-side only; no browser digest path). |
| `lm-evaluation-harness` release artifacts (surveyed in this repository) | research-process.md source table (lm-eval row) | Results ship with config, versions, seeds, and per-sample logs alongside aggregate numbers. | A bare aggregate is hard to audit; ship the raw sample with the number. | Each receipt keeps the raw generated text, token trace, and stability run similarities, not only the final scalar coordinates. |

## Decision and structural effect

1. New format `aleph-frontier-receipts/0.1.0`, written by `search/frontier_receipts.py run` to
   `web/public/aleph-frontier.receipts.json`. One receipt per evaluated point: `target` /
   `targetDigest`, `prompt` / `promptDigest`, `model` (repo, revision, weights digest), `metric`
   descriptor, `procedure` constants, `measurement` (generation seconds, max tokens, stability
   runs/temperature/similarities), observed fields (`epsilon`, `similarity`, `stability`,
   `length`, `output`, `toktext`, `toknll`), `supersedes` (the historical values and
   `outputIdentical`), `status`, and `receiptDigest` = `aleph-canonical/0.2.0` digest of the
   receipt body.
2. Artifact points gained `receiptDigest`; `scripts/check-public-frontier.mjs` enforces
   one-to-one linkage: every displayed point resolves to exactly one displayed receipt (target,
   model repo, and every measured field must match), orphaned displayed receipts fail closed, and
   the receipt counts are re-derived.
3. `search/frontier_receipts.py run` re-derives each target's token count and prompt length and
   refuses mismatches; checkpoints make the run resumable. `verify` re-checks the checked-in
   artifact against the checked-in receipts with no MLX import.
4. No new dependency, no new service, no new process. The Node checker remains the verification
   surface; there is still no browser digest path.
5. Disposition of the historical export: it stays retrievable from git history (the branch base
   `814c7d3` holds the pre-regeneration file). Candidate coordinates were carried over unmodified
   as inputs to a fresh evaluation; every displayed measurement is new, and superseded historical
   values are kept per receipt under `supersedes`, never reused as evidence.

## What the regeneration found

- All 30 displayed points were re-measured locally on 2026-10-15 with the pinned
  `mlx-community/Qwen3-4B-4bit` and `mlx-community/Qwen3-1.7B-4bit` revisions recorded on
  `run.models`.
- 29/30 generated outputs were byte-identical to the historical export; the single differing
  output is the length-15 `spring` point.
- 21/30 fit values reproduced exactly (the English embedding metric is bit-stable); the 9 CJK
  `spring`/`crush` points shifted slightly, with the declared character-trigram Jaccard formula
  recorded as the metric of record on their receipts. Stability is a fresh three-sample measure
  for every point and changed on 25/30 points; it is recorded as re-measured, not as a correction
  of the historical number.

## Reproduce

```bash
python search/frontier_receipts.py run     # re-measure (pinned MLX env; resumable, checkpointed)
python search/finalize.py --no-merge       # publish the measured points
python search/add_pitch.py                 # keep the display reveal first
node scripts/check-public-frontier.mjs     # artifact <-> receipt linkage
```

## Boundary — what receipts do not establish

- The regenerated artifact is product/demo evidence with per-point receipts; it is not a
  benchmark-grade performance result (no release statistics and no statistical-significance
  policy applied; one local environment).
- Receipts record what one declared procedure measured at measurement time; the checker verifies
  linkage and canonical form only and never calls a model.
- The `pitch` entry is a display reveal and deliberately carries no receipt.
- `filtered` receipts may exist (none today); the checker fails closed on displayed receipts
  without a point, not on filtered ones.

## Verification

- `search/tests/test_frontier_receipts.py`: 21 tests (canonical digests, receipt body shape,
  refusal paths, resumability, selection status, fail-closed verify).
- `npm test` green after regeneration: `search/tests` 62 tests, engine 444 tests (skipped=3),
  canonical parity 126 pinned assertions / 2448 differentials.
- Nine crafted tamper cases all fail closed and a restore re-passes: mutated receipt digest; raw
  prompt mutation; prompt mutation with recomputed receipt digest (caught by `promptDigest`);
  missing point linkage; referenced receipt marked `filtered`; deleted receipt; duplicate receipt
  digest; inflated counts; drifted artifact `epsilon`.

## Cross-links

- [research-process.md](research-process.md) — gate and "Current gaps".
- [research-directions.md](research-directions.md) — Track C.
- [open-questions.md](../open-questions.md) — §4 "Search strategy".
- [checks.md](../checks.md) — "Public frontier receipts".
- `search/frontier_receipts.py`, `web/public/aleph-frontier.receipts.json`,
  `scripts/check-public-frontier.mjs`.
