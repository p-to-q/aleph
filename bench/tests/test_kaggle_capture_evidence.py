from __future__ import annotations

import io
import json
import sys
import tempfile
import unittest
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from bench.engine.kaggle_capture import (
    artifact_id_for,
    serialize_capture_payload,
)
from bench.engine.kaggle_capture_evidence import (
    CAPTURE_FILENAME,
    KaggleCaptureEvidenceError,
    verify_capture_evidence,
    write_capture_evidence_bundle,
)
from bench.tasks.kaggle.generate_v0_2_capture import OUTPUT_PATH
from bench.tests.test_kaggle_capture_task_v0_2 import (
    OpenAI,
    RUNTIME_313,
    _Chats,
    _Clock,
    _load_generated_task,
    _write_package,
)


TASK_SLUG = "aleph-bench-v0-2-capture-canary"
DATASET = "owner/aleph-bench-v02-scorer-conformance"
DOWNLOADED_AT = "2026-09-22T00:02:00Z"


def _task_info(
    *,
    version: int = 3,
    state: str = "BENCHMARK_TASK_VERSION_CREATION_STATE_COMPLETED",
    datasets: tuple[str, ...] = (DATASET,),
) -> SimpleNamespace:
    return SimpleNamespace(
        slug=SimpleNamespace(
            owner_slug="owner",
            task_slug=TASK_SLUG,
            version_number=version,
        ),
        creation_state=state,
        creation_error_message="platform detail" if state.endswith("ERRORED") else None,
        error=None,
        source_kernel_id=12345,
        options=SimpleNamespace(dataset_data_sources=list(datasets)),
        create_time=datetime(2026, 9, 21, 23, 58, tzinfo=timezone.utc),
        url=f"https://www.kaggle.com/benchmarks/owner/{TASK_SLUG}/{version}",
    )


def _run_info(
    *,
    version: int = 3,
    model: str = "google/gemini-2.5-flash",
    state: str = "BENCHMARK_TASK_RUN_STATE_COMPLETED",
    start: datetime | None = None,
    end: datetime | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        task_slug=SimpleNamespace(
            owner_slug="owner",
            task_slug=TASK_SLUG,
            version_number=version,
        ),
        id=24680,
        model_version_slug=model,
        state=state,
        error_message="run detail" if state.endswith("ERRORED") else None,
        start_time=start or datetime(2026, 9, 21, 23, 59, tzinfo=timezone.utc),
        end_time=end or datetime(2026, 9, 22, 0, 1, tzinfo=timezone.utc),
    )


def _archive(
    payload_bytes: bytes,
    source_bytes: bytes,
    *,
    notebook: bool = False,
    strip_notebook_shebang: bool = False,
    extra_payload: bool = False,
    extra_source: bool = False,
) -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        archive.writestr(f"output/{CAPTURE_FILENAME}", payload_bytes)
        if extra_payload:
            archive.writestr(f"duplicate/{CAPTURE_FILENAME}", payload_bytes)
        if notebook:
            notebook_source = source_bytes.decode("utf-8")
            if strip_notebook_shebang:
                self_contained_shebang = "#!/usr/bin/env python3\n"
                if not notebook_source.startswith(self_contained_shebang):
                    raise AssertionError("test source is missing the expected shebang")
                notebook_source = notebook_source[len(self_contained_shebang) :]
                if not notebook_source.endswith("\n"):
                    raise AssertionError("test source is missing the expected final newline")
                notebook_source = notebook_source[:-1]
            notebook_bytes = (
                json.dumps(
                    {
                        "cells": [
                            {
                                "cell_type": "code",
                                "metadata": {},
                                "source": notebook_source,
                            }
                        ],
                        "metadata": {},
                        "nbformat": 4,
                        "nbformat_minor": 5,
                    },
                    sort_keys=True,
                )
                + "\n"
            ).encode("utf-8")
            archive.writestr("source/__notebook__.ipynb", notebook_bytes)
        else:
            archive.writestr("source/task.py", source_bytes)
        if extra_source:
            archive.writestr("source/task-copy.py", source_bytes)
        archive.writestr("logs/run.log", "complete\n")
    return output.getvalue()


class KaggleCaptureEvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.generated, cls.previous_kaggle_module = _load_generated_task()
        cls.package_tmp = tempfile.TemporaryDirectory()
        cls.package_root = Path(cls.package_tmp.name) / "package"
        cls.package_root.mkdir()
        _write_package(cls.package_root)
        cls.source_bytes = OUTPUT_PATH.read_bytes()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.package_tmp.cleanup()
        if cls.previous_kaggle_module is None:
            sys.modules.pop("kaggle_benchmarks", None)
        else:
            sys.modules["kaggle_benchmarks"] = cls.previous_kaggle_module

    def _payload_bytes(self, *, finish_reason: str | None = "stop") -> bytes:
        output_tmp = tempfile.TemporaryDirectory()
        self.addCleanup(output_tmp.cleanup)
        capture_path = Path(output_tmp.name) / "capture.json"
        self.generated.run_capture_canary(
            OpenAI(),
            chats=_Chats(finish_reason=finish_reason),
            package_root=self.package_root,
            capture_path=capture_path,
            observed_runtime=RUNTIME_313,
            clock=_Clock(),
        )
        return capture_path.read_bytes()

    def _blocked_payload_bytes(self) -> bytes:
        output_tmp = tempfile.TemporaryDirectory()
        self.addCleanup(output_tmp.cleanup)
        empty_package = Path(output_tmp.name) / "empty-package"
        empty_package.mkdir()
        capture_path = Path(output_tmp.name) / "capture.json"
        self.generated.run_capture_canary(
            OpenAI(),
            chats=_Chats(),
            package_root=empty_package,
            capture_path=capture_path,
            observed_runtime=RUNTIME_313,
            clock=_Clock(),
        )
        return capture_path.read_bytes()

    def _write(
        self,
        *,
        archive_bytes: bytes,
        task_info: SimpleNamespace | None = None,
        run_info: SimpleNamespace | None = None,
        output_dir: Path | None = None,
    ) -> tuple[dict[str, Any], Path, tempfile.TemporaryDirectory[str] | None]:
        output_tmp = None
        if output_dir is None:
            output_tmp = tempfile.TemporaryDirectory()
            self.addCleanup(output_tmp.cleanup)
            output_dir = Path(output_tmp.name) / "evidence"
        evidence = write_capture_evidence_bundle(
            task_info=task_info or _task_info(),
            run_info=run_info or _run_info(),
            requested_task=f"owner/{TASK_SLUG}",
            expected_version=3,
            expected_source_kernel_id=12345,
            expected_run_id=24680,
            expected_datasets=(DATASET,),
            archive_bytes=archive_bytes,
            output_dir=output_dir,
            downloaded_at=DOWNLOADED_AT,
        )
        return evidence, output_dir, output_tmp

    def test_exact_run_bundle_preserves_and_verifies_all_bytes(self) -> None:
        payload_bytes = self._payload_bytes()
        archive_bytes = _archive(payload_bytes, self.source_bytes)
        evidence, output_dir, output_tmp = self._write(archive_bytes=archive_bytes)
        self.assertIsNotNone(output_tmp)

        self.assertTrue(evidence["assemblyEligible"])
        self.assertIsNone(evidence["task"]["creationErrorStringSha256"])
        self.assertIsNone(evidence["run"]["errorStringSha256"])
        archive_copy = (output_dir / evidence["archive"]["file"]).read_bytes()
        payload_copy = (output_dir / evidence["payload"]["file"]).read_bytes()
        source_copy = (output_dir / evidence["source"]["file"]).read_bytes()
        self.assertEqual(archive_copy, archive_bytes)
        self.assertEqual(payload_copy, payload_bytes)
        self.assertEqual(source_copy, self.source_bytes)
        self.assertEqual(
            verify_capture_evidence(
                evidence,
                archive_bytes=archive_copy,
                payload_bytes=payload_copy,
                source_bytes=source_copy,
            ),
            evidence,
        )

    def test_missing_finish_reason_is_bound_and_assembly_eligible(self) -> None:
        payload_bytes = self._payload_bytes(finish_reason=None)
        evidence, _, output_tmp = self._write(
            archive_bytes=_archive(payload_bytes, self.source_bytes)
        )
        self.assertIsNotNone(output_tmp)
        self.assertTrue(evidence["assemblyEligible"])
        self.assertTrue(evidence["payload"]["canonicalReplayEligible"])

    def test_zero_call_preflight_block_is_retained_as_ineligible_evidence(self) -> None:
        payload_bytes = self._blocked_payload_bytes()
        evidence, _, output_tmp = self._write(
            archive_bytes=_archive(payload_bytes, self.source_bytes)
        )
        self.assertIsNotNone(output_tmp)
        self.assertFalse(evidence["assemblyEligible"])
        self.assertFalse(evidence["payload"]["captureComplete"])
        self.assertEqual(
            evidence["run"]["modelVersionSlug"],
            "google/gemini-2.5-flash",
        )

    def test_exact_notebook_code_cell_source_is_accepted(self) -> None:
        payload_bytes = self._payload_bytes()
        evidence, _, output_tmp = self._write(
            archive_bytes=_archive(
                payload_bytes,
                self.source_bytes,
                notebook=True,
            )
        )
        self.assertIsNotNone(output_tmp)
        self.assertEqual(evidence["source"]["archiveKind"], "notebookCodeCell")
        self.assertEqual(evidence["source"]["notebookCellIndex"], 0)

    def test_jupytext_shebang_elision_is_accepted_and_full_source_retained(self) -> None:
        payload_bytes = self._payload_bytes()
        evidence, output_dir, output_tmp = self._write(
            archive_bytes=_archive(
                payload_bytes,
                self.source_bytes,
                notebook=True,
                strip_notebook_shebang=True,
            )
        )
        self.assertIsNotNone(output_tmp)
        self.assertEqual(evidence["source"]["archiveKind"], "notebookCodeCell")
        retained = (output_dir / evidence["source"]["file"]).read_bytes()
        self.assertEqual(retained, self.source_bytes)

    def test_archive_confusion_fails_closed(self) -> None:
        payload_bytes = self._payload_bytes()
        cases = {
            "duplicate-payload": (
                _archive(
                    payload_bytes,
                    self.source_bytes,
                    extra_payload=True,
                ),
                "exactly one raw payload",
            ),
            "duplicate-source": (
                _archive(
                    payload_bytes,
                    self.source_bytes,
                    extra_source=True,
                ),
                "exactly one matching task source",
            ),
            "wrong-source": (
                _archive(payload_bytes, self.source_bytes + b"# drift\n"),
                "exactly one matching task source",
            ),
        }
        for name, (archive_bytes, message) in cases.items():
            with self.subTest(name=name), self.assertRaisesRegex(
                KaggleCaptureEvidenceError, message
            ):
                self._write(archive_bytes=archive_bytes)

    def test_payload_contract_and_run_model_drift_fail_closed(self) -> None:
        payload = json.loads(self._payload_bytes().decode("utf-8"))
        payload["taskIdentity"]["definitionSha256"] = "0" * 64
        payload["id"] = artifact_id_for(payload)
        drifted_payload = serialize_capture_payload(payload)
        with self.assertRaisesRegex(
            KaggleCaptureEvidenceError, "taskIdentity drifted"
        ):
            self._write(
                archive_bytes=_archive(drifted_payload, self.source_bytes)
            )

        payload_bytes = self._payload_bytes()
        with self.assertRaisesRegex(
            KaggleCaptureEvidenceError, "run model differs"
        ):
            self._write(
                archive_bytes=_archive(payload_bytes, self.source_bytes),
                run_info=_run_info(model="other/model"),
            )

    def test_terminal_error_is_retained_without_raw_platform_message(self) -> None:
        payload_bytes = self._payload_bytes()
        evidence, _, output_tmp = self._write(
            archive_bytes=_archive(payload_bytes, self.source_bytes),
            task_info=_task_info(
                state="BENCHMARK_TASK_VERSION_CREATION_STATE_ERRORED"
            ),
            run_info=_run_info(state="BENCHMARK_TASK_RUN_STATE_ERRORED"),
        )
        self.assertIsNotNone(output_tmp)
        self.assertFalse(evidence["assemblyEligible"])
        serialized = json.dumps(evidence)
        self.assertNotIn("platform detail", serialized)
        self.assertNotIn("run detail", serialized)
        self.assertRegex(
            evidence["task"]["creationErrorStringSha256"], r"^[0-9a-f]{64}$"
        )
        self.assertRegex(
            evidence["run"]["errorStringSha256"], r"^[0-9a-f]{64}$"
        )

    def test_run_interval_and_existing_outputs_fail_closed(self) -> None:
        payload_bytes = self._payload_bytes()
        archive_bytes = _archive(payload_bytes, self.source_bytes)
        with self.assertRaisesRegex(
            KaggleCaptureEvidenceError, "starts before"
        ):
            self._write(
                archive_bytes=archive_bytes,
                run_info=_run_info(
                    start=datetime(2026, 9, 22, 0, 0, 30, tzinfo=timezone.utc)
                ),
            )

        output_tmp = tempfile.TemporaryDirectory()
        self.addCleanup(output_tmp.cleanup)
        output_dir = Path(output_tmp.name) / "evidence"
        self._write(archive_bytes=archive_bytes, output_dir=output_dir)
        before = {
            path.name: path.read_bytes() for path in output_dir.iterdir()
        }
        with self.assertRaisesRegex(
            KaggleCaptureEvidenceError, "refusing to overwrite"
        ):
            self._write(archive_bytes=archive_bytes, output_dir=output_dir)
        self.assertEqual(
            {path.name: path.read_bytes() for path in output_dir.iterdir()},
            before,
        )


if __name__ == "__main__":
    unittest.main()
