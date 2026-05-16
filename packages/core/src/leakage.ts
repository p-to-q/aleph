function ngrams(tokens: string[], n: number): Set<string> {
  const out = new Set<string>();
  for (let i = 0; i <= tokens.length - n; i += 1) out.add(tokens.slice(i, i + n).join(" "));
  return out;
}

export function leakageScore(prompt: string, target: string): number {
  const p = prompt.toLowerCase().match(/[\p{L}\p{N}]+/gu) ?? [];
  const t = target.toLowerCase().match(/[\p{L}\p{N}]+/gu) ?? [];
  if (p.length === 0 || t.length === 0) return 0;
  const unigramOverlap = p.filter((tok) => t.includes(tok)).length / p.length;
  const targetTrigrams = ngrams(t, 3);
  const promptTrigrams = ngrams(p, 3);
  const trigramOverlap = promptTrigrams.size
    ? [...promptTrigrams].filter((gram) => targetTrigrams.has(gram)).length / promptTrigrams.size
    : 0;
  return Math.max(0, Math.min(1, 0.55 * unigramOverlap + 0.45 * trigramOverlap));
}
