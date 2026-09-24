# Aleph-Bench standalone extraction E1

## Status

This is the first, inventory-only slice of
[`#29`](https://github.com/p-to-q/aleph/issues/29). It records the reviewed
Aleph-Bench source closure at
`087cca087da05714a5d7246ab0bb20adcc3012cd` without merging the benchmark
development branch into the Aleph product branch.

The target authority remains `p-to-q/aleph-benchmark`. This slice does not move
authority, publish a release, or change benchmark behavior. It makes the later
move reviewable and content-addressed.

## E1 artifacts

- [source-v0.2.inventory.json](../benchmark/extraction/source-v0.2.inventory.json)
  is the machine-readable source inventory.
- [check-benchmark-extraction-inventory.py](../../scripts/check-benchmark-extraction-inventory.py)
  regenerates or verifies the inventory from the pinned Git commit.

The checker reads source facts only from the Git object database through
`git ls-tree` and `git cat-file`. A dirty checkout cannot alter the recorded
source bytes. The pinned commit must exist locally; the checker never fetches
from the network. Git replacement objects and promisor lazy-fetching are
disabled, and ambient `GIT_*` repository, worktree, object-store, index, and
namespace redirects are removed from every plumbing call. Legacy grafts and
shallow boundaries only affect commit ancestry, which the checker does not
traverse; a shallow clone is valid when the complete pinned tree and blob
closure is present, and fails otherwise.

## Owned tree and dispositions

E1 classifies every tracked file under `bench/` and `schemas/`, plus `LICENSE`,
`NOTICE`, the `aleph-bench` launcher, and three exact operational/provenance
documents:

```text
docs/benchmark/kaggle-capture-runbook.md
docs/benchmark/kaggle-diagnostic-runbook.md
docs/benchmark/platform-release-policy.md
```

No catch-all inclusion rule is permitted.
All other `docs/benchmark/`, `docs/research/`, and staged launch documents stay
outside the E1 owned set.

| Disposition | Count | Meaning |
| --- | ---: | --- |
| `copy` | 78 | Preserve source bytes, path, and Git mode. |
| `port` | 6 | Use this source file, but remove a named product/v0.1 dependency in a later reviewable PR. |
| `regenerate` | 2 | Retain the current bytes as a receipt; regenerate the destination from the copied generator. |
| `rewrite` | 6 | Use the source document as input to a truthful standalone document; do not present it as a byte-identical copy. |
| `exclude` | 89 | Keep historical/generated material outside the active v0.2 authority closure. |

The total is 181 files: 160 under `bench/`, 15 under `schemas/`, three owned root
files, and three exact operational/provenance documents under `docs/benchmark/`.

### Byte-copy closure

The 78 `copy` records are the following exact groups. The manifest expands
every group into individual file records.

```text
LICENSE
aleph-bench
bench/__init__.py
bench/config/frozen_ladder-v0.2.json
bench/conformance/scorer-v0.2.json
bench/data/generate_s2.py
bench/data/v0.2/public/s2/s2-001.json ... s2-030.json
bench/engine/__init__.py
bench/engine/adapters/{__init__,base,hosted_black_box,identity,mock,replay}.py
bench/engine/{frozen_ladder,kaggle_capture,kaggle_capture_evidence,
  kaggle_creation_output,kaggle_diagnostic_receipt,kaggle_push_once,
  kaggle_run_once,leakage_gate,manifest,preflight,protocol,
  response_cache,schema_validation,scoring_core}.py
bench/tasks/kaggle/generate_v0_2_{capture,diagnostic}.py
bench/tests/__init__.py
bench/tests/test_kaggle_capture.py
bench/tests/test_kaggle_capture_evidence.py
bench/tests/test_kaggle_capture_task_v0_2.py
bench/tests/test_kaggle_creation_output.py
bench/tests/test_kaggle_diagnostic_receipt_v0_2.py
bench/tests/test_kaggle_diagnostic_v0_2.py
bench/tests/test_kaggle_push_once.py
bench/tests/test_kaggle_run_once.py
bench/tests/test_replay_adapter.py
bench/tests/test_scorer_conformance.py
bench/tests/test_v0_2_verify.py
schemas/v0.2/aleph-bench-item.schema.json
schemas/v0.2/aleph-bench-kaggle-capture-evidence.schema.json
schemas/v0.2/aleph-bench-kaggle-capture-payload.schema.json
schemas/v0.2/aleph-bench-kaggle-diagnostic-receipt.schema.json
schemas/v0.2/aleph-bench-manifest.schema.json
schemas/v0.2/aleph-bench-platform-package.schema.json
schemas/v0.2/aleph-bench-result.schema.json
```

The mock adapter is included as a deterministic test fixture. Mock results are
not included and must not be represented as model evidence.

### Port closure

The six `port` records stay at the same destination paths, but may not be
copied into the standalone authority unchanged:

- `bench/engine/metrics.py`: replace its internal design-spec link with the
  standalone protocol document without changing metric behavior.
- `bench/run.py`: remove eager v0.1 imports and legacy-only commands.
- `bench/engine/platform_package_v0_2.py`: replace the v0.1 write guard with a
  standalone output-safety boundary.
- `bench/engine/report.py`: remove the unversioned v0.1 schema fallback.
- `bench/engine/verify.py`: remove legacy bundle/replay imports and the product
  repository's separate `aleph-run` schema dependency; the v0.2 result schema
  already embeds the run contract it validates.
- `bench/tests/test_protocol_v0_2.py`: replace checked-in v0.1 fixtures with a
  small local wrong-protocol fixture.

Each port belongs in a later PR with one behavioral acceptance gate. E1 does
not perform those edits.

### Regenerated and rewritten destinations

The checked-in Kaggle task files are generated distribution artifacts:

```text
bench/tasks/kaggle/aleph_bench_v0_2_capture.py
bench/tasks/kaggle/aleph_bench_v0_2_diagnostic.py
```

The standalone repository must regenerate them with Python 3.13 and prove
byte equality with the corresponding inventory receipts. The 30 S2 JSON files
are different: they are frozen protocol inputs, so their exact bytes are copied
and independently checked by `bench/data/generate_s2.py --check`.

Six mixed historical or repository-coupled documents require truthful
rewrites:

| Source | Planned standalone destination |
| --- | --- |
| `NOTICE` | `NOTICE` |
| `bench/README.md` | `docs/protocol-v0.2.md` |
| `bench/data/README.md` | `docs/dataset-v0.2.md` |
| `docs/benchmark/kaggle-capture-runbook.md` | `docs/operations/kaggle-capture.md` |
| `docs/benchmark/kaggle-diagnostic-runbook.md` | `docs/operations/kaggle-diagnostic.md` |
| `docs/benchmark/platform-release-policy.md` | `docs/release-policy.md` |

`NOTICE` is hashed because Apache attribution and provenance are release
requirements. Its standalone rewrite must retain applicable copyright and
attribution while removing product-prototype statements that do not describe
the benchmark authority. Publication must fail closed until that rewritten
notice is reviewed together with the copied `LICENSE`.

The three operational sources are hashed because they define how hosted runs
and release evidence are produced, retained, and promoted. They still require
rewrites because their current links and repository assumptions target the
mixed Aleph tree. Root README, packaging, CI, citation, contribution, security,
and other operational documentation are later standalone-owned work. E1 does
not copy product documentation or staged launch templates into the authority
repository.

## Exclusions

The 89 excluded records remain individually hashed in the manifest so omission
is explicit rather than accidental:

- `generated-mock-evidence` — 39 files under `bench/results/`, including the
  generated v0.1 platform snapshot and mock evidence;
- `legacy-v0.1` — 50 immutable v0.1 data, engine, replay, fixture, test, and
  schema files.

`schemas/v0.2/aleph-bench-kaggle-receipt.schema.json` is deliberately in the
legacy group. Its receipt format is numbered 0.2, but its source protocol is
fixed to `0.1-legacy`; its directory name does not make it active v0.2 source.

Product-only `apps/`, `packages/`, `search/`, `web/`, Node metadata, and the
current mixed CI workflow are outside the owned extraction tree. Cache files,
Python bytecode, local journals, downloaded archives, and private evidence are
untracked runtime state and are never extraction inputs.

## Integrity contract

Every file record contains:

```text
source, destination, disposition, mode, gitBlobSha1, sha256, bytes
```

Excluded records also name exactly one exclusion group. Destinations are
repository-relative POSIX paths or `null`; parent traversal, absolute paths,
backslashes, control characters, source symlink/submodule entries, and Git
modes other than `100644` and `100755` fail closed. Non-null destination paths
must also be unique.

The classified-tree digest is calculated as follows:

1. Sort complete file records by `source`.
2. Serialize each record as compact ASCII JSON with sorted keys and no
   non-finite numbers.
3. Prefix each serialized record with its unsigned eight-byte big-endian
   length.
4. Hash the domain separator
   `aleph-bench-extraction-inventory-tree-v1\0` followed by those frames with
   SHA-256.

The manifest digest is SHA-256 over compact sorted-key ASCII JSON after
removing only `digests.manifestSha256`. The checked-in file itself uses sorted,
two-space-indented ASCII JSON and exactly one trailing newline. No timestamp,
checkout path, branch tip, or other mutable host value enters either digest.

Manifest reads reject symlinks and non-regular files. Regeneration rejects
symlinks in the repository-relative parent chain and writes a unique temporary
regular file in the anchored destination directory, flushes and `fsync`s it,
then installs it with an atomic `os.replace` and directory `fsync`. These checks
prevent accidental link traversal and ordinary path-substitution races; they do
not claim to defend against a process with sustained malicious write access to
the repository directories during the check.

Git blob SHA-1 is retained for source-repository provenance. SHA-256 is the
cross-repository content identity.

## Acceptance gate

Run from the repository root:

```bash
python3 scripts/check-benchmark-extraction-inventory.py
npm run lint
git diff --check
```

Regeneration is explicit and must be reviewed as a manifest diff:

```bash
python3 scripts/check-benchmark-extraction-inventory.py --write
python3 scripts/check-benchmark-extraction-inventory.py
```

E1 is complete only when the checker reports the pinned commit, all 181 files,
the five disposition counts, and matching classified-tree and manifest
digests. A future source commit requires a new inventory; changing the mutable
branch ref alone cannot update this record.

## Out of scope

- Merging `benchmark/source-v0.2` into product `main`.
- Changing scorer, protocol, dataset, CLI, Kaggle control-plane, or tests.
- Creating the standalone packaging or CI foundation.
- Calling a model, spending Kaggle quota, or publishing GitHub, Kaggle, or
  Hugging Face artifacts.
- Claiming that source authority has moved before the standalone clean-clone,
  regeneration, and release gates pass.
