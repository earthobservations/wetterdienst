import type { Value } from '#shared/types/api'
import { mountSuspended } from '@nuxt/test-utils/runtime'
import { afterEach, describe, expect, it, vi } from 'vitest'
import QueryPanel from '~/components/QueryPanel.vue'

// the panel's DuckDB, answered by DuckDB-wasm's Node build rather than the browser's bundles, which
// load from a CDN into a worker
vi.mock('@duckdb/duckdb-wasm', async () => {
  const { nodeDuckDB } = await import('../../duckdb-node')
  const db = await nodeDuckDB()
  return {
    getJsDelivrBundles: () => ({}),
    selectBundle: async () => ({ mainModule: '', mainWorker: '' }),
    ConsoleLogger: class {},
    AsyncDuckDB: class {
      async instantiate() {}
      async connect() {
        const conn = db.connect()
        return { query: async (sql: string) => conn.query(sql), close: async () => conn.close() }
      }

      async terminate() {}
    },
  }
})

// the worker the panel starts for the browser's bundle, which the Node build has no use for
vi.stubGlobal('Worker', class {})
vi.spyOn(URL, 'createObjectURL').mockReturnValue('blob:duckdb')
vi.spyOn(URL, 'revokeObjectURL').mockReturnValue()

const data: Value[] = [{
  station_id: '01048',
  resolution: 'daily',
  dataset: 'climate_summary',
  parameter: 'temperature_air_mean_2m',
  timestamp: '2020-01-01T00:00:00.000000+00:00',
  value: 1.5,
  quality: 10,
}]

const mounted: { unmount: () => void }[] = []

afterEach(() => {
  mounted.splice(0).forEach(wrapper => wrapper.unmount())
})

// the rows the panel hands on for a query
async function transform(query: string) {
  const wrapper = await mountSuspended(QueryPanel, { props: { data, expectedColumns: Object.keys(data[0]!), mode: 'station' } })
  mounted.push(wrapper)
  await wrapper.find('button').trigger('click')
  await wrapper.find('textarea').setValue(query)
  const run = wrapper.findAll('button').find(button => button.text() === 'Run Query')!
  await run.trigger('click')
  await vi.waitFor(() => expect(wrapper.emitted('dataTransformed')).toHaveLength(1))
  return wrapper.emitted<[Value[]]>('dataTransformed')![0]![0]
}

describe('queryPanel', () => {
  it('hands on a query\'s values plain: a timestamp as the REST API writes it, a count as a number', async () => {
    // a TIMESTAMP came as milliseconds since the epoch, which the table's timestamp cell failed on,
    // and a COUNT(*) as a BigInt
    const rows = await transform('SELECT station_id, resolution, dataset, parameter, timestamp::TIMESTAMP AS timestamp, value, quality, COUNT(*) OVER () AS n FROM data')
    expect(rows).toEqual([{ ...data[0], n: 1 }])
  })
})
