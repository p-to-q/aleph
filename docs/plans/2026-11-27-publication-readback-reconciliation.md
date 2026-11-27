# Reconcile public publication evidence before further release work

Acceptance gate: independently verify the exact HF H1 snapshot and accepted
standalone wrapper, then correct both repositories' active release maps with
source-bound readback evidence. A missing current write credential must not be
used as proof that an earlier publication never happened.

## Evidence and implementation

1. Preserve the product primary checkout and its unrelated changes. Work on a
   separate branch; retain failed checks as well as passing evidence.
2. Review standalone PR #29 at its exact head. Re-run canonical acceptance from
   a fresh clone, compare two wrapper builds and exercise actual HF local
   directory/config discovery, not only the CSV loader. Merge only that head.
3. Read public Hub main and historical tag identities, exact revision file
   inventories/bytes, H1 receipt, checksums, Croissant, and Dataset Server rows.
   Compare all original files, allowing only the recorded four metadata changes
   and one added receipt. Recompute the unchanged payload identities rather
   than trusting an old issue comment.
4. Add a narrow read-only snapshot auditor plus offline mutation tests using
   existing stdlib/test conventions. Preserve its exact source and input/output
   digests. It must never upload, dispatch tasks, read credentials or call models.
5. Correct current H1 status and preserve H2, installed-distribution, portable
   runtime, authority, hosted decoding and fresh-authorization gates. Record
   independent wrapper acceptance separately from the older staging tag.
6. Run targeted regressions and Node 20+ lint, review small PRs before merge,
   and verify remote main and retained release evidence after publication.

## Boundaries

Product 1.0.4, protocol/package 0.2.0 and HF historical 0.1.0 stay separate.
No model performance claim, HF write, new Kaggle run, paid compute, authority
cutover, dependency addition, scoring change or broad cleanup is authorized by
this gate. Installation/runtime qualification remains a separate implementation
contract; do not invent package layout just to mark it complete.
