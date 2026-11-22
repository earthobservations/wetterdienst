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

/** What is being worked out for a key: the run, the askers waiting for it, and the means to stop it where none is left */
interface Running<T> {
  promise: Promise<T>
  controller: AbortController
  askers: number
}

/** The failure of an asker whose request ended before the answer came: it is nobody's to tell */
export class AbortedError extends Error {
  constructor() {
    super('The request ended before the answer was ready.')
    this.name = 'AbortError'
  }
}

export class TtlCache<T> {
  private readonly entries = new Map<string, Entry<T>>()
  private readonly pending = new Map<string, Running<T>>()
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

  /** Whether a fresh value of `key` is held (it is not made the one used last) */
  has(key: string): boolean {
    const held = this.entries.get(key)
    return !!held && held.expires > this.now()
  }

  /**
   * The value of `key`: the one held while it is fresh, else the one `load` works out (called once for any number of askers
   * that come while it runs).
   *
   * An asker whose `signal` aborts stops waiting at once (`AbortedError`), and the run is told to stop (the `signal` it is
   * given) only when every asker of it has gone: one client leaving does not take the answer from the others.
   */
  async get(key: string, load: (signal: AbortSignal) => Promise<T>, signal?: AbortSignal): Promise<T> {
    const held = this.entries.get(key)
    if (held && held.expires > this.now()) {
      // used now: last in the order of removal
      this.entries.delete(key)
      this.entries.set(key, held)
      return held.value
    }
    if (held)
      this.entries.delete(key)
    let running = this.pending.get(key)
    if (!running) {
      const controller = new AbortController()
      const started: Running<T> = {
        controller,
        askers: 0,
        promise: load(controller.signal).then((value) => {
          this.store(key, value)
          return value
        }).finally(() => {
          if (this.pending.get(key) === started)
            this.pending.delete(key)
        }),
      }
      // a run that every asker has left fails with nobody to tell
      started.promise.catch(() => {})
      this.pending.set(key, started)
      running = started
    }
    return this.wait(running, signal)
  }

  private wait(running: Running<T>, signal?: AbortSignal): Promise<T> {
    running.askers++
    if (!signal)
      return running.promise
    return new Promise<T>((resolve, reject) => {
      const leave = () => {
        if (--running.askers === 0)
          running.controller.abort()
        reject(new AbortedError())
      }
      if (signal.aborted) {
        leave()
        return
      }
      signal.addEventListener('abort', leave, { once: true })
      running.promise.then(
        (value) => {
          signal.removeEventListener('abort', leave)
          resolve(value)
        },
        (failure: unknown) => {
          signal.removeEventListener('abort', leave)
          reject(failure)
        },
      )
    })
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

/** Too many are waiting already: the call is refused, not queued */
export class QueueFullError extends Error {
  constructor() {
    super('Too many reads are waiting.')
    this.name = 'QueueFullError'
  }
}

/** The call waited longer than it may: it is refused, and its place is given up */
export class QueueTimeoutError extends Error {
  constructor() {
    super('The read waited too long for its turn.')
    this.name = 'QueueTimeoutError'
  }
}

export interface LimiterOptions {
  /** How many calls may wait at most; one more is refused with `QueueFullError` (default: no bound) */
  maxWaiting?: number
  /** How long a call may wait for its turn, in milliseconds, before `QueueTimeoutError` (default: no bound) */
  maxWaitMs?: number
}

interface Waiting {
  wake: () => void
  fail: (failure: Error) => void
}

/**
 * A queue for work that is costly to run side by side: at most `limit` of the calls run at once, the others wait their turn
 * (in the order they came), and a call that fails gives its place to the next. The queue is bounded in length and in time
 * (`LimiterOptions`), and a call whose `signal` aborts while it waits leaves the queue (`AbortedError`) and never runs.
 */
export function createLimiter(limit: number, { maxWaiting = Infinity, maxWaitMs = Infinity }: LimiterOptions = {}): <T>(work: () => Promise<T>, signal?: AbortSignal) => Promise<T> {
  let running = 0
  const waiting: Waiting[] = []
  return async <T>(work: () => Promise<T>, signal?: AbortSignal) => {
    if (signal?.aborted)
      throw new AbortedError()
    if (running < limit) {
      running++
    }
    else {
      if (waiting.length >= maxWaiting)
        throw new QueueFullError()
      // woken with the place of the call that ended, which is handed over and never freed in between
      await new Promise<void>((resolve, reject) => {
        let timer: ReturnType<typeof setTimeout> | undefined
        let onAbort = () => {}
        const turn: Waiting = {
          wake: () => {
            leave()
            resolve()
          },
          fail: (failure) => {
            leave()
            waiting.splice(waiting.indexOf(turn), 1)
            reject(failure)
          },
        }
        function leave() {
          clearTimeout(timer)
          signal?.removeEventListener('abort', onAbort)
        }
        if (Number.isFinite(maxWaitMs))
          timer = setTimeout(() => turn.fail(new QueueTimeoutError()), maxWaitMs)
        onAbort = () => turn.fail(new AbortedError())
        signal?.addEventListener('abort', onAbort, { once: true })
        waiting.push(turn)
      })
    }
    try {
      return await work()
    }
    finally {
      const next = waiting.shift()
      if (next)
        next.wake()
      else
        running--
    }
  }
}
