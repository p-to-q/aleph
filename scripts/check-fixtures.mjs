import { readdirSync, readFileSync } from "node:fs";

const schema = JSON.parse(readFileSync("schemas/aleph-run.schema.json", "utf8"));
const manifest = JSON.parse(readFileSync("packages/fixtures/src/manifest.json", "utf8"));
const fixtureFiles = readdirSync("packages/fixtures/src")
  .filter((file) => file.endsWith("-run.json") || file === "sample-run.json")
  .sort();

if (fixtureFiles.length < 2) throw new Error("expected at least two AlephRun fixtures");

function resolveRef(ref) {
  const parts = ref.replace(/^#\//, "").split("/");
  let current = schema;
  for (const part of parts) current = current[part];
  if (!current) throw new Error(`unknown schema ref: ${ref}`);
  return current;
}

function typeName(value) {
  if (Array.isArray(value)) return "array";
  if (value === null) return "null";
  return typeof value;
}

function validateValue(definition, value, path, errors) {
  if (definition.$ref) {
    validateValue(resolveRef(definition.$ref), value, path, errors);
    return;
  }

  if (definition.enum && !definition.enum.includes(value)) {
    errors.push(`${path}: expected one of ${definition.enum.join(", ")}`);
  }

  if (definition.type) {
    const actual = typeName(value);
    if (definition.type === "integer") {
      if (!Number.isInteger(value)) errors.push(`${path}: expected integer, got ${actual}`);
    } else if (actual !== definition.type) {
      errors.push(`${path}: expected ${definition.type}, got ${actual}`);
      return;
    }
  }

  if (typeof value === "number") {
    if (definition.minimum !== undefined && value < definition.minimum) errors.push(`${path}: below minimum ${definition.minimum}`);
    if (definition.maximum !== undefined && value > definition.maximum) errors.push(`${path}: above maximum ${definition.maximum}`);
  }

  if (definition.type === "object") {
    const properties = definition.properties ?? {};
    for (const key of definition.required ?? []) {
      if (!(key in value)) errors.push(`${path}: missing required property ${key}`);
    }
    if (definition.additionalProperties === false) {
      for (const key of Object.keys(value)) {
        if (!(key in properties)) errors.push(`${path}: unexpected property ${key}`);
      }
    }
    for (const [key, propertyDefinition] of Object.entries(properties)) {
      if (key in value) validateValue(propertyDefinition, value[key], `${path}.${key}`, errors);
    }
  }

  if (definition.type === "array") {
    value.forEach((item, index) => validateValue(definition.items, item, `${path}[${index}]`, errors));
  }
}

function checkFixtureInvariants(file, run) {
  const errors = [];
  if (!Array.isArray(run.candidates) || run.candidates.length < 5) {
    errors.push("expected at least five candidates");
  }
  if (run.config.budget.candidates !== run.candidates.length) {
    errors.push("candidate budget should match fixture candidate count");
  }
  if (!run.candidates.some((candidate) => candidate.id === run.selectedCandidateId)) {
    errors.push("selected candidate missing");
  }
  if (!run.candidates.some((candidate) => candidate.id === "explicit" && candidate.label === "Explicit Reconstruction" && candidate.leakage > 0.8)) {
    errors.push("explicit reconstruction baseline missing or not marked leaky");
  }
  if (!run.candidates.some((candidate) => candidate.label === "Shortest Found Candidate")) {
    errors.push("shortest found candidate missing");
  }
  if (run.observations.mode !== "fixture") {
    errors.push("fixture observation mode missing");
  }
  if (!Array.isArray(run.observations.tokenLoss) || run.observations.tokenLoss.length < 8) {
    errors.push("token loss fixture too small");
  }
  if (run.config.mode === "non_leaking") {
    const selected = run.candidates.find((candidate) => candidate.id === run.selectedCandidateId);
    if (!selected || selected.leakage > 0.2) {
      errors.push("selected non-leaking candidate should stay below leakage threshold");
    }
  }
  return errors.map((error) => `${file}: ${error}`);
}

let sawNonLeakingRun = false;
const errors = [];
const runsByFile = new Map();
for (const file of fixtureFiles) {
  const run = JSON.parse(readFileSync(`packages/fixtures/src/${file}`, "utf8"));
  runsByFile.set(file, run);
  validateValue(schema, run, file, errors);
  errors.push(...checkFixtureInvariants(file, run));
  if (run.config.mode === "non_leaking") sawNonLeakingRun = true;
}
if (!sawNonLeakingRun) errors.push("expected a non_leaking AlephRun fixture");

if (!Array.isArray(manifest.fixtures)) {
  errors.push("manifest.json: fixtures should be an array");
} else {
  const manifestFiles = new Set();
  let defaultCount = 0;
  for (const [index, entry] of manifest.fixtures.entries()) {
    const prefix = `manifest.json.fixtures[${index}]`;
    for (const key of ["id", "file", "label", "mode", "observationMode", "default"]) {
      if (!(key in entry)) errors.push(`${prefix}: missing ${key}`);
    }
    if (entry.default === true) defaultCount += 1;
    if (typeof entry.file === "string") manifestFiles.add(entry.file);
    const run = runsByFile.get(entry.file);
    if (!run) {
      errors.push(`${prefix}: unknown fixture file ${entry.file}`);
      continue;
    }
    if (entry.id !== run.id) errors.push(`${prefix}: id does not match ${entry.file}`);
    if (entry.label !== run.target.label) errors.push(`${prefix}: label does not match ${entry.file}`);
    if (entry.mode !== run.config.mode) errors.push(`${prefix}: mode does not match ${entry.file}`);
    if (entry.observationMode !== run.observations.mode) errors.push(`${prefix}: observationMode does not match ${entry.file}`);
  }
  for (const file of fixtureFiles) {
    if (!manifestFiles.has(file)) errors.push(`manifest.json: missing fixture file ${file}`);
  }
  if (defaultCount !== 1) errors.push("manifest.json: expected exactly one default fixture");
}

if (errors.length) {
  console.error("Fixture contract check failed:");
  for (const error of errors) console.error(`- ${error}`);
  process.exit(1);
}
console.log("check-fixtures: ok");
