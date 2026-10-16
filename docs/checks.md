# Checks

The root lint command is intentionally lightweight and can run without installing frontend dependencies:

```bash
npm run lint
```

It runs:

```text
scripts/doctor.mjs
scripts/check-links.mjs
scripts/check-placeholders.mjs
scripts/check-maintenance-routes.mjs
scripts/check-language.mjs
scripts/check-core.mjs
scripts/check-contract.mjs
scripts/check-fixtures.mjs
scripts/check-run-file.mjs
scripts/check-repo.mjs
```

The TypeScript-importing checks (`check-core.mjs`, `check-fixtures.mjs`, `check-run-file.mjs`)
need Node with default type stripping (>= 22.18); the root `engines.node` floor states the same
(docs/next-backlog.md P3 decision, 2026-10-15).

## What these checks prove

- Required repository files exist.
- Local Markdown links resolve.
- Template placeholders are not left in active files.
- Maintenance route language matches the current artifact-first shape.
- The glossary and claim ledger contain a finite required phrase set, the quality bar retains a
  finite avoid-list, and four guarded regex patterns reject a small set of known overclaim phrasings
  in active Markdown. This is not general semantic or claim-consistency validation.
- Core helpers preserve expected observed-frontier, compression-ratio, and legacy `leakageScore`
  surface-copy-proxy behavior; this is wire/helper regression coverage, not PR0 evidence validation.
- Core enum contracts stay aligned with `schemas/aleph-run.schema.json`.
- AlephRun fixture JSON files validate against `schemas/aleph-run.schema.json`.
- Run files round trip through the product loader (`web/app/lib/run-file.ts`): every packed fixture
  opens, keeps candidate identity and the selected candidate, saves back byte-for-byte when it was
  opened from a file, and crafted invalid files fail closed with clear issues. Digest
  recomputation, replay, and duplicate-key strictness are engine-side and are not asserted here.
- The token NLL evidence entry is pinned in the schema and exercised from the contract side: one
  `{token, loss ≥ 0}` per decoded token (optional 1-based `rank`, `topAlternatives`, no hidden
  fields), in lockstep with the exported `TokenLossPoint` type; `check-fixtures.mjs` passes a
  shape-valid white-box trace and fails closed on six malformed traces; `check-run-file.mjs`
  accepts the loss-0 boundary in the product loader and rejects negative losses and non-1-based
  ranks. Contract note: [research/token-nll-evidence-note.md](research/token-nll-evidence-note.md).
- Fixture runs preserve enough candidate points, the explicit reconstruction baseline, shortest-found
  endpoint, selected candidate, observation mode, and the legacy `non-leaking` fixture threshold.
  Passing that fixture check does not establish channel-qualified tested noncopy.
- The fixture manifest indexes every fixture run exactly once and keeps id, label, mode, and observation mode aligned.
- Reference screenshots are not kept in the archive.
- `optional/` is not active as a template leftover.
- `THESIS.md`, `docs/open-questions.md`, `docs/strategy.md`, `docs/quality-bar.md`, and `docs/repository-shape.md` are present.

## What these checks do not prove

- The React app builds or its open/save controls behave in a browser; that requires `npm install`
  and `npm run build`, and the controls are covered by review plus the wiring build.
- That an accepted run file is authentic: digests are not recomputed (the engine importer does
  that) and duplicate object keys are not detected.
- Hosted model credentials are present, external providers are reachable, or a live model returns good candidates.
- That a token NLL trace is authentic model internals: the checks above pin the entry shape only,
  and shape validity does not establish provenance; only the live adapter path (with its recorded
  receipt) covers a real local model run. Attribution and waveform values remain fixture-shaped.
- External URLs are still live.

Record broader checks in `docs/verification.md`.

## Public frontier receipts

`npm test` runs `scripts/check-public-frontier.mjs`, which validates the public MLX frontier artifact
(`web/public/aleph-frontier.json`) together with its receipt sidecar
(`web/public/aleph-frontier.receipts.json`, schema `aleph-frontier-receipts/0.1.0`). Every displayed
measured point must match exactly one receipt through `receiptDigest`; the checker recomputes the
receipt, prompt, and output digests with the native-JS canonicalization in
`scripts/aleph-canonical.mjs` (Node-side only — the browser digest path remains its own undecided
surface), re-derives the receipt counts, and fails closed on orphaned displayed receipts, duplicate
digests, measurement mismatches, or broken digest linkage. It establishes artifact-to-evaluation
linkage and canonical form; it does not establish that the measurements satisfy the research
measurement contracts, and it never calls a model.

## MiniPrompt reproduction checks

`npm test` also runs `search/tests/test_miniprompt.py` (pure standard library) and the
MLX-gated smoke tests in `search/miniprompt/tests/` (skipped without MLX; run them with
`search/.venv`). The pure tests pin the strict config parser and digests, the scan-policy
state machine to concrete upstream sequences, the seeded sampling derivations, receipt
construction, and the fail-closed receipt verifier via tamper probes whose digests are
re-fixed after tampering, so the semantic checks must fire on their own. The verifier is also
the no-MLX `verify` command:

```bash
python3 -m search.miniprompt.cli verify search/miniprompt/receipts/canary-hello-001
```

It replays the declared scan policy across recorded outcomes and checks each acquisition's
evidence chain (all-match plus greedy continuation) canonically; it does not re-run the model,
and running a scan itself needs the pinned MLX environment.

## Matched-budget comparison checks

`npm test` also runs `search/tests/test_compare.py` (pure standard library, no MLX): the declared
comparison fixtures and their pinned digests, the strict config parser, the readable-artifact
verifier with tamper probes (evaluation sequence and budget structure, per-budget selection,
staircase `kept` flags, stability runs, copy ratios, digest linkage, negative-zero
normalization), the digest-bound record builder/verifier against the real archived raw receipt
(build, tamper, on-disk tamper, kept-derivation mirror of the shipped selector, fail-closed
refusals), the pure runner helpers, and a faked-model dry run of the readable runner's state
machine (pause/resume, idempotent completion, tampered-artifact refusal). The verifier is also
the no-MLX command:

```bash
python3 -m search.compare.cli verify search/compare/receipts/canary-1p7b
```

It re-derives both side artifacts with their own fail-closed verifiers, re-checks the cross-side
identity assertions and the declared findings, and recomputes every digest; it does not re-run
the model (running an instance needs the pinned MLX environment) and it never expresses a
comparison verdict.

## Release gate

Before a formal release, run:

```bash
npm run lint
npm run test
npm --workspace web run build
npm run api:smoke
apps/api/.venv/bin/python -m pytest apps/api/tests -q
search/.venv/bin/python search/preflight.py
git diff --check
```

Also run a server-configured hosted smoke against `/health` and `/api/search`
when the release depends on hosted black-box mode. A passing hosted smoke
documents that the pinned adapter/configuration returned prompt/output
candidates as `black_box` observations in that run; it does not prove general
runtime support, token NLL, logits, or a globally shortest prompt.

## API smoke

The API adapter boundary has an additional smoke check:

```bash
npm run api:smoke
```

It validates `mode=mock` and a fake live-search response against
`schemas/aleph-run.schema.json`, checks the Shortest Found and Explicit
Reconstruction endpoints, and verifies that `local_mlx_search` fails
recoverably when `search/server.py` is not running. It requires the local API
Python environment but does not require MLX or a live model.

## Demo readiness

Before demo freeze, run:

```bash
npm run demo:check
```

It runs the required fixture/mock path (`npm test`, `npm run lint`,
`npm run build`, `npm run api:smoke`, API compile, and API pytest), then tries
`search/preflight.py` with `search/.venv/bin/python` when available as an
optional local-MLX check. If
`http://127.0.0.1:8000/health` is reachable, it also runs
`npm run api:live-smoke`. Blocked optional checks mean local MLX mode is
unavailable in that shell. If preflight is ok but live smoke is blocked, start
`search/server.py`; if preflight is blocked, set up `search/.venv`. Either case
does not invalidate the fixture/mock demo path.
