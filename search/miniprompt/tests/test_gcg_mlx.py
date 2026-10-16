"""MLX smoke tests for the MiniPrompt execution path (opt-in, GPU).

Run with the pinned environment:

    search/.venv/bin/python -m unittest discover -s search/miniprompt/tests -t .

These tests are skipped when MLX is not importable, so the default test path
stays MLX-free. They load the pinned 1.7B snapshot, which must be present in
the local Hugging Face cache; ``load_pinned_model`` re-checks the weights
digest and fails closed on any pin mismatch. The acquisition- and
scaffold-criterion regression tests below use faked model objects only (no
snapshot needed).
"""

from __future__ import annotations

import json
import sys
import tempfile
import types
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
    import mlx.core as mx  # noqa: E402

    from search.miniprompt import fixtures, gcg, runner, sampling  # noqa: E402
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

    def test_scaffold_token_derivation(self):
        self.assertEqual(
            gcg.scaffold_token_ids(self.tokenizer, self.config.scaffold),
            {"prefixIds": [], "midIds": []},
        )
        declared = config_from_canonical({
            **self.config.to_canonical(),
            "scaffold": {
                "chatTemplate": ["<|im_start|>user\n", "<|im_end|>\n"],
                "systemPrompt": "You are helpful.",
                "inputStr": "Say:",
            },
        }).scaffold
        derived = gcg.scaffold_token_ids(self.tokenizer, declared)
        expected_prefix = (
            list(self.tokenizer.encode("<|im_start|>user\n", add_special_tokens=False))
            + list(self.tokenizer.encode("You are helpful.", add_special_tokens=False))
            + list(self.tokenizer.encode("Say:", add_special_tokens=False))
        )
        self.assertEqual(derived["prefixIds"], expected_prefix)
        self.assertEqual(
            derived["midIds"],
            list(self.tokenizer.encode("<|im_end|>\n", add_special_tokens=False)),
        )
        # pinned derivation under the pinned 1.7B tokenizer (probed 2026-10-16 UTC)
        self.assertEqual(derived["prefixIds"], [151644, 872, 198, 2610, 525, 10950, 13, 45764, 25])
        self.assertEqual(derived["midIds"], [151645, 198])

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

    def test_topk_guard_in_run_attempt(self):
        huge = config_from_canonical({**self.config.to_canonical(), "topk": 200000})
        with self.assertRaises(ValueError):
            gcg.run_attempt(
                self.model, huge, n_free=2, steps_budget=1,
                target_ids=[19, 17], initial_free_ids=[1, 2],
            )

    def test_resume_from_terminal_acquisition_checkpoint(self):
        target_ids, _ = gcg.target_token_ids(self.tokenizer, "42")
        free_ids = [113822, 115719, 118027, 104922, 97102]
        resume = {
            "step": 3, "freeIds": list(free_ids), "bestLoss": 0.5, "bestIds": list(free_ids),
            "solutionSource": "acquired", "solutionLoss": 0.25,
            "trajectory": [
                {"step": 0, "loss": 3.0, "matchTokens": 0, "seconds": 0.5},
                {"step": 1, "loss": 1.0, "matchTokens": 1, "seconds": 0.5},
                {"step": 2, "loss": 0.25, "matchTokens": 2, "seconds": 0.5},
            ],
            "lastMatchTokens": 2, "lastLoss": 0.25, "acquiredAtStep": 2,
        }
        outcome = gcg.run_attempt(
            self.model, self.config, n_free=5, steps_budget=200,
            target_ids=target_ids, initial_free_ids=free_ids, resume=resume,
        )
        self.assertFalse(outcome["paused"])
        self.assertTrue(outcome["acquired"])
        self.assertEqual(outcome["acquiredAtStep"], 2)
        self.assertEqual(outcome["stepsRun"], 3)          # no new steps were run
        self.assertEqual(outcome["trajectory"], resume["trajectory"])
        self.assertEqual(outcome["solutionFreeIds"], free_ids)

    def test_run_scan_receipt_reuse_guard(self):
        tiny = config_from_canonical({
            **self.config.to_canonical(), "label": "smoke-reuse",
            "stepsInitial": 1, "stepsHardCap": 4, "maxAttempts": 1,
            "batch": 8, "miniBatch": 8, "topk": 16,
        })
        quiet = lambda *args, **kwargs: None  # noqa: E731
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(runner.run_scan(tiny, tmp, max_seconds=None, log=quiet), 0)
            # the same declaration reports complete without reloading or re-running
            self.assertEqual(runner.run_scan(tiny, tmp, max_seconds=None, log=quiet), 0)
            # a different declaration in the same run directory is refused
            other = config_from_canonical({**tiny.to_canonical(), "target": "42"})
            with self.assertRaises(runner.RunStateError):
                runner.run_scan(other, tmp, max_seconds=None, log=quiet)
            # a tampered receipt is refused
            receipt_path = Path(tmp) / "receipt.json"
            bad = json.loads(receipt_path.read_text(encoding="utf-8"))
            bad["result"]["attempts"] = 99
            receipt_path.write_text(json.dumps(bad), encoding="utf-8")
            with self.assertRaises(runner.RunStateError):
                runner.run_scan(tiny, tmp, max_seconds=None, log=quiet)


def _criterion_probe_model(*, single_sequence_miss: bool, greedy_miss: bool = False):
    """A fake model whose evaluation-shape variants disagree.

    - The batched candidate forward (the shape the pre-fix in-loop all-match
      came from) reports an all-match.
    - The full-length single-sequence forward (``n_free + len(target)``, the
      teacher-forced solution check and receipt re-check shape) reports an
      all-match unless ``single_sequence_miss`` is set, in which case the
      second target position misses (the batch-axis case observed on
      canary-42, 2026-10-16 UTC).
    - The prefix-length forwards of the greedy continuation reproduce the
      targets unless ``greedy_miss`` is set, in which case the first greedy
      step emits a wrong token (the sequence-length-axis case observed on
      canary-hamlet-line, 2026-10-16 UTC).
    """

    def _rows(length, first_token, second_token):
        rows = mx.zeros((length, 16))
        if length >= 2:
            rows = rows.at[1, first_token].add(10.0)
        if length >= 3:
            rows = rows.at[2, second_token].add(10.0)
        return rows

    batched_bias = _rows(4, 3, 4)
    full_bias = _rows(4, 3, 15 if single_sequence_miss else 4)
    short2_bias = _rows(2, 7 if greedy_miss else 3, 0)
    short3_bias = _rows(3, 3, 4)

    class _Embedding:
        def __init__(self, table):
            self._table = table

        def __call__(self, ids):
            return self._table[ids]

        def as_linear(self, x):
            return x @ self._table.T

    class _Model:
        def __init__(self):
            self._weight = mx.zeros((8, 16))
            self.args = types.SimpleNamespace(vocab_size=16)
            self.model = types.SimpleNamespace(embed_tokens=_Embedding(mx.zeros((16, 8))))

        def __call__(self, ids, cache=None, input_embeddings=None):
            embeddings = (
                input_embeddings if input_embeddings is not None else self.model.embed_tokens(ids)
            )
            if int(embeddings.shape[0]) > 1:
                bias = batched_bias
            elif embeddings.shape[-2] == 2:
                bias = short2_bias
            elif embeddings.shape[-2] == 3:
                bias = short3_bias
            else:
                bias = full_bias
            return embeddings @ self._weight + bias

    return _Model()


@unittest.skipUnless(HAS_MLX, "MLX is not available")
class AcquisitionCriterionTests(unittest.TestCase):
    """Acquisition requires both declared evidences, evaluated in-loop.

    Regression for the first tranche-2 fail-closed stops (2026-10-16 UTC):
    a batched-only all-match must not claim an acquisition (canary-42), a
    teacher-forced all-match without a reproducing greedy continuation must
    not either (canary-hamlet-line), and a genuine all-match plus greedy
    reproduction still acquires. Uses faked, evaluation-shape-dependent model
    objects — no pinned snapshot or cache is needed.
    """

    def _config(self):
        base = fixtures.preset("canary-42").to_canonical()
        base.update({"label": "fake-criterion", "topk": 4, "batch": 3, "miniBatch": 3})
        return config_from_canonical(base)

    def test_batched_only_match_never_claims_acquisition(self):
        # The batched forward reports an all-match the single-sequence
        # teacher-forced check denies: nothing may be claimed.
        config = self._config()
        model = _criterion_probe_model(single_sequence_miss=True)
        outcome = gcg.run_attempt(
            model, config, n_free=2, steps_budget=3, target_ids=[3, 4],
            initial_free_ids=[1, 2],
        )
        self.assertFalse(outcome["acquired"])
        self.assertIsNone(outcome["acquiredAtStep"])
        self.assertEqual(outcome["solutionSource"], "best_by_loss")
        self.assertEqual(outcome["stepsRun"], 3)
        self.assertEqual(outcome["trajectory"][-1]["matchTokens"], 1)

    def test_single_sequence_match_still_acquires(self):
        config = self._config()
        model = _criterion_probe_model(single_sequence_miss=False)
        outcome = gcg.run_attempt(
            model, config, n_free=2, steps_budget=3, target_ids=[3, 4],
            initial_free_ids=[1, 2],
        )
        self.assertTrue(outcome["acquired"])
        self.assertEqual(outcome["acquiredAtStep"], 0)
        self.assertEqual(outcome["stepsRun"], 1)
        self.assertEqual(outcome["trajectory"][-1]["matchTokens"], 2)

    def test_teacher_forced_match_without_greedy_reproduction_does_not_acquire(self):
        # The single-sequence teacher-forced check reports a full match, but
        # the true greedy continuation misses the first token: the scan must
        # fall through and keep going, not claim an acquisition.
        config = self._config()
        model = _criterion_probe_model(single_sequence_miss=False, greedy_miss=True)
        outcome = gcg.run_attempt(
            model, config, n_free=2, steps_budget=3, target_ids=[3, 4],
            initial_free_ids=[1, 2],
        )
        self.assertFalse(outcome["acquired"])
        self.assertIsNone(outcome["acquiredAtStep"])
        self.assertEqual(outcome["solutionSource"], "best_by_loss")
        self.assertEqual(outcome["stepsRun"], 3)
        self.assertEqual(outcome["trajectory"][-1]["matchTokens"], 2)


def _scaffold_probe_model(prefix, free, mid, target, *, greedy_requires_mid=False):
    """A fake model keyed to the declared scaffold layout.

    - a single-sequence forward of the full layout length reports the target
      tokens as argmax at the scaffold-shifted loss positions (independent of
      the free-token content);
    - the prefix-length forwards of the greedy continuation reproduce the
      targets (with ``greedy_requires_mid``, the first emission only
      reproduces when the mid scaffold token is present at its position);
    - batched candidate forwards return flat logits and are recorded.
    """

    full = len(prefix) + len(free) + len(mid) + len(target)
    loss_start = len(prefix) + len(free) - 1
    mid_pos = len(prefix) + len(free)
    greedy_len = len(prefix) + len(free) + len(mid)

    class _Embedding:
        def __init__(self, table):
            self._table = table

        def __call__(self, ids):
            return self._table[ids]

        def as_linear(self, x):
            return x @ self._table.T

    class _Model:
        def __init__(self):
            self._weight = mx.zeros((8, 16))
            self.args = types.SimpleNamespace(vocab_size=16)
            self.model = types.SimpleNamespace(embed_tokens=_Embedding(mx.zeros((16, 8))))
            self.batched = []

        def __call__(self, ids, cache=None, input_embeddings=None):
            embeddings = (
                input_embeddings if input_embeddings is not None else self.model.embed_tokens(ids)
            )
            length = int(embeddings.shape[-2])
            rows = mx.zeros((length, 16))
            if int(embeddings.shape[0]) > 1:
                self.batched.append(mx.array(ids).tolist())
            elif length == full:
                for offset, token in enumerate(target):
                    rows = rows.at[loss_start + offset, token].add(10.0)
            elif length == greedy_len:
                token = target[0]
                if greedy_requires_mid and int(ids[0, mid_pos].item()) != mid[0]:
                    token = 15
                rows = rows.at[length - 1, token].add(10.0)
            elif length == greedy_len + 1:
                rows = rows.at[length - 1, target[1]].add(10.0)
            return embeddings @ self._weight + rows

    return _Model()


@unittest.skipUnless(HAS_MLX, "MLX is not available")
class ScaffoldCriterionTests(unittest.TestCase):
    """The declared scaffold layout drives the criterion shapes (faked models).

    Pins, for a declared scaffold: the teacher-forced loss positions shift by
    the prefix; candidate mutations stay inside the free window; the greedy
    continuation runs from ``prefix + free + mid``; and ``wholePromptTokens``
    counts the scaffold. Uses faked model objects — no snapshot needed.
    """

    PREFIX = [11]
    FREE = [1, 2]
    MID = [12]
    TARGET = [3, 4]

    def _config(self):
        base = fixtures.preset("canary-42").to_canonical()
        base.update({"label": "fake-scaffold", "topk": 4, "batch": 3, "miniBatch": 3})
        return config_from_canonical(base)

    def _run(self, *, greedy_requires_mid=False):
        model = _scaffold_probe_model(
            self.PREFIX, self.FREE, self.MID, self.TARGET,
            greedy_requires_mid=greedy_requires_mid,
        )
        outcome = gcg.run_attempt(
            model, self._config(), n_free=len(self.FREE), steps_budget=3,
            target_ids=self.TARGET, initial_free_ids=self.FREE,
            prefix_ids=self.PREFIX, mid_ids=self.MID,
        )
        return model, outcome

    def test_scaffolded_acquisition_and_whole_prompt_accounting(self):
        _, outcome = self._run()
        self.assertTrue(outcome["acquired"])
        self.assertEqual(outcome["acquiredAtStep"], 0)
        self.assertEqual(
            outcome["wholePromptTokens"],
            len(self.PREFIX) + len(self.FREE) + len(self.MID) + len(self.TARGET),
        )
        self.assertEqual(outcome["trajectory"][-1]["matchTokens"], len(self.TARGET))

    def test_scaffolded_free_window_is_the_only_mutated_region(self):
        prefix_len = len(self.PREFIX)
        free_len = len(self.FREE)
        mid_len = len(self.MID)
        model, outcome = self._run()
        rows = [row for chunk in model.batched for row in chunk]
        self.assertTrue(rows, "no batched candidate forward was recorded")
        for row in rows:
            self.assertEqual(row[:prefix_len], self.PREFIX)
            self.assertEqual(row[prefix_len + free_len : prefix_len + free_len + mid_len], self.MID)
            self.assertEqual(row[prefix_len + free_len + mid_len :], self.TARGET)
        self.assertTrue(outcome["acquired"])

    def test_greedy_continuation_runs_from_the_scaffold_context(self):
        _, outcome = self._run(greedy_requires_mid=True)
        self.assertTrue(outcome["acquired"])


if __name__ == "__main__":
    unittest.main()
