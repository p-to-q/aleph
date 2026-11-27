"""Offline mock snapshot/mutation tests; no Hub credentials or HTTP requests."""
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[3] / "scripts/audit-hf-h1-snapshot.py"
SPEC = importlib.util.spec_from_file_location("hf_h1_audit", SCRIPT)
audit = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(audit)


def encoded(value):
    return (json.dumps(value, sort_keys=True) + "\n").encode()


def checksum(files):
    return "".join(audit.sha(raw) + "  " + p + "\n" for p, raw in sorted(files.items())
        if p not in {"checksums.sha256", "package-manifest.json", ".gitattributes", audit.RECEIPT}).encode()


def index(files):
    return [{"path": p, "type": "file", "size": len(raw),
             "oid": hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()}
            for p, raw in sorted(files.items())]


def mock_snapshot(root):
    old = {"README.md": b"old card", "croissant.json": b'{"sameAs":"dead"}',
           "package-manifest.json": b'{"version":"old"}', "data/target.txt": b"mock-only target"}
    old["checksums.sha256"] = checksum(old)
    new = old | {"README.md": b"historical M0/v0.1; deterministic mock pipeline outputs; not the current Aleph Bench protocol release",
                 "croissant.json": b"{}", "package-manifest.json": b'{"version":"new"}'}
    new["checksums.sha256"] = checksum(new)
    receipt = {"baseline": {"mainCommit": audit.BASELINE}, "immutableTag": {"peeledCommit": audit.BASELINE},
        "changedFiles": [{"path": p, "old": {"bytes": len(old[p]), "sha256": audit.sha(old[p])},
                          "new": {"bytes": len(new[p]), "sha256": audit.sha(new[p])}} for p in sorted(audit.CHANGED)],
        "unchangedExistingTree": audit.tree_identity({p: raw for p, raw in old.items() if p not in audit.CHANGED}),
        "payloadTree": audit.tree_identity({"data/target.txt": old["data/target.txt"]})}
    new[audit.RECEIPT] = encoded(receipt)
    inputs = {"baseline-tree.json": encoded(index(old)), "main-tree.json": encoded(index(new)),
              "capture.json": encoded({"capturedAt": "2026-11-27T00:00:00+00:00"}),
              "dataset-size.json": encoded({"size": {"splits": [
                  {"dataset": audit.DATASET, "config": "public-s2-items", "split": "test", "num_rows": 30},
                  {"dataset": audit.DATASET, "config": "public-s2-prompts", "split": "test", "num_rows": 240}]}, "pending": [], "failed": [], "partial": False})}
    for p, commit in (("baseline-api.json", audit.BASELINE), ("main-api.json", audit.MAIN), ("ending-main-api.json", audit.MAIN)):
        inputs[p] = encoded({"sha": commit, "private": False, "gated": False, "disabled": False})
    for name, files in (("baseline", old), ("main", new)):
        inputs.update({name + "/" + p: raw for p, raw in files.items()})
    for p, raw in inputs.items():
        dest = root / p
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(raw)
    return audit.sha(new[audit.RECEIPT])


class SnapshotAuditTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.receipt_digest = mock_snapshot(self.root)
        self.pin = patch.object(audit, "RECEIPT_SHA256", self.receipt_digest)
        self.pin.start()
        self.addCleanup(self.pin.stop)
        self.net = patch.object(audit, "fetch", side_effect=AssertionError("HTTP forbidden in offline tests"))
        self.net.start()
        self.addCleanup(self.net.stop)

    def test_complete_mock_snapshot_replays_offline(self):
        result = audit.verify(self.root)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["modelCalls"], 0)
        self.assertFalse(result["h2Qualified"])
        self.assertEqual(result["payloadTree"]["fileCount"], 1)

    def test_changed_payload_rejected_even_after_updating_checksum_and_git_tree(self):
        for name in ("baseline", "main"):
            directory = self.root / name
            (directory / "data/target.txt").write_bytes(b"forged-target")
            files = {p.relative_to(directory).as_posix(): p.read_bytes() for p in directory.rglob("*") if p.is_file()}
            files["checksums.sha256"] = checksum(files)
            (directory / "checksums.sha256").write_bytes(files["checksums.sha256"])
            (self.root / (name + "-tree.json")).write_bytes(encoded(index(files)))
        with self.assertRaisesRegex(ValueError, "receipt .*binding differs"):
            audit.verify(self.root)

    def test_extra_snapshot_file_rejected(self):
        (self.root / "extra").write_text("not in the snapshot")
        with self.assertRaisesRegex(ValueError, "file set differs"):
            audit.verify(self.root)

    def test_unexpected_empty_directory_rejected(self):
        (self.root / "extra").mkdir()
        with self.assertRaisesRegex(ValueError, "extra snapshot directory"):
            audit.verify(self.root)

    def test_changed_ending_revision_rejected(self):
        p = self.root / "ending-main-api.json"
        value = audit.parse(p.read_bytes()); value["sha"] = "0" * 40
        p.write_bytes(encoded(value))
        with self.assertRaisesRegex(ValueError, "public revision mismatch"):
            audit.verify(self.root)

    def test_partial_or_duplicate_dataset_server_rows_rejected(self):
        path = self.root / "dataset-size.json"
        original = path.read_bytes()
        for mutation in ("partial", "duplicate", "wrong_dataset"):
            value = audit.parse(original)
            if mutation == "partial":
                value["partial"] = True
            elif mutation == "duplicate":
                value["size"]["splits"].append(value["size"]["splits"][0])
            else:
                value["size"]["splits"][0]["dataset"] = "another/dataset"
            path.write_bytes(encoded(value))
            with self.subTest(mutation=mutation), self.assertRaisesRegex(ValueError, "Dataset Server"):
                audit.verify(self.root)

    def test_nonobject_api_rejected(self):
        (self.root / "main-api.json").write_text("[]")
        with self.assertRaisesRegex(ValueError, "public revision mismatch"):
            audit.verify(self.root)

    def test_linked_input_rejected(self):
        p = self.root / "main/README.md"
        raw = p.read_bytes(); p.unlink()
        external = self.root / "original-card"; external.write_bytes(raw)
        p.symlink_to(external)
        with self.assertRaisesRegex(ValueError, "linked snapshot input"):
            audit.verify(self.root)

    def test_partial_capture_never_verifies(self):
        (self.root / "ending-main-api.json").unlink()
        with self.assertRaises(OSError):
            audit.verify(self.root)

    def test_capture_refuses_existing_output_before_http(self):
        with self.assertRaises(FileExistsError):
            audit.capture(self.root)

    def test_checksum_coverage_and_duplicates_rejected(self):
        files = {"README.md": b"a", "data/x": b"x", "package-manifest.json": b"{}"}
        valid = checksum(files)
        audit.verify_checksums(valid, files)
        for invalid in (valid.splitlines(keepends=True)[0], valid + valid):
            with self.assertRaises(ValueError):
                audit.verify_checksums(invalid, files)

    def test_unsafe_paths_rejected(self):
        for value in ("", ".", "..", "a/../b", "/tmp/x", "a//b", "./a", "a\\b", "a\nx"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                audit.safe_path(value)

    def test_duplicate_json_tree_and_lfs_rejected(self):
        with self.assertRaisesRegex(ValueError, "duplicate JSON key"):
            audit.parse(b'{"a":1,"a":2}')
        row = index({"file": b"x"})[0]
        for values in ([row, row], [row | {"lfs": {"size": 1}}]):
            with self.assertRaises(ValueError):
                audit.inventory(encoded(values))

    def test_git_blob_and_size_bind_actual_bytes(self):
        row = index({"file": b"data"})[0]
        audit.bind_blob(b"data", row)
        for raw in (b"DATA", b"different size"):
            with self.assertRaises(ValueError):
                audit.bind_blob(raw, row)

    def test_payload_changes_are_outside_h1_boundary(self):
        old = {p: b"old" for p in audit.CHANGED} | {"data/x": b"x"}
        new = {p: b"new" for p in audit.CHANGED} | {"data/x": b"x", audit.RECEIPT: b"receipt"}
        audit.verify_delta(old, new)
        with self.assertRaisesRegex(ValueError, "boundary differs"):
            audit.verify_delta(old, new | {"data/x": b"changed"})


if __name__ == "__main__":
    unittest.main()
