from __future__ import annotations

import copy
import itertools
import math
import sys
import unittest
from pathlib import Path


SEARCH_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SEARCH_ROOT))

from aleph_search import monotone, observed_length_distortion_frontier  # noqa: E402


def point(point_id: str, length: int, epsilon: float, *, role: str | None = None) -> dict[str, object]:
    item: dict[str, object] = {
        "id": point_id,
        "prompt": f"prompt-{point_id}",
        "output": f"output-{point_id}",
        "length": length,
        "epsilon": epsilon,
        "similarity": 1 - epsilon,
        "stability": 0.8,
    }
    if role is not None:
        item["role"] = role
    return item


class ObservedFrontierTests(unittest.TestCase):
    def test_dominated_budget_does_not_clone_winner_at_new_length(self) -> None:
        short = point("short", 4, 0.1)
        longer = point("longer", 8, 0.4)
        source = [short, longer]
        before = copy.deepcopy(source)

        result = observed_length_distortion_frontier(source)

        self.assertEqual(result, [short])
        self.assertEqual(source, before)
        self.assertTrue(all(candidate in source for candidate in result))
        self.assertNotIn(8, [candidate["length"] for candidate in result])

    def test_explicit_reconstruction_is_retained_as_a_baseline(self) -> None:
        short = point("short", 4, 0.1)
        explicit = point("explicit", 12, 0.2, role="explicit_reconstruction")

        self.assertEqual(
            observed_length_distortion_frontier([explicit, short]),
            [short, explicit],
        )

    def test_result_is_permutation_invariant_with_deterministic_ties(self) -> None:
        archive = [
            point("z-tie", 4, 0.4),
            point("a-tie", 4, 0.4),
            point("middle", 8, 0.3),
            point("dominated", 12, 0.35),
            point("explicit", 20, 0.0, role="explicit_reconstruction"),
        ]

        expected = ["a-tie", "middle", "explicit"]
        for ordering in itertools.permutations(archive):
            result = observed_length_distortion_frontier(ordering)
            self.assertEqual([candidate["id"] for candidate in result], expected)

    def test_dominated_injection_and_second_projection_do_not_change_the_view(self) -> None:
        archive = [point("short", 4, 0.4), point("middle", 8, 0.2)]
        first = observed_length_distortion_frontier(archive)
        with_dominated = observed_length_distortion_frontier(
            archive + [point("dominated", 10, 0.5)]
        )

        self.assertEqual(first, with_dominated)
        self.assertEqual(observed_length_distortion_frontier(first), first)
        self.assertEqual(monotone(archive), first)

    def test_incomplete_or_nonfinite_objectives_fail_closed(self) -> None:
        invalid = [
            {"prompt": "missing length", "epsilon": 0.2},
            {"prompt": "missing epsilon", "length": 2},
            point("negative-length", -1, 0.2),
            point("negative-epsilon", 2, -0.1),
            point("nan", 2, math.nan),
            point("infinity", 2, math.inf),
        ]

        for candidate in invalid:
            with self.subTest(candidate=candidate):
                with self.assertRaises(ValueError):
                    observed_length_distortion_frontier([candidate])


if __name__ == "__main__":
    unittest.main()
