from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import math
import os
import re
import stat
import subprocess
import sys
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path, PurePosixPath
from typing import Any, Callable, Iterable, Iterator, Sequence

from bench.engine.kaggle_capture_evidence import (
    KaggleCaptureEvidenceError,
    VerifiedCaptureBundle,
    load_verified_capture_bundle,
)
from bench.engine.kaggle_run_once import (
    AnchoredDispatchPaths,
    CAPTURE_TASK_SLUG,
    MAX_CREATION_JOURNAL_BYTES,
    KaggleReadUnavailable,
    KaggleRunOnceError,
    VerifiedCreationAuthority,
    _canonical_json_bytes,
    _dispatch_claim_path,
    current_capture_source_identity,
    fetch_benchmark_task_runs,
    fetch_model_proxy_quota,
    run_once,
    verify_creation_authority_bytes,
)


POLICY_PATH = Path(__file__).parents[1] / "config" / "kaggle-capture-queue-v1.json"
_LOADED_REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
MAX_POLICY_BYTES = 262_144
MAX_QUEUE_RECEIPT_BYTES = 262_144
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_COMMIT = re.compile(r"^[0-9a-f]{40}$")
_MODEL_SLUG = re.compile(r"^[a-z0-9](?:[a-z0-9._-]{0,198}[a-z0-9])?$")
_WRITER_ID = re.compile(r"^[a-z0-9](?:[a-z0-9._-]{0,98}[a-z0-9])?$")
_MONEY = re.compile(r"^(?:0|[1-9][0-9]*)\.[0-9]{2}$")
_TERMINAL_RUN_STATES = {
    "BENCHMARK_TASK_RUN_STATE_COMPLETED",
    "BENCHMARK_TASK_RUN_STATE_ERRORED",
}
_COMPLETED_RUN_STATE = "BENCHMARK_TASK_RUN_STATE_COMPLETED"
_ACTIVE_RUN_STATES = {
    "BENCHMARK_TASK_RUN_STATE_UNSPECIFIED",
    "BENCHMARK_TASK_RUN_STATE_QUEUED",
    "BENCHMARK_TASK_RUN_STATE_RUNNING",
}
_REFILL_JITTER = timedelta(milliseconds=5)
_RETRY_EPSILON = timedelta(microseconds=1)
# Kaggle serializes USD through binary floats; tolerate only sub-nanodollar
# representation noise.
_QUOTA_ARITHMETIC_TOLERANCE = Decimal("1e-9")
_MIN_MONTHLY_ADVANCE = timedelta(days=20)
_MAX_MONTHLY_ADVANCE = timedelta(days=40)
_LOCK_PATH = PurePosixPath(".aleph-kaggle-v10-queue.lock")


class KaggleQueueError(KaggleRunOnceError):
    """Raised when the finite queue cannot safely continue."""


class KaggleQueueBreaker(KaggleQueueError):
    """A permanent stop for this exact policy id and digest."""


class KaggleQueueHeld(KaggleQueueError):
    """A read-only condition that may become eligible later."""

    def __init__(self, reason: str, *, retry_after: str | None = None):
        super().__init__(reason)
        self.reason = reason
        self.retry_after = retry_after


class KaggleQueueExpired(KaggleQueueError):
    """The reviewed policy reached its exclusive expiry boundary."""


class KaggleControlRootDrift(KaggleQueueError):
    """The activation-pinned control-root directory identity changed."""


@dataclass(frozen=True, slots=True)
class LoadedQueuePolicy:
    value: dict[str, Any]
    raw_bytes: bytes
    sha256: str


@dataclass(frozen=True, slots=True)
class CompletedQueueEntry:
    entry: dict[str, Any]
    decision: dict[str, Any]
    decision_bytes: bytes
    journal: dict[str, Any]
    journal_bytes: bytes
    bundle: VerifiedCaptureBundle
    terminal: dict[str, Any]
    terminal_bytes: bytes
    completion: dict[str, Any]
    completion_bytes: bytes


@dataclass(frozen=True, slots=True)
class QueueLockLease:
    root_identity: dict[str, Any]
    root_fd: int
    identity: dict[str, Any]
    error: str | None = None


def _reject_duplicate_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise KaggleQueueError("queue JSON contains a duplicate key")
        value[key] = item
    return value


def _reject_json_constant(_value: str) -> None:
    raise KaggleQueueError("queue JSON contains a non-finite constant")


def _strict_json_bytes(data: bytes, *, role: str) -> dict[str, Any]:
    if not data or len(data) > MAX_QUEUE_RECEIPT_BYTES:
        raise KaggleQueueError(f"{role} exceeds the safety limit")
    try:
        value = json.loads(
            data.decode("utf-8", errors="strict"),
            object_pairs_hook=_reject_duplicate_pairs,
            parse_constant=_reject_json_constant,
        )
    except KaggleQueueError:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError, RecursionError):
        raise KaggleQueueError(f"{role} is not bounded strict JSON") from None
    if not isinstance(value, dict):
        raise KaggleQueueError(f"{role} must be an object")
    try:
        _canonical_json_bytes(value)
    except (TypeError, ValueError, UnicodeError, RecursionError):
        raise KaggleQueueError(f"{role} is not canonicalizable JSON") from None
    return value


def _read_stable_regular(path: Path, *, maximum: int, role: str) -> bytes:
    required = ("O_NOFOLLOW", "O_NONBLOCK", "O_CLOEXEC")
    if any(not hasattr(os, flag) for flag in required):
        raise KaggleQueueError(f"{role} reader requires fail-closed file flags")
    try:
        before = os.stat(path, follow_symlinks=False)
    except OSError as exc:
        raise KaggleQueueError(f"cannot read {role}: {exc}") from exc
    if (
        not stat.S_ISREG(before.st_mode)
        or before.st_nlink != 1
        or before.st_size <= 0
        or before.st_size > maximum
    ):
        raise KaggleQueueError(
            f"{role} must be one bounded single-link regular file"
        )
    descriptor: int | None = None
    try:
        descriptor = os.open(
            path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC
        )
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
                raise KaggleQueueError(f"{role} changed while it was opened")
            data = handle.read(maximum + 1)
            after = os.fstat(handle.fileno())
    except KaggleQueueError:
        raise
    except OSError as exc:
        raise KaggleQueueError(f"cannot read {role}: {exc}") from exc
    finally:
        if descriptor is not None:
            os.close(descriptor)
    try:
        final = os.stat(path, follow_symlinks=False)
    except OSError:
        raise KaggleQueueError(f"{role} changed while it was read") from None
    identity = (opened.st_dev, opened.st_ino)
    if (
        not data
        or len(data) > maximum
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
        raise KaggleQueueError(f"{role} changed while it was read")
    return data


def _exact_fields(value: Any, expected: set[str], *, role: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != expected:
        raise KaggleQueueError(f"{role} has invalid fields")
    return value


def _string(value: Any, *, role: str, maximum: int = 2_000) -> str:
    if (
        not isinstance(value, str)
        or not value
        or len(value) > maximum
        or any(ord(character) < 32 or ord(character) == 127 for character in value)
    ):
        raise KaggleQueueError(f"{role} must be a bounded string")
    return value


def _positive_int(value: Any, *, role: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise KaggleQueueError(f"{role} must be a positive integer")
    return value


def _false(value: Any, *, role: str) -> None:
    if value is not False:
        raise KaggleQueueError(f"{role} must remain false")


def _decimal(value: Any, *, role: str, positive: bool = False) -> Decimal:
    if not isinstance(value, str) or not _MONEY.fullmatch(value):
        raise KaggleQueueError(f"{role} must be a fixed two-decimal USD string")
    try:
        number = Decimal(value)
    except InvalidOperation:
        raise KaggleQueueError(f"{role} is invalid") from None
    if number < 0 or (positive and number <= 0):
        raise KaggleQueueError(f"{role} is invalid")
    return number


def _fraction(value: Any, *, role: str) -> Decimal:
    number = _decimal(value, role=role)
    if number > 1:
        raise KaggleQueueError(f"{role} must be between zero and one")
    return number


def _time(value: Any, *, role: str) -> datetime:
    text = _string(value, role=role, maximum=64)
    if not text.endswith("Z"):
        raise KaggleQueueError(f"{role} must be canonical UTC")
    try:
        parsed = datetime.fromisoformat(text[:-1] + "+00:00")
    except ValueError:
        raise KaggleQueueError(f"{role} is invalid") from None
    if parsed.tzinfo is None or parsed.utcoffset() != timedelta(0):
        raise KaggleQueueError(f"{role} must be UTC")
    return parsed


def _relative_path(value: Any, *, role: str) -> PurePosixPath:
    text = _string(value, role=role, maximum=500)
    path = PurePosixPath(text)
    if (
        path.is_absolute()
        or not path.parts
        or any(part in {"", ".", ".."} for part in path.parts)
        or str(path) != text
    ):
        raise KaggleQueueError(f"{role} must be a canonical relative path")
    return path


def _sha(value: Any, *, role: str, commit: bool = False) -> str:
    text = _string(value, role=role, maximum=64)
    pattern = _COMMIT if commit else _SHA256
    if not pattern.fullmatch(text):
        raise KaggleQueueError(f"{role} has an invalid digest")
    return text


def _model_slug(value: Any, *, role: str) -> str:
    text = _string(value, role=role, maximum=200)
    if not _MODEL_SLUG.fullmatch(text):
        raise KaggleQueueError(f"{role} is not an exact model-version slug")
    return text


def _canonical_time(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _sample_clock(
    clock: Callable[[], datetime],
    *,
    role: str,
    not_before: datetime | None = None,
) -> datetime:
    value = clock()
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise KaggleQueueBreaker(f"{role} must be timezone-aware")
    value = value.astimezone(timezone.utc)
    if not_before is not None and value < not_before:
        raise KaggleQueueBreaker(f"{role} moved backwards")
    return value


def _policy_entry_paths(entry: dict[str, Any]) -> dict[str, PurePosixPath]:
    fields = {
        "completionReceipt": "completionReceiptRelativePath",
        "decisionReceipt": "decisionRelativePath",
        "dispatchJournal": "journalRelativePath",
        "evidenceBundle": "bundleDirectory",
        "terminalQuotaReceipt": "terminalQuotaRelativePath",
    }
    return {
        role: _relative_path(
            entry[field], role=f"queue entry {entry['order']} {role}"
        )
        for role, field in fields.items()
    }


def _pretty_canonical_json_bytes(value: dict[str, Any]) -> bytes:
    try:
        return (
            json.dumps(
                value,
                allow_nan=False,
                ensure_ascii=True,
                indent=2,
                sort_keys=True,
            )
            + "\n"
        ).encode("ascii")
    except (TypeError, ValueError, UnicodeError, RecursionError):
        raise KaggleQueueError(
            "queue policy cannot be canonically encoded"
        ) from None


def _validate_policy(value: dict[str, Any]) -> None:
    _exact_fields(
        value,
        {
            "artifactKind",
            "authority",
            "captureContract",
            "catalogRequirements",
            "circuitBreaker",
            "dispatchPolicy",
            "evidenceGate",
            "evidenceLayout",
            "excludedModels",
            "expiresAt",
            "fixedEligibility",
            "policyId",
            "policySchemaVersion",
            "queue",
            "stateMachine",
            "targetProtocolVersion",
            "trackingIssue",
        },
        role="queue policy",
    )
    expected_scalars = {
        "artifactKind": "aleph_bench_kaggle_capture_queue_policy",
        "policyId": "aleph-bench-v0.2-kaggle-capture-queue-v1",
        "policySchemaVersion": "1.0.0",
        "targetProtocolVersion": "0.2.0",
        "trackingIssue": "https://github.com/p-to-q/aleph/issues/93",
    }
    for key, expected in expected_scalars.items():
        if value[key] != expected:
            raise KaggleQueueError(f"queue policy {key} is invalid")
    _time(value["expiresAt"], role="queue policy expiry")

    authority = _exact_fields(
        value["authority"],
        {
            "captureSourceAuthorityCommit",
            "captureSourceSha256",
            "creationJournalSha256",
            "creationRunId",
            "creationRunModelVersionSlug",
            "datasetRefs",
            "expectedInitialRuns",
            "notebookSha256",
            "repository",
            "sourceKernelId",
            "taskOwner",
            "taskSlug",
            "taskVersion",
        },
        role="queue policy authority",
    )
    if authority["repository"] != "p-to-q/aleph":
        raise KaggleQueueError("queue policy repository is invalid")
    _sha(
        authority["captureSourceAuthorityCommit"],
        role="capture source authority commit",
        commit=True,
    )
    _sha(authority["captureSourceSha256"], role="capture source digest")
    _sha(authority["creationJournalSha256"], role="creation journal digest")
    _sha(authority["notebookSha256"], role="capture notebook digest")
    if authority["taskOwner"] != "jahyee":
        raise KaggleQueueError("queue policy task owner is invalid")
    if authority["taskSlug"] != CAPTURE_TASK_SLUG:
        raise KaggleQueueError("queue policy task slug is invalid")
    if authority["taskVersion"] != 10:
        raise KaggleQueueError("queue policy task version is invalid")
    if authority["sourceKernelId"] != 135410138:
        raise KaggleQueueError("queue policy source kernel is invalid")
    if authority["datasetRefs"] != [
        "jahyee/aleph-bench-v02-scorer-conformance"
    ]:
        raise KaggleQueueError("queue policy dataset authority is invalid")
    initial_runs = authority["expectedInitialRuns"]
    if not isinstance(initial_runs, list) or len(initial_runs) != 1:
        raise KaggleQueueError("queue policy initial run set is invalid")
    initial_run = _exact_fields(
        initial_runs[0],
        {"modelVersionSlug", "runId", "state"},
        role="queue policy initial run",
    )
    if (
        initial_run["runId"] != 3193338
        or initial_run["modelVersionSlug"] != "gemini-3.7-flash"
        or initial_run["state"] != _COMPLETED_RUN_STATE
        or authority["creationRunId"] != initial_run["runId"]
        or authority["creationRunModelVersionSlug"]
        != initial_run["modelVersionSlug"]
    ):
        raise KaggleQueueError("queue policy initial run is invalid")

    capture = _exact_fields(
        value["captureContract"],
        {
            "captureGeneration",
            "captureSchemaVersion",
            "maxTransportRetries",
            "numericReturn",
            "plannedCallCount",
            "scopeKind",
            "scorerExecution",
            "timeoutSeconds",
        },
        role="queue policy capture contract",
    )
    expected_capture = {
        "captureGeneration": 4,
        "captureSchemaVersion": "1.2.0",
        "maxTransportRetries": 0,
        "numericReturn": False,
        "plannedCallCount": 6,
        "scopeKind": "transportCanary",
        "scorerExecution": False,
        "timeoutSeconds": 180,
    }
    if capture != expected_capture:
        raise KaggleQueueError("queue policy capture contract drifted")

    catalog = _exact_fields(
        value["catalogRequirements"],
        {
            "allowModelProxy",
            "deprecatedAt",
            "isDefault",
            "parentPublished",
            "versionPublished",
        },
        role="queue policy catalog requirements",
    )
    if catalog != {
        "allowModelProxy": True,
        "deprecatedAt": None,
        "isDefault": True,
        "parentPublished": True,
        "versionPublished": True,
    }:
        raise KaggleQueueError("queue policy catalog requirements drifted")

    breaker = _exact_fields(
        value["circuitBreaker"],
        {"automaticReset", "terminalOn"},
        role="queue policy circuit breaker",
    )
    if breaker["automaticReset"] is not False or breaker["terminalOn"] != [
        "dispatch_ambiguous_or_unreconciled",
        "transport_or_provider_failure",
        "invalid_or_incomplete_capture",
        "authority_or_identity_drift",
        "prior_evidence_gate_failure",
        "quota_or_allowance_drift",
        "post_run_cost_breaker",
        "local_writer_or_remote_run_set_conflict",
    ]:
        raise KaggleQueueError("queue policy circuit breaker drifted")

    dispatch = _exact_fields(
        value["dispatchPolicy"],
        {
            "dailyQueueSpendCapUsd",
            "dailyRefillAdvanceSeconds",
            "dailyRefillAdvanceToleranceMilliseconds",
            "dailyReserveFraction",
            "dailyReserveMinimumUsd",
            "dailyReserveRule",
            "forbidLocalMidnightReset",
            "forbidPaidRetry",
            "maxDispatchesPerRollingWindow",
            "maxPaidSchedulePostsPerInvocation",
            "maxTotalDispatches",
            "monthlyRefillAdvanceRule",
            "monthlyReserveFraction",
            "postRunQuotaSource",
            "refillTimeRole",
            "rejectIntermediateOrReversedRefillTime",
            "requireOneControlRoot",
            "requireOneOriginalCreationReceipt",
            "requireOneWriterHost",
            "requireStrictSerialRuns",
            "rollingSpendAccounting",
            "rollingWindowSeconds",
            "sameWindowRefillTimeJitterToleranceMilliseconds",
        },
        role="queue policy dispatch policy",
    )
    _decimal(dispatch["dailyQueueSpendCapUsd"], role="daily spend cap", positive=True)
    _fraction(dispatch["dailyReserveFraction"], role="daily reserve fraction")
    _decimal(dispatch["dailyReserveMinimumUsd"], role="daily reserve minimum")
    _fraction(dispatch["monthlyReserveFraction"], role="monthly reserve fraction")
    expected_dispatch = {
        "dailyReserveRule": "max_usd_or_fraction",
        "dailyRefillAdvanceSeconds": 86400,
        "dailyRefillAdvanceToleranceMilliseconds": 5,
        "forbidLocalMidnightReset": True,
        "forbidPaidRetry": True,
        "maxDispatchesPerRollingWindow": 3,
        "maxPaidSchedulePostsPerInvocation": 1,
        "maxTotalDispatches": 6,
        "monthlyRefillAdvanceRule": (
            "prior_boundary_elapsed_unchanged_allowance_coherent_usage_reset"
        ),
        "postRunQuotaSource": (
            "independent_terminal_quota_receipt_after_verified_evidence"
        ),
        "refillTimeRole": "consistency_observation_not_window_key",
        "rejectIntermediateOrReversedRefillTime": True,
        "requireOneControlRoot": True,
        "requireOneOriginalCreationReceipt": True,
        "requireOneWriterHost": True,
        "requireStrictSerialRuns": True,
        "rollingSpendAccounting": (
            "max_declared_worst_case_sum_and_coherent_observed_usage_increase"
        ),
        "rollingWindowSeconds": 86400,
        "sameWindowRefillTimeJitterToleranceMilliseconds": 5,
    }
    for key, expected in expected_dispatch.items():
        if dispatch[key] != expected or type(dispatch[key]) is not type(expected):
            raise KaggleQueueError(f"queue dispatch policy {key} drifted")

    evidence_gate = _exact_fields(
        value["evidenceGate"],
        {
            "assemblyEligible",
            "canonicalReplayEligible",
            "captureComplete",
            "closedWorldBundleReload",
            "dispatchJournalState",
            "exactCatalogBinding",
            "exactRunBinding",
            "finalizationReceiptBindsPriorArtifacts",
            "terminalQuotaReceiptAfterVerifiedEvidence",
            "verifiedEvidenceEnvelope",
        },
        role="queue evidence gate",
    )
    if evidence_gate != {
        "assemblyEligible": True,
        "canonicalReplayEligible": True,
        "captureComplete": True,
        "closedWorldBundleReload": True,
        "dispatchJournalState": "reconciled",
        "exactCatalogBinding": True,
        "exactRunBinding": True,
        "finalizationReceiptBindsPriorArtifacts": True,
        "terminalQuotaReceiptAfterVerifiedEvidence": True,
        "verifiedEvidenceEnvelope": True,
    }:
        raise KaggleQueueError("queue evidence gate drifted")

    layout = _exact_fields(
        value["evidenceLayout"],
        {
            "artifactDirectoryMode",
            "artifactFileMode",
            "controlRootMode",
            "controlRootSentinelRelativePath",
            "creationJournalRelativePath",
            "requireNewEntryPaths",
        },
        role="queue evidence layout",
    )
    if (
        layout["artifactDirectoryMode"] != "0700"
        or layout["artifactFileMode"] != "0600"
        or layout["controlRootMode"] != "0700"
    ):
        raise KaggleQueueError("queue evidence permissions drifted")
    _relative_path(
        layout["controlRootSentinelRelativePath"],
        role="control-root sentinel path",
    )
    _relative_path(
        layout["creationJournalRelativePath"], role="creation journal path"
    )
    if layout["requireNewEntryPaths"] is not True:
        raise KaggleQueueError("queue entry paths must remain new")

    eligibility = _exact_fields(
        value["fixedEligibility"],
        {
            "canonicalScoringInputEligible",
            "huggingFaceEligible",
            "leaderboardEligible",
            "publicationEligible",
            "resultEligible",
            "scoreEligible",
        },
        role="queue fixed eligibility",
    )
    for key, item in eligibility.items():
        _false(item, role=f"queue {key}")

    excluded = value["excludedModels"]
    if not isinstance(excluded, list) or len(excluded) != 7:
        raise KaggleQueueError("queue excluded-model list is invalid")
    excluded_slugs: list[str] = []
    for index, item in enumerate(excluded, start=1):
        item = _exact_fields(
            item,
            {"modelVersionSlug", "reason"},
            role=f"excluded model {index}",
        )
        excluded_slugs.append(
            _model_slug(item["modelVersionSlug"], role="excluded model slug")
        )
        _string(item["reason"], role="excluded model reason")
    if len(set(excluded_slugs)) != len(excluded_slugs):
        raise KaggleQueueError("queue excluded-model slugs are not unique")

    queue = value["queue"]
    if not isinstance(queue, list) or len(queue) != 6:
        raise KaggleQueueError("queue must contain exactly six entries")
    model_slugs: list[str] = []
    model_ids: list[int] = []
    version_ids: list[int] = []
    proxy_slugs: list[str] = []
    artifact_directories: list[str] = []
    all_paths: list[str] = []
    for order, raw_entry in enumerate(queue, start=1):
        entry = _exact_fields(
            raw_entry,
            {
                "allowModelProxy",
                "bundleDirectory",
                "completionReceiptRelativePath",
                "decisionRelativePath",
                "declaredWorstCaseCostUsd",
                "deprecatedAt",
                "isDefault",
                "journalRelativePath",
                "minimumSecondsSincePreviousDispatchExclusive",
                "modelId",
                "modelProxySlug",
                "modelVersionId",
                "modelVersionSlug",
                "mustBeOnlyQueueDispatchInRollingWindow",
                "order",
                "parentPublished",
                "postRunBreakerUsd",
                "requiresPriorHealthyEntries",
                "requiresProvenDailyAllowanceUsageReset",
                "role",
                "terminalQuotaRelativePath",
                "versionPublished",
            },
            role=f"queue entry {order}",
        )
        if entry["order"] != order:
            raise KaggleQueueError("queue entries are not in exact order")
        for key in (
            "allowModelProxy",
            "isDefault",
            "parentPublished",
            "versionPublished",
        ):
            if entry[key] is not True:
                raise KaggleQueueError(f"queue entry {order} {key} drifted")
        if entry["deprecatedAt"] is not None:
            raise KaggleQueueError(f"queue entry {order} is deprecated")
        slug = _model_slug(
            entry["modelVersionSlug"], role=f"queue entry {order} model slug"
        )
        proxy = _string(
            entry["modelProxySlug"],
            role=f"queue entry {order} proxy slug",
            maximum=300,
        )
        model_slugs.append(slug)
        proxy_slugs.append(proxy)
        model_ids.append(_positive_int(entry["modelId"], role="model ID"))
        version_ids.append(
            _positive_int(entry["modelVersionId"], role="model version ID")
        )
        worst = _decimal(
            entry["declaredWorstCaseCostUsd"],
            role=f"queue entry {order} worst-case cost",
            positive=True,
        )
        breaker_cost = _decimal(
            entry["postRunBreakerUsd"],
            role=f"queue entry {order} post-run breaker",
            positive=True,
        )
        if worst != breaker_cost:
            raise KaggleQueueError(
                f"queue entry {order} cost and breaker must match"
            )
        artifact = str(PurePosixPath(entry["decisionRelativePath"]).parent)
        artifact_directories.append(artifact)
        paths = _policy_entry_paths(entry)
        for path in paths.values():
            if path != PurePosixPath(artifact) and PurePosixPath(artifact) not in path.parents:
                raise KaggleQueueError(
                    f"queue entry {order} path escapes its artifact directory"
                )
            all_paths.append(str(path))
        _string(entry["role"], role=f"queue entry {order} role")
        minimum_seconds = entry["minimumSecondsSincePreviousDispatchExclusive"]
        if (
            isinstance(minimum_seconds, bool)
            or not isinstance(minimum_seconds, int)
            or minimum_seconds < 0
        ):
            raise KaggleQueueError(
                f"queue entry {order} prior-dispatch age is invalid"
            )
        expected_tail = order == len(queue)
        if (
            entry["mustBeOnlyQueueDispatchInRollingWindow"] is not expected_tail
            or entry["requiresProvenDailyAllowanceUsageReset"] is not expected_tail
            or minimum_seconds != (86400 if expected_tail else 0)
            or entry["requiresPriorHealthyEntries"] != order - 1
        ):
            raise KaggleQueueError(
                f"queue entry {order} quarantine policy drifted"
            )
    for values, role in (
        (model_slugs, "model slugs"),
        (model_ids, "model IDs"),
        (version_ids, "model version IDs"),
        (proxy_slugs, "proxy slugs"),
        (artifact_directories, "artifact directories"),
        (all_paths, "artifact paths"),
    ):
        if len(values) != len(set(values)):
            raise KaggleQueueError(f"queue {role} are not unique")
    if set(model_slugs) & set(excluded_slugs):
        raise KaggleQueueError("queue includes an explicitly excluded model")
    if dispatch["maxTotalDispatches"] != len(queue):
        raise KaggleQueueError("queue dispatch count differs from its entries")

    state = _exact_fields(
        value["stateMachine"],
        {
            "exhaustedOn",
            "expiredOn",
            "heldOn",
            "onlyHeldMayClearAutomatically",
        },
        role="queue state machine",
    )
    if state != {
        "exhaustedOn": "all_six_entries_finalized",
        "expiredOn": "expires_at_reached",
        "heldOn": [
            "awaiting_terminal_run_or_evidence_finalization",
            "required_read_temporarily_unavailable",
            "rolling_window_dispatch_limit",
            "quota_reserve_or_rolling_spend_cap",
            "claude_fresh_window_not_yet_proven",
        ],
        "onlyHeldMayClearAutomatically": True,
    }:
        raise KaggleQueueError("queue state-machine contract drifted")


def load_queue_policy(
    path: Path = POLICY_PATH, *, expected_sha256: str
) -> LoadedQueuePolicy:
    """Load the one checked-in queue policy with an external digest pin."""

    if not _SHA256.fullmatch(expected_sha256):
        raise KaggleQueueError("expected policy SHA-256 is invalid")
    data = _read_stable_regular(
        path, maximum=MAX_POLICY_BYTES, role="queue policy"
    )
    digest = hashlib.sha256(data).hexdigest()
    if digest != expected_sha256:
        raise KaggleQueueError("queue policy SHA-256 differs from activation authority")
    value = _strict_json_bytes(data, role="queue policy")
    if data != _pretty_canonical_json_bytes(value):
        raise KaggleQueueError("queue policy file bytes are not canonical JSON")
    _validate_policy(value)
    return LoadedQueuePolicy(value=value, raw_bytes=data, sha256=digest)


def verify_execution_checkout(
    root: Path, *, expected_commit: str
) -> dict[str, str]:
    """Bind execution to one clean, merged Git checkout."""

    _sha(expected_commit, role="expected execution commit", commit=True)
    try:
        resolved = root.resolve(strict=True)
    except OSError as exc:
        raise KaggleQueueError(f"cannot resolve execution checkout: {exc}") from exc
    try:
        head = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=resolved,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=30,
        ).stdout.strip()
        status_text = subprocess.run(
            ["git", "status", "--porcelain=v1", "--untracked-files=all"],
            cwd=resolved,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=30,
        ).stdout
    except (OSError, subprocess.SubprocessError) as exc:
        raise KaggleQueueError(f"cannot verify execution checkout: {exc}") from exc
    if head != expected_commit:
        raise KaggleQueueError("execution checkout is not the activated merge commit")
    if status_text:
        raise KaggleQueueError("execution checkout is not clean")
    return {"commit": head, "repositoryRoot": str(resolved)}


def _verify_loaded_authority_paths(
    execution_root: Path, *, policy_path: Path
) -> Path:
    """Prove the executing modules and policy came from the claimed checkout."""

    try:
        root = execution_root.resolve(strict=True)
        expected_policy = (
            root / "bench" / "config" / "kaggle-capture-queue-v1.json"
        ).resolve(strict=True)
        observed_policy = policy_path.resolve(strict=True)
    except OSError as exc:
        raise KaggleQueueError(f"cannot bind loaded execution paths: {exc}") from exc
    if root != _LOADED_REPOSITORY_ROOT or observed_policy != expected_policy:
        raise KaggleQueueError(
            "executing queue code and policy are not from the claimed checkout"
        )
    for callable_object in (
        run_queue_once,
        run_once,
        load_verified_capture_bundle,
    ):
        module = sys.modules.get(callable_object.__module__)
        module_file = getattr(module, "__file__", None)
        if not isinstance(module_file, str):
            raise KaggleQueueError("loaded queue authority module has no file identity")
        try:
            Path(module_file).resolve(strict=True).relative_to(root)
        except (OSError, ValueError):
            raise KaggleQueueError(
                "loaded queue authority module escaped the claimed checkout"
            ) from None
    return root


def _private_root_identity(root: Path) -> dict[str, Any]:
    required = ("O_NOFOLLOW", "O_CLOEXEC", "O_DIRECTORY")
    if any(not hasattr(os, flag) for flag in required) or not hasattr(os, "geteuid"):
        raise KaggleQueueError("control root requires fail-closed filesystem flags")
    try:
        before = os.stat(root, follow_symlinks=False)
        descriptor = os.open(
            root, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_DIRECTORY
        )
    except OSError as exc:
        raise KaggleQueueError(f"cannot open private control root: {exc}") from exc
    try:
        opened = os.fstat(descriptor)
    finally:
        os.close(descriptor)
    if (
        not stat.S_ISDIR(before.st_mode)
        or not stat.S_ISDIR(opened.st_mode)
        or (before.st_dev, before.st_ino) != (opened.st_dev, opened.st_ino)
        or before.st_uid != os.geteuid()
        or stat.S_IMODE(before.st_mode) & 0o077
    ):
        raise KaggleQueueError(
            "control root must be one private directory owned by this user"
        )
    return {
        "device": before.st_dev,
        "inode": before.st_ino,
        "ownerUid": before.st_uid,
        "mode": format(stat.S_IMODE(before.st_mode), "04o"),
    }


def _pinned_control_root_identity(
    root: Path,
    *,
    expected_device: int,
    expected_inode: int,
) -> dict[str, Any]:
    """Prove that the live pathname still names the activation-pinned root."""

    _positive_int(expected_device, role="expected control-root device")
    _positive_int(expected_inode, role="expected control-root inode")
    observed = _private_root_identity(root)
    if (
        observed["device"] != expected_device
        or observed["inode"] != expected_inode
    ):
        raise KaggleControlRootDrift(
            "control-root pathname differs from its activation-pinned identity"
        )
    return observed


@contextmanager
def _exclusive_queue_lock(
    root: Path,
    *,
    expected_device: int,
    expected_inode: int,
) -> Iterator[QueueLockLease]:
    """Hold one same-host writer lock for the complete controller invocation.

    The policy deliberately does not claim a distributed lock.  This lock
    closes the local decision-to-POST race and makes receipt publication
    atomic with respect to another controller using the same private root.
    """

    pinned_root = _pinned_control_root_identity(
        root,
        expected_device=expected_device,
        expected_inode=expected_inode,
    )
    required = ("O_NOFOLLOW", "O_CLOEXEC", "O_DIRECTORY", "O_NONBLOCK")
    if any(not hasattr(os, flag) for flag in required) or not hasattr(os, "geteuid"):
        raise KaggleQueueError("queue lock requires fail-closed filesystem flags")
    root_fd: int | None = None
    lock_fd: int | None = None
    try:
        root_fd = os.open(
            root, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_DIRECTORY
        )
        opened_root = os.fstat(root_fd)
        if (
            opened_root.st_dev != expected_device
            or opened_root.st_ino != expected_inode
            or opened_root.st_uid != os.geteuid()
            or stat.S_IMODE(opened_root.st_mode) != 0o700
            or (opened_root.st_dev, opened_root.st_ino)
            != (pinned_root["device"], pinned_root["inode"])
        ):
            raise KaggleControlRootDrift(
                "opened control root differs from its activation-pinned identity"
            )
        # The directory inode is the primary lease.  Locking only a named file
        # would let a same-root contender rename that pathname, create a fresh
        # inode, and acquire a second independent flock while the first writer
        # is already at the paid boundary.
        try:
            fcntl.flock(root_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise KaggleQueueHeld(
                "another same-root controller invocation is active"
            ) from None
        marker_error: str | None = None
        opened: os.stat_result | None = None
        named: os.stat_result | None = None
        try:
            lock_fd = os.open(
                _LOCK_PATH.name,
                os.O_RDWR
                | os.O_CREAT
                | os.O_NOFOLLOW
                | os.O_CLOEXEC
                | os.O_NONBLOCK,
                0o600,
                dir_fd=root_fd,
            )
            opened = os.fstat(lock_fd)
            named = os.stat(
                _LOCK_PATH.name,
                dir_fd=root_fd,
                follow_symlinks=False,
            )
        except OSError:
            marker_error = "queue lock marker cannot be safely opened"

        if opened is not None and named is not None:
            if (
                stat.S_ISREG(opened.st_mode)
                and stat.S_ISREG(named.st_mode)
                and (opened.st_dev, opened.st_ino)
                == (named.st_dev, named.st_ino)
                and opened.st_uid == os.geteuid()
            ):
                try:
                    fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError:
                    raise KaggleQueueHeld(
                        "another same-root controller invocation is active"
                    ) from None
                except OSError:
                    marker_error = "queue lock marker cannot be safely locked"
            else:
                marker_error = (
                    "queue lock must be one private single-link regular file"
                )

        # Publish every marker-integrity breaker while the root-directory
        # lease is still held.  This includes hard-link and pathname/inode
        # drift; releasing the root first would reopen a decision-to-POST race.
        if marker_error is None and lock_fd is not None:
            try:
                opened = os.fstat(lock_fd)
                named = os.stat(
                    _LOCK_PATH.name,
                    dir_fd=root_fd,
                    follow_symlinks=False,
                )
            except OSError:
                marker_error = "queue lock marker changed while it was locked"
        identity = (
            {}
            if opened is None
            else {
                "device": opened.st_dev,
                "inode": opened.st_ino,
                "mode": format(stat.S_IMODE(opened.st_mode), "04o"),
                "ownerUid": opened.st_uid,
            }
        )
        if marker_error is None and (
            named is None
            or not stat.S_ISREG(opened.st_mode)
            or not stat.S_ISREG(named.st_mode)
            or opened.st_nlink != 1
            or named.st_nlink != 1
            or (opened.st_dev, opened.st_ino) != (named.st_dev, named.st_ino)
            or opened.st_uid != os.geteuid()
            or named.st_uid != os.geteuid()
            or stat.S_IMODE(opened.st_mode) != 0o600
            or stat.S_IMODE(named.st_mode) != 0o600
        ):
            marker_error = "queue lock must be one private single-link regular file"
        # Close the lstat/open/flock race before exposing the lease to any
        # receipt or remote-state read.
        if _pinned_control_root_identity(
            root,
            expected_device=expected_device,
            expected_inode=expected_inode,
        ) != pinned_root:
            raise KaggleControlRootDrift(
                "control-root pathname changed while acquiring its lease"
            )
        yield QueueLockLease(
            root_identity=pinned_root,
            root_fd=root_fd,
            identity=identity,
            error=marker_error,
        )
    except KaggleQueueHeld:
        raise
    except KaggleQueueError:
        raise
    except OSError as exc:
        raise KaggleQueueError(f"cannot acquire private queue lock: {exc}") from exc
    finally:
        if lock_fd is not None:
            try:
                fcntl.flock(lock_fd, fcntl.LOCK_UN)
            except OSError:
                pass
            os.close(lock_fd)
        if root_fd is not None:
            try:
                fcntl.flock(root_fd, fcntl.LOCK_UN)
            except OSError:
                pass
            os.close(root_fd)


def _path_under(root: Path, relative: PurePosixPath) -> Path:
    return root.joinpath(*relative.parts)


@contextmanager
def _private_directory_fd(
    root: Path,
    relative: PurePosixPath,
    *,
    expected_device: int,
    expected_inode: int,
    create: bool,
) -> Iterator[int]:
    """Open one owned 0700 directory chain relative to the pinned root."""

    required = ("O_NOFOLLOW", "O_CLOEXEC", "O_DIRECTORY")
    if any(not hasattr(os, flag) for flag in required) or not hasattr(
        os, "geteuid"
    ):
        raise KaggleQueueError(
            "private directory traversal requires fail-closed filesystem flags"
        )
    root_fd: int | None = None
    current_fd: int | None = None
    try:
        root_fd = os.open(
            root, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_DIRECTORY
        )
        opened_root = os.fstat(root_fd)
        if (
            opened_root.st_dev != expected_device
            or opened_root.st_ino != expected_inode
            or opened_root.st_uid != os.geteuid()
            or stat.S_IMODE(opened_root.st_mode) != 0o700
        ):
            raise KaggleControlRootDrift(
                "opened control root differs from its activation-pinned identity"
            )
        current_fd = root_fd
        for part in relative.parts:
            created = False
            try:
                next_fd = os.open(
                    part,
                    os.O_RDONLY
                    | os.O_NOFOLLOW
                    | os.O_CLOEXEC
                    | os.O_DIRECTORY,
                    dir_fd=current_fd,
                )
            except FileNotFoundError:
                if not create:
                    raise
                os.mkdir(part, mode=0o700, dir_fd=current_fd)
                os.fsync(current_fd)
                next_fd = os.open(
                    part,
                    os.O_RDONLY
                    | os.O_NOFOLLOW
                    | os.O_CLOEXEC
                    | os.O_DIRECTORY,
                    dir_fd=current_fd,
                )
                created = True
            try:
                if created:
                    os.fchmod(next_fd, 0o700)
                    os.fsync(next_fd)
                opened = os.fstat(next_fd)
                if (
                    not stat.S_ISDIR(opened.st_mode)
                    or opened.st_uid != os.geteuid()
                    or stat.S_IMODE(opened.st_mode) != 0o700
                ):
                    raise KaggleQueueError(
                        "private directory chain must contain only owned "
                        "0700 directories"
                    )
            except BaseException:
                os.close(next_fd)
                raise
            if current_fd != root_fd:
                os.close(current_fd)
            current_fd = next_fd
        yield current_fd
    except (KaggleQueueError, KaggleControlRootDrift):
        raise
    except OSError as exc:
        raise KaggleQueueError(
            f"cannot traverse private control-root directory: {exc}"
        ) from exc
    finally:
        if current_fd is not None and current_fd != root_fd:
            os.close(current_fd)
        if root_fd is not None:
            os.close(root_fd)


def _read_private_root_file(
    root: Path,
    relative: PurePosixPath,
    *,
    expected_device: int,
    expected_inode: int,
    maximum: int,
    role: str,
) -> bytes:
    """Read one private file without following any root-relative alias."""

    required = ("O_NOFOLLOW", "O_NONBLOCK", "O_CLOEXEC")
    if any(not hasattr(os, flag) for flag in required):
        raise KaggleQueueError(f"{role} reader requires fail-closed file flags")
    with _private_directory_fd(
        root,
        relative.parent,
        expected_device=expected_device,
        expected_inode=expected_inode,
        create=False,
    ) as directory_fd:
        try:
            before = os.stat(
                relative.name,
                dir_fd=directory_fd,
                follow_symlinks=False,
            )
        except OSError as exc:
            raise KaggleQueueError(f"cannot read {role}: {exc}") from exc
        if (
            not stat.S_ISREG(before.st_mode)
            or before.st_uid != os.geteuid()
            or before.st_nlink != 1
            or stat.S_IMODE(before.st_mode) != 0o600
            or before.st_size <= 0
            or before.st_size > maximum
        ):
            raise KaggleQueueError(
                f"{role} must be one owned private bounded single-link regular file"
            )
        descriptor: int | None = None
        try:
            descriptor = os.open(
                relative.name,
                os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC,
                dir_fd=directory_fd,
            )
            with os.fdopen(descriptor, "rb", closefd=True) as handle:
                descriptor = None
                opened = os.fstat(handle.fileno())
                if (
                    not stat.S_ISREG(opened.st_mode)
                    or opened.st_uid != os.geteuid()
                    or opened.st_nlink != 1
                    or stat.S_IMODE(opened.st_mode) != 0o600
                    or (opened.st_dev, opened.st_ino)
                    != (before.st_dev, before.st_ino)
                    or opened.st_size != before.st_size
                    or opened.st_mtime_ns != before.st_mtime_ns
                    or opened.st_ctime_ns != before.st_ctime_ns
                ):
                    raise KaggleQueueError(f"{role} changed while it was opened")
                data = handle.read(maximum + 1)
                after = os.fstat(handle.fileno())
        except KaggleQueueError:
            raise
        except OSError as exc:
            raise KaggleQueueError(f"cannot read {role}: {exc}") from exc
        finally:
            if descriptor is not None:
                os.close(descriptor)
        try:
            final = os.stat(
                relative.name,
                dir_fd=directory_fd,
                follow_symlinks=False,
            )
        except OSError:
            raise KaggleQueueError(f"{role} changed while it was read") from None
        identity = (opened.st_dev, opened.st_ino)
        if (
            not data
            or len(data) > maximum
            or after.st_size != len(data)
            or after.st_uid != os.geteuid()
            or after.st_nlink != 1
            or stat.S_IMODE(after.st_mode) != 0o600
            or final.st_uid != os.geteuid()
            or final.st_nlink != 1
            or stat.S_IMODE(final.st_mode) != 0o600
            or (after.st_dev, after.st_ino) != identity
            or (final.st_dev, final.st_ino) != identity
            or after.st_mtime_ns != opened.st_mtime_ns
            or final.st_mtime_ns != opened.st_mtime_ns
            or after.st_ctime_ns != opened.st_ctime_ns
            or final.st_ctime_ns != opened.st_ctime_ns
        ):
            raise KaggleQueueError(f"{role} changed while it was read")
        return data


def _ensure_private_directory(
    root: Path,
    relative: PurePosixPath,
    *,
    expected_device: int,
    expected_inode: int,
) -> None:
    with _private_directory_fd(
        root,
        relative,
        expected_device=expected_device,
        expected_inode=expected_inode,
        create=True,
    ):
        pass


def _write_private_once(
    root: Path,
    relative: PurePosixPath,
    value: dict[str, Any],
    *,
    expected_device: int,
    expected_inode: int,
) -> bytes:
    """Create one canonical receipt below a private root without aliases."""

    data = _canonical_json_bytes(value)
    if len(data) > MAX_QUEUE_RECEIPT_BYTES:
        raise KaggleQueueError("queue receipt exceeds the safety limit")
    with _private_directory_fd(
        root,
        relative.parent,
        expected_device=expected_device,
        expected_inode=expected_inode,
        create=True,
    ) as directory_fd:
        flags = (
            os.O_WRONLY
            | os.O_CREAT
            | os.O_EXCL
            | os.O_NOFOLLOW
            | os.O_CLOEXEC
        )
        file_fd: int | None = None
        try:
            file_fd = os.open(
                relative.name, flags, 0o600, dir_fd=directory_fd
            )
            os.fchmod(file_fd, 0o600)
            with os.fdopen(file_fd, "wb", closefd=True) as handle:
                file_fd = None
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
                opened = os.fstat(handle.fileno())
            final = os.stat(
                relative.name,
                dir_fd=directory_fd,
                follow_symlinks=False,
            )
            if (
                not stat.S_ISREG(opened.st_mode)
                or opened.st_uid != os.geteuid()
                or opened.st_nlink != 1
                or stat.S_IMODE(opened.st_mode) != 0o600
                or opened.st_size != len(data)
                or (final.st_dev, final.st_ino)
                != (opened.st_dev, opened.st_ino)
                or final.st_uid != os.geteuid()
                or final.st_nlink != 1
                or stat.S_IMODE(final.st_mode) != 0o600
                or final.st_size != len(data)
            ):
                raise KaggleQueueError(
                    "new queue receipt failed private-file verification"
                )
            os.fsync(directory_fd)
        except FileExistsError as exc:
            raise KaggleQueueError(
                "queue receipt already exists and cannot be overwritten: "
                f"{relative}"
            ) from exc
        except KaggleQueueError:
            raise
        except OSError as exc:
            raise KaggleQueueError(
                f"cannot durably write queue receipt: {exc}"
            ) from exc
        finally:
            if file_fd is not None:
                os.close(file_fd)
    return data


def _read_json_file(path: Path, *, role: str) -> tuple[dict[str, Any], bytes]:
    data = _read_stable_regular(
        path, maximum=MAX_QUEUE_RECEIPT_BYTES, role=role
    )
    value = _strict_json_bytes(data, role=role)
    if data != _canonical_json_bytes(value):
        raise KaggleQueueError(f"{role} bytes are not canonical JSON")
    return value, data


def _hash_record(data: bytes) -> dict[str, Any]:
    return {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def _quota_map(records: Any, *, role: str) -> dict[str, dict[str, Any]]:
    if not isinstance(records, list) or len(records) != 2:
        raise KaggleQueueError(f"{role} must contain daily and monthly quota")
    mapped: dict[str, dict[str, Any]] = {}
    for raw in records:
        record = _exact_fields(
            raw,
            {"allowedUsd", "period", "refillTime", "remainingUsd", "usedUsd"},
            role=f"{role} record",
        )
        period = record["period"]
        if period not in {"DAILY", "MONTHLY"} or period in mapped:
            raise KaggleQueueError(f"{role} has duplicate or unknown periods")
        numbers: dict[str, Decimal] = {}
        for key in ("allowedUsd", "remainingUsd", "usedUsd"):
            value = record[key]
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise KaggleQueueError(f"{role} has an invalid {key}")
            number = float(value)
            if not math.isfinite(number) or number < 0:
                raise KaggleQueueError(f"{role} has an invalid {key}")
            numbers[key] = Decimal(str(number))
        arithmetic_error = abs(
            numbers["remainingUsd"]
            - (numbers["allowedUsd"] - numbers["usedUsd"])
        )
        if (
            numbers["usedUsd"] > numbers["allowedUsd"]
            or numbers["remainingUsd"] > numbers["allowedUsd"]
            or arithmetic_error > _QUOTA_ARITHMETIC_TOLERANCE
        ):
            raise KaggleQueueError(f"{role} quota arithmetic is invalid")
        if record["refillTime"] is None:
            raise KaggleQueueError(f"{role} refillTime is unavailable")
        _time(record["refillTime"], role=f"{role} refillTime")
        mapped[period] = dict(record)
    if set(mapped) != {"DAILY", "MONTHLY"}:
        raise KaggleQueueError(f"{role} is incomplete")
    return mapped


def _quota_decimal(record: dict[str, Any], key: str) -> Decimal:
    return Decimal(str(record[key]))


def _validate_fresh_quota_observation(
    quota: dict[str, dict[str, Any]], *, observed_at: datetime
) -> None:
    """Reject a current quota observation already beyond its raw boundary."""

    for period in ("DAILY", "MONTHLY"):
        refill = _time(
            quota[period]["refillTime"], role=f"fresh {period} refillTime"
        )
        if observed_at >= refill:
            raise KaggleQueueBreaker(
                f"fresh {period} quota does not contain its observation time"
            )


def _classify_refill(
    before: dict[str, Any],
    after: dict[str, Any],
    *,
    period: str,
    before_observed_at: datetime,
    after_observed_at: datetime,
) -> str:
    for value, role in (
        (before_observed_at, "prior quota observation time"),
        (after_observed_at, "current quota observation time"),
    ):
        if not isinstance(value, datetime) or value.tzinfo is None:
            raise KaggleQueueBreaker(f"{role} is not timezone-aware")
    before_observed_at = before_observed_at.astimezone(timezone.utc)
    after_observed_at = after_observed_at.astimezone(timezone.utc)
    if after_observed_at < before_observed_at:
        raise KaggleQueueBreaker("quota observation clock moved backwards")
    if _quota_decimal(before, "allowedUsd") != _quota_decimal(after, "allowedUsd"):
        raise KaggleQueueBreaker(f"{period} quota allowance changed")
    before_time = _time(before["refillTime"], role=f"prior {period} refillTime")
    after_time = _time(after["refillTime"], role=f"current {period} refillTime")
    if before_observed_at >= before_time:
        raise KaggleQueueBreaker(
            f"prior {period} quota was stale at its announced refill boundary"
        )
    delta = after_time - before_time
    if abs(delta) <= _REFILL_JITTER:
        if after_observed_at >= min(before_time, after_time):
            raise KaggleQueueBreaker(
                f"{period} quota remained stale across its announced refill boundary"
            )
        if _quota_decimal(after, "usedUsd") < _quota_decimal(before, "usedUsd"):
            raise KaggleQueueBreaker(
                f"{period} quota usage decreased without a coherent refill"
            )
        return "same_window_jitter_tolerated"
    if delta < timedelta(0):
        raise KaggleQueueBreaker(f"{period} quota refillTime reversed")
    if after_observed_at < before_time or after_observed_at >= after_time:
        raise KaggleQueueBreaker(
            f"{period} quota advance does not bracket the observed refill"
        )
    if _quota_decimal(after, "usedUsd") >= _quota_decimal(before, "usedUsd"):
        raise KaggleQueueBreaker(
            f"{period} quota advance has no coherent usage reset"
        )
    if period == "DAILY":
        if abs(delta - timedelta(days=1)) > _REFILL_JITTER:
            raise KaggleQueueBreaker(
                "DAILY quota refillTime did not advance by a coherent 24-hour period"
            )
        return "advanced_window"
    if delta < _MIN_MONTHLY_ADVANCE or delta > _MAX_MONTHLY_ADVANCE:
        raise KaggleQueueBreaker(
            f"{period} quota refillTime changed by an ambiguous interval"
        )
    return "advanced_window"


def _decision_authorization(
    *,
    policy: LoadedQueuePolicy,
    entry: dict[str, Any],
    decision_path: PurePosixPath,
    decision_bytes: bytes,
    execution_commit: str,
) -> dict[str, Any]:
    return {
        "artifactKind": "aleph_bench_kaggle_queue_dispatch_authorization",
        "authorizationVersion": 1,
        "decision": {
            "bytes": len(decision_bytes),
            "relativePath": str(decision_path),
            "sha256": hashlib.sha256(decision_bytes).hexdigest(),
        },
        "executionCommit": execution_commit,
        "modelVersionSlug": entry["modelVersionSlug"],
        "order": entry["order"],
        "policyId": policy.value["policyId"],
        "policySha256": policy.sha256,
    }


def _validate_decision(
    value: dict[str, Any],
    *,
    data: bytes,
    policy: LoadedQueuePolicy,
    entry: dict[str, Any],
    writer_id: str,
    control_identity: dict[str, Any],
    expected_execution: dict[str, str],
) -> None:
    _exact_fields(
        value,
        {
            "artifactKind",
            "budget",
            "controlRoot",
            "createdAt",
            "decisionVersion",
            "execution",
            "fixedEligibility",
            "planned",
            "policy",
            "priorEntries",
            "snapshot",
            "target",
            "writerId",
        },
        role="queue decision receipt",
    )
    if (
        value["artifactKind"] != "aleph_bench_kaggle_queue_dispatch_decision"
        or value["decisionVersion"] != 1
        or value["writerId"] != writer_id
    ):
        raise KaggleQueueBreaker("queue decision identity drifted")
    _time(value["createdAt"], role="queue decision time")
    if value["controlRoot"] != control_identity:
        raise KaggleQueueBreaker("queue decision control-root identity drifted")
    if value["fixedEligibility"] != policy.value["fixedEligibility"]:
        raise KaggleQueueBreaker("queue decision eligibility boundary drifted")
    policy_record = _exact_fields(
        value["policy"],
        {"bytes", "id", "relativePath", "sha256"},
        role="queue decision policy",
    )
    if policy_record != {
        "bytes": len(policy.raw_bytes),
        "id": policy.value["policyId"],
        "relativePath": "bench/config/kaggle-capture-queue-v1.json",
        "sha256": policy.sha256,
    }:
        raise KaggleQueueBreaker("queue decision policy binding drifted")
    execution_record = _exact_fields(
        value["execution"],
        {"captureSourceAuthorityCommit", "commit", "repositoryRootSha256"},
        role="queue decision execution",
    )
    if (
        execution_record["captureSourceAuthorityCommit"]
        != policy.value["authority"]["captureSourceAuthorityCommit"]
        or execution_record
        != _execution_record(policy=policy, execution=expected_execution)
    ):
        raise KaggleQueueBreaker("queue decision execution binding drifted")
    target = _exact_fields(
        value["target"],
        {"modelVersionSlug", "order"},
        role="queue decision target",
    )
    if target != {
        "modelVersionSlug": entry["modelVersionSlug"],
        "order": entry["order"],
    }:
        raise KaggleQueueBreaker("queue decision target drifted")
    if not isinstance(value["priorEntries"], list):
        raise KaggleQueueBreaker("queue decision prior entries are invalid")
    # These objects are rebuilt and compared by the state-machine caller. Here
    # they only need to remain strict JSON; the full receipt is content-bound.
    _exact_fields(
        value["planned"],
        {
            "bundleRelativePath",
            "claimRelativePath",
            "completionRelativePath",
            "journalRelativePath",
        },
        role="queue decision planned paths",
    )
    _exact_fields(
        value["snapshot"],
        {"client", "creationAuthority", "model", "quota", "runs", "source", "task"},
        role="queue decision snapshot",
    )
    _exact_fields(
        value["budget"],
        {
            "apiObservedIncreaseUsd",
            "conservativeProjectedSpendUsd",
            "dailyReserveUsd",
            "declaredRollingSpendUsd",
            "declaredWorstCaseCostUsd",
            "monthlyReserveUsd",
            "rollingDispatchCount",
            "rollingWindowHours",
        },
        role="queue decision budget",
    )
    if data != _canonical_json_bytes(value):
        raise KaggleQueueBreaker("queue decision bytes drifted")


def _validate_journal_for_entry(
    value: dict[str, Any],
    *,
    data: bytes,
    policy: LoadedQueuePolicy,
    entry: dict[str, Any],
    decision_path: PurePosixPath,
    decision_bytes: bytes,
    decision: dict[str, Any],
    execution_commit: str,
) -> dict[str, Any]:
    required = {
        "artifactKind",
        "client",
        "creationAuthority",
        "createdAt",
        "dispatchAuthorization",
        "dispatchFailure",
        "failure",
        "journalVersion",
        "operationId",
        "quotaAfter",
        "reconciliation",
        "remotePreflight",
        "response",
        "responseFailure",
        "state",
        "target",
        "updatedAt",
    }
    fields = set(value)
    has_quota_after = value.get("quotaAfter") is not None
    if has_quota_after:
        if fields != required:
            raise KaggleQueueBreaker("queue dispatch journal has invalid fields")
        _quota_map(value["quotaAfter"], role="queue dispatch quota after")
    else:
        if fields != required | {"quotaAfterFailure"}:
            raise KaggleQueueBreaker("queue dispatch journal has invalid fields")
        quota_failure = value["quotaAfterFailure"]
        if (
            not isinstance(quota_failure, dict)
            or set(quota_failure) != {"message", "type"}
            or not isinstance(quota_failure["type"], str)
            or not quota_failure["type"]
            or len(quota_failure["type"]) > 200
            or not isinstance(quota_failure["message"], str)
            or len(quota_failure["message"]) > 2_000
        ):
            raise KaggleQueueBreaker(
                "queue dispatch quota-after failure is invalid"
            )
    if (
        value["artifactKind"] != "kaggle_benchmark_run_dispatch"
        or value["journalVersion"] != 2
        or value["state"] != "reconciled"
        or value["failure"] is not None
        or value["responseFailure"] is not None
    ):
        raise KaggleQueueBreaker("queue dispatch journal is not reconciled")
    expected_authorization = _decision_authorization(
        policy=policy,
        entry=entry,
        decision_path=decision_path,
        decision_bytes=decision_bytes,
        execution_commit=execution_commit,
    )
    if value["dispatchAuthorization"] != expected_authorization:
        raise KaggleQueueBreaker("queue dispatch authorization drifted")
    authority = policy.value["authority"]
    if value["target"] != {
        "model": entry["modelVersionSlug"],
        "owner": authority["taskOwner"],
        "task": authority["taskSlug"],
        "version": authority["taskVersion"],
    }:
        raise KaggleQueueBreaker("queue dispatch journal target drifted")
    remote = value["remotePreflight"]
    if not isinstance(remote, dict):
        raise KaggleQueueBreaker("queue dispatch preflight is invalid")
    decision_snapshot = decision["snapshot"]
    if (
        value["client"] != decision_snapshot["client"]
        or value["creationAuthority"]
        != decision_snapshot["creationAuthority"]
        or remote.get("task") != decision_snapshot["task"]
        or remote.get("model") != decision_snapshot["model"]
        or remote.get("runs") != decision_snapshot["runs"]
        or remote.get("quota") != decision_snapshot["quota"]
    ):
        raise KaggleQueueBreaker(
            "queue decision and scheduler preflight snapshot drifted"
        )
    model = remote.get("model")
    expected_model = {
        "allowModelProxy": entry["allowModelProxy"],
        "benchmarkModelId": entry["modelId"],
        "benchmarkModelVersionId": entry["modelVersionId"],
        "deprecatedAt": entry["deprecatedAt"],
        "isDefault": entry["isDefault"],
        "modelProxySlug": entry["modelProxySlug"],
        "parentPublished": entry["parentPublished"],
        "slug": entry["modelVersionSlug"],
        "versionPublished": entry["versionPublished"],
    }
    if not isinstance(model, dict) or any(
        model.get(key) != expected for key, expected in expected_model.items()
    ):
        raise KaggleQueueBreaker("queue dispatch catalog binding drifted")
    reconciliation = value["reconciliation"]
    if not isinstance(reconciliation, dict) or not isinstance(
        reconciliation.get("run"), dict
    ):
        raise KaggleQueueBreaker("queue dispatch run binding is invalid")
    run = reconciliation["run"]
    if run.get("model") != entry["modelVersionSlug"]:
        raise KaggleQueueBreaker("queue dispatch run model drifted")
    _positive_int(run.get("id"), role="queue dispatch run ID")
    _quota_map(remote.get("quota"), role="queue dispatch quota before")
    if data != _canonical_json_bytes(value):
        raise KaggleQueueBreaker("queue dispatch journal bytes drifted")
    return run


def _evidence_path(
    root: Path, entry: dict[str, Any], *, task: str, version: int, run_id: int
) -> Path:
    bundle = _policy_entry_paths(entry)["evidenceBundle"]
    name = f"{task}-v{version}-run-{run_id}-evidence.json"
    return _path_under(root, bundle) / name


def _verify_private_bundle_modes(evidence_path: Path) -> None:
    """Enforce the queue manifest's 0700 directory / 0600 member contract."""

    directory = evidence_path.parent
    try:
        directory_stat = os.stat(directory, follow_symlinks=False)
        members = list(os.scandir(directory))
    except OSError as exc:
        raise KaggleQueueBreaker(
            f"cannot inspect private capture bundle modes: {exc}"
        ) from exc
    if (
        not stat.S_ISDIR(directory_stat.st_mode)
        or directory_stat.st_uid != os.geteuid()
        or stat.S_IMODE(directory_stat.st_mode) != 0o700
    ):
        raise KaggleQueueBreaker(
            "capture bundle directory is not private mode 0700"
        )
    for member in members:
        try:
            member_stat = member.stat(follow_symlinks=False)
        except OSError as exc:
            raise KaggleQueueBreaker(
                f"cannot inspect capture bundle member mode: {exc}"
            ) from exc
        if (
            not stat.S_ISREG(member_stat.st_mode)
            or member_stat.st_nlink != 1
            or member_stat.st_uid != os.geteuid()
            or stat.S_IMODE(member_stat.st_mode) != 0o600
        ):
            raise KaggleQueueBreaker(
                "capture bundle members must be private 0600 single-link files"
            )


def _validate_bundle_for_entry(
    bundle: VerifiedCaptureBundle,
    *,
    policy: LoadedQueuePolicy,
    entry: dict[str, Any],
    journal_bytes: bytes,
    run_id: int,
) -> None:
    authority = policy.value["authority"]
    evidence = bundle.evidence
    payload = bundle.payload
    if bundle.dispatch_journal_bytes != journal_bytes:
        raise KaggleQueueBreaker(
            "capture bundle dispatch journal differs from the original"
        )
    if (
        evidence.get("assemblyEligible") is not True
        or evidence.get("leaderboardEligible") is not False
        or evidence.get("publicationEligible") is not False
        or payload.get("captureComplete") is not True
        or payload.get("canonicalReplayEligible") is not True
    ):
        raise KaggleQueueBreaker("queue capture failed the evidence eligibility gate")
    task = evidence.get("task")
    run = evidence.get("run")
    if not isinstance(task, dict) or not isinstance(run, dict):
        raise KaggleQueueBreaker("queue capture task/run binding is invalid")
    if (
        task.get("owner") != authority["taskOwner"]
        or task.get("slug") != authority["taskSlug"]
        or task.get("version") != authority["taskVersion"]
        or task.get("sourceKernelId") != authority["sourceKernelId"]
        or task.get("datasets") != authority["datasetRefs"]
        or run.get("id") != run_id
        or run.get("modelVersionSlug") != entry["modelVersionSlug"]
        or run.get("state") != _COMPLETED_RUN_STATE
    ):
        raise KaggleQueueBreaker("queue capture exact run binding drifted")


_BREAKER_PATH = PurePosixPath(".aleph-kaggle-v10-queue-breaker.json")


def _sentinel_value(
    *,
    policy: LoadedQueuePolicy,
    writer_id: str,
    control_identity: dict[str, Any],
    lock_identity: dict[str, Any],
    execution_commit: str,
    creation_relative: PurePosixPath,
    creation_bytes: bytes,
    created_at: str,
) -> dict[str, Any]:
    return {
        "artifactKind": "aleph_bench_kaggle_queue_control_root",
        "controlRoot": control_identity,
        "createdAt": created_at,
        "creationJournal": {
            "bytes": len(creation_bytes),
            "relativePath": str(creation_relative),
            "sha256": hashlib.sha256(creation_bytes).hexdigest(),
        },
        "executionCommit": execution_commit,
        "lockFile": lock_identity,
        "policyId": policy.value["policyId"],
        "policySha256": policy.sha256,
        "sentinelVersion": 1,
        "writerId": writer_id,
    }


def _load_or_create_sentinel(
    *,
    root: Path,
    policy: LoadedQueuePolicy,
    writer_id: str,
    control_identity: dict[str, Any],
    lock_identity: dict[str, Any],
    execution_commit: str,
    creation_relative: PurePosixPath,
    creation_bytes: bytes,
    now: datetime,
) -> dict[str, Any]:
    sentinel_relative = _relative_path(
        policy.value["evidenceLayout"]["controlRootSentinelRelativePath"],
        role="control-root sentinel path",
    )
    sentinel_path = _path_under(root, sentinel_relative)
    expected = _sentinel_value(
        policy=policy,
        writer_id=writer_id,
        control_identity=control_identity,
        lock_identity=lock_identity,
        execution_commit=execution_commit,
        creation_relative=creation_relative,
        creation_bytes=creation_bytes,
        created_at=_canonical_time(now),
    )
    if not sentinel_path.exists():
        _write_private_once(
            root,
            sentinel_relative,
            expected,
            expected_device=control_identity["device"],
            expected_inode=control_identity["inode"],
        )
        return expected
    existing, _data = _read_json_file(
        sentinel_path, role="queue control-root sentinel"
    )
    expected["createdAt"] = existing.get("createdAt")
    _time(expected["createdAt"], role="control-root sentinel creation time")
    if existing != expected:
        raise KaggleQueueBreaker("queue control-root sentinel drifted")
    return existing


def _prior_record(item: CompletedQueueEntry) -> dict[str, Any]:
    return {
        "completion": _hash_record(item.completion_bytes),
        "decision": _hash_record(item.decision_bytes),
        "evidence": {
            **_hash_record(item.bundle.evidence_bytes),
            "id": item.bundle.evidence["id"],
        },
        "journal": _hash_record(item.journal_bytes),
        "modelVersionSlug": item.entry["modelVersionSlug"],
        "order": item.entry["order"],
        "runId": item.journal["reconciliation"]["run"]["id"],
        "terminalQuota": _hash_record(item.terminal_bytes),
    }


def _planned_paths(
    *,
    root: Path,
    entry: dict[str, Any],
    creation_path: Path,
    creation_authority: VerifiedCreationAuthority,
    authority: dict[str, Any],
) -> dict[str, str]:
    paths = _policy_entry_paths(entry)
    claim_path = _dispatch_claim_path(
        creation_journal_path=creation_path,
        creation_authority=creation_authority,
        owner=authority["taskOwner"],
        task=authority["taskSlug"],
        version=authority["taskVersion"],
        model=entry["modelVersionSlug"],
    )
    try:
        claim_relative = claim_path.relative_to(root)
    except ValueError:
        raise KaggleQueueError("dispatch claim escaped the control root") from None
    return {
        "bundleRelativePath": str(paths["evidenceBundle"]),
        "claimRelativePath": claim_relative.as_posix(),
        "completionRelativePath": str(paths["completionReceipt"]),
        "journalRelativePath": str(paths["dispatchJournal"]),
    }


def _execution_record(
    *, policy: LoadedQueuePolicy, execution: dict[str, str]
) -> dict[str, str]:
    return {
        "captureSourceAuthorityCommit": policy.value["authority"][
            "captureSourceAuthorityCommit"
        ],
        "commit": execution["commit"],
        "repositoryRootSha256": hashlib.sha256(
            execution["repositoryRoot"].encode("utf-8")
        ).hexdigest(),
    }


def _validate_snapshot(
    snapshot: dict[str, Any],
    *,
    policy: LoadedQueuePolicy,
    entry: dict[str, Any],
    completed: Sequence[CompletedQueueEntry],
) -> dict[str, dict[str, Any]]:
    _exact_fields(
        snapshot,
        {"client", "creationAuthority", "model", "quota", "runs", "source", "task"},
        role="queue pre-dispatch snapshot",
    )
    authority = policy.value["authority"]
    source = snapshot["source"]
    if (
        not isinstance(source, dict)
        or source.get("sha256") != authority["captureSourceSha256"]
        or source.get("notebookSha256") != authority["notebookSha256"]
    ):
        raise KaggleQueueBreaker("capture source identity drifted")
    task = snapshot["task"]
    if (
        not isinstance(task, dict)
        or task.get("owner") != authority["taskOwner"]
        or task.get("task") != authority["taskSlug"]
        or task.get("version") != authority["taskVersion"]
        or task.get("sourceKernelId") != authority["sourceKernelId"]
        or task.get("datasets") != authority["datasetRefs"]
    ):
        raise KaggleQueueBreaker("exact Kaggle Task identity drifted")
    creation = snapshot["creationAuthority"]
    if (
        not isinstance(creation, dict)
        or creation.get("canonicalSha256")
        != authority["creationJournalSha256"]
    ):
        raise KaggleQueueBreaker("creation authority binding drifted")
    model = snapshot["model"]
    expected_model = {
        "allowModelProxy": entry["allowModelProxy"],
        "benchmarkModelId": entry["modelId"],
        "benchmarkModelVersionId": entry["modelVersionId"],
        "deprecatedAt": entry["deprecatedAt"],
        "isDefault": entry["isDefault"],
        "modelProxySlug": entry["modelProxySlug"],
        "parentPublished": entry["parentPublished"],
        "slug": entry["modelVersionSlug"],
        "versionPublished": entry["versionPublished"],
    }
    if not isinstance(model, dict):
        raise KaggleQueueBreaker("Kaggle model catalog record is invalid")
    for key, expected in expected_model.items():
        actual = model.get(key)
        if isinstance(expected, bool):
            if actual is not expected:
                raise KaggleQueueBreaker(f"Kaggle model catalog {key} drifted")
        elif actual != expected:
            raise KaggleQueueBreaker(f"Kaggle model catalog {key} drifted")

    runs = snapshot["runs"]
    if not isinstance(runs, list):
        raise KaggleQueueBreaker("exact Task run set is invalid")
    expected_runs = [
        {
            "id": item["runId"],
            "model": item["modelVersionSlug"],
            "state": item["state"],
        }
        for item in authority["expectedInitialRuns"]
    ]
    expected_runs.extend(
        {
            "id": item.journal["reconciliation"]["run"]["id"],
            "model": item.entry["modelVersionSlug"],
            "state": _COMPLETED_RUN_STATE,
        }
        for item in completed
    )
    observed = [
        {"id": item.get("id"), "model": item.get("model"), "state": item.get("state")}
        for item in runs
        if isinstance(item, dict)
    ]
    if observed != expected_runs:
        raise KaggleQueueBreaker("exact Task run set drifted")
    return _quota_map(snapshot["quota"], role="fresh pre-dispatch quota")


def _terminal_quota_value(
    *,
    observed_at: str,
    quota: list[dict[str, Any]],
    policy: LoadedQueuePolicy,
    entry: dict[str, Any],
    decision: dict[str, Any],
    decision_bytes: bytes,
    journal: dict[str, Any],
    journal_bytes: bytes,
    bundle: VerifiedCaptureBundle,
    writer_id: str,
    execution_commit: str,
) -> dict[str, Any]:
    terminal_observed_at = _time(
        observed_at, role="terminal quota observation time"
    )
    decision_observed_at = _time(
        decision["createdAt"], role="dispatch decision time"
    )
    journal_updated_at = _time(
        journal["updatedAt"], role="dispatch journal update time"
    )
    if terminal_observed_at < max(decision_observed_at, journal_updated_at):
        raise KaggleQueueBreaker(
            "terminal quota observation predates its dispatch evidence"
        )
    before = _quota_map(
        decision["snapshot"]["quota"], role="dispatch-decision quota"
    )
    after = _quota_map(quota, role="terminal quota")
    comparisons: dict[str, str] = {}
    deltas: dict[str, Decimal] = {}
    for period in ("DAILY", "MONTHLY"):
        classification = _classify_refill(
            before[period],
            after[period],
            period=period,
            before_observed_at=decision_observed_at,
            after_observed_at=terminal_observed_at,
        )
        if classification != "same_window_jitter_tolerated":
            raise KaggleQueueBreaker(
                "terminal quota crossed a refill boundary; exact run cost is ambiguous"
            )
        comparisons[period] = classification
        deltas[period] = _quota_decimal(
            after[period], "usedUsd"
        ) - _quota_decimal(before[period], "usedUsd")
    conservative = max(deltas.values())
    breaker = _decimal(
        entry["postRunBreakerUsd"], role="post-run breaker", positive=True
    )
    if conservative >= breaker:
        raise KaggleQueueBreaker(
            "terminal quota cost upper bound reached the entry breaker"
        )
    run_id = journal["reconciliation"]["run"]["id"]
    return {
        "artifactKind": "aleph_bench_kaggle_queue_terminal_quota",
        "bindings": {
            "decision": _hash_record(decision_bytes),
            "evidence": {
                **_hash_record(bundle.evidence_bytes),
                "id": bundle.evidence["id"],
            },
            "journal": _hash_record(journal_bytes),
        },
        "costUpperBound": {
            "breakerUsd": entry["postRunBreakerUsd"],
            "conservativeUsd": format(conservative, "f"),
            "dailyDeltaUsd": format(deltas["DAILY"], "f"),
            "monthlyDeltaUsd": format(deltas["MONTHLY"], "f"),
            "strictlyBelowBreaker": True,
        },
        "executionCommit": execution_commit,
        "fixedEligibility": policy.value["fixedEligibility"],
        "observedAt": observed_at,
        "policyId": policy.value["policyId"],
        "policySha256": policy.sha256,
        "quota": quota,
        "refillComparison": comparisons,
        "target": {
            "modelVersionSlug": entry["modelVersionSlug"],
            "order": entry["order"],
            "runId": run_id,
        },
        "terminalQuotaVersion": 1,
        "writerId": writer_id,
    }


def _completion_value(
    *,
    finalized_at: str,
    policy: LoadedQueuePolicy,
    entry: dict[str, Any],
    decision_bytes: bytes,
    journal: dict[str, Any],
    journal_bytes: bytes,
    bundle: VerifiedCaptureBundle,
    terminal_bytes: bytes,
    writer_id: str,
    execution_commit: str,
) -> dict[str, Any]:
    _time(finalized_at, role="queue completion time")
    return {
        "artifactKind": "aleph_bench_kaggle_queue_entry_completion",
        "bindings": {
            "decision": _hash_record(decision_bytes),
            "evidence": {
                **_hash_record(bundle.evidence_bytes),
                "id": bundle.evidence["id"],
            },
            "journal": _hash_record(journal_bytes),
            "terminalQuota": _hash_record(terminal_bytes),
        },
        "completionVersion": 1,
        "executionCommit": execution_commit,
        "finalizedAt": finalized_at,
        "fixedEligibility": policy.value["fixedEligibility"],
        "outcome": "healthy_capture_evidence_not_a_score",
        "policyId": policy.value["policyId"],
        "policySha256": policy.sha256,
        "target": {
            "modelVersionSlug": entry["modelVersionSlug"],
            "order": entry["order"],
            "runId": journal["reconciliation"]["run"]["id"],
        },
        "writerId": writer_id,
    }


def _load_or_finalize_entry(
    *,
    root: Path,
    policy: LoadedQueuePolicy,
    entry: dict[str, Any],
    completed_before: Sequence[CompletedQueueEntry],
    writer_id: str,
    control_identity: dict[str, Any],
    execution: dict[str, str],
    creation_path: Path,
    creation_authority: VerifiedCreationAuthority,
    clock: Callable[[], datetime],
    quota_reader: Callable[[], list[dict[str, Any]]],
) -> CompletedQueueEntry:
    paths = _policy_entry_paths(entry)
    decision_path = _path_under(root, paths["decisionReceipt"])
    journal_path = _path_under(root, paths["dispatchJournal"])
    decision, decision_bytes = _read_json_file(
        decision_path, role=f"queue entry {entry['order']} decision"
    )
    _validate_decision(
        decision,
        data=decision_bytes,
        policy=policy,
        entry=entry,
        writer_id=writer_id,
        control_identity=control_identity,
        expected_execution=execution,
    )
    if decision["priorEntries"] != [
        _prior_record(item) for item in completed_before
    ]:
        raise KaggleQueueBreaker("queue decision prior-entry binding drifted")
    quota = _validate_snapshot(
        decision["snapshot"],
        policy=policy,
        entry=entry,
        completed=completed_before,
    )
    expected_planned = _planned_paths(
        root=root,
        entry=entry,
        creation_path=creation_path,
        creation_authority=creation_authority,
        authority=policy.value["authority"],
    )
    if decision["planned"] != expected_planned:
        raise KaggleQueueBreaker("queue decision planned paths drifted")
    decision_time = _time(decision["createdAt"], role="queue decision time")
    expected_budget = _budget_record(
        policy=policy,
        entry=entry,
        completed=completed_before,
        quota=quota,
        now=decision_time,
    )
    if decision["budget"] != expected_budget:
        raise KaggleQueueBreaker("queue decision budget binding drifted")
    journal, journal_bytes = _read_json_file(
        journal_path, role=f"queue entry {entry['order']} dispatch journal"
    )
    run = _validate_journal_for_entry(
        journal,
        data=journal_bytes,
        policy=policy,
        entry=entry,
        decision_path=paths["decisionReceipt"],
        decision_bytes=decision_bytes,
        decision=decision,
        execution_commit=execution["commit"],
    )
    evidence_path = _evidence_path(
        root,
        entry,
        task=policy.value["authority"]["taskSlug"],
        version=policy.value["authority"]["taskVersion"],
        run_id=run["id"],
    )
    _verify_private_bundle_modes(evidence_path)
    try:
        bundle = load_verified_capture_bundle(evidence_path)
    except KaggleCaptureEvidenceError as exc:
        raise KaggleQueueBreaker(
            f"queue capture bundle failed closed-world verification: {exc}"
        ) from exc
    _validate_bundle_for_entry(
        bundle,
        policy=policy,
        entry=entry,
        journal_bytes=journal_bytes,
        run_id=run["id"],
    )

    terminal_path = _path_under(root, paths["terminalQuotaReceipt"])
    if terminal_path.exists():
        terminal, terminal_bytes = _read_json_file(
            terminal_path, role=f"queue entry {entry['order']} terminal quota"
        )
        expected_terminal = _terminal_quota_value(
            observed_at=terminal.get("observedAt"),
            quota=terminal.get("quota"),
            policy=policy,
            entry=entry,
            decision=decision,
            decision_bytes=decision_bytes,
            journal=journal,
            journal_bytes=journal_bytes,
            bundle=bundle,
            writer_id=writer_id,
            execution_commit=execution["commit"],
        )
        if terminal != expected_terminal:
            raise KaggleQueueBreaker("terminal quota receipt drifted")
        terminal_time = _time(
            terminal["observedAt"], role="terminal quota observation time"
        )
        if terminal_time < decision_time:
            raise KaggleQueueBreaker(
                "terminal quota observation predates its dispatch decision"
            )
    else:
        try:
            quota = quota_reader()
        except KaggleReadUnavailable as exc:
            raise KaggleQueueHeld(
                "terminal quota read is temporarily unavailable"
            ) from exc
        except KaggleRunOnceError as exc:
            raise KaggleQueueBreaker(
                f"terminal quota integrity validation failed: {exc}"
            ) from exc
        except Exception as exc:
            raise KaggleQueueBreaker(
                f"terminal quota reader failed unexpectedly: {type(exc).__name__}"
            ) from exc
        terminal_time = _sample_clock(
            clock,
            role="terminal quota observation clock",
            not_before=decision_time,
        )
        terminal = _terminal_quota_value(
            observed_at=_canonical_time(terminal_time),
            quota=quota,
            policy=policy,
            entry=entry,
            decision=decision,
            decision_bytes=decision_bytes,
            journal=journal,
            journal_bytes=journal_bytes,
            bundle=bundle,
            writer_id=writer_id,
            execution_commit=execution["commit"],
        )
        terminal_bytes = _write_private_once(
            root,
            paths["terminalQuotaReceipt"],
            terminal,
            expected_device=control_identity["device"],
            expected_inode=control_identity["inode"],
        )

    completion_path = _path_under(root, paths["completionReceipt"])
    if completion_path.exists():
        completion, completion_bytes = _read_json_file(
            completion_path, role=f"queue entry {entry['order']} completion"
        )
        expected_completion = _completion_value(
            finalized_at=completion.get("finalizedAt"),
            policy=policy,
            entry=entry,
            decision_bytes=decision_bytes,
            journal=journal,
            journal_bytes=journal_bytes,
            bundle=bundle,
            terminal_bytes=terminal_bytes,
            writer_id=writer_id,
            execution_commit=execution["commit"],
        )
        if completion != expected_completion:
            raise KaggleQueueBreaker("queue completion receipt drifted")
        if _time(
            completion["finalizedAt"], role="queue completion time"
        ) < terminal_time:
            raise KaggleQueueBreaker(
                "queue completion predates its terminal quota observation"
            )
    else:
        completion_time = _sample_clock(
            clock,
            role="queue completion clock",
            not_before=terminal_time,
        )
        completion = _completion_value(
            finalized_at=_canonical_time(completion_time),
            policy=policy,
            entry=entry,
            decision_bytes=decision_bytes,
            journal=journal,
            journal_bytes=journal_bytes,
            bundle=bundle,
            terminal_bytes=terminal_bytes,
            writer_id=writer_id,
            execution_commit=execution["commit"],
        )
        completion_bytes = _write_private_once(
            root,
            paths["completionReceipt"],
            completion,
            expected_device=control_identity["device"],
            expected_inode=control_identity["inode"],
        )
    return CompletedQueueEntry(
        entry=entry,
        decision=decision,
        decision_bytes=decision_bytes,
        journal=journal,
        journal_bytes=journal_bytes,
        bundle=bundle,
        terminal=terminal,
        terminal_bytes=terminal_bytes,
        completion=completion,
        completion_bytes=completion_bytes,
    )


def _budget_record(
    *,
    policy: LoadedQueuePolicy,
    entry: dict[str, Any],
    completed: Sequence[CompletedQueueEntry],
    quota: dict[str, dict[str, Any]],
    now: datetime,
) -> dict[str, Any]:
    dispatch_policy = policy.value["dispatchPolicy"]
    _validate_fresh_quota_observation(quota, observed_at=now)
    window = timedelta(seconds=dispatch_policy["rollingWindowSeconds"])
    decision_times: list[tuple[CompletedQueueEntry, datetime]] = []
    for item in completed:
        created = _time(
            item.decision["createdAt"], role="prior queue decision time"
        )
        if created > now:
            raise KaggleQueueBreaker("local clock moved behind a prior decision")
        decision_times.append((item, created))
    recent = [item for item, created in decision_times if created > now - window]
    if len(recent) >= dispatch_policy["maxDispatchesPerRollingWindow"]:
        earliest = min(
            created for _item, created in decision_times if created > now - window
        )
        raise KaggleQueueHeld(
            "rolling 24-hour queue dispatch limit is reached",
            retry_after=_canonical_time(earliest + window),
        )
    if completed:
        last_time = decision_times[-1][1]
        minimum = timedelta(
            seconds=entry["minimumSecondsSincePreviousDispatchExclusive"]
        )
        if now - last_time <= minimum:
            raise KaggleQueueHeld(
                "selected queue entry requires more separation from the prior dispatch",
                retry_after=_canonical_time(
                    last_time + minimum + _RETRY_EPSILON
                ),
            )
        latest_quota = _quota_map(
            completed[-1].terminal["quota"], role="latest terminal quota"
        )
        latest_quota_time = _time(
            completed[-1].terminal["observedAt"],
            role="latest terminal quota observation time",
        )
        daily_class = _classify_refill(
            latest_quota["DAILY"],
            quota["DAILY"],
            period="DAILY",
            before_observed_at=latest_quota_time,
            after_observed_at=now,
        )
        _classify_refill(
            latest_quota["MONTHLY"],
            quota["MONTHLY"],
            period="MONTHLY",
            before_observed_at=latest_quota_time,
            after_observed_at=now,
        )
        if entry["requiresProvenDailyAllowanceUsageReset"]:
            if (
                daily_class != "advanced_window"
                or _quota_decimal(quota["DAILY"], "usedUsd")
                >= _quota_decimal(latest_quota["DAILY"], "usedUsd")
            ):
                raise KaggleQueueHeld(
                    "Claude tail requires a proved fresh DAILY allowance usage reset"
                )
    if entry["mustBeOnlyQueueDispatchInRollingWindow"] and recent:
        raise KaggleQueueHeld(
            "selected queue entry must be the only dispatch in its rolling window"
        )

    selected_cost = _decimal(
        entry["declaredWorstCaseCostUsd"],
        role="selected declared worst-case cost",
        positive=True,
    )
    declared = selected_cost + sum(
        (
            _decimal(
                item.entry["declaredWorstCaseCostUsd"],
                role="prior declared worst-case cost",
                positive=True,
            )
            for item in recent
        ),
        Decimal("0"),
    )
    observed_increase = Decimal("0")
    if recent:
        earliest_quota = _quota_map(
            recent[0].decision["snapshot"]["quota"],
            role="earliest rolling decision quota",
        )
        classification = _classify_refill(
            earliest_quota["DAILY"],
            quota["DAILY"],
            period="DAILY",
            before_observed_at=_time(
                recent[0].decision["createdAt"],
                role="earliest rolling decision time",
            ),
            after_observed_at=now,
        )
        if classification == "same_window_jitter_tolerated":
            observed_increase = _quota_decimal(
                quota["DAILY"], "usedUsd"
            ) - _quota_decimal(earliest_quota["DAILY"], "usedUsd")
    conservative = max(declared, observed_increase + selected_cost)
    spend_cap = _decimal(
        dispatch_policy["dailyQueueSpendCapUsd"],
        role="rolling queue spend cap",
        positive=True,
    )
    if conservative >= spend_cap:
        raise KaggleQueueHeld("rolling queue spend cap is reached")

    daily_allowed = _quota_decimal(quota["DAILY"], "allowedUsd")
    monthly_allowed = _quota_decimal(quota["MONTHLY"], "allowedUsd")
    daily_reserve = max(
        _decimal(
            dispatch_policy["dailyReserveMinimumUsd"],
            role="daily reserve minimum",
        ),
        daily_allowed
        * _fraction(
            dispatch_policy["dailyReserveFraction"],
            role="daily reserve fraction",
        ),
    )
    monthly_reserve = monthly_allowed * _fraction(
        dispatch_policy["monthlyReserveFraction"],
        role="monthly reserve fraction",
    )
    if (
        _quota_decimal(quota["DAILY"], "remainingUsd") - selected_cost
        < daily_reserve
        or _quota_decimal(quota["MONTHLY"], "remainingUsd") - selected_cost
        < monthly_reserve
    ):
        raise KaggleQueueHeld("quota reserve would be violated")
    return {
        "apiObservedIncreaseUsd": format(observed_increase, "f"),
        "conservativeProjectedSpendUsd": format(conservative, "f"),
        "dailyReserveUsd": format(daily_reserve, "f"),
        "declaredRollingSpendUsd": format(declared, "f"),
        "declaredWorstCaseCostUsd": entry["declaredWorstCaseCostUsd"],
        "monthlyReserveUsd": format(monthly_reserve, "f"),
        "rollingDispatchCount": len(recent) + 1,
        "rollingWindowHours": 24,
    }


def _decision_value(
    *,
    policy: LoadedQueuePolicy,
    entry: dict[str, Any],
    completed: Sequence[CompletedQueueEntry],
    snapshot: dict[str, Any],
    budget: dict[str, Any],
    writer_id: str,
    control_identity: dict[str, Any],
    execution: dict[str, str],
    planned: dict[str, str],
    now: datetime,
) -> dict[str, Any]:
    return {
        "artifactKind": "aleph_bench_kaggle_queue_dispatch_decision",
        "budget": budget,
        "controlRoot": control_identity,
        "createdAt": _canonical_time(now),
        "decisionVersion": 1,
        "execution": _execution_record(policy=policy, execution=execution),
        "fixedEligibility": policy.value["fixedEligibility"],
        "planned": planned,
        "policy": {
            "bytes": len(policy.raw_bytes),
            "id": policy.value["policyId"],
            "relativePath": "bench/config/kaggle-capture-queue-v1.json",
            "sha256": policy.sha256,
        },
        "priorEntries": [_prior_record(item) for item in completed],
        "snapshot": snapshot,
        "target": {
            "modelVersionSlug": entry["modelVersionSlug"],
            "order": entry["order"],
        },
        "writerId": writer_id,
    }


def _entry_artifact_exists(root: Path, entry: dict[str, Any]) -> bool:
    paths = _policy_entry_paths(entry)
    artifact_root = _path_under(root, paths["decisionReceipt"].parent)
    return artifact_root.exists() or any(
        _path_under(root, path).exists() for path in paths.values()
    )


def _validate_pending_entry(
    *,
    root: Path,
    policy: LoadedQueuePolicy,
    entry: dict[str, Any],
    completed_before: Sequence[CompletedQueueEntry],
    writer_id: str,
    control_identity: dict[str, Any],
    execution: dict[str, str],
    creation_path: Path,
    creation_authority: VerifiedCreationAuthority,
) -> dict[str, Any]:
    paths = _policy_entry_paths(entry)
    decision, decision_bytes = _read_json_file(
        _path_under(root, paths["decisionReceipt"]),
        role=f"queue entry {entry['order']} pending decision",
    )
    _validate_decision(
        decision,
        data=decision_bytes,
        policy=policy,
        entry=entry,
        writer_id=writer_id,
        control_identity=control_identity,
        expected_execution=execution,
    )
    if decision["priorEntries"] != [
        _prior_record(item) for item in completed_before
    ]:
        raise KaggleQueueBreaker("pending decision prior-entry binding drifted")
    quota = _validate_snapshot(
        decision["snapshot"],
        policy=policy,
        entry=entry,
        completed=completed_before,
    )
    expected_planned = _planned_paths(
        root=root,
        entry=entry,
        creation_path=creation_path,
        creation_authority=creation_authority,
        authority=policy.value["authority"],
    )
    if decision["planned"] != expected_planned:
        raise KaggleQueueBreaker("pending decision planned paths drifted")
    if decision["budget"] != _budget_record(
        policy=policy,
        entry=entry,
        completed=completed_before,
        quota=quota,
        now=_time(decision["createdAt"], role="pending decision time"),
    ):
        raise KaggleQueueBreaker("pending decision budget binding drifted")
    journal, journal_bytes = _read_json_file(
        _path_under(root, paths["dispatchJournal"]),
        role=f"queue entry {entry['order']} pending journal",
    )
    return _validate_journal_for_entry(
        journal,
        data=journal_bytes,
        policy=policy,
        entry=entry,
        decision_path=paths["decisionReceipt"],
        decision_bytes=decision_bytes,
        decision=decision,
        execution_commit=execution["commit"],
    )


def _validate_live_run_set(
    runs: Any,
    *,
    policy: LoadedQueuePolicy,
    completed: Sequence[CompletedQueueEntry],
    pending: dict[str, Any] | None,
) -> dict[str, Any] | None:
    """Validate the complete live v10 run set against durable local state."""

    if not isinstance(runs, list):
        raise KaggleQueueBreaker("live exact Task run set is invalid")
    normalized: list[dict[str, Any]] = []
    for raw in runs:
        record = _exact_fields(
            raw,
            {"endTime", "errorMessage", "id", "model", "startTime", "state"},
            role="live exact Task run",
        )
        _positive_int(record["id"], role="live exact Task run ID")
        _string(record["model"], role="live exact Task run model", maximum=200)
        state = _string(
            record["state"], role="live exact Task run state", maximum=100
        )
        if state not in _ACTIVE_RUN_STATES | _TERMINAL_RUN_STATES:
            raise KaggleQueueBreaker("live exact Task run has an unknown state")
        for field in ("startTime", "endTime"):
            if record[field] is not None:
                _time(record[field], role=f"live exact Task run {field}")
        if record["errorMessage"] is not None:
            _string(
                record["errorMessage"],
                role="live exact Task run error",
                maximum=20_000,
            )
        normalized.append(dict(record))
    normalized.sort(key=lambda item: item["id"])
    if len({item["id"] for item in normalized}) != len(normalized):
        raise KaggleQueueBreaker("live exact Task run set has duplicate IDs")

    authority = policy.value["authority"]
    expected = [
        {
            "id": item["runId"],
            "model": item["modelVersionSlug"],
            "state": item["state"],
        }
        for item in authority["expectedInitialRuns"]
    ]
    expected.extend(
        {
            "id": item.journal["reconciliation"]["run"]["id"],
            "model": item.entry["modelVersionSlug"],
            "state": _COMPLETED_RUN_STATE,
        }
        for item in completed
    )
    if pending is not None:
        expected.append(
            {
                "id": pending["id"],
                "model": pending["model"],
                "state": None,
            }
        )
    expected.sort(key=lambda item: item["id"])
    observed_identity = [
        {"id": item["id"], "model": item["model"]} for item in normalized
    ]
    expected_identity = [
        {"id": item["id"], "model": item["model"]} for item in expected
    ]
    if observed_identity != expected_identity:
        raise KaggleQueueBreaker("live exact Task run set drifted")
    for index, item in enumerate(expected):
        if item["state"] is not None and normalized[index]["state"] != item["state"]:
            raise KaggleQueueBreaker("live exact Task terminal state drifted")
    if pending is None:
        return None
    return next(item for item in normalized if item["id"] == pending["id"])


def _scan_entries(
    *,
    root: Path,
    policy: LoadedQueuePolicy,
    writer_id: str,
    control_identity: dict[str, Any],
    execution: dict[str, str],
    creation_path: Path,
    creation_authority: VerifiedCreationAuthority,
    clock: Callable[[], datetime],
    live_runs: list[dict[str, Any]],
    quota_reader: Callable[[], list[dict[str, Any]]],
) -> tuple[list[CompletedQueueEntry], dict[str, Any] | None, str | None]:
    completed: list[CompletedQueueEntry] = []
    queue = policy.value["queue"]
    for index, entry in enumerate(queue):
        paths = _policy_entry_paths(entry)
        decision_exists = _path_under(root, paths["decisionReceipt"]).exists()
        journal_exists = _path_under(root, paths["dispatchJournal"]).exists()
        bundle_exists = _path_under(root, paths["evidenceBundle"]).exists()
        terminal_exists = _path_under(
            root, paths["terminalQuotaReceipt"]
        ).exists()
        completion_exists = _path_under(
            root, paths["completionReceipt"]
        ).exists()
        flags = (
            decision_exists,
            journal_exists,
            bundle_exists,
            terminal_exists,
            completion_exists,
        )
        if not any(flags):
            if _entry_artifact_exists(root, entry):
                raise KaggleQueueBreaker(
                    "selected queue artifact directory already exists"
                )
            if any(_entry_artifact_exists(root, later) for later in queue[index + 1 :]):
                raise KaggleQueueBreaker("a later queue entry has out-of-order artifacts")
            _validate_live_run_set(
                live_runs, policy=policy, completed=completed, pending=None
            )
            return completed, entry, None
        if not decision_exists or not journal_exists:
            raise KaggleQueueBreaker(
                "queue entry has an orphan decision or dispatch artifact"
            )
        pending_run = _validate_pending_entry(
            root=root,
            policy=policy,
            entry=entry,
            completed_before=completed,
            writer_id=writer_id,
            control_identity=control_identity,
            execution=execution,
            creation_path=creation_path,
            creation_authority=creation_authority,
        )
        evidence_path = _evidence_path(
            root,
            entry,
            task=policy.value["authority"]["taskSlug"],
            version=policy.value["authority"]["taskVersion"],
            run_id=pending_run["id"],
        )
        evidence_exists = evidence_path.is_file()
        live_pending = _validate_live_run_set(
            live_runs,
            policy=policy,
            completed=completed,
            pending=pending_run,
        )
        if live_pending is None:
            raise KaggleQueueBreaker("pending queue run disappeared")
        if not evidence_exists:
            if terminal_exists or completion_exists:
                raise KaggleQueueBreaker(
                    "queue entry has finalization without a capture bundle"
                )
            if any(_entry_artifact_exists(root, later) for later in queue[index + 1 :]):
                raise KaggleQueueBreaker("a later queue entry bypassed evidence finalization")
            if live_pending["state"] == "BENCHMARK_TASK_RUN_STATE_ERRORED":
                raise KaggleQueueBreaker(
                    "journal-bound Kaggle run reached provider error"
                )
            if live_pending["state"] == _COMPLETED_RUN_STATE:
                raise KaggleQueueBreaker(
                    "platform run completed without complete Aleph evidence"
                )
            return completed, None, "awaiting_terminal_evidence"
        if live_pending["state"] != _COMPLETED_RUN_STATE:
            raise KaggleQueueBreaker(
                "Aleph evidence exists before the live run is completed"
            )
        if completion_exists and not terminal_exists:
            raise KaggleQueueBreaker(
                "queue completion exists without its terminal-quota receipt"
            )
        item = _load_or_finalize_entry(
            root=root,
            policy=policy,
            entry=entry,
            completed_before=completed,
            writer_id=writer_id,
            control_identity=control_identity,
            execution=execution,
            creation_path=creation_path,
            creation_authority=creation_authority,
            clock=clock,
            quota_reader=quota_reader,
        )
        completed.append(item)
    _validate_live_run_set(
        live_runs, policy=policy, completed=completed, pending=None
    )
    return completed, None, "exhausted"


def _recheck_completed_entries(
    root: Path, completed: Sequence[CompletedQueueEntry]
) -> None:
    for item in completed:
        paths = _policy_entry_paths(item.entry)
        for role, path, expected in (
            (
                "decision",
                _path_under(root, paths["decisionReceipt"]),
                item.decision_bytes,
            ),
            (
                "dispatch journal",
                _path_under(root, paths["dispatchJournal"]),
                item.journal_bytes,
            ),
            (
                "terminal quota",
                _path_under(root, paths["terminalQuotaReceipt"]),
                item.terminal_bytes,
            ),
            (
                "completion",
                _path_under(root, paths["completionReceipt"]),
                item.completion_bytes,
            ),
        ):
            observed = _read_stable_regular(
                path, maximum=MAX_QUEUE_RECEIPT_BYTES, role=f"prior {role}"
            )
            if observed != expected:
                raise KaggleQueueBreaker(f"prior queue {role} changed")
        _verify_private_bundle_modes(item.bundle.evidence_path)
        try:
            reloaded = load_verified_capture_bundle(item.bundle.evidence_path)
        except KaggleCaptureEvidenceError as exc:
            raise KaggleQueueBreaker(
                "prior closed-world evidence bundle failed verification: "
                f"{exc}"
            ) from exc
        if (
            reloaded.evidence_bytes != item.bundle.evidence_bytes
            or reloaded.payload_bytes != item.bundle.payload_bytes
            or reloaded.archive_bytes != item.bundle.archive_bytes
            or reloaded.source_bytes != item.bundle.source_bytes
            or reloaded.dispatch_journal_bytes != item.bundle.dispatch_journal_bytes
        ):
            raise KaggleQueueBreaker("prior closed-world evidence bundle changed")


def _breaker_value(
    *,
    policy: LoadedQueuePolicy,
    writer_id: str,
    execution_commit: str,
    reason: str,
    now: datetime,
) -> dict[str, Any]:
    return {
        "artifactKind": "aleph_bench_kaggle_queue_breaker",
        "breakerVersion": 1,
        "createdAt": _canonical_time(now),
        "executionCommit": execution_commit,
        "failure": {
            "message": _string(reason, role="queue breaker reason", maximum=4_000),
            "type": "PermanentPolicyBreaker",
        },
        "fixedEligibility": policy.value["fixedEligibility"],
        "policyId": policy.value["policyId"],
        "policySha256": policy.sha256,
        "writerId": writer_id,
    }


def _load_breaker(
    path: Path,
    *,
    policy: LoadedQueuePolicy,
    writer_id: str,
    execution_commit: str,
) -> tuple[dict[str, Any], bytes]:
    value, data = _read_json_file(path, role="queue breaker receipt")
    _exact_fields(
        value,
        {
            "artifactKind",
            "breakerVersion",
            "createdAt",
            "executionCommit",
            "failure",
            "fixedEligibility",
            "policyId",
            "policySha256",
            "writerId",
        },
        role="queue breaker receipt",
    )
    if (
        value["artifactKind"] != "aleph_bench_kaggle_queue_breaker"
        or value["breakerVersion"] != 1
        or value["executionCommit"] != execution_commit
        or value["fixedEligibility"] != policy.value["fixedEligibility"]
        or value["policyId"] != policy.value["policyId"]
        or value["policySha256"] != policy.sha256
        or value["writerId"] != writer_id
    ):
        raise KaggleQueueError("queue breaker receipt authority drifted")
    _time(value["createdAt"], role="queue breaker time")
    failure = _exact_fields(
        value["failure"], {"message", "type"}, role="queue breaker failure"
    )
    if failure["type"] != "PermanentPolicyBreaker":
        raise KaggleQueueError("queue breaker failure type drifted")
    _string(failure["message"], role="queue breaker reason", maximum=4_000)
    return value, data


def _persist_breaker(
    root: Path,
    *,
    expected_device: int,
    expected_inode: int,
    policy: LoadedQueuePolicy,
    writer_id: str,
    execution_commit: str,
    reason: str,
    now: datetime,
) -> dict[str, Any]:
    _pinned_control_root_identity(
        root,
        expected_device=expected_device,
        expected_inode=expected_inode,
    )
    path = _path_under(root, _BREAKER_PATH)
    if path.exists():
        return _load_breaker(
            path,
            policy=policy,
            writer_id=writer_id,
            execution_commit=execution_commit,
        )[0]
    value = _breaker_value(
        policy=policy,
        writer_id=writer_id,
        execution_commit=execution_commit,
        reason=reason,
        now=now,
    )
    try:
        _write_private_once(
            root,
            _BREAKER_PATH,
            value,
            expected_device=expected_device,
            expected_inode=expected_inode,
        )
    except KaggleControlRootDrift:
        raise
    except KaggleQueueError:
        if path.exists():
            return _load_breaker(
                path,
                policy=policy,
                writer_id=writer_id,
                execution_commit=execution_commit,
            )[0]
        raise
    return value


def _status(
    status: str,
    *,
    policy: LoadedQueuePolicy,
    reason: str,
    completed: int,
    retry_after: str | None = None,
    selected: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "artifactKind": "aleph_bench_kaggle_queue_status",
        "completedEntries": completed,
        "fixedEligibility": policy.value["fixedEligibility"],
        "policyId": policy.value["policyId"],
        "policySha256": policy.sha256,
        "reason": reason,
        "retryAfter": retry_after,
        "selected": (
            None
            if selected is None
            else {
                "modelVersionSlug": selected["modelVersionSlug"],
                "order": selected["order"],
            }
        ),
        "status": status,
    }


def _utc_datetime_now() -> datetime:
    return datetime.now(timezone.utc)


def _run_queue_once_locked(
    *,
    control_root: Path,
    expected_control_device: int,
    expected_control_inode: int,
    writer_id: str,
    expected_policy_sha256: str,
    expected_execution_commit: str,
    execution_root: Path,
    locked_control_identity: dict[str, Any],
    locked_control_fd: int,
    lock_identity: dict[str, Any],
    policy_path: Path = POLICY_PATH,
    now: Callable[[], datetime] = _utc_datetime_now,
    initial_instant: datetime,
    execution_verifier: Callable[..., dict[str, str]] = verify_execution_checkout,
    source_reader: Callable[[], dict[str, Any]] = current_capture_source_identity,
    run_set_reader: Callable[..., list[dict[str, Any]]] = fetch_benchmark_task_runs,
    quota_reader: Callable[[], list[dict[str, Any]]] = fetch_model_proxy_quota,
    dispatcher: Callable[..., dict[str, Any]] = run_once,
) -> dict[str, Any]:
    """Advance the finite v10 queue by at most one paid scheduling POST."""

    if not isinstance(writer_id, str) or not _WRITER_ID.fullmatch(writer_id):
        raise KaggleQueueError("writer ID must be one bounded lowercase identity")
    _verify_loaded_authority_paths(execution_root, policy_path=policy_path)
    policy = load_queue_policy(
        policy_path, expected_sha256=expected_policy_sha256
    )
    execution = execution_verifier(
        execution_root, expected_commit=expected_execution_commit
    )
    instant = initial_instant
    control_identity = _pinned_control_root_identity(
        control_root,
        expected_device=expected_control_device,
        expected_inode=expected_control_inode,
    )
    if control_identity != locked_control_identity:
        raise KaggleControlRootDrift(
            "locked control-root identity differs from the activation pin"
        )
    authority = policy.value["authority"]
    source = source_reader()
    if (
        source.get("sha256") != authority["captureSourceSha256"]
        or source.get("notebookSha256") != authority["notebookSha256"]
    ):
        raise KaggleQueueError("current capture source differs from queue authority")
    creation_relative = _relative_path(
        policy.value["evidenceLayout"]["creationJournalRelativePath"],
        role="creation journal path",
    )
    creation_path = _path_under(control_root, creation_relative)
    creation_bytes = _read_private_root_file(
        control_root,
        creation_relative,
        expected_device=expected_control_device,
        expected_inode=expected_control_inode,
        maximum=MAX_CREATION_JOURNAL_BYTES,
        role="creation authority journal",
    )
    if hashlib.sha256(creation_bytes).hexdigest() != authority[
        "creationJournalSha256"
    ]:
        raise KaggleQueueError("creation journal digest differs from queue authority")
    creation_authority = verify_creation_authority_bytes(
        creation_bytes,
        expected_owner=authority["taskOwner"],
        expected_task=authority["taskSlug"],
        expected_version=authority["taskVersion"],
        current_source=source,
    )
    expiry = _time(policy.value["expiresAt"], role="queue policy expiry")
    breaker_path = _path_under(control_root, _BREAKER_PATH)
    if breaker_path.exists():
        breaker, _data = _load_breaker(
            breaker_path,
            policy=policy,
            writer_id=writer_id,
            execution_commit=execution["commit"],
        )
        return _status(
            "breaker",
            policy=policy,
            reason=breaker["failure"]["message"],
            completed=0,
        )
    sentinel_relative = _relative_path(
        policy.value["evidenceLayout"]["controlRootSentinelRelativePath"],
        role="control-root sentinel path",
    )
    sentinel_exists = _path_under(control_root, sentinel_relative).exists()
    if instant < expiry or sentinel_exists:
        _load_or_create_sentinel(
            root=control_root,
            policy=policy,
            writer_id=writer_id,
            control_identity=control_identity,
            lock_identity=lock_identity,
            execution_commit=execution["commit"],
            creation_relative=creation_relative,
            creation_bytes=creation_bytes,
            now=instant,
        )
    elif any(
        _entry_artifact_exists(control_root, entry)
        for entry in policy.value["queue"]
    ):
        raise KaggleQueueBreaker(
            "queue artifacts exist without the control-root sentinel"
        )
    completed: list[CompletedQueueEntry] = []
    selected: dict[str, Any] | None = None
    try:
        try:
            live_runs = run_set_reader(
                owner=authority["taskOwner"],
                task=authority["taskSlug"],
                version=authority["taskVersion"],
            )
        except KaggleReadUnavailable as exc:
            raise KaggleQueueHeld(
                "live exact Task run read is temporarily unavailable"
            ) from exc
        except KaggleRunOnceError as exc:
            raise KaggleQueueBreaker(
                f"live exact Task run integrity validation failed: {exc}"
            ) from exc
        except Exception as exc:
            raise KaggleQueueBreaker(
                f"live exact Task run reader failed unexpectedly: {type(exc).__name__}"
            ) from exc
        completed, selected, local_state = _scan_entries(
            root=control_root,
            policy=policy,
            writer_id=writer_id,
            control_identity=control_identity,
            execution=execution,
            creation_path=creation_path,
            creation_authority=creation_authority,
            clock=now,
            live_runs=live_runs,
            quota_reader=quota_reader,
        )
        if local_state == "awaiting_terminal_evidence":
            return _status(
                "held",
                policy=policy,
                reason="the current queue run is awaiting terminal closed-world evidence",
                completed=len(completed),
            )
        if local_state == "exhausted":
            return _status(
                "exhausted",
                policy=policy,
                reason="all six queue entries are finalized",
                completed=len(completed),
            )
        if selected is None:
            raise KaggleQueueBreaker("queue state did not select one exact next entry")
        # Expiry forbids a new paid transition; it must not hide or prevent
        # reconciliation and finalization of a transition already made.
        if instant >= expiry:
            return _status(
                "expired",
                policy=policy,
                reason="queue policy expiry has been reached",
                completed=len(completed),
                selected=selected,
            )
        if selected["requiresPriorHealthyEntries"] != len(completed):
            raise KaggleQueueBreaker("queue entry prior-health gate drifted")
        paths = _policy_entry_paths(selected)
        planned = _planned_paths(
            root=control_root,
            entry=selected,
            creation_path=creation_path,
            creation_authority=creation_authority,
            authority=authority,
        )

        def guard(snapshot: dict[str, Any]) -> dict[str, Any]:
            guard_now = now()
            if not isinstance(guard_now, datetime) or guard_now.tzinfo is None:
                raise KaggleQueueBreaker("queue clock became invalid")
            guard_now = guard_now.astimezone(timezone.utc)
            if guard_now < instant:
                raise KaggleQueueBreaker("queue clock moved backwards")
            if guard_now >= expiry:
                raise KaggleQueueExpired(
                    "queue policy expired at the paid boundary"
                )
            load_queue_policy(
                policy_path, expected_sha256=expected_policy_sha256
            )
            _verify_loaded_authority_paths(
                execution_root, policy_path=policy_path
            )
            fresh_execution = execution_verifier(
                execution_root, expected_commit=expected_execution_commit
            )
            if fresh_execution != execution:
                raise KaggleQueueBreaker("execution checkout changed during preflight")
            if _pinned_control_root_identity(
                control_root,
                expected_device=expected_control_device,
                expected_inode=expected_control_inode,
            ) != locked_control_identity:
                raise KaggleControlRootDrift(
                    "control-root pathname changed during paid preflight"
                )
            _load_or_create_sentinel(
                root=control_root,
                policy=policy,
                writer_id=writer_id,
                control_identity=control_identity,
                lock_identity=lock_identity,
                execution_commit=execution["commit"],
                creation_relative=creation_relative,
                creation_bytes=creation_bytes,
                now=guard_now,
            )
            if _read_private_root_file(
                control_root,
                creation_relative,
                expected_device=expected_control_device,
                expected_inode=expected_control_inode,
                maximum=MAX_CREATION_JOURNAL_BYTES,
                role="creation authority journal",
            ) != creation_bytes:
                raise KaggleQueueBreaker("creation journal changed during preflight")
            _recheck_completed_entries(control_root, completed)
            if _entry_artifact_exists(control_root, selected):
                raise KaggleQueueHeld(
                    "another same-root controller claimed the selected entry"
                )
            quota = _validate_snapshot(
                snapshot,
                policy=policy,
                entry=selected,
                completed=completed,
            )
            budget = _budget_record(
                policy=policy,
                entry=selected,
                completed=completed,
                quota=quota,
                now=guard_now,
            )
            decision = _decision_value(
                policy=policy,
                entry=selected,
                completed=completed,
                snapshot=snapshot,
                budget=budget,
                writer_id=writer_id,
                control_identity=control_identity,
                execution=execution,
                planned=planned,
                now=guard_now,
            )
            try:
                decision_bytes = _write_private_once(
                    control_root,
                    paths["decisionReceipt"],
                    decision,
                    expected_device=expected_control_device,
                    expected_inode=expected_control_inode,
                )
            except KaggleQueueError:
                if _path_under(
                    control_root, paths["decisionReceipt"]
                ).exists():
                    raise KaggleQueueHeld(
                        "another same-root controller won the decision receipt"
                    ) from None
                raise
            _ensure_private_directory(
                control_root,
                paths["dispatchJournal"].parent,
                expected_device=expected_control_device,
                expected_inode=expected_control_inode,
            )
            return _decision_authorization(
                policy=policy,
                entry=selected,
                decision_path=paths["decisionReceipt"],
                decision_bytes=decision_bytes,
                execution_commit=execution["commit"],
            )

        journal = dispatcher(
            owner=authority["taskOwner"],
            task=authority["taskSlug"],
            version=authority["taskVersion"],
            model=selected["modelVersionSlug"],
            journal_path=_path_under(control_root, paths["dispatchJournal"]),
            creation_journal_path=creation_path,
            pre_dispatch_guard=guard,
            anchored_paths=AnchoredDispatchPaths(
                control_root_fd=locked_control_fd,
                control_root=control_root,
                expected_control_device=expected_control_device,
                expected_control_inode=expected_control_inode,
                creation_journal_relative_path=creation_relative,
                journal_relative_path=paths["dispatchJournal"],
            ),
        )
        if _pinned_control_root_identity(
            control_root,
            expected_device=expected_control_device,
            expected_inode=expected_control_inode,
        ) != locked_control_identity:
            raise KaggleControlRootDrift(
                "control-root pathname changed across the paid boundary"
            )
        decision, decision_bytes = _read_json_file(
            _path_under(control_root, paths["decisionReceipt"]),
            role="new queue decision",
        )
        journal_bytes = _read_stable_regular(
            _path_under(control_root, paths["dispatchJournal"]),
            maximum=MAX_QUEUE_RECEIPT_BYTES,
            role="new queue dispatch journal",
        )
        if journal_bytes != _canonical_json_bytes(journal):
            raise KaggleQueueBreaker("returned queue dispatch journal bytes drifted")
        _validate_journal_for_entry(
            journal,
            data=journal_bytes,
            policy=policy,
            entry=selected,
            decision_path=paths["decisionReceipt"],
            decision_bytes=decision_bytes,
            decision=decision,
            execution_commit=execution["commit"],
        )
        result = _status(
            "dispatched",
            policy=policy,
            reason="one exact queue entry was scheduled and reconciled",
            completed=len(completed),
            selected=selected,
        )
        result["runId"] = journal["reconciliation"]["run"]["id"]
        result["journalSha256"] = hashlib.sha256(journal_bytes).hexdigest()
        result["decisionSha256"] = hashlib.sha256(decision_bytes).hexdigest()
        return result
    except KaggleControlRootDrift:
        # The pathname no longer names the trusted activation root. Never
        # persist a breaker into the untrusted replacement directory.
        raise
    except KaggleQueueExpired as exc:
        return _status(
            "expired",
            policy=policy,
            reason=str(exc),
            completed=len(completed),
            selected=selected,
        )
    except KaggleQueueHeld as exc:
        return _status(
            "held",
            policy=policy,
            reason=exc.reason,
            retry_after=exc.retry_after,
            completed=len(completed),
            selected=selected,
        )
    except KaggleQueueBreaker as exc:
        breaker = _persist_breaker(
            control_root,
            expected_device=expected_control_device,
            expected_inode=expected_control_inode,
            policy=policy,
            writer_id=writer_id,
            execution_commit=execution["commit"],
            reason=str(exc),
            now=instant,
        )
        return _status(
            "breaker",
            policy=policy,
            reason=breaker["failure"]["message"],
            completed=len(completed),
            selected=selected,
        )
    except KaggleRunOnceError as exc:
        breaker = _persist_breaker(
            control_root,
            expected_device=expected_control_device,
            expected_inode=expected_control_inode,
            policy=policy,
            writer_id=writer_id,
            execution_commit=execution["commit"],
            reason=f"one-shot scheduler failed closed: {exc}",
            now=instant,
        )
        return _status(
            "breaker",
            policy=policy,
            reason=breaker["failure"]["message"],
            completed=len(completed),
            selected=selected,
        )
    except Exception as exc:
        decision_exists = (
            selected is not None
            and _path_under(
                control_root,
                _policy_entry_paths(selected)["decisionReceipt"],
            ).exists()
        )
        if decision_exists:
            breaker = _persist_breaker(
                control_root,
                expected_device=expected_control_device,
                expected_inode=expected_control_inode,
                policy=policy,
                writer_id=writer_id,
                execution_commit=execution["commit"],
                reason=(
                    "dispatch failed after its durable decision receipt: "
                    f"{type(exc).__name__}: {exc}"
                ),
                now=instant,
            )
            return _status(
                "breaker",
                policy=policy,
                reason=breaker["failure"]["message"],
                completed=len(completed),
                selected=selected,
            )
        return _status(
            "held",
            policy=policy,
            reason=f"required read is temporarily unavailable: {type(exc).__name__}",
            completed=len(completed),
            selected=selected,
        )


def run_queue_once(
    *,
    control_root: Path,
    expected_control_device: int,
    expected_control_inode: int,
    writer_id: str,
    expected_policy_sha256: str,
    expected_execution_commit: str,
    execution_root: Path,
    policy_path: Path = POLICY_PATH,
    now: Callable[[], datetime] = _utc_datetime_now,
    execution_verifier: Callable[..., dict[str, str]] = verify_execution_checkout,
    source_reader: Callable[[], dict[str, Any]] = current_capture_source_identity,
    run_set_reader: Callable[..., list[dict[str, Any]]] = fetch_benchmark_task_runs,
    quota_reader: Callable[[], list[dict[str, Any]]] = fetch_model_proxy_quota,
    dispatcher: Callable[..., dict[str, Any]] = run_once,
) -> dict[str, Any]:
    """Advance the finite queue under one same-root invocation lock."""

    if not isinstance(writer_id, str) or not _WRITER_ID.fullmatch(writer_id):
        raise KaggleQueueError("writer ID must be one bounded lowercase identity")
    _pinned_control_root_identity(
        control_root,
        expected_device=expected_control_device,
        expected_inode=expected_control_inode,
    )
    _verify_loaded_authority_paths(execution_root, policy_path=policy_path)
    policy = load_queue_policy(
        policy_path, expected_sha256=expected_policy_sha256
    )
    execution = execution_verifier(
        execution_root, expected_commit=expected_execution_commit
    )
    instant = _sample_clock(now, role="queue invocation clock")
    try:
        with _exclusive_queue_lock(
            control_root,
            expected_device=expected_control_device,
            expected_inode=expected_control_inode,
        ) as lease:
            if lease.error is not None:
                breaker = _persist_breaker(
                    control_root,
                    expected_device=expected_control_device,
                    expected_inode=expected_control_inode,
                    policy=policy,
                    writer_id=writer_id,
                    execution_commit=execution["commit"],
                    reason=f"queue lock preflight failed closed: {lease.error}",
                    now=instant,
                )
                return _status(
                    "breaker",
                    policy=policy,
                    reason=breaker["failure"]["message"],
                    completed=0,
                )
            try:
                return _run_queue_once_locked(
                    control_root=control_root,
                    expected_control_device=expected_control_device,
                    expected_control_inode=expected_control_inode,
                    writer_id=writer_id,
                    expected_policy_sha256=expected_policy_sha256,
                    expected_execution_commit=expected_execution_commit,
                    execution_root=execution_root,
                    locked_control_identity=lease.root_identity,
                    locked_control_fd=lease.root_fd,
                    lock_identity=lease.identity,
                    policy_path=policy_path,
                    now=now,
                    initial_instant=instant,
                    execution_verifier=execution_verifier,
                    source_reader=source_reader,
                    run_set_reader=run_set_reader,
                    quota_reader=quota_reader,
                    dispatcher=dispatcher,
                )
            except KaggleControlRootDrift:
                raise
            except KaggleQueueHeld as exc:
                return _status(
                    "held",
                    policy=policy,
                    reason=exc.reason,
                    retry_after=exc.retry_after,
                    completed=0,
                )
            except KaggleQueueError as exc:
                breaker = _persist_breaker(
                    control_root,
                    expected_device=expected_control_device,
                    expected_inode=expected_control_inode,
                    policy=policy,
                    writer_id=writer_id,
                    execution_commit=execution["commit"],
                    reason=f"trusted queue preflight failed closed: {exc}",
                    now=instant,
                )
                return _status(
                    "breaker",
                    policy=policy,
                    reason=breaker["failure"]["message"],
                    completed=0,
                )
            except Exception as exc:
                return _status(
                    "held",
                    policy=policy,
                    reason=(
                        "trusted queue preflight read is temporarily unavailable: "
                        f"{type(exc).__name__}"
                    ),
                    completed=0,
                )
    except KaggleQueueHeld as exc:
        return _status(
            "held",
            policy=policy,
            reason=exc.reason,
            retry_after=exc.retry_after,
            completed=0,
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Advance the reviewed finite Kaggle v10 capture queue by at most "
            "one no-retry scheduling POST."
        )
    )
    parser.add_argument("--control-root", required=True, type=Path)
    parser.add_argument("--expect-control-device", required=True, type=int)
    parser.add_argument("--expect-control-inode", required=True, type=int)
    parser.add_argument("--writer-id", required=True)
    parser.add_argument("--expect-policy-sha256", required=True)
    parser.add_argument("--expect-execution-commit", required=True)
    parser.add_argument("--execution-root", required=True, type=Path)
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)
    try:
        result = run_queue_once(
            control_root=args.control_root,
            expected_control_device=args.expect_control_device,
            expected_control_inode=args.expect_control_inode,
            writer_id=args.writer_id,
            expected_policy_sha256=args.expect_policy_sha256,
            expected_execution_commit=args.expect_execution_commit,
            execution_root=args.execution_root,
        )
    except (KaggleQueueError, OSError, ValueError) as exc:
        print(f"Kaggle finite queue failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=True, indent=2, sort_keys=True))
    return 2 if result["status"] == "breaker" else 0


if __name__ == "__main__":
    raise SystemExit(main())
