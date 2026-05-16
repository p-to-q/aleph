# Security Policy

## Reporting

Do not open a public issue for a vulnerability. Report security concerns to the maintainers through the private channel configured for this project.

Use GitHub's private security advisory flow:

https://github.com/p-to-q/repo-template/security/advisories/new

Include reproduction steps, affected files or workflows, and your impact assessment.

## Supported versions

This template does not define a release matrix. Projects adopting it should fill in the supported branches, package versions, or deployment channels before accepting external users.

## Scope

Security-sensitive surfaces include:

- authentication, authorization, secrets, tokens, and credentials;
- dependency changes;
- CI/CD workflows and release automation;
- agent workflows that can read or write repository content;
- generated artifacts that are executed or rendered by users.
