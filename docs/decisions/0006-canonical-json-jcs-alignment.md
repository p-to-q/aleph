# ADR 0006: Canonical JSON aligned with RFC 8785 (JCS)

## Status

Accepted.

## Context

Every engine digest (event content digests, blob digests, stream digest,
projection digests) is taken over the canonical JSON form built in
``search/engine/canonical.py``. Consumers outside Python — starting with the
web app — will eventually recompute or check those digests, so the canonical
form must follow a documented cross-language standard rather than a local
convention.

An audit by differential testing against ``JSON.stringify`` (the ECMAScript
reference that RFC 8785 §3.2.2.3 adopts) found 1710 mismatches in 100,000
sampled doubles (1.71 %), in three classes:

- integral-valued floats kept a Python ``.0`` suffix (``1.0`` vs ``1``),
- exponent notation kept zero padding (``1e-05`` vs ``1e-5``),
- fixed/exponent switching thresholds differed (``1e16`` vs
  ``10000000000000000``).

Integers above ``2**53 - 1`` also round-trip lossily through JavaScript
consumers (``9007199254740993`` becomes ``9007199254740992``), and key order
differed from the JCS UTF-16 code-unit order for non-BMP strings. Prior art:
the JSONCANON work (Zenodo 20819570) argues exactly this standard-plus-
differential-testing discipline for canonicalization implementations.

## Decision

Adopt the RFC 8785 (JCS) serialization profile in ``canonical.py``:

- numbers render per ECMAScript ``Number::toString`` (shortest round-trip
  digits; fixed notation for ``1e-6 <= |x| < 1e21``; signed exponent notation
  otherwise; ``-0.0`` renders ``0``);
- mapping keys are ordered by UTF-16 code units;
- strings must be valid Unicode: lone surrogates have no canonical form and
  raise ``CanonicalFormError``;
- integers must stay within the I-JSON exact range ``|n| <= 2**53 - 1``
  (RFC 7493, the input domain RFC 8785 requires);
- text is still NFC-normalized before serialization — an explicit Aleph
  extension; the canonical form is the JCS form *of the NFC-normalized value*;
- ``CANONICAL_FORM_VERSION`` becomes ``aleph-canonical/0.2.0`` and every
  engine-created bundle records it as ``canonicalSchemaVersion``.

Verification: a differential test (``test_jcs_differential.py``) renders 2000
fixed-seed doubles plus boundary vectors through the new formatter and through
``node -e 'JSON.stringify'`` and requires byte equality; a one-off 100,000
vector fuzz of the same comparison finished with zero mismatches.

## Consequences

- Digests of any structure containing integral-valued floats (for example a
  weight ``1.0``), exponent-rendered floats, or ``-0.0`` change. The engine is
  pre-release and no bundle has left the repository, so the version bump is
  contained; stored fixtures are rebuilt by their builders.
- Cross-language digest recomputation with standard JCS tooling becomes
  possible; a JS consumer no longer needs a bespoke canonicalizer.
- The NFC extension remains a documented divergence from a strict JCS library:
  libraries operating on already-NFC text agree with us byte-for-byte.
- The integer bound turns a silent JavaScript precision loss into a typed
  fail-closed error at write time.

## References

- RFC 8785, JSON Canonicalization Scheme (JCS), §3.2.2 numbers and key order.
- RFC 7493, I-JSON, integer exactness bound.
- JSONCANON: Trustworthy JSON Canonicalization via Dual Independent
  Implementations and Differential Testing (Zenodo 20819570).
