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
- ``pin4b-hello-smoke``: bounded second-pin evidence on the pinned
  ``Qwen3-4B-4bit`` snapshot (same canary target, two-rung-scale declared
  budgets), used by the matched-budget comparison's 4B instance.
- ``canary-42`` / ``canary-hamlet-line`` / ``pin4b-jumps-smoke``: the declared
  tranche-2 extension presets (numeric-minimal target; natural-short target under a
  declared tighter cap; the control target mirrored at the 4B pin), added by the
  matched-budget comparison's tranche 2 without changing any existing preset.
"""

from __future__ import annotations

from .config import CONFIG_SCHEMA, MiniPromptConfig, config_from_canonical

PINNED_MODELS = {
    "mlx-community/Qwen3-1.7B-4bit": {
        "revision": "3b1b1768f8f8cf8351c712464f906e86c2b8269e",
        "weightsDigest": "sha256:0e86d9677e519323849eac1bc272caae88567a481ff188c431f70be543d9995f",
    },
    "mlx-community/Qwen3-4B-4bit": {
        "revision": "4dcb3d101c2a062e5c1d4bb173588c54ea6c4d25",
        "weightsDigest": "sha256:e240c0bdc0ebb0681bf0da0f98d9719fd6ebe269a3633f81542c13e81345651d",
    },
}


def _declared(
    label: str,
    target: str,
    repo: str = "mlx-community/Qwen3-1.7B-4bit",
    **overrides,
) -> MiniPromptConfig:
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


def pin4b_hello_smoke() -> MiniPromptConfig:
    """Bounded second-pin run: the canary target on the pinned 4B snapshot.

    A deliberately small declared scan (three attempts, ``stepsInitial=60``)
    so the run stays bounded on the larger model; whatever the scan finds is
    archived as-is. The 4B pin identity is the one recorded by the frontier
    receipts (``4dcb3d10…``); the weights digest is re-checked fail-closed at
    load time.
    """
    return _declared(
        "pin4b-hello-smoke",
        "hello world",
        repo="mlx-community/Qwen3-4B-4bit",
        stepsInitial=60,
        stepsHardCap=1200,
        maxAttempts=3,
    )


def canary_42() -> MiniPromptConfig:
    """Numeric stratum: target ``42`` under the upstream-default scan surface.

    The feasibility receipt acquired this target at step 87/240 of a single
    5-free-token run; this preset re-runs it under the frozen module policy so
    the comparison's numeric stratum has a declared raw counterpart.
    """
    return _declared("canary-42", "42")


def canary_hamlet_line() -> MiniPromptConfig:
    """Natural-short stratum: ``to be, or not to be`` under a declared tighter cap.

    Declared below the canary defaults (``maxAttempts=6``, ``stepsHardCap=2000``)
    so the second natural-target stratum stays bounded; acquired or partial, the
    scan result is archived as-is.
    """
    return _declared(
        "canary-hamlet-line",
        "to be, or not to be",
        maxAttempts=6,
        stepsHardCap=2000,
    )


def pin4b_jumps_smoke() -> MiniPromptConfig:
    """Second-pin control mirror: the six-token control target on the 4B snapshot.

    Mirrors ``control-jumps-partial``'s declared bounds (two attempts,
    ``stepsInitial=60``) so the negative/partial control exists at both pinned
    scales.
    """
    return _declared(
        "pin4b-jumps-smoke",
        "jumps over the lazy dog",
        repo="mlx-community/Qwen3-4B-4bit",
        stepsInitial=60,
        stepsHardCap=1000,
        maxAttempts=2,
    )


PRESETS = {
    "canary-hello": canary_hello,
    "control-jumps-partial": control_jumps_partial,
    "pin4b-hello-smoke": pin4b_hello_smoke,
    "canary-42": canary_42,
    "canary-hamlet-line": canary_hamlet_line,
    "pin4b-jumps-smoke": pin4b_jumps_smoke,
}


def preset(name: str) -> MiniPromptConfig:
    if name not in PRESETS:
        raise KeyError(f"unknown preset {name!r}; known: {', '.join(sorted(PRESETS))}")
    return PRESETS[name]()
