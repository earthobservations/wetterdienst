import type { StormScan } from '~/utils/storm-cells'
import { API_FETCH } from '~/utils/api-answer'
import { isOutdated, parseScan, REFRESH_MS } from '~/utils/storm-cells'

export type StormCellsStatus = 'idle' | 'pending' | 'success' | 'error'

/**
 * The newest scan of DWD's thunderstorm cells for the map's layer (GH-4208), asked for while the layer is `active` and
 * the tab is in front, and asked for again `interval` after each answer, which is how often DWD writes a scan. Hidden
 * (the layer is off, the tab is in the background) nothing is asked for and nothing is waiting: the timer is cleared, and
 * the scan is asked for at once when the layer is turned on again or the tab comes back.
 *
 * Most scans hold no cell, so an empty list is a scan like any other: `scan` is then a scan with no cells and the time
 * it is of, which is what the panel says. A scan that fails to refresh is kept, with `refreshFailed`, so that the map
 * does not lose its cells for one failed request; one that has never come is an `error`, which `retry` asks again.
 *
 * A scan that is kept ages: once its reference time is more than 20 minutes behind (the backend's own stale threshold)
 * it is `outdated`, and the page takes its cells off the map while the list says so. Age is read whenever the layer
 * turns on, an answer comes or a request fails, which is at least every `interval` while the layer is shown.
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
  /** The moment the age of the scan is read against */
  const now = ref(Date.now())
  const visibility = useDocumentVisibility()

  let timer: ReturnType<typeof setTimeout> | undefined
  let generation = 0

  // a request on its way is what the page is waiting for, whatever failed before it
  const status = computed<StormCellsStatus>(() => {
    if (scan.value)
      return 'success'
    if (loading.value)
      return 'pending'
    return error.value ? 'error' : 'idle'
  })
  const outdated = computed(() => Boolean(scan.value) && isOutdated(scan.value!.referenceTime, now.value))

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
        now.value = Date.now()
        // the next one is `interval` after this answer, failed or not: a refused request is not asked again at once
        schedule()
      }
    }
  }

  /** Asks again now (the Retry of a scan that never came, and of a refresh that failed) */
  function retry() {
    error.value = null
    refreshFailed.value = false
    return load()
  }

  watch(wanted, (isWanted) => {
    // the age of the scan kept is read again, so that cells that were true hours ago are not taken for the sky now
    now.value = Date.now()
    if (!isWanted) {
      // a request on its way is not waited for: its answer is dropped, and nothing is scheduled after it
      generation++
      loading.value = false
      stop()
      return
    }
    // shown, or the tab is back: what failed before is of the time before, and the scan is asked for at once
    error.value = null
    refreshFailed.value = false
    void load()
  }, { immediate: true })

  onScopeDispose(() => {
    generation++
    stop()
  })

  return { scan, status, error, refreshFailed, loading, outdated, retry }
}
