from __future__ import annotations

import copy
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from dataclasses import FrozenInstanceError, replace
from fractions import Fraction
from pathlib import Path
from unittest import mock

from search.bounded.compiler import (
    CoordinateCompiler,
    check_fc02_curve_transfer,
    check_fc03_composition,
    check_fc04_zero_slack_threshold_sandwich,
    compiler_witness_transfer,
    compose_compilers,
    parse_manifest_compilers,
)
from search.bounded.finite_theory import (
    MAX_THEORY_SCALAR,
    EncodingSpec,
    FiniteSystem,
    TheoryManifest,
    check_ft01_threshold_duality,
    check_ft02_structure_monotonicity,
    check_ft03_threshold_monotonicity,
    check_ft04_two_part_identity,
    check_ft05_archive_upper_bound,
    check_ft06_append_only_archive_monotonicity,
    check_ft07_suite_subset_implication,
    check_ft08_pareto_soundness,
    check_ft09_pareto_completeness,
    is_prefix_free,
    kraft_sum,
    pareto_frontier,
    sha256_json,
    structure,
    threshold,
)


MANIFEST_PATH = (
    Path(__file__).resolve().parents[1]
    / "bounded"
    / "theory"
    / "manifest.json"
)
REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
STATEMENT_MAP_PATH = (
    REPOSITORY_ROOT
    / "search"
    / "bounded"
    / "theory"
    / "statement-map.json"
)
RECEIPT_PATH = (
    REPOSITORY_ROOT
    / "search"
    / "bounded"
    / "theory"
    / "results"
    / "receipt.json"
)


def raw_manifest() -> dict[str, object]:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def rehash(raw: dict[str, object]) -> None:
    systems = raw["systems"]
    assert isinstance(systems, list)
    system_digests: dict[str, str] = {}
    for system in systems:
        assert isinstance(system, dict)
        payload = {key: value for key, value in system.items() if key != "contentSha256"}
        system["contentSha256"] = sha256_json(payload)
        system_digests[str(system["id"])] = str(system["contentSha256"])
    compilers = raw["compilers"]
    assert isinstance(compilers, list)
    for compiler in compilers:
        assert isinstance(compiler, dict)
        compiler["sourceSystemContentSha256"] = system_digests[
            str(compiler["sourceSystemId"])
        ]
        compiler["destinationSystemContentSha256"] = system_digests[
            str(compiler["destinationSystemId"])
        ]
        payload = {
            key: value for key, value in compiler.items() if key != "contentSha256"
        }
        compiler["contentSha256"] = sha256_json(payload)


class FiniteTheoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.manifest = TheoryManifest.from_path(MANIFEST_PATH)
        cls.systems = {system.id: system for system in cls.manifest.systems}
        cls.compilers = parse_manifest_compilers(
            cls.manifest.compiler_records,
            cls.systems,
        )
        cls.forward, cls.reverse = cls.compilers
        cls.source = cls.systems["source-v0"]
        cls.destination = cls.systems["destination-v0"]

    def test_fixture_has_exact_prefix_code_and_cost_invariants(self) -> None:
        self.assertEqual(self.manifest.targets, ("alpha", "beta"))
        for system in self.manifest.systems:
            codes = [point.code_bits for point in system.coordinates]
            self.assertTrue(is_prefix_free(codes))
            self.assertLessEqual(kraft_sum(codes), Fraction(1, 1))
            self.assertEqual(len(codes), len(set(codes)))
            self.assertEqual(
                system.content_sha256,
                system.declared_content_sha256,
            )
            for point in system.coordinates:
                self.assertEqual(point.charged_bit_cost, len(point.code_bits))
        raw_short = self.destination.coordinate("d-0")
        raw_long = self.destination.coordinate("d-00")
        self.assertLess(len(raw_short.payload_bits), len(raw_long.payload_bits))
        self.assertGreater(raw_short.charged_bit_cost, raw_long.charged_bit_cost)
        self.assertEqual(kraft_sum(["0", "10", "11"]), Fraction(1, 1))
        self.assertGreater(kraft_sum(["0", "1", "00"]), Fraction(1, 1))

    def test_loaded_objects_are_immutable(self) -> None:
        with self.assertRaises(FrozenInstanceError):
            self.source.id = "mutated"  # type: ignore[misc]
        with self.assertRaises(FrozenInstanceError):
            self.source.coordinates[0].charged_bit_cost = 0  # type: ignore[misc]
        with self.assertRaises(FrozenInstanceError):
            self.forward.cost_overhead_bits = 0  # type: ignore[misc]

    def test_ft01_through_ft04_hold_for_every_system_and_target(self) -> None:
        for system in self.manifest.systems:
            for target in self.manifest.targets:
                with self.subTest(system=system.id, target=target):
                    self.assertTrue(check_ft01_threshold_duality(system, target))
                    self.assertTrue(check_ft02_structure_monotonicity(system, target))
                    self.assertTrue(check_ft03_threshold_monotonicity(system, target))
                    self.assertTrue(check_ft04_two_part_identity(system, target))

    def test_ft05_and_ft06_cover_empty_and_nested_archives(self) -> None:
        empty = self.manifest.archive("source-empty")
        first = self.manifest.archive("source-first")
        later = self.manifest.archive("source-later")
        complete = self.manifest.archive("source-complete")
        for target in self.manifest.targets:
            self.assertTrue(check_ft05_archive_upper_bound(self.source, empty, target))
            self.assertTrue(check_ft05_archive_upper_bound(self.source, later, target))
            self.assertTrue(
                check_ft06_append_only_archive_monotonicity(
                    self.source,
                    empty,
                    first,
                    target,
                )
            )
            self.assertTrue(
                check_ft06_append_only_archive_monotonicity(
                    self.source,
                    later,
                    complete,
                    target,
                )
            )
        with self.assertRaisesRegex(ValueError, "append-only"):
            check_ft06_append_only_archive_monotonicity(
                self.source,
                later,
                first,
                "alpha",
            )

    def test_ft07_is_one_way_conjunctive_suite_inclusion(self) -> None:
        basic = self.manifest.suite("basic")
        strict = self.manifest.suite("strict")
        self.assertTrue(
            check_ft07_suite_subset_implication(
                strict,
                basic,
                self.manifest.verification_outcomes,
            )
        )
        self.assertFalse(
            all(
                not set(basic.check_ids).issubset(outcome)
                or set(strict.check_ids).issubset(outcome)
                for outcome in self.manifest.verification_outcomes
            )
        )
        with self.assertRaisesRegex(ValueError, "not a subset"):
            check_ft07_suite_subset_implication(
                basic,
                strict,
                self.manifest.verification_outcomes,
            )

    def test_ft08_and_ft09_preserve_first_duplicate_representative(self) -> None:
        frontier = pareto_frontier(self.source.coordinates)
        frontier_ids = [point.id for point in frontier]
        self.assertIn("s-0", frontier_ids)
        self.assertNotIn("s-1", frontier_ids)
        self.assertIs(frontier[frontier_ids.index("s-0")], self.source.coordinate("s-0"))
        self.assertTrue(check_ft08_pareto_soundness(self.source.coordinates))
        self.assertTrue(check_ft09_pareto_completeness(self.source.coordinates))
        self.assertEqual(pareto_frontier(()), ())

    def test_fc01_through_fc04_hold_and_composition_is_exact(self) -> None:
        for target in self.manifest.targets:
            witness = compiler_witness_transfer(
                self.forward,
                self.source,
                self.destination,
                "s-0",
                target,
            )
            self.assertEqual(witness.id, "d-0")
        self.assertTrue(
            check_fc02_curve_transfer(
                self.forward,
                self.source,
                self.destination,
            )
        )
        self.assertTrue(
            check_fc02_curve_transfer(
                self.reverse,
                self.destination,
                self.source,
            )
        )
        self.assertTrue(
            check_fc03_composition(
                self.forward,
                self.reverse,
                self.source,
                self.destination,
                self.source,
            )
        )
        identity = compose_compilers(
            self.forward,
            self.reverse,
            self.source,
            self.destination,
            self.source,
            compiler_id="source-round-trip",
        )
        self.assertEqual(dict(identity.mapping), {point.id: point.id for point in self.source.coordinates})
        self.assertEqual(identity.cost_overhead_bits, 2)
        self.assertEqual(identity.residual_slack, 0)
        self.assertEqual(identity.declared_content_sha256, identity.content_sha256)
        self.assertTrue(
            check_fc04_zero_slack_threshold_sandwich(
                self.forward,
                self.reverse,
                self.source,
                self.destination,
            )
        )
        positive_slack_draft = replace(
            self.forward,
            residual_slack=1,
            declared_content_sha256="",
        )
        positive_slack = replace(
            positive_slack_draft,
            declared_content_sha256=positive_slack_draft.content_sha256,
        )
        with self.assertRaisesRegex(ValueError, "zero residual slack"):
            check_fc04_zero_slack_threshold_sandwich(
                positive_slack,
                self.reverse,
                self.source,
                self.destination,
            )

    def test_identity_and_positive_slack_compiler_boundaries(self) -> None:
        identity_mapping = tuple(
            (point.id, point.id) for point in self.source.coordinates
        )
        identity_draft = CoordinateCompiler(
            id="source-identity",
            source_system_id=self.source.id,
            destination_system_id=self.source.id,
            source_system_content_sha256=self.source.content_sha256,
            destination_system_content_sha256=self.source.content_sha256,
            cost_overhead_bits=0,
            residual_slack=0,
            mapping=identity_mapping,
            declared_content_sha256="",
        )
        identity = replace(
            identity_draft,
            declared_content_sha256=identity_draft.content_sha256,
        )
        identity.validate(self.source, self.source)
        self.assertTrue(
            check_fc02_curve_transfer(identity, self.source, self.source)
        )
        self.assertTrue(
            check_fc03_composition(
                identity,
                identity,
                self.source,
                self.source,
                self.source,
            )
        )

        positive_slack_draft = replace(
            self.forward,
            id="source-to-destination-positive-slack",
            residual_slack=1,
            declared_content_sha256="",
        )
        positive_slack = replace(
            positive_slack_draft,
            declared_content_sha256=positive_slack_draft.content_sha256,
        )
        positive_slack.validate(self.source, self.destination)
        self.assertTrue(
            check_fc02_curve_transfer(
                positive_slack,
                self.source,
                self.destination,
            )
        )

    def test_empty_feasible_zero_budget_and_singleton_boundaries(self) -> None:
        self.assertIsNone(structure(self.source.coordinates, "alpha", 0))
        self.assertEqual(threshold(self.source.coordinates, "alpha", 0), 6)
        self.assertIsNone(structure((), "alpha", 0))
        self.assertIsNone(threshold((), "alpha", 0))
        raw = raw_manifest()
        source_raw = copy.deepcopy(raw["systems"][0])
        assert isinstance(source_raw, dict)
        source_raw["coordinates"] = [source_raw["coordinates"][0]]
        source_raw["contentSha256"] = sha256_json(
            {key: value for key, value in source_raw.items() if key != "contentSha256"}
        )
        singleton = FiniteSystem.from_mapping(
            source_raw,
            targets=self.manifest.targets,
            objective_names=self.manifest.objective_names,
            path="singleton",
        )
        for target in self.manifest.targets:
            self.assertTrue(check_ft01_threshold_duality(singleton, target))
            self.assertTrue(check_ft02_structure_monotonicity(singleton, target))
            self.assertTrue(check_ft03_threshold_monotonicity(singleton, target))
            self.assertTrue(check_ft04_two_part_identity(singleton, target))

    def test_computed_query_naturals_can_exceed_manifest_scalar_cap(self) -> None:
        beyond_manifest_cap = MAX_THEORY_SCALAR + 1
        self.assertEqual(
            structure(self.source.coordinates, "alpha", beyond_manifest_cap),
            0,
        )
        self.assertEqual(
            threshold(
                self.source.coordinates,
                "alpha",
                beyond_manifest_cap,
            ),
            4,
        )
        for invalid in (-1, 1.0, True):
            with self.subTest(invalid=invalid):
                for query in (structure, threshold):
                    with self.subTest(query=query.__name__):
                        with self.assertRaisesRegex(
                            ValueError,
                            "non-negative exact integer",
                        ):
                            query(self.source.coordinates, "alpha", invalid)

        oversized_manifest = raw_manifest()
        oversized_point = oversized_manifest["systems"][0]["coordinates"][0]
        oversized_point["residuals"]["alpha"] = beyond_manifest_cap
        oversized_point["objectives"]["alpha_residual"] = beyond_manifest_cap
        rehash(oversized_manifest)
        with self.assertRaisesRegex(ValueError, "scalar limit"):
            TheoryManifest.from_mapping(oversized_manifest)

        adjusted_draft = replace(
            self.forward,
            id="source-to-destination-large-adjustment",
            cost_overhead_bits=MAX_THEORY_SCALAR,
            residual_slack=MAX_THEORY_SCALAR,
            declared_content_sha256="",
        )
        adjusted = replace(
            adjusted_draft,
            declared_content_sha256=adjusted_draft.content_sha256,
        )
        self.assertTrue(
            check_fc02_curve_transfer(
                adjusted,
                self.source,
                self.destination,
            )
        )

    def test_system_level_prefix_and_rendering_collisions_are_reachable(self) -> None:
        prefix_collision = raw_manifest()
        prefix_source = prefix_collision["systems"][0]
        prefix_point = prefix_source["coordinates"][1]
        prefix_point["codeBits"] = "00000"
        rehash(prefix_collision)
        original_encode = EncodingSpec.encode

        def encode_with_collision(
            encoding: EncodingSpec,
            role: str,
            payload_bits: str,
        ) -> str:
            if role == "source" and payload_bits == "0":
                return "00000"
            return original_encode(encoding, role, payload_bits)

        with mock.patch.object(
            EncodingSpec,
            "encode",
            autospec=True,
            side_effect=encode_with_collision,
        ):
            with self.assertRaisesRegex(ValueError, "not prefix-free"):
                TheoryManifest.from_mapping(prefix_collision)

        rendering_collision = raw_manifest()
        rendering_source = rendering_collision["systems"][0]
        rendering_point = rendering_source["coordinates"][1]
        rendering_point["rendering"] = "source:"
        rehash(rendering_collision)
        original_render = EncodingSpec.render

        def render_with_collision(
            encoding: EncodingSpec,
            role: str,
            payload_bits: str,
        ) -> str:
            if role == "source" and payload_bits == "0":
                return "source:"
            return original_render(encoding, role, payload_bits)

        with mock.patch.object(
            EncodingSpec,
            "render",
            autospec=True,
            side_effect=render_with_collision,
        ):
            with self.assertRaisesRegex(
                ValueError,
                "lossy duplicate renderings",
            ):
                TheoryManifest.from_mapping(rendering_collision)

    def test_corrupt_coordinates_fail_closed(self) -> None:
        mutations = [
            (
                "incorrect charged cost",
                lambda point, system: (
                    point.update({"chargedBitCost": 4}),
                    point["objectives"].update({"charged_bit_cost": 4}),
                ),
            ),
            (
                "float residual",
                lambda point, system: (
                    point["residuals"].update({"alpha": 1.5}),
                    point["objectives"].update({"alpha_residual": 1.5}),
                ),
            ),
            (
                "negative residual",
                lambda point, system: (
                    point["residuals"].update({"alpha": -1}),
                    point["objectives"].update({"alpha_residual": -1}),
                ),
            ),
            (
                "incomplete target table",
                lambda point, system: point["residuals"].pop("beta"),
            ),
            (
                "duplicate ID",
                lambda point, system: point.update({"id": "s-empty"}),
            ),
            (
                "uncharged scaffold",
                lambda point, system: (
                    point.update({"codeBits": "000100", "chargedBitCost": 6}),
                    point["objectives"].update({"charged_bit_cost": 6}),
                ),
            ),
        ]
        for label, mutate in mutations:
            with self.subTest(label=label):
                raw = raw_manifest()
                source = raw["systems"][0]
                assert isinstance(source, dict)
                point = source["coordinates"][1]
                assert isinstance(point, dict)
                mutate(point, source)
                rehash(raw)
                with self.assertRaises(ValueError):
                    TheoryManifest.from_mapping(raw)

    def test_corrupt_system_tables_and_encoding_fail_closed(self) -> None:
        cases = []
        duplicate_system = raw_manifest()
        duplicate_system["systems"][1]["id"] = "source-v0"
        for system in duplicate_system["systems"]:
            system["contentSha256"] = sha256_json(
                {
                    key: value
                    for key, value in system.items()
                    if key != "contentSha256"
                }
            )
        cases.append(duplicate_system)

        role_prefix = raw_manifest()
        role_prefix["systems"][1]["encoding"]["roleTags"]["compiled"] = "00"
        rehash(role_prefix)
        cases.append(role_prefix)

        unknown_outcome = raw_manifest()
        unknown_outcome["verificationOutcomes"].append(["invented"])
        rehash(unknown_outcome)
        cases.append(unknown_outcome)

        stale_digest = raw_manifest()
        stale_digest["systems"][0]["coordinates"][0]["residuals"]["alpha"] = 5
        cases.append(stale_digest)

        for raw in cases:
            with self.subTest(case=cases.index(raw)):
                with self.assertRaises(ValueError):
                    TheoryManifest.from_mapping(raw)

    def test_corrupt_compilers_fail_closed(self) -> None:
        mutations = [
            lambda compiler: compiler["mapping"].pop("s-0"),
            lambda compiler: compiler["mapping"].update({"s-0": "missing"}),
            lambda compiler: compiler["mapping"].update({"s-0": {"alpha": "d-0"}}),
            lambda compiler: compiler.update({"costOverheadBits": 0}),
            lambda compiler: compiler["mapping"].update({"s-0": "d-empty"}),
        ]
        for mutate in mutations:
            with self.subTest(mutation=mutations.index(mutate)):
                raw = raw_manifest()
                compiler = raw["compilers"][0]
                mutate(compiler)
                rehash(raw)
                manifest = TheoryManifest.from_mapping(raw)
                systems = {system.id: system for system in manifest.systems}
                with self.assertRaises(ValueError):
                    parse_manifest_compilers(manifest.compiler_records, systems)

    def test_strict_loader_rejects_duplicate_keys_and_nonfinite_numbers(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            duplicate_path = Path(temp_dir) / "duplicate.json"
            duplicate_path.write_text('{"schemaVersion":"x","schemaVersion":"y"}', encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "duplicate JSON object key"):
                TheoryManifest.from_path(duplicate_path)
            nonfinite_path = Path(temp_dir) / "nonfinite.json"
            nonfinite_path.write_text('{"value":NaN}', encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "non-finite JSON number"):
                TheoryManifest.from_path(nonfinite_path)

    def test_independent_verifier_reconstructs_the_checked_receipt(self) -> None:
        from search.bounded import verify_theory

        raw_manifest = verify_theory.strict_json(MANIFEST_PATH)
        manifest = verify_theory.parse_manifest(raw_manifest)
        raw_statement_map = verify_theory.strict_json(STATEMENT_MAP_PATH)
        statement_map = verify_theory.parse_statement_map(raw_statement_map)
        expected = verify_theory.build_expected_receipt(
            raw_manifest=raw_manifest,
            manifest=manifest,
            manifest_path=MANIFEST_PATH,
            raw_statement_map=raw_statement_map,
            statement_map=statement_map,
            statement_map_path=STATEMENT_MAP_PATH,
            repository_root=REPOSITORY_ROOT,
        )
        self.assertEqual(verify_theory.strict_json(RECEIPT_PATH), expected)
        self.assertEqual(
            verify_theory.sha256_file(STATEMENT_MAP_PATH),
            verify_theory.EXPECTED_STATEMENT_MAP_FILE_SHA256,
        )

    def test_independent_verifier_rejects_map_and_receipt_mutations(self) -> None:
        def run_verifier(
            *,
            statement_map: Path = STATEMENT_MAP_PATH,
            receipt: Path = RECEIPT_PATH,
            output: Path,
        ) -> subprocess.CompletedProcess[str]:
            return subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "search.bounded.verify_theory",
                    "--no-lean",
                    "--manifest",
                    str(MANIFEST_PATH),
                    "--statement-map",
                    str(statement_map),
                    "--receipt",
                    str(receipt),
                    "--out",
                    str(output),
                ],
                cwd=REPOSITORY_ROOT,
                check=False,
                capture_output=True,
                text=True,
            )

        with tempfile.TemporaryDirectory() as temp_dir:
            temporary = Path(temp_dir)
            mutated_map = json.loads(STATEMENT_MAP_PATH.read_text(encoding="utf-8"))
            mutated_map["statements"][0]["claim"] += " Mutated."
            mutated_map_path = temporary / "statement-map.json"
            mutated_map_path.write_text(
                json.dumps(mutated_map, sort_keys=True, indent=2) + "\n",
                encoding="utf-8",
            )
            map_output = temporary / "map-verification.json"
            map_result = run_verifier(
                statement_map=mutated_map_path,
                output=map_output,
            )
            self.assertNotEqual(map_result.returncode, 0)
            self.assertFalse(json.loads(map_output.read_text())["verified"])

            mutated_receipt = json.loads(RECEIPT_PATH.read_text(encoding="utf-8"))
            mutated_receipt["systemEvidence"][0]["pareto"]["candidateIds"][0] = (
                "invented-candidate"
            )
            mutated_receipt_path = temporary / "receipt.json"
            mutated_receipt_path.write_text(
                json.dumps(mutated_receipt, sort_keys=True, indent=2) + "\n",
                encoding="utf-8",
            )
            receipt_output = temporary / "receipt-verification.json"
            receipt_result = run_verifier(
                receipt=mutated_receipt_path,
                output=receipt_output,
            )
            self.assertNotEqual(receipt_result.returncode, 0)
            receipt_verification = json.loads(receipt_output.read_text())
            self.assertFalse(receipt_verification["verified"])
            self.assertIn(
                "receipt bytes differ from independent deterministic reconstruction",
                receipt_verification["errors"],
            )

            typed_receipt = json.loads(RECEIPT_PATH.read_text(encoding="utf-8"))
            typed_receipt["scope"]["finiteExactIntegersOnly"] = 1
            typed_receipt_path = temporary / "typed-receipt.json"
            typed_receipt_path.write_text(
                json.dumps(typed_receipt, sort_keys=True, indent=2) + "\n",
                encoding="utf-8",
            )
            typed_output = temporary / "typed-verification.json"
            typed_result = run_verifier(
                receipt=typed_receipt_path,
                output=typed_output,
            )
            self.assertNotEqual(typed_result.returncode, 0)
            self.assertFalse(json.loads(typed_output.read_text())["verified"])

            float_receipt_path = temporary / "float-receipt.json"
            float_receipt_path.write_text(
                RECEIPT_PATH.read_text(encoding="utf-8").replace(
                    '"finiteExactIntegersOnly": true',
                    '"finiteExactIntegersOnly": 1.0',
                ),
                encoding="utf-8",
            )
            float_output = temporary / "float-verification.json"
            float_result = run_verifier(
                receipt=float_receipt_path,
                output=float_output,
            )
            self.assertNotEqual(float_result.returncode, 0)
            self.assertIn(
                "floating-point JSON number is forbidden",
                json.loads(float_output.read_text())["errors"][0],
            )

    def test_independent_protected_baseline_rejects_symlinks(self) -> None:
        from search.bounded import verify_theory

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            target = root / "target.txt"
            target.write_bytes(b"protected")
            link = root / "protected.txt"
            link.symlink_to(target)
            expected = hashlib.sha256(b"protected").hexdigest()
            with mock.patch.dict(
                verify_theory.PROTECTED_FILES,
                {"protected.txt": expected},
                clear=True,
            ):
                with self.assertRaisesRegex(ValueError, "non-symlink"):
                    verify_theory.protected_baseline(root)

    def test_axiom_parser_accepts_wrapping_but_rejects_truncation_and_duplicates(
        self,
    ) -> None:
        from search.bounded.verify_theory import parse_axiom_audit_output

        names = ("Example.long_theorem", "Example.kernel_theorem")
        wrapped = (
            "'Example.long_theorem' depends on axioms: [propext,\n"
            " Classical.choice,\n"
            " Quot.sound]\n"
            "'Example.kernel_theorem' does not depend on any axioms\n"
        )
        self.assertEqual(
            parse_axiom_audit_output(wrapped, names),
            {
                "Example.long_theorem": (
                    "Classical.choice",
                    "Quot.sound",
                    "propext",
                ),
                "Example.kernel_theorem": (),
            },
        )
        with self.assertRaisesRegex(ValueError, "truncated"):
            parse_axiom_audit_output(
                "'Example.long_theorem' depends on axioms: [propext,\n",
                ("Example.long_theorem",),
            )
        with self.assertRaisesRegex(ValueError, "duplicate"):
            parse_axiom_audit_output(wrapped + wrapped, names)

    def test_public_theorem_inventory_detects_attributes_and_protected_theorems(
        self,
    ) -> None:
        from search.bounded.verify_theory import PUBLIC_THEOREM_PATTERN

        source = (
            "@[simp] protected theorem visible_one : True := by trivial\n"
            "noncomputable lemma visible_two : True := by trivial\n"
            "private theorem hidden : True := by trivial\n"
        )
        self.assertEqual(
            PUBLIC_THEOREM_PATTERN.findall(source),
            ["visible_one", "visible_two"],
        )

    def test_work_budget_rejects_quadratic_suite_expansion(self) -> None:
        from search.bounded import verify_theory

        raw = raw_manifest()
        raw["verifierSuites"] = [
            {"id": f"suite-{index}", "checkIds": []}
            for index in range(101)
        ]
        raw["verificationOutcomes"] = [[]]
        with self.assertRaisesRegex(ValueError, "pair count"):
            TheoryManifest.from_mapping(raw)
        with self.assertRaisesRegex(ValueError, "pair count"):
            verify_theory.parse_manifest(raw)

    def test_failed_lean_run_replaces_stale_success_and_paths_do_not_collide(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temporary = Path(temp_dir)
            python_output = temporary / "verification.json"
            lean_output = temporary / "lean-verification.json"
            lean_output.write_text(
                '{"compiled":true,"stale":true}\n',
                encoding="utf-8",
            )
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "search.bounded.verify_theory",
                    "--lake",
                    str(temporary / "missing-lake"),
                    "--out",
                    str(python_output),
                    "--lean-out",
                    str(lean_output),
                ],
                cwd=REPOSITORY_ROOT,
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(result.returncode, 0)
            lean_failure = json.loads(lean_output.read_text())
            self.assertFalse(lean_failure["compiled"])
            self.assertTrue(lean_failure["errors"])

            lean_output.write_text(
                '{"compiled":true,"stale":true}\n',
                encoding="utf-8",
            )
            mutated_receipt = json.loads(
                RECEIPT_PATH.read_text(encoding="utf-8")
            )
            mutated_receipt["scope"]["finiteExactIntegersOnly"] = 1
            mutated_receipt_path = temporary / "mutated-receipt.json"
            mutated_receipt_path.write_text(
                json.dumps(mutated_receipt, sort_keys=True, indent=2) + "\n",
                encoding="utf-8",
            )
            receipt_failure = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "search.bounded.verify_theory",
                    "--receipt",
                    str(mutated_receipt_path),
                    "--out",
                    str(python_output),
                    "--lean-out",
                    str(lean_output),
                ],
                cwd=REPOSITORY_ROOT,
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(receipt_failure.returncode, 0)
            skipped_lean = json.loads(lean_output.read_text())
            self.assertFalse(skipped_lean["compiled"])
            self.assertTrue(skipped_lean["errors"])

            receipt_before = RECEIPT_PATH.read_bytes()
            collision = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "search.bounded.verify_theory",
                    "--no-lean",
                    "--out",
                    str(RECEIPT_PATH),
                ],
                cwd=REPOSITORY_ROOT,
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(collision.returncode, 2)
            self.assertEqual(RECEIPT_PATH.read_bytes(), receipt_before)


if __name__ == "__main__":
    unittest.main()
