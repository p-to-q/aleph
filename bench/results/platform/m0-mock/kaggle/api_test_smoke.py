"""Local smoke test for the Aleph-Bench M0 Kaggle API-test wrapper.

This script deliberately uses a stub LLM. It proves the package-level task I/O
contract before Kaggle-hosted model access exists; it does not produce model
evidence or leaderboard rows.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
import sys


KAGGLE_DIR = Path(__file__).resolve().parent
PACKAGE_ROOT = KAGGLE_DIR.parent
SUBMISSION_PATH = PACKAGE_ROOT / "data/submission_format.csv"
sys.path.insert(0, str(KAGGLE_DIR))

import aleph_bench_m0_task  # noqa: E402


class StubLLM:
    def __init__(self) -> None:
        self.prompts: list[str] = []

    def prompt(self, prompt: str) -> str:
        self.prompts.append(prompt)
        return f"stub-output-{len(self.prompts):03d}"


def load_submission_rows() -> list[dict[str, str]]:
    with SUBMISSION_PATH.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def row_key(row: dict[str, object]) -> tuple[str, str, str]:
    return (str(row["row_id"]), str(row["item_id"]), str(row["prompt_id"]))


def main() -> None:
    expected_rows = load_submission_rows()
    prompts = aleph_bench_m0_task.load_sendable_prompts()
    llm = StubLLM()
    observed_rows = aleph_bench_m0_task.run_black_box_model("stub/model", llm)

    errors: list[str] = []
    if len(prompts) != 180:
        errors.append(f"expected 180 non-leaking prompts, found {len(prompts)}")
    if len(expected_rows) != 180:
        errors.append(f"expected 180 submission rows, found {len(expected_rows)}")
    if len(observed_rows) != len(expected_rows):
        errors.append(f"expected {len(expected_rows)} outputs, found {len(observed_rows)}")
    if len(llm.prompts) != len(expected_rows):
        errors.append(f"expected {len(expected_rows)} prompt() calls, found {len(llm.prompts)}")
    if any(row.get("disqualified") for row in prompts):
        errors.append("load_sendable_prompts returned at least one disqualified prompt")

    expected_keys = [row_key(row) for row in expected_rows]
    observed_keys = [row_key(row) for row in observed_rows]
    if observed_keys != expected_keys:
        errors.append("observed output row order or ids do not match submission_format.csv")

    required_fields = {"row_id", "model_id", "item_id", "prompt_id", "output_text"}
    for index, row in enumerate(observed_rows):
        if set(row) != required_fields:
            errors.append(f"row {index} has fields {sorted(row)}, expected {sorted(required_fields)}")
            break
        if row["model_id"] != "stub/model":
            errors.append(f"row {index} has unexpected model_id {row['model_id']!r}")
            break
        if not row["output_text"]:
            errors.append(f"row {index} has empty output_text")
            break

    report = {
        "status": "failed" if errors else "ok",
        "packageRoot": str(PACKAGE_ROOT),
        "sendablePrompts": len(prompts),
        "submissionRows": len(expected_rows),
        "promptCalls": len(llm.prompts),
        "firstRow": observed_rows[0] if observed_rows else None,
        "errors": errors,
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    if errors:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
