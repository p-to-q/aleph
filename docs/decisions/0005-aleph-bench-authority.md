# ADR 0005: Aleph-Bench authority and release topology

## Status

Accepted.

## Context

Aleph-Bench currently exists in three different forms:

1. source, tests, datasets, schemas, and packaging code on an Aleph development branch;
2. uncommitted follow-up work in a local worktree;
3. one generated M0 platform snapshot in `p-to-q/aleph-benchmark`.

Those forms are not interchangeable. The public repository at commit
`f37fa45f7f7dec11e1cdebb7139027a114dbb631` contains generated platform files but cannot regenerate
them. The local worktree contains later experiments but is not a durable or reviewable source. Treating
either as canonical would make fixes, provenance, and release digests ambiguous.

## Decision

The target state is:

- `p-to-q/aleph-benchmark` is the canonical Aleph-Bench source repository;
- it owns benchmark engines, datasets, schemas, tests, protocol documentation, and release tooling;
- it generates its Kaggle, Hugging Face, Croissant, evidence, and report artifacts from source;
- Aleph remains the product/workbench repository and consumes versioned benchmark releases through
  files rather than hidden cross-repository imports.

Until the standalone repository meets that contract, authority is temporarily fixed as follows:

- `p-to-q/aleph` branch `benchmark/source-v0.1`, initially pinned at
  `d4427308e4449ad89dc4f2abe25b8b842d214d39`, is the reviewable benchmark source;
- `p-to-q/aleph-benchmark@f37fa45f7f7dec11e1cdebb7139027a114dbb631` is a generated preview mirror,
  not a source tree and not a release-quality benchmark;
- the dirty local `claude/hardcore-turing-a706f5` worktree is experimental evidence only until its
  changes are separated, reviewed, and committed;
- generated files under `bench/results/platform/` and `platform/` must not be hand-edited as their
  source of truth.

The temporary source branch exists to receive small benchmark-only fixes without merging the full
benchmark history into the Aleph product `main` branch. Every such change must use an issue and a PR
whose base is `benchmark/source-v0.1`.

## Source map during extraction

| Contract | Temporary source | Derived or mirrored output |
|---|---|---|
| Scoring, leakage, aggregation | `bench/engine/` | packaged Kaggle scorer and reports |
| Frozen S2 items and ladders | `bench/data/` | public JSONL and CSV datasets |
| Benchmark result contracts | `schemas/` and `packages/core/src/bench.ts` | schemas copied into platform packages |
| Conformance and parity checks | `bench/tests/` | CI receipts |
| Platform package layout | `bench/engine/platform_package.py` | `bench/results/platform/` and standalone snapshot |
| Protocol and claims | `docs/benchmark/` | platform README and evaluation notes |

If a generated file disagrees with its temporary source, the source plus a clean regeneration wins.
If an uncommitted worktree disagrees with the temporary branch, neither change is accepted until it is
reviewed through a PR.

## Migration gates

Authority moves to `p-to-q/aleph-benchmark` only after one reviewed PR proves all of the following:

1. a clean checkout installs and runs the benchmark tests;
2. source commands regenerate the complete platform package in a temporary directory;
3. package verification is closed-world and checks digests;
4. no generated document contains maintainer-local absolute paths;
5. the repository has a license, contribution guide, citation metadata, security policy, and CI;
6. a mock release is visibly separated from real model evidence;
7. regenerated artifacts match their checked-in or release-attached counterparts.

The migration records the final Aleph source commit and the first standalone source commit. After that
point, `benchmark/source-v0.1` is frozen as a provenance record; new benchmark changes go only to the
standalone repository.

## Release flow after migration

```text
source + protocol manifest + fixtures
  -> unit, metamorphic, parity, and replay checks
  -> clean temporary package build
  -> closed-world manifest and checksums
  -> versioned tag and immutable release assets
  -> Kaggle / Hugging Face publication
  -> Aleph imports versioned result files
```

Mock, fixture, black-box, and white-box evidence remain separate throughout this flow. A generated
preview must never be presented as a model ranking.

## Consequences

- Benchmark fixes can proceed without touching the owner's uncommitted worktree.
- The full benchmark implementation does not enter Aleph product `main` during extraction.
- The public standalone repository is explicitly incomplete until it passes the migration gates.
- Release artifacts gain a single derivation path and an auditable source commit.
- Extraction is a repository migration, not an opportunity to combine scorer redesign, new datasets,
  hosted-model runs, or product UI work.

