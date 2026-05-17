import type { AlephRun } from "../../../../packages/core/src/types";

const API_BASE = (import.meta as Record<string, unknown> & { env: Record<string, string> }).env.VITE_API_BASE ?? "http://127.0.0.1:8010";

export type AppMode = "mock" | "local_mlx_search";

export async function searchRun(targetText: string, mode: AppMode, signal?: AbortSignal): Promise<AlephRun> {
  const res = await fetch(`${API_BASE}/api/search`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ target_text: targetText, mode }),
    signal,
  });

  if (!res.ok) {
    const detail = await res.json().catch(() => ({}));
    throw new Error((detail as { detail?: string }).detail ?? `HTTP ${res.status}`);
  }

  return res.json() as Promise<AlephRun>;
}

export function exportRun(run: AlephRun) {
  const blob = new Blob([JSON.stringify(run, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `aleph-run-${run.id}.json`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
