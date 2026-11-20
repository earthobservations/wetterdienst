import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { effectScope, nextTick, ref } from 'vue'
import { loadFrame, useRadarPlayer } from '~/composables/useRadarPlayer'
import { frameKey, parseLoop } from '~/utils/radar'
import { radarAnswer } from '../../helpers/radar-answer'

// The loop of the Radar tool (GH-3788): the frames are loaded a few at a time (the server serves 32 requests at once), the frame the
// loop opens on first; one that fails is asked for once more and then dropped; the loop starts by itself once everything is in hand
// unless the system asks for less motion; any control is the reader's and keeps it from starting by itself; and a new list does not
// throw the reader back to the start.

const scopes: Array<ReturnType<typeof effectScope>> = []

/** The frames of a loop of `past` minutes and the 24 of the forecast, `run` being the newest run */
function framesOf(run = '2026-11-19T21:25:00Z', past = 120) {
  return parseLoop(radarAnswer({ run, past })).frames
}

interface Pending { url: string, resolve: (ok: boolean) => void }

/** A loader that holds every request until the test answers it, and counts how many are open at once */
function holdingLoader() {
  const pending: Pending[] = []
  const asked: string[] = []
  let open = 0
  let mostAtOnce = 0
  const load = (url: string) => new Promise<boolean>((resolve) => {
    asked.push(url)
    open++
    mostAtOnce = Math.max(mostAtOnce, open)
    pending.push({ url, resolve: (ok) => {
      open--
      resolve(ok)
    } })
  })
  return { load, pending, asked, mostAtOnce: () => mostAtOnce }
}

/** The player in a scope of its own, as a page has it */
function mount(options: { frames?: ReturnType<typeof framesOf>, autoplay?: boolean, load?: (url: string, signal?: AbortSignal) => Promise<boolean>, concurrency?: number } = {}) {
  const frames = ref(options.frames ?? framesOf())
  const autoplay = ref(options.autoplay ?? true)
  const scope = effectScope()
  scopes.push(scope)
  const player = scope.run(() => useRadarPlayer(frames, { autoplay: () => autoplay.value, load: options.load ?? (async () => true), concurrency: options.concurrency, frameMs: 100, dwellMs: 300, retryDelays: [1000, 3000] }))!
  return { frames, autoplay, player, scope }
}

async function settle() {
  await vi.advanceTimersByTimeAsync(0)
  await nextTick()
}

beforeEach(() => {
  vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout'] })
})

afterEach(() => {
  scopes.splice(0).forEach(scope => scope.stop())
  vi.useRealTimers()
})

describe('loading the frames', () => {
  it('asks for the frame the loop opens on first, then the others in time order, and never more than 5 at once', async () => {
    const loader = holdingLoader()
    const { player } = mount({ load: loader.load })
    await settle()
    // the first five: the newest frame of the analysis, then the oldest four
    expect(loader.asked).toHaveLength(5)
    expect(loader.asked[0]).toContain('time=2026-11-19T21%3A25%3A00Z')
    expect(loader.asked[1]).toContain('time=2026-11-19T19%3A25%3A00Z')
    expect(player.shown.value).toBeNull()
    // as one is answered, the next is asked for: the open requests stay at 5
    loader.pending.shift()!.resolve(true)
    await settle()
    expect(loader.asked).toHaveLength(6)
    expect(player.shown.value?.time).toBe('2026-11-19T21:25:00Z')
    for (let step = 0; step < 60; step++) {
      loader.pending.shift()?.resolve(true)
      await settle()
    }
    expect(loader.asked).toHaveLength(49)
    expect(loader.mostAtOnce()).toBe(5)
    expect(new Set(loader.asked).size).toBe(49)
  })

  it('has a picture as soon as the opening frame is in, before the others', async () => {
    const loader = holdingLoader()
    const { player } = mount({ load: loader.load })
    await settle()
    expect(player.current.value?.time).toBe('2026-11-19T21:25:00Z')
    expect(player.shown.value).toBeNull()
    loader.pending[0]!.resolve(true)
    await settle()
    expect(player.shown.value?.time).toBe('2026-11-19T21:25:00Z')
    expect(player.settled.value).toBe(false)
  })

  it('asks for a frame that failed twice more, after the pauses of its backoff, and drops it from the loop where it fails every time', async () => {
    const bad = framesOf()[3]!
    const failures: string[] = []
    const load = vi.fn(async (url: string) => {
      if (url.includes(encodeURIComponent(bad.time)) && url.includes(`run=${encodeURIComponent(bad.run)}`)) {
        failures.push(url)
        return false
      }
      return true
    })
    const { player } = mount({ load, autoplay: false })
    await settle()
    // the first failure is not yet a drop: the frame waits for its second try
    expect(failures).toHaveLength(1)
    expect(player.playable.value).toHaveLength(49)
    await vi.advanceTimersByTimeAsync(900)
    expect(failures).toHaveLength(1)
    await vi.advanceTimersByTimeAsync(200)
    await settle()
    expect(failures).toHaveLength(2)
    expect(player.playable.value).toHaveLength(49)
    // the third after the longer pause, and then it is given up
    await vi.advanceTimersByTimeAsync(3100)
    await settle()
    expect(failures).toHaveLength(3)
    expect(player.playable.value).toHaveLength(48)
    expect(player.playable.value.map(frame => frameKey(frame))).not.toContain(frameKey(bad))
    expect(player.progress.value).toEqual({ loaded: 48, failed: 1, total: 49 })
    // the others are in hand: the loop is settled without it
    expect(player.settled.value).toBe(true)
  })

  it('does not let a frame that waits for its next try hold one of the 5 places: the others go on, and a loop that fails altogether is given up after its tries, not after 49 of them in turn', async () => {
    const asked: string[] = []
    const { player } = mount({ autoplay: false, load: async (url) => {
      asked.push(url)
      return false
    } })
    await settle()
    // every frame has had its first try at once, though 5 are asked for at a time: a failure frees its place
    expect(new Set(asked).size).toBe(49)
    await vi.advanceTimersByTimeAsync(1100)
    await vi.advanceTimersByTimeAsync(3100)
    await settle()
    expect(player.progress.value).toEqual({ loaded: 0, failed: 49, total: 49 })
  })

  it('keeps going where the frame is there on a later try', async () => {
    const bad = framesOf()[3]!
    let tries = 0
    const load = async (url: string) => {
      if (url.includes(encodeURIComponent(bad.time)) && url.includes(`run=${encodeURIComponent(bad.run)}`))
        return ++tries > 2
      return true
    }
    const { player } = mount({ load, autoplay: false })
    await settle()
    await vi.advanceTimersByTimeAsync(1100)
    await settle()
    await vi.advanceTimersByTimeAsync(3100)
    await settle()
    expect(tries).toBe(3)
    expect(player.playable.value).toHaveLength(49)
    expect(player.progress.value.failed).toBe(0)
  })

  it('does not give a frame up for good: it is asked for again with the next list, where it is still listed (a 503 or a 429 passes)', async () => {
    const bad = framesOf()[3]!
    let broken = true
    const asked: string[] = []
    const load = async (url: string) => {
      asked.push(url)
      return !(broken && url.includes(encodeURIComponent(bad.time)) && url.includes(`run=${encodeURIComponent(bad.run)}`))
    }
    const { player, frames } = mount({ load, autoplay: false })
    await settle()
    await vi.advanceTimersByTimeAsync(1100)
    await settle()
    await vi.advanceTimersByTimeAsync(3100)
    await settle()
    expect(player.playable.value).toHaveLength(48)
    // DWD is fine again, and the list is asked for again: the same list of frames, a new answer
    broken = false
    frames.value = framesOf()
    await settle()
    expect(player.playable.value).toHaveLength(49)
    expect(player.progress.value.failed).toBe(0)
    // only the frame that was given up was asked for again
    expect(asked.filter(url => url.includes(encodeURIComponent(bad.time)) && url.includes(`run=${encodeURIComponent(bad.run)}`))).toHaveLength(4)
  })
})

describe('the request of a frame (N2)', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('is true for a frame that came, with the body read to the end so that the HTTP cache keeps it, and is asked for with a signal', async () => {
    const blob = vi.fn(async () => new Blob(['png']))
    const fetcher = vi.fn(async () => ({ ok: true, blob }))
    vi.stubGlobal('fetch', fetcher)
    expect(await loadFrame('/api/radar/frame?x')).toBe(true)
    expect(blob).toHaveBeenCalled()
    expect((fetcher.mock.calls[0] as unknown as [string, { signal: AbortSignal }])[1].signal).toBeInstanceOf(AbortSignal)
  })

  it('is false for an error, whose body is cancelled and not read: the connection is let go', async () => {
    const cancel = vi.fn(async () => {})
    const blob = vi.fn()
    vi.stubGlobal('fetch', vi.fn(async () => ({ ok: false, body: { cancel }, blob })))
    expect(await loadFrame('/api/radar/frame?x')).toBe(false)
    expect(cancel).toHaveBeenCalled()
    expect(blob).not.toHaveBeenCalled()
  })

  it('is false for a request that fails, and for one that is aborted by the caller', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => {
      throw new TypeError('network')
    }))
    expect(await loadFrame('/api/radar/frame?x')).toBe(false)
    const controller = new AbortController()
    vi.stubGlobal('fetch', vi.fn((_url: string, init: { signal: AbortSignal }) => new Promise((_, reject) => {
      init.signal.addEventListener('abort', () => reject(new DOMException('aborted', 'AbortError')))
    })))
    const result = loadFrame('/api/radar/frame?x', controller.signal)
    controller.abort()
    expect(await result).toBe(false)
  })

  it('has the requests that are on their way aborted when the page is left (the scope stops)', async () => {
    const signals: AbortSignal[] = []
    const { scope } = mount({ autoplay: false, load: (_url, signal) => {
      signals.push(signal!)
      return new Promise<boolean>(() => {})
    } })
    await settle()
    expect(signals).toHaveLength(5)
    expect(signals.every(signal => !signal.aborted)).toBe(true)
    scope.stop()
    expect(signals.every(signal => signal.aborted)).toBe(true)
  })
})

describe('playing', () => {
  it('starts by itself once every frame is in hand, and goes round the loop, holding the last frame a moment', async () => {
    const { player } = mount()
    await settle()
    expect(player.settled.value).toBe(true)
    expect(player.playing.value).toBe(true)
    expect(player.index.value).toBe(24)
    await vi.advanceTimersByTimeAsync(100)
    expect(player.index.value).toBe(25)
    await vi.advanceTimersByTimeAsync(100 * 23)
    expect(player.index.value).toBe(48)
    // the last frame is held for the dwell, then the loop starts again from the first
    await vi.advanceTimersByTimeAsync(299)
    expect(player.index.value).toBe(48)
    await vi.advanceTimersByTimeAsync(1)
    expect(player.index.value).toBe(0)
    await vi.advanceTimersByTimeAsync(100)
    expect(player.index.value).toBe(1)
  })

  it('does not start by itself where the system asks for less motion, and runs when the reader presses play', async () => {
    const { player } = mount({ autoplay: false })
    await settle()
    expect(player.settled.value).toBe(true)
    expect(player.playing.value).toBe(false)
    await vi.advanceTimersByTimeAsync(5000)
    expect(player.index.value).toBe(24)
    player.play()
    expect(player.playing.value).toBe(true)
    await vi.advanceTimersByTimeAsync(100)
    expect(player.index.value).toBe(25)
  })

  it('does not start before every frame is in hand', async () => {
    const loader = holdingLoader()
    const { player } = mount({ load: loader.load })
    await settle()
    for (let step = 0; step < 20; step++) {
      loader.pending.shift()?.resolve(true)
      await settle()
    }
    expect(player.settled.value).toBe(false)
    expect(player.playing.value).toBe(false)
  })

  it('waits for a frame that is not in yet, and goes on when it comes', async () => {
    // the reader has pressed play before the loop is whole: the frame after the newest is held back
    const gate: Array<() => void> = []
    const frames = framesOf()
    const slow = frames[25]!
    const load = (url: string) => url.includes(encodeURIComponent(slow.time)) && url.includes(`run=${encodeURIComponent(slow.run)}`)
      ? new Promise<boolean>(resolve => gate.push(() => resolve(true)))
      : Promise.resolve(true)
    const { player } = mount({ load, frames })
    await settle()
    player.play()
    await vi.advanceTimersByTimeAsync(1000)
    // it went round the frames that are there and skips the one that is not
    expect(player.playing.value).toBe(true)
    expect(player.current.value?.time).not.toBe(slow.time)
    gate.forEach(open => open())
    await settle()
    await vi.advanceTimersByTimeAsync(5000)
    expect(player.progress.value.loaded).toBe(49)
  })

  it('pauses on every control, and the loop never starts by itself again after one', async () => {
    const { player, autoplay } = mount()
    await settle()
    expect(player.playing.value).toBe(true)
    player.pause()
    expect(player.playing.value).toBe(false)
    const at = player.index.value
    await vi.advanceTimersByTimeAsync(2000)
    expect(player.index.value).toBe(at)
    // not even where the setting changes or the list is renewed
    autoplay.value = false
    autoplay.value = true
    await settle()
    expect(player.playing.value).toBe(false)
  })

  it('stops where the reader steps or drags the slider, and clamps to the loop', async () => {
    const { player } = mount()
    await settle()
    player.step(-1)
    expect(player.playing.value).toBe(false)
    expect(player.index.value).toBe(23)
    player.seek(-5)
    expect(player.index.value).toBe(0)
    player.seek(999)
    expect(player.index.value).toBe(48)
    player.seek(10.4)
    expect(player.index.value).toBe(10)
    player.step(1)
    expect(player.index.value).toBe(11)
  })

  it('toggles', async () => {
    const { player } = mount({ autoplay: false })
    await settle()
    player.toggle()
    expect(player.playing.value).toBe(true)
    player.toggle()
    expect(player.playing.value).toBe(false)
  })

  it('stops the loop that started by itself where the system then asks for less motion', async () => {
    const { player, autoplay } = mount()
    await settle()
    expect(player.playing.value).toBe(true)
    autoplay.value = false
    await settle()
    expect(player.playing.value).toBe(false)
  })

  it('stands still while the tab is hidden, and goes on when it is back', async () => {
    const { player } = mount()
    await settle()
    Object.defineProperty(document, 'visibilityState', { configurable: true, get: () => 'hidden' })
    document.dispatchEvent(new Event('visibilitychange'))
    await settle()
    const at = player.index.value
    await vi.advanceTimersByTimeAsync(2000)
    expect(player.index.value).toBe(at)
    Object.defineProperty(document, 'visibilityState', { configurable: true, get: () => 'visible' })
    document.dispatchEvent(new Event('visibilitychange'))
    await settle()
    await vi.advanceTimersByTimeAsync(100)
    expect(player.index.value).not.toBe(at)
  })

  it('does not play a loop of one frame', async () => {
    const { player } = mount({ frames: framesOf('2026-11-19T21:25:00Z', 0).slice(0, 1) })
    await settle()
    expect(player.playable.value).toHaveLength(1)
    expect(player.playing.value).toBe(false)
    player.play()
    expect(player.playing.value).toBe(false)
  })
})

describe('a new list of the frames', () => {
  it('keeps the reader at the frame they were at, where it is still in the loop', async () => {
    const { player, frames } = mount({ autoplay: false })
    await settle()
    player.seek(10)
    const watching = player.current.value!.time
    frames.value = framesOf('2026-11-19T21:30:00Z')
    await settle()
    expect(player.current.value?.time).toBe(watching)
  })

  it('follows the new newest frame of the analysis where the loop rests on the newest', async () => {
    const { player, frames } = mount({ autoplay: false })
    await settle()
    expect(player.current.value?.time).toBe('2026-11-19T21:25:00Z')
    frames.value = framesOf('2026-11-19T21:30:00Z')
    await settle()
    expect(player.current.value?.time).toBe('2026-11-19T21:30:00Z')
    expect(player.current.value?.kind).toBe('observation')
  })

  it('asks for the frames it has not, and not for the ones it has', async () => {
    const asked: string[] = []
    const { frames } = mount({ autoplay: false, load: async (url) => {
      asked.push(url)
      return true
    } })
    await settle()
    expect(asked).toHaveLength(49)
    frames.value = framesOf('2026-11-19T21:30:00Z')
    await settle()
    // one new analysis frame, and the forecast of the new run (24), which are other images than the old run's
    expect(asked).toHaveLength(49 + 1 + 24)
  })

  it('forgets what the list no longer has', async () => {
    const { player, frames } = mount({ autoplay: false })
    await settle()
    frames.value = framesOf('2026-11-19T21:30:00Z', 60)
    await settle()
    expect(player.progress.value.total).toBe(13 + 24)
    expect(player.loaded.value.size).toBeLessThanOrEqual(13 + 24)
  })
})
