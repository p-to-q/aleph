# Aleph-Bench — M0 implementation (`bench/`)

Implementation and operations readme for the `bench/` engine. For the full design, research, and
launch dossier (12 numbered docs + launch kit), see [`docs/benchmark/`](../docs/benchmark/README.md);
for the frozen v0.1 M0 result read
[`docs/benchmark/m0-evidence.md`](../docs/benchmark/m0-evidence.md).


Aleph-Bench turns the Aleph compression workbench into a controlled comparison instrument. Instead of asking for one model's shortest known prompt path, it holds the target set and procedure fixed and compares how much non-leaking prompt coordinate length different models need.

## Protocol versions

The checked-in, unversioned M0 dataset and evidence paths are the immutable **v0.1** record. v0.1
called its soft normalized-edit score `exact`; that historical meaning remains attached to those bytes
and results. Do not regenerate v0.1 artifacts with a newer scorer or reinterpret their numbers under a
newer protocol.

**v0.2 is a breaking scorer protocol**, not a correction that can be applied in place. Its dataset
and schemas live in v0.2 namespaces; every generated v0.2 result and platform package carries
`protocolVersion: "0.2.0"` and must be written to a user-selected path, never a legacy v0.1 path. The
runner rejects missing, mixed, or different protocol versions before scoring. v0.1 and v0.2 scores
are therefore not directly comparable.

v0.2 scoring is reproducible only under Python 3.13 with Unicode Character Database 15.1.0. Those
runtime versions are part of the scoring profile and are checked before a run; a mismatched runtime
fails closed rather than silently changing Unicode behavior.

The public S2 dataset is also a protocol input, not an interchangeable directory. Canonical runs
require dataset id `aleph-bench-v0.2-public-s2`, exactly 30 items, and the length-framed
filename-and-content SHA-256 declared in `bench/config/frozen_ladder-v0.2.json`; that identity is
checked before model calls and repeated in manifests and results. Full runs carry
`evaluationScope: "canonical"`. A library-only item limit is diagnostic and produces
`evaluationScope: "smoke"`; the release CLI intentionally exposes no `--limit`, and smoke results
must not be presented as full benchmark evidence.

## M0 Shape

The first implementation is Track F, Frozen Ladder:

```text
BenchItem
  -> 4 rung ladder with 2 paraphrases per rung
  -> model adapter generations
  -> leakage gate
  -> monotone non-leaking frontier
  -> AURC, ECL@tau, Elicit@k, bootstrap CIs
  -> BenchResult
```

M0 uses S2 compositional targets: synthetic, rule-generated outputs that should not be memorized as public text, but can be reconstructed from a sufficiently precise rule prompt.

Each item/model run keeps the canonical `AlephRun` plus a benchmark-only `measurements` receipt. The receipt records every ladder prompt's rung, paraphrase, measured length, raw decoded outputs, effective rerun count, fidelity mean, fidelity variance, fidelity standard deviation, and leakage-gate decision. Raw model output is captured as a string before any scoring normalization; adapters must not trim whitespace or coerce non-string values. This keeps stochastic-run variance visible without adding benchmark-only fields to product `CandidatePoint` objects.

## Evidence Modes

The checked-in frozen v0.1 M0 result is deterministic mock evidence. It validates that historical
benchmark pipeline, not the relative quality of real models. Generated v0.2 mock results have the
same evidence limitation and are not a real-model leaderboard.

Hosted black-box runs are supported by the adapter path, but require server-side OpenAI-compatible credentials. Black-box rows report generated text behavior only; they do not report logits, token NLL, or model-internal evidence.

The hosted path is covered by offline local `/chat/completions` tests: request path, bearer auth, model id, prompt message, temperature, `max_tokens`, response parsing, HTTP error reporting, bounded retry on 429/5xx failures, and a one-item end-to-end `black_box` `BenchResult`.

Hosted runs can use `--cache-dir` to save per-call responses and resume after interruption. Use an
ignored path such as `.cache/aleph-bench/v0.2-hosted` so provider outputs do not become accidental
repository artifacts.

The v0.2 cache identity includes the protocol and raw-response capture versions. Cached outputs remain
raw strings: normalization belongs to a declared metric, not to transport or cache handling.
Treat a cache directory as a resume namespace for one provider deployment and evidence run. A mutable
provider model alias does not reveal its backend revision; use a fresh cache namespace when the alias,
deployment, or intended evidence date may have changed.
The cache path must be a dedicated private directory: it may be absent (the CLI creates it as `0700`)
or already have mode `0700`. The CLI rejects broader existing directories and symlinked path
components under user-controlled paths instead of changing their permissions. Root-owned system
directory aliases whose parent is not writable, such as macOS `/var`, are resolved as trusted
ancestors.

The frozen protocol records a seed, but the portable hosted adapter does not send that seed to the
OpenAI-compatible provider. It is a logical coordinate for bootstrap sampling and cache identity.
Hosted prompts are called five times even at temperature zero so provider-side nondeterminism remains
observable; the mock adapters remain single-call deterministic fixtures.

Hosted retries default to two retries with a one-second delay. Override with `ALEPH_CUSTOM_API_MAX_RETRIES` and `ALEPH_CUSTOM_API_RETRY_DELAY_SECONDS` when a provider needs a different policy.
Retry count is bounded to 0–5. Doctor and manifest distinguish logical generations from the maximum
HTTP attempts under that retry policy; the latter is still not a billing guarantee because a timed
out provider request may already have executed.

`ALEPH_CUSTOM_API_BASE_URL` is the OpenAI-compatible API base URL prefix (for example,
`https://provider.example/v1`); the adapter appends `/chat/completions`. The M0 hosted adapter
speaks one wire format; for cross-vendor coverage (Anthropic, Gemini, Grok) point it at an
OpenAI-compatible proxy such as OpenRouter or LiteLLM. Native Anthropic / Gemini / Vertex adapters
are M1 scope.
Remote endpoints must use HTTPS so bearer credentials are not sent in cleartext; plain HTTP is
accepted only for `localhost`, `127.0.0.1`, or `::1` test servers. Redirect responses are rejected
instead of followed so credentials remain bound to the configured endpoint.

## Metrics

- **AURC** is the area under the monotone rate-distortion staircase. Lower is better.
- **ECL@tau** is, per item, the shortest non-leaking coordinate length that reaches the fidelity
  threshold.
- **Elicit@k** is the share of items where a non-leaking prompt with measured length at most `k`
  reaches the fidelity threshold. The M0 default is a 16-unit budget, loaded from
  `bench/config/frozen_ladder-v0.2.json` for v0.2.
- **Leakage** is a gate, not a penalty. Disqualified prompts are excluded from compression metrics.

The v0.2 threshold is `tau = 0.95`. It accepts exactly three fidelity metric classes:

- `exact`: binary equality of the two raw decoded Python string code-point sequences. It performs no
  Unicode, newline, case, or whitespace normalization.
- `normalized_edit_similarity`: replace CRLF and lone CR with LF, normalize to NFC, then compute
  `1 - Levenshtein / max(code-point lengths)`. Case, whitespace, punctuation, and order remain
  significant.
- `unicode_char_ngram`: normalize to NFC, case-fold, normalize to NFC again, collapse Unicode
  whitespace, form code-point trigram multisets, and report multiset Jaccard similarity. Repeated
  trigrams retain their multiplicity; punctuation, symbols, and ZWJ code points are retained.

An undeclared or unsupported metric class is an error; v0.2 has no implicit fallback to an older
metric. The current S2 items declare `normalized_edit_similarity`. The v0.1 near-miss behavior remains
only a legacy v0.1 fact and is not v0.2 `exact` semantics. Engine and generated-scorer behavior is
locked by the shared [v0.2 scorer conformance vectors](conformance/scorer-v0.2.json).

The v0.2 leakage unit is `unicode_dual_channel_v1`. Both channels map CRLF and lone CR to LF, apply
NFKC, case-fold, and apply NFKC again. The lexical channel then keeps Latin-like letter/number runs
together, emits wide/full-width letters and numbers such as CJK code points individually, and retains
punctuation and symbols. The boundary-insensitive skeleton channel compares the remaining non-space
code points directly, so inserting punctuation or splitting a word cannot defeat only the lexical
segmentation. The gate disqualifies a prompt if any of these six thresholds is reached:

```text
lexical:   lcsRatio >= 0.65
        or targetTrigramRecall >= 0.50
        or verbatimSpanUnits >= 16
skeleton:  skeletonLcsRatio >= 0.80
        or skeletonTargetTrigramRecall >= 0.80
        or skeletonVerbatimSpanUnits >= 32
```

Shared normalization removes controls, format characters, surrogates, variation selectors, and emoji
skin-tone modifiers. Private-use (`Co`) and unassigned (`Cn`) code points are deliberately preserved
rather than erased, because opaque copied payloads must remain visible. The conservative skeleton is
not a Unicode UTS #39 confusable-skeleton implementation: cross-script homoglyph substitution remains
a documented manual-audit limitation, as do same-script and multi-code-point visual confusables
such as `I`/`l` and `rn`/`m`. Both trigram-recall channels count occurrences rather than
distinct trigram membership, so a short repeated substring cannot claim full recall of a long repeated
target. Scorer inputs are capped at 16,384 Unicode code points before any quadratic edit/LCS work.
Normalization output is separately capped at 32,768 code points, and every edit/LCS pair is rejected
before allocation when its length product exceeds 1,000,000 cells; compatibility expansion therefore
cannot bypass the raw-input bound.

Before those overlap tests, v0.2 also fails closed on raw prompt bidi-control code points and CJK
Compatibility Ideographs. Each receipt records `failClosedReason` as `bidi_control`,
`cjk_compatibility_ideograph`, or `null`; benchmark targets containing either class are invalid.

Length and token measurement are a separate contract. v0.2 hardens output scoring and leakage, but
does not resolve the cross-provider length/token definition or the aggregate ECL convention tracked
in [#35](https://github.com/p-to-q/aleph/issues/35). The current result reports mean ECL over only
the items that reach `tau`, alongside `coverageAtTau`; it is not yet the design document's proposed
median normalized compression factor. Until #35 lands, do not present the interim length proxy as
tokenizer-comparable evidence across scripts or providers, or ECL as a settled leaderboard headline.

## Commands

All v0.2 examples name the versioned dataset explicitly and write generated artifacts outside the
repository. They do not overwrite the frozen v0.1 evidence.

Check dataset validity, leakage-gate distribution, hosted environment variables, and call budget
before a run:

```bash
./aleph-bench doctor \
  --data-dir bench/data/v0.2/public/s2 \
  --model hosted:model-a,hosted:model-b,hosted:model-c
```

Write a no-call manifest of the non-leaking prompts that would be sent:

```bash
./aleph-bench manifest \
  --data-dir bench/data/v0.2/public/s2 \
  --model hosted:model-a,hosted:model-b,hosted:model-c \
  --out /tmp/aleph-bench-v0.2/hosted-manifest.json
```

v0.2 manifests validate against
[schemas/v0.2/aleph-bench-manifest.schema.json](../schemas/v0.2/aleph-bench-manifest.schema.json)
before the CLI writes them.

Run a deterministic mock result and render a report in a temporary directory:

```bash
./aleph-bench run \
  --data-dir bench/data/v0.2/public/s2 \
  --model mock-frontier,mock-mid,mock-small \
  --seed 0 \
  --out /tmp/aleph-bench-v0.2/mock-result.json
./aleph-bench report \
  --result /tmp/aleph-bench-v0.2/mock-result.json \
  --out /tmp/aleph-bench-v0.2/mock-report.md
```

Run hosted black-box rows after setting `ALEPH_CUSTOM_API_BASE_URL`,
`ALEPH_CUSTOM_API_KEY`, and a reviewed `ALEPH_CUSTOM_API_DEPLOYMENT_ID`. The deployment id is a
non-secret operator receipt for the exact provider snapshot or proxy route; do not put credentials
in it.

```bash
./aleph-bench run \
  --data-dir bench/data/v0.2/public/s2 \
  --model hosted:model-a,hosted:model-b,hosted:model-c \
  --seed 0 \
  --cache-dir .cache/aleph-bench/v0.2-hosted \
  --out /tmp/aleph-bench-v0.2/hosted-result.json
```

Build and check a disposable v0.2 scorer-conformance package. A package is not a release merely
because it was generated successfully:

```bash
./aleph-bench package-v0.2 --out-dir /tmp/aleph-bench-v0.2-package
./aleph-bench package-v0.2 --check /tmp/aleph-bench-v0.2-package/package-manifest.json
python3.13 /tmp/aleph-bench-v0.2-package/kaggle/run_conformance.py
```

The generated package includes the 30-item JSONL dataset, v0.2 schemas, shared conformance vectors,
checksums, and the scorer core copied byte-for-byte from the canonical engine module. It is staging
material for Kaggle integration and scorer conformance, not a complete Kaggle evaluator: it does not
implement submission I/O, model execution, AURC/ECL aggregation, or leaderboard hosting. It is also
not model evidence or a publication bundle.

### Diagnose the Kaggle deployment path without creating a score

The generated task at
`bench/tasks/kaggle/aleph_bench_v0_2_diagnostic.py` is a separate deployment canary. It is not part
of the scorer-conformance package and must never be selected for an Aleph-Bench leaderboard. Check
that its bytes still match the canonical v0.2 data and package identities with:

```bash
python3.13 bench/tasks/kaggle/generate_v0_2_diagnostic.py --check
```

The task returns a structured dictionary and writes
`aleph-bench-v0.2-kaggle-diagnostic-receipt.json`; it deliberately has no numeric result. Its first
helper action requires Python 3.13 and Unicode database 15.1.0. A mismatch produces a blocked receipt
with zero attempted model calls before the helper reads an attached package, invokes the model, or
opens a per-prompt named chat. Kaggle's SDK still creates its empty root task chat before entering the
helper. A conformant runtime then verifies the attached scorer-conformance package and runs only the
literal six-prompt set `s2-001/002/003 × r1-p0/p1`, with one isolated named chat per prompt,
`reasoning="none"`, a 2,048-token output cap, and no retries. Empty output, invalid usage, a near-cap
response, a non-string output, or a proxy exception stops the canary and preserves a blocked partial
receipt. The task records a call-ahead state before every dispatch, and its Kaggle assertion marks any
blocked dictionary as not passed without discarding the diagnostic payload.

"No retries" is enforced at both layers used by the supported Kaggle transports: the task sets the
OpenAI client retry count to zero or verifies the GenAI retry controller permits one attempt, then
reads that setting back before any call. Task creation has a separate one-shot journaled helper
because released Kaggle CLI push retries the non-idempotent create request. The runbook binds the
result to the exact returned task version and the unique task run for that version, then downloads
the run output without scheduling another model run. Kaggle's create acknowledgement may omit the
backing-kernel ID while creation is still pending; this is recorded as `null`, then observed by the
later exact-version readback when Kaggle exposes it. Artifact retrieval is independently bound to
the unique run instead of treating a missing kernel ID as a lost create response. The helper reads
the latest remote task version and fails closed when its creation is non-terminal; operators must
still serialize task creation because the remote API exposes no idempotency key.
It accepts only the reviewed Python 3.13 / Kaggle CLI 2.2.4 / Kaggle SDK 0.1.37 / Jupytext 1.19.5
client matrix and fails before authentication when that local environment drifts.

Additional model runs on an already-created Task version must use the exact-version one-shot
scheduler, not `kaggle benchmarks tasks run`. The released Kaggle CLI command targets the latest
version, wraps the paid scheduling request in generic retry, and returns no run id. Aleph's helper
requires the exact owner, Task, positive version, and canonical model-version slug; snapshots the
complete run set and daily/monthly quota; fsyncs a durable retry barrier; crosses the paid API once;
then binds exactly one new run id by read-only run-set difference:

```bash
python3.13 -m bench.engine.kaggle_run_once \
  --owner OWNER \
  --task TASK \
  --version VERSION \
  --model CANONICAL-MODEL-VERSION \
  --creation-journal /absolute/private/evidence/creation/dispatch/push-journal.json \
  --journal /absolute/private/evidence/MODEL/dispatch/run-journal.json
```

List canonical model-version slugs with `kaggle benchmarks tasks models`. Never use a provider path
or mutable `@` alias as the scheduler input. A `reconciled` journal is the only successful outcome.
`ambiguous`, `not_scheduled`, an existing journal, a conflicting active run, model-catalog drift,
an existing run for the same exact model, parent-version redirection, or a non-unique run-set
difference is a hard stop. Inspect and reconcile read-only; do not choose a new journal and dispatch
the same run again.

The creation journal must be the exact canonical `kaggle_push_once` receipt for this Task version.
The scheduler verifies its current generated source and deterministic notebook identity before it
creates the run journal or schedules a paid run, then resolves and binds the exact source-kernel
readback. Any generated source change requires a new one-shot Task version; older immutable Task
versions do not receive compatibility exceptions.

Immediately before the paid boundary, the scheduler atomically creates a durable model claim in a
private sidecar directory beside the original creation journal. Its name is derived from the exact
receipt/task/model rather than the chosen run-journal path, so concurrent local attempts for the
same exact model and a second local journal path cannot both dispatch. Different models must still
be scheduled one at a time. After all remote preflight reads and immediately before that claim, it
revalidates both the current generated source and the original receipt bytes.
Retain the claim permanently. This is a same-host,
same-receipt-filesystem guard, not a distributed lock: never copy the creation receipt into another
control directory or schedule the same Task version from another host.

For evidence download, `--run-id` and `--dispatch-journal` are inseparable. The journal must use
version 2 and carry verified creation authority. Legacy v1 journals are not accepted by the current
evidence path; historical recovery requires a separate reviewed authority migration. An unbound
evidence-schema 1.0 bundle may remain readable as diagnostic history, but it is always
`assemblyEligible: false`; removing an authority binding cannot preserve an assembly-eligible
artifact.

Write the final evidence files to a separate `MODEL/bundle/` directory. The binder retains a
content-bound copy of the dispatch journal there; the original `dispatch/run-journal.json` must
remain outside because the closed-world loader rejects every file not named by the envelope. Use
`python3.13 -m bench.engine.kaggle_capture_bundle` to non-destructively materialize an older flat
layout whose sole extra file is an identical original `run-journal.json`.

Even a complete receipt has `evidenceMode: "none"`, `protocolConformant: false`,
`leaderboardEligible: false`, `publicationEligible: false`, and `diagnosticScalar: null`. It proves
only that this small transport-and-capture path worked; it is not AURC, a model rank, or permission
to schedule a canonical v0.2 run. See the
[Kaggle deployment diagnostic runbook](../docs/benchmark/kaggle-diagnostic-runbook.md).

### Assemble score-free capture evidence offline

`bench.engine.kaggle_capture_evidence.load_verified_capture_bundle` is the public loader for one
explicit evidence filename. It accepts only a bounded, closed-world directory of single-link
regular files and reruns the full archive, payload, source, dispatch-journal, and envelope verifier.
`bench.engine.capture_set_receipt.assemble_capture_set_receipt` compares those verified snapshots
with one content-addressed scope plan, rejects gaps, overlaps, duplicates, identity drift, and shard
order drift, then emits a deterministic score-free `CaptureSetReceipt`.

The only current authority plan is returned by `transport_canary_scope_plan()`: six calls, six
prompts, three touched items, rerun zero, and zero complete canonical items. Its 2,048-token capture
policy is not the formal v0.2 hosted 512-token policy. The canonical authority registry is therefore
checked in empty, and no current or synthetic receipt can set `canonicalScoringInputEligible` true.
Adding an exact formal scope-plan id, request-policy digest, and content-addressed model mapping is a
separate review gate; a receipt never contains a score, `BenchManifest`, or `BenchResult`.
Serialization checks schema, content identity, and internal consistency, but it does not establish
authority from receipt bytes alone. Before any scorer consumes a receipt, run
`verify_capture_set_receipt` with the exact retained bundles, scope plan, and model mapping; that
function rebuilds the receipt and compares every field.

### Replay a retained legacy Kaggle run

A completed legacy Kaggle `*.run.json` retains the named conversations, raw assistant strings, and
request usage even though the task returns only a leaderboard float. Convert it into a canonical,
detailed, offline receipt with no model or network calls:

```bash
./aleph-bench kaggle-replay \
  --run-json /path/to/aleph_bench_frozen_ladder.run.json \
  --package-root bench/results/platform/m0-mock \
  --max-tokens 512 \
  --out /tmp/aleph-bench/kaggle-receipt.json
```

The command accepts only a receipt-identical immutable v0.1 package, requires exact 180-row
conversation coverage, executes the pinned scorer from one verified in-memory snapshot, and checks
Kaggle's scalar against inverse AURC. It writes a fresh content-addressed receipt without replacing
an existing path and exits `2` when empty, invalid-usage, or near-cap outputs make the run
operationally blocked. The supported legacy task identity, audited `512` generation cap, and
four-token saturation margin are fixed; changing the asserted cap cannot reclassify a truncated run
as valid. `--max-tokens` remains explicit because the retained run JSON does not itself prove the
invocation argument. Inputs and output text are bounded before the quadratic legacy scorer runs, and
serialization checks cross-field semantics in addition to JSON Schema and content identity. This
includes replaying the raw rows with the pinned scorer and comparing the complete detailed result.
The receipt is not a signature: retain the source run JSON and verify `sourceRunSha256` when auditing
the extraction. This improves inspection of legacy evidence; it does not relabel that evidence as v0.2. See the
[Kaggle replay runbook](../docs/benchmark/kaggle-runbook.md).

Track, split, stratum, `tau`, `k`, rerun count, bootstrap count, dataset identity, and leakage
thresholds are frozen in the v0.2 protocol configuration. The release CLI does not expose overrides
for them and does not expose a smoke-test item limit; change to any of those values requires a new
protocol rather than another command-line flag. The exact config bytes are independently anchored by
SHA-256 in the protocol module and rechecked before planning or model calls, so editing the config
while retaining `protocolVersion: "0.2.0"` fails closed.

### Frozen v0.1 legacy evidence

`bench/data/public/s2`, `bench/results/m0-*`, `bench/results/platform/m0-mock`, the root benchmark
schemas, and `docs/benchmark/m0-evidence.md` are the frozen v0.1 record. Verification of that package
is read-only and digest-based:

```bash
./aleph-bench audit
./aleph-bench bundle --check bench/results/m0-bundle.json
./aleph-bench package --check bench/results/platform/m0-mock/package-manifest.json
```

The legacy `audit`, `bundle`, and `package` commands are check-only: they validate frozen receipts and
digests and never replay the v0.1 scorer or rewrite evidence. Do not point `run`, `manifest`, report
output, caches, or `package-v0.2` output at legacy paths; write guards reject those destinations.
