import { resolve as pathResolve } from 'node:path'
import { pathToFileURL } from 'node:url'

export async function resolve(specifier, context, nextResolve) {
  if (specifier === 'next/server') {
    return {
      url: pathToFileURL(pathResolve(process.cwd(), 'node_modules/next/server.js')).href,
      shortCircuit: true,
    }
  }
  return nextResolve(specifier, context)
}
