from __future__ import annotations

import re
from dataclasses import dataclass


TOKEN_RE = re.compile(r"[A-Za-z0-9]+")
DEFAULT_THRESHOLDS = {
    "lcsRatio": 0.65,
    "trigramOverlap": 0.5,
    "verbatimSpanTokens": 16,
}


@dataclass(frozen=True)
class LeakageGateResult:
    disqualified: bool
    lcsRatio: float
    trigramOverlap: float
    verbatimSpanTokens: int
    thresholds: dict[str, float | int]

    def as_dict(self) -> dict[str, object]:
        return {
            "disqualified": self.disqualified,
            "lcsRatio": self.lcsRatio,
            "trigramOverlap": self.trigramOverlap,
            "verbatimSpanTokens": self.verbatimSpanTokens,
            "thresholds": dict(self.thresholds),
        }


def tokens(text: str) -> list[str]:
    return TOKEN_RE.findall(text.lower())


def lcs_length(a: list[str], b: list[str]) -> int:
    if not a or not b:
        return 0
    previous = [0] * (len(b) + 1)
    for token_a in a:
        current = [0]
        for j, token_b in enumerate(b, start=1):
            if token_a == token_b:
                current.append(previous[j - 1] + 1)
            else:
                current.append(max(previous[j], current[j - 1]))
        previous = current
    return previous[-1]


def longest_common_span(a: list[str], b: list[str]) -> int:
    best = 0
    previous = [0] * (len(b) + 1)
    for token_a in a:
        current = [0]
        for j, token_b in enumerate(b, start=1):
            value = previous[j - 1] + 1 if token_a == token_b else 0
            current.append(value)
            best = max(best, value)
        previous = current
    return best


def ngrams(values: list[str], n: int) -> set[tuple[str, ...]]:
    return {tuple(values[i : i + n]) for i in range(max(0, len(values) - n + 1))}


def evaluate_leakage(
    prompt: str,
    target: str,
    thresholds: dict[str, float | int] | None = None,
) -> LeakageGateResult:
    active = dict(DEFAULT_THRESHOLDS if thresholds is None else thresholds)
    prompt_tokens = tokens(prompt)
    target_tokens = tokens(target)
    if not prompt_tokens or not target_tokens:
        return LeakageGateResult(False, 0.0, 0.0, 0, active)

    lcs_ratio = lcs_length(prompt_tokens, target_tokens) / len(target_tokens)
    target_trigrams = ngrams(target_tokens, 3)
    prompt_trigrams = ngrams(prompt_tokens, 3)
    trigram_overlap = (
        len(target_trigrams & prompt_trigrams) / len(target_trigrams) if target_trigrams else 0.0
    )
    span = longest_common_span(prompt_tokens, target_tokens)
    disqualified = (
        lcs_ratio >= float(active["lcsRatio"])
        or trigram_overlap >= float(active["trigramOverlap"])
        or span >= int(active["verbatimSpanTokens"])
    )
    return LeakageGateResult(
        disqualified=disqualified,
        lcsRatio=round(lcs_ratio, 6),
        trigramOverlap=round(trigram_overlap, 6),
        verbatimSpanTokens=span,
        thresholds=active,
    )


def leakage_score(result: LeakageGateResult) -> float:
    span_score = min(1.0, result.verbatimSpanTokens / int(result.thresholds["verbatimSpanTokens"]))
    return round(max(result.lcsRatio, result.trigramOverlap, span_score), 6)
