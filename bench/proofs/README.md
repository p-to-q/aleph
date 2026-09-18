# Unicode runtime compatibility proof

Aleph-Bench v0.2 accepts only Python 3.13 with Unicode Character Database (UCD) 15.1. This directory
contains a standard-library-only, offline proof of why Python 3.11/UCD 14 cannot silently be treated
as the same scorer runtime.

This artifact is **Slice 0a**, the negative-control proof needed before deployment work can rely on
the runtime mismatch. It is not the complete portable-runtime gate proposed in the capture-only
scoring plan. In particular, it does not certify Python 3.11 plus `unicodedata2`, vendor the official
Unicode conformance inputs, or claim equivalence with the v0.2 scorer.

The harness requires explicit interpreter paths. One isolated worker per runtime records identity and
counterexamples and writes that runtime's lossless property stream, so a stream cannot be combined
with identity from another process. Worker stdout/stderr, execution time, and file size are bounded;
`-B` prevents bytecode-cache writes. The parent hashes every proof input, including the protocol
module that supplies leakage thresholds, before and after both workers. It checks their CPython series
and UCD versions, scans all 1,114,112 code points, removes the temporary streams automatically, and
compares every decoded field exactly. SHA-256 binds the retained summary to the streams and difference
sets; hashes do not decide whether properties are equal. The harness also observes two concrete scorer
counterexamples through public pure scorer primitives. It never changes the frozen runtime constants,
calls a model, reaches Kaggle, or accesses the network.

```bash
python3 bench/proofs/unicode_runtime_compatibility.py \
  --python311 /path/to/python3.11 \
  --python313 /path/to/python3.13 \
  --check bench/proofs/unicode-runtime-compatibility-v0.2.json
```

Use `--output /new/path.json` instead of `--check` to retain a fresh, non-overwriting receipt. The
receipt records full interpreter and platform observations, source/config hashes, per-runtime stream
hashes, exact difference-set hashes, property counts, and both counterexamples. Reproduction compares
all semantic results while allowing the new machine identity to differ from the original evidence
host.

This is a compatibility proof, not a second scorer. The Python 3.11 observations are explicitly
non-canonical probes; the guarded v0.2 entry points still reject that runtime. The exhaustive scan is
single-code-point coverage and does not prove arbitrary multi-code-point normalization behavior. It
also does not run the official Unicode conformance files or evaluate `unicodedata2`; those remain
the remaining Slice 0 work for any future portable profile, not grounds for weakening v0.2.
