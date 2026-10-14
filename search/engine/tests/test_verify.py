"""Fail-closed verifier: adversarial corruption modes, one test per mode.

Every bundle in this file is a fixture or a deliberate corruption of one.
None of the values are model evidence.
"""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from search.engine.archive import (
    ARCHIVE_VIEW_SCHEMA_VERSION,
    RunBundle,
    materialize,
    read_manifest,
)
from search.engine.canonical import digest, digest_bytes
from search.engine.contracts import (
    Candidate,
    Message,
    Placement,
    adapter_identity,
    evaluation_receipt,
    proposal_receipt,
)
from search.engine.events import build_event
from search.engine.fixtures.demo import (
    DEMO_RUN_ID,
    build_demo_bundle,
    build_demo_bundle_interrupted,
    demo_coordinate_cost,
    demo_scaffold,
)
from search.engine.tests.support import (
    fresh_tmpdir,
    make_demo_bundle,
    mutate_receipt_blob,
    rebuild_event,
    rewrite_stream,
)
from search.engine.verify import verify_bundle


def errors_for(root: Path, **kwargs) -> list[str]:
    return list(verify_bundle(root, **kwargs).errors)


def assert_has_error(testcase: unittest.TestCase, errors: list[str], needle: str) -> None:
    testcase.assertTrue(
        any(needle in error for error in errors),
        f"expected an error containing {needle!r}, got: {errors}",
    )


class TestVerifyHappyPath(unittest.TestCase):
    def test_known_good_demo_verifies(self) -> None:
        tmp = fresh_tmpdir()
        root = make_demo_bundle(tmp)
        report = verify_bundle(root)
        self.assertTrue(report.ok, report.errors)
        self.assertEqual(report.run_id, DEMO_RUN_ID)
        self.assertEqual(report.confirmation_outcome, "confirmed")
        self.assertIsNotNone(report.stream_digest)
        self.assertEqual(len(report.materialized_digests or {}), 4)

    def test_verify_is_deterministic_and_idempotent(self) -> None:
        tmp = fresh_tmpdir()
        root = make_demo_bundle(tmp)
        first = verify_bundle(root)
        second = verify_bundle(root)
        self.assertTrue(first.ok and second.ok)
        self.assertEqual(
            (root / "verify.json").read_bytes(), (root / "verify.json").read_bytes()
        )
        # Deterministic: rebuild in a fresh directory yields the same payload.
        root2 = make_demo_bundle(tmp, "bundle2")
        verify_bundle(root2)
        self.assertEqual(
            json.loads((root / "verify.json").read_text(encoding="utf-8")),
            json.loads((root2 / "verify.json").read_text(encoding="utf-8")),
        )

    def test_aborted_run_verifies(self) -> None:
        tmp = fresh_tmpdir()
        bundle = RunBundle.create(
            tmp / "bundle",
            run_id="aborted-run",
            target_digest=digest("t"),
            known_metrics=("fit",),
            adapter_digests=(digest("a"),),
            nesting_rule="t_dec_nested_in_w_search",
            scheduler_model="single-worker-v0",
            model_manifest={"fixture": True},
        )
        bundle.close(status="aborted")
        materialize(tmp / "bundle")
        report = verify_bundle(tmp / "bundle")
        self.assertTrue(report.ok, report.errors)


class TestStreamCorruption(unittest.TestCase):
    def test_reordered_events_fail(self) -> None:
        tmp = fresh_tmpdir()
        root = make_demo_bundle(tmp)
        records = (root / "events.jsonl").read_text(encoding="utf-8").splitlines()
        swapped = [records[0], records[2], records[1], *records[3:]]
        (root / "events.jsonl").write_text("\n".join(swapped) + "\n", encoding="utf-8")
        errors = errors_for(root)
        assert_has_error(self, errors, "expected 1")

    def test_tampered_payload_fails(self) -> None:
        tmp = fresh_tmpdir()
        root = make_demo_bundle(tmp)

        def mutate(event):
            payload = dict(event.payload, candidateIds=["sha256:" + "0" * 64])
            return rebuild_event(event, payload=payload)

        rewrite_stream(root, {2: mutate})
        errors = errors_for(root)
        assert_has_error(self, errors, "do not match")

    def test_duplicate_event_id_fails(self) -> None:
        tmp = fresh_tmpdir()
        root = make_demo_bundle(tmp)

        def mutate(event):
            return rebuild_event(event, event_id=f"{DEMO_RUN_ID}:run-started")

        rewrite_stream(root, {3: mutate})
        errors = errors_for(root)
        assert_has_error(self, errors, "duplicate event id")

    def test_sequence_gap_fails(self) -> None:
        tmp = fresh_tmpdir()
        root = make_demo_bundle(tmp)

        def mutate(event):
            return rebuild_event(event, sequence=event.sequence + 1)

        rewrite_stream(root, {10: mutate})
        errors = errors_for(root)
        assert_has_error(self, errors, "expected 10")

    def test_orphan_parent_fails(self) -> None:
        tmp = fresh_tmpdir()
        root = make_demo_bundle(tmp)

        def mutate(event):
            return rebuild_event(event, parent_event_ids=("missing-parent",))

        rewrite_stream(root, {7: mutate})
        errors = errors_for(root)
        assert_has_error(self, errors, "orphan parent")

    def test_truncated_final_write_fails(self) -> None:
        tmp = fresh_tmpdir()
        root = make_demo_bundle(tmp)
        text = (root / "events.jsonl").read_text(encoding="utf-8")
        (root / "events.jsonl").write_text(text[:-10], encoding="utf-8")  # no trailing newline
        errors = errors_for(root)
        assert_has_error(self, errors, "does not end in a newline")

    def test_discovery_relabelled_as_confirmation_fails(self) -> None:
        tmp = fresh_tmpdir()
        root = make_demo_bundle(tmp)
        # Phase-table violation: a proposal record relabelled as confirmation
        # is rejected at parse time, before any digest bookkeeping.
        lines = (root / "events.jsonl").read_text(encoding="utf-8").splitlines()
        record = json.loads(lines[2])
        record["phase"] = "confirmation"
        lines[2] = json.dumps(record)
        (root / "events.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")
        errors = errors_for(root)
        assert_has_error(self, errors, "cannot carry phase")

    def test_unknown_top_level_file_fails(self) -> None:
        tmp = fresh_tmpdir()
        root = make_demo_bundle(tmp)
        (root / "stray.txt").write_text("x", encoding="utf-8")
        errors = errors_for(root)
        assert_has_error(self, errors, "unknown entry in bundle root")

    def test_export_files_fail_in_pr_a(self) -> None:
        tmp = fresh_tmpdir()
        root = make_demo_bundle(tmp)
        (root / "exports" / "aleph-run.json").write_text("{}", encoding="utf-8")
        errors = errors_for(root)
        assert_has_error(self, errors, "PR A cannot attest")


class TestBlobCorruption(unittest.TestCase):
    def test_missing_blob_fails(self) -> None:
        tmp = fresh_tmpdir()
        root = make_demo_bundle(tmp)
        snapshot = json.loads((root / "events.jsonl").read_text(encoding="utf-8").splitlines()[2])
        blob = snapshot["blobDigests"][0]
        (root / "blobs/sha256" / blob.split(":", 1)[1]).unlink()
        errors = errors_for(root)
        assert_has_error(self, errors, "is missing")

    def test_blob_content_mismatch_fails(self) -> None:
        tmp = fresh_tmpdir()
        root = make_demo_bundle(tmp)
        snapshot = json.loads((root / "events.jsonl").read_text(encoding="utf-8").splitlines()[2])
        blob = snapshot["blobDigests"][0]
        (root / "blobs/sha256" / blob.split(":", 1)[1]).write_bytes(b"tampered")
        errors = errors_for(root)
        assert_has_error(self, errors, "does not match its declared digest")

    def test_unreferenced_blob_fails_in_closed_run(self) -> None:
        tmp = fresh_tmpdir()
        root = make_demo_bundle(tmp)
        orphan = digest_bytes(b"orphan")
        (root / "blobs/sha256" / orphan.split(":", 1)[1]).write_bytes(b"orphan")
        errors = errors_for(root)
        assert_has_error(self, errors, "unreferenced blob")

    def test_missing_target_blob_fails(self) -> None:
        tmp = fresh_tmpdir()
        root = make_demo_bundle(tmp)
        manifest = read_manifest(root)
        (root / "blobs/sha256" / manifest.target_blob_digest.split(":", 1)[1]).unlink()
        errors = errors_for(root)
        assert_has_error(self, errors, "target blob")


class TestReceiptCorruption(unittest.TestCase):
    def test_receipt_candidate_ids_mismatch_fails(self) -> None:
        tmp = fresh_tmpdir()
        root = make_demo_bundle(tmp)

        def mutate(receipt):
            receipt["candidates"] = []
            return receipt

        mutate_receipt_blob(root, 2, mutate)
        errors = errors_for(root)
        assert_has_error(self, errors, "do not match")

    def test_unknown_adapter_digest_fails(self) -> None:
        tmp = fresh_tmpdir()
        root = make_demo_bundle(tmp)

        def mutate(receipt):
            receipt["adapter"]["revision"] = "tampered-revision"
            return receipt

        mutate_receipt_blob(root, 2, mutate)
        errors = errors_for(root)
        assert_has_error(self, errors, "not declared in the manifest")

    def test_unknown_metric_fails_closed(self) -> None:
        tmp = fresh_tmpdir()
        root = make_demo_bundle(tmp)
        # The evaluation_completed events are at sequences 9, 11, 25.
        def mutate(receipt):
            receipt["metrics"]["inventedMetric"] = 0.5
            return receipt

        mutate_receipt_blob(root, 9, mutate)
        errors = errors_for(root)
        assert_has_error(self, errors, "unknown metrics")

    def test_proposal_receipt_with_scores_fails(self) -> None:
        tmp = fresh_tmpdir()
        root = make_demo_bundle(tmp)

        def mutate(receipt):
            receipt["resourceUse"]["fit"] = 0.99
            return receipt

        mutate_receipt_blob(root, 2, mutate)
        errors = errors_for(root)
        assert_has_error(self, errors, "evaluator scores")

    def test_non_numeric_metric_value_fails(self) -> None:
        tmp = fresh_tmpdir()
        root = make_demo_bundle(tmp)

        def mutate(receipt):
            receipt["metrics"]["fit"] = "high"
            return receipt

        mutate_receipt_blob(root, 9, mutate)
        errors = errors_for(root)
        assert_has_error(self, errors, "must be an int or float")


class TestAccountingCorruption(unittest.TestCase):
    def test_missing_budget_reservation_fails(self) -> None:
        tmp = fresh_tmpdir()
        root = make_demo_bundle(tmp)

        def mutate(event):
            return rebuild_event(event, payload=dict(event.payload, reservationId="rsv-invented"))

        rewrite_stream(root, {2: mutate})
        errors = errors_for(root)
        assert_has_error(self, errors, "without open reservation")

    def test_unsettled_reservation_fails(self) -> None:
        tmp = fresh_tmpdir()
        root = make_demo_bundle(tmp)
        # The budget_committed for rsv-search references a different reservation.
        def mutate(event):
            return rebuild_event(event, payload=dict(event.payload, reservationId="rsv-other"))

        rewrite_stream(root, {3: mutate})
        errors = errors_for(root)
        assert_has_error(self, errors, "no open reservation to settle")

    def test_wrong_account_for_call_fails(self) -> None:
        tmp = fresh_tmpdir()
        root = make_demo_bundle(tmp)
        # Relabel the proposal reservation as T_dec: the open reservation is
        # found, but its account does not match the call it backs.
        def mutate(event):
            return rebuild_event(event, payload=dict(event.payload, account="T_dec"))

        rewrite_stream(root, {1: mutate})
        errors = errors_for(root)
        assert_has_error(self, errors, "expected W_search")

    def test_dangling_evaluation_start_fails(self) -> None:
        tmp = fresh_tmpdir()
        root = tmp / "bundle"
        from search.engine.canonical import canonical_bytes

        adapter = adapter_identity("fixture-proposal", "rev", "proposal")
        candidate = Candidate(
            messages=(Message(role="user", content="coordinate"),),
            placement=demo_scaffold(),
            proposal_mode="seed",
        )
        bundle = RunBundle.create(
            root,
            run_id="dangling-run",
            target_digest=digest("t"),
            known_metrics=("fit",),
            adapter_digests=(adapter.adapter_digest,),
            nesting_rule="t_dec_nested_in_w_search",
            scheduler_model="single-worker-v0",
            model_manifest={"fixture": True},
        )
        receipt = proposal_receipt(
            request_id="req-p", adapter=adapter, candidates=(candidate,)
        )
        receipt_digest = digest(receipt.to_canonical())
        bundle.append_event(
            build_event(
                event_id="dangling-run:event-01",
                sequence=1,
                event_type="budget_reserved",
                phase="discovery",
                payload={"reservationId": "rsv-s", "account": "W_search", "stage": "discovery"},
            )
        )
        bundle.append_event(
            build_event(
                event_id="dangling-run:event-02",
                sequence=2,
                event_type="proposal_succeeded",
                phase="discovery",
                payload={"requestId": "req-p", "reservationId": "rsv-s", "candidateIds": [candidate.candidate_id]},
                blob_digests=(receipt_digest,),
            ),
            blobs={receipt_digest: canonical_bytes(receipt.to_canonical())},
        )
        bundle.append_event(
            build_event(
                event_id="dangling-run:event-03",
                sequence=3,
                event_type="budget_reserved",
                phase="discovery",
                payload={"reservationId": "rsv-e", "account": "T_dec", "stage": "discovery"},
            )
        )
        bundle.append_event(
            build_event(
                event_id="dangling-run:event-04",
                sequence=4,
                event_type="evaluation_started",
                phase="discovery",
                payload={"requestId": "req-e", "reservationId": "rsv-e", "candidateId": candidate.candidate_id},
            )
        )
        bundle.close(status="aborted")
        errors = errors_for(root)
        assert_has_error(self, errors, "started but never terminated")


class TestArchiveIntegrity(unittest.TestCase):
    def test_tampered_archive_digest_chain_fails(self) -> None:
        tmp = fresh_tmpdir()
        root = make_demo_bundle(tmp)

        def mutate(event):
            return rebuild_event(
                event, payload=dict(event.payload, archiveDigest=digest("tampered"))
            )

        rewrite_stream(root, {4: mutate})
        errors = errors_for(root)
        assert_has_error(self, errors, "declares archive digest")

    def test_confirmation_context_reuse_fails(self) -> None:
        tmp = fresh_tmpdir()
        root = make_demo_bundle(tmp)

        # Confirmation_started at 27 must not reuse the discovery context.
        def mutate_ctx(event):
            return rebuild_event(
                event,
                payload=dict(event.payload, confirmationContextDigest=digest({"fixture": "discovery-context"})),
            )

        rewrite_stream(root, {27: mutate_ctx})
        errors = errors_for(root)
        assert_has_error(self, errors, "reuses the discovery context digest")

    def test_confirmation_evaluation_outside_shortlist_fails(self) -> None:
        tmp = fresh_tmpdir()
        root = make_demo_bundle(tmp)
        # Confirmation evaluation at 25 must target the shortlist; point it at
        # the rejected candidate.
        snapshot_records = [
            json.loads(line)
            for line in (root / "events.jsonl").read_text(encoding="utf-8").splitlines()
        ]
        # rejected candidate id from seq 14 payload
        rejected_id = snapshot_records[14]["payload"]["candidateId"]

        def mutate(event):
            return rebuild_event(event, payload=dict(event.payload, candidateId=rejected_id))

        mutate_receipt_blob(root, 25, lambda receipt: dict(receipt, candidateId=rejected_id))
        rewrite_stream(root, {24: mutate, 25: mutate})
        errors = errors_for(root)
        assert_has_error(self, errors, "outside the frozen shortlist")


class TestMaterializationTamper(unittest.TestCase):
    def test_tampered_materialized_view_fails(self) -> None:
        tmp = fresh_tmpdir()
        root = make_demo_bundle(tmp)
        path = root / "materialized/archive.json"
        path.write_text(json.dumps({"tampered": True}), encoding="utf-8")
        errors = errors_for(root)
        assert_has_error(self, errors, "differs from the replayed derivation")

    def test_missing_materialized_view_fails(self) -> None:
        tmp = fresh_tmpdir()
        root = make_demo_bundle(tmp)
        (root / "materialized/resource-ledger.json").unlink()
        errors = errors_for(root)
        assert_has_error(self, errors, "materialized view is missing")

    def test_tampered_verify_json_fails(self) -> None:
        tmp = fresh_tmpdir()
        root = make_demo_bundle(tmp)
        verify_bundle(root)
        (root / "verify.json").write_text(json.dumps({"ok": True, "fake": 1}), encoding="utf-8")
        errors = errors_for(root)
        assert_has_error(self, errors, "verify.json does not match")


class TestRunState(unittest.TestCase):
    def test_open_run_fails_when_closed_required(self) -> None:
        tmp = fresh_tmpdir()
        root = tmp / "bundle"
        build_demo_bundle_interrupted(root)
        materialize(root)
        errors = errors_for(root)
        assert_has_error(self, errors, "run is not completed")

    def test_open_run_verifies_without_closed_requirement(self) -> None:
        tmp = fresh_tmpdir()
        root = tmp / "bundle"
        build_demo_bundle_interrupted(root)
        materialize(root)
        report = verify_bundle(root, require_closed=False)
        self.assertTrue(report.ok, report.errors)


class TestTargetCopyFallback(unittest.TestCase):
    def build_copy_bundle(self, root: Path, *, role: str, promote: bool) -> None:
        target = "copy-me-target"
        target_digest = digest(target)
        proposal_adapter = adapter_identity("fixture-proposal", "rev", "proposal")
        evaluation_adapter = adapter_identity("fixture-evaluation", "rev", "evaluation")
        candidate = Candidate(
            messages=(Message(role="user", content=target),),
            placement=demo_scaffold(),
            proposal_mode="reference",
            role=role,
        )
        candidate_id = candidate.candidate_id
        bundle = RunBundle.create(
            root,
            run_id="copy-run",
            target_digest=target_digest,
            target_content=target,
            known_metrics=("fit",),
            adapter_digests=(proposal_adapter.adapter_digest, evaluation_adapter.adapter_digest),
            nesting_rule="t_dec_nested_in_w_search",
            scheduler_model="single-worker-v0",
            model_manifest={"fixture": True},
        )

        def push(sequence, event_type, phase, payload, parents=(), blobs=None):
            bundle.append_event(
                build_event(
                    event_id=f"copy-run:event-{sequence:02d}",
                    sequence=sequence,
                    event_type=event_type,
                    phase=phase,
                    payload=payload,
                    parent_event_ids=parents,
                    blob_digests=tuple((blobs or {}).keys()),
                ),
                blobs=blobs or {},
            )

        from search.engine.canonical import canonical_bytes

        receipt = proposal_receipt(
            request_id="req-p", adapter=proposal_adapter, candidates=(candidate,)
        )
        receipt_blob = canonical_bytes(receipt.to_canonical())
        receipt_digest = digest(receipt.to_canonical())
        push(1, "budget_reserved", "discovery", {"reservationId": "rsv-s", "account": "W_search", "stage": "discovery"}, parents=("copy-run:run-started",))
        push(2, "proposal_succeeded", "discovery", {"requestId": "req-p", "reservationId": "rsv-s", "candidateIds": [candidate_id]}, parents=("copy-run:event-01",), blobs={receipt_digest: receipt_blob})
        push(3, "budget_committed", "discovery", {"reservationId": "rsv-s", "account": "W_search", "stage": "discovery"}, parents=("copy-run:event-02",))
        archive = {candidate_id: candidate.to_canonical()}
        archive_digest = digest({"schemaVersion": ARCHIVE_VIEW_SCHEMA_VERSION, "candidates": dict(archive)})
        push(4, "archive_changed", "discovery", {"candidateId": candidate_id, "archiveDigest": archive_digest, "coordinateCost": demo_coordinate_cost(candidate).to_canonical()}, parents=("copy-run:event-03",))
        push(5, "budget_reserved", "discovery", {"reservationId": "rsv-e", "account": "T_dec", "stage": "discovery"}, parents=("copy-run:event-04",))
        push(6, "evaluation_started", "discovery", {"requestId": "req-e", "reservationId": "rsv-e", "candidateId": candidate_id}, parents=("copy-run:event-05",))
        eval_receipt = evaluation_receipt(request_id="req-e", adapter=evaluation_adapter, candidate_id=candidate_id, metrics={"fit": 0.5})
        eval_digest = digest(eval_receipt.to_canonical())
        push(7, "evaluation_completed", "discovery", {"requestId": "req-e", "reservationId": "rsv-e", "candidateId": candidate_id}, parents=("copy-run:event-06",), blobs={eval_digest: canonical_bytes(eval_receipt.to_canonical())})
        push(8, "budget_committed", "discovery", {"reservationId": "rsv-e", "account": "T_dec", "stage": "discovery"}, parents=("copy-run:event-07",))
        if promote:
            push(9, "candidate_promoted", "discovery", {"candidateId": candidate_id}, parents=("copy-run:event-08",))
        shortlist = [candidate_id] if promote else []
        push(10 if promote else 9, "search_frozen", "freeze", {"archiveDigest": archive_digest, "shortlistCandidateIds": shortlist, "selectionRule": "fixture", "discoveryContextDigest": digest("ctx")}, parents=(f"copy-run:event-{9 if promote else 8:02d}",))
        push(11 if promote else 10, "confirmation_started", "confirmation", {"confirmationContextDigest": digest("ctx2"), "seed": "s"}, parents=(f"copy-run:event-{10 if promote else 9:02d}",))
        push(12 if promote else 11, "confirmation_completed", "confirmation", {"outcome": "confirmed" if promote else "no_confirmed_candidate", **({"candidateId": candidate_id} if promote else {})}, parents=(f"copy-run:event-{11 if promote else 10:02d}",))
        bundle.close(status="completed")
        try:
            materialize(root)
        except ValueError:
            # Corrupt streams may fail derivation during materialization;
            # verification must report that failure, not swallow it.
            pass

    def test_ordinary_candidate_copying_target_fails(self) -> None:
        tmp = fresh_tmpdir()
        root = tmp / "bundle"
        self.build_copy_bundle(root, role="candidate", promote=False)
        errors = errors_for(root)
        assert_has_error(self, errors, "unlogged target-copy fallback")

    def test_explicit_reconstruction_control_is_exempt(self) -> None:
        tmp = fresh_tmpdir()
        root = tmp / "bundle"
        self.build_copy_bundle(root, role="explicit_reconstruction", promote=False)
        report = verify_bundle(root)
        self.assertTrue(report.ok, report.errors)

    def test_promoting_explicit_reconstruction_fails(self) -> None:
        tmp = fresh_tmpdir()
        root = tmp / "bundle"
        self.build_copy_bundle(root, role="explicit_reconstruction", promote=True)
        errors = errors_for(root)
        assert_has_error(self, errors, "never promote an explicit_reconstruction")


class TestVerifierIndependence(unittest.TestCase):
    def test_verifier_does_not_import_scheduler(self) -> None:
        import pathlib

        source = (pathlib.Path(__file__).resolve().parents[1] / "verify.py").read_text(encoding="utf-8")
        self.assertNotIn("hybrid_pareto", source)
        self.assertNotIn("import mlx", source)
        self.assertNotIn("requests", source)


if __name__ == "__main__":
    unittest.main()
