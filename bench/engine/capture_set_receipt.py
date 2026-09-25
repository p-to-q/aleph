from __future__ import annotations

import copy
import hashlib
import json
from itertools import islice
from pathlib import Path
from typing import Any, Iterable

from .kaggle_capture import (
    CAPTURE_SCHEMA_VERSION,
    LEGACY_CAPTURE_SCHEMA_VERSION,
    expected_row_id,
    parse_capture_payload,
    prompt_utf8_sha256,
)
from .kaggle_capture_evidence import (
    REPO_ROOT,
    TARGET_PROTOCOL_VERSION,
    VerifiedCaptureBundle,
    _expected_capture_contract,
    _parse_evidence_bytes,
    verify_capture_evidence,
)
from .schema_validation import SchemaValidationError, load_schema, validate


RECEIPT_SCHEMA_PATH = (
    REPO_ROOT / "schemas/v0.2/aleph-bench-capture-set-receipt.schema.json"
)
LEGACY_RECEIPT_SCHEMA_PATH = (
    REPO_ROOT
    / "schemas/v0.2/aleph-bench-capture-set-receipt-v1.0.schema.json"
)
LEGACY_TRANSPORT_CANARY_SCOPE_PLAN_PATH = (
    REPO_ROOT
    / "bench/config/capture_scope_plan-v0.2-transport-canary-task-v3.json"
)
AUTHORITY_REGISTRY_PATH = (
    REPO_ROOT / "bench/config/capture_set_authority-v0.2.json"
)
LEGACY_RECEIPT_SCHEMA_VERSION = "1.0.0"
RECEIPT_SCHEMA_VERSION = "1.1.0"
LEGACY_SCOPE_PLAN_SCHEMA_VERSION = "1.0.0"
SCOPE_PLAN_SCHEMA_VERSION = "1.1.0"
MODEL_MAPPING_SCHEMA_VERSION = "1.0.0"
ARTIFACT_KIND = "aleph_bench_capture_set_receipt"
SCOPE_PLAN_ARTIFACT_KIND = "aleph_bench_capture_scope_plan"
MODEL_MAPPING_ARTIFACT_KIND = "aleph_bench_canonical_model_mapping"
AUTHORITY_REGISTRY_ARTIFACT_KIND = (
    "aleph_bench_capture_set_authority_registry"
)
RECEIPT_ID_PREFIX = "aleph-bench-capture-set-receipt-v1-artifact-"
SCOPE_PLAN_ID_PREFIX = "aleph-bench-capture-scope-plan-v1-artifact-"
MODEL_MAPPING_ID_PREFIX = (
    "aleph-bench-canonical-model-mapping-v1-artifact-"
)
MAX_SCOPE_PLAN_BYTES = 32 * 1024 * 1024
MAX_RECEIPT_BYTES = 4 * 1024 * 1024
MAX_AUTHORITY_REGISTRY_BYTES = 1_048_576
LEGACY_TRANSPORT_CANARY_SCOPE_PLAN_SHA256 = (
    "57b1cf86a41bc4fadcf07e68592ac1a0d9ec874a40477caf53c6f19adba238d0"
)
AUTHORITY_REGISTRY_LOGICAL_PATH = (
    "bench/config/capture_set_authority-v0.2.json"
)
FORBIDDEN_ARTIFACT_FIELDS = frozenset(
    {"score", "scores", "metric", "metrics", "BenchManifest", "BenchResult"}
)


class CaptureSetReceiptError(ValueError):
    """Raised when capture bundles cannot form one exact score-free set."""


def _fail(message: str) -> None:
    raise CaptureSetReceiptError(message)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical_json_bytes(value: Any, *, role: str) -> bytes:
    try:
        return json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("ascii")
    except (TypeError, ValueError, UnicodeError, RecursionError):
        raise CaptureSetReceiptError(
            f"{role} cannot be canonically encoded"
        ) from None


def _canonical_json_equal(left: Any, right: Any, *, role: str) -> bool:
    """Compare the exact JSON identities used by the content digests.

    Python considers ``0``, ``0.0``, and ``-0.0`` equal even though this
    module's canonical JSON encoding gives them different artifact bytes.
    Identity gates must use the artifact encoding, not Python value equality.
    """

    return _canonical_json_bytes(
        left, role=f"{role} left value"
    ) == _canonical_json_bytes(right, role=f"{role} right value")


def _artifact_id(value: dict[str, Any], prefix: str, *, role: str) -> str:
    body = {key: child for key, child in value.items() if key != "id"}
    return prefix + _sha256(_canonical_json_bytes(body, role=role))


def _reject_forbidden_fields(value: Any) -> None:
    active: set[int] = set()
    stack: list[tuple[Any, int, bool]] = [(value, 0, False)]
    visited = 0
    while stack:
        current, depth, exiting = stack.pop()
        if not isinstance(current, (dict, list)):
            continue
        identity = id(current)
        if exiting:
            active.remove(identity)
            continue
        if identity in active:
            _fail("capture-set artifact contains a cyclic value")
        if depth > 128:
            _fail("capture-set artifact exceeds the nesting limit")
        visited += 1
        if visited > 100_000:
            _fail("capture-set artifact exceeds the node limit")
        active.add(identity)
        stack.append((current, depth, True))
        if isinstance(current, dict):
            forbidden = FORBIDDEN_ARTIFACT_FIELDS.intersection(current)
            if forbidden:
                _fail(
                    "capture-set artifacts cannot contain score, metric, "
                    "BenchManifest, or BenchResult fields"
                )
            children = current.values()
        else:
            children = current
        for child in reversed(list(children)):
            stack.append((child, depth + 1, False))


def _strict_keys(value: Any, expected: set[str], *, role: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != expected:
        _fail(f"{role} has invalid fields")
    return value


def _nonempty_string(value: Any, *, role: str, maximum: int = 1024) -> str:
    if not isinstance(value, str) or not value or len(value) > maximum:
        _fail(f"{role} must be one bounded non-empty string")
    try:
        value.encode("utf-8", errors="strict")
    except UnicodeEncodeError:
        _fail(f"{role} is not strict UTF-8")
    return value


def _scope_counts(calls: list[dict[str, Any]]) -> dict[str, Any]:
    prompt_reruns: dict[tuple[str, str], set[int]] = {}
    item_prompts: dict[str, set[str]] = {}
    reruns: set[int] = set()
    for call in calls:
        item_id = call["itemId"]
        prompt_id = call["promptId"]
        rerun = call["rerunIndex"]
        prompt_reruns.setdefault((item_id, prompt_id), set()).add(rerun)
        item_prompts.setdefault(item_id, set()).add(prompt_id)
        reruns.add(rerun)
    complete_items = 0
    for item_id, prompts in item_prompts.items():
        if len(prompts) == 6 and all(
            prompt_reruns[(item_id, prompt_id)] == set(range(5))
            for prompt_id in prompts
        ):
            complete_items += 1
    return {
        "callCount": len(calls),
        "uniquePromptCount": len(prompt_reruns),
        "touchedItemCount": len(item_prompts),
        "completeCanonicalItemCount": complete_items,
        "rerunIndices": sorted(reruns),
        "orderedRowIds": [call["rowId"] for call in calls],
    }


def _verify_scope_contract(scope_kind: str, calls: list[dict[str, Any]]) -> dict[str, Any]:
    coverage = _scope_counts(calls)
    expected = _scope_contract_counts(scope_kind)
    observed = {key: coverage[key] for key in expected}
    if observed != expected:
        _fail(f"{scope_kind} scope contract is incomplete or over-complete")
    return coverage


def _scope_contract_counts(scope_kind: str) -> dict[str, Any]:
    return (
        {
            "callCount": 6,
            "uniquePromptCount": 6,
            "touchedItemCount": 3,
            "completeCanonicalItemCount": 0,
            "rerunIndices": [0],
        }
        if scope_kind == "transportCanary"
        else {
            "callCount": 900,
            "uniquePromptCount": 180,
            "touchedItemCount": 30,
            "completeCanonicalItemCount": 30,
            "rerunIndices": [0, 1, 2, 3, 4],
        }
    )


def _verify_scope_call(call: Any, *, role: str) -> dict[str, Any]:
    record = _strict_keys(
        call,
        {
            "rowId",
            "itemId",
            "promptId",
            "rerunIndex",
            "conversationName",
            "promptText",
            "promptUtf8Sha256",
            "promptCodePointCount",
        },
        role=role,
    )
    item_id = _nonempty_string(record["itemId"], role=f"{role}.itemId", maximum=128)
    prompt_id = _nonempty_string(
        record["promptId"], role=f"{role}.promptId", maximum=128
    )
    rerun_index = record["rerunIndex"]
    if (
        isinstance(rerun_index, bool)
        or not isinstance(rerun_index, int)
        or not 0 <= rerun_index <= 4
    ):
        _fail(f"{role}.rerunIndex is invalid")
    if record["rowId"] != expected_row_id(item_id, prompt_id, rerun_index):
        _fail(f"{role}.rowId disagrees with its coordinate")
    _nonempty_string(
        record["conversationName"],
        role=f"{role}.conversationName",
        maximum=256,
    )
    prompt = record["promptText"]
    if not isinstance(prompt, str) or len(prompt) > 16_384:
        _fail(f"{role}.promptText is invalid")
    try:
        prompt_digest = prompt_utf8_sha256(prompt)
    except ValueError as exc:
        raise CaptureSetReceiptError(f"{role}.promptText is invalid") from exc
    if record["promptUtf8Sha256"] != prompt_digest:
        _fail(f"{role}.promptUtf8Sha256 disagrees with promptText")
    if record["promptCodePointCount"] != len(prompt):
        _fail(f"{role}.promptCodePointCount disagrees with promptText")
    return record


def _scope_plan_id(plan: dict[str, Any]) -> str:
    return _artifact_id(
        plan,
        SCOPE_PLAN_ID_PREFIX,
        role="capture scope plan",
    )


def transport_canary_scope_plan() -> dict[str, Any]:
    """Return the exact authority-generated scope for the current six-call task."""

    expected, _source = _expected_capture_contract()
    plan = {
        "scopePlanSchemaVersion": SCOPE_PLAN_SCHEMA_VERSION,
        "artifactKind": SCOPE_PLAN_ARTIFACT_KIND,
        "targetProtocolVersion": TARGET_PROTOCOL_VERSION,
        "scopeKind": "transportCanary",
        "datasetIdentity": copy.deepcopy(expected["datasetIdentity"]),
        "packageIdentity": copy.deepcopy(expected["packageIdentity"]),
        "callPlanIdentity": copy.deepcopy(expected["callPlanIdentity"]),
        "requestPolicy": copy.deepcopy(expected["requestPolicy"]),
        "orderedCalls": copy.deepcopy(expected["shard"]["plannedCalls"]),
        "id": "",
    }
    plan["id"] = _scope_plan_id(plan)
    return plan


def legacy_transport_canary_scope_plan() -> dict[str, Any]:
    """Return the immutable Task-v3 scope used by capture schema 1.1 evidence."""

    try:
        data = LEGACY_TRANSPORT_CANARY_SCOPE_PLAN_PATH.read_bytes()
    except OSError:
        raise CaptureSetReceiptError(
            "cannot read legacy transport-canary scope plan"
        ) from None
    if (
        not data
        or len(data) > MAX_SCOPE_PLAN_BYTES
        or _sha256(data) != LEGACY_TRANSPORT_CANARY_SCOPE_PLAN_SHA256
    ):
        _fail("legacy transport-canary scope plan bytes drifted")
    try:
        plan = json.loads(data.decode("utf-8", errors="strict"))
    except (
        UnicodeDecodeError,
        json.JSONDecodeError,
        ValueError,
        RecursionError,
        OverflowError,
    ):
        _fail("legacy transport-canary scope plan is not strict JSON")
    if not isinstance(plan, dict):
        _fail("legacy transport-canary scope plan must be a JSON object")
    return plan


def _transport_canary_scope_plan_for_receipt(
    receipt_schema_version: str,
) -> dict[str, Any]:
    if receipt_schema_version == LEGACY_RECEIPT_SCHEMA_VERSION:
        return legacy_transport_canary_scope_plan()
    if receipt_schema_version == RECEIPT_SCHEMA_VERSION:
        return transport_canary_scope_plan()
    _fail("capture-set receipt schema version is unsupported")


def _verify_scope_plan(plan: Any) -> dict[str, Any]:
    record = _strict_keys(
        plan,
        {
            "scopePlanSchemaVersion",
            "artifactKind",
            "targetProtocolVersion",
            "scopeKind",
            "datasetIdentity",
            "packageIdentity",
            "callPlanIdentity",
            "requestPolicy",
            "orderedCalls",
            "id",
        },
        role="capture scope plan",
    )
    _reject_forbidden_fields(record)
    encoded = _canonical_json_bytes(record, role="capture scope plan")
    if len(encoded) > MAX_SCOPE_PLAN_BYTES:
        _fail("capture scope plan exceeds the safety limit")
    scope_plan_schema_version = record["scopePlanSchemaVersion"]
    if scope_plan_schema_version not in {
        LEGACY_SCOPE_PLAN_SCHEMA_VERSION,
        SCOPE_PLAN_SCHEMA_VERSION,
    }:
        _fail("capture scope plan schema version is unsupported")
    if record["artifactKind"] != SCOPE_PLAN_ARTIFACT_KIND:
        _fail("capture scope plan artifact kind is invalid")
    if record["targetProtocolVersion"] != TARGET_PROTOCOL_VERSION:
        _fail("capture scope plan targets another protocol")
    scope_kind = record["scopeKind"]
    if scope_kind not in {"transportCanary", "canonicalFull"}:
        _fail("capture scope plan kind is unsupported")
    for role in (
        "datasetIdentity",
        "packageIdentity",
        "callPlanIdentity",
        "requestPolicy",
    ):
        if not isinstance(record[role], dict):
            _fail(f"capture scope plan {role} must be an object")
    has_timeout = "transportTimeoutSeconds" in record["requestPolicy"]
    if scope_plan_schema_version == LEGACY_SCOPE_PLAN_SCHEMA_VERSION:
        if has_timeout:
            _fail("legacy capture scope plan contains an unversioned timeout")
    elif not has_timeout:
        _fail("capture scope plan schema 1.1 requires a timeout")
    calls = record["orderedCalls"]
    if not isinstance(calls, list) or not 1 <= len(calls) <= 900:
        _fail("capture scope plan calls are invalid")
    if (
        record["callPlanIdentity"].get("totalPlannedCallCount") != 900
        or record["callPlanIdentity"].get("rerunsPerPrompt") != 5
    ):
        _fail("capture scope plan disagrees with the frozen 900-call policy")
    row_ids: set[str] = set()
    coordinates: set[tuple[str, str, int]] = set()
    conversations: set[str] = set()
    for index, raw_call in enumerate(calls):
        call = _verify_scope_call(raw_call, role=f"orderedCalls[{index}]")
        row_id = call["rowId"]
        coordinate = (call["itemId"], call["promptId"], call["rerunIndex"])
        conversation = call["conversationName"]
        if row_id in row_ids:
            _fail("capture scope plan has a duplicate row id")
        if coordinate in coordinates:
            _fail("capture scope plan has a duplicate prompt/rerun coordinate")
        if conversation in conversations:
            _fail("capture scope plan has a duplicate conversation name")
        row_ids.add(row_id)
        coordinates.add(coordinate)
        conversations.add(conversation)
    _verify_scope_contract(scope_kind, calls)
    if record["id"] != _scope_plan_id(record):
        _fail("capture scope plan artifact id mismatch")
    if scope_kind == "transportCanary":
        frozen_plan = (
            legacy_transport_canary_scope_plan()
            if scope_plan_schema_version == LEGACY_SCOPE_PLAN_SCHEMA_VERSION
            else transport_canary_scope_plan()
        )
        if not _canonical_json_equal(
            record,
            frozen_plan,
            role="frozen transport-canary scope plan",
        ):
            _fail(
                "transport-canary scope differs from its frozen generated authority"
            )
    return record


def _model_mapping_id(mapping: dict[str, Any]) -> str:
    return _artifact_id(
        mapping,
        MODEL_MAPPING_ID_PREFIX,
        role="canonical model mapping",
    )


def _verify_model_mapping(mapping: Any) -> dict[str, Any]:
    record = _strict_keys(
        mapping,
        {
            "mappingSchemaVersion",
            "artifactKind",
            "platform",
            "scheduledSlug",
            "runtimeObservedProxySlug",
            "canonicalModelId",
            "providerRevision",
            "id",
        },
        role="canonical model mapping",
    )
    _reject_forbidden_fields(record)
    if record["mappingSchemaVersion"] != MODEL_MAPPING_SCHEMA_VERSION:
        _fail("canonical model mapping schema version is unsupported")
    if record["artifactKind"] != MODEL_MAPPING_ARTIFACT_KIND:
        _fail("canonical model mapping artifact kind is invalid")
    if record["platform"] != "kaggle":
        _fail("canonical model mapping platform is invalid")
    for field in (
        "scheduledSlug",
        "runtimeObservedProxySlug",
        "canonicalModelId",
    ):
        _nonempty_string(record[field], role=f"canonical model mapping {field}", maximum=300)
    if record["providerRevision"] is not None:
        _nonempty_string(
            record["providerRevision"],
            role="canonical model mapping providerRevision",
            maximum=300,
        )
    if record["id"] != _model_mapping_id(record):
        _fail("canonical model mapping artifact id mismatch")
    return record


def _registry_duplicate_pairs(
    pairs: list[tuple[str, Any]],
) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, child in pairs:
        if key in value:
            _fail("capture-set authority registry contains a duplicate JSON key")
        value[key] = child
    return value


def _registry_constant(_value: str) -> None:
    _fail("capture-set authority registry contains a non-finite JSON constant")


def _load_authority_registry() -> tuple[dict[str, Any], bytes]:
    try:
        data = AUTHORITY_REGISTRY_PATH.read_bytes()
    except OSError:
        raise CaptureSetReceiptError(
            "cannot read capture-set authority registry"
        ) from None
    if not data or len(data) > MAX_AUTHORITY_REGISTRY_BYTES:
        _fail("capture-set authority registry exceeds the safety limit")
    try:
        registry = json.loads(
            data.decode("utf-8", errors="strict"),
            object_pairs_hook=_registry_duplicate_pairs,
            parse_constant=_registry_constant,
        )
    except CaptureSetReceiptError:
        raise
    except (
        UnicodeDecodeError,
        json.JSONDecodeError,
        ValueError,
        RecursionError,
        OverflowError,
    ):
        _fail("capture-set authority registry is not bounded strict JSON")
    record = _strict_keys(
        registry,
        {
            "registrySchemaVersion",
            "artifactKind",
            "targetProtocolVersion",
            "canonicalScoringAuthorities",
        },
        role="capture-set authority registry",
    )
    if record["registrySchemaVersion"] != "1.0.0":
        _fail("capture-set authority registry schema version is unsupported")
    if record["artifactKind"] != AUTHORITY_REGISTRY_ARTIFACT_KIND:
        _fail("capture-set authority registry artifact kind is invalid")
    if record["targetProtocolVersion"] != TARGET_PROTOCOL_VERSION:
        _fail("capture-set authority registry targets another protocol")
    entries = record["canonicalScoringAuthorities"]
    if not isinstance(entries, list) or len(entries) > 10_000:
        _fail("capture-set authority registry entries are invalid")
    seen_pairs: set[tuple[str, str]] = set()
    for index, raw_entry in enumerate(entries):
        entry = _strict_keys(
            raw_entry,
            {"scopePlanId", "canonicalModelMappingId", "requestPolicySha256"},
            role=f"capture-set authority registry entry {index}",
        )
        for field in entry:
            _nonempty_string(
                entry[field],
                role=f"capture-set authority registry entry {index}.{field}",
                maximum=256,
            )
        pair = (entry["scopePlanId"], entry["canonicalModelMappingId"])
        if pair in seen_pairs:
            _fail("capture-set authority registry has a duplicate authority pair")
        seen_pairs.add(pair)
    return record, data


def _model_identity(
    evidence: dict[str, Any], payload: dict[str, Any]
) -> dict[str, Any]:
    catalog = evidence.get("modelCatalogBinding")
    observation = payload["modelObservation"]
    return {
        "platform": "kaggle",
        "taskRunModelSlug": evidence["run"]["modelVersionSlug"],
        "scheduledSlug": catalog["scheduledSlug"] if catalog is not None else None,
        "runtimeProxySlug": observation["slug"],
        "benchmarkModelId": (
            catalog["benchmarkModelId"] if catalog is not None else None
        ),
        "benchmarkModelVersionId": (
            catalog["benchmarkModelVersionId"] if catalog is not None else None
        ),
        "modelObservationSha256": _sha256(
            _canonical_json_bytes(observation, role="model observation")
        ),
    }


def _task_platform_identity(evidence: dict[str, Any]) -> dict[str, Any]:
    task = evidence["task"]
    return {
        "owner": task["owner"],
        "slug": task["slug"],
        "version": task["version"],
        "sourceKernelId": task["sourceKernelId"],
        "datasets": copy.deepcopy(task["datasets"]),
        "taskReadbackSha256": _sha256(
            _canonical_json_bytes(task, role="Task platform readback")
        ),
    }


def _reverify_bundle(
    bundle: VerifiedCaptureBundle,
) -> tuple[dict[str, Any], dict[str, Any]]:
    if not isinstance(bundle, VerifiedCaptureBundle):
        _fail("capture-set members must come from load_verified_capture_bundle")
    evidence = _parse_evidence_bytes(bundle.evidence_bytes)
    expected_name = (
        f"{evidence['task']['slug']}-v{evidence['task']['version']}"
        f"-run-{evidence['run']['id']}-evidence.json"
    )
    if bundle.evidence_path.name != expected_name:
        _fail("capture-set member evidence file name disagrees with its run")
    verify_capture_evidence(
        evidence,
        archive_bytes=bundle.archive_bytes,
        payload_bytes=bundle.payload_bytes,
        source_bytes=bundle.source_bytes,
        dispatch_journal_bytes=bundle.dispatch_journal_bytes,
    )
    payload = parse_capture_payload(bundle.payload_bytes)
    if evidence["assemblyEligible"] is not True:
        _fail("capture-set member is not assembly eligible")
    return evidence, payload


def _same(value: Any, expected: Any, *, role: str) -> None:
    if not _canonical_json_equal(value, expected, role=role):
        _fail(f"capture-set member {role} drifted")


def _receipt_schema_version_for_snapshots(
    snapshots: list[tuple[dict[str, Any], dict[str, Any]]],
) -> str:
    generations = {
        (
            payload.get("captureSchemaVersion"),
            payload.get("taskIdentity", {}).get("version"),
        )
        for _evidence, payload in snapshots
    }
    if len(generations) != 1:
        _fail("capture set mixes capture schema or Task generations")
    generation = generations.pop()
    if generation == (LEGACY_CAPTURE_SCHEMA_VERSION, "3"):
        return LEGACY_RECEIPT_SCHEMA_VERSION
    if generation == (CAPTURE_SCHEMA_VERSION, "4"):
        return RECEIPT_SCHEMA_VERSION
    _fail("capture set uses an unsupported capture schema and Task generation")


def _canonical_policy_compatible(
    request_policy: dict[str, Any], call_plan: dict[str, Any]
) -> bool:
    # v0.2 itself reviews only temperature=0, max_tokens=512, and five reruns.
    # The exact remaining transport fields are authorized by the registered
    # request-policy digest, never inferred here.
    return (
        request_policy.get("conversationIsolation")
        == "oneNamedChatPerPromptAndRerun"
        and request_policy.get("transportRetries") == 0
        and request_policy.get("maxAttemptsPerCall") == 1
        and request_policy.get("temperature") == 0
        and request_policy.get("maxOutputTokens") == 512
        and call_plan.get("rerunsPerPrompt") == 5
        and call_plan.get("totalPlannedCallCount") == 900
    )


def _authority_match(
    registry: dict[str, Any],
    *,
    scope_plan_id: str,
    model_mapping_id: str | None,
    request_policy: dict[str, Any],
) -> bool:
    if model_mapping_id is None:
        return False
    request_digest = _sha256(
        _canonical_json_bytes(request_policy, role="request policy")
    )
    return any(
        entry
        == {
            "scopePlanId": scope_plan_id,
            "canonicalModelMappingId": model_mapping_id,
            "requestPolicySha256": request_digest,
        }
        for entry in registry["canonicalScoringAuthorities"]
    )


def _eligibility_blockers(
    *,
    scope_kind: str,
    request_policy: dict[str, Any],
    call_plan: dict[str, Any],
    mapping: dict[str, Any] | None,
    authority_matched: bool,
) -> list[str]:
    blockers: list[str] = []
    if scope_kind != "canonicalFull":
        blockers.append("scopeIsNotCanonicalFull")
    if not _canonical_policy_compatible(request_policy, call_plan):
        blockers.append("requestPolicyIsNotProtocolCompatible")
    if mapping is None:
        blockers.append("canonicalModelMappingMissing")
    if not authority_matched:
        blockers.append("canonicalAuthorityNotRegistered")
    return blockers


def _member_record(
    bundle: VerifiedCaptureBundle,
    evidence: dict[str, Any],
    payload: dict[str, Any],
) -> dict[str, Any]:
    catalog = evidence.get("modelCatalogBinding")
    dispatch = catalog["dispatchJournal"] if catalog is not None else None
    return {
        "evidence": {
            "id": evidence["id"],
            "file": bundle.evidence_path.name,
            "bytes": len(bundle.evidence_bytes),
            "sha256": _sha256(bundle.evidence_bytes),
        },
        "payload": {
            "id": payload["id"],
            "file": evidence["payload"]["file"],
            "bytes": len(bundle.payload_bytes),
            "sha256": _sha256(bundle.payload_bytes),
        },
        "archive": {
            "file": evidence["archive"]["file"],
            "bytes": len(bundle.archive_bytes),
            "sha256": _sha256(bundle.archive_bytes),
        },
        "source": {
            "file": evidence["source"]["file"],
            "bytes": len(bundle.source_bytes),
            "sha256": _sha256(bundle.source_bytes),
        },
        "dispatchJournal": (
            {
                "file": dispatch["file"],
                "bytes": len(bundle.dispatch_journal_bytes),
                "sha256": _sha256(bundle.dispatch_journal_bytes),
            }
            if dispatch is not None and bundle.dispatch_journal_bytes is not None
            else None
        ),
        "runId": evidence["run"]["id"],
        "operationId": catalog["operationId"] if catalog is not None else None,
        "modelCatalogBindingSha256": (
            _sha256(
                _canonical_json_bytes(catalog, role="model catalog binding")
            )
            if catalog is not None
            else None
        ),
        "shard": {
            "id": payload["shard"]["id"],
            "fullShardPlanSha256": payload["shard"]["fullShardPlanSha256"],
            "coverageSha256": payload["shard"]["coverageSha256"],
            "rowIds": [
                call["rowId"] for call in payload["shard"]["plannedCalls"]
            ],
        },
    }


def assemble_capture_set_receipt(
    bundles: Iterable[VerifiedCaptureBundle],
    *,
    scope_plan: dict[str, Any],
    canonical_model_mapping: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Assemble verified snapshots into one deterministic, score-free receipt."""

    plan = _verify_scope_plan(copy.deepcopy(scope_plan))
    mapping = (
        _verify_model_mapping(copy.deepcopy(canonical_model_mapping))
        if canonical_model_mapping is not None
        else None
    )
    registry, registry_bytes = _load_authority_registry()
    bundle_list = list(islice(iter(bundles), 901))
    if not bundle_list or len(bundle_list) > 900:
        _fail("capture set must contain between one and 900 explicit bundles")
    snapshots = [_reverify_bundle(bundle) for bundle in bundle_list]
    receipt_schema_version = _receipt_schema_version_for_snapshots(snapshots)
    expected_scope_plan_schema_version = (
        LEGACY_SCOPE_PLAN_SCHEMA_VERSION
        if receipt_schema_version == LEGACY_RECEIPT_SCHEMA_VERSION
        else SCOPE_PLAN_SCHEMA_VERSION
    )
    if plan["scopePlanSchemaVersion"] != expected_scope_plan_schema_version:
        _fail("capture scope plan schema does not match the capture generation")
    if plan["scopeKind"] == "transportCanary":
        expected_plan = _transport_canary_scope_plan_for_receipt(
            receipt_schema_version
        )
        if not _canonical_json_equal(
            plan,
            expected_plan,
            role="capture-generation transport-canary scope plan",
        ):
            _fail("transport-canary scope does not match the capture generation")

    first_evidence, first_payload = snapshots[0]
    dataset = first_payload["datasetIdentity"]
    package = first_payload["packageIdentity"]
    call_plan = first_payload["callPlanIdentity"]
    request_policy = first_payload["requestPolicy"]
    task_platform = _task_platform_identity(first_evidence)
    task_source = first_payload["taskIdentity"]
    model = _model_identity(first_evidence, first_payload)
    model_observation = first_payload["modelObservation"]
    runtime = first_payload["runtimeObservation"]

    for evidence, payload in snapshots:
        _same(payload["datasetIdentity"], dataset, role="dataset identity")
        _same(payload["packageIdentity"], package, role="package identity")
        _same(payload["callPlanIdentity"], call_plan, role="call-plan identity")
        _same(payload["requestPolicy"], request_policy, role="request policy")
        _same(
            _task_platform_identity(evidence),
            task_platform,
            role="Task platform version",
        )
        _same(payload["taskIdentity"], task_source, role="task source identity")
        _same(_model_identity(evidence, payload), model, role="model identity")
        _same(
            payload["modelObservation"],
            model_observation,
            role="runtime model observation",
        )
        _same(payload["runtimeObservation"], runtime, role="runtime observation")

    for field, observed in (
        ("datasetIdentity", dataset),
        ("packageIdentity", package),
        ("callPlanIdentity", call_plan),
        ("requestPolicy", request_policy),
    ):
        if not _canonical_json_equal(
            plan[field], observed, role=f"scope-plan {field}"
        ):
            _fail(f"capture set differs from scope-plan {field}")

    if mapping is not None:
        if model["scheduledSlug"] is None:
            _fail("canonical model mapping requires catalog-bound capture evidence")
        if (
            mapping["scheduledSlug"] != model["scheduledSlug"]
            or mapping["runtimeObservedProxySlug"] != model["runtimeProxySlug"]
        ):
            _fail("canonical model mapping differs from observed model identities")

    evidence_ids: set[str] = set()
    payload_ids: set[str] = set()
    run_ids: set[int] = set()
    shard_ids: set[str] = set()
    row_ids: set[str] = set()
    coordinates: set[tuple[str, str, int]] = set()
    conversations: set[str] = set()
    plan_calls = plan["orderedCalls"]
    plan_index = {call["rowId"]: index for index, call in enumerate(plan_calls)}
    ordered_members: list[tuple[int, dict[str, Any]]] = []

    for bundle, (evidence, payload) in zip(bundle_list, snapshots):
        for value, seen, role in (
            (evidence["id"], evidence_ids, "evidence id"),
            (payload["id"], payload_ids, "payload id"),
            (evidence["run"]["id"], run_ids, "run id"),
            (payload["shard"]["id"], shard_ids, "shard id"),
        ):
            if value in seen:
                _fail(f"capture set has a duplicate {role}")
            seen.add(value)

        member_indices: list[int] = []
        for call in payload["shard"]["plannedCalls"]:
            row_id = call["rowId"]
            coordinate = (call["itemId"], call["promptId"], call["rerunIndex"])
            conversation = call["conversationName"]
            if row_id in row_ids:
                _fail("capture set has a duplicate or overlapping row id")
            if coordinate in coordinates:
                _fail("capture set has a duplicate prompt/rerun coordinate")
            if conversation in conversations:
                _fail("capture set has a duplicate conversation name")
            if row_id not in plan_index or not _canonical_json_equal(
                plan_calls[plan_index[row_id]],
                call,
                role="scope-plan call",
            ):
                _fail("capture set contains an unplanned or drifted call")
            row_ids.add(row_id)
            coordinates.add(coordinate)
            conversations.add(conversation)
            member_indices.append(plan_index[row_id])
        if member_indices != sorted(member_indices):
            _fail("capture shard call order drifted from the scope plan")
        if member_indices != list(
            range(member_indices[0], member_indices[-1] + 1)
        ):
            _fail("capture shard is not one contiguous scope-plan slice")
        ordered_members.append(
            (
                member_indices[0],
                _member_record(
                    bundle,
                    evidence,
                    payload,
                ),
            )
        )

    expected_row_ids = [call["rowId"] for call in plan_calls]
    if len(row_ids) != len(expected_row_ids) or row_ids != set(expected_row_ids):
        _fail("capture set has a gap or extra row relative to the scope plan")
    ordered_members.sort(key=lambda pair: pair[0])
    flattened_rows = [
        row_id
        for _start, member in ordered_members
        for row_id in member["shard"]["rowIds"]
    ]
    if flattened_rows != expected_row_ids:
        _fail("capture-set shard ordering does not reproduce the scope plan")

    coverage = _verify_scope_contract(plan["scopeKind"], plan_calls)
    authority_matched = _authority_match(
        registry,
        scope_plan_id=plan["id"],
        model_mapping_id=mapping["id"] if mapping is not None else None,
        request_policy=request_policy,
    )
    blockers = _eligibility_blockers(
        scope_kind=plan["scopeKind"],
        request_policy=request_policy,
        call_plan=call_plan,
        mapping=mapping,
        authority_matched=authority_matched,
    )
    authority_status = (
        "frozenTransportCanary"
        if plan["scopeKind"] == "transportCanary"
        else "registeredCanonical"
        if authority_matched
        else "candidateUnregistered"
    )
    receipt = {
        "receiptSchemaVersion": receipt_schema_version,
        "artifactKind": ARTIFACT_KIND,
        "targetProtocolVersion": TARGET_PROTOCOL_VERSION,
        "scoreFree": True,
        "scopeKind": plan["scopeKind"],
        "scopePlan": {
            "id": plan["id"],
            "orderedCallCount": len(plan_calls),
            "authorityStatus": authority_status,
        },
        "authorityRegistry": {
            "file": AUTHORITY_REGISTRY_LOGICAL_PATH,
            "bytes": len(registry_bytes),
            "sha256": _sha256(registry_bytes),
            "matched": authority_matched,
        },
        "canonicalModelMapping": (
            {
                key: mapping[key]
                for key in (
                    "id",
                    "platform",
                    "scheduledSlug",
                    "runtimeObservedProxySlug",
                    "canonicalModelId",
                    "providerRevision",
                )
            }
            if mapping is not None
            else None
        ),
        "canonicalScoringInputEligible": not blockers,
        "canonicalScoringInputBlockers": blockers,
        "leaderboardEligible": False,
        "resultEligible": False,
        "publicationEligible": False,
        "identities": {
            "dataset": copy.deepcopy(dataset),
            "package": copy.deepcopy(package),
            "callPlan": copy.deepcopy(call_plan),
            "requestPolicy": copy.deepcopy(request_policy),
            "taskPlatform": copy.deepcopy(task_platform),
            "taskSource": copy.deepcopy(task_source),
            "model": copy.deepcopy(model),
            "runtime": copy.deepcopy(runtime),
        },
        "coverage": coverage,
        "members": [member for _start, member in ordered_members],
        "id": "",
    }
    receipt["id"] = _artifact_id(
        receipt,
        RECEIPT_ID_PREFIX,
        role="capture-set receipt",
    )
    _validate_receipt_shape(receipt)
    return receipt


def _validate_receipt_self_consistency(receipt: dict[str, Any]) -> None:
    scope_kind = receipt["scopeKind"]
    coverage = receipt["coverage"]
    expected_counts = _scope_contract_counts(scope_kind)
    observed_counts = {key: coverage[key] for key in expected_counts}
    if observed_counts != expected_counts:
        _fail("capture-set receipt coverage disagrees with its scope kind")
    if receipt["scopePlan"]["orderedCallCount"] != expected_counts["callCount"]:
        _fail("capture-set receipt scope-plan count disagrees with its scope kind")
    if len(coverage["orderedRowIds"]) != expected_counts["callCount"]:
        _fail("capture-set receipt ordered rows disagree with its scope kind")

    identities = receipt["identities"]
    call_plan_digest = identities["callPlan"]["fullShardPlanSha256"]
    model = identities["model"]
    model_catalog_values = (
        model["scheduledSlug"],
        model["benchmarkModelId"],
        model["benchmarkModelVersionId"],
    )
    catalog_bound = all(value is not None for value in model_catalog_values)
    catalog_empty = all(value is None for value in model_catalog_values)
    if not catalog_bound and not catalog_empty:
        _fail("capture-set receipt model catalog identity is inconsistent")

    seen_evidence_ids: set[str] = set()
    seen_payload_ids: set[str] = set()
    seen_run_ids: set[int] = set()
    seen_shard_ids: set[str] = set()
    flattened_rows: list[str] = []
    for member in receipt["members"]:
        for value, seen, role in (
            (member["evidence"]["id"], seen_evidence_ids, "evidence id"),
            (member["payload"]["id"], seen_payload_ids, "payload id"),
            (member["runId"], seen_run_ids, "run id"),
            (member["shard"]["id"], seen_shard_ids, "shard id"),
        ):
            if value in seen:
                _fail(f"capture-set receipt has a duplicate {role}")
            seen.add(value)
        if member["shard"]["fullShardPlanSha256"] != call_plan_digest:
            _fail("capture-set receipt member full-shard-plan binding drifted")
        member_catalog_bound = all(
            value is not None
            for value in (
                member["dispatchJournal"],
                member["operationId"],
                member["modelCatalogBindingSha256"],
            )
        )
        member_catalog_empty = all(
            value is None
            for value in (
                member["dispatchJournal"],
                member["operationId"],
                member["modelCatalogBindingSha256"],
            )
        )
        if (not member_catalog_bound and not member_catalog_empty) or (
            member_catalog_bound is not catalog_bound
        ):
            _fail("capture-set receipt member model-catalog binding is inconsistent")
        flattened_rows.extend(member["shard"]["rowIds"])

    if flattened_rows != coverage["orderedRowIds"]:
        _fail("capture-set receipt member rows disagree with ordered coverage")

    mapping = receipt["canonicalModelMapping"]
    if mapping is not None:
        full_mapping = {
            "mappingSchemaVersion": MODEL_MAPPING_SCHEMA_VERSION,
            "artifactKind": MODEL_MAPPING_ARTIFACT_KIND,
            **copy.deepcopy(mapping),
        }
        _verify_model_mapping(full_mapping)
        if (
            mapping["platform"] != model["platform"]
            or mapping["scheduledSlug"] != model["scheduledSlug"]
            or mapping["runtimeObservedProxySlug"] != model["runtimeProxySlug"]
        ):
            _fail(
                "capture-set receipt canonical model mapping differs from "
                "its observed model identities"
            )

    if scope_kind == "transportCanary":
        frozen = _transport_canary_scope_plan_for_receipt(
            receipt["receiptSchemaVersion"]
        )
        if receipt["scopePlan"]["id"] != frozen["id"]:
            _fail("capture-set receipt transport-canary scope id is not frozen")
        frozen_rows = [call["rowId"] for call in frozen["orderedCalls"]]
        if coverage["orderedRowIds"] != frozen_rows:
            _fail("capture-set receipt transport-canary rows are not frozen")
        for receipt_field, plan_field in (
            ("dataset", "datasetIdentity"),
            ("package", "packageIdentity"),
            ("callPlan", "callPlanIdentity"),
            ("requestPolicy", "requestPolicy"),
        ):
            if not _canonical_json_equal(
                identities[receipt_field],
                frozen[plan_field],
                role=f"transport-canary {receipt_field} identity",
            ):
                _fail(
                    "capture-set receipt transport-canary identity differs "
                    "from frozen authority"
                )


def _validate_receipt_shape(receipt: Any) -> dict[str, Any]:
    if not isinstance(receipt, dict):
        _fail("capture-set receipt must be a JSON object")
    _reject_forbidden_fields(receipt)
    encoded = _canonical_json_bytes(receipt, role="capture-set receipt")
    if len(encoded) > MAX_RECEIPT_BYTES:
        _fail("capture-set receipt exceeds the safety limit")
    try:
        receipt_schema_version = receipt.get("receiptSchemaVersion")
        if receipt_schema_version == LEGACY_RECEIPT_SCHEMA_VERSION:
            schema_path = LEGACY_RECEIPT_SCHEMA_PATH
        elif receipt_schema_version == RECEIPT_SCHEMA_VERSION:
            schema_path = RECEIPT_SCHEMA_PATH
        else:
            _fail("capture-set receipt schema version is unsupported")
        validate(receipt, load_schema(schema_path))
    except CaptureSetReceiptError:
        raise
    except (SchemaValidationError, OSError, json.JSONDecodeError, RecursionError):
        _fail("capture-set receipt schema validation failed")
    _validate_receipt_self_consistency(receipt)
    registry, registry_bytes = _load_authority_registry()
    registry_binding = receipt["authorityRegistry"]
    if (
        registry_binding["bytes"] != len(registry_bytes)
        or registry_binding["sha256"] != _sha256(registry_bytes)
    ):
        _fail("capture-set receipt authority-registry binding mismatch")
    mapping = receipt["canonicalModelMapping"]
    authority_matched = _authority_match(
        registry,
        scope_plan_id=receipt["scopePlan"]["id"],
        model_mapping_id=mapping["id"] if mapping is not None else None,
        request_policy=receipt["identities"]["requestPolicy"],
    )
    if registry_binding["matched"] is not authority_matched:
        _fail("capture-set receipt authority match was not derived")
    expected_status = (
        "frozenTransportCanary"
        if receipt["scopeKind"] == "transportCanary"
        else "registeredCanonical"
        if authority_matched
        else "candidateUnregistered"
    )
    if receipt["scopePlan"]["authorityStatus"] != expected_status:
        _fail("capture-set receipt authority status was not derived")
    expected_blockers = _eligibility_blockers(
        scope_kind=receipt["scopeKind"],
        request_policy=receipt["identities"]["requestPolicy"],
        call_plan=receipt["identities"]["callPlan"],
        mapping=mapping,
        authority_matched=authority_matched,
    )
    if receipt["canonicalScoringInputBlockers"] != expected_blockers:
        _fail("capture-set receipt eligibility blockers were not derived")
    if receipt["canonicalScoringInputEligible"] is not (not expected_blockers):
        _fail("capture-set eligibility disagrees with its blockers")
    if receipt["id"] != _artifact_id(
        receipt,
        RECEIPT_ID_PREFIX,
        role="capture-set receipt",
    ):
        _fail("capture-set receipt artifact id mismatch")
    return receipt


def verify_capture_set_receipt(
    receipt: dict[str, Any],
    bundles: Iterable[VerifiedCaptureBundle],
    *,
    scope_plan: dict[str, Any],
    canonical_model_mapping: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Rebuild a receipt from exact bundle snapshots and compare every field."""

    _validate_receipt_shape(receipt)
    expected = assemble_capture_set_receipt(
        bundles,
        scope_plan=scope_plan,
        canonical_model_mapping=canonical_model_mapping,
    )
    if not _canonical_json_equal(
        receipt, expected, role="rebuilt capture-set receipt"
    ):
        _fail("capture-set receipt differs from verified bundle assembly")
    return receipt


def serialize_capture_set_receipt(receipt: dict[str, Any]) -> bytes:
    """Return deterministic bytes after schema and self-consistency checks.

    Serialization is not an authority check. Before scorer use, call
    :func:`verify_capture_set_receipt` with the exact bundles, scope plan, and
    optional model mapping so every field is rebuilt from retained evidence.
    """

    _validate_receipt_shape(receipt)
    return (
        json.dumps(
            receipt,
            allow_nan=False,
            ensure_ascii=True,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    ).encode("ascii")
