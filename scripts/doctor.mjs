#!/usr/bin/env node
/**
 * Template doctor.
 *
 * Checks the default Seed surface. Heavy routes live in optional/ and are
 * checked by router/template checks rather than treated as always-active docs.
 */
import { existsSync, readFileSync } from "node:fs";

const required = [
  "README.md",
  "LICENSE",
  "NOTICE",
  "CONTRIBUTING.md",
  "CODE_OF_CONDUCT.md",
  "SECURITY.md",
  "SUPPORT.md",
  "AGENTS.md",
  "PROMPT.md",
  "WORKFLOW.md",
  "docs/index.md",
  "docs/project-brief.md",
  "docs/project-scale.md",
  "docs/router.md",
  "docs/template-forms.md",
  "docs/agent-rules.md",
  "docs/engineering-discipline.md",
  "docs/labels.md",
  "docs/license-policy.md",
  "docs/review-gates.md",
  "docs/checks.md",
  "checks/profile-matrix.json",
  "templates/profiles/micro.md",
  "templates/profiles/standard.md",
  "templates/profiles/strict.md",
  "templates/profiles/research-strict.md",
  "templates/router/README.md",
  ".github/PULL_REQUEST_TEMPLATE.md",
  ".github/dependabot.yml",
];

const missing = required.filter((file) => !existsSync(file));
if (missing.length) {
  console.error("Missing required Seed files:");
  for (const file of missing) console.error(`- ${file}`);
  process.exit(1);
}

for (const optionalRoute of [
  "optional/decisions/README.md",
  "optional/research/README.md",
  "optional/exec-plans/README.md",
  "optional/history/README.md",
  "optional/github/README.md",
  "optional/agent-rules/README.md",
]) {
  if (!existsSync(optionalRoute)) {
    console.error(`Missing optional route README: ${optionalRoute}`);
    process.exit(1);
  }
}

const readme = readFileSync("README.md", "utf8");
if (!readme.includes("Seed") || !readme.includes("repo-template")) {
  console.error("README.md should position this repository as a Seed while retaining the repo-template name.");
  process.exit(1);
}

const pkg = JSON.parse(readFileSync("package.json", "utf8"));
if (pkg.license !== "Apache-2.0") {
  console.error("package.json license should default to Apache-2.0.");
  process.exit(1);
}

const license = readFileSync("LICENSE", "utf8");
if (!license.includes("Apache License") || !license.includes("Version 2.0")) {
  console.error("LICENSE should contain Apache License, Version 2.0 text.");
  process.exit(1);
}

console.log(`Template doctor passed (${required.length} active files and optional route READMEs checked).`);
