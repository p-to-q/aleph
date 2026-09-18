from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import re
import sys
import zipfile
from datetime import datetime
from pathlib import Path, PurePosixPath
from typing import Any

from .kaggle_diagnostic_receipt import (
    MAX_RECEIPT_BYTES,
    parse_kaggle_diagnostic_receipt_bytes,
)


RECEIPT_FILENAME = "aleph-bench-v0.2-kaggle-diagnostic-receipt.json"
MAX_ARCHIVE_BYTES = 268_435_456
MAX_ARCHIVE_ENTRIES = 4_096
MAX_ARCHIVE_UNCOMPRESSED_BYTES = 1_073_741_824
_SLUG_SEGMENT = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,98}[a-z0-9])?$")


class KaggleCreationOutputError(ValueError):
    """Raised when a task-creation output cannot be bound and verified."""


def _fail(message: str) -> None:
    raise KaggleCreationOutputError(message)


def _write_exclusive(path: Path, data: bytes) -> None:
    # Exclusive creation closes the race between a preflight exists check and
    # the write; an older task version must never be silently overwritten.
    with path.open("xb") as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())


def _parse_task_slug(value: str) -> tuple[str | None, str]:
    parts = value.split("/")
    if len(parts) == 1:
        owner = None
        task = parts[0]
    elif len(parts) == 2:
        owner, task = parts
    else:
        _fail("task must be TASK or OWNER/TASK")
    for role, segment in (("owner", owner), ("task", task)):
        if segment is not None and not _SLUG_SEGMENT.fullmatch(segment):
            _fail(f"invalid Kaggle {role} slug: {segment!r}")
    return owner, task


def _enum_name(value: Any) -> str:
    name = getattr(value, "name", None)
    if isinstance(name, str) and name:
        return name
    return str(value).rsplit(".", 1)[-1]


def _task_metadata(
    task_info: Any,
    *,
    requested_task: str,
    expected_version: int,
    expected_source_kernel_id: int,
    expected_datasets: tuple[str, ...],
) -> dict[str, Any]:
    requested_owner, requested_slug = _parse_task_slug(requested_task)
    response_slug = getattr(task_info, "slug", None)
    if response_slug is None:
        _fail("Kaggle task response has no version slug")
    actual_owner = getattr(response_slug, "owner_slug", None) or None
    actual_slug = getattr(response_slug, "task_slug", None)
    actual_version = getattr(response_slug, "version_number", None)
    if actual_slug != requested_slug:
        _fail(
            f"Kaggle returned task {actual_slug!r}, expected {requested_slug!r}"
        )
    if requested_owner is not None and actual_owner != requested_owner:
        _fail(
            f"Kaggle returned owner {actual_owner!r}, expected {requested_owner!r}"
        )
    if actual_version != expected_version:
        _fail(
            f"Kaggle returned task version {actual_version!r}, "
            f"expected {expected_version}"
        )

    state = _enum_name(getattr(task_info, "creation_state", None))
    if state not in {
        "BENCHMARK_TASK_VERSION_CREATION_STATE_COMPLETED",
        "BENCHMARK_TASK_VERSION_CREATION_STATE_ERRORED",
    }:
        error = getattr(task_info, "creation_error_message", None) or getattr(
            task_info, "error", None
        )
        suffix = f": {error}" if error else ""
        _fail(f"task creation is not complete ({state}){suffix}")

    source_kernel_id = getattr(task_info, "source_kernel_id", None)
    if (
        isinstance(source_kernel_id, bool)
        or not isinstance(source_kernel_id, int)
        or source_kernel_id <= 0
    ):
        _fail("completed task version has no positive source_kernel_id")
    if source_kernel_id != expected_source_kernel_id:
        _fail(
            f"Kaggle returned source kernel {source_kernel_id}, "
            f"expected {expected_source_kernel_id}"
        )

    options = getattr(task_info, "options", None)
    actual_datasets = tuple(
        sorted(getattr(options, "dataset_data_sources", None) or ())
    )
    expected_sorted = tuple(sorted(expected_datasets))
    if actual_datasets != expected_sorted:
        _fail(
            "attached Kaggle datasets differ: "
            f"expected {list(expected_sorted)!r}, found {list(actual_datasets)!r}"
        )

    create_time = getattr(task_info, "create_time", None)
    if isinstance(create_time, datetime):
        create_time_value: str | None = create_time.isoformat()
    elif create_time is None:
        create_time_value = None
    else:
        create_time_value = str(create_time)
    return {
        "requested": requested_task,
        "owner": actual_owner,
        "slug": actual_slug,
        "version": actual_version,
        "sourceKernelId": source_kernel_id,
        "creationState": state,
        "creationError": (
            getattr(task_info, "creation_error_message", None)
            or getattr(task_info, "error", None)
            or None
        ),
        "createTime": create_time_value,
        "url": getattr(task_info, "url", None) or None,
        "datasets": list(actual_datasets),
    }


def _safe_archive_entry(info: zipfile.ZipInfo) -> None:
    name = info.filename
    if not name or "\\" in name or "\x00" in name:
        _fail(f"unsafe creation archive entry: {name!r}")
    path = PurePosixPath(name)
    if path.is_absolute() or ".." in path.parts:
        _fail(f"unsafe creation archive entry: {name!r}")
    unix_mode = (info.external_attr >> 16) & 0o170000
    if unix_mode == 0o120000:
        _fail(f"symlink creation archive entry is forbidden: {name!r}")


def _extract_verified_receipt(
    archive_bytes: bytes,
) -> tuple[bytes, dict[str, Any], str]:
    if len(archive_bytes) > MAX_ARCHIVE_BYTES:
        _fail(
            f"creation archive exceeds the {MAX_ARCHIVE_BYTES}-byte safety limit"
        )
    try:
        with zipfile.ZipFile(io.BytesIO(archive_bytes)) as archive:
            infos = archive.infolist()
            if len(infos) > MAX_ARCHIVE_ENTRIES:
                _fail("creation archive has too many entries")
            total_size = 0
            matches: list[zipfile.ZipInfo] = []
            for info in infos:
                _safe_archive_entry(info)
                total_size += info.file_size
                if total_size > MAX_ARCHIVE_UNCOMPRESSED_BYTES:
                    _fail("creation archive uncompressed size exceeds the safety limit")
                if PurePosixPath(info.filename).name == RECEIPT_FILENAME:
                    matches.append(info)
            if len(matches) != 1:
                _fail(
                    "creation archive must contain exactly one diagnostic receipt; "
                    f"found {len(matches)}"
                )
            receipt_info = matches[0]
            if receipt_info.file_size > MAX_RECEIPT_BYTES:
                _fail("creation receipt exceeds the safety limit")
            receipt_bytes = archive.read(receipt_info)
    except zipfile.BadZipFile as exc:
        raise KaggleCreationOutputError(
            f"Kaggle creation output is not a valid zip archive: {exc}"
        ) from exc
    receipt = parse_kaggle_diagnostic_receipt_bytes(receipt_bytes)
    return receipt_bytes, receipt, receipt_info.filename


def _gate_result(receipt: dict[str, Any], mode: str) -> tuple[bool, str]:
    calls = receipt["calls"]
    if mode == "zero-call":
        passed = (
            receipt["status"] == "blocked"
            and receipt["phase"] == "package_preflight"
            and calls["attempted"] == 0
            and calls["completed"] == 0
            and calls["activeCall"] is None
            and receipt["rows"] == []
        )
        return passed, (
            "package preflight blocked before every model call"
            if passed
            else "receipt did not prove the zero-call package gate"
        )
    if mode == "six-call":
        passed = (
            receipt["status"] == "complete"
            and calls["attempted"] == 6
            and calls["completed"] == 6
            and calls["activeCall"] is None
            and len(receipt["rows"]) == 6
        )
        return passed, (
            "all six diagnostic calls completed"
            if passed
            else "receipt retained but the six-call canary did not complete"
        )
    _fail(f"unknown gate mode: {mode!r}")


def _validate_gate_datasets(mode: str, datasets: tuple[str, ...]) -> None:
    if mode == "zero-call":
        if datasets:
            _fail("zero-call gate must expect no attached datasets")
        return
    if mode == "six-call":
        if len(datasets) != 1:
            _fail("six-call gate must expect exactly one attached dataset")
        return
    _fail(f"unknown gate mode: {mode!r}")


def _source_kernel_for_download(
    task_info: Any, expected_source_kernel_id: int
) -> int:
    """Bind a terminal task response to the journaled creation kernel."""

    creation_state = _enum_name(getattr(task_info, "creation_state", None))
    if creation_state not in {
        "BENCHMARK_TASK_VERSION_CREATION_STATE_COMPLETED",
        "BENCHMARK_TASK_VERSION_CREATION_STATE_ERRORED",
    }:
        _fail(
            "task creation is not terminal; wait and retry this read-only "
            f"download ({creation_state})"
        )
    source_kernel_id = getattr(task_info, "source_kernel_id", None)
    if (
        isinstance(source_kernel_id, bool)
        or not isinstance(source_kernel_id, int)
        or source_kernel_id <= 0
    ):
        _fail("task version has no downloadable source kernel")
    if source_kernel_id != expected_source_kernel_id:
        _fail(
            f"Kaggle returned source kernel {source_kernel_id}, "
            f"expected {expected_source_kernel_id}"
        )
    return source_kernel_id


def _read_bounded_download(response: Any) -> bytes:
    """Consume a streamed SDK download without an unbounded `.content` read."""

    close = getattr(response, "close", None)
    try:
        raise_for_status = getattr(response, "raise_for_status", None)
        if callable(raise_for_status):
            raise_for_status()
        headers = getattr(response, "headers", {}) or {}
        content_length = headers.get("Content-Length") or headers.get(
            "content-length"
        )
        announced_bytes: int | None = None
        if content_length is not None:
            try:
                announced_bytes = int(content_length)
            except (TypeError, ValueError) as exc:
                raise KaggleCreationOutputError(
                    "Kaggle creation output has an invalid Content-Length"
                ) from exc
            if announced_bytes < 0:
                _fail("Kaggle creation output has a negative Content-Length")
            if announced_bytes > MAX_ARCHIVE_BYTES:
                _fail("Kaggle creation output exceeds the archive safety limit")

        iter_content = getattr(response, "iter_content", None)
        if not callable(iter_content):
            _fail("Kaggle creation output response is not stream-readable")
        body = bytearray()
        for chunk in iter_content(chunk_size=1_048_576):
            if not chunk:
                continue
            if not isinstance(chunk, (bytes, bytearray)):
                _fail("Kaggle creation output stream yielded non-byte content")
            if len(body) + len(chunk) > MAX_ARCHIVE_BYTES:
                _fail("Kaggle creation output exceeds the archive safety limit")
            body.extend(chunk)
        if announced_bytes is not None and len(body) != announced_bytes:
            _fail(
                "Kaggle creation output length differs from Content-Length: "
                f"expected {announced_bytes}, received {len(body)}"
            )
        return bytes(body)
    finally:
        if callable(close):
            close()


def write_creation_bundle(
    *,
    task_info: Any,
    requested_task: str,
    expected_version: int,
    expected_source_kernel_id: int,
    expected_datasets: tuple[str, ...],
    archive_bytes: bytes,
    gate_mode: str,
    output_dir: Path,
) -> tuple[dict[str, Any], bool]:
    """Validate and persist one exact task-creation archive and receipt."""

    _validate_gate_datasets(gate_mode, expected_datasets)
    task = _task_metadata(
        task_info,
        requested_task=requested_task,
        expected_version=expected_version,
        expected_source_kernel_id=expected_source_kernel_id,
        expected_datasets=expected_datasets,
    )
    receipt_bytes, receipt, receipt_entry = _extract_verified_receipt(
        archive_bytes
    )
    gate_passed, gate_message = _gate_result(receipt, gate_mode)
    if task["creationState"] != "BENCHMARK_TASK_VERSION_CREATION_STATE_COMPLETED":
        gate_passed = False
        gate_message = (
            "creation kernel errored; receipt retained for manual review"
        )
    stem = f"{task['slug']}-v{expected_version}-creation-{task['sourceKernelId']}"
    output_dir.mkdir(parents=True, exist_ok=True)
    archive_path = output_dir / f"{stem}.zip"
    receipt_path = output_dir / f"{stem}-receipt.json"
    metadata_path = output_dir / f"{stem}-metadata.json"
    for path in (archive_path, receipt_path, metadata_path):
        if path.exists():
            _fail(f"refusing to overwrite existing creation artifact: {path}")

    metadata = {
        "artifactKind": "kaggle_task_creation_bundle",
        "task": task,
        "archive": {
            "file": archive_path.name,
            "bytes": len(archive_bytes),
            "sha256": hashlib.sha256(archive_bytes).hexdigest(),
            "receiptEntry": receipt_entry,
        },
        "receipt": {
            "file": receipt_path.name,
            "id": receipt["id"],
            "status": receipt["status"],
            "phase": receipt["phase"],
            "attempted": receipt["calls"]["attempted"],
            "completed": receipt["calls"]["completed"],
            "activeCall": receipt["calls"]["activeCall"],
            "manualReviewRequired": (
                task["creationState"]
                != "BENCHMARK_TASK_VERSION_CREATION_STATE_COMPLETED"
                or receipt["calls"]["activeCall"] is not None
                or (
                    receipt["status"] == "blocked"
                    and receipt["calls"]["attempted"] > 0
                )
            ),
        },
        "gate": {
            "mode": gate_mode,
            "passed": gate_passed,
            "message": gate_message,
        },
    }
    metadata_bytes = (
        json.dumps(metadata, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")
    written: list[Path] = []
    try:
        for path, data in (
            (archive_path, archive_bytes),
            (receipt_path, receipt_bytes),
            (metadata_path, metadata_bytes),
        ):
            _write_exclusive(path, data)
            written.append(path)
    except Exception:
        # Only remove files created by this invocation; pre-existing evidence
        # is protected by exclusive creation above.
        for path in reversed(written):
            try:
                path.unlink()
            except OSError:
                pass
        raise
    return metadata, gate_passed


def _download_creation_archive(
    task: str, version: int, expected_source_kernel_id: int
) -> tuple[Any, bytes]:
    try:
        from kaggle.api.kaggle_api_extended import KaggleApi
        from kagglesdk.benchmarks.types.benchmark_tasks_api_service import (
            ApiBenchmarkTaskSlug,
            ApiGetBenchmarkTaskRequest,
        )
        from kagglesdk.kernels.types.kernels_api_service import (
            ApiDownloadKernelOutputZipRequest,
        )
    except ImportError as exc:
        raise KaggleCreationOutputError(
            "Kaggle CLI 2.2.4 or newer is required to download creation output"
        ) from exc

    owner, task_slug = _parse_task_slug(task)
    slug = ApiBenchmarkTaskSlug()
    if owner is not None:
        slug.owner_slug = owner
    slug.task_slug = task_slug
    slug.version_number = version
    get_request = ApiGetBenchmarkTaskRequest()
    get_request.slug = slug

    api = KaggleApi()
    api.authenticate()
    with api.build_kaggle_client() as client:
        get_task = client.benchmarks.benchmark_tasks_api_client.get_benchmark_task
        task_info = api.with_retry(get_task)(get_request)
        source_kernel_id = _source_kernel_for_download(
            task_info, expected_source_kernel_id
        )
        output_request = ApiDownloadKernelOutputZipRequest()
        output_request.kernel_session_id = source_kernel_id
        download = client.kernels.kernels_api_client.download_kernel_output_zip
        response = api.with_retry(download)(output_request)
        return task_info, _read_bounded_download(response)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Download and verify the backing kernel output for one exact "
            "Kaggle benchmark task version without scheduling a model run."
        )
    )
    parser.add_argument("task", help="TASK or OWNER/TASK slug")
    parser.add_argument("--version", type=int, required=True)
    parser.add_argument("--source-kernel-id", type=int, required=True)
    parser.add_argument(
        "--gate", choices=("zero-call", "six-call"), required=True
    )
    datasets = parser.add_mutually_exclusive_group(required=True)
    datasets.add_argument(
        "--expect-no-datasets", action="store_true"
    )
    datasets.add_argument(
        "--expect-dataset", action="append", default=[]
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)
    if args.version <= 0:
        parser.error("--version must be positive")
    if args.source_kernel_id <= 0:
        parser.error("--source-kernel-id must be positive")
    expected_datasets = (
        () if args.expect_no_datasets else tuple(args.expect_dataset)
    )
    try:
        task_info, archive_bytes = _download_creation_archive(
            args.task, args.version, args.source_kernel_id
        )
        metadata, passed = write_creation_bundle(
            task_info=task_info,
            requested_task=args.task,
            expected_version=args.version,
            expected_source_kernel_id=args.source_kernel_id,
            expected_datasets=expected_datasets,
            archive_bytes=archive_bytes,
            gate_mode=args.gate,
            output_dir=args.output,
        )
    except (OSError, ValueError) as exc:
        print(f"invalid Kaggle creation output: {exc}", file=sys.stderr)
        return 1
    print(
        f"retained task {metadata['task']['slug']} v{metadata['task']['version']} "
        f"creation kernel {metadata['task']['sourceKernelId']}: "
        f"{metadata['gate']['message']}"
    )
    return 0 if passed else 2


if __name__ == "__main__":
    raise SystemExit(main())
