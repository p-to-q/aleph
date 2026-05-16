# Review Gates

This document defines three review passes before treating a template release as ready.

## 1. UI and reader review

Audience: developer, user, early adopter.

Questions:

- Is the repository entrypoint clear within 60 seconds?
- Can a new contributor tell which profile applies?
- Are there too many files for the selected profile?
- Are optional ADR/RFC/research lanes clearly optional?
- Does AGENTS/PROMPT/WORKFLOW help agent use, or does it add ceremony?

### Sample UI review note

```text
Reviewer: early adopter
Profile tested: standard
Clear: yes
Confusing: optional/decisions looked mandatory until project-scale explained otherwise
Action: add one sentence to README profile table
```

## 2. Template and golden-flow review

Audience: maintainer or release operator.

Questions:

- Do all profile/template checks pass?
- Do all README files contain a sample?
- Do local Markdown links pass?
- Does `doctor` catch missing required surfaces?
- Are the scripts dependency-free or clearly documented?
- If the project has real golden outputs, do those project-specific golden tests pass?

Run:

```bash
npm run check:template
npm run lint
```

## 3. Final verification review

Audience: maintainer.

Questions:

- Is the license consistent across files?
- Are source adaptations documented?
- Are known limits explicit?
- Has the ZIP integrity check passed?
- Are external GitHub Actions unverified unless actually run on GitHub?

### Sample final verdict

```text
Verdict: ship candidate
Required fixes: none
Known limits: workflows not run in GitHub Actions; external links not fetched locally
Next step: publish as GitHub template repository
```


## Router review

Before final verification, review the Router decision:

```text
- Is the selected profile named in README or docs/project-scale.md?
- Are uncalled routes deleted, parked, or clearly disabled?
- Are blank templates rewritten?
- Are stack-specific rules present only for stacks the repo actually uses?
- Is WORKFLOW active only if humans/agents will maintain it?
```
