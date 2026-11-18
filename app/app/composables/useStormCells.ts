import type { StormScan } from '~/utils/storm-cells'
import { API_FETCH } from '~/utils/api-answer'
import { parseScan, REFRESH_MS } from '~/utils/storm-cells'

export type StormCellsStatus = 'idle' | 'pending' | 'success' | 'error'

/**
 * The newest scan of DWD's thunderstorm cells for the map's layer (GH-4208), asked for while the layer is `active` and
 * the tab is in front, and asked for again `interval` after each answer, which is how often DWD writes a scan. Hidden
 * (the layer is off, the tab is in the background) nothing is asked for and nothing is waiting: the timer is cleared, and
 * a tab that comes back asks at once if the scan it holds is older than `interval`.
 *
 * Most scans hold no cell, so an empty list is a scan like any other: `scan` is then a scan with no cells and the time
 * it is of, which is what the panel says. A scan that fails to refresh is kept, with `refreshFailed`, so that the map
 * does not lose its cells for one failed request; one that has never come is an `error`, which `retry` asks again.
 *
 * The cells are asked without their forecast track (`track=false`): the map draws the outline, the severity and the
 * direction of the motion, which stay. `load` is how the answer is asked for, by default that request; a test gives its own.
 */
export function useStormCells(active: () => boolean, options: { interval?: number, load?: () => Promise<unknown> } = {}) {
  const interval = options.interval ?? REFRESH_MS
  const ask = options.load ?? (() => $fetch('/api/storm-cells', { query: { track: 'false' }, ...API_FETCH }))
  const scan = shallowRef<StormScan | null>(null)
  const loading = ref(false)
  const error = shallowRef<unknown>(null)
  /** A refresh failed while a scan is in hand */
  const refreshFailed = ref(false)
  const visibility = useDocumentVisibility()

  /** When the scan in hand was asked for, for the tab that comes back */
  let askedAt = 0
  let timer: ReturnType<typeof setTimeout> | undefined
  let generation = 0

  const status = computed<StormCellsStatus>(() => {
    if (scan.value)
      return 'success'
    if (error.value)
      return 'error'
    return loading.value ? 'pending' : 'idle'
  })

  function stop() {
    clearTimeout(timer)
    timer = undefined
  }

  /** Whether the layer wants a scan now: shown, and in a tab that is in front */
  const wanted = () => active() && visibility.value !== 'hidden'

  function schedule() {
    stop()
    if (!wanted())
      return
    timer = setTimeout(() => void load(), interval)
  }

  async function load() {
    stop()
    const mine = ++generation
    loading.value = true
    try {
      const answer = await ask()
      if (mine !== generation)
        return
      scan.value = parseScan(answer)
      error.value = null
      refreshFailed.value = false
    }
    catch (failure) {
      if (mine !== generation)
        return
      if (scan.value)
        refreshFailed.value = true
      else
        error.value = failure
    }
    finally {
      if (mine === generation) {
        loading.value = false
        askedAt = Date.now()
        // the next one is `interval` after this answer, failed or not: a refused request is not asked again at once
        schedule()
      }
    }
  }

  /** Asks again now (the Retry of a scan that never came, and of a refresh that failed) */
  function retry() {
    error.value = null
    return load()
  }

  watch(wanted, (now) => {
    if (!now) {
      // a request on its way is not waited for: its answer is dropped, and nothing is scheduled after it
      generation++
      loading.value = false
      stop()
      return
    }
    // shown (or the tab is back): at once where there is no scan or the one in hand is as old as the interval, else when it is due
    const due = scan.value && Date.now() - askedAt < interval
    if (due) {
      timer = setTimeout(() => void load(), interval - (Date.now() - askedAt))
      return
    }
    void load()
  }, { immediate: true })

  onScopeDispose(() => {
    generation++
    stop()
  })

  return { scan, status, error, refreshFailed, loading, retry }
}
