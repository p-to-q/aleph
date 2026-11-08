import assert from 'node:assert/strict'
import { register } from 'node:module'

const target = 'A sufficiently long target for the hosted route.'
const calls = []
let primaryCalls = 0
let fallbackCallsSeen = 0
let emitEmptyPrimary = false
let emitOversizedPrimary = false

process.env.ALEPH_CUSTOM_API_BASE_URL = 'https://primary.test/v1'
process.env.ALEPH_CUSTOM_API_KEY = 'primary-test-key'
process.env.ALEPH_CUSTOM_API_MODEL = 'primary-test-model'
process.env.ALEPH_CUSTOM_API_FALLBACK_BASE_URL = 'https://fallback.test/v1'
process.env.ALEPH_CUSTOM_API_FALLBACK_KEY = 'fallback-test-key'
process.env.ALEPH_CUSTOM_API_FALLBACK_MODEL = 'fallback-test-model'

register('./next-server-loader.mjs', import.meta.url)

globalThis.fetch = async (input, init = {}) => {
  const url = new URL(input)
  const body = JSON.parse(init.body)
  calls.push({ host: url.hostname, body })

  if (url.hostname === 'primary.test') {
    primaryCalls += 1
    if (emitOversizedPrimary) {
      return new Response(JSON.stringify({
        choices: [{ message: { content: 'x'.repeat(MAX_SEARCH_OUTPUT_CHARS + 1) } }],
      }), { status: 200, headers: { 'content-type': 'application/json' } })
    }
    if (emitEmptyPrimary && primaryCalls === 1) {
      emitEmptyPrimary = false
      return new Response(JSON.stringify({
        choices: [{ message: { content: '```text\n```' } }],
      }), { status: 200, headers: { 'content-type': 'application/json' } })
    }
    if (primaryCalls === 3) return new Response('primary stub failure', { status: 400 })
    return new Response(JSON.stringify({
      choices: [{ message: { content: 'discarded primary output' } }],
    }), { status: 200, headers: { 'content-type': 'application/json' } })
  }

  assert.equal(url.hostname, 'fallback.test')
  fallbackCallsSeen += 1
  return new Response(JSON.stringify({
    choices: [{ message: { content: fallbackCallsSeen % 2 ? 'fallback stub output' : 'fallback stub output!' } }],
  }), { status: 200, headers: { 'content-type': 'application/json' } })
}

const { POST } = await import('../web/app/api/search/route.ts')
const { MAX_SEARCH_OUTPUT_CHARS, MAX_SEARCH_TARGET_CHARS } = await import('../web/app/lib/search-limits.mjs')

const malformedJsonResponse = await POST(new Request('http://localhost/api/search', {
  method: 'POST', headers: { 'content-type': 'application/json' }, body: '{',
}))
assert.equal(malformedJsonResponse.status, 400)
const nonObjectBodyResponse = await POST(new Request('http://localhost/api/search', {
  method: 'POST', headers: { 'content-type': 'application/json' }, body: 'null',
}))
assert.equal(nonObjectBodyResponse.status, 400)
const nonStringTargetResponse = await POST(new Request('http://localhost/api/search', {
  method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ target_text: 42 }),
}))
assert.equal(nonStringTargetResponse.status, 422)
const oversizedTargetResponse = await POST(new Request('http://localhost/api/search', {
  method: 'POST', headers: { 'content-type': 'application/json' },
  body: JSON.stringify({ target_text: 'x'.repeat(MAX_SEARCH_TARGET_CHARS + 1) }),
}))
assert.equal(oversizedTargetResponse.status, 413)
assert.equal(calls.length, 0)

const paddedTarget = `${' '.repeat(8)}${'x'.repeat(MAX_SEARCH_TARGET_CHARS)}`
const paddedTargetResponse = await POST(new Request('http://localhost/api/search', {
  method: 'POST', headers: { 'content-type': 'application/json' },
  body: JSON.stringify({ target_text: paddedTarget }),
}))
assert.equal(paddedTargetResponse.status, 200)
assert.ok(calls.some((call) =>
  call.body.messages.at(-1).content.includes(`${'x'.repeat(MAX_SEARCH_TARGET_CHARS)}`),
))

primaryCalls = 0
fallbackCallsSeen = 0
calls.length = 0
const response = await POST(new Request('http://localhost/api/search', {
  method: 'POST',
  headers: { 'content-type': 'application/json' },
  body: JSON.stringify({ target_text: target }),
}))

assert.equal(response.status, 200)
const run = await response.json()
const fallbackCalls = calls.filter((call) => call.host === 'fallback.test')
assert.equal(run.config.model, 'fallback-test-model')
assert.equal(run.config.budget.repeatedSamples, 2)
assert.equal(run.candidates.length, 5)
assert.equal(primaryCalls, 4)
assert.equal(fallbackCalls.length, 10)
assert.ok(fallbackCalls.every((call) => call.body.model === 'fallback-test-model'))
assert.equal(run.candidates.filter((candidate) => candidate.role === 'explicit_reconstruction').length, 1)

const explicit = run.candidates.find((candidate) => candidate.role === 'explicit_reconstruction')
assert.equal(explicit.output, 'fallback stub output')
assert.notEqual(explicit.fit, 1)
assert.equal(explicit.stability, 0.98)
assert.match(explicit.note, /Model-generated Explicit Reconstruction baseline/)
assert.ok(fallbackCalls.some((call) =>
  call.body.messages.at(-1).content.includes(`Reproduce the following output exactly:\n\n${target}`),
))
assert.ok(run.candidates.every((candidate) => candidate.output !== 'discarded primary output'))

// Oversized outputs switch connections before any similarity scoring begins.
primaryCalls = 0
fallbackCallsSeen = 0
calls.length = 0
emitOversizedPrimary = true
const oversizedOutputResponse = await POST(new Request('http://localhost/api/search', {
  method: 'POST', headers: { 'content-type': 'application/json' },
  body: JSON.stringify({ target_text: target }),
}))
emitOversizedPrimary = false
assert.equal(oversizedOutputResponse.status, 200)
assert.equal((await oversizedOutputResponse.json()).config.model, 'fallback-test-model')
assert.equal(fallbackCallsSeen, 10)

// A primary run that fits its allotted window should finish even when fallback
// credentials are configured.
primaryCalls = 0
fallbackCallsSeen = 0
calls.length = 0
let virtualNow = Date.now()
const realDateNow = Date.now
Date.now = () => virtualNow
const thirtySecondPrimaryFetch = globalThis.fetch
globalThis.fetch = async (input, init = {}) => {
  const url = new URL(input)
  const body = JSON.parse(init.body)
  calls.push({ host: url.hostname, body })
  assert.equal(url.hostname, 'primary.test')
  primaryCalls += 1
  virtualNow += 2800
  return new Response(JSON.stringify({
    choices: [{ message: { content: 'complete primary output' } }],
  }), { status: 200, headers: { 'content-type': 'application/json' } })
}
const primaryResponse = await POST(new Request('http://localhost/api/search', {
  method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ target_text: target }),
}))
Date.now = realDateNow
globalThis.fetch = thirtySecondPrimaryFetch
assert.equal(primaryResponse.status, 200)
assert.equal((await primaryResponse.json()).config.model, 'primary-test-model')
assert.equal(primaryCalls, 10)
assert.equal(fallbackCallsSeen, 0)

// A pending provider request must observe the abort before fallback regenerates
// the complete run inside its reserved window.
primaryCalls = 0
fallbackCallsSeen = 0
calls.length = 0
let primaryAbortObserved = false
let acceleratePrimaryAbort = true
const realSetTimeout = globalThis.setTimeout
globalThis.setTimeout = (callback, delay, ...args) => {
  if (acceleratePrimaryAbort && delay > 1000) {
    acceleratePrimaryAbort = false
    return realSetTimeout(callback, 0, ...args)
  }
  return realSetTimeout(callback, delay, ...args)
}
const pendingPrimaryFetch = globalThis.fetch
globalThis.fetch = async (input, init = {}) => {
  const url = new URL(input)
  const body = JSON.parse(init.body)
  calls.push({ host: url.hostname, body })
  if (url.hostname === 'primary.test') {
    primaryCalls += 1
    return new Promise((resolve, reject) => {
      const signal = init.signal
      const rejectAsAborted = () => {
        primaryAbortObserved = true
        reject(new DOMException('The operation was aborted.', 'AbortError'))
      }
      if (signal?.aborted) rejectAsAborted()
      else signal?.addEventListener('abort', rejectAsAborted, { once: true })
    })
  }
  assert.equal(url.hostname, 'fallback.test')
  fallbackCallsSeen += 1
  return new Response(JSON.stringify({
    choices: [{ message: { content: fallbackCallsSeen % 2 ? 'fallback stub output' : 'fallback stub output!' } }],
  }), { status: 200, headers: { 'content-type': 'application/json' } })
}
const abortFallbackStartedAt = Date.now()
const abortFallbackResponse = await POST(new Request('http://localhost/api/search', {
  method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ target_text: target }),
}))
const abortFallbackElapsed = Date.now() - abortFallbackStartedAt
globalThis.fetch = pendingPrimaryFetch
globalThis.setTimeout = realSetTimeout
assert.equal(abortFallbackResponse.status, 200)
assert.equal((await abortFallbackResponse.json()).config.model, 'fallback-test-model')
assert.equal(primaryAbortObserved, true)
assert.ok(primaryCalls >= 1 && primaryCalls <= 2)
assert.equal(fallbackCallsSeen, 10)
assert.ok(abortFallbackElapsed < 2000)

// Simulate a slow primary run that reaches its budget before fallback. The
// fallback still gets its reserved window and can regenerate all five pairs.
primaryCalls = 0
fallbackCallsSeen = 0
calls.length = 0
virtualNow = Date.now()
Date.now = () => virtualNow
const slowPrimaryResponse = globalThis.fetch
globalThis.fetch = async (input, init = {}) => {
  const url = new URL(input)
  const body = JSON.parse(init.body)
  calls.push({ host: url.hostname, body })
  if (url.hostname === 'primary.test') {
    primaryCalls += 1
    virtualNow += 6250
    return new Response(JSON.stringify({
      choices: [{ message: { content: 'discarded primary output' } }],
    }), { status: 200, headers: { 'content-type': 'application/json' } })
  }
  assert.equal(url.hostname, 'fallback.test')
  fallbackCallsSeen += 1
  virtualNow += 1000
  return new Response(JSON.stringify({
    choices: [{ message: { content: fallbackCallsSeen % 2 ? 'fallback stub output' : 'fallback stub output!' } }],
  }), { status: 200, headers: { 'content-type': 'application/json' } })
}
const budgetResponse = await POST(new Request('http://localhost/api/search', {
  method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ target_text: target }),
}))
Date.now = realDateNow
globalThis.fetch = slowPrimaryResponse
assert.equal(budgetResponse.status, 200)
assert.equal((await budgetResponse.json()).config.model, 'fallback-test-model')
assert.equal(primaryCalls, 6)
assert.equal(fallbackCallsSeen, 10)

// A non-empty provider body can still clean to an empty sample; it must also
// select the complete fallback path.
primaryCalls = 0
fallbackCallsSeen = 0
calls.length = 0
emitEmptyPrimary = true
const emptyResponse = await POST(new Request('http://localhost/api/search', {
  method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ target_text: target }),
}))
assert.equal(emptyResponse.status, 200)
const emptyFallbackRun = await emptyResponse.json()
assert.equal(emptyFallbackRun.config.model, 'fallback-test-model')
assert.equal(fallbackCallsSeen, 10)
assert.ok(emptyFallbackRun.candidates.every((candidate) => candidate.output.length > 0))

console.log('check-hosted-search: ok — fallback identity, deadlines, abort recovery, measured stability, empty-output recovery')
