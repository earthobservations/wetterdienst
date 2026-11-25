import type { Ref } from 'vue'
import type { RadarFrame } from '~/utils/radar'
import { DWELL_MS, FRAME_MS, frameKey, frameUrl, indexAfterRefresh, nextReady, openingIndex, PRELOAD_CONCURRENCY, preloadOrder } from '~/utils/radar'

/** How long a frame's request may take before it is given up as a failure, in milliseconds */
export const LOAD_TIMEOUT_MS = 30_000

/**
 * Loads a frame's image into the browser's cache: true where it came, false where it did not (a 404, a 502, a 503, a 429, no connection).
 * A `fetch`, not an `Image`, so that the body is read to the end and the answer is kept by the HTTP cache (the frame of a run is
 * `max-age=3600`) for the picture on the map, which asks for the same address.
 */
export async function loadFrame(url: string, signal?: AbortSignal): Promise<boolean> {
  try {
    // a request that is not answered in 30 s is a failure (a hung connection would hold one of the 5 places of the queue for ever), and one
    // the page no longer wants (it was left) is aborted
    const timeout = AbortSignal.timeout(LOAD_TIMEOUT_MS)
    const response = await fetch(url, { signal: signal && 'any' in AbortSignal ? AbortSignal.any([signal, timeout]) : (signal ?? timeout) })
    if (!response.ok) {
      // the body of an error is not read: the connection is let go
      await response.body?.cancel().catch(() => {})
      return false
    }
    await response.blob()
    return true
  }
  catch {
    return false
  }
}

/**
 * How long a frame that failed waits before each new try, in milliseconds: two more tries, after 2 s and after 6 s. A 503 (too many
 * requests at once) or a 429 passes within seconds, so a frame that failed for it is not given up for good: and a frame that is given up
 * is asked for again with the next list (every 5 minutes).
 */
export const RETRY_DELAYS_MS: readonly number[] = [2000, 6000]

export interface RadarPlayerOptions {
  /** Whether the loop starts by itself once every frame is in hand: not under `prefers-reduced-motion` */
  autoplay: () => boolean
  /** How a frame's image is loaded; a test gives its own */
  load?: (url: string, signal?: AbortSignal) => Promise<boolean>
  /** How many frames are loaded at once */
  concurrency?: number
  /** The pace of the loop, for a test */
  frameMs?: number
  dwellMs?: number
  /** The pauses before the tries after a failure; a test gives shorter ones */
  retryDelays?: readonly number[]
}

/**
 * The loop of the Radar tool (GH-3788): the frames of the list, loaded a few at a time into the browser's cache (the server serves
 * 32 requests at once), the one shown, and the controls that move it.
 *
 * - **Loading.** The frame the loop opens on is asked for first, then the others in time order, `concurrency` at a time, so there
 *   is a picture at once and the loop plays smoothly from the cache. A frame that fails is asked for twice more, after 2 s and 6 s,
 *   and then dropped from the loop (`playable`): a missing frame must not stop the others. A dropped frame is not dropped for good:
 *   a new list asks for it again.
 * - **Playing.** The loop starts by itself, once, when every frame is in hand, unless `autoplay()` says it must not (the reader
 *   asked their system for less motion) or the reader has touched a control. It steps on to the next frame that is loaded, holds the
 *   last one a moment and goes round; it waits for a frame that is not there yet and stands still while the tab is hidden.
 *   Any control (pause, a step, the slider) is the reader's choice, and the loop never starts by itself again after it.
 * - **A new list** (every 5 minutes): the reader stays at the frame they were at where it is still in the loop. A loop that rests on
 *   the newest frame of the analysis follows the new newest one. Frames that were given up and are still listed are asked for again.
 */
export function useRadarPlayer(frames: Ref<readonly RadarFrame[]>, options: RadarPlayerOptions) {
  const load = options.load ?? loadFrame
  const concurrency = options.concurrency ?? PRELOAD_CONCURRENCY
  const frameMs = options.frameMs ?? FRAME_MS
  const dwellMs = options.dwellMs ?? DWELL_MS
  const retryDelays = options.retryDelays ?? RETRY_DELAYS_MS

  const loaded = shallowRef<ReadonlySet<string>>(new Set())
  const failed = shallowRef<ReadonlySet<string>>(new Set())
  const index = ref(0)
  const playing = ref(false)
  /** The reader used a control: the loop does not start by itself after that */
  const chosen = ref(false)
  let startedByItself = false
  const visibility = useDocumentVisibility()

  const playable = computed(() => frames.value.filter(frame => !failed.value.has(frameKey(frame))))
  const current = computed<RadarFrame | null>(() => playable.value[index.value] ?? null)
  const isLoaded = (frame: RadarFrame) => loaded.value.has(frameKey(frame))
  /** The frame to draw: the one the loop is at, once its image is in hand */
  const shown = computed(() => current.value && isLoaded(current.value) ? current.value : null)
  const settled = computed(() => playable.value.length > 0 && playable.value.every(isLoaded))
  const progress = computed(() => ({
    loaded: frames.value.filter(isLoaded).length,
    failed: frames.value.filter(frame => failed.value.has(frameKey(frame))).length,
    total: frames.value.length,
  }))

  // ---- loading -----------------------------------------------------------------------------------------------------

  /** The frames being asked for now: only these count against the `concurrency`; a frame that waits for its next try holds no place of the queue */
  const inFlight = new Set<string>()
  const waiting = new Set<string>()
  const tries = new Map<string, number>()
  const retryTimers = new Set<ReturnType<typeof setTimeout>>()
  // what is on its way is aborted with the page (the scope), so that a frame is not loaded for a page that is gone
  const controller = new AbortController()
  let stopped = false

  const add = (set: ReadonlySet<string>, key: string): ReadonlySet<string> => new Set(set).add(key)

  function pump() {
    if (stopped)
      return
    const wanted = preloadOrder(frames.value, new Set([...loaded.value, ...failed.value, ...inFlight, ...waiting]))
    for (const frame of wanted) {
      if (inFlight.size >= concurrency)
        break
      void fetchFrame(frame)
    }
  }

  async function fetchFrame(frame: RadarFrame) {
    const key = frameKey(frame)
    inFlight.add(key)
    const ok = await load(frameUrl(frame), controller.signal)
    inFlight.delete(key)
    if (stopped)
      return
    if (ok) {
      loaded.value = add(loaded.value, key)
    }
    else if ((tries.get(key) ?? 0) < retryDelays.length) {
      // another try after a pause, with the others going on meanwhile
      const delay = retryDelays[tries.get(key) ?? 0]!
      tries.set(key, (tries.get(key) ?? 0) + 1)
      waiting.add(key)
      const timer = setTimeout(() => {
        // a timer that has run is no longer kept
        retryTimers.delete(timer)
        waiting.delete(key)
        pump()
      }, delay)
      retryTimers.add(timer)
    }
    else {
      failed.value = add(failed.value, key)
    }
    pump()
  }

  watch(frames, () => {
    // what the list no longer has is forgotten, so that the sets do not grow for as long as the page is open
    const keys = new Set(frames.value.map(frameKey))
    loaded.value = new Set([...loaded.value].filter(key => keys.has(key)))
    // a frame that was given up is asked for again: it may have failed for a 503 or a 429 that is over, or DWD may have it now (M3)
    failed.value = new Set()
    tries.clear()
    waiting.clear()
    pump()
  }, { immediate: true })

  // ---- which frame ------------------------------------------------------------------------------------------------

  watch(playable, (next, before) => {
    const was = before?.[index.value] ?? null
    const rested = before && was && before.length > 0 && index.value === openingIndex(before)
    index.value = was && !rested ? indexAfterRefresh(next, was) : openingIndex(next)
  }, { immediate: true })

  // ---- playing ----------------------------------------------------------------------------------------------------

  let timer: ReturnType<typeof setTimeout> | undefined
  function stopTimer() {
    clearTimeout(timer)
    timer = undefined
  }

  function schedule() {
    stopTimer()
    const count = playable.value.length
    if (!playing.value || count < 2 || visibility.value === 'hidden' || stopped)
      return
    timer = setTimeout(() => {
      const next = nextReady(index.value, count, candidate => isLoaded(playable.value[candidate]!))
      // a frame that is not in yet is waited for; the watch below runs again when it is
      if (next === null)
        schedule()
      else
        index.value = next
    }, index.value === count - 1 ? dwellMs : frameMs)
  }
  watch([playing, index, loaded, playable, visibility], schedule)

  // by itself, once, when everything is in hand
  watch([settled, () => options.autoplay()], ([isSettled, allowed]) => {
    if (isSettled && allowed && !chosen.value && !startedByItself && playable.value.length > 1) {
      startedByItself = true
      playing.value = true
    }
    // the reader asked for less motion while it was running by itself
    if (!allowed && startedByItself && !chosen.value)
      playing.value = false
  }, { immediate: true })

  // ---- the controls ---------------------------------------------------------------------------------------------

  function play() {
    chosen.value = true
    playing.value = playable.value.length > 1
  }
  function pause() {
    chosen.value = true
    playing.value = false
  }
  function toggle() {
    if (playing.value)
      pause()
    else
      play()
  }
  /** Moves to the frame at `to` (clamped to the loop) and pauses: the slider and the steps are the reader's hand on the loop */
  function seek(to: number) {
    chosen.value = true
    playing.value = false
    index.value = Math.min(Math.max(Math.round(to), 0), Math.max(playable.value.length - 1, 0))
  }
  function step(by: number) {
    seek(index.value + by)
  }

  onScopeDispose(() => {
    stopped = true
    stopTimer()
    controller.abort()
    retryTimers.forEach(clearTimeout)
    retryTimers.clear()
  })

  return { playable, index, current, shown, playing, settled, progress, loaded, play, pause, toggle, seek, step }
}
