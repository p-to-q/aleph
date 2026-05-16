# Micro Profile

Use for small demos, internal experiments, and short-lived prototypes.

## Keep active

- `README.md`
- `LICENSE` / `NOTICE`
- `CONTRIBUTING.md`
- `SECURITY.md` / `SUPPORT.md`
- minimal CI doctor
- PR template

## Park by default

- ADR/RFC lane
- research briefs
- exec plans
- CodeQL
- release workflow
- agent automation

## Sample

```text
A one-file prototype can still keep Apache-2.0, a README, and a PR template.
It does not need ADRs unless the prototype becomes a dependency for others.
```

## Router note

After choosing `micro`, run the checklist in `docs/router.md`. Delete uncalled routes instead of leaving unused process active.

### Sample

```text
Profile: micro
Action: keep matching routes, rewrite blank templates, delete route files that the project will not maintain.
```
