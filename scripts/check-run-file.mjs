import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { downloadTextFor, parseRunFile, RUN_FILE_LIMITS } from "../web/app/lib/run-file.ts";

// Product-side run-file round trip (docs/next-backlog.md P1): every packed
// fixture must open, keep candidate identities and the selected candidate,
// and save back byte-for-byte. Crafted files must fail closed with clear
// issues. Digest/replay verification is the engine importer's job and is
// explicitly not asserted here.
//
// Runtime: Node >= 22.18 (default TypeScript type stripping — same requirement
// as scripts/check-core.mjs / scripts/check-fixtures.mjs); the package.json
// engines floor matches since the P3 decision (docs/next-backlog.md, 2026-10-15).

const fixtures = [
  "packages/fixtures/src/sample-run.json",
  "packages/fixtures/src/non-leaking-run.json",
  "packages/fixtures/src/gettysburg-run.json",
];

function parseOk(text, label) {
  const result = parseRunFile(text);
  assert.equal(result.ok, true, `${label}: expected parse to succeed: ${JSON.stringify(result.issues ?? [])}`);
  return result;
}

function parseRejected(text, needle, label) {
  const result = parseRunFile(text);
  assert.equal(result.ok, false, `${label}: expected parse to fail`);
  const joined = result.issues.map((issue) => `${issue.path}: ${issue.message}`).join("; ");
  assert.ok(joined.includes(needle), `${label}: expected issue containing ${JSON.stringify(needle)}, got: ${joined}`);
}

function valueOf(text) {
  return JSON.parse(text);
}

function mutate(text, fn) {
  const value = valueOf(text);
  fn(value);
  return JSON.stringify(value);
}

let roundTrips = 0;
for (const path of fixtures) {
  const raw = readFileSync(path, "utf8");
  const result = parseOk(raw, path);
  const value = valueOf(raw);

  assert.equal(result.points.length, value.candidates.length, `${path}: point count`);
  const idSet = new Set(result.points.map((point) => point.id));
  assert.equal(idSet.size, value.candidates.length, `${path}: point ids unique`);
  for (const candidate of value.candidates) {
    assert.ok(idSet.has(candidate.id), `${path}: candidate ${candidate.id} present in points`);
  }
  for (let i = 1; i < result.points.length; i += 1) {
    assert.ok(result.points[i - 1].epsilon >= result.points[i].epsilon, `${path}: epsilon order`);
  }
  assert.ok(result.selectedIndex >= 0, `${path}: selectedIndex resolved`);
  assert.equal(result.points[result.selectedIndex].id, result.run.selectedCandidateId, `${path}: selected candidate`);
  assert.equal(result.run.id, value.id, `${path}: run id`);

  // Save (pretty JSON) → reopen keeps the selected candidate.
  const savedFromValue = downloadTextFor(result.run, null);
  assert.ok(savedFromValue.endsWith("\n"), `${path}: saved text ends with a newline`);
  const reopened = parseOk(savedFromValue, `${path} (re-saved)`);
  assert.equal(reopened.run.selectedCandidateId, result.run.selectedCandidateId, `${path}: re-saved selection`);
  assert.equal(reopened.points.length, result.points.length, `${path}: re-saved point count`);
  assert.equal(reopened.selectedIndex, result.selectedIndex, `${path}: re-saved selected index`);

  // Save from an opened file is byte-preserving.
  assert.equal(downloadTextFor(result.run, raw), raw, `${path}: byte-preserving save`);
  roundTrips += 1;
}

const samplePath = fixtures[0];
const sampleRaw = readFileSync(samplePath, "utf8");
const sampleValue = valueOf(sampleRaw);
const wellFormedRef = {
  schemaVersion: "aleph-artifact-ref/0.1.0",
  runId: sampleValue.id,
  bundleDigest: `sha256:${"a".repeat(64)}`,
  projectionDigest: `sha256:${"b".repeat(64)}`,
};

// A well-formed artifactRef passes the static checks and stays usable; the
// product cannot recompute the digests (engine-side), so fabricated-but-
// well-formed refs are accepted here and labeled unverified in the UI.
parseOk(mutate(sampleRaw, (value) => { value.artifactRef = wellFormedRef; }), "well-formed artifactRef");

let rejections = 0;
const rejected = (text, needle, label) => {
  parseRejected(text, needle, label);
  rejections += 1;
};

rejected("", "not valid JSON", "empty text");
rejected("{", "not valid JSON", "truncated JSON");
rejected("[1, 2]", "top level must be a JSON object", "array top level");
rejected("null", "top level must be a JSON object", "null top level");
rejected("\uFEFF" + sampleRaw, "byte-order mark", "UTF-8 BOM");
rejected("x".repeat(RUN_FILE_LIMITS.maxTextLength + 1), "too large", "oversized text");
rejected(mutate(sampleRaw, (value) => { delete value.selectedCandidateId; }), "missing required property selectedCandidateId", "missing selectedCandidateId");
rejected(mutate(sampleRaw, (value) => { value.extra = 1; }), "unexpected property extra", "unknown top-level property");
rejected(mutate(sampleRaw, (value) => { value.candidates[0].extra = 1; }), "unexpected property extra", "unknown candidate property");
rejected(mutate(sampleRaw, (value) => { value.candidates[0].fit = 1.2; }), "above maximum 1", "fit above 1");
rejected(mutate(sampleRaw, (value) => { value.candidates[0].tokens = -1; }), "below minimum 0", "negative tokens");
rejected(mutate(sampleRaw, (value) => { value.candidates[0].role = "x"; }), "expected one of candidate, explicit_reconstruction", "invalid role");
rejected(mutate(sampleRaw, (value) => { value.config.mode = "x"; }), "expected one of unrestricted, non_leaking", "invalid config mode");
rejected(mutate(sampleRaw, (value) => { value.observations.mode = "x"; }), "expected one of fixture, mock, black_box, white_box, simulated", "invalid observation mode");
rejected(mutate(sampleRaw, (value) => { value.config.budget.candidates += 1; }), "must equal the candidate count", "budget candidate count mismatch");
rejected(mutate(sampleRaw, (value) => { value.config.budget.maxPromptTokens = 1; }), "must be at least the maximum candidate token count", "budget below observed token max");
// The engine-derived exact maximum also opens (the fixtures pin the declared-cap style).
parseOk(mutate(sampleRaw, (value) => { value.config.budget.maxPromptTokens = Math.max(...value.candidates.map((c) => c.tokens)); }), "engine-derived maxPromptTokens");
rejected(mutate(sampleRaw, (value) => { value.selectedCandidateId = "nope"; }), "is not among the candidate ids", "selected candidate missing from ids");
rejected(mutate(sampleRaw, (value) => { value.candidates = []; value.config.budget.candidates = 0; value.config.budget.maxPromptTokens = 0; }), "must not be empty", "empty candidates");
rejected(mutate(sampleRaw, (value) => { value.artifactRef = { ...wellFormedRef, schemaVersion: "aleph-artifact-ref/9.9.9" }; }), "aleph-artifact-ref/0.1.0", "unknown artifactRef version");
rejected(mutate(sampleRaw, (value) => { value.artifactRef = { ...wellFormedRef, runId: "other-run" }; }), "must match the run id", "artifactRef runId mismatch");
rejected(mutate(sampleRaw, (value) => { value.artifactRef = { ...wellFormedRef, bundleDigest: "sha256:zz" }; }), "sha256: digest", "malformed bundleDigest");
rejected(mutate(sampleRaw, (value) => { value.artifactRef = { ...wellFormedRef, projectionDigest: "md5:abc" }; }), "sha256: digest", "malformed projectionDigest");
rejected(mutate(sampleRaw, (value) => { value.target.label = "bad \uD800 end"; }), "unpaired surrogate", "lone surrogate");
rejected(
  '{"id":"a","createdAt":"c","target":{"text":"t"},"config":{"model":"m","decoding":"d","metric":"me","mode":"unrestricted","budget":{"candidates":1,"maxPromptTokens":1,"repeatedSamples":1}},"candidates":[{"id":"c1","label":"l","prompt":"p","output":"o","tokens":1,"fit":1e999,"stability":1,"compression":1,"leakage":0}],"selectedCandidateId":"c1","observations":{"mode":"fixture"}}',
  "non-finite",
  "non-finite number literal",
);

// A file without the trailing newline still opens (the engine's byte-form
// requirement is a research-import concern, not a product concern).
const trimmed = sampleRaw.endsWith("\n") ? sampleRaw.slice(0, -1) : sampleRaw;
parseOk(trimmed, "no trailing newline");

const garbage = ["", " ", "{}", "[]", "null", "true", "0", '"s"', '{"a":', "not json at all"];
for (const text of garbage) {
  let result;
  assert.doesNotThrow(() => { result = parseRunFile(text); }, `garbage input threw: ${JSON.stringify(text)}`);
  assert.equal(result.ok, false, `garbage input accepted: ${JSON.stringify(text)}`);
}

console.log(
  `check-run-file: ok — ${fixtures.length} fixtures opened + round-tripped (${roundTrips}), ${rejections} crafted files rejected, ${garbage.length} garbage inputs fail closed, well-formed artifactRef accepted shape-only`,
);
