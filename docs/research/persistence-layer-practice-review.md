# Persistence-layer practice review (prior-art backfill)

**Date:** 2026-10-15 · **Scope:** the persistence-layer choice left open by the engine plan —
`docs/open-questions.md` §8, the "Persistence | Not chosen." row in `docs/state-of-play.md`, and
review §8 item 1 ("survey event-store/JSONL/SQLite practice when picked"). **Why:** the
structural-decision research gate in `docs/research/research-process.md` requires a recorded
prior-art survey before new storage structure lands. This note is that survey. It changes
documentation status and constraints, not code: no new module, format, or dependency.

Evidence tags: **F** = fact observed in a primary source — external pages fetched 2026-10-15 (URL
in Sources), or this repository (path given inline); **I** = interpretation for Aleph; **U** =
open question.

## 1. What Aleph already has (F, repository)

**F.** The merged engine writes one append-only run bundle per run, with the layout fixed by issue
#106 (`search/engine/archive.py` docstring):

```text
runs/<run_id>/
  manifest.json
  events.jsonl
  blobs/sha256/<digest>
  materialized/{archive,views,confirmation,resource-ledger}.json
  exports/{aleph-run,aleph-run-projection}.json
  verify.json
```

`events.jsonl` is the only authority. Everything under `materialized/` is derived by replaying
that stream, "so a view can be deleted and rebuilt byte-identically". The writer "refuses to
rewrite an existing event line and refuses to overwrite a blob whose digest already exists with
different bytes"; blobs are content-addressed, so an identical write is a no-op; `manifest.json`
is rewritten "exactly once at `close()` (atomic replace)" to record the final stream digest.

**F.** Export is already a fail-closed exchange format (`search/engine/export_aleph_run.py`): a
measurement-lossless `AlephRun` projection plus a projection record carrying `artifactRef` and a
per-leaf source map. Only a run that closed as `completed` is exportable (typed `ExportError`
otherwise); `createdAt` is byte-copied from the declared `run_started` payload and is never
invented.

**F.** The verifier "recomputes every derived artifact from the source stream" and requires the
`materialized/` files and the exports to equal the replayed bytes byte-for-byte
(`search/engine/verify.py`). Corruption fails closed.

**F.** `docs/open-questions.md` §8 lists four options — no persistence; local JSON export/import;
file-backed runs; database — with the maintainer leaning "JSON export/import before database".
`docs/state-of-play.md` records the acceptance gate "JSON import/export first; database only after
saved-run workflow proves useful" and lists "Add JSON import for `AlephRun`" as Next Correct Move
#4.

**I.** The genuinely open questions are therefore narrower than "which store": (a) what a strict
import surface must verify to preserve the evidence boundary; (b) whether and when any queryable
index or database is justified on top of the bundle; (c) what keeps the bundle a durable,
exchangeable unit. The survey addresses each.

## 2. Event-log practice (Fowler; Azure Architecture Center; Kreps; Kafka)

**F (Fowler, Event Sourcing).** The pattern's definition is to capture all changes to application
state "as a sequence of events"; the log supports a "Complete Rebuild" — "discard the application
state completely and rebuild it by re-running the events from the event log" — and audit logs fall
out of the same stream. Fowler's cautions: "One of the tricky elements to Event Sourcing is how to
deal with external systems that don't follow this approach (and most don't)", and interactions
that are both queries and updates to external systems "cause a lot of complication".

**F (Azure Architecture Center, Event Sourcing pattern).** Record each action "in an append-only
store" that "acts as the system of record" from which domain objects are materialized; events are
immutable and appended, which improves write throughput. Large streams make replaying every event
costly, so practice adds periodic snapshots and implements materialized views — "read-only
projections of the event store that are optimized for querying". The pattern is explicitly costly:
it "introduces significant trade-offs", is costly to migrate to or from, "constrains future design
decisions", requires upcasters or compensating events when schemas or bad data demand change,
conflicts with deletion requirements, and leaves projections only eventually consistent.

**F (Kreps, The Log).** "A log is perhaps the simplest possible storage abstraction. It is an
append-only, totally-ordered sequence of records ordered by time." The essay's frame: logs are the
unifying abstraction for data integration, real-time processing, and system building; in
leaderless serving designs "the log is the source of truth".

**F (Kreps/Narkhede/Rao, Kafka, NetDB'11).** Kafka is a "distributed messaging system … for
collecting and delivering high volumes of log data"; consumers pull data, and retention is a
configured, time-based policy.

**I.** Aleph's bundle already implements this practice's core: an append-only log as system of
record with derived, disposable projections. What the practice adds is discipline: derived
artifacts must never become a second source of truth (the verifier already enforces this), and any
future snapshot/index must be rebuildable from the log. Azure's trade-off paragraph reads,
honestly, as an argument against adopting an event-store server or database at our scale: those
costs buy multi-writer, cross-service, long-stream properties Aleph does not need.

**U.** If cross-run query surfaces appear, decide between a disposable index rebuilt from bundles
and a real database, against the triggers in §6.

## 3. File-backed stores, serialization, and content addressing (SQLite; JSON Lines; Git; DVC)

**F (SQLite, Appropriate Uses).** SQLite "strives to provide local data storage for individual
applications and devices" and emphasizes "economy, efficiency, reliability, independence, and
simplicity". Its own page separates "Situations Where SQLite Works Well" from "Situations Where A
Client/Server RDBMS May Work Better" (client/server applications, high concurrency, high volume
websites), and states SQLite "does not compete with client/server databases".

**F (SQLite, WAL).** WAL gives "readers do not block writers and a writer does not block readers",
but "since there is only one WAL file, there can only be one writer at a time" — single-writer
semantics per database file.

**F (SQLite, Application File Format; Long Term Support).** "Writes to an SQLite database are
atomic"; application formats are "usually contained within a single file, for ease of transport";
"Incremental And Continuous Updates" are a stated benefit; and "the intent of the developers is to
support SQLite through the year 2050".

**F (JSON Lines).** JSON Lines "is a convenient format for storing structured data that may be
processed one record at a time"; each line is a valid JSON value; the encoding section expects
UTF-8; it works with unix-style text processing tools.

**F (Git internals).** "Git is a content-addressable filesystem": objects live in the object
database under `.git/objects` and are retrieved by a key derived from their content.

**F (DVC internal files).** Bulk data lives in the cache "based on hashes of the data contents"
(the first two hash characters name the directory, the rest the file name); "no data tracked by
DVC should ever be pushed to the Git repository, only the DVC files that are needed to download or
reproduce that data".

**I.** `blobs/sha256/<digest>` is the Git/DVC content-addressing pattern, and `events.jsonl` is the
JSON Lines shape (one record per line, UTF-8, append-friendly). SQLite matters to Aleph only as a
candidate future index/query layer or whole-library file: single-file, atomic, long-lived — but
single-writer, and its documentation repeatedly warns not to choose it for shared-repository or
high-concurrency needs. Our constraints are one user, one machine, and one writer per bundle at
a time — an operational assumption, not an enforced guarantee: the bundle writer has no
cross-process serialization, so concurrent writers are themselves a trigger to revisit this
choice (§6).

**U.** If a whole-library file is ever wanted, "SQLite as the application file format" is the
practice-backed candidate, with the bundle remaining the import/export interchange. No trigger
today.

## 4. Evaluation and experiment-tooling practice (Inspect; lm-evaluation-harness; MLflow)

**F (Inspect, Log Files).** Evaluations write one log per task, to `./logs` by default; since
v0.3.46 `.eval` is the default format, which "supports compression and incremental access to
samples"; `.json` logs remain supported and can grow large. Logs "can get quite large (multiple
GB)", so readers can request just the header (`header_only`); a viewer reads logs interactively.

**F (lm-evaluation-harness).** "To save evaluation results provide an `--output_path`. We also
support logging model responses with the `--log_samples` flag for post-hoc analysis"; results and
samples can be published (e.g., to the Hub).

**F (MLflow, Backend Stores).** The backend store holds run metadata; "the file-based backend
stores metadata in local files in the `./mlruns` directory. This was the default backend in
earlier versions of MLflow, but is still supported for backward compatibility" — with a documented
migration path, and a database backend that is "now the default" and recommended "for better
performance and reliability". Bulk artifacts live in a separate artifact store; deleting a run
does not automatically remove its metadata or artifacts (an explicit `gc` command exists).

**I.** Harness practice converges on the triangle Aleph already has: per-run evidence files as the
durable primary artifact; a derived layer for reading and browsing; metadata indexes kept separate
from bulk artifacts. Inspect's header-only reads are a precedent for reading run metadata
without loading everything — they do not establish the integrity of the omitted content (our
verifier still replays the full stream) — and its per-task log file remains the analogue of our
per-run bundle as the unit of exchange. MLflow's history is the cautionary precedent for the file-vs-database fork: a
file store works until saved-run workflows want cross-run queries; the ecosystem answer then is a
migration story plus an explicit exchange format. For Aleph, the exchange format (export, plus the
planned import) should land before any such pressure arrives — matching the maintainer leaning.

**U.** Whether a future index is a store-root `index.json`, an on-demand rebuild, or per-run
scanning is an import-slice design decision.

## 5. Cross-source synthesis

**F → I.** Five practice clusters agree on one shape: (1) an ordered, append-only log per unit of
work as the system of record; (2) content-addressed bulk data; (3) derived, disposable projections
for reads; (4) optional, clearly disposable indexes or databases for queries; (5) self-contained
files/directories as the exchange unit. Aleph's bundle already instantiates this shape (§1). The
missing file-first piece is the **round trip**: export exists, import does not. The deferred piece
is any **queryable index/database**, which every source treats as a performance layer carrying
migration and consistency costs.

## 6. Effect on our structure

**In one sentence:** the structure does not change today — bundles remain the system of record and
no dependency is added — but the next structural step (a strict import surface) now has its
prior-art basis, and a database is explicitly deferred with recorded triggers.

| Area | Current structure | Finding | Action | Priority |
|---|---|---|---|---|
| Persistence choice | per-run bundles; no database | file-first matches practice for single-writer evidence stores; databases are query accelerants with migration costs | keep bundles as the system of record; record DB deferral + triggers; no dependency | now (this note) |
| Import surface | none | the round trip is the missing file-first piece across all reviewed practice | implement strict import for `AlephRun`/bundles: schema and digest checks; derived views replayed, never trusted from disk; refuse non-completed runs; fail closed | next slice (state-of-play Next Correct Move #4) |
| Cross-run queryability | manual bundle scans | indexes are disposable layers over logs | optional rebuildable index later; only under triggers | deferred |
| Deletion / retention | no policy | append-only conflicts with deletion; artifact stores need explicit gc | record as open question (§8) | low |
| Whole-library file | none | SQLite-as-application-file-format is the practice-backed single-file candidate | keep as candidate, not chosen | deferred |

**Re-evaluation triggers (I):** (i) a saved-run workflow with cross-run queries becomes a product
surface; (ii) concurrent writers or multi-machine sync become real; (iii) manifest scanning across
bundles outgrows the UI. Until then: no database, no index, no dependency.

## 7. What does not change

- No new module, format, or dependency; the engine stays standard library and file-based.
- `events.jsonl` stays the only authority; `materialized/` stays disposable and replay-derived;
  exports stay measurement-lossless, digest-bound, and fail-closed.
- The maintainer leaning stands: JSON export/import before any database.

## 8. Open questions (U)

1. **Import semantics:** trusted vs. adversarial bundles; where digests are re-verified; whether
   import can cross store roots; failure atomicity (a failed import leaves the target unchanged).
2. **Index format:** whether a future store-level index is a rebuildable JSON file, per-run scan,
   or SQLite; built only under the §6 triggers.
3. **Retention/GC:** when blobs and bundles may be deleted while exports and verifier references
   stay valid.
4. **Multi-machine sync:** semantics if hosted runs and local runs ever share one library.

## Sources (fetched 2026-10-15)

- Fowler, *Event Sourcing* — https://martinfowler.com/eaaDev/EventSourcing.html
- Azure Architecture Center, *Event Sourcing pattern* —
  https://learn.microsoft.com/en-us/azure/architecture/patterns/event-sourcing
- Kreps, *The Log: What every software engineer should know about real-time data's unifying
  abstraction* — Internet Archive capture `20170427172319` of
  https://engineering.linkedin.com/distributed-systems/log-what-every-software-engineer-should-know-about-real-time-datas-unifying
  (direct LinkedIn URL now 404; captured page byline dated December 16, 2013)
- Kreps, Narkhede, Rao, *Kafka: a Distributed Messaging System for Log Processing* — NetDB'11;
  PDF retrieved from https://notes.stephenholiday.com/Kafka.pdf (byte-verified: identical sha256
  on refetch)
- SQLite: *Appropriate Uses For SQLite* — https://sqlite.org/whentouse.html · *Write-Ahead
  Logging* — https://sqlite.org/wal.html · *SQLite As An Application File Format* —
  https://sqlite.org/appfileformat.html · *Long Term Support* — https://sqlite.org/lts.html
- *JSON Lines* — https://jsonlines.org/
- *Git Internals — Git Objects* — https://git-scm.com/book/en/v2/Git-Internals-Git-Objects
- DVC, *Internal Files* — https://doc.dvc.org/user-guide/project-structure/internal-files
- *Inspect — Log Files* — https://inspect.aisi.org.uk/eval-logs.html
- EleutherAI, *lm-evaluation-harness* — https://github.com/EleutherAI/lm-evaluation-harness
- MLflow, *Backend Stores* — https://mlflow.org/docs/latest/self-hosting/architecture/backend-store
- Attempted but not usable (recorded for honesty): O'Reilly "The Log" (404/moved), the direct
  LinkedIn article URL (404), and an ACM Queue mirror (403 Cloudflare challenge).
