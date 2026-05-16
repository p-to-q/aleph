# Template Forms

This template contains three types of files. Treating them differently prevents unnecessary complexity.

## 1. Blank templates

Blank templates are meant to be rewritten.

Examples:

- `docs/project-brief.md`
- `docs/glossary.md`
- `optional/decisions/adrs/TEMPLATE.md`
- `optional/decisions/rfcs/TEMPLATE.md`
- `optional/research/briefs/TEMPLATE.md`
- `optional/exec-plans/active/TEMPLATE.md`

Sample use:

```text
Replace placeholders with project truth before publishing.
If the project does not need the lane, delete the directory or keep only a disabled README.
```

## 2. Structural templates

Structural templates define a directory shape or workflow surface. They should be customized, not blindly copied.

Examples:

- `.github/ISSUE_TEMPLATE/`
- `.github/workflows/`
- `docs/handoff/`
- `optional/agent-rules/cursor/`

Sample use:

```text
Keep the shape when the workflow exists.
Remove issue templates, workflows, or stack rules that do not correspond to real project behavior.
```

## 3. Instructional templates

Instructional templates are operating contracts. They should be short, maintained, and accurate.

Examples:

- `docs/engineering-discipline.md`
- `docs/agent-rules.md`
- `AGENTS.md`
- `PROMPT.md`
- `WORKFLOW.md`
- `CONTRIBUTING.md`

Sample use:

```text
Keep the instruction only if people will follow it.
If the project is too small for the instruction, delete it or mark it disabled.
```
