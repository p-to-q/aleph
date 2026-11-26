/** Bounded health probe. Never invokes search or a model provider. */
export async function probeSearchHealth(url, {
  configured = true,
  requireHostedCapability = false,
  timeoutMs = 3000,
  fetchImpl = globalThis.fetch,
} = {}) {
  if (!configured) return false
  const controller = new AbortController()
  let timer
  /** @type {Promise<boolean>} */
  const deadline = new Promise((resolve) => {
    timer = setTimeout(() => {
      controller.abort()
      resolve(false)
    }, timeoutMs)
  })
  try {
    const request = Promise.resolve()
      .then(() => fetchImpl(url, { signal: controller.signal }))
      .then(async (response) => {
        if (!response.ok) return false
        if (!requireHostedCapability) return true
        const body = await response.json()
        return body?.hosted_black_box_configured === true
      })
    // Include body parsing in the deadline, even if a transport ignores abort.
    return await Promise.race([request, deadline])
  } catch {
    return false
  } finally {
    clearTimeout(timer)
  }
}
