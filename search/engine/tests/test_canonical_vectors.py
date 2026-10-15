"""Conformance vectors for the canonical form, pinned byte for byte.

The engine's canonical form is ``aleph-canonical/0.2.0``: the RFC 8785 (JCS)
serialization profile with NFC pre-normalization as the one documented Aleph
extension (ADR 0006, ``docs/decisions/0006-canonical-json-jcs-alignment.md``).
The practice review (``docs/research/engine-and-benchmark-practice-review.md``
section 2) asks for fixed vectors with expected canonical bytes and digests so
the profile cannot drift silently; this module is that pin, and it runs
without node.

Every expectation was cross-checked against a real ECMAScript engine
(``JSON.stringify``, plus ``String.prototype.normalize`` for the NFC
extension) and, for the digests, against ``shasum -a 256``. The node-gated
differential in ``test_jcs_differential.py`` re-runs the comparison live when
a ``node`` binary is present.
"""

from __future__ import annotations

import unittest

from search.engine.canonical import (
    CANONICAL_FORM_VERSION,
    MAX_CANONICAL_INT,
    CanonicalFormError,
    canonical_bytes,
    canonical_json,
    canonicalize,
    digest,
    digest_bytes,
)


class TestProfilePin(unittest.TestCase):
    def test_version_is_pinned(self) -> None:
        self.assertEqual(CANONICAL_FORM_VERSION, "aleph-canonical/0.2.0")

    def test_integer_bound_is_pinned(self) -> None:
        self.assertEqual(MAX_CANONICAL_INT, 2**53 - 1)


class TestNumberVectors(unittest.TestCase):
    """ECMAScript ``Number::toString`` cases, including the 0.1.0 divergences."""

    VECTORS = (
        (0.0, "0"),
        (-0.0, "0"),
        (1.0, "1"),
        (-1.0, "-1"),
        (100.0, "100"),
        (0.5, "0.5"),
        (-2.5, "-2.5"),
        (123.456, "123.456"),
        (0.30000000000000004, "0.30000000000000004"),
        (1e15, "1000000000000000"),
        (1e16, "10000000000000000"),
        (1e20, "100000000000000000000"),
        (1e21, "1e+21"),
        (1e22, "1e+22"),
        (1e-5, "0.00001"),
        (1e-6, "0.000001"),
        (1.2e-6, "0.0000012"),
        (1.2e-7, "1.2e-7"),
        (1e-7, "1e-7"),
        (-1e-7, "-1e-7"),
        (5e-324, "5e-324"),
        (1.7976931348623157e308, "1.7976931348623157e+308"),
        (2.2250738585072014e-308, "2.2250738585072014e-308"),
        (9007199254740991.0, "9007199254740991"),
        (123456789012345678.0, "123456789012345680"),
    )

    def test_number_rendering(self) -> None:
        for value, expected in self.VECTORS:
            self.assertEqual(canonical_json(value), expected, repr(value))


class TestStringVectors(unittest.TestCase):
    VECTORS = (
        ("", '""'),
        ("plain", '"plain"'),
        ('a"b', '"a\\"b"'),
        ("a\\b", '"a\\\\b"'),
        ("/", '"/"'),
        ("\u0000", '"\\u0000"'),
        ("\u001f", '"\\u001f"'),
        ("\b\t\n\f\r", '"\\b\\t\\n\\f\\r"'),
        ("\u007f", '"\u007f"'),
        ("\u2028\u2029", '"\u2028\u2029"'),
        ("\u00e9", '"\u00e9"'),
        ("e\u0301", '"\u00e9"'),
        ("A\u030A", '"\u00c5"'),
        ("\ufb01", '"\ufb01"'),
        ("\U0001F600", '"\U0001F600"'),
        ("\U00010000", '"\U00010000"'),
        ("\ufffd", '"\ufffd"'),
        ("Z\u00fcrich", '"Z\u00fcrich"'),
        ("\u65e5\u672c\u8a9e", '"\u65e5\u672c\u8a9e"'),
    )

    def test_string_rendering(self) -> None:
        for value, expected in self.VECTORS:
            self.assertEqual(canonical_json(value), expected, repr(value))


class TestNfcExtension(unittest.TestCase):
    """NFC pre-normalization is the one documented divergence from strict JCS."""

    def test_composed_and_decomposed_spellings_collide(self) -> None:
        self.assertEqual(canonical_bytes("\u00e9"), canonical_bytes("e\u0301"))
        self.assertEqual(canonical_bytes("\u00e9"), b'"\xc3\xa9"')

    def test_nfc_is_not_nfkc(self) -> None:
        # Compatibility forms stay distinct because a tokenizer can observe them.
        self.assertEqual(canonical_json("\ufb01"), '"\ufb01"')
        self.assertNotEqual(canonical_bytes("\u00a0"), canonical_bytes(" "))

    def test_astral_text_is_literal_utf8(self) -> None:
        self.assertEqual(canonical_bytes("\U0001F600"), b'"\xf0\x9f\x98\x80"')


class TestKeyOrderVectors(unittest.TestCase):
    """UTF-16 code-unit order, including cases code-point order gets wrong."""

    VECTORS = (
        ({"b": 1, "a": 2}, '{"a":2,"b":1}'),
        ({"B": 1, "a": 2, "A": 3, "b": 4}, '{"A":3,"B":1,"a":2,"b":4}'),
        ({"Z": 1, "a": 2, "A": 3}, '{"A":3,"Z":1,"a":2}'),
        ({"\ue000": 1, "\U00010000": 2}, '{"\U00010000":2,"\ue000":1}'),
        ({"10": 1, "9": 2}, '{"10":1,"9":2}'),
    )

    def test_key_order(self) -> None:
        for value, expected in self.VECTORS:
            self.assertEqual(canonical_json(value), expected, repr(value))

    def test_key_order_is_insertion_order_independent(self) -> None:
        forward = {"\ue000": 1, "\U00010000": 2}
        backward = {"\U00010000": 2, "\ue000": 1}
        self.assertEqual(canonical_bytes(forward), canonical_bytes(backward))


class TestStructureVectors(unittest.TestCase):
    def test_structures(self) -> None:
        vectors = (
            ([1.0, -0.0, 2], "[1,0,2]"),
            ({"w": 1.0, "r": [0.5, 1.0]}, '{"r":[0.5,1],"w":1}'),
            ({"z": None, "a": {"y": [True, False]}}, '{"a":{"y":[true,false]},"z":null}'),
            (True, "true"),
            (False, "false"),
            (None, "null"),
        )
        for value, expected in vectors:
            self.assertEqual(canonical_json(value), expected, repr(value))

    def test_ascii_object_bytes(self) -> None:
        self.assertEqual(canonical_bytes({"b": 1, "a": 2}), b'{"a":2,"b":1}')


class TestPinnedDigests(unittest.TestCase):
    """SHA-256 pins, cross-checked against ``shasum -a 256``."""

    def test_simple_object(self) -> None:
        expected = "sha256:d3626ac30a87e6f7a6428233b3c68299976865fa5508e4267c5415c76af7a772"
        self.assertEqual(digest({"a": 2, "b": 1}), expected)
        self.assertEqual(digest({"b": 1, "a": 2}), expected)
        self.assertEqual(digest_bytes(b'{"a":2,"b":1}'), expected)

    def test_nfc_digest_matches_its_bytes(self) -> None:
        expected = "sha256:f2886017e9c7abacf804b54d64787dce2b611c9544ba21f3affdd126a6e50086"
        self.assertEqual(digest("\u00e9"), expected)
        self.assertEqual(digest("e\u0301"), expected)

    def test_receipt_shaped_document(self) -> None:
        value = {"schemaVersion": "aleph-canonical/0.2.0", "value": {"ratio": 0.1, "weight": 1}}
        expected = "sha256:290f1f6ad3080e97b99f19f94e1598017c6eee0ae839fefc0021c6fb395621a9"
        self.assertEqual(digest(value), expected)


class TestFailClosedVectors(unittest.TestCase):
    def test_integer_bound(self) -> None:
        self.assertEqual(canonical_json(2**53 - 1), "9007199254740991")
        for value in (2**53, -(2**53), 10**21):
            with self.assertRaises(CanonicalFormError):
                canonicalize(value)

    def test_non_finite_numbers(self) -> None:
        for value in (float("nan"), float("inf"), float("-inf")):
            with self.assertRaises(CanonicalFormError):
                canonicalize(value)

    def test_lone_surrogates(self) -> None:
        for value in ("\ud800", "x\udfff", {"k": "\ud800"}, {"\ud800": 1}):
            with self.assertRaises(CanonicalFormError):
                canonicalize(value)

    def test_nfc_key_collision(self) -> None:
        with self.assertRaises(CanonicalFormError):
            canonicalize({"\u00e9": 1, "e\u0301": 2})

    def test_unsupported_inputs(self) -> None:
        unsupported = (b"bytes", bytearray(b"x"), 1 + 2j, {1: "int key"}, {None: 1}, {1, 2})
        for value in unsupported:
            with self.assertRaises(CanonicalFormError):
                canonicalize(value)
        with self.assertRaises(CanonicalFormError):
            canonicalize({"k": object()})


if __name__ == "__main__":
    unittest.main()
