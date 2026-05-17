import type { AlephRun, CandidatePoint } from "../../../../packages/core/src/types";
import {
  candidateEndpoint,
  candidatePlotPosition,
  candidateRangeProgress,
  candidateRank,
  candidateSummary,
  displayMode,
  observationBadge,
  percent,
} from "../lib/runView";
import { Metric } from "./Metric";
import { SearchDial } from "./SearchDial";

interface ParetoFrontierProps {
  run: AlephRun;
  selected: CandidatePoint;
  selectedIndex: number;
  onSelect: (id: string) => void;
}

export function ParetoFrontier({ run, selected, selectedIndex, onSelect }: ParetoFrontierProps) {
  const endpoint = candidateEndpoint(run, selectedIndex);

  return (
    <>
      <div className="panel frontier">
        <div className="section-head">
          <div>
            <p className="eyebrow">
              Pareto Frontier
              <span className="mode-badge">{observationBadge(run.observations)}</span>
              <span className="mode-badge">{displayMode(run.config.mode)}</span>
            </p>
            <h1>{selected.label}</h1>
            <p className="summary">{candidateSummary(selected)}</p>
          </div>
          <SearchDial progress={candidateRangeProgress(selectedIndex, run.candidates.length)} />
        </div>

        <div className="plot" aria-label="Pareto frontier candidates">
          {run.candidates.map((c, index) => (
            <button
              key={c.id}
              className={c.id === selected.id ? "dot active" : "dot"}
              style={candidatePlotPosition(c, index, run.candidates.length)}
              onClick={() => onSelect(c.id)}
              title={`${c.label}: ${c.tokens} tokens / ${percent(c.fit)} fit`}
            />
          ))}
        </div>

        <div className="candidate-ribbon" aria-label="Candidate sequence">
          {run.candidates.map((c, index) => (
            <button
              key={c.id}
              className={c.id === selected.id ? "candidate-step active" : "candidate-step"}
              onClick={() => onSelect(c.id)}
              title={`${c.label}: ${c.tokens} tokens`}
              type="button"
            >
              <span>{index + 1}</span>
              <b>{c.tokens}t</b>
            </button>
          ))}
        </div>

        <div className="slider-row">
          <span>Shortest Found</span>
          <input
            type="range"
            min="0"
            max={run.candidates.length - 1}
            value={selectedIndex}
            onChange={(event) => onSelect(run.candidates[Number(event.target.value)].id)}
          />
          <span>Explicit Reconstruction</span>
        </div>
        <p className="slider-status">
          <strong>{endpoint}</strong>
          <span>{selected.label} / rank {candidateRank(selected)} of {run.candidates.length}</span>
        </p>
      </div>

      <div className="metrics six">
        <Metric label="Tokens" value={selected.tokens} />
        <Metric label="Fit" value={percent(selected.fit)} />
        <Metric label="Stable" value={percent(selected.stability)} />
        <Metric label="Compress" value={percent(selected.compression)} />
        <Metric label="Leak" value={percent(selected.leakage)} />
        <Metric label="NLL" value={selected.nll?.toFixed(2) ?? "--"} />
      </div>
    </>
  );
}
