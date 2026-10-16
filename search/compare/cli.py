"""Command-line entry points for matched-budget comparison instances.

::

    python -m search.compare.cli run --instance canary-1p7b --run-dir DIR [--max-seconds N]
    python -m search.compare.cli verify PATH

``run`` needs the pinned MLX environment (``search/.venv``) for its child
slices; ``verify`` is pure standard library and re-checks a comparison record
and both side artifacts without MLX, the model, or the network. Exit codes:
0 complete, 1 failure, 2 usage, 3 paused by the invocation time budget
(re-run the same command to resume).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import fixtures
from .record import load_json_strict, verify_comparison


def _resolve_record(path: Path) -> Path:
    return path / "comparison.json" if path.is_dir() else path


def cmd_run(args) -> int:
    from . import run  # lazy: spawns the MLX-backed child slices

    try:
        return run.run_instance(args.instance, args.run_dir, max_seconds=args.max_seconds)
    except run.RunInstanceError as exc:
        print(f"FAIL: {exc}")
        return 1


def cmd_verify(args) -> int:
    path = _resolve_record(Path(args.path))
    if not path.is_file():
        print(f"FAIL: no comparison record at {path}")
        return 1
    try:
        record = load_json_strict(path)
    except ValueError as exc:
        print(f"FAIL {path}: unreadable record ({exc})")
        return 1
    errors = verify_comparison(record, path.parent)
    if errors:
        print(f"FAIL {path}")
        for error in errors:
            print(f" - {error}")
        return 1
    totals = record["totals"]
    print(
        f"OK {path} targets={totals['targets']} rawAcquired={totals['rawAcquired']} "
        f"readableFoundUnderTau={totals['readableFoundUnderTau']}"
    )
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m search.compare.cli",
        description="Matched-budget comparison between MiniPrompt raw coordinates and Aleph's readable search.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="run or resume a declared instance (needs the pinned MLX venv)")
    run.add_argument(
        "--instance",
        required=True,
        choices=sorted(fixtures.INSTANCES),
        help="declared comparison instance name",
    )
    run.add_argument("--run-dir", required=True, help="instance directory (comparison.json + targets/)")
    run.add_argument(
        "--max-seconds",
        type=float,
        default=300.0,
        help="pause after roughly this many seconds; re-run the same command to resume (default 300)",
    )
    run.set_defaults(func=cmd_run)

    verify = sub.add_parser("verify", help="fail-closed record verification (no MLX, no network)")
    verify.add_argument("path", help="comparison.json file or instance directory")
    verify.set_defaults(func=cmd_verify)

    args = parser.parse_args(argv)
    if args.command == "run":
        return cmd_run(args)
    if args.command == "verify":
        return cmd_verify(args)
    parser.print_usage(sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
