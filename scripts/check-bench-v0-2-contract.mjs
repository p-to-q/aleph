import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const types = readFileSync("packages/core/src/bench-v0-2.ts", "utf8");
const barrel = readFileSync("packages/core/src/index.ts", "utf8");
const itemSchema = JSON.parse(readFileSync("schemas/v0.2/aleph-bench-item.schema.json", "utf8"));
const resultSchema = JSON.parse(readFileSync("schemas/v0.2/aleph-bench-result.schema.json", "utf8"));
const manifestSchema = JSON.parse(readFileSync("schemas/v0.2/aleph-bench-manifest.schema.json", "utf8"));
const packageSchema = JSON.parse(
  readFileSync("schemas/v0.2/aleph-bench-platform-package.schema.json", "utf8")
);

function typeExpression(typeName) {
  const match = types.match(new RegExp(`export type ${typeName} =\\s*([\\s\\S]*?);\\n`));
  if (!match) throw new Error(`missing exported type: ${typeName}`);
  return match[1];
}

function objectBody(typeName) {
  const match = types.match(new RegExp(`export type ${typeName} = \\{([\\s\\S]*?)\\n\\};`));
  if (!match) throw new Error(`missing exported object type: ${typeName}`);
  return match[1];
}

function stringUnion(typeName) {
  return [...typeExpression(typeName).matchAll(/"([^"]+)"/g)]
    .map((match) => match[1])
    .sort();
}

function requiredFields(typeName) {
  return [...objectBody(typeName).matchAll(/^\s{2}([A-Za-z][A-Za-z0-9]*):/gm)]
    .map((match) => match[1])
    .sort();
}

function schemaEnum(schema, path) {
  let value = schema;
  for (const part of path) value = value?.[part];
  if (!Array.isArray(value)) throw new Error(`missing schema enum: ${path.join(".")}`);
  return [...value].sort();
}

function assertRequired(typeName, schema, path = ["required"]) {
  let required = schema;
  for (const part of path) required = required?.[part];
  assert.deepEqual(requiredFields(typeName), [...required].sort(), `${typeName} required fields drifted`);
}

assert.match(barrel, /export \* from "\.\/bench-v0-2\.ts";/, "core barrel must export v0.2 types");
assert.deepEqual(
  stringUnion("BenchMetricClassV02"),
  schemaEnum(itemSchema, ["properties", "metricClass", "enum"]),
  "v0.2 metric classes drifted"
);
assert.deepEqual(
  stringUnion("BenchStratumV02"),
  schemaEnum(itemSchema, ["properties", "stratum", "enum"]),
  "v0.2 strata drifted"
);
assertRequired("BenchItemV02", itemSchema);
assertRequired("BenchResultV02", resultSchema);
assertRequired("BenchManifestV02", manifestSchema);
assertRequired("BenchPlatformPackageV02", packageSchema);
assertRequired("BenchScoringProfileV02", resultSchema, ["$defs", "scoringProfile", "required"]);
assertRequired(
  "BenchLeakageGateThresholdsV02",
  resultSchema,
  ["$defs", "leakageThresholds", "required"]
);
assertRequired(
  "BenchLeakageGateResultV02",
  resultSchema,
  ["$defs", "leakageGate", "required"]
);
assertRequired(
  "BenchPromptMeasurementV02",
  resultSchema,
  ["$defs", "promptMeasurement", "required"]
);
assertRequired(
  "BenchPlatformArtifactV02",
  packageSchema,
  ["$defs", "artifact", "required"]
);
assert.doesNotMatch(types, /trigramOverlap|verbatimSpanTokens/, "v0.2 types must not expose v0.1 leakage fields");

console.log("check-bench-v0-2-contract: ok");
