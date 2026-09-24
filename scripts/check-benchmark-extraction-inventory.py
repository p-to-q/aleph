#!/usr/bin/env python3
"""Generate or verify the pinned Aleph-Bench E1 extraction inventory.

Source facts are read from the pinned Git commit through ``git ls-tree`` and
``git cat-file``. Benchmark files in the working tree are never used as source
evidence.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import secrets
import stat
import subprocess
import sys
from collections import Counter
from pathlib import Path, PurePosixPath
from typing import Any


PINNED_COMMIT = "10abdc1368439d1ab454ee3862a59e14b67a9530"
SOURCE_REPOSITORY = "https://github.com/p-to-q/aleph"
SOURCE_REF = "refs/heads/benchmark/source-v0.2"
DESTINATION_REPOSITORY = "https://github.com/p-to-q/aleph-benchmark"
MANIFEST_PATH = Path("docs/benchmark/extraction/source-v0.2.inventory.json")

# This is the byte-for-byte response from Apache's canonical license endpoint,
# including its leading and trailing line feeds. Keep the expectation outside
# the generated manifest so ``--write`` cannot bless an abridged license.
EXPECTED_FIXED_SOURCE_CONTENT = {
    "LICENSE": {
        "bytes": 11_358,
        "sha256": "cfc7749b96f63bd31c3c42b5c471bf756814053e847c10f3eb003417bc523d30",
    },
}

OWNED_PREFIX_COUNTS = {
    "bench/": 160,
    "schemas/": 15,
}
OWNED_FILES = (
    "LICENSE",
    "NOTICE",
    "aleph-bench",
    "docs/benchmark/kaggle-capture-runbook.md",
    "docs/benchmark/kaggle-diagnostic-runbook.md",
    "docs/benchmark/platform-release-policy.md",
)
EXPECTED_DISPOSITION_COUNTS = {
    "copy": 78,
    "exclude": 89,
    "port": 6,
    "regenerate": 2,
    "rewrite": 6,
}
EXPECTED_EXCLUSION_COUNTS = {
    "generated-mock-evidence": 39,
    "legacy-v0.1": 50,
}

CLASSIFIED_TREE_ALGORITHM = "sha256-length-framed-canonical-file-records-v1"
MANIFEST_ALGORITHM = "sha256-canonical-json-without-manifest-sha256-v1"
TREE_DOMAIN = b"aleph-bench-extraction-inventory-tree-v1\0"


class InventoryError(RuntimeError):
    """Raised when the pinned source or checked-in manifest is inconsistent."""


def _validate_fixed_source_content(
    *, path: str, byte_count: int, sha256: str
) -> None:
    expected = EXPECTED_FIXED_SOURCE_CONTENT.get(path)
    if expected is None:
        return
    if byte_count != expected["bytes"] or sha256 != expected["sha256"]:
        raise InventoryError(
            f"fixed source content differs at {path}: "
            f"expected bytes={expected['bytes']} sha256={expected['sha256']}, "
            f"found bytes={byte_count} sha256={sha256}"
        )


def _numbered_paths(prefix: str, start: int, end: int, suffix: str) -> set[str]:
    return {f"{prefix}{index:03d}{suffix}" for index in range(start, end + 1)}


COPY_PATHS = {
    "LICENSE",
    "aleph-bench",
    "bench/__init__.py",
    "bench/config/frozen_ladder-v0.2.json",
    "bench/conformance/scorer-v0.2.json",
    "bench/data/generate_s2.py",
    "bench/engine/__init__.py",
    "bench/engine/adapters/__init__.py",
    "bench/engine/adapters/base.py",
    "bench/engine/adapters/hosted_black_box.py",
    "bench/engine/adapters/identity.py",
    "bench/engine/adapters/mock.py",
    "bench/engine/adapters/replay.py",
    "bench/engine/frozen_ladder.py",
    "bench/engine/kaggle_capture.py",
    "bench/engine/kaggle_capture_evidence.py",
    "bench/engine/kaggle_creation_output.py",
    "bench/engine/kaggle_diagnostic_receipt.py",
    "bench/engine/kaggle_push_once.py",
    "bench/engine/kaggle_run_once.py",
    "bench/engine/leakage_gate.py",
    "bench/engine/manifest.py",
    "bench/engine/preflight.py",
    "bench/engine/protocol.py",
    "bench/engine/response_cache.py",
    "bench/engine/schema_validation.py",
    "bench/engine/scoring_core.py",
    "bench/tasks/kaggle/generate_v0_2_capture.py",
    "bench/tasks/kaggle/generate_v0_2_diagnostic.py",
    "bench/tests/__init__.py",
    "bench/tests/test_kaggle_capture.py",
    "bench/tests/test_kaggle_capture_evidence.py",
    "bench/tests/test_kaggle_capture_task_v0_2.py",
    "bench/tests/test_kaggle_creation_output.py",
    "bench/tests/test_kaggle_diagnostic_receipt_v0_2.py",
    "bench/tests/test_kaggle_diagnostic_v0_2.py",
    "bench/tests/test_kaggle_push_once.py",
    "bench/tests/test_kaggle_run_once.py",
    "bench/tests/test_replay_adapter.py",
    "bench/tests/test_scorer_conformance.py",
    "bench/tests/test_v0_2_verify.py",
    "schemas/v0.2/aleph-bench-item.schema.json",
    "schemas/v0.2/aleph-bench-kaggle-capture-evidence.schema.json",
    "schemas/v0.2/aleph-bench-kaggle-capture-payload.schema.json",
    "schemas/v0.2/aleph-bench-kaggle-diagnostic-receipt.schema.json",
    "schemas/v0.2/aleph-bench-manifest.schema.json",
    "schemas/v0.2/aleph-bench-platform-package.schema.json",
    "schemas/v0.2/aleph-bench-result.schema.json",
} | _numbered_paths("bench/data/v0.2/public/s2/s2-", 1, 30, ".json")

PORT_PATHS = {
    "bench/engine/metrics.py",
    "bench/engine/platform_package_v0_2.py",
    "bench/engine/report.py",
    "bench/engine/verify.py",
    "bench/run.py",
    "bench/tests/test_protocol_v0_2.py",
}

REGENERATE_PATHS = {
    "bench/tasks/kaggle/aleph_bench_v0_2_capture.py",
    "bench/tasks/kaggle/aleph_bench_v0_2_diagnostic.py",
}

REWRITE_DESTINATIONS = {
    "NOTICE": "NOTICE",
    "bench/README.md": "docs/protocol-v0.2.md",
    "bench/data/README.md": "docs/dataset-v0.2.md",
    "docs/benchmark/kaggle-capture-runbook.md": "docs/operations/kaggle-capture.md",
    "docs/benchmark/kaggle-diagnostic-runbook.md": (
        "docs/operations/kaggle-diagnostic.md"
    ),
    "docs/benchmark/platform-release-policy.md": "docs/release-policy.md",
}

LEGACY_EXACT_PATHS = {
    "bench/config/frozen_ladder.json",
    "bench/engine/audit.py",
    "bench/engine/bundle.py",
    "bench/engine/kaggle_receipt.py",
    "bench/engine/legacy_v0_1.py",
    "bench/engine/platform_package.py",
    "bench/tests/test_kaggle_receipt.py",
    "bench/tests/test_m0.py",
    "bench/tests/test_v0_1_immutable.py",
    "schemas/aleph-bench-audit.schema.json",
    "schemas/aleph-bench-bundle.schema.json",
    "schemas/aleph-bench-item.schema.json",
    "schemas/aleph-bench-manifest.schema.json",
    "schemas/aleph-bench-platform-package.schema.json",
    "schemas/aleph-bench-result.schema.json",
    "schemas/aleph-run.schema.json",
    "schemas/v0.2/aleph-bench-kaggle-receipt.schema.json",
}
LEGACY_PREFIXES = (
    "bench/data/public/",
    "bench/legacy/",
    "bench/tests/fixtures/",
)
GENERATED_MOCK_PREFIXES = ("bench/results/",)

EXCLUSION_DESCRIPTIONS = {
    "generated-mock-evidence": (
        "Generated v0.1 mock evidence and platform snapshots are release outputs, "
        "not standalone v0.2 source."
    ),
    "legacy-v0.1": (
        "Immutable v0.1 data, replay code, tests, and schemas remain historical "
        "provenance outside the active v0.2 authority closure."
    ),
}


def _canonical_compact_json(value: Any) -> bytes:
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("ascii")


def _canonical_file_json(value: Any) -> bytes:
    return (
        json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=True,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    ).encode("ascii")


def _repository_root() -> Path:
    expected = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        ["git", "--no-replace-objects", "rev-parse", "--show-toplevel"],
        cwd=expected,
        check=False,
        env=_git_environment(),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if result.returncode != 0:
        detail = result.stderr.decode("utf-8", errors="replace").strip()
        raise InventoryError(f"could not locate Git repository: {detail}")
    try:
        observed = Path(result.stdout.decode("utf-8").strip()).resolve(strict=True)
    except (OSError, UnicodeError) as exc:
        raise InventoryError(f"invalid Git repository root: {exc}") from exc
    if observed != expected:
        raise InventoryError(
            f"checker must live under repository root {observed}, found {expected}"
        )
    return observed


def _git_environment() -> dict[str, str]:
    """Return an ambient-Git-free environment for provenance reads.

    In particular, repository/object/index redirects must not make the pinned
    object name resolve against a caller-selected object database. Keeping only
    non-Git variables preserves ordinary PATH, locale, and HOME behavior.
    """

    environment = {
        key: value for key, value in os.environ.items() if not key.startswith("GIT_")
    }
    # A promisor/partial clone must fail closed when the pinned closure is
    # incomplete; provenance verification must never hydrate objects remotely.
    environment["GIT_NO_LAZY_FETCH"] = "1"
    environment["GIT_NO_REPLACE_OBJECTS"] = "1"
    return environment


def _git(root: Path, arguments: list[str]) -> bytes:
    result = subprocess.run(
        ["git", "--no-replace-objects", *arguments],
        cwd=root,
        check=False,
        env=_git_environment(),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if result.returncode != 0:
        detail = result.stderr.decode("utf-8", errors="replace").strip()
        raise InventoryError(f"git {' '.join(arguments)} failed: {detail}")
    return result.stdout


def _validate_git_source(root: Path) -> None:
    object_format = _git(root, ["rev-parse", "--show-object-format"]).decode(
        "ascii"
    ).strip()
    if object_format != "sha1":
        raise InventoryError(
            f"inventory records Git blob SHA-1, repository uses {object_format!r}"
        )
    resolved = _git(
        root, ["rev-parse", "--verify", f"{PINNED_COMMIT}^{{commit}}"]
    ).decode("ascii").strip()
    if resolved != PINNED_COMMIT:
        raise InventoryError(
            f"pinned source did not resolve exactly: {resolved!r} != {PINNED_COMMIT!r}"
        )
    object_type = _git(root, ["cat-file", "-t", PINNED_COMMIT]).decode(
        "ascii"
    ).strip()
    if object_type != "commit":
        raise InventoryError(f"pinned source is {object_type!r}, expected commit")


def _safe_repository_path(path: str, *, role: str) -> None:
    if (
        not path
        or "\\" in path
        or any(ord(character) < 32 or ord(character) == 127 for character in path)
    ):
        raise InventoryError(f"unsafe {role} path: {path!r}")
    candidate = PurePosixPath(path)
    if candidate.is_absolute() or ".." in candidate.parts or candidate.as_posix() != path:
        raise InventoryError(f"unsafe {role} path: {path!r}")


def _ls_owned_tree(root: Path) -> dict[str, dict[str, Any]]:
    raw = _git(
        root,
        [
            "ls-tree",
            "-rz",
            "-r",
            "--full-tree",
            "-l",
            PINNED_COMMIT,
            "--",
            "bench",
            "schemas",
            *OWNED_FILES,
        ],
    )
    entries: dict[str, dict[str, Any]] = {}
    records = raw.split(b"\0")
    if records and records[-1] == b"":
        records.pop()
    for record in records:
        try:
            header, encoded_path = record.split(b"\t", 1)
            mode_bytes, type_bytes, oid_bytes, size_bytes = header.split()
            path = encoded_path.decode("utf-8")
            mode = mode_bytes.decode("ascii")
            object_type = type_bytes.decode("ascii")
            oid = oid_bytes.decode("ascii")
            size = int(size_bytes.decode("ascii"))
        except (UnicodeError, ValueError) as exc:
            raise InventoryError(f"could not parse git ls-tree record: {record!r}") from exc
        _safe_repository_path(path, role="source")
        if path in entries:
            raise InventoryError(f"duplicate source path from git ls-tree: {path}")
        if object_type != "blob":
            raise InventoryError(f"unsupported Git object at {path}: {object_type}")
        if mode not in {"100644", "100755"}:
            raise InventoryError(f"unsupported Git mode at {path}: {mode}")
        if len(oid) != 40 or any(character not in "0123456789abcdef" for character in oid):
            raise InventoryError(f"invalid Git blob SHA-1 at {path}: {oid!r}")
        if size < 0:
            raise InventoryError(f"invalid Git blob size at {path}: {size}")
        entries[path] = {
            "mode": mode,
            "gitBlobSha1": oid,
            "bytes": size,
        }
    return entries


def _classification(path: str) -> tuple[str, str | None, str | None]:
    candidates: list[tuple[str, str | None, str | None]] = []
    if path in COPY_PATHS:
        candidates.append(("copy", path, None))
    if path in PORT_PATHS:
        candidates.append(("port", path, None))
    if path in REGENERATE_PATHS:
        candidates.append(("regenerate", path, None))
    if path in REWRITE_DESTINATIONS:
        candidates.append(("rewrite", REWRITE_DESTINATIONS[path], None))
    if path in LEGACY_EXACT_PATHS or path.startswith(LEGACY_PREFIXES):
        candidates.append(("exclude", None, "legacy-v0.1"))
    if path.startswith(GENERATED_MOCK_PREFIXES):
        candidates.append(("exclude", None, "generated-mock-evidence"))
    if len(candidates) != 1:
        raise InventoryError(
            f"source path must have exactly one classification, found {len(candidates)}: {path}"
        )
    disposition, destination, exclusion = candidates[0]
    if destination is not None:
        _safe_repository_path(destination, role="destination")
    return disposition, destination, exclusion


def _classified_tree_sha256(files: list[dict[str, Any]]) -> str:
    digest = hashlib.sha256()
    digest.update(TREE_DOMAIN)
    for record in sorted(files, key=lambda value: value["source"]):
        encoded = _canonical_compact_json(record)
        digest.update(len(encoded).to_bytes(8, "big"))
        digest.update(encoded)
    return digest.hexdigest()


def _manifest_sha256(manifest: dict[str, Any]) -> str:
    payload = copy.deepcopy(manifest)
    try:
        del payload["digests"]["manifestSha256"]
    except (KeyError, TypeError) as exc:
        raise InventoryError("manifest lacks digests.manifestSha256") from exc
    return hashlib.sha256(_canonical_compact_json(payload)).hexdigest()


def _build_manifest(root: Path) -> dict[str, Any]:
    _validate_git_source(root)
    tree = _ls_owned_tree(root)
    expected_total = sum(OWNED_PREFIX_COUNTS.values()) + len(OWNED_FILES)
    if len(tree) != expected_total:
        raise InventoryError(
            f"owned source count drifted: expected {expected_total}, found {len(tree)}"
        )
    for prefix, expected_count in OWNED_PREFIX_COUNTS.items():
        observed_count = sum(path.startswith(prefix) for path in tree)
        if observed_count != expected_count:
            raise InventoryError(
                f"owned prefix {prefix} count drifted: expected {expected_count}, "
                f"found {observed_count}"
            )
    for path in OWNED_FILES:
        if path not in tree:
            raise InventoryError(f"missing owned exact file: {path}")
    explicitly_classified = (
        COPY_PATHS
        | PORT_PATHS
        | REGENERATE_PATHS
        | set(REWRITE_DESTINATIONS)
        | LEGACY_EXACT_PATHS
    )
    missing_explicit_paths = sorted(explicitly_classified - set(tree))
    if missing_explicit_paths:
        raise InventoryError(
            f"explicit classification paths are absent from pinned source: {missing_explicit_paths}"
        )

    files: list[dict[str, Any]] = []
    for path in sorted(tree):
        facts = tree[path]
        blob = _git(root, ["cat-file", "blob", facts["gitBlobSha1"]])
        if len(blob) != facts["bytes"]:
            raise InventoryError(
                f"Git blob size mismatch at {path}: ls-tree={facts['bytes']}, "
                f"cat-file={len(blob)}"
            )
        blob_sha256 = hashlib.sha256(blob).hexdigest()
        _validate_fixed_source_content(
            path=path,
            byte_count=len(blob),
            sha256=blob_sha256,
        )
        disposition, destination, exclusion = _classification(path)
        record: dict[str, Any] = {
            "bytes": len(blob),
            "destination": destination,
            "disposition": disposition,
            "gitBlobSha1": facts["gitBlobSha1"],
            "mode": facts["mode"],
            "sha256": blob_sha256,
            "source": path,
        }
        if exclusion is not None:
            record["exclusion"] = exclusion
        files.append(record)

    destinations = [row["destination"] for row in files if row["destination"] is not None]
    duplicate_destinations = sorted(
        destination
        for destination, count in Counter(destinations).items()
        if count > 1
    )
    if duplicate_destinations:
        raise InventoryError(
            f"multiple source files map to the same destination: {duplicate_destinations}"
        )

    disposition_counts = dict(sorted(Counter(row["disposition"] for row in files).items()))
    if disposition_counts != EXPECTED_DISPOSITION_COUNTS:
        raise InventoryError(
            "disposition counts drifted: "
            f"expected {EXPECTED_DISPOSITION_COUNTS}, found {disposition_counts}"
        )
    exclusion_counts = dict(
        sorted(Counter(row["exclusion"] for row in files if "exclusion" in row).items())
    )
    if exclusion_counts != EXPECTED_EXCLUSION_COUNTS:
        raise InventoryError(
            "exclusion counts drifted: "
            f"expected {EXPECTED_EXCLUSION_COUNTS}, found {exclusion_counts}"
        )

    manifest: dict[str, Any] = {
        "artifactKind": "aleph_bench_extraction_inventory",
        "destination": {
            "repository": DESTINATION_REPOSITORY,
        },
        "dispositionCounts": disposition_counts,
        "exclusions": [
            {
                "id": exclusion_id,
                "reason": EXCLUSION_DESCRIPTIONS[exclusion_id],
                "trackedFiles": exclusion_counts[exclusion_id],
            }
            for exclusion_id in sorted(EXPECTED_EXCLUSION_COUNTS)
        ],
        "files": files,
        "formatVersion": 1,
        "ownedTree": {
            "files": list(OWNED_FILES),
            "prefixes": [
                {"path": prefix, "trackedFiles": count}
                for prefix, count in sorted(OWNED_PREFIX_COUNTS.items())
            ],
            "trackedFiles": len(files),
        },
        "source": {
            "commit": PINNED_COMMIT,
            "gitObjectFormat": "sha1",
            "ref": SOURCE_REF,
            "repository": SOURCE_REPOSITORY,
        },
    }
    manifest["digests"] = {
        "classifiedTreeAlgorithm": CLASSIFIED_TREE_ALGORITHM,
        "classifiedTreeSha256": _classified_tree_sha256(files),
        "manifestAlgorithm": MANIFEST_ALGORITHM,
        "manifestSha256": "",
    }
    manifest["digests"]["manifestSha256"] = _manifest_sha256(manifest)
    return manifest


def _reject_json_constant(value: str) -> None:
    raise InventoryError(f"non-finite JSON constant is forbidden: {value}")


def _reject_duplicate_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, child in pairs:
        if key in value:
            raise InventoryError(f"duplicate JSON key is forbidden: {key!r}")
        value[key] = child
    return value


def _manifest_target(root: Path) -> Path:
    """Validate the lexical target and lstat every existing parent directory."""

    _safe_repository_path(MANIFEST_PATH.as_posix(), role="manifest")
    target = root / MANIFEST_PATH
    try:
        target.relative_to(root)
    except ValueError as exc:
        raise InventoryError(f"manifest path escapes repository root: {target}") from exc

    current = root
    try:
        root_status = os.lstat(current)
    except OSError as exc:
        raise InventoryError(f"could not lstat repository root {root}: {exc}") from exc
    if stat.S_ISLNK(root_status.st_mode) or not stat.S_ISDIR(root_status.st_mode):
        raise InventoryError(f"repository root is not a real directory: {root}")

    for component in MANIFEST_PATH.parent.parts:
        current /= component
        try:
            status = os.lstat(current)
        except OSError as exc:
            raise InventoryError(
                f"could not lstat manifest parent directory {current}: {exc}"
            ) from exc
        if stat.S_ISLNK(status.st_mode):
            raise InventoryError(f"manifest parent directory is a symlink: {current}")
        if not stat.S_ISDIR(status.st_mode):
            raise InventoryError(f"manifest parent is not a directory: {current}")
    return target


def _open_manifest_parent(root: Path) -> int:
    """Open the checked parent chain one component at a time without following links."""

    _manifest_target(root)
    if (
        os.name != "posix"
        or not hasattr(os, "O_NOFOLLOW")
        or not hasattr(os, "O_DIRECTORY")
    ):
        raise InventoryError(
            "secure manifest access requires POSIX O_NOFOLLOW and O_DIRECTORY"
        )
    flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_DIRECTORY
    flags |= getattr(os, "O_CLOEXEC", 0)
    descriptor: int | None = None
    try:
        descriptor = os.open(root, flags)
        for component in MANIFEST_PATH.parent.parts:
            child = os.open(component, flags, dir_fd=descriptor)
            os.close(descriptor)
            descriptor = child
        return descriptor
    except OSError as exc:
        if descriptor is not None:
            os.close(descriptor)
        raise InventoryError(
            f"could not securely open manifest parent {MANIFEST_PATH.parent}: {exc}"
        ) from exc


def _manifest_lstat(parent_fd: int, *, required: bool) -> os.stat_result | None:
    """lstat the manifest relative to its anchored parent and require a regular file."""

    try:
        status = os.lstat(MANIFEST_PATH.name, dir_fd=parent_fd)
    except FileNotFoundError as exc:
        if required:
            raise InventoryError(
                f"inventory manifest does not exist: {MANIFEST_PATH}"
            ) from exc
        return None
    except OSError as exc:
        raise InventoryError(f"could not lstat inventory manifest: {exc}") from exc
    if stat.S_ISLNK(status.st_mode):
        raise InventoryError(
            f"inventory manifest must not be a symlink: {MANIFEST_PATH}"
        )
    if not stat.S_ISREG(status.st_mode):
        raise InventoryError(
            f"inventory manifest must be a regular file: {MANIFEST_PATH}"
        )
    return status


def _file_snapshot(status: os.stat_result) -> tuple[int, int, int, int, int, int]:
    """Capture fields that reveal replacement or mutation during one operation."""

    return (
        status.st_dev,
        status.st_ino,
        status.st_mode,
        status.st_size,
        status.st_mtime_ns,
        status.st_ctime_ns,
    )


def _read_manifest_bytes(root: Path) -> bytes:
    parent_fd = _open_manifest_parent(root)
    file_fd: int | None = None
    try:
        expected_status = _manifest_lstat(parent_fd, required=True)
        assert expected_status is not None
        flags = os.O_RDONLY | os.O_NOFOLLOW | getattr(os, "O_CLOEXEC", 0)
        flags |= getattr(os, "O_NONBLOCK", 0)
        try:
            file_fd = os.open(MANIFEST_PATH.name, flags, dir_fd=parent_fd)
        except OSError as exc:
            raise InventoryError(
                f"could not securely open inventory manifest: {exc}"
            ) from exc
        opened_status = os.fstat(file_fd)
        if not stat.S_ISREG(opened_status.st_mode):
            raise InventoryError(
                f"inventory manifest must be a regular file: {MANIFEST_PATH}"
            )
        if (expected_status.st_dev, expected_status.st_ino) != (
            opened_status.st_dev,
            opened_status.st_ino,
        ):
            raise InventoryError("inventory manifest changed while it was being opened")
        with os.fdopen(file_fd, "rb", closefd=False) as stream:
            raw = stream.read()
        if _file_snapshot(opened_status) != _file_snapshot(os.fstat(file_fd)):
            raise InventoryError("inventory manifest changed while it was being read")
        return raw
    finally:
        if file_fd is not None:
            os.close(file_fd)
        os.close(parent_fd)


def _parent_fd_matches_worktree(root: Path, parent_fd: int) -> None:
    """Recheck that the anchored directory is still the visible in-root parent."""

    visible_parent = _manifest_target(root).parent
    visible_status = os.lstat(visible_parent)
    opened_status = os.fstat(parent_fd)
    if (visible_status.st_dev, visible_status.st_ino) != (
        opened_status.st_dev,
        opened_status.st_ino,
    ):
        raise InventoryError("manifest parent directory changed during atomic write")


def _atomic_write_manifest(root: Path, payload: bytes) -> None:
    """Atomically replace the manifest through an anchored, no-follow directory fd."""

    parent_fd = _open_manifest_parent(root)
    temporary_fd: int | None = None
    temporary_name: str | None = None
    try:
        previous_status = _manifest_lstat(parent_fd, required=False)
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW
        flags |= getattr(os, "O_CLOEXEC", 0)
        for _attempt in range(128):
            candidate = (
                f".{MANIFEST_PATH.name}.tmp-{os.getpid()}-{secrets.token_hex(16)}"
            )
            try:
                temporary_fd = os.open(candidate, flags, 0o600, dir_fd=parent_fd)
            except FileExistsError:
                continue
            except OSError as exc:
                raise InventoryError(
                    f"could not create manifest temporary file: {exc}"
                ) from exc
            temporary_name = candidate
            break
        if temporary_fd is None or temporary_name is None:
            raise InventoryError("could not allocate a unique manifest temporary file")

        remaining = memoryview(payload)
        while remaining:
            written = os.write(temporary_fd, remaining)
            if written <= 0:
                raise InventoryError("short write while creating inventory manifest")
            remaining = remaining[written:]
        os.fchmod(temporary_fd, 0o644)
        os.fsync(temporary_fd)
        os.close(temporary_fd)
        temporary_fd = None

        current_status = _manifest_lstat(parent_fd, required=False)
        if previous_status is None:
            if current_status is not None:
                raise InventoryError("inventory manifest appeared during atomic write")
        elif current_status is None or _file_snapshot(previous_status) != _file_snapshot(
            current_status
        ):
            raise InventoryError("inventory manifest changed during atomic write")

        _parent_fd_matches_worktree(root, parent_fd)
        try:
            os.replace(
                temporary_name,
                MANIFEST_PATH.name,
                src_dir_fd=parent_fd,
                dst_dir_fd=parent_fd,
            )
        except (NotImplementedError, OSError) as exc:
            raise InventoryError(
                f"could not atomically replace inventory manifest: {exc}"
            ) from exc
        temporary_name = None
        os.fsync(parent_fd)
    finally:
        if temporary_fd is not None:
            os.close(temporary_fd)
        if temporary_name is not None:
            try:
                os.unlink(temporary_name, dir_fd=parent_fd)
            except FileNotFoundError:
                pass
        os.close(parent_fd)


def _load_manifest(root: Path) -> tuple[dict[str, Any], bytes]:
    try:
        raw = _read_manifest_bytes(root)
    except OSError as exc:
        raise InventoryError(f"could not read inventory manifest {MANIFEST_PATH}: {exc}") from exc
    try:
        value = json.loads(
            raw.decode("ascii"),
            object_pairs_hook=_reject_duplicate_pairs,
            parse_constant=_reject_json_constant,
        )
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise InventoryError(f"invalid inventory JSON {MANIFEST_PATH}: {exc}") from exc
    if not isinstance(value, dict):
        raise InventoryError("inventory manifest must contain one JSON object")
    return value, raw


def _first_difference(expected: Any, observed: Any, path: str = "$") -> str | None:
    if type(expected) is not type(observed):
        return f"{path}: expected {type(expected).__name__}, found {type(observed).__name__}"
    if isinstance(expected, dict):
        expected_keys = set(expected)
        observed_keys = set(observed)
        if expected_keys != observed_keys:
            return (
                f"{path}: keys differ; missing={sorted(expected_keys - observed_keys)}, "
                f"unexpected={sorted(observed_keys - expected_keys)}"
            )
        for key in sorted(expected):
            difference = _first_difference(expected[key], observed[key], f"{path}.{key}")
            if difference is not None:
                return difference
        return None
    if isinstance(expected, list):
        if len(expected) != len(observed):
            return f"{path}: expected {len(expected)} items, found {len(observed)}"
        for index, (expected_child, observed_child) in enumerate(zip(expected, observed)):
            difference = _first_difference(
                expected_child, observed_child, f"{path}[{index}]"
            )
            if difference is not None:
                return difference
        return None
    if expected != observed:
        return f"{path}: expected {expected!r}, found {observed!r}"
    return None


def _check_manifest(root: Path) -> dict[str, Any]:
    observed, raw = _load_manifest(root)
    canonical = _canonical_file_json(observed)
    if raw != canonical:
        raise InventoryError(
            f"{MANIFEST_PATH} is not canonical sorted, indented ASCII JSON "
            "with one trailing newline"
        )

    expected = _build_manifest(root)
    difference = _first_difference(expected, observed)
    if difference is not None:
        raise InventoryError(f"inventory differs from pinned Git source: {difference}")

    observed_tree_digest = _classified_tree_sha256(observed["files"])
    if observed_tree_digest != observed["digests"]["classifiedTreeSha256"]:
        raise InventoryError("classified tree digest does not match manifest file records")
    observed_manifest_digest = _manifest_sha256(observed)
    if observed_manifest_digest != observed["digests"]["manifestSha256"]:
        raise InventoryError("manifest digest does not match canonical manifest content")
    return observed


def _write_manifest(root: Path) -> None:
    manifest = _build_manifest(root)
    _atomic_write_manifest(root, _canonical_file_json(manifest))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Generate or verify the pinned Aleph-Bench E1 extraction inventory."
    )
    parser.add_argument(
        "--write",
        action="store_true",
        help="Regenerate the deterministic manifest from the pinned Git commit.",
    )
    args = parser.parse_args(argv)

    root = _repository_root()
    if args.write:
        _write_manifest(root)
    manifest = _check_manifest(root)
    counts = manifest["dispositionCounts"]
    print(
        "inventory ok: "
        f"commit={manifest['source']['commit']} "
        f"files={manifest['ownedTree']['trackedFiles']} "
        + " ".join(f"{name}={counts[name]}" for name in sorted(counts))
    )
    print(f"classified tree sha256: {manifest['digests']['classifiedTreeSha256']}")
    print(f"manifest sha256: {manifest['digests']['manifestSha256']}")
    if args.write:
        print(f"wrote {MANIFEST_PATH}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (InventoryError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1) from None
