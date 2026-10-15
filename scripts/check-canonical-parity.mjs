/**
 * Cross-language parity check for the Aleph canonical form (`aleph-canonical/0.2.0`).
 *
 * Phase 1 pins the conformance vectors — the same expectations as
 * `search/engine/tests/test_canonical_vectors.py`, including the RFC 8785
 * worked example, the Appendix B number table, and the three pinned SHA-256
 * digests — against `scripts/aleph-canonical.mjs`, so the JavaScript
 * implementation cannot drift silently even where no Python interpreter exists.
 *
 * Phase 2 (skipped with a note when `python3` is absent) differentials the
 * JavaScript implementation against the engine's `search/engine/canonical.py`
 * over a deterministic corpus: fixed-seed doubles, a full-BMP string sweep,
 * key-order permutations, nested structures, and fail-closed cases. Both sides
 * must agree on the canonical bytes AND the digest for every row, and both
 * sides must fail closed (`CanonicalFormError`) on the same rows.
 */

import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import path from "node:path";

import {
  CANONICAL_FORM_VERSION,
  MAX_CANONICAL_INT,
  CanonicalFormError,
  bareDigest,
  canonicalBytes,
  canonicalJson,
  canonicalize,
  digest,
  digestBytes,
  isDigest,
  normalizeText,
  utf8ByteLength,
} from "./aleph-canonical.mjs";

const REPO_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");

const failures = [];
let assertions = 0;

function record(message) {
  failures.push(message);
}

function expectEqual(actual, expected, label) {
  assertions += 1;
  if (actual !== expected) {
    record(`${label}: expected ${JSON.stringify(expected)}, got ${JSON.stringify(actual)}`);
  }
}

function expectCanonical(value, expected, label) {
  assertions += 1;
  let actual;
  try {
    actual = canonicalJson(value);
  } catch (error) {
    record(`${label}: unexpected ${error.name}: ${error.message}`);
    return;
  }
  if (actual !== expected) {
    record(
      `${label}: canonical mismatch\n      expected ${JSON.stringify(expected)}\n      actual   ${JSON.stringify(actual)}`
    );
  }
}

function expectThrowsFrom(fn, label) {
  assertions += 1;
  try {
    fn();
  } catch (error) {
    if (!(error instanceof CanonicalFormError)) {
      record(`${label}: expected CanonicalFormError, got ${error.name}: ${error.message}`);
    }
    return;
  }
  record(`${label}: expected CanonicalFormError, but no error was raised`);
}

function expectThrows(value, label) {
  expectThrowsFrom(() => canonicalize(value), label);
}

const utf8 = (text) => new TextEncoder().encode(text);

function bytesEqual(left, right) {
  return left.length === right.length && left.every((byte, index) => byte === right[index]);
}

function expectBytes(actual, expected, label) {
  assertions += 1;
  if (!bytesEqual(actual, expected)) {
    record(`${label}: byte mismatch (got ${Array.from(actual).join(",")})`);
  }
}

function expectBytesDiffer(left, right, label) {
  assertions += 1;
  if (bytesEqual(left, right)) {
    record(`${label}: expected different bytes`);
  }
}

// ---------------------------------------------------------------------------
// Phase 1 — pinned conformance vectors (no Python required).
// ---------------------------------------------------------------------------

expectEqual(CANONICAL_FORM_VERSION, "aleph-canonical/0.2.0", "profile version");
expectEqual(MAX_CANONICAL_INT, 2 ** 53 - 1, "I-JSON integer bound");

const NUMBER_VECTORS = [
  [0.0, "0"],
  [-0.0, "0"],
  [1.0, "1"],
  [-1.0, "-1"],
  [100.0, "100"],
  [0.5, "0.5"],
  [-2.5, "-2.5"],
  [123.456, "123.456"],
  [0.30000000000000004, "0.30000000000000004"],
  [1e15, "1000000000000000"],
  [1e16, "10000000000000000"],
  [1e20, "100000000000000000000"],
  [1e21, "1e+21"],
  [1e22, "1e+22"],
  [1e-5, "0.00001"],
  [1e-6, "0.000001"],
  [1.2e-6, "0.0000012"],
  [1.2e-7, "1.2e-7"],
  [1e-7, "1e-7"],
  [-1e-7, "-1e-7"],
  [5e-324, "5e-324"],
  [1.7976931348623157e308, "1.7976931348623157e+308"],
  [2.2250738585072014e-308, "2.2250738585072014e-308"],
  [9007199254740991.0, "9007199254740991"],
  [123456789012345678.0, "123456789012345680"],
];
NUMBER_VECTORS.forEach(([value, expected], index) => {
  expectCanonical(value, expected, `number vector ${index} (${String(value)})`);
});

const RFC_NUMBER_VECTORS = [
  [5e-324, "5e-324"],
  [-5e-324, "-5e-324"],
  [1.7976931348623157e308, "1.7976931348623157e+308"],
  [-1.7976931348623157e308, "-1.7976931348623157e+308"],
  [9007199254740992.0, "9007199254740992"],
  [295147905179352830000.0, "295147905179352830000"],
  [9.999999999999997e22, "9.999999999999997e+22"],
  [1e23, "1e+23"],
  [1.0000000000000001e23, "1.0000000000000001e+23"],
  [999999999999999700000.0, "999999999999999700000"],
  [999999999999999900000.0, "999999999999999900000"],
  [9.999999999999997e-7, "9.999999999999997e-7"],
  [333333333.3333332, "333333333.3333332"],
  [333333333.33333325, "333333333.33333325"],
  [333333333.3333333, "333333333.3333333"],
  [333333333.3333334, "333333333.3333334"],
  [333333333.33333343, "333333333.33333343"],
  [-0.0000033333333333333333, "-0.0000033333333333333333"],
  [1424953923781206.2, "1424953923781206.2"],
];
RFC_NUMBER_VECTORS.forEach(([value, expected], index) => {
  expectCanonical(value, expected, `RFC 8785 Appendix B vector ${index} (${String(value)})`);
});

const STRING_VECTORS = [
  ["", '""'],
  ["plain", '"plain"'],
  ['a"b', '"a\\"b"'],
  ["a\\b", '"a\\\\b"'],
  ["/", '"/"'],
  ["\u0000", '"\\u0000"'],
  ["\u001f", '"\\u001f"'],
  ["\b\t\n\f\r", '"\\b\\t\\n\\f\\r"'],
  ["\u007f", '"\u007f"'],
  ["\u2028\u2029", '"\u2028\u2029"'],
  ["\u00e9", '"\u00e9"'],
  ["e\u0301", '"\u00e9"'],
  ["A\u030A", '"\u00c5"'],
  ["\ufb01", '"\ufb01"'],
  ["\u{1F600}", '"\u{1F600}"'],
  ["\u{10000}", '"\u{10000}"'],
  ["\ufffd", '"\ufffd"'],
  ["Z\u00fcrich", '"Z\u00fcrich"'],
  ["\u65e5\u672c\u8a9e", '"\u65e5\u672c\u8a9e"'],
];
STRING_VECTORS.forEach(([value, expected], index) => {
  expectCanonical(value, expected, `string vector ${index} (${JSON.stringify(value)})`);
});

const KEY_ORDER_VECTORS = [
  [{ b: 1, a: 2 }, '{"a":2,"b":1}'],
  [{ B: 1, a: 2, A: 3, b: 4 }, '{"A":3,"B":1,"a":2,"b":4}'],
  [{ Z: 1, a: 2, A: 3 }, '{"A":3,"Z":1,"a":2}'],
  [{ "\ue000": 1, "\u{10000}": 2 }, '{"\u{10000}":2,"\ue000":1}'],
  [{ 10: 1, 9: 2 }, '{"10":1,"9":2}'],
];
KEY_ORDER_VECTORS.forEach(([value, expected], index) => {
  expectCanonical(value, expected, `key-order vector ${index}`);
});

const FORWARD = { "\ue000": 1, "\u{10000}": 2 };
const BACKWARD = { "\u{10000}": 2, "\ue000": 1 };
expectBytes(canonicalBytes(FORWARD), canonicalBytes(BACKWARD), "key-order insertion independence");

const STRUCTURE_VECTORS = [
  [[1.0, -0.0, 2], "[1,0,2]"],
  [{ w: 1.0, r: [0.5, 1.0] }, '{"r":[0.5,1],"w":1}'],
  [{ z: null, a: { y: [true, false] } }, '{"a":{"y":[true,false]},"z":null}'],
  [true, "true"],
  [false, "false"],
  [null, "null"],
];
STRUCTURE_VECTORS.forEach(([value, expected], index) => {
  expectCanonical(value, expected, `structure vector ${index}`);
});

expectCanonical({ ["__proto__"]: 1, a: 2 }, '{"__proto__":1,"a":2}', "proto-like key stays a key");
const nullPrototype = Object.create(null);
nullPrototype.a = 1;
expectCanonical(nullPrototype, '{"a":1}', "null-prototype object");

expectBytes(canonicalBytes("\u00e9"), utf8('"\u00e9"'), "NFC composed bytes");
expectBytes(canonicalBytes("e\u0301"), utf8('"\u00e9"'), "NFC decomposed bytes");
expectBytes(canonicalBytes("\u{1F600}"), utf8('"\u{1F600}"'), "astral literal utf8");
expectCanonical("\ufb01", '"\ufb01"', "NFC is not NFKC (fi ligature)");
expectBytesDiffer(canonicalBytes("\u00a0"), canonicalBytes(" "), "NFC keeps no-break space distinct");

const BS = "\\";
const RFC_WORKED_INPUT = {
  numbers: [333333333.33333329, 1e30, 4.5, 2e-3, 1e-27],
  string: "€$" + "\u000f" + "\n" + "A'B" + '"' + BS + BS + '"' + "/",
  literals: [null, true, false],
};
const RFC_WORKED_EXPECTED =
  '{"literals":[null,true,false],"numbers":[333333333.3333333,1e+30,4.5,0.002,1e-27],"string":"' +
  "€$" +
  BS +
  "u000f" +
  BS +
  "n" +
  "A'B" +
  BS +
  '"' +
  BS +
  BS +
  BS +
  BS +
  BS +
  '"' +
  "/" +
  '"' +
  "}";
expectCanonical(RFC_WORKED_INPUT, RFC_WORKED_EXPECTED, "RFC 8785 section 3.2.2/3.2.3 worked example");
expectEqual(
  digest(RFC_WORKED_INPUT),
  digestBytes(utf8(RFC_WORKED_EXPECTED)),
  "RFC 8785 worked example digest"
);

const PINNED_SIMPLE_OBJECT = "sha256:d3626ac30a87e6f7a6428233b3c68299976865fa5508e4267c5415c76af7a772";
expectEqual(digest({ a: 2, b: 1 }), PINNED_SIMPLE_OBJECT, "pinned simple-object digest");
expectEqual(digest({ b: 1, a: 2 }), PINNED_SIMPLE_OBJECT, "pinned simple-object digest (reordered)");
expectEqual(digestBytes(utf8('{"a":2,"b":1}')), PINNED_SIMPLE_OBJECT, "pinned simple-object digest (bytes)");

const PINNED_NFC = "sha256:f2886017e9c7abacf804b54d64787dce2b611c9544ba21f3affdd126a6e50086";
expectEqual(digest("\u00e9"), PINNED_NFC, "pinned NFC digest (composed)");
expectEqual(digest("e\u0301"), PINNED_NFC, "pinned NFC digest (decomposed)");

const PINNED_RECEIPT =
  "sha256:290f1f6ad3080e97b99f19f94e1598017c6eee0ae839fefc0021c6fb395621a9";
expectEqual(
  digest({ schemaVersion: "aleph-canonical/0.2.0", value: { ratio: 0.1, weight: 1 } }),
  PINNED_RECEIPT,
  "pinned receipt-shaped digest"
);

expectCanonical(2 ** 53 - 1, "9007199254740991", "largest exact integer");
// 2**53 as a JavaScript number is the IEEE-754 double 9007199254740992; it
// renders exactly as the Python engine renders that double. The I-JSON integer
// bound is a Python-write-side constraint; see the module docstring.
expectCanonical(2 ** 53, "9007199254740992", "2**53 as a double");

expectThrows(Number.NaN, "NaN");
expectThrows(Number.POSITIVE_INFINITY, "positive infinity");
expectThrows(Number.NEGATIVE_INFINITY, "negative infinity");
expectThrows("\ud800", "lone high surrogate string");
expectThrows("x\udfff", "lone low surrogate string");
expectThrows({ k: "\ud800" }, "nested lone surrogate");
expectThrows({ "\ud800": 1 }, "lone surrogate key");
expectThrows({ "\u00e9": 1, "e\u0301": 2 }, "NFC key collision");
expectThrows(1n, "bigint");
expectThrows(new Uint8Array([1, 2]), "raw bytes");
expectThrows([1, , 3], "sparse array");
expectThrows([undefined], "undefined element");
expectThrows({ k: undefined }, "undefined property");
expectThrows(new Set([1]), "Set");
expectThrows(new Date(), "Date");
expectThrows(() => {}, "function");
expectThrows(Symbol("s"), "symbol");
expectThrows({ [Symbol("s")]: 1 }, "symbol key");
expectThrowsFrom(() => normalizeText(1), "normalizeText non-string");
expectThrowsFrom(() => digestBytes("not bytes"), "digestBytes non-bytes input");
expectThrowsFrom(() => utf8ByteLength("\ud800"), "utf8ByteLength lone surrogate");

expectEqual(bareDigest({ a: 2, b: 1 }), PINNED_SIMPLE_OBJECT.slice("sha256:".length), "bareDigest strips prefix");
expectEqual(isDigest(PINNED_SIMPLE_OBJECT), true, "isDigest accepts a pinned digest");
expectEqual(isDigest("sha256:" + "0".repeat(64)), true, "isDigest accepts lowercase hex");
expectEqual(isDigest("sha256:" + "0".repeat(63)), false, "isDigest rejects short hex");
expectEqual(isDigest("SHA256:" + "0".repeat(64)), false, "isDigest rejects uppercase prefix");
expectEqual(normalizeText("e\u0301"), "\u00e9", "normalizeText returns NFC");
expectEqual(utf8ByteLength("\u00e9"), 2, "utf8ByteLength acute");
expectEqual(utf8ByteLength("\u{1F600}"), 4, "utf8ByteLength emoji");
expectCanonical(canonicalize({ b: 1, a: 2 }), '{"a":2,"b":1}', "canonicalize output re-renders canonically");

// ---------------------------------------------------------------------------
// Phase 2 — live differential against the Python engine.
// ---------------------------------------------------------------------------

const PYTHON_DRIVER = String.raw`
import json, math, random, struct, sys
from itertools import permutations

sys.path.insert(0, ".")

from search.engine.canonical import (
    CANONICAL_FORM_VERSION,
    CanonicalFormError,
    canonical_json,
    digest,
)

rows = []


def add(value, kind):
    row = {"kind": kind}
    try:
        row["input"] = json.dumps(value, ensure_ascii=True)
    except (TypeError, ValueError):
        return
    try:
        row["ok"] = True
        row["canonical"] = canonical_json(value)
        row["digest"] = digest(value)
    except CanonicalFormError as error:
        row["ok"] = False
        row["error"] = str(error)
    rows.append(row)


SPECIALS = [
    0.0, -0.0, 1.0, -1.0, 100.0, 0.5, -2.5, 123.456, 0.30000000000000004,
    1e15, 1e16, 1e20, 1e21, 1e22, 1e-5, 1e-6, 1e-7, 1e-8,
    5e-324, 1.7976931348623157e308, 2.2250738585072014e-308,
    9007199254740991.0, 123456789012345678.0, 295147905179352830000.0,
    9.999999999999997e22, 1e23, 333333333.33333329, 2e-3, 1e-27, 1e30,
]
for value in SPECIALS:
    add(value, "number")

rng = random.Random(0xC0FFEE)
generated = 0
while generated < 2000:
    bits = rng.getrandbits(64)
    value = struct.unpack("<d", struct.pack("<Q", bits))[0]
    if math.isfinite(value):
        add(value, "number")
        generated += 1

FIXED_STRINGS = [
    "", "plain", 'a"b', "a\\b", "/", "\u0000", "\u001f", "\b\t\n\f\r",
    "\u007f", "\u2028\u2029", "\u00e9", "e\u0301", "A\u030A", "\u212b",
    "\ufb01", "\U0001F600", "\U00010000", "\ufffd", "Z\u00fcrich",
    "\u65e5\u672c\u8a9e", "\u00a0", " ",
]
for text in FIXED_STRINGS:
    add(text, "string")

add([chr(cp) for cp in range(0x0000, 0x10000) if not 0xD800 <= cp <= 0xDFFF], "string-sweep")

rng_strings = random.Random(0x5EED)
add([chr(rng_strings.randint(0x10000, 0x10FFFF)) for _ in range(256)], "string-astral")
combining = []
for _ in range(64):
    base = chr(rng_strings.choice(range(0x0041, 0x005B)) | rng_strings.choice((0x00, 0x20)))
    combining.append(base + chr(rng_strings.randint(0x0300, 0x036F)))
add(combining, "string-combining")

KEY_POOL = [
    "", "a", "A", "z", "Z", "10", "9", "1", "0", "\u007f", "\u00e9", "e\u0301",
    "\u65e5", "\ue000", "\u2028", 'q"k', "b\\s", "\U00010000", "\U0001F600", "A\u030A",
]
for pair in permutations(KEY_POOL, 2):
    add({key: index for index, key in enumerate(pair)}, "key-order")
for triple in (("z", "\ue000", "\U00010000"), ("e\u0301", "z", "9"), ("A\u030A", "b", "10")):
    add({key: index for index, key in enumerate(triple)}, "key-order")

add({"weight": 1.0, "ratio": 0.1, "items": [1, -0.0, 2], "nested": {"z": None, "a": [True, False]}}, "structure")
add({"schemaVersion": "aleph-canonical/0.2.0", "value": {"ratio": 0.1, "weight": 1}, "ids": ["sha256:" + "0" * 64]}, "structure")
add({"": 1, "\u00a0": 2, " ": 3}, "structure")
add({"__proto__": 1, "a": 2}, "structure")
add({"runId": "aleph-mlx-canary-001", "candidates": [{"id": "sha256:" + "f" * 64, "metrics": {"fit": 1.0, "stability": 0.5}}], "omitted": []}, "structure")

add("\ud800", "error")
add("x\udfff", "error")
add({"k": "\ud800"}, "error")
add({"\ud800": 1}, "error")
add({"\u00e9": 1, "e\u0301": 2}, "error")

print(json.dumps({"version": CANONICAL_FORM_VERSION, "rows": rows}, ensure_ascii=True))
`;

function runPythonDifferential() {
  const result = spawnSync("python3", ["-c", PYTHON_DRIVER], {
    cwd: REPO_ROOT,
    encoding: "utf8",
    maxBuffer: 256 * 1024 * 1024,
  });
  if (result.error) {
    if (result.error.code === "ENOENT") {
      return { skipped: true, cases: 0 };
    }
    record(`differential: cannot spawn python3: ${result.error.message}`);
    return { skipped: false, cases: 0 };
  }
  if (result.status !== 0) {
    const stderr = (result.stderr || "").trim().split("\n").slice(0, 6).join("\n      ");
    record(`differential: python3 exited with status ${result.status}\n      ${stderr}`);
    return { skipped: false, cases: 0 };
  }
  let payload;
  try {
    payload = JSON.parse(result.stdout);
  } catch (error) {
    record(`differential: cannot parse python output: ${error.message}`);
    return { skipped: false, cases: 0 };
  }
  expectEqual(payload.version, CANONICAL_FORM_VERSION, "differential engine version");
  assertions += 1;
  if (!Array.isArray(payload.rows) || payload.rows.length < 2000) {
    record(`differential: unexpected row count ${payload.rows?.length}`);
    return { skipped: false, cases: payload.rows?.length ?? 0 };
  }
  const brief = (text) => (text.length > 140 ? `${text.slice(0, 137)}...` : text);
  let cases = 0;
  for (const [index, row] of payload.rows.entries()) {
    cases += 1;
    const label = `${row.kind}#${index}`;
    let value;
    try {
      value = JSON.parse(row.input);
    } catch (error) {
      record(`${label}: cannot re-parse transported input: ${error.message}`);
      continue;
    }
    let jsOk = true;
    let jsCanonical = null;
    let jsDigest = null;
    let jsError = null;
    try {
      jsCanonical = canonicalJson(value);
      jsDigest = digest(value);
    } catch (error) {
      jsOk = false;
      jsError = error;
    }
    if (row.ok !== jsOk) {
      const pythonSide = row.ok ? "ok" : `failed (${row.error})`;
      const jsSide = jsOk ? "ok" : `failed (${jsError.name}: ${jsError.message})`;
      record(`${label}: python ${pythonSide} but JS ${jsSide}; input=${brief(row.input)}`);
      continue;
    }
    if (row.ok) {
      if (jsCanonical !== row.canonical) {
        record(
          `${label}: canonical mismatch; input=${brief(row.input)}\n      python ${JSON.stringify(
            brief(row.canonical)
          )}\n      js     ${JSON.stringify(brief(jsCanonical))}`
        );
      }
      if (jsDigest !== row.digest) {
        record(`${label}: digest mismatch; input=${brief(row.input)}`);
      }
    } else if (!(jsError instanceof CanonicalFormError)) {
      record(`${label}: both sides fail closed, but JS threw ${jsError.name} instead of CanonicalFormError`);
    }
  }
  return { skipped: false, cases };
}

const differential = runPythonDifferential();

if (failures.length > 0) {
  console.error("check-canonical-parity: FAILED");
  for (const failure of failures.slice(0, 40)) console.error(`- ${failure}`);
  if (failures.length > 40) console.error(`- ... and ${failures.length - 40} more`);
  process.exit(1);
}

const differentialNote = differential.skipped
  ? "python differential skipped: python3 not found on PATH"
  : `${differential.cases} differential cases vs search/engine/canonical.py`;
console.log(`check-canonical-parity: ok (${assertions} pinned assertions; ${differentialNote})`);
