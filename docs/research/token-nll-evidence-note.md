# Token NLL Evidence Contract Note

Status: gate note for the P2 adapter evidence slice (one schema rule set + adapter strictness +
product labeling; no new module family or dependency), recorded under the structural decision
research gate in [research-process.md](research-process.md). Access date for all sources below:
2026-10-15 (UTC).

## Question

[../next-backlog.md](../next-backlog.md) "P2: Adapter Evidence Contract" records the tasks: decide
which `ObservationSet` fields are required for token NLL; separate white-box adapter output from
simulated UI panels; add a local MLX receipt that covers token NLL shape; and defer deletion
ablation until the scoring route can compute it honestly. The local MLX spike had already begun
returning `toktext`/`toknll` traces on the explicit-reconstruction point, and the API adapter
forwarded them as `ObservationSet.tokenLoss` — but no shape rule said which traces count as
evidence. A truncated, mismatched, or non-finite trace could surface as token evidence, and the
token NLL chips read as model internals while the surrounding panel still said "fixture /
precomputed".

What exact shape makes a token NLL trace admissible as white-box evidence, what should the adapter
do when a trace is malformed, and how should the product label measured traces versus fixture data?

## Sources inspected

| Source (accessed 2026-10-15) | Location | F — what was observed | I — interpretation | U — use here |
|---|---|---|---|---|
| lm-evaluation-harness model API | `lm_eval/api/model.py` at `EleutherAI/lm-evaluation-harness` main; fetched to `/tmp/token-nll-sources/lm-eval-model-api.py` | The `LM` interface types log-probability as a first-class result: `loglikelihood` returns `(logprob, is_greedy)` tuples and `loglikelihood_rolling` returns per-document log-probabilities, with each token predicted exactly once. | The harness treats the model-internal log-probability channel as typed, documented output — and aggregates it to one value per continuation or document. | Token NLL stays a typed channel; Aleph keeps it per decoded token, finer-grained than the surveyed harness contract, and makes no aggregate-level claim from it. |
| Hugging Face generation source, `compute_transition_scores` | `src/transformers/generation/utils.py` at `huggingface/transformers` main; fetched to `/tmp/token-nll-sources/hf-generation-utils.py` | The documented method computes "the scores of the selected tokens at generation time" from per-step logits/log-softmax; the returned tensor carries one score per generated token. | Per-token scores are a standard productized white-box channel, obtained from the generation call rather than recomputed by consumers. | The adapter consumes the engine trace token by token; it never fabricates, interpolates, or truncates losses to make a shape fit. |
| OpenAI OpenAPI schema `ChatCompletionTokenLogprob` | `openai/openai-openapi` master; fetched to `/tmp/token-nll-sources/openai-openapi.yaml` | Token-level log-probabilities have an explicit entry schema (required `token`, `logprob`, `bytes`, `top_logprobs`), a sentinel `-9999.0` for "very unlikely" tokens, and `logprobs: null` examples when the channel is not requested. | Token-level channels get an explicit per-entry schema, sentinels for edge cases, and a typed absent state. | Aleph's entry is `{token, loss ≥ 0}` plus optional 1-based `rank` and `topAlternatives`; sentinels are rejected, and malformed traces fail closed to `black_box` instead of emitting partial evidence. |
| ADR 0004 (in-repo) | [../decisions/0004-white-box-adapter-output.md](../decisions/0004-white-box-adapter-output.md) | Token-level NLL may ride `ObservationSet.tokenLoss` as white-box adapter output; fixture observations stay labeled; black-box runs stay `black_box`; UI panels must not imply full interpretability. | The output boundary and honesty rules are contract, not polish. | The schema rule, adapter strictness, and labels below implement the enforcement ADR 0004 left to later slices. |
| Frontier receipts tooling (in-repo) | `search/frontier_receipts.py` | Receipts normalize `0.0 if value == 0`; the explicit-reconstruction trace saturates float32 log-softmax to `-0.0`. | Saturation produces negative zero, not negative loss; normalization keeps `loss ≥ 0` honest and bytes stable. | The adapter mirrors the normalization before writing entries; the receipt below records the wire trace (`-0.0`) next to the adapted shape (`min=0 max=0`). |
| Recorded requirement (in-repo) | [../next-backlog.md](../next-backlog.md) P2; [../claim-ledger.md](../claim-ledger.md) | Acceptance gate: white-box output validated through schema or typed tests, and labels that keep simulated panels from being mistaken for model internals. | The recorded answer is a shape plus labels, not a new subsystem. | This note, the checks below, and the explorer labels are that answer. |

Source files and sha256:

- `lm-eval-model-api.py` `b8b1db336e168b53d9ca808fe837d5bf8943d9dca76a14cf747e4f3a22d50545`
- `hf-generation-utils.py` `7944240ff1ee27a7b3acc16571b7a480cc14f16e7222aeb1a79d289ebc96e3ea`
- `openai-openapi.yaml` `761157f39a247082a5b67110f5e471680e7bb966920e1d1f782359a5abdeaac7`

Also fetched and checked for coverage at less depth: the lm-eval user guide
(`lm-eval-interface.md`, `354a8e1beb1f00de04e152b0e38d6d010e8031d20eb504580672d8f3369d9487`) and
the Hugging Face text-generation index page (`hf-compute-transition-scores.md`,
`353309d695c3da8ba4a9056f2c3014c12385ecacbb33f6a6d91e20460b7ddedd`); neither changes the reading
above.

## Decision and structural effect

1. **Schema rule.** `schemas/aleph-run.schema.json` pins the token NLL entry: `{token: string,
   loss: number with minimum 0}`, optional `rank` (integer, minimum 1; 1-based) and
   `topAlternatives` (array of strings), with `additionalProperties: false`. `check-contract.mjs`
   keeps the schema in lockstep with the exported `TokenLossPoint` type and the recorded numeric
   rules.
2. **Adapter rule.** `apps/api/aleph_api/services/local_mlx_search.py` (`_token_loss`) admits a
   trace only when it is a non-empty list whose `toktext`/`toknll` lists match in length, every
   token is a string, and every loss is a finite real number ≥ 0 (bools, NaN, infinities, negative
   values, or any mismatch make the whole trace inadmissible). An inadmissible trace drops the
   field and the response is labeled `black_box` — fail closed, never partial evidence. Negative
   zero from float32 saturation normalizes to `0.0`, mirroring `search/frontier_receipts.py`.
3. **Product separation.** `check-run-file.mjs` pins the product loader at the same boundary
   (loss 0 accepted; negative losses and non-1-based ranks rejected with clear issues), and
   `web/app/components/aleph-explorer.tsx` labels receipt-linked points "measured archive ·
   receipts" while fixture fallback data keeps its fixture label; the token NLL evidence heading
   carries the model id.
4. **Receipt.** One live local MLX run covers the shape end to end
   ([2026-10-15-token-nll-receipt.md](2026-10-15-token-nll-receipt.md)): white-box response,
   `entries=10 min=0 max=0` after normalization, with the raw wire capture showing the `-0.0`
   saturation that motivated the normalization.
5. **No new dependency, no new service.** The Node checks, the API tests, and the existing live
   smoke carry the contract; the default `npm run lint` / `npm test` path stays free of MLX.

## Boundary — what the contract does not establish

- Shape validity is not provenance: the checks pin the entry shape only, and one live receipt
  covers one real local model run. Nothing here establishes that a particular trace came from a
  model.
- A present token NLL trace is not prompt quality, leakage evidence, or a shortest-prompt claim;
  the receipt repeats the same non-claims as `npm run api:live-smoke`.
- The hosted black-box path cannot carry this channel; absence must stay `black_box`.
- Deletion ablation and prompt-token attribution remain deferred — there is no honest scoring
  route yet, so they stay UI-shaped and labeled.
- White-box panel completeness is not claimed; the product shows the trace for the
  explicit-reconstruction point (receipt-linked archive points or the live local path).

## Verification

- `scripts/check-fixtures.mjs`: a shape-valid white-box trace passes; six malformed traces
  (negative loss, zero rank, missing loss, non-string token, non-number loss, extra field) fail
  closed with messages.
- `scripts/check-run-file.mjs`: the product loader accepts the loss-0 boundary and rejects
  negative losses and non-1-based ranks.
- `apps/api` tests: `_token_loss` admits the valid boundary, normalizes `-0.0` to `0.0`, and fails
  closed on ten malformed cases; an invalid newer point does not shadow an older valid trace; the
  observation mapping omits `tokenLoss` unless the trace is valid (25 tests in the suite).
- Live receipt: [2026-10-15-token-nll-receipt.md](2026-10-15-token-nll-receipt.md).
- Full suites on the slice are re-run before the PR: `npm run lint`, `npm test`, the `apps/api`
  pytest suite, and `npm --workspace web run build`; results are recorded in
  [../verification.md](../verification.md).

## Cross-links

- [../next-backlog.md](../next-backlog.md) — P2 Adapter Evidence Contract; P2 White-box / Black-box
  Evidence Split.
- [../checks.md](../checks.md) — what the contract checks prove and do not prove.
- [../surfaces.md](../surfaces.md) — token NLL surface status.
- [../state-of-play.md](../state-of-play.md) — model-internal evidence row.
- [../verification.md](../verification.md) — executed checks for this slice.
- ADR [0004](../decisions/0004-white-box-adapter-output.md); `search/frontier_receipts.py`;
  `scripts/check-contract.mjs`, `scripts/check-fixtures.mjs`, `scripts/check-run-file.mjs`.
