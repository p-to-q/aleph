"""Measurement-lossless ``AlephRun`` projection for Aleph run bundles (PR B).

The exporter projects a closed, verified bundle into the strict
``schemas/aleph-run.schema.json`` shape and writes two files under
``exports/``:

- ``aleph-run.json`` — the product-facing projection, validated against the
  strict schema before writing;
- ``aleph-run-projection.json`` — the projection record: ``artifactRef``
  (bundle stream digest + projection digest), a complete per-leaf source map,
  the omitted (unevaluated) candidate ids, and the documented projection
  policy.

Projection rules, all deterministic and fail-closed:

- Every projected value is a byte copy of a bundle leaf, a documented render
  of one (canonical JSON), or a documented derivation from bundle leaves; the
  source map records which, per leaf, so nothing is silently invented.
- ``createdAt`` is byte-copied from ``run_started.payload.createdAt`` (a
  caller-declared run timestamp; the kernel never stores wall-clock time). The
  strict schema requires the field, and the exporter never invents a date: a
  bundle without a declared timestamp fails export with a typed error. This is
  the documented date-free policy aligned with the strict schema.
- Only a run that closed as ``completed`` is exportable: an aborted run fails
  closed with a typed error, and the verifier refuses to attest exports it
  cannot re-derive.
- Candidates in the projection are exactly the archived candidates that have a
  discovery evaluation receipt. Unevaluated archives — for example the tagged
  explicit-reconstruction control, which is archived then policy-excluded —
  carry no measured scores, so they are not projected; they stay in the linked
  bundle and are listed in ``omittedCandidateIds``.
- ``fit``/``stability``/``compression``/``leakage`` are byte-copied from the
  candidate's final discovery evaluation receipt metrics; ``nll`` is copied
  when declared. ``output`` is the receipt's ``outputs.text``. A missing or
  malformed required value fails the export, never defaults.
- ``prompt`` copies a single message verbatim and renders multiple messages as
  ``role: content`` lines joined by blank lines (a display projection; the
  exact coordinate stays in the bundle).
- ``label`` is a presentation label derived from the candidate role and
  proposal mode, matching the product fixture conventions.
- ``selectedCandidateId`` is the confirmed candidate when confirmation says
  ``confirmed``, else the top-ranked frozen-shortlist candidate; a run that
  never promoted any candidate fails export.
- ``config`` is copied from the declared evidence: the frozen configuration
  (pinned by the scheduler as a content-addressed blob on ``search_frozen``)
  and the manifest's model manifest.

Replay never calls adapters and the verifier imports no scheduler: this module
reads receipts through the strict typed parsers and reads the frozen config
as raw pinned JSON, so it imports only the artifact kernel.

Prior practice. The export pair follows the attestation shape standardized
by in-toto and SLSA: the bundle is the subject (matched purely by digest),
the projection record (projection + per-leaf source map + omitted candidates
+ policy) is the predicate, and ``artifactRef`` binds the two; SLSA v1.0
``buildDefinition`` / ``runDetails`` are the vocabulary reference. The
``sha256:`` prefix is our spelling of a digest set (``{ALGORITHM: HEX}``).
Structural mapping only: no dependency on either tool. See
``docs/research/engine-and-benchmark-practice-review.md`` (§1).

Pure standard library. No MLX, no network, no clock, no randomness.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from .archive import (
    ArchiveError,
    EXPORT_NAMES,
    RunManifest,
    _atomic_write,
    derive_state,
    read_bundle,
)
from .canonical import canonical_bytes, canonical_json, digest, digest_bytes, is_digest
from .contracts import (
    Candidate,
    evaluation_receipt_from_canonical,
    proposal_receipt_from_canonical,
)
from .events import Event

PROJECTION_RECORD_SCHEMA_VERSION = "aleph-engine-projection/0.1.0"
ARTIFACT_REF_SCHEMA_VERSION = "aleph-artifact-ref/0.1.0"

DEFAULT_SCHEMA_PATH = Path(__file__).resolve().parents[2] / "schemas" / "aleph-run.schema.json"

OBSERVATION_MODES = ("fixture", "mock", "black_box", "white_box", "simulated")
RUN_MODES = ("unrestricted", "non_leaking")

_LABEL_ROLE = "Explicit Reconstruction"
_LABEL_BY_MODE = {
    "seed": "Seed",
    "delete": "Delete",
    "rewrite": "Rewrite",
    "repair": "Repair",
    "reference": "Reference",
}


class ExportError(ValueError):
    """Raised when a bundle cannot be projected without loss or invention."""


@dataclass(frozen=True)
class ProjectionRecord:
    """Everything the exporter derives: projection, sidecar, and digests."""

    run_id: str
    projection: dict[str, Any]
    projection_record: dict[str, Any]
    artifact_ref: dict[str, Any]
    omitted_candidate_ids: tuple[str, ...]
    digests: tuple[tuple[str, str], ...]


@dataclass(frozen=True)
class ExportResult:
    """What :func:`export_aleph_run` wrote into ``exports/``."""

    root: Path
    run_id: str
    projection: dict[str, Any]
    projection_record: dict[str, Any]
    omitted_candidate_ids: tuple[str, ...]
    digests: tuple[tuple[str, str], ...]


def candidate_label(role: str, proposal_mode: str) -> str:
    """The deterministic presentation label for a candidate role and mode."""
    if role == "explicit_reconstruction":
        return _LABEL_ROLE
    return _LABEL_BY_MODE[proposal_mode]


def _schema_path_or(schema_path: Path | None) -> Path:
    return Path(schema_path) if schema_path is not None else DEFAULT_SCHEMA_PATH


def load_target_blob(
    root: Path, manifest: RunManifest, blobs: Mapping[str, bytes]
) -> dict[str, bytes]:
    """Return ``blobs`` plus the manifest-declared target blob, verified.

    ``read_bundle`` resolves only event-referenced blobs; the target blob is
    referenced by the manifest, so both the exporter and the verifier merge it
    in here before projecting.
    """
    merged = dict(blobs)
    target_digest = manifest.target_blob_digest
    if target_digest and target_digest not in merged:
        path = root / "blobs" / "sha256" / target_digest.split(":", 1)[1]
        try:
            payload = path.read_bytes()
        except OSError as error:
            raise ExportError(f"declared target blob {target_digest} is missing: {error}") from error
        if digest_bytes(payload) != target_digest:
            raise ExportError("target blob content does not match its declared digest")
        merged[target_digest] = payload
    return merged


# ---------------------------------------------------------------------------
# Strict-schema structural validation (stdlib only, no jsonschema dependency)
# ---------------------------------------------------------------------------

_SUPPORTED_TYPES = frozenset(
    {"string", "integer", "number", "boolean", "array", "object"}
)

_SCHEMA_KEYWORDS = frozenset(
    {
        "$schema",
        "$id",
        "title",
        "description",
        "type",
        "enum",
        "required",
        "properties",
        "additionalProperties",
        "items",
        "minimum",
        "maximum",
        "$defs",
        "$ref",
    }
)


def validate_against_schema(value: Any, schema_path: Path) -> list[str]:
    """Validate ``value`` against ``aleph-run.schema.json``, returning errors.

    A small interpreter for the draft 2020-12 subset the schema uses
    (``$ref``/``$defs``, types, ``enum``, ``required``, ``properties``,
    ``additionalProperties``, ``items``, ``minimum``/``maximum``). Keywords
    outside the supported subset fail closed, so a future schema feature can
    never be silently skipped.
    """
    try:
        schema = json.loads(Path(schema_path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ExportError(f"cannot read projection schema {schema_path}: {error}") from error
    if not isinstance(schema, Mapping):
        raise ExportError("projection schema must be a JSON object")
    errors: list[str] = []
    _validate_subschema(schema, value, "$", schema, errors)
    return errors


def _validate_subschema(
    definition: Any, value: Any, path: str, root: Mapping[str, Any], errors: list[str]
) -> None:
    if not isinstance(definition, Mapping):
        errors.append(f"{path}: schema definition must be an object")
        return
    unknown = set(definition) - _SCHEMA_KEYWORDS
    if unknown:
        errors.append(f"{path}: schema uses unsupported keywords {sorted(unknown)} (fail closed)")
        return
    if "$ref" in definition:
        ref = definition["$ref"]
        if not isinstance(ref, str) or not ref.startswith("#/"):
            errors.append(f"{path}: unsupported schema reference {ref!r}")
            return
        target: Any = root
        for part in ref[2:].split("/"):
            if not isinstance(target, Mapping) or part not in target:
                errors.append(f"{path}: unresolved schema reference {ref!r}")
                return
            target = target[part]
        _validate_subschema(target, value, path, root, errors)
        return
    enum_values = definition.get("enum")
    if enum_values is not None:
        if not isinstance(enum_values, list):
            errors.append(f"{path}: unsupported 'enum' value (fail closed)")
        elif value not in enum_values:
            errors.append(f"{path}: expected one of {enum_values}")
    typ = definition.get("type")
    if typ is not None and typ not in _SUPPORTED_TYPES:
        # A type value the interpreter does not implement would otherwise be
        # silently unenforced (e.g. "null" or a union list): fail closed.
        errors.append(f"{path}: unsupported 'type' value {typ!r} (fail closed)")
    if typ == "string":
        if not isinstance(value, str):
            errors.append(f"{path}: expected string, got {type(value).__name__}")
    elif typ == "integer":
        if isinstance(value, bool) or not isinstance(value, int):
            errors.append(f"{path}: expected integer, got {type(value).__name__}")
    elif typ == "number":
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            errors.append(f"{path}: expected number, got {type(value).__name__}")
    elif typ == "boolean":
        if not isinstance(value, bool):
            errors.append(f"{path}: expected boolean, got {type(value).__name__}")
    elif typ == "array":
        if not isinstance(value, list):
            errors.append(f"{path}: expected array, got {type(value).__name__}")
        else:
            items = definition.get("items")
            if items is None:
                pass
            elif not isinstance(items, Mapping):
                errors.append(f"{path}: unsupported 'items' value (fail closed)")
            else:
                for index, item in enumerate(value):
                    _validate_subschema(items, item, f"{path}[{index}]", root, errors)
    elif typ == "object":
        if not isinstance(value, Mapping):
            errors.append(f"{path}: expected object, got {type(value).__name__}")
            return
        properties = definition.get("properties", {})
        if not isinstance(properties, Mapping):
            errors.append(f"{path}: unsupported 'properties' value (fail closed)")
            properties = {}
        required = definition.get("required", [])
        if "required" in definition and (
            not isinstance(required, list) or not all(isinstance(key, str) for key in required)
        ):
            errors.append(f"{path}: unsupported 'required' value (fail closed)")
            required = []
        for key in required:
            if key not in value:
                errors.append(f"{path}: missing required property {key}")
        additional = definition.get("additionalProperties")
        if additional is not None and not isinstance(additional, bool):
            errors.append(f"{path}: unsupported 'additionalProperties' value (fail closed)")
        if additional is False:
            for key in value:
                if key not in properties:
                    errors.append(f"{path}: unexpected property {key}")
        for key, property_definition in properties.items():
            if key in value and isinstance(property_definition, Mapping):
                _validate_subschema(property_definition, value[key], f"{path}.{key}", root, errors)
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        minimum = definition.get("minimum")
        if minimum is not None and (isinstance(minimum, bool) or not isinstance(minimum, (int, float))):
            errors.append(f"{path}: unsupported 'minimum' value (fail closed)")
        elif minimum is not None and value < minimum:
            errors.append(f"{path}: below minimum {minimum}")
        maximum = definition.get("maximum")
        if maximum is not None and (isinstance(maximum, bool) or not isinstance(maximum, (int, float))):
            errors.append(f"{path}: unsupported 'maximum' value (fail closed)")
        elif maximum is not None and value > maximum:
            errors.append(f"{path}: above maximum {maximum}")


# ---------------------------------------------------------------------------
# Projection
# ---------------------------------------------------------------------------


def _set_leaf(root: dict[str, Any], path: str, value: Any) -> None:
    parts = [part for part in path.split("/") if part]
    node: Any = root
    for index, part in enumerate(parts[:-1]):
        next_part = parts[index + 1]
        if part.isdigit():
            item_index = int(part)
            if not isinstance(node, list):
                raise ExportError(f"source-map path {path!r} expects a list at {part!r}")
            while len(node) <= item_index:
                node.append({})
            node = node[item_index]
        else:
            if part not in node:
                node[part] = [] if next_part.isdigit() else {}
            node = node[part]
    node[parts[-1]] = value


def _leaf_paths(value: Any, prefix: str = "") -> list[str]:
    if isinstance(value, Mapping):
        paths: list[str] = []
        for key in value:
            paths.extend(_leaf_paths(value[key], f"{prefix}/{key}"))
        return paths
    if isinstance(value, list):
        paths = []
        for index, item in enumerate(value):
            paths.extend(_leaf_paths(item, f"{prefix}/{index}"))
        return paths
    return [prefix]


def _non_empty_str(value: Any, label: str, errors: list[str]) -> None:
    if not isinstance(value, str) or not value:
        errors.append(f"{label} must be a non-empty str")


def _unit_metric(value: Any, label: str, errors: list[str]) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        errors.append(f"{label} must be an int or float")
    elif not 0.0 <= float(value) <= 1.0:
        errors.append(f"{label} must be within [0, 1], got {value!r}")


def _non_negative_int(value: Any, label: str, errors: list[str]) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        errors.append(f"{label} must be a non-negative int")


def project_bundle(
    manifest: RunManifest,
    events: Sequence[Event],
    blobs: Mapping[str, bytes],
    *,
    schema_path: Path | None = None,
) -> ProjectionRecord:
    """Derive the projection record from in-memory bundle evidence.

    Pure: no disk access beyond reading the strict schema for validation. The
    exporter and the verifier call this same function, so an exported file and
    its attestation can never disagree by construction.
    """
    errors: list[str] = []

    def error(message: str) -> None:
        errors.append(message)

    if not manifest.closed:
        raise ExportError("cannot project an open bundle (manifest is not closed)")
    if not events or events[0].event_type != "run_started":
        raise ExportError("cannot project a bundle without a leading run_started event")

    created_at = events[0].payload.get("createdAt")
    if created_at is None:
        error(
            "missing required field 'createdAt': the bundle carries no declared run "
            "timestamp (run_started.createdAt); the kernel stores no wall-clock time "
            "and the exporter never invents one — declare run_created_at when "
            "scheduling the run"
        )
    else:
        _non_empty_str(created_at, "run_started.createdAt", errors)

    target_text: str | None = None
    if not manifest.target_blob_digest or manifest.target_blob_digest not in blobs:
        error("missing target blob: the manifest declares no stored target content")
    else:
        try:
            decoded = blobs[manifest.target_blob_digest].decode("utf-8")
        except UnicodeDecodeError as exc:
            error(f"target blob is not UTF-8 text: {exc}")
        else:
            _non_empty_str(decoded, "target text", errors)
            target_text = decoded

    model_manifest = manifest.model_manifest
    model = model_manifest.get("model")
    _non_empty_str(model, "modelManifest.model", errors)

    decoding_value = model_manifest.get("decoding")
    decoding: str | None = None
    decoding_rendered = False
    if isinstance(decoding_value, str) and decoding_value:
        decoding = decoding_value
    elif isinstance(decoding_value, Mapping) and decoding_value:
        decoding = canonical_json(decoding_value)
        decoding_rendered = True
    else:
        error("modelManifest.decoding must be a non-empty str or mapping")

    mode = model_manifest.get("mode")
    if mode not in RUN_MODES:
        error(f"modelManifest.mode must be one of {list(RUN_MODES)}")
    observation_mode = model_manifest.get("observationMode")
    if observation_mode not in OBSERVATION_MODES:
        error(f"modelManifest.observationMode must be one of {list(OBSERVATION_MODES)}")

    freeze_event: Event | None = None
    confirm_event: Event | None = None
    completion_status: str | None = None
    run_completed_seen = False
    for event in events:
        if event.event_type == "search_frozen":
            freeze_event = event
        elif event.event_type == "confirmation_completed":
            confirm_event = event
        elif event.event_type == "run_completed":
            run_completed_seen = True
            completion_status = event.payload.get("status")
    if freeze_event is None:
        error("bundle has no search_frozen event")
    if confirm_event is None:
        error("bundle has no confirmation_completed event")
    if not run_completed_seen:
        error("bundle has no run_completed event")
    elif completion_status != "completed":
        error(
            f"cannot project a run closed with status {completion_status!r}: "
            "only completed runs are exportable"
        )

    metric: str | None = None
    config_digest = freeze_event.payload.get("frozenConfigDigest") if freeze_event else None
    if not is_digest(config_digest):
        error(
            "search_frozen is missing frozenConfigDigest: the run did not pin its "
            "frozen configuration, so config fields cannot be projected"
        )
    elif config_digest not in blobs:
        error(f"frozen config blob {config_digest} is missing from the bundle")
    else:
        try:
            config = json.loads(blobs[config_digest])
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            error(f"frozen config blob is unreadable: {exc}")
        else:
            if not isinstance(config, Mapping):
                error("frozen config blob must contain a JSON object")
            else:
                metric = config.get("metric")
                _non_empty_str(metric, "frozen config metric", errors)
                if metric not in manifest.known_metrics:
                    error(
                        f"frozen config metric {metric!r} is not declared in "
                        f"known_metrics {list(manifest.known_metrics)}"
                    )

    # Replay per-candidate evidence.
    proposed: dict[str, tuple[str, int, Candidate]] = {}
    costs: dict[str, tuple[int, Mapping[str, Any]]] = {}
    evaluations: dict[str, tuple[int, str, Any]] = {}
    archive_order: list[str] = []
    rejected_reason: dict[str, str | None] = {}
    for event in events:
        if event.event_type == "proposal_succeeded":
            record = json.loads(blobs[event.blob_digests[0]])
            receipt = proposal_receipt_from_canonical(record)
            for index, candidate in enumerate(receipt.candidates):
                proposed[candidate.candidate_id] = (event.blob_digests[0], index, candidate)
        elif event.event_type == "archive_changed":
            candidate_id = event.payload["candidateId"]
            archive_order.append(candidate_id)
            costs[candidate_id] = (event.sequence, event.payload["coordinateCost"])
        elif event.event_type == "evaluation_completed" and event.phase == "discovery":
            record = json.loads(blobs[event.blob_digests[0]])
            receipt = evaluation_receipt_from_canonical(record)
            evaluations[receipt.candidate_id] = (event.sequence, event.blob_digests[0], receipt)
        elif event.event_type == "candidate_rejected":
            rejected_reason[event.payload["candidateId"]] = event.payload.get("reason")

    included_ids = [candidate_id for candidate_id in archive_order if candidate_id in evaluations]
    omitted_ids = [candidate_id for candidate_id in archive_order if candidate_id not in evaluations]
    if not included_ids:
        error(
            "no archived candidate has a discovery evaluation receipt; a projection "
            "with an empty candidate set would lose every coordinate"
        )

    points: list[dict[str, Any]] = []
    samples_max = 0
    for candidate_id in included_ids:
        if candidate_id not in proposed or candidate_id not in costs:
            error(
                f"candidate {candidate_id} is archived and evaluated but has no "
                "proposal receipt or coordinate cost in the stream"
            )
            continue
        proposal_blob, proposal_index, candidate = proposed[candidate_id]
        _eval_sequence, eval_blob, receipt = evaluations[candidate_id]
        cost_sequence, cost = costs[candidate_id]
        metrics = dict(receipt.metrics)
        point: dict[str, Any] = {"id": candidate.candidate_id}
        if candidate.role != "candidate":
            point["role"] = candidate.role
        point["label"] = candidate_label(candidate.role, candidate.proposal_mode)
        if len(candidate.messages) == 1:
            point["prompt"] = candidate.messages[0].content
        else:
            point["prompt"] = "\n\n".join(
                f"{message.role}: {message.content}" for message in candidate.messages
            )
        output_text = dict(receipt.outputs).get("text")
        _non_empty_str(output_text, f"candidate {candidate_id}: evaluation receipt outputs.text", errors)
        point["output"] = output_text
        tokens = cost.get("coordinateTokens")
        _non_negative_int(tokens, f"candidate {candidate_id}: coordinateCost.coordinateTokens", errors)
        point["tokens"] = tokens
        for name in ("fit", "stability", "compression", "leakage"):
            value = metrics.get(name)
            _unit_metric(value, f"candidate {candidate_id}: metric {name}", errors)
            point[name] = value
        nll = metrics.get("nll")
        if nll is not None:
            if isinstance(nll, bool) or not isinstance(nll, (int, float)) or nll < 0:
                error(f"candidate {candidate_id}: metric nll must be a non-negative number")
            else:
                point["nll"] = nll
        samples = dict(receipt.resource_use).get("samples")
        if samples is not None:
            _non_negative_int(samples, f"candidate {candidate_id}: resourceUse.samples", errors)
            samples_max = max(samples_max, samples)
        points.append(point)

    selected: str | None = None
    selected_source: str | None = None
    selected_note: str | None = None
    if confirm_event is None or freeze_event is None:
        selected = None
    elif confirm_event.payload["outcome"] == "confirmed":
        selected = confirm_event.payload.get("candidateId")
        _non_empty_str(selected, "confirmation_completed.candidateId", errors)
        selected_source = f"events[{confirm_event.sequence}].payload.candidateId"
    else:
        shortlist = freeze_event.payload["shortlistCandidateIds"]
        if not shortlist:
            error(
                "no confirmed candidate and the frozen shortlist is empty: the run "
                "never promoted a candidate, so no selected candidate exists"
            )
        else:
            selected = shortlist[0]
            selected_source = f"events[{freeze_event.sequence}].payload.shortlistCandidateIds[0]"
            selected_note = (
                "confirmation did not confirm; the top-ranked frozen-shortlist "
                "candidate is selected"
            )
    if selected is not None and selected not in included_ids:
        error(f"selected candidate {selected!r} is not in the projected candidate set")

    # Assemble the projection and its source map leaf by leaf.
    projection: dict[str, Any] = {}
    source_map: dict[str, dict[str, Any]] = {}

    def put(path: str, kind: str, source: str, value: Any, note: str | None = None) -> None:
        _set_leaf(projection, path, value)
        entry: dict[str, Any] = {"kind": kind, "source": source}
        if note is not None:
            entry["note"] = note
        source_map[path] = entry

    put("/id", "copy", "manifest.runId", manifest.run_id)
    put("/createdAt", "copy", "events[0].payload.createdAt", created_at)
    put("/target/text", "copy", f"blob:{manifest.target_blob_digest}", target_text)
    put("/config/model", "copy", "manifest.modelManifest.model", model)
    put(
        "/config/decoding",
        "copy" if not decoding_rendered else "render",
        "manifest.modelManifest.decoding",
        decoding,
        "canonical JSON render of the declared decoding mapping" if decoding_rendered else None,
    )
    metric_source = (
        f"events[{freeze_event.sequence}].blob({config_digest}).metric"
        if freeze_event is not None
        else "missing: the bundle has no search_frozen event"
    )
    put("/config/metric", "copy", metric_source, metric)
    put("/config/mode", "copy", "manifest.modelManifest.mode", mode)
    put(
        "/config/budget/candidates",
        "derived",
        "projection.candidates",
        len(points),
        "count of projected candidates",
    )
    token_values = [
        point["tokens"]
        for point in points
        if isinstance(point["tokens"], int) and not isinstance(point["tokens"], bool)
    ]
    put(
        "/config/budget/maxPromptTokens",
        "derived",
        "archive coordinateCost.coordinateTokens",
        max(token_values, default=0),
        "maximum coordinateTokens over projected candidates",
    )
    put(
        "/config/budget/repeatedSamples",
        "derived",
        "evaluation receipt resourceUse.samples",
        samples_max,
        "maximum declared samples over projected discovery receipts; 0 when undeclared",
    )
    for index, point in enumerate(points):
        candidate_id = point["id"]
        proposal_blob, proposal_index, candidate = proposed[candidate_id]
        eval_sequence, eval_blob, receipt = evaluations[candidate_id]
        cost_sequence, cost = costs[candidate_id]
        base = f"/candidates/{index}"
        put(f"{base}/id", "copy", f"blob:{proposal_blob}.candidates[{proposal_index}].candidateId", point["id"])
        if "role" in point:
            put(
                f"{base}/role",
                "copy",
                f"blob:{proposal_blob}.candidates[{proposal_index}].candidateRole",
                point["role"],
            )
        put(
            f"{base}/label",
            "derived",
            f"blob:{proposal_blob}.candidates[{proposal_index}].candidateRole + .proposalMode",
            point["label"],
            "'Explicit Reconstruction' for explicit_reconstruction, else the capitalized proposal mode",
        )
        if len(candidate.messages) == 1:
            put(
                f"{base}/prompt",
                "copy",
                f"blob:{proposal_blob}.candidates[{proposal_index}].messages[0].content",
                point["prompt"],
            )
        else:
            put(
                f"{base}/prompt",
                "render",
                f"blob:{proposal_blob}.candidates[{proposal_index}].messages[*]",
                point["prompt"],
                "'role: content' lines joined by blank lines",
            )
        put(f"{base}/output", "copy", f"blob:{eval_blob}.outputs.text", point["output"])
        put(
            f"{base}/tokens",
            "copy",
            f"events[{cost_sequence}].payload.coordinateCost.coordinateTokens",
            point["tokens"],
        )
        for name in ("fit", "stability", "compression", "leakage"):
            put(f"{base}/{name}", "copy", f"blob:{eval_blob}.metrics.{name}", point[name])
        if "nll" in point:
            put(f"{base}/nll", "copy", f"blob:{eval_blob}.metrics.nll", point["nll"])
    if selected is not None:
        put("/selectedCandidateId", "copy", selected_source, selected, selected_note)
    put("/observations/mode", "copy", "manifest.modelManifest.observationMode", observation_mode)

    # The projection file embeds a self-describing artifact ref. The projection
    # digest excludes the ref itself, so the digest is non-circular.
    projection_digest = digest(projection)
    artifact_ref = {
        "schemaVersion": ARTIFACT_REF_SCHEMA_VERSION,
        "runId": manifest.run_id,
        "bundleDigest": manifest.stream_digest,
        "projectionDigest": projection_digest,
    }
    put("/artifactRef/schemaVersion", "derived", f"constant {ARTIFACT_REF_SCHEMA_VERSION}", artifact_ref["schemaVersion"])
    put("/artifactRef/runId", "copy", "manifest.runId", manifest.run_id)
    put("/artifactRef/bundleDigest", "copy", "manifest.streamDigest", manifest.stream_digest)
    put(
        "/artifactRef/projectionDigest",
        "derived",
        "digest over the projection without artifactRef",
        projection_digest,
        "self-reference excluded so the digest is non-circular",
    )

    # Validate the full projection (including the ref) against the strict schema.
    schema_errors = validate_against_schema(projection, _schema_path_or(schema_path))
    errors.extend(schema_errors)
    if errors:
        raise ExportError("; ".join(errors))

    # Completeness self-check: the source map covers exactly the projection.
    map_keys = set(source_map)
    leaf_keys = set(_leaf_paths(projection))
    if map_keys != leaf_keys:
        raise ExportError(
            "internal source-map mismatch: "
            f"missing {sorted(leaf_keys - map_keys)}, extra {sorted(map_keys - leaf_keys)}"
        )

    policy = {
        "createdAt": (
            "fail-closed: byte-copied from run_started.payload.createdAt (a "
            "caller-declared run timestamp); the exporter never reads the wall clock"
        ),
        "candidateInclusion": (
            "archived candidates with at least one discovery evaluation receipt; "
            "unevaluated archives (e.g. policy-excluded reconstruction controls) "
            "stay in the linked bundle only and are listed in omittedCandidateIds"
        ),
        "label": (
            "derived presentation label: 'Explicit Reconstruction' for "
            "explicit_reconstruction, otherwise the capitalized proposal mode"
        ),
        "prompt": (
            "single message copied verbatim; multiple messages rendered as "
            "'role: content' lines joined by blank lines"
        ),
        "metrics": (
            "fit/stability/compression/leakage copied from the candidate's final "
            "discovery evaluation receipt; nll copied when declared"
        ),
        "selectedCandidateId": (
            "the confirmed candidate when confirmation says confirmed, else the "
            "top-ranked frozen-shortlist candidate"
        ),
        "decoding": "string copied verbatim; a mapping is rendered as canonical JSON",
        "repeatedSamples": (
            "maximum declared resourceUse.samples across projected discovery "
            "receipts; 0 when none is declared"
        ),
    }
    omitted = [
        {"candidateId": candidate_id, "rejectionReason": rejected_reason.get(candidate_id)}
        for candidate_id in omitted_ids
    ]
    projection_record = {
        "schemaVersion": PROJECTION_RECORD_SCHEMA_VERSION,
        "runId": manifest.run_id,
        "artifactRef": artifact_ref,
        "sourceMap": source_map,
        "omittedCandidateIds": omitted,
        "policy": policy,
    }
    digests = (
        ("aleph-run.json", digest_bytes(canonical_bytes(projection))),
        (
            "aleph-run-projection.json",
            digest_bytes(canonical_bytes(projection_record)),
        ),
    )
    return ProjectionRecord(
        run_id=manifest.run_id,
        projection=projection,
        projection_record=projection_record,
        artifact_ref=artifact_ref,
        omitted_candidate_ids=tuple(omitted_ids),
        digests=digests,
    )


def export_aleph_run(root: Path, *, schema_path: Path | None = None) -> ExportResult:
    """Project a closed bundle into ``exports/`` and write both files.

    Fails closed (no files are written) on any defect: an unreadable bundle,
    missing required evidence, or a projection that does not satisfy the strict
    schema.
    """
    root = Path(root)
    try:
        snapshot = read_bundle(root)
        # The projection is defined over replayed evidence: derive once so any
        # derivation defect fails closed here, not inside the projection.
        derive_state(snapshot.manifest, snapshot.events, snapshot.blobs)
    except (ArchiveError, ValueError) as error:
        raise ExportError(f"cannot export: {error}") from error
    record = project_bundle(
        snapshot.manifest,
        snapshot.events,
        load_target_blob(root, snapshot.manifest, snapshot.blobs),
        schema_path=schema_path,
    )
    exports_dir = root / "exports"
    exports_dir.mkdir(parents=True, exist_ok=True)
    run_name, projection_name = EXPORT_NAMES
    _atomic_write(
        exports_dir / f"{run_name}.json",
        canonical_bytes(record.projection) + b"\n",
    )
    _atomic_write(
        exports_dir / f"{projection_name}.json",
        canonical_bytes(record.projection_record) + b"\n",
    )
    return ExportResult(
        root=root,
        run_id=record.run_id,
        projection=record.projection,
        projection_record=record.projection_record,
        omitted_candidate_ids=record.omitted_candidate_ids,
        digests=record.digests,
    )
