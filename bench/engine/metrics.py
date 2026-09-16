from __future__ import annotations

import random
import re
from statistics import mean
from typing import Any, Callable, Iterable


TOKEN_RE = re.compile(r"[A-Za-z0-9]+")


def token_count(text: str) -> int:
    return len(TOKEN_RE.findall(text))


def normalized_text(text: str) -> str:
    return " ".join(TOKEN_RE.findall(text.lower()))


def levenshtein(a: str, b: str) -> int:
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    previous = list(range(len(b) + 1))
    for i, char_a in enumerate(a, start=1):
        current = [i]
        for j, char_b in enumerate(b, start=1):
            insert = current[j - 1] + 1
            delete = previous[j] + 1
            replace = previous[j - 1] + (0 if char_a == char_b else 1)
            current.append(min(insert, delete, replace))
        previous = current
    return previous[-1]


def exact_fidelity(target: str, output: str) -> float:
    """Exact-class fidelity with edit-distance signal for near misses.

    Returns ``1.0`` on exact equality (the audit gate requires this); on any
    mismatch, falls back to ``1 - normalized_edit_distance`` rather than a
    hard ``0.0``. This refines ``docs/benchmark/02-design-spec.md`` §5, which
    describes the exact class as binary; the gradient is a deliberate M0
    softening so a one-character drift does not look identical to an empty
    output. The change is documented in
    ``docs/benchmark/02-design-spec.md`` and tracked in the audit notes.
    """

    if target == output:
        return 1.0
    target_norm = normalized_text(target)
    output_norm = normalized_text(output)
    if not target_norm and not output_norm:
        return 1.0
    if not target_norm or not output_norm:
        return 0.0
    distance = levenshtein(target_norm, output_norm)
    scale = max(len(target_norm), len(output_norm))
    return round(max(0.0, 1.0 - distance / scale), 6)


def char_ngram_fidelity(target: str, output: str, n: int = 3) -> float:
    def grams(value: str) -> set[str]:
        clean = normalized_text(value)
        if len(clean) < n:
            return {clean} if clean else set()
        return {clean[i : i + n] for i in range(len(clean) - n + 1)}

    target_grams = grams(target)
    output_grams = grams(output)
    if not target_grams and not output_grams:
        return 1.0
    if not target_grams or not output_grams:
        return 0.0
    return round(len(target_grams & output_grams) / len(target_grams | output_grams), 6)


def fidelity(target: str, output: str, metric_class: str) -> float:
    if metric_class == "exact":
        return exact_fidelity(target, output)
    if metric_class == "lexical":
        return char_ngram_fidelity(target, output)
    # M0 keeps semantic, judge, and execution classes explicit without hiding
    # them behind a weighted score. Exact fallback keeps the pipeline runnable.
    return exact_fidelity(target, output)


def distortion(target: str, output: str, metric_class: str) -> float:
    return round(1.0 - fidelity(target, output, metric_class), 6)


def monotone_lower_envelope(points: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return real candidate points that improve the best known distortion."""
    by_length: dict[int, dict[str, Any]] = {}
    for point in points:
        if point.get("disqualified"):
            continue
        length = int(point["tokens"])
        current = by_length.get(length)
        if current is None or point["distortion"] < current["distortion"]:
            by_length[length] = point

    envelope: list[dict[str, Any]] = []
    best_distortion: float | None = None
    for point in sorted(by_length.values(), key=lambda item: (item["tokens"], item["distortion"])):
        if best_distortion is None or point["distortion"] < best_distortion:
            best_distortion = point["distortion"]
            frontier_point = dict(point)
            frontier_point["frontierRank"] = len(envelope) + 1
            envelope.append(frontier_point)
    return envelope


def aurc(frontier: list[dict[str, Any]], normalizer_tokens: int) -> float:
    """Area under the non-leaking rate-distortion staircase. Lower is better.

    ``normalizer_tokens`` is the right-hand budget anchor used to rescale the
    x-axis into ``[0, 1]``. ``frozen_ladder.evaluate_item`` passes the
    explicit-reconstruction prompt length (the rung-0 prompt — which is
    gated out of scoring but still anchors the budget), or the target text
    length if it is larger:

        explicit_tokens = max(
            token_count(item["frozenLadder"][0]["prompt"]),
            token_count(target),
            1,
        )

    The curve starts at the empty-budget baseline ``distortion = 1.0`` and
    drops only when the first eligible prompt becomes available. Beyond the
    right-hand anchor, the curve is held at its last distortion value, so AURC
    degrades smoothly when a model never reaches the target within the budget.
    The choice matches ``docs/benchmark/02-design-spec.md`` §2's
    ``L_max = |explicit reconstruction prompt|``.
    """

    if not frontier:
        return 1.0
    normalizer = max(1, normalizer_tokens)
    area = 0.0
    previous_x = 0.0
    current_distortion = 1.0
    for point in sorted(frontier, key=lambda item: item["tokens"]):
        x = max(previous_x, min(1.0, point["tokens"] / normalizer))
        area += (x - previous_x) * current_distortion
        current_distortion = point["distortion"]
        previous_x = x
    area += max(0.0, 1.0 - previous_x) * current_distortion
    return round(max(0.0, min(1.0, area)), 6)


def ecl_at_tau(frontier: list[dict[str, Any]], tau: float) -> int | None:
    hits = [point["tokens"] for point in frontier if point["fidelity"] >= tau]
    return min(hits) if hits else None


def elicit_at_k(points: list[dict[str, Any]], tau: float, k: int) -> bool:
    """Return whether an eligible prompt within the k-unit budget reaches tau."""

    return any(point["tokens"] <= k and point["fidelity"] >= tau for point in points)


def ci95(values: list[float], *, seed: int, samples: int) -> dict[str, float] | None:
    if not values:
        return None
    if len(values) == 1:
        value = round(values[0], 6)
        return {"low": value, "high": value}
    rng = random.Random(seed)
    boot = []
    for _ in range(samples):
        draw = [values[rng.randrange(len(values))] for _ in values]
        boot.append(mean(draw))
    boot.sort()
    low_index = int(0.025 * (len(boot) - 1))
    high_index = int(0.975 * (len(boot) - 1))
    return {"low": round(boot[low_index], 6), "high": round(boot[high_index], 6)}


def summarize(values: list[float], *, seed: int, samples: int) -> tuple[float | None, dict[str, float] | None]:
    if not values:
        return None, None
    return round(mean(values), 6), ci95(values, seed=seed, samples=samples)


def rank_by_metric(rows: list[dict[str, Any]], key: str) -> list[str]:
    return [row["model"] for row in sorted(rows, key=lambda row: (row[key], row["model"]))]
