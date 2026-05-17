import type { ObservationSet } from "../../../../packages/core/src/types";
import { displayMode, observationBadge, tokenLossSummary } from "../lib/runView";
import { Panel } from "./Panel";

function Empty({ label }: { label: string }) {
  return <p className="caption no-data">{label} unavailable for this observation mode.</p>;
}

export function ObservationPanels({ observations }: { observations: ObservationSet }) {
  const evalPassed = observations.evalSuite?.filter((item) => item.passed).length ?? 0;
  const evalTotal = observations.evalSuite?.length ?? 0;
  const badge = observationBadge(observations);
  const lossSummary = tokenLossSummary(observations);

  return (
    <section className="observations">
      <Panel title="Token Loss" badge={badge}>
        {observations.tokenLoss?.length ? (
          <>
            {lossSummary ? (
              <div className="loss-summary">
                <span>{lossSummary.count} tokens</span>
                <span>avg {lossSummary.avg.toFixed(2)}</span>
                <span>max {lossSummary.max.toFixed(2)}</span>
              </div>
            ) : null}
            <div className="tokens">
              {observations.tokenLoss.map((t, index) => (
                <span
                  key={`${t.token}-${index}`}
                  style={{ opacity: 0.35 + Math.min(t.loss / 2, 0.65) }}
                  title={`loss ${t.loss} / rank ${t.rank ?? "--"}`}
                >
                  {t.token}
                </span>
              ))}
            </div>
            {observations.mode === "white_box" ? <p className="caption">token NLL from local adapter output</p> : null}
          </>
        ) : <Empty label="Token loss" />}
      </Panel>

      <Panel title="Waveform" badge={badge}>
        {observations.waveform?.length ? (
          <div className="wave">
            {observations.waveform.map((p) => <i key={p.index} style={{ height: `${20 + p.value * 70}px` }} />)}
          </div>
        ) : <Empty label="Waveform" />}
      </Panel>

      <Panel title="Attribution" badge={badge}>
        {observations.attribution?.length ? (
          <div className="attribution">
            {observations.attribution.map((item) => (
              <p key={item.promptToken}>
                <span>{item.promptToken}</span>
                <meter min="0" max="1" value={item.score} />
                <b>+{item.deltaLossIfRemoved?.toFixed(2)}</b>
              </p>
            ))}
          </div>
        ) : <Empty label="Attribution" />}
      </Panel>

      <Panel title="Loss Curve" badge={badge}>
        {observations.lossCurve?.length ? (
          <>
            <div className="loss-curve">
              {observations.lossCurve.map((point) => (
                <i key={point.step} style={{ height: `${20 + (5 - point.loss) * 16}px` }} title={`step ${point.step} / loss ${point.loss}`} />
              ))}
            </div>
            <p className="caption">step {observations.lossCurve.at(-1)?.step} / loss {observations.lossCurve.at(-1)?.loss}</p>
          </>
        ) : <Empty label="Loss curve" />}
      </Panel>

      <Panel title="Compression Exposure" badge={badge}>
        {observations.exposureVectors?.length ? (
          <div className="exposure-list">
            {observations.exposureVectors.map((item) => (
              <p key={item.name}><span>{item.name}</span><b>{displayMode(item.level)} / {item.value}%</b></p>
            ))}
          </div>
        ) : <Empty label="Exposure vectors" />}
      </Panel>

      <Panel title="Eval Suite" badge={badge}>
        {observations.evalSuite?.length ? (
          <>
            <p className="summary">{evalPassed} of {evalTotal} passing</p>
            {observations.evalSuite.map((item) => (
              <p key={item.name}>{item.passed ? "✓" : "×"} {item.name}</p>
            ))}
          </>
        ) : <Empty label="Eval suite" />}
      </Panel>
    </section>
  );
}
