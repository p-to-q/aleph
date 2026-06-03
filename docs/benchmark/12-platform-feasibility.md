# Platform Feasibility: What Is Actually Measurable on Kaggle (and against closed APIs)

This document answers a make-or-break planning question: **can ALEPH-Bench actually run on Kaggle
against OpenAI / Claude / Gemini, and which metrics can the system really capture?** The short answer
splits cleanly along the line the dossier already drew — and confirms the design was right to draw it.

> **The flagship (Track F) and every behavioral metric are fully measurable on Kaggle against all
> vendors, including Claude. The "human-invisible" bit-level metrics (NLL / bits-per-byte / per-token
> loss) are NOT obtainable from the closed APIs — only from open-weight models. This is not a gap to
> fix; it is exactly why Track W was scoped to open weights and Track F was made the flagship.**

## 1. The hard fact: logprob availability per vendor (2026)

The bit-level metrics all require **logprobs**, specifically the *teacher-forced* probability the model
assigns to a given target string. Current reality:

| Vendor | Logprobs exposed? | Teacher-forced target NLL / bits possible? |
|---|---|---|
| **Anthropic / Claude** | **No** — API returns `"logprobs": null`. Pure black-box. | **No** |
| **OpenAI** | Only **generated-token** top-k logprobs (0–20); **not** prompt/target tokens. Newest frontier models (e.g. GPT-5-class) often expose **none**. | **No** (no echo/teacher-forcing on chat models) |
| **Gemini** | `responseLogprobs` → `avgLogprobs` + top candidates for **output** tokens (GA on Vertex since 2025); newest frontier (Gemini-3-Pro-class) often **none**. | **No** |
| **Open weights** (Qwen / DeepSeek / Llama via vLLM; local MLX) | **Full logits**; `prompt_logprobs` available. | **Yes** — full Track W |

Two consequences that matter:

- Even the *generated-token* logprobs that OpenAI/Gemini do expose are **not teacher-forced scoring of
  an arbitrary target** — they only tell you the probability of the tokens the model *chose to
  generate*, not `P(y | p)` for a target `y` the model did not produce. Bits-per-byte of a target
  therefore cannot be computed from them.
- They are **not comparable across vendors** anyway (different tokenizers; Claude has none). A
  *cross-vendor* bits leaderboard is impossible in principle — another reason Track W lives only inside
  the open-weight set, where the measurement is controlled and comparable.

## 2. Kaggle specifically

**Yes, the benchmark runs on Kaggle, and yes you can request the frontier models.** Kaggle Community
Benchmarks provides free model access via the `kaggle-benchmarks` SDK, and the **Benchmarks Resource
Grant** explicitly grants access to OpenAI, Google, Anthropic, Grok, Qwen, and DeepSeek models — which
is precisely what the [grant application draft](launch-kit/kaggle-grant-application.md) requests.

But the Kaggle SDK surface is `llm.prompt()` — a **generation / structured-output** interface that
returns text (and Pydantic-typed objects), **not logprobs**. Kaggle's own benchmark cookbook states the
constraint plainly: *many providers such as Anthropic do not expose token-probabilities, and they could
not obtain them from GPT-5 or Gemini-3-Pro despite availability for some other models.* So on Kaggle,
against the big models, you measure **behavior**, not bits.

**That is all Track F needs.** The flagship leaderboard is built entirely from black-box behavioral
signals, so it maps onto Kaggle's SDK with zero friction.

## 3. The measurability matrix (the "capturable indices")

| Metric | Claude | OpenAI | Gemini | Open weights | Kaggle SDK | Track |
|---|---|---|---|---|---|---|
| Fidelity / distortion (text vs target) | ✓ | ✓ | ✓ | ✓ | ✓ | **F** |
| Prompt length → ECL@τ, CF, AURC, Elicit@k | ✓ | ✓ | ✓ | ✓ | ✓ | **F** |
| Stability (rerun variance) | ✓ | ✓ | ✓ | ✓ | ✓ | **F** |
| Leakage gate (string overlap; no model needed) | ✓ | ✓ | ✓ | ✓ | ✓ | **F** |
| Eval pass-rate (execution / schema) | ✓ | ✓ | ✓ | ✓ | ✓ | **F** |
| Transfer gap | ✓ | ✓ | ✓ | ✓ | ✓ | **F** |
| Generated-token logprobs | ✗ | ~ | ~ | ✓ | ✗ | — |
| **Teacher-forced NLL / bits-per-byte** | ✗ | ✗ | ✗ | ✓ | ✗ | **W** |
| Per-token loss / attribution (Δloss) | ✗ | ✗ | ✗ | ✓ | ✗ | **W** |

Everything in the **F** rows — the entire public leaderboard — is capturable on Kaggle against every
vendor. Only the **W** rows need open weights, and they run in a Kaggle **GPU notebook** (or locally via
the existing MLX path) where you load the weights and read logits yourself.

## 4. The three roles of the "human-invisible" bits — none needs a closed API

The bit-level signals are not lost; they live where they are actually obtainable, doing three jobs:

1. **Dataset construction (open reference model).** The existing engine already uses teacher-forced NLL
   on a local open model to *guide* the search for short prompts (`Theta.score()`, `hardest_tokens()`
   in [`search/aleph_search.py`](../../search/aleph_search.py)). Building the frozen ladders is where
   the invisible bits do their most important work — and that is an *offline, open-weight* step.
2. **Track W rigor anchor (open-weight models).** Bits-per-byte and two-part description length are
   reported for Qwen/DeepSeek/Llama-class models as the most rigorous numbers we can offer
   ([`09-metric-validity-and-rigor.md`](09-metric-validity-and-rigor.md) §4).
3. **Not required for the closed-API leaderboard.** Ranking Claude vs GPT vs Gemini happens entirely on
   behavioral Track F. No bits needed at eval time.

## 5. The behavioral shadow: capturing the bits' *effect* without logprobs

You can still recover a **behavioral estimate of the invisible likelihood** from any vendor, including
Claude, with no logprobs at all: **resample**. Generate the model's output `R` times at non-zero
temperature for a given prompt and measure how often it lands within distortion `ε` of the target. That
hit-rate is a Monte-Carlo estimate of the probability mass the model places near `y` given `p` — a
behavioral shadow of `P(y | p)`. It is exactly what `stability` + repeated sampling already compute, and
it is **fully capturable on Kaggle against every model**. So the leaderboard gets a principled,
likelihood-flavored signal even where the actual bits are sealed off.

## 6. Practical plan on Kaggle

The product framing follows directly: **the primary deliverable is a black-box, cross-vendor
leaderboard (Track F), in the spirit of LMArena / LMSYS Chatbot Arena but on the elicitation-efficiency
axis — with a separate, explicitly `white_box`-labeled table (Track W) shown alongside for open-weight
models.** The two never merge: one ranks all vendors behaviorally; the other reports bits for the models
that expose them.

```text
Track F leaderboard (the public, cross-vendor board — the LMArena-style headline):
  → run via kaggle-benchmarks `@kbench.task` + llm.prompt() against
    OpenAI / Anthropic / Google / DeepSeek / Qwen / Grok (Resource Grant)
  → metrics: AURC, ECL@τ, Elicit@k, stability, leakage gate, eval pass-rate, transfer
  → 100% measurable; this is the headline result.

Track W rigor anchor (open weights only):
  → run in a Kaggle GPU notebook (or local MLX) loading Qwen/DeepSeek/Llama
  → read logits directly → teacher-forced NLL, bits-per-byte, two-part code length
  → a separate, labeled table; never merged into the black-box board.

Construction (offline):
  → use an open reference model's NLL to build + verify frozen ladders.
```

## 7. One-line answer

Your benchmark runs on Kaggle against every major model, and the grant gets you those models for free —
but only the **behavioral** metrics are detectable there; the **bit-level** metrics are obtainable only
from open weights (Kaggle GPU notebook or local). The design already accounts for this exactly: Track F
is the cross-vendor leaderboard, Track W is the open-weight rigor anchor, and the "invisible" bits do
their real work at *construction time* on an open model — so nothing important is lost, and nothing on
the public board depends on a logprob a vendor refuses to give.

---

## Sources

- [Anthropic API does not expose logprobs (returns null)](https://github.com/anerli/anthropic-logprobs)
- [OpenAI logprobs are completion-tokens only, not prompt tokens](https://community.openai.com/t/get-logprobs-for-prompt-tokens-not-just-for-completion/717289) · [Using logprobs (OpenAI cookbook)](https://cookbook.openai.com/examples/using_logprobs)
- [Gemini responseLogprobs / avgLogprobs (Vertex GA)](https://developers.googleblog.com/unlock-gemini-reasoning-with-logprobs-on-vertex-ai/)
- [Kaggle Benchmarks cookbook — providers like Anthropic don't expose token-probabilities; not obtainable from GPT-5 / Gemini-3-Pro](https://github.com/Kaggle/kaggle-benchmarks/blob/ci/cookbook.md) · [Benchmarks Resource Grant (free model access)](https://www.kaggle.com/blog/introducing-the-benchmarks-resource-grant-program)
- [Log Probability Tracking of LLM APIs (availability is patchy)](https://arxiv.org/pdf/2512.03816)
