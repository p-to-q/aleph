"""MiniPrompt/ACR reproduction package (method-level, MLX-only run path).

This package reimplements the MiniPrompt length scan and the GCG inner loop of
``locuslab/acr-memorization`` (pinned ``bf3ba2e7``) for MLX, under the
declared interface conditions in
``docs/research/miniprompt-reproduction-note.md``.

Layering:

- ``config``, ``scan``, ``sampling``, ``receipts`` — pure standard-library
  parts; importable and testable without MLX.
- ``gcg`` and ``runner`` — the MLX execution path (imports ``mlx``/``mlx_lm``);
  only imported by explicit run commands and the opt-in MLX test module.

Found prompts are raw coordinates: free-token IDs are the ground truth and
decoded text is a declared rendering, never a readable prompt.
"""
