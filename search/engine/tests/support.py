"""Shared helpers for the artifact kernel tests.

These helpers build demo bundles in temporary directories and rewrite bundle
files on disk to produce adversarial corruption modes. Everything produced by
these helpers is a fixture, never model evidence.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any, Callable, Mapping

from search.engine.archive import _atomic_write
from search.engine.canonical import canonical_bytes, canonical_json, digest_bytes
from search.engine.events import Event, event_from_canonical, stream_digest
from search.engine.fixtures.demo import build_demo_bundle

REPO_ROOT = Path(__file__).resolve().parents[3]


def fresh_tmpdir() -> Path:
    return Path(tempfile.mkdtemp(prefix="aleph-engine-test-"))


def make_demo_bundle(tmp: Path, name: str = "bundle") -> Path:
    root = tmp / name
    return build_demo_bundle(root)


def read_event_records(root: Path) -> list[dict[str, Any]]:
    text = (root / "events.jsonl").read_text(encoding="utf-8")
    return [json.loads(line) for line in text.splitlines() if line.strip()]


_OVERRIDE_KEY_MAP = {
    "event_id": "eventId",
    "event_type": "eventType",
    "schema_version": "schemaVersion",
    "parent_event_ids": "parentEventIds",
    "blob_digests": "blobDigests",
}


def rebuild_event(event: Event, **overrides: Any) -> Event:
    """Rebuild an event with overridden fields; content digest is recomputed.

    Overrides use the dataclass field names; they are mapped to the canonical
    record keys. The stale ``contentDigest`` is dropped and recomputed by the
    ``Event`` constructor, so verification errors isolate the mutation itself.
    """
    canonical = event.to_canonical()
    canonical.update({_OVERRIDE_KEY_MAP.get(key, key): value for key, value in overrides.items()})
    canonical.pop("contentDigest", None)
    return Event(
        event_id=canonical["eventId"],
        sequence=canonical["sequence"],
        event_type=canonical["eventType"],
        phase=canonical["phase"],
        payload=canonical["payload"],
        parent_event_ids=tuple(canonical["parentEventIds"]),
        blob_digests=tuple(canonical["blobDigests"]),
        schema_version=canonical["schemaVersion"],
    )


def rewrite_stream(root: Path, mutations: Mapping[int, Callable[[Event], Event]]) -> None:
    """Rewrite ``events.jsonl`` with mutated events and a consistent manifest digest.

    ``mutations`` maps sequence numbers to functions that take the original
    event and return a rebuilt (possibly changed) event. The manifest stream
    digest is recomputed so verification errors isolate the mutation itself.
    """
    records = read_event_records(root)
    events = [event_from_canonical(record) for record in records]
    for sequence, mutate in mutations.items():
        events[sequence] = mutate(events[sequence])
    text = "".join(canonical_json(event.to_canonical()) + "\n" for event in events)
    _atomic_write(root / "events.jsonl", text.encode("utf-8"))
    rewrite_manifest_stream_digest(root, stream_digest(events))


def rewrite_manifest_stream_digest(root: Path, stream_digest_value: str) -> None:
    payload = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    payload["streamDigest"] = stream_digest_value
    _atomic_write(root / "manifest.json", canonical_bytes(payload) + b"\n")


def rewrite_blob_file(root: Path, blob_digest: str, payload: bytes) -> str:
    """Overwrite (or create) one blob file with new bytes; returns the new digest."""
    new_digest = digest_bytes(payload)
    path = root / "blobs/sha256" / new_digest.split(":", 1)[1]
    _atomic_write(path, payload)
    return new_digest


def mutate_receipt_blob(
    root: Path,
    event_sequence: int,
    mutate: Callable[[dict[str, Any]], dict[str, Any]],
) -> str:
    """Replace the first receipt blob of an event with a mutated receipt.

    The event's ``blob_digests`` and content digest are recomputed, and the
    manifest stream digest is refreshed, so verification errors isolate the
    receipt-level mutation. Returns the new blob digest.
    """
    records = read_event_records(root)
    events = [event_from_canonical(record) for record in records]
    event = events[event_sequence]
    old_digest = event.blob_digests[0]
    path = root / "blobs/sha256" / old_digest.split(":", 1)[1]
    receipt = json.loads(path.read_text(encoding="utf-8"))
    mutated = mutate(dict(receipt))
    new_payload = canonical_bytes(mutated)
    new_digest = rewrite_blob_file(root, old_digest, new_payload)
    blobs = list(event.blob_digests)
    blobs[0] = new_digest
    events[event_sequence] = rebuild_event(event, blob_digests=blobs)
    text = "".join(canonical_json(item.to_canonical()) + "\n" for item in events)
    _atomic_write(root / "events.jsonl", text.encode("utf-8"))
    rewrite_manifest_stream_digest(root, stream_digest(events))
    return new_digest
