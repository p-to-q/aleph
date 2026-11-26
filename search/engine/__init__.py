"""Aleph engine: artifact-first, replayable search kernel.

PR A delivers the standard-library artifact kernel: canonical serialization,
adapter contracts, the append-only event archive, the six-account resource
ledger, a pure replay adapter, and an independent verifier. PR B adds the
hybrid Pareto scheduler, protected confirmation, and the measurement-lossless
``AlephRun`` projection. PR C adds one opt-in, non-kernel module —
``adapters/mlx.py`` — which imports MLX lazily inside its functions and is
never imported by the kernel, exporter, or verifier. No kernel module imports
MLX, performs network access, or requires an optional embedding package.
"""
