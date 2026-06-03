# Kaggle Community Benchmark Scaffold

This directory is a launch scaffold, not checked-in hosted evidence. Kaggle Community Benchmarks run through a notebook/task interface with model access supplied by Kaggle's benchmark program. The M0 task should call each model on the non-leaking frozen-ladder prompts, then score outputs with the same local AURC/ECL/Elicit/leakage code used by `./aleph-bench`.

The included `aleph_bench_m0_task.py` is intentionally minimal and defensive. Kaggle Community Benchmarks use executable Python tasks built around the `kaggle-benchmarks` SDK's `@kbench.task(...)` decorator and `llm.prompt(...)`; this scaffold keeps that shape visible while leaving exact model-access wiring to the approved Kaggle notebook.

- it keeps explicit reconstruction anchors out of submissions;
- it treats model outputs as `black_box` behavioral evidence;
- it does not request or report logits, token NLL, or bits;
- it points maintainers back to the repository verifier before publishing rows.

For the API-test preparation step, run `python3 kaggle/api_test_smoke.py` from this package or from the repository path where it is checked in. The smoke test uses a stub LLM to verify that the task wrapper calls `prompt(...)` once per non-leaking row and emits the exact public submission shape. Passing the smoke test is not hosted model evidence; it only proves the package is ready to be wired into Kaggle's approved notebook.

Before a public Kaggle benchmark launch, replace the placeholder model loop with the exact Kaggle `kaggle-benchmarks` SDK calls used by the approved Resource Grant notebook, save the notebook version, and attach the resulting hosted `BenchResult` plus manifest/report as separate evidence artifacts.
