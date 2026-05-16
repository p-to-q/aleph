# Source Ledger

This repository is an adapted template, not a verbatim mirror. The source ledger records what was inspected and how it was transformed.

## Source status

| File family | Source status | Notes |
| --- | --- | --- |
| `LICENSE` | standard upstream text | Apache-2.0 text is intentionally unmodified. |
| GitHub workflows/config | adapted source | Rewritten as lightweight seeds with comments; project-specific Wittgenstein commands removed. |
| `AGENTS.md`, `PROMPT.md`, `WORKFLOW.md` | adapted source | Preserves human/agent contract shape; removes codec/modality specifics. |
| `docs/engineering-discipline.md` | adapted source | Preserves discipline principles; removes Wittgenstein-only architecture doctrine. |
| ADR/RFC/research/handoff docs | adapted structure | Kept as optional lanes and templates. |
| Profile/router docs | new template content | Derived from the research conclusion, p-to-q lightweight repos, and route cleanup needs. |
| Agent/Cursor rules | adapted source | Cross-filled from `Jah-yee/cursor-rules`; kept optional under `optional/agent-rules/` so Cursor is not required. |

## Primary source surfaces

| Source | What was observed | Template adaptation |
| --- | --- | --- |
| `p-to-q/.github/profile/README.md` | p-to-q tone: experimental craft, human-readable interfaces, flat/simple patterns | Reflected in the template's lightness, printable docs, and visible files over hidden machinery. |
| `p-to-q/wittgenstein` root | README route split for humans vs agents; public health files; Apache-2.0; AGENTS/PROMPT/WORKFLOW | Generalized into public entrypoints and human/agent workflow without modality-specific architecture. |
| `p-to-q/wittgenstein/docs/engineering-discipline.md` | read-before-write, smallest effective change, receipts, no self-ratification, no drive-by refactor | Rewritten as a profile-aware discipline doc. |
| `p-to-q/wittgenstein/.github` | CODEOWNERS, PR template, issue templates, Dependabot, labelers, workflows | Preserved as lightweight GitHub automation with comments explaining intent. |
| `p-to-q/wittgenstein/docs/research/briefs/K_orchestration_prior_art.md` | Brief K adopted OpenAI Symphony's `WORKFLOW.md` contract but not the runtime | Preserved as the sourcing rationale for `WORKFLOW.md`. |
| `p-to-q/wittgenstein/docs/handoff/workflow-md-spec.md` | Handoff brief specified the exact WORKFLOW contract shape and read order | Preserved as the reason handoff briefs are first-class. |
| `p-to-q/wittgenstein/docs/adrs/0017-orchestration-workflow-contract.md` | Ratified the orchestration contract | Template keeps `WORKFLOW.md` optional for `research-strict`, not mandatory for all repos. |
| `p-to-q/wittgenstein/docs/labels.md` and ADR-0019 | Labels are contracts; prefixed queues encode status/priority/size/stage/slice | Template keeps a smaller type/status/priority/size/slice label set. |
| Wittgenstein issues/PRs | Research ledgers, maintainer re-audit loops, owner review, dependency and receipt PRs | Captured in `optional/history/issue-pr-ledger.md` as patterns to preserve, not copied task lists. |
| `Jah-yee/cursor-rules` | Cursor/User/Project rule split; repository-first behavior; smallest correct change; no drive-by refactor; optional stack rules | Added `docs/agent-rules.md` and optional Cursor-compatible seeds under `optional/agent-rules/cursor/`. |
| `p-to-q/carburetor` | Artifact/product README with receipts, editions, docs map, implementation status, Apache-2.0 | Reinforced lightweight public README pattern and receipts-over-claims guidance. |
| `p-to-q/centrifuge-sort` | One-file artifact repo with source-shaped public reference | Reinforced `micro` mode and one-file artifact support. |
| `p-to-q/site` | Public site repo with short thesis and minimal engineering route | Reinforced lightweight public surface pattern. |
| `p-to-q/flatus` | Product README with install path, samples, known limitations, docs map, release notes, Apache-2.0 | Reinforced receipts, limitations, release/user-facing docs guidance. |
| GitHub Docs: template repositories | A template repo generates new repositories with the same directory structure and files | Template stays file-first and avoids hidden state. |
| GitHub Docs: repository best practices | README, license, contribution guidelines, code of conduct, SECURITY.md, Dependabot, code scanning | Template includes these as public and security defaults. |

## Change policy

When copying or adapting more material from a source repository:

1. Keep the originating URL or repository path in this ledger.
2. Remove project-specific doctrine unless this template itself needs it.
3. Add a short note explaining why the file exists.
4. Prefer small, readable files over hidden generators.
5. Do not claim a file is verbatim unless it is.

## Sample source note

```markdown
<!-- Source note: adapted from p-to-q/wittgenstein WORKFLOW.md.
     We keep the issue/agent contract shape but remove Wittgenstein-specific modality routing. -->
```


## What changed in v0.4

- Kept the repository name as `repo-template` but positioned it as a Seed in README and docs.
- Moved heavy routes from active `docs/` / `.github/` surfaces into `optional/`: decisions, research, exec plans, history, strict workflows, release/archive, and agent rules.
- Renamed generic `golden` checks to template checks under `checks/`; projects can still add real golden tests when outputs require them.
- Shortened the active documentation map and made `docs/router.md` the main deletion/retention contract.
- Added `optional/README.md`, `optional/github/README.md`, and `optional/release/README.md` so parked routes remain understandable without being active.
- Expanded `docs/content-sync.md` with a cross-link contract to keep README, Router, docs, agent prompts, and optional routes aligned.

## What changed in v0.3

- Added Router guidance so unused routes can be deleted rather than left as dead process.
- Collapsed agent-heavy into `research-strict` while keeping AGENTS/PROMPT/WORKFLOW first-class.
- Added optional Cursor-compatible rule seeds under `optional/agent-rules/cursor/`.
- Expanded engineering discipline with repository-first behavior, architecture conflict resolution, robustness, validation order, and stack-specific routing.
- Added template forms: blank, structural, and instructional.
