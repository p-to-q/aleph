import { existsSync } from "node:fs";

const required = [
  "README.md",
  "THESIS.md",
  "LICENSE",
  "NOTICE",
  "CONTRIBUTING.md",
  "SECURITY.md",
  "SUPPORT.md",
  "AGENTS.md",
  "PROMPT.md",
  "WORKFLOW.md",
  "docs/project-brief.md",
  "docs/core-concept.md",
  "docs/open-questions.md",
  "docs/repository-shape.md",
  "docs/maintainer-review.md",
  "docs/strategy.md",
  "docs/quality-bar.md",
  "docs/contributor-map.md",
  "docs/engineering-discipline.md",
  "docs/architecture.md",
  "docs/surfaces.md",
  "docs/research/research-process.md",
  "docs/research/implementation-routes.md",
  "packages/core/src/types.ts",
  "packages/fixtures/src/sample-run.json",
  "schemas/aleph-run.schema.json",
  "apps/web/static/aleph-atlas-console.html"
];

const missing = required.filter((file) => !existsSync(file));
if (missing.length) {
  console.error("Missing required files:");
  for (const file of missing) console.error(`- ${file}`);
  process.exit(1);
}

const major = Number(process.versions.node.split(".")[0]);
if (major < 20) {
  console.error(`Node >=20 is required. Current: ${process.version}`);
  process.exit(1);
}
console.log("doctor: ok");
