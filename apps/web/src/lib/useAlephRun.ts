import { useMemo, useRef, useState, useCallback } from "react";
import { fixtureRuns } from "../../../../packages/fixtures/src/index";
import type { AlephRun } from "../../../../packages/core/src/types";
import { selectedCandidate, selectedCandidateIndex } from "./runView";
import { type AppMode, searchRun } from "./runClient";

type Status = "idle" | "loading" | "error";

export type FixtureOption = {
  id: string;
  label: string;
};

export const fixtureOptions: FixtureOption[] = fixtureRuns.map((run) => ({
  id: run.id,
  label: run.target.label ?? run.id,
}));

export function useAlephRun() {
  const [fixtureIndex, setFixtureIndex] = useState(0);
  const fixture = fixtureRuns[fixtureIndex] as AlephRun;
  const [run, setRun] = useState<AlephRun>(fixture);
  const [selectedId, setSelectedId] = useState(fixture.selectedCandidateId);
  const [status, setStatus] = useState<Status>("idle");
  const [error, setError] = useState<string | null>(null);
  const [mode, setMode] = useState<AppMode>("mock");
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const abortRef = useRef<AbortController | null>(null);

  const selected = useMemo(() => selectedCandidate(run, selectedId), [run, selectedId]);
  const selectedIndex = selectedCandidateIndex(run, selected);

  function selectFixture(index: number) {
    const next = fixtureRuns[index] as AlephRun;
    setFixtureIndex(index);
    setRun(next);
    setSelectedId(next.selectedCandidateId);
    setError(null);
    setStatus("idle");
    if (textareaRef.current) textareaRef.current.value = next.target.text;
  }

  const generateRun = useCallback(async () => {
    const targetText = textareaRef.current?.value?.trim() ?? "";
    if (!targetText) return;

    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    setStatus("loading");
    setError(null);

    try {
      const result = await searchRun(targetText, mode, controller.signal);
      setRun(result);
      setSelectedId(result.selectedCandidateId);
      setStatus("idle");
    } catch (err) {
      if (err instanceof Error && err.name === "AbortError") return;
      setError(err instanceof Error ? err.message : String(err));
      setStatus("error");
    }
  }, [mode]);

  return {
    error,
    fixture,
    fixtureIndex,
    mode,
    run,
    selected,
    selectedIndex,
    status,
    textareaRef,
    generateRun,
    selectCandidate: setSelectedId,
    selectFixture,
    setMode,
  };
}

export type UseAlephRunState = ReturnType<typeof useAlephRun>;
