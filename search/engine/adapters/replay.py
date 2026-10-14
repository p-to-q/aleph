"""Standard-library replay kernel for Aleph run bundles.

Replay is the semantic twin of a live run: the same event stream, manifest, and
blobs produce the same archive view, views, confirmation view, and resource
ledger — byte-identically. Replay never calls an adapter: every receipt is
read from its content-addressed blob and validated against its typed contract.

An interrupted run can be resumed with ``archive.RunBundle.open_for_append``;
the events appended after the interruption carry consecutive sequences, so the
final stream is exactly the stream an uninterrupted run would have written.
Replaying that stream therefore yields the same digests as an uninterrupted
run, which the test suite pins.

The verifier must not import the scheduler/search module, and it does not: this
module depends only on the artifact kernel itself.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from typing import Mapping

from ..archive import (
    BundleSnapshot,
    DerivedState,
    RunManifest,
    derive_state,
    read_bundle,
)
from ..events import Event


class ReplayError(ValueError):
    """Raised when a bundle cannot be replayed into derived state."""


@dataclass(frozen=True)
class ReplayResult:
    """The fully replayed semantic state of a bundle."""

    snapshot: BundleSnapshot
    derived: DerivedState

    @property
    def root(self) -> Path:
        return self.snapshot.root

    @property
    def digests(self) -> dict[str, str]:
        """Digests of the four materialized views, as replay derives them."""
        return dict(self.derived.digests)


def replay_stream(
    manifest: RunManifest,
    events: tuple[Event, ...],
    blobs: Mapping[str, bytes],
) -> DerivedState:
    """Derive state from an in-memory manifest, event stream, and blob map."""
    if not isinstance(manifest, RunManifest):
        raise ReplayError("replay requires a RunManifest")
    if not isinstance(events, tuple) or not all(isinstance(item, Event) for item in events):
        raise ReplayError("replay requires a tuple of Event instances")
    if not isinstance(blobs, Mapping):
        raise ReplayError("replay requires a blob map")
    try:
        return derive_state(manifest, events, blobs)
    except ValueError as error:
        raise ReplayError(f"replay failed: {error}") from error


def replay(root: Path) -> ReplayResult:
    """Replay a bundle from disk, failing closed on any inconsistency.

    No adapter is invoked, no file is modified, and no terminal logical call is
    reissued: the result is derived exclusively from the recorded stream.
    """
    try:
        snapshot = read_bundle(root)
    except ValueError as error:
        raise ReplayError(f"cannot read bundle: {error}") from error
    try:
        derived = derive_state(snapshot.manifest, snapshot.events, snapshot.blobs)
    except ValueError as error:
        raise ReplayError(f"cannot derive state: {error}") from error
    return ReplayResult(snapshot=snapshot, derived=derived)
