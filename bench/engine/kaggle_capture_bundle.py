from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .kaggle_capture_evidence import materialize_legacy_capture_bundle


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Materialize one verified legacy flat Kaggle capture directory "
            "as a new closed-world bundle without changing the source files."
        )
    )
    parser.add_argument("--evidence", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)
    try:
        bundle = materialize_legacy_capture_bundle(
            args.evidence,
            args.output,
        )
    except (OSError, ValueError) as exc:
        print(f"cannot materialize capture bundle: {exc}", file=sys.stderr)
        print(
            "the exclusive output may now contain a partial artifact; "
            "do not reuse or overwrite it, and audit it manually before "
            "any explicit removal",
            file=sys.stderr,
        )
        return 1
    print(
        f"materialized verified capture bundle {bundle.evidence['id']} "
        f"at {bundle.evidence_path.parent}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
