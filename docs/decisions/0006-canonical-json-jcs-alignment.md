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
fixed-seed doubles, a full-BMP string sweep (plus astral and combining
samples), and key-order cases through the new formatter and through ``node``
(``JSON.stringify``, ``String.prototype.normalize``, default sort) and
requires byte equality; a one-off 100,000 vector fuzz of the number
comparison finished with zero mismatches. Fixed conformance vectors with
expected bytes and digests (``test_canonical_vectors.py``) pin the profile
where node is absent.

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

## Relation to the practice review

The engine and benchmark practice review
(``docs/research/engine-and-benchmark-practice-review.md``, sections 2 and 7)
surveyed the same divergence and recorded the opposite *timing*: keep
``aleph-canonical/0.1.0``, write the profile down, add conformance vectors,
and leave JCS interoperability open until a cross-language consumer exists.
This ADR supersedes that recommendation for the text form; the review's own
items are fulfilled, and the records stay reconciled in writing:

1. The deferral premise ("only the Python verifier computes digests") is
   already half-invalid on this tree: the projection this canonical form
   underwrites has a TypeScript contract (``packages/core``) and a web
   consumer, and digest recomputation is the stated verification story. The
   cost of changing the form is at its minimum now — the engine is
   pre-release and no bundle has left the repository — while after the first
   external bundle the versioned form would have to break instead.
2. Under 0.1.0, byte-equality in any other language meant reimplementing
   Python's float formatting; the audit found 1.71 % of sampled doubles
   diverging across three mundane classes, so such a port would drift
   silently. Under the JCS-aligned form a JavaScript consumer recomputes
   digests from native primitives alone: ``JSON.stringify`` for numbers and
   strings, ``Array.prototype.sort()`` for UTF-16 key order, and
   ``String.prototype.normalize("NFC")`` for the extension.
3. Interoperability is therefore resolved for the text form: for input that
   is already NFC, the canonical bytes equal strict-JCS bytes; the NFC
   pre-normalization remains the single documented extension, pinned by a
   conformance vector.

The review document and ``docs/research/research-process.md`` carry dated
update notes pointing here so the two records cannot be read as
contradictory.

## References

- RFC 8785, JSON Canonicalization Scheme (JCS), §3.2.2 numbers and key order.
- RFC 7493, I-JSON, integer exactness bound.
- JSONCANON: Trustworthy JSON Canonicalization via Dual Independent
  Implementations and Differential Testing (Zenodo 20819570).
