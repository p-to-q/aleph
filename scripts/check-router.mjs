#!/usr/bin/env node
/**
 * Router check.
 * Ensures the profile/router docs and template matrix stay in sync.
 */
import { readFileSync, existsSync } from "node:fs";

const profiles = ["micro", "standard", "strict", "research-strict"];
const router = readFileSync("docs/router.md", "utf8");
const scale = readFileSync("docs/project-scale.md", "utf8");
const readme = readFileSync("README.md", "utf8");
const matrix = JSON.parse(readFileSync("checks/profile-matrix.json", "utf8"));

for (const profile of profiles) {
  if (!router.includes(profile)) throw new Error(`docs/router.md missing ${profile}`);
  if (!scale.includes(profile)) throw new Error(`docs/project-scale.md missing ${profile}`);
  if (!readme.includes(profile)) throw new Error(`README.md missing ${profile}`);
  if (!Array.isArray(matrix[profile])) throw new Error(`checks/profile-matrix.json missing ${profile}`);
}

const required = [
  "docs/router.md",
  "docs/template-forms.md",
  "docs/agent-rules.md",
  "templates/router/README.md",
  "templates/router/apply-profile-prompt.md",
  "templates/router/route-deletion-checklist.md",
  "optional/decisions/README.md",
  "optional/research/README.md",
  "optional/exec-plans/README.md",
  "optional/history/README.md",
  "optional/github/README.md",
  "optional/agent-rules/cursor/project/00-core-engineering.mdc",
  "optional/agent-rules/cursor/project/50-no-drive-by-refactor.mdc",
];

for (const file of required) {
  if (!existsSync(file)) throw new Error(`missing router/optional route file: ${file}`);
}

if (!router.includes("uncalled route")) {
  throw new Error("docs/router.md should explain uncalled route deletion.");
}

console.log(`Router check passed (${profiles.length} profiles, ${required.length} route files checked).`);
