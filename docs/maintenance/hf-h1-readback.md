# Recheck the historical Hugging Face publication

The 2026-11-27 independent readback corrects a maintenance bookkeeping error:
H1 was already published at Hub commit
`045d768ee4f1ade5812b3d2761f5bd8b7c5855a9`. Its public API modification time is
2026-09-24 18:42:51 UTC (2026-09-25 02:42:51 Asia/Shanghai). This audit made no
Hub write. An unavailable current write credential would not undo that event.
The [source-bound result](evidence/hf-h1-readback.json) records exact identities.

## Reproduce

From the product repository, capture into a new external directory:

```bash
python3.13 -I -S -B scripts/audit-hf-h1-snapshot.py --capture-dir ../fresh-h1-snapshot > ../h1-readback.json
python3.13 -I -S -B scripts/audit-hf-h1-snapshot.py --check ../fresh-h1-snapshot > ../h1-replay.json
python3.13 -B -m unittest search.engine.tests.test_hf_h1_snapshot_audit -v
```

The first command makes anonymous public GET requests. The second only reads
retained files; it makes no HTTP requests. Failed/partial captures remain for
diagnosis, and an existing capture directory is never overwritten. The expected
H1 main commit and historical commit/receipt are pinned in the script. If Hub
main moves, review the new event separately; do not simply repin this H1 audit
to bypass H2's release gate. `snapshotTree` binds the complete retained capture,
including API responses, original file bytes, server counts and capture time;
`auditorSha256` binds the verifier used for that report.

## Prior art and evidence boundary (accessed 2026-11-27)

- **F — primary response evidence:** the [Hub repository API](https://huggingface.co/api/datasets/p-to-q/aleph-bench)
  and its exact-revision recursive tree endpoints expose file paths, byte counts
  and Git blob IDs. This auditor binds downloaded bytes to each object ID before
  comparing the historical and H1 file sets. Equal object IDs are downloaded
  once and checked against both revision inventories.
- **F — original control:** [the pinned publication receipt](https://huggingface.co/datasets/p-to-q/aleph-bench/blob/045d768ee4f1ade5812b3d2761f5bd8b7c5855a9/h1-publication-receipt.json)
  binds the four metadata changes, 31 unchanged original files and the 21-file
  scientific payload. The auditor pins its SHA-256, recomputes both trees and
  checks both original checksum inventories. Public raw bytes and the immutable
  historical tag are retained in the snapshot; no local import is treated as a
  substitute for them.
- **F — consumer response evidence:** [Dataset Server size](https://datasets-server.huggingface.co/size?dataset=p-to-q%2Faleph-bench)
  reports 30 item rows and 240 prompt rows, with no pending, failed or partial
  result. Duplicated or missing split rows fail the check.
- **I — decision:** H1 is complete and publicly readable; remove it from pending
  work in active release maps. Use this narrow stdlib auditor and the existing
  test discovery rather than adding an uploader, service, dependency or workflow.
- **U — still unproved:** current authenticated write access, H2 v0.2 publication,
  installed-distribution qualification, portable/platform acceptance, scientific
  generalization and formal model scores. Anonymous HTTP captures are replayable
  observations, not signed statements by Hugging Face or renewed execution
  authorization. The H1 receipt itself keeps original-generation provenance
  unknown; this readback does not reconstruct or invent it.

## Retained evidence packet

The release map's `evidence.publicationReadbackPacket` binds the 639,936-byte
archive, both GitHub release mirrors, its exact pre-evidence source commits and
all 276 regular members. Downloaded bytes from both mirrors match the local
archive; an independent unpack verifies every member hash, size and mode.
Rebuilding produces identical archive bytes. Replaying the unpacked H1 input,
15 auditor tests and six real-snapshot mutations succeeds without HTTP.

The archive preserves the original live capture result and the stricter final
verifier's replay separately. Its README identifies the exact source of each;
do not attribute the initial capture to the later verifier. It also retains
failed checks and independently loaded HF/Croissant output. This evidence asset
does not move either release tag or promote H2.
