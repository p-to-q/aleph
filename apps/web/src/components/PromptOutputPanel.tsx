import { useEffect, useState } from "react";
import type { CandidatePoint } from "../../../../packages/core/src/types";
import { candidateRank, percent } from "../lib/runView";

const TYPEWRITER_MS = 6;

function TypewriterPre({ text }: { text: string }) {
  const [displayed, setDisplayed] = useState(text);

  useEffect(() => {
    setDisplayed("");
    let pos = 0;
    const id = setInterval(() => {
      pos += 3;
      setDisplayed(text.slice(0, pos));
      if (pos >= text.length) clearInterval(id);
    }, TYPEWRITER_MS);
    return () => clearInterval(id);
  }, [text]);

  return <pre>{displayed}</pre>;
}

export function PromptOutputPanel({ candidate }: { candidate: CandidatePoint }) {
  return (
    <aside className="panel output">
      <p className="eyebrow">
        Current Prompt
        <span className="mode-badge">candidate {candidateRank(candidate)}</span>
      </p>
      <pre>{candidate.prompt}</pre>
      <div className="prompt-meta">
        <span>{candidate.tokens} tokens</span>
        <span>{percent(candidate.compression)} compression</span>
        <span>{percent(candidate.leakage)} leak</span>
      </div>
      <p className="eyebrow">Model Output</p>
      <TypewriterPre text={candidate.output} />
      <p className="note">{candidate.note}</p>
    </aside>
  );
}
