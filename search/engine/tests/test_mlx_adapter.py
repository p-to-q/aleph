"""Unit tests for the pinned MLX canary adapter (no MLX required).

The adapter module must import without MLX, pin checks and snapshot
resolution must fail closed, and the declared metric helpers are exercised
with plain token lists and a stub tokenizer. The live canary is covered by
``test_mlx_canary_live.py`` (skipped unless explicitly enabled).
"""

from __future__ import annotations

import hashlib
import re
import tempfile
import unittest
from pathlib import Path

from search.engine.adapters import mlx as mlx_adapter
from search.engine.canonical import digest
from search.engine.contracts import Candidate, Message, Placement

_PLACEMENT = Placement(
    scaffold_id="test-scaffold/0.1.0",
    scaffold_digest=digest({"test": "scaffold"}),
    prompt_position="messages[0]",
    rendered_template_version="test-template/0.1.0",
)


def _candidate(*texts: str) -> Candidate:
    return Candidate(
        messages=tuple(Message(role="user", content=text) for text in texts),
        placement=_PLACEMENT,
        proposal_mode="seed",
    )


class PinTest(unittest.TestCase):
    def test_pin_constants(self) -> None:
        self.assertTrue(re.fullmatch(r"[0-9a-f]{40}", mlx_adapter.PINNED_REVISION))
        self.assertEqual(mlx_adapter.PINNED_MLX_VERSION, "0.31.2")
        self.assertEqual(mlx_adapter.PINNED_MLX_LM_VERSION, "0.31.3")
        self.assertIn("/", mlx_adapter.PINNED_MODEL)

    def test_check_pinned_versions(self) -> None:
        mlx_adapter.check_pinned_versions("0.31.2", "0.31.3")
        with self.assertRaises(mlx_adapter.MlxPinError):
            mlx_adapter.check_pinned_versions("0.31.1", "0.31.3")
        with self.assertRaises(mlx_adapter.MlxPinError):
            mlx_adapter.check_pinned_versions("0.31.2", "0.31.4")

    def test_resolve_fails_closed_when_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(mlx_adapter.MlxPinError) as caught:
                mlx_adapter.resolve_pinned_snapshot(Path(tmp))
        self.assertIn(mlx_adapter.PINNED_REVISION, str(caught.exception))

    def test_resolve_never_substitutes_another_revision(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            other = (
                Path(tmp)
                / f"models--{mlx_adapter.PINNED_MODEL.replace('/', '--')}"
                / "snapshots"
                / ("0" * 40)
            )
            other.mkdir(parents=True)
            for name in ("config.json", "tokenizer.json", "tokenizer_config.json"):
                (other / name).write_text("{}", encoding="utf-8")
            (other / "model.safetensors").write_bytes(b"stub")
            with self.assertRaises(mlx_adapter.MlxPinError):
                mlx_adapter.resolve_pinned_snapshot(Path(tmp))

    def _make_snapshot(self, root: Path) -> Path:
        snapshot = mlx_adapter.pinned_snapshot_path(root)
        snapshot.mkdir(parents=True)
        (snapshot / "config.json").write_text('{"model_type": "test"}', encoding="utf-8")
        (snapshot / "tokenizer.json").write_text('{"tokenizer": true}', encoding="utf-8")
        (snapshot / "tokenizer_config.json").write_text('{"chat_template": "x"}', encoding="utf-8")
        (snapshot / "model.safetensors").write_bytes(b"stub-weights")
        return snapshot

    def test_resolve_pinned_snapshot_found(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            snapshot = self._make_snapshot(Path(tmp))
            self.assertEqual(mlx_adapter.resolve_pinned_snapshot(Path(tmp)), snapshot)

    def test_snapshot_files_records_digests(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            snapshot = self._make_snapshot(Path(tmp))
            records = mlx_adapter.snapshot_files(snapshot)
            by_path = {record["path"]: record for record in records}
            self.assertIn("model.safetensors", by_path)
            expected = hashlib.sha256(b"stub-weights").hexdigest()
            self.assertEqual(by_path["model.safetensors"]["sha256"], f"sha256:{expected}")
            self.assertEqual(by_path["model.safetensors"]["bytes"], len(b"stub-weights"))

    def test_snapshot_files_requires_weights(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            snapshot = self._make_snapshot(Path(tmp))
            (snapshot / "model.safetensors").unlink()
            with self.assertRaises(mlx_adapter.MlxPinError):
                mlx_adapter.snapshot_files(snapshot)


class MetricsTest(unittest.TestCase):
    def test_fit_leakage_compression_stability(self) -> None:
        metrics = mlx_adapter.canary_metrics(
            target_tokens=[5, 5, 6],
            coordinate_tokens=[5, 9],
            continuation_token_lists=[[5, 6], [5, 6]],
        )
        self.assertEqual(metrics["fit"], round(2 / 3, 6))
        self.assertEqual(metrics["stability"], 1.0)
        self.assertEqual(metrics["compression"], round(3 / 5, 6))
        self.assertEqual(metrics["leakage"], round(1 / 3, 6))

    def test_stability_counts_identical_samples(self) -> None:
        metrics = mlx_adapter.canary_metrics(
            target_tokens=[1],
            coordinate_tokens=[],
            continuation_token_lists=[[1], [2]],
        )
        self.assertEqual(metrics["stability"], 0.5)
        self.assertEqual(metrics["compression"], 1.0)

    def test_empty_inputs_fail_closed(self) -> None:
        with self.assertRaises(mlx_adapter.MlxCanaryError):
            mlx_adapter.canary_metrics(
                target_tokens=[], coordinate_tokens=[], continuation_token_lists=[[1]]
            )
        with self.assertRaises(mlx_adapter.MlxCanaryError):
            mlx_adapter.canary_metrics(
                target_tokens=[1], coordinate_tokens=[], continuation_token_lists=[]
            )


class _StubTokenizer:
    """Minimal tokenizer stub: one token per character, plus a chat template."""

    def encode(self, text, add_special_tokens=False):  # noqa: ANN001
        return list(range(len(text)))

    def apply_chat_template(
        self, messages, tokenize=True, add_generation_prompt=False, enable_thinking=False
    ):  # noqa: ANN001
        payload = "|".join(message["content"] for message in messages)
        if tokenize:
            return list(range(len(payload) + 20))
        return f"<chat>{payload}</chat>"


class CoordinateCostTest(unittest.TestCase):
    def test_coordinate_cost_under_stub_tokenizer(self) -> None:
        candidate = _candidate("abc", "de")
        cost = mlx_adapter.canary_coordinate_cost(
            candidate,
            tokenizer=_StubTokenizer(),
            tokenizer_view="stub-tokenizer/0.1.0",
            tokenizer_digest=digest({"stub": "tokenizer"}),
            target_tokens=2,
        )
        coordinate_text = "user: abc\n\nuser: de"
        self.assertEqual(mlx_adapter.canary_coordinate_text(candidate), coordinate_text)
        self.assertEqual(cost.coordinate_tokens, len(coordinate_text))
        self.assertEqual(cost.coordinate_utf8_bytes, len(coordinate_text.encode("utf-8")))
        self.assertEqual(cost.full_rendered_tokens, len("abc|de") + 20)
        self.assertEqual(cost.full_rendered_utf8_bytes, len("<chat>abc|de</chat>".encode("utf-8")))
        self.assertEqual(cost.target_tokens, 2)
        self.assertEqual(cost.continuation_tokens, 0)


def _mlx_importable() -> bool:
    try:
        import mlx.core  # noqa: F401
        import mlx_lm  # noqa: F401
    except Exception:  # noqa: BLE001 — any import failure means "not available"
        return False
    return True


class RuntimeTest(unittest.TestCase):
    def test_runtime_matches_pin_or_fails_closed(self) -> None:
        if _mlx_importable():
            mx, mlx_lm = mlx_adapter.require_pinned_runtime()
            self.assertEqual(mx.__version__, mlx_adapter.PINNED_MLX_VERSION)
            self.assertEqual(mlx_lm.__version__, mlx_adapter.PINNED_MLX_LM_VERSION)
        else:
            with self.assertRaises(mlx_adapter.MlxUnavailableError):
                mlx_adapter.require_pinned_runtime()


if __name__ == "__main__":
    unittest.main()
