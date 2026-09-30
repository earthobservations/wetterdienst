import type { Value } from '#shared/types/api'
import { AsyncDuckDB } from '@duckdb/duckdb-wasm'
import { mountSuspended } from '@nuxt/test-utils/runtime'
import { flushPromises } from '@vue/test-utils'
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

// A hold on a statement, opened by the test at the point where the order of two callers matters
function gate() {
  let open!: () => void
  const opened = new Promise<void>((resolve) => {
    open = resolve
  })
  return { opened, open }
}

// the undoing of each test's hold on DuckDB's connections, after the panels are unmounted
const unwatched: (() => void)[] = []

afterEach(() => {
  unwatched.splice(0).forEach(restore => restore())
})

// The statements the panel hands DuckDB, in order, each held until `hold` answers for it
function watchStatements(hold: (sql: string) => Promise<void> | undefined = () => undefined) {
  const statements: string[] = []
  const connect = AsyncDuckDB.prototype.connect
  const spy = vi.spyOn(AsyncDuckDB.prototype, 'connect').mockImplementation(async function (this: AsyncDuckDB) {
    const conn = await connect.call(this)
    const query = conn.query.bind(conn)
    return Object.assign(conn, {
      query: async (sql: string) => {
        statements.push(sql)
        await hold(sql)
        return query(sql)
      },
    })
  })
  unwatched.push(() => spy.mockRestore())
  return statements
}

// a panel in query mode on `data`
async function queryMode() {
  const wrapper = await mountSuspended(QueryPanel, { props: { data, expectedColumns: Object.keys(data[0]!), mode: 'station' } })
  mounted.push(wrapper)
  await wrapper.find('button').trigger('click')
  return wrapper
}

function runButton(wrapper: Awaited<ReturnType<typeof queryMode>>) {
  return wrapper.findAll('button').find(button => button.text() === 'Run Query')!
}

const creates = (statements: string[]) => statements.filter(sql => sql.startsWith('CREATE TABLE'))

describe('queryPanel table load', () => {
  it('offers no second run while the first starts DuckDB and loads the table', async () => {
    // Run Query stayed clickable until the table was loaded, and two runs loaded it interleaved
    const hold = gate()
    const statements = watchStatements(sql => sql.startsWith('CREATE TABLE') ? hold.opened : undefined)
    const wrapper = await queryMode()
    await runButton(wrapper).trigger('click')
    await vi.waitFor(() => expect(creates(statements)).toHaveLength(1))
    expect(runButton(wrapper).attributes('disabled')).toBeDefined()
    hold.open()
    await vi.waitFor(() => expect(wrapper.emitted('dataTransformed')).toHaveLength(1))
    expect(wrapper.emitted<[Value[]]>('dataTransformed')![0]![0]).toEqual(data)
  })

  it('loads the table once for a run and the syntax check made while it loads', async () => {
    // the check loaded the table as well, its DROP and CREATE between the run's statements
    const hold = gate()
    const statements = watchStatements(sql => sql.startsWith('CREATE TABLE') ? hold.opened : undefined)
    const instantiate = vi.spyOn(AsyncDuckDB.prototype, 'instantiate')
    unwatched.push(() => instantiate.mockRestore())
    const wrapper = await queryMode()
    await wrapper.find('textarea').setValue('SELECT * FROM data')
    await runButton(wrapper).trigger('click')
    // the check, 500 ms after the edit, is under way once its spinner shows
    await vi.waitFor(() => expect(wrapper.find('div.absolute.top-2.right-2').exists()).toBe(true), { timeout: 2000 })
    await flushPromises()
    hold.open()
    await vi.waitFor(() => expect(wrapper.emitted('dataTransformed')).toHaveLength(1))
    await vi.waitFor(() => expect(wrapper.find('div.absolute.top-2.right-2').exists()).toBe(false))
    expect(wrapper.emitted<[Value[]]>('dataTransformed')![0]![0]).toEqual(data)
    expect(creates(statements)).toHaveLength(1)
    // and one database, which the check found started
    expect(instantiate).toHaveBeenCalledTimes(1)
  })
})
