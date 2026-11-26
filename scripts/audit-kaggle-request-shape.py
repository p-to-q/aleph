#!/usr/bin/env python3
"""Capture pinned SDK requests offline; never dispatch a benchmark or model call."""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import importlib.metadata
import io
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import tempfile
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[1]
MODEL = "anthropic/claude-haiku-4-5@20251001"
VERSIONS = {"kaggle-benchmarks": "0.6.3", "openai": "3.16.2"}
CASES = (
    ("target_description", "discovery", "Answer with only the integer that is six multiplied by seven."),
    ("empty_candidate", "discovery", ""),
    ("confirmation_shape_only", "confirmation", "Answer with only the integer that is six multiplied by seven."),
)


def inspect_request(body, prompt, phase):
    """Compare actual wire JSON with the text and decoding requested by Aleph."""
    errors = []
    if body.get("messages") != [{"role": "user", "content": prompt}]:
        errors.append("candidate_text_not_preserved")
    if body.get("model") != MODEL:
        errors.append("model_identity_not_preserved")
    if type(body.get("temperature")) not in (int, float) or body["temperature"] != 0:
        errors.append("requested_temperature_zero_not_preserved")
    expected_seed = 108 if phase == "confirmation" else 107
    if type(body.get("seed")) is not int or body["seed"] != expected_seed:
        errors.append("phase_seed_not_preserved")
    if type(body.get("max_tokens")) is not int or body["max_tokens"] != 64:
        errors.append("output_bound_not_preserved")
    return errors


def worker():
    # The parent supplies a temporary HOME and no credentials, proxies, or .env.
    forbidden = ("MODEL_PROXY_", "KAGGLE_", "OPENAI_", "ANTHROPIC_")
    if any(name.startswith(forbidden) for name in os.environ):
        raise ValueError("worker requires a credential-free environment")
    versions = {name: importlib.metadata.version(name) for name in VERSIONS}
    if versions != VERSIONS:
        raise ValueError(f"pinned SDK versions required: {VERSIONS}; observed: {versions}")
    network_attempts = []

    def network_guard(event, args):
        if event in {"socket.connect", "socket.getaddrinfo", "socket.sendto"}:
            network_attempts.append(event)
            raise RuntimeError("network forbidden during offline request audit")

    sys.addaudithook(network_guard)
    # Suppress SDK chat rendering; never capture request headers or client reprs.
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        import httpx
        import kaggle_benchmarks as kbench
        from kaggle_benchmarks.kaggle import model_proxy

        sys.path.insert(0, str(REPO))
        from search.engine.kaggle_canary import hosted_call

        captured = []
        transports = []

        def capture(request):
            if request.method != "POST" or request.url != "https://aleph.invalid/openapi/chat/completions":
                raise ValueError("unexpected mock endpoint")
            captured.append(json.loads(request.content))
            return httpx.Response(200, json={
                "id": "offline-mock", "object": "chat.completion", "created": 0,
                "model": MODEL, "choices": [{"index": 0, "finish_reason": "stop",
                    "message": {"role": "assistant", "content": "OFFLINE-MOCK"}}],
            })

        def mock_transport(*, retries):
            if retries != 0:
                raise ValueError("transport retries must remain disabled")
            transports.append({"retries": retries, "kind": "httpx.MockTransport"})
            return httpx.MockTransport(capture)

        initial_http = httpx.Client(transport=httpx.MockTransport(capture), trust_env=False)
        with patch.object(model_proxy.utils, "build_httpx_client", return_value=initial_http):
            actor = model_proxy.ModelProxy(model=MODEL, api_key="offline-not-a-credential",
                                           base_url="https://aleph.invalid")
        try:
            with patch.object(httpx, "HTTPTransport", side_effect=mock_transport):
                call = hosted_call(actor, kbench.chats, MODEL, Path("unused-offline-path"))
                for name, phase, prompt in CASES:
                    result = call(phase, prompt)
                    if result["output"] != "OFFLINE-MOCK":
                        raise ValueError("unexpected mock response")
            capability = actor.support_temperature
            retries = actor.client.max_retries
        finally:
            actor.client.close()
            initial_http.close()

    if network_attempts or len(captured) != len(CASES) or len(transports) != 1:
        raise ValueError("unexpected network attempt or mock request count")
    cases = []
    for (name, phase, prompt), body in zip(CASES, captured, strict=True):
        cases.append({"name": name, "phase": phase, "inputText": prompt,
                      "wireBody": body, "errors": inspect_request(body, prompt, phase)})
    package_root = Path(kbench.__file__).parent
    sensitive = ("actors/llms.py", "actors/proxy_openai.py", "serializers/openai.py",
                 "serializers/base.py", "kaggle/model_proxy.py")
    return {
        "schemaVersion": "aleph-kaggle-request-shape-audit/1",
        "status": "blocked" if any(case["errors"] for case in cases) else "shape_preserved",
        "scope": "local_sdk_wire_shape_not_hosted_provider_acceptance",
        "modelCalls": 0, "mockHttpRequests": len(captured), "networkAttempts": len(network_attempts),
        "responseKind": "explicit_in_memory_mock_no_provider_usage_or_cost",
        "runtime": {"python": platform.python_version(), "platform": platform.platform(),
                    "packages": {**versions, "httpx": importlib.metadata.version("httpx")}},
        "factorySupportTemperature": capability, "transportMaxRetries": retries,
        "sourceFilesSha256": {name: hashlib.sha256((package_root / name).read_bytes()).hexdigest()
                              for name in sensitive},
        "adapterSha256": hashlib.sha256((REPO / "search/engine/kaggle_canary.py").read_bytes()).hexdigest(),
        "cases": cases,
        "nextGate": "Version a faithful provider-compatible control and effective-decoding policy; obtain fresh bounded authorization before another hosted run.",
    }


def run_audit():
    """Start a fresh interpreter without inherited secrets, proxies or user config."""
    with tempfile.TemporaryDirectory(prefix="aleph-request-shape-") as home:
        result = subprocess.run([sys.executable, "-I", "-B", str(Path(__file__).resolve()), "--worker"],
            cwd=home, env={"HOME": home, "PATH": os.defpath, "LANG": "C.UTF-8"},
            capture_output=True, text=True, timeout=120)
    if result.returncode:
        # Child has no credentials, but do not persist arbitrary dependency logs.
        raise RuntimeError(f"isolated SDK audit failed (exit {result.returncode}); no provider run authorized")
    report = json.loads(result.stdout)
    report["auditScriptSha256"] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    report["sourceCommit"] = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO, text=True).strip()
    report["sourceDirty"] = bool(subprocess.check_output(["git", "status", "--porcelain"], cwd=REPO, text=True))
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="new JSON receipt path (never overwritten)")
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.worker:
        print(json.dumps(worker(), sort_keys=True, allow_nan=False))
        return 0
    if not args.output:
        parser.error("--output is required")
    if args.output.exists():
        parser.error("output already exists; do not overwrite evidence")
    report = run_audit()
    with args.output.open("x") as handle:
        json.dump(report, handle, indent=2, sort_keys=True, allow_nan=False)
        handle.write("\n")
    print(json.dumps({"status": report["status"], "modelCalls": 0,
                      "mockHttpRequests": report["mockHttpRequests"], "receipt": str(args.output)}))
    return 2 if report["status"] == "blocked" else 0


if __name__ == "__main__":
    raise SystemExit(main())
