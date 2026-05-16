# Route Deletion Checklist

Use this after copying the template.

## Checklist

- [ ] Profile chosen in README and docs/project-scale.md.
- [ ] Blank templates rewritten or deleted.
- [ ] Unused workflows deleted or disabled.
- [ ] Unused issue templates deleted.
- [ ] Unused ADR/RFC/research/exec-plan routes deleted or parked.
- [ ] Stack-specific agent rules match actual stacks.
- [ ] CODEOWNERS has real maintainers.
- [ ] License owner and NOTICE updated.
- [ ] CI commands match the project.
- [ ] Template checks still pass.

## Sample

```text
If there is no Python code, delete optional/agent-rules/cursor/stacks/backend-python.mdc.
If there is no release process, delete .github/workflows/release.yml.
```
