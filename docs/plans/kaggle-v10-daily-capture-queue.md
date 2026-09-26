# Kaggle Task v10 finite capture queue

- Status: permanently stopped at entry 2 by v1 breaker
  `6e0b53a09431d8ffa6008ed28bb7d7d8387c979b141b3cac0cff6351c3e6d33a`; the frontier fix in
  [#95](https://github.com/p-to-q/aleph/issues/95) does not clear or reactivate this policy
- Tracking issue: [#93](https://github.com/p-to-q/aleph/issues/93)
- Successor plan: [GPT-only one-shot authority](kaggle-v10-gpt-successor.md), tracked by
  [#96](https://github.com/p-to-q/aleph/issues/96)
- Parent: [#59](https://github.com/p-to-q/aleph/issues/59)
- Formal-score blockers: [#77](https://github.com/p-to-q/aleph/issues/77) and
  [#78](https://github.com/p-to-q/aleph/issues/78)
- Target protocol: Aleph-Bench `0.2.0`
- Last updated: 2026-09-26

## Objective

Run one finite, reviewable sequence of private six-call transport/capture canaries on the exact
reviewed Kaggle Task v10. The sequence broadens provider/runtime compatibility evidence without
turning routine automation into an open-ended spender or confusing a captured response with a
benchmark score.

This section records the original v1 objective. Operationally, v1 dispatched and retained Grok
and Gemma, then latched its permanent breaker before Gemma terminal finalization. No remaining
entry in this policy is authorized. The checked-in policy and this plan are retained as immutable
history; continuation requires the separately reviewed successor authority linked above.

This policy is deliberately narrower than “use the available quota.” It authorizes only six exact
catalog versions, at most one paid scheduling request per invocation, with closed-world evidence
required before the next entry and a permanent breaker for the policy version after any material
failure.

## Starting authority and completed baseline

The queue begins from this immutable capture authority:

- repository authority commit `0194da92218d3e3896e5cabb10595f2fac1620dd`;
- Task `jahyee/aleph-bench-v0-2-capture-canary/10` and source kernel `135410138`;
- creation-journal SHA-256
  `f6c4360dc843bede4e6020dece9ee5e91f7b2e8935ce819c1600cb8dc219f672`;
- generated source SHA-256
  `df9a9cd7387df5392c07c11a88149001e3cdaf67551c35b14530690c1f4ee0db`;
- deterministic notebook SHA-256
  `5f4103d304c057ec3e100d6750ff4052c41b7b3961c85d3c09fb7e14d6d04071`;
- private dataset `jahyee/aleph-bench-v02-scorer-conformance`;
- internal capture generation `4`, capture schema `1.2.0`, timeout `180` seconds, and zero
  transport retries; and
- exact initial run set containing only run `3193338`, model version `gemini-3.7-flash`, in state
  `BENCHMARK_TASK_RUN_STATE_COMPLETED`.

Creation run `3193338` used `gemini-3.7-flash` and completed all six planned calls. Its retained
payload is capture-complete and canonical-replay-eligible, with evidence id
`aleph-bench-kaggle-capture-evidence-v1-artifact-ee79c5e1ffe8f5c4b289dd8ccbe70320ccb79bde0395f4b5010c2aebe05d8ed0`.
It intentionally has no dispatch-journal catalog authority, so `assemblyEligible=false`. It is the
creation baseline, not a queue member, score, result, leaderboard row, or publication candidate.

## Decision and activation boundary

The machine policy is
[`bench/config/kaggle-capture-queue-v1.json`](../../bench/config/kaggle-capture-queue-v1.json).
Its exact file bytes are part of every decision receipt. The policy becomes executable only after:

1. this plan, the machine policy, the single-step controller, and its fail-closed tests merge;
2. the final private control root is created once and its POSIX device/inode are captured as
   external activation pins rather than recomputed by each invocation;
3. the saved automation is updated through its API with the exact merge commit, policy path and
   SHA-256, private control-root path and activation pins, ordered queue, budget limits, and
   breaker semantics;
4. the saved automation is read back and matches those values; and
5. a fresh invocation revalidates Task, source, creation receipt, run set, catalog, quota, control
   root, prior evidence, expiry, and policy bytes before the paid boundary.

The merge does not itself dispatch a model. A stale checkout, unmerged policy, changed policy
digest, or prompt-only restatement is not authority.

## Exact ordered queue

Kaggle's live catalog exposed each listed parent and version as published, default, proxy-enabled,
and not deprecated when #93 was opened. The API did not expose a frozen or immutable flag, so this
policy makes no such claim. Every field is re-read and must match byte-for-byte before dispatch.

| Order | Canonical version slug | Model/version IDs | Exact Model Proxy slug | Declared worst case and post-run breaker |
|---:|---|---:|---|---:|
| 1 | `grok-4.20-0309-non-reasoning` | `146` / `144` | `xai/grok-4.20-0309-non-reasoning` | `$0.25` |
| 2 | `gemma-4-31b-it` | `140` / `138` | `google/gemma-4-31b` | `$0.05` |
| 3 | `gpt-5.4-mini-2026-03-17` | `138` / `136` | `openai/gpt-5.4-mini-2026-03-17` | `$0.05` |
| 4 | `qwen3-235b-a22b-instruct-2507` | `62` / `67` | `qwen/qwen3-235b-a22b-instruct-2507` | `$0.25` |
| 5 | `gemini-3.8-flash` | `170` / `168` | `google/gemini-3.8-flash` | `$0.10` |
| 6 | `claude-sonnet-4-5-20250929` | `71` / `75` | `anthropic/claude-sonnet-4-5@20250929` | `$0.25` |

The order is binding. Each exact catalog version may be scheduled at most once on Task v10. The
Anthropic tail is quarantined: entries 1–5 must first pass the full evidence gate, more than 24
hours must have elapsed since the preceding queue dispatch, no other queue dispatch may fall in
its rolling 24-hour window, and a coherent DAILY allowance/usage reset must be proved.

These models are outside phase 1:

- `gemini-3.7-flash`, because it is already the v10 creation run;
- `gpt-5.4-nano-2026-03-17`, because it is already the current v9 evidence;
- `claude-haiku-4-5-20251001`, because its retained timeout is a permanent no-retry result;
- `qwen3-coder-480b-a35b-instruct` and `gpt-oss-120b`, because each has a retained first-call
  `RateLimitError`; and
- `glm-5` and `deepseek-r1-0528`, because each has retained near-cap invalid capture evidence.

No alias, wildcard, provider guess, case folding, punctuation normalization, suffix normalization,
mutable `latest`, or dynamic catalog selection may add or substitute a model.

## Single-step controller contract

The queue controller is a policy layer over the reviewed `bench.engine.kaggle_run_once`; it is not
a second scheduler. A single invocation either returns a read-only held/exhausted decision or
delegates exactly once to that scheduler. It must never call the generic
`kaggle benchmarks tasks run` path.

Before delegation, it writes and fsyncs a decision receipt binding:

- exact policy bytes and SHA-256 plus the running merged repository commit;
- one private control root, original creation receipt, and writer host;
- the fresh Task/source/notebook/run-set and exact catalog observations;
- fresh complete `DAILY` and `MONTHLY` quota records, including their raw `refillTime`
  observations;
- prior queue journals, evidence ids and member digests; and
- the selected entry and its new planned journal and bundle paths.

The controller supplies a final pre-dispatch guard to the existing scheduler so authority, quota,
run set, policy bytes, and prior evidence are checked again after the scheduler's own fresh reads
and immediately before its durable claim and one paid scheduling POST. A failed guard creates no
claim, run journal, or model call.

All retained artifacts live under the one private operator-supplied control root. The policy fixes
each entry's decision, journal, evidence-bundle, terminal-quota, and completion-receipt relative
paths. The controller verifies the local root's private mode and sentinel identity, exact creation-
receipt bytes, path containment, and new selected-entry paths; an unexpected local sentinel or
remote run-set change trips the breaker. Repository paths and public docs never contain the private
absolute root.

Before any control-root receipt read, the controller requires the live pathname to match the
device/inode captured once at activation. It rechecks that external pin against the opened and
locked directory descriptor, at paid preflight, and after the scheduler returns. A mismatch exits
without writing a breaker into the untrusted replacement path. One non-blocking POSIX advisory
lease on that private control-root directory inode is held from the first trusted control-root read
through journal validation after any paid POST. The controller also
retains `.aleph-kaggle-v10-queue.lock` as a private marker, locks it, and binds its device/inode to
the control-root sentinel. A second process using the same root returns `held`; replacing or
renaming the marker cannot create an independent lease or let that process classify the first
writer's durable decision as an orphan while the first writer is between decision and POST. A
process loss releases both advisory locks, and the next invocation permanently breaks on marker
identity drift, an orphan decision, or an ambiguous journal. The marker is synchronization state,
not benchmark evidence.

The queue passes that already-open root descriptor—not a freshly resolved pathname—into the
one-shot scheduler. Creation-receipt reads, the receipt-local paid-call claim, initial run journal,
and every journal replacement use descriptor-relative no-follow traversal with owned `0700`
directories and owned single-link `0600` files. A descendant alias introduced before or after the
final guard cannot redirect a retry barrier outside the activated root: it either fails before the
paid POST or arrives after the anchored claim and journal barriers are already durable.

This is not a distributed lock. A copied receipt or a writer on another host does not share the
local filesystem claim. One original receipt, root, and writer host remain operator invariants; if
there is any reason to suspect they were violated, stop and reconcile the exact remote run set
read-only. Never rename, replace, rotate, copy, or repoint the live control-root pathname while the
policy is active. The activation pin prevents a replacement directory from becoming a second
controller root, while directory-inode locking serializes users of the original root. Never update
the saved device/inode merely because a later invocation observes different values; that is a
security failure requiring read-only reconciliation and a new reviewed activation decision.

Every invocation also reads the complete exact v10 run set. It must equal the creation baseline,
all verified completed entries, and at most the one journal-bound pending run. `QUEUED` or
`RUNNING` is a recoverable hold. Provider `ERRORED`, an unknown state, a missing/extra run, or
platform `COMPLETED` without a complete Aleph evidence envelope is a permanent breaker. The exact
run-specific `*-evidence.json` file—not existence of its parent directory—is the bundle-ready
marker because the binder writes that envelope last. An empty or partially populated directory
never authorizes loading, finalization, or another dispatch.

The operator/automation sequence is serial: poll read-only; when the exact run is completed, run
the reviewed capture-evidence binder to completion and verify the closed-world bundle; only then
invoke the queue controller to retain terminal quota, write completion, and consider the next
entry. The binder and controller must never overlap on the private root. This sequencing rule is
part of the one-writer-host invariant; the queue lock does not coordinate unrelated tools or
another host.

## Serial, quota, and budget gates

- At most one paid scheduling POST is allowed per controller invocation and heartbeat.
- At most three queue entries may be dispatched in any rolling 24-hour interval, counted from the
  immutable decision receipts. Local date and midnight never reset this count.
- Only one run may be active, queued, unknown, or awaiting complete evidence on Task v10.
- Before dispatch, the selected entry's declared worst-case cost must leave at least
  `max($2.00, 20% of DAILY allowance)` and 20% of MONTHLY allowance.
- The conservative rolling-spend upper bound is the greater of (a) the sum of declared worst-case
  costs for queue decisions in the preceding 24 hours and (b) any coherent observed increase in
  account usage. The latter may include unrelated activity; authorization is held when the upper
  bound reaches `$1.00`.
- Raw `refillTime` is an observation, not a window key. Reads representing one window may differ by
  at most 5 milliseconds. A material DAILY advance must be one 86,400-second period, within the
  same 5-millisecond tolerance, and agree with an unchanged allowance and coherent usage reset. A
  MONTHLY material advance likewise requires the prior refill boundary to have elapsed, an
  unchanged allowance, and a coherent reset into the next service period. An intermediate jump,
  reversal, missing value, allowance change, non-finite money, or ambiguous reset trips the
  breaker. Each comparison binds both reads to after-read UTC observation times: the prior read
  must precede its announced boundary, while the current read must either remain before that same
  boundary or bracket the one accepted period advance. A stale API timestamp observed across a
  boundary never proves a reset.
- The per-entry amounts are conservative preflight reserves and post-run breakers, not hard
  provider-side spend caps. Kaggle exposes no per-run hard cap.

A run or evidence finalization still in progress, a temporarily unavailable required read, a
rolling count, reserve, spend-cap, or not-yet-proved Claude reset produces `held`, not a breaker.
Only `held` may be reevaluated after the relevant remote state or time advances and fresh live quota
remains consistent. A later quota refill never clears a breaker and never makes a failed exact model
retryable.

## Evidence before the next entry

Every earlier queue member must have all of the following before the next model is selected:

- canonical dispatch journal state `reconciled`;
- one exact terminal Task/run/model/catalog binding;
- exact journal-bound evidence and the byte-identical retained dispatch receipt;
- successful closed-world bundle reload and full envelope verification;
- `captureComplete=true`, `canonicalReplayEligible=true`, and `assemblyEligible=true`; and
- an immutable completion receipt binding the decision, reconciled journal, verified evidence
  members, and a separately fetched terminal-quota receipt; and
- a fresh post-terminal cost observation below the entry's breaker.

Platform `Completed`, a Task URL, quota movement, raw strings alone, an unbound envelope, or the
creation run cannot satisfy this gate.

The scheduler's immediate `quotaAfter` is retained only as a scheduling observation: it may have
been sampled while the new run was still queued and cannot finalize cost. The independent terminal-
quota receipt is fetched only after the run is terminal and its evidence bundle passes closed-world
verification. The completion receipt content-binds all prior artifact digests and is required even
for the sixth entry before clean exhaustion may be declared.

## Permanent circuit breaker for v1

Any ambiguous, unscheduled, returned-but-unreconciled, contradictory, partial, timed-out,
rate-limited, provider-failed, missing-usage, empty, non-string, oversized, near-cap, or otherwise
invalid capture ends this policy version. So does drift in source, notebook, receipt, Task, dataset,
SDK, timeout/retry settings, catalog, run set, bundle, evidence, quota, allowance, control root,
local writer sentinel, actual cost, or policy digest.

Retain the exact failure and notify once. Automation then remains read-only. It may resume only
under a new policy id and digest merged through review. It must not clear the breaker at another
heartbeat, after a quota refill, or by changing the journal path.

## Score and publication boundary

Every queue call uses the six-call `transportCanary` scope with no scorer and no numeric return.
All artifacts have fixed false score, result, canonical-scoring-input, leaderboard, publication,
and Hugging Face eligibility. They cannot support a rank, metric, scalar, benchmark-result, or model
quality claim.

A formal result still requires #59, #77, #78, a separately reviewed numeric Task and run plan,
complete canonical coverage, Python 3.13/UCD 15.1 replay, and an explicit publication issue/PR.
This policy authorizes no public Kaggle or Hugging Face mutation, 30-call rehearsal, or 900-call
formal run.

## Completion and expiry

The policy expires at `2026-10-25T00:00:00Z`; the boundary is exclusive for every new paid
transition. At and after that boundary the controller must still reconcile any existing journal,
remote run, breaker condition, evidence bundle, terminal quota, and completion receipt; expiry may
not hide an ambiguous/provider-failed run or strand already-paid valid evidence. It returns
`expired` only when reconciliation leaves a not-yet-dispatched next entry, `exhausted` only after
all six entries have verified completion receipts, and permanently broken after a listed failure.
Every state is read-only except an authorized next-entry transition; only a temporary `held` state
may clear automatically. Keep #93 open while the queue is live. Record one durable issue comment
per terminal entry with exact identities, hashes, calls, eligibility, quota, and the phrase
“capture evidence, not a score.” Close the issue only after clean exhaustion or after the retained
breaker and next authority decision are documented.

## Validation gate

Before activation, the implementation must prove with local fake SDK/filesystem tests that every
identity, source, catalog, quota, count, active-run, prior-evidence, expiry, concurrency, and breaker
failure makes zero paid calls. The sole happy path must make exactly one paid call and cannot select
the second entry until exact closed-world evidence and terminal completion receipt for the first
pass. Tests must cover the 5-millisecond same-window tolerance, valid period advance, intermediate
or reversed refill drift, rolling 24-hour boundary, and prove that local midnight does not reset
authorization. They must also cover lock-marker mode and inode replacement while another process
holds the root lease, full control-root pathname replacement against externally pinned
device/inode, the validation-to-open race, and descendant path replacement after the final guard,
plus reconciliation/finalization at the exclusive expiry boundary. Platform
`Completed` with incomplete Aleph evidence must set the breaker.

Run the focused queue/scheduler/evidence tests, the complete benchmark suite, deterministic source
generation check, repository lint, and `git diff --check` without a remote model call. After merge,
read back the updated automation before the first separately recorded queue execution.
