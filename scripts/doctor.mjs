import { createHash } from "node:crypto";
import { existsSync, readFileSync } from "node:fs";

const APACHE_2_LICENSE_SHA256 =
  "cfc7749b96f63bd31c3c42b5c471bf756814053e847c10f3eb003417bc523d30";

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

// Public mirrors redistribute Aleph code, so a shortened paraphrase is not a
// sufficient license artifact. Keep the root copy byte-identical to Apache-2.0.
const licenseSha256 = createHash("sha256")
  .update(readFileSync("LICENSE"))
  .digest("hex");
if (licenseSha256 !== APACHE_2_LICENSE_SHA256) {
  console.error(
    `LICENSE must be the complete official Apache-2.0 text (${APACHE_2_LICENSE_SHA256}). ` +
      `Current SHA-256: ${licenseSha256}`
  );
  process.exit(1);
}

const major = Number(process.versions.node.split(".")[0]);
if (major < 20) {
  console.error(`Node >=20 is required. Current: ${process.version}`);
  process.exit(1);
}
console.log("doctor: ok");
