"""Aleph-Bench M0 Kaggle Community Benchmark scaffold.

This file is packaged for reviewer inspection. It is not executed by the local
test suite because Kaggle model access is granted inside Kaggle notebooks.
"""

from __future__ import annotations

import json
from pathlib import Path


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
PROMPTS_PATH = PACKAGE_ROOT / "data/public_s2_prompts.jsonl"


# Kaggle notebook wiring sketch (uncomment only inside the approved benchmark
# notebook, where kaggle-benchmarks is installed and model access is available):
#
# import kaggle_benchmarks as kbench
#
# @kbench.task(name="aleph_bench_m0_prompt", store_task=False)
# def aleph_bench_m0_prompt(llm, item_id: str, prompt_id: str, prompt: str) -> dict[str, str]:
#     with kbench.chats.new(f"{item_id}:{prompt_id}"):
#         output = llm.prompt(prompt)
#     return {"item_id": item_id, "prompt_id": prompt_id, "output_text": str(output)}
#
# results = aleph_bench_m0_prompt.evaluate(llm=[kbench.llm], evaluation_data=prompt_dataframe)


def load_sendable_prompts() -> list[dict[str, object]]:
    rows = []
    for line in PROMPTS_PATH.read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        if not row["disqualified"]:
            rows.append(row)
    return rows


def run_black_box_model(model_id: str, llm: object) -> list[dict[str, str]]:
    """Run one Kaggle-provided model over all non-leaking M0 prompts.

    `llm` is expected to be the model object provided by the Kaggle Community
    Benchmarks notebook environment. It should expose a generation method such
    as `prompt(...)`; exact SDK wiring belongs in the submitted Kaggle notebook.
    """

    outputs = []
    for row in load_sendable_prompts():
        output = llm.prompt(str(row["prompt"]))
        outputs.append(
            {
                "row_id": f"{row['item_id']}:{row['prompt_id']}",
                "model_id": model_id,
                "item_id": str(row["item_id"]),
                "prompt_id": str(row["prompt_id"]),
                "output_text": str(output),
            }
        )
    return outputs


def main() -> None:
    raise SystemExit(
        "This scaffold must run inside a Kaggle Community Benchmarks notebook "
        "with approved model access. Locally, use ./aleph-bench package --check."
    )


if __name__ == "__main__":
    main()
