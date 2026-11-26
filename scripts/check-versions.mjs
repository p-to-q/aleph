import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
const read = (path) => JSON.parse(readFileSync(path, 'utf8'))
const root = read('package.json')
const lock = read('package-lock.json')
assert.equal(lock.version, root.version, 'root lock version')
for (const path of ['', ...root.workspaces]) {
  const manifest = read(path ? `${path}/package.json` : 'package.json')
  assert.equal(manifest.version, root.version, `${path || 'root'} manifest version`)
  assert.equal(lock.packages[path]?.version, root.version, `${path || 'root'} lock version`)
}
assert.equal(read('release-status.json').productVersion, root.version, 'release mapping')
const health = readFileSync('web/app/health/route.ts', 'utf8')
assert.match(health, /import \{ version \} from ['"]\.\.\/\.\.\/package\.json['"]/, 'health uses app manifest')
console.log(`check-versions: all product workspaces, lockfile, release mapping and health use ${root.version}`)
