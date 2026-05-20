# Changelog

## Unreleased

- Clarified the explorer frontier as a discrete candidate frontier rather than
  a continuous fitted curve.
- Made the dashboard's frontier basin label a localized explanation entrypoint;
  its underline opens a note explaining that UI
  easing does not imply a measured continuous loss surface.
- Improved the frontier help dialog's keyboard focus handling.
- Updated the frontier slider's accessibility label to reference the discrete
  candidate frontier.
- Added research notes on garden-path-like prompt coordinates and surfaced that
  Custom API searches can sometimes find short, strange model-specific cues near
  the compression edge.
- Added dashboard source labeling so `model θ` can be read against the actual
  run source: fixture, local MLX, custom API, or mock.

## v1.0.3 - 2026-05-20

Patch release: updates Aleph's local white-box runtime framing after MLX
upstream added Linux CUDA backend support. The current local path remains
MLX-backed and Apple Silicon is still the known-good maintainer route, while
Linux CUDA is now part of the forward hardware story. See
[docs/releases/1.0.3.md](docs/releases/1.0.3.md).

## v1.0.2 - 2026-05-19

Patch release: production metadata, Vercel Web Analytics, and explorer i18n /
result-view polish. No run-contract or adapter change. See
[docs/releases/1.0.2.md](docs/releases/1.0.2.md).

## v1.0.1 - 2026-05-19

Patch release for the public Aleph launch surface. See [docs/releases/1.0.1.md](docs/releases/1.0.1.md).

## v1.0.0 - 2026-05-19

First formal Aleph release. See [docs/releases/1.0.0.md](docs/releases/1.0.0.md).
