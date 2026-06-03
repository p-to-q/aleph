# Research Synthesis: What a Credible Benchmark Requires

This is the research phase. It surveys how the strongest and most community-driven LLM benchmarks are
designed, evaluated, hardened against contamination, and hosted — then distills a **minimum bar** and
the moves that make a research community comfortable enough to adopt a benchmark and impressed enough
to cite it. Every claim is sourced at the end.

It answers the two questions that frame the project:

- **(a) How do we make the benchmark comprehensive?** → §1 construct validity, §2 dataset & coverage,
  §3 contamination, §5 the minimum bar.
- **(b) What technical work makes the community comfortable and persuades them?** → §4 hosting &
  adoption, §6 the "trust surface", §7 what to copy from each exemplar.

## 1. The methodological backbone: construct validity

The most important recent result for us is a 29-reviewer systematic review of **445 LLM benchmarks**
from top NLP/ML venues, *Measuring what Matters: Construct Validity in LLM Benchmarks*. Construct
validity = "having measures that represent what matters to the phenomenon." Its audit of the field is
a catalogue of exactly the traps a new benchmark must avoid:

- **47.8%** of benchmarks use *contested* phenomenon definitions (no consensus on what is being
  measured).
- **27%** rely on *convenience sampling* of whatever datasets were lying around.
- **21.1%** confound the construct with a *format requirement* that itself impedes performance.
- Only **16%** perform any statistical testing; only **53.4%** present *any* construct-validity
  evidence.

It gives **eight recommendations**, which we adopt as the benchmark's design checklist:

1. **Define the phenomenon** — precise operational definition, scope, sub-components.
2. **Measure only the phenomenon** — control confounds and auxiliary abilities.
3. **Construct representative datasets** — principled sampling, not convenience.
4. **Acknowledge limits of reused datasets** — document adaptations.
5. **Prepare for contamination** — detection tests + held-out sets.
6. **Use statistics** — uncertainty estimates, justified sample sizes.
7. **Conduct error analysis** — investigate failure modes and scoring bias.
8. **Justify construct validity** — connect tasks and metrics to the definition and to real-world use.

The single most actionable consequence for ALEPH-Bench: **our headline metric must not be an
arbitrary weighted sum** (recommendations 2 and 8). The current
`fit·0.45 + stability·0.25 + compression·0.2 − leakage·0.1` is precisely the failure mode the review
flags. We replace it with a parameter-free rate–distortion functional and report sub-scores
separately (§02-design-spec).

## 2. Dataset design and coverage — lessons from the exemplars

**BIG-bench** is the reference model for *community-driven* coverage: 200+ tasks contributed by 400+
authors via GitHub pull requests, each task reviewed by peers before merge. Lesson: a benchmark
becomes "the community's" when *contributing an item is a first-class, documented workflow*, not a
private maintainer act.

**HELM (Stanford)** is the reference model for *comprehensiveness as a matrix*: it evaluates across a
grid of *scenarios × metrics*, deliberately reporting many metrics (accuracy, calibration, robustness,
fairness, efficiency) rather than collapsing to one. Lesson: comprehensiveness is a **declared
taxonomy** (which abilities, which conditions) plus **multi-metric reporting**, not a big
undifferentiated pile of questions.

**lm-evaluation-harness (EleutherAI)** is the reference model for *standardization*: 60+ academic
benchmarks and 200+ tasks behind one interface, versioned tasks, centralized prompt templates, and
explicit uncertainty reporting. It is the backend of the HF Open LLM Leaderboard and is used by
NVIDIA, Cohere, BigScience, Mosaic, Anthropic and others. Lesson: **the harness, not the dataset, is
what gets adopted.** A dataset nobody can run consistently dies; a task that drops into the standard
harness is run by everyone.

For ALEPH-Bench this means coverage is a *stratified taxonomy* (canonical recall, compositional,
functional/behavioral, structured, multilingual) with per-stratum reporting, and the corpus must be
contributable by PR. The five canonical texts in `search/targets.py` are a fine demo seed but a poor
benchmark on their own: they measure verbatim recall of famous English passages, which is a
memorization confound (recommendation 2), is small (recommendation 3/6), and is maximally
contamination-prone (recommendation 5).

## 3. Contamination — the credibility battleground

Contamination is now *the* axis on which benchmarks live or die, and the field has converged on a
layered defense. The cautionary tale: OpenAI's audit found every frontier model could reproduce
verbatim gold patches or problem specifics for some **SWE-bench Verified** tasks; top models score
~81% on Verified but ~46% on the contamination-controlled **SWE-bench Pro**. The 35-point gap *is* the
contamination.

The defenses, strongest first:

- **Private held-out split.** SWE-bench Pro's private set is 276 instances from proprietary codebases
  that are *legally inaccessible* to model trainers — contamination is structurally impossible, not
  merely discouraged. This is the gold standard and the most persuasive single thing a benchmark can
  have.
- **Time-gating / rolling refresh.** **LiveCodeBench** ingests new competition problems continuously
  and filters by each model's training cutoff, so models are only scored on problems published after
  they were trained. **LiveBench** releases fresh questions monthly. Lesson: a *fresh* split defeats
  memorization even for public data.
- **Canary strings.** BIG-bench embeds a canary GUID so trainers can filter the data and researchers
  can probe leakage ("can the model emit the canary?"). Necessary but *not sufficient*: the pre-RLHF
  GPT-4-base can emit the BIG-bench canary, proving the data leaked anyway. Canaries detect and
  signal; they do not prevent.
- **Strong copyleft licensing** as a deterrent to inclusion in training corpora (SWE-bench Pro uses
  GPL on its OSS subsets).

ALEPH-Bench has a structural advantage here that most benchmarks lack: large parts of the corpus
(compositional, structured, functional targets) can be **freshly generated after a cutoff**, so the
*targets themselves* are non-memorizable. We still adopt all four layers (§02-design-spec §6).

## 4. Hosting and adoption — where to launch

Three homes matter, and the right answer is to use all three rather than choose.

**Kaggle Community Benchmarks** — launched 2025 with Google, and aimed at exactly this use case:
"design, run and share custom benchmarks for evaluating AI models," turning task suites into public
leaderboards with reproducible, auditable results. The SDK is small and a good fit for us:

```python
@kbench.task(name="elicit_borges_8tok")
def task(llm, target: str, ladder_rung: str):
    out = llm.prompt(ladder_rung)          # model under test runs the short prompt
    return kbench.assertions.assert_...    # fidelity check → score
# tasks grouped into a Benchmark → leaderboard across frontier models
```

It supports structured/multimodal I/O, tool use, a built-in Python interpreter, and `DataFrame`-scale
runs. Critically, the **Benchmarks Resource Grant Program** gives selected benchmarks increased
compute quota and *free access to leading models* (OpenAI, Google, Anthropic, Grok, Qwen, DeepSeek) —
which solves the single biggest practical problem of a model-comparison benchmark: paying for every
model's API. *Applying for this grant should be an explicit milestone.*

**lm-evaluation-harness** — implement ALEPH-Bench as a task here and every lab that already runs
lm-eval can run it with one config line; it is also the path of least resistance onto the HF Open LLM
Leaderboard surface. This is the adoption multiplier.

**Hugging Face** — host the dataset (with a **Croissant** machine-readable metadata file, now an
expectation for serious datasets and required for NeurIPS Datasets & Benchmarks submissions) and the
leaderboard as a Gradio **Space** reading a results dataset. HF is where the open community looks
first.

## 5. The minimum bar (a checklist a reviewer would apply)

Synthesizing the above, a benchmark is "real" — not a blog post — when it has all of:

1. A **precisely defined construct** and a one-line statement of what a high score does and does not
   mean.
2. A **dataset** with documented provenance, a sampling protocol, per-stratum structure, and a
   **datasheet**; a clear **license**; a stable **download URL**; a **Croissant** metadata file.
3. A **public + held-out (ideally private) split**, a **contamination strategy** (canary +
   freshness + audit), and reported gaps between them.
4. A **runnable, versioned harness** that reproduces every number from a fixed seed, ideally inside a
   standard tool (lm-eval / Kaggle), with pinned model/decoding/metric versions.
5. **Metrics justified against the construct**, reported with **uncertainty** (bootstrap CIs), plus
   **per-stratum breakdowns** and **error analysis**.
6. A **leaderboard** with a submission path, anti-overfitting policy, and visible confidence bands.
7. A **maintenance plan**: who updates it, how versions are cut, how the fresh split rolls.
8. Honest **limitations** and a **claims ledger** — what the benchmark cannot tell you.

Items 1–5 are the difference between "publishable" and "ignored." Items 6–8 are the difference between
"a paper" and "a standard the community maintains with you."

## 6. The trust surface — what makes the community comfortable

Beyond correctness, adoption is a trust phenomenon. The recurring signals across HELM, lm-eval, Arena,
and SWE-bench:

- **Uncertainty over point estimates.** Chatbot Arena fits a Bradley–Terry model over ~6M pairwise
  human votes and *always* shows Elo with 95% confidence bands, marking low-data models "preliminary."
  A leaderboard that shows a bare number reads as naïve; one that shows a CI reads as careful.
- **Reproducibility receipts.** Every score traces to a seed, a harness version, and a logged
  transcript. (Aleph's existing `docs/verification.md` discipline is already this instinct.)
- **Adversarial self-audit.** SWE-bench's credibility *rose* when its authors published the
  contamination audit against their own benchmark. Publishing your benchmark's weaknesses is the
  strongest trust signal available.
- **Separation of evidence modes.** HELM and Aleph both refuse to conflate measured vs simulated.
  ALEPH-Bench keeps black-box behavioral fidelity, white-box NLL, and fixture/demo strictly labeled.
- **Meeting people in their tools.** The harness lands in lm-eval/Kaggle/HF; contributing an item is
  a documented PR; the dataset has a Croissant file. Low friction is a trust signal.

## 7. What to copy from each exemplar (one line each)

| Exemplar | The one move to copy |
|---|---|
| Construct-validity review (445 benchmarks) | The 8-point checklist; kill the arbitrary weighted sum. |
| BIG-bench | PR-based community task submission + canary GUID. |
| HELM | Comprehensiveness as a declared scenario×metric matrix, multi-metric reporting. |
| lm-evaluation-harness | Be a *task in the standard harness*; version everything; report uncertainty. |
| SWE-bench Verified→Pro | Private held-out split; publish your own contamination audit; report the gap. |
| LiveBench / LiveCodeBench | A time-gated *fresh* split that is non-memorizable by construction. |
| Chatbot Arena | Statistical aggregation with confidence intervals; "preliminary" labels. |
| Kaggle Community Benchmarks | Launch surface + the Resource Grant for free frontier-model access. |
| HF Open LLM Leaderboard | Croissant-documented dataset + Gradio leaderboard Space. |
| NeurIPS D&B track | Datasheet + reproducibility checklist + hosting/licensing/maintenance plan = the paper. |

## 8. Where current best practice can be pushed (preview)

The exemplars above measure **accuracy at a fixed prompt**. None of them measure **prompt length at
fixed accuracy**. That orthogonal axis — elicitation efficiency as a per-model rate–distortion
frontier — is the gap ALEPH-Bench fills, and the place to push past current practice:

- a **curve-valued** score (AURC) instead of a scalar accuracy, summarized by interpretable duals;
- **leakage as a validity gate** rather than a soft term;
- a **white-box MDL track** that grounds the behavioral score in teacher-forced description length,
  connecting the leaderboard to the "language modeling is compression" literature;
- a **transfer column** distinguishing universal short prompts from model-specific "garden-path"
  coordinates — a phenomenon the repo already documents and no leaderboard currently reports.

These are developed in [`02-design-spec.md`](02-design-spec.md) and defended in
[`04-positioning-and-novelty.md`](04-positioning-and-novelty.md).

---

## Sources

- [Measuring what Matters: Construct Validity in LLM Benchmarks (445-benchmark review, 8 recommendations)](https://arxiv.org/abs/2511.04703)
- [EleutherAI lm-evaluation-harness](https://github.com/EleutherAI/lm-evaluation-harness/) · [task guide](https://github.com/EleutherAI/lm-evaluation-harness/blob/main/docs/task_guide.md)
- [google/BIG-bench](https://github.com/google/BIG-bench/) · [BIG-Bench canary contamination in GPT-4](https://www.lesswrong.com/posts/kSmHMoaLKGcGgyWzs/big-bench-canary-contamination-in-gpt-4)
- [SWE-bench Pro (Scale) public](https://labs.scale.com/leaderboard/swe_bench_pro_public) / [private](https://labs.scale.com/leaderboard/swe_bench_pro_private) · [Is SWE-bench Verified contaminated?](https://www.codesota.com/news/swe-bench-contamination-debate)
- [LiveCodeBench: Holistic and Contamination-Free Evaluation](https://arxiv.org/abs/2403.07974) · [LiveBench](https://github.com/LiveBench/LiveBench)
- [Chatbot Arena / LMArena Bradley–Terry methodology](https://lmsys.org/blog/2023-12-07-leaderboard/) · [Prompt-to-Leaderboard](https://arxiv.org/pdf/2502.14855)
- [Kaggle Community Benchmarks (Google blog)](https://blog.google/innovation-and-ai/technology/developers-tools/kaggle-community-benchmarks/) · [Kaggle Benchmarks docs](https://www.kaggle.com/docs/benchmarks) · [kaggle-benchmarks SDK](https://github.com/Kaggle/kaggle-benchmarks) · [Benchmarks Resource Grant Program](https://www.kaggle.com/blog/introducing-the-benchmarks-resource-grant-program)
- [HF Open LLM Leaderboard](https://huggingface.co/spaces/open-llm-leaderboard/open_llm_leaderboard) · [Croissant metadata format](https://github.com/mlcommons/croissant)
- [NeurIPS Datasets & Benchmarks Track — raising the bar](https://blog.neurips.cc/2025/03/10/neurips-datasets-benchmarks-raising-the-bar-for-dataset-submissions/) · [2026 Call](https://neurips.cc/Conferences/2026/CallForEvaluationsDatasets)
- [LLMLingua](https://arxiv.org/abs/2310.05736) · [Prompt Compression survey](https://arxiv.org/html/2410.12388v2) · [Instruction-Following Under Compression](https://arxiv.org/pdf/2512.17920)
- [Language Modeling Is Compression](https://arxiv.org/abs/2309.10668) · [The KoLMogorov Test: Compression by Code Generation](https://arxiv.org/html/2503.13992v1)
