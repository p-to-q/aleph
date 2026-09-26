import type { CandidatePoint } from "./types.ts";

function assertComparableCandidates(candidates: CandidatePoint[]): void {
  const ids = new Set<string>();
  for (const candidate of candidates) {
    if (typeof candidate.id !== "string" || candidate.id.trim().length === 0) {
      throw new Error("Candidate id must be a non-empty string");
    }
    if (ids.has(candidate.id)) throw new Error(`Duplicate candidate id: ${candidate.id}`);
    ids.add(candidate.id);
    if (!Number.isInteger(candidate.tokens) || candidate.tokens < 0) {
      throw new Error(`Candidate ${candidate.id} has invalid tokens`);
    }
    for (const [name, value] of [
      ["fit", candidate.fit],
      ["stability", candidate.stability],
      ["leakage", candidate.leakage],
    ] as const) {
      if (!Number.isFinite(value) || value < 0 || value > 1) {
        throw new Error(`Candidate ${candidate.id} has invalid ${name}`);
      }
    }
  }
}

export function paretoFrontier(candidates: CandidatePoint[]): CandidatePoint[] {
  assertComparableCandidates(candidates);
  return [...candidates]
    .filter((candidate) => {
      return !candidates.some((other) => {
        const noWorse =
          other.tokens <= candidate.tokens &&
          other.fit >= candidate.fit &&
          other.stability >= candidate.stability &&
          other.leakage <= candidate.leakage;
        const strictlyBetter =
          other.tokens < candidate.tokens ||
          other.fit > candidate.fit ||
          other.stability > candidate.stability ||
          other.leakage < candidate.leakage;
        return other.id !== candidate.id && noWorse && strictlyBetter;
      });
    })
    .sort(
      (a, b) =>
        a.tokens - b.tokens ||
        b.fit - a.fit ||
        b.stability - a.stability ||
        a.leakage - b.leakage ||
        a.id.localeCompare(b.id),
    );
}
