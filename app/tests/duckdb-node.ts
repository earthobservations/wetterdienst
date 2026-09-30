import type { DuckDBBindings } from '@duckdb/duckdb-wasm/blocking'
import { createRequire } from 'node:module'
import { dirname, join } from 'node:path'

/**
 * DuckDB-wasm's own Node build, so a query answers as it answers the query panel: an Arrow table DuckDB
 * wrote, read with the Arrow the panel's DuckDB reads it with. Loaded by path, as the build is CommonJS
 * and the browser's bundles need a worker.
 *
 * @returns An open database
 */
export async function nodeDuckDB(): Promise<DuckDBBindings> {
  const require = createRequire(import.meta.url)
  const duckdb: typeof import('@duckdb/duckdb-wasm/blocking') = require('@duckdb/duckdb-wasm/blocking')
  const dist = dirname(require.resolve('@duckdb/duckdb-wasm/blocking'))
  const db = await duckdb.createDuckDB({
    mvp: { mainModule: join(dist, 'duckdb-mvp.wasm'), mainWorker: join(dist, 'duckdb-node-mvp.worker.cjs') },
    eh: { mainModule: join(dist, 'duckdb-eh.wasm'), mainWorker: join(dist, 'duckdb-node-eh.worker.cjs') },
  }, new duckdb.VoidLogger(), duckdb.NODE_RUNTIME)
  await db.instantiate()
  db.open({})
  return db
}
