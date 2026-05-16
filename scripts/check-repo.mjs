import { existsSync, readFileSync } from "node:fs";

const requiredDocs = [
  "THESIS.md",
  "docs/core-concept.md",
  "docs/open-questions.md",
  "docs/repository-shape.md",
  "docs/maintainer-review.md",
  "docs/strategy.md",
  "docs/quality-bar.md",
  "docs/contributor-map.md",
  "docs/engineering-discipline.md",
  "docs/checks.md",
  "docs/research/research-process.md",
  "docs/research/implementation-routes.md",
  "docs/decisions/0001-repository-shape.md",
  "docs/plans/hackathon-v0.md",
  "schemas/aleph-run.schema.json"
];
for (const file of requiredDocs) {
  if (!existsSync(file)) throw new Error(`missing required doc: ${file}`);
}
if (existsSync("optional")) throw new Error("optional/ should not be active in this repository shape");
if (existsSync("docs/archive/images") || existsSync("docs/archive/research-screenshots.md")) {
  throw new Error("reference screenshots should not be kept in the archive");
}

const run = JSON.parse(readFileSync("packages/fixtures/src/sample-run.json", "utf8"));
if (!Array.isArray(run.candidates) || run.candidates.length < 5) throw new Error("expected at least five candidates");
if (run.config.budget.candidates !== run.candidates.length) throw new Error("candidate budget should match fixture candidate count");
if (!run.candidates.some((c) => c.id === run.selectedCandidateId)) throw new Error("selected candidate missing");
if (!run.candidates.some((c) => c.id === "explicit" && c.leakage > 0.8)) throw new Error("explicit reconstruction baseline missing or not marked leaky");
if (!run.observations || run.observations.mode !== "fixture") throw new Error("fixture observation mode missing");
if (!Array.isArray(run.observations.tokenLoss) || run.observations.tokenLoss.length < 8) throw new Error("token loss fixture too small");

const concept = readFileSync("docs/core-concept.md", "utf8");
for (const phrase of ["Settled", "Open for discussion", "Deferred or explicitly out of scope"]) {
  if (!concept.includes(phrase)) throw new Error(`core concept missing section: ${phrase}`);
}
const thesis = readFileSync("THESIS.md", "utf8");
for (const phrase of ["compression path", "Shortest Found", "Explicit Reconstruction", "AlephRun"]) {
  if (!thesis.includes(phrase)) throw new Error(`thesis missing phrase: ${phrase}`);
}
const shape = readFileSync("docs/repository-shape.md", "utf8");
if (!shape.includes("artifact-first product lab")) throw new Error("repository shape decision missing");
const strategy = readFileSync("docs/strategy.md", "utf8");
for (const phrase of ["Fallback ladder", "console-first", "AlephRun"]) {
  if (!strategy.includes(phrase)) throw new Error(`strategy missing phrase: ${phrase}`);
}
const quality = readFileSync("docs/quality-bar.md", "utf8");
for (const phrase of ["shortest known prompt", "mock/simulated", "next correct move"]) {
  if (!quality.includes(phrase)) throw new Error(`quality bar missing phrase: ${phrase}`);
}
console.log("check-repo: ok");
