import { describe, expect, it, vi } from 'vitest'
import { AbortedError, createLimiter, QueueFullError, QueueTimeoutError, TtlCache } from '../../server/utils/ttlCache'

// The memory of what the server calculated (GH-4258): fresh for a while, bounded, worked out once, and never keeping a failure.

describe('the cache', () => {
  const clock = () => {
    const state = { now: 1000 }
    return { state, now: () => state.now }
  }

  it('gives a value the life `ttlOf` names for it where that is not the cache\'s own (GH-4390)', async () => {
    const { state, now } = clock()
    const cache = new TtlCache<{ short: boolean }>({ ttlMs: 1000, maxEntries: 10, now, ttlOf: value => value.short ? 10 : 1000 })
    const load = vi.fn(async (short: boolean) => ({ short }))

    await cache.get('short', () => load(true))
    await cache.get('long', () => load(false))
    state.now += 11
    await cache.get('short', () => load(true))
    await cache.get('long', () => load(false))
    expect(load.mock.calls).toEqual([[true], [false], [true]])
    state.now += 989
    await cache.get('long', () => load(false))
    expect(load).toHaveBeenCalledTimes(4)
  })

  it('serves what it worked out until the entry expires, then works it out again', async () => {
    const { state, now } = clock()
    const cache = new TtlCache<number>({ ttlMs: 100, maxEntries: 10, now })
    const load = vi.fn(async () => load.mock.calls.length)

    expect(await cache.get('a', load)).toBe(1)
    state.now += 99
    expect(await cache.get('a', load)).toBe(1)
    state.now += 1
    expect(await cache.get('a', load)).toBe(2)
    expect(load).toHaveBeenCalledTimes(2)
  })

  it('works a key out once for askers that come while it runs, and each key by itself', async () => {
    const cache = new TtlCache<string>({ ttlMs: 1000, maxEntries: 10 })
    let release!: (value: string) => void
    const load = vi.fn(() => new Promise<string>((resolve) => {
      release = resolve
    }))

    const first = cache.get('a', load)
    const second = cache.get('a', load)
    const other = cache.get('b', async () => 'b')
    release('answer')

    expect(await Promise.all([first, second, other])).toEqual(['answer', 'answer', 'b'])
    expect(load).toHaveBeenCalledTimes(1)
  })

  it('keeps a failure for nobody: every asker of the failed run gets it, and the next asker tries again', async () => {
    const cache = new TtlCache<string>({ ttlMs: 1000, maxEntries: 10 })
    let release!: () => void
    const failing = vi.fn(() => new Promise<string>((_, reject) => {
      release = () => reject(new Error('backend down'))
    }))

    const first = cache.get('a', failing)
    const second = cache.get('a', failing)
    release()
    await expect(first).rejects.toThrow('backend down')
    await expect(second).rejects.toThrow('backend down')
    expect(failing).toHaveBeenCalledTimes(1)
    expect(cache.size).toBe(0)

    expect(await cache.get('a', async () => 'fine')).toBe('fine')
  })

  it('keeps at most as many entries as it is told, and drops the one used longest ago', async () => {
    const cache = new TtlCache<string>({ ttlMs: 1000, maxEntries: 2 })
    const load = (value: string) => vi.fn(async () => value)
    await cache.get('a', load('a'))
    await cache.get('b', load('b'))
    // used again: now `b` is the one used longest ago
    await cache.get('a', load('a'))
    await cache.get('c', load('c'))

    expect(cache.size).toBe(2)
    const again = { a: load('a2'), b: load('b2'), c: load('c2') }
    expect(await cache.get('a', again.a)).toBe('a')
    expect(await cache.get('c', again.c)).toBe('c')
    expect(await cache.get('b', again.b)).toBe('b2')
  })

  it('drops an entry that has expired when it is asked for again, so what it holds does not outlive its use', async () => {
    const { state, now } = clock()
    const cache = new TtlCache<string>({ ttlMs: 10, maxEntries: 10, now })
    await cache.get('a', async () => 'a')
    state.now += 11
    await expect(cache.get('a', async () => {
      throw new Error('gone')
    })).rejects.toThrow('gone')
    expect(cache.size).toBe(0)
  })
})

describe('the queue of reads', () => {
  it('lets at most the limit run at once, the others wait their turn in order, and a failure gives its place on', async () => {
    const limit = createLimiter(2)
    let running = 0
    let most = 0
    const order: number[] = []
    const gates: Array<() => void> = []
    const work = (id: number, fail = false) => limit(async () => {
      running++
      most = Math.max(most, running)
      order.push(id)
      await new Promise<void>(resolve => gates.push(resolve))
      running--
      if (fail)
        throw new Error(`failed ${id}`)
      return id
    })

    const results = [work(1), work(2, true), work(3), work(4)].map(promise => promise.catch((error: Error) => error.message))
    await vi.waitFor(() => expect(order).toEqual([1, 2]))
    gates[1]!()
    await vi.waitFor(() => expect(order).toEqual([1, 2, 3]))
    gates[0]!()
    await vi.waitFor(() => expect(order).toEqual([1, 2, 3, 4]))
    gates[2]!()
    gates[3]!()

    expect(await Promise.all(results)).toEqual([1, 'failed 2', 3, 4])
    expect(most).toBe(2)
  })
})

describe('a read that nobody waits for any more', () => {
  it('is given up where its one asker has gone, and the cache keeps nothing of it', async () => {
    const cache = new TtlCache<string>({ ttlMs: 1000, maxEntries: 10 })
    let stopped = false
    const client = new AbortController()
    const asked = cache.get('a', signal => new Promise<string>((_, reject) => {
      signal.addEventListener('abort', () => {
        stopped = true
        reject(new AbortedError())
      })
    }), client.signal)
    client.abort()

    await expect(asked).rejects.toBeInstanceOf(AbortedError)
    expect(stopped).toBe(true)
    expect(cache.size).toBe(0)
    expect(await cache.get('a', async () => 'again')).toBe('again')
  })

  it('goes on where another asker still waits for it: one client leaving does not take the answer from the rest', async () => {
    const cache = new TtlCache<string>({ ttlMs: 1000, maxEntries: 10 })
    let release!: (value: string) => void
    let stopped = false
    const load = (signal: AbortSignal) => new Promise<string>((resolve) => {
      release = resolve
      signal.addEventListener('abort', () => {
        stopped = true
      })
    })
    const leaving = new AbortController()
    const staying = new AbortController()
    const gone = cache.get('a', load, leaving.signal)
    const stays = cache.get('a', load, staying.signal)
    const noSignal = cache.get('a', load)
    leaving.abort()
    await expect(gone).rejects.toBeInstanceOf(AbortedError)
    // the asker with no signal is one that stays, whatever the others do
    staying.abort()
    await expect(stays).rejects.toBeInstanceOf(AbortedError)
    expect(stopped).toBe(false)
    release('answer')
    expect(await noSignal).toBe('answer')
  })

  it('gives up the run at once where the asker has gone before it asked: the run is told to stop as it starts, and nothing is kept', async () => {
    const cache = new TtlCache<string>({ ttlMs: 1000, maxEntries: 10 })
    const client = new AbortController()
    client.abort()
    const load = vi.fn((signal: AbortSignal) => new Promise<string>((_, reject) => signal.addEventListener('abort', () => reject(new AbortedError()))))
    await expect(cache.get('a', load, client.signal)).rejects.toBeInstanceOf(AbortedError)
    expect(load).toHaveBeenCalledTimes(1)
    expect(load.mock.calls[0]![0].aborted).toBe(true)
    expect(cache.size).toBe(0)
  })
})

describe('the bounds of the queue of reads', () => {
  /** Calls that run until the test lets each go, and which of them have started */
  function gated() {
    const started: number[] = []
    const gates = new Map<number, () => void>()
    return {
      started,
      release: (id: number) => gates.get(id)!(),
      work: (id: number) => async () => {
        started.push(id)
        await new Promise<void>(resolve => gates.set(id, resolve))
        return id
      },
    }
  }

  it('refuses a call that finds as many waiting as it allows, which is a refusal and no wait', async () => {
    const limit = createLimiter(1, { maxWaiting: 2 })
    const { started, release, work } = gated()
    const first = limit(work(1))
    const second = limit(work(2))
    const third = limit(work(3))
    await vi.waitFor(() => expect(started).toEqual([1]))

    await expect(limit(work(4))).rejects.toBeInstanceOf(QueueFullError)
    // the place of the refused call was never taken
    release(1)
    await vi.waitFor(() => expect(started).toEqual([1, 2]))
    release(2)
    await vi.waitFor(() => expect(started).toEqual([1, 2, 3]))
    release(3)
    expect(await Promise.all([first, second, third])).toEqual([1, 2, 3])
    // and the queue takes calls again once it has room
    const later = limit(work(5))
    await vi.waitFor(() => expect(started.at(-1)).toBe(5))
    release(5)
    expect(await later).toBe(5)
  })

  it('refuses a call that waited longer than it may, and does not run it', async () => {
    vi.useFakeTimers()
    try {
      const limit = createLimiter(1, { maxWaitMs: 1000 })
      const { started, release, work } = gated()
      const first = limit(work(1))
      const second = limit(work(2))
      const settled = second.then(() => 'ran', (failure: unknown) => failure)
      await vi.advanceTimersByTimeAsync(999)
      expect(started).toEqual([1])
      await vi.advanceTimersByTimeAsync(2)
      expect(await settled).toBeInstanceOf(QueueTimeoutError)
      release(1)
      await first
      expect(started).toEqual([1])
    }
    finally {
      vi.useRealTimers()
    }
  })

  it('does not time a call that got its turn: the wait ends with it', async () => {
    vi.useFakeTimers()
    try {
      const limit = createLimiter(1, { maxWaitMs: 1000 })
      const { started, release, work } = gated()
      const first = limit(work(1))
      const second = limit(work(2))
      await vi.advanceTimersByTimeAsync(500)
      release(1)
      await first
      await vi.advanceTimersByTimeAsync(5000)
      expect(started).toEqual([1, 2])
      release(2)
      expect(await second).toBe(2)
    }
    finally {
      vi.useRealTimers()
    }
  })

  it('takes a call whose request has closed out of the queue, never runs it, and hands the place on to the next', async () => {
    const limit = createLimiter(1)
    const { started, release, work } = gated()
    const closing = new AbortController()
    const first = limit(work(1))
    const closed = limit(work(2), closing.signal)
    const third = limit(work(3))
    closing.abort()
    await expect(closed).rejects.toBeInstanceOf(AbortedError)

    release(1)
    await first
    await vi.waitFor(() => expect(started).toEqual([1, 3]))
    release(3)
    expect(await third).toBe(3)
    expect(started).not.toContain(2)
  })

  it('does not run a call whose request has closed already', async () => {
    const limit = createLimiter(2)
    const closing = new AbortController()
    closing.abort()
    const work = vi.fn(async () => 1)
    await expect(limit(work, closing.signal)).rejects.toBeInstanceOf(AbortedError)
    expect(work).not.toHaveBeenCalled()
  })
})
