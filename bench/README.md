# Aleph-Bench — M0 implementation (`bench/`)

Implementation and operations readme for the `bench/` engine. For the full design, research, and
launch dossier (12 numbered docs + launch kit), see [`docs/benchmark/`](../docs/benchmark/README.md);
for the M0 result read [`docs/benchmark/m0-evidence.md`](../docs/benchmark/m0-evidence.md).


Aleph-Bench turns the Aleph compression workbench into a controlled comparison instrument. Instead of asking for one model's shortest known prompt path, it holds the target set and procedure fixed and compares how much non-leaking prompt coordinate length different models need.

## M0 Shape

The first implementation is Track F, Frozen Ladder:

```text
BenchItem
  -> 4 rung ladder with 2 paraphrases per rung
  -> model adapter generations
  -> leakage gate
  -> monotone non-leaking frontier
  -> AURC, ECL@tau, Elicit@k, bootstrap CIs
  -> BenchResult
```

M0 uses S2 compositional targets: synthetic, rule-generated outputs that should not be memorized as public text, but can be reconstructed from a sufficiently precise rule prompt.

Each item/model run keeps the canonical `AlephRun` plus a benchmark-only `measurements` receipt. The receipt records every ladder prompt's rung, paraphrase, token count, effective rerun count, fidelity mean, fidelity variance, fidelity standard deviation, and leakage-gate decision. This keeps stochastic-run variance visible without adding benchmark-only fields to product `CandidatePoint` objects.

## Evidence Modes

The checked-in M0 result is deterministic mock evidence. It validates the benchmark pipeline, not the relative quality of real models.

Hosted black-box runs are supported by the adapter path, but require server-side OpenAI-compatible credentials. Black-box rows report generated text behavior only; they do not report logits, token NLL, or model-internal evidence.

The hosted path is covered by offline local `/chat/completions` tests: request path, bearer auth, model id, prompt message, temperature, `max_tokens`, response parsing, HTTP error reporting, bounded retry on 429/5xx failures, and a one-item end-to-end `black_box` `BenchResult`.

Hosted runs can use `--cache-dir` to save per-call responses and resume after interruption. Use an ignored path such as `.cache/aleph-bench/m0-hosted` so provider outputs do not become accidental repository artifacts.

Hosted retries default to two retries with a one-second delay. Override with `ALEPH_CUSTOM_API_MAX_RETRIES` and `ALEPH_CUSTOM_API_RETRY_DELAY_SECONDS` when a provider needs a different policy.

## Metrics

- **AURC** is the area under the monotone rate-distortion staircase. Lower is better.
- **ECL@tau** is the shortest non-leaking coordinate length that reaches the fidelity threshold.
- **Elicit@k** is the share of items where one of the `k` shortest non-leaking prompts reaches the fidelity threshold.
- **Leakage** is a gate, not a penalty. Disqualified prompts are excluded from compression metrics.

The default M0 threshold is `tau = 0.9`, with exact-match fidelity using normalized edit distance for near misses.

The default leakage thresholds are `lcsRatio = 0.65`, `trigramOverlap = 0.5`, and `verbatimSpanTokens = 16`. The LCS gate is intentionally high in M0 because S2 rule prompts must be allowed to name parameters without quoting full target spans.

## Commands

Check dataset validity, leakage-gate distribution, hosted environment variables, and call budget before a run:

```bash
./aleph-bench doctor --model hosted:model-a,hosted:model-b,hosted:model-c
```

Write a no-call manifest of the non-leaking prompts that would be sent:

```bash
./aleph-bench manifest --model hosted:model-a,hosted:model-b,hosted:model-c --out bench/results/m0-hosted-manifest.json
```

Manifests validate against [schemas/aleph-bench-manifest.schema.json](../schemas/aleph-bench-manifest.schema.json) before the CLI writes them.

Verify dataset, result, and manifest consistency:

```bash
./aleph-bench verify
```

`verify` also validates every embedded item run against the canonical [schemas/aleph-run.schema.json](../schemas/aleph-run.schema.json), so benchmark aggregates cannot silently drift away from the product run contract.

Verify the full checked-in mock M0 bundle, including the audit receipt:

```bash
./aleph-bench verify --audit bench/results/m0-audit.json --bundle bench/results/m0-bundle.json
```

Run the M0 acceptance-gate audit:

```bash
./aleph-bench audit
```

Write the same audit as a durable JSON receipt:

```bash
./aleph-bench audit --out bench/results/m0-audit.json
```

Audit receipts validate against [schemas/aleph-bench-audit.schema.json](../schemas/aleph-bench-audit.schema.json).

`audit` repeats that canonical `AlephRun` contract check alongside the M0 acceptance gates. It is intentionally limited to deterministic mock results because it reruns seed 0 and seed 1; use `verify` and `report` for hosted results unless a future audit mode explicitly allows adapter calls.

The audit also checks M0 seed integrity: 30 S2 items, one shared field-level canary kept out of target and prompt text, a 10/10/10 arithmetic/lattice/route family split, and exactly two prompts for each of the four ladder rungs.

Build or check the mock M0 evidence bundle digest manifest:

```bash
./aleph-bench bundle --out bench/results/m0-bundle.json
./aleph-bench bundle --check bench/results/m0-bundle.json
```

Bundle manifests validate against [schemas/aleph-bench-bundle.schema.json](../schemas/aleph-bench-bundle.schema.json). The bundle records file digests for the checked-in mock result, prompt manifest, audit receipt, generated report, and evidence note; it does not add model evidence.

Render a markdown report from a result JSON:

```bash
./aleph-bench report --result bench/results/m0-first-run.json --out bench/results/m0-report.md
```

Run the deterministic mock receipt:

```bash
./aleph-bench run --track F --model mock-frontier,mock-mid,mock-small --split public --seed 0 --out bench/results/m0-first-run.json
```

Run hosted black-box rows after setting `ALEPH_CUSTOM_API_BASE_URL` and `ALEPH_CUSTOM_API_KEY`:

```bash
./aleph-bench run --track F --model hosted:model-a,hosted:model-b,hosted:model-c --split public --seed 0 --cache-dir .cache/aleph-bench/m0-hosted --out bench/results/m0-hosted-run.json
```

Build the platform release package for Hugging Face Dataset, Kaggle Dataset, Kaggle Community Benchmark review, and Croissant metadata:

```bash
./aleph-bench package --out-dir bench/results/platform/m0-mock
./aleph-bench package --check bench/results/platform/m0-mock/package-manifest.json
python3 bench/results/platform/m0-mock/kaggle/api_test_smoke.py
```

The checked package includes JSONL and CSV tables, a Hugging Face dataset card, Kaggle `dataset-metadata.json` with resource schemas, Croissant JSON-LD, mock evidence receipts, JSON schemas, checksums, a Kaggle Community Benchmark scaffold in `kaggle/`, and a stubbed API-test smoke harness that verifies the 180-row non-leaking prompt/output contract before hosted Kaggle model access exists.
