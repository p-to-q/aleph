# Synchronize Linux acceptance and release identities

The owner requested completion of both repositories and public release surfaces.
This product-side slice mirrors Benchmark's source-bound Linux qualification and
its separate zero-model-call hosted runtime observation. The Benchmark plan is
`docs/plans/2026-11-27-release-completion.md` in `p-to-q/aleph-benchmark`.

## Acceptance

- Mirror the exact accepted evidence records and download-verified archive hash.
- Keep Linux arm64 CLI acceptance distinct from hosted CI, Kaggle scorer
  qualification, model quality, HF H2 publication and authority transition.
- Publish product patch 1.0.5 with matching workspace/lock/release-map versions,
  a small reviewed PR, immutable tag and release notes. Do not move v1.0.4.
- Run the repository lint gate, relevant tests and production build. After merge,
  verify production deployment source and the canonical `/health` version.
- Record actual account-level Actions refusal and HF's missing authenticated
  session; neither is repaired by inventing a successful status.

No UI, metric, dataset, model policy, permission, credential, or historical
provenance change belongs to this slice. No paid overage or model calls.
