from __future__ import annotations

import hashlib
import json
import os
import secrets
import stat
from pathlib import Path, PurePosixPath
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
RECEIPT_PATH = REPO_ROOT / "bench/legacy/v0.1-immutable.json"
EXPECTED_RECEIPT_SHA256 = "e1c9a9ea3acb3e286b75fd094e7efde1ac3f76809e489d54851da435641b89cc"
EXPECTED_SOURCE_COMMIT = "ecc3badb3cedeb659dd4a47c8664e725f4d57232"
EXPECTED_PLATFORM_DIRECTORIES = {
    "data",
    "docs",
    "evidence",
    "huggingface",
    "kaggle",
    "schemas",
}
IMMUTABLE_TREE_PATHS = {
    "bench/data/public/s2",
    "bench/results/platform/m0-mock",
}


def load_v0_1_receipt() -> dict[str, Any]:
    receipt_stat = RECEIPT_PATH.lstat()
    if not stat.S_ISREG(receipt_stat.st_mode) or receipt_stat.st_nlink != 1:
        raise ValueError(
            "Aleph-Bench v0.1 immutable receipt must be a singly-linked regular file"
        )
    if stat.S_IMODE(receipt_stat.st_mode) != 0o644:
        raise ValueError("Aleph-Bench v0.1 immutable receipt mode must be 0644")
    raw_receipt = RECEIPT_PATH.read_bytes()
    observed_digest = hashlib.sha256(raw_receipt).hexdigest()
    if observed_digest != EXPECTED_RECEIPT_SHA256:
        raise ValueError(
            "Aleph-Bench v0.1 immutable receipt bytes changed: "
            f"expected {EXPECTED_RECEIPT_SHA256}, found {observed_digest}"
        )
    receipt = json.loads(raw_receipt)
    if not isinstance(receipt, dict):
        raise ValueError("Aleph-Bench v0.1 immutable receipt must be a JSON object")
    if receipt.get("formatVersion") != 1 or receipt.get("protocolVersion") != "0.1":
        raise ValueError("unsupported Aleph-Bench v0.1 immutable receipt")
    if receipt.get("sourceCommit") != EXPECTED_SOURCE_COMMIT:
        raise ValueError("Aleph-Bench v0.1 immutable receipt has the wrong source commit")
    return receipt


def validated_relative_path(raw_path: str) -> PurePosixPath:
    path = PurePosixPath(raw_path)
    if (
        not raw_path
        or "\\" in raw_path
        or path.is_absolute()
        or ".." in path.parts
        or path.as_posix() != raw_path
    ):
        raise ValueError(f"unsafe or non-canonical receipt path: {raw_path!r}")
    return path


def is_ignored(relative_path: PurePosixPath, ignored: dict[str, list[str]]) -> bool:
    return (
        any(part in ignored["directoryNames"] for part in relative_path.parts[:-1])
        or relative_path.name in ignored["fileNames"]
        or any(relative_path.name.endswith(suffix) for suffix in ignored["fileSuffixes"])
    )


def aggregate_sha256(files: list[tuple[PurePosixPath, Path]]) -> str:
    aggregate = hashlib.sha256()
    for relative_path, path in sorted(files, key=lambda item: item[0].as_posix()):
        path_bytes = relative_path.as_posix().encode("utf-8")
        content = path.read_bytes()
        aggregate.update(len(path_bytes).to_bytes(4, "big"))
        aggregate.update(path_bytes)
        aggregate.update(len(content).to_bytes(8, "big"))
        aggregate.update(content)
    return aggregate.hexdigest()


def _repository_path_has_safe_ancestors(
    relative_entry: PurePosixPath,
    *,
    group_name: str,
    errors: list[str],
) -> bool:
    current = REPO_ROOT
    for index, part in enumerate(relative_entry.parts):
        current /= part
        try:
            metadata = current.lstat()
        except FileNotFoundError:
            errors.append(f"v0.1 {group_name} path is missing: {relative_entry}")
            return False
        if stat.S_ISLNK(metadata.st_mode):
            traversed = PurePosixPath(*relative_entry.parts[: index + 1])
            errors.append(
                f"v0.1 {group_name} path has a symlink component: {traversed}"
            )
            return False
        if index < len(relative_entry.parts) - 1:
            if not stat.S_ISDIR(metadata.st_mode):
                traversed = PurePosixPath(*relative_entry.parts[: index + 1])
                errors.append(
                    f"v0.1 {group_name} path ancestor is not a directory: {traversed}"
                )
                return False
            ancestor_mode = stat.S_IMODE(metadata.st_mode)
            if ancestor_mode != 0o755:
                traversed = PurePosixPath(*relative_entry.parts[: index + 1])
                errors.append(
                    f"v0.1 {group_name} ancestor mode mismatch: {traversed} "
                    f"expected 0755, found {ancestor_mode:04o}"
                )
    return True


def _regular_files(
    root: Path,
    *,
    logical_prefix: PurePosixPath,
    ignored: dict[str, list[str]],
) -> tuple[list[tuple[PurePosixPath, Path]], list[str]]:
    files: list[tuple[PurePosixPath, Path]] = []
    errors: list[str] = []
    if root.is_symlink():
        return [], [f"symlink is forbidden in immutable v0.1 package: {root}"]
    if not root.is_dir():
        return [], [f"immutable v0.1 package directory is missing: {root}"]
    root_mode = stat.S_IMODE(root.lstat().st_mode)
    if root_mode != 0o755:
        errors.append(
            "immutable v0.1 package directory mode mismatch: . expected 0755, "
            f"found {root_mode:04o}"
        )

    observed_directories: set[str] = set()
    for path in sorted(root.rglob("*")):
        relative = PurePosixPath(path.relative_to(root).as_posix())
        if path.is_symlink():
            errors.append(f"symlink is forbidden in immutable v0.1 package: {relative}")
            continue
        if "__pycache__" in relative.parts or relative.name.endswith((".pyc", ".pyo")):
            errors.append(
                f"importable bytecode is forbidden in immutable v0.1 package: {relative}"
            )
            continue
        if is_ignored(relative, ignored):
            continue
        path_stat = path.lstat()
        mode = path_stat.st_mode
        if stat.S_ISDIR(mode):
            observed_directories.add(relative.as_posix())
            directory_mode = stat.S_IMODE(mode)
            if directory_mode != 0o755:
                errors.append(
                    "immutable v0.1 package directory mode mismatch: "
                    f"{relative} expected 0755, found {directory_mode:04o}"
                )
            continue
        if not stat.S_ISREG(mode):
            errors.append(f"non-regular file in immutable v0.1 package: {relative}")
            continue
        if path_stat.st_nlink != 1:
            errors.append(
                "hard-linked file is forbidden in immutable v0.1 package: "
                f"{relative} (link count {path_stat.st_nlink})"
            )
            continue
        file_mode = stat.S_IMODE(mode)
        if file_mode != 0o644:
            errors.append(
                "immutable v0.1 package file mode mismatch: "
                f"{relative} expected 0644, found {file_mode:04o}"
            )
        files.append((logical_prefix / relative, path))
    if observed_directories != EXPECTED_PLATFORM_DIRECTORIES:
        missing = sorted(EXPECTED_PLATFORM_DIRECTORIES - observed_directories)
        unexpected = sorted(observed_directories - EXPECTED_PLATFORM_DIRECTORIES)
        errors.append(
            "v0.1 platform package directory set changed: "
            f"missing={missing}, unexpected={unexpected}"
        )
    return files, errors


def verify_v0_1_package_receipt(package_root: Path) -> list[str]:
    """Anchor a copied v0.1 package to the checked-in immutable receipt."""

    receipt = load_v0_1_receipt()
    group = receipt["groups"]["platformPackage"]
    logical_prefix = validated_relative_path(group["paths"][0])
    files, errors = _regular_files(
        Path(package_root),
        logical_prefix=logical_prefix,
        ignored=receipt["ignored"],
    )
    if len(files) != group["fileCount"]:
        errors.append(
            "v0.1 platform package file set changed: "
            f"expected {group['fileCount']}, found {len(files)}"
        )
    actual = aggregate_sha256(files)
    if actual != group["sha256"]:
        errors.append(
            "v0.1 platform package bytes do not match the immutable receipt: "
            f"expected {group['sha256']}, found {actual}"
        )
    return errors


def verify_v0_1_repository_receipt() -> list[str]:
    """Verify every checked-in v0.1 group without executing a current scorer."""

    receipt = load_v0_1_receipt()
    errors: list[str] = []
    for name, group in receipt["groups"].items():
        collected: dict[PurePosixPath, Path] = {}
        for raw_entry in group["paths"]:
            relative_entry = validated_relative_path(raw_entry)
            entry = REPO_ROOT.joinpath(*relative_entry.parts)
            if not _repository_path_has_safe_ancestors(
                relative_entry,
                group_name=name,
                errors=errors,
            ):
                continue
            entry_stat = entry.lstat()
            if stat.S_ISDIR(entry_stat.st_mode):
                entry_mode = stat.S_IMODE(entry_stat.st_mode)
                if entry_mode != 0o755:
                    errors.append(
                        f"v0.1 {name} directory mode mismatch: {relative_entry} "
                        f"expected 0755, found {entry_mode:04o}"
                    )
            candidates = entry.rglob("*") if entry.is_dir() else (entry,)
            for candidate in candidates:
                relative = PurePosixPath(candidate.relative_to(REPO_ROOT).as_posix())
                if candidate.is_symlink():
                    errors.append(f"v0.1 {name} path is a symlink: {relative}")
                    continue
                if name == "platformPackage" and (
                    "__pycache__" in relative.parts
                    or relative.name.endswith((".pyc", ".pyo"))
                ):
                    errors.append(
                        "importable bytecode is forbidden in immutable v0.1 "
                        f"platform package: {relative}"
                    )
                    continue
                if is_ignored(relative, receipt["ignored"]):
                    continue
                candidate_stat = candidate.lstat()
                mode = candidate_stat.st_mode
                if stat.S_ISDIR(mode):
                    directory_mode = stat.S_IMODE(mode)
                    if directory_mode != 0o755:
                        errors.append(
                            f"v0.1 {name} directory mode mismatch: {relative} "
                            f"expected 0755, found {directory_mode:04o}"
                        )
                    continue
                if not stat.S_ISREG(mode):
                    errors.append(f"v0.1 {name} path is not a regular file: {relative}")
                    continue
                if candidate_stat.st_nlink != 1:
                    errors.append(
                        f"v0.1 {name} path is hard-linked: {relative} "
                        f"(link count {candidate_stat.st_nlink})"
                    )
                    continue
                file_mode = stat.S_IMODE(mode)
                if file_mode != 0o644:
                    errors.append(
                        f"v0.1 {name} file mode mismatch: {relative} "
                        f"expected 0644, found {file_mode:04o}"
                    )
                if relative in collected:
                    errors.append(f"v0.1 {name} receipt paths overlap at {relative}")
                    continue
                collected[relative] = candidate
        files = sorted(collected.items(), key=lambda item: item[0].as_posix())
        if len(files) != group["fileCount"]:
            errors.append(
                f"v0.1 {name} file set changed: expected {group['fileCount']}, "
                f"found {len(files)}"
            )
        actual = aggregate_sha256(files)
        if actual != group["sha256"]:
            errors.append(
                f"v0.1 {name} bytes changed: expected {group['sha256']}, found {actual}"
            )
    return errors


def protected_v0_1_paths() -> list[tuple[Path, bool]]:
    protected: list[tuple[Path, bool]] = [(RECEIPT_PATH.resolve(strict=False), False)]
    for group in load_v0_1_receipt()["groups"].values():
        for raw_entry in group["paths"]:
            relative = validated_relative_path(raw_entry)
            path = REPO_ROOT.joinpath(*relative.parts).resolve(strict=False)
            protected.append((path, raw_entry in IMMUTABLE_TREE_PATHS))
    return protected


def _identity(metadata: os.stat_result) -> tuple[int, int]:
    return metadata.st_dev, metadata.st_ino


def _protected_v0_1_identity_sets() -> tuple[
    set[tuple[int, int]], set[tuple[int, int]], set[tuple[int, int]]
]:
    """Return protected file, directory, and protected-ancestor identities."""

    protected_files: set[tuple[int, int]] = set()
    protected_directories: set[tuple[int, int]] = set()
    protected_ancestors: set[tuple[int, int]] = set()
    for protected, is_tree in protected_v0_1_paths():
        entries = [protected]
        if is_tree:
            try:
                entries.extend(protected.rglob("*"))
            except OSError as exc:
                raise ValueError(
                    f"could not inspect immutable Aleph-Bench v0.1 tree {protected}"
                ) from exc
        for entry in entries:
            try:
                metadata = entry.lstat()
            except OSError as exc:
                raise ValueError(
                    f"immutable Aleph-Bench v0.1 path is unavailable: {entry}"
                ) from exc
            if stat.S_ISLNK(metadata.st_mode):
                raise ValueError(
                    f"immutable Aleph-Bench v0.1 path must not be a symlink: {entry}"
                )
            if stat.S_ISDIR(metadata.st_mode):
                protected_directories.add(_identity(metadata))
            elif stat.S_ISREG(metadata.st_mode):
                protected_files.add(_identity(metadata))
            else:
                raise ValueError(
                    f"immutable Aleph-Bench v0.1 path has an unsafe file type: {entry}"
                )

        ancestor_start = protected if is_tree else protected.parent
        for ancestor in (ancestor_start, *ancestor_start.parents):
            try:
                metadata = ancestor.stat()
            except OSError as exc:
                raise ValueError(
                    "could not inspect an immutable Aleph-Bench v0.1 path ancestor"
                ) from exc
            if stat.S_ISDIR(metadata.st_mode):
                protected_ancestors.add(_identity(metadata))
    return protected_files, protected_directories, protected_ancestors


def assert_not_v0_1_write(path: Path, *, recursive: bool = False) -> None:
    """Reject a prospective write that could mutate immutable v0.1 bytes."""

    requested = Path(path).absolute()
    target = requested.resolve(strict=False)
    for protected, is_directory in protected_v0_1_paths():
        inside_protected = target == protected or (
            is_directory and target.is_relative_to(protected)
        )
        contains_protected = recursive and protected.is_relative_to(target)
        if inside_protected or contains_protected:
            raise ValueError(
                f"refusing to write {target}: Aleph-Bench v0.1 path "
                f"{protected} is immutable"
            )

    protected_files, protected_directories, protected_ancestors = (
        _protected_v0_1_identity_sets()
    )
    try:
        target_metadata = requested.lstat()
    except FileNotFoundError:
        target_metadata = None
    except OSError as exc:
        raise ValueError(f"could not safely inspect output path {requested}") from exc

    if target_metadata is not None:
        target_identity = _identity(target_metadata)
        if stat.S_ISLNK(target_metadata.st_mode):
            raise ValueError(f"refusing to write through output symlink: {requested}")
        if target_identity in protected_files or target_identity in protected_directories:
            raise ValueError(
                f"refusing to write {requested}: it aliases immutable Aleph-Bench v0.1 bytes"
            )
        if recursive:
            if not stat.S_ISDIR(target_metadata.st_mode):
                raise ValueError(f"recursive output path must be a directory: {requested}")
            if target_identity in protected_ancestors:
                raise ValueError(
                    f"refusing recursive write {requested}: it contains immutable "
                    "Aleph-Bench v0.1 paths"
                )
        else:
            if (
                not stat.S_ISREG(target_metadata.st_mode)
                or target_metadata.st_nlink != 1
            ):
                raise ValueError(
                    f"output must be a singly linked regular file: {requested}"
                )

    for ancestor in requested.parents:
        try:
            ancestor_metadata = ancestor.stat()
        except FileNotFoundError:
            continue
        except OSError as exc:
            raise ValueError(f"could not safely inspect output ancestor {ancestor}") from exc
        if _identity(ancestor_metadata) in protected_directories:
            raise ValueError(
                f"refusing to write {requested}: output is inside an immutable "
                "Aleph-Bench v0.1 directory"
            )


def safe_write_bytes(path: Path, content: bytes, *, mode: int = 0o600) -> None:
    """Atomically replace a non-v0.1 file without following the output entry."""

    if isinstance(mode, bool) or not isinstance(mode, int) or not 0 <= mode <= 0o777:
        raise ValueError("output mode must be an integer between 0000 and 0777")
    target = Path(path).absolute()
    assert_not_v0_1_write(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    assert_not_v0_1_write(target)

    directory_flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(
        os, "O_NOFOLLOW", 0
    )
    try:
        parent_descriptor = os.open(target.parent, directory_flags)
    except OSError as exc:
        raise ValueError(f"could not safely open output directory {target.parent}") from exc

    temporary_name = f".{target.name}.{os.getpid()}.{secrets.token_hex(8)}.tmp"
    temporary_descriptor: int | None = None
    try:
        try:
            existing_metadata = os.stat(
                target.name,
                dir_fd=parent_descriptor,
                follow_symlinks=False,
            )
        except FileNotFoundError:
            existing_metadata = None
        if existing_metadata is not None and (
            not stat.S_ISREG(existing_metadata.st_mode)
            or existing_metadata.st_nlink != 1
        ):
            raise ValueError(f"output must be a singly linked regular file: {target}")

        creation_mode = mode if existing_metadata is None else 0o600
        temporary_descriptor = os.open(
            temporary_name,
            os.O_WRONLY
            | os.O_CREAT
            | os.O_EXCL
            | getattr(os, "O_NOFOLLOW", 0),
            creation_mode,
            dir_fd=parent_descriptor,
        )
        if existing_metadata is not None:
            # Preserve an existing file's permissions; never broaden them.
            os.fchmod(temporary_descriptor, stat.S_IMODE(existing_metadata.st_mode))
        with os.fdopen(temporary_descriptor, "wb") as handle:
            temporary_descriptor = None
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())

        assert_not_v0_1_write(target)
        os.replace(
            temporary_name,
            target.name,
            src_dir_fd=parent_descriptor,
            dst_dir_fd=parent_descriptor,
        )
        os.fsync(parent_descriptor)
    finally:
        if temporary_descriptor is not None:
            os.close(temporary_descriptor)
        try:
            os.unlink(temporary_name, dir_fd=parent_descriptor)
        except FileNotFoundError:
            pass
        finally:
            os.close(parent_descriptor)


def safe_write_text(
    path: Path,
    content: str,
    *,
    encoding: str = "utf-8",
    mode: int = 0o600,
) -> None:
    safe_write_bytes(path, content.encode(encoding), mode=mode)
