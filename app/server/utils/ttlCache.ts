// A small cache of what the server worked out, held in the memory of the process (GH-4258): each entry lives for `ttlMs`, at
// most `maxEntries` are kept (the one used longest ago goes first), and a key that is being worked out is worked out once,
// whoever asks while it is: the others wait for the same answer. A failure is nobody's answer: it is not kept, and the next
// asker tries again.
//
// Nitro's own cache (`defineCachedEventHandler`) is not used because its storage is the process's memory as well, with no
// limit on the entries and none removed when they expire; an entry of this cache is a station's years or the list of the
// stations, and the number of stations that can be asked for is the 133,000 of GHCN.

export interface TtlCacheOptions {
  /** How long an entry is served, in milliseconds */
  ttlMs: number
  /** How many entries are kept at most */
  maxEntries: number
  /** The clock, in milliseconds; the tests move it */
  now?: () => number
}

interface Entry<T> {
  value: T
  expires: number
}

export class TtlCache<T> {
  private readonly entries = new Map<string, Entry<T>>()
  private readonly pending = new Map<string, Promise<T>>()
  private readonly ttlMs: number
  private readonly maxEntries: number
  private readonly now: () => number

  constructor({ ttlMs, maxEntries, now = Date.now }: TtlCacheOptions) {
    this.ttlMs = ttlMs
    this.maxEntries = maxEntries
    this.now = now
  }

  /** How many entries are held, the expired ones that have not been asked for again included */
  get size(): number {
    return this.entries.size
  }

  /**
   * The value of `key`: the one held while it is fresh, else the one `load` works out (called once for any number of askers
   * that come while it runs).
   */
  async get(key: string, load: () => Promise<T>): Promise<T> {
    const held = this.entries.get(key)
    if (held && held.expires > this.now()) {
      // used now: last in the order of removal
      this.entries.delete(key)
      this.entries.set(key, held)
      return held.value
    }
    if (held)
      this.entries.delete(key)
    const running = this.pending.get(key)
    if (running)
      return running
    const promise = load().then((value) => {
      this.store(key, value)
      return value
    }).finally(() => {
      this.pending.delete(key)
    })
    this.pending.set(key, promise)
    return promise
  }

  private store(key: string, value: T): void {
    this.entries.delete(key)
    this.entries.set(key, { value, expires: this.now() + this.ttlMs })
    while (this.entries.size > this.maxEntries) {
      const oldest = this.entries.keys().next().value
      if (oldest === undefined)
        break
      this.entries.delete(oldest)
    }
  }

  clear(): void {
    this.entries.clear()
  }
}

/**
 * A queue for work that is costly to run side by side: at most `limit` of the calls run at once, the others wait their turn
 * (in the order they came), and a call that fails gives its place to the next.
 */
export function createLimiter(limit: number): <T>(work: () => Promise<T>) => Promise<T> {
  let running = 0
  const waiting: Array<() => void> = []
  return async <T>(work: () => Promise<T>) => {
    if (running < limit)
      running++
    else
      // woken with the place of the call that ended, which is handed over and never freed in between
      await new Promise<void>(resolve => waiting.push(resolve))
    try {
      return await work()
    }
    finally {
      const next = waiting.shift()
      if (next)
        next()
      else
        running--
    }
  }
}
