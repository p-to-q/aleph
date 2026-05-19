from __future__ import annotations

import difflib
import re


def token_count(text: str) -> int:
    compact = text.strip()
    if not compact:
        return 0
    return len(compact.split())


def compression_ratio(candidate_prompt: str, explicit_prompt: str) -> float:
    explicit_tokens = token_count(explicit_prompt)
    if explicit_tokens <= 0:
        return 0.0
    ratio = 1 - (token_count(candidate_prompt) / explicit_tokens)
    return max(0.0, min(1.0, ratio))


def similarity_score(target_text: str, output: str) -> float:
    target = target_text.strip()
    actual = output.strip()
    if target == actual and target:
        return 1.0
    return difflib.SequenceMatcher(a=target, b=actual).ratio()


def leakage_score(prompt: str, target_text: str) -> float:
    prompt_tokens = re.findall(r"[\w'-]+", prompt.lower())
    target_tokens = re.findall(r"[\w'-]+", target_text.lower())
    if not prompt_tokens or not target_tokens:
        return 0.0

    target_lookup = set(target_tokens)
    unigram_overlap = sum(token in target_lookup for token in prompt_tokens) / len(prompt_tokens)

    target_trigrams = _ngrams(target_tokens, 3)
    prompt_trigrams = _ngrams(prompt_tokens, 3)
    trigram_overlap = (
        sum(gram in target_trigrams for gram in prompt_trigrams) / len(prompt_trigrams)
        if prompt_trigrams
        else 0.0
    )

    return max(0.0, min(1.0, 0.55 * unigram_overlap + 0.45 * trigram_overlap))


def overall_score(
    *,
    similarity: float,
    compression: float,
    leakage: float,
    reliability: float | None,
) -> float:
    stability = reliability if reliability is not None else 0.5
    score = similarity * 0.45 + stability * 0.25 + compression * 0.2 - leakage * 0.1
    return max(0.0, min(1.0, score))


def _ngrams(tokens: list[str], n: int) -> set[str]:
    return {" ".join(tokens[index:index + n]) for index in range(0, max(0, len(tokens) - n + 1))}
