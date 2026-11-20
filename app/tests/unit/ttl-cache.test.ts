import { describe, expect, it, vi } from 'vitest'
import { createLimiter, TtlCache } from '../../server/utils/ttlCache'

// The memory of what the server calculated (GH-4258): fresh for a while, bounded, worked out once, and never keeping a failure.

describe('the cache', () => {
  const clock = () => {
    const state = { now: 1000 }
    return { state, now: () => state.now }
  }

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
