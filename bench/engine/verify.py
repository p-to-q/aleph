from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .bundle import build_m0_bundle, compare_bundle
from .frozen_ladder import stable_dataset_path
from .schema_validation import SchemaValidationError, load_schema, validate


REPO_ROOT = Path(__file__).resolve().parents[2]


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _validate_dataset(data_dir: Path, item_schema: dict[str, Any], errors: list[str]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for path in sorted(data_dir.glob("*.json")):
        try:
            item = _load_json(path)
            validate(item, item_schema)
            items.append(item)
        except (json.JSONDecodeError, SchemaValidationError) as exc:
            errors.append(f"{path}: {exc}")
    if not items:
        errors.append(f"{data_dir}: no BenchItems found")
    return items


def verify_artifacts(
    *,
    data_dir: Path,
    result_path: Path,
    manifest_path: Path,
    audit_path: Path | None = None,
    bundle_path: Path | None = None,
) -> dict[str, Any]:
    errors: list[str] = []
    item_schema = load_schema(REPO_ROOT / "schemas/aleph-bench-item.schema.json")
    aleph_run_schema = load_schema(REPO_ROOT / "schemas/aleph-run.schema.json")
    result_schema = load_schema(REPO_ROOT / "schemas/aleph-bench-result.schema.json")
    manifest_schema = load_schema(REPO_ROOT / "schemas/aleph-bench-manifest.schema.json")
    audit_schema = load_schema(REPO_ROOT / "schemas/aleph-bench-audit.schema.json")
    bundle_schema = load_schema(REPO_ROOT / "schemas/aleph-bench-bundle.schema.json")

    items = _validate_dataset(data_dir, item_schema, errors)

    result: dict[str, Any] = {}
    manifest: dict[str, Any] = {}
    audit: dict[str, Any] = {}
    bundle: dict[str, Any] = {}
    try:
        result = _load_json(result_path)
        validate(result, result_schema)
    except (json.JSONDecodeError, SchemaValidationError) as exc:
        errors.append(f"{result_path}: {exc}")
    try:
        manifest = _load_json(manifest_path)
        validate(manifest, manifest_schema)
    except (json.JSONDecodeError, SchemaValidationError) as exc:
        errors.append(f"{manifest_path}: {exc}")
    if audit_path is not None:
        try:
            audit = _load_json(audit_path)
            validate(audit, audit_schema)
        except (json.JSONDecodeError, OSError, SchemaValidationError) as exc:
            errors.append(f"{audit_path}: {exc}")
    if bundle_path is not None:
        try:
            bundle = _load_json(bundle_path)
            validate(bundle, bundle_schema)
        except (json.JSONDecodeError, OSError, SchemaValidationError) as exc:
            errors.append(f"{bundle_path}: {exc}")

    expected_dataset_path = stable_dataset_path(data_dir)
    item_ids = {item["id"] for item in items}
    canaries = {item["canaryGuid"] for item in items}

    if result:
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
    else:
        aleph_run_contract_count = 0

    if manifest:
        if manifest["datasetPath"] != expected_dataset_path:
            errors.append("manifest datasetPath does not match data directory")
        if manifest["promptCount"] != manifest["nonLeakingPromptCount"] + manifest["gatedPromptCount"]:
            errors.append("manifest prompt counts do not add up")
        expected_generations = (
            manifest["nonLeakingPromptCount"] * manifest["modelCount"] * manifest["effectiveReruns"]
        )
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

    if result and manifest:
        result_models = sorted(model["model"] for model in result["models"])
        manifest_models = sorted(model["model"] for model in manifest["models"])
        if result_models != manifest_models:
            errors.append("result models do not match manifest models")
        if result["track"] != manifest["track"] or result["split"] != manifest["split"] or result["seed"] != manifest["seed"]:
            errors.append("result track/split/seed do not match manifest")

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
        "dataDir": expected_dataset_path,
        "resultPath": stable_dataset_path(result_path),
        "manifestPath": stable_dataset_path(manifest_path),
        "auditPath": stable_dataset_path(audit_path) if audit_path is not None else None,
        "bundlePath": stable_dataset_path(bundle_path) if bundle_path is not None else None,
        "itemCount": len(items),
        "resultItemRuns": len(result.get("itemRuns", [])) if result else 0,
        "resultAlephRunContractCount": aleph_run_contract_count,
        "resultModelCount": len(result.get("models", [])) if result else 0,
        "manifestPromptCount": manifest.get("promptCount", 0) if manifest else 0,
        "manifestNonLeakingPromptCount": manifest.get("nonLeakingPromptCount", 0) if manifest else 0,
        "manifestGatedPromptCount": manifest.get("gatedPromptCount", 0) if manifest else 0,
        "manifestEstimatedGenerations": manifest.get("estimatedGenerations", 0) if manifest else 0,
        "auditCheckCount": len(audit.get("checks", [])) if audit else 0,
        "bundleArtifactCount": len(bundle.get("artifacts", [])) if bundle else 0,
        "errors": errors,
    }


def format_verify_report(report: dict[str, Any]) -> str:
    lines = [
        f"status: {report['status']}",
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
            f"{report['manifestEstimatedGenerations']} estimated generations)"
        ),
    ]
    if report["auditPath"] is not None:
        lines.append(f"audit: {report['auditPath']} ({report['auditCheckCount']} checks)")
    if report["bundlePath"] is not None:
        lines.append(f"bundle: {report['bundlePath']} ({report['bundleArtifactCount']} artifacts)")
    for error in report["errors"]:
        lines.append(f"error: {error}")
    return "\n".join(lines)
