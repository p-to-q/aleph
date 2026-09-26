import type { AlephRun, CandidatePoint } from "./types.ts";
import { paretoFrontier } from "./frontier.ts";

export function annotateFrontier(run: AlephRun): AlephRun {
  const frontierRanks = new Map(
    paretoFrontier(run.candidates).map((candidate, index) => [candidate.id, index + 1]),
  );
  const candidates: CandidatePoint[] = run.candidates.map((candidate) => {
    const { frontierRank: _staleRank, ...observation } = candidate;
    const frontierRank = frontierRanks.get(candidate.id);
    return frontierRank === undefined ? observation : { ...observation, frontierRank };
  });
  return { ...run, candidates };
}
