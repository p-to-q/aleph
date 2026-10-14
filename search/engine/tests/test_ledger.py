"""Six-account ledger: separation, reservations, and fail-closed accounting."""

from __future__ import annotations

import unittest

from search.engine.canonical import digest
from search.engine.ledger import (
    ACCOUNTS,
    CoordinateCost,
    DecoderAccount,
    LedgerError,
    Reservation,
    ResourceLedger,
    VerificationAccount,
    coordinate_cost_from_canonical,
    new_ledger,
)


def make_cost(**overrides) -> CoordinateCost:
    values = dict(
        tokenizer_view="demo-tokenizer/0.1.0",
        tokenizer_digest=digest("tokenizer"),
        coordinate_tokens=3,
        coordinate_utf8_bytes=12,
        full_rendered_tokens=11,
        full_rendered_utf8_bytes=108,
    )
    values.update(overrides)
    return CoordinateCost(**values)


def make_ledger() -> ResourceLedger:
    return new_ledger(
        nesting_rule="t_dec_nested_in_w_search",
        scheduler_model="single-worker-v0",
        model_manifest={"fixture": True},
    )


class TestCoordinateCost(unittest.TestCase):
    def test_requires_declared_tokenizer_view_and_digest(self) -> None:
        with self.assertRaises(LedgerError):
            CoordinateCost(tokenizer_view="", tokenizer_digest=digest("t"), coordinate_tokens=0, coordinate_utf8_bytes=0, full_rendered_tokens=0, full_rendered_utf8_bytes=0)

    def test_negative_counts_rejected(self) -> None:
        with self.assertRaises(LedgerError):
            make_cost(coordinate_tokens=-1)

    def test_full_rendered_cannot_be_shorter_than_coordinate(self) -> None:
        with self.assertRaises(LedgerError):
            make_cost(coordinate_tokens=5, full_rendered_tokens=4)

    def test_prefix_free_bits_validated(self) -> None:
        self.assertIsNone(make_cost().prefix_free_bits)
        make_cost(prefix_free_bits=0)
        make_cost(prefix_free_bits=17)
        for bad in (-1, 1.5, True, "3"):
            with self.assertRaises(LedgerError, msg=repr(bad)):
                make_cost(prefix_free_bits=bad)  # type: ignore[arg-type]

    def test_canonical_round_trip(self) -> None:
        cost = make_cost(target_tokens=10, prefix_free_bits=8)
        rebuilt = coordinate_cost_from_canonical(cost.to_canonical())
        self.assertEqual(rebuilt, cost)

    def test_canonical_declares_cost_basis(self) -> None:
        self.assertEqual(make_cost().to_canonical()["costBasis"], "declared_tokenizer_view_not_word_count")


class TestAccounts(unittest.TestCase):
    def test_decoder_account_rejects_bad_counts(self) -> None:
        account = DecoderAccount()
        for bad in (-1, 1.5, True):
            with self.assertRaises(LedgerError):
                account.add(calls=bad)  # type: ignore[arg-type]

    def test_decoder_account_accumulates(self) -> None:
        account = DecoderAccount()
        account.add(calls=1, input_tokens=5, samples=2)
        account.add(calls=2, input_tokens=7)
        self.assertEqual(account.calls, 3)
        self.assertEqual(account.input_tokens, 12)
        self.assertEqual(account.samples, 2)

    def test_verification_account_rejects_bad_counts(self) -> None:
        account = VerificationAccount()
        with self.assertRaises(LedgerError):
            account.add(fresh_samples=-1)

    def test_search_work_account_rejects_bad_counts(self) -> None:
        ledger = make_ledger()
        with self.assertRaises(LedgerError):
            ledger.search_work.add(evaluation_calls=-1)

    def test_total_adapter_calls_is_derived(self) -> None:
        ledger = make_ledger()
        ledger.search_work.add(proposal_calls=2, evaluation_calls=3)
        self.assertEqual(ledger.search_work.to_canonical()["totalAdapterCalls"], 5)


class TestReservations(unittest.TestCase):
    def test_lifecycle_reserve_settle(self) -> None:
        ledger = make_ledger()
        reservation = Reservation(
            reservation_id="rsv-1", account="W_search", stage="discovery", event_id="ev-1"
        )
        ledger.reserve(reservation)
        self.assertIn("rsv-1", ledger.open_reservations)
        settled = ledger.settle("rsv-1", "committed")
        self.assertEqual(settled, reservation)
        self.assertNotIn("rsv-1", ledger.open_reservations)
        self.assertEqual(ledger.settled_reservations["rsv-1"], "committed")

    def test_double_reserve_rejected(self) -> None:
        ledger = make_ledger()
        reservation = Reservation(reservation_id="r", account="T_dec", stage="discovery", event_id="e")
        ledger.reserve(reservation)
        with self.assertRaises(LedgerError):
            ledger.reserve(reservation)

    def test_double_settle_rejected(self) -> None:
        ledger = make_ledger()
        ledger.reserve(Reservation(reservation_id="r", account="T_dec", stage="discovery", event_id="e"))
        ledger.settle("r", "failed")
        with self.assertRaises(LedgerError):
            ledger.settle("r", "failed")

    def test_settle_unknown_rejected(self) -> None:
        ledger = make_ledger()
        with self.assertRaises(LedgerError):
            ledger.settle("missing", "committed")

    def test_unknown_outcome_rejected(self) -> None:
        ledger = make_ledger()
        ledger.reserve(Reservation(reservation_id="r", account="T_dec", stage="discovery", event_id="e"))
        with self.assertRaises(LedgerError):
            ledger.settle("r", "maybe")

    def test_require_open_fails_closed(self) -> None:
        ledger = make_ledger()
        with self.assertRaises(LedgerError):
            ledger.require_open("missing")

    def test_empty_event_id_rejected(self) -> None:
        with self.assertRaises(LedgerError):
            Reservation(reservation_id="r", account="T_dec", stage="discovery", event_id="")

    def test_unknown_account_and_stage_rejected(self) -> None:
        with self.assertRaises(LedgerError):
            Reservation(reservation_id="r", account="invented", stage="discovery", event_id="e")
        with self.assertRaises(LedgerError):
            Reservation(reservation_id="r", account="T_dec", stage="invented", event_id="e")


class TestResourceLedger(unittest.TestCase):
    def test_six_accounts_kept_separate(self) -> None:
        canonical = make_ledger().to_canonical()
        self.assertEqual(canonical["accountsPresent"], list(ACCOUNTS))
        self.assertIn("C_p", canonical)
        self.assertIn("T_dec", canonical)
        self.assertIn("W_search", canonical)
        self.assertIn("D_crit", canonical)
        self.assertIn("V_verify", canonical)
        self.assertIn("M_desc", canonical)

    def test_no_collapse_policy_declared(self) -> None:
        self.assertEqual(
            make_ledger().to_canonical()["collapsePolicy"],
            "accounts_reported_separately_no_published_conversion",
        )

    def test_nesting_rule_mandatory_and_validated(self) -> None:
        with self.assertRaises(LedgerError):
            new_ledger(
                nesting_rule="invented",
                scheduler_model="s",
                model_manifest={"fixture": True},
            )

    def test_scheduler_model_required_for_d_crit(self) -> None:
        with self.assertRaises(LedgerError):
            new_ledger(nesting_rule="t_dec_nested_in_w_search", scheduler_model="", model_manifest={"fixture": True})

    def test_model_manifest_required(self) -> None:
        with self.assertRaises(LedgerError):
            new_ledger(nesting_rule="t_dec_nested_in_w_search", scheduler_model="s", model_manifest={})

    def test_conflicting_c_p_rejected(self) -> None:
        ledger = make_ledger()
        ledger.record_coordinate_cost("c1", make_cost(coordinate_tokens=3))
        with self.assertRaises(LedgerError):
            ledger.record_coordinate_cost("c1", make_cost(coordinate_tokens=4))

    def test_identical_c_p_is_idempotent(self) -> None:
        ledger = make_ledger()
        ledger.record_coordinate_cost("c1", make_cost())
        ledger.record_coordinate_cost("c1", make_cost())

    def test_ledger_digest_changes_with_accounts(self) -> None:
        first = make_ledger()
        second = make_ledger()
        self.assertEqual(first.ledger_digest, second.ledger_digest)
        second.record_coordinate_cost("c1", make_cost())
        self.assertNotEqual(first.ledger_digest, second.ledger_digest)

    def test_decoder_stages_defaulted(self) -> None:
        ledger = make_ledger()
        self.assertIn("discovery", ledger.decoder)
        self.assertIn("confirmation", ledger.decoder)

    def test_canonical_includes_reservation_state(self) -> None:
        ledger = make_ledger()
        ledger.reserve(Reservation(reservation_id="r", account="T_dec", stage="discovery", event_id="e"))
        canonical = ledger.to_canonical()
        self.assertEqual([item["reservationId"] for item in canonical["reservations"]["open"]], ["r"])
        ledger.settle("r", "committed")
        self.assertEqual(ledger.to_canonical()["reservations"]["settled"], {"r": "committed"})


class TestNoWordCountFallback(unittest.TestCase):
    def test_str_split_never_used_as_coordinate_cost(self) -> None:
        # The package-level contract: no word-count shortcut in the kernel.
        import pathlib
        import re

        root = pathlib.Path(__file__).resolve().parents[1]
        for module in ("canonical.py", "contracts.py", "events.py", "archive.py", "ledger.py", "verify.py"):
            source = (root / module).read_text(encoding="utf-8")
            # Word-count shortcuts are banned; argumented splits (digest prefix
            # parsing) are structural, not coordinate costs.
            self.assertNotIn("str.split()", source, module)
            self.assertIsNone(re.search(r"\.split\(\s*\)", source), module)


if __name__ == "__main__":
    unittest.main()
