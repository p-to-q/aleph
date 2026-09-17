#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
V2_DATA_DIR = REPO_ROOT / "bench/data/v0.2/public/s2"
V2_SCHEMA_DIR = REPO_ROOT / "schemas/v0.2"
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from bench.engine.frozen_ladder import (  # noqa: E402
    run_benchmark,
)
from bench.engine.audit import format_audit_report  # noqa: E402
from bench.engine.bundle import build_m0_bundle, compare_bundle  # noqa: E402
from bench.engine.manifest import build_manifest  # noqa: E402
from bench.engine.kaggle_receipt import (  # noqa: E402
    DEFAULT_SATURATION_MARGIN_TOKENS,
    DEFAULT_V0_1_PACKAGE_ROOT,
    build_kaggle_receipt,
    validate_kaggle_replay_output_path,
    write_new_kaggle_receipt,
)
from bench.engine.legacy_v0_1 import (  # noqa: E402
    assert_not_v0_1_write,
    safe_write_text,
    verify_v0_1_repository_receipt,
)
from bench.engine.platform_package import (  # noqa: E402
    check_platform_package,
    format_package_check,
)
from bench.engine.platform_package_v0_2 import (  # noqa: E402
    check_v0_2_package,
    format_v0_2_package_check,
    write_v0_2_package,
)
from bench.engine.preflight import format_preflight, preflight  # noqa: E402
from bench.engine.report import render_report_file  # noqa: E402
from bench.engine.schema_validation import (  # noqa: E402
    SchemaValidationError,
    load_schema,
    validate,
)
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
    run.add_argument("--model", action="append", required=True, help="Model id; repeat or comma-separate")
    run.add_argument("--seed", type=int, default=0)
    run.add_argument("--out", required=True)
    run.add_argument("--data-dir", default=str(V2_DATA_DIR))
    run.add_argument("--cache-dir", default=None, help="Optional response cache directory for resumable adapter calls")
    doctor = subparsers.add_parser("doctor", help="Check dataset, leakage gate, model env, and call budget")
    doctor.add_argument("--model", action="append", default=[], help="Model id; repeat or comma-separate")
    doctor.add_argument("--data-dir", default=str(V2_DATA_DIR))
    doctor.add_argument("--json", action="store_true", help="Emit machine-readable preflight JSON")
    manifest = subparsers.add_parser("manifest", help="Write a no-call manifest of non-leaking benchmark prompts")
    manifest.add_argument("--model", action="append", required=True, help="Model id; repeat or comma-separate")
    manifest.add_argument("--seed", type=int, default=0)
    manifest.add_argument("--out", required=True)
    manifest.add_argument("--data-dir", default=str(V2_DATA_DIR))
    audit = subparsers.add_parser(
        "audit",
        help="Verify the immutable v0.1 audit receipt without replaying its scorer",
    )
    audit.add_argument("--json", action="store_true", help="Emit machine-readable audit JSON")
    bundle = subparsers.add_parser("bundle", help="Check the immutable v0.1 evidence bundle")
    bundle.add_argument("--result", default=str(REPO_ROOT / "bench/results/m0-first-run.json"))
    bundle.add_argument("--manifest", default=str(REPO_ROOT / "bench/results/m0-call-manifest.json"))
    bundle.add_argument("--audit", default=str(REPO_ROOT / "bench/results/m0-audit.json"))
    bundle.add_argument("--report", default=str(REPO_ROOT / "bench/results/m0-report.md"))
    bundle.add_argument("--evidence-note", default=str(REPO_ROOT / "docs/benchmark/m0-evidence.md"))
    bundle.add_argument(
        "--check",
        default=str(REPO_ROOT / "bench/results/m0-bundle.json"),
        help="Compare the immutable bundle manifest with current files",
    )
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
    package = subparsers.add_parser("package", help="Check the immutable v0.1 platform package")
    package.add_argument("--check", required=True, help="Check the v0.1 package-manifest.json")
    package.add_argument("--json", action="store_true", help="Emit machine-readable package report")
    package_v0_2 = subparsers.add_parser(
        "package-v0.2",
        help="Build or check a v0.2 scorer conformance package",
    )
    package_v0_2.add_argument("--out-dir", default=None)
    package_v0_2.add_argument("--check", default=None)
    package_v0_2.add_argument("--json", action="store_true")
    kaggle_replay = subparsers.add_parser(
        "kaggle-replay",
        help="Replay a completed legacy Kaggle run into a canonical detailed receipt",
    )
    kaggle_replay.add_argument("--run-json", required=True)
    kaggle_replay.add_argument(
        "--package-root",
        default=str(DEFAULT_V0_1_PACKAGE_ROOT),
        help="Receipt-identical immutable v0.1 platform package",
    )
    kaggle_replay.add_argument(
        "--max-tokens",
        required=True,
        type=int,
        help=(
            "Operator-asserted max_tokens; the legacy run JSON does not prove "
            "this invocation argument"
        ),
    )
    kaggle_replay.add_argument(
        "--saturation-margin-tokens",
        type=int,
        default=DEFAULT_SATURATION_MARGIN_TOKENS,
        help="Treat usage within this many tokens of max_tokens as near-cap",
    )
    kaggle_replay.add_argument("--out", required=True)
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
        report = preflight(data_dir=Path(args.data_dir), models=models)
        if args.json:
            print(json.dumps(report, indent=2, sort_keys=True))
        else:
            print(format_preflight(report))
        return 0 if report["status"] == "ready" else 2
    if args.command == "manifest":
        out = Path(args.out)
        assert_not_v0_1_write(out)
        models = parse_models(args.model)
        manifest = build_manifest(
            data_dir=Path(args.data_dir),
            models=models,
            seed=args.seed,
        )
        schema = load_schema(V2_SCHEMA_DIR / "aleph-bench-manifest.schema.json")
        validate(manifest, schema)
        safe_write_text(
            out,
            json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        )
        print(f"wrote {out}")
        return 0
    if args.command == "audit":
        receipt_errors = verify_v0_1_repository_receipt()
        if receipt_errors:
            print("status: failed")
            for error in receipt_errors:
                print(f"error: {error}")
            return 2
        report = json.loads(
            (REPO_ROOT / "bench/results/m0-audit.json").read_text(encoding="utf-8")
        )
        schema = load_schema(REPO_ROOT / "schemas/aleph-bench-audit.schema.json")
        validate(report, schema)
        if args.json:
            print(json.dumps(report, indent=2, sort_keys=True))
        else:
            print(format_audit_report(report))
        return 0 if report["status"] == "ok" else 2
    if args.command == "bundle":
        canonical_paths = {
            "result": REPO_ROOT / "bench/results/m0-first-run.json",
            "manifest": REPO_ROOT / "bench/results/m0-call-manifest.json",
            "audit": REPO_ROOT / "bench/results/m0-audit.json",
            "report": REPO_ROOT / "bench/results/m0-report.md",
            "evidence note": REPO_ROOT / "docs/benchmark/m0-evidence.md",
            "bundle": REPO_ROOT / "bench/results/m0-bundle.json",
        }
        supplied_paths = {
            "result": Path(args.result),
            "manifest": Path(args.manifest),
            "audit": Path(args.audit),
            "report": Path(args.report),
            "evidence note": Path(args.evidence_note),
            "bundle": Path(args.check),
        }
        for role, expected_path in canonical_paths.items():
            if supplied_paths[role].resolve(strict=False) != expected_path.resolve(
                strict=False
            ):
                raise ValueError(
                    "immutable v0.1 bundle check requires canonical "
                    f"{role} path {expected_path.relative_to(REPO_ROOT)}"
                )
        receipt_errors = verify_v0_1_repository_receipt()
        if receipt_errors:
            raise ValueError(
                "immutable v0.1 receipt failed: " + "; ".join(receipt_errors)
            )
        bundle = build_m0_bundle(
            result_path=Path(args.result),
            manifest_path=Path(args.manifest),
            audit_path=Path(args.audit),
            report_path=Path(args.report),
            evidence_note_path=Path(args.evidence_note),
        )
        schema = load_schema(REPO_ROOT / "schemas/aleph-bench-bundle.schema.json")
        validate(bundle, schema)
        expected = json.loads(Path(args.check).read_text(encoding="utf-8"))
        validate(expected, schema)
        errors = compare_bundle(expected, bundle)
        if errors:
            print("status: failed")
            for error in errors:
                print(f"error: {error}")
            return 2
        if args.json:
            print(json.dumps(bundle, indent=2, sort_keys=True))
        else:
            print(f"status: ok\nbundle: {args.check}")
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
            assert_not_v0_1_write(out)
            safe_write_text(out, markdown)
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
        report = check_platform_package(Path(args.check))
        if args.json:
            print(json.dumps(report, indent=2, sort_keys=True))
        else:
            print(format_package_check(report))
        return 0 if report["status"] == "ok" else 2
    if args.command == "package-v0.2":
        if bool(args.out_dir) == bool(args.check):
            raise SystemExit("package-v0.2 requires exactly one of --out-dir or --check")
        if args.check:
            report = check_v0_2_package(Path(args.check))
            if args.json:
                print(json.dumps(report, indent=2, sort_keys=True))
            else:
                print(format_v0_2_package_check(report))
            return 0 if report["status"] == "ok" else 2
        out_dir = Path(args.out_dir)
        manifest = write_v0_2_package(out_dir)
        if args.json:
            print(json.dumps(manifest, indent=2, sort_keys=True))
        else:
            print(f"wrote {out_dir / 'package-manifest.json'}")
        return 0
    if args.command == "kaggle-replay":
        run_json_path = Path(args.run_json)
        package_root = Path(args.package_root)
        out = validate_kaggle_replay_output_path(
            run_json_path=run_json_path,
            package_root=package_root,
            out=Path(args.out),
        )
        receipt = build_kaggle_receipt(
            run_json_path=run_json_path,
            package_root=package_root,
            max_tokens=args.max_tokens,
            saturation_margin_tokens=args.saturation_margin_tokens,
        )
        write_new_kaggle_receipt(out, receipt)
        summary = {
            "status": receipt["diagnostics"]["status"],
            "receipt": str(out),
            "id": receipt["id"],
            "rowCount": receipt["rowCount"],
            "emptyRowCount": len(receipt["diagnostics"]["emptyRowIds"]),
            "invalidUsageRowCount": len(
                receipt["diagnostics"]["invalidUsageRowIds"]
            ),
            "nearCapRowCount": len(receipt["diagnostics"]["nearCapRowIds"]),
            "leaderboardScalar": receipt["leaderboardScalar"],
            "replayedScalar": receipt["replayedScalar"],
        }
        print(json.dumps(summary, indent=2, sort_keys=True))
        return 0 if receipt["diagnostics"]["status"] == "valid" else 2
    if args.command != "run":
        raise AssertionError(args.command)
    out = Path(args.out)
    assert_not_v0_1_write(out)
    if args.cache_dir:
        assert_not_v0_1_write(Path(args.cache_dir), recursive=True)
    models = parse_models(args.model)
    result = run_benchmark(
        data_dir=Path(args.data_dir),
        models=models,
        seed=args.seed,
        cache_dir=Path(args.cache_dir) if args.cache_dir else None,
    )
    schema = load_schema(V2_SCHEMA_DIR / "aleph-bench-result.schema.json")
    validate(result, schema)
    safe_write_text(out, json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (json.JSONDecodeError, OSError, RuntimeError, SchemaValidationError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(2) from None
