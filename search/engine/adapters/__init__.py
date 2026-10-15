"""Engine adapters.

``replay.py`` is the pure-standard-library replay kernel adapter. ``mlx.py``
is the opt-in pinned MLX canary adapter (PR C): it imports MLX lazily inside
its functions, is never imported by the kernel, exporter, or verifier, and is
exercised only on an Apple Silicon host with the pinned snapshot.
"""
