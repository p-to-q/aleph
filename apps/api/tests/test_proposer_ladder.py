from __future__ import annotations

import sys
from pathlib import Path

SEARCH_ROOT = Path(__file__).resolve().parents[3] / "search"
sys.path.insert(0, str(SEARCH_ROOT))

from aleph_search import Proposer  # noqa: E402


class FakeTheta:
    def __init__(self) -> None:
        self.calls: list[tuple[float, str]] = []

    def gen(self, prompt: str, max_tokens: int, temp: float = 0.0) -> str:  # noqa: ARG002
        self.calls.append((temp, prompt))
        if "BUDGET=<word_budget>" in prompt:
            return "\n".join(
                [
                    "BUDGET=8: tiny coordinate",
                    "BUDGET=8: compact title cue",
                    "BUDGET=16: medium coordinate with form",
                    "BUDGET=64: long reconstruction strategy naming the source",
                ]
            )
        if "most 16 words" in prompt:
            return "fallback middle cue"
        return "fallback prompt"


def test_propose_ladder_parses_budgeted_lines_and_fills_missing_slots() -> None:
    proposer = Proposer(FakeTheta())

    ladder = proposer.propose_ladder(
        target="A small place for seeing too much, gently.",
        budgets=[8, 16, 64],
        n_each=2,
    )

    assert ladder[8] == ["tiny coordinate", "compact title cue"]
    assert ladder[16] == ["medium coordinate with form", "fallback middle cue"]
    assert ladder[64] == ["long reconstruction strategy naming the source", "fallback prompt"]
