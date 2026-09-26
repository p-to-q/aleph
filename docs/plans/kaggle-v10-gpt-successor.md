# Kaggle Task v10 GPT-only successor authority

- Status: contract-only; no activation or paid dispatch is authorized by this commit
- Tracking issue: [#96](https://github.com/p-to-q/aleph/issues/96)
- Predecessor incident: [#95](https://github.com/p-to-q/aleph/issues/95)
- Parent queue: [#93](https://github.com/p-to-q/aleph/issues/93)
- Target protocol: Aleph-Bench `0.2.0`
- Last updated: 2026-09-26

## Decision

Continue the exact private Kaggle Task v10 from its immutable, permanently broken v1 control
root through a new one-shot authority. This successor authorizes only original order 3,
`gpt-5.4-mini-2026-03-17`, and at most one paid scheduling POST in its entire lifetime. Original
orders 4–6 retain their identities and relative order as future work, but this policy does not
authorize them. Each later model requires another reviewed, content-addressed stacked policy.

The narrower authority is intentional. It keeps the migration, imported budget ledger, paid
boundary, and terminal evidence gate reviewable without pretending that a replacement policy may
silently clear a predecessor breaker.

## Facts retained from the predecessor

The v1 root remains byte-for-byte immutable. Its checked-in predecessor manifest is
[`bench/config/kaggle-capture-queue-predecessor-v1.json`](../../bench/config/kaggle-capture-queue-predecessor-v1.json),
SHA-256 `3eaf32b51638730aa269d9b5fda3775b57f1c6895720b083f1859d0053225ad2`.
It pins the exact closed-world file set, private modes, single-link files, root identity, old policy,
execution commit, two durable paid-call claims, two decisions and journals, both verified capture
bundles, Grok terminal/completion receipts, and the permanent breaker.

The manifest also makes absences first-class facts:

- Gemma has no terminal-quota or completion receipt;
- original order 3 and later have no predecessor artifacts or paid-call claims; and
- a delayed account-wide quota read must never be relabeled as Gemma terminal evidence.

The successor imports this ledger from the verified predecessor decision timestamps:

| Original order | Model | Decision time | Successor accounting |
|---:|---|---|---:|
| 1 | `grok-4.20-0309-non-reasoning` | `2026-09-25T17:30:44.070006Z` | `$0.25` declared policy debit; separate v1 terminal upper bound retained |
| 2 | `gemma-4-31b-it` | `2026-09-25T17:34:25.401999Z` | `$0.05` declared policy debit only; terminal cost unknown |

`$0.05` for Gemma is a conservative policy debit, not actual cost, terminal evidence, or a
provider-side hard cap. The controller must dynamically include each imported debit only while its
decision timestamp is inside the rolling 24-hour window. A migration-time `2 / $0.30` observation
may be recorded for audit, but it is never a permanent rolling-window state.

## Machine contract

The successor policy is
[`bench/config/kaggle-capture-queue-successor-v1.json`](../../bench/config/kaggle-capture-queue-successor-v1.json),
SHA-256 `56695a3e350b1fa58501d0673e3524c98a07a7510748c671943bf5b775cd9771`.
It fixes:

- the exact three-run remote starting set: creation `3193338`, Grok `3201166`, and Gemma
  `3201633`, all completed;
- one exact GPT catalog version, its deterministic paid-call claim, and all fixed new-root paths;
- `maxSuccessorDispatchesTotal=1`;
- `maxSuccessorDispatchesPerRollingWindow=1`;
- `maxCombinedDispatchesPerRollingWindow=3` including imported predecessor decisions;
- one paid scheduling POST per controller invocation;
- a rolling interval of `(now - 24h, now]`, declared spend equal to the selected debit plus active
  prior debits, and conservative spend equal to the maximum of that sum and coherent observed
  usage increase plus the selected debit; the projected value must remain strictly below `$1.00`;
- fresh daily/monthly reserve, refill-consistency, rolling-spend, and post-run terminal-quota
  gates; and
- fixed false score, result, leaderboard, publication, and Hugging Face eligibility.

The policy is a data contract, not executable authority by itself. A merged file, its digest, or a
chat instruction does not authorize a call.

## Root and activation protocol

Activation uses a brand-new fixed destination leaf. The activator must reject a destination that
already exists, including a partial root from an earlier attempt. It must never adopt, repair,
truncate, clear, rename, or overwrite either root.

The only permitted write order is:

1. create the private successor leaf and its durable `0600` lease marker;
2. write the durable activation intent;
3. copy the original creation journal byte-for-byte to its operational successor path;
4. write a content-addressed migration receipt after full predecessor and live read-only
   verification; and
5. write the activation-final marker last, binding the intent, receipt, policy, merged execution
   commit, root identity, and lock identity.

Every intermediate file is `0600`; every directory is `0700`; every authority file must have one
hard link. If the process stops after creating the destination but before activation-final, that
root is a retained failure artifact and can never become runnable. The controller may load a
complete activation but may not create or repair activation files.

The predecessor root is opened once, matched to externally supplied device/inode pins, and held by
shared advisory lease. All descendant reads are descriptor-relative and no-follow. The successor
root is opened and locked separately. The lock order is always predecessor shared lease then
successor exclusive lease. This is a same-host safety contract, not a distributed lock; one fixed
predecessor root, one fixed successor root, and one writer host remain operator invariants.

## Read-only predecessor verification

Neither activation nor the successor controller may call the v1 queue scanner or finalizer. Those
paths can write terminal/completion artifacts and therefore cannot be used to verify Gemma's
incomplete predecessor state.

A dedicated pure verifier must, from the pinned predecessor directory descriptor:

- compare the exact closed-world file and directory sets with the predecessor manifest;
- reject symlinks, hard links, wrong owner/mode, aliases, root replacement, or unstable reads;
- validate canonical JSON and every manifest digest/byte count;
- validate the old sentinel, breaker, policy, execution, creation authority, two paid-call claims,
  decisions, journals, Grok terminal/completion chain, and both closed-world capture bundles;
- prove Gemma terminal/completion and all order-3-plus predecessor paths remain absent; and
- return a semantic ledger without writing a byte to the predecessor root.

The activator writes that verified state into the migration receipt. Each controller invocation
and the final paid guard then re-runs the predecessor verification. The receipt records the
verification; it does not replace the source bytes or self-prove its own inputs.

## One-shot controller

The successor gets its own parser and controller. The v1 controller intentionally hard-codes six
entries and its v1 policy identity, so conditional reuse would risk importing invalid assumptions.
Shared low-level filesystem and quota helpers may be extracted only with unchanged v1 regression
coverage.

A dry-run is a separate read-only entry point. It verifies policy, execution, both roots,
activation-final, migration receipt, source, catalog, quotas, and the exact three-run set, then
reports GPT as the sole eligible entry. It performs zero writes and cannot receive a scheduler
callable.

The live controller may cross the paid boundary only after it:

- repeats every dry-run check;
- dynamically recomputes imported rolling decisions at the current UTC instant;
- writes and fsyncs one new successor decision binding the migration receipt and empty
  `priorSuccessorEntries`;
- repeats predecessor, activation, execution, catalog, quota, and remote exact-run-set validation
  in the scheduler's final guard; and
- delegates one time to the reviewed one-shot scheduler with zero paid retry.

After GPT is scheduled, a second invocation may only reconcile that exact journal and run. Kaggle
`COMPLETED` is insufficient. Clean exhaustion requires a verified closed-world GPT bundle, a fresh
terminal-quota receipt fetched after evidence verification, and a completion receipt binding all
prior artifacts. Any further scheduling request is outside this policy.

## Permanent failure and mutation boundaries

Authority, identity, predecessor, activation, catalog, quota, run-set, scheduler, evidence, or
cost drift permanently breaks this successor policy. The breaker is written only to the already
trusted successor root. If the predecessor pathname is replaced or its identity cannot be proven,
the replacement predecessor path receives no write.

A true extra, missing, duplicate, wrong-model, errored, or unknown-state remote run is a no-call
failure. A queued/running GPT bound to the one durable successor journal is a hold. A temporary
read failure is a hold only when the source's error contract proves it is availability-related;
integrity ambiguity is a breaker.

## Reviewable PR stack

1. **Filesystem capability PR:** pinned descriptor-relative/no-follow read primitives and an
   fd-based bundle loader; no policy, activation, or paid behavior.
2. **Authority/activation PR:** predecessor manifest, successor policy, pure verifier, and one-shot
   activator; no scheduler import and no paid entry point.
3. **Controller PR:** separate dry-run and GPT-only controller with budget, concurrency,
   mutation/race, and paid-boundary tests.
4. **Operational activation:** only after all PRs merge and CI passes, create the real successor
   root once, read back the merge SHA and hashes, then update and unpause the saved automation.
5. **Future tail:** after GPT terminal completion, create a new stacked authority for original
   order 4. Orders 5 and 6 remain separately reviewable.

## Validation gates

Before activation:

- canonical policy and manifest parsing plus semantic mutation tests;
- predecessor root/file/bundle/claim/absence verification tests;
- destination-preexists, source/destination-alias, double-activation, every-fsync-stop, root
  replacement, descendant symlink/hard-link, and bundle swap tests;
- two consecutive dry-runs proving zero writes and zero paid POSTs;
- exactly one happy paid-boundary test and zero paid calls for every failure case;
- dynamic rolling-window tests before, at, and after each imported timestamp boundary;
- complete benchmark unit suite, repository lint, deterministic source generation check, and
  `git diff --check`.

After merge, live activation and GPT dispatch each require separate durable readback. Until then,
the existing Kaggle automation remains paused.

## Publication boundary

This is six-call transport/capture evidence, not a benchmark score. It cannot create or update a
public Kaggle leaderboard row, Hugging Face result, model card score, rank, or quality claim.
Canonical replay, numeric scoring, full coverage, and publication remain separately gated by
issues #59, #77, and #78.
