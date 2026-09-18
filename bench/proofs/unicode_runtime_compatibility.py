"""Reproduce the Unicode-runtime incompatibility behind Aleph-Bench v0.2.

This is a proof harness, not a scorer. It observes public scorer primitives
under both the accepted runtime and a rejected runtime while leaving
``validate_scoring_runtime`` and every frozen scorer constant intact. Rejected
runtime observations are negative-control evidence, never canonical scores.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import platform
import selectors
import shutil
import struct
import subprocess
import sys
import sysconfig
import tempfile
import time
import unicodedata
from collections import Counter
from pathlib import Path
from typing import Any, BinaryIO

try:
    import resource
except ImportError:  # pragma: no cover - the supported proof hosts are POSIX.
    resource = None  # type: ignore[assignment]


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
RUNNER_PATH = Path(__file__).resolve()
SCORING_CORE_PATH = REPO_ROOT / "bench/engine/scoring_core.py"
PROTOCOL_MODULE_PATH = REPO_ROOT / "bench/engine/protocol.py"
PROTOCOL_CONFIG_PATH = REPO_ROOT / "bench/config/frozen_ladder-v0.2.json"
CHECKED_RECEIPT_PATH = (
    REPO_ROOT / "bench/proofs/unicode-runtime-compatibility-v0.2.json"
)

TOTAL_CODEPOINTS = 0x110000
MAX_PROPERTY_TEXT_CODEPOINTS = 64
MAX_RECEIPT_BYTES = 1024 * 1024
MAX_WORKER_JSON_BYTES = 64 * 1024
MAX_WORKER_STDERR_BYTES = 64 * 1024
RECEIPT_VERSION = "1"
ARTIFACT_KIND = "aleph-bench-unicode-runtime-compatibility-proof"
ARTIFACT_ID_PREFIX = "aleph-bench-unicode-runtime-proof-v0.2-artifact-"

ROLE_SPECS = {
    "negativeControl": {
        "pythonSeries": "3.11",
        "unicodeDatabaseVersion": "14.0.0",
    },
    "reference": {
        "pythonSeries": "3.13",
        "unicodeDatabaseVersion": "15.1.0",
    },
}
PROPERTY_NAMES = (
    "category",
    "eastAsianWidth",
    "isSpace",
    "casefold",
    "nfc",
    "nfkc",
)

# Category and East Asian Width have fixed ASCII encodings. Variable-length
# text properties are stored losslessly as length-prefixed UTF-32BE. The
# surrogatepass handler is required because this proof covers the surrogate
# code-point range as data too. Hashes bind streams; they never decide equality.
PROPERTY_HEADER = struct.Struct(">2s2sc")
TEXT_LENGTH = struct.Struct(">I")
MAX_ENCODED_RECORD_BYTES = PROPERTY_HEADER.size + 3 * (
    TEXT_LENGTH.size + 4 * MAX_PROPERTY_TEXT_CODEPOINTS
)
MAX_PROPERTY_TABLE_BYTES = TOTAL_CODEPOINTS * MAX_ENCODED_RECORD_BYTES

LEAKAGE_PROMPT = "\U0001e030"
LEAKAGE_TARGET = "\u0430"
FIDELITY_TARGET = "\u00e0\U0001e4ec\u0315\u035cb"
FIDELITY_OUTPUT = "a\U0001e4ec\u035c\u0315\u0300b"

CONCLUSION = {
    "checkedInFixtureEquivalenceAssessed": False,
    "python311Ucd14EquivalentToV02": False,
    "runtimeLockMustRemain": True,
}
LIMITATIONS = (
    "The exhaustive table covers each code point independently; it is not exhaustive over multi-code-point normalization sequences.",
    "Case folding and whitespace observations come from Python str methods, not standalone UCD files.",
    "The interpreter executable digest does not content-address its standard library, shared libraries, or operating-system image.",
    "This proof does not execute Unicode conformance files or evaluate the optional unicodedata2 portability candidate.",
    "Negative-control values are probe observations, not canonical Aleph-Bench results.",
)
PROOF_INPUT_SPECS = {
    "protocolConfig": (
        "bench/config/frozen_ladder-v0.2.json",
        PROTOCOL_CONFIG_PATH,
    ),
    "protocolModule": ("bench/engine/protocol.py", PROTOCOL_MODULE_PATH),
    "runner": ("bench/proofs/unicode_runtime_compatibility.py", RUNNER_PATH),
    "scoringCore": ("bench/engine/scoring_core.py", SCORING_CORE_PATH),
}


class ProofError(RuntimeError):
    """Raised when the proof environment or receipt fails closed."""


def expected_method() -> dict[str, Any]:
    return {
        "codepointRange": {"start": "U+0000", "stopInclusive": "U+10FFFF"},
        "equalityMethod": "exact field comparison after lossless decoding",
        "maxPropertyTextCodepoints": MAX_PROPERTY_TEXT_CODEPOINTS,
        "networkCallsMadeByHarness": False,
        "networkRequired": False,
        "propertyRecordEncoding": "ASCII metadata plus uint32-length-prefixed UTF-32BE with surrogatepass",
        "canonicalScoringEntryPointsCalledByProbe": False,
        "scorerPublicPrimitivesUsed": [
            "fail_closed_codepoint_reason",
            "lcs_length",
            "longest_common_span",
            "ngrams",
            "normalize_unicode",
            "normalized_edit_similarity",
            "unicode_lexical_units",
            "unicode_skeleton_codepoints",
        ],
        "singleCodepointProperties": list(PROPERTY_NAMES),
        "streamAndDifferenceHashesUsedForEquality": False,
        "workerIsolationFlags": ["-B", "-I", "-S"],
    }


def _canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("ascii")


def _pretty_json_bytes(value: Any) -> bytes:
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


def _strict_json_object(text: str, *, role: str) -> dict[str, Any]:
    def reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ProofError(f"duplicate JSON key in {role}: {key}")
            result[key] = value
        return result

    def reject_constant(value: str) -> None:
        raise ProofError(f"non-finite JSON value in {role}: {value}")

    def parse_finite_float(value: str) -> float:
        parsed = float(value)
        if not math.isfinite(parsed):
            raise ProofError(f"non-finite JSON value in {role}: {value}")
        return parsed

    try:
        value = json.loads(
            text,
            object_pairs_hook=reject_duplicates,
            parse_constant=reject_constant,
            parse_float=parse_finite_float,
        )
    except (json.JSONDecodeError, OverflowError, RecursionError, ValueError) as exc:
        raise ProofError(f"invalid JSON in {role}: {exc}") from exc
    if not isinstance(value, dict):
        raise ProofError(f"{role} must be a JSON object")
    return value


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _proof_input_bindings() -> dict[str, dict[str, str]]:
    return {
        name: {"path": relative_path, "sha256": _sha256_file(source_path)}
        for name, (relative_path, source_path) in PROOF_INPUT_SPECS.items()
    }


def _codepoints(text: str) -> list[str]:
    return [f"U+{ord(char):04X}" for char in text]


def _expected_leakage_thresholds() -> dict[str, float | int]:
    from bench.engine.protocol import DEFAULT_LEAKAGE_THRESHOLDS

    return dict(DEFAULT_LEAKAGE_THRESHOLDS)


def expected_counterexamples() -> list[dict[str, Any]]:
    """Return the complete v0.2 counterexample semantics this proof asserts."""

    thresholds = _expected_leakage_thresholds()
    negative_leakage = {
        "disqualified": False,
        "failClosedReason": None,
        "lcsRatio": 0.0,
        "skeletonLcsRatio": 0.0,
        "skeletonTargetTrigramRecall": 0.0,
        "skeletonVerbatimSpanUnits": 0,
        "targetTrigramRecall": 0.0,
        "thresholds": thresholds,
        "unit": "unicode_dual_channel_v1",
        "verbatimSpanUnits": 0,
    }
    reference_leakage = {
        "disqualified": True,
        "failClosedReason": None,
        "lcsRatio": 1.0,
        "skeletonLcsRatio": 1.0,
        "skeletonTargetTrigramRecall": 0.0,
        "skeletonVerbatimSpanUnits": 1,
        "targetTrigramRecall": 0.0,
        "thresholds": thresholds,
        "unit": "unicode_dual_channel_v1",
        "verbatimSpanUnits": 1,
    }
    reference_fidelity_codepoints = _codepoints(FIDELITY_TARGET)
    return [
        {
            "coverage": "single-code-point leakage decision",
            "id": "ucd-15-1-cyrillic-modifier-leakage",
            "input": {
                "prompt": LEAKAGE_PROMPT,
                "promptCodepoints": _codepoints(LEAKAGE_PROMPT),
                "target": LEAKAGE_TARGET,
                "targetCodepoints": _codepoints(LEAKAGE_TARGET),
            },
            "negativeControl": {
                "normalizedPromptCodepoints": _codepoints(LEAKAGE_PROMPT),
                "normalizedTargetCodepoints": _codepoints(LEAKAGE_TARGET),
                "result": negative_leakage,
            },
            "reference": {
                "normalizedPromptCodepoints": _codepoints(LEAKAGE_TARGET),
                "normalizedTargetCodepoints": _codepoints(LEAKAGE_TARGET),
                "result": reference_leakage,
            },
        },
        {
            "coverage": "multi-code-point NFC fidelity decision",
            "id": "ucd-15-1-combining-mark-order-fidelity",
            "input": {
                "output": FIDELITY_OUTPUT,
                "outputCodepoints": _codepoints(FIDELITY_OUTPUT),
                "target": FIDELITY_TARGET,
                "targetCodepoints": _codepoints(FIDELITY_TARGET),
            },
            "negativeControl": {
                "normalizedEditSimilarity": 0.666667,
                "normalizedOutputCodepoints": _codepoints(
                    "a\U0001e4ec\u0300\u0315\u035cb"
                ),
                "normalizedTargetCodepoints": reference_fidelity_codepoints,
            },
            "reference": {
                "normalizedEditSimilarity": 1.0,
                "normalizedOutputCodepoints": reference_fidelity_codepoints,
                "normalizedTargetCodepoints": reference_fidelity_codepoints,
            },
        },
    ]


def property_values(codepoint: int) -> tuple[str, str, bool, str, str, str]:
    """Return the six scorer-relevant single-code-point observations."""

    if (
        isinstance(codepoint, bool)
        or not isinstance(codepoint, int)
        or not 0 <= codepoint < TOTAL_CODEPOINTS
    ):
        raise ValueError("codepoint must be an integer in [0, 0x110000)")
    char = chr(codepoint)
    return (
        unicodedata.category(char),
        unicodedata.east_asian_width(char),
        char.isspace(),
        char.casefold(),
        unicodedata.normalize("NFC", char),
        unicodedata.normalize("NFKC", char),
    )


def encode_property_record(values: tuple[str, str, bool, str, str, str]) -> bytes:
    """Encode one observation without hashes or lossy substitutions."""

    category, width, is_space, casefold, nfc, nfkc = values
    if len(category) != 2 or not category.isascii():
        raise ProofError(f"invalid Unicode category value: {category!r}")
    if width not in {"A", "F", "H", "N", "Na", "W"}:
        raise ProofError(f"invalid East Asian Width value: {width!r}")
    if not isinstance(is_space, bool):
        raise ProofError("isSpace must be a boolean")
    if any(not isinstance(text, str) for text in (casefold, nfc, nfkc)):
        raise ProofError("text properties must be strings")
    try:
        parts = [
            PROPERTY_HEADER.pack(
                category.encode("ascii"),
                width.encode("ascii"),
                b"1" if is_space else b"0",
            )
        ]
    except (UnicodeEncodeError, struct.error) as exc:
        raise ProofError("invalid fixed-width Unicode property value") from exc
    for name, text in (("casefold", casefold), ("nfc", nfc), ("nfkc", nfkc)):
        if len(text) > MAX_PROPERTY_TEXT_CODEPOINTS:
            raise ProofError(
                f"{name} expanded past the proof bound: {len(text)} code points"
            )
        encoded = text.encode("utf-32-be", errors="surrogatepass")
        parts.extend((TEXT_LENGTH.pack(len(encoded)), encoded))
    return b"".join(parts)


def property_record(codepoint: int) -> bytes:
    return encode_property_record(property_values(codepoint))


def _read_exact(handle: BinaryIO, size: int, *, role: str) -> bytes:
    data = handle.read(size)
    if len(data) != size:
        raise ProofError(f"{role} property stream ended inside a record")
    return data


def decode_property_record(
    handle: BinaryIO, *, role: str
) -> tuple[str, str, bool, str, str, str]:
    """Decode one exact record and reject malformed or oversized fields."""

    header = _read_exact(handle, PROPERTY_HEADER.size, role=role)
    category_raw, width_raw, space_raw = PROPERTY_HEADER.unpack(header)
    if space_raw not in {b"0", b"1"}:
        raise ProofError(f"{role} property stream has an invalid isSpace byte")
    texts: list[str] = []
    for name in ("casefold", "nfc", "nfkc"):
        length = TEXT_LENGTH.unpack(
            _read_exact(handle, TEXT_LENGTH.size, role=role)
        )[0]
        if length % 4 or length > 4 * MAX_PROPERTY_TEXT_CODEPOINTS:
            raise ProofError(f"{role} property stream has an invalid {name} length")
        raw = _read_exact(handle, length, role=role)
        try:
            texts.append(raw.decode("utf-32-be", errors="surrogatepass"))
        except UnicodeDecodeError as exc:
            raise ProofError(
                f"{role} property stream has invalid UTF-32BE in {name}"
            ) from exc
    try:
        category = category_raw.decode("ascii")
        width = width_raw.rstrip(b"\x00").decode("ascii")
    except UnicodeDecodeError as exc:
        raise ProofError(f"{role} property stream has non-ASCII metadata") from exc
    if len(category) != 2 or width not in {"A", "F", "H", "N", "Na", "W"}:
        raise ProofError(f"{role} property stream has invalid metadata values")
    return category, width, space_raw == b"1", *texts


def write_property_table(path: Path) -> None:
    """Write one lossless record for every Unicode code point."""

    with path.open("xb") as handle:
        for codepoint in range(TOTAL_CODEPOINTS):
            handle.write(property_record(codepoint))


def _channel_metrics(
    prompt_units: list[str], target_units: list[str]
) -> tuple[float, float, int]:
    """Compose the leakage gate's public sequence primitives."""

    from bench.engine import scoring_core

    if not prompt_units or not target_units:
        return 0.0, 0.0, 0
    lcs_ratio = scoring_core.lcs_length(prompt_units, target_units) / len(
        target_units
    )
    target_trigrams = scoring_core.ngrams(target_units, 3)
    prompt_trigrams = scoring_core.ngrams(prompt_units, 3)
    target_trigram_count = sum(target_trigrams.values())
    trigram_recall = (
        sum((target_trigrams & prompt_trigrams).values()) / target_trigram_count
        if target_trigram_count
        else 0.0
    )
    span = scoring_core.longest_common_span(prompt_units, target_units)
    return lcs_ratio, trigram_recall, span


def observe_counterexamples() -> dict[str, Any]:
    """Observe known drift without bypassing the canonical runtime guard.

    The guarded ``fidelity`` and ``evaluate_leakage`` entry points are not
    called by this negative-control probe. It composes public pure primitives;
    a reference-runtime test checks the observations against the guarded entry
    points exactly.
    """

    from bench.engine import scoring_core
    from bench.engine.protocol import DEFAULT_LEAKAGE_THRESHOLDS

    try:
        scoring_core.validate_scoring_runtime()
        runtime_validation: dict[str, Any] = {"accepted": True, "error": None}
    except RuntimeError as exc:
        runtime_validation = {"accepted": False, "error": str(exc)}

    thresholds = dict(DEFAULT_LEAKAGE_THRESHOLDS)
    prompt_lexical = scoring_core.unicode_lexical_units(LEAKAGE_PROMPT)
    target_lexical = scoring_core.unicode_lexical_units(LEAKAGE_TARGET)
    prompt_skeleton = scoring_core.unicode_skeleton_codepoints(LEAKAGE_PROMPT)
    target_skeleton = scoring_core.unicode_skeleton_codepoints(LEAKAGE_TARGET)
    lexical = _channel_metrics(prompt_lexical, target_lexical)
    skeleton = _channel_metrics(prompt_skeleton, target_skeleton)
    fail_closed_reason = scoring_core.fail_closed_codepoint_reason(LEAKAGE_PROMPT)
    leakage = {
        "disqualified": (
            fail_closed_reason is not None
            or lexical[0] >= float(thresholds["lcsRatio"])
            or lexical[1] >= float(thresholds["targetTrigramRecall"])
            or lexical[2] >= int(thresholds["verbatimSpanUnits"])
            or skeleton[0] >= float(thresholds["skeletonLcsRatio"])
            or skeleton[1]
            >= float(thresholds["skeletonTargetTrigramRecall"])
            or skeleton[2] >= int(thresholds["skeletonVerbatimSpanUnits"])
        ),
        "failClosedReason": fail_closed_reason,
        "lcsRatio": round(lexical[0], 6),
        "skeletonLcsRatio": round(skeleton[0], 6),
        "skeletonTargetTrigramRecall": round(skeleton[1], 6),
        "skeletonVerbatimSpanUnits": skeleton[2],
        "targetTrigramRecall": round(lexical[1], 6),
        "thresholds": thresholds,
        "unit": scoring_core.LEAKAGE_UNIT,
        "verbatimSpanUnits": lexical[2],
    }
    return {
        "runtime": runtime_identity(),
        "runtimeValidation": runtime_validation,
        "probeBoundary": {
            "canonicalScoringEntryPointsCalled": False,
            "runtimeConstantsChanged": False,
            "publicPurePrimitivesOnly": True,
        },
        "leakage": {
            "result": leakage,
            "normalizedPromptCodepoints": _codepoints("".join(prompt_skeleton)),
            "normalizedTargetCodepoints": _codepoints("".join(target_skeleton)),
        },
        "fidelity": {
            "normalizedEditSimilarity": scoring_core.normalized_edit_similarity(
                FIDELITY_TARGET, FIDELITY_OUTPUT
            ),
            "normalizedOutputCodepoints": _codepoints(
                scoring_core.normalize_unicode(FIDELITY_OUTPUT)
            ),
            "normalizedTargetCodepoints": _codepoints(
                scoring_core.normalize_unicode(FIDELITY_TARGET)
            ),
        },
    }


def runtime_identity() -> dict[str, Any]:
    executable = Path(sys.executable).resolve()
    unicode_module_file = getattr(unicodedata, "__file__", None)
    return {
        "cacheTag": sys.implementation.cache_tag,
        "compiler": platform.python_compiler(),
        "executableSha256": _sha256_file(executable),
        "implementation": platform.python_implementation(),
        "platform": platform.platform(),
        "pythonBuild": list(platform.python_build()),
        "pythonSeries": f"{sys.version_info.major}.{sys.version_info.minor}",
        "pythonVersion": platform.python_version(),
        "soabi": sysconfig.get_config_var("SOABI"),
        "sysVersion": sys.version,
        "unicodeDatabaseVersion": unicodedata.unidata_version,
        "unicodeModuleSha256": (
            _sha256_file(Path(unicode_module_file).resolve())
            if isinstance(unicode_module_file, str)
            else None
        ),
    }


def _resolve_interpreter(value: str) -> Path:
    located = shutil.which(value)
    if located is None:
        raise ProofError(f"interpreter not found or not executable: {value}")
    return Path(located).resolve()


def _set_worker_file_limit(file_size_limit: int) -> None:
    if resource is None:  # pragma: no cover - checked before spawning.
        raise RuntimeError("RLIMIT_FSIZE is unavailable")
    _, hard_limit = resource.getrlimit(resource.RLIMIT_FSIZE)
    enforced_limit = (
        file_size_limit
        if hard_limit == resource.RLIM_INFINITY
        else min(file_size_limit, hard_limit)
    )
    resource.setrlimit(resource.RLIMIT_FSIZE, (enforced_limit, enforced_limit))


def _kill_worker(process: subprocess.Popen[bytes]) -> None:
    if process.poll() is None:
        try:
            process.kill()
        except OSError:
            pass
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired as exc:  # pragma: no cover
        raise ProofError("worker did not terminate after SIGKILL") from exc


def _run_bounded_process(
    command: list[str],
    *,
    role: str,
    timeout_seconds: int,
    file_size_limit: int = MAX_PROPERTY_TABLE_BYTES,
) -> tuple[bytes, bytes]:
    """Run a worker with streaming output caps and an OS-enforced file cap."""

    if resource is None:
        raise ProofError("Unicode proof workers require POSIX RLIMIT_FSIZE support")
    if file_size_limit < 1:
        raise ValueError("file_size_limit must be positive")

    def set_file_limit() -> None:
        _set_worker_file_limit(file_size_limit)

    try:
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            preexec_fn=set_file_limit,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise ProofError(f"could not start {role}: {exc}") from exc
    if process.stdout is None or process.stderr is None:  # pragma: no cover
        _kill_worker(process)
        raise ProofError(f"could not open bounded worker pipes for {role}")

    streams = {"stdout": process.stdout, "stderr": process.stderr}
    limits = {
        "stdout": MAX_WORKER_JSON_BYTES,
        "stderr": MAX_WORKER_STDERR_BYTES,
    }
    buffers = {name: bytearray() for name in streams}
    selector = selectors.DefaultSelector()
    for name, stream in streams.items():
        selector.register(stream, selectors.EVENT_READ, data=name)
    deadline = time.monotonic() + timeout_seconds
    failure: str | None = None

    try:
        while selector.get_map():
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                failure = f"{role} timed out after {timeout_seconds} seconds"
                break
            for key, _ in selector.select(timeout=min(remaining, 0.25)):
                name = str(key.data)
                chunk = os.read(key.fd, 8192)
                if not chunk:
                    selector.unregister(key.fileobj)
                    key.fileobj.close()
                    continue
                available = limits[name] - len(buffers[name])
                buffers[name].extend(chunk[:available])
                if len(chunk) > available:
                    failure = f"{role} {name} exceeded {limits[name]} bytes"
                    break
            if failure is not None:
                break

        if failure is not None:
            _kill_worker(process)
            raise ProofError(failure)
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            _kill_worker(process)
            raise ProofError(f"{role} timed out after {timeout_seconds} seconds")
        try:
            returncode = process.wait(timeout=remaining)
        except subprocess.TimeoutExpired as exc:
            _kill_worker(process)
            raise ProofError(
                f"{role} timed out after {timeout_seconds} seconds"
            ) from exc
    finally:
        selector.close()
        for stream in streams.values():
            if not stream.closed:
                stream.close()

    if returncode != 0:
        detail = bytes(buffers["stderr"]).decode("utf-8", errors="replace").strip()
        suffix = f": {detail}" if detail else ""
        raise ProofError(f"{role} failed with exit code {returncode}{suffix}")
    return bytes(buffers["stdout"]), bytes(buffers["stderr"])


def _run_runtime_worker(
    interpreter: Path, output_path: Path, *, timeout_seconds: int
) -> tuple[dict[str, Any], dict[str, int | str]]:
    """Collect identity, counterexamples, and the property stream in one process."""

    executable_sha256 = _sha256_file(interpreter)
    stdout, _ = _run_bounded_process(
        [
            str(interpreter),
            "-B",
            "-I",
            "-S",
            str(RUNNER_PATH),
            "--_worker-runtime-table",
            str(output_path),
        ],
        role=f"runtime worker {interpreter}",
        timeout_seconds=timeout_seconds,
    )
    if _sha256_file(interpreter) != executable_sha256:
        raise ProofError(f"interpreter changed while worker ran: {interpreter}")
    try:
        text = stdout.decode("ascii")
    except UnicodeDecodeError as exc:
        raise ProofError(f"runtime worker emitted non-ASCII JSON: {interpreter}") from exc
    observation = _strict_json_object(text, role=f"runtime worker {interpreter.name}")
    runtime = observation.get("runtime")
    if not isinstance(runtime, dict) or runtime.get("executableSha256") != executable_sha256:
        raise ProofError(
            f"runtime worker identity does not match requested interpreter: {interpreter}"
        )
    try:
        observed_size = output_path.stat().st_size
    except OSError as exc:
        raise ProofError(f"runtime worker did not create {output_path}") from exc
    if not 0 < observed_size <= MAX_PROPERTY_TABLE_BYTES:
        raise ProofError(f"property table has an invalid size: {observed_size}")
    return observation, {
        "bytes": observed_size,
        "sha256": _sha256_file(output_path),
    }


def compare_property_tables(
    left_path: Path,
    right_path: Path,
    *,
    codepoint_count: int = TOTAL_CODEPOINTS,
) -> dict[str, Any]:
    """Compare all fields exactly and return compact difference-set bindings."""

    if (
        isinstance(codepoint_count, bool)
        or not isinstance(codepoint_count, int)
        or not 1 <= codepoint_count <= TOTAL_CODEPOINTS
    ):
        raise ValueError("codepoint_count must be in [1, 0x110000]")
    property_counts: Counter[str] = Counter()
    category_transitions: Counter[str] = Counter()
    width_transitions: Counter[str] = Counter()
    space_transitions: Counter[str] = Counter()
    property_sets = {name: hashlib.sha256() for name in PROPERTY_NAMES}
    union_set = hashlib.sha256()
    first_difference: dict[str, str | None] = {
        name: None for name in PROPERTY_NAMES
    }
    last_difference: dict[str, str | None] = {
        name: None for name in PROPERTY_NAMES
    }
    differing_codepoints = 0

    with left_path.open("rb") as left, right_path.open("rb") as right:
        for codepoint in range(codepoint_count):
            old = decode_property_record(left, role="negativeControl")
            new = decode_property_record(right, role="reference")
            changed = [
                name
                for name, old_value, new_value in zip(PROPERTY_NAMES, old, new)
                if old_value != new_value
            ]
            if not changed:
                continue
            encoded_codepoint = struct.pack(">I", codepoint)
            union_set.update(encoded_codepoint)
            differing_codepoints += 1
            for name in changed:
                property_counts[name] += 1
                property_sets[name].update(encoded_codepoint)
                label = f"U+{codepoint:04X}"
                if first_difference[name] is None:
                    first_difference[name] = label
                last_difference[name] = label
            if "category" in changed:
                category_transitions[f"{old[0]}->{new[0]}"] += 1
            if "eastAsianWidth" in changed:
                width_transitions[f"{old[1]}->{new[1]}"] += 1
            if "isSpace" in changed:
                space_transitions[f"{int(old[2])}->{int(new[2])}"] += 1
        if left.read(1) or right.read(1):
            raise ProofError("property stream contains trailing records or bytes")

    return {
        "categoryTransitions": dict(sorted(category_transitions.items())),
        "comparedCodepoints": codepoint_count,
        "differingCodepointCount": differing_codepoints,
        "differenceSetSha256": union_set.hexdigest(),
        "eastAsianWidthTransitions": dict(sorted(width_transitions.items())),
        "firstDifferenceByProperty": first_difference,
        "lastDifferenceByProperty": last_difference,
        "propertyDifferenceCounts": {
            name: property_counts[name] for name in PROPERTY_NAMES
        },
        "propertyDifferenceSetSha256": {
            name: property_sets[name].hexdigest() for name in PROPERTY_NAMES
        },
        "whitespaceTransitions": dict(sorted(space_transitions.items())),
    }


def _validate_role(role: str, observation: dict[str, Any]) -> None:
    runtime = observation.get("runtime")
    if not isinstance(runtime, dict):
        raise ProofError(f"{role} worker omitted runtime identity")
    for key, value in ROLE_SPECS[role].items():
        if runtime.get(key) != value:
            raise ProofError(
                f"{role} requires {key}={value!r}; found {runtime.get(key)!r}"
            )
    if runtime.get("implementation") != "CPython":
        raise ProofError(f"{role} requires CPython")


def _artifact_id(payload: dict[str, Any]) -> str:
    try:
        digest = hashlib.sha256(_canonical_json_bytes(payload)).hexdigest()
    except (OverflowError, RecursionError, TypeError, ValueError) as exc:
        raise ProofError(f"proof receipt is not canonical JSON: {exc}") from exc
    return ARTIFACT_ID_PREFIX + digest


def build_receipt(
    python311: str,
    python313: str,
    *,
    timeout_seconds: int = 600,
) -> dict[str, Any]:
    """Run both explicit interpreters and build one content-addressed receipt."""

    if isinstance(timeout_seconds, bool) or not 1 <= timeout_seconds <= 3600:
        raise ProofError("timeout_seconds must be in [1, 3600]")
    interpreters = {
        "negativeControl": _resolve_interpreter(python311),
        "reference": _resolve_interpreter(python313),
    }
    expected_thresholds = _expected_leakage_thresholds()
    proof_inputs = _proof_input_bindings()
    observations: dict[str, dict[str, Any]] = {}
    property_tables: dict[str, dict[str, int | str]] = {}

    with tempfile.TemporaryDirectory(prefix="aleph-unicode-proof-") as temporary:
        root = Path(temporary)
        tables = {role: root / f"{role}.bin" for role in ROLE_SPECS}
        for role in ROLE_SPECS:
            observation, property_table = _run_runtime_worker(
                interpreters[role],
                tables[role],
                timeout_seconds=timeout_seconds,
            )
            _validate_role(role, observation)
            observations[role] = observation
            property_tables[role] = property_table
        comparison = compare_property_tables(
            tables["negativeControl"], tables["reference"]
        )

    if _proof_input_bindings() != proof_inputs:
        raise ProofError("proof inputs changed while workers ran")
    if _expected_leakage_thresholds() != expected_thresholds:
        raise ProofError("leakage thresholds changed while workers ran")

    counterexamples = [
        {
            "coverage": "single-code-point leakage decision",
            "id": "ucd-15-1-cyrillic-modifier-leakage",
            "input": {
                "prompt": LEAKAGE_PROMPT,
                "promptCodepoints": _codepoints(LEAKAGE_PROMPT),
                "target": LEAKAGE_TARGET,
                "targetCodepoints": _codepoints(LEAKAGE_TARGET),
            },
            "negativeControl": observations["negativeControl"]["leakage"],
            "reference": observations["reference"]["leakage"],
        },
        {
            "coverage": "multi-code-point NFC fidelity decision",
            "id": "ucd-15-1-combining-mark-order-fidelity",
            "input": {
                "output": FIDELITY_OUTPUT,
                "outputCodepoints": _codepoints(FIDELITY_OUTPUT),
                "target": FIDELITY_TARGET,
                "targetCodepoints": _codepoints(FIDELITY_TARGET),
            },
            "negativeControl": observations["negativeControl"]["fidelity"],
            "reference": observations["reference"]["fidelity"],
        },
    ]
    payload = {
        "artifactKind": ARTIFACT_KIND,
        "conclusion": dict(CONCLUSION),
        "counterexamples": counterexamples,
        "limitations": list(LIMITATIONS),
        "method": expected_method(),
        "proofInputs": proof_inputs,
        "protocolVersion": "0.2.0",
        "receiptVersion": RECEIPT_VERSION,
        "runtimes": {
            role: {
                **observations[role]["runtime"],
                "probeBoundary": observations[role]["probeBoundary"],
                "propertyTable": property_tables[role],
                "runtimeValidation": observations[role]["runtimeValidation"],
            }
            for role in ROLE_SPECS
        },
        "singleCodepointComparison": comparison,
    }
    receipt = dict(payload)
    receipt["id"] = _artifact_id(payload)
    validate_receipt(receipt)
    return receipt


def _load_json(path: Path) -> dict[str, Any]:
    try:
        with path.open("rb") as handle:
            raw = handle.read(MAX_RECEIPT_BYTES + 1)
        if len(raw) > MAX_RECEIPT_BYTES:
            raise ProofError(
                f"proof receipt exceeds {MAX_RECEIPT_BYTES} bytes: {path}"
            )
        text = raw.decode("ascii")
    except ProofError:
        raise
    except (OSError, UnicodeError) as exc:
        raise ProofError(f"could not read proof receipt {path}: {exc}") from exc
    return _strict_json_object(text, role=f"proof receipt {path}")


def _expect_exact_keys(value: dict[str, Any], expected: set[str], *, role: str) -> None:
    observed = set(value)
    if observed != expected:
        missing = sorted(expected - observed)
        extra = sorted(observed - expected)
        raise ProofError(f"{role} keys differ; missing={missing}, extra={extra}")


def _is_sha256(value: Any) -> bool:
    if not isinstance(value, str) or len(value) != 64:
        return False
    try:
        int(value, 16)
    except ValueError:
        return False
    return value == value.lower()


def _validate_nonnegative_counts(value: Any, *, role: str) -> dict[str, int]:
    if not isinstance(value, dict):
        raise ProofError(f"{role} must be an object")
    result: dict[str, int] = {}
    for key, count in value.items():
        if not isinstance(key, str) or not key:
            raise ProofError(f"{role} keys must be non-empty strings")
        if isinstance(count, bool) or not isinstance(count, int) or count < 0:
            raise ProofError(f"{role} values must be non-negative integers")
        result[key] = count
    return result


def _validate_difference_labels(
    value: Any, counts: dict[str, int], *, role: str
) -> None:
    if not isinstance(value, dict) or set(value) != set(PROPERTY_NAMES):
        raise ProofError(f"{role} property keys are incomplete")
    for name, label in value.items():
        if counts[name] == 0:
            if label is not None:
                raise ProofError(f"{role}.{name} must be null when its count is zero")
            continue
        if not isinstance(label, str) or not label.startswith("U+"):
            raise ProofError(f"{role}.{name} must be a Unicode code-point label")
        try:
            codepoint = int(label[2:], 16)
        except ValueError as exc:
            raise ProofError(
                f"{role}.{name} must be a Unicode code-point label"
            ) from exc
        if not 0 <= codepoint < TOTAL_CODEPOINTS or label != f"U+{codepoint:04X}":
            raise ProofError(f"{role}.{name} has a non-canonical code-point label")


def validate_receipt(receipt: dict[str, Any]) -> None:
    """Validate identity and the narrow semantic claims made by this receipt."""

    _expect_exact_keys(
        receipt,
        {
            "artifactKind",
            "conclusion",
            "counterexamples",
            "id",
            "limitations",
            "method",
            "proofInputs",
            "protocolVersion",
            "receiptVersion",
            "runtimes",
            "singleCodepointComparison",
        },
        role="proof receipt",
    )
    if receipt.get("artifactKind") != ARTIFACT_KIND:
        raise ProofError("unexpected artifactKind")
    if receipt.get("receiptVersion") != RECEIPT_VERSION:
        raise ProofError("unexpected receiptVersion")
    if receipt.get("protocolVersion") != "0.2.0":
        raise ProofError("unexpected protocolVersion")
    if receipt.get("conclusion") != CONCLUSION:
        raise ProofError("proof receipt conclusion drifted")
    if receipt.get("limitations") != list(LIMITATIONS):
        raise ProofError("proof receipt limitations drifted")
    if receipt.get("method") != expected_method():
        raise ProofError("proof receipt method drifted")

    proof_inputs = receipt.get("proofInputs")
    if not isinstance(proof_inputs, dict):
        raise ProofError("proofInputs must be an object")
    _expect_exact_keys(proof_inputs, set(PROOF_INPUT_SPECS), role="proofInputs")
    for name, (relative_path, source_path) in PROOF_INPUT_SPECS.items():
        binding = proof_inputs[name]
        if not isinstance(binding, dict):
            raise ProofError(f"proofInputs.{name} must be an object")
        _expect_exact_keys(binding, {"path", "sha256"}, role=f"proofInputs.{name}")
        if binding.get("path") != relative_path:
            raise ProofError(f"proofInputs.{name}.path drifted")
        if binding.get("sha256") != _sha256_file(source_path):
            raise ProofError(f"proofInputs.{name}.sha256 drifted")

    comparison = receipt.get("singleCodepointComparison")
    if not isinstance(comparison, dict):
        raise ProofError("proof receipt is missing singleCodepointComparison")
    _expect_exact_keys(
        comparison,
        {
            "categoryTransitions",
            "comparedCodepoints",
            "differingCodepointCount",
            "differenceSetSha256",
            "eastAsianWidthTransitions",
            "firstDifferenceByProperty",
            "lastDifferenceByProperty",
            "propertyDifferenceCounts",
            "propertyDifferenceSetSha256",
            "whitespaceTransitions",
        },
        role="singleCodepointComparison",
    )
    if comparison.get("comparedCodepoints") != TOTAL_CODEPOINTS:
        raise ProofError("proof receipt does not cover every Unicode code point")
    counts = _validate_nonnegative_counts(
        comparison.get("propertyDifferenceCounts"),
        role="propertyDifferenceCounts",
    )
    if set(counts) != set(PROPERTY_NAMES):
        raise ProofError("proof receipt property counts are incomplete")
    difference_count = comparison.get("differingCodepointCount")
    if (
        isinstance(difference_count, bool)
        or not isinstance(difference_count, int)
        or not 0 <= difference_count <= TOTAL_CODEPOINTS
    ):
        raise ProofError("invalid differingCodepointCount")
    if counts and not max(counts.values()) <= difference_count <= sum(counts.values()):
        raise ProofError("differingCodepointCount contradicts property counts")
    if not _is_sha256(comparison.get("differenceSetSha256")):
        raise ProofError("invalid differenceSetSha256")
    property_hashes = comparison.get("propertyDifferenceSetSha256")
    if not isinstance(property_hashes, dict) or set(property_hashes) != set(
        PROPERTY_NAMES
    ):
        raise ProofError("property difference-set hashes are incomplete")
    empty_digest = hashlib.sha256().hexdigest()
    for name, digest in property_hashes.items():
        if not _is_sha256(digest):
            raise ProofError(f"invalid property difference-set hash for {name}")
        if counts[name] == 0 and digest != empty_digest:
            raise ProofError(f"empty difference set for {name} has a non-empty digest")
    if difference_count == 0 and comparison["differenceSetSha256"] != empty_digest:
        raise ProofError("empty union difference set has a non-empty digest")
    _validate_difference_labels(
        comparison.get("firstDifferenceByProperty"),
        counts,
        role="firstDifferenceByProperty",
    )
    _validate_difference_labels(
        comparison.get("lastDifferenceByProperty"),
        counts,
        role="lastDifferenceByProperty",
    )
    transition_specs = (
        ("categoryTransitions", "category"),
        ("eastAsianWidthTransitions", "eastAsianWidth"),
        ("whitespaceTransitions", "isSpace"),
    )
    for transition_name, property_name in transition_specs:
        transitions = _validate_nonnegative_counts(
            comparison.get(transition_name), role=transition_name
        )
        if sum(transitions.values()) != counts[property_name]:
            raise ProofError(f"{transition_name} contradicts {property_name} count")

    runtimes = receipt.get("runtimes")
    if not isinstance(runtimes, dict) or set(runtimes) != set(ROLE_SPECS):
        raise ProofError("proof receipt runtime roles are incomplete")
    runtime_keys = {
        "cacheTag",
        "compiler",
        "executableSha256",
        "implementation",
        "platform",
        "probeBoundary",
        "propertyTable",
        "pythonBuild",
        "pythonSeries",
        "pythonVersion",
        "runtimeValidation",
        "soabi",
        "sysVersion",
        "unicodeDatabaseVersion",
        "unicodeModuleSha256",
    }
    expected_probe_boundary = {
        "canonicalScoringEntryPointsCalled": False,
        "publicPurePrimitivesOnly": True,
        "runtimeConstantsChanged": False,
    }
    for role, expected in ROLE_SPECS.items():
        runtime = runtimes[role]
        if not isinstance(runtime, dict):
            raise ProofError(f"invalid runtime identity for {role}")
        _expect_exact_keys(runtime, runtime_keys, role=f"runtimes.{role}")
        for key, value in expected.items():
            if runtime.get(key) != value:
                raise ProofError(f"runtime identity drift for {role}.{key}")
        if runtime.get("implementation") != "CPython":
            raise ProofError(f"runtime identity drift for {role}.implementation")
        if not _is_sha256(runtime.get("executableSha256")):
            raise ProofError(f"invalid executableSha256 for {role}")
        unicode_module_sha = runtime.get("unicodeModuleSha256")
        if unicode_module_sha is not None and not _is_sha256(unicode_module_sha):
            raise ProofError(f"invalid unicodeModuleSha256 for {role}")
        if runtime.get("probeBoundary") != expected_probe_boundary:
            raise ProofError(f"probe boundary drift for {role}")
        property_table = runtime.get("propertyTable")
        if not isinstance(property_table, dict):
            raise ProofError(f"propertyTable must be an object for {role}")
        _expect_exact_keys(
            property_table, {"bytes", "sha256"}, role=f"runtimes.{role}.propertyTable"
        )
        table_bytes = property_table.get("bytes")
        if (
            isinstance(table_bytes, bool)
            or not isinstance(table_bytes, int)
            or not 0 < table_bytes <= MAX_PROPERTY_TABLE_BYTES
        ):
            raise ProofError(f"invalid property table byte count for {role}")
        if not _is_sha256(property_table.get("sha256")):
            raise ProofError(f"invalid property table digest for {role}")
        runtime_validation = runtime.get("runtimeValidation")
        if not isinstance(runtime_validation, dict):
            raise ProofError(f"runtimeValidation must be an object for {role}")
        _expect_exact_keys(
            runtime_validation,
            {"accepted", "error"},
            role=f"runtimes.{role}.runtimeValidation",
        )
        if role == "reference":
            if runtime_validation != {"accepted": True, "error": None}:
                raise ProofError("reference runtime must pass the frozen guard")
        elif (
            runtime_validation.get("accepted") is not False
            or not isinstance(runtime_validation.get("error"), str)
            or not runtime_validation["error"]
        ):
            raise ProofError("negative-control runtime must fail the frozen guard")

    if receipt.get("counterexamples") != expected_counterexamples():
        raise ProofError("proof receipt counterexample semantics drifted")
    expected_id = receipt.get("id")
    payload = {key: value for key, value in receipt.items() if key != "id"}
    if expected_id != _artifact_id(payload):
        raise ProofError("proof receipt artifact id mismatch")


def _semantic_projection(receipt: dict[str, Any]) -> dict[str, Any]:
    """Exclude machine identity while retaining every reproduced claim."""

    return {
        "artifactKind": receipt["artifactKind"],
        "conclusion": receipt["conclusion"],
        "counterexamples": receipt["counterexamples"],
        "limitations": receipt["limitations"],
        "method": receipt["method"],
        "proofInputs": receipt["proofInputs"],
        "protocolVersion": receipt["protocolVersion"],
        "receiptVersion": receipt["receiptVersion"],
        "runtimeSemantics": {
            role: {
                "implementation": receipt["runtimes"][role]["implementation"],
                "propertyTable": receipt["runtimes"][role]["propertyTable"],
                "pythonSeries": receipt["runtimes"][role]["pythonSeries"],
                "runtimeValidation": receipt["runtimes"][role]["runtimeValidation"],
                "unicodeDatabaseVersion": receipt["runtimes"][role][
                    "unicodeDatabaseVersion"
                ],
            }
            for role in ROLE_SPECS
        },
        "singleCodepointComparison": receipt["singleCodepointComparison"],
    }


def check_receipt(expected_path: Path, observed: dict[str, Any]) -> None:
    expected = _load_json(expected_path)
    validate_receipt(expected)
    validate_receipt(observed)
    if _semantic_projection(expected) != _semantic_projection(observed):
        raise ProofError("reproduced Unicode semantics differ from the checked receipt")


def _write_new(path: Path, content: bytes) -> None:
    try:
        with path.open("xb") as handle:
            handle.write(content)
    except FileExistsError as exc:
        raise ProofError(f"refusing to replace existing output: {path}") from exc
    except OSError as exc:
        raise ProofError(f"could not write proof receipt {path}: {exc}") from exc


def _positive_timeout(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be an integer") from exc
    if not 1 <= parsed <= 3600:
        raise argparse.ArgumentTypeError("must be in [1, 3600]")
    return parsed


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Reproduce Aleph-Bench v0.2 Unicode runtime drift offline."
    )
    parser.add_argument("--python311", help="explicit CPython 3.11/UCD 14 path")
    parser.add_argument("--python313", help="explicit CPython 3.13/UCD 15.1 path")
    parser.add_argument("--check", type=Path, help="reproduce and check this receipt")
    parser.add_argument("--output", type=Path, help="write a new receipt; never overwrite")
    parser.add_argument(
        "--timeout-seconds", type=_positive_timeout, default=600, help=argparse.SUPPRESS
    )
    parser.add_argument("--_worker-runtime-table", type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args()

    if args._worker_runtime_table is not None:
        observation = observe_counterexamples()
        write_property_table(args._worker_runtime_table)
        print(_canonical_json_bytes(observation).decode("ascii"))
        return 0
    if not args.python311 or not args.python313:
        parser.error("--python311 and --python313 are required")
    if args.check is not None and args.output is not None:
        parser.error("--check and --output are mutually exclusive")

    try:
        receipt = build_receipt(
            args.python311,
            args.python313,
            timeout_seconds=args.timeout_seconds,
        )
        if args.check is not None:
            check_receipt(args.check, receipt)
            print(f"Unicode compatibility proof matches {args.check}")
        elif args.output is not None:
            _write_new(args.output, _pretty_json_bytes(receipt))
            print(f"wrote Unicode compatibility proof to {args.output}")
        else:
            sys.stdout.buffer.write(_pretty_json_bytes(receipt))
    except ProofError as exc:
        print(f"Unicode compatibility proof failed: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
