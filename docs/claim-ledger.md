# Claim Ledger

This file helps parallel accounts converge without turning chat context into hidden product truth. It lists the claims Aleph may make now, what evidence supports each claim, and which account should handle drift.

## How to use this ledger

- If a change introduces a new public claim, check whether it fits one of the rows below.
- If it needs runtime evidence, route it to the account that owns the artifact.
- If it needs a new product meaning, route it to Account A before changing product docs.
- If it only needs wording discipline, Account G can tighten the glossary or language check.

## Current claims

| Claim | Current status | Evidence | Drift owner | Notes |
|---|---|---|---|---|
| Aleph is a reverse prompt compression workbench. | settled | `README.md`, `THESIS.md`, `docs/core-concept.md` | Account A | Do not recast Aleph as a generic prompt optimizer. |
| Aleph estimates the shortest known prompt under fixed model, decoding, metric, and budget. | settled | `THESIS.md`, `docs/core-concept.md`, `docs/research/compression-definition.md` | Account A | Never upgrade this to a global optimum claim. |
| The compression path runs from Shortest Found to Explicit Reconstruction. | settled | `THESIS.md`, `docs/core-concept.md`, fixtures | Account C for UI drift, Account G for wording drift | Preserve both endpoints as distinct concepts. |
| `AlephRun` is the durable exchange shape. | settled but experimental | `packages/core/src/types.ts`, `schemas/aleph-run.schema.json`, `docs/decisions/0003-aleph-run-data-contract.md` | Account A | Schema/type migrations must converge through Account A. |
| Fixture observations are not model evidence. | settled | `docs/surfaces.md`, `packages/fixtures/README.md`, fixture `observations.mode` | Account D for fixture drift, Account G for wording drift | Fixture values may demonstrate UI shape only. |
| Token loss, waveform, attribution, and exposure panels may be fixture or simulated. | implemented as fixture/simulated surface | `docs/surfaces.md`, fixture observations | Account C for UI labels, Account E for demo wording | Do not call these real model internals without logits. |
| Local MLX search is an experimental engine, not the product contract. | active implementation route | `search/`, `apps/api/aleph_api/services/local_mlx_search.py`, `apps/api/smoke.py`, `apps/api/live_smoke.py`, `docs/verification.md` | Account B for adapter behavior, Account A for promotion | API smoke covers mock, recoverable failure, and fake live shape. Live smoke has verified a local `white_box` AlephRun-compatible response when `search/server.py` is running. |
| White-box product observations require logits or model internals. | settled guardrail | `README.md`, `THESIS.md`, `docs/research/research-process.md` | Account A for theory, Account E for demo wording | Use fixture, mock, simulated, or black-box labels otherwise. |
| Demo instructions reflect runnable repository paths. | active verification claim | `DEMO.md`, `docs/verification.md`, `docs/checks.md` | Account E | Account G may flag wording drift but should not rewrite demo flow. |

## Collaboration pattern

Account G should act before demo freeze and after implementation-bearing accounts have changed public-facing claims:

1. Account B, C, D, or F changes behavior or artifacts.
2. Account G checks whether the glossary and claim ledger still describe the change honestly.
3. Account E records runnable verification and demo consequences.
4. Account A resolves any product-theory or contract migration conflicts.

This lets Account G absorb terminology and overclaim risk without blocking implementation accounts on copy edits.
