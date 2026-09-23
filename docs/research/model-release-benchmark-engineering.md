# Model-release benchmark engineering survey

Status: research record

Related issues: [#38](https://github.com/p-to-q/aleph/issues/38),
[#55](https://github.com/p-to-q/aleph/issues/55), and
[#59](https://github.com/p-to-q/aleph/issues/59)

Last reviewed: 2026-09-24

## Why this survey exists

Aleph does not need another list of famous benchmark names. It needs to understand why a result from
a maintained benchmark is legible, reproducible, comparable, and debuggable after its original
runner, platform, or model alias has changed.

This review separates two categories that are often conflated:

1. **Model-release benchmarks** define the scientific task and score reported in model cards and
   technical reports.
2. **Evaluation harnesses and hosted platforms** define how requests are executed, isolated,
   resumed, retained, and published.

The source set uses official repositories, papers, documentation, and first-party model reports.
The goal is not to import a large framework. It is to identify the smallest durable contracts Aleph
must implement.

## What a modern model score actually identifies

A reproducible score is not `benchmark + scalar`. The practical identity is:

```text
dataset subset and release
× prompt / few-shot / chain-of-thought policy
× model snapshot and provider handler
× reasoning effort, tools, scaffold, and chat template
× decoding, output cap, attempts, timeout, and seed policy
× judge, classifier, baseline, or deterministic scorer revision
× harness commit, runtime profile, and exclusions
× aggregation and uncertainty method
```

The official DeepSeek-R1 tables, for example, distinguish exact match, prompt-strict, pass@1,
judge-backed Arena results, generation length, sampling, and repeated responses. OpenAI and
Anthropic reports also qualify SWE-bench results by subset, scaffold, tool access, reasoning mode,
and maximum steps. Aleph must preserve the same dimensions even though its scorer is deterministic.

## Berkeley / BAIR / LMSYS lineage

### Berkeley Function-Calling Leaderboard

[BFCL](https://github.com/ShishirPatil/gorilla/tree/main/berkeley-function-call-leaderboard)
is the strongest direct engineering example for Aleph.

- The benchmark has explicit generations: v1 single-turn AST evaluation; v2 enterprise and live
  data; v3 multi-turn and multi-step execution; v4 agentic web search, memory, irrelevance, and
  format sensitivity.
- The official
  [changelog](https://github.com/ShishirPatil/gorilla/blob/main/berkeley-function-call-leaderboard/CHANGELOG.md)
  records ground-truth repairs, provider-handler fixes, model additions and removals, result-layout
  migrations, and scoring-weight changes. A changed score formula is not hidden as maintenance.
- Raw model results and scores are separate artifacts. Logs retain user, assistant, tool and state
  messages, transformed input, raw response, decode success, empty/failure states, and forced exits.
- Provider-specific handlers and pinned model ids are part of the result identity. The harness
  supports hosted APIs, OpenAI-compatible endpoints, local vLLM/SGLang, and offline evaluation.
- Unevaluated categories are represented as `N/A`, not as a model-quality zero.

Aleph should borrow BFCL's lifecycle discipline: provider handlers are versioned experimental
apparatus; raw, normalized, parsed, and scored layers remain distinct; missing is never zero; and
every dataset or formula correction has a visible compatibility consequence.

### Chatbot Arena

[LMArena](https://github.com/lmarena) evolved from Berkeley LMSYS and the Sky Computing Lab
community. Its public method moved from Elo presentation toward a
[Bradley-Terry model with bootstrap uncertainty](https://www.lmsys.org/blog/2023-12-07-leaderboard/).

Arena is a live measurement system rather than a deterministic static benchmark. Anonymous random
pairing, the voting population, time window, model sampling policy, ties, category slices, style
control, alias changes, and provider model drift all affect a snapshot. Aleph should not copy its
subjective scorer, but should copy its explicit snapshot dates, confidence intervals, retirement
policy, and disclosure that closed model aliases can move.

### Arena-Hard-Auto

[Arena-Hard-Auto](https://github.com/lmarena/arena-hard-auto) turns difficult Arena prompts into a
versioned automatic benchmark. The score identity includes the exact prompt set, judge snapshot,
judge prompt, baseline/reference responses, style control, and Bradley-Terry aggregation. The open
prompt set also creates a gaming risk acknowledged by the maintainers.

For Aleph, the important lesson is that every hidden experimental variable must become a field. A
deterministic scorer reduces judge drift, but does not remove prompt, model-handler, runtime, or
aggregation drift.

## Model-release benchmark matrix

### Knowledge and reasoning

| Benchmark | Maintainer and lifecycle | Technical contract | Reproducibility lesson |
|---|---|---|---|
| [MMLU](https://github.com/hendrycks/test) | Hendrycks et al.; static, MIT | 57 subjects, four choices; canonical script uses five-shot prompts and single-token choice log-probabilities, then weighted mean accuracy. | Generative letter extraction, choice log-probability, zero-shot, and five-shot results are different protocols. Public static data is now saturated and contamination-prone. |
| [MMLU-Pro](https://github.com/TIGER-AI-Lab/MMLU-Pro) | TIGER-Lab; versioned, Apache-2.0 | More options, 14 domains, chain-of-thought generation followed by answer extraction. Official runners support API and local models. | Prompt, CoT policy, answer extractor, and options order are score inputs. `retry_wrong` changes the experiment and must be disabled or declared. |
| [GPQA](https://github.com/idavidrein/gpqa) | GPQA authors; controlled static data, MIT | Graduate-level multiple choice; Diamond is the hardest curated subset. Choices are seed-shuffled; accuracy/pass@1 is common. | Record subset, data-access revision, shuffle seed, retrieval/tool access, and CoT/few-shot policy. Canary and controlled data access are part of contamination defense. |
| [BIG-Bench Hard](https://github.com/google/BIG-bench/tree/main/bigbench/benchmark_tasks) | Google BIG-bench; static, Apache-2.0 | 23 heterogeneous tasks with task-specific normalization or scorers, commonly three-shot CoT and macro aggregation. | A single aggregate hides task heterogeneity. Task list, prompt, normalization, and aggregation must be frozen. |
| [LiveBench](https://github.com/LiveBench/LiveBench) | LiveBench team; dated releases, Apache-2.0 | Objective ground-truth tasks across six categories; release selection, resume, failure retry, and agentic Docker paths. | `latest` may include non-public material. Reproducibility requires an immutable dated release; platform failures should not be silently counted as ability errors. |

### Mathematics

| Benchmark | Maintainer and lifecycle | Technical contract | Reproducibility lesson |
|---|---|---|---|
| [GSM8K](https://github.com/openai/grade-school-math) | OpenAI; archived static repo, MIT | JSONL grade-school problems; final answer follows `####`; exact numeric extraction. | CoT, majority vote, tool use, and numeric extraction change results. It remains a compatibility baseline, not a strong fresh frontier headline. |
| [MATH](https://github.com/hendrycks/math) / MATH-500 | Hendrycks et al.; static, MIT | Competition mathematics with LaTeX/symbolic answers; full MATH and MATH-500 are distinct sets. | Exact-string and symbolic-equivalence graders are not interchangeable. Record subset, grader, tools, and response extractor. |
| [FrontierMath](https://epoch.ai/frontiermath/the-benchmark) | Epoch AI; tiered/date releases with private holdout | Research-level problems with strict answer verification, public samples and controlled evaluation. | Access tier, release date, tools, pass@k, and evaluator relationship must be disclosed. Controlled data can improve contamination resistance but weakens independent replication. |

### Code and agents

| Benchmark | Maintainer and lifecycle | Technical contract | Reproducibility lesson |
|---|---|---|---|
| [HumanEval](https://github.com/openai/human-eval) | OpenAI; static, MIT | 164 Python completion tasks; generated programs execute unit tests; pass@k. | Execution needs a sandbox, timeout, sample count, temperature, and explicit opt-in. Public solutions and contamination limit frontier meaning. |
| [MBPP](https://github.com/google-research/google-research/tree/master/mbpp) | Google Research; static, Apache-2.0 | Roughly 1,000 descriptions with reference solutions and tests; includes a hand-verified subset and fixed few-shot ids. | Subset, examples, sandbox, dependency set, and timeout are protocol inputs. |
| [SWE-bench Verified](https://github.com/SWE-bench/SWE-bench) | Princeton and community; actively maintained, MIT | 500 human-validated GitHub issues; per-instance repository/test Docker image; resolved rate; saved test output supports re-grading. | Architecture/OS, image digest, scaffold, exclusions, and cache identity matter. Different official model reports have used 477- and 500-instance denominators. |
| [LiveCodeBench](https://github.com/LiveCodeBench/LiveCodeBench) | Berkeley/community; rolling date windows and releases, MIT | Continuously collected coding problems; generation, execution, test-output prediction, and repair; model-family prompt registry. | Release/date window, prompt adapter, checker revision, process isolation, timeout, sample count, and errata determine comparability. |

### Instruction following, tools, multimodal, multilingual, and safety

| Benchmark | Maintainer and lifecycle | Technical contract | Reproducibility lesson |
|---|---|---|---|
| [IFEval](https://github.com/google-research/google-research/tree/master/instruction_following_eval) | Google Research; static, Apache-2.0 | Deterministic instruction checkers with instruction- and prompt-level metrics in strict and loose variants. | `prompt strict`, `instruction loose`, and other columns are different scores. Loose normalization must never be described as strict compliance. |
| [MMMU / MMMU-Pro](https://github.com/MMMU-Benchmark/MMMU) | MMMU team; evolving, Apache-2.0 | Multi-discipline image+text multiple choice/open questions; Pro and vision-only variants change answerability and choice structure. | Standard, vision-only, and Pro; image preprocessing; test access; tools; and server lifecycle all belong in result identity. |
| [BFCL](https://github.com/ShishirPatil/gorilla/tree/main/berkeley-function-call-leaderboard) | UC Berkeley Gorilla; frequent releases and errata, Apache-2.0 | AST, execution, multi-turn, multi-step, irrelevance, and agentic category scorers with explicit weighted aggregation. | Tool schema, backend state, provider handler, FC/non-FC model mode, result parser, and scoring weights must be pinned. |
| [Chatbot Arena](https://github.com/lmarena) | Berkeley/LMSYS/LMArena/Sky; continuously online | Anonymous pairwise human preference; Bradley-Terry, ties, bootstrap intervals, categories and style control. | A snapshot requires time cutoff, sampling population, aliases, model revision policy, and statistical method. It is not an exact offline replay target. |
| [Arena-Hard-Auto](https://github.com/lmarena/arena-hard-auto) | LMArena; versioned, Apache-2.0 | Hard/creative prompt sets; LLM judge or ensemble; reference/baseline; style control; Bradley-Terry and uncertainty. | Judge, prompt, baseline, reference responses, dataset version, and aggregation are inseparable from the scalar. |
| [Belebele](https://github.com/facebookresearch/belebele) | Meta AI; static, CC-BY-SA-4.0 data | 122 parallel language variants, 900 passages per language, four-choice reading comprehension. | Language/script, translated versus English instructions, and per-artifact licenses must be retained. Cross-language token length is not directly comparable without a declared measurement unit. |
| [HarmBench](https://github.com/centerforaisafety/HarmBench) | Center for AI Safety and collaborators; maintained pipeline, MIT | Attack generation, merge, target completion, and classifier evaluation are separate stages; local, Ray, and Slurm execution. | Attack set, target system prompt, behavior taxonomy, classifier checkpoint/threshold, and failure stage must be versioned independently. |
| [AIR-Bench 2024](https://github.com/stanford-crfm/air-bench-2024) | Stanford CRFM; dated safety release, Apache-2.0 | Thousands of prompts over hundreds of risk categories with judge-backed ordinal scoring. | Judge snapshot and prompt are scorer dependencies; safety should retain category results rather than only a global scalar. |

## Evaluation harness and platform matrix

| System | Architecture | Portability and recovery | Result/evidence model | Aleph lesson |
|---|---|---|---|---|
| [HELM](https://github.com/stanford-crfm/helm) | `RunSpec → Scenario → Adapter → Request → Executor → Metric → Stat` | API/local backends, request cache and error flags; lifecycle now demonstrates the need for maintenance governance. | Run spec, scenario state, per-instance and aggregate stats. | Borrow serializable state/controller separation, not the entire dependency graph. |
| [lm-evaluation-harness](https://github.com/EleutherAI/lm-evaluation-harness) | YAML task/group plus Python utilities and backend registry | Python optional extras for HF/vLLM/API; response cache and task integrity tests. | Task config/version, seeds, hashes, results and raw samples; HF/W&B adapters. | Borrow small declarative task specs and raw sample hashes; do not make topology-sensitive cache authoritative. |
| [SWE-bench harness](https://github.com/SWE-bench/SWE-bench) | Instance/prediction/image/test/scorer separation | Per-instance Docker; saved logs; resume by run id/instance. | Prediction, patch, report, test output, trajectory. | Preserve re-scorable raw evidence; key cache by content, not a human run name. |
| [Inspect AI](https://inspect.aisi.org.uk/) | Task, dataset, solver, tool, scorer, metric | Local/cloud sandbox, sample retry, crash recovery, failure thresholds and checkpointing. | Versioned `.eval` log with EvalSpec, samples, events, results, stats and error. | Best reference for typed failure, sample ledger and resume-from-log semantics. |
| [OpenCompass](https://github.com/open-compass/opencompass) | Model/dataset/evaluator/summarizer config; partition then runner | Local, Slurm and cloud; inference/scoring separation; reuse and evaluation-only rerun. | Effective config, logs, predictions, results and summary. | Snapshot the effective config and make runtime capabilities explicit. |
| [OpenAI Evals](https://github.com/openai/evals) | YAML registry, JSONL data, templates/custom evals | CompletionFn abstraction; append-style event log; coarse eval-set resume. | Versioned eval id and event stream. | Borrow explicit split/version naming and event logs; Aleph needs finer sample recovery. |
| [Hugging Face Eval Results](https://huggingface.co/docs/hub/en/eval-results) | Dataset `eval.yaml`; model `.eval_results/*.yaml` | Publication/index layer, not an execution authority; allow-listed beta. | Dataset revision, task id, value, source, notes and verification state. | Always require exact revision and source; keep Aleph-owned result records because community PRs are not permanent authority. |
| [Kaggle Benchmarks](https://github.com/Kaggle/kaggle-cli/blob/main/docs/benchmarks.md) | Python `@task`; hosted Model Proxy; numeric main result drives leaderboard | Managed Python runtime; push/run/status/log/download; Task/run-level recovery, not sample-level recovery. | Platform Task version, model run state, source/log/output archive and scalar. | Use Kaggle for hosted execution, but add exact-version scheduling, sample ledger, offline replay, and immutable external receipts. |

## Current Aleph gap matrix

| Priority | Current condition | Risk | Required change |
|---|---|---|---|
| P0 | No current-protocol public Kaggle numeric run with complete real-model evidence. | Missing/error/legacy zero rows can be mistaken for model quality. | Make incomplete, failed, withdrawn, and not-run `N/A`; publish a scalar only after complete coverage and replay. |
| P0 | Protocol, dataset, scorer, call plan, runtime, Task, model and surface ids are not bound by one frozen artifact. | A score cannot be reconstructed after any one surface changes. | Add an immutable semantic release manifest and append-only run/result records. |
| P0 | Capture, diagnostic, replay, Task, and publication artifacts have related but fragmented states. | Operators see “no score” without knowing dispatch, platform, evidence, or scorer state. | Define typed attempt/failure/coverage and lifecycle state machines. |
| P0 | v0.2 requires Python 3.13/UCD 15.1 while current Kaggle uses Python 3.11. | The target runtime cannot legally score the reference protocol. | Keep v0.2 immutable; prove a separately identified portable profile on 3.11–3.13 before numeric promotion. |
| P1 | Model/provider mapping is partly inferred from suffixes and mutable aliases. | A row label can disagree with the runtime actor. | Add a versioned model registry retaining requested canonical slug, internal version id, proxy slug, runtime-observed identity, mapping rule and date. |
| P1 | The benchmark subsystem is not yet an installable, profile-based package. | Contributors cannot reproduce clean-wheel behavior or select minimal platform dependencies. | Add `pyproject.toml` only when the portable profile stabilizes; use minimal core plus `kaggle`, `hf`, and `dev` extras. |
| P1 | CI proves strong scorer behavior but not the final support matrix. | macOS success can be mistaken for Kaggle Linux evidence. | Test clean installs on Linux/macOS and Python 3.11/3.12/3.13; retain platform and dependency digests. |
| P1 | GitHub, Kaggle and HF descriptions can drift by hand. | Public pages can name different current releases or limitations. | Generate all public note fragments from the release manifest and verify them with daily readback. |
| P1 | Public S2 is small and fully visible. | Construct, discrimination, multilingual and contamination claims remain weak. | Keep the unique elicitation construct; later add held-out/fresh strata and sensitivity studies without silently changing the current denominator. |
| P2 | Public docs expose M0, Track F, S2, capture, diagnostic and internal stage vocabulary. | The project appears more complicated and less mature than the stable user path. | Public entry uses `Aleph Bench` plus one sentence, one reproduce command, one run command, one result link and one limitations section; internal names move to methodology. |

## Design conclusion

Aleph should combine four proven patterns:

1. HELM/OpenCompass separation of specification, execution, scoring and aggregation.
2. Inspect/SWE-bench typed sample evidence, crash recovery and offline re-grading.
3. LiveBench/OpenAI Evals/BFCL explicit release, errata and comparability boundaries.
4. Kaggle and Hugging Face as execution/distribution adapters under a Git-owned semantic release.

It should explicitly reject scalar-only evidence, human run-name cache keys, silent paid retries,
infrastructure failures counted as zero, mutable `latest` data compared to old scores, unpinned
judges/classifiers, and three manually maintained public score copies.
