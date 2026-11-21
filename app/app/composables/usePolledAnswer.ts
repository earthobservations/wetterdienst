export type PolledStatus = 'idle' | 'pending' | 'success' | 'error'

/**
 * An answer of the backend that is asked for while it is `active` and the tab is in front, and asked for again `interval`
 * after each answer (GH-4208, GH-3788: the radar's list of frames and the thunderstorm cells, which DWD writes every 5
 * minutes). Hidden (not active, or the tab in the background) nothing is asked for and nothing is waiting: the timer is
 * cleared, and the answer is asked for at once when it is wanted again.
 *
 * An answer that fails to refresh is kept, with `refreshFailed`, so that the page does not lose what it shows for one
 * failed request; one that has never come is an `error`, which `retry` asks again. A request on its way is what the page is
 * waiting for, whatever failed before it. `now` is the moment the age of the answer is read against: it is set whenever the
 * answer is wanted again, an answer comes or a request fails, which is at least every `interval` while it is shown.
 *
 * `load` is how it is asked for and `parse` reads the answer; a `parse` that throws is a failed request.
 */
export function usePolledAnswer<T>(active: () => boolean, options: { interval: number, load: () => Promise<unknown>, parse: (answer: unknown) => T }) {
  const data = shallowRef<T | null>(null)
  const loading = ref(false)
  const error = shallowRef<unknown>(null)
  /** A refresh failed while an answer is in hand */
  const refreshFailed = ref(false)
  /** The moment the age of the answer is read against */
  const now = ref(Date.now())
  const visibility = useDocumentVisibility()

  let timer: ReturnType<typeof setTimeout> | undefined
  let generation = 0

  const status = computed<PolledStatus>(() => {
    if (data.value)
      return 'success'
    if (loading.value)
      return 'pending'
    return error.value ? 'error' : 'idle'
  })

  function stop() {
    clearTimeout(timer)
    timer = undefined
  }

  /** Whether the answer is wanted now: shown, and in a tab that is in front */
  const wanted = () => active() && visibility.value !== 'hidden'

  function schedule() {
    stop()
    if (!wanted())
      return
    timer = setTimeout(() => void load(), options.interval)
  }

  async function load() {
    stop()
    const mine = ++generation
    loading.value = true
    try {
      const answer = await options.load()
      if (mine !== generation)
        return
      data.value = options.parse(answer)
      error.value = null
      refreshFailed.value = false
    }
    catch (failure) {
      if (mine !== generation)
        return
      if (data.value)
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

  /** Asks again now (the Retry of an answer that never came, and of a refresh that failed) */
  function retry() {
    error.value = null
    refreshFailed.value = false
    return load()
  }

  watch(wanted, (isWanted) => {
    // the age of the answer kept is read again, so that what was true hours ago is not taken for the sky now
    now.value = Date.now()
    if (!isWanted) {
      // a request on its way is not waited for: its answer is dropped, and nothing is scheduled after it
      generation++
      loading.value = false
      stop()
      return
    }
    // shown, or the tab is back: what failed before is of the time before, and the answer is asked for at once
    error.value = null
    refreshFailed.value = false
    void load()
  }, { immediate: true })

  onScopeDispose(() => {
    generation++
    stop()
  })

  return { data, status, error, refreshFailed, loading, now, retry }
}
