"""Deterministic candidate operators: one adversarial mode per test.

Everything here is a fixture: operators are pure text transforms over
candidate messages and never consult a model. Each test pins one invariant:
label, determinism, Unicode safety, empty-product failure, or strict parsing.
"""

from __future__ import annotations

import unittest

from search.engine.canonical import digest
from search.engine.contracts import Candidate, Message, Placement
from search.engine.operators import (
    OPERATOR_LABELS,
    OPERATOR_SPEC_BUILDERS,
    OperatorFailure,
    apply_operator,
    operator_spec_from_canonical,
)
from search.engine.operators.delete import DeleteSpec, delete_spec_from_canonical
from search.engine.operators.reference import ReferenceSpec, reference_spec_from_canonical
from search.engine.operators.repair import RepairSpec, repair_spec_from_canonical
from search.engine.operators.rewrite import RewriteSpec, rewrite_spec_from_canonical

PLACEMENT = Placement(
    scaffold_id="operator-test-scaffold",
    scaffold_digest=digest({"fixture": "operator-test-scaffold", "version": "1"}),
    prompt_position="messages[0]",
    rendered_template_version="1",
)


def make_candidate(messages, *, mode: str = "seed", role: str = "candidate") -> Candidate:
    return Candidate(
        messages=tuple(
            Message(role=role_name, content=content) for role_name, content in messages
        ),
        placement=PLACEMENT,
        proposal_mode=mode,
        role=role,
    )


def make_specs():
    """One representative valid spec per operator, over a 3-message candidate."""
    return [
        DeleteSpec(index=1),
        RewriteSpec(index=1, transform="collapse_whitespace"),
        RepairSpec(index=1, repair="normalize_line_endings"),
        ReferenceSpec(source_messages=(Message(role="system", content="ref"),), at="append"),
    ]


class TestSharedInvariants(unittest.TestCase):
    def test_all_operator_labels_have_parsers(self) -> None:
        self.assertEqual(set(OPERATOR_SPEC_BUILDERS), set(OPERATOR_LABELS))

    def test_every_operator_rejects_non_candidate_input(self) -> None:
        candidate = make_candidate([("user", "hello"), ("user", "world")])
        for spec in make_specs():
            with self.subTest(operator=spec.operator):
                with self.assertRaises(OperatorFailure):
                    spec.apply((Message(role="user", content="x"),))
                with self.assertRaises(OperatorFailure):
                    apply_operator(spec, candidate.messages)

    def test_every_operator_labels_its_product(self) -> None:
        candidate = make_candidate([("user", "alpha"), ("user", "beta"), ("user", "gamma")])
        for spec in make_specs():
            with self.subTest(operator=spec.operator):
                product = spec.apply(candidate)
                self.assertEqual(product.proposal_mode, spec.operator)

    def test_every_operator_preserves_placement_and_role(self) -> None:
        candidate = make_candidate(
            [("user", "alpha"), ("user", "beta"), ("user", "gamma")], role="candidate"
        )
        control = make_candidate(
            [("user", "alpha"), ("user", "beta"), ("user", "gamma")],
            role="explicit_reconstruction",
        )
        for spec in make_specs():
            with self.subTest(operator=spec.operator):
                product = spec.apply(control)
                self.assertEqual(product.placement, control.placement)
                self.assertEqual(product.role, "explicit_reconstruction")

    def test_every_operator_is_deterministic(self) -> None:
        candidate = make_candidate([("user", "alpha"), ("user", " beta "), ("user", "gamma")])
        for spec in make_specs():
            with self.subTest(operator=spec.operator):
                first = spec.apply(candidate)
                second = spec.apply(candidate)
                self.assertEqual(first.candidate_id, second.candidate_id)
                self.assertEqual(first.to_canonical(), second.to_canonical())

    def test_every_operator_leaves_input_untouched(self) -> None:
        candidate = make_candidate([("user", "alpha"), ("user", " beta "), ("user", "gamma")])
        original = candidate.to_canonical()
        for spec in make_specs():
            spec.apply(candidate)
        self.assertEqual(candidate.to_canonical(), original)

    def test_empty_content_product_rejected(self) -> None:
        # Kernel allows empty message content; operators must not ship it.
        candidate = make_candidate([("user", "ok"), ("user", "")])
        with self.assertRaises(OperatorFailure):
            DeleteSpec(index=0).apply(candidate)

    def test_cjk_and_emoji_survive_repair_of_zero_width(self) -> None:
        content = "你好，世界 🚀 👨\u200d👩\u200d👧 café"
        candidate = make_candidate([("user", content), ("user", "other")])
        product = RepairSpec(index=0, repair="strip_zero_width").apply(candidate)
        self.assertEqual(product.messages[0].content, content)
        self.assertIn("\u200d", product.messages[0].content)

    def test_apply_operator_rejects_unknown_spec(self) -> None:
        class FakeSpec:
            operator = "seed"

        candidate = make_candidate([("user", "alpha"), ("user", "beta")])
        with self.assertRaises(OperatorFailure):
            apply_operator(FakeSpec(), candidate)  # type: ignore[arg-type]


class TestSpecParsing(unittest.TestCase):
    def test_canonical_round_trip_per_operator(self) -> None:
        for spec in make_specs():
            with self.subTest(operator=spec.operator):
                rebuilt = operator_spec_from_canonical(spec.to_canonical())
                self.assertEqual(rebuilt, spec)

    def test_every_parser_rejects_unknown_fields(self) -> None:
        for spec in make_specs():
            with self.subTest(operator=spec.operator):
                payload = dict(spec.to_canonical())
                payload["sneaky"] = True
                with self.assertRaises(OperatorFailure):
                    operator_spec_from_canonical(payload)

    def test_every_parser_rejects_null_index(self) -> None:
        for spec in make_specs():
            if spec.operator == "reference":
                continue
            with self.subTest(operator=spec.operator):
                payload = dict(spec.to_canonical())
                payload["index"] = None
                with self.assertRaises(OperatorFailure):
                    operator_spec_from_canonical(payload)

    def test_every_parser_rejects_bool_index(self) -> None:
        for spec in make_specs():
            if spec.operator == "reference":
                continue
            with self.subTest(operator=spec.operator):
                payload = dict(spec.to_canonical())
                payload["index"] = True
                with self.assertRaises(OperatorFailure):
                    operator_spec_from_canonical(payload)

    def test_dispatcher_rejects_missing_operator(self) -> None:
        with self.assertRaises(OperatorFailure):
            operator_spec_from_canonical({"index": 0})

    def test_dispatcher_rejects_seed_mode(self) -> None:
        with self.assertRaises(OperatorFailure):
            operator_spec_from_canonical({"operator": "seed", "index": 0})

    def test_dispatcher_rejects_non_mapping(self) -> None:
        with self.assertRaises(OperatorFailure):
            operator_spec_from_canonical("delete")  # type: ignore[arg-type]


class TestDelete(unittest.TestCase):
    def test_delete_removes_the_indexed_message(self) -> None:
        candidate = make_candidate([("user", "alpha"), ("user", "beta"), ("user", "gamma")])
        product = DeleteSpec(index=1).apply(candidate)
        self.assertEqual([m.content for m in product.messages], ["alpha", "gamma"])

    def test_delete_first_and_last(self) -> None:
        candidate = make_candidate([("user", "alpha"), ("user", "beta"), ("user", "gamma")])
        self.assertEqual(
            [m.content for m in DeleteSpec(index=0).apply(candidate).messages],
            ["beta", "gamma"],
        )
        self.assertEqual(
            [m.content for m in DeleteSpec(index=2).apply(candidate).messages],
            ["alpha", "beta"],
        )

    def test_delete_single_message_rejected(self) -> None:
        candidate = make_candidate([("user", "only")])
        with self.assertRaises(OperatorFailure):
            DeleteSpec(index=0).apply(candidate)

    def test_delete_index_out_of_range_rejected(self) -> None:
        candidate = make_candidate([("user", "alpha"), ("user", "beta")])
        with self.assertRaises(OperatorFailure):
            DeleteSpec(index=2).apply(candidate)

    def test_delete_negative_index_rejected_at_construction(self) -> None:
        with self.assertRaises(OperatorFailure):
            DeleteSpec(index=-1)

    def test_delete_bool_index_rejected_at_construction(self) -> None:
        with self.assertRaises(OperatorFailure):
            DeleteSpec(index=True)  # type: ignore[arg-type]

    def test_delete_parser_wrong_operator_label(self) -> None:
        with self.assertRaises(OperatorFailure):
            delete_spec_from_canonical({"operator": "rewrite", "index": 0})


class TestRewrite(unittest.TestCase):
    def _rewrite(self, content: str, transform: str) -> str:
        candidate = make_candidate([("user", "other"), ("user", content)])
        product = RewriteSpec(index=1, transform=transform).apply(candidate)
        return product.messages[1].content

    def test_strip(self) -> None:
        self.assertEqual(self._rewrite("  \t padded \n", "strip"), "padded")

    def test_collapse_whitespace(self) -> None:
        self.assertEqual(self._rewrite("a  b\n c\t\td", "collapse_whitespace"), "a b c d")

    def test_dedent(self) -> None:
        self.assertEqual(self._rewrite("\n    x\n      y\n", "dedent"), "x\n  y")

    def test_lowercase_keeps_cjk_and_emoji(self) -> None:
        self.assertEqual(self._rewrite("HELLO 你好 🚀", "lowercase"), "hello 你好 🚀")

    def test_rewrite_normalizes_to_nfc(self) -> None:
        candidate = make_candidate([("user", "other"), ("user", "cafe\u0301")])
        product = RewriteSpec(index=1, transform="strip").apply(candidate)
        self.assertEqual(product.messages[1].content, "café")

    def test_unknown_transform_rejected(self) -> None:
        with self.assertRaises(OperatorFailure):
            RewriteSpec(index=0, transform="paraphrase")

    def test_empty_result_rejected(self) -> None:
        candidate = make_candidate([("user", "other"), ("user", " \t ")])
        with self.assertRaises(OperatorFailure):
            RewriteSpec(index=1, transform="strip").apply(candidate)

    def test_index_out_of_range_rejected(self) -> None:
        candidate = make_candidate([("user", "alpha"), ("user", "beta")])
        with self.assertRaises(OperatorFailure):
            RewriteSpec(index=2, transform="strip").apply(candidate)

    def test_parser_wrong_operator_label(self) -> None:
        with self.assertRaises(OperatorFailure):
            rewrite_spec_from_canonical({"operator": "delete", "index": 0, "transform": "strip"})

    def test_parser_missing_transform_rejected(self) -> None:
        with self.assertRaises(OperatorFailure):
            rewrite_spec_from_canonical({"operator": "rewrite", "index": 0})


class TestRepair(unittest.TestCase):
    def _repair(self, content: str, repair: str) -> str:
        candidate = make_candidate([("user", "other"), ("user", content)])
        product = RepairSpec(index=1, repair=repair).apply(candidate)
        return product.messages[1].content

    def test_normalize_line_endings(self) -> None:
        self.assertEqual(self._repair("a\r\nb\rc", "normalize_line_endings"), "a\nb\nc")

    def test_strip_zero_width(self) -> None:
        self.assertEqual(
            self._repair("\u200bhidden\u2060\u200btail\ufeff", "strip_zero_width"), "hiddentail"
        )

    def test_remove_control_chars_keeps_newline_and_tab(self) -> None:
        self.assertEqual(
            self._repair("a\x00b\x1fc\x7fd\ne\tf", "remove_control_chars"), "abcd\ne\tf"
        )

    def test_collapse_blank_lines(self) -> None:
        self.assertEqual(
            self._repair("a\n\n\nb\n  \n  \nc", "collapse_blank_lines"), "a\n\nb\n\nc"
        )

    def test_unknown_repair_rejected(self) -> None:
        with self.assertRaises(OperatorFailure):
            RepairSpec(index=0, repair="invent")

    def test_empty_result_rejected(self) -> None:
        candidate = make_candidate([("user", "other"), ("user", "\u200b\u200b")])
        with self.assertRaises(OperatorFailure):
            RepairSpec(index=1, repair="strip_zero_width").apply(candidate)

    def test_index_out_of_range_rejected(self) -> None:
        candidate = make_candidate([("user", "alpha"), ("user", "beta")])
        with self.assertRaises(OperatorFailure):
            RepairSpec(index=2, repair="strip_zero_width").apply(candidate)

    def test_parser_wrong_operator_label(self) -> None:
        with self.assertRaises(OperatorFailure):
            repair_spec_from_canonical({"operator": "rewrite", "index": 0, "repair": "strip_zero_width"})

    def test_parser_missing_repair_rejected(self) -> None:
        with self.assertRaises(OperatorFailure):
            repair_spec_from_canonical({"operator": "repair", "index": 0})


class TestReference(unittest.TestCase):
    SOURCE = (Message(role="system", content="参考 ref 🚀"),)

    def _apply(self, at: str, index: int = 0) -> Candidate:
        candidate = make_candidate([("user", "alpha"), ("user", "beta")])
        return ReferenceSpec(source_messages=self.SOURCE, at=at, index=index).apply(candidate)

    def test_prepend_order(self) -> None:
        product = self._apply("prepend")
        self.assertEqual(
            [(m.role, m.content) for m in product.messages],
            [("system", "参考 ref 🚀"), ("user", "alpha"), ("user", "beta")],
        )

    def test_append_order(self) -> None:
        product = self._apply("append")
        self.assertEqual(
            [(m.role, m.content) for m in product.messages],
            [("user", "alpha"), ("user", "beta"), ("system", "参考 ref 🚀")],
        )

    def test_insert_in_middle(self) -> None:
        product = self._apply("insert", index=1)
        self.assertEqual(
            [(m.role, m.content) for m in product.messages],
            [("user", "alpha"), ("system", "参考 ref 🚀"), ("user", "beta")],
        )

    def test_insert_at_edges(self) -> None:
        self.assertEqual(len(self._apply("insert", index=0).messages), 3)
        self.assertEqual(len(self._apply("insert", index=2).messages), 3)

    def test_insert_index_out_of_range_rejected(self) -> None:
        candidate = make_candidate([("user", "alpha"), ("user", "beta")])
        with self.assertRaises(OperatorFailure):
            ReferenceSpec(source_messages=self.SOURCE, at="insert", index=3).apply(candidate)

    def test_index_forbidden_for_prepend(self) -> None:
        with self.assertRaises(OperatorFailure):
            ReferenceSpec(source_messages=self.SOURCE, at="prepend", index=1)

    def test_empty_source_rejected(self) -> None:
        with self.assertRaises(OperatorFailure):
            ReferenceSpec(source_messages=(), at="append")

    def test_source_must_be_messages(self) -> None:
        with self.assertRaises(OperatorFailure):
            ReferenceSpec(source_messages=("just a string",), at="append")  # type: ignore[arg-type]

    def test_unknown_at_rejected(self) -> None:
        with self.assertRaises(OperatorFailure):
            ReferenceSpec(source_messages=self.SOURCE, at="overwrite")

    def test_parser_round_trip_preserves_source(self) -> None:
        spec = ReferenceSpec(source_messages=self.SOURCE, at="insert", index=1)
        rebuilt = reference_spec_from_canonical(spec.to_canonical())
        self.assertEqual(rebuilt, spec)
        self.assertEqual(rebuilt.source_messages[0].content, "参考 ref 🚀")

    def test_parser_wrong_operator_label(self) -> None:
        with self.assertRaises(OperatorFailure):
            reference_spec_from_canonical(
                {"operator": "delete", "at": "append", "index": 0, "sourceMessages": []}
            )


if __name__ == "__main__":
    unittest.main()

class TestRedTeamRegressions(unittest.TestCase):
    """Regressions pinned by the independent review of the operators slice."""

    def test_reference_parser_malformed_source_item_is_typed_failure(self) -> None:
        with self.assertRaises(OperatorFailure):
            reference_spec_from_canonical(
                {
                    "operator": "reference",
                    "at": "append",
                    "index": 0,
                    "sourceMessages": [{"role": "user", "content": "x", "extra": 1}],
                }
            )

    def test_remove_control_chars_preserves_emoji_join_sequences(self) -> None:
        candidate = make_candidate(
            [("user", "other"), ("user", "\u200d\U0001f468\u200d\U0001f469\u200d\U0001f467")]
        )
        product = RepairSpec(index=1, repair="remove_control_chars").apply(candidate)
        self.assertEqual(
            product.messages[1].content, "\u200d\U0001f468\u200d\U0001f469\u200d\U0001f467"
        )
