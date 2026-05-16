# Profiles

Profiles are copy-edit guides. They are not generators and do not hide repository state.

Use one of four modes:

- `micro.md`
- `standard.md`
- `strict.md`
- `research-strict.md`

Then apply [`docs/router.md`](../../docs/router.md): keep called routes and delete, park, or disable uncalled routes.

## Sample selection

```text
Is this a short-lived experiment?       -> micro
Is this a reusable public repo?         -> standard
Will decisions affect future users?     -> strict
Will research or agents drive delivery? -> research-strict
```

Start lower. Promote when the project earns more process.
