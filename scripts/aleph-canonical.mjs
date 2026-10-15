/**
 * JavaScript implementation of the Aleph canonical form (`aleph-canonical/0.2.0`).
 *
 * The engine (`search/engine/canonical.py`; decision record
 * `docs/decisions/0006-canonical-json-jcs-alignment.md`) takes every digest
 * over this canonical form: the RFC 8785 (JCS) serialization profile with
 * Unicode NFC pre-normalization as the one documented Aleph extension. This
 * module is the second, non-Python implementation: it rebuilds the same bytes
 * and digests from native JavaScript primitives alone (`JSON.stringify`,
 * default `Array.prototype.sort` for the UTF-16 key order, and
 * `String.prototype.normalize("NFC")`), and `scripts/check-canonical-parity.mjs`
 * differentials it against the Python engine in `npm test`. It is verification
 * surface, not engine code: no engine module imports it, and its only
 * dependency is `node:crypto`.
 *
 * Documented asymmetries against the Python profile (both deliberate):
 * - A JavaScript number is always an IEEE-754 double, so the I-JSON exact
 *   integer bound (`|n| <= 2**53 - 1`) cannot be re-checked here: an integer
 *   that large has already been rounded by the time a `JSON.parse`d value
 *   exists. The bound is enforced where exact integers exist (the Python
 *   writer); this reader accepts any finite double and renders it byte for
 *   byte as the Python writer would have.
 * - `bigint` values are rejected: pass a `Number`. The Python profile has no
 *   integer domain beyond the I-JSON bound, so a `bigint` has no canonical
 *   counterpart.
 */

import { createHash } from "node:crypto";

export const CANONICAL_FORM_VERSION = "aleph-canonical/0.2.0";
export const DIGEST_ALGORITHM = "sha256";
export const DIGEST_PREFIX = `${DIGEST_ALGORITHM}:`;
export const MAX_CANONICAL_INT = 2 ** 53 - 1;

export class CanonicalFormError extends Error {
  constructor(message) {
    super(message);
    this.name = "CanonicalFormError";
  }
}

const ASCII_ONLY = /^[\u0000-\u007f]*$/;
const textEncoder = new TextEncoder();

export function normalizeText(value) {
  if (typeof value !== "string") {
    throw new CanonicalFormError("normalizeText requires a string");
  }
  return value.normalize("NFC");
}

function assertNoLoneSurrogates(text, label) {
  for (let index = 0; index < text.length; index += 1) {
    const code = text.charCodeAt(index);
    if (code >= 0xd800 && code <= 0xdbff) {
      const next = text.charCodeAt(index + 1);
      if (!(next >= 0xdc00 && next <= 0xdfff)) {
        throw new CanonicalFormError(`${label} contains a lone surrogate`);
      }
      index += 1;
    } else if (code >= 0xdc00 && code <= 0xdfff) {
      throw new CanonicalFormError(`${label} contains a lone surrogate`);
    }
  }
}

export function utf8ByteLength(value) {
  const normalized = normalizeText(value);
  assertNoLoneSurrogates(normalized, "value");
  return textEncoder.encode(normalized).length;
}

function describeType(value) {
  if (value === null) return "null";
  if (typeof value === "object") {
    return value.constructor?.name ?? "object";
  }
  return typeof value;
}

function isPlainObject(value) {
  if (value === null || typeof value !== "object") return false;
  const prototype = Object.getPrototypeOf(value);
  return prototype === null || prototype === Object.prototype;
}

/**
 * Return a normalized tree, the JavaScript analogue of `canonicalize` in the
 * Python engine: NFC strings, `-0` collapsed to `0`, arrays with every element
 * canonicalized, and plain objects with NFC-normalized unique keys. Object key
 * ORDER is not materialized in the returned tree — JavaScript object iteration
 * order is not controllable for integer-like keys — so `canonicalJson`
 * computes the RFC 8785 order at render time.
 */
export function canonicalize(value) {
  if (value === null || typeof value === "boolean") return value;
  if (typeof value === "number") {
    if (!Number.isFinite(value)) {
      throw new CanonicalFormError(`non-finite number has no canonical form: ${value}`);
    }
    return value === 0 ? 0 : value;
  }
  if (typeof value === "string") {
    if (ASCII_ONLY.test(value)) return value; // ASCII is NFC-invariant and surrogate-free
    const normalized = value.normalize("NFC");
    assertNoLoneSurrogates(normalized, "string");
    return normalized;
  }
  if (typeof value === "bigint") {
    throw new CanonicalFormError(
      "bigint has no canonical form; pass a Number (the I-JSON integer bound is a Python-write-side constraint)"
    );
  }
  if (Array.isArray(value)) {
    const items = [];
    for (let index = 0; index < value.length; index += 1) {
      if (!(index in value)) {
        throw new CanonicalFormError("sparse arrays have no canonical form");
      }
      items.push(canonicalize(value[index]));
    }
    return items;
  }
  if (ArrayBuffer.isView(value) || value instanceof ArrayBuffer) {
    throw new CanonicalFormError("raw bytes must be stored as a blob, not inlined");
  }
  if (isPlainObject(value)) {
    if (Object.getOwnPropertySymbols(value).length > 0) {
      throw new CanonicalFormError("symbol-keyed properties have no canonical form");
    }
    const canonical = {};
    const seenKeys = new Set();
    for (const key of Object.keys(value)) {
      const normalizedKey = ASCII_ONLY.test(key) ? key : key.normalize("NFC");
      if (!ASCII_ONLY.test(key)) assertNoLoneSurrogates(normalizedKey, "mapping key");
      if (seenKeys.has(normalizedKey)) {
        throw new CanonicalFormError(`mapping keys collide after NFC: ${JSON.stringify(normalizedKey)}`);
      }
      seenKeys.add(normalizedKey);
      Object.defineProperty(canonical, normalizedKey, {
        value: canonicalize(value[key]),
        enumerable: true,
        writable: true,
        configurable: true,
      });
    }
    return canonical;
  }
  throw new CanonicalFormError(`unsupported canonical type: ${describeType(value)}`);
}

// RFC 8785 key order is UTF-16 code units; the default Array.prototype.sort()
// comparator compares exactly those code units, and canonical keys are already
// NFC-normalized, so the default comparator is exactly the profile order.
function sortedKeys(object) {
  return Object.keys(object).sort();
}

function render(value) {
  if (value === null) return "null";
  const kind = typeof value;
  if (kind === "boolean") return value ? "true" : "false";
  if (kind === "number") return String(value);
  if (kind === "string") return JSON.stringify(value);
  if (Array.isArray(value)) return `[${value.map(render).join(",")}]`;
  if (kind === "object") {
    return `{${sortedKeys(value)
      .map((key) => `${JSON.stringify(key)}:${render(value[key])}`)
      .join(",")}}`;
  }
  throw new CanonicalFormError(`no canonical rendering for ${kind}`);
}

export function canonicalJson(value) {
  return render(canonicalize(value));
}

export function canonicalBytes(value) {
  return textEncoder.encode(canonicalJson(value));
}

export function digestBytes(payload) {
  if (!(payload instanceof Uint8Array)) {
    throw new CanonicalFormError("digestBytes requires a Uint8Array");
  }
  return DIGEST_PREFIX + createHash("sha256").update(payload).digest("hex");
}

export function digest(value) {
  return digestBytes(canonicalBytes(value));
}

export function bareDigest(value) {
  return digest(value).slice(DIGEST_PREFIX.length);
}

export function isDigest(value) {
  return (
    typeof value === "string" &&
    value.startsWith(DIGEST_PREFIX) &&
    /^[0-9a-f]{64}$/.test(value.slice(DIGEST_PREFIX.length))
  );
}
