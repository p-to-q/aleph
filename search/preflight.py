#!/usr/bin/env python3
"""Preflight checks for the optional local MLX search engine."""

from __future__ import annotations

import importlib.util
import platform
import socket
import sys
from urllib import error, request
from pathlib import Path


REQUIRED_MODULES = [
    ("mlx_lm", "mlx-lm"),
    ("sentence_transformers", "sentence-transformers"),
    ("fastapi", "fastapi"),
    ("uvicorn", "uvicorn"),
    ("numpy", "numpy"),
]
MODEL_CANDIDATES = [
    "mlx-community/Qwen3-1.7B-4bit",
    "mlx-community/Qwen3-4B-4bit",
    "Qwen/Qwen3-8B-MLX-4bit",
]


def main() -> None:
    errors: list[str] = []
    machine = platform.machine()
    print(f"architecture: {machine}")
    if machine != "arm64":
        errors.append("MLX requires Apple Silicon arm64 for this local route.")

    print(f"python: {platform.python_version()}")
    print(f"python_executable: {sys.executable}")
    print(f"virtual_env: {_virtual_env_label()}")
    if sys.prefix == sys.base_prefix and not Path("search/.venv").exists():
        print("search_venv: missing; recommended for the optional MLX search engine")

    for module, package in REQUIRED_MODULES:
        if importlib.util.find_spec(module) is None:
            errors.append(f"missing Python module `{module}`; install package `{package}`")
            print(f"{module}: missing")
        else:
            print(f"{module}: ok")

    cache_root = Path.home() / ".cache" / "huggingface" / "hub"
    cached = []
    for repo in MODEL_CANDIDATES:
        cache_dir = cache_root / ("models--" + repo.replace("/", "--"))
        if cache_dir.exists():
            cached.append(repo)
    if cached:
        print("cached_models:")
        for repo in cached:
            print(f"- {repo}")
    else:
        print("cached_models: none of the default local MLX candidates found")
        print("first live run may download a model through mlx-lm/Hugging Face")

    _check_port(errors)

    if errors:
        print("\npreflight: blocked")
        for error in errors:
            print(f"- {error}")
        print("\nsetup:")
        print("python3 -m venv search/.venv")
        print("source search/.venv/bin/activate")
        print("pip install -r search/requirements.txt")
        print("python3 search/preflight.py")
        raise SystemExit(1)

    print("\npreflight: ok")
    print("next: python3 search/server.py")


def _virtual_env_label() -> str:
    if sys.prefix != sys.base_prefix:
        return sys.prefix
    candidates = [Path("search/.venv"), Path(".venv"), Path("apps/api/.venv")]
    existing = [str(path) for path in candidates if path.exists()]
    if existing:
        return f"none active; found {', '.join(existing)}"
    return "none active"


def _check_port(errors: list[str]) -> None:
    host = "127.0.0.1"
    port = 8000
    health_url = f"http://{host}:{port}/health"

    try:
        with request.urlopen(health_url, timeout=1) as response:
            print(f"port_{port}: search health responded {response.status}")
            return
    except error.URLError:
        pass

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(1)
        if sock.connect_ex((host, port)) == 0:
            errors.append(
                "port 8000 is already in use but did not answer /health; stop that process or set ALEPH_MLX_SEARCH_URL."
            )
            print(f"port_{port}: occupied by a non-search service")
        else:
            print(f"port_{port}: available")


if __name__ == "__main__":
    main()
