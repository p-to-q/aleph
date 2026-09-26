import { readFileSync } from "node:fs";

const artifactUrl = new URL("../web/public/aleph-frontier.json", import.meta.url);

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

let artifact;
try {
  artifact = JSON.parse(readFileSync(artifactUrl, "utf8"));
} catch (error) {
  console.error(`Public frontier contract check failed: ${error.message}`);
  process.exit(1);
}

const errors = [];
checkFiniteNumbers(artifact, "frontier", errors);

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

      if (!Number.isInteger(point.length) || point.length < 0) {
        errors.push(`${pointPath}.length: expected a non-negative integer`);
      } else if (point.length <= previousLength) {
        errors.push(`${pointPath}.length: points must be strictly ordered by observed length`);
      } else {
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

      const isExplicit = point.role === "explicit_reconstruction";
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
    }

    if (target.key === "pitch") {
      if (explicitCount !== 0) errors.push(`${targetPath}: pitch must not define an explicit baseline`);
    } else if (explicitCount !== 1) {
      errors.push(`${targetPath}: expected exactly one Explicit Reconstruction, found ${explicitCount}`);
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
    `${measuredTargets.length} explicit baselines)`
);
