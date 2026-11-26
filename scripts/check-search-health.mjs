import assert from 'node:assert/strict'
import { probeSearchHealth } from '../web/app/lib/search-health.mjs'

let calls = 0
const healthy = async () => { calls += 1; return { ok: true } }
assert.equal(await probeSearchHealth('http://localhost:8000/health', {
  configured: false, fetchImpl: healthy,
}), false)
assert.equal(calls, 0, 'hosted unconfigured MLX must make no local request')
assert.equal(await probeSearchHealth('https://mlx.test/health', { fetchImpl: healthy }), true)
for (const fetchImpl of [
  async () => ({ ok: false }),
  () => { throw new Error('sync transport failure') },
  async () => { throw new Error('network failure') },
]) assert.equal(await probeSearchHealth('/health', { fetchImpl }), false)
for (const value of [true, false, undefined, 'true', 1]) {
  assert.equal(await probeSearchHealth('/health', {
    requireHostedCapability: true,
    fetchImpl: async () => ({ ok: true, json: async () => ({ hosted_black_box_configured: value }) }),
  }), value === true)
}
assert.equal(await probeSearchHealth('/health', {
  requireHostedCapability: true,
  fetchImpl: async () => ({ ok: true, json: async () => { throw new Error('invalid JSON') } }),
}), false)
let timedOutSignal
const stalled = probeSearchHealth('https://stalled.test/health', {
  timeoutMs: 15,
  fetchImpl: async (_url, { signal }) => {
    timedOutSignal = signal
    return new Promise(() => {}) // Deliberately ignores abort.
  },
})
assert.equal(await probeSearchHealth('/health', { fetchImpl: healthy }), true,
  'healthy mode must resolve before an unrelated stalled mode')
assert.equal(await stalled, false)
assert.equal(timedOutSignal.aborted, true)
assert.equal(await probeSearchHealth('/health', {
  timeoutMs: 15, requireHostedCapability: true,
  fetchImpl: async () => ({ ok: true, json: () => new Promise(() => {}) }),
}), false, 'body parsing is also bounded')
console.log('check-search-health: ok — endpoint policy, independent probes, bounded transport/body, capability validation')
