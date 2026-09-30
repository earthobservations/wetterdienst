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

// the undoing of each test's spies on DuckDB
const unwatched: (() => void)[] = []

afterEach(() => {
  unwatched.splice(0).forEach(restore => restore())
})

// The statements the panel hands DuckDB, in order, each held until `hold` answers for it; `ran`,
// those DuckDB was handed on, in the order it was. The connection closes once `closing` answers
function watchStatements(hold: (sql: string) => Promise<void> | undefined = () => undefined, closing: () => Promise<void> = async () => {}) {
  const statements: string[] = []
  const ran: string[] = []
  const connect = AsyncDuckDB.prototype.connect
  const spy = vi.spyOn(AsyncDuckDB.prototype, 'connect').mockImplementation(async function (this: AsyncDuckDB) {
    const conn = await connect.call(this)
    const query = conn.query.bind(conn)
    const close = conn.close.bind(conn)
    return Object.assign(conn, {
      query: async (sql: string) => {
        statements.push(sql)
        await hold(sql)
        ran.push(sql)
        return query(sql)
      },
      close: async () => {
        await closing()
        return close()
      },
    })
  })
  unwatched.push(() => spy.mockRestore())
  return Object.assign(statements, { ran })
}

// a panel in query mode on `rows`
async function queryMode(rows = data) {
  const wrapper = await mountSuspended(QueryPanel, { props: { data: rows, expectedColumns: Object.keys(rows[0]!), mode: 'station' } })
  mounted.push(wrapper)
  await wrapper.find('button').trigger('click')
  return wrapper
}

function buttonLabelled(wrapper: Awaited<ReturnType<typeof queryMode>>, label: string) {
  return wrapper.findAll('button').find(button => button.text() === label)!
}

function runButton(wrapper: Awaited<ReturnType<typeof queryMode>>) {
  return buttonLabelled(wrapper, 'Run Query')
}

// the query edited to `sql`, and the syntax check that follows 500 ms later run at once
async function editNow(wrapper: Awaited<ReturnType<typeof queryMode>>, sql: string) {
  vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout'] })
  try {
    await wrapper.find('textarea').setValue(sql)
    vi.advanceTimersByTime(500)
  }
  finally {
    vi.useRealTimers()
  }
  await flushPromises()
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
    vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout'] })
    try {
      await wrapper.find('textarea').setValue('SELECT * FROM data')
      await runButton(wrapper).trigger('click')
      await vi.waitFor(() => expect(creates(statements)).toHaveLength(1))
      // the check, 500 ms after the edit, while the run's load is under way
      vi.advanceTimersByTime(500)
    }
    finally {
      vi.useRealTimers()
    }
    await flushPromises()
    expect(wrapper.find('div.absolute.top-2.right-2').exists()).toBe(true)
    hold.open()
    await vi.waitFor(() => expect(wrapper.emitted('dataTransformed')).toHaveLength(1))
    await vi.waitFor(() => expect(wrapper.find('div.absolute.top-2.right-2').exists()).toBe(false))
    expect(wrapper.emitted<[Value[]]>('dataTransformed')![0]![0]).toEqual(data)
    expect(creates(statements)).toHaveLength(1)
    // and one database, which the check found started
    expect(instantiate).toHaveBeenCalledTimes(1)
  })

  it('tells no syntax error from a check whose rows a Fetch replaced while they loaded', async () => {
    // its statements met the newer rows' load between its DROP and CREATE, and the error it told
    // kept Run Query disabled for a query that was fine
    const hold = gate()
    let held = false
    const statements = watchStatements((sql) => {
      if (!held && sql.startsWith('CREATE TABLE')) {
        held = true
        return hold.opened
      }
      return undefined
    })
    const wrapper = await queryMode()
    await editNow(wrapper, 'SELECT * FROM data LIMIT 10')
    await vi.waitFor(() => expect(creates(statements)).toHaveLength(1))
    const newer = [{ ...data[0]!, station_id: '04411' }]
    await wrapper.setProps({ data: newer })
    await buttonLabelled(wrapper, 'Transform with SQL Query').trigger('click')
    await runButton(wrapper).trigger('click')
    await flushPromises()
    hold.open()
    // the rows handed back as query mode was left, then the run's result
    await vi.waitFor(() => expect(wrapper.emitted('dataTransformed')).toHaveLength(2))
    await vi.waitFor(() => expect(wrapper.find('div.absolute.top-2.right-2').exists()).toBe(false))
    expect(wrapper.text()).not.toContain('Syntax Error')
    expect(runButton(wrapper).attributes('disabled')).toBeUndefined()
  })
})

describe('queryPanel run left behind', () => {
  // the query the panel opens with
  const opening = 'SELECT * FROM data LIMIT 100'

  it('hands on nothing from a query left by Cancel', async () => {
    // its result replaced the fetched rows Cancel had handed back
    const hold = gate()
    const statements = watchStatements(sql => sql === opening ? hold.opened : undefined)
    const wrapper = await queryMode()
    await runButton(wrapper).trigger('click')
    await vi.waitFor(() => expect(statements).toContain(opening))
    await buttonLabelled(wrapper, 'Cancel').trigger('click')
    hold.open()
    await flushPromises()
    expect(wrapper.emitted('dataTransformed')).toEqual([[data]])
  })

  it('runs no query left by Cancel while the table loaded', async () => {
    // it ran once the table was loaded, keeping DuckDB from a newer run's query
    const hold = gate()
    const statements = watchStatements(sql => sql.startsWith('CREATE TABLE') ? hold.opened : undefined)
    const wrapper = await queryMode()
    await runButton(wrapper).trigger('click')
    await vi.waitFor(() => expect(creates(statements)).toHaveLength(1))
    await buttonLabelled(wrapper, 'Cancel').trigger('click')
    hold.open()
    await vi.waitFor(() => expect(statements.some(sql => sql.startsWith('INSERT'))).toBe(true))
    await flushPromises()
    expect(statements).not.toContain(opening)
  })

  // each step of a run that can fail, held until the test opens it and failing then, and whether the
  // run has reached it
  const failing = {
    'the query': (hold: Promise<void>) => {
      const statements = watchStatements(sql => sql === opening ? hold.then(() => Promise.reject(new Error('lost'))) : undefined)
      return () => statements.includes(opening)
    },
    'the table\'s load': (hold: Promise<void>) => {
      const statements = watchStatements(sql => sql.startsWith('CREATE TABLE') ? hold.then(() => Promise.reject(new Error('lost'))) : undefined)
      return () => creates(statements).length > 0
    },
    'DuckDB\'s start': (hold: Promise<void>) => {
      const instantiate = vi.spyOn(AsyncDuckDB.prototype, 'instantiate').mockImplementation(() => hold.then(() => Promise.reject(new Error('lost'))))
      unwatched.push(() => instantiate.mockRestore())
      return () => instantiate.mock.calls.length > 0
    },
  }

  it.each(Object.keys(failing) as (keyof typeof failing)[])('tells no error of %s failing for a query left by Cancel', async (step) => {
    // "Query error: ...", "Failed to load data: ..." or "Failed to initialize database" showed once
    // query mode was entered again, about a query nobody waited for
    const hold = gate()
    const reached = failing[step](hold.opened)
    const wrapper = await queryMode()
    await runButton(wrapper).trigger('click')
    await vi.waitFor(() => expect(reached()).toBe(true))
    await buttonLabelled(wrapper, 'Cancel').trigger('click')
    hold.open()
    await flushPromises()
    await buttonLabelled(wrapper, 'Transform with SQL Query').trigger('click')
    expect(wrapper.text()).not.toMatch(/Query error|Failed to/)
  })

  it('keeps a newer run\'s spinner when a query left by Cancel answers', async () => {
    // Run Query showed loading, and disabled, until the query left behind answered, and then as
    // idle while the newer run was still under way
    const first = gate()
    const second = gate()
    const newer = 'SELECT * FROM data LIMIT 50'
    const statements = watchStatements(sql => sql === opening ? first.opened : sql === newer ? second.opened : undefined)
    const wrapper = await queryMode()
    await runButton(wrapper).trigger('click')
    await vi.waitFor(() => expect(statements).toContain(opening))
    await buttonLabelled(wrapper, 'Cancel').trigger('click')
    await buttonLabelled(wrapper, 'Transform with SQL Query').trigger('click')
    expect(runButton(wrapper).attributes('disabled')).toBeUndefined()
    await wrapper.find('textarea').setValue(newer)
    await runButton(wrapper).trigger('click')
    await vi.waitFor(() => expect(statements).toContain(newer))
    first.open()
    await flushPromises()
    expect(runButton(wrapper).attributes('disabled')).toBeDefined()
    second.open()
    await vi.waitFor(() => expect(runButton(wrapper).attributes('disabled')).toBeUndefined())
    expect(wrapper.emitted('dataTransformed')).toEqual([[data], [data]])
  })
})

describe('queryPanel unmounted', () => {
  // a panel in query mode, left out of `mounted`, as the test unmounts it itself
  async function unmountable() {
    const wrapper = await mountSuspended(QueryPanel, { props: { data, expectedColumns: Object.keys(data[0]!), mode: 'station' } })
    await wrapper.find('button').trigger('click')
    return wrapper
  }

  it('starts no DuckDB for a syntax check still to come', async () => {
    // the check ran after the panel was gone, and started a database nothing ended
    const instantiate = vi.spyOn(AsyncDuckDB.prototype, 'instantiate')
    unwatched.push(() => instantiate.mockRestore())
    const wrapper = await unmountable()
    vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout'] })
    try {
      await wrapper.find('textarea').setValue('SELECT * FROM data LIMIT 10')
      wrapper.unmount()
      // past the check's 500 ms
      vi.advanceTimersByTime(1000)
    }
    finally {
      vi.useRealTimers()
    }
    await flushPromises()
    expect(instantiate).not.toHaveBeenCalled()
  })

  it.each([
    { starter: 'a syntax check', start: (wrapper: Awaited<ReturnType<typeof unmountable>>) => editNow(wrapper, 'SELECT * FROM data LIMIT 10') },
    { starter: 'a run', start: (wrapper: Awaited<ReturnType<typeof unmountable>>) => runButton(wrapper).trigger('click') },
  ])('ends the database $starter under way starts, and loads no table into it', async ({ start }) => {
    const hold = gate()
    const instantiate = vi.spyOn(AsyncDuckDB.prototype, 'instantiate').mockImplementation(() => hold.opened.then(() => null))
    const terminate = vi.spyOn(AsyncDuckDB.prototype, 'terminate')
    unwatched.push(() => instantiate.mockRestore(), () => terminate.mockRestore())
    const statements = watchStatements()
    const wrapper = await unmountable()
    await start(wrapper)
    await vi.waitFor(() => expect(instantiate).toHaveBeenCalled())
    wrapper.unmount()
    hold.open()
    await vi.waitFor(() => expect(terminate).toHaveBeenCalledTimes(1))
    await flushPromises()
    expect([...statements]).toEqual([])
  })

  it.each([
    { starter: 'a syntax check', start: (wrapper: Awaited<ReturnType<typeof unmountable>>) => editNow(wrapper, 'SELECT * FROM data LIMIT 10') },
    { starter: 'a run', start: (wrapper: Awaited<ReturnType<typeof unmountable>>) => runButton(wrapper).trigger('click') },
  ])('stops the table load $starter has under way, and queries nothing, once unmounted', async ({ start }) => {
    // the load went on inserting, and the check or run queried, a connection being closed
    const hold = gate()
    // the connection still open while the load's CREATE answers, as a slow close leaves it
    const closing = gate()
    const statements = watchStatements(sql => sql.startsWith('CREATE TABLE') ? hold.opened : undefined, () => closing.opened)
    const wrapper = await unmountable()
    await start(wrapper)
    await vi.waitFor(() => expect(creates(statements)).toHaveLength(1))
    wrapper.unmount()
    hold.open()
    await flushPromises()
    closing.open()
    await flushPromises()
    expect(verbs(statements)).toEqual(['DROP', 'CREATE'])
    expect(statements.filter(sql => !/^(?:DROP|CREATE) /.test(sql))).toEqual([])
  })

  it('ends the database when its connection fails to close', async () => {
    const terminate = vi.spyOn(AsyncDuckDB.prototype, 'terminate')
    unwatched.push(() => terminate.mockRestore())
    watchStatements(undefined, () => Promise.reject(new Error('lost')))
    const wrapper = await unmountable()
    await runButton(wrapper).trigger('click')
    await vi.waitFor(() => expect(wrapper.emitted('dataTransformed')).toHaveLength(1))
    wrapper.unmount()
    await vi.waitFor(() => expect(terminate).toHaveBeenCalledTimes(1))
  })

  it('logs a database that fails to end, rather than fail the unmount', async () => {
    const terminate = vi.spyOn(AsyncDuckDB.prototype, 'terminate').mockRejectedValueOnce(new Error('lost'))
    const logged = vi.spyOn(console, 'error').mockImplementation(() => {})
    unwatched.push(() => terminate.mockRestore(), () => logged.mockRestore())
    const wrapper = await unmountable()
    await runButton(wrapper).trigger('click')
    await vi.waitFor(() => expect(wrapper.emitted('dataTransformed')).toHaveLength(1))
    wrapper.unmount()
    await vi.waitFor(() => expect(logged).toHaveBeenCalledWith('Failed to terminate DuckDB:', expect.any(Error)))
  })
})

describe('queryPanel failed start or load', () => {
  it('revokes the worker\'s script when the worker cannot be started', async () => {
    // a Worker refused, by a CSP that blocks blob: workers, left the script's URL behind
    vi.stubGlobal('Worker', class {
      constructor() {
        throw new Error('blocked')
      }
    })
    unwatched.push(() => vi.stubGlobal('Worker', class {}))
    vi.mocked(URL.createObjectURL).mockClear()
    vi.mocked(URL.revokeObjectURL).mockClear()
    const wrapper = await queryMode()
    await runButton(wrapper).trigger('click')
    // and why
    await vi.waitFor(() => expect(wrapper.text()).toContain('Failed to initialize database: blocked'))
    expect(URL.createObjectURL).toHaveBeenCalledTimes(1)
    expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:duckdb')
  })

  it('starts DuckDB again for the next run after its start failed, ending the database that failed', async () => {
    const instantiate = vi.spyOn(AsyncDuckDB.prototype, 'instantiate').mockRejectedValueOnce(new Error('lost'))
    const terminate = vi.spyOn(AsyncDuckDB.prototype, 'terminate')
    unwatched.push(() => instantiate.mockRestore(), () => terminate.mockRestore())
    vi.mocked(URL.createObjectURL).mockClear()
    vi.mocked(URL.revokeObjectURL).mockClear()
    const wrapper = await queryMode()
    await runButton(wrapper).trigger('click')
    await vi.waitFor(() => expect(wrapper.text()).toContain('Failed to initialize database'))
    expect(terminate).toHaveBeenCalledTimes(1)
    // nor the worker's script
    expect(URL.revokeObjectURL).toHaveBeenCalledTimes(1)
    await vi.waitFor(() => expect(runButton(wrapper).attributes('disabled')).toBeUndefined())
    // the syntax check leaves it to the run, rather than start it again at every pause in typing
    await editNow(wrapper, 'SELECT * FROM data LIMIT 10')
    expect(instantiate).toHaveBeenCalledTimes(1)
    await runButton(wrapper).trigger('click')
    await vi.waitFor(() => expect(wrapper.emitted('dataTransformed')).toHaveLength(1))
    expect(wrapper.emitted<[Value[]]>('dataTransformed')![0]![0]).toEqual(data)
    expect(instantiate).toHaveBeenCalledTimes(2)
  })

  it('loads the table again for the next run after its load failed, not for the syntax check', async () => {
    let failed = false
    const statements = watchStatements((sql) => {
      if (!failed && sql.startsWith('CREATE TABLE')) {
        failed = true
        return Promise.reject(new Error('lost'))
      }
      return undefined
    })
    const wrapper = await queryMode()
    await runButton(wrapper).trigger('click')
    await vi.waitFor(() => expect(wrapper.text()).toContain('Failed to load data: lost'))
    await vi.waitFor(() => expect(runButton(wrapper).attributes('disabled')).toBeUndefined())
    // the check leaves it to the run, rather than load every row again at every pause in typing
    await editNow(wrapper, 'SELECT * FROM data LIMIT 50')
    await flushPromises()
    expect(creates(statements)).toHaveLength(1)
    await runButton(wrapper).trigger('click')
    await vi.waitFor(() => expect(wrapper.emitted('dataTransformed')).toHaveLength(1))
    expect(wrapper.emitted<[Value[]]>('dataTransformed')![0]![0]).toEqual(data)
  })

  it('tells a start that failed with no error given as failed for an unknown reason', async () => {
    // reading `undefined.message` failed the start's own promise, and the run told that TypeError
    const instantiate = vi.spyOn(AsyncDuckDB.prototype, 'instantiate').mockRejectedValueOnce(undefined)
    unwatched.push(() => instantiate.mockRestore())
    const wrapper = await queryMode()
    await runButton(wrapper).trigger('click')
    await vi.waitFor(() => expect(wrapper.text()).toContain('Failed to initialize database: Unknown error'))
  })

  it('inserts no more of the rows a Fetch replaced, with no run to load newer ones', async () => {
    // their load ran every batch, keeping DuckDB busy and the rows held, until the next run
    const older = Array.from({ length: 250 }, (_, i) => ({ ...data[0]!, value: i }))
    const hold = gate()
    let held = false
    const statements = watchStatements((sql) => {
      if (!held && sql.startsWith('INSERT')) {
        held = true
        return hold.opened
      }
      return undefined
    })
    const wrapper = await queryMode(older)
    await runButton(wrapper).trigger('click')
    await vi.waitFor(() => expect(held).toBe(true))
    await wrapper.setProps({ data })
    hold.open()
    await flushPromises()
    expect(verbs(statements.ran)).toEqual(['DROP', 'CREATE', 'INSERT'])
  })

  it('starts no load for rows a Fetch replaced while it waited for the load before it', async () => {
    // it dropped and created the table for rows nobody would query, once the load before it ended
    const older = Array.from({ length: 250 }, (_, i) => ({ ...data[0]!, value: i }))
    const hold = gate()
    let held = false
    const statements = watchStatements((sql) => {
      if (!held && sql.startsWith('INSERT')) {
        held = true
        return hold.opened
      }
      return undefined
    })
    const wrapper = await queryMode(older)
    await runButton(wrapper).trigger('click')
    await vi.waitFor(() => expect(held).toBe(true))
    for (const rows of [[...older], data]) {
      await wrapper.setProps({ data: rows })
      await buttonLabelled(wrapper, 'Transform with SQL Query').trigger('click')
      await runButton(wrapper).trigger('click')
    }
    hold.open()
    // each Fetch's rows handed back as query mode was left, then the last run's result
    await vi.waitFor(() => expect(wrapper.emitted('dataTransformed')).toHaveLength(3))
    expect(wrapper.emitted<[Value[]]>('dataTransformed')![2]![0]).toEqual(data)
    expect(verbs(statements.ran)).toEqual(['DROP', 'CREATE', 'INSERT', 'DROP', 'CREATE', 'INSERT'])
  })

  it.each([
    { ended: 'stopped', fails: false, loads: ['DROP', 'CREATE', 'DROP', 'CREATE', 'INSERT'] },
    { ended: 'failed', fails: true, loads: ['DROP', 'DROP', 'CREATE', 'INSERT'] },
  ])('loads newer rows once the load of the rows before them has $ended', async ({ fails, loads }) => {
    // a Fetch's rows loaded while the run before it still loaded the older ones would drop and
    // create the table between that load's statements; nor does the older load's failure fail them
    const hold = gate()
    let held = false
    const statements = watchStatements((sql) => {
      if (!held && sql.startsWith('CREATE TABLE')) {
        held = true
        return fails ? hold.opened.then(() => Promise.reject(new Error('lost'))) : hold.opened
      }
      return undefined
    })
    const wrapper = await queryMode()
    await runButton(wrapper).trigger('click')
    await vi.waitFor(() => expect(creates(statements)).toHaveLength(1))
    const newer = [{ ...data[0]!, station_id: '04411' }]
    await wrapper.setProps({ data: newer })
    await buttonLabelled(wrapper, 'Transform with SQL Query').trigger('click')
    await runButton(wrapper).trigger('click')
    await flushPromises()
    hold.open()
    // the rows handed back as query mode was left, then the newer run's result
    await vi.waitFor(() => expect(wrapper.emitted('dataTransformed')).toHaveLength(2))
    expect(wrapper.emitted<[Value[]]>('dataTransformed')![1]![0]).toEqual(newer)
    expect(verbs(statements.ran)).toEqual(loads)
  })

  it('inserts no more of the rows a Fetch replaced while they loaded', async () => {
    // their load ran every batch, and the newer rows' load waited for it
    const older = Array.from({ length: 250 }, (_, i) => ({ ...data[0]!, value: i }))
    const hold = gate()
    let held = false
    const statements = watchStatements((sql) => {
      if (!held && sql.startsWith('INSERT')) {
        held = true
        return hold.opened
      }
      return undefined
    })
    const wrapper = await queryMode(older)
    await runButton(wrapper).trigger('click')
    await vi.waitFor(() => expect(held).toBe(true))
    await wrapper.setProps({ data })
    await buttonLabelled(wrapper, 'Transform with SQL Query').trigger('click')
    await runButton(wrapper).trigger('click')
    hold.open()
    await vi.waitFor(() => expect(wrapper.emitted('dataTransformed')).toHaveLength(2))
    expect(wrapper.emitted<[Value[]]>('dataTransformed')![1]![0]).toEqual(data)
    expect(verbs(statements.ran)).toEqual(['DROP', 'CREATE', 'INSERT', 'DROP', 'CREATE', 'INSERT'])
  })
})

describe('queryPanel syntax check', () => {
  it('checks the text it validated, not the text edited while it waited for the table', async () => {
    // it read the query again for EXPLAIN, so it ran text validateQuery never saw: here a DROP
    const hold = gate()
    const statements = watchStatements(sql => sql.startsWith('CREATE TABLE') ? hold.opened : undefined)
    const wrapper = await queryMode()
    await editNow(wrapper, 'SELECT * FROM data LIMIT 10')
    await vi.waitFor(() => expect(creates(statements)).toHaveLength(1))
    // edited, with the next check's delay on a fake timer that never fires, so it cannot move the
    // check under way on however slow the runner
    vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout'] })
    try {
      await wrapper.find('textarea').setValue('SELECT * FROM data LIMIT 10; DROP TABLE data')
    }
    finally {
      vi.useRealTimers()
    }
    hold.open()
    await vi.waitFor(() => expect(statements).toContain('SELECT * FROM (SELECT * FROM data LIMIT 10) LIMIT 0'))
    expect(statements.filter(sql => sql.includes('; DROP TABLE data'))).toEqual([])
  })

  it('tells the newest check\'s answer, and its spinner, over a check still waiting for the table', async () => {
    // the older check answered last, clearing the newer one's error, and its spinner showed until
    // the table was loaded
    const hold = gate()
    const statements = watchStatements(sql => sql.startsWith('CREATE TABLE') ? hold.opened : undefined)
    const wrapper = await queryMode()
    await editNow(wrapper, 'SELECT * FROM data LIMIT 10')
    await vi.waitFor(() => expect(creates(statements)).toHaveLength(1))
    const spinner = () => wrapper.find('div.absolute.top-2.right-2').exists()
    expect(spinner()).toBe(true)
    await editNow(wrapper, 'SELECT * FROM data LIMIT 10; DROP TABLE data')
    expect(wrapper.text()).toContain('Syntax Error')
    expect(spinner()).toBe(false)
    hold.open()
    await vi.waitFor(() => expect(statements.some(sql => sql.startsWith('INSERT'))).toBe(true))
    await flushPromises()
    expect(wrapper.text()).toContain('Syntax Error')
    expect(spinner()).toBe(false)
  })

  it('keeps the newest check\'s spinner when a check left behind ends', async () => {
    const newer = 'SELECT * FROM data LIMIT 20'
    const loaded = gate()
    const explained = gate()
    const statements = watchStatements(sql => sql.startsWith('CREATE TABLE')
      ? loaded.opened
      : sql === `EXPLAIN ${newer}` ? explained.opened : undefined)
    const wrapper = await queryMode()
    const spinner = () => wrapper.find('div.absolute.top-2.right-2').exists()
    await editNow(wrapper, 'SELECT * FROM data LIMIT 10')
    await vi.waitFor(() => expect(creates(statements)).toHaveLength(1))
    await editNow(wrapper, newer)
    loaded.open()
    await vi.waitFor(() => expect(statements).toContain(`EXPLAIN ${newer}`))
    await flushPromises()
    // the newer check is still under way
    expect(spinner()).toBe(true)
    explained.open()
    await vi.waitFor(() => expect(spinner()).toBe(false))
  })

  it('asks for no schema for a check left behind while DuckDB explained it', async () => {
    const older = 'SELECT * FROM data LIMIT 10'
    const explained = gate()
    const statements = watchStatements(sql => sql === `EXPLAIN ${older}` ? explained.opened : undefined)
    const wrapper = await queryMode()
    await editNow(wrapper, older)
    await vi.waitFor(() => expect(statements).toContain(`EXPLAIN ${older}`))
    await editNow(wrapper, 'SELECT * FROM data LIMIT 20')
    explained.open()
    await vi.waitFor(() => expect(statements).toContain('SELECT * FROM (SELECT * FROM data LIMIT 20) LIMIT 0'))
    await flushPromises()
    expect(statements).not.toContain(`SELECT * FROM (${older}) LIMIT 0`)
  })
})

// the statements that loaded the table, by their first word
function verbs(statements: string[]) {
  return statements.map(sql => sql.split(' ')[0]).filter(verb => verb !== 'SELECT' && verb !== 'EXPLAIN')
}

describe('queryPanel note on misread types', () => {
  it('names the types the browser\'s DuckDB misreads and the cast that reads them', async () => {
    // a BIT reads as DuckDB's bytes, a TIME WITH TIME ZONE without its offset, a UHUGEINT of 2^127
    // or more as negative
    const wrapper = await mountSuspended(QueryPanel, { props: { data, expectedColumns: Object.keys(data[0]!), mode: 'station' } })
    mounted.push(wrapper)
    await wrapper.find('button').trigger('click')
    const text = wrapper.text()
    for (const part of ['BIT', 'TIME WITH TIME ZONE', 'UHUGEINT', '2^127', 'CAST(column AS VARCHAR)'])
      expect(text).toContain(part)
  })
})

describe('queryPanel failed run', () => {
  it.each([
    { failure: 'DuckDB refusing it', sql: 'SELECT * FROM data WHERE valu > 1', told: 'Query error' },
    { failure: 'its columns', sql: 'SELECT station_id FROM data', told: 'missing expected columns' },
    { failure: 'the validator refusing it', sql: 'DELETE FROM data', told: 'Only SELECT queries' },
  ])('hands back the fetched rows for a query failing by $failure, not the query\'s before it', async ({ sql, told }) => {
    // the table went on showing the previous query's rows under the new query's error, as its output
    const wrapper = await queryMode()
    await runButton(wrapper).trigger('click')
    await vi.waitFor(() => expect(wrapper.emitted('dataTransformed')).toHaveLength(1))
    expect(wrapper.emitted<[Value[]]>('dataTransformed')![0]![0]).not.toBe(data)
    await wrapper.find('textarea').setValue(sql)
    await runButton(wrapper).trigger('click')
    await vi.waitFor(() => expect(wrapper.emitted('dataTransformed')).toHaveLength(2))
    expect(wrapper.emitted<[Value[]]>('dataTransformed')![1]![0]).toBe(data)
    expect(wrapper.text()).toContain(told)
    expect(wrapper.text()).not.toContain('Query executed successfully')
  })

  it('hands back nothing for a failing query when no query\'s rows are shown', async () => {
    const wrapper = await queryMode()
    await wrapper.find('textarea').setValue('SELECT * FROM data WHERE valu > 1')
    await runButton(wrapper).trigger('click')
    await vi.waitFor(() => expect(wrapper.text()).toContain('Query error'))
    expect(wrapper.emitted('dataTransformed')).toBeUndefined()
  })
})
