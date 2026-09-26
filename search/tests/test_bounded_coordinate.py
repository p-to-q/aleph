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
from search.bounded.generate_lean import render_frontier, render_problem
from search.bounded.run import archive_jsonl_bytes, build_experiment, build_receipt
from search.bounded.verify import (
    build_verification,
    verify_archive_data,
    verify_receipt_data,
)
from search.bounded.verify_lean import (
    EXPECTED_PUBLIC_THEOREM_AXIOMS,
    expected_lean_receipt,
    parse_axiom_audit_output,
    public_theorem_names,
)


MANIFEST_PATH = BOUNDED_ROOT / "problem.json"
RECEIPT_PATH = BOUNDED_ROOT / "results" / "receipt.json"
ARCHIVE_PATH = BOUNDED_ROOT / "results" / "candidates.jsonl"
VERIFICATION_PATH = BOUNDED_ROOT / "results" / "verification.json"
LEAN_VERIFICATION_PATH = BOUNDED_ROOT / "results" / "lean-verification.json"
EXPECTED_RECEIPT_FILE_SHA256 = "ae4bacf3739d3015cf0c71ccbe7c9da249d29a7ac0514c79173ec23d3c89bc7b"
EXPECTED_ARCHIVE_FILE_SHA256 = "273b5a53eab00a484bf77c71c78fa6eb76f92302492cb0633b6cfeb702b29ebe"


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
        receipt, candidate_archive = build_experiment(self.manifest)
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
                runs[f"{landscape}:random-16-seed-1729"]["logicalAdaptiveRounds"],
                1,
            )

        archive_coordinates = {
            point["id"]: point["coordinate"] for point in candidate_archive
        }
        compositional_random = runs["compositional:random-16-seed-1729"]
        opaque_random = runs["opaque:random-16-seed-1729"]
        self.assertEqual(
            [archive_coordinates[item] for item in compositional_random["evaluationCandidateIds"]],
            [archive_coordinates[item] for item in opaque_random["evaluationCandidateIds"]],
        )

    def test_seeded_receipt_is_byte_stable_and_independently_verifiable(self) -> None:
        first, first_archive = build_experiment(self.manifest)
        second, second_archive = build_experiment(self.manifest)
        first_bytes = json.dumps(first, sort_keys=True, separators=(",", ":"))
        second_bytes = json.dumps(second, sort_keys=True, separators=(",", ":"))
        self.assertEqual(first_bytes, second_bytes)
        self.assertEqual(
            archive_jsonl_bytes(first_archive),
            archive_jsonl_bytes(second_archive),
        )
        self.assertEqual(verify_receipt_data(self.manifest, first), [])
        with tempfile.TemporaryDirectory() as temp_dir:
            first_dir = Path(temp_dir) / "first"
            second_dir = Path(temp_dir) / "second"
            first_dir.mkdir()
            second_dir.mkdir()
            first_path = first_dir / "receipt.json"
            second_path = second_dir / "receipt.json"
            first_archive_path = first_dir / "candidates.jsonl"
            second_archive_path = second_dir / "candidates.jsonl"
            write_json(first_path, first)
            write_json(second_path, second)
            first_archive_path.write_bytes(archive_jsonl_bytes(first_archive))
            second_archive_path.write_bytes(archive_jsonl_bytes(second_archive))
            self.assertEqual(first_path.read_bytes(), second_path.read_bytes())
            self.assertEqual(
                first_archive_path.read_bytes(),
                second_archive_path.read_bytes(),
            )
            self.assertEqual(sha256_file(first_path), sha256_file(second_path))

            env = os.environ.copy()
            env["PYTHONHASHSEED"] = "1"
            subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "search.bounded.run",
                    "--out",
                    str(first_path),
                    "--archive-out",
                    str(first_archive_path),
                ],
                cwd=REPOSITORY_ROOT,
                env=env,
                check=True,
                capture_output=True,
                text=True,
            )
            env["PYTHONHASHSEED"] = "999"
            subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "search.bounded.run",
                    "--out",
                    str(second_path),
                    "--archive-out",
                    str(second_archive_path),
                ],
                cwd=REPOSITORY_ROOT,
                env=env,
                check=True,
                capture_output=True,
                text=True,
            )
            self.assertEqual(first_path.read_bytes(), second_path.read_bytes())
            self.assertEqual(first_archive_path.read_bytes(), second_archive_path.read_bytes())

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
        raw["maxCoordinateTokens"] = 1_000_000_000
        manifest = ProblemManifest.from_mapping(raw)
        with self.assertRaisesRegex(ValueError, "exceeds the explicit limit"):
            build_receipt(manifest, max_candidate_count=1_000)

    def test_generated_lean_problem_matches_the_manifest(self) -> None:
        generated = BOUNDED_ROOT / "lean" / "BoundedCoordinate" / "GeneratedProblem.lean"
        self.assertEqual(generated.read_text(encoding="utf-8"), render_problem(self.manifest))

    def test_generated_lean_frontier_is_bound_to_the_published_artifacts(self) -> None:
        receipt = json.loads(RECEIPT_PATH.read_text(encoding="utf-8"))
        candidate_archive = [
            json.loads(line)
            for line in ARCHIVE_PATH.read_text(encoding="utf-8").splitlines()
            if line
        ]
        generated = (
            BOUNDED_ROOT / "lean" / "BoundedCoordinate" / "GeneratedFrontier.lean"
        )
        self.assertEqual(
            generated.read_text(encoding="utf-8"),
            render_frontier(
                self.manifest,
                receipt,
                candidate_archive,
                receipt_file_sha256=sha256_file(RECEIPT_PATH),
                archive_file_sha256=sha256_file(ARCHIVE_PATH),
            ),
        )

    def test_axiom_audit_inventory_is_complete_and_parseable(self) -> None:
        theorem_names = public_theorem_names()
        lines = []
        for name in theorem_names:
            dependencies = EXPECTED_PUBLIC_THEOREM_AXIOMS[name]
            if dependencies:
                lines.append(
                    f"'{name}' depends on axioms: [{', '.join(dependencies)}]"
                )
            else:
                lines.append(f"'{name}' does not depend on any axioms")
        self.assertEqual(
            parse_axiom_audit_output("\n".join(lines), theorem_names),
            EXPECTED_PUBLIC_THEOREM_AXIOMS,
        )
        with self.assertRaisesRegex(ValueError, "incomplete Lean axiom audit"):
            parse_axiom_audit_output("\n".join(lines[:-1]), theorem_names)

    def test_cli_normalizes_paths_before_enforcing_artifact_containment(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            output_dir = root / "results"
            receipt_argument = output_dir / "uncreated" / ".." / "receipt.json"
            archive_path = output_dir / "candidates.jsonl"
            verification_argument = output_dir / "audit" / ".." / "verification.json"
            subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "search.bounded.run",
                    "--out",
                    str(receipt_argument),
                    "--archive-out",
                    str(archive_path),
                ],
                cwd=REPOSITORY_ROOT,
                check=True,
                capture_output=True,
                text=True,
            )
            subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "search.bounded.verify",
                    "--receipt",
                    str(receipt_argument),
                    "--archive",
                    str(archive_path),
                    "--out",
                    str(verification_argument),
                ],
                cwd=REPOSITORY_ROOT,
                check=True,
                capture_output=True,
                text=True,
            )
            self.assertTrue((output_dir / "receipt.json").is_file())
            self.assertTrue((output_dir / "verification.json").is_file())

            outside = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "search.bounded.run",
                    "--out",
                    str(output_dir / "receipt.json"),
                    "--archive-out",
                    str(root / "outside.jsonl"),
                ],
                cwd=REPOSITORY_ROOT,
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(outside.returncode, 0)
            self.assertIn("must be inside", outside.stderr)

    def test_checked_in_results_match_fresh_reconstruction(self) -> None:
        receipt = json.loads(RECEIPT_PATH.read_text(encoding="utf-8"))
        candidate_archive = [
            json.loads(line)
            for line in ARCHIVE_PATH.read_text(encoding="utf-8").splitlines()
            if line
        ]
        expected_receipt, expected_archive = build_experiment(self.manifest)
        self.assertEqual(receipt, expected_receipt)
        self.assertEqual(candidate_archive, expected_archive)
        self.assertEqual(sha256_file(RECEIPT_PATH), EXPECTED_RECEIPT_FILE_SHA256)
        self.assertEqual(sha256_file(ARCHIVE_PATH), EXPECTED_ARCHIVE_FILE_SHA256)
        verification = json.loads(VERIFICATION_PATH.read_text(encoding="utf-8"))
        self.assertEqual(
            verification,
            build_verification(
                self.manifest,
                receipt,
                candidate_archive,
                receipt_file_sha256=sha256_file(RECEIPT_PATH),
                archive_file_sha256=sha256_file(ARCHIVE_PATH),
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
        receipt, candidate_archive = build_experiment(self.manifest)
        archive_mutations = []

        wrong_length = copy.deepcopy(candidate_archive)
        wrong_length[0]["length"] = 99
        archive_mutations.append(wrong_length)

        wrong_fit = copy.deepcopy(candidate_archive)
        wrong_fit[7]["fit"] = 1.0
        archive_mutations.append(wrong_fit)

        for mutation in archive_mutations:
            with self.subTest(archive_mutation=True):
                self.assertTrue(verify_archive_data(self.manifest, receipt, mutation))

        receipt_mutations = []

        wrong_lineage = copy.deepcopy(receipt)
        beam = next(run for run in wrong_lineage["searchRuns"] if run["lineage"])
        beam["lineage"][0]["parentCoordinate"] = ["forged"]
        receipt_mutations.append(wrong_lineage)

        wrong_manifest = copy.deepcopy(receipt)
        wrong_manifest["manifestContentSha256"] = "0" * 64
        receipt_mutations.append(wrong_manifest)

        for mutation in receipt_mutations:
            with self.subTest(mutated_fields=list(mutation)):
                self.assertTrue(verify_receipt_data(self.manifest, mutation))

    def test_verifier_rejects_archive_byte_hash_mismatch(self) -> None:
        receipt, candidate_archive = build_experiment(self.manifest)
        verification = build_verification(
            self.manifest,
            receipt,
            candidate_archive,
            receipt_file_sha256="0" * 64,
            archive_file_sha256="f" * 64,
        )
        self.assertFalse(verification["verified"])
        self.assertIn(
            "candidate archive bytes do not match the receipt file hash",
            verification["errors"],
        )


if __name__ == "__main__":
    unittest.main()
