"""Independent arithmetic replay and adversarial retained-evidence probes."""
import json
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from search.engine.canary_evidence import check_canary_evidence
from search.engine.contracts import evaluation_request
from search.engine.ledger import LEDGER_SCHEMA_VERSION
from search.engine.tests import test_mlx_adapter as fixture_adapter


class CanaryEvidenceTest(unittest.TestCase):
    def replay(self, mutate=None):
        adapter = fixture_adapter.SampleEvidenceTest().make_adapter()
        receipt = adapter.evaluate(evaluation_request(
            request_id="fixture", reservation_id="reserved", adapter=adapter.identity,
            candidate=fixture_adapter._candidate("compute"))).to_canonical()
        if mutate:
            mutate(receipt)
        snapshot = SimpleNamespace(
            manifest=SimpleNamespace(ledger_schema_version=LEDGER_SCHEMA_VERSION),
            events=[SimpleNamespace(event_type="evaluation_completed", blob_digests=["blob"], event_id="fixture")],
            blobs={"blob": json.dumps(receipt).encode()},
        )
        report = SimpleNamespace(ok=True, errors=[], payload=lambda: {"ok": True})
        with patch("search.engine.canary_evidence.verify_bundle", return_value=report), patch(
            "search.engine.canary_evidence.read_bundle", return_value=snapshot
        ):
            return check_canary_evidence(None)

    def test_replays_retained_arithmetic_without_runtime(self):
        report = self.replay()
        self.assertTrue(report["ok"], report["errors"])
        self.assertEqual(report["evaluationsReplayed"], 1)

    def test_semantic_tampering_fails_even_after_structural_verification(self):
        def usage(r): r["resourceUse"]["inputTokens"] = 12
        def metrics(r): r["metrics"]["fit"] = 0.123
        def raw(r): r["outputs"]["samples"][0]["text"] = "altered"
        def missing(r): del r["outputs"]["samples"]
        def bad_token(r): r["outputs"]["samples"][0]["tokenIds"] = [True]
        for mutate in (usage, metrics, raw, missing, bad_token):
            with self.subTest(mutate=mutate.__name__):
                self.assertFalse(self.replay(mutate)["ok"])
