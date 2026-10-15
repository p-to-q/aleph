# Engine & benchmark practice review (prior-art backfill)

**Date:** 2026-10-15 · **Scope:** artifact kernel and projection (PR A / PR B), hybrid search scheduler, protected confirmation, and the public benchmark packaging surfaces (Aleph-Bench, Kaggle, Hugging Face). **Why:** the project's original thread requires engineering decisions to follow industry standards — academic benchmark practice, mainstream benchmark repositories, and the Kaggle harness — and the engine/packaging structural decisions were made without a recorded survey. This note backfills that survey.

Evidence tags: **F** = fact observed in a primary source (fetched 2026-10-15; URL in Sources); **I** = interpretation for Aleph; **U** = open question. Nothing here changes science claims; it changes structure, vocabulary, and release practice.

## 1. Attestation and provenance practice (in-toto, SLSA)

**F.** The in-toto *Statement* v1.0 is the industry-standard middle layer for attestations:

```jsonc
{ "_type": "https://in-toto.io/Statement/v1",
  "subject": [ { "name": "<NAME>", "digest": { "<ALGORITHM>": "<HEX_VALUE>" } } ],
  "predicateType": "<URI>", "predicate": { ... } }
```

Subject artifacts are matched **purely by digest** (`name` is optional disambiguation; digest sets may carry several algorithms, and producers/consumers must agree on acceptable ones). **F.** SLSA provenance is a predicate on this layer: `buildDefinition` (build type, external parameters, resolved dependencies) plus `runDetails` (builder identity, invocation metadata, byproducts) — the ecosystem separates "what was built / how it was run" (predicate) from "which artifact" (subject), and binds them by digest.

**I.** Aleph's run bundle already has this shape: the bundle is the subject (`bundleDigest`); `aleph-run-projection.json` (projection + per-leaf source map + policy + omitted candidates) is the predicate; `artifactRef` is the typed pointer to the pair. The mapping is structural, not incidental.

**Recommendations.** (1) Record this mapping in the engine docs (short "relation to attestation practice" paragraph; improves reviewer orientation at near-zero cost). (2) Optional follow-up: name the fields closer to the standard vocabulary in a projection-record `0.2.0` (`subject` + digest set) — only if a second consumer ever reads it. (3) Keep "matched by digest only" (already true) and keep the digest algorithm explicit (`sha256:` prefix is our spelling of `{ALGORITHM: HEX}`).

## 2. Canonical serialization practice (RFC 8785 JCS)

**F.** RFC 8785 (JSON Canonicalization Scheme) is what the ecosystem signs and hashes: W3C Verifiable Credential Data Integrity converts inputs with JCS; SCITT profiles declare canonicalization explicitly; A2A agent cards use JCS before JWS. JCS rules: ECMAScript `JSON.stringify` primitives; object properties sorted by **UTF-16 code units**; **no Unicode normalization**; numbers as IEEE-754 doubles with ECMAScript shortest-round-trip formatting; numbers outside the double range *recommended to be represented as strings* (Appendix D).

**F — measured divergences between `aleph-canonical/0.1.0` and JCS** (reproduced on this tree, 2026-10-15):

| Input | Aleph canonical | JCS / ECMAScript |
|---|---|---|
| keys `"\uE000"`, `"\U00010000"` | `\uE000` sorts first (code-point order) | `\U00010000` sorts first (UTF-16 order: `D800 < E000`) |
| float `1e-7` | `1e-07` (Python repr) | `1e-7` |
| int `9007199254740993` | exact integer | rounds to `...992`; string-recommended |
| text | NFC-normalized before hashing | serialized as-is (normalization out of scope) |

**I.** Every divergence is deliberate: NFC makes digests text-fidelity-based (composed and decomposed spellings of one grapheme must collide, or the same prompt would get two identities); code-point order and exact integers are what Python can guarantee; fail-closed types are stricter than JCS. For a self-contained system whose verifier is the same Python profile, this is sound. It is **not** interoperable with JCS-based tooling, and the TypeScript side could not re-derive our digests without reimplementing the profile. That is acceptable *today* because only the Python verifier computes digests — but it is currently an unrecorded dependency.

**Recommendations.** (1) Write the profile down (proposed decision record): name (`aleph-canonical/0.1.0`), rules, and the intentional divergence list above. (2) Add **conformance vectors** (fixed fixtures with expected canonical bytes/digests) so the profile cannot drift silently — cheapest high-value item. (3) Keep JCS interoperability as an explicit open question (U): adopt JCS in TS, add a Python `jcs` mode, or declare internal-only — decide when a cross-language consumer exists.

**Update (2026-10-15, ADR 0006).** This recommendation was recorded before the follow-up differential audit quantified the divergence (1710 of 100,000 sampled doubles, 1.71 %, in three mundane classes, plus the key-order and integer-precision cases). The engine then adopted the JCS text form as `aleph-canonical/0.2.0` (`docs/decisions/0006-canonical-json-jcs-alignment.md`): recommendations (1) and (2) are fulfilled — decision record plus fixed conformance vectors in `search/engine/tests/test_canonical_vectors.py` — and (3) is resolved for already-NFC text; NFC pre-normalization remains the single documented extension. See the ADR section "Relation to the practice review".

## 3. Search and racing practice (NSGA-II, Hyperband/ASHA, prompt optimizers)

**F.** Multi-objective selection practice keeps an explicit non-dominated archive; scalarized scores (weighted sums) are known to miss concave regions, so selection scores *drive* search while the reported front stays Pareto-defined (NSGA-II lineage: non-dominated sorting + crowding distance for diversity; Deb et al., IEEE TEC 2002). Racing practice: Hyperband / ASHA promote candidates through resource rungs (successive halving with factor η), asynchronously under parallel budgets (Li et al. 2017/2018).

**F.** In the same problem family, DSPy's MIPROv2 searches instruction+few-shot combinations with a surrogate (Bayesian/TPE) over grounded proposals, with light/medium/heavy budget presets and minibatch evaluation; GEPA uses reflective evolution with Pareto signals (already cited in our prior-art table); APE/PromptWizard/TextGrad are the broader family.

**I.** `hybrid_pareto.py` already separates the two roles: the declared acquisition (operator weights, exploration share, exploit top-k) only schedules; what is projected is the declared-metric frontier; freeze/confirmation are phase-locked. That is the frontier-first discipline the literature recommends, in a more auditable form (everything declared and replayed).

**Recommendations (non-blocking; v1 candidates, not v0).** (1) Add a "relation to prior practice" paragraph to the scheduler module docs: declared frontier ≈ non-dominated archive; racing rules ≈ ASHA-style promotion; proposal operators + schedule ≈ optimizer family (MIPROv2/GEPA). (2) Backlog: crowding-distance-style parent rule; a staged successive-halving racing rule; a surrogate-guided proposal family — all deterministic and receipted.

## 4. Confirmation and pre-registration practice

**F.** Reusing a holdout for repeated selection inflates overfitting; the reusable-holdout line (Dwork et al., *Science* 2015; NeurIPS 2015) formalizes controlled reuse and its cost. Pre-registration for predictive modeling (arXiv 2311.18807; 2025 opinion piece in a clinical/ML venue) formalizes register-then-confirm with a frozen analysis plan and reporting inconclusive outcomes.

**I.** Our protected confirmation is a single-use locked holdout with a pre-registered decision rule: fresh context digest ≠ discovery; fresh seed and request ids; only the frozen shortlist; thresholds declared in `ConfirmationSpec` before any event; a first-class `indeterminate` outcome. Compared with common published practice this is *stronger* than average and is the right shape for a benchmark-science paper.

**Recommendations.** (1) Cite the lineage in the module docs (one paragraph: holdout reuse; pre-registration; why `indeterminate` is required). (2) Keep the one-shot rule (no confirmation reuse across runs); if that ever changes, write the multiple-comparison policy first.

## 5. Benchmark harness and packaging practice (lm-eval, Kaggle Benchmarks, BetterBench, Croissant)

**F — lm-evaluation-harness** (mainstream open harness): `--output_path` writes `results.json`; `--log_samples` stores per-sample records; sample caches are keyed by (model, task) (rank-dependent); results and samples are pushed to the Hugging Face Hub as artifacts (`--hf_hub_log_args`); W&B logs `results.json` as a versioned artifact. Reproduction value comes from config + samples + pinned versions, not from the scalar.

**F — Kaggle Benchmarks** (the Kaggle harness, current product): tasks are Python functions decorated with `@kbench.task` running against an LLM; assertions are built-in/custom/model-judge (`assess_response_with_judge`); runs happen via the `kaggle benchmarks` CLI (`push`, `run`, `status`, `log`, `download`, `publish`); model access uses short-lived model-proxy credentials; results (and source notebooks) are downloadable; publishing makes a task public. This is the concrete surface for "run Aleph on Kaggle" beyond a dataset upload.

**F — BetterBench** (NeurIPS 2024 Datasets & Benchmarks): assessment criteria are *design, implementation, documentation, maintenance*; it ships a minimum-QA checklist (Appendix I) whose items include documenting test tasks and rationale, assumptions, limitations, evaluation metric, license, contact person, and maintenance/feedback channels; it finds most benchmarks neither report statistical significance nor support easy replication; contamination/gamification mitigations include globally unique identifiers or encrypting evaluation instances.

**F — Croissant** (MLCommons): dataset metadata format adopted by Kaggle and Hugging Face for dataset ingestion/discovery.

**I — implications for Aleph-Bench.** (1) A released Aleph-Bench result should always ship: full config, versions, seeds, digests, and per-sample outputs (our bundle already gives this; the *release artifact* must expose it in the harness-conventional shape). (2) Adopt a minimum-QA checklist for Aleph-Bench releases (start from BetterBench's categories; add the statistical-significance requirement). (3) Publish Croissant metadata alongside dataset releases on HF/Kaggle. (4) `kbench` interop is an un-designed gap: wrap an Aleph coordinate as a `@kbench.task` running assertions (discovery/projection stay with us; Kaggle runs the evaluation) — needs a design slice before any Kaggle-hosted bench claims.

## 6. Effect on our structure (summary)

| Area | Current structure | Research finding | Action | Priority |
|---|---|---|---|---|
| Attestation vocabulary | custom bundle + projection | structurally compatible with in-toto Statement / SLSA | doc mapping; optional v0.2 naming | low |
| Canonical profile | `aleph-canonical/0.1.0` | diverges from JCS by design; currently undeclared | decision record + conformance vectors; interop = open question | **medium** |
| Search scheduler | `hybrid-pareto-v0` | frontier-first matches practice | docs paragraph; v1 options backlogged | low |
| Confirmation | protected confirmation | ≈ pre-registered locked holdout (stronger than average) | docs citation; keep one-shot | low |
| Bench packaging | ad-hoc | lm-eval / kbench / BetterBench conventions | QA checklist + results+samples release + Croissant; kbench interop design | **high** |
| Process | research notes exist | no gate tied to structural changes | add structural-decision gate to research-process.md | **now** |

**Update (2026-10-15, ADR 0006).** The canonical-profile row is superseded: the engine adopted the JCS-aligned text form; see the update note in section 2.

## 7. What does not change

- No re-architecture of PR A/B modules; no new dependencies (in-toto/SLSA/JCS are references, not imports).
- No JCS switch now; our profile stays, but becomes documented and pinned by vectors. *(Update, same day: superseded — the engine adopted the JCS text form; see the update note in section 2.)*
- **I** — PR B export slice: reviewed against these practices; the subject/predicate split, complete per-leaf source map, and fail-closed derivation match what the ecosystem expects in spirit. **No blocking changes**; optional vocabulary follow-up only.

## 8. Remaining backfill backlog (U)

1. Persistence-layer choice (open since the engine plan): survey event-store/JSONL/SQLite practice when picked.
   *Update (2026-10-15, same day): surveyed — see
   [`persistence-layer-practice-review.md`](persistence-layer-practice-review.md). Disposition: run
   bundles stay the system of record; a strict, fail-closed import surface is the next step;
   a database stays deferred with recorded triggers; no new dependency.*
2. `kbench` interop design slice (§5).
3. Statistical-significance reporting for Aleph-Bench scores (which tests, sample sizes, aggregation).
4. Cross-language digest verification (TS/third parties) → JCS-compat decision.
   *Update (2026-10-15, same day): implemented — `scripts/aleph-canonical.mjs`
   recomputes the canonical bytes and digests in JavaScript and
   `scripts/check-canonical-parity.mjs` (wired into `npm test`) differentials
   against the Python engine; see the ADR 0006 follow-up.*
5. Hosted-canary practice (#107): Kaggle model-proxy quotas/pricing — before the canary unfreezes.

## Sources (fetched 2026-10-15)

*Update (2026-10-15): added DOI/arXiv/PMID identifiers to the search-lineage, optimizer, and reusable-holdout entries; identifiers checked against Crossref/arXiv/PubMed the same day.*

- in-toto Statement v1.0 — https://github.com/in-toto/attestation/blob/9294e52190339981e15ff4a8196c44b24dd95fbc/spec/v1.0/statement.md
- SLSA v1.0 Provenance — https://slsa.dev/spec/v1.0/provenance
- RFC 8785 JCS — https://www.rfc-editor.org/rfc/rfc8785.txt ; W3C VC Data Integrity (JCS usage) — https://www.w3.org/TR/vc-data-integrity/ ; A2A agent cards (JCS + JWS) — https://github.com/a2aproject/A2A
- NSGA-II — Deb, Pratap, Agarwal, Meyarivan, IEEE TEC 6(2), 2002; DOI 10.1109/4235.996017
- Hyperband — Li et al., JMLR 18(153), 2018, arXiv:1603.06560; ASHA — Li et al., MLSys 2020, arXiv:1810.05934
- DSPy MIPROv2 — https://dspy.ai/api/optimizers/MIPROv2/ ; paper: arXiv:2406.11695
- Dwork et al., "The reusable holdout", Science 349(6248), 2015; DOI 10.1126/science.aaa9375; PMID 26250683; "Generalization in Adaptive Data Analysis and Holdout Reuse", NeurIPS 2015
- "Pre-registration for Predictive Modeling" — arXiv:2311.18807
- lm-evaluation-harness — https://github.com/EleutherAI/lm-evaluation-harness (README, fetched 2026-10-15)
- Kaggle Benchmarks — https://github.com/Kaggle/kaggle-benchmarks (user guide); CLI: https://github.com/Kaggle/kaggle-cli/blob/main/docs/benchmarks.md ; announcement: https://www.kaggle.com/discussions/product-announcements/667898
- BetterBench — https://arxiv.org/abs/2411.12990 (NeurIPS 2024 D&B); https://betterbench.stanford.edu
- Croissant — https://mlcommons.org/working-groups/data/croissant/ ; Croissant 1.1 — https://theodi.org/news-and-events/blog/croissant-11/
