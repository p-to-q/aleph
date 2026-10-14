"""Run bundle: append-only writer, reader, resume, and materialization."""

from __future__ import annotations

import json
import unittest

from search.engine.archive import (
    ArchiveError,
    RunBundle,
    RunManifest,
    materialize,
    read_bundle,
    read_manifest,
)
from search.engine.canonical import digest
from search.engine.events import build_event
from search.engine.fixtures.demo import (
    DEMO_RUN_ID,
    build_demo_bundle,
    build_demo_bundle_interrupted,
    demo_bundle_config,
    demo_event_id,
    demo_events,
    resume_demo_bundle,
)
from search.engine.tests.support import fresh_tmpdir, make_demo_bundle


class TestRunManifest(unittest.TestCase):
    def test_open_manifest_cannot_carry_stream_digest(self) -> None:
        config = demo_bundle_config()
        with self.assertRaises(ArchiveError):
            RunManifest(
                run_id="r",
                target_digest=digest("t"),
                known_metrics=("fit",),
                adapter_digests=(digest("a"),),
                nesting_rule="t_dec_nested_in_w_search",
                scheduler_model="s",
                model_manifest={"fixture": True},
                closed=False,
                stream_digest=digest("stream"),
            )

    def test_closed_manifest_requires_stream_digest(self) -> None:
        with self.assertRaises(ArchiveError):
            RunManifest(
                run_id="r",
                target_digest=digest("t"),
                known_metrics=("fit",),
                adapter_digests=(digest("a"),),
                nesting_rule="t_dec_nested_in_w_search",
                scheduler_model="s",
                model_manifest={"fixture": True},
                closed=True,
            )

    def test_round_trip_rejects_unknown_fields(self) -> None:
        from search.engine.archive import manifest_from_canonical

        manifest = read_manifest(make_demo_bundle(fresh_tmpdir()))
        payload = manifest.to_canonical()
        payload["invented"] = 1
        with self.assertRaises(ArchiveError):
            manifest_from_canonical(payload)

    def test_requires_declared_metrics_and_adapters(self) -> None:
        with self.assertRaises(ArchiveError):
            RunManifest(
                run_id="r",
                target_digest=digest("t"),
                known_metrics=(),
                adapter_digests=(digest("a"),),
                nesting_rule="t_dec_nested_in_w_search",
                scheduler_model="s",
                model_manifest={"fixture": True},
            )
        with self.assertRaises(ArchiveError):
            RunManifest(
                run_id="r",
                target_digest=digest("t"),
                known_metrics=("fit",),
                adapter_digests=(),
                nesting_rule="t_dec_nested_in_w_search",
                scheduler_model="s",
                model_manifest={"fixture": True},
            )


class TestBundleCreation(unittest.TestCase):
    def test_layout_matches_issue_106(self) -> None:
        root = make_demo_bundle(fresh_tmpdir())
        for name in (
            "manifest.json",
            "events.jsonl",
            "blobs/sha256",
            "materialized/archive.json",
            "materialized/views.json",
            "materialized/confirmation.json",
            "materialized/resource-ledger.json",
            "exports",
        ):
            self.assertTrue((root / name).exists(), name)

    def test_refuses_non_empty_root(self) -> None:
        tmp = fresh_tmpdir()
        root = tmp / "bundle"
        root.mkdir()
        (root / "stray.txt").write_text("no", encoding="utf-8")
        with self.assertRaises(ArchiveError):
            RunBundle.create(root, **demo_bundle_config())

    def test_run_started_is_first_event(self) -> None:
        root = make_demo_bundle(fresh_tmpdir())
        snapshot = read_bundle(root)
        self.assertEqual(snapshot.events[0].event_type, "run_started")
        self.assertEqual(snapshot.events[-1].event_type, "run_completed")

    def test_manifest_sealed_with_stream_digest(self) -> None:
        root = make_demo_bundle(fresh_tmpdir())
        manifest = read_manifest(root)
        self.assertTrue(manifest.closed)
        self.assertIsNotNone(manifest.stream_digest)

    def test_demo_stream_has_30_events(self) -> None:
        root = make_demo_bundle(fresh_tmpdir())
        snapshot = read_bundle(root)
        self.assertEqual(len(snapshot.events), 30)

    def test_all_event_types_exercised(self) -> None:
        root = make_demo_bundle(fresh_tmpdir())
        snapshot = read_bundle(root)
        seen = {event.event_type for event in snapshot.events}
        from search.engine.events import EVENT_TYPES

        self.assertEqual(seen, set(EVENT_TYPES))

    def test_blobs_are_content_addressed(self) -> None:
        root = make_demo_bundle(fresh_tmpdir())
        snapshot = read_bundle(root)
        for digest_str, payload in snapshot.blobs.items():
            path = root / "blobs/sha256" / digest_str.split(":", 1)[1]
            self.assertEqual(path.read_bytes(), payload)
            self.assertEqual(len(digest_str), 7 + 64)


class TestAppendOnly(unittest.TestCase):
    def test_wrong_sequence_rejected(self) -> None:
        tmp = fresh_tmpdir()
        bundle = RunBundle.create(tmp / "bundle", **demo_bundle_config())
        event = build_event(
            event_id=demo_event_id(5, DEMO_RUN_ID),
            sequence=5,  # next is 1
            event_type="budget_reserved",
            phase="discovery",
            payload={"reservationId": "rsv", "account": "W_search", "stage": "discovery"},
        )
        with self.assertRaises(ArchiveError):
            bundle.append_event(event)

    def test_duplicate_event_id_rejected(self) -> None:
        tmp = fresh_tmpdir()
        bundle = RunBundle.create(tmp / "bundle", **demo_bundle_config())
        event = build_event(
            event_id=f"{DEMO_RUN_ID}:run-started",  # already used by run_started
            sequence=1,
            event_type="budget_reserved",
            phase="discovery",
            payload={"reservationId": "rsv", "account": "W_search", "stage": "discovery"},
        )
        with self.assertRaises(ArchiveError):
            bundle.append_event(event)

    def test_blob_digest_collision_rejected(self) -> None:
        tmp = fresh_tmpdir()
        bundle = RunBundle.create(tmp / "bundle", **demo_bundle_config())
        digest_str = bundle.store_blob_bytes(b"original")
        # Adversarial: a path that already exists with content that does not
        # match its declared digest must fail closed, never overwrite.
        path = tmp / "bundle" / "blobs/sha256" / digest_str.split(":", 1)[1]
        path.write_bytes(b"tampered content")
        with self.assertRaises(ArchiveError):
            bundle.store_blob_bytes(b"original")

    def test_identical_blob_write_is_noop(self) -> None:
        tmp = fresh_tmpdir()
        bundle = RunBundle.create(tmp / "bundle", **demo_bundle_config())
        first = bundle.store_blob_bytes(b"same")
        second = bundle.store_blob_bytes(b"same")
        self.assertEqual(first, second)

    def test_cannot_append_after_close(self) -> None:
        tmp = fresh_tmpdir()
        bundle = RunBundle.create(tmp / "bundle", **demo_bundle_config())
        bundle.close(status="aborted")
        with self.assertRaises(ArchiveError):
            bundle.append_event(
                build_event(
                    event_id=demo_event_id(1, DEMO_RUN_ID),
                    sequence=1,
                    event_type="budget_reserved",
                    phase="discovery",
                    payload={"reservationId": "rsv", "account": "W_search", "stage": "discovery"},
                )
            )

    def test_cannot_reopen_closed_bundle(self) -> None:
        tmp = fresh_tmpdir()
        bundle = RunBundle.create(tmp / "bundle", **demo_bundle_config())
        bundle.close(status="aborted")
        with self.assertRaises(ArchiveError):
            RunBundle.open_for_append(tmp / "bundle")


class TestResume(unittest.TestCase):
    def test_resume_equals_uninterrupted(self) -> None:
        tmp = fresh_tmpdir()
        uninterrupted = build_demo_bundle(tmp / "full")
        interrupted_root = tmp / "partial"
        bundle = build_demo_bundle_interrupted(interrupted_root)
        self.assertFalse(read_manifest(interrupted_root).closed)
        self.assertEqual(bundle.next_sequence, 15)
        resume_demo_bundle(interrupted_root)
        from search.engine.adapters.replay import replay

        first = replay(uninterrupted)
        second = replay(interrupted_root)
        self.assertEqual(first.digests, second.digests)
        self.assertEqual(
            [event.to_canonical() for event in first.snapshot.events],
            [event.to_canonical() for event in second.snapshot.events],
        )

    def test_materialized_views_rebuild_byte_identically(self) -> None:
        tmp = fresh_tmpdir()
        root = make_demo_bundle(tmp)
        views_dir = root / "materialized"
        originals = {path.name: path.read_bytes() for path in views_dir.iterdir()}
        for path in views_dir.iterdir():
            path.unlink()
        materialize(root)
        for name, payload in originals.items():
            self.assertEqual((views_dir / name).read_bytes(), payload, name)


class TestMaterialization(unittest.TestCase):
    def test_derived_views_do_not_invent_candidates(self) -> None:
        tmp = fresh_tmpdir()
        root = make_demo_bundle(tmp)
        archive_view = json.loads((root / "materialized/archive.json").read_text(encoding="utf-8"))
        self.assertEqual(len(archive_view["candidates"]), 3)
        for candidate in archive_view["candidates"].values():
            self.assertIn("candidateId", candidate)
            self.assertNotIn("score", candidate)

    def test_promoted_and_rejected_recorded_in_views(self) -> None:
        tmp = fresh_tmpdir()
        root = make_demo_bundle(tmp)
        views = json.loads((root / "materialized/views.json").read_text(encoding="utf-8"))
        self.assertEqual(len(views["promotedCandidateIds"]), 1)
        self.assertEqual(len(views["rejectedCandidateIds"]), 1)
        self.assertEqual(views["selectionRule"], "demo-pareto-v0")

    def test_confirmation_view_records_outcome(self) -> None:
        tmp = fresh_tmpdir()
        root = make_demo_bundle(tmp)
        view = json.loads(
            (root / "materialized/confirmation.json").read_text(encoding="utf-8")
        )
        self.assertEqual(view["outcome"], "confirmed")
        self.assertIn("candidateId", view)

    def test_ledger_view_reconciles_accounts(self) -> None:
        tmp = fresh_tmpdir()
        root = make_demo_bundle(tmp)
        ledger = json.loads(
            (root / "materialized/resource-ledger.json").read_text(encoding="utf-8")
        )
        self.assertEqual(ledger["W_search"]["components"]["proposalCalls"], 2)
        self.assertEqual(ledger["W_search"]["components"]["proposalFailures"], 1)
        self.assertEqual(ledger["W_search"]["components"]["evaluationCalls"], 4)
        self.assertEqual(ledger["W_search"]["components"]["evaluationFailures"], 1)
        self.assertEqual(ledger["W_search"]["components"]["rejectedCandidates"], 1)
        self.assertEqual(ledger["W_search"]["components"]["proposedCandidates"], 3)
        self.assertEqual(ledger["T_dec"]["byStage"]["discovery"]["calls"], 3)
        self.assertEqual(ledger["T_dec"]["byStage"]["discovery"]["failures"], 1)
        self.assertEqual(ledger["T_dec"]["byStage"]["confirmation"]["calls"], 1)
        self.assertEqual(ledger["V_verify"]["freshSamples"], 1)
        self.assertGreater(ledger["D_crit"]["longestDependencyPath"], 0)


if __name__ == "__main__":
    unittest.main()
