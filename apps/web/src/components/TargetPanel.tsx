import type { RefObject } from "react";
import type { AlephRun } from "../../../../packages/core/src/types";
import { displayMode, observationBadge, observationCaption } from "../lib/runView";
import { Metric } from "./Metric";

interface TargetPanelProps {
  textareaRef: RefObject<HTMLTextAreaElement>;
  initialText: string;
  run: AlephRun;
  onGenerate: () => void;
  onExport: () => void;
  loading: boolean;
}

export function TargetPanel({ textareaRef, initialText, run, onGenerate, onExport, loading }: TargetPanelProps) {
  return (
    <aside className="panel target">
      <p className="eyebrow">
        Target Output
        <span className="mode-badge">{observationBadge(run.observations)}</span>
      </p>
      <textarea ref={textareaRef} defaultValue={initialText} />
      <div className="button-row">
        <button onClick={onGenerate} disabled={loading}>
          {loading ? "Searching…" : "Generate Compression Path"}
        </button>
        <button className="secondary" onClick={onExport} disabled={loading}>Export JSON</button>
      </div>
      <p className="caption">{observationCaption(run)}</p>

      <div className="setup-grid">
        <Metric label="Mode" value={displayMode(run.config.mode)} />
        <Metric label="Budget" value={run.config.budget.candidates} />
        <Metric label="Samples" value={run.config.budget.repeatedSamples} />
        <Metric label="Max tokens" value={run.config.budget.maxPromptTokens} />
      </div>
    </aside>
  );
}
