from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import os
import re
import stat
import sys
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Callable, Iterable, Sequence

from bench.engine.kaggle_push_once import (
    CAPTURE_OUTPUT_PATH,
    CAPTURE_TASK_SLUG,
    CREATION_JOURNAL_VERSION,
    KagglePushOnceError,
    NOTEBOOK_IDENTITY_PROFILE,
    REQUIRED_CLIENT_VERSIONS,
    _canonical_json_bytes,
    _enum_name,
    _exact_source_and_notebook,
    _exception_record,
    _fsync_parent_directory,
    _replace_journal,
    _utc_now,
    _verified_client_versions,
    _write_initial_journal,
    render_capture_task_source,
)
from bench.tasks.kaggle.generate_v0_2_capture import TASK_SOURCE_PATH


_SLUG_PART = re.compile(
    r"^[a-z0-9](?:[a-z0-9_-]{0,98}[a-z0-9])?$"
)
_MODEL_SLUG = re.compile(
    r"^[a-z0-9](?:[a-z0-9._-]{0,198}[a-z0-9])?$"
)
_COMPLETED_TASK_STATE = "BENCHMARK_TASK_VERSION_CREATION_STATE_COMPLETED"
_TERMINAL_RUN_STATES = {
    "BENCHMARK_TASK_RUN_STATE_COMPLETED",
    "BENCHMARK_TASK_RUN_STATE_ERRORED",
}
_ACKNOWLEDGED_CREATION_STATES = {
    "BENCHMARK_TASK_VERSION_CREATION_STATE_UNSPECIFIED",
    "BENCHMARK_TASK_VERSION_CREATION_STATE_QUEUED",
    "BENCHMARK_TASK_VERSION_CREATION_STATE_RUNNING",
    "BENCHMARK_TASK_VERSION_CREATION_STATE_COMPLETED",
}
_CREATION_ONLY_TASK_VERSION_CEILINGS = {
    ("jahyee", CAPTURE_TASK_SLUG): 8,
}
DEFAULT_RECONCILE_DELAYS_SECONDS = (0.0, 1.0, 2.0, 4.0, 8.0)
MAX_CREATION_JOURNAL_BYTES = 2_097_152
_DISPATCH_CLAIM_DIRECTORY = ".aleph-kaggle-run-claims"
_CREATION_JOURNAL_ROOT_FIELDS = {
    "artifactKind",
    "client",
    "createdAt",
    "datasets",
    "failure",
    "gate",
    "journalVersion",
    "operationId",
    "remotePreflight",
    "response",
    "source",
    "state",
    "task",
    "updatedAt",
}
_CREATION_RESPONSE_FIELDS = {
    "creationState",
    "datasets",
    "owner",
    "sourceKernelId",
    "task",
    "url",
    "version",
}
_CREATION_SOURCE_FIELDS = {
    "bytes",
    "notebookProfile",
    "notebookSha256",
    "path",
    "sha256",
}
_CREATION_AUTHORITY_FIELDS = {
    "canonicalBytes",
    "canonicalSha256",
    "journal",
    "source",
    "task",
}
_CREATION_AUTHORITY_TASK_FIELDS = {
    "acknowledgedSourceKernelId",
    "datasets",
    "owner",
    "resolvedSourceKernelId",
    "task",
    "version",
}
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_PYTHON_313 = re.compile(r"^3\.13(?:\.\d+)(?:[+._-][A-Za-z0-9._-]+)?$")
_DATASET_SLUG = re.compile(
    r"^[a-z0-9](?:[a-z0-9_-]{0,98}[a-z0-9])?/"
    r"[a-z0-9](?:[a-z0-9_-]{0,98}[a-z0-9])?$"
)


class KaggleRunOnceError(KagglePushOnceError):
    """Raised before dispatch, or after a conclusively skipped schedule."""


class KaggleRunOutcomeAmbiguous(KaggleRunOnceError):
    """Raised after dispatch when the unique paid run cannot be proved."""


@dataclass(frozen=True, slots=True)
class VerifiedCreationAuthority:
    """One strict canonical capture-task creation receipt."""

    journal: dict[str, Any]
    canonical_bytes: bytes
    source: dict[str, Any]
    response: dict[str, Any]


def _authority_object(value: Any, *, role: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise KaggleRunOnceError(f"creation authority {role} must be an object")
    return value


def _authority_exact_fields(
    value: dict[str, Any], expected: set[str], *, role: str
) -> None:
    if set(value) != expected:
        raise KaggleRunOnceError(
            f"creation authority {role} has invalid fields"
        )


def _authority_positive_int(value: Any, *, role: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise KaggleRunOnceError(
            f"creation authority {role} must be a positive integer"
        )
    return value


def _authority_optional_positive_int(value: Any, *, role: str) -> int | None:
    if value is None:
        return None
    return _authority_positive_int(value, role=role)


def _authority_string(
    value: Any, *, role: str, maximum: int = 2_000
) -> str:
    if (
        not isinstance(value, str)
        or not value
        or len(value) > maximum
        or any(ord(character) < 32 or ord(character) == 127 for character in value)
    ):
        raise KaggleRunOnceError(
            f"creation authority {role} must be a bounded string"
        )
    return value


def _authority_time(value: Any, *, role: str) -> datetime:
    if not isinstance(value, str):
        raise KaggleRunOnceError(
            f"creation authority {role} is not a valid timestamp"
        )
    try:
        parsed = datetime.fromisoformat(
            value[:-1] + "+00:00" if value.endswith("Z") else value
        )
        if parsed.utcoffset() is None:
            raise ValueError
        parsed = parsed.astimezone(timezone.utc)
    except (ValueError, OverflowError):
        raise KaggleRunOnceError(
            f"creation authority {role} is not a valid timestamp"
        ) from None
    return parsed


def _authority_datasets(value: Any, *, role: str) -> list[str]:
    if not isinstance(value, list) or len(value) != 1:
        raise KaggleRunOnceError(
            f"creation authority {role} must contain exactly one dataset"
        )
    datasets = [
        _authority_string(dataset, role=f"{role} dataset", maximum=200)
        for dataset in value
    ]
    if any(not _DATASET_SLUG.fullmatch(dataset) for dataset in datasets):
        raise KaggleRunOnceError(
            f"creation authority {role} contains an invalid dataset slug"
        )
    if PurePosixPath(datasets[0]).name != "aleph-bench-v02-scorer-conformance":
        raise KaggleRunOnceError(
            "creation authority dataset is not the frozen capture package"
        )
    return datasets


def _reject_creation_authority_duplicate_pairs(
    pairs: list[tuple[str, Any]],
) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, child in pairs:
        if key in value:
            raise KaggleRunOnceError(
                "creation authority contains a duplicate JSON key"
            )
        value[key] = child
    return value


def _reject_creation_authority_json_constant(_value: str) -> None:
    raise KaggleRunOnceError(
        "creation authority contains a non-finite JSON constant"
    )


def current_capture_source_identity() -> dict[str, Any]:
    """Return the exact reviewed source and deterministic notebook identity."""

    try:
        source, notebook_text = _exact_source_and_notebook(
            CAPTURE_OUTPUT_PATH,
            expected_path=CAPTURE_OUTPUT_PATH,
            expected_source=render_capture_task_source(),
            source_label="capture",
        )
    except KagglePushOnceError as exc:
        raise KaggleRunOnceError(str(exc)) from exc
    return {
        "path": TASK_SOURCE_PATH,
        "bytes": len(source),
        "sha256": hashlib.sha256(source).hexdigest(),
        "notebookProfile": NOTEBOOK_IDENTITY_PROFILE,
        "notebookSha256": hashlib.sha256(
            notebook_text.encode("utf-8")
        ).hexdigest(),
    }


def _validate_current_source_identity(value: Any) -> dict[str, Any]:
    source = _authority_object(value, role="current source")
    _authority_exact_fields(
        source, _CREATION_SOURCE_FIELDS, role="current source"
    )
    if source["path"] != TASK_SOURCE_PATH:
        raise KaggleRunOnceError(
            "creation authority current source path is invalid"
        )
    _authority_positive_int(source["bytes"], role="current source bytes")
    if source["notebookProfile"] != NOTEBOOK_IDENTITY_PROFILE:
        raise KaggleRunOnceError(
            "creation authority current source notebookProfile is invalid"
        )
    for field in ("sha256", "notebookSha256"):
        if not isinstance(source[field], str) or not _SHA256.fullmatch(
            source[field]
        ):
            raise KaggleRunOnceError(
                f"creation authority current source {field} is invalid"
            )
    return source


def _validate_prior_task(value: Any) -> None:
    if value is None:
        return
    prior = _authority_object(value, role="prior task")
    _authority_exact_fields(
        prior,
        {
            "creationState",
            "datasets",
            "owner",
            "sourceKernelId",
            "task",
            "version",
        },
        role="prior task",
    )
    if prior["owner"] is not None:
        _authority_string(prior["owner"], role="prior task owner", maximum=100)
    _authority_string(prior["task"], role="prior task slug", maximum=100)
    _authority_positive_int(prior["version"], role="prior task version")
    _authority_string(
        prior["creationState"], role="prior task creation state", maximum=200
    )
    _authority_optional_positive_int(
        prior["sourceKernelId"], role="prior task source kernel ID"
    )
    datasets = prior["datasets"]
    if not isinstance(datasets, list) or len(datasets) > 100:
        raise KaggleRunOnceError(
            "creation authority prior task datasets are invalid"
        )
    parsed = [
        _authority_string(
            dataset, role="prior task dataset", maximum=200
        )
        for dataset in datasets
    ]
    if parsed != sorted(set(parsed)) or any(
        not _DATASET_SLUG.fullmatch(dataset) for dataset in parsed
    ):
        raise KaggleRunOnceError(
            "creation authority prior task datasets are invalid"
        )


def verify_creation_authority_bytes(
    data: bytes,
    *,
    expected_owner: str,
    expected_task: str,
    expected_version: int,
    current_source: dict[str, Any] | None = None,
) -> VerifiedCreationAuthority:
    """Strictly verify one canonical creation journal against current source."""

    if not data or len(data) > MAX_CREATION_JOURNAL_BYTES:
        raise KaggleRunOnceError(
            "creation authority journal exceeds the safety limit"
        )
    try:
        journal = json.loads(
            data.decode("utf-8", errors="strict"),
            object_pairs_hook=_reject_creation_authority_duplicate_pairs,
            parse_constant=_reject_creation_authority_json_constant,
        )
    except KaggleRunOnceError:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError, RecursionError):
        raise KaggleRunOnceError(
            "creation authority journal is not bounded strict JSON"
        ) from None
    journal = _authority_object(journal, role="journal")
    _authority_exact_fields(
        journal, _CREATION_JOURNAL_ROOT_FIELDS, role="journal"
    )
    try:
        canonical_bytes = _canonical_json_bytes(journal)
    except (TypeError, ValueError, UnicodeError, RecursionError):
        raise KaggleRunOnceError(
            "creation authority journal cannot be canonically encoded"
        ) from None
    if data != canonical_bytes:
        raise KaggleRunOnceError(
            "creation authority journal bytes are not canonical"
        )
    if journal["journalVersion"] != CREATION_JOURNAL_VERSION or isinstance(
        journal["journalVersion"], bool
    ):
        raise KaggleRunOnceError(
            "creation authority journal version is unsupported"
        )
    if journal["artifactKind"] != "kaggle_task_creation_dispatch":
        raise KaggleRunOnceError(
            "creation authority journal artifact kind is invalid"
        )
    if journal["task"] != expected_task or expected_task != CAPTURE_TASK_SLUG:
        raise KaggleRunOnceError(
            "creation authority journal targets a different task"
        )
    if journal["gate"] != "six-call-capture":
        raise KaggleRunOnceError(
            "creation authority journal is not a capture creation receipt"
        )
    if journal["state"] != "returned" or journal["failure"] is not None:
        raise KaggleRunOnceError(
            "creation authority journal is not a returned creation receipt"
        )
    operation_id = _authority_string(
        journal["operationId"], role="operation ID", maximum=36
    )
    try:
        if str(uuid.UUID(operation_id)) != operation_id:
            raise ValueError
    except ValueError:
        raise KaggleRunOnceError(
            "creation authority operation ID is invalid"
        ) from None
    created_at = _authority_time(journal["createdAt"], role="createdAt")
    updated_at = _authority_time(journal["updatedAt"], role="updatedAt")
    if updated_at < created_at:
        raise KaggleRunOnceError(
            "creation authority timestamps are reversed"
        )

    client = _authority_object(journal["client"], role="client")
    _authority_exact_fields(
        client, {"python", *REQUIRED_CLIENT_VERSIONS}, role="client"
    )
    if not isinstance(client["python"], str) or not _PYTHON_313.fullmatch(
        client["python"]
    ):
        raise KaggleRunOnceError(
            "creation authority client Python version is invalid"
        )
    for name, expected in REQUIRED_CLIENT_VERSIONS.items():
        if client[name] != expected:
            raise KaggleRunOnceError(
                f"creation authority client {name} version drifted"
            )

    datasets = _authority_datasets(journal["datasets"], role="datasets")
    expected_source = _validate_current_source_identity(
        current_capture_source_identity()
        if current_source is None
        else current_source
    )
    source = _authority_object(journal["source"], role="source")
    _authority_exact_fields(source, _CREATION_SOURCE_FIELDS, role="source")
    source_path = _authority_string(
        source["path"], role="source path", maximum=4_096
    )
    pure_source_path = PurePosixPath(source_path)
    expected_parts = PurePosixPath(TASK_SOURCE_PATH).parts
    if (
        not pure_source_path.is_absolute()
        or any(part in {".", ".."} for part in pure_source_path.parts)
        or pure_source_path.parts[-len(expected_parts) :] != expected_parts
    ):
        raise KaggleRunOnceError(
            "creation authority source path is not the generated capture source"
        )
    for field in (
        "bytes",
        "sha256",
        "notebookProfile",
        "notebookSha256",
    ):
        if source[field] != expected_source[field]:
            raise KaggleRunOnceError(
                f"creation authority current source {field} drifted"
            )

    remote = _authority_object(
        journal["remotePreflight"], role="remote preflight"
    )
    _authority_exact_fields(
        remote, {"observedAt", "priorTask"}, role="remote preflight"
    )
    _authority_time(remote["observedAt"], role="remote preflight observedAt")
    _validate_prior_task(remote["priorTask"])

    response = _authority_object(journal["response"], role="response")
    _authority_exact_fields(
        response, _CREATION_RESPONSE_FIELDS, role="response"
    )
    response_owner = _authority_string(
        response["owner"], role="response owner", maximum=100
    )
    response_task = _authority_string(
        response["task"], role="response task", maximum=100
    )
    response_version = _authority_positive_int(
        response["version"], role="response version"
    )
    frozen_through_version = _CREATION_ONLY_TASK_VERSION_CEILINGS.get(
        (response_owner, response_task)
    )
    if (
        frozen_through_version is not None
        and response_version <= frozen_through_version
    ):
        raise KaggleRunOnceError(
            "creation authority task version is frozen creation-only"
        )
    if (
        response_owner != expected_owner
        or response_task != expected_task
        or response_version != expected_version
    ):
        raise KaggleRunOnceError(
            "creation authority response targets a different task version"
        )
    response_state = _authority_string(
        response["creationState"], role="response creation state", maximum=200
    )
    if response_state not in _ACKNOWLEDGED_CREATION_STATES:
        raise KaggleRunOnceError(
            "creation authority response did not acknowledge a viable creation"
        )
    acknowledged_kernel = _authority_optional_positive_int(
        response["sourceKernelId"], role="acknowledged source kernel ID"
    )
    if response["url"] is not None:
        _authority_string(response["url"], role="response URL", maximum=4_096)
    response_datasets = _authority_datasets(
        response["datasets"], role="response datasets"
    )
    if response_datasets != datasets:
        raise KaggleRunOnceError(
            "creation authority response datasets differ from the request"
        )
    response["sourceKernelId"] = acknowledged_kernel
    return VerifiedCreationAuthority(
        journal=journal,
        canonical_bytes=canonical_bytes,
        source=expected_source,
        response=response,
    )


def read_creation_authority(path: Path) -> bytes:
    """Snapshot one bounded receipt without leaf aliases or extra links."""

    required_flags = ("O_NOFOLLOW", "O_NONBLOCK", "O_CLOEXEC")
    if any(not hasattr(os, flag) for flag in required_flags):
        raise KaggleRunOnceError(
            "creation authority reader requires fail-closed file flags"
        )
    try:
        before = os.stat(path, follow_symlinks=False)
    except OSError as exc:
        raise KaggleRunOnceError(
            f"cannot read creation authority journal: {exc}"
        ) from exc
    if before.st_size > MAX_CREATION_JOURNAL_BYTES:
        raise KaggleRunOnceError(
            "creation authority journal exceeds the safety limit"
        )
    if (
        not stat.S_ISREG(before.st_mode)
        or before.st_nlink != 1
        or before.st_size <= 0
    ):
        raise KaggleRunOnceError(
            "creation authority journal must be one bounded single-link regular file"
        )
    flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC
    descriptor: int | None = None
    try:
        descriptor = os.open(path, flags)
        with os.fdopen(descriptor, "rb", closefd=True) as handle:
            descriptor = None
            opened = os.fstat(handle.fileno())
            if (
                not stat.S_ISREG(opened.st_mode)
                or opened.st_nlink != 1
                or (opened.st_dev, opened.st_ino)
                != (before.st_dev, before.st_ino)
                or opened.st_size != before.st_size
                or opened.st_mtime_ns != before.st_mtime_ns
                or opened.st_ctime_ns != before.st_ctime_ns
            ):
                raise KaggleRunOnceError(
                    "creation authority journal changed while it was opened"
                )
            data = handle.read(MAX_CREATION_JOURNAL_BYTES + 1)
            after = os.fstat(handle.fileno())
    except KaggleRunOnceError:
        raise
    except OSError as exc:
        raise KaggleRunOnceError(
            f"cannot read creation authority journal: {exc}"
        ) from exc
    finally:
        if descriptor is not None:
            os.close(descriptor)
    try:
        final = os.stat(path, follow_symlinks=False)
    except OSError:
        raise KaggleRunOnceError(
            "creation authority journal changed while it was read"
        ) from None
    identity = (opened.st_dev, opened.st_ino)
    if (
        not data
        or len(data) > MAX_CREATION_JOURNAL_BYTES
        or after.st_size != len(data)
        or after.st_nlink != 1
        or final.st_nlink != 1
        or (after.st_dev, after.st_ino) != identity
        or (final.st_dev, final.st_ino) != identity
        or after.st_mtime_ns != opened.st_mtime_ns
        or final.st_mtime_ns != opened.st_mtime_ns
        or after.st_ctime_ns != opened.st_ctime_ns
        or final.st_ctime_ns != opened.st_ctime_ns
    ):
        raise KaggleRunOnceError(
            "creation authority journal changed while it was read"
        )
    return data


def bind_creation_authority(
    authority: VerifiedCreationAuthority,
    *,
    task_record: dict[str, Any],
) -> dict[str, Any]:
    """Bind a verified create receipt to one completed exact-version readback."""

    try:
        canonical_bytes = _canonical_json_bytes(authority.journal)
    except (TypeError, ValueError, UnicodeError, RecursionError):
        raise KaggleRunOnceError(
            "creation authority journal cannot be canonically encoded"
        ) from None
    if canonical_bytes != authority.canonical_bytes:
        raise KaggleRunOnceError(
            "creation authority changed after verification"
        )
    response = authority.response
    identity = (
        task_record.get("owner"),
        task_record.get("task"),
        task_record.get("version"),
    )
    expected_identity = (
        response["owner"],
        response["task"],
        response["version"],
    )
    if identity != expected_identity:
        raise KaggleRunOnceError(
            "exact task readback differs from creation authority"
        )
    if task_record.get("datasets") != response["datasets"]:
        raise KaggleRunOnceError(
            "exact task datasets differ from creation authority"
        )
    resolved_kernel = _authority_positive_int(
        task_record.get("sourceKernelId"),
        role="resolved source kernel ID",
    )
    acknowledged_kernel = response["sourceKernelId"]
    if (
        acknowledged_kernel is not None
        and acknowledged_kernel != resolved_kernel
    ):
        raise KaggleRunOnceError(
            "exact task source kernel differs from creation authority"
        )
    return {
        "canonicalBytes": len(canonical_bytes),
        "canonicalSha256": hashlib.sha256(canonical_bytes).hexdigest(),
        "journal": copy.deepcopy(authority.journal),
        "source": copy.deepcopy(authority.source),
        "task": {
            "owner": identity[0],
            "task": identity[1],
            "version": identity[2],
            "datasets": list(response["datasets"]),
            "acknowledgedSourceKernelId": acknowledged_kernel,
            "resolvedSourceKernelId": resolved_kernel,
        },
    }


def verify_creation_authority_binding(
    value: Any,
    *,
    task_record: dict[str, Any],
    current_source: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Rebuild and compare an embedded creation-authority binding."""

    binding = _authority_object(value, role="binding")
    _authority_exact_fields(
        binding, _CREATION_AUTHORITY_FIELDS, role="binding"
    )
    canonical_size = _authority_positive_int(
        binding["canonicalBytes"], role="binding canonical bytes"
    )
    digest = binding["canonicalSha256"]
    if not isinstance(digest, str) or not _SHA256.fullmatch(digest):
        raise KaggleRunOnceError(
            "creation authority binding digest is invalid"
        )
    journal = _authority_object(binding["journal"], role="binding journal")
    try:
        canonical_bytes = _canonical_json_bytes(journal)
    except (TypeError, ValueError, UnicodeError, RecursionError):
        raise KaggleRunOnceError(
            "creation authority binding journal cannot be encoded"
        ) from None
    if (
        canonical_size != len(canonical_bytes)
        or digest != hashlib.sha256(canonical_bytes).hexdigest()
    ):
        raise KaggleRunOnceError(
            "creation authority binding byte identity drifted"
        )
    identity = _authority_object(binding["task"], role="binding task")
    _authority_exact_fields(
        identity, _CREATION_AUTHORITY_TASK_FIELDS, role="binding task"
    )
    expected_identity = (
        task_record.get("owner"),
        task_record.get("task"),
        task_record.get("version"),
    )
    if (
        identity.get("owner"),
        identity.get("task"),
        identity.get("version"),
    ) != expected_identity:
        raise KaggleRunOnceError(
            "creation authority binding targets a different task version"
        )
    authority = verify_creation_authority_bytes(
        canonical_bytes,
        expected_owner=expected_identity[0],
        expected_task=expected_identity[1],
        expected_version=expected_identity[2],
        current_source=current_source,
    )
    expected_binding = bind_creation_authority(
        authority, task_record=task_record
    )
    if binding != expected_binding:
        raise KaggleRunOnceError(
            "creation authority binding disagrees with its journal or readback"
        )
    return binding


def _validate_target(
    *, owner: str, task: str, version: int, model: str, journal_path: Path
) -> None:
    if not _SLUG_PART.fullmatch(owner):
        raise KaggleRunOnceError("owner must be a lowercase Kaggle slug")
    if not _SLUG_PART.fullmatch(task):
        raise KaggleRunOnceError("task must be a lowercase Kaggle slug")
    if isinstance(version, bool) or not isinstance(version, int) or version <= 0:
        raise KaggleRunOnceError("version must be a positive integer")
    if not _MODEL_SLUG.fullmatch(model):
        raise KaggleRunOnceError(
            "model must be one exact canonical BenchmarkModelVersion slug; "
            "provider paths and @ aliases are not accepted"
        )
    if journal_path.exists():
        raise KaggleRunOnceError(
            f"run journal already exists; inspect it and do not retry: {journal_path}"
        )


def _dispatch_claim_path(
    *,
    creation_journal_path: Path,
    creation_authority: VerifiedCreationAuthority,
    owner: str,
    task: str,
    version: int,
    model: str,
) -> Path:
    """Return the receipt-local, journal-path-independent paid-call claim."""

    key = b"\0".join(
        (
            creation_authority.canonical_bytes,
            owner.encode("ascii"),
            task.encode("ascii"),
            str(version).encode("ascii"),
            model.encode("ascii"),
        )
    )
    return (
        creation_journal_path.parent
        / _DISPATCH_CLAIM_DIRECTORY
        / f"{hashlib.sha256(key).hexdigest()}.json"
    )


def _write_dispatch_claim(path: Path, claim: dict[str, Any]) -> None:
    """Durably claim one receipt/task/model boundary with atomic creation."""

    required_flags = ("O_NOFOLLOW", "O_CLOEXEC", "O_DIRECTORY")
    if any(not hasattr(os, flag) for flag in required_flags) or not hasattr(
        os, "geteuid"
    ):
        raise KaggleRunOnceError(
            "dispatch claim requires fail-closed filesystem flags"
        )
    try:
        path.parent.mkdir(mode=0o700)
        _fsync_parent_directory(path.parent)
    except FileExistsError:
        pass
    except OSError as exc:
        raise KaggleRunOnceError(
            f"cannot create dispatch-claim directory: {exc}"
        ) from exc
    try:
        directory = os.stat(path.parent, follow_symlinks=False)
    except OSError as exc:
        raise KaggleRunOnceError(
            f"cannot inspect dispatch-claim directory: {exc}"
        ) from exc
    if (
        not stat.S_ISDIR(directory.st_mode)
        or directory.st_uid != os.geteuid()
        or stat.S_IMODE(directory.st_mode) & 0o077
    ):
        raise KaggleRunOnceError(
            "dispatch-claim directory must be a private owned directory"
        )

    data = _canonical_json_bytes(claim)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC
    descriptor: int | None = None
    try:
        descriptor = os.open(path, flags, 0o600)
        with os.fdopen(descriptor, "wb", closefd=True) as handle:
            descriptor = None
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        _fsync_parent_directory(path)
    except FileExistsError as exc:
        raise KaggleRunOnceError(
            "a durable dispatch claim already exists for this exact "
            f"creation receipt, task version, and model: {path}"
        ) from exc
    except OSError as exc:
        # A partial claim is intentionally retained as a hard stop. Removing it
        # could turn an uncertain local write into a second paid API attempt.
        raise KaggleRunOnceError(
            f"cannot durably write dispatch claim; inspect {path}: {exc}"
        ) from exc
    finally:
        if descriptor is not None:
            os.close(descriptor)


def _positive_int(value: Any, *, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise KaggleRunOnceError(f"Kaggle returned an invalid {label}")
    return value


def _iso_datetime(value: Any, *, label: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, datetime):
        raise KaggleRunOnceError(f"Kaggle returned an invalid {label}")
    if value.tzinfo is None:
        # kagglesdk 0.1.37 drops the offset from service timestamps whose
        # documented semantics are UTC. Retain that compatibility repair in
        # the receipt instead of serializing a misleading local time.
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _task_record(
    task_info: Any,
    *,
    expected_owner: str,
    expected_task: str,
    expected_version: int,
) -> dict[str, Any]:
    slug = getattr(task_info, "slug", None)
    owner = getattr(slug, "owner_slug", None)
    task = getattr(slug, "task_slug", None)
    version = getattr(slug, "version_number", None)
    if (owner, task, version) != (
        expected_owner,
        expected_task,
        expected_version,
    ):
        raise KaggleRunOnceError(
            "Kaggle exact-version preflight returned a different task identity"
        )
    state = _enum_name(getattr(task_info, "creation_state", None))
    if state != _COMPLETED_TASK_STATE:
        raise KaggleRunOnceError(
            "exact Kaggle task version is not ready to run "
            f"({state})"
        )
    source_kernel_id = _positive_int(
        getattr(task_info, "source_kernel_id", None),
        label="source kernel ID",
    )
    options = getattr(task_info, "options", None)
    datasets = list(getattr(options, "dataset_data_sources", None) or ())
    if (
        not datasets
        or datasets != sorted(set(datasets))
        or any(
            not isinstance(dataset, str)
            or not _DATASET_SLUG.fullmatch(dataset)
            for dataset in datasets
        )
    ):
        raise KaggleRunOnceError(
            "Kaggle returned invalid or unordered exact task datasets"
        )
    return {
        "owner": owner,
        "task": task,
        "version": version,
        "creationState": state,
        "sourceKernelId": source_kernel_id,
        "datasets": datasets,
        "url": getattr(task_info, "url", None) or None,
    }


def _run_record(
    run: Any,
    *,
    expected_owner: str,
    expected_task: str,
    expected_version: int,
) -> dict[str, Any]:
    slug = getattr(run, "task_slug", None)
    identity = (
        getattr(slug, "owner_slug", None),
        getattr(slug, "task_slug", None),
        getattr(slug, "version_number", None),
    )
    if identity != (expected_owner, expected_task, expected_version):
        raise KaggleRunOnceError(
            "Kaggle run listing escaped the requested exact task version"
        )
    model = getattr(run, "model_version_slug", None)
    if not isinstance(model, str) or not _MODEL_SLUG.fullmatch(model):
        raise KaggleRunOnceError("Kaggle returned an invalid run model slug")
    error_message = getattr(run, "error_message", None)
    if error_message is not None and not isinstance(error_message, str):
        raise KaggleRunOnceError("Kaggle returned an invalid run error message")
    return {
        "id": _positive_int(getattr(run, "id", None), label="run ID"),
        "model": model,
        "state": _enum_name(getattr(run, "state", None)),
        "startTime": _iso_datetime(
            getattr(run, "start_time", None), label="run start time"
        ),
        "endTime": _iso_datetime(
            getattr(run, "end_time", None), label="run end time"
        ),
        "errorMessage": error_message or None,
    }


def _run_set(
    runs: Iterable[Any],
    *,
    expected_owner: str,
    expected_task: str,
    expected_version: int,
) -> list[dict[str, Any]]:
    records = [
        _run_record(
            run,
            expected_owner=expected_owner,
            expected_task=expected_task,
            expected_version=expected_version,
        )
        for run in runs
    ]
    ids = [record["id"] for record in records]
    if len(set(ids)) != len(ids):
        raise KaggleRunOnceError("Kaggle returned duplicate run IDs")
    return sorted(records, key=lambda record: record["id"])


def _model_record(model_info: Any, *, expected_model: str) -> dict[str, Any]:
    version = getattr(model_info, "version", None)
    slug = getattr(version, "slug", None)
    if slug != expected_model:
        raise KaggleRunOnceError(
            "Kaggle model preflight returned a different canonical version slug"
        )
    if getattr(version, "published", None) is not True:
        raise KaggleRunOnceError("requested Kaggle model version is not published")
    if getattr(version, "allow_model_proxy", None) is not True:
        raise KaggleRunOnceError(
            "requested Kaggle model version does not allow Model Proxy execution"
        )
    proxy_slug = getattr(version, "model_proxy_slug", None)
    if not isinstance(proxy_slug, str) or not proxy_slug:
        raise KaggleRunOnceError(
            "requested Kaggle model version has no Model Proxy identity"
        )
    return {
        "benchmarkModelId": _positive_int(
            getattr(model_info, "id", None), label="benchmark model ID"
        ),
        "benchmarkModelVersionId": _positive_int(
            getattr(version, "id", None), label="benchmark model version ID"
        ),
        "slug": slug,
        "modelProxySlug": proxy_slug,
        "displayName": getattr(version, "display_name", None) or None,
        "deprecatedAt": _iso_datetime(
            getattr(version, "deprecation_time", None),
            label="model deprecation time",
        ),
    }


def _finite_number(value: Any, *, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise KaggleRunOnceError(f"Kaggle returned an invalid {label}")
    number = float(value)
    if not math.isfinite(number) or number < 0:
        raise KaggleRunOnceError(f"Kaggle returned an invalid {label}")
    return number


def _quota_record(response: Any) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    periods: set[str] = set()
    for balance in getattr(response, "quota_balances", None) or ():
        period = _enum_name(getattr(balance, "refill_period", None))
        if period not in {"DAILY", "MONTHLY"} or period in periods:
            raise KaggleRunOnceError(
                "Kaggle returned duplicate or unknown Model Proxy quota periods"
            )
        periods.add(period)
        used = _finite_number(
            getattr(balance, "quota_used", None), label="quota used"
        )
        allowed = _finite_number(
            getattr(balance, "total_quota_allowed", None),
            label="quota allowance",
        )
        if used > allowed:
            raise KaggleRunOnceError("Kaggle quota used exceeds its allowance")
        records.append(
            {
                "period": period,
                "usedUsd": used,
                "allowedUsd": allowed,
                "remainingUsd": allowed - used,
                "refillTime": _iso_datetime(
                    getattr(balance, "refill_time", None),
                    label="quota refill time",
                ),
            }
        )
    if periods != {"DAILY", "MONTHLY"}:
        raise KaggleRunOnceError(
            "Kaggle did not return both daily and monthly Model Proxy quotas"
        )
    return sorted(records, key=lambda record: record["period"])


def _schedule_response_record(
    response: Any, *, expected_model_version_id: int
) -> dict[str, Any]:
    results = list(getattr(response, "results", None) or ())
    if len(results) != 1:
        raise KaggleRunOnceError(
            "Kaggle schedule response did not contain exactly one result"
        )
    result = results[0]
    scheduled = getattr(result, "run_scheduled", None)
    if not isinstance(scheduled, bool):
        raise KaggleRunOnceError("Kaggle returned an invalid scheduled flag")
    task_version_id = _positive_int(
        getattr(result, "benchmark_task_version_id", None),
        label="internal task version ID",
    )
    model_version_id = _positive_int(
        getattr(result, "benchmark_model_version_id", None),
        label="internal model version ID",
    )
    if model_version_id != expected_model_version_id:
        raise KaggleRunOnceError(
            "Kaggle schedule response identified a different model version"
        )
    parent_id = getattr(result, "parent_task_version_id", None)
    if parent_id:
        _positive_int(parent_id, label="parent task version ID")
        raise KaggleRunOnceError(
            "Kaggle redirected scheduling to a parent task version"
        )
    reason = getattr(result, "run_skipped_reason", None)
    if reason is not None and not isinstance(reason, str):
        raise KaggleRunOnceError("Kaggle returned an invalid skip reason")
    return {
        "runScheduled": scheduled,
        "runSkippedReason": reason or None,
        "benchmarkTaskVersionId": task_version_id,
        "benchmarkModelVersionId": model_version_id,
        "parentTaskVersionId": None,
    }


def _new_runs(
    before: Sequence[dict[str, Any]], after: Sequence[dict[str, Any]]
) -> list[dict[str, Any]]:
    before_ids = {record["id"] for record in before}
    if not before_ids.issubset({record["id"] for record in after}):
        raise KaggleRunOnceError(
            "Kaggle post-dispatch run listing lost pre-existing run IDs"
        )
    return [record for record in after if record["id"] not in before_ids]


def schedule_and_reconcile_once(
    *,
    owner: str,
    task: str,
    version: int,
    model: str,
    journal_path: Path,
    creation_journal_path: Path,
    creation_authority: VerifiedCreationAuthority,
    fetch_task: Callable[[], Any],
    fetch_model: Callable[[], Any],
    fetch_runs: Callable[[], Iterable[Any]],
    fetch_quota: Callable[[], Any],
    fetch_current_source: Callable[[], dict[str, Any]],
    schedule_run: Callable[[], Any],
    client_versions: dict[str, str],
    reconcile_delays: Sequence[float] = DEFAULT_RECONCILE_DELAYS_SECONDS,
    clock: Callable[[], str] = _utc_now,
    sleeper: Callable[[float], None] = time.sleep,
) -> dict[str, Any]:
    """Cross one paid scheduling boundary and bind its unique run ID."""

    _validate_target(
        owner=owner,
        task=task,
        version=version,
        model=model,
        journal_path=journal_path,
    )
    if not reconcile_delays or any(
        isinstance(delay, bool)
        or not isinstance(delay, (int, float))
        or not math.isfinite(float(delay))
        or delay < 0
        for delay in reconcile_delays
    ):
        raise KaggleRunOnceError("reconciliation delays must be finite and non-negative")

    retained_authority_bytes = read_creation_authority(creation_journal_path)
    if retained_authority_bytes != creation_authority.canonical_bytes:
        raise KaggleRunOnceError(
            "creation authority does not match the retained original journal"
        )
    locally_verified_authority = verify_creation_authority_bytes(
        creation_authority.canonical_bytes,
        expected_owner=owner,
        expected_task=task,
        expected_version=version,
        current_source=creation_authority.source,
    )
    if locally_verified_authority != creation_authority:
        raise KaggleRunOnceError(
            "creation authority changed after initial verification"
        )

    exact_task = _task_record(
        fetch_task(),
        expected_owner=owner,
        expected_task=task,
        expected_version=version,
    )
    bind_creation_authority(creation_authority, task_record=exact_task)
    exact_model = _model_record(fetch_model(), expected_model=model)
    before_runs = _run_set(
        fetch_runs(),
        expected_owner=owner,
        expected_task=task,
        expected_version=version,
    )
    active = [
        record
        for record in before_runs
        if record["state"] not in _TERMINAL_RUN_STATES
    ]
    if active:
        raise KaggleRunOnceError(
            "exact task version has unresolved queued, running, or unknown runs"
        )
    if any(record["model"] == model for record in before_runs):
        raise KaggleRunOnceError(
            "exact task version already has a run for the requested model; "
            "inspect the retained run instead of choosing another journal"
        )
    quota_before = _quota_record(fetch_quota())
    current_source = _validate_current_source_identity(fetch_current_source())
    creation_authority = verify_creation_authority_bytes(
        creation_authority.canonical_bytes,
        expected_owner=owner,
        expected_task=task,
        expected_version=version,
        current_source=current_source,
    )
    creation_binding = bind_creation_authority(
        creation_authority, task_record=exact_task
    )
    confirmed_runs = _run_set(
        fetch_runs(),
        expected_owner=owner,
        expected_task=task,
        expected_version=version,
    )
    if confirmed_runs != before_runs:
        raise KaggleRunOnceError(
            "exact task run set changed during preflight; inspect it before "
            "choosing any journal or scheduling again"
        )

    final_source = _validate_current_source_identity(fetch_current_source())
    creation_authority = verify_creation_authority_bytes(
        creation_authority.canonical_bytes,
        expected_owner=owner,
        expected_task=task,
        expected_version=version,
        current_source=final_source,
    )
    creation_binding = bind_creation_authority(
        creation_authority, task_record=exact_task
    )
    if read_creation_authority(
        creation_journal_path
    ) != creation_authority.canonical_bytes:
        raise KaggleRunOnceError(
            "creation authority changed during remote preflight"
        )

    claim_path = _dispatch_claim_path(
        creation_journal_path=creation_journal_path,
        creation_authority=creation_authority,
        owner=owner,
        task=task,
        version=version,
        model=model,
    )
    _write_dispatch_claim(
        claim_path,
        {
            "claimVersion": 1,
            "artifactKind": "kaggle_benchmark_model_dispatch_claim",
            "createdAt": clock(),
            "target": {
                "owner": owner,
                "task": task,
                "version": version,
                "model": model,
            },
            "creationAuthoritySha256": hashlib.sha256(
                creation_authority.canonical_bytes
            ).hexdigest(),
            "runJournal": str(journal_path.resolve(strict=False)),
        },
    )

    journal: dict[str, Any] = {
        "journalVersion": 2,
        "artifactKind": "kaggle_benchmark_run_dispatch",
        "operationId": str(uuid.uuid4()),
        "createdAt": clock(),
        "updatedAt": clock(),
        "state": "prepared",
        "target": {
            "owner": owner,
            "task": task,
            "version": version,
            "model": model,
        },
        "client": dict(client_versions),
        "creationAuthority": creation_binding,
        "remotePreflight": {
            "observedAt": clock(),
            "task": exact_task,
            "model": exact_model,
            "runs": before_runs,
            "quota": quota_before,
        },
        "response": None,
        "reconciliation": None,
        "dispatchFailure": None,
        "responseFailure": None,
        "failure": None,
    }
    _write_initial_journal(journal_path, journal)

    # This durable state is the no-retry barrier for the only paid call.
    journal["state"] = "dispatching"
    journal["updatedAt"] = clock()
    _replace_journal(journal_path, journal)

    dispatch_failure: dict[str, str] | None = None
    response_failure: dict[str, str] | None = None
    try:
        response = schedule_run()
    except BaseException as exc:
        dispatch_failure = _exception_record(exc)
        journal["dispatchFailure"] = dispatch_failure
        journal["failure"] = dispatch_failure
        journal["state"] = "ambiguous"
        journal["updatedAt"] = clock()
        _replace_journal(journal_path, journal)
        if not isinstance(exc, Exception):
            raise
    else:
        try:
            journal["response"] = _schedule_response_record(
                response,
                expected_model_version_id=exact_model[
                    "benchmarkModelVersionId"
                ],
            )
        except Exception as exc:
            response_failure = _exception_record(exc)
            journal["responseFailure"] = response_failure
            journal["failure"] = response_failure
            journal["state"] = "ambiguous"
            journal["updatedAt"] = clock()
            _replace_journal(journal_path, journal)
        else:
            if not journal["response"]["runScheduled"]:
                journal["state"] = "not_scheduled"
                journal["updatedAt"] = clock()
                journal["failure"] = {
                    "type": "RunSkipped",
                    "message": journal["response"]["runSkippedReason"]
                    or "Kaggle did not schedule the requested run",
                }
                try:
                    journal["quotaAfter"] = _quota_record(fetch_quota())
                except Exception as exc:
                    journal["quotaAfterFailure"] = _exception_record(exc)
                _replace_journal(journal_path, journal)
                raise KaggleRunOnceError(
                    "Kaggle conclusively skipped the requested run; "
                    "inspect the journal"
                )
            journal["state"] = "returned_unreconciled"
            journal["updatedAt"] = clock()
            _replace_journal(journal_path, journal)

    observations: list[dict[str, Any]] = []
    for attempt, delay in enumerate(reconcile_delays, start=1):
        if delay:
            sleeper(float(delay))
        observed_at = clock()
        try:
            after_runs = _run_set(
                fetch_runs(),
                expected_owner=owner,
                expected_task=task,
                expected_version=version,
            )
            delta = _new_runs(before_runs, after_runs)
        except Exception as exc:
            observations.append(
                {
                    "attempt": attempt,
                    "observedAt": observed_at,
                    "delaySeconds": float(delay),
                    "failure": _exception_record(exc),
                }
            )
            continue

        observations.append(
            {
                "attempt": attempt,
                "observedAt": observed_at,
                "delaySeconds": float(delay),
                "runIds": [record["id"] for record in after_runs],
                "newRuns": delta,
            }
        )
        if not delta:
            continue
        if len(delta) != 1 or delta[0]["model"] != model:
            journal["reconciliation"] = {
                "observations": observations,
                "run": None,
            }
            journal["state"] = "ambiguous"
            journal["updatedAt"] = clock()
            journal["failure"] = {
                "type": "RunSetMismatch",
                "message": (
                    "post-dispatch run-set difference was not exactly one "
                    "run for the requested model"
                ),
            }
            _replace_journal(journal_path, journal)
            raise KaggleRunOutcomeAmbiguous(
                "paid scheduling outcome is ambiguous; inspect the journal and "
                "do not schedule again"
            )

        if response_failure is not None:
            journal["reconciliation"] = {
                "observations": observations,
                "run": delta[0],
            }
            journal["state"] = "ambiguous"
            journal["updatedAt"] = clock()
            journal["failure"] = response_failure
            _replace_journal(journal_path, journal)
            raise KaggleRunOutcomeAmbiguous(
                "Kaggle returned a contradictory schedule acknowledgement; "
                "the new run is recorded but must not be promoted or retried"
            )

        journal["reconciliation"] = {
            "observations": observations,
            "run": delta[0],
        }
        journal["state"] = "reconciled"
        journal["updatedAt"] = clock()
        journal["failure"] = None
        try:
            journal["quotaAfter"] = _quota_record(fetch_quota())
        except Exception as exc:
            journal["quotaAfter"] = None
            journal["quotaAfterFailure"] = _exception_record(exc)
        _replace_journal(journal_path, journal)
        return journal

    journal["reconciliation"] = {
        "observations": observations,
        "run": None,
    }
    journal["state"] = "ambiguous"
    journal["updatedAt"] = clock()
    if dispatch_failure is None and response_failure is None:
        journal["failure"] = {
            "type": "RunNotObserved",
            "message": "no new run became visible within the reconciliation window",
        }
    try:
        journal["quotaAfter"] = _quota_record(fetch_quota())
    except Exception as exc:
        journal["quotaAfter"] = None
        journal["quotaAfterFailure"] = _exception_record(exc)
    _replace_journal(journal_path, journal)
    raise KaggleRunOutcomeAmbiguous(
        "paid scheduling outcome is ambiguous; inspect the exact task version, "
        "quota, and journal; do not schedule again"
    )


def run_once(
    *,
    owner: str,
    task: str,
    version: int,
    model: str,
    journal_path: Path,
    creation_journal_path: Path,
    reconcile_delays: Sequence[float] = DEFAULT_RECONCILE_DELAYS_SECONDS,
) -> dict[str, Any]:
    """Schedule one exact Kaggle Task/model pair without paid-call retry."""

    _validate_target(
        owner=owner,
        task=task,
        version=version,
        model=model,
        journal_path=journal_path,
    )
    client_versions = _verified_client_versions()
    source_identity = current_capture_source_identity()
    creation_authority = verify_creation_authority_bytes(
        read_creation_authority(creation_journal_path),
        expected_owner=owner,
        expected_task=task,
        expected_version=version,
        current_source=source_identity,
    )
    try:
        from kaggle.api.kaggle_api_extended import KaggleApi
        from kagglesdk.benchmarks.types.benchmark_tasks_api_service import (
            ApiBatchScheduleBenchmarkTaskRunsRequest,
            ApiBenchmarkTaskSlug,
            ApiGetBenchmarkTaskRequest,
            ApiListBenchmarkTaskRunsRequest,
        )
        from kagglesdk.benchmarks.types.benchmarks_api_service import (
            ApiListBenchmarkModelsRequest,
        )
        from kagglesdk.models.types.model_proxy_api_service import (
            ApiGetModelProxyQuotasRequest,
        )
    except ImportError as exc:
        raise KaggleRunOnceError(
            "Kaggle CLI 2.2.4 or newer is required for one-shot scheduling"
        ) from exc

    slug = ApiBenchmarkTaskSlug()
    slug.owner_slug = owner
    slug.task_slug = task
    slug.version_number = version

    get_request = ApiGetBenchmarkTaskRequest()
    get_request.slug = slug
    schedule_request = ApiBatchScheduleBenchmarkTaskRunsRequest()
    schedule_request.task_slugs = [slug]
    schedule_request.model_version_slugs = [model]

    api = KaggleApi()
    api.authenticate()
    with api.build_kaggle_client() as client:
        tasks = client.benchmarks.benchmark_tasks_api_client

        def fetch_task() -> Any:
            return api.with_retry(tasks.get_benchmark_task)(get_request)

        def fetch_model() -> Any:
            matches: list[Any] = []
            page_token = ""
            seen_tokens: set[str] = set()
            models = client.benchmarks.benchmarks_api_client
            for _ in range(100):
                request = ApiListBenchmarkModelsRequest()
                request.page_size = 100
                if page_token:
                    request.page_token = page_token
                response = api.with_retry(models.list_benchmark_models)(request)
                for candidate in getattr(response, "benchmark_models", None) or ():
                    if getattr(getattr(candidate, "version", None), "slug", None) == model:
                        matches.append(candidate)
                page_token = getattr(response, "next_page_token", None) or ""
                if not page_token:
                    break
                if page_token in seen_tokens:
                    raise KaggleRunOnceError(
                        "Kaggle model pagination repeated a page token"
                    )
                seen_tokens.add(page_token)
            else:
                raise KaggleRunOnceError(
                    "Kaggle model pagination exceeded 100 pages"
                )
            if len(matches) != 1:
                raise KaggleRunOnceError(
                    "exact canonical Kaggle model version was missing or duplicated"
                )
            return matches[0]

        def fetch_runs() -> list[Any]:
            runs: list[Any] = []
            page_token = ""
            seen_tokens: set[str] = set()
            for _ in range(100):
                request = ApiListBenchmarkTaskRunsRequest()
                request.task_slug = slug
                request.page_size = 100
                if page_token:
                    request.page_token = page_token
                response = api.with_retry(tasks.list_benchmark_task_runs)(request)
                runs.extend(getattr(response, "runs", None) or ())
                page_token = getattr(response, "next_page_token", None) or ""
                if not page_token:
                    return runs
                if page_token in seen_tokens:
                    raise KaggleRunOnceError(
                        "Kaggle run pagination repeated a page token"
                    )
                seen_tokens.add(page_token)
            raise KaggleRunOnceError("Kaggle run pagination exceeded 100 pages")

        def fetch_quota() -> Any:
            quotas = client.models.model_proxy_api_client
            return api.with_retry(quotas.get_model_proxy_quotas)(
                ApiGetModelProxyQuotasRequest()
            )

        schedule = tasks.batch_schedule_benchmark_task_runs
        return schedule_and_reconcile_once(
            owner=owner,
            task=task,
            version=version,
            model=model,
            journal_path=journal_path,
            creation_journal_path=creation_journal_path.resolve(strict=True),
            creation_authority=creation_authority,
            fetch_task=fetch_task,
            fetch_model=fetch_model,
            fetch_runs=fetch_runs,
            fetch_quota=fetch_quota,
            fetch_current_source=current_capture_source_identity,
            # Deliberately never wrap this paid, non-idempotent POST in
            # KaggleApi.with_retry.
            schedule_run=lambda: schedule(schedule_request),
            client_versions=client_versions,
            reconcile_delays=reconcile_delays,
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Schedule one exact Kaggle benchmark Task version/model pair. "
            "The paid call is never retried."
        )
    )
    parser.add_argument("--owner", required=True)
    parser.add_argument("--task", required=True)
    parser.add_argument("--version", required=True, type=int)
    parser.add_argument("--model", required=True)
    parser.add_argument(
        "--creation-journal", required=True, type=Path
    )
    parser.add_argument("--journal", required=True, type=Path)
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)
    try:
        journal = run_once(
            owner=args.owner,
            task=args.task,
            version=args.version,
            model=args.model,
            journal_path=args.journal,
            creation_journal_path=args.creation_journal,
        )
    except (OSError, ValueError) as exc:
        print(f"Kaggle one-shot run failed: {exc}", file=sys.stderr)
        return 1
    run = journal["reconciliation"]["run"]
    print(
        f"scheduled {args.owner}/{args.task} v{args.version} once against "
        f"{args.model}; reconciled run {run['id']} ({run['state']})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
