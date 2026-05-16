# Release and Archive Route

Enable this route when the repository publishes tagged releases, keeps historical documents, or has public surfaces that should not be silently rewritten.

Start with [`archive-policy.md`](archive-policy.md). Add release notes, changelog rules, or release workflows only when the project actually releases artifacts.

## Sample

```text
Strict SDK:
  keep archive-policy.md
  copy optional/github/workflows/release.yml to .github/workflows/release.yml
  require changelog entries for public API changes

Micro demo:
  delete this route
```
