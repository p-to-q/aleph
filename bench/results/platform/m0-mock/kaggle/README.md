# Kaggle Community Benchmark Scaffold

This directory is a launch scaffold, not checked-in hosted evidence. Kaggle Community Benchmarks run through a notebook/task interface with model access supplied by Kaggle's benchmark program. The M0 task should call each model on the non-leaking frozen-ladder prompts, then score outputs with the vendored AURC/ECL/Elicit/leakage code shipped here so a Kaggle notebook does **not** need to clone the Aleph repository.

## Files

- `aleph_bench_m0_task.py` — scaffold/template. `import`-safe (no third-party deps) and prints a friendly notebook-only message when executed as `__main__` rather than crashing. The `@kbench.task` wiring is documented inline; uncomment it in the approved Kaggle notebook.
- `_scoring.py` — vendored copy of the pure metric functions from `bench/engine/metrics.py` and `bench/engine/leakage_gate.py` (standard library only). This is the *source of truth* for scoring inside Kaggle; do not edit it by hand — regenerate the package from the Aleph repo.
- `score_outputs.py` — given a submission row sequence (CSV path or list of dicts) plus the items/prompts JSONL files, produces a `BenchResult`-compatible JSON. Use this in the Kaggle notebook after `.evaluate(...)` returns.
- `api_test_smoke.py` — local end-to-end smoke test. Verifies I/O shape (one `prompt(...)` call per non-leaking row, correct submission CSV), then runs the vendored scorer against the stub outputs and asserts `aurc ∈ [0, 1]`, a monotone non-leaking frontier, and that rung-0 prompts are gated.

## Boundary

- it keeps explicit reconstruction anchors out of submissions;
- it treats model outputs as `black_box` behavioral evidence;
- it does not request or report logits, token NLL, or bits;
- it points maintainers back to the repository verifier before publishing rows.

## How it slots into a Kaggle notebook

```python
import kaggle_benchmarks as kbench
from aleph_bench_m0_task import aleph_bench_m0_prompt, prompt_dataframe
from score_outputs import score_submission

results = aleph_bench_m0_prompt.evaluate(llm=[kbench.llm], evaluation_data=prompt_dataframe())
submission = [row for row in results]  # adapt to the SDK's return shape
bench_result = score_submission(
    items_path="../data/public_s2_items.jsonl",
    prompts_path="../data/public_s2_prompts.jsonl",
    submission_rows=submission,
    model_id="kaggle/<model>",
)
```

## Local smoke

Run `python3 kaggle/api_test_smoke.py` from this directory. The smoke test uses a stub LLM to verify the I/O contract and the vendored scorer. Passing the smoke test is not hosted model evidence; it only proves the package is ready to be wired into Kaggle's approved notebook.

Before a public Kaggle benchmark launch, finalize the Resource Grant application (`docs/benchmark/launch-kit/kaggle-grant-application.md`), replace the placeholder model loop with the exact Kaggle `kaggle-benchmarks` SDK calls used by the approved notebook, save the notebook version, and attach the resulting hosted `BenchResult` plus manifest/report as separate evidence artifacts.
