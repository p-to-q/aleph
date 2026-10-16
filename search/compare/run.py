"""Instance driver for matched-budget comparisons (pure standard library).

Drives one declared comparison instance to completion by spawning the two
heavy steps as bounded, resumable subprocesses:

- raw side: ``python -m search.miniprompt.cli run --preset … --run-dir …``
- readable side: ``python -m search.compare.readable --instance … --target-key …``

Slices are re-spawned per invocation (the model load cost is the price of
staying inside tool-call budgets); both children persist state atomically, so
a killed slice only re-runs its unfinished operation. The driver enforces the
shared wall-clock envelope on the recorded operation seconds (raw: receipt
trajectory seconds; readable: the artifact's recorded ``wallClockSeconds``)
and never archives a comparison whose sides exceed the envelope plus the
declared slack. After both sides complete it builds the digest-bound
comparison record and self-verifies it against the on-disk artifacts before
writing ``comparison.json``.

Exit codes: 0 complete, 1 failure, 3 paused by the invocation time budget
(re-run the same command to resume; artifacts on disk are the checkpoint).
"""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

from search.miniprompt.receipts import verify_receipt, write_json_atomic

from . import fixtures
from .record import (
    ENVELOPE_SLACK_SECONDS,
    build_comparison_record,
    load_json_strict,
    raw_wall_clock_seconds,
    verify_comparison,
    verify_readable,
)

SLICE_CAP_SECONDS = 150
MIN_SLICE_REMAINING = 60
WORKER_SAFETY_SECONDS = 540


class RunInstanceError(RuntimeError):
    """The comparison instance cannot be driven to a consistent archive."""


def utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _append_log(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(text)


def _raw_receipt_path(instance_dir: Path) -> Path:
    return instance_dir / "raw" / "receipt.json"


def _load_raw(instance_dir: Path, spec) -> dict | None:
    path = _raw_receipt_path(instance_dir)
    if not path.is_file():
        return None
    receipt = load_json_strict(path)
    errors = verify_receipt(receipt)
    if errors:
        # Never re-run over an inconsistent receipt: fail closed.
        raise RunInstanceError(f"raw receipt fails verification: {errors[:3]}")
    if receipt.get("configDigest") != spec.raw_config_digest:
        raise RunInstanceError("raw receipt belongs to a different declared preset digest")
    return receipt


def _load_readable(instance_dir: Path, config) -> dict | None:
    path = instance_dir / "readable.json"
    if not path.is_file():
        return None
    doc = load_json_strict(path)
    errors = verify_readable(doc)
    if errors:
        raise RunInstanceError(f"readable artifact fails verification: {errors[:3]}")
    if doc.get("configDigest") != config.digest or doc.get("instance") != config.label:
        raise RunInstanceError("readable artifact belongs to a different declaration")
    return doc


def raw_seconds(instance_dir: Path, receipt: dict | None) -> float:
    """Recorded raw-side seconds: receipt trajectories, else the run state."""
    if receipt is not None:
        return raw_wall_clock_seconds(receipt)
    state_path = instance_dir / "raw" / "state.json"
    if not state_path.is_file():
        return 0.0
    state = load_json_strict(state_path)
    total = 0.0
    for attempt in state.get("attempts") or []:
        for step in attempt.get("trajectory") or []:
            total += float(step["seconds"])
    current = state.get("current") or {}
    for step in current.get("trajectory") or []:
        total += float(step["seconds"])
    return total


def readable_seconds(instance_dir: Path, doc: dict | None) -> float:
    """Recorded readable-side seconds: the artifact value, else the run state."""
    if doc is not None:
        return float(doc["wallClockSeconds"])
    state_path = instance_dir / "readable-state.json"
    if not state_path.is_file():
        return 0.0
    state = load_json_strict(state_path)
    total = 0.0
    for value in (state.get("recordedSeconds") or {}).values():
        total += float(value)
    return total


def _run_slice(cmd, log_path: Path, log, *, timeout: float):
    """Run one child slice; returns ``(returncode_or_None, timed_out, tail)``."""
    started = time.monotonic()
    try:
        proc = subprocess.run(cmd, cwd=str(repo_root()), capture_output=True, text=True, timeout=timeout)
        rc, out, err = proc.returncode, proc.stdout or "", proc.stderr or ""
        timed_out = False
    except subprocess.TimeoutExpired as exc:
        rc, timed_out = None, True
        out = exc.stdout if isinstance(exc.stdout, str) else ""
        err = exc.stderr if isinstance(exc.stderr, str) else ""
    elapsed = time.monotonic() - started
    block = (
        f"\n$ {' '.join(cmd)}\n"
        f"[driver] head={cmd[3] if len(cmd) > 3 else '?'} rc={rc} timedOut={timed_out} "
        f"slice={elapsed:.1f}s\n{out}{err}"
    )
    _append_log(log_path, block)
    tail = (out + err).strip().splitlines()[-3:]
    return rc, timed_out, " | ".join(tail)


def run_instance(name: str, run_dir, *, max_seconds=300.0, log=print) -> int:
    """Run or resume one instance. Returns 0 complete, 1 failure, 3 paused."""
    config = fixtures.instance(name)
    run_dir = Path(run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)
    comparison_path = run_dir / "comparison.json"

    if comparison_path.is_file():
        record_obj = load_json_strict(comparison_path)
        errors = verify_comparison(record_obj, run_dir)
        if errors:
            raise RunInstanceError(f"existing comparison record fails verification: {errors[:3]}")
        log(f"comparison already complete and verified: {comparison_path}")
        return 0

    limits = config.envelope_seconds + ENVELOPE_SLACK_SECONDS
    started = time.monotonic()
    hard_deadline = started + float(max_seconds)
    worker_safety = started + WORKER_SAFETY_SECONDS

    while True:
        pending = []
        for spec in config.targets:
            instance_dir = run_dir / "targets" / spec.key
            receipt = _load_raw(instance_dir, spec)
            doc = _load_readable(instance_dir, config)
            seconds_raw = raw_seconds(instance_dir, receipt)
            seconds_readable = readable_seconds(instance_dir, doc)
            if seconds_raw > limits:
                log(f"target {spec.key!r}: raw side exceeded the shared envelope "
                    f"({seconds_raw:.1f}s > {limits}s); this comparison cannot be archived")
                return 1
            if seconds_readable > limits:
                log(f"target {spec.key!r}: readable side exceeded the shared envelope "
                    f"({seconds_readable:.1f}s > {limits}s); this comparison cannot be archived")
                return 1
            if receipt is None:
                pending.append((spec, "raw", instance_dir))
            if doc is None:
                pending.append((spec, "readable", instance_dir))

        if not pending:
            payloads = []
            for spec in config.targets:
                instance_dir = run_dir / "targets" / spec.key
                receipt = _load_raw(instance_dir, spec)
                doc = _load_readable(instance_dir, config)
                if receipt is None or doc is None:
                    raise RunInstanceError("internal error: building before both sides completed")
                payloads.append(
                    {
                        "key": spec.key,
                        "raw": {
                            "receipt": receipt,
                            "wallClockSeconds": round(raw_wall_clock_seconds(receipt), 1),
                        },
                        "readable": {
                            "doc": doc,
                            "wallClockSeconds": round(float(doc["wallClockSeconds"]), 1),
                        },
                    }
                )
            record_obj = build_comparison_record(
                config=config,
                targets=payloads,
                created_at=utc_now(),
                base_dir=run_dir,
            )
            errors = verify_comparison(record_obj, run_dir)
            if errors:
                raise RunInstanceError(f"the built comparison record failed self-verification: {errors[:3]}")
            write_json_atomic(comparison_path, record_obj)
            log(f"comparison.json written: {comparison_path}")
            return 0

        for spec, side, instance_dir in pending:
            remaining = hard_deadline - time.monotonic()
            safety_left = worker_safety - time.monotonic()
            if min(remaining, safety_left) < MIN_SLICE_REMAINING:
                log("invocation budget reached; the instance is incomplete — re-run the same command to resume")
                return 3
            seconds = int(max(30.0, min(float(SLICE_CAP_SECONDS), remaining - 40.0)))
            timeout = max(60.0, min(seconds + 300.0, safety_left))

            if side == "raw":
                cmd = [
                    sys.executable, "-m", "search.miniprompt.cli", "run",
                    "--preset", spec.raw_preset,
                    "--run-dir", str(instance_dir / "raw"),
                    "--max-seconds", str(seconds),
                ]
                log_path = instance_dir / "raw" / "cli-output.txt"
            else:
                cmd = [
                    sys.executable, "-m", "search.compare.readable",
                    "--instance", config.label,
                    "--target-key", spec.key,
                    "--run-dir", str(instance_dir),
                    "--max-seconds", str(seconds),
                ]
                log_path = instance_dir / "readable.cli-output.txt"

            log(f"[driver] target {spec.key!r} {side}: slice {seconds}s")
            rc, timed_out, tail = _run_slice(cmd, log_path, log, timeout=timeout)
            if timed_out:
                log(f"[driver] target {spec.key!r} {side}: slice timed out (killed; state on disk resumes)")
                continue
            if rc not in (0, 3):
                log(f"[driver] target {spec.key!r} {side}: slice failed rc={rc}: {tail}")
                return 1
            log(f"[driver] target {spec.key!r} {side}: rc={rc} {('— paused, resumes' if rc == 3 else '— complete')}")

        if time.monotonic() >= hard_deadline:
            return 3
