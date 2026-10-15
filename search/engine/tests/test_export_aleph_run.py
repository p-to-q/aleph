"""Measurement-lossless AlephRun projection: adversarial exporter tests.

Every bundle here is a fixture built by the deterministic scheduled demo;
all values are simulated by construction and are never model evidence. The
exporter under test projects a verified bundle into the strict
``schemas/aleph-run.schema.json`` shape with a complete source map, and the
verifier attests the exported files by replaying the same projection.
"""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from search.engine.adapters.replay import replay
from search.engine.archive import RunBundle, read_bundle, read_manifest
from search.engine.canonical import canonical_bytes, canonical_json, digest, digest_bytes
from search.engine.contracts import evaluation_receipt
from search.engine.events import Event
from search.engine.fixtures.demo import (
    DEMO_NESTING_RULE,
    DEMO_SCHEDULED_CREATED_AT,
    DEMO_SCHEDULED_RUN_ID,
    DEMO_TARGET,
    ScheduledDemoEvaluationAdapter,
    build_demo_bundle,
    build_demo_bundle_interrupted,
    build_scheduled_demo_bundle,
    demo_target_digest,
    scheduled_demo_config,
    scheduled_demo_confirmation,
    scheduled_demo_manifest,
    scheduled_demo_seeds,
)
from search.engine.hybrid_pareto import run_hybrid_search
from search.engine.tests.support import fresh_tmpdir
from search.engine.verify import verify_bundle

# Imported after the fixture import above so a missing exporter fails these
# tests loudly (test-first: this module does not exist yet).
from search.engine.export_aleph_run import (  # noqa: E402
    ARTIFACT_REF_SCHEMA_VERSION,
    PROJECTION_RECORD_SCHEMA_VERSION,
    ExportError,
    ExportResult,
    ProjectionRecord,
    candidate_label,
    export_aleph_run,
    project_bundle,
    validate_against_schema,
)


def exported(tmp, name="bundle") -> Path:
    root = tmp / name
    build_scheduled_demo_bundle(root)
    return root


def load_projection(root: Path) -> dict:
    return json.loads((root / "exports" / "aleph-run.json").read_text(encoding="utf-8"))


def load_record(root: Path) -> dict:
    return json.loads((root / "exports" / "aleph-run-projection.json").read_text(encoding="utf-8"))


def leaf_paths(value, prefix="/"):
    """Every scalar leaf path of a nested JSON value, sorted."""
    if isinstance(value, dict):
        out = []
        for key in sorted(value):
            out.extend(leaf_paths(value[key], f"{prefix}{key}/"))
        return out
    if isinstance(value, list):
        out = []
        for index, item in enumerate(value):
            out.extend(leaf_paths(item, f"{prefix}{index}/"))
        return out
    return [prefix.rstrip("/")]


def discovery_receipts(root: Path) -> dict:
    """candidate id -> final discovery evaluation receipt, replayed from disk."""
    snapshot = read_bundle(root)
    receipts = {}
    for event in snapshot.events:
        if event.event_type == "evaluation_completed" and event.phase == "discovery":
            receipt = json.loads(snapshot.blobs[event.blob_digests[0]])
            receipts[event.payload["candidateId"]] = receipt
    return receipts


def proposal_receipts(root: Path) -> dict:
    """candidate id -> (blob digest, candidate index) of its proposal receipt."""
    snapshot = read_bundle(root)
    found = {}
    for event in snapshot.events:
        if event.event_type == "proposal_succeeded":
            receipt = json.loads(snapshot.blobs[event.blob_digests[0]])
            for index, candidate in enumerate(receipt["candidates"]):
                found[candidate["candidateId"]] = (event.blob_digests[0], index)
    return found


def aborted_bundle(tmp, name="aborted") -> Path:
    """A minimal closed run aborted before any freeze: kernel-legal, no exports."""
    root = tmp / name
    target = "aborted probe target"
    bundle = RunBundle.create(
        root,
        run_id=f"{name}-001",
        target_digest=digest_bytes(target.encode("utf-8")),
        target_content=target,
        known_metrics=("fit",),
        adapter_digests=(digest({"adapter": "aborted-probe"}),),
        nesting_rule=DEMO_NESTING_RULE,
        scheduler_model="hybrid-pareto-v0",
        model_manifest=scheduled_demo_manifest(),
        run_started_payload={"createdAt": DEMO_SCHEDULED_CREATED_AT},
    )
    bundle.close(status="aborted")
    return root


class TestExportHappyPath(unittest.TestCase):
    def test_export_writes_both_files(self) -> None:
        root = exported(fresh_tmpdir())
        self.assertTrue((root / "exports" / "aleph-run.json").exists())
        self.assertTrue((root / "exports" / "aleph-run-projection.json").exists())

    def test_projection_matches_strict_schema(self) -> None:
        root = exported(fresh_tmpdir())
        projection = load_projection(root)
        self.assertEqual(
            validate_against_schema(
                projection, Path(__file__).resolve().parents[3] / "schemas" / "aleph-run.schema.json"
            ),
            [],
        )

    def test_artifact_ref_digests_are_consistent(self) -> None:
        root = exported(fresh_tmpdir())
        projection = load_projection(root)
        ref = projection["artifactRef"]
        self.assertEqual(ref["schemaVersion"], ARTIFACT_REF_SCHEMA_VERSION)
        self.assertEqual(ref["runId"], DEMO_SCHEDULED_RUN_ID)
        self.assertEqual(ref["bundleDigest"], read_manifest(root).stream_digest)
        without_ref = {key: value for key, value in projection.items() if key != "artifactRef"}
        self.assertEqual(ref["projectionDigest"], digest(without_ref))

    def test_export_then_verify_bundle_still_ok(self) -> None:
        root = exported(fresh_tmpdir())
        report = verify_bundle(root)
        self.assertTrue(report.ok, report.errors)

    def test_export_result_digests_match_files(self) -> None:
        tmp = fresh_tmpdir()
        root = tmp / "bundle"
        result = build_scheduled_demo_bundle(root, export=False)
        result = export_aleph_run(Path(result))
        self.assertIsInstance(result, ExportResult)
        digests = dict(result.digests)
        run_file = (root / "exports" / "aleph-run.json").read_bytes()
        self.assertEqual(digests["aleph-run.json"], digest_bytes(run_file[:-1]))

    def test_export_then_replay_still_ok(self) -> None:
        root = exported(fresh_tmpdir())
        result = replay(root)
        self.assertEqual(result.snapshot.manifest.run_id, DEMO_SCHEDULED_RUN_ID)

    def test_export_is_byte_deterministic(self) -> None:
        first = exported(fresh_tmpdir(), name="first")
        second = exported(fresh_tmpdir(), name="second")
        for name in ("aleph-run.json", "aleph-run-projection.json"):
            self.assertEqual(
                (first / "exports" / name).read_bytes(),
                (second / "exports" / name).read_bytes(),
                name,
            )

    def test_id_created_at_and_target_are_byte_copies(self) -> None:
        root = exported(fresh_tmpdir())
        projection = load_projection(root)
        self.assertEqual(projection["id"], DEMO_SCHEDULED_RUN_ID)
        self.assertEqual(projection["createdAt"], DEMO_SCHEDULED_CREATED_AT)
        self.assertEqual(projection["target"], {"text": DEMO_TARGET})
        snapshot = read_bundle(root)
        self.assertEqual(
            projection["createdAt"], snapshot.events[0].payload["createdAt"]
        )

    def test_candidate_metrics_are_byte_copies_of_receipts(self) -> None:
        root = exported(fresh_tmpdir())
        projection = load_projection(root)
        receipts = discovery_receipts(root)
        self.assertTrue(projection["candidates"])
        for point in projection["candidates"]:
            receipt = receipts[point["id"]]
            for metric in ("fit", "stability", "compression", "leakage"):
                self.assertEqual(point[metric], receipt["metrics"][metric], (point["id"], metric))
            self.assertEqual(point["output"], receipt["outputs"]["text"])

    def test_tokens_are_byte_copies_of_coordinate_cost(self) -> None:
        root = exported(fresh_tmpdir())
        projection = load_projection(root)
        snapshot = read_bundle(root)
        costs = {
            event.payload["candidateId"]: event.payload["coordinateCost"]["coordinateTokens"]
            for event in snapshot.events
            if event.event_type == "archive_changed"
        }
        for point in projection["candidates"]:
            self.assertEqual(point["tokens"], costs[point["id"]])

    def test_selected_candidate_is_the_confirmed_one(self) -> None:
        root = exported(fresh_tmpdir())
        projection = load_projection(root)
        snapshot = read_bundle(root)
        completed = next(
            event for event in snapshot.events if event.event_type == "confirmation_completed"
        )
        self.assertEqual(completed.payload["outcome"], "confirmed")
        self.assertEqual(projection["selectedCandidateId"], completed.payload["candidateId"])
        self.assertIn(
            projection["selectedCandidateId"],
            [point["id"] for point in projection["candidates"]],
        )

    def test_unevaluated_control_stays_in_bundle_only(self) -> None:
        root = exported(fresh_tmpdir())
        projection = load_projection(root)
        record = load_record(root)
        control = next(
            seed for seed in scheduled_demo_seeds() if seed.role == "explicit_reconstruction"
        )
        ids = [point["id"] for point in projection["candidates"]]
        self.assertNotIn(control.candidate_id, ids)
        omitted = {entry["candidateId"] for entry in record["omittedCandidateIds"]}
        self.assertIn(control.candidate_id, omitted)
        # The complete archive remains in the bundle.
        snapshot = read_bundle(root)
        archived = {
            event.payload["candidateId"]
            for event in snapshot.events
            if event.event_type == "archive_changed"
        }
        self.assertIn(control.candidate_id, archived)

    def test_budget_fields_match_projection(self) -> None:
        root = exported(fresh_tmpdir())
        projection = load_projection(root)
        budget = projection["config"]["budget"]
        self.assertEqual(budget["candidates"], len(projection["candidates"]))
        self.assertEqual(
            budget["maxPromptTokens"], max(point["tokens"] for point in projection["candidates"])
        )
        self.assertEqual(budget["repeatedSamples"], 2)  # declared by the fixture evaluator

    def test_config_is_projected_from_declared_evidence(self) -> None:
        root = exported(fresh_tmpdir())
        projection = load_projection(root)
        manifest = read_manifest(root)
        config = projection["config"]
        self.assertEqual(config["model"], manifest.model_manifest["model"])
        self.assertEqual(config["metric"], scheduled_demo_config().metric)
        self.assertEqual(config["mode"], manifest.model_manifest["mode"])
        self.assertEqual(
            config["decoding"], canonical_json(manifest.model_manifest["decoding"])
        )

    def test_prompt_single_message_copied_verbatim(self) -> None:
        root = exported(fresh_tmpdir())
        projection = load_projection(root)
        receipts = proposal_receipts(root)
        snapshot = read_bundle(root)
        for point in projection["candidates"]:
            receipt = json.loads(snapshot.blobs[receipts[point["id"]][0]])
            messages = receipt["candidates"][receipts[point["id"]][1]]["messages"]
            if len(messages) == 1:
                self.assertEqual(point["prompt"], messages[0]["content"])

    def test_prompt_multi_message_rendered_deterministically(self) -> None:
        root = exported(fresh_tmpdir())
        projection = load_projection(root)
        seed = next(seed for seed in scheduled_demo_seeds() if seed.role == "candidate")
        self.assertGreater(len(seed.messages), 1)
        point = next(point for point in projection["candidates"] if point["id"] == seed.candidate_id)
        expected = "\n\n".join(f"{message.role}: {message.content}" for message in seed.messages)
        self.assertEqual(point["prompt"], expected)

    def test_observations_mode_is_declared(self) -> None:
        root = exported(fresh_tmpdir())
        projection = load_projection(root)
        self.assertEqual(projection["observations"], {"mode": "fixture"})

    def test_projection_record_carries_policy_and_schema_version(self) -> None:
        root = exported(fresh_tmpdir())
        record = load_record(root)
        self.assertEqual(record["schemaVersion"], PROJECTION_RECORD_SCHEMA_VERSION)
        self.assertEqual(record["runId"], DEMO_SCHEDULED_RUN_ID)
        for key in ("createdAt", "candidateInclusion", "label", "selectedCandidateId"):
            self.assertIn(key, record["policy"])


class TestCandidateLabelRule(unittest.TestCase):
    def test_explicit_reconstruction_label(self) -> None:
        self.assertEqual(candidate_label("explicit_reconstruction", "reference"), "Explicit Reconstruction")

    def test_proposal_mode_labels(self) -> None:
        for mode in ("seed", "delete", "rewrite", "repair", "reference"):
            self.assertEqual(candidate_label("candidate", mode), mode.capitalize())


class TestExportFailClosed(unittest.TestCase):
    def test_pr_a_demo_bundle_export_fails_closed(self) -> None:
        tmp = fresh_tmpdir()
        root = build_demo_bundle(tmp / "pr-a-demo")
        with self.assertRaises(ExportError) as caught:
            export_aleph_run(root)
        message = str(caught.exception)
        self.assertIn("createdAt", message)
        self.assertIn("frozenConfigDigest", message)
        self.assertIn("declare run_created_at", message)  # the policy is explicit

    def test_open_bundle_export_fails(self) -> None:
        tmp = fresh_tmpdir()
        root = tmp / "open"
        bundle = build_demo_bundle_interrupted(root)
        self.assertFalse(bundle.manifest.closed)
        with self.assertRaises(ExportError) as caught:
            export_aleph_run(root)
        self.assertIn("open", str(caught.exception))

    def test_aborted_run_export_fails_closed(self) -> None:
        root = aborted_bundle(fresh_tmpdir())
        with self.assertRaises(ExportError) as caught:
            export_aleph_run(root)
        message = str(caught.exception)
        self.assertIn("aborted", message)
        self.assertIn("only completed runs are exportable", message)
        self.assertFalse(any((root / "exports").iterdir()))  # nothing was written

    def test_missing_declared_created_at_fails(self) -> None:
        tmp = fresh_tmpdir()
        root = tmp / "no-created-at"
        build_scheduled_demo_bundle(root, export=False, created_at=None)
        with self.assertRaises(ExportError) as caught:
            export_aleph_run(root)
        self.assertIn("createdAt", str(caught.exception))

    def test_missing_observation_mode_fails(self) -> None:
        tmp = fresh_tmpdir()
        manifest = scheduled_demo_manifest()
        manifest.pop("observationMode")
        root = tmp / "no-obs-mode"
        build_scheduled_demo_bundle(root, export=False, manifest=manifest)
        with self.assertRaises(ExportError) as caught:
            export_aleph_run(root)
        self.assertIn("observationMode", str(caught.exception))

    def test_missing_run_mode_fails(self) -> None:
        tmp = fresh_tmpdir()
        manifest = scheduled_demo_manifest()
        manifest.pop("mode")
        root = tmp / "no-mode"
        build_scheduled_demo_bundle(root, export=False, manifest=manifest)
        with self.assertRaises(ExportError) as caught:
            export_aleph_run(root)
        self.assertIn("mode", str(caught.exception))

    def test_missing_required_metric_fails(self) -> None:
        tmp = fresh_tmpdir()
        root = tmp / "no-compression"

        class NoCompressionEvaluator(ScheduledDemoEvaluationAdapter):
            def evaluate(self, request):
                receipt = super().evaluate(request)
                metrics = dict(receipt.metrics)
                metrics.pop("compression")
                return evaluation_receipt(
                    request_id=receipt.request_id,
                    adapter=receipt.adapter,
                    candidate_id=receipt.candidate_id,
                    metrics=metrics,
                    resource_use=dict(receipt.resource_use),
                    outputs=dict(receipt.outputs),
                )

        build_scheduled_demo_bundle(root, export=False, evaluation=NoCompressionEvaluator)
        with self.assertRaises(ExportError) as caught:
            export_aleph_run(root)
        self.assertIn("compression", str(caught.exception))

    def test_missing_output_text_fails(self) -> None:
        tmp = fresh_tmpdir()
        root = tmp / "no-output-text"

        class NoTextEvaluator(ScheduledDemoEvaluationAdapter):
            def evaluate(self, request):
                receipt = super().evaluate(request)
                return evaluation_receipt(
                    request_id=receipt.request_id,
                    adapter=receipt.adapter,
                    candidate_id=receipt.candidate_id,
                    metrics=dict(receipt.metrics),
                    resource_use=dict(receipt.resource_use),
                    outputs={"fixture": True},
                )

        build_scheduled_demo_bundle(root, export=False, evaluation=NoTextEvaluator)
        with self.assertRaises(ExportError) as caught:
            export_aleph_run(root)
        self.assertIn("outputs.text", str(caught.exception))

    def test_metric_out_of_schema_range_fails(self) -> None:
        tmp = fresh_tmpdir()
        root = tmp / "bad-fit"

        class BadFitEvaluator(ScheduledDemoEvaluationAdapter):
            def evaluate(self, request):
                receipt = super().evaluate(request)
                metrics = dict(receipt.metrics)
                metrics["fit"] = 1.5
                return evaluation_receipt(
                    request_id=receipt.request_id,
                    adapter=receipt.adapter,
                    candidate_id=receipt.candidate_id,
                    metrics=metrics,
                    resource_use=dict(receipt.resource_use),
                    outputs=dict(receipt.outputs),
                )

        build_scheduled_demo_bundle(root, export=False, evaluation=BadFitEvaluator)
        with self.assertRaises(ExportError) as caught:
            export_aleph_run(root)
        self.assertIn("fit", str(caught.exception))

    def test_empty_shortlist_fails(self) -> None:
        tmp = fresh_tmpdir()
        root = tmp / "empty-shortlist"

        class WeakEvaluator(ScheduledDemoEvaluationAdapter):
            def evaluate(self, request):
                receipt = super().evaluate(request)
                metrics = dict(receipt.metrics)
                metrics["fit"] = 0.1
                return evaluation_receipt(
                    request_id=receipt.request_id,
                    adapter=receipt.adapter,
                    candidate_id=receipt.candidate_id,
                    metrics=metrics,
                    resource_use=dict(receipt.resource_use),
                    outputs=dict(receipt.outputs),
                )

        build_scheduled_demo_bundle(root, export=False, evaluation=WeakEvaluator)
        with self.assertRaises(ExportError) as caught:
            export_aleph_run(root)
        self.assertIn("selectedCandidateId", str(caught.exception))

    def test_missing_target_blob_fails(self) -> None:
        tmp = fresh_tmpdir()
        root = tmp / "no-target"
        build_scheduled_demo_bundle(root, export=False)
        manifest = read_manifest(root)
        (root / "blobs" / "sha256" / manifest.target_blob_digest.split(":", 1)[1]).unlink()
        with self.assertRaises(ExportError) as caught:
            export_aleph_run(root)
        self.assertIn("target blob", str(caught.exception))

    def test_missing_schema_file_fails_closed(self) -> None:
        tmp = fresh_tmpdir()
        root = exported(tmp)
        with self.assertRaises(ExportError):
            export_aleph_run(root, schema_path=tmp / "no-such-schema.json")

    def test_export_module_is_stdlib_and_scheduler_free(self) -> None:
        import pathlib

        source = (
            pathlib.Path(__file__).resolve().parents[1] / "export_aleph_run.py"
        ).read_text(encoding="utf-8")
        self.assertNotIn("hybrid_pareto", source)
        self.assertNotIn("import mlx", source)
        self.assertNotIn("requests", source)
        self.assertNotIn("datetime", source)


class TestSourceMap(unittest.TestCase):
    def test_source_map_covers_exactly_every_leaf(self) -> None:
        root = exported(fresh_tmpdir())
        projection = load_projection(root)
        record = load_record(root)
        self.assertEqual(set(leaf_paths(projection)), set(record["sourceMap"]))

    def test_source_map_entries_are_well_formed(self) -> None:
        root = exported(fresh_tmpdir())
        record = load_record(root)
        for path, entry in record["sourceMap"].items():
            self.assertIn(entry["kind"], ("copy", "render", "derived"), path)
            self.assertIsInstance(entry["source"], str)
            self.assertTrue(entry["source"], path)

    def test_metric_sources_point_at_receipt_blobs(self) -> None:
        root = exported(fresh_tmpdir())
        projection = load_projection(root)
        record = load_record(root)
        snapshot = read_bundle(root)
        eval_blobs = {
            event.payload["candidateId"]: event.blob_digests[0]
            for event in snapshot.events
            if event.event_type == "evaluation_completed" and event.phase == "discovery"
        }
        for path, entry in record["sourceMap"].items():
            if path.endswith("/fit"):
                index = int(path.split("/")[2])
                point_id = projection["candidates"][index]["id"]
                self.assertIn(eval_blobs[point_id], entry["source"], path)

    def test_created_at_source_points_at_run_started(self) -> None:
        root = exported(fresh_tmpdir())
        record = load_record(root)
        self.assertEqual(record["sourceMap"]["/createdAt"]["source"], "events[0].payload.createdAt")
        self.assertEqual(record["sourceMap"]["/createdAt"]["kind"], "copy")

    def test_id_source_points_at_manifest(self) -> None:
        root = exported(fresh_tmpdir())
        record = load_record(root)
        self.assertEqual(record["sourceMap"]["/id"]["source"], "manifest.runId")

    def test_tokens_source_points_at_archive_event(self) -> None:
        root = exported(fresh_tmpdir())
        record = load_record(root)
        token_paths = [path for path in record["sourceMap"] if path.endswith("/tokens")]
        self.assertTrue(token_paths)
        for path in token_paths:
            self.assertIn("coordinateCost.coordinateTokens", record["sourceMap"][path]["source"])


class TestSchemaInterop(unittest.TestCase):
    SCHEMA = Path(__file__).resolve().parents[3] / "schemas" / "aleph-run.schema.json"

    def test_schema_declares_optional_artifact_ref(self) -> None:
        schema = json.loads(self.SCHEMA.read_text(encoding="utf-8"))
        self.assertIn("artifactRef", schema["properties"])
        self.assertNotIn("artifactRef", schema["required"])
        self.assertFalse(schema["additionalProperties"])

    def test_validator_rejects_unknown_top_level_field(self) -> None:
        projection = load_projection(exported(fresh_tmpdir()))
        projection["invented"] = 1
        errors = validate_against_schema(projection, self.SCHEMA)
        self.assertTrue(any("invented" in error for error in errors), errors)

    def test_validator_rejects_missing_required_field(self) -> None:
        projection = load_projection(exported(fresh_tmpdir()))
        projection.pop("selectedCandidateId")
        errors = validate_against_schema(projection, self.SCHEMA)
        self.assertTrue(any("selectedCandidateId" in error for error in errors), errors)

    def test_validator_rejects_bad_enum(self) -> None:
        projection = load_projection(exported(fresh_tmpdir()))
        projection["observations"]["mode"] = "invented_mode"
        errors = validate_against_schema(projection, self.SCHEMA)
        self.assertTrue(errors)

    def test_validator_rejects_out_of_range_metric(self) -> None:
        projection = load_projection(exported(fresh_tmpdir()))
        projection["candidates"][0]["leakage"] = 1.5
        errors = validate_against_schema(projection, self.SCHEMA)
        self.assertTrue(errors)

    def test_validator_rejects_wrong_type(self) -> None:
        projection = load_projection(exported(fresh_tmpdir()))
        projection["candidates"][0]["tokens"] = "three"
        errors = validate_against_schema(projection, self.SCHEMA)
        self.assertTrue(errors)

    def test_validator_fails_closed_on_unknown_keyword(self) -> None:
        tmp = fresh_tmpdir()
        schema_path = tmp / "schema.json"
        schema_path.write_text(json.dumps({"type": "object", "pattern": "x"}), encoding="utf-8")
        errors = validate_against_schema({}, schema_path)
        self.assertTrue(any("unsupported keywords" in error for error in errors), errors)

    def test_validator_rejects_unsupported_type_value(self) -> None:
        tmp = fresh_tmpdir()
        schema_path = tmp / "schema.json"
        schema_path.write_text(json.dumps({"type": "strin"}), encoding="utf-8")
        errors = validate_against_schema({}, schema_path)
        self.assertTrue(any("unsupported 'type' value" in error for error in errors), errors)

    def test_validator_rejects_malformed_keyword_values(self) -> None:
        cases = (
            ({"type": "array", "items": True}, [1]),
            ({"type": "object", "additionalProperties": {"type": "string"}}, {}),
            ({"enum": 5}, "x"),
            ({"type": "object", "properties": 5}, {}),
        )
        for schema, value in cases:
            with self.subTest(schema=schema):
                tmp = fresh_tmpdir()
                schema_path = tmp / "schema.json"
                schema_path.write_text(json.dumps(schema), encoding="utf-8")
                errors = validate_against_schema(value, schema_path)
                self.assertTrue(errors, (schema, errors))


class TestVerifyAttestation(unittest.TestCase):
    def test_unknown_export_file_fails_verify(self) -> None:
        tmp = fresh_tmpdir()
        root = exported(tmp)
        (root / "exports" / "stray.json").write_text("{}\n", encoding="utf-8")
        report = verify_bundle(root)
        self.assertTrue(any("stray.json" in error for error in report.errors), report.errors)

    def test_tampered_export_fails_verify(self) -> None:
        tmp = fresh_tmpdir()
        root = exported(tmp)
        path = root / "exports" / "aleph-run.json"
        projection = json.loads(path.read_text(encoding="utf-8"))
        projection["candidates"][0]["fit"] = 0.111
        path.write_text(canonical_json(projection) + "\n", encoding="utf-8")
        report = verify_bundle(root)
        self.assertTrue(
            any("differs from the replayed derivation" in error for error in report.errors),
            report.errors,
        )

    def test_tampered_sidecar_fails_verify(self) -> None:
        tmp = fresh_tmpdir()
        root = exported(tmp)
        path = root / "exports" / "aleph-run-projection.json"
        record = json.loads(path.read_text(encoding="utf-8"))
        record["policy"]["label"] = "tampered"
        path.write_text(canonical_json(record) + "\n", encoding="utf-8")
        report = verify_bundle(root)
        self.assertTrue(
            any("differs from the replayed derivation" in error for error in report.errors),
            report.errors,
        )

    def test_partial_export_set_fails_verify(self) -> None:
        tmp = fresh_tmpdir()
        root = exported(tmp)
        (root / "exports" / "aleph-run-projection.json").unlink()
        report = verify_bundle(root)
        self.assertTrue(any("incomplete" in error for error in report.errors), report.errors)

    def test_rewritten_receipt_evidence_fails_verify(self) -> None:
        from search.engine.tests.support import mutate_receipt_blob

        tmp = fresh_tmpdir()
        root = exported(tmp)
        snapshot = read_bundle(root)
        seq = next(
            event.sequence
            for event in snapshot.events
            if event.event_type == "evaluation_completed" and event.phase == "discovery"
        )

        def lower_fit(receipt):
            receipt["metrics"]["fit"] = 0.8
            return receipt

        mutate_receipt_blob(root, seq, lower_fit)
        report = verify_bundle(root)
        self.assertTrue(
            any("differs from the replayed derivation" in error for error in report.errors),
            report.errors,
        )

    def test_export_in_open_run_fails_verify(self) -> None:
        tmp = fresh_tmpdir()
        root = tmp / "open"
        build_demo_bundle_interrupted(root)
        (root / "exports" / "aleph-run.json").write_text("{}\n", encoding="utf-8")
        (root / "exports" / "aleph-run-projection.json").write_text("{}\n", encoding="utf-8")
        report = verify_bundle(root, require_closed=False)
        self.assertTrue(any("not completed" in error for error in report.errors), report.errors)

    def test_aborted_run_with_exports_fails_verify(self) -> None:
        tmp = fresh_tmpdir()
        root = aborted_bundle(tmp)
        (root / "exports" / "aleph-run.json").write_text("{}\n", encoding="utf-8")
        (root / "exports" / "aleph-run-projection.json").write_text("{}\n", encoding="utf-8")
        report = verify_bundle(root)
        self.assertFalse(report.ok)
        self.assertTrue(
            any("cannot attest export files" in error for error in report.errors), report.errors
        )
        self.assertTrue(any("aborted" in error for error in report.errors), report.errors)

    def test_export_absent_verifies_clean(self) -> None:
        tmp = fresh_tmpdir()
        root = build_demo_bundle(tmp / "pr-a-demo")
        report = verify_bundle(root)
        self.assertTrue(report.ok, report.errors)
        self.assertFalse([error for error in report.errors if "export" in error])


if __name__ == "__main__":
    unittest.main()
