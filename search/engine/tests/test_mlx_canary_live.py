"""Live pinned MLX canary; skipped unless explicitly enabled.

The default suite and CI never require Metal: this test runs only when
``ALEPH_RUN_MLX_CANARY=1`` and the pinned snapshot and runtime are available
on the host (Apple Silicon, mlx 0.31.2, mlx-lm 0.31.3).
"""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path


def _skip_reason() -> str | None:
    if os.environ.get("ALEPH_RUN_MLX_CANARY") != "1":
        return "set ALEPH_RUN_MLX_CANARY=1 to run the live MLX canary"
    try:
        import mlx.core  # noqa: F401
        import mlx_lm  # noqa: F401
    except Exception as error:  # noqa: BLE001
        return f"MLX runtime unavailable: {error}"
    from search.engine.adapters.mlx import MlxPinError, resolve_pinned_snapshot

    try:
        resolve_pinned_snapshot()
    except MlxPinError as error:
        return str(error)
    return None


_SKIP_REASON = _skip_reason()


@unittest.skipIf(_SKIP_REASON is not None, _SKIP_REASON or "")
class LiveCanaryTest(unittest.TestCase):
    def test_run_canary_bundle_verifies(self) -> None:
        from search.engine import canary
        from search.engine.verify import verify_bundle

        with tempfile.TemporaryDirectory(prefix="aleph-mlx-live-") as tmp:
            bundle = Path(tmp) / "bundle"
            summary = canary.run_canary(bundle=bundle, created_at="2026-10-15T00:00:00Z")
            self.assertTrue(summary["verify"]["ok"])
            report = verify_bundle(bundle)
            self.assertTrue(report.ok, report.errors)


if __name__ == "__main__":
    unittest.main()
