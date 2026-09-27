# Contributor Map

Read this file when you are new to the repository and need to know where work belongs.

## Start here

1. `README.md` — short public entrypoint.
2. `THESIS.md` — full product and research thesis.
3. `docs/core-concept.md` — settled, open, and deferred decisions.
4. `docs/open-questions.md` — active uncertainty and maintainer leanings.
5. `docs/surfaces.md` — which surfaces are stable, experimental, stub, or archived.
6. `docs/state-of-play.md` — what is settled, implemented, researched, still open, and next.
7. `docs/repository-shape.md` — why the repository is shaped this way.
8. `docs/repository-governance.md` — post-Hackathon path, naming, branch, and claim cleanup rules.
9. `docs/architecture.md` — implementation shape and data flow.
10. `docs/strategy.md` — Hackathon and long-term path, including fallbacks.
11. `docs/next-backlog.md` — next issue candidates and acceptance gates.
12. `docs/quality-bar.md` — review checklist and language/code boundaries.
13. `docs/maintainer-review.md` — current maintainer judgment and next best changes.
14. `docs/claim-ledger.md` — settled claims, evidence, and account drift owners.

## Product and UI

- `docs/ui/product-principles.md`
- `docs/ui/interaction-model.md`
- `docs/ui/visual-system.md`
- `web/` — active Next.js launch surface.
- `apps/web/` — archived legacy frontend reference.
- `packages/ui/`

## Core contracts

- `packages/core/src/types.ts` — shared `AlephRun` contract.
- `schemas/aleph-run.schema.json` — JSON shape for run fixtures or API output.
- `packages/fixtures/src/sample-run.json` — current fixture used by the demo.

## Research and framing

- `docs/plans/iclr-readable-coordinate-program.md` — **governing PR0 research contract**: closest
  collisions, readable/raw compression paths, working reverse search, typed provenance, source
  interventions, falsification gates, and the reviewable PR sequence. Read this first.
- `docs/research/research-process.md` — research receipts and how each source changes the project.
- `docs/research/math-computation-ai-systems.md` — evidence-graded survey and system decomposition for
  program synthesis, theorem proving, test-time search, verification, reproducibility, and human
  checkability; it reports research routes, not Aleph results.
- `docs/plans/model-relative-coordinate-landmarks.md` — long-horizon mathematical/computational
  program: coordinate structure functions, finite BCS ground truth, Lean bootstrap, description versus
  discovery, source identifiability, role contracts, and R0--R4 gates.
- `docs/plans/research-and-benchmark-hardening.md` — current validity-first program for Aleph and Aleph-Bench.
- `docs/decisions/0005-aleph-bench-authority.md` — canonical benchmark target, temporary source branch, and release topology.
- `docs/research/prior-art.md` — Aleph's CS center of gravity and relationship to prompt search,
  mathematical-discovery systems, inversion, instrumentation, and benchmark runtimes.
- `docs/source-ledger.md` — versioned compact primary-source index with an evidence cutoff and explicit
  transfer boundaries; URLs are inspected references, not stability guarantees.
- `docs/research/implementation-routes.md` — staged implementation options.
- `docs/research/compression-definition.md` — model-relative description-length framing.
- `docs/research/research-directions.md` — which research families matter now, later, or only as contrast.
- `docs/claim-ledger.md` — claim-to-evidence map for convergence between accounts.

The repository definitions, frozen protocols, and versioned artifacts are authoritative. Kaggle is a
hosted runtime/portability surface; Hugging Face is a public data and result distribution surface;
GitHub is the code and governance entry. A successful platform run is not, by itself, a scientific
definition, proof, or official benchmark result.

## Process

- `AGENTS.md` — agent/human operating rules.
- `PROMPT.md` — short prompt for delegated coding work.
- `WORKFLOW.md` — lightweight work contract.
- `docs/decisions/` — durable decisions.
- `docs/plans/` — multi-step implementation plans.

## Archive

- `docs/archive/` preserves early prototypes and summarized decisions.
- Archive files are receipts, not product contracts.
