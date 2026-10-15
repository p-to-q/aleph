"""Strict import surface: round trip, provenance, and adversarial tests.

Every bundle here is a fixture built by the deterministic scheduled demo; all
values are simulated by construction and are never model evidence. Import is
read-only: bundle mode replays and re-derives the projection, file mode checks
canonical bytes, schema, and digests, and only a bundle-anchored import is
replay-verified.
"""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from search.engine.archive import materialize
from search.engine.canonical import canonical_bytes, digest, digest_bytes
from search.engine.export_aleph_run import (
    ARTIFACT_REF_SCHEMA_VERSION,
    PROJECTION_RECORD_SCHEMA_VERSION,
)
from search.engine.fixtures.demo import (
    DEMO_SCHEDULED_RUN_ID,
    build_demo_bundle_interrupted,
    build_scheduled_demo_bundle,
)
from search.engine.import_aleph_run import (
    AlephRunImportError,
    import_aleph_run,
)
from search.engine.tests.support import aborted_bundle, fresh_tmpdir, make_demo_bundle
from search.engine.verify import verify_bundle


def scheduled(tmp: Path, name: str = "bundle", **kwargs) -> Path:
    return build_scheduled_demo_bundle(tmp / name, **kwargs)


def export_path(root: Path) -> Path:
    return root / "exports" / "aleph-run.json"


def load_value(root: Path) -> dict:
    return json.loads(export_path(root).read_text(encoding="utf-8"))


def refresh_digest(value: dict) -> None:
    """Recompute artifactRef.projectionDigest for an intentionally mutated value."""
    without_ref = {key: item for key, item in value.items() if key != "artifactRef"}
    value["artifactRef"]["projectionDigest"] = digest(without_ref)


def snapshot_tree(root: Path) -> dict:
    out = {}
    for path in sorted(root.rglob("*")):
        if path.is_file():
            out[str(path.relative_to(root))] = (
                path.stat().st_size,
                digest_bytes(path.read_bytes()),
            )
    return out


class TestRoundTrip(unittest.TestCase):
    def test_file_import_matches_export_and_round_trips_bytes(self) -> None:
        tmp = fresh_tmpdir()
        root = scheduled(tmp)
        shared = tmp / "shared" / "run.json"
        shared.parent.mkdir()
        shared.write_bytes(export_path(root).read_bytes())
        imported = import_aleph_run(shared)
        self.assertEqual(imported.source, "file")
        self.assertEqual(imported.run_id, DEMO_SCHEDULED_RUN_ID)
        self.assertEqual(imported.value, load_value(root))
        self.assertEqual(imported.to_canonical_bytes(), shared.read_bytes())
        self.assertFalse(imported.replay_verified)
        self.assertIsNone(imported.bundle_root)
        self.assertIsNone(imported.projection_record)
        self.assertIsNone(imported.omitted_candidate_ids)
        self.assertEqual(imported.bundle_digest, imported.value["artifactRef"]["bundleDigest"])

    def test_bundle_import_replays_and_carries_the_record(self) -> None:
        tmp = fresh_tmpdir()
        root = scheduled(tmp)
        imported = import_aleph_run(root)
        self.assertEqual(imported.source, "bundle")
        self.assertEqual(imported.run_id, DEMO_SCHEDULED_RUN_ID)
        self.assertTrue(imported.replay_verified)
        self.assertEqual(imported.bundle_root, root)
        self.assertEqual(imported.value, load_value(root))
        self.assertEqual(
            imported.value["artifactRef"]["schemaVersion"], ARTIFACT_REF_SCHEMA_VERSION
        )
        manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(imported.bundle_digest, manifest["streamDigest"])
        record = imported.projection_record
        self.assertEqual(record["schemaVersion"], PROJECTION_RECORD_SCHEMA_VERSION)
        self.assertEqual(record["artifactRef"], imported.value["artifactRef"])
        expected_omitted = tuple(entry["candidateId"] for entry in record["omittedCandidateIds"])
        self.assertEqual(imported.omitted_candidate_ids, expected_omitted)
        self.assertTrue(expected_omitted)  # the unevaluated control stays bundle-only

    def test_bundle_import_works_without_exports_on_disk(self) -> None:
        tmp = fresh_tmpdir()
        root = scheduled(tmp, "no-exports", export=False)
        # The layout pre-creates an empty exports/ dir; the export files are absent.
        self.assertFalse(export_path(root).exists())
        self.assertFalse((root / "exports" / "aleph-run-projection.json").exists())
        imported = import_aleph_run(root)
        self.assertTrue(imported.replay_verified)
        twin = scheduled(tmp, "with-exports")
        self.assertEqual(imported.value, load_value(twin))

    def test_anchored_file_import_becomes_replay_verified(self) -> None:
        tmp = fresh_tmpdir()
        root = scheduled(tmp)
        imported = import_aleph_run(export_path(root), bundle_root=root)
        self.assertEqual(imported.source, "file")
        self.assertTrue(imported.replay_verified)
        self.assertEqual(imported.bundle_root, root)
        self.assertEqual(imported.value, load_value(root))
        self.assertIsNotNone(imported.projection_record)
        self.assertEqual(
            imported.omitted_candidate_ids, import_aleph_run(root).omitted_candidate_ids
        )

    def test_import_is_read_only(self) -> None:
        tmp = fresh_tmpdir()
        root = scheduled(tmp)
        before = snapshot_tree(root)
        import_aleph_run(root)
        import_aleph_run(export_path(root), bundle_root=root)
        import_aleph_run(export_path(root))
        self.assertEqual(snapshot_tree(root), before)


class TestBundleRefusals(unittest.TestCase):
    def test_open_bundle_refused(self) -> None:
        tmp = fresh_tmpdir()
        root = tmp / "open"
        build_demo_bundle_interrupted(root)
        with self.assertRaises(AlephRunImportError) as caught:
            import_aleph_run(root)
        self.assertIn("not completed", str(caught.exception))

    def test_aborted_run_refused_by_the_projection_step(self) -> None:
        tmp = fresh_tmpdir()
        root = aborted_bundle(tmp)
        materialize(root)
        # A materialized aborted run is kernel-legal and verifies clean; the
        # refusal must come from the projection step, not the verifier.
        self.assertTrue(verify_bundle(root, write_verify_json=False).ok)
        with self.assertRaises(AlephRunImportError) as caught:
            import_aleph_run(root)
        message = str(caught.exception)
        self.assertIn("aborted", message)
        self.assertIn("only completed runs are exportable", message)

    def test_pr_a_demo_bundle_refused(self) -> None:
        tmp = fresh_tmpdir()
        root = make_demo_bundle(tmp / "pr-a")
        with self.assertRaises(AlephRunImportError) as caught:
            import_aleph_run(root)
        self.assertIn("cannot re-derive the projection", str(caught.exception))

    def test_tampered_export_file_refused(self) -> None:
        tmp = fresh_tmpdir()
        root = scheduled(tmp)
        path = export_path(root)
        path.write_bytes(path.read_bytes()[:-1])  # drop the trailing newline
        with self.assertRaises(AlephRunImportError) as caught:
            import_aleph_run(root)
        message = str(caught.exception)
        self.assertIn("failed verification", message)
        self.assertIn("differs from the replayed derivation", message)

    def test_tampered_materialized_view_refused(self) -> None:
        tmp = fresh_tmpdir()
        root = scheduled(tmp)
        views = root / "materialized" / "views.json"
        views.write_bytes(views.read_bytes() + b" ")
        with self.assertRaises(AlephRunImportError) as caught:
            import_aleph_run(root)
        self.assertIn("materialized view", str(caught.exception))

    def test_missing_materialized_view_refused(self) -> None:
        tmp = fresh_tmpdir()
        root = scheduled(tmp)
        (root / "materialized" / "views.json").unlink()
        with self.assertRaises(AlephRunImportError) as caught:
            import_aleph_run(root)
        self.assertIn("materialized view is missing", str(caught.exception))

    def test_unknown_bundle_entry_refused(self) -> None:
        tmp = fresh_tmpdir()
        root = scheduled(tmp)
        (root / "stray.txt").write_text("stray\n", encoding="utf-8")
        with self.assertRaises(AlephRunImportError) as caught:
            import_aleph_run(root)
        self.assertIn("unknown entry", str(caught.exception))

    def test_foreign_file_against_bundle_refused(self) -> None:
        tmp = fresh_tmpdir()
        root_a = scheduled(tmp, "a")
        root_b = scheduled(tmp, "b", run_id="aleph-demo-scheduled-002")
        with self.assertRaises(AlephRunImportError) as caught:
            import_aleph_run(export_path(root_a), bundle_root=root_b)
        self.assertIn("not the same run", str(caught.exception))

    def test_altered_file_against_bundle_refused(self) -> None:
        tmp = fresh_tmpdir()
        root = scheduled(tmp)
        value = load_value(root)
        value["candidates"][0]["label"] = "Altered"
        refresh_digest(value)
        scratch = tmp / "altered.json"
        scratch.write_bytes(canonical_bytes(value) + b"\n")
        with self.assertRaises(AlephRunImportError) as caught:
            import_aleph_run(scratch, bundle_root=root)
        self.assertIn("differs from the projection re-derived", str(caught.exception))

    def test_source_and_bundle_root_together_refused(self) -> None:
        tmp = fresh_tmpdir()
        root = scheduled(tmp)
        with self.assertRaises(AlephRunImportError) as caught:
            import_aleph_run(root, bundle_root=root)
        self.assertIn("exactly one", str(caught.exception))

    def test_missing_source_refused(self) -> None:
        tmp = fresh_tmpdir()
        with self.assertRaises(AlephRunImportError) as caught:
            import_aleph_run(tmp / "missing")
        self.assertIn("neither a file nor a directory", str(caught.exception))


class TestFileStrictness(unittest.TestCase):
    """Adversarial single-file variants; each must fail closed with a clear reason."""

    def setUp(self) -> None:
        self.tmp = fresh_tmpdir()
        self.root = scheduled(self.tmp)
        self.original = export_path(self.root).read_bytes()
        self.scratch = self.tmp / "variants" / "run.json"
        self.scratch.parent.mkdir()

    def import_variant(self, payload: bytes) -> str:
        self.scratch.write_bytes(payload)
        with self.assertRaises(AlephRunImportError) as caught:
            import_aleph_run(self.scratch)
        return str(caught.exception)

    def import_value(self, value: dict) -> str:
        return self.import_variant(canonical_bytes(value) + b"\n")

    def test_non_canonical_bytes_refused(self) -> None:
        value = load_value(self.root)
        reordered = json.dumps(
            dict(reversed(list(value.items()))), ensure_ascii=False, separators=(",", ":")
        ).encode("utf-8") + b"\n"
        cases = [
            (
                "pretty-printed",
                json.dumps(value, indent=2).encode("utf-8") + b"\n",
                "byte-identical",
            ),
            ("missing newline", canonical_bytes(value), "trailing newline"),
            ("trailing space", self.original + b" ", "byte-identical"),
            ("reordered keys", reordered, "byte-identical"),
        ]
        for name, payload, fragment in cases:
            with self.subTest(name):
                self.assertIn(fragment, self.import_variant(payload))

    def test_parse_defects_refused(self) -> None:
        cases = [
            ("empty file", b"", "not valid strict JSON"),
            ("duplicate key", b'{"id": "a", "id": "b"}\n', "duplicate object key 'id'"),
            ("NaN literal", b'{"id": NaN}\n', "non-finite"),
            ("invalid UTF-8", b"\xff\xfe{}\n", "UTF-8"),
            ("BOM", b"\xef\xbb\xbf" + self.original, "byte-order mark"),
            ("not an object", b"[1, 2]\n", "JSON object"),
        ]
        for name, payload, fragment in cases:
            with self.subTest(name):
                self.assertIn(fragment, self.import_variant(payload))

    def test_unwritable_canonical_values_refused(self) -> None:
        tokens = load_value(self.root)["candidates"][0]["tokens"]
        big = self.original.replace(
            f'"tokens":{tokens}'.encode("utf-8"), f'"tokens":{2**60}'.encode("utf-8"), 1
        )
        self.assertIn("I-JSON", self.import_variant(big))
        surrogate = load_value(self.root)
        surrogate["target"]["text"] = "bad \ud800 text"
        payload = json.dumps(surrogate, ensure_ascii=True).encode("ascii") + b"\n"
        self.assertIn("surrogate", self.import_variant(payload))

    def test_decomposed_text_refused(self) -> None:
        # The canonical profile writes NFC; NFD bytes are not the canonical form
        # of any value, so a decomposed file fails closed.
        value = load_value(self.root)
        value["candidates"][0]["prompt"] = value["candidates"][0]["prompt"] + "caf\u00e9"
        refresh_digest(value)
        nfc_payload = canonical_bytes(value) + b"\n"
        nfd_payload = nfc_payload.replace("caf\u00e9".encode("utf-8"), "cafe\u0301".encode("utf-8"))
        self.assertNotEqual(nfc_payload, nfd_payload)
        self.assertIn("byte-identical", self.import_variant(nfd_payload))

    def test_non_canonical_number_form_refused(self) -> None:
        tokens = load_value(self.root)["candidates"][0]["tokens"]
        payload = self.original.replace(
            f'"tokens":{tokens}'.encode("utf-8"), f'"tokens":{tokens}e0'.encode("utf-8"), 1
        )
        self.assertIn("byte-identical", self.import_variant(payload))

    def test_schema_defects_refused(self) -> None:
        unexpected = load_value(self.root)
        unexpected["extra"] = 1
        refresh_digest(unexpected)
        missing = load_value(self.root)
        del missing["selectedCandidateId"]
        refresh_digest(missing)
        out_of_range = load_value(self.root)
        out_of_range["candidates"][0]["fit"] = 1.5
        refresh_digest(out_of_range)
        wrong_type = load_value(self.root)
        wrong_type["candidates"][0]["fit"] = "high"
        refresh_digest(wrong_type)
        cases = [
            ("unexpected property", unexpected, "unexpected property extra"),
            ("missing property", missing, "missing required property selectedCandidateId"),
            ("out of range", out_of_range, "above maximum"),
            ("wrong type", wrong_type, "expected number"),
        ]
        for name, value, fragment in cases:
            with self.subTest(name):
                self.assertIn(fragment, self.import_value(value))

    def test_stale_or_mangled_digest_refused(self) -> None:
        altered = load_value(self.root)
        altered["candidates"][0]["fit"] = 0.123456
        self.assertIn("projectionDigest does not match", self.import_value(altered))
        mangled = load_value(self.root)
        mangled["artifactRef"]["projectionDigest"] = digest({"x": 1})
        self.assertIn("projectionDigest does not match", self.import_value(mangled))

    def test_artifact_ref_defects_refused(self) -> None:
        missing = load_value(self.root)
        del missing["artifactRef"]
        unknown = load_value(self.root)
        unknown["artifactRef"]["schemaVersion"] = "aleph-artifact-ref/0.9.9"
        foreign = load_value(self.root)
        foreign["artifactRef"]["runId"] = "ghost-run"
        bad_bundle = load_value(self.root)
        bad_bundle["artifactRef"]["bundleDigest"] = "banana"
        bad_projection = load_value(self.root)
        bad_projection["artifactRef"]["projectionDigest"] = "banana"
        cases = [
            ("missing ref", missing, "missing artifactRef"),
            ("unknown version", unknown, "schemaVersion"),
            ("run id mismatch", foreign, "does not match the run id"),
            ("bad bundle digest", bad_bundle, "bundleDigest must be a sha256"),
            ("bad projection digest", bad_projection, "projectionDigest must be a sha256"),
        ]
        for name, value, fragment in cases:
            with self.subTest(name):
                self.assertIn(fragment, self.import_value(value))

    def test_exporter_invariants_refused(self) -> None:
        empty = load_value(self.root)
        empty["candidates"] = []
        empty["config"]["budget"]["candidates"] = 0
        empty["config"]["budget"]["maxPromptTokens"] = 0
        refresh_digest(empty)
        self.assertIn("must not be empty", self.import_value(empty))
        count = load_value(self.root)
        count["config"]["budget"]["candidates"] += 1
        refresh_digest(count)
        self.assertIn("budget.candidates must equal", self.import_value(count))
        tokens = load_value(self.root)
        tokens["config"]["budget"]["maxPromptTokens"] += 1
        refresh_digest(tokens)
        self.assertIn("maxPromptTokens must equal", self.import_value(tokens))
        selected = load_value(self.root)
        selected["selectedCandidateId"] = "ghost-candidate"
        refresh_digest(selected)
        self.assertIn(
            "selectedCandidateId 'ghost-candidate' is not among", self.import_value(selected)
        )


class TestHygiene(unittest.TestCase):
    def test_module_is_stdlib_and_scheduler_free(self) -> None:
        source = (Path(__file__).resolve().parents[1] / "import_aleph_run.py").read_text(
            encoding="utf-8"
        )
        self.assertNotIn("hybrid_pareto", source)
        self.assertNotIn("import mlx", source)
        self.assertNotIn("requests", source)
        self.assertNotIn("datetime", source)


if __name__ == "__main__":
    unittest.main()
