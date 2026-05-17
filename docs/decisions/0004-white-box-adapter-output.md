# ADR 0004: White-box adapter output boundary

## Status

Accepted.

## Decision

Treat token-level NLL from the local MLX path as **white-box adapter output** when it is returned through `ObservationSet.tokenLoss` with `observations.mode = "white_box"`.

This does not make the whole product a completed white-box workbench. It only means the adapter can return model-internal token scoring for a run, and UI surfaces may display it when present.

## Rationale

`search/aleph_search.py` already supports teacher-forced token scoring through `theta.score(...)`. The live `search/server.py` route now attaches token NLL for the explicit/right-end point when scoring succeeds, and `apps/api` maps that response into the shared `AlephRun` shape.

Keeping this as an adapter-output boundary preserves the existing honesty rule:

- fixture and simulated observations remain labeled as such;
- black-box runs without token NLL remain `black_box`;
- white-box claims require logits or model internals;
- UI panels may show token loss, but should not imply full mechanistic interpretability.

## Consequences

- Account B owns the local MLX adapter behavior and smoke checks.
- Account C may display `ObservationSet.tokenLoss` when present.
- Account A should review any future expansion of white-box fields beyond token NLL.
- `npm run lint` must remain independent of MLX, model downloads, and a running search server.
