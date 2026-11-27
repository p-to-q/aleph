#!/usr/bin/env python3
"""Read/replay the historical H1 publication; no credentials, uploads or models."""
from __future__ import annotations

import argparse
import concurrent.futures
import datetime
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import stat
import sys
import urllib.parse
import urllib.request

DATASET = "p-to-q/aleph-bench"
BASELINE = "3bccb9d20b4bf4c180e93dc2480c4b8943f5c14c"
MAIN = "045d768ee4f1ade5812b3d2761f5bd8b7c5855a9"
RECEIPT = "h1-publication-receipt.json"
RECEIPT_SHA256 = "0fc4c413934582da80387168f40866e3d0cf5dd21c53ae16343f826c0017a763"
CHANGED = {"README.md", "checksums.sha256", "croissant.json", "package-manifest.json"}
MAX_BYTES = 3 * 1024 * 1024
MAX_FILES = 100
SCHEMA = "aleph-hf-h1-readback/1"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def parse(raw: bytes):
    def pairs(values):
        result = {}
        for key, value in values:
            require(key not in result, "duplicate JSON key: " + key)
            result[key] = value
        return result
    return json.loads(raw, object_pairs_hook=pairs,
                      parse_constant=lambda value: require(False, "nonfinite JSON: " + value))


def safe_path(value: str) -> str:
    require(isinstance(value, str) and bool(value), "empty/nontext path")
    path = PurePosixPath(value)
    require(not path.is_absolute() and path.as_posix() == value
            and bool(path.parts) and all(p not in {".", ".."} for p in path.parts)
            and not any(c in value for c in "\\\x00\r\n"), "unsafe path: " + value)
    return value


def inventory(raw: bytes) -> dict:
    entries = parse(raw)
    require(isinstance(entries, list) and len(entries) <= MAX_FILES, "unbounded inventory")
    files = {}
    for row in entries:
        require(isinstance(row, dict) and row.get("type") in {"file", "directory"}, "invalid tree entry")
        path = safe_path(row["path"])
        if row["type"] == "directory":
            continue
        require(path not in files, "duplicate tree path: " + path)
        require(type(row.get("size")) is int and 0 <= row["size"] <= MAX_BYTES, "invalid file size")
        require(re.fullmatch(r"[0-9a-f]{40}", row.get("oid", "")) is not None, "invalid Git blob")
        require("lfs" not in row, "unexpected LFS object; this historical snapshot uses Git blobs")
        files[path] = row
    require(files and sum(v["size"] for v in files.values()) <= 10 * MAX_BYTES, "invalid inventory size")
    return files


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def bind_blob(raw: bytes, row: dict) -> None:
    require(len(raw) == row["size"], "file size differs: " + row["path"])
    blob = hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()
    require(blob == row["oid"], "Git blob differs: " + row["path"])


def tree_identity(files: dict[str, bytes]) -> dict:
    framed = b"".join(path.encode() + b"\0" + sha(raw).encode() + b"\0"
                      + str(len(raw)).encode() + b"\n"
                      for path, raw in sorted(files.items(), key=lambda item: item[0].encode()))
    return {"fileCount": len(files), "bytes": sum(map(len, files.values())), "sha256": sha(framed)}


def verify_delta(old: dict, new: dict) -> None:
    require(set(new) - set(old) == {RECEIPT} and not set(old) - set(new), "unexpected added/removed files")
    changed = {p for p in old if old[p] != new[p]}
    require(changed == CHANGED, "metadata-only change boundary differs: " + repr(sorted(changed)))


def verify_checksums(raw: bytes, files: dict[str, bytes]) -> None:
    entries = {}
    for line in raw.decode().splitlines():
        require(re.fullmatch(r"[0-9a-f]{64}  .+", line) is not None, "malformed checksum line")
        digest, path = line.split("  ", 1)
        safe_path(path)
        require(path not in entries, "duplicate checksum path")
        require(path in files and sha(files[path]) == digest, "checksum differs: " + path)
        entries[path] = digest
    # The historical checksum inventory intentionally excludes three control
    # files and .gitattributes. The immutable Git trees bind all of them too.
    require(set(entries) == set(files) - {"checksums.sha256", "package-manifest.json", ".gitattributes", RECEIPT},
            "checksum coverage differs")


def read_regular(root: Path, relative: str) -> bytes:
    current = root
    for part in PurePosixPath(safe_path(relative)).parts:
        current = current / part
        require(not current.is_symlink(), "linked snapshot input: " + relative)
    info = current.stat()
    require(stat.S_ISREG(info.st_mode) and info.st_size <= MAX_BYTES, "invalid snapshot input: " + relative)
    raw = current.read_bytes()
    require(len(raw) == info.st_size and len(raw) <= MAX_BYTES, "snapshot input changed: " + relative)
    return raw


def verify(root: Path) -> dict:
    require(root.is_dir() and not root.is_symlink(), "snapshot must be a real directory")
    old_index = inventory(read_regular(root, "baseline-tree.json"))
    new_index = inventory(read_regular(root, "main-tree.json"))
    for leaf, commit in (("baseline-api.json", BASELINE), ("main-api.json", MAIN), ("ending-main-api.json", MAIN)):
        value = parse(read_regular(root, leaf))
        require(isinstance(value, dict) and value.get("sha") == commit and value.get("private") is False
                and value.get("gated") is False and value.get("disabled") is False, "public revision mismatch: " + leaf)
    old, new = {}, {}
    for name, entries, values in (("baseline", old_index, old), ("main", new_index, new)):
        for path, row in entries.items():
            values[path] = read_regular(root, name + "/" + path)
            bind_blob(values[path], row)
    expected = {"baseline-tree.json", "main-tree.json", "baseline-api.json", "main-api.json",
                "ending-main-api.json", "dataset-size.json", "capture.json"}
    expected |= {name + "/" + p for name, values in (("baseline", old), ("main", new)) for p in values}
    observed = set()
    for path in root.rglob("*"):
        require(not path.is_symlink(), "linked snapshot entry")
        if path.is_dir():
            require(any(p.startswith(path.relative_to(root).as_posix() + "/") for p in expected), "extra snapshot directory")
        else:
            require(path.is_file(), "nonregular snapshot entry")
            observed.add(path.relative_to(root).as_posix())
    require(observed == expected, "snapshot file set differs")
    verify_delta(old, new)
    require(sha(new[RECEIPT]) == RECEIPT_SHA256, "unrecognized historical publication receipt")
    receipt = parse(new[RECEIPT])
    require(receipt["baseline"]["mainCommit"] == BASELINE
            and receipt["immutableTag"]["peeledCommit"] == BASELINE, "receipt baseline differs")
    for row in receipt["changedFiles"]:
        for side, files in (("old", old), ("new", new)):
            raw = files[row["path"]]
            require(row[side] == {"bytes": len(raw), "sha256": sha(raw)}, "receipt file binding differs")
    unchanged = tree_identity({p: old[p] for p in old if p not in CHANGED})
    payload = tree_identity({p: raw for p, raw in old.items()
        if p.startswith(("data/", "evidence/", "schemas/")) or p in {"kaggle/_scoring.py", "kaggle/score_outputs.py"}})
    for key, value in (("unchangedExistingTree", unchanged), ("payloadTree", payload)):
        require(all(receipt[key][k] == v for k, v in value.items()), "receipt tree binding differs: " + key)
    verify_checksums(new["checksums.sha256"], new)
    verify_checksums(old["checksums.sha256"], old)
    card = new["README.md"].decode()
    require("historical M0/v0.1" in card and "deterministic mock pipeline outputs" in card
            and "not the current Aleph Bench protocol release" in card, "historical/mock boundary missing")
    require("sameAs" not in parse(new["croissant.json"]), "Croissant sameAs was not removed")
    size = parse(read_regular(root, "dataset-size.json"))
    rows = size["size"]["splits"]
    require(isinstance(rows, list) and len(rows) == 2, "Dataset Server split coverage differs")
    counts = {(r["config"], r["split"]): r["num_rows"] for r in rows}
    require(all(r.get("dataset") == DATASET and type(r.get("num_rows")) is int for r in rows)
            and counts == {("public-s2-items", "test"): 30, ("public-s2-prompts", "test"): 240}
            and size.get("partial") is False and size.get("pending") == [] and size.get("failed") == [],
            "Dataset Server row/status mismatch")
    capture = parse(read_regular(root, "capture.json"))
    return {"schemaVersion": SCHEMA, "status": "ok", "dataset": DATASET, "mainCommit": MAIN,
            "historicalCommit": BASELINE, "historicalTag": "v0.1.0-m0", "capturedAt": capture["capturedAt"],
            "auditorSha256": sha(Path(__file__).read_bytes()),
            "h1ReceiptSha256": RECEIPT_SHA256, "changedExistingPaths": sorted(CHANGED),
            "addedPaths": [RECEIPT], "unchangedExistingTree": unchanged, "payloadTree": payload,
            "snapshotTree": tree_identity({p: read_regular(root, p) for p in expected}),
            "datasetRows": {k[0]: v for k, v in sorted(counts.items())},
            "authentication": "none", "hubWrites": 0, "modelCalls": 0,
            "h2Qualified": False, "protocolAuthorityCutover": False,
            "scope": "public_H1_readback_not_current_write_access_or_H2_qualification"}


def fetch(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "aleph-public-readback/1"})
    with urllib.request.urlopen(request, timeout=35) as response:
        require(response.status == 200 and not response.headers.get("Link"), "incomplete HTTP response")
        raw = response.read(MAX_BYTES + 1)
    require(len(raw) <= MAX_BYTES, "oversized HTTP body")
    return raw


def capture(root: Path) -> None:
    require(not root.resolve().is_relative_to(Path(__file__).resolve().parents[1]),
            "capture must be outside the source checkout")
    root.mkdir(mode=0o700, exist_ok=False)
    api = "https://huggingface.co/api/datasets/" + DATASET
    endpoints = {"main-api.json": api, "baseline-api.json": api + "/revision/v0.1.0-m0",
        "baseline-tree.json": api + "/tree/" + BASELINE + "?recursive=true",
        "main-tree.json": api + "/tree/" + MAIN + "?recursive=true",
        "dataset-size.json": "https://datasets-server.huggingface.co/size?dataset=" + DATASET}
    for name, url in endpoints.items():
        (root / name).write_bytes(fetch(url))
    require(parse((root / "main-api.json").read_bytes())["sha"] == MAIN, "current main differs; review before recapture")
    # Identical Git object IDs in the two exact-revision trees need only one
    # download: the Git blob hash of the downloaded bytes is checked against both.
    jobs = {}
    for name, commit in (("baseline", BASELINE), ("main", MAIN)):
        for path, row in inventory((root / (name + "-tree.json")).read_bytes()).items():
            jobs.setdefault(row["oid"], []).append((name, commit, path, row))
    def download(entries):
        name, commit, path, row = entries[0]
        raw = fetch("https://huggingface.co/datasets/" + DATASET + "/raw/" + commit + "/"
                    + urllib.parse.quote(path, safe="/") + "?download=true")
        for name, _, path, row in entries:
            bind_blob(raw, row)
            dest = root / name / path
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(raw)
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        # Consume every result so failed downloads can never be silently skipped.
        list(pool.map(download, jobs.values()))
    (root / "ending-main-api.json").write_bytes(fetch(api))
    (root / "capture.json").write_text(json.dumps({"capturedAt": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "requests": len(endpoints) + len(jobs) + 1, "authentication": "none"}, indent=2) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--capture-dir", type=Path, help="new external directory; read-only public HTTP capture")
    mode.add_argument("--check", type=Path, help="offline replay of an existing capture; no HTTP")
    args = parser.parse_args()
    try:
        root = args.capture_dir if args.capture_dir is not None else args.check
        if args.capture_dir is not None:
            capture(root)
        report = verify(root)
    except (OSError, ValueError, KeyError, TypeError) as error:
        report = {"schemaVersion": SCHEMA, "status": "failed", "errors": [str(error)], "hubWrites": 0, "modelCalls": 0}
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
