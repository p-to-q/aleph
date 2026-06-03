#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from bench.engine.frozen_ladder import (  # noqa: E402
    DEFAULT_BOOTSTRAP_SAMPLES,
    DEFAULT_K,
    DEFAULT_RERUNS,
    DEFAULT_TAU,
    run_benchmark,
)
from bench.engine.audit import audit_m0_acceptance, format_audit_report  # noqa: E402
from bench.engine.bundle import build_m0_bundle, compare_bundle  # noqa: E402
from bench.engine.manifest import build_manifest  # noqa: E402
from bench.engine.platform_package import (  # noqa: E402
    DEFAULT_PACKAGE_DIR,
    check_platform_package,
    format_package_check,
    write_platform_package,
)
from bench.engine.preflight import format_preflight, preflight  # noqa: E402
from bench.engine.report import render_report_file  # noqa: E402
from bench.engine.schema_validation import load_schema, validate  # noqa: E402
from bench.engine.verify import format_verify_report, verify_artifacts  # noqa: E402


def parse_models(values: list[str]) -> list[str]:
    models: list[str] = []
    for value in values:
        models.extend(part.strip() for part in value.split(",") if part.strip())
    return models


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="aleph-bench")
    subparsers = parser.add_subparsers(dest="command", required=True)
    run = subparsers.add_parser("run", help="Run a frozen-ladder benchmark")
    run.add_argument("--track", default="F", choices=["F"])
    run.add_argument("--model", action="append", required=True, help="Model id; repeat or comma-separate")
    run.add_argument("--split", default="public")
    run.add_argument("--seed", type=int, default=0)
    run.add_argument("--out", required=True)
    run.add_argument("--data-dir", default=str(REPO_ROOT / "bench/data/public/s2"))
    run.add_argument("--tau", type=float, default=DEFAULT_TAU)
    run.add_argument("--k", type=int, default=DEFAULT_K)
    run.add_argument("--reruns", type=int, default=DEFAULT_RERUNS)
    run.add_argument("--bootstrap-samples", type=int, default=DEFAULT_BOOTSTRAP_SAMPLES)
    run.add_argument("--limit", type=int, default=None, help="Optional item limit for tests or smoke runs")
    run.add_argument("--cache-dir", default=None, help="Optional response cache directory for resumable adapter calls")
    doctor = subparsers.add_parser("doctor", help="Check dataset, leakage gate, model env, and call budget")
    doctor.add_argument("--model", action="append", default=[], help="Model id; repeat or comma-separate")
    doctor.add_argument("--data-dir", default=str(REPO_ROOT / "bench/data/public/s2"))
    doctor.add_argument("--reruns", type=int, default=DEFAULT_RERUNS)
    doctor.add_argument("--json", action="store_true", help="Emit machine-readable preflight JSON")
    manifest = subparsers.add_parser("manifest", help="Write a no-call manifest of non-leaking benchmark prompts")
    manifest.add_argument("--model", action="append", required=True, help="Model id; repeat or comma-separate")
    manifest.add_argument("--split", default="public")
    manifest.add_argument("--seed", type=int, default=0)
    manifest.add_argument("--out", required=True)
    manifest.add_argument("--data-dir", default=str(REPO_ROOT / "bench/data/public/s2"))
    manifest.add_argument("--reruns", type=int, default=DEFAULT_RERUNS)
    audit = subparsers.add_parser("audit", help="Run the M0 acceptance-gate audit")
    audit.add_argument("--data-dir", default=str(REPO_ROOT / "bench/data/public/s2"))
    audit.add_argument("--result", default=str(REPO_ROOT / "bench/results/m0-first-run.json"))
    audit.add_argument("--evidence-note", default=str(REPO_ROOT / "docs/benchmark/m0-evidence.md"))
    audit.add_argument("--json", action="store_true", help="Emit machine-readable audit JSON")
    audit.add_argument("--out", default=None, help="Optional JSON output path for the audit receipt")
    bundle = subparsers.add_parser("bundle", help="Build or check the M0 evidence bundle digest manifest")
    bundle.add_argument("--result", default=str(REPO_ROOT / "bench/results/m0-first-run.json"))
    bundle.add_argument("--manifest", default=str(REPO_ROOT / "bench/results/m0-call-manifest.json"))
    bundle.add_argument("--audit", default=str(REPO_ROOT / "bench/results/m0-audit.json"))
    bundle.add_argument("--report", default=str(REPO_ROOT / "bench/results/m0-report.md"))
    bundle.add_argument("--evidence-note", default=str(REPO_ROOT / "docs/benchmark/m0-evidence.md"))
    bundle.add_argument("--out", default=None, help="Optional JSON output path for the bundle manifest")
    bundle.add_argument("--check", default=None, help="Compare a checked-in bundle manifest with current files")
    bundle.add_argument("--json", action="store_true", help="Emit machine-readable bundle JSON")
    verify = subparsers.add_parser("verify", help="Validate benchmark dataset, result, and manifest artifacts")
    verify.add_argument("--data-dir", default=str(REPO_ROOT / "bench/data/public/s2"))
    verify.add_argument("--result", default=str(REPO_ROOT / "bench/results/m0-first-run.json"))
    verify.add_argument("--manifest", default=str(REPO_ROOT / "bench/results/m0-call-manifest.json"))
    verify.add_argument("--audit", default=None, help="Optional audit receipt JSON to validate with the bundle")
    verify.add_argument("--bundle", default=None, help="Optional evidence bundle JSON to validate against current files")
    verify.add_argument("--json", action="store_true", help="Emit machine-readable verification JSON")
    report = subparsers.add_parser("report", help="Render markdown tables from a BenchResult")
    report.add_argument("--result", default=str(REPO_ROOT / "bench/results/m0-first-run.json"))
    report.add_argument("--out", default=None, help="Optional markdown output path")
    package = subparsers.add_parser("package", help="Build or check the M0 platform release package")
    package.add_argument("--out-dir", default=str(DEFAULT_PACKAGE_DIR))
    package.add_argument("--check", default=None, help="Check an existing package-manifest.json")
    package.add_argument("--json", action="store_true", help="Emit machine-readable package report")
    validate_croissant = subparsers.add_parser(
        "validate-croissant",
        help="Validate a Croissant JSON-LD file with mlcroissant (must be installed)",
    )
    validate_croissant.add_argument("path", help="Path to croissant.json")
    validate_croissant.add_argument(
        "--records",
        action="append",
        default=[],
        help="Optional record set ids to stream end-to-end (repeat or comma-separate)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "doctor":
        models = parse_models(args.model)
        report = preflight(data_dir=Path(args.data_dir), models=models, reruns=args.reruns)
        if args.json:
            print(json.dumps(report, indent=2, sort_keys=True))
        else:
            print(format_preflight(report))
        return 0 if report["status"] == "ready" else 2
    if args.command == "manifest":
        models = parse_models(args.model)
        manifest = build_manifest(
            data_dir=Path(args.data_dir),
            models=models,
            split=args.split,
            seed=args.seed,
            reruns=args.reruns,
        )
        schema = load_schema(REPO_ROOT / "schemas/aleph-bench-manifest.schema.json")
        validate(manifest, schema)
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"wrote {out}")
        return 0
    if args.command == "audit":
        report = audit_m0_acceptance(
            data_dir=Path(args.data_dir),
            result_path=Path(args.result),
            evidence_note_path=Path(args.evidence_note),
        )
        schema = load_schema(REPO_ROOT / "schemas/aleph-bench-audit.schema.json")
        validate(report, schema)
        if args.out:
            out = Path(args.out)
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            print(f"wrote {out}")
        elif args.json:
            print(json.dumps(report, indent=2, sort_keys=True))
        else:
            print(format_audit_report(report))
        return 0 if report["status"] == "ok" else 2
    if args.command == "bundle":
        bundle = build_m0_bundle(
            result_path=Path(args.result),
            manifest_path=Path(args.manifest),
            audit_path=Path(args.audit),
            report_path=Path(args.report),
            evidence_note_path=Path(args.evidence_note),
        )
        schema = load_schema(REPO_ROOT / "schemas/aleph-bench-bundle.schema.json")
        validate(bundle, schema)
        if args.check:
            expected = json.loads(Path(args.check).read_text(encoding="utf-8"))
            validate(expected, schema)
            errors = compare_bundle(expected, bundle)
            if errors:
                print("status: failed")
                for error in errors:
                    print(f"error: {error}")
                return 2
            print(f"status: ok\nbundle: {args.check}")
            return 0
        if args.out:
            out = Path(args.out)
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(json.dumps(bundle, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            print(f"wrote {out}")
        elif args.json:
            print(json.dumps(bundle, indent=2, sort_keys=True))
        else:
            print(json.dumps(bundle, indent=2, sort_keys=True))
        return 0
    if args.command == "verify":
        report = verify_artifacts(
            data_dir=Path(args.data_dir),
            result_path=Path(args.result),
            manifest_path=Path(args.manifest),
            audit_path=Path(args.audit) if args.audit else None,
            bundle_path=Path(args.bundle) if args.bundle else None,
        )
        if args.json:
            print(json.dumps(report, indent=2, sort_keys=True))
        else:
            print(format_verify_report(report))
        return 0 if report["status"] == "ok" else 2
    if args.command == "report":
        markdown = render_report_file(Path(args.result))
        if args.out:
            out = Path(args.out)
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(markdown, encoding="utf-8")
            print(f"wrote {out}")
        else:
            print(markdown)
        return 0
    if args.command == "validate-croissant":
        try:
            import mlcroissant as mlc  # type: ignore[import-untyped]
        except ImportError as exc:
            print(
                "error: mlcroissant is not installed. "
                "Install with `pip install mlcroissant` to run this check.",
                file=sys.stderr,
            )
            raise SystemExit(2) from exc
        path = Path(args.path)
        ds = mlc.Dataset(jsonld=str(path))
        record_ids = parse_models(args.records) if args.records else [
            rs.id for rs in ds.metadata.record_sets
        ]
        summary: dict[str, int] = {}
        for record_id in record_ids:
            rows = list(ds.records(record_id))
            summary[record_id] = len(rows)
        print(json.dumps({
            "status": "ok",
            "path": str(path),
            "name": ds.metadata.name,
            "version": getattr(ds.metadata, "version", None),
            "recordSets": summary,
        }, indent=2, sort_keys=True))
        return 0
    if args.command == "package":
        if args.check:
            report = check_platform_package(Path(args.check))
            if args.json:
                print(json.dumps(report, indent=2, sort_keys=True))
            else:
                print(format_package_check(report))
            return 0 if report["status"] == "ok" else 2
        manifest = write_platform_package(Path(args.out_dir))
        if args.json:
            print(json.dumps(manifest, indent=2, sort_keys=True))
        else:
            print(f"wrote {Path(args.out_dir) / 'package-manifest.json'}")
        return 0
    if args.command != "run":
        raise AssertionError(args.command)
    models = parse_models(args.model)
    result = run_benchmark(
        data_dir=Path(args.data_dir),
        models=models,
        split=args.split,
        seed=args.seed,
        tau=args.tau,
        k=args.k,
        reruns=args.reruns,
        bootstrap_samples=args.bootstrap_samples,
        limit=args.limit,
        cache_dir=Path(args.cache_dir) if args.cache_dir else None,
    )
    schema = load_schema(REPO_ROOT / "schemas/aleph-bench-result.schema.json")
    validate(result, schema)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
