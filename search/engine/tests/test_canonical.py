"""Canonical serialization: determinism, Unicode, and fail-closed rejection."""

from __future__ import annotations

import math
import unittest

from search.engine.canonical import (
    CanonicalFormError,
    bare_digest,
    canonical_bytes,
    canonical_json,
    canonicalize,
    digest,
    digest_bytes,
    is_digest,
    normalize_text,
    utf8_byte_length,
)


class TestNormalizeText(unittest.TestCase):
    def test_nfc_composes_decomposed_graphemes(self) -> None:
        self.assertEqual(normalize_text("e\u0301"), "\u00e9")

    def test_nfc_keeps_compatibility_distinctions(self) -> None:
        # NFKC would fold these; NFC must not.
        self.assertEqual(normalize_text("\u00a0"), "\u00a0")  # NO-BREAK SPACE
        self.assertEqual(normalize_text("\uff21"), "\uff21")  # fullwidth A
        self.assertEqual(normalize_text("\ufb01"), "\ufb01")  # ﬁ ligature

    def test_whitespace_is_never_stripped_or_collapsed(self) -> None:
        value = "  leading\n\n\ttrailing  "
        self.assertEqual(normalize_text(value), value)

    def test_rejects_non_string(self) -> None:
        with self.assertRaises(CanonicalFormError):
            normalize_text(42)  # type: ignore[arg-type]


class TestCanonicalize(unittest.TestCase):
    def test_cjk_and_emoji_round_trip(self) -> None:
        value = {"text": "你好，世界 \U0001f30d", "n": 1}
        self.assertEqual(canonical_json(value), '{"n":1,"text":"你好，世界 \U0001f30d"}')

    def test_sorted_keys_and_compact_separators(self) -> None:
        value = {"b": 1, "a": {"z": 2, "y": [1, 2]}}
        self.assertEqual(canonical_json(value), '{"a":{"y":[1,2],"z":2},"b":1}')

    def test_dict_key_order_does_not_change_digest(self) -> None:
        first = {"a": 1, "b": [1, 2, 3], "c": "x"}
        second = {"c": "x", "b": [1, 2, 3], "a": 1}
        self.assertEqual(digest(first), digest(second))

    def test_sequence_order_is_semantic(self) -> None:
        self.assertNotEqual(digest([1, 2, 3]), digest([3, 2, 1]))

    def test_nfc_collisions_collapse_but_compatibility_does_not(self) -> None:
        composed = "caf\u00e9"
        decomposed = "cafe\u0301"
        self.assertEqual(digest(composed), digest(decomposed))
        self.assertNotEqual(digest("\u00a0"), digest(" "))

    def test_negative_zero_collapses_to_zero(self) -> None:
        self.assertEqual(canonicalize({"x": -0.0}), {"x": 0.0})
        self.assertEqual(digest(-0.0), digest(0.0))

    def test_non_finite_floats_rejected(self) -> None:
        for bad in (float("nan"), float("inf"), -float("inf")):
            with self.assertRaises(CanonicalFormError):
                canonicalize({"x": bad})

    def test_raw_bytes_rejected(self) -> None:
        with self.assertRaises(CanonicalFormError):
            canonicalize(b"raw")
        with self.assertRaises(CanonicalFormError):
            canonicalize({"x": bytearray(b"raw")})

    def test_non_string_mapping_keys_rejected(self) -> None:
        with self.assertRaises(CanonicalFormError):
            canonicalize({1: "one"})  # type: ignore[dict-item]

    def test_nfc_key_collision_rejected(self) -> None:
        with self.assertRaises(CanonicalFormError):
            canonicalize({"e\u0301": 1, "\u00e9": 2})

    def test_unsupported_types_rejected(self) -> None:
        for bad in ({1, 2, 3}, object(), math):
            with self.assertRaises(CanonicalFormError):
                canonicalize({"x": bad})

    def test_deep_nesting(self) -> None:
        value: dict = {"leaf": 1}
        for _ in range(50):
            value = {"nested": value}
        self.assertTrue(is_digest(digest(value)))

    def test_empty_containers(self) -> None:
        self.assertEqual(canonical_json({}), "{}")
        self.assertEqual(canonical_json([]), "[]")
        self.assertEqual(canonical_json(None), "null")


class TestDigest(unittest.TestCase):
    def test_prefixed_sha256(self) -> None:
        value = digest("payload")
        self.assertTrue(value.startswith("sha256:"))
        self.assertEqual(len(value), 7 + 64)

    def test_digest_bytes_matches_hex(self) -> None:
        payload = "payload".encode("utf-8")
        import hashlib

        self.assertEqual(
            digest_bytes(payload), "sha256:" + hashlib.sha256(payload).hexdigest()
        )

    def test_bare_digest_is_unprefixed(self) -> None:
        value = bare_digest("payload")
        self.assertEqual(value, digest("payload").split(":", 1)[1])

    def test_is_digest(self) -> None:
        good = "sha256:" + "a" * 64
        self.assertTrue(is_digest(good))
        for bad in ("sha256:" + "a" * 63, "sha512:" + "a" * 64, "sha256:" + "A" * 64, "", None, 42):
            self.assertFalse(is_digest(bad))  # type: ignore[arg-type]

    def test_canonical_bytes_matches_canonical_json(self) -> None:
        value = {"b": "\u00e9\u4f60\u597d \U0001f30d", "a": [1, -0.0]}
        self.assertEqual(canonical_bytes(value), canonical_json(value).encode("utf-8"))


class TestUtf8ByteLength(unittest.TestCase):
    def test_multibyte_lengths(self) -> None:
        self.assertEqual(utf8_byte_length("a"), 1)
        self.assertEqual(utf8_byte_length("\u00e9"), 2)
        self.assertEqual(utf8_byte_length("\u4f60"), 3)
        self.assertEqual(utf8_byte_length("\U0001f30d"), 4)
        self.assertEqual(utf8_byte_length("你好"), 6)

    def test_is_byte_measure_not_token_count(self) -> None:
        # The docstring contract: this is a byte measurement, never a token count.
        self.assertEqual(utf8_byte_length("a" * 10), 10)


if __name__ == "__main__":
    unittest.main()
