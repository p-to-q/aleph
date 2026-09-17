from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from .adapters import MockAdapter, normalize_model_id, validate_deployment_id
from .adapters.hosted_black_box import (
    DEFAULT_MAX_TOKENS,
    DEFAULT_TIMEOUT_SECONDS,
    HOSTED_ADAPTER_ID,
    HOSTED_ADAPTER_VERSION,
    HOSTED_REQUEST_PAYLOAD_VERSION,
    HOSTED_WIRE_PROTOCOL,
    MAX_HOSTED_RETRIES,
    MAX_RETRY_DELAY_SECONDS,
)
from .adapters.base import ModelAdapter
from .bundle import build_m0_bundle, compare_bundle
from .frozen_ladder import (
    FIXED_CREATED_AT as RESULT_FIXED_CREATED_AT,
    evaluate_item,
    load_items,
    result_notes,
    stable_dataset_path,
    summarize_model_runs,
)
from .manifest import (
    FIXED_CREATED_AT as MANIFEST_FIXED_CREATED_AT,
    build_prompt_receipts,
    manifest_notes,
)
from .legacy_v0_1 import verify_v0_1_repository_receipt
from .protocol import (
    DEFAULT_BOOTSTRAP_SAMPLES,
    DEFAULT_RERUNS,
    FROZEN_DATASET_HASH_ALGORITHM,
    FROZEN_DATASET_ID,
    FROZEN_DATASET_ITEM_COUNT,
    FROZEN_DATASET_SHA256,
    aleph_run_artifact_id,
    decoding_for_evidence_mode,
    manifest_artifact_id,
    result_artifact_id,
)
from .schema_validation import SchemaValidationError, load_schema, validate
from .scoring_core import PROTOCOL_VERSION


REPO_ROOT = Path(__file__).resolve().parents[2]
LEGACY_DATA_DIR = REPO_ROOT / "bench/data/public/s2"
LEGACY_RESULT_PATH = REPO_ROOT / "bench/results/m0-first-run.json"
LEGACY_MANIFEST_PATH = REPO_ROOT / "bench/results/m0-call-manifest.json"
LEGACY_AUDIT_PATH = REPO_ROOT / "bench/results/m0-audit.json"
LEGACY_BUNDLE_PATH = REPO_ROOT / "bench/results/m0-bundle.json"


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


LEGACY_PROTOCOL = "0.1-legacy"


class _ReceiptAdapter(ModelAdapter):
    """Replay retained raw strings through the canonical scorer without I/O."""

    def __init__(
        self,
        *,
        model_id: str,
        observation_mode: str,
        effective_reruns: int,
        outputs: dict[tuple[str, str], list[str]],
        receipts: dict[tuple[str, str], list[dict[str, str]]],
    ) -> None:
        super().__init__(
            model_id=model_id,
            observation_mode=observation_mode,
            temperature=0.0,
        )
        self.effective_reruns = effective_reruns
        self.outputs = outputs
        self.receipts = receipts
        self._last_response_receipt: dict[str, str] | None = None

    def reruns(self, configured: int) -> int:
        if configured != DEFAULT_RERUNS:
            raise ValueError("receipt replay requires the frozen rerun count")
        return self.effective_reruns

    def generate(
        self,
        prompt: str,
        item: dict[str, Any],
        ladder_prompt: dict[str, Any],
        *,
        seed: int,
        rerun_index: int,
    ) -> str:
        del prompt, seed
        key = (item["id"], ladder_prompt["id"])
        try:
            output = self.outputs[key][rerun_index]
            self._last_response_receipt = (
                dict(self.receipts[key][rerun_index])
                if self.observation_mode == "black_box"
                else None
            )
            return output
        except (KeyError, IndexError) as exc:
            raise ValueError(
                f"raw-output receipt is incomplete for {self.model_id}:{key[0]}:{key[1]}"
            ) from exc

    def last_response_receipt(self) -> dict[str, str] | None:
        return (
            dict(self._last_response_receipt)
            if self._last_response_receipt is not None
            else None
        )


def _expected_model_receipt(model: str) -> tuple[str, int]:
    canonical, evidence_mode, uses_configured_reruns = normalize_model_id(model)
    if canonical != model:
        raise ValueError(f"non-canonical v0.2 result model id {model!r}")
    return evidence_mode, DEFAULT_RERUNS if uses_configured_reruns else 1


def _verify_adapter_identity(
    *,
    identity: Any,
    model: str,
    evidence_mode: str,
    context: str,
    errors: list[str],
) -> dict[str, Any]:
    if not isinstance(identity, dict):
        errors.append(f"{context} lacks adapter identity")
        return {}
    if identity.get("model") != model:
        errors.append(f"{context} adapter identity model drifted")
    if identity.get("observationMode") != evidence_mode:
        errors.append(f"{context} adapter identity evidence mode drifted")
    if evidence_mode == "mock":
        expected = MockAdapter(model).evidence_identity()
        if identity != expected:
            errors.append(f"{context} mock adapter identity is not canonical")
        return identity
    if evidence_mode != "black_box":
        errors.append(f"{context} has unsupported adapter evidence mode")
        return identity

    expected_fields = {
        "adapterId": HOSTED_ADAPTER_ID,
        "adapterVersion": HOSTED_ADAPTER_VERSION,
        "temperature": 0.0,
        "wireProtocol": HOSTED_WIRE_PROTOCOL,
        "requestPayloadVersion": HOSTED_REQUEST_PAYLOAD_VERSION,
        "maxTokens": DEFAULT_MAX_TOKENS,
        "providerModel": model.removeprefix("hosted:"),
        "timeoutSeconds": DEFAULT_TIMEOUT_SECONDS,
    }
    for field, expected in expected_fields.items():
        if identity.get(field) != expected:
            errors.append(f"{context} adapter identity {field} is not canonical")
    endpoint_digest = identity.get("endpointSha256")
    if (
        not isinstance(endpoint_digest, str)
        or len(endpoint_digest) != 64
        or any(character not in "0123456789abcdef" for character in endpoint_digest)
    ):
        errors.append(f"{context} adapter identity endpointSha256 is invalid")
    try:
        validate_deployment_id(identity.get("deploymentId"))
    except (TypeError, ValueError):
        errors.append(f"{context} adapter identity deploymentId is invalid")
    return identity


def _load_dataset(data_dir: Path, errors: list[str]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for path in sorted(data_dir.glob("*.json")):
        try:
            item = _load_json(path)
            if not isinstance(item, dict):
                raise TypeError("BenchItem must be a JSON object")
            items.append(item)
        except (json.JSONDecodeError, OSError, TypeError) as exc:
            errors.append(f"{path}: {exc}")
    if not items:
        errors.append(f"{data_dir}: no BenchItems found")
    return items


def _load_object(path: Path, role: str, errors: list[str]) -> dict[str, Any] | None:
    try:
        value = _load_json(path)
    except (json.JSONDecodeError, OSError) as exc:
        errors.append(f"{path}: {exc}")
        return None
    if not isinstance(value, dict):
        errors.append(f"{path}: {role} must be a JSON object")
        return None
    return value


def _protocol_label(value: dict[str, Any]) -> str:
    version = value.get("protocolVersion")
    if version is None:
        return LEGACY_PROTOCOL
    if version == PROTOCOL_VERSION:
        return PROTOCOL_VERSION
    return f"unsupported:{version!r}"


def _is_rfc3339_utc(value: Any) -> bool:
    if not isinstance(value, str) or not value.endswith("Z"):
        return False
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError:
        return False
    return parsed.utcoffset() is not None and parsed.utcoffset().total_seconds() == 0


def _require_canonical_legacy_path(
    role: str,
    observed: Path,
    expected: Path,
    errors: list[str],
) -> None:
    if Path(observed).resolve(strict=False) != expected.resolve(strict=False):
        errors.append(
            f"immutable v0.1 verification requires canonical {role} path "
            f"{stable_dataset_path(expected)}"
        )


def _verify_v0_2_manifest_receipts(
    *,
    items: list[dict[str, Any]],
    manifest: dict[str, Any],
    errors: list[str],
) -> None:
    seed = manifest.get("seed")
    if isinstance(seed, bool) or not isinstance(seed, int):
        errors.append("manifest seed must be an integer")
    else:
        manifest_content = dict(manifest)
        manifest_content.pop("id", None)
        expected_id = manifest_artifact_id(manifest_content)
        if manifest.get("id") != expected_id:
            errors.append("manifest id does not match its seed and protocol")
    if manifest.get("createdAt") != MANIFEST_FIXED_CREATED_AT:
        errors.append("manifest createdAt does not match the frozen manifest timestamp")
    if manifest.get("notes") != manifest_notes():
        errors.append("manifest notes do not match the canonical honesty notes")
    expected_prompts, expected_gated = build_prompt_receipts(items)
    if manifest.get("prompts") != expected_prompts:
        errors.append(
            "manifest sendable prompt receipts do not match the canonical dataset and leakage gate"
        )
    if manifest.get("gatedPrompts") != expected_gated:
        errors.append(
            "manifest gated prompt receipts do not match the canonical dataset and leakage gate"
        )
    expected_counts = {
        "itemCount": len(items),
        "promptCount": len(expected_prompts) + len(expected_gated),
        "nonLeakingPromptCount": len(expected_prompts),
        "gatedPromptCount": len(expected_gated),
    }
    for field, expected in expected_counts.items():
        if manifest.get(field) != expected:
            errors.append(f"manifest {field} does not match canonical prompt receipts")

    hosted_max_retries = manifest.get("hostedMaxRetries")
    hosted_retry_delay_seconds = manifest.get("hostedRetryDelaySeconds")
    if (
        isinstance(hosted_retry_delay_seconds, bool)
        or not isinstance(hosted_retry_delay_seconds, (int, float))
        or not 0.0 <= hosted_retry_delay_seconds <= MAX_RETRY_DELAY_SECONDS
    ):
        errors.append(
            "manifest hostedRetryDelaySeconds is outside the supported retry bound"
        )
    if (
        isinstance(hosted_max_retries, bool)
        or not isinstance(hosted_max_retries, int)
        or not 0 <= hosted_max_retries <= MAX_HOSTED_RETRIES
    ):
        errors.append("manifest hostedMaxRetries is outside the supported retry bound")
    else:
        hosted_generations = len(expected_prompts) * sum(
            row.get("effectiveReruns", 0)
            for row in manifest.get("models", [])
            if row.get("evidenceMode") == "black_box"
        )
        if manifest.get("estimatedMaxHttpAttempts") != hosted_generations * (
            hosted_max_retries + 1
        ):
            errors.append(
                "manifest estimatedMaxHttpAttempts does not match its hosted retry policy"
            )

    for row in manifest.get("models", []):
        model = row.get("model")
        try:
            evidence_mode, effective_reruns = _expected_model_receipt(model)
        except (TypeError, ValueError) as exc:
            errors.append(str(exc))
            continue
        if row.get("evidenceMode") != evidence_mode:
            errors.append(f"manifest model {model} has an invalid evidenceMode")
        if row.get("effectiveReruns") != effective_reruns:
            errors.append(f"manifest model {model} has an invalid effectiveReruns")
        adapter_identity = _verify_adapter_identity(
            identity=row.get("adapterIdentity"),
            model=model,
            evidence_mode=evidence_mode,
            context=f"manifest model {model}",
            errors=errors,
        )
        if evidence_mode == "black_box":
            if adapter_identity.get("maxRetries") != hosted_max_retries:
                errors.append(
                    f"manifest model {model} retry policy does not match hostedMaxRetries"
                )
            if (
                adapter_identity.get("retryDelaySeconds")
                != hosted_retry_delay_seconds
            ):
                errors.append(
                    f"manifest model {model} retry policy does not match hostedRetryDelaySeconds"
                )
        if row.get("status") != "ready":
            errors.append(
                f"manifest model {model} was not ready for the verified result run"
            )
        if row.get("missingEnv") != []:
            errors.append(
                f"manifest model {model} has unresolved environment requirements"
            )
        if "error" in row:
            errors.append(f"manifest model {model} has a planning error")


def _verify_v0_2_result_receipts(
    *,
    items: list[dict[str, Any]],
    result: dict[str, Any],
    errors: list[str],
) -> None:
    """Recompute item runs and aggregates from retained raw adapter strings."""

    if result.get("evaluationScope") != "canonical":
        errors.append("verified v0.2 releases must have evaluationScope=canonical")
        return
    if result.get("requestedItemLimit") is not None:
        errors.append("canonical v0.2 releases must have requestedItemLimit=null")
    if result.get("evaluatedItemCount") != len(items):
        errors.append("result evaluatedItemCount does not match the canonical dataset")
    expected_metric_classes = sorted({item["metricClass"] for item in items})
    if result.get("metricClasses") != expected_metric_classes:
        errors.append("result metricClasses do not match the canonical dataset")
    runs_by_pair: dict[tuple[str, str], dict[str, Any]] = {}
    for run in result.get("itemRuns", []):
        key = (run.get("model"), run.get("itemId"))
        if not all(isinstance(part, str) for part in key):
            continue
        if key in runs_by_pair:
            continue
        runs_by_pair[key] = run

    summaries_by_model = {
        summary.get("model"): summary
        for summary in result.get("models", [])
        if isinstance(summary.get("model"), str)
    }
    expected_modes: set[str] = set()
    for model in summaries_by_model:
        try:
            mode, _ = _expected_model_receipt(model)
        except ValueError:
            continue
        expected_modes.add(mode)
    if result.get("config", {}).get("evidenceModes") != sorted(expected_modes):
        errors.append("result config evidenceModes do not match model summaries")
    if result.get("notes") != result_notes(sorted(expected_modes)):
        errors.append("result notes do not match the declared evidence modes and protocol")
    seed = result.get("seed")
    if isinstance(seed, bool) or not isinstance(seed, int):
        errors.append("result seed must be an integer for receipt replay")
        return
    result_content = dict(result)
    result_content.pop("id", None)
    expected_result_id = result_artifact_id(result_content)
    if result.get("id") != expected_result_id:
        errors.append("result id does not match its seed, scope, and protocol")
    created_at = result.get("createdAt")
    if not _is_rfc3339_utc(created_at):
        errors.append("result createdAt must be an RFC 3339 UTC timestamp")
        return
    if expected_modes == {"mock"} and created_at != RESULT_FIXED_CREATED_AT:
        errors.append("mock result createdAt does not match the frozen fixture timestamp")

    for model, observed_summary in summaries_by_model.items():
        try:
            evidence_mode, effective_reruns = _expected_model_receipt(model)
        except ValueError as exc:
            errors.append(str(exc))
            continue
        if observed_summary.get("evidenceMode") != evidence_mode:
            errors.append(f"result model {model} has an invalid evidenceMode")
            continue

        outputs: dict[tuple[str, str], list[str]] = {}
        receipts: dict[tuple[str, str], list[dict[str, str]]] = {}
        model_runs: list[dict[str, Any]] = []
        replayable = True
        for item in items:
            observed = runs_by_pair.get((model, item["id"]))
            if observed is None:
                replayable = False
                continue
            aleph_run = observed.get("alephRun", {})
            run_content = dict(aleph_run)
            run_content.pop("id", None)
            expected_run_id = aleph_run_artifact_id(
                item_id=item["id"], seed=seed, artifact=run_content
            )
            if aleph_run.get("id") != expected_run_id:
                errors.append(
                    f"item run {item['id']}/{model} AlephRun id does not match its identity"
                )
            run_config = aleph_run.get("config", {})
            budget = run_config.get("budget", {})
            candidates = aleph_run.get("candidates", [])
            candidate_tokens = [
                candidate.get("tokens")
                for candidate in candidates
                if isinstance(candidate, dict)
                and isinstance(candidate.get("tokens"), int)
                and not isinstance(candidate.get("tokens"), bool)
            ]
            if run_config.get("model") != model:
                errors.append(f"result {model}:{item['id']} AlephRun model drifted")
            if run_config.get("metric") != item["metricClass"]:
                errors.append(f"result {model}:{item['id']} AlephRun metric drifted")
            if run_config.get("decoding") != decoding_for_evidence_mode(evidence_mode):
                errors.append(f"result {model}:{item['id']} AlephRun decoding drifted")
            if budget.get("candidates") != len(candidates):
                errors.append(
                    f"result {model}:{item['id']} AlephRun candidate budget drifted"
                )
            expected_max_tokens = max(candidate_tokens) if candidate_tokens else 0
            if (
                len(candidate_tokens) != len(candidates)
                or budget.get("maxPromptTokens") != expected_max_tokens
            ):
                errors.append(
                    f"result {model}:{item['id']} AlephRun maxPromptTokens does not "
                    "bound its candidates"
                )
            if budget.get("repeatedSamples") != effective_reruns:
                errors.append(
                    f"result {model}:{item['id']} AlephRun repeatedSamples drifted"
                )
            measurements = {
                row.get("promptId"): row
                for row in observed.get("measurements", [])
                if isinstance(row, dict) and isinstance(row.get("promptId"), str)
            }
            for ladder in item["frozenLadder"]:
                measurement = measurements.get(ladder["id"])
                if measurement is None or not isinstance(measurement.get("outputs"), list):
                    errors.append(
                        f"result {model}:{item['id']} lacks raw outputs for {ladder['id']}"
                    )
                    replayable = False
                    continue
                raw_outputs = measurement["outputs"]
                raw_receipts = measurement.get("responseReceipts")
                expected_count = (
                    0
                    if ladder["expectedLeakage"] == "leaky_anchor"
                    else effective_reruns
                )
                if len(raw_outputs) != expected_count or any(
                    not isinstance(output, str) for output in raw_outputs
                ):
                    errors.append(
                        f"result {model}:{item['id']}:{ladder['id']} has an invalid raw-output receipt count"
                    )
                    replayable = False
                    continue
                expected_receipt_count = (
                    expected_count if evidence_mode == "black_box" else 0
                )
                if (
                    not isinstance(raw_receipts, list)
                    or len(raw_receipts) != expected_receipt_count
                    or any(
                        not isinstance(receipt, dict)
                        or not _is_rfc3339_utc(receipt.get("capturedAt"))
                        or receipt.get("source") not in {"provider", "cache"}
                        for receipt in raw_receipts
                    )
                ):
                    errors.append(
                        f"result {model}:{item['id']}:{ladder['id']} has an invalid response-capture receipt"
                    )
                    replayable = False
                    continue
                outputs[(item["id"], ladder["id"])] = raw_outputs
                receipts[(item["id"], ladder["id"])] = raw_receipts
        if not replayable:
            continue

        adapter = _ReceiptAdapter(
            model_id=model,
            observation_mode=evidence_mode,
            effective_reruns=effective_reruns,
            outputs=outputs,
            receipts=receipts,
        )
        try:
            for item in items:
                expected_run = evaluate_item(
                    item,
                    adapter,
                    seed=seed,
                    created_at=created_at,
                )
                observed_run = runs_by_pair[(model, item["id"])]
                if observed_run != expected_run:
                    errors.append(
                        f"result {model}:{item['id']} does not match canonical rescoring of raw outputs"
                    )
                model_runs.append(expected_run)
            expected_summary = summarize_model_runs(
                model=model,
                evidence_mode=evidence_mode,
                runs=model_runs,
                seed=seed,
                bootstrap_samples=DEFAULT_BOOTSTRAP_SAMPLES,
            )
            adapter_identity = _verify_adapter_identity(
                identity=observed_summary.get("adapterIdentity"),
                model=model,
                evidence_mode=evidence_mode,
                context=f"result model {model}",
                errors=errors,
            )
            expected_summary["adapterIdentity"] = adapter_identity
            all_receipts = [
                receipt
                for values in receipts.values()
                for receipt in values
            ]
            response_capture: dict[str, Any] | None = None
            if evidence_mode == "black_box":
                captured_at = [receipt["capturedAt"] for receipt in all_receipts]
                response_capture = {
                    "responseCount": len(all_receipts),
                    "providerResponseCount": sum(
                        receipt["source"] == "provider" for receipt in all_receipts
                    ),
                    "cacheHitCount": sum(
                        receipt["source"] == "cache" for receipt in all_receipts
                    ),
                    "capturedAtMin": min(captured_at),
                    "capturedAtMax": max(captured_at),
                }
            expected_summary["responseCapture"] = response_capture
            if observed_summary != expected_summary:
                errors.append(
                    f"result model summary {model} does not match recomputed item runs"
                )
        except (KeyError, TypeError, ValueError) as exc:
            errors.append(f"result receipt replay failed for {model}: {exc}")


def verify_artifacts(
    *,
    data_dir: Path,
    result_path: Path,
    manifest_path: Path,
    audit_path: Path | None = None,
    bundle_path: Path | None = None,
) -> dict[str, Any]:
    errors: list[str] = []
    items = _load_dataset(data_dir, errors)
    result = _load_object(result_path, "BenchResult", errors)
    manifest = _load_object(manifest_path, "BenchManifest", errors)

    labels = {
        _protocol_label(value)
        for value in [*items, result, manifest]
        if value is not None
    }
    unsupported = sorted(label for label in labels if label.startswith("unsupported:"))
    if unsupported:
        errors.append(f"unsupported protocol versions: {unsupported}")
    supported_labels = labels - set(unsupported)
    if len(supported_labels) > 1:
        errors.append(
            "dataset, result, and manifest mix incompatible protocol versions: "
            f"{sorted(supported_labels)}"
        )
    protocol_version = (
        next(iter(supported_labels)) if len(supported_labels) == 1 else "unknown"
    )
    schema_dir = (
        REPO_ROOT / "schemas/v0.2"
        if protocol_version == PROTOCOL_VERSION
        else REPO_ROOT / "schemas"
    )
    item_schema = load_schema(schema_dir / "aleph-bench-item.schema.json")
    aleph_run_schema = load_schema(REPO_ROOT / "schemas/aleph-run.schema.json")
    result_schema = load_schema(schema_dir / "aleph-bench-result.schema.json")
    manifest_schema = load_schema(schema_dir / "aleph-bench-manifest.schema.json")

    if protocol_version == LEGACY_PROTOCOL:
        _require_canonical_legacy_path("dataset", data_dir, LEGACY_DATA_DIR, errors)
        _require_canonical_legacy_path("result", result_path, LEGACY_RESULT_PATH, errors)
        _require_canonical_legacy_path(
            "manifest", manifest_path, LEGACY_MANIFEST_PATH, errors
        )
        if audit_path is not None:
            _require_canonical_legacy_path(
                "audit", audit_path, LEGACY_AUDIT_PATH, errors
            )
        if bundle_path is not None:
            _require_canonical_legacy_path(
                "bundle", bundle_path, LEGACY_BUNDLE_PATH, errors
            )
        for receipt_error in verify_v0_1_repository_receipt():
            errors.append(f"immutable v0.1 receipt: {receipt_error}")

    items_valid = True
    if protocol_version == PROTOCOL_VERSION:
        try:
            items = load_items(data_dir, require_canonical=True)
        except (OSError, RuntimeError, ValueError) as exc:
            items_valid = False
            errors.append(f"{data_dir}: canonical v0.2 dataset check failed: {exc}")
    for index, item in enumerate(items):
        try:
            validate(item, item_schema)
        except SchemaValidationError as exc:
            items_valid = False
            errors.append(f"{data_dir} item {index}: {exc}")
    result_valid = result is not None
    if result is not None:
        try:
            validate(result, result_schema)
        except SchemaValidationError as exc:
            result_valid = False
            errors.append(f"{result_path}: {exc}")
    manifest_valid = manifest is not None
    if manifest is not None:
        try:
            validate(manifest, manifest_schema)
        except SchemaValidationError as exc:
            manifest_valid = False
            errors.append(f"{manifest_path}: {exc}")

    audit: dict[str, Any] = {}
    bundle: dict[str, Any] = {}
    if protocol_version == PROTOCOL_VERSION and (audit_path is not None or bundle_path is not None):
        errors.append("v0.2 audit and bundle artifacts are not implemented; verify result and manifest only")
    elif audit_path is not None:
        audit_schema = load_schema(REPO_ROOT / "schemas/aleph-bench-audit.schema.json")
        try:
            audit = _load_json(audit_path)
            validate(audit, audit_schema)
        except (json.JSONDecodeError, OSError, SchemaValidationError) as exc:
            errors.append(f"{audit_path}: {exc}")
    if protocol_version != PROTOCOL_VERSION and bundle_path is not None:
        bundle_schema = load_schema(REPO_ROOT / "schemas/aleph-bench-bundle.schema.json")
        try:
            bundle = _load_json(bundle_path)
            validate(bundle, bundle_schema)
        except (json.JSONDecodeError, OSError, SchemaValidationError) as exc:
            errors.append(f"{bundle_path}: {exc}")

    expected_dataset_path = stable_dataset_path(data_dir)
    item_ids = {item["id"] for item in items} if items_valid else set()
    canaries = {item["canaryGuid"] for item in items} if items_valid else set()

    if result_valid:
        aleph_run_contract_count = 0
        for run in result.get("itemRuns", []):
            if not isinstance(run, dict):
                errors.append("unknown:unknown alephRun: item run is not an object")
                continue
            try:
                validate(run["alephRun"], aleph_run_schema)
                aleph_run_contract_count += 1
            except (KeyError, TypeError, SchemaValidationError) as exc:
                errors.append(f"{run.get('itemId', '<unknown>')}:{run.get('model', '<unknown>')} alephRun: {exc}")
        if result.get("config", {}).get("datasetPath") != expected_dataset_path:
            errors.append("result config datasetPath does not match data directory")
        if len(canaries) == 1 and result.get("canaryGuid") != next(iter(canaries)):
            errors.append("result canaryGuid does not match dataset canary")
        result_item_ids = {run["itemId"] for run in result.get("itemRuns", []) if "itemId" in run}
        unknown = sorted(result_item_ids - item_ids)
        if unknown:
            errors.append(f"result references unknown item ids: {unknown}")
        model_item_total = sum(model["itemCount"] for model in result.get("models", []) if "itemCount" in model)
        if len(result.get("itemRuns", [])) != model_item_total:
            errors.append("result itemRuns length does not match model itemCount total")
        result_models = [model["model"] for model in result["models"]]
        if len(set(result_models)) != len(result_models):
            errors.append("result model ids must be unique")
        expected_pairs = {(model, item_id) for model in result_models for item_id in item_ids}
        observed_pairs = [(run["model"], run["itemId"]) for run in result["itemRuns"]]
        if len(set(observed_pairs)) != len(observed_pairs):
            errors.append("result contains duplicate model/item runs")
        if set(observed_pairs) != expected_pairs:
            errors.append("result does not cover the complete model/item Cartesian product")
        for model in result["models"]:
            if model["itemCount"] != len(item_ids):
                errors.append(
                    f"result model {model['model']} itemCount does not match dataset"
                )
        prompts_by_item = {
            item["id"]: {prompt["id"] for prompt in item["frozenLadder"]}
            for item in items
        }
        for run in result["itemRuns"]:
            prompt_ids = [row["promptId"] for row in run["measurements"]]
            if len(set(prompt_ids)) != len(prompt_ids):
                errors.append(
                    f"result {run['model']}:{run['itemId']} has duplicate measurements"
                )
            if set(prompt_ids) != prompts_by_item.get(run["itemId"], set()):
                errors.append(
                    f"result {run['model']}:{run['itemId']} does not cover its frozen ladder"
                )
        if protocol_version == PROTOCOL_VERSION and items_valid:
            expected_identity = {
                "datasetId": FROZEN_DATASET_ID,
                "datasetItemCount": FROZEN_DATASET_ITEM_COUNT,
                "datasetSha256": FROZEN_DATASET_SHA256,
                "datasetHashAlgorithm": FROZEN_DATASET_HASH_ALGORITHM,
            }
            for field, expected in expected_identity.items():
                if result.get("config", {}).get(field) != expected:
                    errors.append(f"result config {field} does not match canonical dataset")
            _verify_v0_2_result_receipts(
                items=items,
                result=result,
                errors=errors,
            )
    else:
        aleph_run_contract_count = 0

    if manifest_valid:
        if manifest["itemCount"] != len(item_ids):
            errors.append("manifest itemCount does not match dataset")
        if manifest["modelCount"] != len(manifest["models"]):
            errors.append("manifest modelCount does not match models length")
        manifest_model_ids = [model["model"] for model in manifest["models"]]
        if len(set(manifest_model_ids)) != len(manifest_model_ids):
            errors.append("manifest model ids must be unique")
        if manifest["datasetPath"] != expected_dataset_path:
            errors.append("manifest datasetPath does not match data directory")
        if manifest["promptCount"] != manifest["nonLeakingPromptCount"] + manifest["gatedPromptCount"]:
            errors.append("manifest prompt counts do not add up")
        if protocol_version == PROTOCOL_VERSION:
            effective_reruns = sum(
                model["effectiveReruns"] for model in manifest["models"]
            )
        else:
            effective_reruns = manifest["modelCount"] * manifest["effectiveReruns"]
        expected_generations = manifest["nonLeakingPromptCount"] * effective_reruns
        if manifest["estimatedGenerations"] != expected_generations:
            errors.append("manifest estimatedGenerations does not match prompt/model/rerun counts")
        if any(prompt["leakageGate"]["disqualified"] for prompt in manifest["prompts"]):
            errors.append("manifest sendable prompts include a disqualified prompt")
        if any(not prompt["leakageGate"]["disqualified"] for prompt in manifest["gatedPrompts"]):
            errors.append("manifest gated prompts include a non-disqualified prompt")
        manifest_item_ids = {prompt["itemId"] for prompt in manifest["prompts"] + manifest["gatedPrompts"]}
        unknown = sorted(manifest_item_ids - item_ids)
        if unknown:
            errors.append(f"manifest references unknown item ids: {unknown}")
        expected_prompt_pairs = {
            (item["id"], prompt["id"])
            for item in items
            for prompt in item["frozenLadder"]
        }
        manifest_prompt_pairs = [
            (prompt["itemId"], prompt["promptId"])
            for prompt in manifest["prompts"] + manifest["gatedPrompts"]
        ]
        if len(set(manifest_prompt_pairs)) != len(manifest_prompt_pairs):
            errors.append("manifest contains duplicate item/prompt entries")
        if set(manifest_prompt_pairs) != expected_prompt_pairs:
            errors.append("manifest does not cover every frozen-ladder prompt exactly once")
        if manifest["promptCount"] != len(expected_prompt_pairs):
            errors.append("manifest promptCount does not match dataset ladders")
        if protocol_version == PROTOCOL_VERSION and items_valid:
            expected_identity = {
                "datasetId": FROZEN_DATASET_ID,
                "datasetItemCount": FROZEN_DATASET_ITEM_COUNT,
                "datasetSha256": FROZEN_DATASET_SHA256,
                "datasetHashAlgorithm": FROZEN_DATASET_HASH_ALGORITHM,
            }
            for field, expected in expected_identity.items():
                if manifest.get(field) != expected:
                    errors.append(f"manifest {field} does not match canonical dataset")
            _verify_v0_2_manifest_receipts(
                items=items,
                manifest=manifest,
                errors=errors,
            )

    if result_valid and manifest_valid:
        result_models = sorted(model["model"] for model in result["models"])
        manifest_models = sorted(model["model"] for model in manifest["models"])
        if result_models != manifest_models:
            errors.append("result models do not match manifest models")
        if result["track"] != manifest["track"] or result["split"] != manifest["split"] or result["seed"] != manifest["seed"]:
            errors.append("result track/split/seed do not match manifest")
        if result["config"].get("scoring") != manifest.get("scoring"):
            errors.append("result scoring profile does not match manifest")
        result_identities = {
            row["model"]: row.get("adapterIdentity") for row in result["models"]
        }
        manifest_identities = {
            row["model"]: row.get("adapterIdentity") for row in manifest["models"]
        }
        if result_identities != manifest_identities:
            errors.append("result adapter identities do not match manifest")

    if audit:
        if audit["dataDir"] != expected_dataset_path:
            errors.append("audit dataDir does not match data directory")
        if audit["resultPath"] != stable_dataset_path(result_path):
            errors.append("audit resultPath does not match result path")
        if audit["status"] != "ok":
            errors.append("audit status is not ok")
        failed_checks = [check["id"] for check in audit["checks"] if check["status"] != "ok"]
        if failed_checks:
            errors.append(f"audit has failed checks: {failed_checks}")

    if bundle:
        artifacts = {artifact["role"]: artifact for artifact in bundle.get("artifacts", [])}
        required_roles = {"result", "manifest", "audit", "report", "evidence_note"}
        missing_roles = sorted(required_roles - set(artifacts))
        if missing_roles:
            errors.append(f"bundle missing artifact roles: {missing_roles}")
        if artifacts.get("result", {}).get("path") != stable_dataset_path(result_path):
            errors.append("bundle result path does not match result path")
        if artifacts.get("manifest", {}).get("path") != stable_dataset_path(manifest_path):
            errors.append("bundle manifest path does not match manifest path")
        if audit_path is None:
            errors.append("bundle verification requires --audit")
        elif artifacts.get("audit", {}).get("path") != stable_dataset_path(audit_path):
            errors.append("bundle audit path does not match audit path")

        if not missing_roles and audit_path is not None:
            current_bundle = build_m0_bundle(
                result_path=result_path,
                manifest_path=manifest_path,
                audit_path=audit_path,
                report_path=REPO_ROOT / artifacts["report"]["path"],
                evidence_note_path=REPO_ROOT / artifacts["evidence_note"]["path"],
            )
            for error in compare_bundle(bundle, current_bundle):
                errors.append(f"bundle {error}")

    return {
        "status": "ok" if not errors else "failed",
        "protocolVersion": protocol_version,
        "dataDir": expected_dataset_path,
        "resultPath": stable_dataset_path(result_path),
        "manifestPath": stable_dataset_path(manifest_path),
        "auditPath": stable_dataset_path(audit_path) if audit_path is not None else None,
        "bundlePath": stable_dataset_path(bundle_path) if bundle_path is not None else None,
        "itemCount": len(items),
        "resultItemRuns": len(result.get("itemRuns", [])) if result is not None else 0,
        "resultAlephRunContractCount": aleph_run_contract_count,
        "resultModelCount": len(result.get("models", [])) if result is not None else 0,
        "manifestPromptCount": manifest.get("promptCount", 0) if manifest is not None else 0,
        "manifestNonLeakingPromptCount": manifest.get("nonLeakingPromptCount", 0) if manifest is not None else 0,
        "manifestGatedPromptCount": manifest.get("gatedPromptCount", 0) if manifest is not None else 0,
        "manifestEstimatedGenerations": manifest.get("estimatedGenerations", 0) if manifest is not None else 0,
        "manifestHostedMaxRetries": manifest.get("hostedMaxRetries")
        if manifest is not None
        else None,
        "manifestEstimatedMaxHttpAttempts": manifest.get(
            "estimatedMaxHttpAttempts", 0
        )
        if manifest is not None
        else 0,
        "auditCheckCount": len(audit.get("checks", [])) if audit else 0,
        "bundleArtifactCount": len(bundle.get("artifacts", [])) if bundle else 0,
        "errors": errors,
    }


def format_verify_report(report: dict[str, Any]) -> str:
    lines = [
        f"status: {report['status']}",
        f"protocol: {report['protocolVersion']}",
        f"dataset: {report['dataDir']} ({report['itemCount']} items)",
        (
            f"result: {report['resultPath']} "
            f"({report['resultModelCount']} models, {report['resultItemRuns']} item runs, "
            f"{report['resultAlephRunContractCount']} canonical AlephRun)"
        ),
        (
            f"manifest: {report['manifestPath']} "
            f"({report['manifestNonLeakingPromptCount']} non-leaking, "
            f"{report['manifestGatedPromptCount']} gated, "
            f"{report['manifestEstimatedGenerations']} logical generations, "
            f"{report['manifestEstimatedMaxHttpAttempts']} max HTTP attempts)"
        ),
    ]
    if report["auditPath"] is not None:
        lines.append(f"audit: {report['auditPath']} ({report['auditCheckCount']} checks)")
    if report["bundlePath"] is not None:
        lines.append(f"bundle: {report['bundlePath']} ({report['bundleArtifactCount']} artifacts)")
    for error in report["errors"]:
        lines.append(f"error: {error}")
    return "\n".join(lines)
