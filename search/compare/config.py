"""Frozen declared configuration for matched-budget comparison instances.

One ``ComparisonConfig`` declares, before any run: the pinned model identity
(repo + revision + weights digest), the target set with the expected raw-side
preset config digests, the readable-side search settings, the shared
wall-clock envelope, and the reproduction threshold tau. Parsing is strict
and fail-closed, mirroring ``search/miniprompt/config.py``: unknown fields,
missing fields, wrong types, non-finite numbers, and non-declared metric
kinds are rejected, so records and artifacts carry the exact declaration they
belong to together with its ``aleph-canonical/0.2.0`` digest.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from search.engine.canonical import digest, is_digest

CONFIG_SCHEMA = "aleph-comparison-config/0.1.0"
READABLE_SCHEMA = "aleph-comparison-readable/0.1.0"
RECORD_SCHEMA = "aleph-comparison-record/0.1.0"

METRIC_EMBEDDING_COSINE = "embedding_cosine"

# The shipped explicit-reconstruction wrapper (search/aleph_search.py): the
# copy baseline is the wrapper plus the target text verbatim.
EXPLICIT_WRAPPER = (
    "Repeat the following text exactly, verbatim, with no preamble, quotes, "
    "or commentary:\n\n"
)


class ConfigError(ValueError):
    """A comparison configuration mapping violates the strict declared contract."""


def _reject_extras_and_missing(value, required, where: str) -> None:
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


def _number(value: dict, key: str, where: str, minimum: float, maximum: float) -> float:
    item = value[key]
    if isinstance(item, bool) or not isinstance(item, (int, float)):
        raise ConfigError(f"{where}.{key}: expected a number")
    item = float(item)
    if not math.isfinite(item):
        raise ConfigError(f"{where}.{key}: expected a finite number")
    if item < minimum or item > maximum:
        raise ConfigError(f"{where}.{key}: expected a number in [{minimum}, {maximum}]")
    return item


@dataclass(frozen=True)
class TargetSpec:
    key: str
    text: str
    raw_preset: str
    raw_config_digest: str


@dataclass(frozen=True)
class ReadableSettings:
    budgets: tuple
    candidates_per_budget: int
    refine_steps: int
    stability_runs: int
    stability_temperature: float
    proposer_seed: int
    metric_kind: str
    metric_model: str


@dataclass(frozen=True)
class ComparisonConfig:
    label: str
    repo: str
    revision: str
    weights_digest: str
    targets: tuple
    readable: ReadableSettings
    envelope_seconds: int
    reproduction_threshold_tau: float
    explicit_wrapper: str

    def to_canonical(self) -> dict:
        return {
            "schema": CONFIG_SCHEMA,
            "label": self.label,
            "model": {
                "repo": self.repo,
                "revision": self.revision,
                "weightsDigest": self.weights_digest,
            },
            "targets": [
                {
                    "key": target.key,
                    "text": target.text,
                    "rawPreset": target.raw_preset,
                    "rawConfigDigest": target.raw_config_digest,
                }
                for target in self.targets
            ],
            "readable": {
                "budgets": list(self.readable.budgets),
                "candidatesPerBudget": self.readable.candidates_per_budget,
                "refineSteps": self.readable.refine_steps,
                "stabilityRuns": self.readable.stability_runs,
                "stabilityTemperature": self.readable.stability_temperature,
                "proposerSeed": self.readable.proposer_seed,
                "metric": {
                    "kind": self.readable.metric_kind,
                    "model": self.readable.metric_model,
                },
            },
            "envelopeSeconds": self.envelope_seconds,
            "reproductionThresholdTau": self.reproduction_threshold_tau,
            "explicitWrapper": self.explicit_wrapper,
        }

    @property
    def digest(self) -> str:
        """The ``aleph-canonical/0.2.0`` digest of the declared mapping."""
        return digest(self.to_canonical())


_MODEL_FIELDS = ("repo", "revision", "weightsDigest")
_TARGET_FIELDS = ("key", "text", "rawPreset", "rawConfigDigest")
_READABLE_FIELDS = (
    "budgets",
    "candidatesPerBudget",
    "refineSteps",
    "stabilityRuns",
    "stabilityTemperature",
    "proposerSeed",
    "metric",
)
_CONFIG_FIELDS = (
    "schema",
    "label",
    "model",
    "targets",
    "readable",
    "envelopeSeconds",
    "reproductionThresholdTau",
    "explicitWrapper",
)


def config_from_canonical(value) -> ComparisonConfig:
    """Strictly parse a declared comparison mapping (fail-closed)."""
    _reject_extras_and_missing(value, _CONFIG_FIELDS, "config")
    if value["schema"] != CONFIG_SCHEMA:
        raise ConfigError(f"config.schema: expected {CONFIG_SCHEMA!r}, got {value['schema']!r}")

    model = value["model"]
    _reject_extras_and_missing(model, _MODEL_FIELDS, "config.model")
    repo = _string(model, "repo", "config.model")
    revision = _string(model, "revision", "config.model")
    weights_digest = _string(model, "weightsDigest", "config.model")
    if not is_digest(weights_digest):
        raise ConfigError("config.model.weightsDigest: expected a sha256:<64 hex> digest")

    targets_raw = value["targets"]
    if not isinstance(targets_raw, list) or not targets_raw:
        raise ConfigError("config.targets: expected a non-empty list")
    targets = []
    seen_keys = set()
    seen_presets = set()
    for position, item in enumerate(targets_raw):
        where = f"config.targets[{position}]"
        _reject_extras_and_missing(item, _TARGET_FIELDS, where)
        key = _string(item, "key", where)
        if key in seen_keys:
            raise ConfigError(f"{where}.key: duplicate target key {key!r}")
        seen_keys.add(key)
        text = _string(item, "text", where)
        raw_preset = _string(item, "rawPreset", where)
        if raw_preset in seen_presets:
            raise ConfigError(
                f"{where}.rawPreset: preset {raw_preset!r} is used by more than one target"
            )
        seen_presets.add(raw_preset)
        raw_config_digest = _string(item, "rawConfigDigest", where)
        if not is_digest(raw_config_digest):
            raise ConfigError(f"{where}.rawConfigDigest: expected a sha256:<64 hex> digest")
        targets.append(
            TargetSpec(
                key=key,
                text=text,
                raw_preset=raw_preset,
                raw_config_digest=raw_config_digest,
            )
        )

    readable = value["readable"]
    _reject_extras_and_missing(readable, _READABLE_FIELDS, "config.readable")
    budgets_raw = readable["budgets"]
    if not isinstance(budgets_raw, list) or not budgets_raw:
        raise ConfigError("config.readable.budgets: expected a non-empty list")
    budgets = []
    for position, item in enumerate(budgets_raw):
        if isinstance(item, bool) or not isinstance(item, int) or item < 1:
            raise ConfigError(f"config.readable.budgets[{position}]: expected an integer >= 1")
        budgets.append(item)
    if len(set(budgets)) != len(budgets):
        raise ConfigError("config.readable.budgets: duplicate entries are not declared")

    metric = readable["metric"]
    _reject_extras_and_missing(metric, ("kind", "model"), "config.readable.metric")
    metric_kind = _string(metric, "kind", "config.readable.metric")
    if metric_kind != METRIC_EMBEDDING_COSINE:
        raise ConfigError(
            "config.readable.metric.kind: only 'embedding_cosine' is declared"
        )
    metric_model = _string(metric, "model", "config.readable.metric")

    explicit_wrapper = _string(value, "explicitWrapper", "config")
    if not explicit_wrapper.endswith("\n\n"):
        raise ConfigError(
            "config.explicitWrapper: expected the declared wrapper form ending in a blank line"
        )

    return ComparisonConfig(
        label=_string(value, "label", "config"),
        repo=repo,
        revision=revision,
        weights_digest=weights_digest,
        targets=tuple(targets),
        readable=ReadableSettings(
            budgets=tuple(budgets),
            candidates_per_budget=_integer(
                readable, "candidatesPerBudget", "config.readable", 1
            ),
            refine_steps=_integer(readable, "refineSteps", "config.readable", 0),
            stability_runs=_integer(readable, "stabilityRuns", "config.readable", 1),
            stability_temperature=_number(
                readable, "stabilityTemperature", "config.readable", 0.0, 2.0
            ),
            proposer_seed=_integer(readable, "proposerSeed", "config.readable", 0),
            metric_kind=metric_kind,
            metric_model=metric_model,
        ),
        envelope_seconds=_integer(value, "envelopeSeconds", "config", 1),
        reproduction_threshold_tau=_number(
            value, "reproductionThresholdTau", "config", 0.0, 1.0
        ),
        explicit_wrapper=explicit_wrapper,
    )
