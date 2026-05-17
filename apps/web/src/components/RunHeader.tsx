import type { AppMode } from "../lib/runClient";
import type { FixtureOption } from "../lib/useAlephRun";
import { displayMode, observationLabel } from "../lib/runView";
import type { AlephRun } from "../../../../packages/core/src/types";

interface RunHeaderProps {
  fixtureIndex: number;
  fixtureOptions: FixtureOption[];
  mode: AppMode;
  run: AlephRun;
  onFixtureChange: (index: number) => void;
  onModeChange: (mode: AppMode) => void;
}

export function RunHeader({ fixtureIndex, fixtureOptions, mode, run, onFixtureChange, onModeChange }: RunHeaderProps) {
  return (
    <header className="topbar">
      <div className="brand"><img src="/brand/aleph-black.png" alt="" /><span>Aleph</span></div>
      <div className="topbar-right">
        <div className="run-strip" aria-label="Run mode and settings">
          <span>{observationLabel(run)}</span>
          {run.observations.mode === "white_box" && run.observations.tokenLoss?.length ? <span>token NLL</span> : null}
          <span>{displayMode(run.config.mode)}</span>
          <span>{run.config.model}</span>
        </div>
        <label className="mode-select">
          <select value={fixtureIndex} onChange={(event) => onFixtureChange(Number(event.target.value))}>
            {fixtureOptions.map((fixture, index) => (
              <option key={fixture.id} value={index}>{fixture.label}</option>
            ))}
          </select>
        </label>
        <label className="mode-select">
          <select value={mode} onChange={(event) => onModeChange(event.target.value as AppMode)}>
            <option value="mock">mock</option>
            <option value="local_mlx_search">local mlx</option>
          </select>
        </label>
      </div>
    </header>
  );
}
