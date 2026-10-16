"""Declared frozen comparison instances.

Each instance is a complete ``ComparisonConfig`` mapping (strictly parsed):
the pinned model identity, the target set (with the raw-side presets and
their exact expected config digests), the readable-side settings, the shared
wall-clock envelope, and the reproduction threshold tau. Instances are
declarations, not suggestions — records embed the exact mapping and its
``aleph-canonical/0.2.0`` digest.

- ``canary-1p7b``: the required canary instance on the pinned 1.7B snapshot —
  ``hello world`` (raw side acquired in the reproduction canary) and
  ``jumps over the lazy dog`` (the negative/partial control that the raw side
  did not acquire under its declared budget).
- ``canary-4b``: the second-pin instance on the pinned 4B snapshot — the same
  canary target under a bounded declared raw preset.
"""

from __future__ import annotations

from search.miniprompt import fixtures as miniprompt_fixtures

from .config import (
    CONFIG_SCHEMA,
    EXPLICIT_WRAPPER,
    ComparisonConfig,
    config_from_canonical,
)

METRIC_EMBEDDING = {
    "kind": "embedding_cosine",
    "model": "sentence-transformers/all-MiniLM-L6-v2",
}


def _target(key: str, text: str, preset_name: str) -> dict:
    preset = miniprompt_fixtures.preset(preset_name)
    if preset.target != text:
        raise ValueError(
            f"comparison target {key!r} declares {text!r} but preset "
            f"{preset_name!r} targets {preset.target!r}"
        )
    return {
        "key": key,
        "text": text,
        "rawPreset": preset_name,
        "rawConfigDigest": preset.digest,
    }


def _instance(label: str, repo: str, targets, **overrides) -> ComparisonConfig:
    pin = miniprompt_fixtures.PINNED_MODELS[repo]
    mapping = {
        "schema": CONFIG_SCHEMA,
        "label": label,
        "model": {
            "repo": repo,
            "revision": pin["revision"],
            "weightsDigest": pin["weightsDigest"],
        },
        "targets": targets,
        "readable": {
            "budgets": [6, 12, 25, 50],
            "candidatesPerBudget": 3,
            "refineSteps": 1,
            "stabilityRuns": 3,
            "stabilityTemperature": 0.8,
            "proposerSeed": 42,
            "metric": dict(METRIC_EMBEDDING),
        },
        "envelopeSeconds": 1800,
        "reproductionThresholdTau": 0.05,
        "explicitWrapper": EXPLICIT_WRAPPER,
    }
    mapping.update(overrides)
    return config_from_canonical(mapping)


def canary_1p7b() -> ComparisonConfig:
    return _instance(
        "canary-1p7b",
        "mlx-community/Qwen3-1.7B-4bit",
        [
            _target("hello-world", "hello world", "canary-hello"),
            _target("lazy-dog", "jumps over the lazy dog", "control-jumps-partial"),
        ],
    )


def canary_4b() -> ComparisonConfig:
    return _instance(
        "canary-4b",
        "mlx-community/Qwen3-4B-4bit",
        [_target("hello-world", "hello world", "pin4b-hello-smoke")],
    )


INSTANCES = {
    "canary-1p7b": canary_1p7b,
    "canary-4b": canary_4b,
}


def instance(name: str) -> ComparisonConfig:
    if name not in INSTANCES:
        raise KeyError(f"unknown comparison instance {name!r}; known: {', '.join(sorted(INSTANCES))}")
    return INSTANCES[name]()
