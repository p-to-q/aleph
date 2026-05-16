# ADR 0001: Repository shape

## Status

Accepted.

## Decision

Use an artifact-first product-lab shape rather than a rigid template profile.

## Rationale

Aleph needs a clear thesis, a runnable UI artifact, shared data contracts, source-backed research, sparse decisions, and lightweight agent delegation. It does not yet need a full RFC route, release discipline, CODEOWNERS, strict governance, or process-heavy template routes.

The p-to-q seed remains a useful reference for file-first discipline, visible artifacts, receipts, limitations, and small reviewable changes. It is not a binding architecture.

## Consequences

- `optional/` has been removed.
- Durable decisions live in `docs/decisions/`.
- Multi-step plans live in `docs/plans/`.
- The active shape is documented in `docs/repository-shape.md`.
- Add process only when it removes confusion for humans or agents.
