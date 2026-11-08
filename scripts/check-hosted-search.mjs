import assert from 'node:assert/strict'
import { register } from 'node:module'

const target = 'A sufficiently long target for the hosted route.'
const calls = []
let primaryCalls = 0

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
    if (primaryCalls === 3) return new Response('primary stub failure', { status: 400 })
    return new Response(JSON.stringify({
      choices: [{ message: { content: 'discarded primary output' } }],
    }), { status: 200, headers: { 'content-type': 'application/json' } })
  }

  assert.equal(url.hostname, 'fallback.test')
  return new Response(JSON.stringify({
    choices: [{ message: { content: 'fallback stub output' } }],
  }), { status: 200, headers: { 'content-type': 'application/json' } })
}

const { POST } = await import('../web/app/api/search/route.ts')
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
assert.equal(explicit.stability, 1)
assert.match(explicit.note, /Model-generated Explicit Reconstruction baseline/)
assert.ok(fallbackCalls.some((call) =>
  call.body.messages.at(-1).content.includes(`Reproduce the following output exactly:\n\n${target}`),
))
assert.ok(run.candidates.every((candidate) => candidate.output !== 'discarded primary output'))

console.log('check-hosted-search: ok — fallback identity, measured baseline, repeated samples')
