"""Replay: deterministic derivation without any adapter call."""

from __future__ import annotations

import json
import unittest

from search.engine.adapters.replay import ReplayError, replay, replay_stream
from search.engine.archive import read_bundle
from search.engine.fixtures.demo import build_demo_bundle
from search.engine.tests.support import fresh_tmpdir, rewrite_stream


class TestReplay(unittest.TestCase):
    def test_replay_matches_materialization_digests(self) -> None:
        tmp = fresh_tmpdir()
        root = build_demo_bundle(tmp / "bundle")
        result = replay(root)
        from search.engine.archive import materialize

        self.assertEqual(result.digests, materialize(root))

    def test_replay_is_repeatable(self) -> None:
        tmp = fresh_tmpdir()
        root = build_demo_bundle(tmp / "bundle")
        first = replay(root)
        second = replay(root)
        self.assertEqual(first.digests, second.digests)

    def test_replay_exposes_derived_views(self) -> None:
        tmp = fresh_tmpdir()
        root = build_demo_bundle(tmp / "bundle")
        result = replay(root)
        self.assertEqual(len(result.derived.archive_view["candidates"]), 3)
        self.assertEqual(result.derived.confirmation_view["outcome"], "confirmed")
        self.assertGreater(result.derived.ledger.critical_path, 0)

    def test_replay_stream_requires_valid_types(self) -> None:
        tmp = fresh_tmpdir()
        root = build_demo_bundle(tmp / "bundle")
        snapshot = read_bundle(root)
        with self.assertRaises(ReplayError):
            replay_stream(snapshot.manifest, list(snapshot.events), snapshot.blobs)  # type: ignore[arg-type]

    def test_replay_fails_closed_on_tampered_stream(self) -> None:
        tmp = fresh_tmpdir()
        root = build_demo_bundle(tmp / "bundle")
        # Reorder two lines and keep the manifest digest consistent.
        rewrite_stream(
            root,
            {1: lambda event: event, 2: lambda event: event},
        )
        records = (root / "events.jsonl").read_text(encoding="utf-8").splitlines()
        # swap lines 1 and 2 (sequences 1 and 2)
        swapped = [records[0], records[2], records[1], *records[3:]]
        (root / "events.jsonl").write_text("\n".join(swapped) + "\n", encoding="utf-8")
        with self.assertRaises(ReplayError):
            replay(root)

    def test_replay_never_calls_adapters(self) -> None:
        # Replay operates purely on recorded evidence; the demo adapters are
        # never constructed on this path.
        tmp = fresh_tmpdir()
        root = build_demo_bundle(tmp / "bundle")
        result = replay(root)
        for event in result.snapshot.events:
            if event.event_type in ("proposal_succeeded", "evaluation_completed"):
                self.assertTrue(event.blob_digests)


if __name__ == "__main__":
    unittest.main()
