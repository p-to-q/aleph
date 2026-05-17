import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const types = readFileSync("packages/core/src/types.ts", "utf8");
const schema = JSON.parse(readFileSync("schemas/aleph-run.schema.json", "utf8"));

function stringUnion(typeName) {
  const match = types.match(new RegExp(`export type ${typeName} = ([^;]+);`));
  if (!match) throw new Error(`missing exported union type: ${typeName}`);
  return [...match[1].matchAll(/"([^"]+)"/g)].map((item) => item[1]).sort();
}

function inlineStringUnion(typeName, fieldName) {
  const typeMatch = types.match(new RegExp(`export type ${typeName} = \\{([\\s\\S]*?)\\n\\};`));
  if (!typeMatch) throw new Error(`missing exported object type: ${typeName}`);
  const fieldMatch = typeMatch[1].match(new RegExp(`${fieldName}: ([^;]+);`));
  if (!fieldMatch) throw new Error(`missing field union: ${typeName}.${fieldName}`);
  return [...fieldMatch[1].matchAll(/"([^"]+)"/g)].map((item) => item[1]).sort();
}

function schemaEnum(path, value) {
  let current = value;
  for (const part of path) current = current?.[part];
  if (!Array.isArray(current)) throw new Error(`missing schema enum: ${path.join(".")}`);
  return [...current].sort();
}

assert.deepEqual(
  schemaEnum(["properties", "config", "properties", "mode", "enum"], schema),
  stringUnion("AlephMode"),
  "SearchConfig.mode schema enum should match AlephMode"
);
assert.deepEqual(
  schemaEnum(["$defs", "observations", "properties", "mode", "enum"], schema),
  stringUnion("ObservationMode"),
  "ObservationSet.mode schema enum should match ObservationMode"
);
assert.deepEqual(
  schemaEnum(["$defs", "exposure", "properties", "level", "enum"], schema),
  inlineStringUnion("ExposureVector", "level"),
  "ExposureVector.level schema enum should match core type"
);

assert.deepEqual(
  [...schema.required].sort(),
  ["candidates", "config", "createdAt", "id", "observations", "selectedCandidateId", "target"].sort(),
  "AlephRun schema should require the durable top-level fields"
);
assert.equal(schema.additionalProperties, false, "AlephRun schema should reject hidden top-level fields");

console.log("check-contract: ok");
