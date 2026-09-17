from __future__ import annotations

import copy
import hashlib
import json
import math
import os
import re
import secrets
import stat
import sys
from datetime import datetime
from pathlib import Path
from types import ModuleType
from typing import Any, Callable

from .legacy_v0_1 import (
    assert_not_v0_1_write,
    load_v0_1_receipt,
    verify_v0_1_package_receipt,
)
from .schema_validation import load_schema, validate


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_V0_1_PACKAGE_ROOT = REPO_ROOT / "bench/results/platform/m0-mock"
RECEIPT_SCHEMA_PATH = (
    REPO_ROOT / "schemas/v0.2/aleph-bench-kaggle-receipt.schema.json"
)
RECEIPT_VERSION = "0.2.0"
SOURCE_PROTOCOL_VERSION = "0.1-legacy"
COMPLETED_STATE = "BENCHMARK_TASK_RUN_STATE_COMPLETED"
DEFAULT_SATURATION_MARGIN_TOKENS = 4
AUDITED_TASK_NAME = "aleph_bench_frozen_ladder"
AUDITED_TASK_VERSION = 3
AUDITED_TASK_DESCRIPTION = (
    "Score target recovery from non-leaking frozen-ladder prompts using inverse AURC."
)
AUDITED_TASK_DEFINITION_SHA256 = (
    "93020f8ac90bd37e3711b6ad233443fc5e7f1ec4f047a8930f1bbf31039f6e02"
)
AUDITED_PACKAGE_MANIFEST_SHA256 = (
    "1f4d0ef9420079f1a5734879c6be716bd7227b950d03703341d4bc74517be8d7"
)
AUDITED_PACKAGE_MANIFEST_BYTES = 10_299
AUDITED_PACKAGE_TREE_SHA256 = (
    "0ae1f94ff0c599bda3ce69de7027c44d128ddd1653e23f1a05d3e885d469dec4"
)
AUDITED_MAX_TOKENS = 512
AUDITED_SATURATION_MARGIN_TOKENS = 4
MAX_RUN_JSON_BYTES = 8 * 1024 * 1024
MAX_PROMPT_CODEPOINTS = 4_096
MAX_OUTPUT_CODEPOINTS = 8_192
MAX_TOTAL_OUTPUT_CODEPOINTS = 262_144
DEPRECATED_MODEL_VERSION_SLUG = "model_version_slug for conversation is DEPRECATED"
AUDITED_ARTIFACT_IDENTITIES = {
    "items": {
        "path": "data/public_s2_items.jsonl",
        "sha256": "f6a8fc84861259ece233a2c883ca5cdc6eebe45c2f699a0898c790653f2b870a",
        "bytes": 92_015,
    },
    "prompts": {
        "path": "data/public_s2_prompts.jsonl",
        "sha256": "32cb5757463ce8d520f24888009c272c022b9d95f9bf59a6bf7ff8b15fd281cc",
        "bytes": 133_353,
    },
    "scoringCore": {
        "path": "kaggle/_scoring.py",
        "sha256": "4b575faba4fdd061cc5f551d0a9bb864ef7e263c06eab0bb794437ab8735af55",
        "bytes": 9_563,
    },
    "scoreOutputs": {
        "path": "kaggle/score_outputs.py",
        "sha256": "a35d9d481526a2c24c0abfbb2fb15b16af94145a6e1405cecf079449f82c5479",
        "bytes": 9_965,
    },
}

_RUN_FIELDS = {
    "conversations",
    "endTime",
    "modelVersion",
    "pyRunId",
    "results",
    "startTime",
    "state",
    "taskVersion",
}
_TASK_FIELDS = {"definition", "description", "name", "versionNumber"}
_REQUEST_METRIC_FIELDS = {
    "inputTokens",
    "outputTokens",
    "inputTokensCostNanodollars",
    "outputTokensCostNanodollars",
    "totalBackendLatencyMs",
}
_CHAT_SUFFIX = re.compile(r"[0-9a-f]{8}\Z")
_UTC_TIMESTAMP = re.compile(
    r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}"
    r"(?:\.[0-9]{1,6})?Z\Z"
)
_MODEL_SLUG = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:/-]*\Z")


class KaggleReceiptError(ValueError):
    """Raised when a Kaggle run cannot be treated as replayable evidence."""


def _reject_json_constant(value: str) -> None:
    raise KaggleReceiptError(f"non-finite JSON constant is forbidden: {value}")


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, child in pairs:
        if key in value:
            raise KaggleReceiptError(f"duplicate JSON object key is forbidden: {key!r}")
        value[key] = child
    return value


def _load_json_bytes(raw: bytes, *, role: str) -> Any:
    try:
        return json.loads(
            raw.decode("utf-8"),
            parse_constant=_reject_json_constant,
            object_pairs_hook=_reject_duplicate_keys,
        )
    except UnicodeDecodeError as exc:
        raise KaggleReceiptError(f"{role} is not valid UTF-8") from exc
    except json.JSONDecodeError as exc:
        raise KaggleReceiptError(f"{role} is not valid JSON: {exc}") from exc


def _load_jsonl_bytes(raw: bytes, *, role: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for index, raw_line in enumerate(raw.splitlines(), start=1):
        if not raw_line.strip():
            continue
        row = _load_json_bytes(raw_line, role=f"{role} line {index}")
        if not isinstance(row, dict):
            raise KaggleReceiptError(f"{role} line {index} must be a JSON object")
        rows.append(row)
    if not rows:
        raise KaggleReceiptError(f"{role} contains no rows")
    return rows


def _parse_utc_timestamp(value: Any, *, role: str) -> datetime:
    text = _require_string(value, role=role)
    if _UTC_TIMESTAMP.fullmatch(text) is None:
        raise KaggleReceiptError(f"{role} must be canonical RFC 3339 UTC")
    try:
        return datetime.fromisoformat(text[:-1] + "+00:00")
    except ValueError as exc:
        raise KaggleReceiptError(f"{role} is not a valid UTC timestamp") from exc


def _read_pinned_file(
    path: Path,
    *,
    expected_sha256: str,
    expected_bytes: int | None = None,
    role: str,
) -> bytes:
    """Read once, hash those exact bytes, and never execute through the path."""

    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        raise KaggleReceiptError(f"could not safely open {role}: {exc}") from exc
    try:
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1:
            raise KaggleReceiptError(f"{role} must be a singly linked regular file")
        if expected_bytes is not None and metadata.st_size != expected_bytes:
            raise KaggleReceiptError(
                f"{role} byte length drifted: expected {expected_bytes}, "
                f"found {metadata.st_size}"
            )
        with os.fdopen(descriptor, "rb") as handle:
            descriptor = -1
            raw = handle.read(expected_bytes + 1 if expected_bytes is not None else -1)
    finally:
        if descriptor >= 0:
            os.close(descriptor)
    if expected_bytes is not None and len(raw) != expected_bytes:
        raise KaggleReceiptError(
            f"{role} byte length drifted: expected {expected_bytes}, found {len(raw)}"
        )
    digest = _sha256(raw)
    if digest != expected_sha256:
        raise KaggleReceiptError(
            f"{role} digest drifted: expected {expected_sha256}, found {digest}"
        )
    return raw


def _read_bounded_regular_file(path: Path, *, max_bytes: int, role: str) -> bytes:
    """Read one regular-file snapshot without following the final symlink."""

    flags = (
        os.O_RDONLY
        | getattr(os, "O_CLOEXEC", 0)
        | getattr(os, "O_NOFOLLOW", 0)
        | getattr(os, "O_NONBLOCK", 0)
    )
    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        raise KaggleReceiptError(f"could not safely open {role}: {exc}") from exc
    try:
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode):
            raise KaggleReceiptError(f"{role} must be a regular file")
        if metadata.st_size > max_bytes:
            raise KaggleReceiptError(
                f"{role} exceeds the {max_bytes}-byte safety limit"
            )
        with os.fdopen(descriptor, "rb") as handle:
            descriptor = -1
            raw = handle.read(max_bytes + 1)
    finally:
        if descriptor >= 0:
            os.close(descriptor)
    if len(raw) > max_bytes:
        raise KaggleReceiptError(f"{role} exceeds the {max_bytes}-byte safety limit")
    return raw


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical_json_bytes(value: Any) -> bytes:
    """Serialize a receipt deterministically and reject non-finite numbers."""

    try:
        return (
            json.dumps(
                value,
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
                allow_nan=False,
            )
            + "\n"
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise KaggleReceiptError(f"receipt is not canonical JSON data: {exc}") from exc


def _identity_json_bytes(value: Any) -> bytes:
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise KaggleReceiptError(f"identity contains invalid JSON data: {exc}") from exc


def _require_exact_fields(value: dict[str, Any], expected: set[str], *, role: str) -> None:
    missing = sorted(expected - set(value))
    unexpected = sorted(set(value) - expected)
    if missing or unexpected:
        raise KaggleReceiptError(
            f"{role} fields drifted; missing={missing}, unexpected={unexpected}"
        )


def _require_string(value: Any, *, role: str, allow_empty: bool = False) -> str:
    if not isinstance(value, str) or (not allow_empty and not value):
        qualifier = "a string" if allow_empty else "a non-empty string"
        raise KaggleReceiptError(f"{role} must be {qualifier}")
    return value


def _require_int(value: Any, *, role: str, minimum: int | None = None) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise KaggleReceiptError(f"{role} must be an integer")
    if minimum is not None and value < minimum:
        raise KaggleReceiptError(f"{role} must be at least {minimum}")
    return value


def _require_finite_number(value: Any, *, role: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise KaggleReceiptError(f"{role} must be a number")
    try:
        result = float(value)
    except (OverflowError, ValueError) as exc:
        raise KaggleReceiptError(f"{role} must be finite") from exc
    if not math.isfinite(result):
        raise KaggleReceiptError(f"{role} must be finite")
    return result


def _require_nonnegative_decimal_string(value: Any, *, role: str) -> str:
    if not isinstance(value, str) or not value.isascii() or not value.isdigit():
        raise KaggleReceiptError(f"{role} must be a non-negative decimal string")
    return value


def _assert_finite_tree(value: Any, *, role: str = "value") -> None:
    if isinstance(value, float) and not math.isfinite(value):
        raise KaggleReceiptError(f"{role} contains a non-finite number")
    if isinstance(value, dict):
        for key, child in value.items():
            _assert_finite_tree(child, role=f"{role}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _assert_finite_tree(child, role=f"{role}[{index}]")


def _strict_request_contents(
    contents: Any,
    *,
    context: str,
    model_slug: str,
) -> tuple[str, str]:
    if not isinstance(contents, list) or len(contents) != 2:
        found = len(contents) if isinstance(contents, list) else "non-array"
        raise KaggleReceiptError(
            f"{context} contents must be the audited two-message exchange; found {found}"
        )
    expected = (
        ("CONTENT_ROLE_USER", "User", False),
        ("CONTENT_ROLE_ASSISTANT", model_slug, True),
    )
    texts: list[str] = []
    for index, (content, (role, sender_name, allow_empty)) in enumerate(
        zip(contents, expected)
    ):
        content_context = f"{context} contents[{index}]"
        if not isinstance(content, dict):
            raise KaggleReceiptError(f"{content_context} must be an object")
        _require_exact_fields(
            content,
            {"parts", "role", "senderName"},
            role=content_context,
        )
        if content["role"] != role or content["senderName"] != sender_name:
            raise KaggleReceiptError(
                f"{content_context} identity drifted: expected {role}/{sender_name!r}"
            )
        parts = content["parts"]
        if not isinstance(parts, list) or len(parts) != 1 or not isinstance(parts[0], dict):
            raise KaggleReceiptError(
                f"{content_context} must contain exactly one text part"
            )
        _require_exact_fields(parts[0], {"text"}, role=f"{content_context} part")
        texts.append(
            _require_string(
                parts[0]["text"],
                role=f"{content_context} text",
                allow_empty=allow_empty,
            )
        )
    return texts[0], texts[1]


def _validate_request_metrics(value: Any, *, context: str) -> dict[str, int | str]:
    if not isinstance(value, dict):
        raise KaggleReceiptError(f"{context} metrics must be an object")
    _require_exact_fields(value, _REQUEST_METRIC_FIELDS, role=f"{context} metrics")
    return {
        "inputTokens": _require_int(
            value["inputTokens"], role=f"{context} inputTokens", minimum=0
        ),
        "outputTokens": _require_int(
            value["outputTokens"], role=f"{context} outputTokens", minimum=0
        ),
        "inputTokensCostNanodollars": _require_nonnegative_decimal_string(
            value["inputTokensCostNanodollars"],
            role=f"{context} inputTokensCostNanodollars",
        ),
        "outputTokensCostNanodollars": _require_nonnegative_decimal_string(
            value["outputTokensCostNanodollars"],
            role=f"{context} outputTokensCostNanodollars",
        ),
        "totalBackendLatencyMs": _require_nonnegative_decimal_string(
            value["totalBackendLatencyMs"],
            role=f"{context} totalBackendLatencyMs",
        ),
    }


def _diagnostics_for_rows(
    rows: list[dict[str, Any]],
    *,
    max_tokens: int,
    saturation_margin_tokens: int,
) -> dict[str, Any]:
    output_tokens = [int(row["usage"]["outputTokens"]) for row in rows]
    empty_row_ids = [row["rowId"] for row in rows if not row["outputText"].strip()]
    invalid_usage_row_ids = [
        row["rowId"]
        for row in rows
        if row["usage"]["inputTokens"] == 0
        or row["usage"]["outputTokens"] == 0
        or row["usage"]["outputTokens"] > max_tokens
    ]
    saturation_threshold = max_tokens - saturation_margin_tokens
    near_cap_row_ids = [
        row["rowId"]
        for row in rows
        if row["usage"]["outputTokens"] >= saturation_threshold
    ]
    return {
        "status": (
            "blocked"
            if empty_row_ids or invalid_usage_row_ids or near_cap_row_ids
            else "valid"
        ),
        "emptyRowIds": empty_row_ids,
        "invalidUsageRowIds": invalid_usage_row_ids,
        "nearCapRowIds": near_cap_row_ids,
        "outputTokenStats": {
            "count": len(output_tokens),
            "min": min(output_tokens),
            "max": max(output_tokens),
            "mean": round(sum(output_tokens) / len(output_tokens), 6),
            "nearCapCount": len(near_cap_row_ids),
            "nearCapThreshold": saturation_threshold,
        },
    }


def parse_run_conversations(
    run: dict[str, Any],
    *,
    expected_prompts: list[dict[str, str]],
    model_slug: str,
    max_tokens: int,
    saturation_margin_tokens: int = DEFAULT_SATURATION_MARGIN_TOKENS,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Extract exactly one raw response for every expected legacy prompt."""

    max_tokens = _require_int(max_tokens, role="max_tokens", minimum=1)
    saturation_margin_tokens = _require_int(
        saturation_margin_tokens,
        role="saturation_margin_tokens",
        minimum=0,
    )
    if saturation_margin_tokens >= max_tokens:
        raise KaggleReceiptError(
            "saturation_margin_tokens must be smaller than max_tokens"
        )
    task = run.get("taskVersion")
    if not isinstance(task, dict):
        raise KaggleReceiptError("run taskVersion must be an object")
    task_name = _require_string(task.get("name"), role="taskVersion.name")
    conversations = run.get("conversations")
    if not isinstance(conversations, list):
        raise KaggleReceiptError("run conversations must be an array")

    expected_by_base: dict[str, dict[str, str]] = {}
    for row in expected_prompts:
        item_id = _require_string(row.get("item_id"), role="expected item_id")
        prompt_id = _require_string(row.get("prompt_id"), role="expected prompt_id")
        prompt = _require_string(row.get("prompt"), role="expected prompt")
        base = f"{item_id}:{prompt_id}"
        if base in expected_by_base:
            raise KaggleReceiptError(f"duplicate expected prompt: {base}")
        expected_by_base[base] = {
            "item_id": item_id,
            "prompt_id": prompt_id,
            "prompt": prompt,
        }

    rows_by_base: dict[str, dict[str, Any]] = {}
    placeholder_ids: list[str] = []
    total_output_codepoints = 0
    for index, conversation in enumerate(conversations):
        context = f"conversation[{index}]"
        if not isinstance(conversation, dict):
            raise KaggleReceiptError(f"{context} must be an object")
        conversation_id = _require_string(
            conversation.get("id"), role=f"{context}.id"
        )
        requests = conversation.get("requests")
        if requests is None:
            _require_exact_fields(
                conversation,
                {"id", "metrics", "modelVersionSlug"},
                role=f"{context} placeholder",
            )
            suffix = conversation_id[len(task_name) + 1 :]
            if (
                index != 0
                or placeholder_ids
                or not conversation_id.startswith(f"{task_name}-")
                or _CHAT_SUFFIX.fullmatch(suffix) is None
                or conversation["metrics"] != {}
                or conversation["modelVersionSlug"] != DEPRECATED_MODEL_VERSION_SLUG
            ):
                raise KaggleReceiptError(
                    f"unexpected request-less conversation: {conversation_id}"
                )
            placeholder_ids.append(conversation_id)
            continue
        if not isinstance(requests, list) or len(requests) != 1:
            raise KaggleReceiptError(
                f"{context} must contain exactly one request; found "
                f"{len(requests) if isinstance(requests, list) else 'non-array'}"
            )
        _require_exact_fields(
            conversation,
            {"id", "requests", "metrics", "modelVersionSlug"},
            role=context,
        )
        if conversation["modelVersionSlug"] != DEPRECATED_MODEL_VERSION_SLUG:
            raise KaggleReceiptError(f"{context} modelVersionSlug marker drifted")
        matching_bases = [
            base
            for base in expected_by_base
            if conversation_id.startswith(f"{base}-")
            and _CHAT_SUFFIX.fullmatch(conversation_id[len(base) + 1 :])
        ]
        if len(matching_bases) != 1:
            raise KaggleReceiptError(
                f"conversation id does not identify exactly one expected prompt: "
                f"{conversation_id}"
            )
        base = matching_bases[0]
        if base in rows_by_base:
            raise KaggleReceiptError(f"duplicate response conversation for {base}")

        request = requests[0]
        if not isinstance(request, dict):
            raise KaggleReceiptError(f"{context} request must be an object")
        _require_exact_fields(
            request,
            {"contents", "id", "metrics"},
            role=f"{context} request",
        )
        request_id = _require_string(request.get("id"), role=f"{context} request id")
        if request_id != f"{conversation_id}-req-1":
            raise KaggleReceiptError(
                f"{context} request id drifted: expected {conversation_id}-req-1, "
                f"found {request_id}"
            )
        prompt_text, output_text = _strict_request_contents(
            request["contents"], context=context, model_slug=model_slug
        )
        if len(prompt_text) > MAX_PROMPT_CODEPOINTS:
            raise KaggleReceiptError(
                f"{context} prompt exceeds the {MAX_PROMPT_CODEPOINTS}-code-point "
                "safety limit"
            )
        if len(output_text) > MAX_OUTPUT_CODEPOINTS:
            raise KaggleReceiptError(
                f"{context} output exceeds the {MAX_OUTPUT_CODEPOINTS}-code-point "
                "safety limit"
            )
        total_output_codepoints += len(output_text)
        if total_output_codepoints > MAX_TOTAL_OUTPUT_CODEPOINTS:
            raise KaggleReceiptError(
                "assistant outputs exceed the "
                f"{MAX_TOTAL_OUTPUT_CODEPOINTS}-code-point aggregate safety limit"
            )
        expected = expected_by_base[base]
        if prompt_text != expected["prompt"]:
            raise KaggleReceiptError(f"prompt text drifted for {base}")
        metrics = _validate_request_metrics(request["metrics"], context=context)
        conversation_metrics = _validate_request_metrics(
            conversation.get("metrics"), context=f"{context} conversation"
        )
        if conversation_metrics != metrics:
            raise KaggleReceiptError(f"conversation/request metrics drifted for {base}")
        rows_by_base[base] = {
            "rowId": base,
            "itemId": expected["item_id"],
            "promptId": expected["prompt_id"],
            "rerunIndex": 0,
            "conversationId": conversation_id,
            "requestId": request_id,
            "promptText": prompt_text,
            "outputText": output_text,
            "usage": metrics,
        }

    if len(placeholder_ids) != 1:
        raise KaggleReceiptError(
            f"expected exactly one task placeholder conversation; found {len(placeholder_ids)}"
        )
    missing = sorted(set(expected_by_base) - set(rows_by_base))
    extra = sorted(set(rows_by_base) - set(expected_by_base))
    if missing or extra:
        raise KaggleReceiptError(
            f"response coverage mismatch; missing={missing}, extra={extra}"
        )
    rows = [rows_by_base[base] for base in expected_by_base]
    diagnostics = _diagnostics_for_rows(
        rows,
        max_tokens=max_tokens,
        saturation_margin_tokens=saturation_margin_tokens,
    )
    return rows, diagnostics


def _load_legacy_score_function(
    *,
    scoring_source: bytes,
    score_outputs_source: bytes,
    item_rows: list[dict[str, Any]],
    prompt_rows: list[dict[str, Any]],
) -> Callable[..., dict[str, Any]]:
    """Execute only the already-hashed source snapshot, never an operator path."""

    scoring_name = "aleph_bench_snapshot/kaggle/_scoring.py"
    score_outputs_name = "aleph_bench_snapshot/kaggle/score_outputs.py"
    scoring_module = ModuleType("_scoring")
    scoring_module.__file__ = scoring_name
    score_module = ModuleType("aleph_bench_v0_1_score_outputs")
    score_module.__file__ = score_outputs_name
    previous_scoring = sys.modules.get("_scoring")
    previous_sys_path = list(sys.path)
    try:
        sys.modules["_scoring"] = scoring_module
        exec(
            compile(scoring_source, scoring_name, "exec"),
            scoring_module.__dict__,
        )
        exec(
            compile(score_outputs_source, score_outputs_name, "exec"),
            score_module.__dict__,
        )
    finally:
        sys.path[:] = previous_sys_path
        if previous_scoring is None:
            sys.modules.pop("_scoring", None)
        else:
            sys.modules["_scoring"] = previous_scoring

    def snapshot_jsonl(path: str | Path) -> list[dict[str, Any]]:
        logical_path = Path(path).as_posix()
        if logical_path.endswith("data/public_s2_items.jsonl"):
            return copy.deepcopy(item_rows)
        if logical_path.endswith("data/public_s2_prompts.jsonl"):
            return copy.deepcopy(prompt_rows)
        raise KaggleReceiptError(
            f"legacy scorer attempted to read an unaudited JSONL path: {logical_path}"
        )

    score_module.__dict__["_load_jsonl"] = snapshot_jsonl
    score_submission = score_module.__dict__.get("score_submission")
    if not callable(score_submission):
        raise KaggleReceiptError("immutable package lacks callable score_submission")
    return score_submission


def _artifact_map(manifest: dict[str, Any]) -> dict[str, dict[str, Any]]:
    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, list):
        raise KaggleReceiptError("package manifest artifacts must be an array")
    by_path: dict[str, dict[str, Any]] = {}
    for index, row in enumerate(artifacts):
        if not isinstance(row, dict):
            raise KaggleReceiptError(f"package artifact[{index}] must be an object")
        path = _require_string(row.get("path"), role=f"package artifact[{index}].path")
        if path in by_path:
            raise KaggleReceiptError(f"duplicate package artifact path: {path}")
        by_path[path] = row
    return by_path


def _snapshot_declared_artifact(
    package_root: Path,
    artifacts: dict[str, dict[str, Any]],
    relative_path: str,
) -> tuple[dict[str, Any], bytes]:
    row = artifacts.get(relative_path)
    if row is None:
        raise KaggleReceiptError(f"package manifest omits {relative_path}")
    expected_sha256 = _require_string(
        row.get("sha256"), role=f"package artifact {relative_path} sha256"
    )
    expected_bytes = _require_int(
        row.get("bytes"), role=f"package artifact {relative_path} bytes", minimum=1
    )
    raw = _read_pinned_file(
        package_root / relative_path,
        expected_sha256=expected_sha256,
        expected_bytes=expected_bytes,
        role=f"package artifact {relative_path}",
    )
    return (
        {"path": relative_path, "sha256": expected_sha256, "bytes": expected_bytes},
        raw,
    )


def _normalize_bench_result(result: dict[str, Any]) -> dict[str, Any]:
    normalized = copy.deepcopy(result)
    config = normalized.get("config")
    if not isinstance(config, dict):
        raise KaggleReceiptError("replayed bench result lacks config")
    config["datasetPath"] = "data/public_s2_items.jsonl"
    _assert_finite_tree(normalized, role="benchResult")
    return normalized


def _load_package_context(package_root: Path) -> dict[str, Any]:
    requested_root = Path(package_root).absolute()
    receipt_errors = verify_v0_1_package_receipt(requested_root)
    if receipt_errors:
        raise KaggleReceiptError(
            "v0.1 package receipt verification failed: " + "; ".join(receipt_errors)
        )
    package_root = requested_root.resolve()
    manifest_path = package_root / "package-manifest.json"
    manifest_raw = _read_pinned_file(
        manifest_path,
        expected_sha256=AUDITED_PACKAGE_MANIFEST_SHA256,
        expected_bytes=AUDITED_PACKAGE_MANIFEST_BYTES,
        role="audited package manifest",
    )
    manifest = _load_json_bytes(manifest_raw, role="package manifest")
    if not isinstance(manifest, dict):
        raise KaggleReceiptError("package manifest must be a JSON object")
    artifacts = _artifact_map(manifest)
    items_identity, items_raw = _snapshot_declared_artifact(
        package_root, artifacts, "data/public_s2_items.jsonl"
    )
    prompts_identity, prompts_raw = _snapshot_declared_artifact(
        package_root, artifacts, "data/public_s2_prompts.jsonl"
    )
    score_identity, score_source = _snapshot_declared_artifact(
        package_root, artifacts, "kaggle/score_outputs.py"
    )
    scoring_core_identity, scoring_source = _snapshot_declared_artifact(
        package_root, artifacts, "kaggle/_scoring.py"
    )
    item_rows = _load_jsonl_bytes(items_raw, role="public S2 items")
    prompt_rows = _load_jsonl_bytes(prompts_raw, role="public S2 prompts")
    sendable: list[dict[str, str]] = []
    seen_prompt_keys: set[tuple[str, str]] = set()
    for index, row in enumerate(prompt_rows):
        item_id = _require_string(row.get("item_id"), role=f"prompt[{index}].item_id")
        prompt_id = _require_string(
            row.get("prompt_id"), role=f"prompt[{index}].prompt_id"
        )
        prompt = _require_string(row.get("prompt"), role=f"prompt[{index}].prompt")
        key = (item_id, prompt_id)
        if key in seen_prompt_keys:
            raise KaggleReceiptError(f"duplicate package prompt: {item_id}:{prompt_id}")
        seen_prompt_keys.add(key)
        disqualified = row.get("disqualified")
        if not isinstance(disqualified, bool):
            raise KaggleReceiptError(f"prompt[{index}].disqualified must be boolean")
        if not disqualified:
            sendable.append(
                {"item_id": item_id, "prompt_id": prompt_id, "prompt": prompt}
            )
    canaries = {row.get("canaryGuid") for row in item_rows}
    if len(canaries) != 1 or not all(isinstance(value, str) and value for value in canaries):
        raise KaggleReceiptError("package items must share one non-empty canaryGuid")
    immutable_receipt = load_v0_1_receipt()
    reference_package_tree_sha256 = immutable_receipt["groups"]["platformPackage"][
        "sha256"
    ]
    if reference_package_tree_sha256 != AUDITED_PACKAGE_TREE_SHA256:
        raise KaggleReceiptError("immutable v0.1 package tree reference drifted")
    return {
        "root": package_root,
        "manifest": manifest,
        "manifestSha256": _sha256(manifest_raw),
        "referencePackageTreeSha256": reference_package_tree_sha256,
        "items": item_rows,
        "prompts": prompt_rows,
        "sendable": sendable,
        "canaryGuid": next(iter(canaries)),
        "itemsIdentity": items_identity,
        "promptsIdentity": prompts_identity,
        "scoreIdentity": score_identity,
        "scoringCoreIdentity": scoring_core_identity,
        "scoreSource": score_source,
        "scoringSource": scoring_source,
    }


def build_kaggle_receipt(
    *,
    run_json_path: Path,
    package_root: Path = DEFAULT_V0_1_PACKAGE_ROOT,
    max_tokens: int,
    saturation_margin_tokens: int = DEFAULT_SATURATION_MARGIN_TOKENS,
) -> dict[str, Any]:
    """Replay one completed v16-style Kaggle run into a canonical receipt."""

    run_path = Path(run_json_path)
    if max_tokens != AUDITED_MAX_TOKENS:
        raise KaggleReceiptError(
            "audited legacy task replay requires --max-tokens "
            f"{AUDITED_MAX_TOKENS}; the run JSON cannot prove overrides"
        )
    if saturation_margin_tokens != AUDITED_SATURATION_MARGIN_TOKENS:
        raise KaggleReceiptError(
            "audited legacy task replay requires --saturation-margin-tokens "
            f"{AUDITED_SATURATION_MARGIN_TOKENS}"
        )
    run_raw = _read_bounded_regular_file(
        run_path,
        max_bytes=MAX_RUN_JSON_BYTES,
        role="Kaggle run JSON",
    )
    run = _load_json_bytes(run_raw, role="Kaggle run")
    if not isinstance(run, dict):
        raise KaggleReceiptError("Kaggle run must be a JSON object")
    _require_exact_fields(run, _RUN_FIELDS, role="Kaggle run")
    if run.get("state") != COMPLETED_STATE:
        raise KaggleReceiptError(
            f"Kaggle run is not completed: {run.get('state')!r}"
        )

    task = run.get("taskVersion")
    if not isinstance(task, dict):
        raise KaggleReceiptError("taskVersion must be an object")
    _require_exact_fields(task, _TASK_FIELDS, role="taskVersion")
    task_name = _require_string(task["name"], role="taskVersion.name")
    task_description = _require_string(
        task["description"], role="taskVersion.description"
    )
    task_definition = _require_string(
        task["definition"], role="taskVersion.definition"
    )
    task_version = _require_int(
        task["versionNumber"], role="taskVersion.versionNumber", minimum=1
    )
    task_definition_sha256 = _sha256(task_definition.encode("utf-8"))
    if (
        task_name != AUDITED_TASK_NAME
        or task_version != AUDITED_TASK_VERSION
        or task_description != AUDITED_TASK_DESCRIPTION
        or task_definition_sha256 != AUDITED_TASK_DEFINITION_SHA256
    ):
        raise KaggleReceiptError(
            "unsupported Kaggle task identity: expected "
            f"{AUDITED_TASK_NAME}@{AUDITED_TASK_VERSION}/"
            f"{AUDITED_TASK_DEFINITION_SHA256} with audited description, found "
            f"{task_name}@{task_version}/{task_definition_sha256}"
        )
    model_version = run.get("modelVersion")
    if not isinstance(model_version, dict) or set(model_version) != {"slug"}:
        raise KaggleReceiptError("modelVersion must contain exactly slug")
    model_slug = _require_string(model_version["slug"], role="modelVersion.slug")
    if len(model_slug) > 256 or _MODEL_SLUG.fullmatch(model_slug) is None:
        raise KaggleReceiptError("modelVersion.slug is not an audited model identifier")
    py_run_id = _require_string(run.get("pyRunId"), role="pyRunId")
    started_at = _require_string(run.get("startTime"), role="startTime")
    ended_at = _require_string(run.get("endTime"), role="endTime")
    started_timestamp = _parse_utc_timestamp(started_at, role="startTime")
    ended_timestamp = _parse_utc_timestamp(ended_at, role="endTime")
    if ended_timestamp < started_timestamp:
        raise KaggleReceiptError("endTime must not precede startTime")

    results = run.get("results")
    if not isinstance(results, list) or len(results) != 1:
        raise KaggleReceiptError("run must contain exactly one result")
    result_row = results[0]
    if not isinstance(result_row, dict) or set(result_row) != {"type", "numericResult"}:
        raise KaggleReceiptError("run result fields drifted")
    if result_row.get("type") != "AGGREGATED":
        raise KaggleReceiptError("run result must be AGGREGATED")
    numeric_result = result_row.get("numericResult")
    if not isinstance(numeric_result, dict) or set(numeric_result) != {"value"}:
        raise KaggleReceiptError("numericResult must contain exactly value")
    leaderboard_scalar = _require_finite_number(
        numeric_result["value"], role="leaderboard scalar"
    )

    package = _load_package_context(Path(package_root))
    rows, diagnostics = parse_run_conversations(
        run,
        expected_prompts=package["sendable"],
        model_slug=model_slug,
        max_tokens=max_tokens,
        saturation_margin_tokens=saturation_margin_tokens,
    )
    submission_rows = [
        {
            "row_id": row["rowId"],
            "model_id": model_slug,
            "item_id": row["itemId"],
            "prompt_id": row["promptId"],
            "output_text": row["outputText"],
        }
        for row in rows
    ]
    score_submission = _load_legacy_score_function(
        scoring_source=package["scoringSource"],
        score_outputs_source=package["scoreSource"],
        item_rows=package["items"],
        prompt_rows=package["prompts"],
    )
    replayed = score_submission(
        items_path="data/public_s2_items.jsonl",
        prompts_path="data/public_s2_prompts.jsonl",
        submission_rows=submission_rows,
        model_id=model_slug,
    )
    if not isinstance(replayed, dict):
        raise KaggleReceiptError("legacy scorer did not return an object")
    bench_result = _normalize_bench_result(replayed)
    aggregate = bench_result.get("aggregate")
    if not isinstance(aggregate, dict):
        raise KaggleReceiptError("replayed bench result lacks aggregate")
    aurc = _require_finite_number(aggregate.get("aurc"), role="replayed aggregate.aurc")
    replayed_scalar = 1.0 - aurc
    if not math.isclose(
        leaderboard_scalar,
        replayed_scalar,
        rel_tol=0.0,
        abs_tol=1e-12,
    ):
        raise KaggleReceiptError(
            "leaderboard scalar does not match replayed inverse AURC: "
            f"{leaderboard_scalar!r} != {replayed_scalar!r}"
        )

    scoring_config = {
        "tau": bench_result["tau"],
        "k": bench_result["k"],
        "seed": bench_result["seed"],
        "bootstrapSamples": bench_result["config"]["bootstrapSamples"],
        "reruns": bench_result["config"]["reruns"],
        "leakageThresholds": bench_result["config"]["leakageThresholds"],
    }
    operator_assertions = {
        "maxTokens": _require_int(max_tokens, role="max_tokens", minimum=1),
        "saturationMarginTokens": _require_int(
            saturation_margin_tokens,
            role="saturation_margin_tokens",
            minimum=0,
        ),
        "maxTokensSource": "operator_asserted_not_present_in_run_json",
    }
    config_sha256 = _sha256(_identity_json_bytes(scoring_config))
    payload = {
        "receiptVersion": RECEIPT_VERSION,
        "sourceProtocolVersion": SOURCE_PROTOCOL_VERSION,
        "sourceRunSha256": _sha256(run_raw),
        "state": run["state"],
        "startedAt": started_at,
        "endedAt": ended_at,
        "pyRunId": py_run_id,
        "taskIdentity": {
            "name": task_name,
            "versionNumber": task_version,
            "description": task_description,
            "definitionSha256": task_definition_sha256,
        },
        "modelIdentity": {"slug": model_slug},
        "datasetIdentity": {
            "packageId": _require_string(
                package["manifest"].get("id"), role="package manifest id"
            ),
            "packageManifestSha256": package["manifestSha256"],
            "referencePackageTreeSha256": package["referencePackageTreeSha256"],
            "items": package["itemsIdentity"],
            "prompts": package["promptsIdentity"],
            "itemCount": len(package["items"]),
            "sendablePromptCount": len(package["sendable"]),
            "canaryGuid": package["canaryGuid"],
        },
        "scoringIdentity": {
            "scoreOutputs": package["scoreIdentity"],
            "scoringCore": package["scoringCoreIdentity"],
            "config": scoring_config,
            "configSha256": config_sha256,
        },
        "operatorAssertions": operator_assertions,
        "expectedRowCount": len(package["sendable"]),
        "rowCount": len(rows),
        "leaderboardScalar": leaderboard_scalar,
        "replayedScalar": replayed_scalar,
        "scalarMatches": True,
        "diagnostics": diagnostics,
        "submissionRows": rows,
        "benchResult": bench_result,
        "notes": [
            "Derived offline from the retained Kaggle run JSON and immutable v0.1 platform scorer.",
            "Raw assistant strings are retained exactly as recorded before scoring normalization.",
            "maxTokens is an operator assertion because the retained run JSON does not prove that invocation argument.",
            "A blocked diagnostic status is evidence of an operationally invalid run, not a valid leaderboard result.",
            "This legacy receipt is not an Aleph-Bench v0.2 model result.",
        ],
    }
    artifact_digest = _sha256(_identity_json_bytes(payload))
    receipt = {
        **payload,
        "id": f"aleph-bench-kaggle-receipt-v0.2-artifact-{artifact_digest}",
    }
    serialize_kaggle_receipt(receipt)
    return receipt


def _validate_kaggle_receipt_semantics(receipt: dict[str, Any]) -> None:
    """Check cross-field claims that JSON Schema cannot express."""

    started = _parse_utc_timestamp(receipt["startedAt"], role="startedAt")
    ended = _parse_utc_timestamp(receipt["endedAt"], role="endedAt")
    if ended < started:
        raise KaggleReceiptError("receipt endedAt must not precede startedAt")

    assertions = receipt["operatorAssertions"]
    if (
        assertions["maxTokens"] != AUDITED_MAX_TOKENS
        or assertions["saturationMarginTokens"]
        != AUDITED_SATURATION_MARGIN_TOKENS
    ):
        raise KaggleReceiptError("receipt operator assertions drifted from audited policy")

    rows = receipt["submissionRows"]
    if receipt["rowCount"] != len(rows) or receipt["expectedRowCount"] != len(rows):
        raise KaggleReceiptError("receipt row counts disagree with submissionRows")
    row_ids: set[str] = set()
    conversation_ids: set[str] = set()
    request_ids: set[str] = set()
    total_output_codepoints = 0
    for index, row in enumerate(rows):
        expected_row_id = f"{row['itemId']}:{row['promptId']}"
        if row["rowId"] != expected_row_id:
            raise KaggleReceiptError(f"submissionRows[{index}] row identity drifted")
        conversation_id = row["conversationId"]
        suffix = conversation_id[len(expected_row_id) + 1 :]
        if (
            not conversation_id.startswith(f"{expected_row_id}-")
            or _CHAT_SUFFIX.fullmatch(suffix) is None
            or row["requestId"] != f"{conversation_id}-req-1"
        ):
            raise KaggleReceiptError(
                f"submissionRows[{index}] conversation/request identity drifted"
            )
        if row["rowId"] in row_ids:
            raise KaggleReceiptError(f"duplicate receipt row id: {row['rowId']}")
        if conversation_id in conversation_ids:
            raise KaggleReceiptError(
                f"duplicate receipt conversation id: {conversation_id}"
            )
        if row["requestId"] in request_ids:
            raise KaggleReceiptError(f"duplicate receipt request id: {row['requestId']}")
        row_ids.add(row["rowId"])
        conversation_ids.add(conversation_id)
        request_ids.add(row["requestId"])
        if len(row["promptText"]) > MAX_PROMPT_CODEPOINTS:
            raise KaggleReceiptError(
                f"submissionRows[{index}] prompt exceeds the safety limit"
            )
        if len(row["outputText"]) > MAX_OUTPUT_CODEPOINTS:
            raise KaggleReceiptError(
                f"submissionRows[{index}] output exceeds the safety limit"
            )
        total_output_codepoints += len(row["outputText"])
    if total_output_codepoints > MAX_TOTAL_OUTPUT_CODEPOINTS:
        raise KaggleReceiptError("receipt assistant outputs exceed the aggregate safety limit")

    expected_diagnostics = _diagnostics_for_rows(
        rows,
        max_tokens=assertions["maxTokens"],
        saturation_margin_tokens=assertions["saturationMarginTokens"],
    )
    if receipt["diagnostics"] != expected_diagnostics:
        raise KaggleReceiptError("receipt diagnostics disagree with submission rows")

    leaderboard_scalar = _require_finite_number(
        receipt["leaderboardScalar"], role="receipt leaderboardScalar"
    )
    replayed_scalar = _require_finite_number(
        receipt["replayedScalar"], role="receipt replayedScalar"
    )
    if not math.isclose(
        leaderboard_scalar, replayed_scalar, rel_tol=0.0, abs_tol=1e-12
    ):
        raise KaggleReceiptError("receipt leaderboard and replayed scalars disagree")
    bench_result = receipt["benchResult"]
    expected_replayed_scalar = 1.0 - _require_finite_number(
        bench_result["aggregate"]["aurc"], role="receipt benchResult aggregate.aurc"
    )
    if not math.isclose(
        replayed_scalar, expected_replayed_scalar, rel_tol=0.0, abs_tol=1e-12
    ):
        raise KaggleReceiptError("receipt replayed scalar disagrees with benchResult")

    model_slug = receipt["modelIdentity"]["slug"]
    if bench_result["models"][0]["model"] != model_slug or any(
        item_run["model"] != model_slug for item_run in bench_result["itemRuns"]
    ):
        raise KaggleReceiptError("receipt model identity disagrees with benchResult")
    item_run_ids = [item_run["itemId"] for item_run in bench_result["itemRuns"]]
    if len(set(item_run_ids)) != len(item_run_ids):
        raise KaggleReceiptError("receipt benchResult contains duplicate item ids")
    row_item_ids = {row["itemId"] for row in rows}
    if row_item_ids != set(item_run_ids):
        raise KaggleReceiptError("receipt row item ids disagree with benchResult")

    canonical_package = _load_package_context(DEFAULT_V0_1_PACKAGE_ROOT)
    expected_prompts = {
        (row["item_id"], row["prompt_id"]): row["prompt"]
        for row in canonical_package["sendable"]
    }
    observed_prompt_keys = {(row["itemId"], row["promptId"]) for row in rows}
    if observed_prompt_keys != set(expected_prompts):
        raise KaggleReceiptError("receipt prompt coverage disagrees with pinned prompts")
    for index, row in enumerate(rows):
        expected_prompt = expected_prompts[(row["itemId"], row["promptId"])]
        if row["promptText"] != expected_prompt:
            raise KaggleReceiptError(
                f"submissionRows[{index}] prompt text disagrees with pinned prompt"
            )
    semantic_submission_rows = [
        {
            "row_id": row["rowId"],
            "model_id": model_slug,
            "item_id": row["itemId"],
            "prompt_id": row["promptId"],
            "output_text": row["outputText"],
        }
        for row in rows
    ]
    semantic_scorer = _load_legacy_score_function(
        scoring_source=canonical_package["scoringSource"],
        score_outputs_source=canonical_package["scoreSource"],
        item_rows=canonical_package["items"],
        prompt_rows=canonical_package["prompts"],
    )
    expected_bench_result = _normalize_bench_result(
        semantic_scorer(
            items_path="data/public_s2_items.jsonl",
            prompts_path="data/public_s2_prompts.jsonl",
            submission_rows=semantic_submission_rows,
            model_id=model_slug,
        )
    )
    if bench_result != expected_bench_result:
        raise KaggleReceiptError(
            "receipt benchResult disagrees with replay of its raw output rows"
        )

    dataset_identity = receipt["datasetIdentity"]
    if (
        dataset_identity["packageManifestSha256"]
        != AUDITED_PACKAGE_MANIFEST_SHA256
        or dataset_identity["referencePackageTreeSha256"]
        != AUDITED_PACKAGE_TREE_SHA256
        or dataset_identity["canaryGuid"] != bench_result["canaryGuid"]
        or dataset_identity["itemCount"] != len(item_run_ids)
        or dataset_identity["sendablePromptCount"] != len(rows)
    ):
        raise KaggleReceiptError("receipt dataset identity claims disagree")
    for key in ("items", "prompts"):
        if dataset_identity[key] != AUDITED_ARTIFACT_IDENTITIES[key]:
            raise KaggleReceiptError(f"receipt dataset {key} identity drifted")

    scoring_identity = receipt["scoringIdentity"]
    for key in ("scoreOutputs", "scoringCore"):
        if scoring_identity[key] != AUDITED_ARTIFACT_IDENTITIES[key]:
            raise KaggleReceiptError(f"receipt {key} identity drifted")
    scoring_config = scoring_identity["config"]
    expected_scoring_config = {
        "tau": bench_result["tau"],
        "k": bench_result["k"],
        "seed": bench_result["seed"],
        "bootstrapSamples": bench_result["config"]["bootstrapSamples"],
        "reruns": bench_result["config"]["reruns"],
        "leakageThresholds": bench_result["config"]["leakageThresholds"],
    }
    if scoring_config != expected_scoring_config:
        raise KaggleReceiptError("receipt scoring config disagrees with benchResult")
    expected_config_sha256 = _sha256(_identity_json_bytes(scoring_config))
    if scoring_identity["configSha256"] != expected_config_sha256:
        raise KaggleReceiptError("receipt scoring config digest disagrees with config")


def serialize_kaggle_receipt(receipt: dict[str, Any]) -> bytes:
    validate(receipt, load_schema(RECEIPT_SCHEMA_PATH))
    _validate_kaggle_receipt_semantics(receipt)
    expected_id = receipt.get("id")
    payload = {key: value for key, value in receipt.items() if key != "id"}
    observed_id = (
        "aleph-bench-kaggle-receipt-v0.2-artifact-"
        + _sha256(_identity_json_bytes(payload))
    )
    if expected_id != observed_id:
        raise KaggleReceiptError(
            f"receipt artifact id mismatch: expected {observed_id}, found {expected_id}"
        )
    return canonical_json_bytes(receipt)


def validate_kaggle_replay_output_path(
    *,
    run_json_path: Path,
    package_root: Path,
    out: Path,
) -> Path:
    """Require a fresh output outside both source evidence inputs."""

    requested_out = Path(out).absolute()
    try:
        requested_out.lstat()
    except FileNotFoundError:
        pass
    except OSError as exc:
        raise KaggleReceiptError(f"could not safely inspect output path: {exc}") from exc
    else:
        raise KaggleReceiptError(
            f"refusing to replace existing Kaggle receipt output: {requested_out}"
        )

    try:
        run_path = Path(run_json_path).resolve(strict=True)
        package_path = Path(package_root).resolve(strict=True)
    except OSError as exc:
        raise KaggleReceiptError(f"could not resolve Kaggle replay input: {exc}") from exc
    output_path = requested_out.resolve(strict=False)
    if output_path == run_path:
        raise KaggleReceiptError("receipt output must not alias the source run JSON")
    if output_path == package_path or output_path.is_relative_to(package_path):
        raise KaggleReceiptError("receipt output must be outside the scorer package")
    assert_not_v0_1_write(output_path)
    return output_path


def _open_directory_no_symlinks(
    path: Path, *, create_missing: bool
) -> tuple[int, set[tuple[int, int]]]:
    """Open an absolute directory component-by-component with stable dirfds."""

    if not path.is_absolute():
        raise KaggleReceiptError("safe directory open requires an absolute path")
    if not hasattr(os, "O_NOFOLLOW") or not hasattr(os, "O_DIRECTORY"):
        raise KaggleReceiptError("safe receipt publication is unsupported on this platform")
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | getattr(os, "O_CLOEXEC", 0)
    anchor = path.anchor or os.sep
    try:
        descriptor = os.open(anchor, flags)
    except OSError as exc:
        raise KaggleReceiptError(f"could not safely open path anchor: {exc}") from exc
    identities: set[tuple[int, int]] = set()
    try:
        metadata = os.fstat(descriptor)
        identities.add((metadata.st_dev, metadata.st_ino))
        for part in path.parts[1:]:
            if part in {"", ".", ".."}:
                raise KaggleReceiptError(f"unsafe receipt directory component: {part!r}")
            try:
                child_descriptor = os.open(part, flags, dir_fd=descriptor)
            except FileNotFoundError:
                if not create_missing:
                    raise
                try:
                    os.mkdir(part, 0o700, dir_fd=descriptor)
                except FileExistsError:
                    pass
                child_descriptor = os.open(part, flags, dir_fd=descriptor)
            except OSError as exc:
                raise KaggleReceiptError(
                    f"could not safely open receipt directory component {part!r}: {exc}"
                ) from exc
            os.close(descriptor)
            descriptor = child_descriptor
            metadata = os.fstat(descriptor)
            if not stat.S_ISDIR(metadata.st_mode):
                raise KaggleReceiptError(
                    f"receipt directory component is not a directory: {part!r}"
                )
            identities.add((metadata.st_dev, metadata.st_ino))
        return descriptor, identities
    except BaseException:
        os.close(descriptor)
        raise


def _open_kaggle_package_root(
    package_root: Path,
    *,
    expected_identity: tuple[int, int] | None = None,
) -> tuple[int, tuple[int, int]]:
    try:
        package_path = Path(package_root).resolve(strict=True)
    except OSError as exc:
        raise KaggleReceiptError(f"could not resolve scorer package root: {exc}") from exc
    descriptor, _ = _open_directory_no_symlinks(package_path, create_missing=False)
    metadata = os.fstat(descriptor)
    identity = metadata.st_dev, metadata.st_ino
    if expected_identity is not None and identity != expected_identity:
        os.close(descriptor)
        raise KaggleReceiptError(
            "scorer package root changed between replay and publication"
        )
    return descriptor, identity


def capture_kaggle_package_root_identity(package_root: Path) -> tuple[int, int]:
    """Capture the scorer-package directory identity used across replay publication."""

    descriptor, identity = _open_kaggle_package_root(package_root)
    os.close(descriptor)
    return identity


def _open_expected_receipt_parent(
    parent: Path,
    *,
    expected_identity: tuple[int, int],
    package_root_identity: tuple[int, int],
) -> int:
    try:
        descriptor, identities = _open_directory_no_symlinks(
            parent,
            create_missing=False,
        )
    except OSError as exc:
        raise KaggleReceiptError(
            "receipt output directory changed or became unavailable during publication"
        ) from exc
    try:
        metadata = os.fstat(descriptor)
        identity = metadata.st_dev, metadata.st_ino
        if identity == expected_identity and package_root_identity not in identities:
            return descriptor
    except BaseException:
        os.close(descriptor)
        raise
    os.close(descriptor)
    raise KaggleReceiptError(
        "receipt output directory changed or entered the scorer package "
        "during publication"
    )


def write_new_kaggle_receipt(
    path: Path,
    receipt: dict[str, Any],
    *,
    run_json_path: Path,
    package_root: Path,
    expected_package_root_identity: tuple[int, int],
) -> None:
    """Publish with a no-replace link; later errors may leave untrusted residue."""

    content = serialize_kaggle_receipt(receipt)
    target = validate_kaggle_replay_output_path(
        run_json_path=run_json_path,
        package_root=package_root,
        out=path,
    )
    assert_not_v0_1_write(target)
    package_descriptor, _ = _open_kaggle_package_root(
        package_root,
        expected_identity=expected_package_root_identity,
    )
    parent_descriptor: int | None = None
    pre_publication_parent_descriptor: int | None = None
    publication_package_descriptor: int | None = None
    post_publication_package_descriptor: int | None = None
    post_publication_parent_descriptor: int | None = None
    temporary_descriptor: int | None = None
    temporary_identity: tuple[int, int] | None = None
    parent_identity: tuple[int, int] | None = None
    temporary_name = f".{target.name}.{os.getpid()}.{secrets.token_hex(8)}.tmp"
    try:
        parent_descriptor, parent_identities = _open_directory_no_symlinks(
            target.parent, create_missing=True
        )
        if expected_package_root_identity in parent_identities:
            raise KaggleReceiptError("receipt output directory aliases the scorer package")
        parent_metadata = os.fstat(parent_descriptor)
        parent_identity = parent_metadata.st_dev, parent_metadata.st_ino
        temporary_descriptor = os.open(
            temporary_name,
            os.O_WRONLY
            | os.O_CREAT
            | os.O_EXCL
            | getattr(os, "O_NOFOLLOW", 0),
            0o600,
            dir_fd=parent_descriptor,
        )
        opened_temporary_metadata = os.fstat(temporary_descriptor)
        temporary_identity = (
            opened_temporary_metadata.st_dev,
            opened_temporary_metadata.st_ino,
        )
        with os.fdopen(os.dup(temporary_descriptor), "wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
            temporary_metadata = os.fstat(handle.fileno())
            if (
                temporary_metadata.st_dev,
                temporary_metadata.st_ino,
            ) != temporary_identity:
                raise KaggleReceiptError(
                    "temporary receipt identity changed while its descriptor was open"
                )
        publication_package_descriptor, _ = _open_kaggle_package_root(
            package_root,
            expected_identity=expected_package_root_identity,
        )
        pre_publication_parent_descriptor = _open_expected_receipt_parent(
            target.parent,
            expected_identity=parent_identity,
            package_root_identity=expected_package_root_identity,
        )
        try:
            os.link(
                temporary_name,
                target.name,
                src_dir_fd=parent_descriptor,
                dst_dir_fd=parent_descriptor,
                follow_symlinks=False,
            )
        except OSError as link_error:
            try:
                published_metadata = os.stat(
                    target.name,
                    dir_fd=parent_descriptor,
                    follow_symlinks=False,
                )
                published_identity = (
                    published_metadata.st_dev,
                    published_metadata.st_ino,
                )
            except OSError:
                if isinstance(link_error, FileExistsError):
                    raise KaggleReceiptError(
                        f"refusing to replace existing Kaggle receipt output: {target}"
                    ) from link_error
                raise link_error
            if temporary_identity is None or published_identity != temporary_identity:
                if isinstance(link_error, FileExistsError):
                    raise KaggleReceiptError(
                        f"refusing to replace existing Kaggle receipt output: {target}"
                    ) from link_error
                raise link_error
        os.fsync(parent_descriptor)
        try:
            cleanup_metadata = os.stat(
                temporary_name,
                dir_fd=parent_descriptor,
                follow_symlinks=False,
            )
        except FileNotFoundError:
            pass
        else:
            cleanup_identity = cleanup_metadata.st_dev, cleanup_metadata.st_ino
            if temporary_identity is None or cleanup_identity != temporary_identity:
                raise KaggleReceiptError(
                    "temporary receipt path changed during publication cleanup"
                )
            os.unlink(temporary_name, dir_fd=parent_descriptor)
        os.fsync(parent_descriptor)
        post_publication_package_descriptor, _ = _open_kaggle_package_root(
            package_root,
            expected_identity=expected_package_root_identity,
        )
        post_publication_parent_descriptor = _open_expected_receipt_parent(
            target.parent,
            expected_identity=parent_identity,
            package_root_identity=expected_package_root_identity,
        )
        published_metadata = os.stat(
            target.name,
            dir_fd=parent_descriptor,
            follow_symlinks=False,
        )
        published_identity = published_metadata.st_dev, published_metadata.st_ino
        if temporary_identity is None or published_identity != temporary_identity:
            raise KaggleReceiptError("receipt output path changed during publication")
    finally:
        for descriptor in (
            temporary_descriptor,
            post_publication_parent_descriptor,
            post_publication_package_descriptor,
            pre_publication_parent_descriptor,
            publication_package_descriptor,
            parent_descriptor,
            package_descriptor,
        ):
            if descriptor is not None:
                try:
                    os.close(descriptor)
                except OSError:
                    pass
