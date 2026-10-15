"""Differential check: the JCS number rendering against a real ES engine.

The canonical form follows RFC 8785, whose number profile is ECMAScript
``Number::toString``; ``JSON.stringify`` is that algorithm's reference
implementation. When a ``node`` binary is on ``PATH`` this test renders 2000
fixed-seed doubles plus the boundary vectors through both implementations and
requires byte equality; without node it skips, so the stdlib-only suite still
runs everywhere (CI runs it under npm test, where node is present).
"""

from __future__ import annotations

import math
import random
import shutil
import struct
import subprocess
import unittest

from search.engine.canonical import canonical_json

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


if __name__ == "__main__":
    unittest.main()
