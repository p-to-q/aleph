import React, { useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import sampleRun from "../../../packages/fixtures/src/sample-run.json";
import type { AlephRun } from "../../../packages/core/src/types";
import "./styles.css";

function pct(value: number) {
  return `${Math.round(value * 100)}%`;
}

function App() {
  const run = sampleRun as AlephRun;
  const [selectedId, setSelectedId] = useState(run.selectedCandidateId);
  const selected = useMemo(() => run.candidates.find((c) => c.id === selectedId) ?? run.candidates[0], [run, selectedId]);
  const selectedIndex = run.candidates.findIndex((c) => c.id === selected.id);
  const evalPassed = run.observations.evalSuite?.filter((item) => item.passed).length ?? 0;
  const evalTotal = run.observations.evalSuite?.length ?? 0;

  return (
    <main className="shell">
      <header className="topbar">
        <div className="brand"><img src="/brand/aleph-black.png" alt=""/><span>Aleph</span></div>
        <div className="meta">{run.config.model} / {run.config.decoding} / {run.config.metric}</div>
      </header>

      <section className="hero">
        <aside className="panel target">
          <p className="eyebrow">Target Output</p>
          <textarea defaultValue={run.target.text} />
          <button>Generate Compression Path</button>
          <p className="caption">Fixture mode. The observations below are product scaffolding, not model evidence.</p>

          <div className="setup-grid">
            <Metric label="Mode" value={run.config.mode.replace("_", " ")} />
            <Metric label="Budget" value={run.config.budget.candidates} />
          </div>
        </aside>

        <section className="center">
          <div className="panel frontier">
            <div className="section-head">
              <div>
                <p className="eyebrow">Pareto Frontier</p>
                <h1>{selected.label}</h1>
                <p className="summary">{selected.tokens} tokens / {pct(selected.fit)} fit / {pct(selected.stability)} stable / {pct(selected.leakage)} leak</p>
              </div>
              <SearchDial progress={(selectedIndex + 1) / run.candidates.length} />
            </div>

            <div className="plot" aria-label="Pareto frontier candidates">
              {run.candidates.map((c, index) => (
                <button
                  key={c.id}
                  className={c.id === selected.id ? "dot active" : "dot"}
                  style={{ left: `${10 + index * 20}%`, bottom: `${Math.round(c.fit * 78)}%` }}
                  onClick={() => setSelectedId(c.id)}
                  title={`${c.label}: ${c.tokens} tokens / ${pct(c.fit)} fit`}
                />
              ))}
            </div>

            <div className="slider-row">
              <span>Shortest Found</span>
              <input
                type="range"
                min="0"
                max={run.candidates.length - 1}
                value={selectedIndex}
                onChange={(event) => setSelectedId(run.candidates[Number(event.target.value)].id)}
              />
              <span>Explicit Reconstruction</span>
            </div>
          </div>

          <div className="metrics six">
            <Metric label="Tokens" value={selected.tokens} />
            <Metric label="Fit" value={pct(selected.fit)} />
            <Metric label="Stable" value={pct(selected.stability)} />
            <Metric label="Compress" value={pct(selected.compression)} />
            <Metric label="Leak" value={pct(selected.leakage)} />
            <Metric label="NLL" value={selected.nll?.toFixed(2) ?? "--"} />
          </div>
        </section>

        <aside className="panel output">
          <p className="eyebrow">Current Prompt</p>
          <pre>{selected.prompt}</pre>
          <p className="eyebrow">Model Output</p>
          <pre>{selected.output}</pre>
          <p className="note">{selected.note}</p>
        </aside>
      </section>

      <section className="observations">
        <Panel title="Token Loss">
          <div className="tokens">
            {run.observations.tokenLoss?.map((t, index) => (
              <span key={`${t.token}-${index}`} style={{ opacity: 0.35 + Math.min(t.loss / 2, 0.65) }} title={`loss ${t.loss} / rank ${t.rank ?? "--"}`}>{t.token}</span>
            ))}
          </div>
        </Panel>

        <Panel title="Waveform">
          <div className="wave">
            {run.observations.waveform?.map((p) => <i key={p.index} style={{ height: `${20 + p.value * 70}px` }} />)}
          </div>
        </Panel>

        <Panel title="Attribution">
          <div className="attribution">
            {run.observations.attribution?.map((item) => (
              <p key={item.promptToken}><span>{item.promptToken}</span><meter min="0" max="1" value={item.score} /> <b>+{item.deltaLossIfRemoved?.toFixed(2)}</b></p>
            ))}
          </div>
        </Panel>

        <Panel title="Loss Curve">
          <div className="loss-curve">
            {run.observations.lossCurve?.map((point) => <i key={point.step} style={{ height: `${20 + (5 - point.loss) * 16}px` }} title={`step ${point.step} / loss ${point.loss}`} />)}
          </div>
          <p className="caption">step {run.observations.lossCurve?.at(-1)?.step} / loss {run.observations.lossCurve?.at(-1)?.loss}</p>
        </Panel>

        <Panel title="Compression Exposure">
          <div className="exposure-list">
            {run.observations.exposureVectors?.map((item) => <p key={item.name}><span>{item.name}</span><b>{item.level.replace("_", " ")} · {item.value}%</b></p>)}
          </div>
        </Panel>

        <Panel title="Eval Suite">
          <p className="summary">{evalPassed} of {evalTotal} passing</p>
          {run.observations.evalSuite?.map((item) => <p key={item.name}>{item.passed ? "✓" : "×"} {item.name}</p>)}
        </Panel>
      </section>
    </main>
  );
}

function SearchDial(props: { progress: number }) {
  return (
    <div className="dial" style={{ "--dial": `${Math.round(props.progress * 360)}deg` } as React.CSSProperties}>
      <span>{Math.round(props.progress * 100)}%</span>
    </div>
  );
}

function Metric(props: { label: string; value: string | number }) {
  return <div className="metric"><strong>{props.value}</strong><span>{props.label}</span></div>;
}

function Panel(props: { title: string; children: React.ReactNode }) {
  return <div className="panel mini"><p className="eyebrow">{props.title}</p>{props.children}</div>;
}

createRoot(document.getElementById("root")!).render(<App />);
