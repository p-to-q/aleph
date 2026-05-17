import { exportRun } from "../lib/runClient";
import type { UseAlephRunState } from "../lib/useAlephRun";
import { fixtureOptions } from "../lib/useAlephRun";
import { ObservationPanels } from "./ObservationPanels";
import { ParetoFrontier } from "./ParetoFrontier";
import { PromptOutputPanel } from "./PromptOutputPanel";
import { RunHeader } from "./RunHeader";
import { TargetPanel } from "./TargetPanel";

export function AlephConsole({ state }: { state: UseAlephRunState }) {
  const { error, fixture, fixtureIndex, mode, run, selected, selectedIndex, status, textareaRef } = state;

  return (
    <main className="shell">
      <RunHeader
        fixtureIndex={fixtureIndex}
        fixtureOptions={fixtureOptions}
        mode={mode}
        run={run}
        onFixtureChange={state.selectFixture}
        onModeChange={state.setMode}
      />

      {status === "error" && (
        <div className="error-bar">
          API unavailable - showing last result. <span>{error}</span>
        </div>
      )}

      <section className="hero">
        <TargetPanel
          textareaRef={textareaRef}
          initialText={fixture.target.text}
          run={run}
          onGenerate={state.generateRun}
          onExport={() => exportRun(run)}
          loading={status === "loading"}
        />

        <section className="center">
          <ParetoFrontier
            run={run}
            selected={selected}
            selectedIndex={selectedIndex}
            onSelect={state.selectCandidate}
          />
        </section>

        <PromptOutputPanel candidate={selected} />
      </section>

      <ObservationPanels observations={run.observations} />
    </main>
  );
}
