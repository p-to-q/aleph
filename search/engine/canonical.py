"""Canonical serialization primitives for the Aleph engine artifact kernel.

Every digest written into a run bundle is taken over the canonical form built
here:

- text is Unicode NFC normalized before hashing (an Aleph extension: RFC 8785
  does not define normalization, but the NFC form is what gets encoded);
- mapping keys must be strings and are ordered by UTF-16 code units, the JSON
  Canonicalization Scheme (RFC 8785) key order;
- sequence order is preserved, because message order is semantic;
- numbers follow the RFC 8785 number profile (ECMAScript ``Number::toString``):
  shortest round-trip digits, fixed notation for ``1e-6 <= |x| < 1e21``,
  signed exponent notation otherwise, and ``-0.0`` collapses to ``0``;
- integers must stay within the I-JSON exact range ``|n| <= 2**53 - 1`` and
  strings must be valid Unicode: lone surrogates have no canonical form;
- output is UTF-8 with no insignificant whitespace.

Serialization is the RFC 8785 (JCS) profile modulo the NFC extension, so an
independent implementation with a standard JCS library (given NFC-normalized
text) recomputes every digest byte-for-byte.

The module is pure standard library. It must stay importable without MLX,
network access, or optional embedding packages.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections.abc import Mapping, Sequence
from functools import lru_cache
from typing import Any
import unicodedata

CANONICAL_FORM_VERSION = "aleph-canonical/0.2.0"  # RFC 8785-aligned; see docs/decisions/0006
DIGEST_ALGORITHM = "sha256"
DIGEST_PREFIX = f"{DIGEST_ALGORITHM}:"


class CanonicalFormError(ValueError):
    """Raised when a value has no canonical representation."""


def normalize_text(value: str) -> str:
    """Return the NFC normalized form of ``value``.

    NFC is deliberately chosen over NFKC. NFC merges only canonical
    equivalences, so a composed and a decomposed spelling of the same grapheme
    collapse, while compatibility distinctions that a tokenizer can observe stay
    distinct: NO-BREAK SPACE is not folded into SPACE, fullwidth CJK forms are
    not folded into ASCII, and ``ﬁ`` is not folded into ``fi``. Whitespace is
    never stripped or collapsed, because leading, trailing, and repeated
    whitespace changes the rendered model input.
    """
    if not isinstance(value, str):
        raise CanonicalFormError("normalize_text requires a str")
    return unicodedata.normalize("NFC", value)


MAX_CANONICAL_INT = 2**53 - 1
"""Largest integer that is exact in IEEE-754 doubles (the I-JSON bound)."""


def _check_unicode(value: str, label: str) -> None:
    """Reject lone surrogates: they have no canonical (valid-Unicode) form."""
    try:
        value.encode("utf-8")
    except UnicodeEncodeError as error:
        raise CanonicalFormError(f"{label} contains a lone surrogate: {value!r}") from error


def _utf16_sort_key(key: str) -> bytes:
    """RFC 8785 key order: compare UTF-16 code units, not code points."""
    return key.encode("utf-16-be")


def _canonical_key_tokens(mapping: Mapping) -> list[str]:
    """Return the mapping's keys in RFC 8785 (UTF-16 code unit) order.

    Pure-ASCII key sets sort identically under Python's code-point order, and
    that is by far the common case, so the UTF-16 encode is only paid when a
    non-ASCII key is present.
    """
    keys = list(mapping)
    if all(key.isascii() for key in keys):
        return sorted(keys)
    return sorted(keys, key=_utf16_sort_key)


_NEEDS_ESCAPE = re.compile(r'[\x00-\x1f"\\]').search


def _render_string(value: str) -> str:
    """Quote a string per RFC 8785; plain strings skip the JSON encoder."""
    if _NEEDS_ESCAPE(value) is None:
        return '"' + value + '"'
    return json.dumps(value, ensure_ascii=False)


@lru_cache(maxsize=65536)
def _es_number_text(value: float) -> str:
    """Render a finite float like ECMAScript ``Number::toString(10)``.

    Cached because digest loops re-render the same metric values many times.

    This is the RFC 8785 number profile: shortest round-trip digits, fixed
    notation for ``1e-6 <= |x| < 1e21``, otherwise signed exponent notation
    with no zero padding. It is verified against ``JSON.stringify`` by a
    differential test.
    """
    if value == 0.0:
        return "0"
    sign = "-" if value < 0.0 else ""
    text = repr(abs(value))
    mantissa, marker, exponent = text.partition("e")
    decimal_exponent = int(exponent) if marker else 0
    integer_part, _, fraction_part = mantissa.partition(".")
    combined = integer_part + fraction_part
    digits = combined.lstrip("0")
    zeros_stripped = len(combined) - len(digits)
    digits = digits.rstrip("0") or "0"
    length = len(digits)
    position = len(integer_part) + decimal_exponent - zeros_stripped
    if length <= position <= 21:
        return sign + digits + "0" * (position - length)
    if 0 < position <= 21:
        return sign + digits[:position] + "." + digits[position:]
    if -6 < position <= 0:
        return sign + "0." + "0" * -position + digits
    exponent_value = position - 1
    prefix = digits if length == 1 else digits[0] + "." + digits[1:]
    return (
        sign + prefix + "e" + ("+" if exponent_value >= 0 else "-") + str(abs(exponent_value))
    )


def _render_canonical(value: Any) -> str:
    """Serialize a canonicalized value with the RFC 8785 serialization rules."""
    if value is None:
        return "null"
    if value is True:
        return "true"
    if value is False:
        return "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return _es_number_text(value)
    if isinstance(value, str):
        return _render_string(value)
    if isinstance(value, list):
        if not value:
            return "[]"
        return "[" + ",".join(map(_render_canonical, value)) + "]"
    if isinstance(value, dict):
        if not value:
            return "{}"
        return "{" + ",".join(
            _render_string(key) + ":" + _render_canonical(item)
            for key, item in value.items()
        ) + "}"
    raise CanonicalFormError(f"no canonical rendering for {type(value).__name__}")


def canonicalize(value: Any) -> Any:
    """Return a canonical JSON-compatible projection of ``value``.

    Accepted inputs are ``None``, ``bool``, ``int``, finite ``float``, ``str``,
    string-keyed mappings, and sequences. Everything else has no canonical form
    and raises, so an unsupported object can never be silently coerced into a
    digest input.
    """
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, int):
        if value > MAX_CANONICAL_INT or value < -MAX_CANONICAL_INT:
            raise CanonicalFormError(
                f"integer outside the I-JSON exact range (|n| <= 2**53 - 1): {value}"
            )
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise CanonicalFormError(f"non-finite float has no canonical form: {value!r}")
        return 0.0 if value == 0.0 else value
    if isinstance(value, str):
        if value.isascii():
            return value  # ASCII is NFC-invariant and never contains surrogates
        normalized = normalize_text(value)
        _check_unicode(normalized, "string")
        return normalized
    if isinstance(value, Mapping):
        canonical: dict[str, Any] = {}
        for key in value:
            if not isinstance(key, str):
                raise CanonicalFormError(f"mapping keys must be str, got {type(key).__name__}")
            if key.isascii():
                normalized_key = key
            else:
                normalized_key = normalize_text(key)
                _check_unicode(normalized_key, "mapping key")
            if normalized_key in canonical:
                raise CanonicalFormError(f"mapping keys collide after NFC: {normalized_key!r}")
            canonical[normalized_key] = canonicalize(value[key])
        return {key: canonical[key] for key in _canonical_key_tokens(canonical)}
    if isinstance(value, (bytes, bytearray)):
        raise CanonicalFormError("raw bytes must be stored as a blob, not inlined")
    if isinstance(value, Sequence):
        return [canonicalize(item) for item in value]
    raise CanonicalFormError(f"unsupported canonical type: {type(value).__name__}")


def canonical_json(value: Any) -> str:
    """Return the canonical JSON text for ``value`` (RFC 8785-aligned)."""
    return _render_canonical(canonicalize(value))


def canonical_bytes(value: Any) -> bytes:
    """Return the canonical UTF-8 bytes for ``value``."""
    return canonical_json(value).encode("utf-8")


def digest_bytes(payload: bytes) -> str:
    """Return the prefixed SHA-256 digest of ``payload``."""
    if not isinstance(payload, (bytes, bytearray)):
        raise CanonicalFormError("digest_bytes requires bytes")
    return DIGEST_PREFIX + hashlib.sha256(payload).hexdigest()


def digest(value: Any) -> str:
    """Return the prefixed SHA-256 digest of the canonical form of ``value``."""
    return digest_bytes(canonical_bytes(value))


def bare_digest(value: Any) -> str:
    """Return the unprefixed hex digest, for filesystem blob paths."""
    return digest(value).split(":", 1)[1]


def is_digest(value: Any) -> bool:
    """Return whether ``value`` is a well-formed prefixed SHA-256 digest."""
    if not isinstance(value, str) or not value.startswith(DIGEST_PREFIX):
        return False
    hex_part = value[len(DIGEST_PREFIX) :]
    return len(hex_part) == 64 and all(char in "0123456789abcdef" for char in hex_part)


def utf8_byte_length(value: str) -> int:
    """Return the canonical UTF-8 byte length of ``value``.

    This is a byte measurement, never a scientific coordinate token cost.
    Token costs come from a declared tokenizer view in the ledger.
    """
    try:
        return len(normalize_text(value).encode("utf-8"))
    except UnicodeEncodeError as error:
        raise CanonicalFormError(f"value contains a lone surrogate: {value!r}") from error
