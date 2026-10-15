"""Differential checks: the canonical form against a real ES engine.

The canonical form follows RFC 8785, whose primitives are ECMAScript
``JSON.stringify`` behavior; ``JSON.stringify`` is that algorithm's reference
implementation, and ``String.prototype.normalize('NFC')`` is the reference for
the NFC extension. When a ``node`` binary is on ``PATH`` these tests render
fixed-seed doubles, a full BMP string sweep, and key-order cases through both
implementations and require byte equality; without node they skip, so the
stdlib-only suite still runs everywhere (CI runs them under npm test, where
node is present). The fixed conformance vectors in
``test_canonical_vectors.py`` keep the profile pinned where node is absent.
"""

from __future__ import annotations

import json
import math
import random
import shutil
import struct
import subprocess
import unittest
from itertools import permutations

from search.engine.canonical import canonical_json, canonicalize

_NODE_SCRIPT = (
    "const rl=require('readline').createInterface({input:process.stdin});"
    "rl.on('line',(l)=>{process.stdout.write(JSON.stringify(Number(l))+'\\n')});"
)


def _vectors(count: int = 2000) -> list[float]:
    vectors = [
        1.0,
        -1.0,
        100.0,
        0.5,
        -2.5,
        123.456,
        0.30000000000000004,
        1e15,
        1e16,
        1e20,
        1e21,
        1e22,
        1e-5,
        1e-6,
        1e-7,
        1e-8,
        -0.0,
        5e-324,
        1.7976931348623157e308,
        2.2250738585072014e-308,
    ]
    rng = random.Random(0xC0FFEE)
    while len(vectors) < count:
        bits = rng.getrandbits(64)
        value = struct.unpack("<d", struct.pack("<Q", bits))[0]
        if math.isfinite(value):
            vectors.append(value)
    return vectors


@unittest.skipUnless(shutil.which("node"), "node binary is required for the JCS differential")
class TestJcsNumberDifferential(unittest.TestCase):
    def test_rendering_matches_json_stringify(self) -> None:
        vectors = _vectors()
        completed = subprocess.run(
            ["node", "-e", _NODE_SCRIPT],
            input="".join(repr(value) + "\n" for value in vectors),
            capture_output=True,
            text=True,
            check=True,
        )
        expected = completed.stdout.splitlines()
        self.assertEqual(len(expected), len(vectors))
        mismatches = [
            (repr(value), canonical_json(value), reference)
            for value, reference in zip(vectors, expected)
            if canonical_json(value) != reference
        ]
        self.assertEqual(mismatches, [])


_STRING_SCRIPT = (
    "const fs=require('fs');"
    "const xs=JSON.parse(fs.readFileSync(0,'utf8'));"
    "process.stdout.write(JSON.stringify(xs.map((s)=>JSON.stringify(s.normalize('NFC')))));"
)


def _string_vectors() -> list[str]:
    vectors = [chr(cp) for cp in range(0x0000, 0x10000) if not 0xD800 <= cp <= 0xDFFF]
    rng = random.Random(0x5EED)
    for _ in range(512):
        vectors.append(chr(rng.randint(0x10000, 0x10FFFF)))
    for _ in range(128):
        base = chr(rng.choice(range(0x0041, 0x005B)) | rng.choice((0x00, 0x20)))
        vectors.append(base + chr(rng.randint(0x0300, 0x036F)))
    vectors += ["\u00e9", "e\u0301", "A\u030A", "\u212b", 'q"k', "b\\s"]
    return vectors


@unittest.skipUnless(shutil.which("node"), "node binary is required for the JCS differential")
class TestJcsStringDifferential(unittest.TestCase):
    def test_rendering_matches_json_stringify(self) -> None:
        vectors = _string_vectors()
        completed = subprocess.run(
            ["node", "-e", _STRING_SCRIPT],
            input=json.dumps(vectors, ensure_ascii=True),
            capture_output=True,
            text=True,
            check=True,
        )
        expected = json.loads(completed.stdout)
        self.assertEqual(len(expected), len(vectors))
        mismatches = [
            (repr(value), canonical_json(value), reference)
            for value, reference in zip(vectors, expected)
            if canonical_json(value) != reference
        ]
        self.assertEqual(mismatches, [])


_KEY_POOL = (
    "",
    "a",
    "A",
    "z",
    "Z",
    "aa",
    "a0",
    "A0",
    "10",
    "9",
    "1",
    "0",
    "\u007f",
    "\u00e0",
    "\u00df",
    "\u1e9e",
    "\u00e9",
    "\u65e5",
    "\ue000",
    "\ufffd",
    "\u2028",
    'q"k',
    "b\\s",
    "\U00010000",
    "\U0001F600",
)


def _key_order_cases() -> list[list[str]]:
    cases = [list(pair) for pair in permutations(_KEY_POOL, 2)]
    cases += [
        ["e\u0301", "z"],
        ["A\u030A", "b"],
        ["\u212b", "\u00e9"],
        ["\u2126", "x"],
        ["z", "\ue000", "\U00010000"],
    ]
    return cases


_KEY_SCRIPT = (
    "const fs=require('fs');"
    "const xs=JSON.parse(fs.readFileSync(0,'utf8'));"
    "process.stdout.write(JSON.stringify(xs.map((p)=>p.map((k)=>k.normalize('NFC')).sort())));"
)


@unittest.skipUnless(shutil.which("node"), "node binary is required for the JCS differential")
class TestJcsKeyOrderDifferential(unittest.TestCase):
    def test_key_order_matches_es_sort(self) -> None:
        cases = _key_order_cases()
        completed = subprocess.run(
            ["node", "-e", _KEY_SCRIPT],
            input=json.dumps(cases, ensure_ascii=True),
            capture_output=True,
            text=True,
            check=True,
        )
        expected = json.loads(completed.stdout)
        self.assertEqual(len(expected), len(cases))
        mismatches = []
        for case, reference in zip(cases, expected):
            ours = list(canonicalize(dict.fromkeys(case)))
            if ours != reference:
                mismatches.append((case, ours, reference))
        self.assertEqual(mismatches, [])


if __name__ == "__main__":
    unittest.main()
