# Bounded Coordinate v0

Bounded Coordinate v0 is Aleph's first executable finite experiment for separating **description complexity** from **discovery complexity**.

It is a synthetic existence example and a systems smoke test. It is not LLM evidence, a claim about natural-language readability, an estimate of Kolmogorov complexity, or evidence that one search policy is generally superior.

Tracked by [issue #102](https://github.com/p-to-q/aleph/issues/102). The governing checked-in research contract is `docs/plans/iclr-readable-coordinate-program.md`.

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
3. a paired seeded SHA-256 pseudorandom hash-priority baseline without replacement, with seed `1729`.

The pseudorandom baseline is operationally defined: hash the policy label, registered seed, public search-space hash, and coordinate; order by the digest; take the first 16 coordinates. Both landscapes therefore receive the same sequence. This is one reproducible seeded realization, not physical randomness, proof of a uniform sampling law, or an inferential estimate over seeds.

The width-one beam and pseudorandom baseline each use 16 evaluator calls. Work fields are intentionally separate:

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

The original eleven-test portability matrix and golden receipt/archive passed under CPython 3.10.9, 3.11.9, 3.12.3, 3.13.2, and 3.14.7. The current fourteen-test suite adds normalized-path containment, generated-frontier binding, and axiom-inventory coverage; it uses only the standard library.

The checked-in result is:

| Policy | Compositional | Opaque | Calls | Adaptive rounds |
| --- | ---: | ---: | ---: | ---: |
| Exhaustive certificate | hit at ordinal 113 | hit at ordinal 113 | 341 | 1 |
| Width-one beam | hit at ordinal 16 | no hit | 16 | 4 |
| Seeded SHA-256 pseudorandom | no hit | no hit | 16 | 1 |

Receipt identities:

- manifest content SHA-256: `05aef719a7651c4e9a0f724fd3cced02912d7cb66e316dbf443fc68a276c51fa`
- receipt canonical-content SHA-256: `91dfc3951a24f627b86f06709bd00e075a7a6c065022bcedf142eff0e6151eb4`
- receipt file-byte SHA-256: `ae4bacf3739d3015cf0c71ccbe7c9da249d29a7ac0514c79173ec23d3c89bc7b`
- candidate-archive canonical-content SHA-256: `fd142e89ec3aacfe0c4870718a42cd782fa6da88272387421bf557afcd4f84c3`
- candidate-archive file-byte SHA-256: `273b5a53eab00a484bf77c71c78fa6eb76f92302492cb0633b6cfeb702b29ebe`

The 682 complete candidate observations live in canonical JSONL rather than being embedded in the summary receipt. `verify.py` checks both parsed content and the actual archive bytes against receipt metadata, then performs a second deterministic Python reconstruction. It independently rebuilds decoding, measurements, hashing, candidate identities, representative frontier, policies, and claims; it shares only the strict manifest parser and Python runtime. It is not an external replication or formal proof.

Verification work is accounted separately from search work. The checked verifier performs two complete domain passes per landscape plus independent beam and pseudorandom trace reconstruction: 1,364 full-domain candidate reconstructions, 64 policy reconstructions, and 1,428 total. Wall-clock timing remains excluded from byte-stable artifacts.

The CLI uses capped geometric accumulation and fails before enumeration when a landscape exceeds 100,000 candidates unless an explicit larger `--max-candidate-count` is provided. The regression suite includes a one-billion-token bound, so even candidate-count calculation cannot become an accidental exponential or huge-integer workload.

## Lean certificate

`GeneratedProblem.lean` is generated from `problem.json`; the Python tests and `generate_lean --check` fail if it drifts. `Basic.lean` proves:

- the declared witness reconstructs the target in both decoders;
- every coordinate of length at most three fails in both decoders;
- through the declared length-four bound, the exact witness is unique in both decoders;
- every published representative-frontier observation is an unchanged member of the corresponding bounded enumeration.

The public theorems quantify over all short token lists. A separate coverage lemma proves that every such list appears in the finite enumeration before the checked finite lemma is applied. `GeneratedFrontier.lean` is generated from the checked receipt and complete archive and records their file digests plus a frontier-content digest, so the frontier theorem is bound to the published artifacts rather than a parallel handwritten fixture.

The pinned toolchain is Lean `4.34.1`. A verified local build used the official `lean-4.34.1-darwin_aarch64.tar.zst` asset with SHA-256 `65f22a4f047738ec742667b3247e836a86ebf06eabc12655c3dee00637e37866`:

```bash
python3 -m search.bounded.verify_lean --lake /path/to/lean-4.34.1/bin/lake
```

The checked receipt records project hash `d52a86ccd190014ddc05c1dc00c9b2db53fceb90fa071905063551f71ff7c4e7`, a successful build, both generated-definition parity checks, and no `sorry`, `admit`, or user-declared `axiom` in project proof sources. It also runs `#print axioms` over all 13 public theorems and rejects missing theorems or any dependency set other than the pinned expected Lean kernel axioms (`propext` and, where used, `Quot.sound`); three direct computational theorems have no axiom dependencies.

Lean verifies the generated finite formal model and membership of the receipt-derived published frontier observations. It does not verify the Python frontier-selection algorithm, the independent Python verifier, or correspondence to an LLM runtime.

## Claim admitted by v0

This construction establishes that equal bounded description optima do not imply equal discovery behavior under a fixed adaptive policy and matched evaluation budget. Here the feedback landscape alone changes whether width-one beam search finds the shared witness.

It does not establish a distributional effect. A paper-facing experiment must extend this into a registered family over witness permutations, tie-break orders, beam widths, budgets, and landscape generators, then report success probability and queries-to-hit without selecting cases after seeing outcomes.

## Artifact map

- `problem.json`: strict, immutable problem manifest;
- `model.py`: typed parser, decoder, measurement, bounded enumeration, and representative frontier;
- `run.py`: public-space policy interface, policy execution, accounting, and receipt writer;
- `verify.py`: independent Python reconstruction and mutation-sensitive verification;
- `generate_lean.py`: deterministic manifest/receipt/archive-to-Lean definition generator;
- `verify_lean.py`: pinned-build, theorem-inventory, and exact axiom-dependency receipt generator;
- `lean/`: generated problem/frontier definitions plus handwritten coverage, minimality, uniqueness, and observation-membership proofs;
- `results/`: byte-stable summary receipt, complete canonical-JSONL candidate archive, Python verification, and Lean verification receipt;
- `../tests/test_bounded_coordinate.py`: boundary, mutation, determinism, portability, parity, and artifact-drift tests.
