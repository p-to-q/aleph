"""Frozen declared configuration for MiniPrompt reproduction runs.

One ``MiniPromptConfig`` declares a single scan: the target text, the pinned
model identity (repo + revision + weights digest), the empty-scaffold layout,
and the frozen scan/GCG parameters. Parsing is strict and fail-closed —
unknown fields, missing fields, wrong types, non-finite numbers, and
non-declared scaffold/decoding/success values are all rejected — so receipts
and run state carry the exact declaration they belong to, together with its
``aleph-canonical/0.2.0`` digest.

Parameter semantics follow the pinned upstream sources
(``locuslab/acr-memorization`` @ ``bf3ba2e7``, ``prompt_optimization/gcg.py``
and ``miniprompt.py``). Two fields are declared Aleph-side hard bounds on top
of the upstream policy: ``stepsHardCap`` (cap applied to the step budget after
upstream growth) and ``maxAttempts`` (hard limit on GCG attempts).
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path

from search.engine.canonical import digest, is_digest

CONFIG_SCHEMA = "aleph-miniprompt-config/0.1.0"

SCAFFOLD_EMPTY = "empty"
DECODING_GREEDY = "greedy"
SUCCESS_TEACHER_FORCED_ALL_MATCH = "teacher_forced_all_match"

_REQUIRED_FIELDS = (
    "schema",
    "label",
    "target",
    "model",
    "scaffold",
    "decoding",
    "successCriterion",
    "nFreeStart",
    "nFreeIncrement",
    "stepMultiplier",
    "maxFreeTokens",
    "stepsInitial",
    "stepsHardCap",
    "maxAttempts",
    "topk",
    "batch",
    "miniBatch",
    "seed",
)
_MODEL_FIELDS = ("repo", "revision", "weightsDigest")


class ConfigError(ValueError):
    """A configuration mapping violates the strict declared contract."""


def _reject_extras_and_missing(value: dict, required, where: str) -> None:
    if not isinstance(value, dict):
        raise ConfigError(f"{where}: expected a mapping")
    unknown = sorted(str(key) for key in set(value) - set(required))
    missing = sorted(set(required) - set(value))
    if unknown:
        raise ConfigError(f"{where}: unknown field(s): {', '.join(unknown)}")
    if missing:
        raise ConfigError(f"{where}: missing field(s): {', '.join(missing)}")


def _string(value: dict, key: str, where: str) -> str:
    item = value[key]
    if not isinstance(item, str) or not item:
        raise ConfigError(f"{where}.{key}: expected a non-empty string")
    return item


def _integer(value: dict, key: str, where: str, minimum: int) -> int:
    item = value[key]
    if isinstance(item, bool) or not isinstance(item, int):
        raise ConfigError(f"{where}.{key}: expected an integer")
    if item < minimum:
        raise ConfigError(f"{where}.{key}: expected >= {minimum}, got {item}")
    return item


def _multiplier(value: dict, key: str, where: str) -> float:
    item = value[key]
    if isinstance(item, bool) or not isinstance(item, (int, float)):
        raise ConfigError(f"{where}.{key}: expected a number")
    item = float(item)
    if not math.isfinite(item):
        raise ConfigError(f"{where}.{key}: expected a finite number")
    if item < 1.0:
        raise ConfigError(f"{where}.{key}: expected >= 1.0, got {item}")
    return item


@dataclass(frozen=True)
class MiniPromptConfig:
    label: str
    target: str
    repo: str
    revision: str
    weights_digest: str
    scaffold: str
    decoding: str
    success_criterion: str
    n_free_start: int
    n_free_increment: int
    step_multiplier: float
    max_free_tokens: int
    steps_initial: int
    steps_hard_cap: int
    max_attempts: int
    topk: int
    batch: int
    mini_batch: int
    seed: int

    def to_canonical(self) -> dict:
        return {
            "schema": CONFIG_SCHEMA,
            "label": self.label,
            "target": self.target,
            "model": {
                "repo": self.repo,
                "revision": self.revision,
                "weightsDigest": self.weights_digest,
            },
            "scaffold": self.scaffold,
            "decoding": self.decoding,
            "successCriterion": self.success_criterion,
            "nFreeStart": self.n_free_start,
            "nFreeIncrement": self.n_free_increment,
            "stepMultiplier": self.step_multiplier,
            "maxFreeTokens": self.max_free_tokens,
            "stepsInitial": self.steps_initial,
            "stepsHardCap": self.steps_hard_cap,
            "maxAttempts": self.max_attempts,
            "topk": self.topk,
            "batch": self.batch,
            "miniBatch": self.mini_batch,
            "seed": self.seed,
        }

    @property
    def digest(self) -> str:
        """The ``aleph-canonical/0.2.0`` digest of the declared mapping."""
        return digest(self.to_canonical())


def config_from_canonical(value) -> MiniPromptConfig:
    """Strictly parse a declared configuration mapping (fail-closed)."""
    _reject_extras_and_missing(value, _REQUIRED_FIELDS, "config")
    if value["schema"] != CONFIG_SCHEMA:
        raise ConfigError(
            f"config.schema: expected {CONFIG_SCHEMA!r}, got {value['schema']!r}"
        )
    model = value["model"]
    _reject_extras_and_missing(model, _MODEL_FIELDS, "config.model")
    repo = _string(model, "repo", "config.model")
    revision = _string(model, "revision", "config.model")
    weights_digest = _string(model, "weightsDigest", "config.model")
    if not is_digest(weights_digest):
        raise ConfigError("config.model.weightsDigest: expected a sha256:<64 hex> digest")

    scaffold = _string(value, "scaffold", "config")
    if scaffold != SCAFFOLD_EMPTY:
        raise ConfigError(
            "config.scaffold: only the upstream empty scaffold is declared; "
            "scaffolded layouts are a future declared extension"
        )
    decoding = _string(value, "decoding", "config")
    if decoding != DECODING_GREEDY:
        raise ConfigError("config.decoding: only 'greedy' is declared")
    criterion = _string(value, "successCriterion", "config")
    if criterion != SUCCESS_TEACHER_FORCED_ALL_MATCH:
        raise ConfigError("config.successCriterion: only 'teacher_forced_all_match' is declared")

    max_free = _integer(value, "maxFreeTokens", "config", -1)
    if max_free == 0:
        raise ConfigError("config.maxFreeTokens: expected -1 (auto: 5x target tokens) or >= 1")

    return MiniPromptConfig(
        label=_string(value, "label", "config"),
        target=_string(value, "target", "config"),
        repo=repo,
        revision=revision,
        weights_digest=weights_digest,
        scaffold=scaffold,
        decoding=decoding,
        success_criterion=criterion,
        n_free_start=_integer(value, "nFreeStart", "config", 1),
        n_free_increment=_integer(value, "nFreeIncrement", "config", 1),
        step_multiplier=_multiplier(value, "stepMultiplier", "config"),
        max_free_tokens=max_free,
        steps_initial=_integer(value, "stepsInitial", "config", 1),
        steps_hard_cap=_integer(value, "stepsHardCap", "config", 1),
        max_attempts=_integer(value, "maxAttempts", "config", 1),
        topk=_integer(value, "topk", "config", 1),
        batch=_integer(value, "batch", "config", 1),
        mini_batch=_integer(value, "miniBatch", "config", 1),
        seed=_integer(value, "seed", "config", 0),
    )


def loads_strict(text: str):
    """Parse JSON fail-closed: duplicate object keys are rejected."""

    def _pairs(pairs):
        seen = {}
        for key, value in pairs:
            if key in seen:
                raise ValueError(f"duplicate object key: {key!r}")
            seen[key] = value
        return seen

    return json.loads(text, object_pairs_hook=_pairs)


def load_config_file(path) -> MiniPromptConfig:
    """Load a declared configuration from a JSON file (strict parsing)."""
    return config_from_canonical(loads_strict(Path(path).read_text(encoding="utf-8")))
