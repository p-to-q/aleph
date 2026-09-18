from __future__ import annotations

import io
import json
import tempfile
import unittest
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from bench.engine import kaggle_creation_output as creation_output
from bench.engine.kaggle_creation_output import (
    KaggleCreationOutputError,
    RECEIPT_FILENAME,
    _read_bounded_download,
    _source_kernel_for_download,
    _validate_gate_datasets,
    write_creation_bundle,
)


COMPLETED = "BENCHMARK_TASK_VERSION_CREATION_STATE_COMPLETED"


def _task_info(
    *,
    owner: str = "owner",
    task: str = "aleph-bench-deployment-diagnostic-2048-none",
    version: int = 2,
    kernel_id: int = 12345,
    datasets: tuple[str, ...] = (),
    state: str = COMPLETED,
) -> SimpleNamespace:
    return SimpleNamespace(
        slug=SimpleNamespace(
            owner_slug=owner,
            task_slug=task,
            version_number=version,
        ),
        creation_state=state,
        creation_error_message=None,
        error=None,
        source_kernel_id=kernel_id,
        options=SimpleNamespace(dataset_data_sources=list(datasets)),
        create_time=datetime(2026, 9, 18, tzinfo=timezone.utc),
        url=f"https://www.kaggle.com/benchmarks/{owner}/{task}/{version}",
    )


def _archive(
    receipt_bytes: bytes = b"{}", *, receipt_name: str = RECEIPT_FILENAME
) -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        archive.writestr(receipt_name, receipt_bytes)
        archive.writestr("creation.log", "complete\n")
    return output.getvalue()


def _receipt(*, complete: bool) -> dict[str, object]:
    attempted = 6 if complete else 0
    return {
        "id": "receipt-id",
        "status": "complete" if complete else "blocked",
        "phase": "complete" if complete else "package_preflight",
        "calls": {
            "attempted": attempted,
            "completed": attempted,
            "activeCall": None,
        },
        "rows": [{} for _ in range(attempted)],
    }


class KaggleCreationOutputTests(unittest.TestCase):
    def test_gate_dataset_contract_is_fail_closed(self) -> None:
        _validate_gate_datasets("zero-call", ())
        _validate_gate_datasets("six-call", ("owner/dataset",))
        cases = {
            "zero-with-dataset": (
                "zero-call",
                ("owner/dataset",),
                "must expect no",
            ),
            "six-with-none": ("six-call", (), "exactly one"),
            "six-with-two": (
                "six-call",
                ("owner/one", "owner/two"),
                "exactly one",
            ),
            "unknown": ("other", (), "unknown gate"),
        }
        for name, (mode, datasets, message) in cases.items():
            with self.subTest(name=name), self.assertRaisesRegex(
                KaggleCreationOutputError, message
            ):
                _validate_gate_datasets(mode, datasets)

    def test_stream_download_is_bounded_without_content_length(self) -> None:
        response = SimpleNamespace(
            headers={},
            raise_for_status=mock.Mock(),
            iter_content=mock.Mock(return_value=iter((b"abc", b"", b"def"))),
            close=mock.Mock(),
        )
        self.assertEqual(_read_bounded_download(response), b"abcdef")
        response.raise_for_status.assert_called_once_with()
        response.iter_content.assert_called_once_with(chunk_size=1_048_576)
        response.close.assert_called_once_with()

    def test_stream_download_rejects_oversize_before_buffering(self) -> None:
        response = SimpleNamespace(
            headers={},
            raise_for_status=mock.Mock(),
            iter_content=mock.Mock(return_value=iter((b"abc", b"d"))),
            close=mock.Mock(),
        )
        with mock.patch.object(creation_output, "MAX_ARCHIVE_BYTES", 3):
            with self.assertRaisesRegex(
                KaggleCreationOutputError, "archive safety limit"
            ):
                _read_bounded_download(response)
        response.close.assert_called_once_with()

    def test_stream_download_rejects_announced_size_before_read(self) -> None:
        response = SimpleNamespace(
            headers={"Content-Length": "4"},
            raise_for_status=mock.Mock(),
            iter_content=mock.Mock(return_value=iter((b"data",))),
            close=mock.Mock(),
        )
        with mock.patch.object(creation_output, "MAX_ARCHIVE_BYTES", 3):
            with self.assertRaisesRegex(
                KaggleCreationOutputError, "archive safety limit"
            ):
                _read_bounded_download(response)
        response.iter_content.assert_not_called()
        response.close.assert_called_once_with()

    def test_download_requires_terminal_exact_source_kernel(self) -> None:
        self.assertEqual(_source_kernel_for_download(_task_info(), 12345), 12345)
        cases = {
            "pending": (
                _task_info(
                    state="BENCHMARK_TASK_VERSION_CREATION_STATE_RUNNING"
                ),
                12345,
                "not terminal",
            ),
            "missing": (_task_info(kernel_id=0), 12345, "no downloadable"),
            "drift": (_task_info(kernel_id=54321), 12345, "expected 12345"),
        }
        for name, (task_info, expected, message) in cases.items():
            with self.subTest(name=name), self.assertRaisesRegex(
                KaggleCreationOutputError, message
            ):
                _source_kernel_for_download(task_info, expected)

    def test_zero_call_bundle_binds_exact_task_version_and_kernel(self) -> None:
        receipt = _receipt(complete=False)
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(
            creation_output,
            "parse_kaggle_diagnostic_receipt_bytes",
            return_value=receipt,
        ) as parse_receipt:
            metadata, passed = write_creation_bundle(
                task_info=_task_info(),
                requested_task=(
                    "owner/aleph-bench-deployment-diagnostic-2048-none"
                ),
                expected_version=2,
                expected_source_kernel_id=12345,
                expected_datasets=(),
                archive_bytes=_archive(),
                gate_mode="zero-call",
                output_dir=Path(tmp),
            )

            self.assertTrue(passed)
            self.assertEqual(metadata["task"]["sourceKernelId"], 12345)
            self.assertEqual(metadata["task"]["version"], 2)
            self.assertTrue(metadata["gate"]["passed"])
            self.assertEqual(parse_receipt.call_count, 1)
            written = sorted(Path(tmp).iterdir())
            self.assertEqual(len(written), 3)
            metadata_path = next(
                path for path in written if path.name.endswith("-metadata.json")
            )
            self.assertEqual(
                json.loads(metadata_path.read_text(encoding="utf-8")), metadata
            )

    def test_incomplete_six_call_receipt_is_retained_but_fails_gate(self) -> None:
        receipt = _receipt(complete=False)
        dataset = "owner/aleph-bench-v02-scorer-conformance"
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(
            creation_output,
            "parse_kaggle_diagnostic_receipt_bytes",
            return_value=receipt,
        ):
            metadata, passed = write_creation_bundle(
                task_info=_task_info(datasets=(dataset,)),
                requested_task=(
                    "owner/aleph-bench-deployment-diagnostic-2048-none"
                ),
                expected_version=2,
                expected_source_kernel_id=12345,
                expected_datasets=(dataset,),
                archive_bytes=_archive(),
                gate_mode="six-call",
                output_dir=Path(tmp),
            )

            self.assertFalse(passed)
            self.assertFalse(metadata["gate"]["passed"])
            self.assertEqual(len(list(Path(tmp).iterdir())), 3)

    def test_complete_six_call_receipt_passes(self) -> None:
        receipt = _receipt(complete=True)
        dataset = "owner/aleph-bench-v02-scorer-conformance"
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(
            creation_output,
            "parse_kaggle_diagnostic_receipt_bytes",
            return_value=receipt,
        ):
            _, passed = write_creation_bundle(
                task_info=_task_info(datasets=(dataset,)),
                requested_task="aleph-bench-deployment-diagnostic-2048-none",
                expected_version=2,
                expected_source_kernel_id=12345,
                expected_datasets=(dataset,),
                archive_bytes=_archive(),
                gate_mode="six-call",
                output_dir=Path(tmp),
            )
            self.assertTrue(passed)

    def test_errored_creation_retains_call_ahead_receipt(self) -> None:
        receipt = _receipt(complete=False)
        receipt["phase"] = "model_calls"
        receipt["calls"] = {
            "attempted": 1,
            "completed": 0,
            "activeCall": {"state": "dispatching"},
        }
        task_info = _task_info(
            state="BENCHMARK_TASK_VERSION_CREATION_STATE_ERRORED",
            datasets=("owner/aleph-bench-v02-scorer-conformance",),
        )
        task_info.creation_error_message = "worker stopped"
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(
            creation_output,
            "parse_kaggle_diagnostic_receipt_bytes",
            return_value=receipt,
        ):
            metadata, passed = write_creation_bundle(
                task_info=task_info,
                requested_task=(
                    "owner/aleph-bench-deployment-diagnostic-2048-none"
                ),
                expected_version=2,
                expected_source_kernel_id=12345,
                expected_datasets=(
                    "owner/aleph-bench-v02-scorer-conformance",
                ),
                archive_bytes=_archive(),
                gate_mode="six-call",
                output_dir=Path(tmp),
            )
            self.assertFalse(passed)
            self.assertEqual(metadata["task"]["creationError"], "worker stopped")
            self.assertTrue(metadata["receipt"]["manualReviewRequired"])
            self.assertEqual(len(list(Path(tmp).iterdir())), 3)

    def test_refuses_task_version_dataset_and_state_drift(self) -> None:
        cases = {
            "version": (_task_info(version=3), (), "zero-call", "version 3"),
            "dataset": (
                _task_info(datasets=("owner/wrong",)),
                ("owner/expected",),
                "six-call",
                "datasets differ",
            ),
            "state": (
                _task_info(state="BENCHMARK_TASK_VERSION_CREATION_STATE_RUNNING"),
                (),
                "zero-call",
                "not complete",
            ),
            "kernel": (
                _task_info(kernel_id=0),
                (),
                "zero-call",
                "source_kernel_id",
            ),
        }
        for name, (task_info, datasets, gate, message) in cases.items():
            with self.subTest(name=name), tempfile.TemporaryDirectory() as tmp:
                with self.assertRaisesRegex(
                    KaggleCreationOutputError, message
                ):
                    write_creation_bundle(
                        task_info=task_info,
                        requested_task=(
                            "owner/aleph-bench-deployment-diagnostic-2048-none"
                        ),
                        expected_version=2,
                        expected_source_kernel_id=12345,
                        expected_datasets=datasets,
                        archive_bytes=_archive(),
                        gate_mode=gate,
                        output_dir=Path(tmp),
                    )

    def test_rejects_duplicate_missing_and_unsafe_receipt_entries(self) -> None:
        duplicate = io.BytesIO()
        with zipfile.ZipFile(duplicate, "w") as archive:
            archive.writestr(RECEIPT_FILENAME, "{}")
            archive.writestr(f"nested/{RECEIPT_FILENAME}", "{}")
        cases = {
            "duplicate": (duplicate.getvalue(), "exactly one"),
            "missing": (_archive(receipt_name="other.json"), "exactly one"),
            "unsafe": (
                _archive(receipt_name=f"../{RECEIPT_FILENAME}"),
                "unsafe creation archive entry",
            ),
        }
        for name, (archive_bytes, message) in cases.items():
            with self.subTest(name=name), tempfile.TemporaryDirectory() as tmp:
                with self.assertRaisesRegex(
                    KaggleCreationOutputError, message
                ):
                    write_creation_bundle(
                        task_info=_task_info(),
                        requested_task=(
                            "owner/aleph-bench-deployment-diagnostic-2048-none"
                        ),
                        expected_version=2,
                        expected_source_kernel_id=12345,
                        expected_datasets=(),
                        archive_bytes=archive_bytes,
                        gate_mode="zero-call",
                        output_dir=Path(tmp),
                    )

    def test_refuses_to_overwrite_retained_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(
            creation_output,
            "parse_kaggle_diagnostic_receipt_bytes",
            return_value=_receipt(complete=False),
        ):
            kwargs = {
                "task_info": _task_info(),
                "requested_task": (
                    "owner/aleph-bench-deployment-diagnostic-2048-none"
                ),
                "expected_version": 2,
                "expected_source_kernel_id": 12345,
                "expected_datasets": (),
                "archive_bytes": _archive(),
                "gate_mode": "zero-call",
                "output_dir": Path(tmp),
            }
            write_creation_bundle(**kwargs)
            with self.assertRaisesRegex(
                KaggleCreationOutputError, "refusing to overwrite"
            ):
                write_creation_bundle(**kwargs)

if __name__ == "__main__":
    unittest.main()
