from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from .frozen_ladder import run_benchmark, stable_dataset_path
from .leakage_gate import evaluate_leakage
from .metrics import distortion, exact_fidelity, rank_by_metric
from .schema_validation import load_schema, validate


REPO_ROOT = Path(__file__).resolve().parents[2]
FORBIDDEN_SCORE_KEYS = {
    "borda",
    "bordaScore",
    "composite",
    "compositeScore",
    "weighted",
    "weightedScore",
    "winRate",
}
EVIDENCE_NOTE_REQUIRED_PHRASES = [
    "deterministic mock evidence",
    "not a real model leaderboard",
    "## Model Summary",
    "## Per-Item Receipt",
    "next evidence step",
]
EXPECTED_S2_FAMILIES = {
    "arithmetic": 10,
    "letter-lattice": 10,
    "route": 10,
}
EXPECTED_LADDER_COORDINATES = {(rung, paraphrase) for rung in range(4) for paraphrase in range(2)}


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _check(check_id: str, passed: bool, evidence: str) -> dict[str, Any]:
    return {
        "id": check_id,
        "status": "ok" if passed else "failed",
        "evidence": evidence,
    }


def _safe_check(check_id: str, fn: Any) -> dict[str, Any]:
    try:
        return fn()
    except Exception as exc:  # pragma: no cover - defensive report path
        return _check(check_id, False, f"{type(exc).__name__}: {exc}")


def _forbidden_keys(value: Any, *, path: str = "$") -> list[str]:
    hits: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{key}"
            if key in FORBIDDEN_SCORE_KEYS:
                hits.append(child_path)
            hits.extend(_forbidden_keys(child, path=child_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            hits.extend(_forbidden_keys(child, path=f"{path}[{index}]"))
    return hits


def _ci_bands_do_not_overlap(result: dict[str, Any]) -> bool:
    ordered = sorted(result["models"], key=lambda row: (row["aurc"], row["model"]))
    for left, right in zip(ordered, ordered[1:]):
        if left["aurcCi95"]["high"] >= right["aurcCi95"]["low"]:
            return False
    return True


def _iia_holds(result: dict[str, Any]) -> bool:
    full_order = rank_by_metric(result["models"], "aurc")
    for removed in full_order:
        reduced = [row for row in result["models"] if row["model"] != removed]
        reduced_order = rank_by_metric(reduced, "aurc")
        if [model for model in full_order if model != removed] != reduced_order:
            return False
    return True


def audit_m0_acceptance(
    *,
    data_dir: Path,
    result_path: Path,
    evidence_note_path: Path,
) -> dict[str, Any]:
    item_schema = load_schema(REPO_ROOT / "schemas/aleph-bench-item.schema.json")
    aleph_run_schema = load_schema(REPO_ROOT / "schemas/aleph-run.schema.json")
    result_schema = load_schema(REPO_ROOT / "schemas/aleph-bench-result.schema.json")
    items = [_load_json(path) for path in sorted(data_dir.glob("*.json"))]
    result = _load_json(result_path)
    note = evidence_note_path.read_text(encoding="utf-8") if evidence_note_path.exists() else ""

    evidence_modes = set(result.get("config", {}).get("evidenceModes", []))

    def schema_check() -> dict[str, Any]:
        for item in items:
            validate(item, item_schema)
        validate(result, result_schema)
        return _check(
            "schema-valid",
            True,
            f"{len(items)} BenchItems and {stable_dataset_path(result_path)} validate against checked-in schemas.",
        )

    def dataset_integrity_check() -> dict[str, Any]:
        failures = []
        expected_ids = [f"s2-{index:03d}" for index in range(1, 31)]
        item_ids = [item.get("id") for item in items]
        if item_ids != expected_ids:
            failures.append(f"expected ids {expected_ids}, got {item_ids}")

        canaries = {item.get("canaryGuid") for item in items}
        if len(canaries) != 1:
            failures.append(f"expected one shared canary, got {sorted(str(value) for value in canaries)}")
        canary = next(iter(canaries)) if len(canaries) == 1 else None

        family_counts = Counter(
            item.get("provenance", {}).get("parameters", {}).get("family", "<missing>")
            for item in items
        )
        if dict(family_counts) != EXPECTED_S2_FAMILIES:
            failures.append(f"expected family counts {EXPECTED_S2_FAMILIES}, got {dict(family_counts)}")

        for item in items:
            item_id = item.get("id", "<unknown>")
            target_text = item.get("target", {}).get("text", "")
            if canary and canary in target_text:
                failures.append(f"{item_id}: canary appears in target text")

            ladder = item.get("frozenLadder", [])
            coordinates = {(row.get("rung"), row.get("paraphrase")) for row in ladder}
            if coordinates != EXPECTED_LADDER_COORDINATES:
                failures.append(
                    f"{item_id}: expected 4x2 ladder coordinates, got {sorted(coordinates, key=str)}"
                )

            for row in ladder:
                rung = row.get("rung")
                paraphrase = row.get("paraphrase")
                expected_id = f"{item_id}-r{rung}-p{paraphrase}"
                if row.get("id") != expected_id:
                    failures.append(f"{item_id}: expected prompt id {expected_id}, got {row.get('id')}")
                expected_leakage = "leaky_anchor" if rung == 0 else "non_leaking_candidate"
                if row.get("expectedLeakage") != expected_leakage:
                    failures.append(
                        f"{item_id}: {row.get('id')} expectedLeakage should be {expected_leakage}"
                    )
                if canary and canary in row.get("prompt", ""):
                    failures.append(f"{item_id}: canary appears in prompt {row.get('id')}")

        return _check(
            "dataset-integrity",
            not failures,
            "30 S2 items share one field-level canary, keep it out of target/prompt text, use a 10/10/10 family split, and carry 4x2 ladder coordinates."
            if not failures
            else f"failures: {failures}",
        )

    def mock_only_check() -> dict[str, Any]:
        return _check(
            "mock-only-audit",
            evidence_modes == {"mock"},
            "audit is limited to deterministic mock results so it never spends hosted model calls."
            if evidence_modes == {"mock"}
            else f"result evidence modes are {sorted(evidence_modes)}; use verify/report for hosted evidence.",
        )

    def aleph_run_contract_check() -> dict[str, Any]:
        failures = []
        for run in result["itemRuns"]:
            if not isinstance(run, dict):
                failures.append("unknown:unknown: item run is not an object")
                continue
            try:
                validate(run["alephRun"], aleph_run_schema)
            except Exception as exc:
                failures.append(f"{run.get('itemId', '<unknown>')}:{run.get('model', '<unknown>')}: {exc}")
        return _check(
            "aleph-run-contract",
            not failures,
            f"all {len(result['itemRuns'])} item runs validate against schemas/aleph-run.schema.json."
            if not failures
            else f"failures: {failures}",
        )

    def exact_check() -> dict[str, Any]:
        failures = [
            item["id"]
            for item in items
            if exact_fidelity(item["target"]["text"], item["target"]["text"]) != 1.0
            or distortion(item["target"]["text"], item["target"]["text"], item["metricClass"]) != 0.0
        ]
        return _check(
            "exact-match",
            not failures,
            "target==output gives fidelity 1.0 and distortion 0.0 for every S2 item."
            if not failures
            else f"failed items: {failures}",
        )

    def leakage_check() -> dict[str, Any]:
        rung_zero_misses = []
        non_anchor_false_positives = []
        for item in items:
            target = item["target"]["text"]
            for ladder in item["frozenLadder"]:
                gate = evaluate_leakage(ladder["prompt"], target)
                if ladder["rung"] == 0 and not gate.disqualified:
                    rung_zero_misses.append(ladder["id"])
                if ladder["rung"] != 0 and gate.disqualified:
                    non_anchor_false_positives.append(ladder["id"])
        frontier_leaks = [
            f"{run['itemId']}:{run['model']}:{point['id']}"
            for run in result["itemRuns"]
            for point in run["frontier"]
            if point["disqualified"]
        ]
        passed = not rung_zero_misses and not non_anchor_false_positives and not frontier_leaks
        if passed:
            evidence = "all 60 rung-0 anchors gate, no rung 1-3 prompts gate, and result frontiers contain no disqualified points."
        else:
            evidence = (
                f"rung-zero misses={rung_zero_misses}; "
                f"non-anchor false positives={non_anchor_false_positives}; "
                f"frontier leaks={frontier_leaks}"
            )
        return _check("leakage-gate", passed, evidence)

    def reproducibility_check() -> dict[str, Any]:
        models = [model["model"] for model in result["models"]]
        reproduced = run_benchmark(
            data_dir=data_dir,
            models=models,
            split=result["split"],
            seed=result["seed"],
            tau=result["tau"],
            k=result["k"],
            reruns=result["config"]["reruns"],
            bootstrap_samples=result["config"]["bootstrapSamples"],
        )
        passed = result == reproduced
        return _check(
            "seed-0-reproducible",
            passed and result["seed"] == 0 and len(result["models"]) == 3,
            "checked-in seed 0 result exactly matches a fresh run with the same config and has three model summaries."
            if passed
            else "fresh seed 0 run differs from the checked-in result.",
        )

    def rank_stability_check() -> dict[str, Any]:
        models = [model["model"] for model in result["models"]]
        seed_one_result = run_benchmark(
            data_dir=data_dir,
            models=models,
            split=result["split"],
            seed=1,
            tau=result["tau"],
            k=result["k"],
            reruns=result["config"]["reruns"],
            bootstrap_samples=result["config"]["bootstrapSamples"],
        )
        seed_zero_order = rank_by_metric(result["models"], "aurc")
        seed_one_order = rank_by_metric(seed_one_result["models"], "aurc")
        passed = (
            seed_zero_order == seed_one_order
            and _ci_bands_do_not_overlap(result)
            and _ci_bands_do_not_overlap(seed_one_result)
        )
        return _check(
            "rank-stable",
            passed,
            f"seed 0 order={seed_zero_order}; seed 1 order={seed_one_order}; adjacent AURC CI bands do not overlap."
            if passed
            else f"seed 0 order={seed_zero_order}; seed 1 order={seed_one_order}; CI overlap detected.",
        )

    def iia_check() -> dict[str, Any]:
        return _check(
            "iia",
            _iia_holds(result),
            "removing any one model preserves the relative AURC order of the other two.",
        )

    def metric_reporting_check() -> dict[str, Any]:
        forbidden = _forbidden_keys(result)
        ci_fields = ("aurcCi95", "eclAtTauCi95", "elicitAtKCi95")
        missing_ci = [
            f"{model['model']}:{field}"
            for model in result["models"]
            for field in ci_fields
            if model.get(field) is None
        ]
        passed = result["stratum"] == "S2" and not forbidden and not missing_ci
        evidence = (
            "result reports S2 stratum, bootstrap CIs for AURC/ECL/Elicit, and no forbidden fused-score keys."
            if passed
            else f"stratum={result.get('stratum')}; forbidden={forbidden}; missing_ci={missing_ci}"
        )
        return _check("metric-reporting", passed, evidence)

    def evidence_note_check() -> dict[str, Any]:
        missing = [phrase for phrase in EVIDENCE_NOTE_REQUIRED_PHRASES if phrase not in note]
        return _check(
            "evidence-note",
            evidence_note_path.exists() and not missing,
            f"{stable_dataset_path(evidence_note_path)} contains the required cold-read sections and honesty phrases."
            if not missing
            else f"missing phrases: {missing}",
        )

    checks = [
        _safe_check("schema-valid", schema_check),
        _safe_check("dataset-integrity", dataset_integrity_check),
        _safe_check("mock-only-audit", mock_only_check),
        _safe_check("aleph-run-contract", aleph_run_contract_check),
        _safe_check("exact-match", exact_check),
        _safe_check("leakage-gate", leakage_check),
        _safe_check("iia", iia_check),
        _safe_check("metric-reporting", metric_reporting_check),
        _safe_check("evidence-note", evidence_note_check),
    ]
    if evidence_modes == {"mock"}:
        checks.insert(5, _safe_check("seed-0-reproducible", reproducibility_check))
        checks.insert(6, _safe_check("rank-stable", rank_stability_check))
    return {
        "status": "ok" if all(check["status"] == "ok" for check in checks) else "failed",
        "dataDir": stable_dataset_path(data_dir),
        "resultPath": stable_dataset_path(result_path),
        "evidenceNotePath": stable_dataset_path(evidence_note_path),
        "checks": checks,
    }


def format_audit_report(report: dict[str, Any]) -> str:
    lines = [
        f"status: {report['status']}",
        f"dataset: {report['dataDir']}",
        f"result: {report['resultPath']}",
        f"evidence note: {report['evidenceNotePath']}",
    ]
    for check in report["checks"]:
        lines.append(f"[{check['status']}] {check['id']}: {check['evidence']}")
    return "\n".join(lines)
