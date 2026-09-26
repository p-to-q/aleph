from __future__ import annotations

import copy
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

BOUNDED_ROOT = Path(__file__).resolve().parents[1] / "bounded"
REPOSITORY_ROOT = Path(__file__).resolve().parents[2]

from search.bounded.model import (
    ProblemManifest,
    budget_value_curve,
    enumerate_landscape,
    evaluate,
    exact_optimum,
    observed_frontier,
    sha256_file,
    write_json,
)
from search.bounded.generate_lean import render_problem
from search.bounded.run import build_receipt
from search.bounded.verify import build_verification, verify_receipt_data
from search.bounded.verify_lean import expected_lean_receipt


MANIFEST_PATH = BOUNDED_ROOT / "problem.json"
RECEIPT_PATH = BOUNDED_ROOT / "results" / "receipt.json"
VERIFICATION_PATH = BOUNDED_ROOT / "results" / "verification.json"
LEAN_VERIFICATION_PATH = BOUNDED_ROOT / "results" / "lean-verification.json"
EXPECTED_RECEIPT_FILE_SHA256 = "ebbab77602d67070bcbaa58ce1897b6d6dc815b6edd00461daffeb320af7c058"


class BoundedCoordinateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.manifest = ProblemManifest.from_path(MANIFEST_PATH)

    def test_exact_enumeration_has_a_shared_four_token_optimum(self) -> None:
        expected_count = sum(
            len(self.manifest.alphabet) ** length
            for length in range(self.manifest.max_coordinate_tokens + 1)
        )
        optima = []
        for landscape in ("compositional", "opaque"):
            archive = enumerate_landscape(self.manifest, landscape)
            self.assertEqual(len(archive), expected_count)
            optimum = exact_optimum(archive)
            self.assertEqual(optimum.length, 4)
            self.assertEqual(optimum.coordinate, ("A", "B", "C", "D"))
            self.assertTrue(all(not item.exact for item in archive if item.length < 4))
            optima.append(optimum.coordinate)
        self.assertEqual(optima[0], optima[1])

    def test_frontier_is_an_unchanged_subset_and_budget_curve_uses_witnesses(self) -> None:
        for landscape in ("compositional", "opaque"):
            archive = enumerate_landscape(self.manifest, landscape)
            frontier = observed_frontier(archive)
            self.assertTrue(all(point in archive for point in frontier))
            self.assertEqual(observed_frontier(frontier), frontier)
            curve = budget_value_curve(archive, self.manifest.max_coordinate_tokens)
            by_id = {point.id: point for point in archive}
            for value in curve:
                witness = by_id[value["witnessCandidateId"]]
                self.assertEqual(value["witnessLength"], witness.length)
                self.assertLessEqual(witness.length, value["coordinateTokenBudget"])

    def test_matched_beam_budget_exposes_the_feedback_geometry_gap(self) -> None:
        receipt = build_receipt(self.manifest)
        runs = {run["id"]: run for run in receipt["searchRuns"]}
        compositional = runs["compositional:beam-1"]
        opaque = runs["opaque:beam-1"]
        self.assertEqual(compositional["evaluationBudget"], opaque["evaluationBudget"])
        self.assertEqual(
            compositional["candidateEvaluatorCalls"],
            opaque["candidateEvaluatorCalls"],
        )
        self.assertEqual(compositional["logicalAdaptiveRounds"], 4)
        self.assertEqual(opaque["logicalAdaptiveRounds"], 4)
        self.assertEqual(compositional["firstHitEvaluationOrdinal"], 16)
        self.assertTrue(compositional["success"])
        self.assertIsNone(opaque["firstHitEvaluationOrdinal"])
        self.assertFalse(opaque["success"])

        for landscape in ("compositional", "opaque"):
            self.assertEqual(
                runs[f"{landscape}:exhaustive"]["logicalAdaptiveRounds"],
                1,
            )
            self.assertEqual(
                runs[f"{landscape}:priority-16-seed-1729"]["logicalAdaptiveRounds"],
                1,
            )

        archive_coordinates = {
            point["id"]: point["coordinate"] for point in receipt["candidateArchive"]
        }
        compositional_priority = runs["compositional:priority-16-seed-1729"]
        opaque_priority = runs["opaque:priority-16-seed-1729"]
        self.assertEqual(
            [archive_coordinates[item] for item in compositional_priority["evaluationCandidateIds"]],
            [archive_coordinates[item] for item in opaque_priority["evaluationCandidateIds"]],
        )

    def test_seeded_receipt_is_byte_stable_and_independently_verifiable(self) -> None:
        first = build_receipt(self.manifest)
        second = build_receipt(self.manifest)
        first_bytes = json.dumps(first, sort_keys=True, separators=(",", ":"))
        second_bytes = json.dumps(second, sort_keys=True, separators=(",", ":"))
        self.assertEqual(first_bytes, second_bytes)
        self.assertEqual(verify_receipt_data(self.manifest, first), [])
        with tempfile.TemporaryDirectory() as temp_dir:
            first_path = Path(temp_dir) / "first.json"
            second_path = Path(temp_dir) / "second.json"
            write_json(first_path, first)
            write_json(second_path, second)
            self.assertEqual(first_path.read_bytes(), second_path.read_bytes())
            self.assertEqual(sha256_file(first_path), sha256_file(second_path))

            env = os.environ.copy()
            env["PYTHONHASHSEED"] = "1"
            subprocess.run(
                [sys.executable, "-m", "search.bounded.run", "--out", str(first_path)],
                cwd=REPOSITORY_ROOT,
                env=env,
                check=True,
                capture_output=True,
                text=True,
            )
            env["PYTHONHASHSEED"] = "999"
            subprocess.run(
                [sys.executable, "-m", "search.bounded.run", "--out", str(second_path)],
                cwd=REPOSITORY_ROOT,
                env=env,
                check=True,
                capture_output=True,
                text=True,
            )
            self.assertEqual(first_path.read_bytes(), second_path.read_bytes())

    def test_manifest_is_immutable_and_fit_penalizes_extra_output(self) -> None:
        source = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        manifest = ProblemManifest.from_mapping(source)
        before = evaluate(manifest, "compositional", ("A",)).output
        source["landscapes"]["compositional"]["chunks"]["A"] = "00"
        self.assertEqual(evaluate(manifest, "compositional", ("A",)).output, before)
        with self.assertRaises(TypeError):
            manifest.raw["landscapes"]["compositional"]["chunks"]["A"] = "00"

        extra_raw = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        extra_raw["target"] = "10"
        extra_raw["maxCoordinateTokens"] = 2
        extra_raw["landscapes"]["opaque"] = {
            "type": "exact_lookup",
            "witness": ["A"],
            "fallback": "00",
        }
        extra_manifest = ProblemManifest.from_mapping(extra_raw)
        extra = evaluate(extra_manifest, "compositional", ("A", "B"))
        self.assertFalse(extra.exact)
        self.assertLess(extra.fit, 1.0)

    def test_smaller_valid_manifest_uses_a_derived_matched_budget(self) -> None:
        raw = {
            "schemaVersion": "bounded-coordinate-problem/v0",
            "id": "two-token-control-v0",
            "alphabet": ["A", "B"],
            "target": "01",
            "maxCoordinateTokens": 2,
            "cost": {"unit": "coordinate_token", "formula": "len(tokens)"},
            "fit": {
                "id": "aligned_exact_bit_matches_v1",
                "denominator": "max_target_output_length",
                "missingOrExtraPositionsMismatch": True,
            },
            "landscapes": {
                "compositional": {"type": "chunk_concat", "chunks": {"A": "0", "B": "1"}},
                "opaque": {"type": "exact_lookup", "witness": ["A", "B"], "fallback": "00"},
            },
        }
        manifest = ProblemManifest.from_mapping(raw)
        receipt = build_receipt(manifest)
        self.assertEqual(receipt["runPolicy"]["matchedEvaluationBudget"], 4)
        self.assertEqual(verify_receipt_data(manifest, receipt), [])

    def test_domain_guard_fails_before_exponential_enumeration(self) -> None:
        raw = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        raw["maxCoordinateTokens"] = 10
        manifest = ProblemManifest.from_mapping(raw)
        with self.assertRaisesRegex(ValueError, "exceeding the explicit limit"):
            build_receipt(manifest, max_candidate_count=1_000)

    def test_generated_lean_problem_matches_the_manifest(self) -> None:
        generated = BOUNDED_ROOT / "lean" / "BoundedCoordinate" / "GeneratedProblem.lean"
        self.assertEqual(generated.read_text(encoding="utf-8"), render_problem(self.manifest))

    def test_checked_in_results_match_fresh_reconstruction(self) -> None:
        receipt = json.loads(RECEIPT_PATH.read_text(encoding="utf-8"))
        self.assertEqual(receipt, build_receipt(self.manifest))
        self.assertEqual(sha256_file(RECEIPT_PATH), EXPECTED_RECEIPT_FILE_SHA256)
        verification = json.loads(VERIFICATION_PATH.read_text(encoding="utf-8"))
        self.assertEqual(
            verification,
            build_verification(
                self.manifest,
                receipt,
                receipt_file_sha256=sha256_file(RECEIPT_PATH),
            ),
        )
        lean_verification = json.loads(
            LEAN_VERIFICATION_PATH.read_text(encoding="utf-8")
        )
        self.assertEqual(
            lean_verification,
            expected_lean_receipt(self.manifest, lean_version="4.34.1"),
        )

    def test_verifier_rejects_measurement_lineage_and_manifest_mutations(self) -> None:
        receipt = build_receipt(self.manifest)
        mutations = []

        wrong_length = copy.deepcopy(receipt)
        wrong_length["candidateArchive"][0]["length"] = 99
        mutations.append(wrong_length)

        wrong_fit = copy.deepcopy(receipt)
        wrong_fit["candidateArchive"][7]["fit"] = 1.0
        mutations.append(wrong_fit)

        wrong_lineage = copy.deepcopy(receipt)
        beam = next(run for run in wrong_lineage["searchRuns"] if run["lineage"])
        beam["lineage"][0]["parentCoordinate"] = ["forged"]
        mutations.append(wrong_lineage)

        wrong_manifest = copy.deepcopy(receipt)
        wrong_manifest["manifestContentSha256"] = "0" * 64
        mutations.append(wrong_manifest)

        for mutation in mutations:
            with self.subTest(mutated_fields=list(mutation)):
                self.assertTrue(verify_receipt_data(self.manifest, mutation))


if __name__ == "__main__":
    unittest.main()
