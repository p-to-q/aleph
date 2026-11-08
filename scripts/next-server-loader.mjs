import { createRequire } from 'node:module'
import { pathToFileURL } from 'node:url'

export async function resolve(specifier, context, nextResolve) {
  if (specifier === 'next/server' && context.parentURL?.startsWith('file:')) {
    const parentRequire = createRequire(context.parentURL)
    return {
      url: pathToFileURL(parentRequire.resolve(specifier)).href,
      shortCircuit: true,
    }
  }
  return nextResolve(specifier, context)
}
