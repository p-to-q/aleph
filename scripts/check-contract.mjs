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

// PR B: the optional artifactRef must stay in lockstep with ResearchArtifactRef.
const artifactRef = schema.properties.artifactRef;
assert.ok(artifactRef, "schema should declare the optional artifactRef property");
assert.equal(artifactRef.type, "object");
assert.equal(artifactRef.additionalProperties, false);
const refTypeMatch = types.match(/export type ResearchArtifactRef = \{([\s\S]*?)\n\};/);
assert.ok(refTypeMatch, "missing exported ResearchArtifactRef type");
const refFields = [...refTypeMatch[1].matchAll(/(\w+)\??:/g)].map((match) => match[1]).sort();
assert.deepEqual(
  [...artifactRef.required].sort(),
  refFields,
  "artifactRef schema required fields should match ResearchArtifactRef"
);
assert.ok(
  /artifactRef\?: ResearchArtifactRef;/.test(types),
  "AlephRun should carry artifactRef as an optional field"
);

// P2 adapter evidence contract (docs/research/token-nll-evidence-note.md):
// the schema and the exported type must agree on the token NLL entry shape,
// and the recorded numeric rules (non-negative loss, 1-based rank) must hold.
const tokenLoss = schema.$defs.tokenLoss;
const tokenLossTypeMatch = types.match(/export type TokenLossPoint = \{([\s\S]*?)\n\};/);
assert.ok(tokenLossTypeMatch, "missing exported TokenLossPoint type");
const tokenLossFields = [...tokenLossTypeMatch[1].matchAll(/(\w+)(\?)?:/g)];
assert.deepEqual(
  [...tokenLoss.required].sort(),
  tokenLossFields.filter((match) => !match[2]).map((match) => match[1]).sort(),
  "tokenLoss schema required fields should match TokenLossPoint"
);
assert.deepEqual(
  Object.keys(tokenLoss.properties).sort(),
  tokenLossFields.map((match) => match[1]).sort(),
  "tokenLoss schema properties should match TokenLossPoint"
);
assert.equal(tokenLoss.additionalProperties, false, "tokenLoss should reject hidden fields");
assert.equal(tokenLoss.properties.loss.minimum, 0, "token NLL losses are non-negative");
assert.equal(tokenLoss.properties.rank.minimum, 1, "token ranks are 1-based");
const observationsTokenLoss = schema.$defs.observations.properties.tokenLoss;
assert.equal(observationsTokenLoss.type, "array", "observations.tokenLoss should be an array");
assert.equal(
  observationsTokenLoss.items.$ref,
  "#/$defs/tokenLoss",
  "observations.tokenLoss should reference the tokenLoss definition"
);
assert.ok(
  /tokenLoss\?: TokenLossPoint\[\];/.test(types),
  "ObservationSet should carry tokenLoss as an optional field"
);

console.log("check-contract: ok");
