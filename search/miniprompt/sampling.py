"""Seeded sampling decisions for MiniPrompt attempts (pure standard library).

Upstream draws free-token initializations and per-step candidate mutations
from the process-global RNG. The reproduction derives every draw from
``random.Random`` seeded with an explicit derivation string built from the
declared seed, the free-token count, and the step index, so attempts are
deterministic per declared configuration and resumable exactly. Nothing here
imports MLX; the MLX path consumes these decisions as plain integer lists.
"""

from __future__ import annotations

import random
from typing import List, Sequence, Tuple

DERIVATION = "miniprompt-python-random-v1"


def _rng(*parts: object) -> random.Random:
    return random.Random(DERIVATION + "/" + "/".join(str(part) for part in parts))


def initial_free_ids(seed: int, n_free: int, vocab_size: int) -> List[int]:
    """Uniform initial free-token IDs for one attempt."""
    rng = _rng("init", seed, n_free, vocab_size)
    return [rng.randrange(vocab_size) for _ in range(n_free)]


def step_mutations(seed: int, n_free: int, topk: int, step: int, batch: int) -> List[Tuple[int, int]]:
    """Per-candidate ``(position, pick)`` draws for one GCG step.

    Each candidate mutates exactly one uniformly chosen free position to a
    uniformly chosen entry of that position's top-k descent candidate list —
    the upstream batch construction, with an explicit derivation.
    """
    rng = _rng("step", seed, n_free, topk, step)
    return [(rng.randrange(n_free), rng.randrange(topk)) for _ in range(batch)]


def apply_mutations(
    base_ids: Sequence[int],
    candidate_rows: Sequence[Sequence[int]],
    mutations: Sequence[Tuple[int, int]],
) -> List[List[int]]:
    """Apply ``(position, pick)`` mutations to a base token row."""
    rows = []
    for position, pick in mutations:
        row = list(base_ids)
        row[position] = candidate_rows[position][pick]
        rows.append(row)
    return rows
