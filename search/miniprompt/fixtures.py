"""Declared frozen run configurations for the MiniPrompt reproduction.

Presets are complete configuration mappings (strictly parsed); each preset is
a declaration, not a suggestion — receipts embed the exact mapping and its
``aleph-canonical/0.2.0`` digest.

- ``canary-hello``: the end-to-end canary (target ``hello world``) on the
  pinned MLX ``Qwen3-1.7B-4bit`` snapshot with upstream-default scan
  parameters (``topk=250``, ``batch=100``, ``num_steps=200``, ``seed=42``,
  ``max_tokens=-1`` style auto cap).
- ``control-jumps-partial``: the six-token target ``jumps over the lazy dog``
  under deliberately small declared budgets, archived as the negative/partial
  control (expected non-acquisition; higher-budget probe evidence for this
  target is in ``docs/research/2026-10-15-miniprompt-feasibility-receipt.md``).
"""

from __future__ import annotations

from .config import CONFIG_SCHEMA, MiniPromptConfig, config_from_canonical

PINNED_MODELS = {
    "mlx-community/Qwen3-1.7B-4bit": {
        "revision": "3b1b1768f8f8cf8351c712464f906e86c2b8269e",
        "weightsDigest": "sha256:0e86d9677e519323849eac1bc272caae88567a481ff188c431f70be543d9995f",
    },
}


def _declared(label: str, target: str, **overrides) -> MiniPromptConfig:
    repo = "mlx-community/Qwen3-1.7B-4bit"
    pin = PINNED_MODELS[repo]
    mapping = {
        "schema": CONFIG_SCHEMA,
        "label": label,
        "target": target,
        "model": {
            "repo": repo,
            "revision": pin["revision"],
            "weightsDigest": pin["weightsDigest"],
        },
        "scaffold": "empty",
        "decoding": "greedy",
        "successCriterion": "teacher_forced_all_match",
        "nFreeStart": 5,
        "nFreeIncrement": 5,
        "stepMultiplier": 1.2,
        "maxFreeTokens": -1,
        "stepsInitial": 200,
        "stepsHardCap": 4000,
        "maxAttempts": 8,
        "topk": 250,
        "batch": 100,
        "miniBatch": 100,
        "seed": 42,
    }
    mapping.update(overrides)
    return config_from_canonical(mapping)


def canary_hello() -> MiniPromptConfig:
    return _declared("canary-hello", "hello world")


def control_jumps_partial() -> MiniPromptConfig:
    return _declared(
        "control-jumps-partial",
        "jumps over the lazy dog",
        stepsInitial=60,
        maxAttempts=2,
        stepsHardCap=1000,
    )


PRESETS = {
    "canary-hello": canary_hello,
    "control-jumps-partial": control_jumps_partial,
}


def preset(name: str) -> MiniPromptConfig:
    if name not in PRESETS:
        raise KeyError(f"unknown preset {name!r}; known: {', '.join(sorted(PRESETS))}")
    return PRESETS[name]()
