import type { CandidatePoint } from "./types.ts";

export function selectedCandidate(candidates: CandidatePoint[], selectedCandidateId: string): CandidatePoint {
  const candidate = candidates.find((item) => item.id === selectedCandidateId);
  if (!candidate) throw new Error(`Candidate not found: ${selectedCandidateId}`);
  return candidate;
}

export function sliderIndexForValue(candidates: CandidatePoint[], value: number): number {
  if (candidates.length === 0) return 0;
  const bounded = Math.max(0, Math.min(100, value));
  return Math.round((bounded / 100) * (candidates.length - 1));
}
