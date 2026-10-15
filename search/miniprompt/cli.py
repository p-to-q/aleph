"""Command-line entry points for MiniPrompt reproduction runs.

    python -m search.miniprompt.cli run --preset canary-hello --run-dir DIR [--max-seconds N]
    python -m search.miniprompt.cli run --config FILE --run-dir DIR [--max-seconds N]
    python -m search.miniprompt.cli verify PATH

``run`` needs the pinned MLX environment (``search/.venv``) and imports the MLX
execution path lazily; ``verify`` is pure standard library and re-checks a
receipt (a receipt file or a run directory) without MLX or network. Exit
codes: 0 complete, 1 failure, 2 usage, 3 paused by the time budget (re-run the
same command to resume).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import fixtures, receipts


def _resolve_receipt(path: Path) -> Path:
    return path / "receipt.json" if path.is_dir() else path


def cmd_verify(args) -> int:
    path = _resolve_receipt(Path(args.path))
    if not path.is_file():
        print(f"FAIL: no receipt at {path}")
        return 1
    try:
        receipt = receipts.load_receipt(path)
    except ValueError as exc:
        print(f"FAIL {path}: unreadable receipt ({exc})")
        return 1
    errors = receipts.verify_receipt(receipt)
    if errors:
        print(f"FAIL {path}")
        for error in errors:
            print(f" - {error}")
        return 1
    result = receipt["result"]
    print(
        f"OK {path} success={result['success']} numFreeTokens={result['numFreeTokens']} "
        f"attempts={result['attempts']} stopReason={result['stopReason']}"
    )
    return 0


def cmd_run(args) -> int:
    if args.preset:
        config = fixtures.preset(args.preset)
    else:
        from .config import load_config_file

        config = load_config_file(args.config)
    from . import runner  # lazy: pulls in the MLX execution path

    return runner.run_scan(config, args.run_dir, max_seconds=args.max_seconds)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m search.miniprompt.cli",
        description="MiniPrompt/ACR raw-coordinate baseline: declared scans with receipts.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="run or resume a declared scan (needs the pinned MLX venv)")
    source = run.add_mutually_exclusive_group(required=True)
    source.add_argument("--preset", choices=sorted(fixtures.PRESETS), help="declared preset name")
    source.add_argument("--config", help="path to a declared configuration JSON file")
    run.add_argument("--run-dir", required=True, help="run directory (state.json + receipt.json)")
    run.add_argument(
        "--max-seconds",
        type=float,
        default=None,
        help="pause after this many seconds; re-run the same command to resume",
    )
    run.set_defaults(func=cmd_run)

    verify = sub.add_parser("verify", help="fail-closed receipt verification (no MLX, no network)")
    verify.add_argument("path", help="receipt file or run directory")
    verify.set_defaults(func=cmd_verify)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
