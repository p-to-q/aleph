import assert from "node:assert/strict";

import { paretoFrontier } from "../packages/core/src/frontier.ts";
import { leakageScore } from "../packages/core/src/leakage.ts";
import { compressionRatio } from "../packages/core/src/metrics.ts";

const candidate = (id, tokens, fit, stability) => ({
  id,
  label: id,
  prompt: "",
  output: "",
  tokens,
  fit,
  stability,
  compression: 0,
  leakage: 0
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
