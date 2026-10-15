import { readFileSync } from "node:fs";
import { canonicalBytes, digestBytes, isDigest } from "./aleph-canonical.mjs";

const artifactUrl = new URL("../web/public/aleph-frontier.json", import.meta.url);

const receiptsUrl = new URL("../web/public/aleph-frontier.receipts.json", import.meta.url);

const RECEIPTS_SCHEMA_VERSION = "aleph-frontier-receipts/0.1.0";
// The measured observation allowlist shared by points and receipts. The same
// list is pinned in search/frontier_receipts.py; keep the two in sync.
const MEASURED_FIELDS = ["epsilon", "prompt", "similarity", "stability", "length", "output", "toktext", "toknll"];
const MEASURED_OPTIONAL_FIELDS = ["embeddingSimilarity"];
const EPSILON_TOLERANCE = 1.2e-4;

function isObject(value) {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

function stableStringify(value) {
  if (Array.isArray(value)) {
    return `[${value.map(stableStringify).join(",")}]`;
  }
  if (isObject(value)) {
    return `{${Object.keys(value)
      .sort()
      .map((key) => `${JSON.stringify(key)}:${stableStringify(value[key])}`)
      .join(",")}}`;
  }
  return JSON.stringify(value);
}

function checkFiniteNumbers(value, path, errors) {
  if (typeof value === "number") {
    if (!Number.isFinite(value)) errors.push(`${path}: expected a finite number`);
    return;
  }
  if (Array.isArray(value)) {
    value.forEach((item, index) => checkFiniteNumbers(item, `${path}[${index}]`, errors));
    return;
  }
  if (isObject(value)) {
    for (const [key, item] of Object.entries(value)) {
      checkFiniteNumbers(item, `${path}.${key}`, errors);
    }
  }
}

function requireFiniteUnitInterval(point, field, path, errors) {
  const value = point[field];
  if (typeof value !== "number" || !Number.isFinite(value) || value < 0 || value > 1) {
    errors.push(`${path}.${field}: expected a finite number in [0, 1]`);
  }
}

function deepEqual(a, b) {
  if (Array.isArray(a) || Array.isArray(b)) {
    return (
      Array.isArray(a) &&
      Array.isArray(b) &&
      a.length === b.length &&
      a.every((item, index) => deepEqual(item, b[index]))
    );
  }
  if (isObject(a) || isObject(b)) {
    return (
      isObject(a) &&
      isObject(b) &&
      Object.keys(a).length === Object.keys(b).length &&
      Object.keys(a).every((key) => Object.prototype.hasOwnProperty.call(b, key) && deepEqual(a[key], b[key]))
    );
  }
  return a === b;
}

function measuredFieldsOf(value, label, errors) {
  const out = {};
  for (const field of MEASURED_FIELDS) {
    if (!(field in value)) {
      errors.push(`${label}: missing measured field ${field}`);
      return null;
    }
    out[field] = value[field];
  }
  for (const field of MEASURED_OPTIONAL_FIELDS) {
    if (field in value) out[field] = value[field];
  }
  return out;
}

function firstMeasurementMismatch(a, b) {
  const keysA = Object.keys(a);
  const keysB = Object.keys(b);
  if (keysA.length !== keysB.length || keysA.some((key) => !keysB.includes(key))) return "field set";
  for (const key of keysA) {
    if (!deepEqual(a[key], b[key])) return key;
  }
  return null;
}

let artifact;
try {
  artifact = JSON.parse(readFileSync(artifactUrl, "utf8"));
} catch (error) {
  console.error(`Public frontier contract check failed: ${error.message}`);
  process.exit(1);
}

const errors = [];
checkFiniteNumbers(artifact, "frontier", errors);

let receiptsDoc = null;
try {
  receiptsDoc = JSON.parse(readFileSync(receiptsUrl, "utf8"));
} catch (error) {
  errors.push(`receipts: cannot read web/public/aleph-frontier.receipts.json: ${error.message}`);
}

const receiptsByDigest = new Map();
if (receiptsDoc !== null) {
  if (!isObject(receiptsDoc)) {
    errors.push("receipts: expected a top-level object");
  } else {
    if (receiptsDoc.schemaVersion !== RECEIPTS_SCHEMA_VERSION) {
      errors.push(`receipts.schemaVersion: expected ${JSON.stringify(RECEIPTS_SCHEMA_VERSION)}`);
    }
    const run = receiptsDoc.run;
    if (!isObject(run)) {
      errors.push("receipts.run: expected an object");
    } else if (run.complete !== true) {
      errors.push("receipts.run.complete: expected true for a published receipts file");
    }
    const receipts = receiptsDoc.receipts;
    if (!Array.isArray(receipts)) {
      errors.push("receipts.receipts: expected an array");
    } else {
      for (const [index, receipt] of receipts.entries()) {
        const where = `receipts[${index}]`;
        if (!isObject(receipt)) {
          errors.push(`${where}: expected an object`);
          continue;
        }
        const digest = receipt.receiptDigest;
        if (!isDigest(digest)) {
          errors.push(`${where}.receiptDigest: expected a sha256: digest`);
        } else if (receiptsByDigest.has(digest)) {
          errors.push(`${where}.receiptDigest: duplicate receipt digest`);
        } else {
          receiptsByDigest.set(digest, receipt);
        }
        const body = { ...receipt };
        delete body.receiptDigest;
        try {
          const computed = digestBytes(canonicalBytes(body));
          if (computed !== digest) errors.push(`${where}.receiptDigest: mismatch (recomputed ${computed})`);
        } catch (error) {
          errors.push(`${where}: receipt body has no canonical form: ${error.message}`);
        }
        try {
          if (!isDigest(receipt.promptDigest) || digestBytes(canonicalBytes(receipt.prompt)) !== receipt.promptDigest) {
            errors.push(`${where}.promptDigest: mismatch`);
          }
          if (!isDigest(receipt.outputDigest) || digestBytes(canonicalBytes(receipt.output)) !== receipt.outputDigest) {
            errors.push(`${where}.outputDigest: mismatch`);
          }
        } catch (error) {
          errors.push(`${where}: prompt/output digest not canonicalizable: ${error.message}`);
        }
        if (typeof receipt.target !== "string" || receipt.target.length === 0) {
          errors.push(`${where}.target: expected a non-empty string`);
        }
        if (!isDigest(receipt.targetDigest)) errors.push(`${where}.targetDigest: expected a sha256: digest`);
        if (receipt.status !== "displayed" && receipt.status !== "filtered") {
          errors.push(`${where}.status: expected "displayed" or "filtered"`);
        }
        if (!isObject(receipt.procedure)) errors.push(`${where}.procedure: expected an object`);
        if (!isObject(receipt.measurement)) errors.push(`${where}.measurement: expected an object`);
        if (!isObject(receipt.supersedes)) errors.push(`${where}.supersedes: expected an object`);
        if (typeof receipt.measuredAt !== "string") errors.push(`${where}.measuredAt: expected a timestamp string`);
        if (!isObject(receipt.model)) {
          errors.push(`${where}.model: expected an object`);
        } else {
          if (typeof receipt.model.repo !== "string" || receipt.model.repo.length === 0) {
            errors.push(`${where}.model.repo: expected a non-empty string`);
          }
          if (typeof receipt.model.revision !== "string" || receipt.model.revision.length === 0) {
            errors.push(`${where}.model.revision: expected a non-empty string`);
          }
          if (!isDigest(receipt.model.weightsDigest)) {
            errors.push(`${where}.model.weightsDigest: expected a sha256: digest`);
          }
        }
        if (typeof receipt.epsilon !== "number" || !Number.isFinite(receipt.epsilon)) {
          errors.push(`${where}.epsilon: expected a finite number`);
        }
        if (typeof receipt.similarity !== "number" || !Number.isFinite(receipt.similarity)) {
          errors.push(`${where}.similarity: expected a finite number`);
        }
        if (
          typeof receipt.epsilon === "number" &&
          Number.isFinite(receipt.epsilon) &&
          typeof receipt.similarity === "number" &&
          Number.isFinite(receipt.similarity) &&
          Math.abs(1 - receipt.similarity - receipt.epsilon) > EPSILON_TOLERANCE
        ) {
          errors.push(`${where}: epsilon/similarity are inconsistent`);
        }
        if (
          typeof receipt.stability !== "number" ||
          !Number.isFinite(receipt.stability) ||
          receipt.stability < 0 ||
          receipt.stability > 1
        ) {
          errors.push(`${where}.stability: expected a finite number in [0, 1]`);
        }
        if (!Number.isInteger(receipt.length) || receipt.length < 0) {
          errors.push(`${where}.length: expected a non-negative integer`);
        }
        if (!Array.isArray(receipt.toktext) || receipt.toktext.some((token) => typeof token !== "string")) {
          errors.push(`${where}.toktext: expected a list of strings`);
        }
        if (
          !Array.isArray(receipt.toknll) ||
          receipt.toknll.some((loss) => typeof loss !== "number" || !Number.isFinite(loss))
        ) {
          errors.push(`${where}.toknll: expected a list of finite numbers`);
        }
        if (Array.isArray(receipt.toktext) && Array.isArray(receipt.toknll) && receipt.toktext.length !== receipt.toknll.length) {
          errors.push(`${where}: toktext and toknll length mismatch`);
        }
        if (receipt.embeddingSimilarity !== undefined) {
          requireFiniteUnitInterval(receipt, "embeddingSimilarity", where, errors);
        }
      }
    }
  }
}

const referencedReceipts = new Map();

function checkPointReceipt(point, target, pointPath, errors, referenced) {
  const digest = point.receiptDigest;
  if (!isDigest(digest)) {
    errors.push(`${pointPath}.receiptDigest: expected a sha256: digest`);
    return;
  }
  const receipt = receiptsByDigest.get(digest);
  if (receipt === undefined) {
    errors.push(`${pointPath}.receiptDigest: does not resolve to a receipt`);
    return;
  }
  if (referenced.has(digest)) {
    errors.push(`${pointPath}: receipt already referenced by ${referenced.get(digest)}`);
    return;
  }
  referenced.set(digest, pointPath);
  if (receipt.status !== "displayed") {
    errors.push(`${pointPath}: references a receipt with status ${JSON.stringify(receipt.status)}`);
  }
  if (receipt.target !== target.key) {
    errors.push(`${pointPath}: receipt target ${JSON.stringify(receipt.target)} does not match ${JSON.stringify(target.key)}`);
  }
  if (isObject(receipt.model) && receipt.model.repo !== target.evalModel) {
    errors.push(`${pointPath}: receipt model repo ${JSON.stringify(receipt.model.repo)} does not match evalModel`);
  }
  const pointFields = measuredFieldsOf(point, pointPath, errors);
  const receiptFields = measuredFieldsOf(receipt, `${pointPath} receipt`, errors);
  if (pointFields === null || receiptFields === null) return;
  const mismatch = firstMeasurementMismatch(pointFields, receiptFields);
  if (mismatch === "field set") {
    errors.push(`${pointPath}: displayed measurement field set differs from its receipt`);
  } else if (mismatch !== null) {
    errors.push(`${pointPath}: displayed ${mismatch} differs from its receipt`);
  }
}

if (!Array.isArray(artifact)) {
  errors.push("frontier: expected a top-level array");
} else {
  const targetKeys = new Set();

  for (const [targetIndex, target] of artifact.entries()) {
    const targetPath = `frontier[${targetIndex}]`;
    if (!isObject(target)) {
      errors.push(`${targetPath}: expected an object`);
      continue;
    }

    if (typeof target.key !== "string" || target.key.length === 0) {
      errors.push(`${targetPath}.key: expected a non-empty string`);
    } else if (targetKeys.has(target.key)) {
      errors.push(`${targetPath}.key: duplicate target key ${target.key}`);
    } else {
      targetKeys.add(target.key);
    }

    if (!Number.isInteger(target.targetTokens) || target.targetTokens < 0) {
      errors.push(`${targetPath}.targetTokens: expected a non-negative integer`);
    }
    if (target.key !== "pitch" && (typeof target.evalModel !== "string" || target.evalModel.length === 0)) {
      errors.push(`${targetPath}.evalModel: measured targets must declare the evaluation model`);
    }
    if (!Array.isArray(target.points)) {
      errors.push(`${targetPath}.points: expected an array`);
      continue;
    }

    let explicitCount = 0;
    let previousLength = -1;
    let bestEpsilon = Number.POSITIVE_INFINITY;
    const observationsByFingerprint = new Map();

    for (const [pointIndex, point] of target.points.entries()) {
      const pointPath = `${targetPath}.points[${pointIndex}]`;
      if (!isObject(point)) {
        errors.push(`${pointPath}: expected an object`);
        continue;
      }
      const isExplicit = point.role === "explicit_reconstruction";

      if (!Number.isInteger(point.length) || point.length < 0) {
        errors.push(`${pointPath}.length: expected a non-negative integer`);
      } else if (!isExplicit && point.length <= previousLength) {
        errors.push(`${pointPath}.length: points must be strictly ordered by observed length`);
      } else if (!isExplicit) {
        previousLength = point.length;
      }

      requireFiniteUnitInterval(point, "epsilon", pointPath, errors);
      requireFiniteUnitInterval(point, "similarity", pointPath, errors);
      requireFiniteUnitInterval(point, "stability", pointPath, errors);
      if (typeof point.prompt !== "string") errors.push(`${pointPath}.prompt: expected a string`);
      if (typeof point.output !== "string") errors.push(`${pointPath}.output: expected a string`);
      if (!Array.isArray(point.toktext)) errors.push(`${pointPath}.toktext: expected an array`);
      if (!Array.isArray(point.toknll)) errors.push(`${pointPath}.toknll: expected an array`);
      if (Array.isArray(point.toktext) && point.toktext.some((token) => typeof token !== "string")) {
        errors.push(`${pointPath}.toktext: expected only strings`);
      }
      if (
        Array.isArray(point.toknll) &&
        point.toknll.some((loss) => typeof loss !== "number" || !Number.isFinite(loss))
      ) {
        errors.push(`${pointPath}.toknll: expected only finite numbers`);
      }
      if (point.embeddingSimilarity !== undefined) {
        requireFiniteUnitInterval(point, "embeddingSimilarity", pointPath, errors);
      }
      if (
        Array.isArray(point.toktext) &&
        Array.isArray(point.toknll) &&
        point.toktext.length !== point.toknll.length
      ) {
        errors.push(`${pointPath}: toktext and toknll must describe the same observed tokens`);
      }

      const hasExplicitLabel = point.label === "Explicit Reconstruction";
      if (point.role !== undefined && !isExplicit) {
        errors.push(`${pointPath}.role: unsupported role ${JSON.stringify(point.role)}`);
      }
      if (isExplicit !== hasExplicitLabel) {
        errors.push(`${pointPath}: explicit role and label must be present together`);
      }
      if (isExplicit) {
        explicitCount += 1;
        if (pointIndex !== target.points.length - 1) {
          errors.push(`${pointPath}: Explicit Reconstruction must be the final baseline`);
        }
      } else if (typeof point.epsilon === "number" && Number.isFinite(point.epsilon)) {
        if (point.epsilon >= bestEpsilon) {
          errors.push(`${pointPath}: non-baseline points must be strict observed distortion improvements`);
        }
        bestEpsilon = Math.min(bestEpsilon, point.epsilon);
      }

      // Identity, derived rank, and provenance/display annotations are not part
      // of the measured observation. In particular, id, frontierRank, label,
      // role, evidence, and stabilityNote are deliberately omitted. Keeping an
      // explicit measurement allowlist also prevents a writer from evading this
      // check with a fresh metadata key.
      const observation = {
        epsilon: point.epsilon,
        prompt: point.prompt,
        similarity: point.similarity,
        stability: point.stability,
        output: point.output,
        toktext: point.toktext,
        toknll: point.toknll,
        ...(point.embeddingSimilarity === undefined
          ? {}
          : { embeddingSimilarity: point.embeddingSimilarity })
      };
      const fingerprint = stableStringify(observation);
      const previous = observationsByFingerprint.get(fingerprint);
      if (previous && previous.length !== point.length) {
        errors.push(
          `${pointPath}: observation duplicates ${previous.path} at a different length ` +
            `(${previous.length} vs ${point.length})`
        );
      } else if (!previous) {
        observationsByFingerprint.set(fingerprint, { length: point.length, path: pointPath });
      }

      if (target.key !== "pitch") {
        checkPointReceipt(point, target, pointPath, errors, referencedReceipts);
      }
    }

    if (target.key === "pitch") {
      if (explicitCount !== 0) errors.push(`${targetPath}: pitch must not define an explicit baseline`);
    } else if (explicitCount !== 1) {
      errors.push(`${targetPath}: expected exactly one Explicit Reconstruction, found ${explicitCount}`);
    }
  }
}

if (receiptsDoc !== null && isObject(receiptsDoc) && Array.isArray(receiptsDoc.receipts)) {
  for (const [digest, receipt] of receiptsByDigest) {
    if (receipt.status === "displayed" && !referencedReceipts.has(digest)) {
      errors.push(`receipts: displayed receipt ${digest} is not referenced by any artifact point`);
    }
  }
  const receiptEntries = receiptsDoc.receipts.filter((receipt) => isObject(receipt));
  const counts = isObject(receiptsDoc.run) ? receiptsDoc.run.counts : undefined;
  if (!isObject(counts)) {
    errors.push("receipts.run.counts: expected an object");
  } else {
    const displayed = receiptEntries.filter((receipt) => receipt.status === "displayed").length;
    const outputsIdentical = receiptEntries.filter(
      (receipt) => isObject(receipt.supersedes) && receipt.supersedes.outputIdentical === true
    ).length;
    const epsilonIdentical = receiptEntries.filter(
      (receipt) => isObject(receipt.supersedes) && deepEqual(receipt.epsilon, receipt.supersedes.epsilon)
    ).length;
    const expectations = {
      evaluated: receiptEntries.length,
      displayed,
      filtered: receiptEntries.length - displayed,
      outputsIdentical,
      epsilonIdentical,
    };
    for (const [field, expected] of Object.entries(expectations)) {
      if (counts[field] !== expected) errors.push(`receipts.run.counts.${field}: expected ${expected}`);
    }
  }
}

if (errors.length > 0) {
  console.error("Public frontier contract check failed:");
  for (const error of errors) console.error(`- ${error}`);
  process.exit(1);
}

const measuredTargets = artifact.filter((target) => target.key !== "pitch");
const pointCount = measuredTargets.reduce((total, target) => total + target.points.length, 0);
console.log(
  `check-public-frontier: ok (${measuredTargets.length} targets, ${pointCount} observed points, ` +
    `${measuredTargets.length} explicit baselines, ${receiptsByDigest.size} receipts — ` +
    "every displayed point receipt-linked)"
);
