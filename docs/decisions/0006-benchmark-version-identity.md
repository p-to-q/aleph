# ADR 0006: Benchmark version identity axes

## Status

Accepted.

## Context

The portable scorer work was provisionally described as protocol `0.3.0`. That conflated two
different kinds of change:

- reproducing protocol `0.2.0` scoring under another runtime; and
- changing benchmark measurement semantics.

Runtime portability does not change the dataset, prompt plan, metrics, thresholds, aggregation, or
eligibility rules. Issue [#35](https://github.com/p-to-q/aleph/issues/35), by contrast, changes
length units, failure denominators, and ECL aggregation. Reusing one version for both would make a
result's scientific meaning ambiguous.

ADR 0005 is already assigned on `main` to Aleph-Bench authority and release topology. This decision
therefore uses 0006 even though the temporary benchmark source branch does not yet contain 0005.

## Decision

A portable implementation of the current benchmark continues to declare:

- `protocolVersion: "0.2.0"`;
- `referenceProtocolVersion: "0.2.0"`; and
- `targetScorer: "aleph-unicode@0.2.0"`.

Its release identity must version independent implementation axes rather than encoding them in the
protocol version:

1. scorer profile id and `scorerProfileVersion`;
2. runtime profile id and `runtimeProfileVersion`;
3. package id, `packageVersion`, and content digest; and
4. schema id and `schemaVersion`.

The exact initial identifiers belong to the reviewed schemas and implementation. They must not
reuse `protocolVersion` as a shorthand.

Portability and numerical comparability are also separate claims. A portable profile begins with
`comparabilityStatus: "unproven"`. Only the exhaustive zero-mismatch proof and canonical receipt in
issue [#77](https://github.com/p-to-q/aleph/issues/77) may change that status to `proven`. A
successful package build, conformance subset, or hosted import cannot do so.

Protocol `0.3.0` is reserved for the semantic work in issue #35. That protocol may later have both
reference and portable implementations, but portability alone does not create it.

## Historical provisional label

The checked-in portable input artifacts, including the string-semantics and vendored Unicode
manifests, contain `profileVersion: "0.3.0-provisional"`. Those bytes are immutable historical
inputs. Do not rewrite their manifests, schemas, receipts, or generator constants to make the label
match this decision.

Future packages must bind each input by its existing semantic or artifact identity and manifest
digest, and may retain the literal value as a legacy source label. It is not the benchmark
`protocolVersion`, the portable scorer profile version, or evidence of comparability.

## Consequences

- Protocol `0.2.0` reference bytes and measurement semantics remain unchanged.
- Portable scorer, runtime, package, and schema revisions can evolve independently and remain
  auditable.
- No portable result joins a v0.2 comparison group until issue #77 proves equivalence.
- Issue #35 can introduce protocol `0.3.0` without colliding with a runtime-port label.
- Existing `0.3.0-provisional` artifacts remain reproducible and require no generated-byte churn.
