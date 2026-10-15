# MiniPrompt/ACR Reproduction Note

Status: gate note for the mandatory closest-baseline reproduction — the third item of the
"Next Correct Move" list in [../state-of-play.md](../state-of-play.md) — recorded under the
structural decision research gate in [research-process.md](research-process.md) **before** any
reproduction module lands. Access date for all sources below: 2026-10-15 (UTC).

## Question

[../state-of-play.md](../state-of-play.md) records the next move: "Reproduce MiniPrompt/ACR
behind the same archive and evaluator boundary." [prior-art.md](prior-art.md),
[research-process.md](research-process.md), and
[../plans/iclr-readable-coordinate-program.md](../plans/iclr-readable-coordinate-program.md)
fix the position: *Rethinking LLM Memorization through the Lens of Adversarial Compression*
(Schwarzschild et al., NeurIPS 2024) is the closest empirical collision and the mandatory
closest white-box baseline; Aleph cannot claim novelty for the bare target-first shortest-input
search object or the model-as-decompressor reading, and the paper must report a raw-coordinate
comparator such as MiniPrompt alongside the readable view.

What exactly is reproduced, on which models and interface conditions, with what added
measurement discipline, and what is explicitly *not* claimed?

## Sources inspected

| Source (accessed 2026-10-15) | Location | F — what was observed | I — interpretation | U — use here |
|---|---|---|---|---|
| Paper abstract page | `arxiv.org/abs/2404.15146`; fetched copy `/tmp/acr-repro-sources/2404.15146.abs.html` (`488163d2…`) | arXiv:2404.15146; versions v1 2024-04-23, v2 2024-07-01, v3 2024-11-11; NeurIPS 2024. | The camera-ready is v3; citations should say arXiv:2404.15146 (NeurIPS 2024). | Source identity for the receipt and later citation checks. |
| Paper full text (ar5iv rendering) | `ar5iv.labs.arxiv.org/html/2404.15146`; fetched copy `2404.15146.ar5iv.html` (`3712f30b…`) | ACR: `ACR(M,y) = |y| / |x*|` with `x* = argmin |x| s.t. M(x) = y`, in tokens, threshold τ = 1; "memorized" means compressible (ratio > 1); the model-output convention is greedy decoding (argmax appended repeatedly); MiniPrompt = GCG plus a length scan (start five tokens long, grow on failure, 20% more steps when the prompt grows, early stop on exact match); "our design choices are heuristic"; experiments: Pythia 410M–12B on famous quotes; four validation categories (random token strings never compressible; post-cutoff AP articles not compressible; Wikipedia sentences sometimes; paraphrases lower ACR). | The algorithm is explicitly an approximate heuristic solver; its found value is not a claimed global optimum — consistent with the repository's "shortest found" reading. | The reproduction preserves the ACR measurement semantics and the scan policy as declared facts; all Aleph claims stay scoped to found values. |
| Upstream GCG implementation (pinned) | `locuslab/acr-memorization` @ `bf3ba2e7bf224482928fba42cd79c295796c0237`, `prompt_optimization/gcg.py` (`74c991ae…`) | Inner loop, exactly: teacher-forced cross-entropy over the target tokens (mean); gradient of the loss with respect to the one-hot/embedding input at all positions; `topk=250` candidate tokens per free position from the descent direction; `batch=100` candidates, each mutating one random free position to a random token among that position's top-k; best candidate by loss becomes the next iterate; early stop when every target token is the argmax of the teacher-forced logits (all-match); a best-by-loss input tracked as fallback. | The all-match criterion is equivalent to greedy decoding reproducing the target from the prompt (induction over positions: each teacher-forced argmax on the true prefix is the next greedy token); verified empirically in the receipt. | This is the exact loop the MLX reproduction must preserve; defaults `topk=250`, `batch=100`, `num_steps=200`, `mini_batch=100`. |
| Upstream MiniPrompt scan (pinned) | `prompt_optimization/miniprompt.py` (`e5bb8cea…`) | Scan policy, exactly: start at 5 free tokens; on failure grow by +5 and multiply the step budget by 1.2; on success record the prompt, set the upper bound to the successful length, and try length − 1; terminate when the next length would reach the upper bound or the lower bound; `max_tokens=-1` caps the upper bound at 5× the target token length; success uses the teacher-forced all-match check; result field `num_free_tokens` = smallest successful free-token count found. | The scan is a heuristic search over lengths, not an exhaustive minimality proof; only successes inside the scan policy are reported. | The reproduction reimplements the same scan policy under a frozen declared configuration. |
| Upstream layout, success check (pinned) | `prompt_optimization/utils.py` (`f44622fb…`) | Layout `[chat_template[0], system_prompt, input_str, free_tokens, chat_template[1], target]`; free tokens initialized as uniform random token IDs; `check_output_with_hard_tokens` = teacher-forced argmax equals every target token. With the default empty scaffold (empty templates, empty system/input), the sequence is exactly `[free tokens, target tokens]`. | The default prompt is a raw token block with no text scaffold; the prompt is raw token IDs, and a decoded rendering is not part of the optimization. | The canary reproduces the empty-scaffold layout exactly; scaffolded layouts become a declared extension, never silent behavior. |
| Upstream driver, config, analysis (pinned) | `prompt-minimization-main.py` (`4b390e94…`), `config/promptmin.yaml` (`5373628c…`), `analyze_results.ipynb` (`453229a5…`), `make_table_of_results.py` (`522f8b0e…`) | Defaults: `EleutherAI/pythia-410m`, `discrete_optimizer: gcg`, `topk: 250`, `batch_size: 100`, `num_steps: 200`, `seed: 42`; results JSON stores `target_length`, `loss_of_target_str`, `loss_of_prompt`, `optimal_prompt`, `num_free_tokens`, `success`; the notebook computes the reported ratio as `target_length / num_free_tokens` and marks `memorized = ratio > 1` with failures marked not memorized. | The published figures' denominator is the free-token count; under empty scaffolding this equals the whole prompt token count, while through scaffolds it can differ from the paper's `|x*|` (whole prompt). | The reproduction records both numbers (whole-prompt tokens; free tokens) and declares which one feeds a comparison. |
| Upstream license | `LICENSE` (`9ec15b4e…`) | BSD 3-Clause (Copyright 2024 Avi Schwarzschild, Zhili Feng, Pratyush Maini). | Method reproduction is license-compatible; no upstream code is copied — the loop is reconstructed for MLX. | Keeps the reproduction clean: method fidelity, own implementation, attribution. |
| In-repo positioning (records) | [prior-art.md](prior-art.md), [../open-questions.md](../open-questions.md) §4/§7, [../plans/iclr-readable-coordinate-program.md](../plans/iclr-readable-coordinate-program.md) (Relation to ACR and MiniPrompt) | MiniPrompt is the mandatory closest white-box baseline; ACR is adopted as prior art; interface conditions (admissible domain, fixed scaffold, tokenizer, decoding, EOS convention, legal-token policy) must be declared for any comparison; the paper must report the readable-versus-raw gap. | The reproduction's role in Aleph: supply the raw comparator under declared conditions, with receipts, so matched-work claims become possible later. | Acceptance gates below inherit these boundaries. |

Source files and sha256 (all fetched 2026-10-15; full manifest at
`/tmp/acr-repro-sources/MANIFEST.sha256`):

- `2404.15146.abs.html` `488163d2f64f71320405c340db22a7be8a014371caeba9dea23bc4c91f34a48e`
- `2404.15146.ar5iv.html` `3712f30b5dc27219b5174af6efe615c65d191b75f1c3a2ce53b450499fe1c8d1`
- `upstream-README.md` `1c68f9f8da505552c1f1de166ad50c783b9fa965828f6d53cc6d5261829d27d5`
- `upstream-LICENSE` `9ec15b4ef985eb26e142d6083fffec6c6fe9a3b49e7c64f0e8a343c5e8838ece`
- `upstream-prompt_optimization_gcg.py` `74c991ae726c9fe91dd8bce580e3bf00c083583ddd910dac568056d1d0b6b379`
- `upstream-prompt_optimization_miniprompt.py` `e5bb8ceabce5371f620613f3df467a6254068b9a3c29cd00eedf6b7b8ae31a06`
- `upstream-prompt_optimization_utils.py` `f44622fb67ebfdf3e6f339b4c111801e8cfdf0c6d6cdb52863563e8faf7591d0`
- `upstream-prompt_optimization_random_search.py` `9dcce81f14ea8e55083e612eaa903539d8a2e807331b4b0de45055bc3d4213fd`
- `upstream-prompt-minimization-main.py` `4b390e9448e6f45add78c621a8d1218fa29b270db1529cbf7150ab1d16acb1f2`
- `upstream-config_promptmin.yaml` `5373628c0f132310ec6f4874fc8d831e027c44eeca55285aaacd7474b973e90f`
- `upstream-example_script.py` `2ba192f945d3d21ff7069ac39942fdbeebbcb3a34ee7d89c78f9837f67817d47`
- `upstream-analyze_results.ipynb` `453229a50b96b8af526393fc2b9197d923ab8df4d4981381691b4c19897c343f`
- `upstream-make_table_of_results.py` `522f8b0e04313f7e898bbb2c8c9e357864e66018d94d73a3284b839468224afa`
- `upstream-requirements.txt` `9ebb63a67bc4e299b15648ba0f5f468f65eb9a9c01e60f7efda302881e7c5acb`

## Interpretation: what this reproduction is, and what it is not

- **Method-level reproduction on Aleph's pinned stack**: the GCG inner loop and the MiniPrompt
  length scan, reimplemented for MLX, run on pinned open-weight models
  (`mlx-community/Qwen3-1.7B-4bit`, later `Qwen3-4B-4bit`) under declared budgets, with receipts
  and resumable state. It is **not** a numeric reproduction of the paper's tables on their models
  (Pythia; no torch stack on the maintainer box, and no such goal).
- **Interface conditions are declared per run** (from the iclr plan): admissible token domain,
  scaffold, tokenizer and length unit, deterministic decoding, exact output convention (greedy;
  target IDs are ground truth), and the legal-token policy for the raw block. Default canary:
  empty scaffold, `[free tokens, target tokens]` — exactly the upstream default layout.
- **Differences are declared, not hidden**: 4-bit quantized MLX models instead of bf16 torch
  models; gradients are taken with respect to input embeddings only (weights frozen); the effect
  of quantization on the gradient direction is unmeasured (see risks); step costs differ from the
  paper's hardware.
- **The found object is a raw coordinate.** In Aleph's coordinate language it belongs to the raw
  view ([../open-questions.md](../open-questions.md) §7): it must be reported as token IDs plus a
  declared rendering, never as a readable prompt, and it carries no human-eligibility claim. The
  feasibility probe's two found prompts decode to non-semantic fragments, which is the expected
  shape of raw optima and exactly why the separation exists.
- **No claims beyond the declared scope**: no global-optimality claim (heuristic solver by
  construction), no memorization or training-data-causality claim, no cross-model transfer claim;
  comparisons against Aleph's readable search happen only at matched declared budgets after this
  baseline exists, with negative results recorded.

## Feasibility evidence (2026-10-15)

A bounded MLX-native probe validated the reproduction's riskiest mechanics before any module
lands; details, commands, hashes, and raw numbers are in the receipt
[2026-10-15-miniprompt-feasibility-receipt.md](2026-10-15-miniprompt-feasibility-receipt.md).

- Gradient flow: the loss gradient with respect to input embeddings differentiates cleanly
  through the quantized Qwen3-1.7B stack (4-bit weights, frozen), and `embed_tokens.as_linear`
  turns the embedding gradient into per-vocabulary descent scores — the MLX equivalent of the
  upstream one-hot gradient.
- Runs: a 6-token natural target from 5 free tokens reached 4/6 teacher-forced match in 200
  steps; the canary target `42` was acquired (all-match) at step 87 of 240 from 5 free tokens;
  `hello world` was acquired at step 10 of 200; a 10-free-token run reached 5/6 match at step 224
  before a tool-timeout kill (recorded as partial).
- Both acquisitions were additionally verified by true greedy continuation from the raw IDs
  (no retokenization): the model emits exactly the target tokens.
- Cost at 1.7B: ≈0.8–1.4 s/step at `batch=100`, `topk=250`; short acquisitions complete in
  seconds to ~2 minutes; a 6-token target resists 200+ steps, so a full scan policy needs
  multi-rung budgets and resumable runs (a single agent tool call is capped well below a full
  scan).

## Unknowns / risks

1. **Quantization vs bf16.** Upstream gradients are taken through bf16 weights; ours through
   4-bit quantized weights. Whether that shifts step counts or failure rates is unmeasured;
   phase 2 measures its own declared budgets, not the paper's numbers.
2. **Scan budgets for quote-length targets** on the pinned models are unknown; the pilot suggests
   per-rung minutes and full scans in the tens of minutes per target at 1.7B. Resumable state is
   required.
3. **Raw-ID round trip.** `encode(decode(ids)) == ids` held for both feasibility acquisitions, but
   decode is not a guaranteed inverse for arbitrary raw IDs; receipts must store IDs as ground
   truth and treat decoded text as a declared rendering.
4. **Denominator convention.** The notebook uses `num_free_tokens`; the paper defines `|x*|` as
   the whole prompt. With non-empty scaffolds these differ; the reproduction records both and
   declares which one a comparison uses.
5. **Their table values** remain unverified on their stack (out of scope); no claim compares to
   them numerically.

## Structural effect (what later PRs will land)

- A new opt-in module family `search/miniprompt/` (MLX-only; **no new dependencies**; follows the
  opt-in canary pattern of PR C — pure parts importable and testable without MLX, model access
  only in explicit run paths). Planned shape: frozen declared run configuration with strict
  parsing; GCG core; MiniPrompt scan; resumable run state; receipts carrying target IDs,
  free-token IDs, seeds, step/batch/topk, model identity (repo + revision + weights digest), and
  per-run outcomes including the greedy-continuation check.
- Evaluation boundary: found prompts are evaluated through the same teacher-forced scoring
  discipline Aleph already uses and archived as raw-view points; nothing enters the readable
  product path.
- Follow-up PR acceptance gates:
  1. The module reproduces the upstream scan-policy mechanics under a frozen declared config
     (start/grow/step-down bounds, step multiplier, cap, early stop), with the policy pinned by
     tests.
  2. Runs are resumable and receipted; every claimed acquisition includes the all-match check
     recorded from raw IDs and is replayable by an independent verifier.
  3. At least one declared canary target is acquired on a pinned model and receipted end to end
     (target IDs, prompt IDs, model identity, budgets).
  4. `npm run lint` and `npm test` stay green; MLX stays out of the default test path; no new
     dependencies.
  5. Raw-view labeling is enforced in every artifact; no readable-prompt or human-eligibility
     language is used for found prompts.
  6. A small declared target set (including at least one negative/partial control) is archived so
     the paper tranche can compare MiniPrompt-found raw prompts against Aleph readable search at
     matched declared budgets.

## Implementation landing (2026-10-16)

The follow-up PR landed the planned shape: `search/miniprompt/` carries the frozen declared
configuration with strict fail-closed parsing (`config.py`), the upstream scan policy as a tested
state machine (`scan.py`), seeded sampling derivations (`sampling.py`), receipt construction plus an
MLX-free fail-closed verifier (`receipts.py`), the MLX GCG core with the pinned-snapshot loader
(`gcg.py`), the resumable scan runner (`runner.py`), and an opt-in CLI (`cli.py`).

Acceptance gates from the list above, discharged:

1. The scan mechanics are pinned by tests (start/grow/step-down bounds, `int(x * 1.2)` budget
   growth, the `max_tokens=-1` auto cap, and the declared hard caps) in
   `search/tests/test_miniprompt.py`.
2. Runs are resumable and receipted; every acquisition carries the all-match check plus a matched
   true-greedy continuation from raw IDs, and the receipt verifier replays the policy over the
   recorded outcomes.
3. The end-to-end canary is archived: `search/miniprompt/receipts/canary-hello-001` (target
   `hello world`; acquired at n=5/4/3 free tokens — steps 34/50/21 — and failed at n=2 within the
   declared 200-step budget, so `numFreeTokens=3`).
4. `npm run lint` and `npm test` stay green with MLX out of the default path (the MLX smoke tests
   skip without MLX and run under `search/.venv`); no new dependencies.
5. Raw-coordinate labeling is carried by every receipt and enforced by the verifier.
6. A small declared set is archived: the canary plus the negative/partial control
   `search/miniprompt/receipts/control-jumps-001` (two attempts under declared budgets, not
   acquired, stopped at the declared attempt bound).
