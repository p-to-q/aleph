"""Opt-in runner and independent re-verification CLI for the pinned MLX canary.

Usage (Apple Silicon host, from the repository root):

    search/.venv/bin/python -m search.engine.canary run \
        --bundle search/engine/receipts/aleph-mlx-canary-001 \
        --created-at 2026-10-15T00:00:00Z

    python3 -m search.engine.canary verify \
        --bundle search/engine/receipts/aleph-mlx-canary-001

``run`` resolves the pinned snapshot (never resolving ``main`` and never
substituting another revision), checks the pinned mlx/mlx-lm versions, runs
the hybrid search against the repository-authored smoke target, exports the
``AlephRun`` projection, and verifies the bundle from disk. ``verify`` re-runs
the independent verifier only; it needs no MLX and no network.

This module is deliberately not part of the default test suite or CI: the live
run requires Metal, the pinned snapshot, and the pinned runtime.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import subprocess
import sys
from pathlib import Path
from typing import Any

from .adapters import mlx as mlx_adapter
from .canonical import digest_bytes
from .export_aleph_run import export_aleph_run
from .fixtures import canary as canary_fixture
from .hybrid_pareto import run_hybrid_search
from .verify import verify_bundle

_REPO_ROOT = Path(__file__).resolve().parents[2]


def _git_commit() -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
            cwd=_REPO_ROOT,
        )
    except (OSError, subprocess.CalledProcessError) as error:
        raise mlx_adapter.MlxCanaryError(f"cannot record the producing Git commit: {error}") from error
    return result.stdout.strip()


def _git_tracked_dirty() -> bool:
    """True when tracked files (staged or unstaged) differ from the commit."""
    for args in (["git", "diff", "--quiet"], ["git", "diff", "--cached", "--quiet"]):
        result = subprocess.run(args, capture_output=True, text=True, cwd=_REPO_ROOT)
        if result.returncode != 0:
            return True
    return False


def _load_chat_template(snapshot: Path) -> str:
    payload = json.loads((snapshot / "tokenizer_config.json").read_text(encoding="utf-8"))
    template = payload.get("chat_template")
    if not isinstance(template, str) or not template:
        raise mlx_adapter.MlxPinError("tokenizer_config.json carries no chat_template to pin")
    return template


def run_canary(*, bundle: Path, created_at: str, run_id: str = canary_fixture.CANARY_RUN_ID) -> dict[str, Any]:
    """Run one live canary into ``bundle``; export, verify, and return a summary."""
    bundle = Path(bundle)
    snapshot = mlx_adapter.resolve_pinned_snapshot()
    resolved_files = mlx_adapter.snapshot_files(snapshot)
    mx, mlx_lm = mlx_adapter.require_pinned_runtime()
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    model, tokenizer = mlx_lm.load(str(snapshot))
    tokenizer_digest = digest_bytes((snapshot / "tokenizer.json").read_bytes())
    chat_template_digest = digest_bytes(_load_chat_template(snapshot).encode("utf-8"))
    probe_ids = tokenizer.apply_chat_template(
        [{"role": "user", "content": "canary probe"}],
        tokenize=True,
        add_generation_prompt=True,
        enable_thinking=False,
    )
    if not list(probe_ids):
        raise mlx_adapter.MlxCanaryError("pinned chat template rendered an empty prompt")
    placement = canary_fixture.canary_placement(
        tokenizer_digest=tokenizer_digest, chat_template_digest=chat_template_digest
    )
    config = canary_fixture.canary_config(placement)
    confirmation = canary_fixture.canary_confirmation()
    decoding = canary_fixture.canary_decoding()
    runtime = {
        "mlx": mx.__version__,
        "mlxLm": mlx_lm.__version__,
        "python": platform.python_version(),
        "platform": platform.platform(),
        "architecture": platform.machine(),
    }
    git_commit = _git_commit()
    pinned_model = f"{mlx_adapter.PINNED_MODEL}@{mlx_adapter.PINNED_REVISION}"
    model_manifest = canary_fixture.canary_manifest(
        model=pinned_model,
        revision=mlx_adapter.PINNED_REVISION,
        decoding=decoding,
        observation_mode="black_box",
        runtime=runtime,
        resolved_files=resolved_files,
        tokenizer_view=canary_fixture.CANARY_TOKENIZER_VIEW,
        tokenizer_digest=tokenizer_digest,
        chat_template_digest=chat_template_digest,
        git_commit=git_commit,
    )
    proposal = canary_fixture.CanaryOperatorProposalAdapter(canary_fixture.canary_proposal_identity())
    evaluation = mlx_adapter.MlxCanaryEvaluationAdapter(
        identity=canary_fixture.canary_evaluation_identity(
            model=pinned_model,
            revision=mlx_adapter.PINNED_REVISION,
            decoding=decoding,
            observation_mode="black_box",
            runtime=runtime,
        ),
        model=model,
        tokenizer=tokenizer,
        target_text=canary_fixture.CANARY_TARGET,
        tokenizer_view=canary_fixture.CANARY_TOKENIZER_VIEW,
        tokenizer_digest=tokenizer_digest,
        max_new_tokens=canary_fixture.CANARY_MAX_NEW_TOKENS,
        samples=canary_fixture.CANARY_SAMPLES,
    )
    target_tokens = len(
        [int(token) for token in tokenizer.encode(canary_fixture.CANARY_TARGET, add_special_tokens=False)]
    )

    def coordinate_cost(candidate: Any) -> Any:
        return mlx_adapter.canary_coordinate_cost(
            candidate,
            tokenizer=tokenizer,
            tokenizer_view=canary_fixture.CANARY_TOKENIZER_VIEW,
            tokenizer_digest=tokenizer_digest,
            target_tokens=target_tokens,
        )

    result = run_hybrid_search(
        bundle,
        run_id,
        config,
        confirmation,
        proposal,
        evaluation,
        target_digest=canary_fixture.canary_target_digest(),
        known_metrics=canary_fixture.CANARY_METRICS,
        target_content=canary_fixture.CANARY_TARGET,
        nesting_rule=canary_fixture.CANARY_NESTING_RULE,
        scheduler_model=canary_fixture.CANARY_SCHEDULER_MODEL,
        model_manifest=model_manifest,
        coordinate_cost=coordinate_cost,
        run_created_at=created_at,
    )
    export = export_aleph_run(bundle)
    report = verify_bundle(bundle)
    summary = {
        "runId": result.run_id,
        "bundle": str(bundle),
        "status": result.status,
        "confirmationOutcome": result.confirmation_outcome,
        "confirmedCandidateId": result.confirmed_candidate_id,
        "shortlistCandidateIds": list(result.shortlist_candidate_ids),
        "selectedCandidateId": export.projection.get("selectedCandidateId"),
        "projectedCandidates": len(export.projection.get("candidates", [])),
        "omittedCandidateIds": list(export.omitted_candidate_ids),
        "streamDigest": report.stream_digest,
        "materializedDigests": report.materialized_digests,
        "projectionDigest": export.projection_record.get("artifactRef", {}).get("projectionDigest"),
        "exportDigests": dict(export.digests),
        "verify": report.payload(),
        "pins": {
            "model": mlx_adapter.PINNED_MODEL,
            "revision": mlx_adapter.PINNED_REVISION,
            "mlx": mlx_adapter.PINNED_MLX_VERSION,
            "mlxLm": mlx_adapter.PINNED_MLX_LM_VERSION,
        },
        "resolvedFiles": [dict(item) for item in resolved_files],
        "gitCommit": git_commit,
        "gitTrackedDirty": _git_tracked_dirty(),
    }
    if not report.ok:
        raise mlx_adapter.MlxCanaryError(
            "canary bundle failed verification: " + "; ".join(report.errors)
        )
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="search.engine.canary",
        description="Pinned MLX canary runner and independent verifier (PR C of #106).",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    run_parser = subparsers.add_parser("run", help="run the live canary into a fresh bundle directory")
    run_parser.add_argument("--bundle", required=True, type=Path)
    run_parser.add_argument(
        "--created-at",
        required=True,
        help="caller-declared run timestamp carried on run_started (the kernel never reads the wall clock)",
    )
    run_parser.add_argument("--run-id", default=canary_fixture.CANARY_RUN_ID)
    verify_parser = subparsers.add_parser(
        "verify", help="re-verify a canary bundle from disk (no MLX needed)"
    )
    verify_parser.add_argument("--bundle", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == "run":
            summary = run_canary(bundle=args.bundle, created_at=args.created_at, run_id=args.run_id)
            print(json.dumps(summary, indent=2, sort_keys=True))
            return 0
        report = verify_bundle(args.bundle)
        print(json.dumps(report.payload(), indent=2, sort_keys=True))
        return 0 if report.ok else 1
    except mlx_adapter.MlxCanaryError as error:
        print(f"canary error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
