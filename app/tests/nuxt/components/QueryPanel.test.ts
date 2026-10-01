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
        return {
          query: async (sql: string) => conn.query(sql),
          send: async (sql: string) => conn.send(sql),
          cancelSent: async () => conn.cancelSent(),
          close: async () => conn.close(),
        }
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
  const wrapper = await mountSuspended(QueryPanel, { props: { data, expectedColumns: Object.keys(data[0]!) } })
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
// those DuckDB was handed on, in the order it was; `cancelled`, the queries sent that a cancel ended
// while held. The connection closes once `closing` answers
function watchStatements(hold: (sql: string) => Promise<void> | undefined = () => undefined, closing: () => Promise<void> = async () => {}) {
  const statements: string[] = []
  const ran: string[] = []
  const cancelled: string[] = []
  const connect = AsyncDuckDB.prototype.connect
  const spy = vi.spyOn(AsyncDuckDB.prototype, 'connect').mockImplementation(async function (this: AsyncDuckDB) {
    const conn = await connect.call(this)
    const query = conn.query.bind(conn)
    const send = conn.send.bind(conn)
    const close = conn.close.bind(conn)
    // the query sent on this connection and held, which DuckDB runs between polls: a cancel ends it,
    // and so does a statement on the same connection
    let pending: { sql: string, end: (reason: Error) => void } | null = null
    return Object.assign(conn, {
      query: async (sql: string) => {
        pending?.end(new Error('Attempting to execute an unsuccessful or closed pending query result'))
        statements.push(sql)
        await hold(sql)
        ran.push(sql)
        return query(sql)
      },
      send: async (sql: string) => {
        statements.push(sql)
        await new Promise<void>((resolve, reject) => {
          pending = { sql, end: reject }
          Promise.resolve(hold(sql)).then(resolve, reject)
        }).finally(() => {
          pending = null
        })
        ran.push(sql)
        return send(sql)
      },
      cancelSent: async () => {
        if (!pending)
          return false
        cancelled.push(pending.sql)
        pending.end(new Error('query was canceled'))
        return true
      },
      close: async () => {
        await closing()
        return close()
      },
    })
  })
  unwatched.push(() => spy.mockRestore())
  return Object.assign(statements, { ran, cancelled })
}

// a panel in query mode on `rows`
async function queryMode(rows = data) {
  const wrapper = await mountSuspended(QueryPanel, { props: { data: rows, expectedColumns: Object.keys(rows[0]!) } })
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
    const wrapper = await mountSuspended(QueryPanel, { props: { data, expectedColumns: Object.keys(data[0]!) } })
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
    const wrapper = await mountSuspended(QueryPanel, { props: { data, expectedColumns: Object.keys(data[0]!) } })
    mounted.push(wrapper)
    await wrapper.find('button').trigger('click')
    const text = wrapper.text()
    for (const part of ['BIT', 'TIME WITH TIME ZONE', 'UHUGEINT', '2^127', 'CAST(column AS VARCHAR)'])
      expect(text).toContain(part)
  })
})

describe('queryPanel statements', () => {
  const several = 'SELECT * FROM data LIMIT 1; SET threads = 1'

  it('checks no statement after the first, and refuses the query', async () => {
    // the check's EXPLAIN ran `SET threads = 1` after the SELECT, and told no error
    const statements = watchStatements()
    const wrapper = await queryMode()
    await editNow(wrapper, several)
    expect(wrapper.text()).toContain('Only one statement can run at a time')
    expect(runButton(wrapper).attributes('disabled')).toBeDefined()
    expect(statements.filter(sql => sql.includes('SET'))).toEqual([])
  })

  it('runs no statement after the first, run before the check', async () => {
    // Run Query ran each statement, and handed on the first one's rows
    const statements = watchStatements()
    const wrapper = await queryMode()
    // edited, with the check's delay on a fake timer that never fires
    vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout'] })
    try {
      await wrapper.find('textarea').setValue(several)
    }
    finally {
      vi.useRealTimers()
    }
    await runButton(wrapper).trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('Only one statement can run at a time')
    expect([...statements]).toEqual([])
    expect(wrapper.emitted('dataTransformed')).toBeUndefined()
  })

  it('checks and runs one statement with a semicolon and a comment after it', async () => {
    // the check asked for the schema of `(... LIMIT 10; -- done) LIMIT 0`, which DuckDB could not
    // parse, and its error kept Run Query disabled
    const statements = watchStatements()
    const wrapper = await queryMode()
    await editNow(wrapper, 'SELECT * FROM data LIMIT 10; -- done')
    await vi.waitFor(() => expect(statements).toContain('SELECT * FROM (SELECT * FROM data LIMIT 10) LIMIT 0'))
    await vi.waitFor(() => expect(wrapper.find('div.absolute.top-2.right-2').exists()).toBe(false))
    expect(wrapper.text()).not.toContain('Syntax Error')
    await runButton(wrapper).trigger('click')
    await vi.waitFor(() => expect(wrapper.emitted('dataTransformed')).toHaveLength(1))
    expect(wrapper.emitted<[Value[]]>('dataTransformed')![0]![0]).toEqual(data)
    // the check explains, and the run runs, the statement as checked, and nothing after it
    expect(statements).toContain('EXPLAIN SELECT * FROM data LIMIT 10')
    expect(statements).toContain('SELECT * FROM data LIMIT 10')
    expect(statements.filter(sql => sql.includes('done'))).toEqual([])
  })
})

describe('queryPanel check after a Fetch', () => {
  // the rows of a summary, which name the station each value was taken from
  const summary: Value[] = [{ ...data[0]!, taken_station_id: '01048' }]
  const spinner = (wrapper: Awaited<ReturnType<typeof queryMode>>) => wrapper.find('div.absolute.top-2.right-2').exists()

  it.each([
    { from: 'station', to: 'summary', before: data, after: summary, errorAfter: false },
    { from: 'summary', to: 'station', before: summary, after: data, errorAfter: true },
  ])('checks the query again for the rows a Fetch brought, from $from to $to rows', async ({ before, after, errorAfter }) => {
    // the answer for the rows before stayed: an error that kept Run Query disabled for a query fine
    // for the new rows, or none for a query that fails on them
    const sql = 'SELECT * FROM data WHERE taken_station_id IS NOT NULL LIMIT 10'
    const statements = watchStatements()
    const wrapper = await mountSuspended(QueryPanel, { props: { data: before, expectedColumns: Object.keys(before[0]!) } })
    mounted.push(wrapper)
    // each check explains the query, and ends once it has
    const checked = async (times: number) => {
      await vi.waitFor(() => expect(statements.filter(statement => statement === `EXPLAIN ${sql}`)).toHaveLength(times))
      await vi.waitFor(() => expect(spinner(wrapper)).toBe(false))
    }
    await wrapper.find('button').trigger('click')
    await editNow(wrapper, sql)
    await checked(1)
    expect(wrapper.text().includes('Syntax Error')).toBe(!errorAfter)
    await wrapper.setProps({ data: after, expectedColumns: Object.keys(after[0]!) })
    await buttonLabelled(wrapper, 'Transform with SQL Query').trigger('click')
    await checked(2)
    expect(wrapper.text().includes('Syntax Error')).toBe(errorAfter)
    expect(runButton(wrapper).attributes('disabled') !== undefined).toBe(errorAfter)
  })

  it('checks the query once for the rows a Fetch brought, however often query mode is entered', async () => {
    const sql = 'SELECT * FROM data LIMIT 10'
    const statements = watchStatements()
    const explained = () => statements.filter(statement => statement === `EXPLAIN ${sql}`)
    const wrapper = await queryMode()
    await editNow(wrapper, sql)
    await vi.waitFor(() => expect(explained()).toHaveLength(1))
    await wrapper.setProps({ data: [{ ...data[0]!, station_id: '04411' }] })
    await buttonLabelled(wrapper, 'Transform with SQL Query').trigger('click')
    await vi.waitFor(() => expect(explained()).toHaveLength(2))
    await vi.waitFor(() => expect(spinner(wrapper)).toBe(false))
    await buttonLabelled(wrapper, 'Cancel').trigger('click')
    await buttonLabelled(wrapper, 'Transform with SQL Query').trigger('click')
    await flushPromises()
    expect(explained()).toHaveLength(2)
  })

  it('checks a query edited just before a Fetch once query mode is entered, not for the closed panel', async () => {
    // the check still due fired for the panel the Fetch had closed, starting DuckDB and loading the
    // new rows, and entering query mode before it fired checked the query twice
    const sql = 'SELECT * FROM data LIMIT 10'
    const statements = watchStatements()
    const explained = () => statements.filter(statement => statement === `EXPLAIN ${sql}`)
    const instantiate = vi.spyOn(AsyncDuckDB.prototype, 'instantiate')
    unwatched.push(() => instantiate.mockRestore())
    const wrapper = await queryMode()
    vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout'] })
    try {
      await wrapper.find('textarea').setValue(sql)
      await wrapper.setProps({ data: [{ ...data[0]!, station_id: '04411' }] })
      vi.advanceTimersByTime(1000)
    }
    finally {
      vi.useRealTimers()
    }
    await flushPromises()
    expect(instantiate).not.toHaveBeenCalled()
    await buttonLabelled(wrapper, 'Transform with SQL Query').trigger('click')
    await vi.waitFor(() => expect(explained()).toHaveLength(1))
    await vi.waitFor(() => expect(spinner(wrapper)).toBe(false))
    expect(explained()).toHaveLength(1)
  })

  it('starts no DuckDB for a query never checked, entering query mode after a Fetch', async () => {
    // DuckDB loads from a CDN, which the panel leaves until a query is edited or run
    const instantiate = vi.spyOn(AsyncDuckDB.prototype, 'instantiate')
    unwatched.push(() => instantiate.mockRestore())
    const wrapper = await queryMode()
    await wrapper.setProps({ data: [{ ...data[0]!, station_id: '04411' }] })
    await buttonLabelled(wrapper, 'Transform with SQL Query').trigger('click')
    await flushPromises()
    expect(instantiate).not.toHaveBeenCalled()
  })
})

describe('queryPanel table columns', () => {
  it('types a column by all its values and keeps a column only later rows carry', async () => {
    // a column null in the first row was VARCHAR, which `avg` refused and which handed `quality`
    // on as text, and a column the first row lacked was no column at all
    const rows = [
      { ...data[0]!, value: null, quality: null },
      { ...data[0]!, timestamp: '2020-01-02T00:00:00.000000+00:00', value: 2.5, quality: 10, distance: 1.25 },
    ] as Value[]
    const wrapper = await queryMode(rows)
    await wrapper.find('textarea').setValue('SELECT *, avg(value) OVER () AS mean FROM data ORDER BY timestamp')
    await runButton(wrapper).trigger('click')
    await vi.waitFor(() => expect(wrapper.emitted('dataTransformed')).toHaveLength(1))
    expect(wrapper.emitted<[Value[]]>('dataTransformed')![0]![0]).toEqual([
      { ...rows[0], distance: null, mean: 2.5 },
      { ...rows[1], mean: 2.5 },
    ])
  })

  it('keeps a column with no value at all as text, which compares with a string', async () => {
    // a summary that found no station has no `taken_station_id` in any row; as a DOUBLE, matching it
    // against a pattern failed
    const rows = [{ ...data[0]!, taken_station_id: null }] as unknown as Value[]
    const wrapper = await queryMode(rows)
    await wrapper.find('textarea').setValue('SELECT * FROM data WHERE taken_station_id IS NULL OR taken_station_id LIKE \'01%\'')
    await runButton(wrapper).trigger('click')
    await vi.waitFor(() => expect(wrapper.emitted('dataTransformed')).toHaveLength(1))
    expect(wrapper.emitted<[Value[]]>('dataTransformed')![0]![0]).toEqual(rows)
  })
})

describe('queryPanel columns of the rows queried', () => {
  const { parameter: _parameter, value: _value, quality: _quality, ...key } = data[0]!
  // each shape of row the panel queries, as the REST API answers it, and the examples it offers
  const shapes = [
    {
      shape: 'long',
      rows: data,
      examples: ['All data (limited)', 'Filter by parameter', 'Aggregate by timestamp', 'Filter by value range', 'Recent data only'],
    },
    {
      shape: 'wide',
      rows: [{ ...key, temperature_air_mean_2m: 1.5 }],
      examples: ['All data (limited)', 'Recent data only'],
    },
    {
      shape: 'interpolated',
      rows: [{ ...key, parameter: 'temperature_air_mean_2m', value: 1.5, distance_mean: 3.25, taken_station_ids: ['01048', '04411'] }],
      examples: ['All data (limited)', 'Filter by parameter', 'Aggregate by timestamp', 'Filter by value range', 'Recent data only', 'Group by source stations'],
    },
    {
      shape: 'summarized',
      rows: [{ ...key, parameter: 'temperature_air_mean_2m', value: 1.5, distance: 1.25, taken_station_id: '01048' }],
      examples: ['All data (limited)', 'Filter by parameter', 'Aggregate by timestamp', 'Filter by value range', 'Recent data only', 'Group by source station'],
    },
  ] as unknown as { shape: string, rows: Value[], examples: string[] }[]

  it.each(shapes)('offers the examples the $shape rows carry the columns of, and runs each', async ({ rows, examples }) => {
    // every query was refused unless it returned the long rows' parameter, value and quality, and an
    // example on a column the rows lack failed on it
    const wrapper = await queryMode(rows)
    expect(wrapper.text()).not.toContain('Required columns')
    expect(wrapper.findAll('details button').map(button => button.text())).toEqual(examples)
    // a run refused, or failed, hands nothing on
    for (const [i, example] of examples.entries()) {
      await buttonLabelled(wrapper, example).trigger('click')
      await runButton(wrapper).trigger('click')
      await vi.waitFor(() => expect(wrapper.emitted('dataTransformed')).toHaveLength(i + 1))
    }
  })

  it('tells no syntax error for a query returning columns of its own', async () => {
    // the check refused a result without the long rows' columns, and Run Query stayed disabled
    const sql = 'SELECT timestamp, temperature_air_mean_2m * 2 AS doubled FROM data LIMIT 10'
    const statements = watchStatements()
    const wrapper = await queryMode(shapes[1]!.rows)
    await editNow(wrapper, sql)
    await vi.waitFor(() => expect(statements).toContain(`SELECT * FROM (${sql}) LIMIT 0`))
    await vi.waitFor(() => expect(wrapper.find('div.absolute.top-2.right-2').exists()).toBe(false))
    expect(wrapper.text()).not.toContain('Syntax Error')
    expect(runButton(wrapper).attributes('disabled')).toBeUndefined()
  })

  it('notes the columns a result lacks against the rows queried, and hands it on', async () => {
    const wrapper = await queryMode()
    await wrapper.find('textarea').setValue('SELECT parameter, avg(value) AS mean FROM data GROUP BY parameter')
    await runButton(wrapper).trigger('click')
    await vi.waitFor(() => expect(wrapper.emitted('dataTransformed')).toHaveLength(1))
    expect(wrapper.emitted<[Value[]]>('dataTransformed')![0]![0]).toEqual([{ parameter: 'temperature_air_mean_2m', mean: 1.5 }])
    expect(wrapper.text()).toContain('missing expected columns: station_id, resolution, dataset, timestamp, value, quality')
  })
})

describe('queryPanel failed run', () => {
  it.each([
    { failure: 'DuckDB refusing it', sql: 'SELECT * FROM data WHERE valu > 1', told: 'Query error' },
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

describe('queryPanel query left running', () => {
  // the query the panel opens with, held until cancelled, as a slow query runs on
  const opening = 'SELECT * FROM data LIMIT 100'
  const newer = [{ ...data[0]!, station_id: '04411' }]

  it.each([
    { leaving: 'Cancel', leave: (wrapper: Awaited<ReturnType<typeof queryMode>>) => buttonLabelled(wrapper, 'Cancel').trigger('click'), rows: data },
    { leaving: 'a Fetch', leave: (wrapper: Awaited<ReturnType<typeof queryMode>>) => wrapper.setProps({ data: newer }), rows: newer },
  ])('cancels the query of a run left by $leaving, and runs the next one without it', async ({ leave, rows }) => {
    // DuckDB ran it on to its end, and the next run and the syntax check waited behind it
    const statements = watchStatements(sql => sql === opening ? new Promise<void>(() => {}) : undefined)
    const wrapper = await queryMode()
    await runButton(wrapper).trigger('click')
    await vi.waitFor(() => expect(statements).toContain(opening))
    await leave(wrapper)
    await flushPromises()
    expect(statements.cancelled).toEqual([opening])
    await buttonLabelled(wrapper, 'Transform with SQL Query').trigger('click')
    await wrapper.find('textarea').setValue('SELECT * FROM data LIMIT 50')
    await runButton(wrapper).trigger('click')
    // the rows handed back as query mode was left, then the next run's result
    await vi.waitFor(() => expect(wrapper.emitted('dataTransformed')).toHaveLength(2))
    expect(wrapper.emitted<[Value[]]>('dataTransformed')![1]![0]).toEqual(rows)
    expect(wrapper.text()).not.toMatch(/Query error|Failed to/)
  })

  it('cancels the query of a run under way as the panel goes', async () => {
    // it ran on until the worker was terminated
    const statements = watchStatements(sql => sql === opening ? new Promise<void>(() => {}) : undefined)
    const wrapper = await mountSuspended(QueryPanel, { props: { data, expectedColumns: Object.keys(data[0]!), mode: 'station' } })
    await wrapper.find('button').trigger('click')
    await runButton(wrapper).trigger('click')
    await vi.waitFor(() => expect(statements).toContain(opening))
    wrapper.unmount()
    await flushPromises()
    expect(statements.cancelled).toEqual([opening])
  })

  it('keeps a run\'s query running through a syntax check made while it runs', async () => {
    // the check's statements, on the connection of the query under way, would end that query
    const hold = gate()
    const statements = watchStatements(sql => sql === opening ? hold.opened : undefined)
    const wrapper = await queryMode()
    await runButton(wrapper).trigger('click')
    await vi.waitFor(() => expect(statements).toContain(opening))
    await editNow(wrapper, 'SELECT * FROM data LIMIT 10')
    await vi.waitFor(() => expect(statements).toContain('EXPLAIN SELECT * FROM data LIMIT 10'))
    hold.open()
    await vi.waitFor(() => expect(wrapper.emitted('dataTransformed')).toHaveLength(1))
    expect(wrapper.emitted<[Value[]]>('dataTransformed')![0]![0]).toEqual(data)
    expect(wrapper.text()).not.toContain('Query error')
  })

  it('sends no query for a run left while its connection opened', async () => {
    // sent once the connection was open, it ran with no run to cancel it
    const connect = AsyncDuckDB.prototype.connect
    const hold = gate()
    let connects = 0
    const sent: string[] = []
    const held = vi.spyOn(AsyncDuckDB.prototype, 'connect').mockImplementation(async function (this: AsyncDuckDB) {
      // the panel's own connection, then the run's
      if (++connects === 2)
        await hold.opened
      const conn = await connect.call(this)
      const send = conn.send.bind(conn)
      return Object.assign(conn, {
        send: async (sql: string) => {
          sent.push(sql)
          return send(sql)
        },
      })
    })
    unwatched.push(() => held.mockRestore())
    const wrapper = await queryMode()
    await runButton(wrapper).trigger('click')
    await vi.waitFor(() => expect(connects).toBe(2))
    await buttonLabelled(wrapper, 'Cancel').trigger('click')
    hold.open()
    await flushPromises()
    expect(sent).toEqual([])
  })

  it('reads no more of a result once its run is left', async () => {
    // a Cancel once the query had ended, which a cancel no longer stops, left every batch to be read
    const connect = AsyncDuckDB.prototype.connect
    const hold = gate()
    let read = 0
    const spy = vi.spyOn(AsyncDuckDB.prototype, 'connect').mockImplementation(async function (this: AsyncDuckDB) {
      const conn = await connect.call(this)
      const send = conn.send.bind(conn)
      return Object.assign(conn, {
        // the result's batches, the second held until the test opens it
        send: async (sql: string) => {
          const reader = await send(sql)
          return (async function* () {
            for (const batch of reader) {
              if (read === 1)
                await hold.opened
              read++
              yield batch
            }
          })()
        },
      })
    })
    unwatched.push(() => spy.mockRestore())
    // three batches of 2048 rows at most
    const rows = Array.from({ length: 5000 }, (_, i) => ({ ...data[0]!, value: i }))
    const wrapper = await queryMode(rows)
    await wrapper.find('textarea').setValue('SELECT * FROM data')
    await runButton(wrapper).trigger('click')
    await vi.waitFor(() => expect(read).toBe(1))
    await buttonLabelled(wrapper, 'Cancel').trigger('click')
    hold.open()
    await flushPromises()
    expect(read).toBe(2)
    expect(wrapper.emitted('dataTransformed')).toEqual([[rows]])
  })

  it('hands on every batch of a result DuckDB sends in several', async () => {
    // a sent query's result is read a batch at a time, 2048 rows each
    const rows = Array.from({ length: 3000 }, (_, i) => ({ ...data[0]!, value: i }))
    const wrapper = await queryMode(rows)
    await wrapper.find('textarea').setValue('SELECT * FROM data ORDER BY value')
    await runButton(wrapper).trigger('click')
    await vi.waitFor(() => expect(wrapper.emitted('dataTransformed')).toHaveLength(1))
    expect(wrapper.emitted<[Value[]]>('dataTransformed')![0]![0]).toEqual(rows)
  })
})

describe('queryPanel column of lists', () => {
  // an interpolated row, whose `taken_station_ids` the REST API answers as a list
  const { parameter: _parameter, value: _value, quality: _quality, ...key } = data[0]!
  const interpolated = (ids: unknown, value = 1.5) => ({ ...key, parameter: 'temperature_air_mean_2m', value, distance_mean: 3.25, taken_station_ids: ids })

  it('loads a column of lists as lists, which list_contains and unnest take, and hands them on as lists', async () => {
    // the lists went in as their text, '01048,04411', which list_contains and unnest refused
    const rows = [interpolated(['01048', '04411']), interpolated(['O\'Hare', null], 2.5), interpolated(null, 3.5)] as unknown as Value[]
    const wrapper = await queryMode(rows)
    await wrapper.find('textarea').setValue('SELECT *, len(taken_station_ids) AS n FROM data WHERE list_contains(taken_station_ids, \'01048\') OR list_contains(taken_station_ids, \'O\'\'Hare\') ORDER BY value')
    await runButton(wrapper).trigger('click')
    await vi.waitFor(() => expect(wrapper.emitted('dataTransformed')).toHaveLength(1))
    expect(wrapper.emitted<[Value[]]>('dataTransformed')![0]![0]).toEqual([
      { ...rows[0], n: 2 },
      { ...rows[1], n: 2 },
    ])
    await wrapper.find('textarea').setValue('SELECT unnest(taken_station_ids) AS id FROM data ORDER BY id')
    await runButton(wrapper).trigger('click')
    await vi.waitFor(() => expect(wrapper.emitted('dataTransformed')).toHaveLength(2))
    expect(wrapper.emitted<[Value[]]>('dataTransformed')![1]![0]).toEqual([{ id: '01048' }, { id: '04411' }, { id: 'O\'Hare' }, { id: null }])
  })

  it.each([
    { order: 'text first', rows: [interpolated('01048'), interpolated(['01048', '04411'], 2.5)] },
    { order: 'list first', rows: [interpolated(['01048', '04411'], 2.5), interpolated('01048')] },
  ])('keeps a column holding lists and text as text, $order', async ({ rows }) => {
    const wrapper = await queryMode(rows as unknown as Value[])
    await wrapper.find('textarea').setValue('SELECT taken_station_ids FROM data ORDER BY value')
    await runButton(wrapper).trigger('click')
    await vi.waitFor(() => expect(wrapper.emitted('dataTransformed')).toHaveLength(1))
    expect(wrapper.emitted<[Value[]]>('dataTransformed')![0]![0]).toEqual([{ taken_station_ids: '01048' }, { taken_station_ids: '01048,04411' }])
  })
})

describe('queryPanel result of no rows', () => {
  it('tells a query that returned no rows, and hands back the fetched rows when the next fails', async () => {
    // nothing told a query that matched nothing, and a failing query after it handed nothing back
    const wrapper = await queryMode()
    await wrapper.find('textarea').setValue('SELECT * FROM data WHERE value > 100000')
    await runButton(wrapper).trigger('click')
    await vi.waitFor(() => expect(wrapper.emitted('dataTransformed')).toHaveLength(1))
    expect(wrapper.emitted<[Value[]]>('dataTransformed')![0]![0]).toEqual([])
    expect(wrapper.text()).toContain('Query executed successfully: 0 row(s) returned')
    await wrapper.find('textarea').setValue('SELECT * FROM data WHERE valu > 1')
    await runButton(wrapper).trigger('click')
    await vi.waitFor(() => expect(wrapper.emitted('dataTransformed')).toHaveLength(2))
    expect(wrapper.emitted<[Value[]]>('dataTransformed')![1]![0]).toBe(data)
    expect(wrapper.text()).toContain('Query error')
    expect(wrapper.text()).not.toContain('Query executed successfully')
  })
})
