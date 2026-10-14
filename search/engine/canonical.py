"""Canonical serialization primitives for the Aleph engine artifact kernel.

Every digest written into a run bundle is taken over the canonical form built
here:

- text is Unicode NFC normalized before hashing;
- mapping keys must be strings and are emitted in sorted order;
- sequence order is preserved, because message order is semantic;
- integers stay exact, floats must be finite, and ``-0.0`` collapses to ``0.0``;
- output is UTF-8 with no insignificant whitespace.

The module is pure standard library. It must stay importable without MLX,
network access, or optional embedding packages.
"""

from __future__ import annotations

import hashlib
import json
import math
from typing import Any, Mapping, Sequence
import unicodedata

CANONICAL_FORM_VERSION = "aleph-canonical/0.1.0"
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
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise CanonicalFormError(f"non-finite float has no canonical form: {value!r}")
        return 0.0 if value == 0.0 else value
    if isinstance(value, str):
        return normalize_text(value)
    if isinstance(value, Mapping):
        canonical: dict[str, Any] = {}
        for key in value:
            if not isinstance(key, str):
                raise CanonicalFormError(f"mapping keys must be str, got {type(key).__name__}")
            normalized_key = normalize_text(key)
            if normalized_key in canonical:
                raise CanonicalFormError(f"mapping keys collide after NFC: {normalized_key!r}")
            canonical[normalized_key] = canonicalize(value[key])
        return {key: canonical[key] for key in sorted(canonical)}
    if isinstance(value, (bytes, bytearray)):
        raise CanonicalFormError("raw bytes must be stored as a blob, not inlined")
    if isinstance(value, Sequence):
        return [canonicalize(item) for item in value]
    raise CanonicalFormError(f"unsupported canonical type: {type(value).__name__}")


def canonical_json(value: Any) -> str:
    """Return the canonical JSON text for ``value``."""
    return json.dumps(
        canonicalize(value),
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    )


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
    return len(normalize_text(value).encode("utf-8"))
