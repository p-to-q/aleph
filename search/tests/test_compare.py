"""Matched-budget comparison: strict config, readable artifact, records, CLI.

Pure standard-library tests (no MLX, no network): the declared fixtures and
their pinned digests, the strict config parser, the readable-artifact
verifier (with tamper probes), the digest-bound comparison record builder and
its fail-closed verifier against the real archived raw receipt, the
independent staircase mirror, the pure runner helpers, and the no-MLX
``verify`` command via subprocess.
"""

from __future__ import annotations

import copy
import json
import statistics
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from search.compare import config as compare_config  # noqa: E402
from search.compare import fixtures as compare_fixtures  # noqa: E402
from search.compare import readable  # noqa: E402
from search.compare import record  # noqa: E402
from search.compare.config import (  # noqa: E402
    CONFIG_SCHEMA,
    EXPLICIT_WRAPPER,
    ConfigError,
    config_from_canonical,
)
from search.engine.canonical import digest  # noqa: E402
from search.miniprompt import fixtures as miniprompt_fixtures  # noqa: E402
from search.miniprompt.receipts import verify_receipt  # noqa: E402

TARGET_IDS = [14990, 1879]
TARGET_RENDERING = ["hello", " world"]
ARCHIVED_RECEIPT = REPO_ROOT / "search/miniprompt/receipts/canary-hello-001/receipt.json"

CANARY_HELLO_DIGEST = "sha256:03e445cb65e458cb30f83d3b15944a12cc6de0ac762bd937cd64a973d7a2f533"
CONTROL_DIGEST = "sha256:2d54ba27610d46fc096cbe3622ad317085c5791684850f0426d4c569a503d055"
PIN4B_DIGEST = "sha256:40de569ad0e4798fa20289ffdb8cd219f22d2cd3a0cbc6550213495a62ac351f"
INSTANCE_1P7B_DIGEST = "sha256:6b0500eed3dd950e5c1e9b4ef5ccf73dd316ea2d43788ed59619dc8dae85a63f"
INSTANCE_4B_DIGEST = "sha256:fd4b450f7074842107722f3cc55308da3a50f100af948f203c9f31a811d9f72f"

TIMESTAMP = "2026-10-16T00:00:00Z"
PIN_1P7B = miniprompt_fixtures.PINNED_MODELS["mlx-community/Qwen3-1.7B-4bit"]


# ---------- independent small formulas for building synthetic artifacts ----------


def trigrams(text: str):
    lowered = text.lower()
    return {lowered[i : i + 3] for i in range(max(0, len(lowered) - 2))}


def ngram_similarity(a: str, b: str) -> float:
    ta, tb = trigrams(a), trigrams(b)
    return len(ta & tb) / len(ta | tb) if ta and tb else 0.0


def containment(prompt: str, target: str) -> float:
    tt = trigrams(target)
    return len(tt & trigrams(prompt)) / len(tt) if tt else 0.0


def contains_text(prompt: str, target: str) -> bool:
    tn = " ".join(target.lower().split())
    return bool(tn) and tn in " ".join(prompt.lower().split())


def unit_config(*, label="unit-hello", budgets=None, **readable_overrides):
    readable = {
        "budgets": budgets if budgets is not None else [6, 12, 25, 50],
        "candidatesPerBudget": 3,
        "refineSteps": 1,
        "stabilityRuns": 3,
        "stabilityTemperature": 0.8,
        "proposerSeed": 42,
        "metric": {"kind": "embedding_cosine", "model": "sentence-transformers/all-MiniLM-L6-v2"},
    }
    readable.update(readable_overrides)
    mapping = {
        "schema": CONFIG_SCHEMA,
        "label": label,
        "model": {
            "repo": "mlx-community/Qwen3-1.7B-4bit",
            "revision": PIN_1P7B["revision"],
            "weightsDigest": PIN_1P7B["weightsDigest"],
        },
        "targets": [
            {
                "key": "hello-world",
                "text": "hello world",
                "rawPreset": "canary-hello",
                "rawConfigDigest": CANARY_HELLO_DIGEST,
            }
        ],
        "readable": readable,
        "envelopeSeconds": 1800,
        "reproductionThresholdTau": 0.05,
        "explicitWrapper": EXPLICIT_WRAPPER,
    }
    return config_from_canonical(mapping)


def synthetic_readable(config, *, wall_clock=12.5):
    """A hand-built readable artifact that must pass ``verify_readable``.

    Planned per-budget outcomes (recorded similarities, first-strict-max with
    strict-improvement refinement): 50 -> r50@0.68; 25 -> c25@0.70 (refine
    0.65 rejected); 12 -> r12@0.66 (exact-output); 6 -> c6@0.32 (refine 0.31
    rejected); explicit @1.0. Kept staircase (ascending lengths 5/7/9/12/18):
    the budget-50 point is dominated and not kept.
    """
    spec = config.targets[0]
    budgets = sorted(config.readable.budgets, reverse=True)
    k = config.readable.candidates_per_budget
    refine_steps = config.readable.refine_steps
    stability_runs = config.readable.stability_runs
    target_text = spec.text

    evaluations = []
    points = []

    def add_eval(phase, budget, prompt, similarity, output):
        entry = {
            "index": len(evaluations),
            "phase": phase,
            "budget": budget,
            "prompt": prompt,
            "promptDigest": digest(prompt),
            "output": output,
            "outputDigest": digest(output),
            "similarity": similarity,
            "similarityNgram3": round(ngram_similarity(output, target_text), 4),
            "outputEqualsTarget": output == target_text.strip(),
            "seconds": 0.1,
            "promptContainsTargetText": contains_text(prompt, target_text),
            "promptTargetTrigramContainment": round(containment(prompt, target_text), 4),
        }
        evaluations.append(entry)
        return entry

    def add_point(budget, evaluation, sims, length, role=None):
        point = {
            "budget": budget,
            "evaluationIndex": evaluation["index"],
            "prompt": evaluation["prompt"],
            "promptDigest": digest(evaluation["prompt"]),
            "promptTokenIds": [100 + i for i in range(length)],
            "length": length,
            "similarity": evaluation["similarity"],
            "epsilon": round(1.0 - evaluation["similarity"], 4),
            "output": evaluation["output"],
            "outputDigest": digest(evaluation["output"]),
            "outputEqualsTarget": evaluation["outputEqualsTarget"],
            "toktext": ["hello", " world"],
            "toknll": [0.5, 0.5],
            "stabilitySimilarities": sims,
            "stability": round(
                max(0.0, 1.0 - min(1.0, statistics.pstdev(sims) * 4)), 3
            )
            if len(sims) >= 2
            else 1.0,
            "kept": False,
        }
        if role is not None:
            point["role"] = role
        points.append(point)
        return point

    plan = {
        50: {
            "proposals": [("p50a", 0.50), ("p50b", 0.55), ("p50c", 0.60)],
            "refine": [("r50", 0.68)],
            "stability": [("r50", 0.66), ("r50", 0.68), ("r50", 0.70)],
            "point": ("r50", 12),
        },
        25: {
            "proposals": [("p25a", 0.60), ("p25b", 0.55), ("p25c", 0.58)],
            "compress": ("c25", 0.70),
            "refine": [("r25", 0.65)],
            "stability": [("c25", 0.69), ("c25", 0.70), ("c25", 0.71)],
            "point": ("c25", 9),
        },
        12: {
            "proposals": [("p12a", 0.40), ("p12b", 0.45), ("p12c", 0.44)],
            "compress": ("c12", 0.35),
            "refine": [("r12", 0.66)],
            "stability": [("r12", 0.64), ("r12", 0.66), ("r12", 0.68)],
            "point": ("r12", 7),
        },
        6: {
            "proposals": [("p6a", 0.30), ("p6b", 0.28), ("p6c", 0.26)],
            "compress": ("c6", 0.32),
            "refine": [("r6", 0.31)],
            "stability": [("c6", 0.30), ("c6", 0.32), ("c6", 0.34)],
            "point": ("c6", 5),
        },
    }
    for position, budget in enumerate(budgets):
        block = plan[budget]
        if len(block["proposals"]) > k:
            raise AssertionError("test plan exceeds candidatesPerBudget")
        best = None
        for prompt, similarity in block["proposals"]:
            output = f"out {prompt} {budget}"
            evaluation = add_eval("propose", budget, prompt, similarity, output)
            if best is None or similarity > best[1]:
                best = (evaluation, similarity)
        if "compress" in block:
            prompt, similarity = block["compress"]
            evaluation = add_eval("compress", budget, prompt, similarity, f"out {prompt} {budget}")
            if similarity > best[1]:
                best = (evaluation, similarity)
        for prompt, similarity in block["refine"]:
            output = target_text if prompt == "r12" else f"out {prompt} {budget}"
            evaluation = add_eval("refine", budget, prompt, similarity, output)
            if similarity > best[1]:
                best = (evaluation, similarity)
        point_prompt = block["point"][0]
        if best[0]["prompt"] != point_prompt:
            raise AssertionError("test plan point does not match its derivation")
        sims = []
        for prompt, similarity in block["stability"]:
            if prompt != point_prompt:
                raise AssertionError("test plan stability runs must follow the point prompt")
            add_eval("stability", budget, prompt, similarity, f"out {prompt} {budget} s")
            sims.append(similarity)
        add_point(budget, best[0], sims, block["point"][1])

    explicit_prompt = config.explicit_wrapper + target_text
    explicit = add_eval("explicit", None, explicit_prompt, 1.0, target_text)
    add_point(None, explicit, [], 18, role="explicit_reconstruction")

    kept = set(record.derive_kept_indices([dict(point, kept=None) for point in points]))
    for index, point in enumerate(points):
        point["kept"] = index in kept

    return {
        "schema": compare_config.READABLE_SCHEMA,
        "tool": {"name": "search/compare", "version": "0.1.0"},
        "createdAt": TIMESTAMP,
        "instance": config.label,
        "configDigest": config.digest,
        "target": {
            "key": spec.key,
            "text": spec.text,
            "tokenIds": list(TARGET_IDS),
            "tokenCount": len(TARGET_IDS),
            "rendering": list(TARGET_RENDERING),
        },
        "model": {
            "repo": config.repo,
            "revision": config.revision,
            "weightsDigest": config.weights_digest,
            "vocabSize": 151936,
        },
        "metric": {
            "kind": config.readable.metric_kind,
            "model": config.readable.metric_model,
            "secondary": dict(record.METRIC_SECONDARY),
        },
        "procedure": {
            "entrypoint": "unit-test",
            "budgets": budgets,
            "candidatesPerBudget": k,
            "refineSteps": refine_steps,
            "stabilityRuns": stability_runs,
            "stabilityTemperature": config.readable.stability_temperature,
            "proposerSeed": config.readable.proposer_seed,
            "generation": {
                "temperature": 0.0,
                "maxOutNonExplicit": int(len(TARGET_IDS) * 1.6) + 32,
                "maxOutExplicit": int(len(TARGET_IDS) * 1.4) + 32,
                "template": "unit-test template",
            },
            "proposeTemperature": 0.85,
            "compressTemperature": 0.5,
            "refineTemperature": 0.6,
            "explicitWrapper": config.explicit_wrapper,
            "rngSeeded": True,
            "declaredDifferences": ["unit-test declaration"],
        },
        "environment": {
            "python": "3.13.0",
            "mlx": "0.31.2",
            "mlxLm": "0.31.3",
            "sentenceTransformers": "5.4.1",
            "platform": "unit-test",
        },
        "startedAt": TIMESTAMP,
        "stoppedAt": TIMESTAMP,
        "wallClockSeconds": wall_clock,
        "stoppedBy": "complete",
        "evaluations": evaluations,
        "points": points,
        "result": {"complete": True, "evaluations": len(evaluations), "points": len(points)},
    }


def write_instance_tree(base: Path, config, doc, receipt, *, with_cli_output=True) -> None:
    target_dir = base / "targets" / "hello-world"
    (target_dir / "raw").mkdir(parents=True, exist_ok=True)
    (target_dir / "raw" / "receipt.json").write_text(
        json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    if with_cli_output:
        (target_dir / "raw" / "cli-output.txt").write_text("unit-test cli output\n", encoding="utf-8")
    (target_dir / "readable.json").write_text(
        json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def archived_receipt() -> dict:
    return record.load_json_strict(ARCHIVED_RECEIPT)


def build_unit_record(base: Path):
    config = unit_config()
    receipt = archived_receipt()
    doc = synthetic_readable(config)
    write_instance_tree(base, config, doc, receipt)
    payload = {
        "key": "hello-world",
        "raw": {"receipt": receipt, "wallClockSeconds": round(record.raw_wall_clock_seconds(receipt), 1)},
        "readable": {"doc": doc, "wallClockSeconds": doc["wallClockSeconds"]},
    }
    record_obj = record.build_comparison_record(
        config=config, targets=[payload], created_at="2026-10-16T09:30:00Z", base_dir=base
    )
    return config, record_obj, doc, receipt


class FixtureTests(unittest.TestCase):
    def test_pinned_preset_digests(self):
        self.assertEqual(miniprompt_fixtures.preset("canary-hello").digest, CANARY_HELLO_DIGEST)
        self.assertEqual(miniprompt_fixtures.preset("control-jumps-partial").digest, CONTROL_DIGEST)
        self.assertEqual(miniprompt_fixtures.preset("pin4b-hello-smoke").digest, PIN4B_DIGEST)

    def test_instance_digests_and_shape(self):
        canary = compare_fixtures.instance("canary-1p7b")
        self.assertEqual(canary.digest, INSTANCE_1P7B_DIGEST)
        self.assertEqual([target.key for target in canary.targets], ["hello-world", "lazy-dog"])
        self.assertEqual(canary.targets[0].raw_config_digest, CANARY_HELLO_DIGEST)
        self.assertEqual(canary.targets[1].raw_config_digest, CONTROL_DIGEST)
        four_b = compare_fixtures.instance("canary-4b")
        self.assertEqual(four_b.digest, INSTANCE_4B_DIGEST)
        self.assertEqual(four_b.targets[0].raw_config_digest, PIN4B_DIGEST)

    def test_archived_receipt_matches_declared_preset(self):
        receipt = archived_receipt()
        self.assertEqual(verify_receipt(receipt), [])
        self.assertEqual(receipt["configDigest"], CANARY_HELLO_DIGEST)
        self.assertEqual(receipt["target"]["tokenIds"], TARGET_IDS)
        self.assertEqual(round(record.raw_wall_clock_seconds(receipt), 1), 185.6)

    def test_explicit_wrapper_matches_shipped_literal(self):
        self.assertEqual(
            EXPLICIT_WRAPPER,
            "Repeat the following text exactly, verbatim, with no preamble, quotes, or commentary:\n\n",
        )


class ConfigTests(unittest.TestCase):
    def test_strict_rejections(self):
        base = unit_config().to_canonical()
        probes = []

        extra = copy.deepcopy(base)
        extra["extra"] = 1
        probes.append(extra)

        dup_budget = copy.deepcopy(base)
        dup_budget["readable"]["budgets"] = [6, 6]
        probes.append(dup_budget)

        bad_tau = copy.deepcopy(base)
        bad_tau["reproductionThresholdTau"] = 1.5
        probes.append(bad_tau)

        bad_wrapper = copy.deepcopy(base)
        bad_wrapper["explicitWrapper"] = "no blank line"
        probes.append(bad_wrapper)

        bad_digest = copy.deepcopy(base)
        bad_digest["model"]["weightsDigest"] = "not-a-digest"
        probes.append(bad_digest)

        dup_preset = copy.deepcopy(base)
        dup_preset["targets"] = [base["targets"][0], dict(base["targets"][0], key="other")]
        probes.append(dup_preset)

        bad_metric = copy.deepcopy(base)
        bad_metric["readable"]["metric"]["kind"] = "ngram"
        probes.append(bad_metric)

        for probe in probes:
            with self.assertRaises(ConfigError):
                config_from_canonical(probe)

    def test_round_trip(self):
        config = unit_config()
        parsed = config_from_canonical(config.to_canonical())
        self.assertEqual(parsed, config)
        self.assertEqual(parsed.digest, config.digest)


class ReadableArtifactTests(unittest.TestCase):
    def test_synthetic_artifact_verifies(self):
        config = unit_config()
        doc = synthetic_readable(config)
        self.assertEqual(record.verify_readable(doc), [])
        findings = record.readable_findings(doc["points"], config.reproduction_threshold_tau)
        self.assertIsNone(findings["readableFound"])
        self.assertEqual(findings["readableBest"]["epsilon"], 0.30)
        self.assertEqual(findings["readableExactMinLength"], 7)
        self.assertEqual(findings["explicitBaseline"]["length"], 18)
        derived = set(record.derive_kept_indices(doc["points"]))
        self.assertEqual(derived, {1, 2, 3, 4})  # budget-50 point is dominated

    def tamper(self, mutate):
        config = unit_config()
        doc = synthetic_readable(config)
        mutate(doc)
        return record.verify_readable(doc)

    def test_tamper_probes(self):
        def first_non_explicit(point):
            return point.get("role") != "explicit_reconstruction"

        def flip_kept(doc):
            for point in doc["points"]:
                if point["budget"] == 50:  # the dominated point, recorded as not kept
                    point["kept"] = True

        def shift_budget(doc):
            doc["evaluations"][1]["budget"] = 25

        def stability_mismatch(doc):
            for point in doc["points"]:
                if point["budget"] == 25:
                    point["stabilitySimilarities"][0] = 0.5

        def drop_stability(doc):
            doc["evaluations"] = [
                e for e in doc["evaluations"] if not (e["phase"] == "stability" and e["budget"] == 6)
            ]

        def prompt_digest(doc):
            doc["points"][1]["prompt"] = "tampered"

        def point_similarity(doc):
            for point in doc["points"]:
                if point["budget"] == 25:
                    point["similarity"] = 0.99
                    point["epsilon"] = 0.01

        def equals_flag(doc):
            doc["evaluations"][0]["outputEqualsTarget"] = True

        def epsilon_inconsistent(doc):
            doc["points"][0]["epsilon"] = doc["points"][0]["epsilon"] + 0.01

        def unknown_eval_field(doc):
            doc["evaluations"][0]["extra"] = 1

        def unknown_point_field(doc):
            doc["points"][1]["extra"] = 1

        def point_equals_flag(doc):
            doc["points"][2]["outputEqualsTarget"] = False

        def explicit_budget(doc):
            doc["evaluations"][-1]["budget"] = 6

        def role_on_budget_point(doc):
            doc["points"][0]["role"] = "generated"

        def negative_zero_epsilon(doc):
            doc["points"][0]["epsilon"] = -0.0

        def negative_zero_loss(doc):
            doc["points"][0]["toknll"] = [0.5, -0.0]

        def toktext_length(doc):
            doc["points"][0]["toktext"] = ["hello"]

        def token_ids_length(doc):
            doc["points"][0]["promptTokenIds"] = [1, 2, 3]

        def result_counts(doc):
            doc["result"]["evaluations"] = 1

        def stopping(doc):
            doc["stoppedBy"] = "time_budget"

        def unknown_top_field(doc):
            doc["note"] = "x"

        probes = {
            "kept flag": flip_kept,
            "evaluation budget": shift_budget,
            "stability similarity": stability_mismatch,
            "missing stability run": drop_stability,
            "point prompt": prompt_digest,
            "point similarity": point_similarity,
            "equals flag": equals_flag,
            "epsilon inconsistency": epsilon_inconsistent,
            "unknown evaluation field": unknown_eval_field,
            "unknown point field": unknown_point_field,
            "point equals flag": point_equals_flag,
            "explicit budget": explicit_budget,
            "role on budget point": role_on_budget_point,
            "negative zero epsilon": negative_zero_epsilon,
            "negative zero loss": negative_zero_loss,
            "toktext length": toktext_length,
            "prompt token ids length": token_ids_length,
            "result counts": result_counts,
            "stoppedBy": stopping,
            "unknown top-level field": unknown_top_field,
        }
        for name, mutate in probes.items():
            with self.subTest(name=name):
                self.assertNotEqual(self.tamper(mutate), [], f"probe {name} was not caught")


class RecordTests(unittest.TestCase):
    def test_build_and_verify_round_trip(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            config, record_obj, doc, receipt = build_unit_record(base)
            self.assertEqual(record.verify_comparison(record_obj, base), [])
            block = record_obj["targets"][0]
            self.assertEqual(record_obj["totals"], {"targets": 1, "rawAcquired": 1, "readableFoundUnderTau": 0})
            self.assertEqual(block["findings"]["rawFound"]["wholePromptTokens"], 5)
            self.assertIsNone(block["findings"]["readableFound"])
            self.assertEqual(block["findings"]["readableBest"]["epsilon"], 0.30)
            self.assertTrue(all(value is True for value in block["crossChecks"].values()))
            self.assertEqual(block["raw"]["wallClockSeconds"], 185.6)
            # JSON round trip through a serialized copy, then verify again
            written = json.loads(json.dumps(record_obj))
            self.assertEqual(record.verify_comparison(written, base), [])

    def test_record_tamper_probes(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            _, record_obj, _, _ = build_unit_record(base)

            def probe(mutate):
                candidate = copy.deepcopy(record_obj)
                mutate(candidate)
                return record.verify_comparison(candidate, base)

            self.assertNotEqual(probe(lambda r: r.update(receiptDigest="sha256:" + "0" * 64)), [])
            self.assertNotEqual(probe(lambda r: r["totals"].update(readableFoundUnderTau=1)), [])
            self.assertNotEqual(
                probe(lambda r: r["targets"][0]["findings"]["readableBest"].update(epsilon=0.31)), []
            )
            self.assertNotEqual(probe(lambda r: r["targets"][0]["raw"].update(wallClockSeconds=200.0)), [])
            self.assertNotEqual(
                probe(lambda r: r["targets"][0]["readable"].update(artifactDigest=digest("x"))), []
            )
            self.assertNotEqual(
                probe(lambda r: r["targets"][0]["crossChecks"].update(modelIdentityEqual=False)), []
            )
            self.assertNotEqual(probe(lambda r: r.update(extra=1)), [])

    def test_build_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            config = unit_config()
            receipt = archived_receipt()
            doc = synthetic_readable(config)
            write_instance_tree(base, config, doc, receipt)
            payload = {
                "key": "hello-world",
                "raw": {"receipt": receipt, "wallClockSeconds": 185.6},
                "readable": {"doc": doc, "wallClockSeconds": doc["wallClockSeconds"]},
            }
            with self.assertRaises(record.ComparisonError):
                record.build_comparison_record(
                    config=config,
                    targets=[dict(payload, raw={"receipt": receipt, "wallClockSeconds": None})],
                    created_at=TIMESTAMP,
                    base_dir=base,
                )
            bad_doc = copy.deepcopy(doc)
            bad_doc["points"][0]["epsilon"] = bad_doc["points"][0]["epsilon"] + 0.05
            with self.assertRaises(record.ComparisonError):
                record.build_comparison_record(
                    config=config,
                    targets=[dict(payload, readable={"doc": bad_doc, "wallClockSeconds": 12.5})],
                    created_at=TIMESTAMP,
                    base_dir=base,
                )

    def test_on_disk_tamper_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            _, record_obj, _, _ = build_unit_record(base)
            self.assertEqual(record.verify_comparison(record_obj, base), [])
            target_dir = base / "targets" / "hello-world"
            readable_path = target_dir / "readable.json"
            doc = json.loads(readable_path.read_text(encoding="utf-8"))
            doc["evaluations"][0]["output"] = "tampered on disk"
            readable_path.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            errors = record.verify_comparison(record_obj, base)
            self.assertTrue(any("artifact" in error or "readable" in error for error in errors))
            # restore, then remove the cli-output file the record references
            write_instance_tree(base, unit_config(), synthetic_readable(unit_config()), archived_receipt())
            (target_dir / "raw" / "cli-output.txt").unlink()
            errors = record.verify_comparison(record_obj, base)
            self.assertTrue(any("cliOutputRef" in error for error in errors))

    def test_kept_derivation_matches_shipped_selector(self):
        import search.aleph_search as shipped

        cases = [
            [
                {"length": 8, "epsilon": 0.4, "prompt": "a", "output": "x"},
                {"length": 8, "epsilon": 0.2, "prompt": "b", "output": "x"},
                {"length": 12, "epsilon": 0.3, "prompt": "c", "output": "x"},
                {"length": 20, "epsilon": 0.0, "prompt": "d", "output": "x", "role": "explicit_reconstruction"},
            ],
            [
                {"length": 5, "epsilon": 0.9, "prompt": "a", "output": "x"},
                {"length": 9, "epsilon": 0.5, "prompt": "b", "output": "x"},
                {"length": 9, "epsilon": 0.4, "prompt": "c", "output": "x"},
                {"length": 9, "epsilon": 0.6, "prompt": "d", "output": "x"},
            ],
        ]
        for case in cases:
            frontier = shipped.observed_length_distortion_frontier(copy.deepcopy(case))
            shipped_kept = set()
            for kept_point in frontier:
                for index, point in enumerate(case):
                    if point == kept_point:
                        shipped_kept.add(index)
                        break
            self.assertEqual(set(record.derive_kept_indices(copy.deepcopy(case))), shipped_kept)

    def test_stability_scalar_pin(self):
        self.assertEqual(record.stability_scalar([0.8, 0.9, 1.0]), 0.673)
        self.assertEqual(record.stability_scalar([]), 1.0)

    def test_copy_proxy_helpers(self):
        self.assertTrue(record.prompt_contains_target_text("Say HELLO   world now", "hello world"))
        self.assertFalse(record.prompt_contains_target_text("hello-world", "hello world"))
        self.assertEqual(record.target_trigram_containment("hello world", "hello world"), 1.0)
        self.assertEqual(record.char_trigram_similarity("abc", "abc"), 1.0)


class ReadableDryRunTests(unittest.TestCase):
    """Drive the readable state machine end-to-end with faked model objects."""

    def _fake_gcg(self):
        import types

        fake = types.ModuleType("search.miniprompt.gcg")

        def load_pinned(repo, revision, weights_digest):
            return (
                object(),
                object(),
                {
                    "repo": repo,
                    "revision": revision,
                    "weightsDigest": weights_digest,
                    "vocabSize": 151936,
                },
            )

        def target_token_ids(tokenizer, text):
            return list(TARGET_IDS), list(TARGET_RENDERING)

        fake.load_pinned = load_pinned
        fake.target_token_ids = target_token_ids
        return fake

    def _fake_gen(self, prompt, max_tokens, temp=0.0, seed=None):
        if prompt.startswith(EXPLICIT_WRAPPER):
            return "hello world"
        if "different candidate" in prompt:
            return "alpha prompt\nbeta prompt\ngamma prompt"
        if "Rewrite it to AT MOST" in prompt:
            return "compressed prompt"
        if "Improve the PROMPT" in prompt:
            return "refined prompt"
        return f"generated {len(prompt)}"

    def _fake_score(self, prompt, target):
        return ["hello", " world"], [0.25, 0.5]

    def _fake_environment(self):
        return {
            "python": "3.13.0",
            "mlx": "0.31.2",
            "mlxLm": "0.31.3",
            "sentenceTransformers": "5.4.1",
            "platform": "dry-run",
        }

    def test_dry_run_pause_resume_complete_and_refusals(self):
        import search.miniprompt as miniprompt_package

        class FakeTok:
            def encode(self, text):
                return [7 + i for i in range(max(1, len(text.split())))]

        class FakeMetric:
            def __init__(self):
                self.calls = 0

            def sim(self, a, b):
                self.calls += 1
                return min(0.99, 0.2 + 0.03 * self.calls)

        config = unit_config()
        spec = config.targets[0]
        fake_gcg = self._fake_gcg()
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(
            sys.modules, {"search.miniprompt.gcg": fake_gcg}
        ), mock.patch.object(
            miniprompt_package, "gcg", fake_gcg, create=True
        ), mock.patch.object(
            readable.Theta, "gen", self._fake_gen
        ), mock.patch.object(
            readable.Theta, "score", self._fake_score
        ), mock.patch.object(
            readable, "Metric", FakeMetric
        ), mock.patch.object(
            readable, "environment_metadata", self._fake_environment
        ):
            # the model identity is taken from the fake load_pinned kwargs
            run_dir = Path(tmp) / "live-1p7b" / "targets" / spec.key
            paused = readable.run_target(config, spec, run_dir, max_seconds=0.0, log=lambda *a: None)
            self.assertEqual(paused, 3)
            state_path = run_dir / "readable-state.json"
            self.assertTrue(state_path.is_file())

            # give point_build a tokenizer with a working encode
            original_load = fake_gcg.load_pinned

            def load_pinned_with_tokenizer(repo, revision, weights_digest):
                model, _, meta = original_load(repo, revision, weights_digest)
                return model, FakeTok(), meta

            fake_gcg.load_pinned = load_pinned_with_tokenizer
            completed = readable.run_target(config, spec, run_dir, max_seconds=None, log=lambda *a: None)
            self.assertEqual(completed, 0)
            doc = record.load_json_strict(run_dir / "readable.json")
            self.assertEqual(record.verify_readable(doc), [])
            self.assertEqual(doc["stoppedBy"], "complete")
            self.assertEqual(len(doc["points"]), len(config.readable.budgets) + 1)
            self.assertEqual(doc["result"]["evaluations"], len(doc["evaluations"]))
            budget_evals = {}
            for evaluation in doc["evaluations"]:
                budget_evals[(evaluation["phase"], evaluation["budget"])] = (
                    budget_evals.get((evaluation["phase"], evaluation["budget"]), 0) + 1
                )
            self.assertEqual(budget_evals[("propose", 50)], 3)
            self.assertNotIn(("compress", 50), budget_evals)
            self.assertEqual(budget_evals[("compress", 25)], 1)
            self.assertEqual(budget_evals[("explicit", None)], 1)

            # idempotent completion fast path
            again = readable.run_target(config, spec, run_dir, max_seconds=None, log=lambda *a: None)
            self.assertEqual(again, 0)

            # a tampered artifact must be refused, not overwritten
            artifact = run_dir / "readable.json"
            tampered = json.loads(artifact.read_text(encoding="utf-8"))
            tampered["wallClockSeconds"] = "not-a-number"
            artifact.write_text(json.dumps(tampered), encoding="utf-8")
            with self.assertRaises(readable.ReadableRunError):
                readable.run_target(config, spec, run_dir, max_seconds=None, log=lambda *a: None)


class ReadableHelperTests(unittest.TestCase):
    def test_parse_and_clean(self):
        text = "1. Here are prompts\n- first prompt\n\u2022 second prompt\nfirst prompt\nx\nthird prompt"
        self.assertEqual(readable.clean_line('2) "hello world"'), "hello world")
        self.assertEqual(readable.clean_line("\u2022 bullet text"), "bullet text")
        self.assertEqual(readable.parse_candidates(text, 5), ["first prompt", "second prompt", "third prompt"])
        self.assertEqual(readable.parse_candidates("", 3), [])
        self.assertEqual(readable.fallback_prompt("hello world", 50), "Write the text: hello world")

    def test_hardest_tokens(self):
        toks = ["the", "quick", "fox", "the", "a", "b"]
        nlls = [0.1, 2.0, 1.5, 0.2, 3.0, 0.01]
        # "a" is skipped by the shipped minimum-length filter; duplicate "the" keeps one entry
        self.assertEqual(readable.hardest_tokens(toks, nlls, k=8), ["quick", "fox", "the"])

    def test_proposal_seed_deterministic_and_distinct(self):
        config = compare_fixtures.instance("canary-1p7b")
        first = readable.proposal_seed(config, "hello-world", "propose", 0)
        self.assertEqual(first, readable.proposal_seed(config, "hello-world", "propose", 0))
        self.assertNotEqual(first, readable.proposal_seed(config, "hello-world", "propose", 1))
        self.assertNotEqual(first, readable.proposal_seed(config, "lazy-dog", "propose", 0))


class CompareCliTests(unittest.TestCase):
    def test_verify_cli_ok_and_fail(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            write_instance_tree(base, unit_config(), synthetic_readable(unit_config()), archived_receipt())
            payload = {
                "key": "hello-world",
                "raw": {
                    "receipt": archived_receipt(),
                    "wallClockSeconds": round(record.raw_wall_clock_seconds(archived_receipt()), 1),
                },
                "readable": {"doc": synthetic_readable(unit_config()), "wallClockSeconds": 12.5},
            }
            record_obj = record.build_comparison_record(
                config=unit_config(), targets=[payload], created_at=TIMESTAMP, base_dir=base
            )
            (base / "comparison.json").write_text(
                json.dumps(record_obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
            )
            ok = subprocess.run(
                [sys.executable, "-m", "search.compare.cli", "verify", str(base)],
                cwd=str(REPO_ROOT),
                capture_output=True,
                text=True,
            )
            self.assertEqual(ok.returncode, 0, ok.stdout + ok.stderr)
            self.assertTrue(ok.stdout.startswith("OK"), ok.stdout)

            bad = copy.deepcopy(record_obj)
            bad["totals"]["rawAcquired"] = 0
            (base / "comparison.json").write_text(
                json.dumps(bad, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
            )
            failed = subprocess.run(
                [sys.executable, "-m", "search.compare.cli", "verify", str(base)],
                cwd=str(REPO_ROOT),
                capture_output=True,
                text=True,
            )
            self.assertEqual(failed.returncode, 1)
            self.assertIn("FAIL", failed.stdout)

    def test_verify_cli_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = subprocess.run(
                [sys.executable, "-m", "search.compare.cli", "verify", tmp],
                cwd=str(REPO_ROOT),
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 1)
            self.assertIn("no comparison record", result.stdout)


if __name__ == "__main__":
    unittest.main()
