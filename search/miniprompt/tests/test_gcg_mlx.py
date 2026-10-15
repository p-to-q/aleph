"""MLX smoke tests for the MiniPrompt execution path (opt-in, GPU).

Run with the pinned environment:

    search/.venv/bin/python -m unittest discover -s search/miniprompt/tests -t .

These tests are skipped when MLX is not importable, so the default test path
stays MLX-free. They load the pinned 1.7B snapshot, which must be present in
the local Hugging Face cache; ``load_pinned_model`` re-checks the weights
digest and fails closed on any pin mismatch.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

try:
    import mlx.core  # noqa: F401
    import mlx_lm  # noqa: F401

    HAS_MLX = True
except Exception:  # pragma: no cover - exercised on MLX-free machines
    HAS_MLX = False

if HAS_MLX:
    from search.miniprompt import fixtures, gcg, sampling  # noqa: E402
    from search.miniprompt.config import config_from_canonical  # noqa: E402


@unittest.skipUnless(HAS_MLX, "MLX is not available")
class GcgMlxTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = fixtures.preset("canary-hello")
        cls.model, cls.tokenizer, cls.meta = gcg.load_pinned_model(cls.config)

    def test_pinned_model_identity(self):
        self.assertEqual(self.meta["repo"], self.config.repo)
        self.assertEqual(self.meta["revision"], self.config.revision)
        self.assertEqual(self.meta["weightsDigest"], self.config.weights_digest)
        self.assertGreater(self.meta["vocabSize"], 0)

    def test_pin_mismatch_fails_closed(self):
        broken = config_from_canonical(
            {**self.config.to_canonical(),
             "model": {**self.config.to_canonical()["model"], "weightsDigest": "sha256:" + "0" * 64}}
        )
        with self.assertRaises(gcg.ModelPinError):
            gcg.load_pinned_model(broken)

    def test_greedy_check_reproduces_feasibility_acquisitions(self):
        cases = [
            ("42", [19, 17], [113822, 115719, 118027, 104922, 97102]),
            ("hello world", [14990, 1879], [95513, 112369, 5846, 31774, 106998]),
        ]
        for text, target_ids, free_ids in cases:
            actual_ids, _ = gcg.target_token_ids(self.tokenizer, text)
            self.assertEqual(actual_ids, target_ids)
            check = gcg.greedy_continuation_check(self.model, self.tokenizer, free_ids, target_ids)
            self.assertTrue(check["matched"], text)
            self.assertEqual(check["emittedIds"], target_ids)
            self.assertTrue(check["roundtripEqual"], text)

    def test_attempt_pause_and_resume(self):
        target_ids, _ = gcg.target_token_ids(self.tokenizer, "42")
        initial = sampling.initial_free_ids(self.config.seed, 2, self.meta["vocabSize"])
        calls = {"count": 0}

        def pause_after_one_step():
            calls["count"] += 1
            return calls["count"] > 1

        paused = gcg.run_attempt(
            self.model, self.config, n_free=2, steps_budget=2, target_ids=target_ids,
            initial_free_ids=initial, should_pause=pause_after_one_step,
        )
        self.assertTrue(paused["paused"])
        resume = paused["resume"]
        self.assertEqual(resume["step"], 1)
        self.assertEqual(len(resume["trajectory"]), 1)
        done = gcg.run_attempt(
            self.model, self.config, n_free=2, steps_budget=2, target_ids=target_ids,
            initial_free_ids=initial, resume=resume,
        )
        self.assertFalse(done["paused"])
        self.assertEqual(done["stepsRun"], 2)
        self.assertEqual(len(done["trajectory"]), 2)
        self.assertTrue(all(entry["seconds"] >= 0 for entry in done["trajectory"]))

    def test_attempt_pauses_before_first_step(self):
        target_ids, _ = gcg.target_token_ids(self.tokenizer, "42")
        initial = sampling.initial_free_ids(self.config.seed, 2, self.meta["vocabSize"])
        paused = gcg.run_attempt(
            self.model, self.config, n_free=2, steps_budget=1, target_ids=target_ids,
            initial_free_ids=initial, should_pause=lambda: True,
        )
        self.assertTrue(paused["paused"])
        self.assertEqual(paused["resume"]["step"], 0)
        self.assertEqual(paused["resume"]["trajectory"], [])


if __name__ == "__main__":
    unittest.main()
