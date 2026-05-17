import type { AlephRun, CandidatePoint, ObservationSet } from "../../../../packages/core/src/types";

export function percent(value: number) {
  return `${Math.round(value * 100)}%`;
}

export function displayMode(value: string) {
  return value.replace("_", " ");
}

export function observationLabel(run: AlephRun) {
  return `${run.observations.mode} observations`;
}

export function observationBadge(observations: ObservationSet) {
  return observations.mode;
}

export function observationCaption(run: AlephRun) {
  if (run.observations.mode === "fixture") {
    return "Fixture mode - product scaffolding, not model evidence.";
  }
  if (run.observations.mode === "white_box" && run.observations.tokenLoss?.length) {
    return "White-box adapter output - token NLL is present for this run.";
  }
  return `${run.observations.mode} - search results from the live API.`;
}

export function tokenLossSummary(observations: ObservationSet) {
  const losses = observations.tokenLoss?.map((point) => point.loss).filter(Number.isFinite) ?? [];
  if (!losses.length) return null;
  const total = losses.reduce((sum, loss) => sum + loss, 0);
  return {
    avg: total / losses.length,
    min: Math.min(...losses),
    max: Math.max(...losses),
    count: losses.length,
  };
}

export function selectedCandidate(run: AlephRun, selectedId: string) {
  return run.candidates.find((candidate) => candidate.id === selectedId) ?? run.candidates[0];
}

export function selectedCandidateIndex(run: AlephRun, candidate: CandidatePoint) {
  return run.candidates.findIndex((item) => item.id === candidate.id);
}

export function candidateEndpoint(run: AlephRun, index: number) {
  if (index === 0) return "Shortest Found";
  if (index === run.candidates.length - 1) return "Explicit Reconstruction";
  return "Compression Path";
}

export function candidateSummary(candidate: CandidatePoint) {
  return `${candidate.tokens} tokens / ${percent(candidate.fit)} fit / ${percent(candidate.stability)} stable / ${percent(candidate.leakage)} leak`;
}

export function candidateRank(candidate: CandidatePoint) {
  return candidate.frontierRank ?? "--";
}

export function candidateRangeProgress(index: number, total: number) {
  return total > 0 ? (index + 1) / total : 0;
}

export function candidatePlotPosition(candidate: CandidatePoint, index: number, total: number) {
  const spread = total > 1 ? index / (total - 1) : 0;
  return {
    left: `${10 + spread * 80}%`,
    bottom: `${Math.round(candidate.fit * 78)}%`,
  };
}
