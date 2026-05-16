import type { AlephRun, CandidatePoint } from "./types";
import { paretoFrontier } from "./frontier";

export function annotateFrontier(run: AlephRun): AlephRun {
  const frontierIds = paretoFrontier(run.candidates).map((candidate) => candidate.id);
  const candidates: CandidatePoint[] = run.candidates.map((candidate) => ({
    ...candidate,
    frontierRank: frontierIds.includes(candidate.id) ? frontierIds.indexOf(candidate.id) + 1 : candidate.frontierRank,
  }));
  return { ...run, candidates };
}
