from __future__ import annotations

import json
import os
import sys
import tempfile
import threading
import unittest
from datetime import datetime, timezone
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest import mock

from bench.engine import kaggle_run_once as run_once
from bench.engine.kaggle_run_once import (
    KaggleRunOnceError,
    KaggleRunOutcomeAmbiguous,
    schedule_and_reconcile_once,
)


OWNER = "jahyee"
TASK = "aleph-bench-v0-2-capture-canary"
VERSION = 6
MODEL = "gpt-5.4-mini"
MODEL_ID = 4301
DATASET = "jahyee/aleph-bench-v02-scorer-conformance"
SOURCE_IDENTITY = {
    "path": "bench/tasks/kaggle/aleph_bench_v0_2_capture.py",
    "bytes": 1234,
    "sha256": "1" * 64,
    "notebookSha256": "2" * 64,
}


def _slug() -> SimpleNamespace:
    return SimpleNamespace(
        owner_slug=OWNER,
        task_slug=TASK,
        version_number=VERSION,
    )


def _task(
    state: str = "BENCHMARK_TASK_VERSION_CREATION_STATE_COMPLETED",
    *,
    source_kernel_id: int | None = 120,
    datasets: tuple[str, ...] = (DATASET,),
) -> SimpleNamespace:
    return SimpleNamespace(
        slug=_slug(),
        creation_state=state,
        source_kernel_id=source_kernel_id,
        options=SimpleNamespace(dataset_data_sources=list(datasets)),
        url=f"https://www.kaggle.com/benchmarks/{OWNER}/{TASK}/{VERSION}",
    )


def _creation_journal_bytes(
    *,
    owner: str = OWNER,
    task: str = TASK,
    version: int = VERSION,
    source_kernel_id: int | None = 120,
    source: dict[str, object] | None = None,
    datasets: tuple[str, ...] = (DATASET,),
    state: str = "returned",
    response_state: str = "BENCHMARK_TASK_VERSION_CREATION_STATE_COMPLETED",
    failure: dict[str, str] | None = None,
) -> bytes:
    source_record = {
        "path": "/reviewed/checkout/" + SOURCE_IDENTITY["path"],
        "bytes": SOURCE_IDENTITY["bytes"],
        "sha256": SOURCE_IDENTITY["sha256"],
        "notebookSha256": SOURCE_IDENTITY["notebookSha256"],
    }
    if source is not None:
        source_record.update(source)
    journal = {
        "journalVersion": 2,
        "artifactKind": "kaggle_task_creation_dispatch",
        "operationId": "12345678-1234-4abc-8123-123456789abc",
        "createdAt": "2026-09-22T23:58:00Z",
        "updatedAt": "2026-09-22T23:58:01Z",
        "task": task,
        "gate": "six-call-capture",
        "datasets": list(datasets),
        "client": {
            "python": "3.13.7",
            "kaggle": "2.2.4",
            "kagglesdk": "0.1.37",
            "jupytext": "1.19.5",
        },
        "source": source_record,
        "remotePreflight": {
            "observedAt": "2026-09-22T23:58:00Z",
            "priorTask": None,
        },
        "state": state,
        "response": {
            "owner": owner,
            "task": task,
            "version": version,
            "sourceKernelId": source_kernel_id,
            "creationState": response_state,
            "url": f"https://www.kaggle.com/benchmarks/{owner}/{task}/{version}",
            "datasets": list(datasets),
        },
        "failure": failure,
    }
    return run_once._canonical_json_bytes(journal)


def _creation_authority(**kwargs: object) -> run_once.VerifiedCreationAuthority:
    return run_once.verify_creation_authority_bytes(
        _creation_journal_bytes(**kwargs),
        expected_owner=OWNER,
        expected_task=TASK,
        expected_version=VERSION,
        current_source=dict(SOURCE_IDENTITY),
    )


def _model(
    *, slug: str = MODEL, model_id: int = MODEL_ID
) -> SimpleNamespace:
    return SimpleNamespace(
        id=301,
        version=SimpleNamespace(
            id=model_id,
            slug=slug,
            published=True,
            allow_model_proxy=True,
            model_proxy_slug="openai/gpt-5.4-mini",
            display_name="GPT-5.4 mini",
            deprecation_time=None,
        ),
    )


def _run(
    run_id: int,
    *,
    model: str = MODEL,
    state: str = "BENCHMARK_TASK_RUN_STATE_COMPLETED",
) -> SimpleNamespace:
    return SimpleNamespace(
        task_slug=_slug(),
        model_version_slug=model,
        id=run_id,
        state=state,
        start_time=datetime(2026, 9, 23, tzinfo=timezone.utc),
        end_time=(
            datetime(2026, 9, 23, 0, 1, tzinfo=timezone.utc)
            if state == "BENCHMARK_TASK_RUN_STATE_COMPLETED"
            else None
        ),
        error_message="",
    )


def _quota(used: float = 0.04) -> SimpleNamespace:
    refill = datetime(2026, 9, 24, tzinfo=timezone.utc)
    return SimpleNamespace(
        quota_balances=[
            SimpleNamespace(
                refill_period="DAILY",
                quota_used=used,
                total_quota_allowed=10.0,
                refill_time=refill,
            ),
            SimpleNamespace(
                refill_period="MONTHLY",
                quota_used=used,
                total_quota_allowed=100.0,
                refill_time=refill,
            ),
        ]
    )


def _response(
    *,
    scheduled: bool = True,
    model_id: int = MODEL_ID,
    parent_id: int = 0,
    reason: str = "",
) -> SimpleNamespace:
    return SimpleNamespace(
        results=[
            SimpleNamespace(
                run_scheduled=scheduled,
                run_skipped_reason=reason,
                benchmark_task_version_id=901,
                benchmark_model_version_id=model_id,
                parent_task_version_id=parent_id,
            )
        ]
    )


class HardStop(BaseException):
    """Synthetic process interruption that must not be converted or retried."""


class KaggleRunOnceTests(unittest.TestCase):
    def _assert_creation_preflight_rejected(
        self, data: bytes | None, message: str
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            creation_path = root / "creation.json"
            if data is not None:
                creation_path.write_bytes(data)
            journal_path = root / "run.json"
            dispatch = mock.Mock()
            with (
                mock.patch.object(
                    run_once, "_verified_client_versions", return_value={}
                ),
                mock.patch.object(
                    run_once,
                    "current_capture_source_identity",
                    return_value=dict(SOURCE_IDENTITY),
                ),
                mock.patch.object(
                    run_once, "schedule_and_reconcile_once", dispatch
                ),
                self.assertRaisesRegex(KaggleRunOnceError, message),
            ):
                run_once.run_once(
                    owner=OWNER,
                    task=TASK,
                    version=VERSION,
                    model=MODEL,
                    journal_path=journal_path,
                    creation_journal_path=creation_path,
                )
            dispatch.assert_not_called()
            self.assertFalse(journal_path.exists())

    def test_creation_authority_reader_rejects_leaf_aliases_and_special_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            original = root / "creation.json"
            original.write_bytes(_creation_journal_bytes())

            alias = root / "creation-link.json"
            alias.symlink_to(original)
            with self.assertRaisesRegex(
                KaggleRunOnceError, "single-link regular file"
            ):
                run_once.read_creation_authority(alias)

            hardlink = root / "creation-hardlink.json"
            os.link(original, hardlink)
            with self.assertRaisesRegex(
                KaggleRunOnceError, "single-link regular file"
            ):
                run_once.read_creation_authority(original)
            hardlink.unlink()

            fifo = root / "creation.fifo"
            os.mkfifo(fifo)
            with self.assertRaisesRegex(
                KaggleRunOnceError, "single-link regular file"
            ):
                run_once.read_creation_authority(fifo)

    def _schedule(
        self,
        journal_path: Path,
        *,
        runs: list[list[SimpleNamespace]],
        schedule_run: object | None = None,
        fetch_task: object | None = None,
        fetch_model: object | None = None,
        fetch_quota: object | None = None,
        fetch_current_source: object | None = None,
        creation_authority: run_once.VerifiedCreationAuthority | None = None,
        confirmed_runs: list[SimpleNamespace] | None = None,
    ) -> tuple[dict[str, object], mock.Mock]:
        schedule = mock.Mock(
            return_value=_response()
        ) if schedule_run is None else schedule_run
        run_snapshots = iter(
            [
                runs[0],
                runs[0] if confirmed_runs is None else confirmed_runs,
                *runs[1:],
            ]
        )
        authority = creation_authority or _creation_authority()
        creation_path = journal_path.parent / "creation.json"
        if not creation_path.exists():
            creation_path.write_bytes(authority.canonical_bytes)
        journal = schedule_and_reconcile_once(
            owner=OWNER,
            task=TASK,
            version=VERSION,
            model=MODEL,
            journal_path=journal_path,
            creation_journal_path=creation_path,
            creation_authority=authority,
            fetch_task=fetch_task or (lambda: _task()),
            fetch_model=fetch_model or (lambda: _model()),
            fetch_runs=lambda: next(run_snapshots),
            fetch_quota=fetch_quota or (lambda: _quota()),
            fetch_current_source=fetch_current_source
            or (lambda: dict(SOURCE_IDENTITY)),
            schedule_run=schedule,
            client_versions={"python": "3.13.7", "kaggle": "2.2.4"},
            reconcile_delays=(0, 0),
            clock=lambda: "2026-09-23T00:00:00Z",
            sleeper=lambda _delay: None,
        )
        return journal, schedule  # type: ignore[return-value]

    def test_success_schedules_once_and_binds_one_exact_new_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            journal_path = Path(tmp) / "run.json"
            journal, schedule = self._schedule(
                journal_path,
                runs=[
                    [_run(10, model="other-model")],
                    [
                        _run(10, model="other-model"),
                        _run(11, state="BENCHMARK_TASK_RUN_STATE_QUEUED"),
                    ],
                ],
            )

            schedule.assert_called_once_with()
            self.assertEqual(journal["state"], "reconciled")
            self.assertEqual(journal["reconciliation"]["run"]["id"], 11)
            self.assertEqual(
                journal["remotePreflight"]["model"]["benchmarkModelVersionId"],
                MODEL_ID,
            )
            self.assertEqual(journal["journalVersion"], 2)
            self.assertEqual(
                journal["creationAuthority"]["task"],
                {
                    "owner": OWNER,
                    "task": TASK,
                    "version": VERSION,
                    "datasets": [DATASET],
                    "acknowledgedSourceKernelId": 120,
                    "resolvedSourceKernelId": 120,
                },
            )
            self.assertIsNone(journal["failure"])
            self.assertEqual(
                json.loads(journal_path.read_text(encoding="utf-8")), journal
            )

    def test_creation_authority_preflight_rejects_strict_json_and_drift(self) -> None:
        base = json.loads(_creation_journal_bytes())
        cases: dict[str, tuple[bytes | None, str]] = {
            "missing": (None, "cannot read creation authority"),
            "oversized": (
                b" " * (run_once.MAX_CREATION_JOURNAL_BYTES + 1),
                "exceeds the safety limit",
            ),
            "duplicate-key": (
                b'{"journalVersion":2,"journalVersion":2}\n',
                "duplicate JSON key",
            ),
            "non-finite": (
                b'{"value":NaN}\n',
                "non-finite JSON constant",
            ),
            "non-canonical": (
                _creation_journal_bytes().rstrip(b"\n"),
                "not canonical",
            ),
        }

        mutations = {
            "extra-shape": ("invalid fields", lambda value: value.update({"extra": 1})),
            "non-returned": (
                "not a returned creation receipt",
                lambda value: value.update({"state": "dispatching"}),
            ),
            "unacknowledged-response": (
                "did not acknowledge a viable creation",
                lambda value: value["response"].update(
                    {
                        "creationState": (
                            "BENCHMARK_TASK_VERSION_CREATION_STATE_ERRORED"
                        )
                    }
                ),
            ),
            "source": (
                "source sha256 drifted",
                lambda value: value["source"].update({"sha256": "a" * 64}),
            ),
            "notebook": (
                "source notebookSha256 drifted",
                lambda value: value["source"].update(
                    {"notebookSha256": "b" * 64}
                ),
            ),
            "version": (
                "different task version",
                lambda value: value["response"].update(
                    {"version": VERSION + 1}
                ),
            ),
            "task": (
                "targets a different task",
                lambda value: value.update({"task": "other-task"}),
            ),
            "dataset": (
                "not the frozen capture package",
                lambda value: (
                    value.update({"datasets": ["jahyee/other-dataset"]}),
                    value["response"].update(
                        {"datasets": ["jahyee/other-dataset"]}
                    ),
                ),
            ),
        }
        for name, (message, mutate) in mutations.items():
            value = json.loads(json.dumps(base))
            mutate(value)
            cases[name] = (run_once._canonical_json_bytes(value), message)

        for name, (data, message) in cases.items():
            with self.subTest(name=name):
                self._assert_creation_preflight_rejected(data, message)

    def test_historical_v7_source_cannot_be_retried_with_another_journal(self) -> None:
        stale = json.loads(_creation_journal_bytes())
        stale["source"].update(
            {
                "sha256": (
                    "a1aff9e2feaa63c67da97c5a5c345f5b"
                    "efc983f8e3ec15516581eecbca45a68c"
                ),
                "notebookSha256": (
                    "1ca08c211ffd0c24206f954c73af161e"
                    "83d137383941af2bdeb3351c78cab55e"
                ),
            }
        )
        stale_bytes = run_once._canonical_json_bytes(stale)
        for attempt in range(2):
            with self.subTest(attempt=attempt):
                self._assert_creation_preflight_rejected(
                    stale_bytes, "current source sha256 drifted"
                )

    def test_null_acknowledged_kernel_is_resolved_by_exact_readback(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            journal, schedule = self._schedule(
                Path(tmp) / "run.json",
                runs=[[], [_run(12)]],
                creation_authority=_creation_authority(
                    source_kernel_id=None,
                    response_state=(
                        "BENCHMARK_TASK_VERSION_CREATION_STATE_UNSPECIFIED"
                    ),
                ),
            )
        schedule.assert_called_once_with()
        self.assertIsNone(
            journal["creationAuthority"]["task"][
                "acknowledgedSourceKernelId"
            ]
        )
        self.assertEqual(
            journal["creationAuthority"]["task"]["resolvedSourceKernelId"],
            120,
        )

    def test_creation_readback_drift_blocks_before_journal_and_schedule(self) -> None:
        cases = {
            "acknowledged-kernel": (
                _creation_authority(source_kernel_id=119),
                lambda: _task(source_kernel_id=120),
                "source kernel differs",
            ),
            "unresolved-kernel": (
                _creation_authority(source_kernel_id=None),
                lambda: _task(source_kernel_id=None),
                "invalid source kernel ID",
            ),
            "dataset": (
                _creation_authority(),
                lambda: _task(datasets=("jahyee/other-dataset",)),
                "datasets differ",
            ),
        }
        for name, (authority, task, message) in cases.items():
            with self.subTest(name=name), tempfile.TemporaryDirectory() as tmp:
                journal_path = Path(tmp) / "run.json"
                schedule = mock.Mock(return_value=_response())
                with self.assertRaisesRegex(KaggleRunOnceError, message):
                    self._schedule(
                        journal_path,
                        runs=[[]],
                        schedule_run=schedule,
                        fetch_task=task,
                        creation_authority=authority,
                    )
                self.assertFalse(journal_path.exists())
                schedule.assert_not_called()

    def test_source_change_during_remote_preflight_blocks_paid_call(self) -> None:
        changed_source = {**SOURCE_IDENTITY, "sha256": "f" * 64}
        with tempfile.TemporaryDirectory() as tmp:
            journal_path = Path(tmp) / "run.json"
            schedule = mock.Mock(return_value=_response())
            with self.assertRaisesRegex(
                KaggleRunOnceError, "current source sha256 drifted"
            ):
                self._schedule(
                    journal_path,
                    runs=[[]],
                    schedule_run=schedule,
                    fetch_current_source=lambda: changed_source,
                )
            self.assertFalse(journal_path.exists())
            schedule.assert_not_called()

    def test_existing_exact_model_blocks_an_alternate_journal_retry(self) -> None:
        for attempt in ("attempt-a.json", "attempt-b.json"):
            with self.subTest(attempt=attempt), tempfile.TemporaryDirectory() as tmp:
                journal_path = Path(tmp) / attempt
                schedule = mock.Mock(return_value=_response())
                with self.assertRaisesRegex(
                    KaggleRunOnceError,
                    "already has a run for the requested model",
                ):
                    self._schedule(
                        journal_path,
                        runs=[[_run(101, model=MODEL)]],
                        schedule_run=schedule,
                    )
                self.assertFalse(journal_path.exists())
                schedule.assert_not_called()

    def test_run_set_change_at_paid_boundary_blocks_without_a_journal(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            journal_path = Path(tmp) / "run.json"
            schedule = mock.Mock(return_value=_response())
            with self.assertRaisesRegex(
                KaggleRunOnceError, "run set changed during preflight"
            ):
                self._schedule(
                    journal_path,
                    runs=[[]],
                    confirmed_runs=[_run(102, model=MODEL)],
                    schedule_run=schedule,
                )
            self.assertFalse(journal_path.exists())
            schedule.assert_not_called()

    def test_receipt_change_at_paid_boundary_blocks_without_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            journal_path = root / "run.json"
            creation_path = root / "creation.json"
            authority = _creation_authority()
            creation_path.write_bytes(authority.canonical_bytes)
            run_read_count = 0

            def fetch_runs() -> list[SimpleNamespace]:
                nonlocal run_read_count
                run_read_count += 1
                if run_read_count == 2:
                    creation_path.write_bytes(b"{}\n")
                return []

            schedule = mock.Mock(return_value=_response())
            with self.assertRaisesRegex(
                KaggleRunOnceError, "changed during remote preflight"
            ):
                schedule_and_reconcile_once(
                    owner=OWNER,
                    task=TASK,
                    version=VERSION,
                    model=MODEL,
                    journal_path=journal_path,
                    creation_journal_path=creation_path,
                    creation_authority=authority,
                    fetch_task=lambda: _task(),
                    fetch_model=lambda: _model(),
                    fetch_runs=fetch_runs,
                    fetch_quota=lambda: _quota(),
                    fetch_current_source=lambda: dict(SOURCE_IDENTITY),
                    schedule_run=schedule,
                    client_versions={},
                    reconcile_delays=(0,),
                )
            self.assertFalse(journal_path.exists())
            self.assertFalse(
                (root / run_once._DISPATCH_CLAIM_DIRECTORY).exists()
            )
            schedule.assert_not_called()

    def test_source_change_at_paid_boundary_blocks_without_artifacts(self) -> None:
        changed_source = {**SOURCE_IDENTITY, "sha256": "f" * 64}
        source_snapshots = iter([dict(SOURCE_IDENTITY), changed_source])
        with tempfile.TemporaryDirectory() as tmp:
            journal_path = Path(tmp) / "run.json"
            schedule = mock.Mock(return_value=_response())
            with self.assertRaisesRegex(
                KaggleRunOnceError, "current source sha256 drifted"
            ):
                self._schedule(
                    journal_path,
                    runs=[[]],
                    schedule_run=schedule,
                    fetch_current_source=lambda: next(source_snapshots),
                )
            self.assertFalse(journal_path.exists())
            self.assertFalse(
                (
                    journal_path.parent
                    / run_once._DISPATCH_CLAIM_DIRECTORY
                ).exists()
            )
            schedule.assert_not_called()

    def test_durable_claim_serializes_concurrent_alternate_journals(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            creation_path = root / "creation.json"
            authority = _creation_authority()
            creation_path.write_bytes(authority.canonical_bytes)
            preclaim_barrier = threading.Barrier(2)
            paid_lock = threading.Lock()
            paid_calls: list[int] = []
            results: list[dict[str, object]] = []
            errors: list[BaseException] = []

            def worker(name: str, run_id: int) -> None:
                read_count = 0

                def fetch_runs() -> list[SimpleNamespace]:
                    nonlocal read_count
                    read_count += 1
                    if read_count == 2:
                        preclaim_barrier.wait(timeout=5)
                    return [] if read_count <= 2 else [_run(run_id)]

                def schedule() -> SimpleNamespace:
                    with paid_lock:
                        paid_calls.append(run_id)
                    return _response()

                try:
                    result = schedule_and_reconcile_once(
                        owner=OWNER,
                        task=TASK,
                        version=VERSION,
                        model=MODEL,
                        journal_path=root / f"{name}.json",
                        creation_journal_path=creation_path,
                        creation_authority=authority,
                        fetch_task=lambda: _task(),
                        fetch_model=lambda: _model(),
                        fetch_runs=fetch_runs,
                        fetch_quota=lambda: _quota(),
                        fetch_current_source=lambda: dict(SOURCE_IDENTITY),
                        schedule_run=schedule,
                        client_versions={},
                        reconcile_delays=(0,),
                        clock=lambda: "2026-09-23T00:00:00Z",
                        sleeper=lambda _delay: None,
                    )
                    results.append(result)
                except BaseException as exc:  # captured for the parent assertion
                    errors.append(exc)

            threads = [
                threading.Thread(target=worker, args=("attempt-a", 201)),
                threading.Thread(target=worker, args=("attempt-b", 202)),
            ]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join(timeout=10)

            self.assertTrue(all(not thread.is_alive() for thread in threads))
            self.assertEqual(len(paid_calls), 1)
            self.assertEqual(len(results), 1)
            self.assertEqual(len(errors), 1)
            self.assertIsInstance(errors[0], KaggleRunOnceError)
            self.assertIn("durable dispatch claim already exists", str(errors[0]))
            claims = list(
                (root / run_once._DISPATCH_CLAIM_DIRECTORY).glob("*.json")
            )
            self.assertEqual(len(claims), 1)

    def test_lost_schedule_response_can_be_reconciled_without_retry(self) -> None:
        schedule = mock.Mock(side_effect=ConnectionError("response lost"))
        with tempfile.TemporaryDirectory() as tmp:
            journal, _ = self._schedule(
                Path(tmp) / "run.json",
                runs=[[], [_run(21, state="BENCHMARK_TASK_RUN_STATE_RUNNING")]],
                schedule_run=schedule,
            )

        schedule.assert_called_once_with()
        self.assertEqual(journal["state"], "reconciled")
        self.assertEqual(journal["reconciliation"]["run"]["id"], 21)
        self.assertEqual(journal["dispatchFailure"]["type"], "ConnectionError")
        self.assertIsNone(journal["failure"])

    def test_unobserved_run_after_dispatch_is_ambiguous_and_not_retried(self) -> None:
        schedule = mock.Mock(return_value=_response())
        with tempfile.TemporaryDirectory() as tmp:
            journal_path = Path(tmp) / "run.json"
            with self.assertRaisesRegex(
                KaggleRunOutcomeAmbiguous, "do not schedule again"
            ):
                self._schedule(
                    journal_path,
                    runs=[[], [], []],
                    schedule_run=schedule,
                )

            retained = json.loads(journal_path.read_text(encoding="utf-8"))
        schedule.assert_called_once_with()
        self.assertEqual(retained["state"], "ambiguous")
        self.assertEqual(retained["failure"]["type"], "RunNotObserved")

    def test_wrong_or_multiple_new_runs_are_ambiguous(self) -> None:
        cases = {
            "wrong-model": [_run(31, model="gemini-3.7-flash")],
            "multiple": [_run(31), _run(32)],
        }
        for name, after in cases.items():
            with self.subTest(name=name), tempfile.TemporaryDirectory() as tmp:
                schedule = mock.Mock(return_value=_response())
                with self.assertRaisesRegex(
                    KaggleRunOutcomeAmbiguous, "ambiguous"
                ):
                    self._schedule(
                        Path(tmp) / "run.json",
                        runs=[[], after],
                        schedule_run=schedule,
                    )
                schedule.assert_called_once_with()

    def test_contradictory_schedule_identity_remains_ambiguous(self) -> None:
        schedule = mock.Mock(return_value=_response(model_id=999))
        with tempfile.TemporaryDirectory() as tmp:
            journal_path = Path(tmp) / "run.json"
            with self.assertRaisesRegex(
                KaggleRunOutcomeAmbiguous, "contradictory"
            ):
                self._schedule(
                    journal_path,
                    runs=[[], [_run(41)]],
                    schedule_run=schedule,
                )
            retained = json.loads(journal_path.read_text(encoding="utf-8"))

        self.assertEqual(retained["state"], "ambiguous")
        self.assertEqual(
            retained["responseFailure"]["type"], "KaggleRunOnceError"
        )
        self.assertEqual(retained["reconciliation"]["run"]["id"], 41)

    def test_skipped_response_is_conclusive_and_retained(self) -> None:
        schedule = mock.Mock(
            return_value=_response(scheduled=False, reason="already exists")
        )
        with tempfile.TemporaryDirectory() as tmp:
            journal_path = Path(tmp) / "run.json"
            with self.assertRaisesRegex(KaggleRunOnceError, "skipped"):
                self._schedule(
                    journal_path,
                    runs=[[]],
                    schedule_run=schedule,
                )
            retained = json.loads(journal_path.read_text(encoding="utf-8"))

        schedule.assert_called_once_with()
        self.assertEqual(retained["state"], "not_scheduled")
        self.assertEqual(retained["failure"]["message"], "already exists")

    def test_active_run_blocks_before_journal_and_schedule(self) -> None:
        schedule = mock.Mock(return_value=_response())
        with tempfile.TemporaryDirectory() as tmp:
            journal_path = Path(tmp) / "run.json"
            with self.assertRaisesRegex(KaggleRunOnceError, "unresolved"):
                self._schedule(
                    journal_path,
                    runs=[[_run(51, state="BENCHMARK_TASK_RUN_STATE_RUNNING")]],
                    schedule_run=schedule,
                )
            self.assertFalse(journal_path.exists())
        schedule.assert_not_called()

    def test_task_and_model_preflight_fail_closed(self) -> None:
        cases = {
            "task": (
                lambda: _task("BENCHMARK_TASK_VERSION_CREATION_STATE_RUNNING"),
                lambda: _model(),
                "not ready",
            ),
            "model": (
                lambda: _task(),
                lambda: _model(slug="other-model"),
                "different canonical",
            ),
        }
        for name, (task, model, message) in cases.items():
            with self.subTest(name=name), tempfile.TemporaryDirectory() as tmp:
                journal_path = Path(tmp) / "run.json"
                schedule = mock.Mock(return_value=_response())
                with self.assertRaisesRegex(KaggleRunOnceError, message):
                    self._schedule(
                        journal_path,
                        runs=[[]],
                        schedule_run=schedule,
                        fetch_task=task,
                        fetch_model=model,
                    )
                self.assertFalse(journal_path.exists())
                schedule.assert_not_called()

    def test_invalid_target_and_existing_journal_block_before_remote_reads(self) -> None:
        for model in ("openai/gpt-5.4-mini", "gpt@default", ""):
            with self.subTest(model=model), tempfile.TemporaryDirectory() as tmp:
                journal_path = Path(tmp) / "run.json"
                reads = mock.Mock()
                with self.assertRaisesRegex(KaggleRunOnceError, "canonical"):
                    schedule_and_reconcile_once(
                        owner=OWNER,
                        task=TASK,
                        version=VERSION,
                        model=model,
                        journal_path=journal_path,
                        creation_journal_path=journal_path.parent / "creation.json",
                        creation_authority=_creation_authority(),
                        fetch_task=reads,
                        fetch_model=reads,
                        fetch_runs=reads,
                        fetch_quota=reads,
                        fetch_current_source=reads,
                        schedule_run=reads,
                        client_versions={},
                    )
                reads.assert_not_called()

        with tempfile.TemporaryDirectory() as tmp:
            journal_path = Path(tmp) / "run.json"
            journal_path.write_text("{}\n", encoding="utf-8")
            reads = mock.Mock()
            with self.assertRaisesRegex(KaggleRunOnceError, "already exists"):
                schedule_and_reconcile_once(
                    owner=OWNER,
                    task=TASK,
                    version=VERSION,
                    model=MODEL,
                    journal_path=journal_path,
                    creation_journal_path=journal_path.parent / "creation.json",
                    creation_authority=_creation_authority(),
                    fetch_task=reads,
                    fetch_model=reads,
                    fetch_runs=reads,
                    fetch_quota=reads,
                    fetch_current_source=reads,
                    schedule_run=reads,
                    client_versions={},
                )
            reads.assert_not_called()

    def test_hard_stop_is_journaled_and_propagated_once(self) -> None:
        schedule = mock.Mock(side_effect=HardStop("interrupted"))
        with tempfile.TemporaryDirectory() as tmp:
            journal_path = Path(tmp) / "run.json"
            with self.assertRaises(HardStop):
                self._schedule(
                    journal_path,
                    runs=[[]],
                    schedule_run=schedule,
                )
            retained = json.loads(journal_path.read_text(encoding="utf-8"))
            alternate_schedule = mock.Mock(return_value=_response())
            alternate_journal = Path(tmp) / "alternate-run.json"
            with self.assertRaisesRegex(
                KaggleRunOnceError, "durable dispatch claim already exists"
            ):
                self._schedule(
                    alternate_journal,
                    runs=[[]],
                    schedule_run=alternate_schedule,
                )
            self.assertFalse(alternate_journal.exists())
            alternate_schedule.assert_not_called()
        schedule.assert_called_once_with()
        self.assertEqual(retained["state"], "ambiguous")
        self.assertEqual(retained["dispatchFailure"]["type"], "HardStop")

    def test_quota_after_failure_does_not_hide_unique_run(self) -> None:
        quotas = iter([_quota(), ConnectionError("quota read failed")])

        def fetch_quota() -> SimpleNamespace:
            result = next(quotas)
            if isinstance(result, Exception):
                raise result
            return result

        with tempfile.TemporaryDirectory() as tmp:
            journal, _ = self._schedule(
                Path(tmp) / "run.json",
                runs=[[], [_run(61)]],
                fetch_quota=fetch_quota,
            )

        self.assertEqual(journal["state"], "reconciled")
        self.assertIsNone(journal["quotaAfter"])
        self.assertEqual(
            journal["quotaAfterFailure"]["type"], "ConnectionError"
        )

    def test_run_once_sets_explicit_version_and_never_retries_schedule(self) -> None:
        class Request:
            pass

        task_client = SimpleNamespace(
            get_benchmark_task=mock.Mock(return_value=_task()),
            list_benchmark_task_runs=mock.Mock(
                side_effect=[
                    SimpleNamespace(runs=[], next_page_token=""),
                    SimpleNamespace(runs=[], next_page_token=""),
                    SimpleNamespace(runs=[_run(71)], next_page_token=""),
                ]
            ),
            batch_schedule_benchmark_task_runs=mock.Mock(
                return_value=_response()
            ),
        )
        model_client = SimpleNamespace(
            list_benchmark_models=mock.Mock(
                return_value=SimpleNamespace(
                    benchmark_models=[_model()], next_page_token=""
                )
            )
        )
        quota_client = SimpleNamespace(
            get_model_proxy_quotas=mock.Mock(side_effect=[_quota(), _quota()])
        )
        client = SimpleNamespace(
            benchmarks=SimpleNamespace(
                benchmark_tasks_api_client=task_client,
                benchmarks_api_client=model_client,
            ),
            models=SimpleNamespace(model_proxy_api_client=quota_client),
        )
        context = mock.MagicMock()
        context.__enter__.return_value = client
        api = mock.Mock()
        api.build_kaggle_client.return_value = context
        api.with_retry.side_effect = lambda function: function

        modules: dict[str, ModuleType] = {}
        for name in (
            "kaggle",
            "kaggle.api",
            "kaggle.api.kaggle_api_extended",
            "kagglesdk",
            "kagglesdk.benchmarks",
            "kagglesdk.benchmarks.types",
            "kagglesdk.benchmarks.types.benchmark_tasks_api_service",
            "kagglesdk.benchmarks.types.benchmarks_api_service",
            "kagglesdk.models",
            "kagglesdk.models.types",
            "kagglesdk.models.types.model_proxy_api_service",
        ):
            modules[name] = ModuleType(name)
        modules["kaggle.api.kaggle_api_extended"].KaggleApi = mock.Mock(
            return_value=api
        )
        task_types = modules[
            "kagglesdk.benchmarks.types.benchmark_tasks_api_service"
        ]
        task_types.ApiBatchScheduleBenchmarkTaskRunsRequest = Request
        task_types.ApiBenchmarkTaskSlug = Request
        task_types.ApiGetBenchmarkTaskRequest = Request
        task_types.ApiListBenchmarkTaskRunsRequest = Request
        modules[
            "kagglesdk.benchmarks.types.benchmarks_api_service"
        ].ApiListBenchmarkModelsRequest = Request
        modules[
            "kagglesdk.models.types.model_proxy_api_service"
        ].ApiGetModelProxyQuotasRequest = Request

        with (
            tempfile.TemporaryDirectory() as tmp,
            mock.patch.object(
                run_once, "_verified_client_versions", return_value={}
            ),
            mock.patch.object(
                run_once,
                "current_capture_source_identity",
                return_value=dict(SOURCE_IDENTITY),
            ),
            mock.patch.dict(sys.modules, modules),
        ):
            creation_journal = Path(tmp) / "creation.json"
            creation_journal.write_bytes(_creation_journal_bytes())
            journal = run_once.run_once(
                owner=OWNER,
                task=TASK,
                version=VERSION,
                model=MODEL,
                journal_path=Path(tmp) / "run.json",
                creation_journal_path=creation_journal,
                reconcile_delays=(0,),
            )

        schedule_request = task_client.batch_schedule_benchmark_task_runs.call_args.args[0]
        requested_slug = schedule_request.task_slugs[0]
        self.assertEqual(requested_slug.owner_slug, OWNER)
        self.assertEqual(requested_slug.task_slug, TASK)
        self.assertEqual(requested_slug.version_number, VERSION)
        self.assertEqual(schedule_request.model_version_slugs, [MODEL])
        task_client.batch_schedule_benchmark_task_runs.assert_called_once()
        self.assertNotIn(
            task_client.batch_schedule_benchmark_task_runs,
            [call.args[0] for call in api.with_retry.call_args_list],
        )
        self.assertEqual(journal["reconciliation"]["run"]["id"], 71)


if __name__ == "__main__":
    unittest.main()
