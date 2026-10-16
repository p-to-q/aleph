"""Matched-budget comparison between MiniPrompt raw coordinates and Aleph's
readable search.

Pure standard-library parts (``config``, ``record``, ``fixtures``) are
importable and testable without MLX; the readable-side runner (``readable``)
is the opt-in MLX execution path, and the instance driver (``run``) spawns
the heavy steps as subprocesses. The declaration and its evidence rules live
in ``docs/research/miniprompt-matched-budget-comparison-note.md``.
"""
