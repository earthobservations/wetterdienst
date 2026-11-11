// Writes the types of the backend's OpenAPI document to .generated/api-schema.d.ts (git-ignored; GH-3908).
// A checkout of the whole repository has the document; the app image's install stage copies only app/, where
// there is none and nothing needs the types (they are erased from the build), so there it does nothing.
import { spawnSync } from 'node:child_process'
import { existsSync } from 'node:fs'
import process from 'node:process'
import { fileURLToPath } from 'node:url'

const snapshot = fileURLToPath(new URL('../../tests/ui/openapi.snapshot.json', import.meta.url))
const output = fileURLToPath(new URL('../.generated/api-schema.d.ts', import.meta.url))

if (existsSync(snapshot)) {
  const run = spawnSync('openapi-typescript', [snapshot, '-o', output], { stdio: 'inherit', shell: true })
  process.exit(run.status ?? 1)
}
