# MiniPrompt scaffolded-layout extension (design and gate record)

Status: records the declared extension of the MiniPrompt reproduction's scaffold surface
(`search/miniprompt/`). The reproduction's empty-scaffold runs and every archived receipt are
unchanged by this extension; scaffolded layouts were previously refused fail-closed
(`config.py`: "scaffolded layouts are a future declared extension") and are now an explicitly
declared per-config option with derived, recorded token IDs.

## Question

Should the raw-coordinate arm support the pinned upstream's scaffolded layouts, and if so under
which declared semantics — so that a future comparison tranche can declare scaffolded raw-side
presets without silent behavior?

## Sources inspected

| Source (accessed 2026-10-16 UTC) | Location | F — what was observed | I — interpretation | U — use here |
|---|---|---|---|---|
| Pinned upstream layout builder (primary) | `locuslab/acr-memorization` @ `bf3ba2e7`, `prompt_optimization/utils.py` (`f44622fb…`; re-fetched and re-hashed 2026-10-16 UTC; clone `/private/tmp/aleph-t3-src/upstream`) | `prep_text` builds `[chat_template[0], system_prompt, input_str, free_tokens, chat_template[1], target_tokens]`; every text part is tokenized with `add_special_tokens=False`; slices: free window after the prefix, target slice = last `\|target\|` positions, loss slice = target positions shifted by one | The scaffold is fixed text around the free tokens; only the free window is optimized | The declared layout and the derivation convention (`add_special_tokens=False`) |
| Pinned upstream GCG (primary) | same pin, `prompt_optimization/gcg.py` (`74c991ae…`) | Gradients are taken w.r.t. the free-token slice only; candidates mutate one free position with a top-k descent token; the in-loop check is a single-sequence teacher-forced argmax over the loss slice | The scaffold is never optimized and never mutated | The free-window generalization of `gcg_step` (gradient slice, mutation offset) |
| Pinned upstream defaults (primary) | same pin, `config/promptmin.yaml` (`5373628c…`) and `prompt-minimization-main.py` (`4b390e94…`, both re-hashed 2026-10-16 UTC) | `chat_template: ['', '']`, `system_prompt: ''`, `input_str: ''`; the driver passes config values straight into `minimize_prompt` | The published runs used the empty scaffold; scaffolded layouts are supported plumbing upstream but did not shape the published figures | Scope: the extension serves declared comparisons of scaffolded coordinates; it does not revise the reproduction |
| Reproduction note (in-repo) | [miniprompt-reproduction-note.md](miniprompt-reproduction-note.md) | "scaffolded layouts become a declared extension, never silent behavior"; with non-empty scaffolds the free-token count differs from the whole-prompt token count, and the reproduction records both numbers | The accounting (free vs whole prompt) must stay explicit for scaffolded runs | The whole-prompt accounting rule below |

## Declared semantics of the extension

- **Config grammar.** `scaffold` is `"empty"` (the declared default; the byte-stable canonical
  form of every existing preset) or a mapping
  `{"chatTemplate": [str, str], "systemPrompt": str, "inputStr": str}`; parts may be empty
  strings, but an all-empty mapping is refused (use `"empty"`); unknown or missing keys and
  wrong types fail closed. The config schema string stays `aleph-miniprompt-config/0.1.0` — the
  extension accepts strictly more documents and leaves the canonical form (and digest) of every
  existing declaration byte-identical.
- **Layout and derivation.** The sequence is
  `[chatTemplate[0], systemPrompt, inputStr, free tokens, chatTemplate[1], target tokens]`;
  each scaffold text part is tokenized with `add_special_tokens=False` exactly as upstream
  (`gcg.scaffold_token_ids`); `prefixIds` = `chatTemplate[0] + systemPrompt + inputStr`,
  `midIds` = `chatTemplate[1]`. The empty scaffold derives empty lists and reduces exactly to
  `[free tokens, target tokens]`.
- **Acquisition criterion (conjunction, unchanged in spirit).** (a) The single-sequence
  teacher-forced all-match evaluated at the scaffold-shifted loss positions (`solution_check`
  with `prefix_ids`/`mid_ids`) — the same fixed shape as the receipt re-check; (b) the true
  greedy continuation generated from the scaffold context `prefix + free + mid` (the
  teacher-forced context minus the target) must emit the target IDs
  (`greedy_continuation_ids`). No retokenization anywhere.
- **Free window.** Gradient and candidate mutations act on `[|prefix|, |prefix| + nFree)`
  only; the scan policy, step budgets, and the `-1` cap (`5 x` target tokens) are unchanged.
- **Accounting.** `wholePromptTokens` = `|prefix| + nFree + |mid| + |target|`;
  `numFreeTokens`/`smallestAcquiredNFree` remain the free-token counts (the paper's ratio
  denominator). For the empty scaffold the whole-prompt count reduces to the current formula.
- **Receipts and state.** New runs record a derived `scaffold` block
  (`{"prefixIds": [...], "midIds": [...]}`) in `state.json` and `receipt.json`; the receipt
  verifier validates the block when present, requires it for scaffolded declared configs,
  refuses derived tokens for the declared empty scaffold, and recomputes `wholePromptTokens`
  from the recorded counts. Receipts and states created before the extension carry no block and
  verify unchanged (the empty scaffold derives empty lists).
- **Declared differences / tool identity.** The change is recorded in
  `receipts.DECLARED_DIFFERENCES` (the scaffold entry is rewritten to the
  supported-extension wording); the tool identity stays
  `{"name": "search/miniprompt", "version": "0.1.0"}`.
- **Non-goals.** No scaffolded presets, runs, or comparison instances are declared here; no
  claim about scaffold quality or readability; no change to the empty-scaffold reproduction
  results; the comparison-side summary helpers must adopt the recorded whole-prompt count when
  scaffolded instances are declared (flagged below).

## Structural effect

- `search/miniprompt/config.py`: `ScaffoldDeclaration` + scaffold grammar (additive; existing
  digests byte-stable).
- `search/miniprompt/gcg.py`: `scaffold_token_ids`; free-window parameterization of `gcg_step`;
  `prefix_ids`/`mid_ids` on `solution_check`, `greedy_continuation_ids`,
  `greedy_continuation_check`, and `run_attempt`; generalized `wholePromptTokens`.
- `search/miniprompt/sampling.py`: `apply_mutations(..., offset=0)` (the default preserves the
  existing behavior).
- `search/miniprompt/runner.py`: derivation at scan start, persisted scaffold block, resume
  validation, receipt wiring.
- `search/miniprompt/receipts.py`: optional `scaffold` block in `build_receipt`; verifier
  rules; declared-difference wording.
- Tests: config grammar (accept/reject/digest stability), scaffolded receipt round-trip and
  tampers, faked-model criterion/free-window/greedy-context pins, pinned-tokenizer derivation.
- No new dependencies; MLX stays out of the default test path; no product surface or
  canonicalization change.

## Follow-ups (not in this slice)

- A declared scaffolded preset + comparison tranche (its own declaration-first step, like
  tranche 2) if scaffolded coordinates are to be compared.
- Comparison summary adoption: `search/compare/record.py` derives `wholePromptTokens` as
  `nFree + target count` today; scaffolded receipts must feed it the recorded whole-prompt
  count before any scaffolded instance is archived.

## Acceptance gates (discharged in this slice)

1. Every existing preset digest is byte-stable; every archived receipt (with and without the
   scaffold block) verifies under the new verifier.
2. Scaffolded layouts run end to end through `run_attempt` with faked models (criterion
   positions, free window, greedy context, whole-prompt accounting) and derive pinned token IDs
   on the pinned 1.7B tokenizer.
3. Falsification: each new acceptance test fails against the pre-extension code.
4. `npm test`, `npm run lint`, and the MLX suite stay green; MLX stays out of the default path.
