import type { CandidatePoint } from "./types";

export function paretoFrontier(candidates: CandidatePoint[]): CandidatePoint[] {
  return candidates
    .filter((candidate) => {
      return !candidates.some((other) => {
        const noWorse = other.tokens <= candidate.tokens && other.fit >= candidate.fit && other.stability >= candidate.stability;
        const strictlyBetter = other.tokens < candidate.tokens || other.fit > candidate.fit || other.stability > candidate.stability;
        return other.id !== candidate.id && noWorse && strictlyBetter;
      });
    })
    .sort((a, b) => a.tokens - b.tokens);
}
