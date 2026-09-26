import assert from "node:assert/strict";

import { paretoFrontier } from "../packages/core/src/frontier.ts";
import { leakageScore } from "../packages/core/src/leakage.ts";
import { compressionRatio } from "../packages/core/src/metrics.ts";
import { annotateFrontier } from "../packages/core/src/run.ts";

const candidate = (id, tokens, fit, stability, leakage = 0) => ({
  id,
  label: id,
  prompt: "",
  output: "",
  tokens,
  fit,
  stability,
  compression: 0,
  leakage
});

const frontier = paretoFrontier([
  candidate("short-weak", 4, 0.62, 0.7),
  candidate("short-strong", 4, 0.8, 0.82),
  candidate("middle", 8, 0.9, 0.84),
  candidate("dominated", 9, 0.88, 0.83),
  candidate("explicit", 14, 0.99, 0.96)
]);
assert.deepEqual(
  frontier.map((point) => point.id),
  ["short-strong", "middle", "explicit"],
  "paretoFrontier should remove dominated candidates and sort by token length"
);

const copyTradeoff = paretoFrontier([
  candidate("lower-copy", 15, 0.84, 0.72, 0.16),
  candidate("higher-fit", 15, 0.93, 0.85, 0.62)
]);
assert.deepEqual(
  copyTradeoff.map((point) => point.id),
  ["higher-fit", "lower-copy"],
  "paretoFrontier should preserve a measured surface-copy tradeoff"
);

const tied = [
  candidate("z-tie", 4, 0.8, 0.8, 0.1),
  candidate("a-tie", 4, 0.8, 0.8, 0.1)
];
assert.deepEqual(
  paretoFrontier(tied).map((point) => point.id),
  ["a-tie", "z-tie"],
  "paretoFrontier should use a locale-independent code-unit id tie-break"
);
assert.deepEqual(
  paretoFrontier([...tied].reverse()).map((point) => point.id),
  ["a-tie", "z-tie"],
  "paretoFrontier ordering should be independent of input order"
);

const stale = candidate("stale", 9, 0.6, 0.6, 0.5);
stale.frontierRank = 1;
const winner = candidate("winner", 4, 0.9, 0.9, 0.1);
const run = {
  id: "rank-test",
  createdAt: "2026-09-27T00:00:00Z",
  target: { text: "target" },
  config: {
    model: "fixture",
    decoding: "fixed",
    metric: "test",
    budget: { candidates: 2, maxPromptTokens: 9, repeatedSamples: 1 },
    mode: "unrestricted"
  },
  candidates: [stale, winner],
  selectedCandidateId: "winner",
  observations: { mode: "fixture" }
};
const annotated = annotateFrontier(run);
assert.equal(annotated.candidates.find((point) => point.id === "stale")?.frontierRank, undefined);
assert.equal(annotated.candidates.find((point) => point.id === "winner")?.frontierRank, 1);
assert.equal(stale.frontierRank, 1, "annotateFrontier should not mutate source candidates");
assert.throws(
  () => paretoFrontier([candidate("duplicate", 1, 1, 1), candidate("duplicate", 2, 0.5, 0.5)]),
  /Duplicate candidate id/,
  "paretoFrontier should reject ambiguous candidate identities"
);
assert.throws(
  () => paretoFrontier([candidate("invalid-tokens", -1, 1, 1)]),
  /invalid tokens/,
  "paretoFrontier should reject invalid measured lengths"
);
assert.throws(
  () => paretoFrontier([candidate("invalid-fit", 1, 1.1, 1)]),
  /invalid fit/,
  "paretoFrontier should reject metrics outside their declared unit interval"
);

assert.equal(compressionRatio(25, 100), 0.75, "compressionRatio should return the saved token share");
assert.equal(compressionRatio(125, 100), 0, "compressionRatio should clamp negative compression to zero");
assert.equal(compressionRatio(10, 0), 0, "compressionRatio should handle missing explicit-token baselines");

const target = "The red desert contained every grain of sand.";
assert.equal(leakageScore("", target), 0, "empty prompts should not leak");
assert.ok(
  leakageScore("red desert every grain", target) > leakageScore("coordinate for a vast landscape", target),
  "leakageScore should increase when prompt tokens copy target tokens"
);
assert.ok(
  leakageScore("the red desert contained every grain of sand", target) > 0.8,
  "near-explicit reconstruction should be marked as highly leaky"
);

console.log("check-core: ok");
