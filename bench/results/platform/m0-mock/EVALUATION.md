# Aleph-Bench M0 Platform Evaluation Protocol

This package is ready to publish as a Hugging Face Dataset or Kaggle Dataset. It is also ready for a community benchmark dry run because it includes the seed data, prompt rows, schemas, mock evidence, and verification commands.

## Evidence Boundary

- The included model rows are deterministic mock evidence.
- They prove the benchmark pipeline, not model quality.
- Hosted black-box rows must use the same S2 items, frozen ladder, leakage thresholds, tau, k, and AURC/ECL/Elicit definitions.
- Do not report logits, token NLL, bits, or white-box claims for hosted black-box rows.

## Submission Shape

Use `data/submission_format.csv` as the public output shape:

```text
row_id,model_id,item_id,prompt_id,output_text
```

`prompt_id` must refer to a non-leaking prompt from `data/public_s2_prompts.jsonl`. Gated explicit reconstruction prompts are present for auditability but should not be submitted as compression candidates.

## Local Verification

From the Aleph repository root:

```bash
./aleph-bench verify --audit bench/results/m0-audit.json --bundle bench/results/m0-bundle.json
./aleph-bench package --check bench/results/platform/m0-mock/package-manifest.json
python3 bench/results/platform/m0-mock/kaggle/api_test_smoke.py
npm run lint
npm run test
```

## Hosted Evidence Upgrade

Before replacing the mock evidence note with real black-box rows:

```bash
./aleph-bench doctor --model hosted:model-a,hosted:model-b,hosted:model-c
./aleph-bench manifest --model hosted:model-a,hosted:model-b,hosted:model-c --out bench/results/m0-hosted-manifest.json
./aleph-bench run --track F --model hosted:model-a,hosted:model-b,hosted:model-c --split public --seed 0 --cache-dir .cache/aleph-bench/m0-hosted --out bench/results/m0-hosted-run.json
./aleph-bench verify --result bench/results/m0-hosted-run.json --manifest bench/results/m0-hosted-manifest.json
./aleph-bench report --result bench/results/m0-hosted-run.json --out bench/results/m0-hosted-report.md
```
