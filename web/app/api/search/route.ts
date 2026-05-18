import { NextResponse } from 'next/server'
import { createHash } from 'node:crypto'

type SearchRequest = {
  target_text?: string
  mode?: string
  label?: string
}

type CandidatePrompt = {
  id: string
  label: string
  prompt: string
  kind: 'explicit' | 'summary' | 'keywords' | 'coordinate' | 'minimal'
}

export async function POST(request: Request) {
  const body = (await request.json().catch(() => ({}))) as SearchRequest
  const targetText = (body.target_text ?? '').trim()

  if (targetText.length < 8) {
    return NextResponse.json(
      { detail: 'target_text must contain at least 8 characters' },
      { status: 422 },
    )
  }

  return NextResponse.json(mockSearch(targetText, body.label))
}

function mockSearch(targetText: string, label?: string) {
  const explicitPrompt = `Reproduce the following output exactly:\n\n${targetText}`
  const candidates = buildCandidatePrompts(targetText, explicitPrompt)
  const explicitTokens = Math.max(1, tokenCount(explicitPrompt))
  const points = candidates.map((candidate, index) => {
    const output =
      candidate.kind === 'explicit' ? targetText : mockOutput(targetText, index)
    const fit = similarityScore(targetText, output)
    const tokens = tokenCount(candidate.prompt)
    return {
      id: `search-point-${index + 1}`,
      label: candidate.label,
      prompt: candidate.prompt,
      output,
      tokens,
      fit,
      stability: candidate.kind === 'explicit' ? 1 : 0.72,
      compression: clamp01(1 - tokens / explicitTokens),
      leakage: leakageScore(candidate.prompt, targetText),
      frontierRank: index + 1,
      note: 'mock adapter: deterministic browser-safe search result',
    }
  })

  points.sort((a, b) => a.tokens - b.tokens)

  return {
    id: `mock-${createHash('sha1').update(targetText).digest('hex').slice(0, 10)}`,
    createdAt: new Date().toISOString(),
    target: { text: targetText, label: label ?? 'Mock web search' },
    config: {
      model: 'mock',
      decoding: 'deterministic',
      metric: 'mock_similarity',
      budget: {
        candidates: points.length,
        maxPromptTokens: Math.max(...points.map((point) => point.tokens)),
        repeatedSamples: 1,
      },
      mode: 'unrestricted',
    },
    candidates: points,
    selectedCandidateId: points[0]?.id ?? 'search-point-1',
    observations: { mode: 'mock' },
  }
}

function buildCandidatePrompts(
  targetText: string,
  explicitPrompt: string,
): CandidatePrompt[] {
  const sentences = sentenceSplit(targetText)
  const summary = sentences.slice(0, 2).join(' ')
  const keywords = keywordsFrom(targetText).join(', ')
  const opening = sentences[0] ?? targetText

  return [
    {
      id: 'minimal-coordinate',
      label: 'Shortest Found (Mock)',
      prompt: `Recover the target output from these compressed cues: ${keywords}. Preserve the same semantic destination.`,
      kind: 'minimal',
    },
    {
      id: 'keyword-coordinate',
      label: 'Keyword Coordinate',
      prompt: `Write the intended output using these coordinates: ${keywords}.`,
      kind: 'keywords',
    },
    {
      id: 'opening-coordinate',
      label: 'Opening Coordinate',
      prompt: `Continue toward the intended output starting from this opening idea:\n\n${opening}`,
      kind: 'coordinate',
    },
    {
      id: 'target-summary',
      label: 'Summary Anchor',
      prompt: `Write the target output described by this summary:\n\n${summary}`,
      kind: 'summary',
    },
    {
      id: 'explicit-reconstruction',
      label: 'Explicit Reconstruction',
      prompt: explicitPrompt,
      kind: 'explicit',
    },
  ]
}

function sentenceSplit(text: string) {
  const parts = text
    .trim()
    .split(/(?<=[.!?])\s+/)
    .map((part) => part.trim())
    .filter(Boolean)
  return parts.length ? parts : [text.trim()]
}

function keywordsFrom(text: string) {
  const seen = new Set<string>()
  const words = text.toLowerCase().match(/[\w'-]+/g) ?? []
  for (const word of words) {
    if (word.length >= 4) seen.add(word)
    if (seen.size >= 8) break
  }
  return [...seen]
}

function mockOutput(targetText: string, index: number) {
  const words = targetText.trim().split(/\s+/).filter(Boolean)
  const keep = Math.max(8, Math.floor(words.length * (0.8 - index * 0.12)))
  return words.slice(0, keep).join(' ')
}

function tokenCount(text: string) {
  return text.trim().split(/\s+/).filter(Boolean).length
}

function similarityScore(targetText: string, output: string) {
  const target = tokenSet(targetText)
  const actual = tokenSet(output)
  if (!target.size || !actual.size) return 0
  const overlap = [...actual].filter((token) => target.has(token)).length
  return round4(overlap / target.size)
}

function leakageScore(prompt: string, targetText: string) {
  const promptTokens = prompt.toLowerCase().match(/[\w'-]+/g) ?? []
  const targetTokens = new Set(targetText.toLowerCase().match(/[\w'-]+/g) ?? [])
  if (!promptTokens.length || !targetTokens.size) return 0
  return round4(
    promptTokens.filter((token) => targetTokens.has(token)).length /
      promptTokens.length,
  )
}

function tokenSet(text: string) {
  return new Set(text.toLowerCase().match(/[\w'-]+/g) ?? [])
}

function clamp01(value: number) {
  return Math.max(0, Math.min(1, value))
}

function round4(value: number) {
  return Math.round(clamp01(value) * 10000) / 10000
}

