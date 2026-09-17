from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path, PurePosixPath
from typing import Any
from unittest.mock import patch

from bench.engine.legacy_v0_1 import (
    assert_not_v0_1_write,
    load_v0_1_receipt,
    safe_write_text,
    verify_v0_1_package_receipt,
    verify_v0_1_repository_receipt,
)


ROOT = Path(__file__).resolve().parents[2]
RECEIPT_PATH = ROOT / "bench/legacy/v0.1-immutable.json"
PLATFORM_PACKAGE = ROOT / "bench/results/platform/m0-mock"
PLATFORM_CONTROL_FILES = {"checksums.sha256", "package-manifest.json"}


def _load_receipt() -> dict[str, Any]:
    return json.loads(RECEIPT_PATH.read_text(encoding="utf-8"))


def _is_ignored(relative_path: PurePosixPath, ignored: dict[str, list[str]]) -> bool:
    return (
        any(part in ignored["directoryNames"] for part in relative_path.parts[:-1])
        or relative_path.name in ignored["fileNames"]
        or any(relative_path.name.endswith(suffix) for suffix in ignored["fileSuffixes"])
    )


def _validated_relative_path(raw_path: str) -> PurePosixPath:
    path = PurePosixPath(raw_path)
    if path.is_absolute() or ".." in path.parts or path.as_posix() != raw_path:
        raise AssertionError(f"unsafe or non-canonical receipt path: {raw_path!r}")
    return path


def _collect_group_files(
    root: Path,
    group: dict[str, Any],
    ignored: dict[str, list[str]],
) -> list[tuple[PurePosixPath, Path]]:
    collected: dict[PurePosixPath, Path] = {}
    for raw_entry in group["paths"]:
        relative_entry = _validated_relative_path(raw_entry)
        entry = root.joinpath(*relative_entry.parts)
        if not entry.exists():
            raise AssertionError(f"declared v0.1 path is missing: {relative_entry}")

        candidates = entry.rglob("*") if entry.is_dir() else (entry,)
        for candidate in candidates:
            relative_candidate = PurePosixPath(candidate.relative_to(root).as_posix())
            if _is_ignored(relative_candidate, ignored):
                continue
            if not candidate.is_file() or candidate.is_symlink():
                continue
            if relative_candidate in collected:
                raise AssertionError(f"overlapping receipt paths include {relative_candidate} twice")
            collected[relative_candidate] = candidate

    return sorted(collected.items(), key=lambda item: item[0].as_posix())


def _aggregate_sha256(files: list[tuple[PurePosixPath, Path]]) -> str:
    aggregate = hashlib.sha256()
    for relative_path, path in files:
        path_bytes = relative_path.as_posix().encode("utf-8")
        content = path.read_bytes()
        aggregate.update(len(path_bytes).to_bytes(4, "big"))
        aggregate.update(path_bytes)
        aggregate.update(len(content).to_bytes(8, "big"))
        aggregate.update(content)
    return aggregate.hexdigest()


def _verify_group(
    root: Path,
    name: str,
    group: dict[str, Any],
    ignored: dict[str, list[str]],
) -> None:
    files = _collect_group_files(root, group, ignored)
    if len(files) != group["fileCount"]:
        raise AssertionError(
            f"v0.1 {name} file set changed: expected {group['fileCount']}, found {len(files)}"
        )
    actual = _aggregate_sha256(files)
    if actual != group["sha256"]:
        raise AssertionError(
            f"v0.1 {name} bytes changed: expected {group['sha256']}, found {actual}"
        )


def _parse_checksums(path: Path) -> dict[str, str]:
    parsed: dict[str, str] = {}
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line:
            continue
        parts = line.split("  ", maxsplit=1)
        if len(parts) != 2 or len(parts[0]) != 64:
            raise AssertionError(f"malformed checksum line {line_number}: {line!r}")
        digest, raw_relative_path = parts
        try:
            int(digest, 16)
        except ValueError as error:
            raise AssertionError(f"invalid SHA-256 on line {line_number}: {digest!r}") from error
        relative_path = _validated_relative_path(raw_relative_path).as_posix()
        if relative_path in parsed:
            raise AssertionError(f"duplicate checksum entry: {relative_path}")
        parsed[relative_path] = digest
    return parsed


class V01ImmutableTests(unittest.TestCase):
    def test_runtime_loader_anchors_exact_receipt_bytes(self) -> None:
        self.assertEqual(load_v0_1_receipt()["sourceCommit"], "ecc3badb3cedeb659dd4a47c8664e725f4d57232")
        with tempfile.TemporaryDirectory() as temporary_directory:
            receipt_path = Path(temporary_directory) / "receipt.json"
            receipt = _load_receipt()
            receipt["sourceCommit"] = "0" * 40
            receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
            with patch("bench.engine.legacy_v0_1.RECEIPT_PATH", receipt_path):
                with self.assertRaisesRegex(ValueError, "receipt bytes changed"):
                    load_v0_1_receipt()

    def test_checked_in_v0_1_groups_match_receipt(self) -> None:
        receipt = _load_receipt()
        self.assertEqual(receipt["formatVersion"], 1)
        self.assertEqual(receipt["protocolVersion"], "0.1")
        self.assertEqual(receipt["sourceCommit"], "ecc3badb3cedeb659dd4a47c8664e725f4d57232")
        self.assertEqual(
            set(receipt["groups"]),
            {"config", "data", "schemas", "results", "platformPackage", "coreTypes"},
        )
        for name, group in receipt["groups"].items():
            with self.subTest(group=name):
                _verify_group(ROOT, name, group, receipt["ignored"])

    def test_cli_output_cannot_overwrite_v0_1_through_a_hardlink(self) -> None:
        protected = ROOT / "bench/results/m0-first-run.json"
        original_digest = hashlib.sha256(protected.read_bytes()).hexdigest()
        with tempfile.TemporaryDirectory() as temporary_directory:
            alias = Path(temporary_directory) / "outside-result.json"
            os.link(protected, alias)
            completed = subprocess.run(
                [
                    str(ROOT / "aleph-bench"),
                    "report",
                    "--result",
                    str(protected),
                    "--out",
                    str(alias),
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(completed.returncode, 2, msg=completed.stderr)
            self.assertIn("aliases immutable Aleph-Bench v0.1", completed.stderr)
            self.assertEqual(
                hashlib.sha256(protected.read_bytes()).hexdigest(),
                original_digest,
            )

    def test_output_guard_uses_inode_identity_for_case_aliases(self) -> None:
        root_alias = ROOT.with_name(ROOT.name.upper())
        protected = ROOT / "bench/results/m0-first-run.json"
        protected_alias = root_alias / "bench/results/m0-first-run.json"
        tree_alias = root_alias / "bench/data/public/s2"
        try:
            aliases_are_supported = (
                protected_alias.exists()
                and protected_alias.samefile(protected)
                and tree_alias.samefile(ROOT / "bench/data/public/s2")
            )
        except OSError:
            aliases_are_supported = False
        if not aliases_are_supported:
            self.skipTest("filesystem is case-sensitive")

        with self.assertRaisesRegex(ValueError, "aliases immutable"):
            assert_not_v0_1_write(protected_alias)
        with self.assertRaisesRegex(ValueError, "inside an immutable"):
            assert_not_v0_1_write(tree_alias / "new-result.json")
        with self.assertRaisesRegex(ValueError, "contains immutable"):
            assert_not_v0_1_write(root_alias, recursive=True)

    def test_atomic_output_rejects_links_and_replaces_regular_files(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            output = root / "nested/result.json"
            safe_write_text(output, "first\n")
            self.assertEqual(output.read_text(encoding="utf-8"), "first\n")
            self.assertEqual(output.stat().st_nlink, 1)
            self.assertEqual(output.stat().st_mode & 0o777, 0o600)
            safe_write_text(output, "second\n")
            self.assertEqual(output.read_text(encoding="utf-8"), "second\n")

            linked_source = root / "linked-source.json"
            linked_source.write_text("keep\n", encoding="utf-8")
            linked_output = root / "linked-output.json"
            os.link(linked_source, linked_output)
            with self.assertRaisesRegex(ValueError, "singly linked regular file"):
                safe_write_text(linked_output, "replace\n")
            self.assertEqual(linked_source.read_text(encoding="utf-8"), "keep\n")

            symlink_output = root / "symlink-output.json"
            symlink_output.symlink_to(linked_source)
            with self.assertRaisesRegex(ValueError, "output symlink"):
                safe_write_text(symlink_output, "replace\n")
            self.assertEqual(linked_source.read_text(encoding="utf-8"), "keep\n")

    def test_atomic_output_obeys_umask_and_never_broadens_existing_mode(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            original_umask = os.umask(0o077)
            try:
                fresh = root / "fresh.txt"
                safe_write_text(fresh, "fresh\n", mode=0o644)
                self.assertEqual(fresh.stat().st_mode & 0o777, 0o600)

                existing = root / "existing.txt"
                existing.write_text("old\n", encoding="utf-8")
                existing.chmod(0o600)
                safe_write_text(existing, "new\n", mode=0o644)
                self.assertEqual(existing.stat().st_mode & 0o777, 0o600)
                self.assertEqual(existing.read_text(encoding="utf-8"), "new\n")
            finally:
                os.umask(original_umask)

    def test_repository_receipt_rejects_mode_drift(self) -> None:
        receipt = _load_receipt()
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_root = Path(temporary_directory)
            for group in receipt["groups"].values():
                for raw_entry in group["paths"]:
                    relative = _validated_relative_path(raw_entry)
                    source = ROOT.joinpath(*relative.parts)
                    destination = temporary_root.joinpath(*relative.parts)
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    if source.is_dir():
                        shutil.copytree(source, destination)
                    else:
                        shutil.copy2(source, destination)
            with patch("bench.engine.legacy_v0_1.REPO_ROOT", temporary_root):
                self.assertEqual(verify_v0_1_repository_receipt(), [])
                drifted = temporary_root / "bench/config/frozen_ladder.json"
                drifted.chmod(0o777)
                errors = verify_v0_1_repository_receipt()
            self.assertTrue(
                any("file mode mismatch" in error for error in errors),
                msg=errors,
            )

            drifted.chmod(0o644)
            for relative_root in (
                "bench/data/public/s2",
                "bench/results/platform/m0-mock",
            ):
                with self.subTest(relative_root=relative_root):
                    root = temporary_root / relative_root
                    root.chmod(0o777)
                    with patch("bench.engine.legacy_v0_1.REPO_ROOT", temporary_root):
                        errors = verify_v0_1_repository_receipt()
                    self.assertTrue(
                        any("directory mode mismatch" in error for error in errors),
                        msg=errors,
                    )
                    root.chmod(0o755)

            data_root = temporary_root / "bench/data"
            external_data = temporary_root / "external-data"
            data_root.rename(external_data)
            data_root.symlink_to(external_data, target_is_directory=True)
            with patch("bench.engine.legacy_v0_1.REPO_ROOT", temporary_root):
                errors = verify_v0_1_repository_receipt()
            self.assertTrue(
                any("symlink component" in error for error in errors),
                msg=errors,
            )

    def test_directory_group_rejects_missing_extra_and_byte_drift(self) -> None:
        receipt = _load_receipt()
        group = receipt["groups"]["data"]
        ignored = receipt["ignored"]
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_root = Path(temporary_directory)
            copied_data = temporary_root / "bench/data/public/s2"
            copied_data.parent.mkdir(parents=True)
            shutil.copytree(ROOT / "bench/data/public/s2", copied_data)
            _verify_group(temporary_root, "data", group, ignored)

            missing = copied_data / "s2-001.json"
            original = missing.read_bytes()
            missing.unlink()
            with self.assertRaisesRegex(AssertionError, "file set changed"):
                _verify_group(temporary_root, "data", group, ignored)
            missing.write_bytes(original)

            extra = copied_data / "unexpected.json"
            extra.write_text("{}\n", encoding="utf-8")
            with self.assertRaisesRegex(AssertionError, "file set changed"):
                _verify_group(temporary_root, "data", group, ignored)
            extra.unlink()

            drifted = copied_data / "s2-001.json"
            drifted.write_bytes(drifted.read_bytes() + b"\n")
            with self.assertRaisesRegex(AssertionError, "bytes changed"):
                _verify_group(temporary_root, "data", group, ignored)

    def test_directory_group_ignores_only_declared_platform_noise(self) -> None:
        receipt = _load_receipt()
        group = receipt["groups"]["data"]
        ignored = receipt["ignored"]
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_root = Path(temporary_directory)
            copied_data = temporary_root / "bench/data/public/s2"
            copied_data.parent.mkdir(parents=True)
            shutil.copytree(ROOT / "bench/data/public/s2", copied_data)
            (copied_data / ".DS_Store").write_bytes(b"ignored")
            cache = copied_data / "__pycache__"
            cache.mkdir()
            (cache / "unexpected.txt").write_text("ignored", encoding="utf-8")
            (copied_data / "generated.pyc").write_bytes(b"ignored")
            _verify_group(temporary_root, "data", group, ignored)

    def test_v0_1_platform_manifest_and_checksums_are_closed_world(self) -> None:
        ignored = _load_receipt()["ignored"]
        package_manifest = json.loads(
            (PLATFORM_PACKAGE / "package-manifest.json").read_text(encoding="utf-8")
        )
        artifacts = package_manifest["artifacts"]
        self.assertEqual(len(artifacts), 32)

        manifest_by_path: dict[str, dict[str, Any]] = {}
        for artifact in artifacts:
            relative_path = _validated_relative_path(artifact["path"]).as_posix()
            self.assertNotIn(relative_path, manifest_by_path)
            manifest_by_path[relative_path] = artifact

        checksums = _parse_checksums(PLATFORM_PACKAGE / "checksums.sha256")
        actual_paths = {
            path.relative_to(PLATFORM_PACKAGE).as_posix()
            for path in PLATFORM_PACKAGE.rglob("*")
            if path.is_file()
            and not path.is_symlink()
            and not _is_ignored(
                PurePosixPath(path.relative_to(PLATFORM_PACKAGE).as_posix()), ignored
            )
        }
        self.assertEqual(actual_paths - PLATFORM_CONTROL_FILES, set(manifest_by_path))
        self.assertEqual(set(checksums), set(manifest_by_path))

        for relative_path, artifact in manifest_by_path.items():
            with self.subTest(path=relative_path):
                content = (PLATFORM_PACKAGE / relative_path).read_bytes()
                digest = hashlib.sha256(content).hexdigest()
                self.assertEqual(len(content), artifact["bytes"])
                self.assertEqual(digest, artifact["sha256"])
                self.assertEqual(digest, checksums[relative_path])

    def test_copied_platform_package_rejects_bytecode_and_extra_directories(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            copied = Path(temporary_directory) / "package"
            shutil.copytree(PLATFORM_PACKAGE, copied)
            self.assertEqual(verify_v0_1_package_receipt(copied), [])

            cache = copied / "kaggle/__pycache__"
            cache.mkdir()
            (cache / "_scoring.cpython-313.pyc").write_bytes(b"untrusted bytecode")
            errors = verify_v0_1_package_receipt(copied)
            self.assertTrue(
                any("importable bytecode is forbidden" in error for error in errors),
                msg=errors,
            )

            shutil.rmtree(cache)
            (copied / "unexpected-empty-directory").mkdir()
            errors = verify_v0_1_package_receipt(copied)
            self.assertTrue(
                any("directory set changed" in error for error in errors),
                msg=errors,
            )

            (copied / "unexpected-empty-directory").rmdir()
            readme = copied / "README.md"
            outside = Path(temporary_directory) / "outside-readme"
            outside.write_bytes(readme.read_bytes())
            readme.unlink()
            os.link(outside, readme)
            errors = verify_v0_1_package_receipt(copied)
            self.assertTrue(
                any("hard-linked file is forbidden" in error for error in errors),
                msg=errors,
            )

            readme.unlink()
            shutil.copy2(PLATFORM_PACKAGE / "README.md", readme)
            executable = copied / "kaggle/score_outputs.py"
            executable.chmod(0o777)
            errors = verify_v0_1_package_receipt(copied)
            self.assertTrue(
                any("file mode mismatch" in error for error in errors),
                msg=errors,
            )


if __name__ == "__main__":
    unittest.main()
