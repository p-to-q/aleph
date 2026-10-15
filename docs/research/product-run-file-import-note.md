# Product Run-File Import Practice Note

Status: gate note for the product open-file slice (new module + product surface), recorded under the
structural decision research gate in [research-process.md](research-process.md). Access date for all
sources below: 2026-10-15.

## Question

The engine already has a strict, fail-closed import surface for `AlephRun` exports and run bundles
([persistence-layer-practice-review.md](persistence-layer-practice-review.md) §6;
`search/engine/import_aleph_run.py`). The product half of
[next-backlog.md](../next-backlog.md) "P1: File-First Run Import/Export" asks how a saved run can
leave the web app, return to it, and keep its selected-candidate semantics — without turning the
browser into a second verification authority or confusing a projection file with the scientific
archive.

## Sources inspected

| Source (accessed 2026-10-15) | Location / URL | F — what was observed | I — interpretation | U — use here |
|---|---|---|---|---|
| Jupyter `nbformat` validator + API docs | `https://raw.githubusercontent.com/jupyter/nbformat/main/nbformat/validator.py`; `https://nbformat.readthedocs.io/en/latest/api.html` (fetched to `/tmp/open-file-sources/`, sha256 recorded) | The notebook format is versioned; `validate()`/`read()` check a notebook against the format schema and raise `ValidationError`; format versions coexist with explicit conversion (`nbformat.convert`). | Opening foreign format files in a tool is done by validating against the format's own versioned schema at the consumer, with explicit errors and explicit version handling. | The product validates run files against the repository's single schema file, reports field-level errors, and fails closed on unknown shapes instead of inventing a product-only format. |
| JSON Schema 2020-12 validation spec | `https://json-schema.org/draft/2020-12/json-schema-validation` (fetched; sha256 recorded) | The dialect `schemas/aleph-run.schema.json` declares; `type`, `enum`, `required`, `additionalProperties`, `minimum`, `maximum` have defined validation semantics. | A closed schema (`additionalProperties: false`) pins interchange shape; a consumer can implement the used keyword subset without a third-party dependency. | `web/app/lib/run-file.ts` imports the same `schemas/aleph-run.schema.json` (single source, zero duplication) and walks the used subset; no new dependency. |
| Event-sourcing practice (Fowler; Kreps) | `docs/research/persistence-layer-practice-review.md` (copies in `/tmp/persist-sources/`) | The event log is the system of record; derived views / read models are disposable projections of it. | What a consumer surface can honestly display is a projection, never the archive itself. | Imported files are labeled "imported run file / projection"; replay and digest checks are named as engine-side; the product never claims the archive. |
| MLflow backend-store documentation | `/tmp/persist-sources/mlflow-backend-store.html` | Artifacts live in a backend store; the tracking UI reads results from that store; storage and presentation are separate concerns. | Consumer surfaces stay thin over a store; they do not become the store. | Open/save operates on standalone files only; the product writes nothing into bundles; cross-store copying stays out of scope (mirrors the engine importer). |
| RFC 8785 (JCS) and ADR 0006 (in-repo) | `docs/decisions/0006-canonical-json-jcs-alignment.md`; `https://www.rfc-editor.org/rfc/rfc8785.txt` | Canonical bytes are an exact text form for signing/hashing (`aleph-canonical/0.2.0`); the JS recomputation surface is Node-side (`node:crypto`). | Byte-level verification is a distinct layer from structural validation, and browser digest support is its own decision surface. | The product slice performs no canonical-byte or digest verification and defers any browser digest path to a future decision; opened files still save back byte-for-byte. |

## Decision and structural effect

1. New module `web/app/lib/run-file.ts`: a dependency-free product loader that parses a saved
   `aleph-run.json` against the repository schema plus the static exporter invariants that need no
   cryptography (non-empty candidates; `budget.candidates` equals the candidate count;
   `maxPromptTokens` at least the observed maximum; `selectedCandidateId` among the candidate ids;
   a present `artifactRef` checked for known version, run-id match, and digest shape).
2. New product surface in `web/app/components/aleph-explorer.tsx`: `open run json` / `save run json`
   controls in both views, a `run file` dashboard row, an imported-projection source label, a slider
   marker for the run's selected candidate, and an explicit error list for rejected files.
3. Semantics: opening a file selects the run's `selectedCandidateId` (slider position preserved),
   keeps candidate ids and roles in the view model, and saves opened files back byte-for-byte; runs
   that never existed as a file (live route responses) must pass the same validation before they can
   be saved.
4. Enforcement: `scripts/check-run-file.mjs` runs in `npm run lint` and `npm test` (fixtures round
   trip through the real module; crafted invalid files reject fail-closed); `next build` compiles
   the wiring.
5. No new dependency and no new process. The strict engine importer remains the verification
   surface; this module cannot and does not claim replay or digest verification.

## Boundary — what the product import does not verify

Documented divergences from the engine file-mode import (deliberate, product vs research layers):

- `artifactRef` is optional in the product (the shipped fixtures and live route runs have none) and
  is shape-checked only when present; the engine requires it and recomputes `projectionDigest`.
- No duplicate-object-key detection (a `JSON.parse` consumer cannot see them); the engine fails
  duplicates closed via `object_pairs_hook`.
- No canonical-bytes requirement; pretty-printed fixtures open, while the engine demands
  `aleph-canonical/0.2.0` bytes plus a trailing newline.
- `maxPromptTokens` may exceed the observed maximum (the shipped fixtures declare it as a budget
  cap; the engine exporter derives it as an exact maximum and the engine import enforces equality
  for its own exports).
- A browser canonical/digest path is explicitly deferred — it would extend the #120 resolution and
  needs its own note before any product digest claim.

## Verification

- `scripts/check-run-file.mjs`: every packed fixture opens, keeps candidate identity and the
  selected candidate, and round-trips; 24 crafted files reject with clear issues; 10 garbage inputs
  fail closed without throwing; a well-formed `artifactRef` is accepted shape-only (pinned as
  documented behavior).
- Repository suites after the change: `npm run lint` green; engine suite 444 tests OK (skipped=3);
  `search/tests` 41 tests OK; canonical parity 126 pinned assertions / 2448 differentials; web
  production build green.
- An independent verification probe exercises the built app route end to end (mock `/api/search`
  response → open → save → reopen) in addition to the module-level cases above.

## Cross-links

- [next-backlog.md](../next-backlog.md) — P1 File-First Run Import/Export.
- [state-of-play.md](../state-of-play.md) — Strict run import row.
- [persistence-layer-practice-review.md](persistence-layer-practice-review.md) — file-first decision.
- `web/app/lib/run-file.ts`, `scripts/check-run-file.mjs`.
