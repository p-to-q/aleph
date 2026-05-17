from __future__ import annotations

import re

from aleph_api.models import CandidatePrompt


def _sentences(text: str) -> list[str]:
    parts = [part.strip() for part in re.split(r"(?<=[.!?])\s+", text.strip()) if part.strip()]
    return parts or [text.strip()]


def _keywords(text: str, limit: int = 8) -> list[str]:
    tokens = re.findall(r"[\w'-]+", text.lower())
    seen: list[str] = []
    for token in tokens:
        if len(token) < 4:
            continue
        if token not in seen:
            seen.append(token)
        if len(seen) >= limit:
            break
    return seen


def build_candidate_prompts(target_text: str, candidate_count: int = 5) -> tuple[str, list[CandidatePrompt]]:
    clean_target = target_text.strip()
    sentences = _sentences(clean_target)
    summary = " ".join(sentences[:2])
    keywords = ", ".join(_keywords(clean_target))
    opening = sentences[0]

    explicit_prompt = f"Reproduce the following output exactly:\n\n{clean_target}"

    candidates: list[CandidatePrompt] = [
        CandidatePrompt(
            id="explicit-reconstruction",
            label="Explicit Reconstruction",
            prompt=explicit_prompt,
            kind="explicit",
        ),
        CandidatePrompt(
            id="target-summary",
            label="Summary Anchor",
            prompt=f"Write the target output described by this summary:\n\n{summary}",
            kind="summary",
        ),
        CandidatePrompt(
            id="keyword-coordinate",
            label="Keyword Coordinate",
            prompt=f"Write the intended output using these coordinates: {keywords}.",
            kind="keywords",
        ),
        CandidatePrompt(
            id="opening-coordinate",
            label="Opening Coordinate",
            prompt=f"Continue toward the intended output starting from this opening idea:\n\n{opening}",
            kind="coordinate",
        ),
        CandidatePrompt(
            id="minimal-coordinate",
            label="Shortest Found (Heuristic)",
            prompt=f"Recover the target output from these compressed cues: {keywords}. Preserve the same semantic destination.",
            kind="minimal",
        ),
    ]

    return explicit_prompt, candidates[:candidate_count]
