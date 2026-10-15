// Product-side, read-only loader for saved AlephRun files — the open half of
// the file-first run round trip (docs/next-backlog.md, "P1: File-First Run
// Import/Export").
//
// This module is deliberately NOT the research import surface. The strict,
// fail-closed importer lives at search/engine/import_aleph_run.py and
// additionally verifies canonical bytes, duplicate-free strict JSON, and the
// projection digest against the bundle. The product flow validates against
// the same schema (schemas/aleph-run.schema.json) plus the static exporter
// invariants that need no cryptography, keeps candidate identities and the
// selected candidate, and labels every imported value as a projection.
// It never claims replay or digest verification — see
// docs/research/product-run-file-import-note.md for the recorded boundary.
//
// No runtime dependencies: JSON.parse plus the shared schema, so the same
// code runs in the browser, in the Next.js build, and under Node
// (scripts/check-run-file.mjs imports this file directly).

import schema from '../../../schemas/aleph-run.schema.json' with { type: 'json' }

export type RunFileIssue = { path: string; message: string }

export type RunFilePoint = {
  id: string
  role?: 'candidate' | 'explicit_reconstruction'
  label: string
  epsilon: number
  prompt: string
  length: number
  similarity: number
  stability: number
  output?: string
}

export type ParsedRunFile = {
  /** The full parsed value, kept for saving/provenance. */
  value: Record<string, unknown>
  id: string
  selectedCandidateId: string
}

export type RunFileParseResult =
  | { ok: true; run: ParsedRunFile; points: RunFilePoint[]; selectedIndex: number }
  | { ok: false; issues: RunFileIssue[] }

export const RUN_FILE_LIMITS = {
  /** Text cap for the browser demo (characters; ~8 MB). */
  maxTextLength: 8 * 1024 * 1024,
} as const

const ARTIFACT_REF_SCHEMA_VERSION = 'aleph-artifact-ref/0.1.0'
const DIGEST_PATTERN = /^sha256:[0-9a-f]{64}$/
// Unpaired UTF-16 surrogates are not valid Unicode; the engine fails them
// closed when it recomputes canonical bytes, and the browser path mirrors
// that refusal because a re-save would silently replace them.
const LONE_SURROGATE =
  /[\uD800-\uDBFF](?![\uDC00-\uDFFF])|(?<![\uD800-\uDBFF])[\uDC00-\uDFFF]/

type SchemaNode = { [key: string]: unknown }

const ROOT_SCHEMA = schema as unknown as SchemaNode

function resolveRef(ref: string): SchemaNode {
  const parts = ref.replace(/^#\//, '').split('/')
  let node: unknown = ROOT_SCHEMA
  for (const part of parts) {
    node = (node as SchemaNode)[part]
  }
  if (!node) throw new Error(`unknown schema ref: ${ref}`)
  return node as SchemaNode
}

function typeName(value: unknown): string {
  if (Array.isArray(value)) return 'array'
  if (value === null) return 'null'
  return typeof value
}

// The schema walker covers exactly the subset of JSON Schema used by
// schemas/aleph-run.schema.json ($ref/$defs, type, integer, enum, minimum,
// maximum, required, properties, additionalProperties, items) — the same
// subset scripts/check-fixtures.mjs walks.
function validateValue(
  definition: SchemaNode,
  value: unknown,
  path: string,
  issues: RunFileIssue[],
): void {
  if (definition.$ref) {
    validateValue(resolveRef(definition.$ref as string), value, path, issues)
    return
  }

  if (typeof value === 'number' && !Number.isFinite(value)) {
    issues.push({ path, message: 'non-finite number is not valid canonical JSON (fail closed)' })
    return
  }

  const enumValues = definition.enum as unknown[] | undefined
  if (enumValues && !enumValues.includes(value)) {
    issues.push({ path, message: `expected one of ${enumValues.join(', ')}` })
  }

  const type = definition.type as string | undefined
  if (type) {
    const actual = typeName(value)
    if (type === 'integer') {
      if (!Number.isInteger(value)) issues.push({ path, message: `expected integer, got ${actual}` })
    } else if (actual !== type) {
      issues.push({ path, message: `expected ${type}, got ${actual}` })
      return
    }
  }

  if (typeof value === 'number') {
    const minimum = definition.minimum as number | undefined
    const maximum = definition.maximum as number | undefined
    if (minimum !== undefined && value < minimum) {
      issues.push({ path, message: `below minimum ${minimum}` })
    }
    if (maximum !== undefined && value > maximum) {
      issues.push({ path, message: `above maximum ${maximum}` })
    }
  }

  if (type === 'string' && typeof value === 'string' && LONE_SURROGATE.test(value)) {
    issues.push({ path, message: 'string contains an unpaired surrogate (not valid Unicode)' })
  }

  if (type === 'object' && typeof value === 'object' && value !== null && !Array.isArray(value)) {
    const record = value as Record<string, unknown>
    const properties = (definition.properties as Record<string, SchemaNode>) ?? {}
    for (const key of (definition.required as string[]) ?? []) {
      if (!(key in record)) issues.push({ path, message: `missing required property ${key}` })
    }
    if (definition.additionalProperties === false) {
      for (const key of Object.keys(record)) {
        if (!(key in properties)) issues.push({ path, message: `unexpected property ${key}` })
      }
    }
    for (const [key, propertyDefinition] of Object.entries(properties)) {
      if (key in record) validateValue(propertyDefinition, record[key], `${path}.${key}`, issues)
    }
  }

  if (type === 'array' && Array.isArray(value)) {
    const items = definition.items as SchemaNode
    value.forEach((item, index) => validateValue(items, item, `${path}[${index}]`, issues))
  }
}

// The engine file importer requires artifactRef and recomputes
// artifactRef.projectionDigest from canonical bytes. The product accepts the
// projection files the repository also ships without a ref (fixtures, live
// route runs) and, when a ref is present, checks every static property except
// the digest recomputation: shape-only, never an authenticity claim.
function checkArtifactRef(value: Record<string, unknown>, issues: RunFileIssue[]): void {
  const ref = value.artifactRef
  if (ref === undefined) return
  if (typeof ref !== 'object' || ref === null || Array.isArray(ref)) return // schema reports the shape
  const record = ref as Record<string, unknown>
  if (record.schemaVersion !== ARTIFACT_REF_SCHEMA_VERSION) {
    issues.push({
      path: '$.artifactRef.schemaVersion',
      message: `must be '${ARTIFACT_REF_SCHEMA_VERSION}' (unknown versions fail closed)`,
    })
  }
  if (record.runId !== value.id) {
    issues.push({
      path: '$.artifactRef.runId',
      message: `must match the run id (got ${JSON.stringify(record.runId)})`,
    })
  }
  for (const name of ['bundleDigest', 'projectionDigest'] as const) {
    const digest = record[name]
    if (typeof digest !== 'string' || !DIGEST_PATTERN.test(digest)) {
      issues.push({
        path: `$.artifactRef.${name}`,
        message: 'must be a sha256: digest (64 lowercase hex digits)',
      })
    }
  }
}

// Mirrors the derivations the exporter guarantees; called only when the value
// is schema-clean (same split as the engine importer).
function checkExporterInvariants(value: Record<string, unknown>, issues: RunFileIssue[]): void {
  const candidates = value.candidates as Record<string, unknown>[]
  if (candidates.length === 0) {
    issues.push({
      path: '$.candidates',
      message: 'must not be empty: an empty candidate set loses every coordinate',
    })
    return
  }
  const ids = candidates.map((candidate) => candidate.id as string)
  const config = value.config as Record<string, unknown>
  const budget = config.budget as Record<string, unknown>
  if (budget.candidates !== candidates.length) {
    issues.push({
      path: '$.config.budget.candidates',
      message: `must equal the candidate count (${candidates.length}), got ${JSON.stringify(budget.candidates)}`,
    })
  }
  const tokens = candidates.map((candidate) => candidate.tokens as number)
  const maximum = Math.max(...tokens)
  // The shipped fixtures declare maxPromptTokens as a budget cap (>= the
  // observed maximum) while the engine exporter derives it as exactly the
  // observed maximum for its exports; the product accepts both styles, so it
  // only checks that candidates stay inside the declared budget.
  if ((budget.maxPromptTokens as number) < maximum) {
    issues.push({
      path: '$.config.budget.maxPromptTokens',
      message: `must be at least the maximum candidate token count (${maximum}), got ${JSON.stringify(budget.maxPromptTokens)}`,
    })
  }
  const selected = value.selectedCandidateId as string
  if (!ids.includes(selected)) {
    issues.push({
      path: '$.selectedCandidateId',
      message: `'${selected}' is not among the candidate ids`,
    })
  }
}

const round4 = (value: number): number => Math.round(value * 10000) / 10000

export function parseRunFile(text: string): RunFileParseResult {
  if (text.length > RUN_FILE_LIMITS.maxTextLength) {
    return {
      ok: false,
      issues: [
        {
          path: '$',
          message: `file is too large for the browser demo (${text.length} characters; limit ${RUN_FILE_LIMITS.maxTextLength})`,
        },
      ],
    }
  }
  if (text.startsWith('\uFEFF')) {
    return {
      ok: false,
      issues: [
        { path: '$', message: 'file starts with a UTF-8 byte-order mark; canonical run files do not' },
      ],
    }
  }

  let value: unknown
  try {
    value = JSON.parse(text)
  } catch (error) {
    return { ok: false, issues: [{ path: '$', message: `file is not valid JSON: ${(error as Error).message}` }] }
  }
  if (typeof value !== 'object' || value === null || Array.isArray(value)) {
    return { ok: false, issues: [{ path: '$', message: 'top level must be a JSON object' }] }
  }

  const record = value as Record<string, unknown>
  const issues: RunFileIssue[] = []
  validateValue(ROOT_SCHEMA, record, '$', issues)
  const schemaClean = issues.length === 0
  checkArtifactRef(record, issues)
  if (schemaClean) checkExporterInvariants(record, issues)
  if (issues.length > 0) return { ok: false, issues }

  const candidates = record.candidates as Record<string, unknown>[]
  const points: RunFilePoint[] = candidates.map((candidate) => ({
    id: candidate.id as string,
    role: candidate.role as RunFilePoint['role'],
    label: candidate.label as string,
    epsilon: round4(1 - (candidate.fit as number)),
    prompt: candidate.prompt as string,
    length: candidate.tokens as number,
    similarity: candidate.fit as number,
    stability: candidate.stability as number,
    output: candidate.output as string,
  }))
  points.sort((a, b) => b.epsilon - a.epsilon)

  const selectedCandidateId = record.selectedCandidateId as string
  // selectedIndex is guaranteed >= 0: the selected-id membership invariant ran
  // above and a failure returned before this point.
  const selectedIndex = points.findIndex((point) => point.id === selectedCandidateId)

  return {
    ok: true,
    run: { value: record, id: record.id as string, selectedCandidateId },
    points,
    selectedIndex,
  }
}

export function downloadTextFor(run: ParsedRunFile, rawText: string | null): string {
  // A run that was opened from a file saves back the exact text that was read
  // (byte-preserving for valid UTF-8 without a BOM); a run that never existed
  // as a file (for example a live route response) is written as pretty JSON
  // with a trailing newline.
  return rawText ?? `${JSON.stringify(run.value, null, 2)}\n`
}
