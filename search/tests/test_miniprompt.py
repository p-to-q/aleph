"""MiniPrompt reproduction: strict config, scan policy, receipts, and CLI.

Pure standard-library tests (no MLX, no network): the strict config parser and
digest, the seeded sampling derivations, the upstream scan-policy state machine
pinned to concrete sequences, receipt construction plus the fail-closed
verifier (including tamper probes with re-fixed digests), and the no-MLX
``verify`` command via subprocess.
"""

from __future__ import annotations

import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from search.engine.canonical import digest  # noqa: E402
from search.miniprompt import fixtures, receipts, sampling  # noqa: E402
from search.miniprompt.config import (  # noqa: E402
    CONFIG_SCHEMA,
    ConfigError,
    config_from_canonical,
    load_config_file,
    loads_strict,
)
from search.miniprompt.scan import ScanPolicy, ScanPolicyError, replay_outcomes  # noqa: E402

TARGET_IDS = [14990, 1879]
TARGET_RENDERING = ["hello", " world"]


def variant(**overrides):
    base = fixtures.preset("canary-hello").to_canonical()
    base.update(overrides)
    return config_from_canonical(base)


def attempt_from_spec(spec, acquired, target_ids=TARGET_IDS):
    n_free = spec.n_free
    if acquired:
        trajectory = [
            {"step": 0, "loss": 1.0, "matchTokens": max(len(target_ids) - 1, 0), "seconds": 0.1},
            {"step": 1, "loss": 0.5, "matchTokens": len(target_ids), "seconds": 0.1},
        ]
        greedy = {
            "ran": True,
            "matched": True,
            "roundtripEqual": True,
            "emittedIds": list(target_ids),
            "freeRendering": "free",
            "emittedRendering": "target",
        }
        return {
            "index": spec.index,
            "nFree": n_free,
            "stepsBudget": spec.steps_budget,
            "stepsRun": 2,
            "acquired": True,
            "acquiredAtStep": 1,
            "initialFreeIds": [1000 + i for i in range(n_free)],
            "solutionFreeIds": [2000 + i for i in range(n_free)],
            "solutionLoss": 0.5,
            "solutionSource": "acquired",
            "wholePromptTokens": n_free + len(target_ids),
            "trajectory": trajectory,
            "greedy": greedy,
        }
    trajectory = [
        {"step": 0, "loss": 9.0, "matchTokens": 0, "seconds": 0.1},
        {"step": 1, "loss": 8.0, "matchTokens": 0, "seconds": 0.1},
    ]
    return {
        "index": spec.index,
        "nFree": n_free,
        "stepsBudget": spec.steps_budget,
        "stepsRun": 2,
        "acquired": False,
        "acquiredAtStep": None,
        "initialFreeIds": [1000 + i for i in range(n_free)],
        "solutionFreeIds": [1000 + i for i in range(n_free)],
        "solutionLoss": 8.0,
        "solutionSource": "best_by_loss",
        "wholePromptTokens": n_free + len(target_ids),
        "trajectory": trajectory,
        "greedy": None,
    }


def build_fixture_receipt(config, outcomes, target_ids=TARGET_IDS):
    policy = ScanPolicy(config, len(target_ids))
    attempts = []
    for outcome in outcomes:
        spec = policy.next_spec()
        assert spec is not None, "fixture outcomes exceed the policy bound"
        attempts.append(attempt_from_spec(spec, outcome, target_ids))
        policy.record(outcome)
    assert policy.next_spec() is None, "fixture outcomes leave the scan unfinished"
    result = receipts.result_from_policy(policy.state, attempts)
    return receipts.build_receipt(
        config=config,
        model={
            "repo": config.repo,
            "revision": config.revision,
            "weightsDigest": config.weights_digest,
            "vocabSize": 151936,
        },
        environment={"python": "3.13", "mlx": "0.31.2", "mlxLm": "0.31.3", "platform": "macOS-test"},
        target={
            "text": config.target,
            "tokenIds": list(target_ids),
            "tokenCount": len(target_ids),
            "rendering": list(TARGET_RENDERING),
        },
        attempts=attempts,
        result=result,
        created_at="2026-10-16T00:00:00Z",
    )


def refix(receipt):
    receipt["receiptDigest"] = digest(receipts.receipt_body(receipt))
    return receipt


class ConfigTests(unittest.TestCase):
    def test_canary_config_fields_and_round_trip(self):
        config = fixtures.preset("canary-hello")
        self.assertEqual(config.to_canonical()["schema"], CONFIG_SCHEMA)
        self.assertEqual(config.target, "hello world")
        self.assertEqual(config.n_free_start, 5)
        self.assertEqual(config.steps_initial, 200)
        self.assertEqual(config.max_free_tokens, -1)
        self.assertEqual(config.topk, 250)
        self.assertEqual(config.batch, 100)
        self.assertEqual(config.seed, 42)
        self.assertEqual(config_from_canonical(config.to_canonical()), config)
        self.assertTrue(config.digest.startswith("sha256:"))

    def test_preset_digests_pinned(self):
        self.assertEqual(
            fixtures.preset("canary-hello").digest,
            "sha256:03e445cb65e458cb30f83d3b15944a12cc6de0ac762bd937cd64a973d7a2f533",
        )
        self.assertEqual(
            fixtures.preset("control-jumps-partial").digest,
            "sha256:2d54ba27610d46fc096cbe3622ad317085c5791684850f0426d4c569a503d055",
        )

    def test_unknown_and_missing_fields_rejected(self):
        mapping = fixtures.preset("canary-hello").to_canonical()
        with self.assertRaises(ConfigError):
            config_from_canonical({**mapping, "extra": 1})
        reduced = dict(mapping)
        del reduced["seed"]
        with self.assertRaises(ConfigError):
            config_from_canonical(reduced)
        with self.assertRaises(ConfigError):
            config_from_canonical({**mapping, "schema": "aleph-miniprompt-config/9.9.9"})
        with self.assertRaises(ConfigError):
            config_from_canonical({**mapping, "model": {**mapping["model"], "extra": 1}})

    def test_declared_value_guards(self):
        for key, value in (
            ("scaffold", "chat"),
            ("decoding", "sampling"),
            ("successCriterion", "loss"),
            ("nFreeStart", 0),
            ("nFreeStart", True),
            ("nFreeIncrement", -5),
            ("seed", -1),
            ("maxFreeTokens", 0),
            ("maxFreeTokens", -2),
            ("stepsInitial", 0),
            ("stepsHardCap", 0),
            ("maxAttempts", 0),
            ("topk", 0),
            ("batch", 0),
            ("miniBatch", 0),
            ("stepMultiplier", 0.5),
            ("stepMultiplier", float("nan")),
            ("stepMultiplier", float("inf")),
            ("stepMultiplier", True),
        ):
            with self.assertRaises(ConfigError, msg=key):
                variant(**{key: value})
        with self.assertRaises(ConfigError):
            variant(model={"repo": "r", "revision": "v", "weightsDigest": "sha256:nothex"})
        self.assertEqual(variant(stepMultiplier=2).step_multiplier, 2.0)

    def test_load_config_file_and_strict_json(self):
        config = fixtures.preset("control-jumps-partial")
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.json"
            path.write_text(json.dumps(config.to_canonical()), encoding="utf-8")
            self.assertEqual(load_config_file(path), config)
        with self.assertRaises(ValueError):
            loads_strict('{"a": 1, "a": 2}')


class SamplingTests(unittest.TestCase):
    def test_initial_free_ids_deterministic_and_in_range(self):
        first = sampling.initial_free_ids(42, 5, 151936)
        self.assertEqual(first, sampling.initial_free_ids(42, 5, 151936))
        self.assertEqual(len(first), 5)
        self.assertTrue(all(0 <= token < 151936 for token in first))
        self.assertNotEqual(first, sampling.initial_free_ids(43, 5, 151936))
        self.assertNotEqual(first, sampling.initial_free_ids(42, 4, 151936))

    def test_step_mutations_deterministic_and_in_range(self):
        first = sampling.step_mutations(42, 5, 250, 0, 100)
        self.assertEqual(first, sampling.step_mutations(42, 5, 250, 0, 100))
        self.assertEqual(len(first), 100)
        self.assertTrue(all(0 <= position < 5 and 0 <= pick < 250 for position, pick in first))
        self.assertNotEqual(first, sampling.step_mutations(42, 5, 250, 1, 100))

    def test_apply_mutations_changes_exactly_one_position(self):
        base = [10, 11, 12]
        rows = [[100, 101], [200, 201], [300, 301]]
        mutated = sampling.apply_mutations(base, rows, [(1, 1), (0, 0), (2, 1)])
        self.assertEqual(mutated, [[10, 201, 12], [100, 11, 12], [10, 11, 301]])
        for row in mutated:
            self.assertEqual(sum(1 for a, b in zip(row, base) if a != b), 1)


class ScanPolicyTests(unittest.TestCase):
    def test_failure_budget_sequence_pinned(self):
        policy = ScanPolicy(variant(maxFreeTokens=500, maxAttempts=8), len(TARGET_IDS))
        budgets = []
        while True:
            spec = policy.next_spec()
            if spec is None:
                break
            budgets.append(spec.steps_budget)
            policy.record(False)
        self.assertEqual(budgets, [200, 240, 288, 345, 414, 496, 595, 714])
        self.assertEqual(policy.state.stop_reason, "max_attempts")
        self.assertEqual(policy.state.steps_budget, 856)
        self.assertEqual(policy.state.running_max, 500)

    def test_descent_to_lower_bound_pinned(self):
        policy = ScanPolicy(fixtures.preset("canary-hello"), len(TARGET_IDS))
        sequence = []
        while True:
            spec = policy.next_spec()
            if spec is None:
                break
            sequence.append((spec.n_free, spec.steps_budget))
            policy.record(True)
        self.assertEqual(sequence, [(5, 200), (4, 200), (3, 200), (2, 200), (1, 200)])
        self.assertEqual(policy.state.stop_reason, "collision")
        self.assertTrue(policy.state.success)
        self.assertEqual(policy.state.running_max, 1)

    def test_mixed_fail_then_descent_collision_pinned(self):
        policy = ScanPolicy(variant(maxFreeTokens=30), len(TARGET_IDS))
        sequence = []
        for outcome in [False, True, True, True, True, True]:
            spec = policy.next_spec()
            sequence.append((spec.n_free, spec.steps_budget))
            policy.record(outcome)
        self.assertEqual(
            sequence, [(5, 200), (10, 240), (9, 240), (8, 240), (7, 240), (6, 240)]
        )
        self.assertEqual(policy.state.stop_reason, "collision")
        self.assertEqual(policy.state.running_max, 6)
        self.assertEqual(policy.state.running_min, 5)

    def test_auto_cap_first_failure_terminates(self):
        # maxFreeTokens == -1 resolves to 5 x target tokens (2 -> 10), so a
        # single failure at n=5 reaches the cap and terminates, exactly upstream.
        policy = ScanPolicy(fixtures.preset("canary-hello"), 2)
        spec = policy.next_spec()
        self.assertEqual((spec.n_free, spec.steps_budget), (5, 200))
        self.assertEqual(policy.state.running_max, 10)
        self.assertFalse(policy.record(False))
        self.assertEqual(policy.state.stop_reason, "collision")
        self.assertFalse(policy.state.success)
        self.assertEqual(policy.state.running_max, 10)

    def test_failure_only_natural_termination(self):
        policy = ScanPolicy(variant(maxFreeTokens=30), len(TARGET_IDS))
        sequence = []
        while True:
            spec = policy.next_spec()
            if spec is None:
                break
            sequence.append(spec.n_free)
            policy.record(False)
        self.assertEqual(sequence, [5, 10, 15, 20, 25])
        self.assertEqual(policy.state.stop_reason, "collision")
        self.assertFalse(policy.state.success)
        self.assertEqual(policy.state.running_max, 30)

    def test_max_attempts_stop(self):
        policy = ScanPolicy(variant(maxFreeTokens=30, maxAttempts=2), len(TARGET_IDS))
        self.assertIsNotNone(policy.next_spec())
        policy.record(False)
        self.assertIsNotNone(policy.next_spec())
        policy.record(False)
        self.assertIsNone(policy.next_spec())
        self.assertEqual(policy.state.stop_reason, "max_attempts")
        self.assertEqual(policy.state.attempts, 2)

    def test_steps_hard_cap_and_initial_clamp(self):
        policy = ScanPolicy(variant(maxFreeTokens=500, stepsHardCap=250), len(TARGET_IDS))
        budgets = []
        while True:
            spec = policy.next_spec()
            if spec is None:
                break
            budgets.append(spec.steps_budget)
            policy.record(False)
        self.assertEqual(budgets[:3], [200, 240, 250])
        self.assertTrue(all(budget == 250 for budget in budgets[2:]))
        clamped = ScanPolicy(variant(stepsInitial=500, stepsHardCap=100), len(TARGET_IDS))
        self.assertEqual(clamped.next_spec().steps_budget, 100)

    def test_record_after_done_raises(self):
        policy = ScanPolicy(fixtures.preset("canary-hello"), len(TARGET_IDS))
        while policy.record(True):
            policy.next_spec()
        with self.assertRaises(ScanPolicyError):
            policy.record(True)

    def test_replay_matches_and_rejects_overflow(self):
        config = variant(maxFreeTokens=30)
        specs, policy = replay_outcomes(config, len(TARGET_IDS), [False, True, True])
        self.assertEqual([(spec.n_free, spec.steps_budget) for spec in specs],
                         [(5, 200), (10, 240), (9, 240)])
        next_spec = policy.next_spec()
        self.assertEqual((next_spec.n_free, next_spec.steps_budget), (8, 240))
        with self.assertRaises(ScanPolicyError):
            replay_outcomes(fixtures.preset("canary-hello"), len(TARGET_IDS), [True] * 6)

    def test_snapshot_round_trip(self):
        policy = ScanPolicy(variant(maxFreeTokens=30), len(TARGET_IDS))
        policy.next_spec()
        policy.record(False)
        policy.next_spec()
        snapshot = policy.to_snapshot()
        restored = ScanPolicy.from_snapshot(variant(maxFreeTokens=30), len(TARGET_IDS), snapshot)
        self.assertEqual(restored.to_snapshot(), snapshot)
        self.assertEqual(restored.next_spec(), policy.next_spec())


class ReceiptTests(unittest.TestCase):
    def test_valid_receipt_passes_and_digest_recomputes(self):
        receipt = build_fixture_receipt(fixtures.preset("canary-hello"), [True] * 5)
        self.assertEqual(receipts.verify_receipt(receipt), [])
        self.assertEqual(receipt["receiptDigest"], digest(receipts.receipt_body(receipt)))
        self.assertTrue(receipts.receipt_body(receipt).get("receiptDigest") is None)

    def test_negative_control_receipt_shape(self):
        receipt = build_fixture_receipt(variant(maxFreeTokens=30, maxAttempts=2), [False, False])
        self.assertEqual(receipts.verify_receipt(receipt), [])
        self.assertFalse(receipt["result"]["success"])
        self.assertEqual(receipt["result"]["stopReason"], "max_attempts")
        self.assertIsNone(receipt["result"]["smallestAcquiredNFree"])
        self.assertTrue(all(attempt["greedy"] is None for attempt in receipt["attempts"]))

    def test_tamper_probes_fail_closed(self):
        base_receipt = build_fixture_receipt(fixtures.preset("canary-hello"), [True] * 5)
        failure_receipt = build_fixture_receipt(variant(maxFreeTokens=30, maxAttempts=2), [False, False])

        def mutate_and_expect(receipt, mutate, expected, refix_digest=True):
            bad = copy.deepcopy(receipt)
            mutate(bad)
            if refix_digest:
                refix(bad)
            errors = receipts.verify_receipt(bad)
            self.assertTrue(errors, expected)
            self.assertTrue(any(expected in error for error in errors), (expected, errors))

        mutate_and_expect(base_receipt, lambda r: r.__setitem__("receiptDigest", "sha256:" + "b" * 64),
                          "receiptDigest: does not match", refix_digest=False)
        mutate_and_expect(base_receipt, lambda r: r["attempts"][2].__setitem__("acquired", False),
                          "acquiredAtStep: expected null")
        mutate_and_expect(failure_receipt, lambda r: r["attempts"][0].__setitem__("acquired", True),
                          "claimed acquisitions require")
        mutate_and_expect(base_receipt, lambda r: r["attempts"][1].__setitem__("stepsBudget", 999),
                          "expected 200 from the scan policy")
        mutate_and_expect(base_receipt, lambda r: r["result"].__setitem__("numFreeTokens", 7),
                          "result.numFreeTokens: expected")
        mutate_and_expect(base_receipt, lambda r: r["result"].__setitem__("stopReason", "max_attempts"),
                          "result.stopReason: expected")
        mutate_and_expect(base_receipt, lambda r: r["result"].__setitem__("success", False),
                          "result.success: expected")
        mutate_and_expect(base_receipt, lambda r: r.__setitem__("attempts", r["attempts"][:4]),
                          "leave the scan unfinished")
        mutate_and_expect(base_receipt, lambda r: r["attempts"][0].__setitem__("stepsRun", 99),
                          "trajectory: length does not match stepsRun")
        mutate_and_expect(base_receipt, lambda r: r["attempts"][0].__setitem__("stepsRun", 999),
                          "stepsRun: exceeds the step budget")
        mutate_and_expect(base_receipt, lambda r: r["attempts"][0].__setitem__("trajectory", r["attempts"][0]["trajectory"][:1]),
                          "trajectory: length does not match stepsRun")
        mutate_and_expect(base_receipt, lambda r: r["attempts"][0]["trajectory"][0].__setitem__("extra", 1),
                          "unknown field 'extra'")
        mutate_and_expect(base_receipt, lambda r: r["attempts"][0]["greedy"].__setitem__("emittedIds", [1, 2]),
                          "does not reproduce the target token IDs")
        mutate_and_expect(base_receipt, lambda r: r["attempts"][0].__setitem__("greedy", None),
                          "claimed acquisitions require")
        mutate_and_expect(base_receipt, lambda r: r["attempts"][0].__setitem__("acquiredAtStep", 0),
                          "acquiredAtStep: expected 1")
        mutate_and_expect(base_receipt, lambda r: r["attempts"][0]["trajectory"][-1].__setitem__("loss", 0.9),
                          "does not match the acquisition step loss")
        mutate_and_expect(base_receipt, lambda r: r["rawView"].__setitem__("label", "readable prompt"),
                          "raw-coordinate labeling")
        mutate_and_expect(base_receipt, lambda r: r.__setitem__("createdAt", "yesterday"),
                          "expected an RFC 3339")
        mutate_and_expect(base_receipt, lambda r: r.__setitem__("extra", 1),
                          "unknown field 'extra'")
        mutate_and_expect(base_receipt, lambda r: r["attempts"][0].__setitem__("extra", 1),
                          "unknown field 'extra'")
        mutate_and_expect(base_receipt, lambda r: r["model"].__setitem__("weightsDigest", "sha256:" + "1" * 64),
                          "differs from the declared config")
        mutate_and_expect(base_receipt, lambda r: r["target"].__setitem__("tokenCount", 3),
                          "tokenCount: does not match")
        mutate_and_expect(base_receipt, lambda r: r.__setitem__("configDigest", "sha256:" + "c" * 64),
                          "configDigest: does not match")

    def test_state_io_round_trip(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "state.json"
            payload = {"schema": receipts.STATE_SCHEMA, "attempts": [1, 2, 3]}
            receipts.write_json_atomic(path, payload)
            self.assertEqual(receipts.read_json(path), payload)
            path.write_text('{"a": 1, "a": 2}', encoding="utf-8")
            with self.assertRaises(ValueError):
                receipts.read_json(path)


class CliTests(unittest.TestCase):
    def test_verify_ok_fail_and_directory(self):
        receipt = build_fixture_receipt(fixtures.preset("canary-hello"), [True] * 5)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "receipt.json"
            path.write_text(json.dumps(receipt), encoding="utf-8")
            for target in (str(path), str(Path(tmp))):
                ok = subprocess.run(
                    [sys.executable, "-m", "search.miniprompt.cli", "verify", target],
                    cwd=REPO_ROOT, capture_output=True, text=True,
                )
                self.assertEqual(ok.returncode, 0, ok.stderr or ok.stdout)
                self.assertIn("OK", ok.stdout)
            bad = copy.deepcopy(receipt)
            bad["result"]["attempts"] = 99
            path.write_text(json.dumps(bad), encoding="utf-8")
            fail = subprocess.run(
                [sys.executable, "-m", "search.miniprompt.cli", "verify", str(path)],
                cwd=REPO_ROOT, capture_output=True, text=True,
            )
            self.assertEqual(fail.returncode, 1)
            self.assertIn("FAIL", fail.stdout)

    def test_pure_import_surface_never_imports_mlx(self):
        code = (
            "import sys; import search.miniprompt.cli, search.miniprompt.fixtures, "
            "search.miniprompt.receipts, search.miniprompt.scan, search.miniprompt.sampling, "
            "search.miniprompt.config; assert 'mlx' not in sys.modules and 'mlx_lm' not in sys.modules; "
            "print('pure-ok')"
        )
        result = subprocess.run(
            [sys.executable, "-c", code], cwd=REPO_ROOT, capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("pure-ok", result.stdout)


if __name__ == "__main__":
    unittest.main()
