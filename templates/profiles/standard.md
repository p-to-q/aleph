# Standard Profile

Use for reusable packages, small public tools, sites, or early open-source repositories.

## Keep active

- all public health files
- CI, Dependabot, CodeQL
- issue and PR templates
- labels and label documentation
- changelog
- surfaces map

## Optional

- ADRs for API, compatibility, security, license, release, or governance decisions
- AGENTS/PROMPT if contributors regularly use coding agents
- link-check schedule for docs-heavy repos

## Sample

```text
A public package should use standard:
- Dependabot keeps routine updates visible.
- CodeQL and SECURITY.md establish the minimum public security posture.
- ADRs remain optional until the package exposes a stable API.
```

## Router note

After choosing `standard`, run the checklist in `docs/router.md`. Delete uncalled routes instead of leaving unused process active.

### Sample

```text
Profile: standard
Action: keep matching routes, rewrite blank templates, delete route files that the project will not maintain.
```
