# Hosted v0.2 M0 Runbook

This runbook turns the next Aleph-Bench step into a procedure-fixed, offline-score-replayable
black-box evidence pass. It does not claim that a provider will regenerate the same model outputs,
and it does not replace or rewrite the immutable checked-in v0.1 mock receipt. Any durable hosted
result must use a new v0.2 namespace and go through its own issue and review.

## Purpose

The checked-in v0.1 M0 result is deterministic mock evidence. A hosted v0.2 run should answer a
narrower question: can the frozen v0.2 Track F procedure produce three schema-valid `black_box` model
rows without changing the canonical dataset identity, leakage gate, metric definitions, or embedded
`AlephRun` contract?

## Model Choice

Choose three hosted models that are likely to separate on S2 compositional targets:

- one frontier or largest available model;
- one mid-tier model from the same or a comparable provider route;
- one smaller or cheaper model that is expected to need more descriptive prompts.

Record the exact provider-facing model ids in the manifest and evidence note. Do not rename rows into marketing tiers after the run; the result file should carry the model ids used for calls.

## Preflight

Credentials must stay server-side:

```bash
export ALEPH_CUSTOM_API_BASE_URL=...
export ALEPH_CUSTOM_API_KEY=...
export ALEPH_CUSTOM_API_DEPLOYMENT_ID=provider-snapshot-or-proxy-route
```

> **Adapter scope (M0).** `ALEPH_CUSTOM_API_BASE_URL` is the OpenAI-compatible API base URL prefix
> (for example, `https://provider.example/v1`); the adapter appends `/chat/completions`
> ([`bench/engine/adapters/hosted_black_box.py`](../../bench/engine/adapters/hosted_black_box.py)).
> For cross-vendor coverage (Anthropic, Gemini, Grok), point it at an OpenAI-compatible proxy
> such as OpenRouter or LiteLLM. Set `ALEPH_CUSTOM_API_DEPLOYMENT_ID` to a stable, non-secret
> snapshot or route identifier reviewed for this run; the manifest and result retain it together
> with a hash of the final endpoint and the upstream model id. **Native Anthropic / Gemini / Vertex
> adapters are M1 scope** — M0 deliberately
> ships a single OpenAI-compatible adapter to keep the surface small and the leaderboard
> contract reviewable.

The adapter rejects HTTP redirects rather than following them, including same-origin redirects.
Configure the final base URL directly so the bearer credential cannot leave the reviewed endpoint.

Optional retry controls:

```bash
export ALEPH_CUSTOM_API_MAX_RETRIES=2
export ALEPH_CUSTOM_API_RETRY_DELAY_SECONDS=1
```

Then check readiness and call budget:

```bash
./aleph-bench doctor \
  --data-dir bench/data/v0.2/public/s2 \
  --model hosted:model-a,hosted:model-b,hosted:model-c
```

Proceed only if `doctor` reports `status: ready` and the canonical dataset id, item count, and digest
match the frozen config. The v0.2 hosted budget is 180 non-leaking prompts times three models times
five calls: 2,700 **logical generations**. With the default two retries, the pre-run upper bound is
8,100 HTTP attempts. A timeout can occur after a provider has generated or billed a response, so the
HTTP-attempt bound is the safer cost envelope; it is not a billing guarantee. Retry count is limited
to 0–5. The repeated logical samples measure provider-side nondeterminism even at temperature zero;
the logical seed is used for bootstrap/cache coordinates and is not sent to the OpenAI-compatible
provider.

Each retained hosted output also carries its original capture timestamp and whether this invocation
came from the provider or the private resume cache. `createdAt` is the run-start timestamp;
the model summary's `responseCapture` range is the provider-output evidence time.

## No-Call Manifest

Create a manifest before spending calls:

```bash
./aleph-bench manifest \
  --data-dir bench/data/v0.2/public/s2 \
  --model hosted:model-a,hosted:model-b,hosted:model-c \
  --out /tmp/aleph-bench-v0.2/hosted-manifest.json
```

Review the manifest for:

- three intended model ids;
- 180 sendable prompts;
- 60 gated explicit reconstruction anchors;
- no prompt text repeated in `gatedPrompts`;
- each hosted model reports five effective reruns;
- `estimatedGenerations` equal to 2,700 logical samples;
- `hostedMaxRetries` equal to the reviewed retry policy (default 2) and
  `estimatedMaxHttpAttempts` equal to 8,100 at that default;
- the canonical dataset id, item count, and digest match the frozen protocol config.

Commit a hosted manifest only if it uses the real model ids for the intended run. Do not commit manifests with placeholder model names.

## Run

Use an ignored local cache so an interrupted hosted run can resume without committing provider outputs:

```bash
./aleph-bench run \
  --data-dir bench/data/v0.2/public/s2 \
  --model hosted:model-a,hosted:model-b,hosted:model-c \
  --seed 0 \
  --cache-dir .cache/aleph-bench/v0.2-hosted \
  --out /tmp/aleph-bench-v0.2/hosted-result.json
```

Track F, public/S2, `tau`, `k`, the rerun count, bootstrap count, dataset identity, and leakage
thresholds are frozen by v0.2. The release CLI exposes no overrides for them and no `--limit` smoke
mode. The cache is runtime state, not evidence. Keep `.cache/` uncommitted.
The current result receipt does not retain provider retry attempts or billing events. Preserve
provider logs alongside any hosted release candidate, and do not report `estimatedGenerations` as an
observed request or cost count.
Use that cache only to resume the same logical run against the same provider deployment. If a mutable
model alias may now resolve to a different backend revision, choose a new cache directory rather than
silently mixing old response receipts into a new evidence date.

## Validation

Run the no-call artifact gate and generated report before changing evidence notes:

```bash
./aleph-bench verify \
  --data-dir bench/data/v0.2/public/s2 \
  --result /tmp/aleph-bench-v0.2/hosted-result.json \
  --manifest /tmp/aleph-bench-v0.2/hosted-manifest.json

./aleph-bench report \
  --result /tmp/aleph-bench-v0.2/hosted-result.json \
  --out /tmp/aleph-bench-v0.2/hosted-report.md
```

Do not run `./aleph-bench audit` or `./aleph-bench bundle` as if either validates hosted v0.2
results. Both commands are read-only checks for immutable v0.1 receipts; they neither replay v0.1 nor
accept a hosted result target. v0.2 verification currently covers the dataset, result, and manifest.

Do not pass the checked-in mock `bench/results/m0-audit.json` or `bench/results/m0-bundle.json` to hosted `verify`; those receipts are tied to `bench/results/m0-first-run.json`.

## Evidence Update

After validation passes, keep the generated artifacts in `/tmp` until a dedicated evidence issue
defines their release path and acceptance gate. Then:

- keep [bench/results/m0-first-run.json](../../bench/results/m0-first-run.json) and
  [docs/benchmark/m0-evidence.md](m0-evidence.md) byte-identical as immutable v0.1 evidence;
- add new result, manifest, report, and evidence-note files under an explicit v0.2 namespace rather
  than reusing any `m0-*` receipt path;
- record the hosted model summary, failure notes, latency/retry observations, and empty-output behavior
  in the new v0.2 evidence note;
- state that hosted rows are `black_box` behavioral evidence only;
- do not add token NLL, logits, bits, or white-box claims.

## Failure Handling

If a provider returns transient failures, keep the cache and rerun the same command after the provider recovers. If a model repeatedly returns empty or malformed content, record the model id and failure mode in the evidence note instead of silently swapping models after seeing scores.

If model ids must change before the first successful full run, regenerate the manifest so the no-call review artifact matches the result.
