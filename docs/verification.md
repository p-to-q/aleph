# Verification

This file records the latest local verification for the template package.

## Latest local check

v0.4.0 local checks passed:

```text
npm run lint                  PASS
node scripts/doctor.mjs       PASS
node scripts/check-links.mjs  PASS
node scripts/check-template.mjs PASS
node scripts/check-router.mjs PASS
JSON parse                    PASS
YAML parse                    PASS
```

## Expected local checks

```sh
npm run lint
node scripts/doctor.mjs
node scripts/check-links.mjs
node scripts/check-template.mjs
node scripts/check-router.mjs
python - <<'PY'
import json, pathlib, yaml
json.loads(pathlib.Path('package.json').read_text())
json.loads(pathlib.Path('checks/profile-matrix.json').read_text())
for root in ['.github', 'optional']:
    for p in pathlib.Path(root).rglob('*.yml'):
        yaml.safe_load(p.read_text())
    for p in pathlib.Path(root).rglob('*.yaml'):
        yaml.safe_load(p.read_text())
PY
```

## Review gates

- UI review: developer, user, and early adopter can understand README, Router, and profile choice.
- Template/golden review: profile matrix, router route expectations, internal docs links, and any project-specific golden tests pass.
- Final verification: package, JSON/YAML, local checks, and ZIP integrity pass.

## Known limitations

- GitHub Actions workflows still need to be tested in a real GitHub runner after publishing.
- Optional workflows under `optional/github/` are not active until copied into `.github/workflows/`.
- External links are not fetched by the local Markdown checker.
- GitHub private vulnerability reporting depends on security advisories being available for `p-to-q/repo-template` after publishing.

## Sample release note

```text
Verdict: ship candidate
Profile tested: template seed before adoption
Known limits: GitHub Actions not run on hosted runner; external links not fetched
Next step: publish as p-to-q/repo-template and mark as GitHub template repository
```
