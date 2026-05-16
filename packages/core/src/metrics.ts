import type { CandidatePoint } from "./types";

export function tokenEstimate(text: string): number {
  return text.trim() ? text.trim().split(/\s+/).length : 0;
}

export function compressionRatio(candidateTokens: number, explicitTokens: number): number {
  if (explicitTokens <= 0) return 0;
  return Math.max(0, Math.min(1, 1 - candidateTokens / explicitTokens));
}

export function scoreCandidate(candidate: CandidatePoint): number {
  // A simple UI ordering score. Real search services should own the objective.
  return candidate.fit * 0.45 + candidate.stability * 0.25 + candidate.compression * 0.2 - candidate.leakage * 0.1;
}
