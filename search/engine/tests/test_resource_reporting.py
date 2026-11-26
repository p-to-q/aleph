"""Accounting missingness and racing evidence, using simulated adapters only."""
from dataclasses import replace
import json
import unittest
from unittest.mock import patch

from search.engine.archive import (
    ArchiveError, DerivationError, _resource_int, _resource_int_from_payload,
    derive_state, read_bundle,
)
from search.engine.contracts import Message, evaluation_receipt
from search.engine.fixtures.demo import (
    ScheduledDemoEvaluationAdapter, build_scheduled_demo_bundle, scheduled_demo_config,
)
from search.engine.ledger import DecoderAccount, SearchWorkAccount, VerificationAccount
from search.engine.tests.support import fresh_tmpdir, make_demo_bundle
from search.engine.verify import verify_bundle


class TestResourceReporting(unittest.TestCase):
    def test_missing_and_misspelled_are_unknown_while_zero_stays_zero(self):
        self.assertIsNone(_resource_int((), "inputTokens"))
        self.assertIsNone(_resource_int((("input_tokens", 11),), "inputTokens"))
        self.assertEqual(_resource_int((("inputTokens", 0),), "inputTokens"), 0)
        self.assertEqual(_resource_int((("samples", 0),), "samples"), 0)
        self.assertEqual(_resource_int((), "inputTokens", legacy=True), 0)

    def test_invalid_reported_counter_is_not_missing(self):
        for value in (None, True, -1, 1.5, "0"):
            with self.subTest(value=value), self.assertRaises(DerivationError):
                _resource_int((("inputTokens", value),), "inputTokens")
        with self.assertRaises(DerivationError):
            _resource_int((("samples", 1), ("samples", 2)), "samples")

    def test_confirmation_checks_keep_missingness_and_reject_invalid_values(self):
        self.assertIsNone(_resource_int_from_payload({}, "tests"))
        self.assertEqual(_resource_int_from_payload({"tests": 0}, "tests"), 0)
        self.assertEqual(_resource_int_from_payload({}, "tests", legacy=True), 0)
        with self.assertRaises(DerivationError):
            _resource_int_from_payload({"tests": None}, "tests")

    def test_unknown_contribution_propagates_in_either_order(self):
        for values in ((None, 5), (5, None)):
            decoder, search, verification = DecoderAccount(), SearchWorkAccount(), VerificationAccount()
            for value in values:
                decoder.add(calls=1, input_tokens=value)
                search.add(proposal_calls=1, retries=value)
                verification.add(tests=value)
            self.assertEqual(decoder.calls, 2)
            self.assertIsNone(decoder.to_canonical()["inputTokens"])
            self.assertIsNone(search.to_canonical()["components"]["retries"])
            self.assertIsNone(verification.to_canonical()["tests"])

    def test_new_bundle_preserves_zero_samples_and_exports_unknown_usage(self):
        class ZeroReportedSamples(ScheduledDemoEvaluationAdapter):
            def evaluate(self, request):
                original = super().evaluate(request)
                return evaluation_receipt(
                    request_id=original.request_id, adapter=original.adapter,
                    candidate_id=original.candidate_id, metrics=dict(original.metrics),
                    resource_use={"samples": 0, "input_tokens": 11},
                    outputs=dict(original.outputs),
                )
        root = build_scheduled_demo_bundle(fresh_tmpdir() / "bundle", evaluation=ZeroReportedSamples)
        ledger = json.loads((root / "materialized/resource-ledger.json").read_text())
        self.assertEqual(ledger["schemaVersion"], "ResourceLedger/0.2.0")
        for stage in ("discovery", "confirmation"):
            self.assertEqual(ledger["T_dec"]["byStage"][stage]["samples"], 0)
            self.assertIsNone(ledger["T_dec"]["byStage"][stage]["inputTokens"])
        self.assertTrue(verify_bundle(root).ok)

    def test_legacy_version_replays_old_totals_without_relabelling(self):
        root = make_demo_bundle(fresh_tmpdir())
        snapshot = read_bundle(root)
        legacy = replace(snapshot.manifest, ledger_schema_version="ResourceLedger/0.1.0")
        ledger = derive_state(legacy, snapshot.events, snapshot.blobs).ledger.to_canonical()
        self.assertEqual(ledger["schemaVersion"], "ResourceLedger/0.1.0")
        self.assertEqual(ledger["T_dec"]["byStage"]["discovery"]["failures"], 1)
        self.assertEqual(ledger["T_dec"]["byStage"]["discovery"]["providerReportedTokens"], 88)
        with self.assertRaises(ArchiveError):
            replace(snapshot.manifest, ledger_schema_version="ResourceLedger/99.0.0")

    def test_racing_exports_unmeasured_reason_and_keeps_measured_rejection(self):
        config = scheduled_demo_config()
        good, control = config.seeds
        skipped = replace(good, messages=(Message(role="user", content="unmeasured seed"),))
        weak = replace(good, messages=(Message(role="user", content="measured weak seed"),))
        config = replace(config, seeds=(weak, good, skipped, control), racing_rule="first_passing", max_proposal_rounds=0)
        with patch("search.engine.fixtures.demo.scheduled_demo_config", return_value=config):
            root = build_scheduled_demo_bundle(fresh_tmpdir() / "racing")
        snapshot = read_bundle(root)
        reasons = {e.payload["candidateId"]: e.payload["reason"] for e in snapshot.events if e.event_type == "candidate_rejected"}
        self.assertEqual(reasons[weak.candidate_id], "dominated")
        self.assertEqual(reasons[skipped.candidate_id], "not_evaluated_after_racing_stop")
        run = json.loads((root / "exports/aleph-run-projection.json").read_text())
        omitted = {entry["candidateId"]: entry["rejectionReason"] for entry in run["omittedCandidateIds"]}
        self.assertEqual(omitted[skipped.candidate_id], "not_evaluated_after_racing_stop")
        self.assertTrue(verify_bundle(root).ok)
