#!/usr/bin/env python3
"""Generated Aleph-Bench v0.2 Kaggle raw-capture canary.

This task captures raw model observations only. It does not import or execute
the v0.2 scorer and cannot emit a leaderboard or publication-eligible score.
"""

# Keep runtime annotations enabled here. Kaggle Benchmarks 0.6.1 reads the
# decorated function's ``__annotations__`` directly instead of resolving
# postponed strings, so ``-> dict`` must remain the actual built-in type.

import copy
import hashlib
import inspect
import json
import os
import platform
import re
import stat
import sys
import tempfile
import unicodedata
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

import kaggle_benchmarks as kbench


TASK_NAME = 'aleph_bench_v0_2_capture_canary'
TASK_VERSION = 3
TASK_DESCRIPTION = 'Capture the fixed Aleph-Bench v0.2 six-call Kaggle canary without scoring.'
DEFINITION_SHA256 = '093a824cae9ae66b15df0cda23bf2debc48e2e6140c0ec979e62e5b17c418b0e'
IMPLEMENTATION_SHA256 = '66c8c3cab54a05c6a2503956e7855b847b2e087189e7a72f271b96a40c012fd4'
PACKAGE_SLUG = 'aleph-bench-v02-scorer-conformance'
KAGGLE_INPUT_ROOT = Path('/kaggle/input')
DEFAULT_CAPTURE_PATH = Path.cwd() / 'aleph-bench-v0.2-kaggle-capture-canary.json'
DATASET_IDENTITY = json.loads(r'''{"hashAlgorithm":"sha256-length-framed-filename-and-content-v1","id":"aleph-bench-v0.2-public-s2","itemCount":30,"sha256":"6f3a03400ec16405414afb94c7c639f2df07f7f0797c3b58ad1c4229e52f2041"}''')
PACKAGE_IDENTITY = json.loads(r'''{"bytes":3427,"files":[{"bytes":1153,"path":"README.md","sha256":"0d31f66335c9ed1c69e2bce45a5fe97657b2bef7802a860815eb42e7a6012179"},{"bytes":764,"path":"checksums.sha256","sha256":"58bda3626fc21a0071ddeb89c97438b61f991bcf52bb5222b37e951a52f9e1d0"},{"bytes":18057,"path":"conformance/scorer-v0.2.json","sha256":"044925b055db9051329e1556ed524f165d6c8e1e47f02eaf9bdb129aeadf67c6"},{"bytes":89395,"path":"data/public_s2_items.jsonl","sha256":"53334e3e0394631ec128d7c7d2bd364ad0bc7d44b030c66cb3cc91b432e04747"},{"bytes":16621,"path":"kaggle/_scoring.py","sha256":"bf38b1ac35bc1cdb99fb59f26de5d0e6ac953ca7f29a07a2b90e7cf3b028dd01"},{"bytes":6119,"path":"kaggle/run_conformance.py","sha256":"75117c1ea0c23c675ab1e20a376dab0e461938b0b5397cb164a4d14600ba1cd8"},{"bytes":3427,"path":"package-manifest.json","sha256":"7a7aad7ae4f3fcc0bebb23cb3f3d11abe842385cc8b94e9c56a806c3c7d6089d"},{"bytes":2446,"path":"schemas/aleph-bench-item.schema.json","sha256":"ad2b014b897084552b481aa73eb0e399f137f16edbd2248a2c8a1578fd8a1bc9"},{"bytes":3494,"path":"schemas/aleph-bench-platform-package.schema.json","sha256":"48a395a6ba930785556fe356c8eb2a142a8042ba12a38c4e5fdd9649ffc765bf"},{"bytes":20453,"path":"schemas/aleph-bench-result.schema.json","sha256":"05414d02ef0d12a678e22387777adab4fb720967f8dafc58faa908b4b57f9bfb"}],"id":"aleph-bench-v0.2-scorer-conformance","manifest":{"artifacts":[{"bytes":1153,"encodingFormat":"text/markdown","path":"README.md","role":"docs","sha256":"0d31f66335c9ed1c69e2bce45a5fe97657b2bef7802a860815eb42e7a6012179"},{"bytes":18057,"encodingFormat":"application/json","path":"conformance/scorer-v0.2.json","role":"conformance","sha256":"044925b055db9051329e1556ed524f165d6c8e1e47f02eaf9bdb129aeadf67c6"},{"bytes":89395,"encodingFormat":"application/x-ndjson","path":"data/public_s2_items.jsonl","role":"data","sha256":"53334e3e0394631ec128d7c7d2bd364ad0bc7d44b030c66cb3cc91b432e04747"},{"bytes":16621,"encodingFormat":"text/x-python","path":"kaggle/_scoring.py","role":"kaggle","sha256":"bf38b1ac35bc1cdb99fb59f26de5d0e6ac953ca7f29a07a2b90e7cf3b028dd01"},{"bytes":6119,"encodingFormat":"text/x-python","path":"kaggle/run_conformance.py","role":"kaggle","sha256":"75117c1ea0c23c675ab1e20a376dab0e461938b0b5397cb164a4d14600ba1cd8"},{"bytes":2446,"encodingFormat":"application/json","path":"schemas/aleph-bench-item.schema.json","role":"schemas","sha256":"ad2b014b897084552b481aa73eb0e399f137f16edbd2248a2c8a1578fd8a1bc9"},{"bytes":3494,"encodingFormat":"application/json","path":"schemas/aleph-bench-platform-package.schema.json","role":"schemas","sha256":"48a395a6ba930785556fe356c8eb2a142a8042ba12a38c4e5fdd9649ffc765bf"},{"bytes":20453,"encodingFormat":"application/json","path":"schemas/aleph-bench-result.schema.json","role":"schemas","sha256":"05414d02ef0d12a678e22387777adab4fb720967f8dafc58faa908b4b57f9bfb"}],"createdAt":"2026-09-17T00:00:00Z","datasetHashAlgorithm":"sha256-length-framed-filename-and-content-v1","datasetId":"aleph-bench-v0.2-public-s2","datasetItemCount":30,"datasetSha256":"6f3a03400ec16405414afb94c7c639f2df07f7f0797c3b58ad1c4229e52f2041","evidenceMode":"none","id":"aleph-bench-v0.2-scorer-conformance","notes":["The vendored scorer is byte-identical to bench/engine/scoring_core.py.","This scorer-core package is integration and conformance staging, not a complete Kaggle evaluator.","Submission I/O, model execution, AURC/ECL aggregation, and leaderboard hosting are out of scope.","This package is not model evidence or a leaderboard."],"packageKind":"scorer_conformance","packageVersion":"0.2.0","protocolVersion":"0.2.0","scoringProfile":{"leakageFailClosedPolicy":"bidi_controls_and_cjk_compatibility_ideographs_v1","leakageUnit":"unicode_dual_channel_v1","lexicalProfile":"unicode_nfc_casefold_whitespace_char3_multiset_jaccard_v1","maxNormalizedTextCharacters":32768,"maxQuadraticCells":1000000,"maxScoringTextCharacters":16384,"normalizationProfile":"unicode_nfc_newline_v1","pythonVersion":"3.13","responseCaptureVersion":"raw-v1","schemaVersion":"0.2.0","scorerId":"aleph-unicode","scorerVersion":"0.2.0","unicodeDatabaseVersion":"15.1.0"},"targetPlatforms":["kaggle_community_benchmark"],"validationCommands":["python3 kaggle/run_conformance.py"]},"manifestPath":"package-manifest.json","sha256":"7a7aad7ae4f3fcc0bebb23cb3f3d11abe842385cc8b94e9c56a806c3c7d6089d"}''')
CALL_PLAN_IDENTITY = json.loads(r'''{"fullShardPlanSha256":"fb2b01bd9984ddc830322baa2aeeb1f0c3ee006a41a641241bd5eaaed9dc7fd7","id":"aleph-bench-v0.2-frozen-call-plan","rerunsPerPrompt":5,"sha256":"c8761e280e089da4eed5871b9efad770284be9178bb6a4253d81cb43e873f6ec","totalPlannedCallCount":900}''')
REQUEST_POLICY = json.loads(r'''{"conversationIsolation":"oneNamedChatPerPromptAndRerun","maxAttemptsPerCall":1,"maxOutputTokens":2048,"nearCapMarginTokens":32,"reasoning":null,"seed":0,"temperature":0,"transportRetries":0}''')
SHARD = json.loads(r'''{"coverageSha256":"2e16bf9db5e67f059f7b42475e0f4df2b140a151354e120f07b2fe671691c2c0","fullShardPlanSha256":"fb2b01bd9984ddc830322baa2aeeb1f0c3ee006a41a641241bd5eaaed9dc7fd7","id":"capture-canary-01","plannedCalls":[{"conversationName":"aleph-capture-s2-001-s2-001-r1-p0-rerun-0","itemId":"s2-001","promptCodePointCount":184,"promptId":"s2-001-r1-p0","promptText":"Create S2-001 arithmetic card. Use start 6, step 3, three rows. For row r, print n=start+(r-1)*step, n+step, n*step, and the glyph sequence blue, copper, jade. End with checksum A-195.","promptUtf8Sha256":"ff865924eb8d5566402183c70d98ffa01157bb025b2d3d3f158de4b68ec44713","rerunIndex":0,"rowId":"s2-001:s2-001-r1-p0:rerun-0"},{"conversationName":"aleph-capture-s2-001-s2-001-r1-p1-rerun-0","itemId":"s2-001","promptCodePointCount":189,"promptId":"s2-001-r1-p1","promptText":"Render an arithmetic card named S2-001 arithmetic card: three numbered rows from start 6 with step 3; include fields n, n+step, n*step, glyph using blue, copper, jade; final checksum A-195.","promptUtf8Sha256":"e9a9f179d95375e8c5afb9f17b5702c2920c1131d162ddb1407fa66b6f912b4e","rerunIndex":0,"rowId":"s2-001:s2-001-r1-p1:rerun-0"},{"conversationName":"aleph-capture-s2-002-s2-002-r1-p0-rerun-0","itemId":"s2-002","promptCodePointCount":321,"promptId":"s2-002-r1-p0","promptText":"Create S2-002 letter lattice. Four lettered lines A-D use names Aster, Beryl, Cato, Dessa. For each line write '<letter>. <name> <verb> the <color> <noun> at <number>.' Use values Aster:copper:cipher:clicks:24; Beryl:jade:delta:drifts:33; Cato:violet:ember:echoes:42; Dessa:silver:fable:folds:51. End with checksum L-108.","promptUtf8Sha256":"7c408ea13ebc21d08508f979137f2d2d9d5be8a52882a840aba92a97badfd8a8","rerunIndex":0,"rowId":"s2-002:s2-002-r1-p0:rerun-0"},{"conversationName":"aleph-capture-s2-002-s2-002-r1-p1-rerun-0","itemId":"s2-002","promptCodePointCount":255,"promptId":"s2-002-r1-p1","promptText":"Render a letter lattice titled S2-002 letter lattice: A-D lines with the fixed name/color/noun/verb/number tuples Aster:copper:cipher:clicks:24; Beryl:jade:delta:drifts:33; Cato:violet:ember:echoes:42; Dessa:silver:fable:folds:51 and final checksum L-108.","promptUtf8Sha256":"375010796c2a832806f4454c302539362e8571a19de0244c3a8ea2908dba365e","rerunIndex":0,"rowId":"s2-002:s2-002-r1-p1:rerun-0"},{"conversationName":"aleph-capture-s2-003-s2-003-r1-p0-rerun-0","itemId":"s2-003","promptCodePointCount":204,"promptId":"s2-003-r1-p0","promptText":"Create S2-003 route receipt. Print four legs as 'leg i: go direction for distance; mark=mark'. Use leg triples west:14:Q5; north:7:T8; east:13:N4; south:6:V6. Then print total 40, parity even, code R-775.","promptUtf8Sha256":"abd8ed7c3daab75256082f8e63b0d9e598ae86085e784dc88f298a484763262b","rerunIndex":0,"rowId":"s2-003:s2-003-r1-p0:rerun-0"},{"conversationName":"aleph-capture-s2-003-s2-003-r1-p1-rerun-0","itemId":"s2-003","promptCodePointCount":172,"promptId":"s2-003-r1-p1","promptText":"Render a route receipt named S2-003 route receipt; four legs from triples west:14:Q5; north:7:T8; east:13:N4; south:6:V6; finish with total 40, parity even, and code R-775.","promptUtf8Sha256":"7db2347fdb61a035ad26735b1da61b38a88991a5aead71fbc658401d5985d7b8","rerunIndex":0,"rowId":"s2-003:s2-003-r1-p1:rerun-0"}]}''')
TASK_IDENTITY = {
    "name": TASK_NAME,
    "version": str(TASK_VERSION),
    "sourcePath": 'bench/tasks/kaggle/aleph_bench_v0_2_capture.py',
    "definitionSha256": DEFINITION_SHA256,
    "implementationSha256": IMPLEMENTATION_SHA256,
}


CAPTURE_SCHEMA_VERSION = "1.1.0"
ARTIFACT_KIND = "aleph_bench_kaggle_raw_capture"
TARGET_PROTOCOL_VERSION = "0.2.0"
ARTIFACT_ID_PREFIX = "aleph-bench-kaggle-capture-v1-artifact-"
MAX_CAPTURE_BYTES = 16 * 1024 * 1024
MAX_RAW_OUTPUT_CODEPOINTS = 65_536
MAX_SCORING_TEXT_CODEPOINTS = 16_384
MAX_PACKAGE_FILES = 32
MAX_PACKAGE_BYTES = 32 * 1024 * 1024
MAX_KAGGLE_INPUT_ENTRIES = 256
MAX_PACKAGE_DISCOVERY_REASON_CODEPOINTS = 240
_CLEAN_FINISH_REASONS = frozenset({"stop", "end_turn", "eos", "completed"})
_TOKEN_LIMIT_FINISH_REASONS = frozenset(
    {"length", "max_tokens", "max_output_tokens", "token_limit", "MAX_TOKENS"}
)
_SUPPORTED_OPENAI_TYPES = frozenset(
    {
        "kaggle_benchmarks.actors.llms.OpenAI",
        "kaggle_benchmarks.actors.proxy_openai.OpenAI",
    }
)
_SUPPORTED_GENAI_TYPES = frozenset(
    {
        "kaggle_benchmarks.actors.llms.GoogleGenAI",
        "kaggle_benchmarks.actors.proxy_genai.GoogleGenAI",
    }
)


def _utc_now():
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace(
        "+00:00", "Z"
    )


def _sha256(data):
    return hashlib.sha256(data).hexdigest()


def _canonical_json_bytes(value):
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("ascii")


def _canonical_string_sha256(value):
    if not isinstance(value, str):
        raise ValueError("canonical string digest requires a string")
    return _sha256(
        json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=True,
            separators=(",", ":"),
        ).encode("ascii")
    )


def _artifact_id(payload):
    body = {key: value for key, value in payload.items() if key != "id"}
    return ARTIFACT_ID_PREFIX + _sha256(_canonical_json_bytes(body))


def _has_adjacent_surrogate_pair(value):
    return any(
        0xD800 <= ord(value[index]) <= 0xDBFF
        and 0xDC00 <= ord(value[index + 1]) <= 0xDFFF
        for index in range(len(value) - 1)
    )


def _has_lone_surrogate(value):
    index = 0
    while index < len(value):
        codepoint = ord(value[index])
        if 0xD800 <= codepoint <= 0xDBFF:
            if index + 1 < len(value) and 0xDC00 <= ord(value[index + 1]) <= 0xDFFF:
                index += 2
                continue
            return True
        if 0xDC00 <= codepoint <= 0xDFFF:
            return True
        index += 1
    return False


def _exception_record(kind, exc):
    exception_type = f"{type(exc).__module__}.{type(exc).__qualname__}"
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_.]*", exception_type):
        exception_type = "builtins.Exception"
    return {
        "failureKind": kind,
        "exceptionType": exception_type[:256],
        "messageStringSha256": _canonical_string_sha256(str(exc)),
    }


def _runtime_observation():
    return {
        "pythonVersion": f"{sys.version_info.major}.{sys.version_info.minor}",
        "pythonFullVersion": platform.python_version(),
        "unicodeDatabaseVersion": unicodedata.unidata_version,
        "platform": platform.platform(),
    }


def _reject_duplicate_pairs(pairs):
    value = {}
    for key, child in pairs:
        if key in value:
            raise ValueError("duplicate JSON key in package artifact")
        value[key] = child
    return value


def _safe_package_path(root, relative):
    path = PurePosixPath(relative)
    if (
        not relative
        or "\\" in relative
        or relative.startswith("/")
        or str(path) != relative
        or any(part in {"", ".", ".."} for part in path.parts)
    ):
        raise ValueError("unsafe package path")
    return root.joinpath(*path.parts)


def _read_exact_regular_file(root, expected):
    path = _safe_package_path(root, expected["path"])
    flags = os.O_RDONLY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor = os.open(path, flags)
    try:
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1:
            raise ValueError("package artifact is not a single-link regular file")
        if before.st_size != expected["bytes"]:
            raise ValueError("package artifact size mismatch")
        chunks = []
        remaining = before.st_size
        while remaining:
            chunk = os.read(descriptor, min(remaining, 1_048_576))
            if not chunk:
                raise ValueError("package artifact ended before its declared size")
            chunks.append(chunk)
            remaining -= len(chunk)
        if os.read(descriptor, 1):
            raise ValueError("package artifact grew while being read")
        after = os.fstat(descriptor)
    finally:
        os.close(descriptor)
    if (
        before.st_dev,
        before.st_ino,
        before.st_size,
        before.st_mtime_ns,
        before.st_ctime_ns,
    ) != (
        after.st_dev,
        after.st_ino,
        after.st_size,
        after.st_mtime_ns,
        after.st_ctime_ns,
    ):
        raise ValueError("package artifact changed while being read")
    data = b"".join(chunks)
    if _sha256(data) != expected["sha256"]:
        raise ValueError("package artifact digest mismatch")
    return data


def _scan_package(root):
    observed_files = []
    pending = [(root, "")]
    while pending:
        directory, prefix = pending.pop()
        entries = sorted(os.scandir(directory), key=lambda entry: entry.name)
        for entry in entries:
            relative = f"{prefix}/{entry.name}" if prefix else entry.name
            metadata = entry.stat(follow_symlinks=False)
            if stat.S_ISLNK(metadata.st_mode):
                raise ValueError("package contains a symlink")
            if stat.S_ISDIR(metadata.st_mode):
                pending.append((Path(entry.path), relative))
            elif stat.S_ISREG(metadata.st_mode):
                observed_files.append(relative)
                if len(observed_files) > MAX_PACKAGE_FILES:
                    raise ValueError("package file-count limit exceeded")
            else:
                raise ValueError("package contains a non-regular entry")
    return sorted(observed_files)


def _verify_package(package_root):
    root = Path(package_root)
    metadata = root.lstat()
    if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISDIR(metadata.st_mode):
        raise ValueError("package mount must be a directory, not a symlink")
    expected_files = PACKAGE_IDENTITY["files"]
    if len(expected_files) > MAX_PACKAGE_FILES:
        raise ValueError("embedded package file-count limit exceeded")
    if sum(row["bytes"] for row in expected_files) > MAX_PACKAGE_BYTES:
        raise ValueError("embedded package byte limit exceeded")
    if _scan_package(root) != [row["path"] for row in expected_files]:
        raise ValueError("package closed-world file set mismatch")
    contents = {
        row["path"]: _read_exact_regular_file(root, row) for row in expected_files
    }
    manifest = json.loads(
        contents[PACKAGE_IDENTITY["manifestPath"]].decode("utf-8"),
        object_pairs_hook=_reject_duplicate_pairs,
        parse_constant=lambda _value: (_ for _ in ()).throw(
            ValueError("non-finite package JSON constant")
        ),
    )
    if manifest != PACKAGE_IDENTITY["manifest"]:
        raise ValueError("package manifest semantic mismatch")
    items = []
    for line in contents["data/public_s2_items.jsonl"].decode("utf-8").splitlines():
        if not line:
            raise ValueError("blank package item line")
        item = json.loads(line, object_pairs_hook=_reject_duplicate_pairs)
        items.append(item)
    if len(items) != DATASET_IDENTITY["itemCount"]:
        raise ValueError("package item count mismatch")
    expected_prompts = {
        call["promptId"]: call for call in SHARD["plannedCalls"]
    }
    observed_prompts = {}
    for item in items:
        for prompt in item.get("frozenLadder", []):
            prompt_id = prompt.get("id")
            if prompt_id not in expected_prompts:
                continue
            observed = {
                "itemId": item.get("id"),
                "promptId": prompt_id,
                "promptText": prompt.get("prompt"),
            }
            if prompt_id in observed_prompts:
                raise ValueError("duplicate canary prompt in package")
            observed_prompts[prompt_id] = observed
    for call in SHARD["plannedCalls"]:
        observed = observed_prompts.get(call["promptId"])
        if observed != {
            "itemId": call["itemId"],
            "promptId": call["promptId"],
            "promptText": call["promptText"],
        }:
            raise ValueError("package canary prompt mismatch")


def _bounded_child_directories(root):
    root = Path(root)
    try:
        entries = sorted(os.scandir(root), key=lambda entry: entry.name)
    except FileNotFoundError:
        return []
    if len(entries) > MAX_KAGGLE_INPUT_ENTRIES:
        raise ValueError("Kaggle input directory entry limit exceeded")
    return [
        Path(entry.path)
        for entry in entries
        if entry.is_dir(follow_symlinks=False)
    ]


def _kaggle_package_candidates(input_root=KAGGLE_INPUT_ROOT):
    root = Path(input_root)
    candidates = [root / PACKAGE_SLUG]
    # Kaggle has used both /kaggle/input/<slug> and the fully-qualified
    # /kaggle/input/datasets/<owner>/<slug> layout. Inspect at most two bounded
    # directory levels; the package hash and closed-world file set remain the
    # authority, never a directory name discovered at runtime.
    for parent in (root, root / "datasets"):
        for child in _bounded_child_directories(parent):
            candidates.append(child / PACKAGE_SLUG)
    unique = []
    seen = set()
    for candidate in candidates:
        key = os.fspath(candidate)
        if key not in seen:
            seen.add(key)
            unique.append(candidate)
    return unique


def _resolve_and_verify_package(package_root, *, input_root=KAGGLE_INPUT_ROOT):
    if package_root is not None:
        root = Path(package_root)
        _verify_package(root)
        return root

    matches = []
    inspected = 0
    first_validation_error = None
    for candidate in _kaggle_package_candidates(input_root):
        try:
            _verify_package(candidate)
        except (FileNotFoundError, NotADirectoryError):
            inspected += 1
            continue
        except ValueError as exc:
            inspected += 1
            reason = str(exc)
            if first_validation_error is None and reason:
                first_validation_error = reason[:MAX_PACKAGE_DISCOVERY_REASON_CODEPOINTS]
            continue
        matches.append(candidate)
    if len(matches) != 1:
        validation_detail = (
            f"; first validation error: {first_validation_error}"
            if first_validation_error is not None
            else ""
        )
        raise ValueError(
            "expected exactly one hash-verified package mount in supported "
            f"Kaggle layouts; found {len(matches)} across "
            f"{inspected + len(matches)} candidates{validation_detail}"
        )
    return matches[0]


def _transport_retry_preflight(llm, model_type):
    try:
        client = llm.client
        if model_type in _SUPPORTED_OPENAI_TYPES:
            configure = getattr(client, "with_options", None)
            if not callable(configure):
                return "transportRetryPolicyUnverified"
            no_retry_client = configure(max_retries=0)
            if getattr(no_retry_client, "max_retries", None) != 0:
                return "transportRetryPolicyUnverified"
            llm.client = no_retry_client
            return None
        if model_type in _SUPPORTED_GENAI_TYPES:
            api_client = getattr(client, "_api_client", None)
            http_options = getattr(api_client, "_http_options", None)
            retry_options = getattr(http_options, "retry_options", object())
            # google-genai's public retry contract defines None as one attempt.
            # Do not depend on the private tenacity controller: its layout is
            # not stable across the SDK versions used by Kaggle images.
            if retry_options is not None:
                return "transportRetryPolicyUnverified"
            return None
    except Exception:
        return "transportRetryPolicyUnverified"
    return "unsupportedModelTransport"


def _model_preflight(llm):
    model_type = f"{type(llm).__module__}.{type(llm).__name__}"
    slug = getattr(llm, "model", None)
    if not isinstance(slug, str) or not re.fullmatch(
        r"[A-Za-z0-9][A-Za-z0-9._-]*"
        r"(?:/[A-Za-z0-9][A-Za-z0-9._-]*)+"
        r"(?:@[A-Za-z0-9][A-Za-z0-9._-]*)?",
        slug,
    ):
        raise ValueError("model identity unavailable or unsafe")
    if model_type in _SUPPORTED_OPENAI_TYPES:
        output_token_parameter = "max_tokens"
    elif model_type in _SUPPORTED_GENAI_TYPES:
        output_token_parameter = "max_output_tokens"
    else:
        raise ValueError("unsupported model transport")
    parameters = inspect.signature(llm.prompt).parameters
    required = {"seed", "temperature", "extra_api_params"}
    if not required.issubset(parameters):
        raise ValueError("Kaggle prompt API is incompatible")
    retry_error = _transport_retry_preflight(llm, model_type)
    if retry_error is not None:
        raise ValueError(retry_error)
    return {
        "platform": "kaggle",
        "slug": slug,
        "pythonType": model_type,
        "mappingStatus": "unmapped",
        "canonicalModelId": None,
        "providerRevision": None,
    }, output_token_parameter


def _usage_integer(value):
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else None


def _finish_reason(chat):
    try:
        messages = chat.messages
    except Exception:
        messages = []
    for message in reversed(messages):
        meta = getattr(message, "_meta", None)
        if not isinstance(meta, dict):
            continue
        value = meta.get("finish_reason", meta.get("finishReason"))
        if isinstance(value, str) and 0 < len(value) <= 256 and not any(
            ord(character) < 32 or ord(character) == 127 for character in value
        ):
            return value
    return None


def _usage_record(chat):
    try:
        usage = chat.usage
    except Exception:
        usage = None
    input_tokens = _usage_integer(getattr(usage, "input_tokens", None))
    output_tokens = _usage_integer(getattr(usage, "output_tokens", None))
    input_cost = _usage_integer(
        getattr(usage, "input_tokens_cost_nanodollars", None)
    )
    output_cost = _usage_integer(
        getattr(usage, "output_tokens_cost_nanodollars", None)
    )
    return {
        "inputTokens": input_tokens,
        "outputTokens": output_tokens,
        "inputCostNanodollars": str(input_cost) if input_cost is not None else None,
        "outputCostNanodollars": str(output_cost) if output_cost is not None else None,
        "backendLatencyMs": _usage_integer(
            getattr(usage, "total_backend_latency_ms", None)
        ),
        "finishReason": _finish_reason(chat),
    }


def _empty_usage():
    return {
        "inputTokens": None,
        "outputTokens": None,
        "inputCostNanodollars": None,
        "outputCostNanodollars": None,
        "backendLatencyMs": None,
        "finishReason": None,
    }


def _row_from_output(call, output, chat, captured_at):
    row = {
        **copy.deepcopy(call),
        "dispatchStarted": True,
        "terminalFailure": None,
        "lifecycleFailure": None,
        "usage": _usage_record(chat),
        "capturedAt": captured_at,
    }
    if isinstance(output, str):
        if _has_adjacent_surrogate_pair(output):
            raise ValueError("adjacent surrogate pair cannot be persisted losslessly")
        row["observedOutputType"] = "string"
        row["rawOutputStringSha256"] = _canonical_string_sha256(output)
        row["rawOutputCodePointCount"] = len(output)
        if len(output) <= MAX_RAW_OUTPUT_CODEPOINTS:
            row["outcome"] = "returnedString"
            row["rawOutput"] = output
        else:
            row["outcome"] = "oversizedOutput"
        return row
    row.update(
        {
            "outcome": "nonStringOutput",
            "observedOutputType": (
                "null"
                if output is None
                else "boolean"
                if isinstance(output, bool)
                else "number"
                if isinstance(output, (int, float))
                else "array"
                if isinstance(output, (list, tuple))
                else "object"
            ),
            "rawOutputStringSha256": None,
            "rawOutputCodePointCount": None,
        }
    )
    return row


def _failed_row(call, kind, exc, captured_at, *, dispatch_started, chat=None):
    return {
        **copy.deepcopy(call),
        "dispatchStarted": dispatch_started,
        "outcome": "failed",
        "observedOutputType": None,
        "rawOutputStringSha256": None,
        "rawOutputCodePointCount": None,
        "terminalFailure": _exception_record(kind, exc),
        "lifecycleFailure": None,
        "usage": _usage_record(chat) if chat is not None else _empty_usage(),
        "capturedAt": captured_at,
    }


def _derive_diagnostics(rows, active):
    planned = SHARD["plannedCalls"]
    missing = [call["rowId"] for call in planned[len(rows) :]]
    def ids(predicate):
        return [row["rowId"] for row in rows if predicate(row)]
    unpaired = ids(
        lambda row: row["outcome"] == "returnedString"
        and _has_lone_surrogate(row["rawOutput"])
    )
    missing_output = ids(lambda row: row["outcome"] == "missingOutput")
    non_string = ids(lambda row: row["outcome"] == "nonStringOutput")
    oversized = ids(lambda row: row["outcome"] == "oversizedOutput")
    terminal_failure = ids(lambda row: row["terminalFailure"] is not None)
    lifecycle_failure = ids(lambda row: row["lifecycleFailure"] is not None)
    scoring_too_long = ids(
        lambda row: row["outcome"] == "returnedString"
        and row["rawOutputCodePointCount"] > MAX_SCORING_TEXT_CODEPOINTS
    )
    missing_usage = ids(
        lambda row: row["usage"]["inputTokens"] is None
        or row["usage"]["outputTokens"] is None
    )
    missing_finish_reason = ids(
        lambda row: row["usage"]["finishReason"] is None
    )
    zero_usage = ids(
        lambda row: row["usage"]["inputTokens"] == 0
        or row["usage"]["outputTokens"] == 0
    )
    threshold = REQUEST_POLICY["maxOutputTokens"] - REQUEST_POLICY["nearCapMarginTokens"]
    near_cap = ids(
        lambda row: row["usage"]["outputTokens"] is not None
        and row["usage"]["outputTokens"] >= threshold
    )
    token_limit = ids(
        lambda row: row["usage"]["finishReason"] in _TOKEN_LIMIT_FINISH_REASONS
    )
    unsupported_finish = ids(
        lambda row: row["usage"]["finishReason"] is not None
        and row["usage"]["finishReason"] not in _CLEAN_FINISH_REASONS
        and row["usage"]["finishReason"] not in _TOKEN_LIMIT_FINISH_REASONS
    )
    active_unpersisted = active is not None and active["state"] in {"prepared", "dispatching"}
    blockers = []
    for present, reason in (
        (bool(missing), "incompleteCoverage"),
        (active_unpersisted, "activeCall"),
        (bool(unpaired), "unpairedSurrogate"),
        (bool(missing_output), "missingOutput"),
        (bool(non_string), "nonStringOutput"),
        (bool(oversized), "oversizedOutput"),
        (bool(terminal_failure), "terminalFailure"),
        (bool(lifecycle_failure), "lifecycleFailure"),
        (bool(scoring_too_long), "scoringTextTooLong"),
        (bool(missing_usage), "missingUsage"),
        (bool(near_cap), "nearCapOutput"),
        (bool(token_limit), "tokenLimitTermination"),
        (bool(unsupported_finish), "unsupportedFinishReason"),
    ):
        if present:
            blockers.append(reason)
    return {
        "coverageComplete": not missing,
        "missingPlannedRowIds": missing,
        "unpairedSurrogateRowIds": unpaired,
        "missingOutputRowIds": missing_output,
        "nonStringOutputRowIds": non_string,
        "oversizedOutputRowIds": oversized,
        "terminalFailureRowIds": terminal_failure,
        "lifecycleFailureRowIds": lifecycle_failure,
        "scoringTextTooLongRowIds": scoring_too_long,
        "missingUsageRowIds": missing_usage,
        "missingFinishReasonRowIds": missing_finish_reason,
        "zeroUsageRowIds": zero_usage,
        "nearCapOutputRowIds": near_cap,
        "tokenLimitTerminationRowIds": token_limit,
        "unsupportedFinishReasonRowIds": unsupported_finish,
        "activeCallRowId": active["call"]["rowId"] if active is not None else None,
        "replayBlockedReasons": blockers,
    }


def _payload(started_at, ended_at, runtime, model, rows, active):
    outcomes = {
        name: sum(row["outcome"] == name for row in rows)
        for name in (
            "returnedString",
            "missingOutput",
            "nonStringOutput",
            "oversizedOutput",
            "failed",
        )
    }
    diagnostics = _derive_diagnostics(rows, active)
    dispatched_rows = sum(row["dispatchStarted"] for row in rows)
    payload = {
        "captureSchemaVersion": CAPTURE_SCHEMA_VERSION,
        "artifactKind": ARTIFACT_KIND,
        "targetProtocolVersion": TARGET_PROTOCOL_VERSION,
        "leaderboardEligible": False,
        "publicationEligible": False,
        "captureComplete": diagnostics["coverageComplete"],
        "canonicalReplayEligible": (
            diagnostics["coverageComplete"]
            and not diagnostics["replayBlockedReasons"]
        ),
        "startedAt": started_at,
        "endedAt": ended_at,
        "datasetIdentity": copy.deepcopy(DATASET_IDENTITY),
        "packageIdentity": {
            key: PACKAGE_IDENTITY[key]
            for key in ("id", "manifestPath", "sha256", "bytes")
        },
        "callPlanIdentity": copy.deepcopy(CALL_PLAN_IDENTITY),
        "taskIdentity": copy.deepcopy(TASK_IDENTITY),
        "modelObservation": copy.deepcopy(model),
        "runtimeObservation": copy.deepcopy(runtime),
        "requestPolicy": copy.deepcopy(REQUEST_POLICY),
        "shard": copy.deepcopy(SHARD),
        "calls": {
            "plannedCallCount": len(SHARD["plannedCalls"]),
            "attemptedCallCount": dispatched_rows
            + (1 if active is not None and active["state"] == "dispatching" else 0),
            "terminalCallCount": dispatched_rows,
            "returnedStringCount": outcomes["returnedString"],
            "missingOutputCount": outcomes["missingOutput"],
            "nonStringOutputCount": outcomes["nonStringOutput"],
            "oversizedOutputCount": outcomes["oversizedOutput"],
            "failedCallCount": outcomes["failed"],
            "activeCall": copy.deepcopy(active),
        },
        "rows": copy.deepcopy(rows),
        "diagnostics": diagnostics,
        "id": "",
    }
    payload["id"] = _artifact_id(payload)
    return payload


def _encoded_payload(payload):
    encoded = (
        json.dumps(
            payload,
            allow_nan=False,
            ensure_ascii=True,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    ).encode("ascii")
    if len(encoded) > MAX_CAPTURE_BYTES:
        raise ValueError("capture payload exceeds its 16 MiB limit")
    return encoded


def _atomic_checkpoint(payload, capture_path):
    path = Path(capture_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_symlink():
        raise ValueError("capture path must not be a symlink")
    data = _encoded_payload(payload)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_path, path)
        directory_flags = os.O_RDONLY
        if hasattr(os, "O_DIRECTORY"):
            directory_flags |= os.O_DIRECTORY
        directory_descriptor = os.open(path.parent, directory_flags)
        try:
            os.fsync(directory_descriptor)
        finally:
            os.close(directory_descriptor)
    finally:
        if temporary_path.exists():
            temporary_path.unlink()


def run_capture_canary(
    llm,
    *,
    chats,
    package_root=None,
    capture_path=DEFAULT_CAPTURE_PATH,
    observed_runtime=None,
    clock=None,
):
    clock = clock or _utc_now
    started_at = clock()
    runtime = observed_runtime if observed_runtime is not None else _runtime_observation()
    unavailable_model = {
        "platform": "kaggle",
        "slug": "unavailable/unobserved",
        "pythonType": None,
        "mappingStatus": "unmapped",
        "canonicalModelId": None,
        "providerRevision": None,
    }
    rows = []
    active = None

    def publish(model):
        payload = _payload(started_at, clock(), runtime, model, rows, active)
        _atomic_checkpoint(payload, capture_path)
        return payload

    try:
        _resolve_and_verify_package(package_root)
    except Exception as exc:
        # Preflight failures occur before model dispatch. Emit only the
        # controlled exception class and bounded message so hosted operators
        # can distinguish package from model compatibility without guessing.
        print(
            "ALEPH_CAPTURE_PREFLIGHT_FAILED "
            f"stage=package type={type(exc).__name__} message={str(exc)[:240]}"
        )
        return publish(unavailable_model)
    try:
        model, token_parameter = _model_preflight(llm)
        if not hasattr(chats, "new") or not callable(chats.new):
            raise ValueError("Kaggle chats API is incompatible")
    except Exception as exc:
        print(
            "ALEPH_CAPTURE_PREFLIGHT_FAILED "
            f"stage=model type={type(exc).__name__} message={str(exc)[:240]}"
        )
        return publish(unavailable_model)

    publish(model)
    for call in SHARD["plannedCalls"]:
        active = {"call": copy.deepcopy(call), "state": "prepared", "updatedAt": clock()}
        publish(model)
        chat_manager = None
        chat = None
        try:
            chat_manager = chats.new(call["conversationName"])
            chat = chat_manager.__enter__()
        except Exception as exc:
            rows.append(
                _failed_row(
                    call,
                    "chatOpenFailed",
                    exc,
                    clock(),
                    dispatch_started=False,
                )
            )
            active = {"call": copy.deepcopy(call), "state": "terminalPersisted", "updatedAt": clock()}
            publish(model)
            active = None
            return publish(model)

        active = {"call": copy.deepcopy(call), "state": "dispatching", "updatedAt": clock()}
        publish(model)
        try:
            prompt_kwargs = {
                "seed": REQUEST_POLICY["seed"],
                "temperature": REQUEST_POLICY["temperature"],
                "extra_api_params": {
                    token_parameter: REQUEST_POLICY["maxOutputTokens"]
                },
            }
            if REQUEST_POLICY["reasoning"] is not None:
                prompt_kwargs["reasoning"] = REQUEST_POLICY["reasoning"]
            output = llm.prompt(call["promptText"], **prompt_kwargs)
        except BaseException as exc:
            if not isinstance(exc, Exception):
                try:
                    chat_manager.__exit__(*sys.exc_info())
                finally:
                    raise
            row = _failed_row(
                call,
                "modelCallFailed",
                exc,
                clock(),
                dispatch_started=True,
                chat=chat,
            )
        else:
            # Classification is deliberately outside the model-call handler.
            # If an exact output cannot be represented by the frozen capture
            # contract, keep the durable dispatching checkpoint instead of
            # relabeling a successful provider response as modelCallFailed.
            try:
                row = _row_from_output(call, output, chat, clock())
            except BaseException:
                try:
                    chat_manager.__exit__(*sys.exc_info())
                finally:
                    raise

        rows.append(row)
        active = {"call": copy.deepcopy(call), "state": "terminalPersisted", "updatedAt": clock()}
        publish(model)
        try:
            chat_manager.__exit__(None, None, None)
        except Exception as exc:
            row["lifecycleFailure"] = _exception_record("chatCloseFailed", exc)
            row["capturedAt"] = clock()
            active["updatedAt"] = clock()
            publish(model)
            active = None
            return publish(model)

        active = None
        payload = publish(model)
        if row["outcome"] != "returnedString":
            return payload

    return payload


@kbench.task(name=TASK_NAME, description=TASK_DESCRIPTION, version=TASK_VERSION)
def aleph_bench_v0_2_capture_canary(llm) -> dict:
    payload = run_capture_canary(llm, chats=kbench.chats)
    kbench.assertions.assert_true(
        payload["captureComplete"],
        expectation="The fixed six-call raw capture completed without retry.",
    )
    return {
        "artifactKind": payload["artifactKind"],
        "artifactId": payload["id"],
        "captureComplete": payload["captureComplete"],
        "canonicalReplayEligible": payload["canonicalReplayEligible"],
        "rowCount": len(payload["rows"]),
        "replayBlockedReasons": payload["diagnostics"]["replayBlockedReasons"],
    }


aleph_bench_v0_2_capture_canary.run(kbench.llm)
