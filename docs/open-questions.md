# Open Questions

This file is for real uncertainty. Do not let unresolved questions become product claims or fixture behavior become evidence.

## First-round questions to settle

### 0. Permanent frontend path

Settled:

- `web/` is the active Next.js app.
- `apps/web/` is archived reference material.

### 1. First real model adapter

Options:

- hosted black-box adapter first;
- local open-weight adapter first;
- fixture-only Hackathon v0 followed by both.

Maintainer leaning: fixture-first for the stable UI contract, local MLX live-search for the Hackathon demo, hosted black-box for the first external run, and local white-box once token loss becomes a stable product observation.

### 2. Default metric

Options:

- exact match / edit distance;
- embedding similarity;
- LLM judge;
- composite metric.

Maintainer leaning: composite metric with explicit sub-scores. Avoid hiding important tradeoffs behind one number.

### 3. Leakage score

Options:

- longest common substring;
- n-gram overlap;
- target copy ratio;
- entity copy limits;
- composite score.

Maintainer leaning: start with n-gram overlap plus copy ratio; add entity limits for examples where names/numbers matter.

### 4. Search strategy

Options:

- heuristic candidate generation;
- black-box evolutionary search;
- ARCA-style length-scanned coordinate optimization;
- GCG-style hard-prompt search;
- soft-prompt route later.

Maintainer leaning: keep the current local MLX shallow-search spike for demo credibility, wrap it behind `apps/api`, then make ARCA/GCG external adapters once the run contract is stable.

### 5. UI emphasis

Options:

- research console;
- public product page;
- hybrid landing-plus-console.

Maintainer leaning: build the console first. A landing page can narrate the console later.

### 6. Persistence

Options:

- no persistence;
- local JSON export/import;
- file-backed runs;
- database.

Maintainer leaning: JSON export/import before database.

## Questions to avoid for now

- Pricing, accounts, teams, or billing.
- Full model hosting strategy.
- Production security model.
- Public benchmark claims.
- Strict Kolmogorov framing.

## How to settle open questions

Settle an open question only through a small implementation spike, an ADR, or a plan that names the acceptance gate. Do not settle it silently inside UI code. Use `docs/strategy.md` for path-level choices and `docs/quality-bar.md` for review criteria.
