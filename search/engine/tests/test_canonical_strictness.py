"""Canonical parsers may not substitute a value the writer always emits.

A ``*_from_canonical`` parser is the only schema an internal record has: the
manifest, the receipts, and the ledger have no JSON Schema file, so nothing
downstream re-checks a field the parser invented. A default therefore does not
mean "optional" — it means a stripped or corrupted field is silently replaced,
and for the accounting records the replacement is a zero that looks like a
cheap run.

The rule these tests encode, for every record whose ``to_canonical`` always
writes a key:

    parsing a payload with that key deleted must raise.

The tests derive the key list from ``to_canonical`` itself, so a field added to
a writer is covered without touching this file. Two parsers are exempt, and
each exemption is measured here rather than assumed: ``candidate_from_canonical``
recomputes the candidate id (which covers the role) and ``event_from_canonical``
recomputes the content digest (which covers the payload, parents, blobs, and
schema version), so in both cases a substituted value survives only when it
already equalled the default.
"""

from __future__ import annotations

import unittest

from search.engine.archive import ArchiveError, RunManifest, manifest_from_canonical
from search.engine.canonical import digest
from search.engine.contracts import (
    Candidate,
    ContractViolation,
    EvaluationReceipt,
    Message,
    Placement,
    ProposalReceipt,
    ProposalRequest,
    AdapterIdentity,
    adapter_identity,
    adapter_identity_from_canonical,
    candidate_from_canonical,
    evaluation_receipt,
    evaluation_receipt_from_canonical,
    proposal_receipt,
    proposal_receipt_from_canonical,
    proposal_request,
    proposal_request_from_canonical,
)
from search.engine.events import Event, EventError, event_from_canonical
from search.engine.ledger import CoordinateCost, LedgerError, coordinate_cost_from_canonical


def make_adapter(role: str = "proposal") -> AdapterIdentity:
    return adapter_identity(
        f"checkpoint#{role}",
        "rev-1",
        role,
        capabilities=("greedy", "logits"),
        manifest={"arm": "self_compression"},
    )


def make_manifest() -> RunManifest:
    return RunManifest(
        run_id="run-1",
        target_digest=digest("target"),
        known_metrics=("fit",),
        adapter_digests=(make_adapter().adapter_digest,),
        nesting_rule="t_dec_nested_in_w_search",
        scheduler_model="single-worker-v0",
        model_manifest={"fixture": True},
        closed=False,
    )


def make_cost() -> CoordinateCost:
    return CoordinateCost(
        tokenizer_view="demo-tokenizer/0.1.0",
        tokenizer_digest=digest("tokenizer"),
        coordinate_tokens=3,
        coordinate_utf8_bytes=12,
        full_rendered_tokens=11,
        full_rendered_utf8_bytes=108,
        target_tokens=7,
        continuation_tokens=5,
        prefix_free_bits=0,
    )


def make_candidate(role: str = "candidate") -> Candidate:
    return Candidate(
        messages=(Message("user", "hello"),),
        placement=Placement(
            scaffold_id="scaffold-1",
            scaffold_digest=digest("scaffold"),
            prompt_position="prefix",
            rendered_template_version="v1",
        ),
        proposal_mode="seed",
        role=role,
    )


def families() -> list[tuple[str, object, object, type[BaseException]]]:
    """Records whose parsers must reject any deleted canonical key."""

    adapter = make_adapter()
    return [
        ("manifest", make_manifest(), manifest_from_canonical, ArchiveError),
        ("coordinate cost", make_cost(), coordinate_cost_from_canonical, LedgerError),
        (
            "adapter identity",
            adapter,
            adapter_identity_from_canonical,
            ContractViolation,
        ),
        (
            "proposal request",
            proposal_request(
                request_id="request-1",
                reservation_id="reservation-1",
                adapter=adapter,
                proposal_mode="seed",
                target_digest=digest("target"),
                context={"frozen": 1},
                parent_candidate_ids=(digest("parent"),),
            ),
            proposal_request_from_canonical,
            ContractViolation,
        ),
        (
            "proposal receipt",
            proposal_receipt(
                request_id="request-2",
                adapter=adapter,
                candidates=(),
                resource_use={"tokens": 5},
            ),
            proposal_receipt_from_canonical,
            ContractViolation,
        ),
        (
            "evaluation receipt",
            evaluation_receipt(
                request_id="request-3",
                adapter=make_adapter("evaluation"),
                candidate_id=digest("candidate"),
                metrics={"fit": 1.0},
                resource_use={"inputTokens": 11, "outputTokens": 7},
                outputs={"output": "measured text"},
            ),
            evaluation_receipt_from_canonical,
            ContractViolation,
        ),
    ]


# A field whose canonical value is a fixed constant carries no information, so
# a missing key reconstructs the same value and cannot be told apart from a
# present one. Such fields are exempt by construction, not by oversight.
CONSTANT_FIELDS = {("coordinate cost", "costBasis")}


class TestCanonicalParsersRequireEveryWrittenField(unittest.TestCase):
    def test_canonical_payloads_round_trip(self) -> None:
        for label, value, parser, _ in families():
            with self.subTest(record=label):
                payload = value.to_canonical()  # type: ignore[attr-defined]
                self.assertEqual(parser(payload).to_canonical(), payload)

    def test_no_written_field_may_be_deleted(self) -> None:
        for label, value, parser, error_type in families():
            payload = value.to_canonical()  # type: ignore[attr-defined]
            self.assertTrue(payload, label)
            for key in payload:
                if (label, key) in CONSTANT_FIELDS:
                    continue
                with self.subTest(record=label, field=key):
                    stripped = {name: item for name, item in payload.items() if name != key}
                    with self.assertRaises(error_type):
                        parser(stripped)

    def test_an_emptied_accounting_field_is_not_a_zero(self) -> None:
        """The concrete fail-open this rule closes: a receipt without
        ``resourceUse`` used to derive a ledger that reported no token use."""

        payload = evaluation_receipt(
            request_id="request-4",
            adapter=make_adapter("evaluation"),
            candidate_id=digest("candidate"),
            metrics={"fit": 1.0},
            resource_use={"inputTokens": 11},
        ).to_canonical()
        payload.pop("resourceUse")
        with self.assertRaisesRegex(ContractViolation, "resourceUse"):
            evaluation_receipt_from_canonical(payload)


class TestDocumentedDefaults(unittest.TestCase):
    """The two remaining defaults, and why each is settled by a digest."""

    def test_candidate_role_survives_only_when_it_equalled_the_default(self) -> None:
        payload = make_candidate("candidate").to_canonical()
        payload.pop("candidateRole")
        reparsed = candidate_from_canonical(payload)
        self.assertEqual(reparsed.role, "candidate")
        self.assertEqual(reparsed.candidate_id, make_candidate("candidate").candidate_id)

        control = make_candidate("explicit_reconstruction").to_canonical()
        control.pop("candidateRole")
        with self.assertRaisesRegex(ContractViolation, "candidate id mismatch"):
            candidate_from_canonical(control)

    def test_event_defaults_are_settled_by_the_content_digest(self) -> None:
        event = Event(
            event_id="event-1",
            sequence=1,
            event_type="run_started",
            phase="run",
            payload={"runId": "run-1", "createdAt": "2026-10-19T00:00:00Z"},
        )
        payload = event.to_canonical()
        # Dropping the schema version reproduces the declared digest only
        # because the default is the version that wrote it, so the reconstruction
        # is lossless; any other version would change the digest and fail.
        without_version = {k: v for k, v in payload.items() if k != "schemaVersion"}
        self.assertEqual(
            event_from_canonical(without_version).schema_version, event.schema_version
        )
        # Parents and blobs are covered by the same digest and, when non-empty,
        # cannot be dropped.
        chained = Event(
            event_id="event-2",
            sequence=2,
            event_type="run_completed",
            phase="run",
            payload={"status": "completed"},
            parent_event_ids=(event.content_digest,),
            blob_digests=(digest("blob"),),
        )
        for key in ("parentEventIds", "blobDigests"):
            with self.subTest(field=key):
                stripped = {k: v for k, v in chained.to_canonical().items() if k != key}
                with self.assertRaises(EventError):
                    event_from_canonical(stripped)


if __name__ == "__main__":
    unittest.main()
