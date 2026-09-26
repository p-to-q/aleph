# Bounded Coordinate v0

Bounded Coordinate v0 is Aleph's first executable finite experiment for separating **description complexity** from **discovery complexity**.

It is a synthetic existence example and a systems smoke test. It is not LLM evidence, a claim about natural-language readability, an estimate of Kolmogorov complexity, or evidence that one search policy is generally superior.

Tracked by [issue #102](https://github.com/p-to-q/aleph/issues/102). The governing research contracts remain `docs/plans/iclr-readable-coordinate-program.md` and `docs/plans/model-relative-coordinate-landmarks.md`.

## Frozen object

`problem.json` defines a four-token coordinate alphabet, a maximum coordinate length of four, one eight-bit target, and two decoder landscapes:

- `compositional`: each token contributes a visible two-bit chunk, so partial coordinates expose useful fit gradients;
- `opaque`: every non-witness coordinate returns the same fallback, so the evaluator is flat until the exact coordinate is queried.

Both landscapes have the same unique exact witness within the bounded domain:

```text
[A, B, C, D]
```

Its coordinate length is four in both landscapes. Only decoder-to-score feedback changes.

The search policy receives a `PublicSearchSpace` containing the alphabet and maximum length plus an evaluator callback. It does not receive the decoder specification or opaque witness. “Opaque” therefore means **flat evaluator feedback**, not a secret or cryptographically hidden problem.

## What runs

The runner performs three policies per landscape:

1. full length-then-lexicographic enumeration, reused as the finite certificate archive;
2. width-one fit-guided beam search;
3. a paired SHA-256-priority control with seed `1729`.

The priority control is a deterministic ordering, not statistical randomness. Its priority input contains only the public search-space hash, seed, and coordinate, so both landscapes receive the same coordinate sequence.

The width-one beam and priority control each use 16 evaluator calls. Work fields are intentionally separate:

- `candidateEvaluatorCalls`: actual calls made for that named policy;
- `logicalAdaptiveRounds`: policy dependency depth under unbounded evaluation parallelism;
- `firstHitEvaluationOrdinal`: position in the deterministic evaluator-call sequence, not wall-clock time;
- `certificateArchiveEvaluatorCalls`: work required to materialize all 341 candidates in one landscape.

Coordinate-token budgets in `budgetValueCurve` are never reused as evaluation budgets.

## Reproduce

Run from the repository root with Python 3.10 or later:

```bash
python3 -m search.bounded.generate_lean --check
python3 -m search.bounded.run
python3 -m search.bounded.verify
python3 -m unittest search/tests/test_bounded_coordinate.py
```

The same ten-test suite and golden receipt passed under CPython 3.10.9, 3.11.9, 3.12.3, 3.13.2, and 3.14.7. The code path uses only the standard library.

The checked-in result is:

| Policy | Compositional | Opaque | Calls | Adaptive rounds |
| --- | ---: | ---: | ---: | ---: |
| Exhaustive certificate | hit at ordinal 113 | hit at ordinal 113 | 341 | 1 |
| Width-one beam | hit at ordinal 16 | no hit | 16 | 4 |
| SHA-256 priority | no hit | no hit | 16 | 1 |

Receipt identities:

- manifest content SHA-256: `05aef719a7651c4e9a0f724fd3cced02912d7cb66e316dbf443fc68a276c51fa`
- receipt canonical-content SHA-256: `695d50f92f33607603d90400e9fcf9bf242269d781f3e86735653981d5a1e22f`
- receipt file-byte SHA-256: `ebbab77602d67070bcbaa58ce1897b6d6dc815b6edd00461daffeb320af7c058`

`verify.py` is a second deterministic Python reconstruction. It independently rebuilds decoding, measurements, candidate identities, representative frontier, policies, and claims, but shares the strict manifest parser and Python runtime. It is not an external replication or formal proof.

The CLI fails before enumeration when a landscape exceeds 100,000 candidates unless an explicit larger `--max-candidate-count` is provided. This prevents a seemingly valid manifest from causing accidental exponential allocation.

## Lean certificate

`GeneratedProblem.lean` is generated from `problem.json`; the Python tests and `generate_lean --check` fail if it drifts. `Basic.lean` proves:

- the declared witness reconstructs the target in both decoders;
- every coordinate of length at most three fails in both decoders;
- through the declared length-four bound, the exact witness is unique in both decoders.

The public theorems quantify over all short token lists. A separate coverage lemma proves that every such list appears in the finite enumeration before the checked finite lemma is applied.

The pinned toolchain is Lean `4.34.1`. A verified local build used the official `lean-4.34.1-darwin_aarch64.tar.zst` asset with SHA-256 `65f22a4f047738ec742667b3247e836a86ebf06eabc12655c3dee00637e37866`:

```bash
python3 -m search.bounded.verify_lean --lake /path/to/lean-4.34.1/bin/lake
```

The checked receipt records project hash `81af92126a43fff795ecbf828c034807f08d9a65fbeb3922fac0cad6f6679f83`, a successful build, generated-definition parity, and no `sorry`, `admit`, or `axiom` in project proof sources.

Lean verifies the generated finite formal model. It does not verify the Python receipt, representative-frontier algorithm, or correspondence to an LLM runtime.

## Claim admitted by v0

This construction establishes that equal bounded description optima do not imply equal discovery behavior under a fixed adaptive policy and matched evaluation budget. Here the feedback landscape alone changes whether width-one beam search finds the shared witness.

It does not establish a distributional effect. A paper-facing experiment must extend this into a registered family over witness permutations, tie-break orders, beam widths, budgets, and landscape generators, then report success probability and queries-to-hit without selecting cases after seeing outcomes.

## Artifact map

- `problem.json`: strict, immutable problem manifest;
- `model.py`: typed parser, decoder, measurement, bounded enumeration, and representative frontier;
- `run.py`: public-space policy interface, policy execution, accounting, and receipt writer;
- `verify.py`: independent Python reconstruction and mutation-sensitive verification;
- `generate_lean.py`: deterministic JSON-to-Lean definition generator;
- `verify_lean.py`: pinned-build and proof-source receipt generator;
- `lean/`: generated definition plus handwritten coverage, minimality, and uniqueness proofs;
- `results/`: byte-stable run, Python verification, and Lean verification receipts;
- `../tests/test_bounded_coordinate.py`: boundary, mutation, determinism, portability, parity, and artifact-drift tests.
