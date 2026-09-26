from __future__ import annotations

import copy
import hashlib
import io
import json
import os
import tempfile
import threading
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path, PurePosixPath
from types import SimpleNamespace
from typing import Any, Callable
from unittest import mock

from bench.engine import kaggle_queue_once as queue
from bench.engine import kaggle_run_once as run_once
from bench.engine.kaggle_capture_evidence import KaggleCaptureEvidenceError


OWNER = "jahyee"
TASK = "aleph-bench-v0-2-capture-canary"
VERSION = 10
DATASET = "jahyee/aleph-bench-v02-scorer-conformance"
SOURCE_KERNEL_ID = 135410138
EXECUTION_COMMIT = "e" * 40
WRITER_ID = "aleph-test-writer"
NOW = datetime(2026, 9, 26, 12, 0, tzinfo=timezone.utc)
DAILY_REFILL = "2026-09-27T20:06:33.714000Z"
MONTHLY_REFILL = "2026-10-22T19:00:32.714000Z"
SOURCE_IDENTITY = {
    "path": "bench/tasks/kaggle/aleph_bench_v0_2_capture.py",
    "bytes": 1234,
    "sha256": "1" * 64,
    "notebookProfile": run_once.NOTEBOOK_IDENTITY_PROFILE,
    "notebookSha256": "2" * 64,
}


class HardStop(BaseException):
    """Synthetic process loss that bypasses controller exception handling."""


def _canonical_time(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _quota(
    *,
    daily_used: float = 0.10,
    monthly_used: float = 0.30,
    daily_refill: str = DAILY_REFILL,
    monthly_refill: str = MONTHLY_REFILL,
    daily_allowed: float = 10.0,
    monthly_allowed: float = 100.0,
) -> list[dict[str, Any]]:
    return [
        {
            "allowedUsd": daily_allowed,
            "period": "DAILY",
            "refillTime": daily_refill,
            "remainingUsd": daily_allowed - daily_used,
            "usedUsd": daily_used,
        },
        {
            "allowedUsd": monthly_allowed,
            "period": "MONTHLY",
            "refillTime": monthly_refill,
            "remainingUsd": monthly_allowed - monthly_used,
            "usedUsd": monthly_used,
        },
    ]


def _creation_journal_bytes(source: dict[str, Any]) -> bytes:
    journal = {
        "artifactKind": "kaggle_task_creation_dispatch",
        "client": {
            "jupytext": "1.19.5",
            "kaggle": "2.2.4",
            "kagglesdk": "0.1.37",
            "nbformat": "5.11.1",
            "python": "3.13.7",
        },
        "createdAt": "2026-09-25T13:02:00Z",
        "datasets": [DATASET],
        "failure": None,
        "gate": "six-call-capture",
        "journalVersion": run_once.CREATION_JOURNAL_VERSION,
        "operationId": "12345678-1234-4abc-8123-123456789abc",
        "remotePreflight": {
            "observedAt": "2026-09-25T13:02:00Z",
            "priorTask": None,
        },
        "response": {
            "creationState": (
                "BENCHMARK_TASK_VERSION_CREATION_STATE_COMPLETED"
            ),
            "datasets": [DATASET],
            "owner": OWNER,
            "sourceKernelId": SOURCE_KERNEL_ID,
            "task": TASK,
            "url": f"https://www.kaggle.com/benchmarks/{OWNER}/{TASK}/{VERSION}",
            "version": VERSION,
        },
        "source": {
            "bytes": source["bytes"],
            "notebookProfile": source["notebookProfile"],
            "notebookSha256": source["notebookSha256"],
            "path": "/reviewed/checkout/" + source["path"],
            "sha256": source["sha256"],
        },
        "state": "returned",
        "task": TASK,
        "updatedAt": "2026-09-25T13:02:01Z",
    }
    return run_once._canonical_json_bytes(journal)


def _write_policy(path: Path, value: dict[str, Any]) -> str:
    data = queue._pretty_canonical_json_bytes(value)
    path.write_bytes(data)
    return hashlib.sha256(data).hexdigest()


def _baseline_run() -> dict[str, Any]:
    return {
        "endTime": "2026-09-25T13:13:37Z",
        "errorMessage": None,
        "id": 3193338,
        "model": "gemini-3.7-flash",
        "startTime": "2026-09-25T13:13:17Z",
        "state": "BENCHMARK_TASK_RUN_STATE_COMPLETED",
    }


def _queue_run(
    run_id: int,
    model: str,
    *,
    state: str = "BENCHMARK_TASK_RUN_STATE_COMPLETED",
) -> dict[str, Any]:
    return {
        "endTime": (
            "2026-09-26T12:01:00Z"
            if state == "BENCHMARK_TASK_RUN_STATE_COMPLETED"
            else None
        ),
        "errorMessage": None,
        "id": run_id,
        "model": model,
        "startTime": "2026-09-26T12:00:00Z",
        "state": state,
    }


class QueueHarness:
    """One isolated private control root and externally pinned test policy."""

    def __init__(self) -> None:
        self._temporary = tempfile.TemporaryDirectory()
        self.workspace = Path(self._temporary.name)
        self.control_root = self.workspace / "control"
        self.control_root.mkdir(mode=0o700)
        self.control_root.chmod(0o700)
        activated_root = os.stat(self.control_root, follow_symlinks=False)
        self.control_device = activated_root.st_dev
        self.control_inode = activated_root.st_ino
        self.execution_root = self.workspace / "checkout"
        self.execution_root.mkdir()
        self.source = dict(SOURCE_IDENTITY)
        self.creation_bytes = _creation_journal_bytes(self.source)

        self.policy = json.loads(queue.POLICY_PATH.read_text(encoding="utf-8"))
        authority = self.policy["authority"]
        authority["captureSourceSha256"] = self.source["sha256"]
        authority["notebookSha256"] = self.source["notebookSha256"]
        authority["creationJournalSha256"] = hashlib.sha256(
            self.creation_bytes
        ).hexdigest()
        self.policy_path = self.workspace / "queue-policy.json"
        self.policy_sha = _write_policy(self.policy_path, self.policy)

        creation_relative = PurePosixPath(
            self.policy["evidenceLayout"]["creationJournalRelativePath"]
        )
        current_parent = self.control_root
        for part in creation_relative.parent.parts:
            current_parent /= part
            current_parent.mkdir(mode=0o700)
            current_parent.chmod(0o700)
        creation_path = self.control_root.joinpath(*creation_relative.parts)
        creation_path.write_bytes(self.creation_bytes)
        creation_path.chmod(0o600)
        self.creation_path = creation_path

        verified = run_once.verify_creation_authority_bytes(
            self.creation_bytes,
            expected_owner=OWNER,
            expected_task=TASK,
            expected_version=VERSION,
            current_source=self.source,
        )
        self.task_record = {
            "creationState": "BENCHMARK_TASK_VERSION_CREATION_STATE_COMPLETED",
            "datasets": [DATASET],
            "owner": OWNER,
            "sourceKernelId": SOURCE_KERNEL_ID,
            "task": TASK,
            "url": f"https://www.kaggle.com/benchmarks/{OWNER}/{TASK}/{VERSION}",
            "version": VERSION,
        }
        self.creation_binding = run_once.bind_creation_authority(
            verified, task_record=self.task_record
        )
        self.live_run_states: dict[int, str] = {}
        self.extra_live_runs: list[dict[str, Any]] = []

    def close(self) -> None:
        self._temporary.cleanup()

    def __enter__(self) -> QueueHarness:
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()

    def execution_verifier(
        self, root: Path, *, expected_commit: str
    ) -> dict[str, str]:
        if root != self.execution_root or expected_commit != EXECUTION_COMMIT:
            raise AssertionError("unexpected execution authority")
        return {
            "commit": EXECUTION_COMMIT,
            "repositoryRoot": str(root.resolve()),
        }

    def entry(self, model: str) -> dict[str, Any]:
        return next(
            item for item in self.policy["queue"] if item["modelVersionSlug"] == model
        )

    def set_live_run_state(self, run_id: int, state: str) -> None:
        self.live_run_states[run_id] = state

    def run_set_reader(self, **kwargs: Any) -> list[dict[str, Any]]:
        """Return a read-only live view derived from durable local journals."""

        if kwargs != {"owner": OWNER, "task": TASK, "version": VERSION}:
            raise AssertionError("unexpected live run-set authority")
        runs = [_baseline_run()]
        for entry in self.policy["queue"]:
            journal_path = self.control_root / entry["journalRelativePath"]
            if not journal_path.is_file():
                continue
            journal = json.loads(journal_path.read_bytes())
            run = journal.get("reconciliation", {}).get("run")
            if not isinstance(run, dict):
                continue
            state = self.live_run_states.get(run["id"], run["state"])
            live = _queue_run(run["id"], run["model"], state=state)
            if state == "BENCHMARK_TASK_RUN_STATE_ERRORED":
                live["endTime"] = "2026-09-26T12:01:00Z"
                live["errorMessage"] = "synthetic provider failure"
            runs.append(live)
        runs.extend(copy.deepcopy(self.extra_live_runs))
        return runs

    def snapshot(
        self,
        entry: dict[str, Any],
        *,
        runs: list[dict[str, Any]] | None = None,
        quota: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        return {
            "client": {
                "jupytext": "1.19.5",
                "kaggle": "2.2.4",
                "kagglesdk": "0.1.37",
                "nbformat": "5.11.1",
                "python": "3.13.7",
            },
            "creationAuthority": copy.deepcopy(self.creation_binding),
            "model": {
                "allowModelProxy": entry["allowModelProxy"],
                "benchmarkModelId": entry["modelId"],
                "benchmarkModelVersionId": entry["modelVersionId"],
                "deprecatedAt": entry["deprecatedAt"],
                "displayName": "Synthetic exact catalog record",
                "isDefault": entry["isDefault"],
                "modelProxySlug": entry["modelProxySlug"],
                "parentPublished": entry["parentPublished"],
                "slug": entry["modelVersionSlug"],
                "versionPublished": entry["versionPublished"],
            },
            "quota": copy.deepcopy(quota if quota is not None else _quota()),
            "runs": copy.deepcopy(runs if runs is not None else [_baseline_run()]),
            "source": copy.deepcopy(self.source),
            "task": copy.deepcopy(self.task_record),
        }

    def invoke(
        self,
        *,
        dispatcher: Callable[..., dict[str, Any]],
        now: Callable[[], datetime] = lambda: NOW,
        quota_reader: Callable[[], list[dict[str, Any]]] = lambda: _quota(),
        run_set_reader: Callable[..., list[dict[str, Any]]] | None = None,
    ) -> dict[str, Any]:
        # Production binds the imported modules and checked-in policy to the
        # activated Git checkout. These unit fixtures intentionally use a
        # temporary policy whose source/creation digests match synthetic bytes,
        # so isolate only that path-origin assertion here; all policy bytes,
        # digest, source, receipt, control-root, and execution bindings still
        # run through the real controller.
        with mock.patch.object(
            queue,
            "_verify_loaded_authority_paths",
            return_value=self.execution_root,
        ):
            return self.invoke_without_path_patch(
                dispatcher=dispatcher,
                now=now,
                quota_reader=quota_reader,
                run_set_reader=run_set_reader,
            )

    def invoke_without_path_patch(
        self,
        *,
        dispatcher: Callable[..., dict[str, Any]],
        now: Callable[[], datetime] = lambda: NOW,
        quota_reader: Callable[[], list[dict[str, Any]]] = lambda: _quota(),
        run_set_reader: Callable[..., list[dict[str, Any]]] | None = None,
        expected_control_device: int | None = None,
        expected_control_inode: int | None = None,
    ) -> dict[str, Any]:
        """Run with authority-path patch ownership delegated to the caller."""

        return queue.run_queue_once(
            control_root=self.control_root,
            expected_control_device=(
                self.control_device
                if expected_control_device is None
                else expected_control_device
            ),
            expected_control_inode=(
                self.control_inode
                if expected_control_inode is None
                else expected_control_inode
            ),
            writer_id=WRITER_ID,
            expected_policy_sha256=self.policy_sha,
            expected_execution_commit=EXECUTION_COMMIT,
            execution_root=self.execution_root,
            policy_path=self.policy_path,
            now=now,
            execution_verifier=self.execution_verifier,
            source_reader=lambda: dict(self.source),
            run_set_reader=(
                self.run_set_reader
                if run_set_reader is None
                else run_set_reader
            ),
            quota_reader=quota_reader,
            dispatcher=dispatcher,
        )


class FakeDispatcher:
    """Exercise the real queue guard while replacing only the remote scheduler."""

    def __init__(
        self,
        harness: QueueHarness,
        *,
        snapshot_mutator: Callable[[dict[str, Any]], None] | None = None,
        runs: list[dict[str, Any]] | None = None,
        quota: list[dict[str, Any]] | None = None,
        mode: str = "reconciled",
        run_id: int = 4100001,
        decision_ready: threading.Event | None = None,
        release_paid_post: threading.Event | None = None,
        quota_after_failure: bool = False,
    ) -> None:
        self.harness = harness
        self.snapshot_mutator = snapshot_mutator
        self.runs = runs
        self.quota = quota
        self.mode = mode
        self.run_id = run_id
        self.decision_ready = decision_ready
        self.release_paid_post = release_paid_post
        self.quota_after_failure = quota_after_failure
        self.delegate_calls = 0
        self.paid_posts = 0

    def __call__(self, **kwargs: Any) -> dict[str, Any]:
        self.delegate_calls += 1
        entry = self.harness.entry(kwargs["model"])
        anchored = kwargs.get("anchored_paths")
        if not isinstance(anchored, run_once.AnchoredDispatchPaths):
            raise AssertionError("queue did not provide anchored scheduler paths")
        opened_root = os.fstat(anchored.control_root_fd)
        if (
            anchored.control_root != self.harness.control_root
            or anchored.expected_control_device != self.harness.control_device
            or anchored.expected_control_inode != self.harness.control_inode
            or opened_root.st_dev != self.harness.control_device
            or opened_root.st_ino != self.harness.control_inode
            or anchored.creation_journal_relative_path
            != PurePosixPath(
                self.harness.policy["evidenceLayout"][
                    "creationJournalRelativePath"
                ]
            )
            or anchored.journal_relative_path
            != PurePosixPath(entry["journalRelativePath"])
        ):
            raise AssertionError("queue anchored scheduler authority drifted")
        snapshot = self.harness.snapshot(
            entry, runs=self.runs, quota=self.quota
        )
        if self.snapshot_mutator is not None:
            self.snapshot_mutator(snapshot)
        authorization = kwargs["pre_dispatch_guard"](snapshot)
        if self.decision_ready is not None:
            self.decision_ready.set()
        if self.release_paid_post is not None:
            if not self.release_paid_post.wait(timeout=5):
                raise AssertionError("timed out waiting to cross the paid boundary")
        if self.mode == "hard-stop-after-decision":
            raise HardStop("process lost after durable decision")

        self.paid_posts += 1
        state = "reconciled" if self.mode == "reconciled" else "ambiguous"
        run_state = "BENCHMARK_TASK_RUN_STATE_QUEUED"
        new_run = _queue_run(self.run_id, entry["modelVersionSlug"], state=run_state)
        observed_runs = [*snapshot["runs"], new_run]
        journal = {
            "artifactKind": "kaggle_benchmark_run_dispatch",
            "client": copy.deepcopy(snapshot["client"]),
            "creationAuthority": copy.deepcopy(snapshot["creationAuthority"]),
            "createdAt": _canonical_time(NOW),
            "dispatchAuthorization": copy.deepcopy(authorization),
            "dispatchFailure": None,
            "failure": (
                None
                if state == "reconciled"
                else {"message": "synthetic ambiguity", "type": "RunNotObserved"}
            ),
            "journalVersion": 2,
            "operationId": "12345678-1234-4abc-8123-123456789abd",
            "quotaAfter": (
                None
                if self.quota_after_failure
                else copy.deepcopy(snapshot["quota"])
            ),
            "reconciliation": {
                "observations": [
                    {
                        "attempt": 1,
                        "delaySeconds": 0.0,
                        "newRuns": [copy.deepcopy(new_run)],
                        "observedAt": _canonical_time(NOW),
                        "runIds": [item["id"] for item in observed_runs],
                    }
                ],
                "run": copy.deepcopy(new_run) if state == "reconciled" else None,
            },
            "remotePreflight": {
                "model": copy.deepcopy(snapshot["model"]),
                "observedAt": _canonical_time(NOW),
                "quota": copy.deepcopy(snapshot["quota"]),
                "runs": copy.deepcopy(snapshot["runs"]),
                "task": copy.deepcopy(snapshot["task"]),
            },
            "response": {
                "benchmarkModelVersionId": entry["modelVersionId"],
                "benchmarkTaskVersionId": 901,
                "parentTaskVersionId": None,
                "runScheduled": True,
                "runSkippedReason": None,
            },
            "responseFailure": None,
            "state": state,
            "target": {
                "model": entry["modelVersionSlug"],
                "owner": OWNER,
                "task": TASK,
                "version": VERSION,
            },
            "updatedAt": _canonical_time(NOW),
        }
        if self.quota_after_failure:
            journal["quotaAfterFailure"] = {
                "message": "synthetic immediate quota read failure",
                "type": "ConnectionError",
            }
        journal_path = Path(kwargs["journal_path"])
        journal_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        journal_path.parent.chmod(0o700)
        journal_path.write_bytes(run_once._canonical_json_bytes(journal))
        journal_path.chmod(0o600)
        if self.mode == "hard-stop-after-journal":
            raise HardStop("process lost after ambiguous journal")
        return journal


def _fake_bundle(
    harness: QueueHarness,
    *,
    entry: dict[str, Any],
    run_id: int,
    journal_bytes: bytes,
) -> SimpleNamespace:
    evidence_path = (
        harness.control_root
        / entry["bundleDirectory"]
        / f"{TASK}-v{VERSION}-run-{run_id}-evidence.json"
    )
    return SimpleNamespace(
        archive_bytes=b"archive",
        dispatch_journal_bytes=journal_bytes,
        evidence={
            "assemblyEligible": True,
            "id": "aleph-bench-kaggle-capture-evidence-v1-artifact-" + "a" * 64,
            "leaderboardEligible": False,
            "publicationEligible": False,
            "run": {
                "id": run_id,
                "modelVersionSlug": entry["modelVersionSlug"],
                "state": "BENCHMARK_TASK_RUN_STATE_COMPLETED",
            },
            "task": {
                "datasets": [DATASET],
                "owner": OWNER,
                "slug": TASK,
                "sourceKernelId": SOURCE_KERNEL_ID,
                "version": VERSION,
            },
        },
        evidence_bytes=b"evidence",
        evidence_path=evidence_path,
        payload={"canonicalReplayEligible": True, "captureComplete": True},
        payload_bytes=b"payload",
        source_bytes=b"source",
    )


def _publish_fake_evidence_marker(bundle: SimpleNamespace) -> None:
    bundle.evidence_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    bundle.evidence_path.parent.chmod(0o700)
    bundle.evidence_path.write_bytes(b"placeholder evidence envelope")
    bundle.evidence_path.chmod(0o600)


class KaggleQueuePolicyTests(unittest.TestCase):
    def test_checked_in_policy_is_canonical_and_digest_pinned(self) -> None:
        data = queue.POLICY_PATH.read_bytes()
        loaded = queue.load_queue_policy(
            queue.POLICY_PATH,
            expected_sha256=hashlib.sha256(data).hexdigest(),
        )
        self.assertEqual(loaded.raw_bytes, data)
        self.assertEqual(loaded.value["authority"]["creationRunId"], 3193338)
        self.assertEqual(len(loaded.value["queue"]), 6)

        with self.assertRaisesRegex(queue.KaggleQueueError, "differs"):
            queue.load_queue_policy(
                queue.POLICY_PATH, expected_sha256="0" * 64
            )

    def test_policy_rejects_noncanonical_duplicate_and_nonfinite_json(self) -> None:
        cases = {
            "noncanonical": json.dumps(
                json.loads(queue.POLICY_PATH.read_text(encoding="utf-8")),
                ensure_ascii=True,
                separators=(",", ":"),
                sort_keys=True,
            ).encode("ascii"),
            "duplicate": b'{"artifactKind":"a","artifactKind":"b"}',
            "nonfinite": b'{"value":NaN}',
        }
        for name, data in cases.items():
            with self.subTest(name=name), tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / "policy.json"
                path.write_bytes(data)
                with self.assertRaises(queue.KaggleQueueError):
                    queue.load_queue_policy(
                        path, expected_sha256=hashlib.sha256(data).hexdigest()
                    )

    def test_policy_semantic_mutations_fail_closed(self) -> None:
        base = json.loads(queue.POLICY_PATH.read_text(encoding="utf-8"))

        def add_field(value: dict[str, Any]) -> None:
            value["unexpected"] = True

        def enable_score(value: dict[str, Any]) -> None:
            value["fixedEligibility"]["scoreEligible"] = True

        def change_initial_model(value: dict[str, Any]) -> None:
            value["authority"]["expectedInitialRuns"][0][
                "modelVersionSlug"
            ] = "other-model"

        def enable_retry(value: dict[str, Any]) -> None:
            value["captureContract"]["maxTransportRetries"] = 1

        def reorder(value: dict[str, Any]) -> None:
            value["queue"][0]["order"] = 2

        def include_excluded(value: dict[str, Any]) -> None:
            value["queue"][0]["modelVersionSlug"] = "gemini-3.7-flash"

        def duplicate_path(value: dict[str, Any]) -> None:
            value["queue"][1]["decisionRelativePath"] = value["queue"][0][
                "decisionRelativePath"
            ]

        mutations = {
            "extra-field": add_field,
            "score-boundary": enable_score,
            "initial-run": change_initial_model,
            "paid-retry": enable_retry,
            "queue-order": reorder,
            "excluded-model": include_excluded,
            "duplicate-path": duplicate_path,
        }
        for name, mutate in mutations.items():
            with self.subTest(name=name), tempfile.TemporaryDirectory() as tmp:
                value = copy.deepcopy(base)
                mutate(value)
                path = Path(tmp) / "policy.json"
                digest = _write_policy(path, value)
                with self.assertRaises(queue.KaggleQueueError):
                    queue.load_queue_policy(path, expected_sha256=digest)

    def test_loaded_authority_paths_reject_a_claimed_temporary_checkout(self) -> None:
        repository_root = Path(queue.__file__).resolve().parents[2]
        self.assertEqual(
            queue._verify_loaded_authority_paths(
                repository_root, policy_path=queue.POLICY_PATH
            ),
            repository_root,
        )

        with tempfile.TemporaryDirectory() as tmp:
            claimed_root = Path(tmp) / "claimed-checkout"
            claimed_policy = (
                claimed_root / "bench/config/kaggle-capture-queue-v1.json"
            )
            claimed_policy.parent.mkdir(parents=True)
            claimed_policy.write_bytes(queue.POLICY_PATH.read_bytes())
            with self.assertRaisesRegex(
                queue.KaggleQueueError, "not from the claimed checkout"
            ):
                # This test deliberately exercises the real origin check: the
                # loaded controller functions still come from repository_root.
                queue._verify_loaded_authority_paths(
                    claimed_root, policy_path=claimed_policy
                )


class KaggleQueueDispatchTests(unittest.TestCase):
    def test_first_entry_dispatches_once_and_binds_decision_to_journal(self) -> None:
        with QueueHarness() as harness:
            dispatcher = FakeDispatcher(harness)
            quota_reader = mock.Mock(side_effect=AssertionError("not needed"))
            result = harness.invoke(
                dispatcher=dispatcher, quota_reader=quota_reader
            )

            self.assertEqual(result["status"], "dispatched")
            self.assertEqual(
                result["selected"],
                {"modelVersionSlug": "grok-4.20-0309-non-reasoning", "order": 1},
            )
            self.assertEqual(dispatcher.delegate_calls, 1)
            self.assertEqual(dispatcher.paid_posts, 1)
            quota_reader.assert_not_called()

            entry = harness.policy["queue"][0]
            decision_path = harness.control_root / entry["decisionRelativePath"]
            journal_path = harness.control_root / entry["journalRelativePath"]
            decision_bytes = decision_path.read_bytes()
            journal = json.loads(journal_path.read_text(encoding="utf-8"))
            authorization = journal["dispatchAuthorization"]
            self.assertEqual(
                authorization["decision"]["sha256"],
                hashlib.sha256(decision_bytes).hexdigest(),
            )
            self.assertEqual(
                authorization["decision"]["relativePath"],
                entry["decisionRelativePath"],
            )
            self.assertEqual(journal["remotePreflight"]["runs"], [_baseline_run()])

    def test_reconciled_journal_quota_read_failure_has_one_strict_shape(self) -> None:
        with QueueHarness() as harness:
            dispatcher = FakeDispatcher(harness, quota_after_failure=True)
            result = harness.invoke(dispatcher=dispatcher)
            self.assertEqual(result["status"], "dispatched")
            self.assertEqual(dispatcher.paid_posts, 1)
            self.assertFalse(
                (harness.control_root / queue._BREAKER_PATH).exists()
            )

            entry = harness.policy["queue"][0]
            policy = queue.load_queue_policy(
                harness.policy_path, expected_sha256=harness.policy_sha
            )
            decision_path = harness.control_root / entry["decisionRelativePath"]
            journal_path = harness.control_root / entry["journalRelativePath"]
            decision_bytes = decision_path.read_bytes()
            decision = json.loads(decision_bytes)
            valid = json.loads(journal_path.read_bytes())

            def validate(value: dict[str, Any]) -> dict[str, Any]:
                data = run_once._canonical_json_bytes(value)
                return queue._validate_journal_for_entry(
                    value,
                    data=data,
                    policy=policy,
                    entry=entry,
                    decision_path=PurePosixPath(
                        entry["decisionRelativePath"]
                    ),
                    decision_bytes=decision_bytes,
                    decision=decision,
                    execution_commit=EXECUTION_COMMIT,
                )

            self.assertEqual(validate(valid)["id"], 4100001)

            normal = copy.deepcopy(valid)
            normal["quotaAfter"] = _quota()
            normal.pop("quotaAfterFailure")
            invalid = {
                "quota-and-failure": {
                    **copy.deepcopy(normal),
                    "quotaAfterFailure": copy.deepcopy(
                        valid["quotaAfterFailure"]
                    ),
                },
                "null-without-failure": {
                    key: copy.deepcopy(value)
                    for key, value in valid.items()
                    if key != "quotaAfterFailure"
                },
                "failure-with-extra-member": {
                    **copy.deepcopy(valid),
                    "quotaAfterFailure": {
                        **copy.deepcopy(valid["quotaAfterFailure"]),
                        "retryable": True,
                    },
                },
                "extra-root-member": {
                    **copy.deepcopy(valid),
                    "quotaAfterReadAttempt": 1,
                },
            }
            for name, journal in invalid.items():
                with self.subTest(name=name), self.assertRaisesRegex(
                    queue.KaggleQueueBreaker,
                    "invalid fields|quota-after failure",
                ):
                    validate(journal)

    def test_same_root_concurrent_invocation_is_held_before_paid_post(self) -> None:
        with QueueHarness() as harness:
            decision_ready = threading.Event()
            release_paid_post = threading.Event()
            first = FakeDispatcher(
                harness,
                decision_ready=decision_ready,
                release_paid_post=release_paid_post,
            )
            second = FakeDispatcher(harness, run_id=4100002)
            first_results: list[dict[str, Any]] = []
            first_errors: list[BaseException] = []

            def run_first() -> None:
                try:
                    first_results.append(
                        harness.invoke_without_path_patch(dispatcher=first)
                    )
                except BaseException as exc:  # pragma: no cover - asserted below
                    first_errors.append(exc)

            with mock.patch.object(
                queue,
                "_verify_loaded_authority_paths",
                return_value=harness.execution_root,
            ):
                worker = threading.Thread(target=run_first, daemon=True)
                worker.start()
                self.assertTrue(
                    decision_ready.wait(timeout=5),
                    "first invocation never durably wrote its decision",
                )
                try:
                    competing = harness.invoke_without_path_patch(
                        dispatcher=second
                    )
                finally:
                    release_paid_post.set()
                    worker.join(timeout=5)

            self.assertFalse(worker.is_alive())
            self.assertEqual(first_errors, [])
            self.assertEqual(first_results[0]["status"], "dispatched")
            self.assertEqual(first.paid_posts, 1)
            self.assertEqual(competing["status"], "held")
            self.assertLessEqual(second.delegate_calls, 1)
            self.assertEqual(second.paid_posts, 0)
            self.assertFalse(
                (harness.control_root / queue._BREAKER_PATH).exists()
            )

    def test_lock_mode_drift_cannot_publish_breaker_around_active_paid_post(
        self,
    ) -> None:
        with QueueHarness() as harness:
            decision_ready = threading.Event()
            release_paid_post = threading.Event()
            first = FakeDispatcher(
                harness,
                decision_ready=decision_ready,
                release_paid_post=release_paid_post,
            )
            contender = FakeDispatcher(harness, run_id=4100002)
            first_results: list[dict[str, Any]] = []
            first_errors: list[BaseException] = []

            def run_first() -> None:
                try:
                    first_results.append(
                        harness.invoke_without_path_patch(dispatcher=first)
                    )
                except BaseException as exc:  # pragma: no cover - asserted below
                    first_errors.append(exc)

            with mock.patch.object(
                queue,
                "_verify_loaded_authority_paths",
                return_value=harness.execution_root,
            ):
                worker = threading.Thread(target=run_first, daemon=True)
                worker.start()
                self.assertTrue(
                    decision_ready.wait(timeout=5),
                    "first invocation never durably wrote its decision",
                )
                lock_path = harness.control_root / queue._LOCK_PATH
                lock_path.chmod(0o644)
                try:
                    competing = harness.invoke_without_path_patch(
                        dispatcher=contender
                    )
                    self.assertEqual(competing["status"], "held")
                    self.assertFalse(
                        (harness.control_root / queue._BREAKER_PATH).exists()
                    )
                finally:
                    release_paid_post.set()
                    worker.join(timeout=5)

                breaker_dispatcher = FakeDispatcher(harness, run_id=4100003)
                broken = harness.invoke_without_path_patch(
                    dispatcher=breaker_dispatcher
                )

            self.assertFalse(worker.is_alive())
            self.assertEqual(first_errors, [])
            self.assertEqual(first_results[0]["status"], "dispatched")
            self.assertEqual(first.paid_posts, 1)
            self.assertEqual(contender.paid_posts, 0)
            self.assertEqual(broken["status"], "breaker")
            self.assertIn("queue lock preflight failed closed", broken["reason"])
            self.assertEqual(breaker_dispatcher.paid_posts, 0)

    def test_lock_inode_replacement_cannot_split_the_active_lease(self) -> None:
        with QueueHarness() as harness:
            decision_ready = threading.Event()
            release_paid_post = threading.Event()
            first = FakeDispatcher(
                harness,
                decision_ready=decision_ready,
                release_paid_post=release_paid_post,
            )
            contender = FakeDispatcher(harness, run_id=4100002)
            first_results: list[dict[str, Any]] = []
            first_errors: list[BaseException] = []

            def run_first() -> None:
                try:
                    first_results.append(
                        harness.invoke_without_path_patch(dispatcher=first)
                    )
                except BaseException as exc:  # pragma: no cover - asserted below
                    first_errors.append(exc)

            with mock.patch.object(
                queue,
                "_verify_loaded_authority_paths",
                return_value=harness.execution_root,
            ):
                worker = threading.Thread(target=run_first, daemon=True)
                worker.start()
                self.assertTrue(
                    decision_ready.wait(timeout=5),
                    "first invocation never durably wrote its decision",
                )
                lock_path = harness.control_root / queue._LOCK_PATH
                displaced_lock = harness.control_root / ".displaced-queue-lock"
                lock_path.rename(displaced_lock)
                lock_path.write_bytes(b"replacement lock inode\n")
                lock_path.chmod(0o600)
                try:
                    competing = harness.invoke_without_path_patch(
                        dispatcher=contender
                    )
                    self.assertEqual(competing["status"], "held")
                    self.assertFalse(
                        (harness.control_root / queue._BREAKER_PATH).exists()
                    )
                finally:
                    release_paid_post.set()
                    worker.join(timeout=5)

                breaker_dispatcher = FakeDispatcher(harness, run_id=4100003)
                broken = harness.invoke_without_path_patch(
                    dispatcher=breaker_dispatcher
                )

            self.assertFalse(worker.is_alive())
            self.assertEqual(first_errors, [])
            self.assertEqual(first_results[0]["status"], "dispatched")
            self.assertEqual(first.paid_posts, 1)
            self.assertEqual(contender.paid_posts, 0)
            self.assertEqual(broken["status"], "breaker")
            self.assertIn("control-root sentinel drifted", broken["reason"])
            self.assertEqual(breaker_dispatcher.paid_posts, 0)

    def test_control_root_path_replacement_cannot_start_a_second_paid_post(
        self,
    ) -> None:
        with QueueHarness() as harness:
            decision_ready = threading.Event()
            release_paid_post = threading.Event()
            first = FakeDispatcher(
                harness,
                decision_ready=decision_ready,
                release_paid_post=release_paid_post,
            )
            contender = FakeDispatcher(harness, run_id=4100002)
            first_results: list[dict[str, Any]] = []
            first_errors: list[BaseException] = []

            def run_first() -> None:
                try:
                    first_results.append(
                        harness.invoke_without_path_patch(dispatcher=first)
                    )
                except BaseException as exc:  # pragma: no cover - asserted below
                    first_errors.append(exc)

            with mock.patch.object(
                queue,
                "_verify_loaded_authority_paths",
                return_value=harness.execution_root,
            ):
                worker = threading.Thread(target=run_first, daemon=True)
                worker.start()
                self.assertTrue(
                    decision_ready.wait(timeout=5),
                    "first invocation never durably wrote its decision",
                )

                displaced_root = harness.workspace / "control-displaced"
                harness.control_root.rename(displaced_root)
                harness.control_root.mkdir(mode=0o700)
                harness.control_root.chmod(0o700)
                replacement_relative = PurePosixPath(
                    harness.policy["evidenceLayout"][
                        "creationJournalRelativePath"
                    ]
                )
                replacement_parent = harness.control_root
                for part in replacement_relative.parent.parts:
                    replacement_parent /= part
                    replacement_parent.mkdir(mode=0o700)
                    replacement_parent.chmod(0o700)
                replacement_creation = harness.control_root.joinpath(
                    *replacement_relative.parts
                )
                replacement_creation.write_bytes(harness.creation_bytes)
                replacement_creation.chmod(0o600)

                with self.assertRaises(queue.KaggleControlRootDrift):
                    harness.invoke_without_path_patch(dispatcher=contender)
                self.assertEqual(contender.delegate_calls, 0)
                self.assertEqual(contender.paid_posts, 0)
                self.assertFalse(
                    (harness.control_root / queue._BREAKER_PATH).exists()
                )

                release_paid_post.set()
                worker.join(timeout=5)

            self.assertFalse(worker.is_alive())
            self.assertEqual(first_results, [])
            self.assertEqual(len(first_errors), 1)
            self.assertIsInstance(
                first_errors[0], queue.KaggleControlRootDrift
            )
            self.assertEqual(first.paid_posts, 1)
            self.assertEqual(first.paid_posts + contender.paid_posts, 1)
            self.assertFalse(
                (harness.control_root / queue._BREAKER_PATH).exists()
            )

    def test_wrong_activation_pin_fails_before_reads_or_paid_post(self) -> None:
        with QueueHarness() as harness:
            dispatcher = FakeDispatcher(harness)
            with mock.patch.object(
                queue,
                "_verify_loaded_authority_paths",
                return_value=harness.execution_root,
            ), self.assertRaises(queue.KaggleControlRootDrift):
                harness.invoke_without_path_patch(
                    dispatcher=dispatcher,
                    expected_control_inode=harness.control_inode + 1,
                )

            self.assertEqual(dispatcher.delegate_calls, 0)
            self.assertEqual(dispatcher.paid_posts, 0)
            self.assertFalse(
                (harness.control_root / queue._BREAKER_PATH).exists()
            )

    def test_creation_authority_intermediate_symlink_breaks_before_paid_post(
        self,
    ) -> None:
        with QueueHarness() as harness:
            creation_directory = harness.control_root / "creation"
            retained_directory = harness.control_root / "creation-retained"
            creation_directory.rename(retained_directory)
            creation_directory.symlink_to(retained_directory, target_is_directory=True)
            dispatcher = FakeDispatcher(harness)

            broken = harness.invoke(dispatcher=dispatcher)

            self.assertEqual(broken["status"], "breaker")
            self.assertIn("private control-root directory", broken["reason"])
            self.assertEqual(dispatcher.delegate_calls, 0)
            self.assertEqual(dispatcher.paid_posts, 0)
            self.assertTrue(
                (harness.control_root / queue._BREAKER_PATH).is_file()
            )

    def test_control_root_swap_between_validation_and_open_fails_closed(
        self,
    ) -> None:
        with QueueHarness() as harness:
            displaced_root = harness.workspace / "control-before-open"
            original = queue._pinned_control_root_identity
            swapped = False

            def swap_after_validation(
                root: Path, *, expected_device: int, expected_inode: int
            ) -> dict[str, Any]:
                nonlocal swapped
                observed = original(
                    root,
                    expected_device=expected_device,
                    expected_inode=expected_inode,
                )
                if not swapped:
                    swapped = True
                    root.rename(displaced_root)
                    root.mkdir(mode=0o700)
                    root.chmod(0o700)
                return observed

            with mock.patch.object(
                queue,
                "_pinned_control_root_identity",
                side_effect=swap_after_validation,
            ), self.assertRaises(queue.KaggleControlRootDrift):
                with queue._exclusive_queue_lock(
                    harness.control_root,
                    expected_device=harness.control_device,
                    expected_inode=harness.control_inode,
                ):
                    self.fail("replacement root must never acquire the lease")

    def test_malformed_lock_latches_one_breaker_without_paid_post(self) -> None:
        with QueueHarness() as harness:
            lock_path = harness.control_root / queue._LOCK_PATH
            lock_path.write_bytes(b"not a valid private queue lock\n")
            lock_path.chmod(0o644)
            first = FakeDispatcher(harness)

            broken = harness.invoke(dispatcher=first)

            self.assertEqual(broken["status"], "breaker")
            self.assertIn("queue lock preflight failed closed", broken["reason"])
            self.assertEqual(first.delegate_calls, 0)
            self.assertEqual(first.paid_posts, 0)
            breaker_path = harness.control_root / queue._BREAKER_PATH
            breaker_bytes = breaker_path.read_bytes()

            repeated_dispatcher = FakeDispatcher(harness, run_id=4100002)
            repeated = harness.invoke(dispatcher=repeated_dispatcher)

            self.assertEqual(repeated["status"], "breaker")
            self.assertEqual(repeated["reason"], broken["reason"])
            self.assertEqual(breaker_path.read_bytes(), breaker_bytes)
            self.assertEqual(repeated_dispatcher.delegate_calls, 0)
            self.assertEqual(repeated_dispatcher.paid_posts, 0)

    def test_hardlinked_lock_marker_latches_permanent_breaker(self) -> None:
        with QueueHarness() as harness:
            first = FakeDispatcher(harness)
            dispatched = harness.invoke(dispatcher=first)
            self.assertEqual(dispatched["status"], "dispatched")
            self.assertEqual(first.paid_posts, 1)

            lock_path = harness.control_root / queue._LOCK_PATH
            alias_path = harness.control_root / ".hardlinked-queue-lock"
            os.link(lock_path, alias_path)
            contender = FakeDispatcher(harness, run_id=4100002)
            broken = harness.invoke(dispatcher=contender)

            self.assertEqual(broken["status"], "breaker")
            self.assertIn("queue lock preflight failed closed", broken["reason"])
            self.assertEqual(contender.delegate_calls, 0)
            self.assertEqual(contender.paid_posts, 0)
            breaker_path = harness.control_root / queue._BREAKER_PATH
            breaker_bytes = breaker_path.read_bytes()

            alias_path.unlink()
            repeated = harness.invoke(
                dispatcher=FakeDispatcher(harness, run_id=4100003)
            )
            self.assertEqual(repeated["status"], "breaker")
            self.assertEqual(repeated["reason"], broken["reason"])
            self.assertEqual(breaker_path.read_bytes(), breaker_bytes)

    def test_nonregular_lock_markers_latch_permanent_breaker(self) -> None:
        for kind in ("symlink", "directory"):
            with self.subTest(kind=kind), QueueHarness() as harness:
                first = FakeDispatcher(harness)
                dispatched = harness.invoke(dispatcher=first)
                self.assertEqual(dispatched["status"], "dispatched")
                self.assertEqual(first.paid_posts, 1)

                lock_path = harness.control_root / queue._LOCK_PATH
                lock_path.unlink()
                if kind == "symlink":
                    lock_path.symlink_to(harness.creation_path)
                else:
                    lock_path.mkdir(mode=0o700)

                contender = FakeDispatcher(harness, run_id=4100002)
                broken = harness.invoke(dispatcher=contender)
                self.assertEqual(broken["status"], "breaker")
                self.assertIn(
                    "queue lock preflight failed closed", broken["reason"]
                )
                self.assertEqual(contender.delegate_calls, 0)
                self.assertEqual(contender.paid_posts, 0)
                self.assertTrue(
                    (harness.control_root / queue._BREAKER_PATH).is_file()
                )

    def test_main_reports_unpersistable_queue_error_without_traceback(self) -> None:
        stderr = io.StringIO()
        with (
            mock.patch.object(
                queue,
                "run_queue_once",
                side_effect=queue.KaggleQueueError("unsafe control root"),
            ),
            mock.patch("sys.stderr", stderr),
        ):
            status = queue.main(
                [
                    "--control-root",
                    "/tmp/unsafe-control-root",
                    "--expect-control-device",
                    "1",
                    "--expect-control-inode",
                    "1",
                    "--writer-id",
                    WRITER_ID,
                    "--expect-policy-sha256",
                    "f" * 64,
                    "--expect-execution-commit",
                    EXECUTION_COMMIT,
                    "--execution-root",
                    "/tmp/aleph-checkout",
                ]
            )

        self.assertEqual(status, 1)
        self.assertEqual(
            stderr.getvalue(),
            "Kaggle finite queue failed: unsafe control root\n",
        )

    def _assert_guard_rejects_without_paid_post(
        self, mutate: Callable[[dict[str, Any]], None]
    ) -> None:
        with QueueHarness() as harness:
            dispatcher = FakeDispatcher(harness, snapshot_mutator=mutate)
            result = harness.invoke(dispatcher=dispatcher)
            self.assertEqual(result["status"], "breaker")
            self.assertEqual(dispatcher.delegate_calls, 1)
            self.assertEqual(dispatcher.paid_posts, 0)
            self.assertTrue(
                (harness.control_root / queue._BREAKER_PATH).is_file()
            )

    def test_baseline_source_task_and_creation_drift_make_zero_paid_calls(self) -> None:
        mutations: dict[str, Callable[[dict[str, Any]], None]] = {
            "baseline-model": lambda value: value["runs"][0].update(
                {"model": "other-model"}
            ),
            "baseline-state": lambda value: value["runs"][0].update(
                {"state": "BENCHMARK_TASK_RUN_STATE_ERRORED"}
            ),
            "extra-run": lambda value: value["runs"].append(
                _queue_run(3193339, "other-model")
            ),
            "source": lambda value: value["source"].update(
                {"sha256": "f" * 64}
            ),
            "task": lambda value: value["task"].update(
                {"sourceKernelId": SOURCE_KERNEL_ID + 1}
            ),
            "creation": lambda value: value["creationAuthority"].update(
                {"canonicalSha256": "f" * 64}
            ),
        }
        for name, mutate in mutations.items():
            with self.subTest(name=name):
                self._assert_guard_rejects_without_paid_post(mutate)

    def test_catalog_field_drift_makes_zero_paid_calls(self) -> None:
        mutations: dict[str, Any] = {
            "benchmarkModelId": 999,
            "benchmarkModelVersionId": 999,
            "slug": "other-model",
            "modelProxySlug": "xai/other-model",
            "parentPublished": False,
            "versionPublished": False,
            "isDefault": False,
            "allowModelProxy": False,
            "deprecatedAt": "2026-09-26T00:00:00Z",
        }
        for field, replacement in mutations.items():
            with self.subTest(field=field):
                self._assert_guard_rejects_without_paid_post(
                    lambda value, field=field, replacement=replacement: value[
                        "model"
                    ].update({field: replacement})
                )

    def test_invalid_and_reserve_exhausted_quota_never_cross_paid_boundary(self) -> None:
        invalid_mutations: dict[str, Callable[[dict[str, Any]], None]] = {
            "missing-monthly": lambda value: value.update(
                {"quota": [value["quota"][0]]}
            ),
            "null-refill": lambda value: value["quota"][0].update(
                {"refillTime": None}
            ),
            "bad-arithmetic": lambda value: value["quota"][0].update(
                {"remainingUsd": 1.0}
            ),
            "stale-daily": lambda value: value["quota"][0].update(
                {"refillTime": _canonical_time(NOW)}
            ),
            "stale-monthly": lambda value: value["quota"][1].update(
                {"refillTime": _canonical_time(NOW)}
            ),
        }
        for name, mutate in invalid_mutations.items():
            with self.subTest(name=name):
                self._assert_guard_rejects_without_paid_post(mutate)

        with QueueHarness() as harness:
            dispatcher = FakeDispatcher(
                harness,
                quota=_quota(daily_used=7.76, monthly_used=0.30),
            )
            result = harness.invoke(dispatcher=dispatcher)
            self.assertEqual(result["status"], "held")
            self.assertIn("reserve", result["reason"])
            self.assertEqual(dispatcher.paid_posts, 0)
            self.assertFalse(
                (harness.control_root / queue._BREAKER_PATH).exists()
            )

    def test_run_set_transport_failure_holds_but_integrity_failure_breaks(self) -> None:
        def unavailable(**_kwargs: Any) -> list[dict[str, Any]]:
            raise run_once.KaggleReadUnavailable("synthetic transport failure")

        with QueueHarness() as harness:
            dispatcher = FakeDispatcher(harness)
            result = harness.invoke(
                dispatcher=dispatcher, run_set_reader=unavailable
            )
            self.assertEqual(result["status"], "held")
            self.assertEqual(dispatcher.paid_posts, 0)
            self.assertFalse(
                (harness.control_root / queue._BREAKER_PATH).exists()
            )

        def invalid(**_kwargs: Any) -> list[dict[str, Any]]:
            raise run_once.KaggleRunOnceError("duplicate run IDs")

        with QueueHarness() as harness:
            dispatcher = FakeDispatcher(harness)
            result = harness.invoke(
                dispatcher=dispatcher, run_set_reader=invalid
            )
            self.assertEqual(result["status"], "breaker")
            self.assertIn("integrity validation failed", result["reason"])
            self.assertEqual(dispatcher.paid_posts, 0)

    def test_expiry_is_exclusive_and_rechecked_inside_final_guard(self) -> None:
        expiry = datetime(2026, 10, 25, tzinfo=timezone.utc)
        with QueueHarness() as harness:
            dispatcher = FakeDispatcher(harness)
            result = harness.invoke(dispatcher=dispatcher, now=lambda: expiry)
            self.assertEqual(result["status"], "expired")
            self.assertEqual(dispatcher.delegate_calls, 0)
            self.assertEqual(dispatcher.paid_posts, 0)

        with QueueHarness() as harness:
            instants = iter([expiry - timedelta(seconds=1), expiry])
            dispatcher = FakeDispatcher(harness)
            result = harness.invoke(
                dispatcher=dispatcher, now=lambda: next(instants)
            )
            self.assertEqual(result["status"], "expired")
            self.assertIn("expired at the paid boundary", result["reason"])
            self.assertEqual(dispatcher.delegate_calls, 1)
            self.assertEqual(dispatcher.paid_posts, 0)


class KaggleQueueQuotaTests(unittest.TestCase):
    def test_quota_arithmetic_tolerates_float_noise_only_within_one_nanodollar(
        self,
    ) -> None:
        awkward = _quota(
            daily_allowed=1.0,
            daily_used=0.06636430000000004,
        )
        awkward[0]["remainingUsd"] = 0.9336357
        mapped = queue._quota_map(awkward, role="awkward Kaggle quota")
        self.assertEqual(mapped["DAILY"]["usedUsd"], 0.06636430000000004)

        drifted = copy.deepcopy(awkward)
        drifted[0]["remainingUsd"] = 0.933635702
        with self.assertRaisesRegex(queue.KaggleQueueError, "arithmetic"):
            queue._quota_map(drifted, role="drifted Kaggle quota")

    def test_refill_jitter_is_same_window_but_real_advance_is_new_window(self) -> None:
        before = _quota()[0]
        for suffix in ("713000Z", "715000Z"):
            with self.subTest(suffix=suffix):
                after = copy.deepcopy(before)
                after["refillTime"] = "2026-09-27T20:06:33." + suffix
                self.assertEqual(
                    queue._classify_refill(
                        before,
                        after,
                        period="DAILY",
                        before_observed_at=NOW,
                        after_observed_at=NOW + timedelta(minutes=1),
                    ),
                    "same_window_jitter_tolerated",
                )

        advanced = copy.deepcopy(before)
        advanced["refillTime"] = "2026-09-28T20:06:33.714000Z"
        advanced["usedUsd"] = 0.01
        advanced["remainingUsd"] = 9.99
        self.assertEqual(
            queue._classify_refill(
                before,
                advanced,
                period="DAILY",
                before_observed_at=NOW,
                after_observed_at=datetime(
                    2026, 9, 28, 12, 0, tzinfo=timezone.utc
                ),
            ),
            "advanced_window",
        )

        with self.assertRaisesRegex(queue.KaggleQueueBreaker, "prior DAILY"):
            queue._classify_refill(
                before,
                advanced,
                period="DAILY",
                before_observed_at=datetime(
                    2026, 9, 27, 20, 6, 33, 714000, tzinfo=timezone.utc
                ),
                after_observed_at=datetime(
                    2026, 9, 28, 12, 0, tzinfo=timezone.utc
                ),
            )

        ambiguous = copy.deepcopy(before)
        ambiguous["refillTime"] = "2026-09-27T20:06:34.714000Z"
        with self.assertRaisesRegex(queue.KaggleQueueBreaker, "coherent"):
            queue._classify_refill(
                before,
                ambiguous,
                period="DAILY",
                before_observed_at=NOW,
                after_observed_at=datetime(
                    2026, 9, 27, 20, 6, 34, tzinfo=timezone.utc
                ),
            )

    def test_monthly_refill_accepts_calendar_lengths_only_with_observed_reset(
        self,
    ) -> None:
        before = _quota()[1]
        before_boundary = datetime(
            2026, 10, 22, 19, 0, 32, 714000, tzinfo=timezone.utc
        )
        for days in (28, 29, 30, 31):
            with self.subTest(days=days):
                after = copy.deepcopy(before)
                after["refillTime"] = _canonical_time(
                    before_boundary + timedelta(days=days)
                )
                after["usedUsd"] = 0.01
                after["remainingUsd"] = 99.99
                self.assertEqual(
                    queue._classify_refill(
                        before,
                        after,
                        period="MONTHLY",
                        before_observed_at=NOW,
                        after_observed_at=before_boundary + timedelta(hours=1),
                    ),
                    "advanced_window",
                )

        no_reset = copy.deepcopy(before)
        no_reset["refillTime"] = _canonical_time(
            before_boundary + timedelta(days=30)
        )
        with self.assertRaisesRegex(queue.KaggleQueueBreaker, "usage reset"):
            queue._classify_refill(
                before,
                no_reset,
                period="MONTHLY",
                before_observed_at=NOW,
                after_observed_at=before_boundary + timedelta(hours=1),
            )

    def test_rolling_dispatch_limit_is_time_based_not_local_midnight(self) -> None:
        policy_data = queue.POLICY_PATH.read_bytes()
        policy = queue.load_queue_policy(
            queue.POLICY_PATH,
            expected_sha256=hashlib.sha256(policy_data).hexdigest(),
        )
        now = datetime(2026, 9, 27, 0, 30, tzinfo=timezone.utc)
        completed = []
        for index, created in enumerate(
            (
                now - timedelta(hours=3),
                now - timedelta(hours=2),
                now - timedelta(hours=1),
            )
        ):
            completed.append(
                SimpleNamespace(
                    decision={
                        "createdAt": _canonical_time(created),
                        "snapshot": {"quota": _quota(daily_used=0.10 + index * 0.01)},
                    },
                    entry=policy.value["queue"][index],
                    terminal={
                        "observedAt": _canonical_time(
                            created + timedelta(minutes=1)
                        ),
                        "quota": _quota(daily_used=0.11 + index * 0.01),
                    },
                )
            )
        with self.assertRaisesRegex(queue.KaggleQueueHeld, "rolling 24-hour"):
            queue._budget_record(
                policy=policy,
                entry=policy.value["queue"][3],
                completed=completed,
                quota=queue._quota_map(
                    _quota(daily_used=0.14), role="test quota"
                ),
                now=now,
            )

        budget = queue._budget_record(
            policy=policy,
            entry=policy.value["queue"][2],
            completed=completed[:2],
            quota=queue._quota_map(
                _quota(
                    daily_used=0.13,
                    daily_refill="2026-09-27T20:06:33.715000Z",
                    monthly_refill="2026-10-22T19:00:32.715000Z",
                ),
                role="test jitter quota",
            ),
            now=now,
        )
        self.assertEqual(budget["rollingDispatchCount"], 3)

    def test_terminal_quota_ignores_immediate_scheduler_read_and_is_strict(self) -> None:
        policy_data = queue.POLICY_PATH.read_bytes()
        policy = queue.load_queue_policy(
            queue.POLICY_PATH,
            expected_sha256=hashlib.sha256(policy_data).hexdigest(),
        )
        entry = policy.value["queue"][0]
        before = _quota()
        decision = {
            "createdAt": _canonical_time(NOW),
            "snapshot": {"quota": before},
        }
        journal = {
            "quotaAfter": copy.deepcopy(before),
            "reconciliation": {"run": {"id": 4100001}},
            "updatedAt": _canonical_time(NOW),
        }
        bundle = SimpleNamespace(evidence={"id": "evidence-id"}, evidence_bytes=b"e")
        terminal = queue._terminal_quota_value(
            observed_at=_canonical_time(NOW + timedelta(minutes=5)),
            quota=_quota(daily_used=0.11, monthly_used=0.31),
            policy=policy,
            entry=entry,
            decision=decision,
            decision_bytes=b"decision",
            journal=journal,
            journal_bytes=b"journal",
            bundle=bundle,
            writer_id=WRITER_ID,
            execution_commit=EXECUTION_COMMIT,
        )
        self.assertEqual(terminal["costUpperBound"]["conservativeUsd"], "0.01")
        self.assertNotEqual(
            terminal["quota"], journal["quotaAfter"],
            "terminal evidence must come from the independent quota read",
        )

        with self.assertRaisesRegex(queue.KaggleQueueBreaker, "breaker"):
            queue._terminal_quota_value(
                observed_at=_canonical_time(NOW + timedelta(minutes=5)),
                quota=_quota(daily_used=0.35, monthly_used=0.55),
                policy=policy,
                entry=entry,
                decision=decision,
                decision_bytes=b"decision",
                journal=journal,
                journal_bytes=b"journal",
                bundle=bundle,
                writer_id=WRITER_ID,
                execution_commit=EXECUTION_COMMIT,
            )


class KaggleQueueFinalizationAndBreakerTests(unittest.TestCase):
    def _prepare_first_dispatch(
        self, harness: QueueHarness
    ) -> tuple[FakeDispatcher, dict[str, Any], bytes]:
        dispatcher = FakeDispatcher(harness)
        result = harness.invoke(dispatcher=dispatcher)
        self.assertEqual(result["status"], "dispatched")
        entry = harness.policy["queue"][0]
        journal_path = harness.control_root / entry["journalRelativePath"]
        return dispatcher, entry, journal_path.read_bytes()

    def test_remote_queued_run_without_evidence_is_a_temporary_hold(self) -> None:
        with QueueHarness() as harness:
            self._prepare_first_dispatch(harness)
            replacement = FakeDispatcher(harness, run_id=4100002)

            result = harness.invoke(dispatcher=replacement)

            self.assertEqual(result["status"], "held")
            self.assertIn("awaiting terminal", result["reason"])
            self.assertEqual(replacement.delegate_calls, 0)
            self.assertEqual(replacement.paid_posts, 0)
            self.assertFalse(
                (harness.control_root / queue._BREAKER_PATH).exists()
            )

    def test_expiry_does_not_hide_a_queued_run(self) -> None:
        with QueueHarness() as harness:
            self._prepare_first_dispatch(harness)
            replacement = FakeDispatcher(harness, run_id=4100002)

            result = harness.invoke(
                dispatcher=replacement,
                now=lambda: datetime(2026, 10, 25, tzinfo=timezone.utc),
            )

            self.assertEqual(result["status"], "held")
            self.assertIn("awaiting terminal", result["reason"])
            self.assertEqual(replacement.delegate_calls, 0)
            self.assertEqual(replacement.paid_posts, 0)

    def test_remote_errored_run_without_evidence_latches_breaker(self) -> None:
        with QueueHarness() as harness:
            self._prepare_first_dispatch(harness)
            harness.set_live_run_state(
                4100001, "BENCHMARK_TASK_RUN_STATE_ERRORED"
            )
            replacement = FakeDispatcher(harness, run_id=4100002)

            result = harness.invoke(dispatcher=replacement)

            self.assertEqual(result["status"], "breaker")
            self.assertIn("provider error", result["reason"])
            self.assertEqual(replacement.delegate_calls, 0)
            self.assertEqual(replacement.paid_posts, 0)

    def test_expiry_does_not_hide_a_provider_error(self) -> None:
        with QueueHarness() as harness:
            self._prepare_first_dispatch(harness)
            harness.set_live_run_state(
                4100001, "BENCHMARK_TASK_RUN_STATE_ERRORED"
            )
            replacement = FakeDispatcher(harness, run_id=4100002)

            result = harness.invoke(
                dispatcher=replacement,
                now=lambda: datetime(2026, 10, 25, tzinfo=timezone.utc),
            )

            self.assertEqual(result["status"], "breaker")
            self.assertIn("provider error", result["reason"])
            self.assertEqual(replacement.delegate_calls, 0)
            self.assertEqual(replacement.paid_posts, 0)

    def test_remote_completed_run_without_evidence_latches_breaker(self) -> None:
        with QueueHarness() as harness:
            self._prepare_first_dispatch(harness)
            harness.set_live_run_state(
                4100001, "BENCHMARK_TASK_RUN_STATE_COMPLETED"
            )
            replacement = FakeDispatcher(harness, run_id=4100002)

            result = harness.invoke(dispatcher=replacement)

            self.assertEqual(result["status"], "breaker")
            self.assertIn("completed without complete Aleph evidence", result["reason"])
            self.assertEqual(replacement.delegate_calls, 0)
            self.assertEqual(replacement.paid_posts, 0)

    def test_expiry_does_not_hide_completed_run_missing_evidence(self) -> None:
        with QueueHarness() as harness:
            self._prepare_first_dispatch(harness)
            harness.set_live_run_state(
                4100001, "BENCHMARK_TASK_RUN_STATE_COMPLETED"
            )
            replacement = FakeDispatcher(harness, run_id=4100002)

            result = harness.invoke(
                dispatcher=replacement,
                now=lambda: datetime(2026, 10, 25, tzinfo=timezone.utc),
            )

            self.assertEqual(result["status"], "breaker")
            self.assertIn(
                "completed without complete Aleph evidence", result["reason"]
            )
            self.assertEqual(replacement.delegate_calls, 0)
            self.assertEqual(replacement.paid_posts, 0)

    def test_permanent_breaker_takes_precedence_after_policy_expiry(self) -> None:
        with QueueHarness() as harness:
            self._prepare_first_dispatch(harness)
            harness.set_live_run_state(
                4100001, "BENCHMARK_TASK_RUN_STATE_ERRORED"
            )
            replacement = FakeDispatcher(harness, run_id=4100002)
            broken = harness.invoke(dispatcher=replacement)
            self.assertEqual(broken["status"], "breaker")

            after_expiry = harness.invoke(
                dispatcher=FakeDispatcher(harness, run_id=4100003),
                now=lambda: datetime(2026, 10, 25, tzinfo=timezone.utc),
            )
            self.assertEqual(after_expiry["status"], "breaker")
            self.assertEqual(after_expiry["reason"], broken["reason"])

    def test_unexpected_remote_run_latches_breaker_before_dispatch(self) -> None:
        with QueueHarness() as harness:
            self._prepare_first_dispatch(harness)
            harness.extra_live_runs.append(
                _queue_run(
                    4999999,
                    "unexpected-model",
                    state="BENCHMARK_TASK_RUN_STATE_QUEUED",
                )
            )
            replacement = FakeDispatcher(harness, run_id=4100002)

            result = harness.invoke(dispatcher=replacement)

            self.assertEqual(result["status"], "breaker")
            self.assertIn("live exact Task run set drifted", result["reason"])
            self.assertIn('"expected"', result["reason"])
            self.assertIn('"observed"', result["reason"])
            self.assertIn("4999999", result["reason"])
            self.assertEqual(replacement.delegate_calls, 0)
            self.assertEqual(replacement.paid_posts, 0)

    def test_large_unexpected_run_set_retains_bounded_diagnostics(self) -> None:
        with QueueHarness() as harness:
            self._prepare_first_dispatch(harness)
            harness.extra_live_runs.extend(
                _queue_run(
                    5_000_000 + index,
                    f"unexpected-model-{index}",
                    state="BENCHMARK_TASK_RUN_STATE_QUEUED",
                )
                for index in range(250)
            )
            replacement = FakeDispatcher(harness, run_id=4100002)

            result = harness.invoke(dispatcher=replacement)

            self.assertEqual(result["status"], "breaker")
            self.assertIn("live exact Task run set drifted", result["reason"])
            self.assertIn('"count":252', result["reason"])
            self.assertIn('"sampleTruncated":true', result["reason"])
            self.assertIn('"sha256"', result["reason"])
            self.assertLess(len(result["reason"]), 4_000)
            self.assertEqual(replacement.delegate_calls, 0)
            self.assertEqual(replacement.paid_posts, 0)

    def test_second_completed_entry_reenters_with_full_durable_frontier(
        self,
    ) -> None:
        with QueueHarness() as harness:
            _first_dispatcher, first, first_journal_bytes = (
                self._prepare_first_dispatch(harness)
            )
            first_bundle = _fake_bundle(
                harness,
                entry=first,
                run_id=4100001,
                journal_bytes=first_journal_bytes,
            )
            _publish_fake_evidence_marker(first_bundle)
            harness.set_live_run_state(
                4100001, "BENCHMARK_TASK_RUN_STATE_COMPLETED"
            )

            second = harness.policy["queue"][1]
            first_completed_runs = [
                _baseline_run(),
                _queue_run(4100001, first["modelVersionSlug"]),
            ]
            second_dispatcher = FakeDispatcher(
                harness,
                runs=first_completed_runs,
                quota=_quota(daily_used=0.11, monthly_used=0.31),
                run_id=4100002,
            )
            bundles = {first_bundle.evidence_path: first_bundle}

            def load_bundle(path: Path) -> SimpleNamespace:
                return bundles[Path(path)]

            with mock.patch.object(
                queue, "load_verified_capture_bundle", side_effect=load_bundle
            ):
                second_result = harness.invoke(
                    dispatcher=second_dispatcher,
                    now=lambda: NOW + timedelta(seconds=1),
                    quota_reader=lambda: _quota(
                        daily_used=0.11, monthly_used=0.31
                    ),
                )

            self.assertEqual(
                second_result["status"], "dispatched", msg=second_result
            )
            self.assertEqual(second_result["completedEntries"], 1)
            self.assertEqual(
                second_result["selected"],
                {"modelVersionSlug": second["modelVersionSlug"], "order": 2},
            )
            self.assertEqual(second_dispatcher.paid_posts, 1)

            waiting_dispatcher = FakeDispatcher(harness, run_id=4100003)
            with mock.patch.object(
                queue, "load_verified_capture_bundle", side_effect=load_bundle
            ):
                waiting = harness.invoke(
                    dispatcher=waiting_dispatcher,
                    now=lambda: NOW + timedelta(seconds=2),
                )

            self.assertEqual(waiting["status"], "held", msg=waiting)
            self.assertEqual(waiting["completedEntries"], 1)
            self.assertIn("awaiting terminal", waiting["reason"])
            self.assertEqual(waiting_dispatcher.delegate_calls, 0)
            self.assertEqual(waiting_dispatcher.paid_posts, 0)
            self.assertFalse(
                (harness.control_root / queue._BREAKER_PATH).exists()
            )

            second_journal_path = (
                harness.control_root / second["journalRelativePath"]
            )
            second_bundle = _fake_bundle(
                harness,
                entry=second,
                run_id=4100002,
                journal_bytes=second_journal_path.read_bytes(),
            )
            _publish_fake_evidence_marker(second_bundle)
            bundles[second_bundle.evidence_path] = second_bundle
            harness.set_live_run_state(
                4100002, "BENCHMARK_TASK_RUN_STATE_COMPLETED"
            )

            third = harness.policy["queue"][2]
            two_completed_runs = [
                *first_completed_runs,
                _queue_run(4100002, second["modelVersionSlug"]),
            ]
            third_dispatcher = FakeDispatcher(
                harness,
                runs=two_completed_runs,
                quota=_quota(daily_used=0.12, monthly_used=0.32),
                run_id=4100003,
            )
            with mock.patch.object(
                queue, "load_verified_capture_bundle", side_effect=load_bundle
            ):
                third_result = harness.invoke(
                    dispatcher=third_dispatcher,
                    now=lambda: NOW + timedelta(seconds=3),
                    quota_reader=lambda: _quota(
                        daily_used=0.12, monthly_used=0.32
                    ),
                )

            self.assertEqual(
                third_result["status"], "dispatched", msg=third_result
            )
            self.assertEqual(third_result["completedEntries"], 2)
            self.assertEqual(
                third_result["selected"],
                {"modelVersionSlug": third["modelVersionSlug"], "order": 3},
            )
            self.assertEqual(third_dispatcher.paid_posts, 1)
            self.assertFalse(
                (harness.control_root / queue._BREAKER_PATH).exists()
            )

    def test_verified_bundle_uses_independent_terminal_quota_receipt(self) -> None:
        with QueueHarness() as harness:
            _dispatcher, first, journal_bytes = self._prepare_first_dispatch(harness)
            bundle = _fake_bundle(
                harness,
                entry=first,
                run_id=4100001,
                journal_bytes=journal_bytes,
            )
            _publish_fake_evidence_marker(bundle)
            harness.set_live_run_state(
                4100001, "BENCHMARK_TASK_RUN_STATE_COMPLETED"
            )
            second_runs = [
                _baseline_run(),
                _queue_run(
                    4100001,
                    first["modelVersionSlug"],
                    state="BENCHMARK_TASK_RUN_STATE_COMPLETED",
                ),
            ]
            second = FakeDispatcher(
                harness,
                runs=second_runs,
                quota=_quota(daily_used=7.96, monthly_used=0.31),
                run_id=4100002,
            )
            terminal_quota = _quota(daily_used=0.11, monthly_used=0.31)
            with mock.patch.object(
                queue, "load_verified_capture_bundle", return_value=bundle
            ):
                result = harness.invoke(
                    dispatcher=second,
                    now=lambda: NOW + timedelta(hours=1),
                    quota_reader=lambda: copy.deepcopy(terminal_quota),
                )

            self.assertEqual(result["status"], "held")
            self.assertEqual(second.paid_posts, 0)
            terminal_path = harness.control_root / first["terminalQuotaRelativePath"]
            completion_path = (
                harness.control_root / first["completionReceiptRelativePath"]
            )
            self.assertTrue(terminal_path.is_file())
            self.assertTrue(completion_path.is_file())
            terminal = json.loads(terminal_path.read_text(encoding="utf-8"))
            self.assertEqual(terminal["quota"], terminal_quota)
            self.assertEqual(terminal["costUpperBound"]["conservativeUsd"], "0.01")

    def test_verified_evidence_is_finalized_at_expiry_without_new_dispatch(
        self,
    ) -> None:
        with QueueHarness() as harness:
            expiry = NOW + timedelta(hours=1)
            harness.policy["expiresAt"] = _canonical_time(expiry)
            harness.policy_sha = _write_policy(
                harness.policy_path, harness.policy
            )
            _dispatcher, first, journal_bytes = self._prepare_first_dispatch(
                harness
            )
            bundle = _fake_bundle(
                harness,
                entry=first,
                run_id=4100001,
                journal_bytes=journal_bytes,
            )
            _publish_fake_evidence_marker(bundle)
            harness.set_live_run_state(
                4100001, "BENCHMARK_TASK_RUN_STATE_COMPLETED"
            )
            replacement = FakeDispatcher(harness, run_id=4100002)

            with mock.patch.object(
                queue, "load_verified_capture_bundle", return_value=bundle
            ):
                result = harness.invoke(
                    dispatcher=replacement,
                    now=lambda: expiry,
                    quota_reader=lambda: _quota(
                        daily_used=0.11, monthly_used=0.31
                    ),
                )

            self.assertEqual(result["status"], "expired")
            self.assertEqual(result["completedEntries"], 1)
            self.assertEqual(replacement.delegate_calls, 0)
            self.assertEqual(replacement.paid_posts, 0)
            self.assertTrue(
                (
                    harness.control_root
                    / first["terminalQuotaRelativePath"]
                ).is_file()
            )
            self.assertTrue(
                (
                    harness.control_root
                    / first["completionReceiptRelativePath"]
                ).is_file()
            )

    def test_prior_bundle_recheck_failure_latches_breaker_before_paid_post(
        self,
    ) -> None:
        with QueueHarness() as harness:
            _dispatcher, first, journal_bytes = self._prepare_first_dispatch(harness)
            bundle = _fake_bundle(
                harness,
                entry=first,
                run_id=4100001,
                journal_bytes=journal_bytes,
            )
            _publish_fake_evidence_marker(bundle)
            harness.set_live_run_state(
                4100001, "BENCHMARK_TASK_RUN_STATE_COMPLETED"
            )
            completed_runs = [
                _baseline_run(),
                _queue_run(
                    4100001,
                    first["modelVersionSlug"],
                    state="BENCHMARK_TASK_RUN_STATE_COMPLETED",
                ),
            ]

            # Finalize entry one while holding entry two on its reserve gate.
            finalizer = FakeDispatcher(
                harness,
                runs=completed_runs,
                quota=_quota(daily_used=7.96, monthly_used=0.31),
                run_id=4100002,
            )
            with mock.patch.object(
                queue, "load_verified_capture_bundle", return_value=bundle
            ):
                finalized = harness.invoke(
                    dispatcher=finalizer,
                    now=lambda: NOW + timedelta(hours=1),
                    quota_reader=lambda: _quota(
                        daily_used=0.11, monthly_used=0.31
                    ),
                )
            self.assertEqual(finalized["status"], "held")
            self.assertTrue(
                (
                    harness.control_root
                    / first["completionReceiptRelativePath"]
                ).is_file()
            )

            # The initial scan succeeds, then the paid-boundary recheck sees
            # an integrity failure in the same invocation. It must become a
            # permanent breaker rather than an automatically recoverable hold.
            next_dispatch = FakeDispatcher(
                harness,
                runs=completed_runs,
                run_id=4100002,
            )
            loader = mock.Mock(
                side_effect=[
                    bundle,
                    KaggleCaptureEvidenceError(
                        "synthetic prior bundle corruption"
                    ),
                ]
            )
            with mock.patch.object(
                queue, "load_verified_capture_bundle", loader
            ):
                broken = harness.invoke(
                    dispatcher=next_dispatch,
                    now=lambda: NOW + timedelta(hours=2),
                )

            self.assertEqual(broken["status"], "breaker")
            self.assertIn(
                "prior closed-world evidence bundle failed verification",
                broken["reason"],
            )
            self.assertEqual(loader.call_count, 2)
            self.assertEqual(next_dispatch.paid_posts, 0)
            breaker_path = harness.control_root / queue._BREAKER_PATH
            breaker_bytes = breaker_path.read_bytes()

            restored_dispatch = FakeDispatcher(
                harness,
                runs=completed_runs,
                run_id=4100003,
            )
            with mock.patch.object(
                queue, "load_verified_capture_bundle", return_value=bundle
            ) as restored_loader:
                repeated = harness.invoke(
                    dispatcher=restored_dispatch,
                    now=lambda: NOW + timedelta(hours=3),
                )
            self.assertEqual(repeated["status"], "breaker")
            self.assertEqual(repeated["reason"], broken["reason"])
            self.assertEqual(breaker_path.read_bytes(), breaker_bytes)
            restored_loader.assert_not_called()
            self.assertEqual(restored_dispatch.delegate_calls, 0)
            self.assertEqual(restored_dispatch.paid_posts, 0)

    def test_terminal_cost_at_breaker_stops_before_next_dispatch(self) -> None:
        with QueueHarness() as harness:
            _dispatcher, first, journal_bytes = self._prepare_first_dispatch(harness)
            bundle = _fake_bundle(
                harness,
                entry=first,
                run_id=4100001,
                journal_bytes=journal_bytes,
            )
            _publish_fake_evidence_marker(bundle)
            harness.set_live_run_state(
                4100001, "BENCHMARK_TASK_RUN_STATE_COMPLETED"
            )
            second = FakeDispatcher(harness, run_id=4100002)
            with mock.patch.object(
                queue, "load_verified_capture_bundle", return_value=bundle
            ):
                result = harness.invoke(
                    dispatcher=second,
                    now=lambda: NOW + timedelta(hours=1),
                    quota_reader=lambda: _quota(
                        daily_used=0.35, monthly_used=0.55
                    ),
                )
            self.assertEqual(result["status"], "breaker")
            self.assertIn("breaker", result["reason"])
            self.assertEqual(second.delegate_calls, 0)
            self.assertEqual(second.paid_posts, 0)

    def test_terminal_quota_transport_failure_holds_but_integrity_failure_breaks(
        self,
    ) -> None:
        with QueueHarness() as harness:
            _dispatcher, first, journal_bytes = self._prepare_first_dispatch(harness)
            bundle = _fake_bundle(
                harness,
                entry=first,
                run_id=4100001,
                journal_bytes=journal_bytes,
            )
            _publish_fake_evidence_marker(bundle)
            harness.set_live_run_state(
                4100001, "BENCHMARK_TASK_RUN_STATE_COMPLETED"
            )
            second = FakeDispatcher(harness, run_id=4100002)

            def unavailable() -> list[dict[str, Any]]:
                raise run_once.KaggleReadUnavailable(
                    "synthetic quota transport failure"
                )

            with mock.patch.object(
                queue, "load_verified_capture_bundle", return_value=bundle
            ):
                held = harness.invoke(
                    dispatcher=second,
                    now=lambda: NOW + timedelta(hours=1),
                    quota_reader=unavailable,
                )
            self.assertEqual(held["status"], "held")
            self.assertFalse(
                (harness.control_root / queue._BREAKER_PATH).exists()
            )

            def invalid() -> list[dict[str, Any]]:
                raise run_once.KaggleRunOnceError("invalid quota schema")

            with mock.patch.object(
                queue, "load_verified_capture_bundle", return_value=bundle
            ):
                broken = harness.invoke(
                    dispatcher=second,
                    now=lambda: NOW + timedelta(hours=1),
                    quota_reader=invalid,
                )
            self.assertEqual(broken["status"], "breaker")
            self.assertIn("integrity validation failed", broken["reason"])
            self.assertEqual(second.paid_posts, 0)

    def test_non_private_bundle_member_latches_breaker_before_loading(self) -> None:
        with QueueHarness() as harness:
            _dispatcher, first, journal_bytes = self._prepare_first_dispatch(harness)
            bundle = _fake_bundle(
                harness,
                entry=first,
                run_id=4100001,
                journal_bytes=journal_bytes,
            )
            _publish_fake_evidence_marker(bundle)
            bundle.evidence_path.chmod(0o644)
            harness.set_live_run_state(
                4100001, "BENCHMARK_TASK_RUN_STATE_COMPLETED"
            )
            loader = mock.Mock(return_value=bundle)
            second = FakeDispatcher(harness, run_id=4100002)
            with mock.patch.object(
                queue, "load_verified_capture_bundle", loader
            ):
                result = harness.invoke(
                    dispatcher=second,
                    now=lambda: NOW + timedelta(hours=1),
                )
            self.assertEqual(result["status"], "breaker")
            self.assertIn("private 0600", result["reason"])
            loader.assert_not_called()
            self.assertEqual(second.paid_posts, 0)

    def test_empty_bundle_directory_is_held_until_exact_evidence_file_exists(
        self,
    ) -> None:
        with QueueHarness() as harness:
            _dispatcher, first, journal_bytes = self._prepare_first_dispatch(harness)
            bundle = _fake_bundle(
                harness,
                entry=first,
                run_id=4100001,
                journal_bytes=journal_bytes,
            )
            bundle.evidence_path.parent.mkdir(parents=True, mode=0o700)
            second_runs = [
                _baseline_run(),
                _queue_run(
                    4100001,
                    first["modelVersionSlug"],
                    state="BENCHMARK_TASK_RUN_STATE_COMPLETED",
                ),
            ]
            second = FakeDispatcher(
                harness,
                runs=second_runs,
                quota=_quota(daily_used=7.96, monthly_used=0.31),
                run_id=4100002,
            )
            loader = mock.Mock(return_value=bundle)
            early_quota = mock.Mock(
                side_effect=AssertionError(
                    "terminal quota must wait for the exact evidence file"
                )
            )
            with mock.patch.object(
                queue, "load_verified_capture_bundle", loader
            ):
                waiting = harness.invoke(
                    dispatcher=second,
                    now=lambda: NOW + timedelta(hours=1),
                    quota_reader=early_quota,
                )
                early_loader_calls = loader.call_count
                early_quota_calls = early_quota.call_count

                harness.set_live_run_state(
                    4100001, "BENCHMARK_TASK_RUN_STATE_COMPLETED"
                )
                _publish_fake_evidence_marker(bundle)
                loader.reset_mock()
                finalized = harness.invoke(
                    dispatcher=second,
                    now=lambda: NOW + timedelta(hours=1),
                    quota_reader=lambda: _quota(
                        daily_used=0.11, monthly_used=0.31
                    ),
                )

            self.assertEqual(waiting["status"], "held")
            self.assertEqual(early_loader_calls, 0)
            self.assertEqual(early_quota_calls, 0)
            self.assertGreaterEqual(loader.call_count, 1)
            self.assertEqual(finalized["status"], "held")
            self.assertEqual(second.paid_posts, 0)
            self.assertFalse(
                (harness.control_root / queue._BREAKER_PATH).exists()
            )

    def test_terminal_observation_clock_is_sampled_after_quota_returns(self) -> None:
        with QueueHarness() as harness:
            _dispatcher, first, journal_bytes = self._prepare_first_dispatch(harness)
            bundle = _fake_bundle(
                harness,
                entry=first,
                run_id=4100001,
                journal_bytes=journal_bytes,
            )
            _publish_fake_evidence_marker(bundle)
            harness.set_live_run_state(
                4100001, "BENCHMARK_TASK_RUN_STATE_COMPLETED"
            )
            second_runs = [
                _baseline_run(),
                _queue_run(
                    4100001,
                    first["modelVersionSlug"],
                    state="BENCHMARK_TASK_RUN_STATE_COMPLETED",
                ),
            ]
            second = FakeDispatcher(
                harness,
                runs=second_runs,
                quota=_quota(daily_used=7.96, monthly_used=0.31),
                run_id=4100002,
            )
            initial = NOW + timedelta(hours=1)
            clock_state = {"quotaReturned": False, "afterSamples": 0}

            def clock() -> datetime:
                if not clock_state["quotaReturned"]:
                    return initial
                clock_state["afterSamples"] += 1
                return initial + timedelta(
                    seconds=clock_state["afterSamples"]
                )

            def terminal_quota_reader() -> list[dict[str, Any]]:
                clock_state["quotaReturned"] = True
                return _quota(daily_used=0.11, monthly_used=0.31)

            with mock.patch.object(
                queue, "load_verified_capture_bundle", return_value=bundle
            ):
                result = harness.invoke(
                    dispatcher=second,
                    now=clock,
                    quota_reader=terminal_quota_reader,
                )

            self.assertEqual(result["status"], "held")
            terminal = json.loads(
                (
                    harness.control_root / first["terminalQuotaRelativePath"]
                ).read_bytes()
            )
            completion = json.loads(
                (
                    harness.control_root / first["completionReceiptRelativePath"]
                ).read_bytes()
            )
            observed = queue._time(
                terminal["observedAt"], role="test terminal observation"
            )
            finalized = queue._time(
                completion["finalizedAt"], role="test completion finalization"
            )
            self.assertGreater(observed, initial)
            self.assertGreaterEqual(finalized, observed)
            self.assertGreaterEqual(clock_state["afterSamples"], 1)

    def test_orphan_decision_after_hard_stop_becomes_latched_breaker(self) -> None:
        with QueueHarness() as harness:
            crashed = FakeDispatcher(harness, mode="hard-stop-after-decision")
            with self.assertRaises(HardStop):
                harness.invoke(dispatcher=crashed)
            self.assertEqual(crashed.paid_posts, 0)

            replacement = FakeDispatcher(harness)
            result = harness.invoke(dispatcher=replacement)
            self.assertEqual(result["status"], "breaker")
            self.assertIn("orphan", result["reason"])
            self.assertEqual(replacement.delegate_calls, 0)
            self.assertEqual(replacement.paid_posts, 0)

            again = FakeDispatcher(harness)
            repeated = harness.invoke(dispatcher=again)
            self.assertEqual(repeated["status"], "breaker")
            self.assertEqual(repeated["reason"], result["reason"])
            self.assertEqual(again.delegate_calls, 0)

    def test_ambiguous_journal_survives_process_loss_and_latches_breaker(self) -> None:
        with QueueHarness() as harness:
            crashed = FakeDispatcher(harness, mode="hard-stop-after-journal")
            with self.assertRaises(HardStop):
                harness.invoke(dispatcher=crashed)
            self.assertEqual(crashed.paid_posts, 1)

            replacement = FakeDispatcher(harness)
            result = harness.invoke(dispatcher=replacement)
            self.assertEqual(result["status"], "breaker")
            self.assertIn("not reconciled", result["reason"])
            self.assertEqual(replacement.delegate_calls, 0)
            self.assertEqual(replacement.paid_posts, 0)

    def test_ambiguous_journal_at_exact_expiry_still_latches_breaker(self) -> None:
        with QueueHarness() as harness:
            crashed = FakeDispatcher(harness, mode="hard-stop-after-journal")
            with self.assertRaises(HardStop):
                harness.invoke(dispatcher=crashed)
            self.assertEqual(crashed.paid_posts, 1)

            replacement = FakeDispatcher(harness, run_id=4100002)
            result = harness.invoke(
                dispatcher=replacement,
                now=lambda: datetime(2026, 10, 25, tzinfo=timezone.utc),
            )

            self.assertEqual(result["status"], "breaker")
            self.assertIn("not reconciled", result["reason"])
            self.assertEqual(replacement.delegate_calls, 0)
            self.assertEqual(replacement.paid_posts, 0)


if __name__ == "__main__":
    unittest.main()
