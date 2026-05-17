import { existsSync, readFileSync } from "node:fs";

const requiredDocs = [
  "THESIS.md",
  "docs/core-concept.md",
  "docs/open-questions.md",
  "docs/state-of-play.md",
  "docs/next-backlog.md",
  "docs/repository-shape.md",
  "docs/repository-governance.md",
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

const concept = readFileSync("docs/core-concept.md", "utf8");
for (const phrase of ["Settled", "Open for discussion", "Deferred or explicitly out of scope"]) {
  if (!concept.includes(phrase)) throw new Error(`core concept missing section: ${phrase}`);
}
const state = readFileSync("docs/state-of-play.md", "utf8");
for (const phrase of ["Core hypothesis", "What Is Settled", "Research Converted Into Product Shape", "Researched But Not Yet Converted", "Next Correct Move"]) {
  if (!state.includes(phrase)) throw new Error(`state of play missing section: ${phrase}`);
}
const backlog = readFileSync("docs/next-backlog.md", "utf8");
for (const phrase of ["P0: Make The Active Surface Unambiguous", "P1: First Real Run Loop", "P1: Metric And Leakage Decision", "P2: Research Route Review"]) {
  if (!backlog.includes(phrase)) throw new Error(`next backlog missing item: ${phrase}`);
}
const thesis = readFileSync("THESIS.md", "utf8");
for (const phrase of ["compression path", "Shortest Found", "Explicit Reconstruction", "AlephRun"]) {
  if (!thesis.includes(phrase)) throw new Error(`thesis missing phrase: ${phrase}`);
}
const shape = readFileSync("docs/repository-shape.md", "utf8");
if (!shape.includes("artifact-first product lab")) throw new Error("repository shape decision missing");
const governance = readFileSync("docs/repository-governance.md", "utf8");
for (const phrase of ["web/", "apps/web/", "codex/publish-aleph-explorer-update", "white-box observations"]) {
  if (!governance.includes(phrase)) throw new Error(`governance missing phrase: ${phrase}`);
}
const strategy = readFileSync("docs/strategy.md", "utf8");
for (const phrase of ["Fallback ladder", "console-first", "AlephRun"]) {
  if (!strategy.includes(phrase)) throw new Error(`strategy missing phrase: ${phrase}`);
}
const quality = readFileSync("docs/quality-bar.md", "utf8");
for (const phrase of ["shortest known prompt", "mock/simulated", "next correct move"]) {
  if (!quality.includes(phrase)) throw new Error(`quality bar missing phrase: ${phrase}`);
}
console.log("check-repo: ok");
