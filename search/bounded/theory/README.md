# Finite Theory v0

Finite Theory v0 is Aleph's exact, executable bridge between the model-relative research claims in `docs/plans/model-relative-coordinate-landmarks.md` and later open-ended search experiments. It proves and reconstructs only statements about explicit finite coordinate systems. It does not estimate Kolmogorov complexity, certify prompt readability, verify an LLM runtime, or claim that a finite archive has solved an open search problem.

Tracked by [issue #105](https://github.com/p-to-q/aleph/issues/105). The earlier Bounded Coordinate v0 experiment from #103 is an immutable bootstrap baseline: every one of its 21 files is pinned by byte digest and remains unchanged.

## Objects and conventions

- A coordinate is immutable and has a stable ID, a lossless rendering, complete target-indexed residuals, and a complete objective vector.
- Charged cost is the full length of a declared prefix code: role tag, fixed-width payload-length field, and payload bits. Display text, token count, and array position are not costs.
- Python `None` and Lean `none` mean positive infinity, used when a finite feasible set is empty.
- `H(r)` is the least residual among coordinates with charged cost at most `r`.
- `L(s)` is the least charged cost among coordinates with residual at most `s`.
- Pareto representatives retain the first source record for each nondominated complete objective vector; they are not synthesized summaries.
- A compiler is one coordinate-only mapping reused across every declared target. Its cost overhead and targetwise residual slack are explicit additive obligations.

The fixture contains two targets, a finite length-delimited source code, a destination code with typed role tags, nested archives including empty and singleton cases, duplicate objective vectors, all outcomes for two conjunctive verifier checks, and forward/reverse compilers. It also contains a deliberate order inversion: a one-bit payload can cost more than a two-bit payload once role scaffolding is charged.

## Claim map

`statement-map.json` is the review surface. Each of FT-01 through FT-09 and FC-01 through FC-04 maps one-to-one to:

1. an English claim and explicit assumptions;
2. an independent Python check;
3. one public Lean theorem;
4. a bounded scope statement;
5. an independent review status.

The Python calculator and independent verifier are separate implementations. `verify_theory.py` does not import `finite_theory.py` or `compiler.py`; it strictly parses and reconstructs the receipt, compiler bounds, archive relations, suites, Pareto output, and all 13 checks. The Lean modules certify the encoded generic propositions, not the Python implementation or English intent.

Both implementations reject manifests whose conservative curve, Pareto, archive, suite, and compiler work estimate exceeds one million finite operations; pair evidence is capped separately before any quadratic list can be materialized. Verification outputs are atomically replaced, input/output path collisions are rejected, and a failed Lean invocation replaces any earlier success receipt with `compiled: false`.

## Reproduce

Run from the repository root with Python 3.10 or later:

```bash
PYTHONHASHSEED=1 python3 -m search.bounded.compiler --manifest search/bounded/theory/manifest.json --statement-map search/bounded/theory/statement-map.json --out /tmp/finite-theory-a.json
PYTHONHASHSEED=777 python3 -m search.bounded.compiler --manifest search/bounded/theory/manifest.json --statement-map search/bounded/theory/statement-map.json --out /tmp/finite-theory-b.json
cmp /tmp/finite-theory-a.json /tmp/finite-theory-b.json
python3 -m search.bounded.verify_theory --manifest search/bounded/theory/manifest.json --statement-map search/bounded/theory/statement-map.json --receipt search/bounded/theory/results/receipt.json --out search/bounded/theory/results/verification.json
python3 -m unittest search.tests.test_finite_theory
```

Compile the two new modules explicitly with the pinned Lean 4.34.1 `lake`; do not import them through the protected #103 root module:

```bash
cd search/bounded/lean
/path/to/lean-4.34.1/bin/lake env lean BoundedCoordinate/FiniteTheory.lean
/path/to/lean-4.34.1/bin/lake env lean BoundedCoordinate/Compiler.lean
```

The checked receipts under `results/` bind the manifest, reviewed statement map, protected #103 baseline, exact reconstructed evidence, verifier source, Lean source, toolchain, and axiom audit. Re-running a calculator is not a substitute for the independent reconstruction.

## Trust boundary

- Exact finite enumeration supports these claims; generalization to unbounded descriptions or natural-language prompts does not follow.
- Prefix-freeness and the finite Kraft inequality validate the declared fixture code, not a universal machine.
- Compiler theorems are conditional: a concrete compiler must first satisfy coverage, destination membership, target independence, cost overhead, and residual slack.
- The archive results are upper bounds. Only the full declared finite domain supplies exact optima.
- Lean rejects `sorry`, `admit`, user-declared `axiom`, theorem-inventory drift, and unexpected axiom dependencies. It does not inspect Kaggle, Hugging Face, MLX, or model-provider execution.
