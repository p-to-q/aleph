import { NextResponse } from 'next/server'
import { createHash } from 'node:crypto'

export const runtime = 'nodejs'
export const maxDuration = 60

type SearchRequest = {
  target_text?: string
  mode?: string
  label?: string
}

type ObservationMode = 'mock' | 'black_box'

type CandidatePrompt = {
  id: string
  label: string
  prompt: string
  kind: 'explicit' | 'summary' | 'keywords' | 'coordinate' | 'minimal'
  plannedFit: number
  stability: number
}

type CandidatePoint = {
  id: string
  label: string
  prompt: string
  output: string
  tokens: number
  fit: number
  stability: number
  compression: number
  leakage: number
  frontierRank: number
  note: string
}

type ChatMessage = {
  role: 'system' | 'user'
  content: string
}

const HOSTED_PRIMARY_BASE_URL = 'https://zapi.aicc0.com/v1'
const HOSTED_FALLBACK_BASE_URL = 'https://jiuuij.de5.net/v1'
const HOSTED_PRIMARY_MODEL = 'deepseek-v4-pro'
const HOSTED_FALLBACK_MODEL = 'qwen3.6-27b-nothinking'
const HOSTED_BASE_URL = (process.env.ALEPH_CUSTOM_API_BASE_URL ??
  process.env.ALEPH_OPENAI_BASE_URL ??
  HOSTED_PRIMARY_BASE_URL).trim().replace(/\/$/, '')
const HOSTED_FALLBACK_URL = (process.env.ALEPH_CUSTOM_API_FALLBACK_BASE_URL ??
  HOSTED_FALLBACK_BASE_URL).trim().replace(/\/$/, '')
const HOSTED_API_KEY = (process.env.ALEPH_CUSTOM_API_KEY ??
  process.env.ALEPH_OPENAI_API_KEY ??
  '').trim()
const HOSTED_FALLBACK_API_KEY = (process.env.ALEPH_CUSTOM_API_FALLBACK_KEY ?? '').trim()
const HOSTED_MODEL = (process.env.ALEPH_CUSTOM_API_MODEL ??
  process.env.ALEPH_OPENAI_MODEL ??
  HOSTED_PRIMARY_MODEL).trim()
const HOSTED_FALLBACK_MODEL_CONFIG = (process.env.ALEPH_CUSTOM_API_FALLBACK_MODEL ??
  HOSTED_FALLBACK_MODEL).trim()
const HOSTED_TIMEOUT_MS = 45000
const HOSTED_TEMPERATURE = 0.2
const HOSTED_REPEATED_SAMPLES = 1
const HOSTED_RETRIES_PER_CONNECTION = 2

export async function POST(request: Request) {
  const body = (await request.json().catch(() => ({}))) as SearchRequest
  const targetText = (body.target_text ?? '').trim()

  if (targetText.length < 8) {
    return NextResponse.json(
      { detail: 'target_text must contain at least 8 characters' },
      { status: 422 },
    )
  }

  if (!hasHostedModelConfig()) {
    return NextResponse.json(mockSearch(targetText, body.label))
  }

  try {
    return NextResponse.json(await hostedBlackBoxSearch(targetText, body.label))
  } catch (error) {
    const detail = error instanceof Error ? error.message : 'Hosted model request failed.'
    return NextResponse.json({ detail }, { status: 502 })
  }
}

function mockSearch(targetText: string, label?: string) {
  const explicitPrompt = `Reproduce the following output exactly:\n\n${targetText}`
  const candidates = buildCandidatePrompts(targetText, explicitPrompt)
  const points = candidates.map((candidate, index) => {
    const output =
      candidate.kind === 'explicit' ? targetText : mockOutput(targetText, candidate.kind)
    const fit =
      candidate.kind === 'explicit'
        ? 1
        : Math.min(candidate.plannedFit, similarityScore(targetText, output) + 0.18)
    return {
      label: candidate.label,
      prompt: candidate.prompt,
      output,
      fit,
      stability: candidate.stability,
      note:
        candidate.kind === 'explicit'
          ? 'Explicit reconstruction baseline; target text is inside the prompt.'
          : 'Mock adapter: semantic sketch only, not a measured model output.',
    }
  })

  return buildRun({
    idPrefix: 'mock',
    targetText,
    label: label ?? 'Mock web search',
    model: 'mock',
    metric: 'mock_similarity',
    observationMode: 'mock',
    points,
    repeatedSamples: 1,
  })
}

async function hostedBlackBoxSearch(targetText: string, label?: string) {
  const explicitPrompt = `Reproduce the following output exactly:\n\n${targetText}`
  const candidates = buildCandidatePrompts(targetText, explicitPrompt)
  const repeatedSamples = HOSTED_REPEATED_SAMPLES
  const points = []

  for (const candidate of candidates) {
    if (candidate.kind === 'explicit') {
      points.push({
        label: candidate.label,
        prompt: candidate.prompt,
        output: targetText,
        fit: 1,
        stability: 1,
        note:
          'Explicit reconstruction baseline; target text is inside the prompt. No token NLL is available in black-box mode.',
      })
      continue
    }

    const outputs = []
    for (let sample = 0; sample < repeatedSamples; sample += 1) {
      outputs.push(await generateHostedOutput(candidate, targetText))
    }
    const output = chooseRepresentativeOutput(targetText, outputs)
    const fit = similarityScore(targetText, output)
    const stability = outputStability(outputs)

    points.push({
      label: candidate.label,
      prompt: candidate.prompt,
      output,
      fit,
      stability,
      note:
        'Hosted black-box model output. Fit and stability are computed from generated text; token NLL/logits are unavailable.',
    })
  }

  return buildRun({
    idPrefix: 'hosted',
    targetText,
    label: label ?? 'Hosted black-box search',
    model: HOSTED_MODEL,
    metric: hasCjk(targetText) ? 'cjk_lexical_overlap_and_sequence_fit' : 'lexical_overlap_and_sequence_fit',
    observationMode: 'black_box',
    points,
    repeatedSamples,
  })
}

async function withHostedRetries<T>(operation: () => Promise<T>) {
  let lastError: unknown
  for (let attempt = 0; attempt < HOSTED_RETRIES_PER_CONNECTION; attempt += 1) {
    try {
      return await operation()
    } catch (error) {
      lastError = error
      if (!isRetryableHostedError(error)) break
      await new Promise((resolve) => setTimeout(resolve, 450 * (attempt + 1)))
    }
  }
  throw lastError
}

function isRetryableHostedError(error: unknown) {
  if (!(error instanceof Error)) return false
  return /503|502|504|timeout|distributor|temporar/i.test(error.message)
}

function buildRun({
  idPrefix,
  targetText,
  label,
  model,
  metric,
  observationMode,
  points,
  repeatedSamples,
}: {
  idPrefix: string
  targetText: string
  label: string
  model: string
  metric: string
  observationMode: ObservationMode
  points: Array<{
    label: string
    prompt: string
    output: string
    fit: number
    stability: number
    note: string
  }>
  repeatedSamples: number
}) {
  const explicitPrompt = `Reproduce the following output exactly:\n\n${targetText}`
  const explicitTokens = Math.max(1, tokenCount(explicitPrompt))
  const candidates: CandidatePoint[] = points.map((point, index) => {
    const tokens = tokenCount(point.prompt)
    return {
      id: `search-point-${index + 1}`,
      label: point.label,
      prompt: point.prompt,
      output: point.output,
      tokens,
      fit: round4(point.fit),
      stability: round4(point.stability),
      compression: round4(1 - tokens / explicitTokens),
      leakage: leakageScore(point.prompt, targetText),
      frontierRank: index + 1,
      note: point.note,
    }
  })
  const selectedCandidateId = selectCandidate(candidates)

  return {
    id: `${idPrefix}-${createHash('sha1').update(`${idPrefix}:${targetText}`).digest('hex').slice(0, 10)}`,
    createdAt: new Date().toISOString(),
    target: { text: targetText, label },
    config: {
      model,
      decoding: observationMode === 'black_box' ? `temperature=${HOSTED_TEMPERATURE}` : 'deterministic',
      metric,
      budget: {
        candidates: candidates.length,
        maxPromptTokens: Math.max(...candidates.map((point) => point.tokens)),
        repeatedSamples,
      },
      mode: 'unrestricted',
    },
    candidates,
    selectedCandidateId,
    observations: {
      mode: observationMode,
      lossCurve: candidates.map((candidate, index) => ({
        step: index + 1,
        loss: round4(1 - candidate.fit),
        candidateId: candidate.id,
      })),
      evalSuite: [
        {
          name: observationMode === 'black_box' ? 'hosted_black_box_adapter' : 'mock_adapter',
          passed: true,
          score: observationMode === 'black_box' ? round4(Math.max(...candidates.map((candidate) => candidate.fit))) : undefined,
          note:
            observationMode === 'black_box'
              ? 'External model outputs were generated behind the server route; no logits or token NLL were requested.'
              : 'Mock route used because hosted model env vars are not configured.',
        },
      ],
    },
  }
}

function buildCandidatePrompts(
  targetText: string,
  explicitPrompt: string,
): CandidatePrompt[] {
  const sentences = sentenceSplit(targetText)
  const summary = sentences.slice(0, 2).join(' ')
  const keywords = keywordsFrom(targetText)
  const cueText = keywords.join(', ')
  const opening = sentences[0] ?? targetText

  return [
    {
      id: 'minimal-coordinate',
      label: 'Shortest Found',
      prompt: `Recover the target output from these compressed cues: ${cueText}. Preserve the intended semantic destination, but do not quote text that is not present in the prompt.`,
      kind: 'minimal',
      plannedFit: 0.48,
      stability: 0.58,
    },
    {
      id: 'keyword-coordinate',
      label: 'Keyword Coordinate',
      prompt: `Write the intended output using these coordinates: ${cueText}.`,
      kind: 'keywords',
      plannedFit: 0.62,
      stability: 0.66,
    },
    {
      id: 'opening-coordinate',
      label: 'Opening Coordinate',
      prompt: `Continue toward the intended output starting from this opening idea:\n\n${opening}`,
      kind: 'coordinate',
      plannedFit: 0.74,
      stability: 0.72,
    },
    {
      id: 'target-summary',
      label: 'Summary Anchor',
      prompt: `Write the target output described by this summary:\n\n${summary}`,
      kind: 'summary',
      plannedFit: 0.84,
      stability: 0.8,
    },
    {
      id: 'explicit-reconstruction',
      label: 'Explicit Reconstruction',
      prompt: explicitPrompt,
      kind: 'explicit',
      plannedFit: 1,
      stability: 1,
    },
  ]
}

function sentenceSplit(text: string) {
  const parts = text
    .trim()
    .split(/(?<=[.!?。！？])\s*/)
    .map((part) => part.trim())
    .filter(Boolean)
  return parts.length ? parts : [text.trim()]
}

function keywordsFrom(text: string) {
  const seen = new Set<string>()
  const quoted = text.match(/[《“"']([^《》“”"']{2,24})[》”"']/gu) ?? []
  for (const item of quoted) {
    seen.add(item.replace(/[《》“”"']/gu, '').trim().toLowerCase())
    if (seen.size >= 4) break
  }
  const words = text.toLowerCase().match(/[\p{L}\p{N}'-]+/gu) ?? []
  for (const word of words) {
    if (word.length >= 4 && word.length <= 28) seen.add(word)
    if (seen.size >= 8) break
  }
  if (seen.size < 4 && hasCjk(text)) {
    const chars = [...text.replace(/[^\p{Script=Han}]/gu, '')]
    for (let i = 0; i < chars.length - 1; i += 2) {
      seen.add(chars.slice(i, i + 2).join(''))
      if (seen.size >= 8) break
    }
  }
  if (!seen.size) seen.add(text.trim().slice(0, 48))
  return [...seen]
}

function mockOutput(targetText: string, kind: CandidatePrompt['kind']) {
  const sentences = sentenceSplit(targetText)
  const cues = keywordsFrom(targetText).slice(0, 5).join(', ')
  const prefix = takeUnits(targetText, kind === 'summary' ? 80 : 44)
  const cjk = hasCjk(targetText)

  if (kind === 'minimal') {
    return cjk
      ? `模拟输出：围绕 ${cues} 的压缩语义草图；缺少逐字复原证据。`
      : `Mock output: a compressed semantic sketch around ${cues}; exact wording is unavailable.`
  }
  if (kind === 'keywords') {
    return cjk
      ? `模拟输出：根据 ${cues} 展开主题，但仍只保留大意。`
      : `Mock output: expands the theme from ${cues}, preserving gist rather than verbatim text.`
  }
  if (kind === 'coordinate') {
    return cjk ? `${prefix}……（模拟续写，非真实模型采样）` : `${prefix}... (mock continuation, not a live model sample)`
  }
  return sentences.slice(0, 2).join(cjk ? '' : ' ')
}

function hasHostedModelConfig() {
  return HOSTED_BASE_URL.length > 0 && HOSTED_API_KEY.length > 0 && HOSTED_MODEL.length > 0
}

async function generateHostedOutput(candidate: CandidatePrompt, targetText: string) {
  const primary = { baseUrl: HOSTED_BASE_URL, apiKey: HOSTED_API_KEY, model: HOSTED_MODEL }
  const fallback =
    HOSTED_FALLBACK_URL && HOSTED_FALLBACK_API_KEY
      ? {
          baseUrl: HOSTED_FALLBACK_URL,
          apiKey: HOSTED_FALLBACK_API_KEY,
          model: HOSTED_FALLBACK_MODEL_CONFIG,
        }
      : null

  try {
    return await withHostedRetries(() => generateHostedOutputWithConnection(candidate, targetText, primary))
  } catch (error) {
    if (!fallback) throw error
    return withHostedRetries(() => generateHostedOutputWithConnection(candidate, targetText, fallback))
  }
}

async function generateHostedOutputWithConnection(
  candidate: CandidatePrompt,
  targetText: string,
  connection: { baseUrl: string; apiKey: string; model: string },
) {
  const controller = new AbortController()
  const timeout = setTimeout(() => controller.abort(), HOSTED_TIMEOUT_MS)
  const payload = {
    model: connection.model,
    messages: hostedMessages(candidate, targetText),
    temperature: HOSTED_TEMPERATURE,
    max_tokens: maxOutputTokens(targetText),
  }

  try {
    const response = await fetch(`${connection.baseUrl}/chat/completions`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${connection.apiKey}`,
      },
      body: JSON.stringify(payload),
      signal: controller.signal,
    })
    const text = await response.text()
    if (!response.ok) {
      throw new Error(`Hosted model returned ${response.status}: ${redactSecrets(text).slice(0, 400)}`)
    }
    const data = JSON.parse(text) as {
      choices?: Array<{ message?: { content?: string | Array<{ text?: string }>; reasoning_content?: string } }>
    }
    const message = data.choices?.[0]?.message
    const content = message?.content
    const output = contentToText(content).trim()
    if (!output) {
      const reason = typeof message?.reasoning_content === 'string' ? ' with reasoning_content only' : ''
      throw new Error(`Hosted model returned an empty output${reason}.`)
    }
    return cleanModelOutput(output)
  } catch (error) {
    if (error instanceof Error && error.name === 'AbortError') {
      throw new Error('Hosted model request timed out.')
    }
    throw error
  } finally {
    clearTimeout(timeout)
  }
}

function hostedMessages(candidate: CandidatePrompt, targetText: string): ChatMessage[] {
  const cjk = hasCjk(targetText)
  const system = cjk
    ? '你是 Aleph 的黑盒生成模型。只输出候选 prompt 生成的文本本身，不解释，不加标题，不提到 mock、评分或 Aleph。'
    : 'You are the black-box generator for Aleph. Return only the text generated from the candidate prompt. Do not explain, add headings, or mention scoring.'
  const user =
    candidate.kind === 'explicit'
      ? candidate.prompt
      : cjk
        ? `${candidate.prompt}\n\n请直接给出目标输出的最佳复原版本。不要描述你在做什么。`
        : `${candidate.prompt}\n\nReturn the best reconstruction of the intended output. Do not describe what you are doing.`
  return [
    { role: 'system', content: system },
    { role: 'user', content: user },
  ]
}

function contentToText(content: string | Array<{ text?: string }> | undefined) {
  if (typeof content === 'string') return content
  if (Array.isArray(content)) return content.map((part) => part.text ?? '').join('')
  return ''
}

function cleanModelOutput(output: string) {
  return output
    .replace(/^```(?:\w+)?\s*/u, '')
    .replace(/\s*```$/u, '')
    .trim()
}

function maxOutputTokens(targetText: string) {
  return Math.min(2048, Math.max(128, Math.ceil(tokenCount(targetText) * 2.4)))
}

function chooseRepresentativeOutput(targetText: string, outputs: string[]) {
  const usable = outputs.map((output) => output.trim()).filter(Boolean)
  if (!usable.length) return ''
  return usable.reduce((best, output) =>
    similarityScore(targetText, output) > similarityScore(targetText, best) ? output : best,
  )
}

function outputStability(outputs: string[]) {
  const usable = outputs.map((output) => output.trim()).filter(Boolean)
  if (usable.length <= 1) return usable.length ? 0.72 : 0
  const pairs: number[] = []
  for (let i = 0; i < usable.length; i += 1) {
    for (let j = i + 1; j < usable.length; j += 1) {
      pairs.push(similarityScore(usable[i], usable[j]))
    }
  }
  return pairs.length ? pairs.reduce((sum, value) => sum + value, 0) / pairs.length : 0.72
}

function selectCandidate(candidates: CandidatePoint[]) {
  if (!candidates.length) return ''
  return candidates.reduce((best, candidate) => {
    const bestScore = candidateScore(best)
    const score = candidateScore(candidate)
    return score > bestScore ? candidate : best
  }, candidates[0]).id
}

function candidateScore(candidate: CandidatePoint) {
  return candidate.fit * 0.55 + candidate.stability * 0.2 + candidate.compression * 0.2 - candidate.leakage * 0.1
}

function redactSecrets(text: string) {
  return [HOSTED_API_KEY, HOSTED_FALLBACK_API_KEY]
    .filter(Boolean)
    .reduce((safe, secret) => safe.split(secret).join('[redacted]'), text)
}

function tokenCount(text: string) {
  if (hasCjk(text)) return Math.max(1, Math.ceil([...text].filter((char) => /\S/u.test(char)).length / 2))
  return text.trim().split(/\s+/).filter(Boolean).length
}

function similarityScore(targetText: string, output: string) {
  const targetTextNormalized = targetText.trim()
  const outputNormalized = output.trim()
  if (targetTextNormalized && targetTextNormalized === outputNormalized) return 1
  const target = lexicalUnits(targetText)
  const actual = lexicalUnits(output)
  if (!target.length || !actual.length) return 0
  const actualSet = new Set(actual)
  const overlap = target.filter((token) => actualSet.has(token)).length
  const lexical = overlap / target.length
  const sequence = sequenceSimilarity(targetText, output)
  return round4(lexical * 0.58 + sequence * 0.42)
}

function leakageScore(prompt: string, targetText: string) {
  const promptTokens = lexicalUnits(prompt)
  const targetTokens = new Set(lexicalUnits(targetText))
  if (!promptTokens.length || !targetTokens.size) return 0
  return round4(
    promptTokens.filter((token) => targetTokens.has(token)).length /
      promptTokens.length,
  )
}

function lexicalUnits(text: string) {
  if (hasCjk(text)) {
    return [...text.toLowerCase()].filter((char) => /[\p{L}\p{N}]/u.test(char))
  }
  return text.toLowerCase().match(/[\p{L}\p{N}'-]+/gu) ?? []
}

function hasCjk(text: string) {
  return /\p{Script=Han}/u.test(text)
}

function takeUnits(text: string, count: number) {
  if (hasCjk(text)) return [...text].slice(0, count).join('')
  return text.trim().split(/\s+/).slice(0, count).join(' ')
}

function sequenceSimilarity(a: string, b: string) {
  const aa = [...a.trim()]
  const bb = [...b.trim()]
  if (!aa.length || !bb.length) return 0
  const maxLen = Math.max(aa.length, bb.length)
  const distance = levenshteinDistance(aa, bb)
  return clamp01(1 - distance / maxLen)
}

function levenshteinDistance(a: string[], b: string[]) {
  const prev = Array.from({ length: b.length + 1 }, (_, index) => index)
  const curr = Array.from({ length: b.length + 1 }, () => 0)
  for (let i = 1; i <= a.length; i += 1) {
    curr[0] = i
    for (let j = 1; j <= b.length; j += 1) {
      const cost = a[i - 1] === b[j - 1] ? 0 : 1
      curr[j] = Math.min(
        curr[j - 1] + 1,
        prev[j] + 1,
        prev[j - 1] + cost,
      )
    }
    for (let j = 0; j <= b.length; j += 1) prev[j] = curr[j]
  }
  return prev[b.length] ?? 0
}

function clamp01(value: number) {
  return Math.max(0, Math.min(1, value))
}

function round4(value: number) {
  return Math.round(clamp01(value) * 10000) / 10000
}
