import type { PolledStatus } from '~/composables/usePolledAnswer'
import type { WarningSnapshot } from '~/utils/warnings'
import { usePolledAnswer } from '~/composables/usePolledAnswer'
import { API_FETCH } from '~/utils/api-answer'
import { parseWarnings, productFor, WARNINGS_CLOCK_MS, WARNINGS_REFRESH_MS, WARNINGS_STALE_AFTER_MS, WARNINGS_TIMEOUT_MS } from '~/utils/warnings'

export type WarningsStatus = PolledStatus

/**
 * DWD's weather warnings (GH-4295): the latest snapshot of `/api/alerts`, asked for while the warnings are `active` and the tab is in
 * front, and again every 5 minutes (`WARNINGS_REFRESH_MS`), which is how long the backend keeps the snapshot: asking sooner asks for
 * the same file. Hidden, nothing is asked for and nothing waits (`usePolledAnswer`), and the answer is asked for at once when it
 * is wanted again.
 *
 * A request that does not answer is given up after 30 seconds (`WARNINGS_TIMEOUT_MS`) and counts as a failed one, so that the next is scheduled: a
 * request that hangs would otherwise leave the warnings as they were for ever. It asks the community product, in the language of the page where DWD
 * writes in it (`productFor`); the language of the page changing asks again. A snapshot that fails to refresh is kept, with `refreshFailed`.
 *
 * `now` is the server's clock (the device's, and how far the answer's own `retrieved_at` was from it: `clockSkewMs`), and it moves every minute while
 * the warnings are wanted, with no request, so that a warning that begins or ends, and a snapshot that grows old, change on the page as they do.
 * Once the snapshot is more than 15 minutes behind it is `stale`, whether or not a refresh has failed: both are said. `load` is how it is asked for;
 * a test gives its own.
 */
export function useWarnings(active: () => boolean, options: { interval?: number, load?: (product: string) => Promise<unknown> } = {}) {
  // the app's own i18n, not `useI18n()`, which only a component's setup may call: the composable is also run in a scope of its own
  const { $i18n } = useNuxtApp()
  const product = computed(() => productFor($i18n.locale.value).product)

  /** The request, given up after the time allowed: the one that hangs is a failure like the one that is refused */
  async function ask(): Promise<unknown> {
    let timer: ReturnType<typeof setTimeout> | undefined
    const giveUp = new Promise<never>((_, reject) => {
      timer = setTimeout(() => reject(new Error('The weather warnings did not answer in time')), WARNINGS_TIMEOUT_MS)
    })
    try {
      const asked = options.load
        ? options.load(product.value)
        : $fetch('/api/alerts', { query: { granularity: 'community', language: product.value }, timeout: WARNINGS_TIMEOUT_MS, ...API_FETCH })
      return await Promise.race([asked, giveUp])
    }
    finally {
      clearTimeout(timer)
    }
  }

  const polled = usePolledAnswer<WarningSnapshot>(active, {
    interval: options.interval ?? WARNINGS_REFRESH_MS,
    load: ask,
    parse: parseWarnings,
  })
  // the texts are in the language asked for: another language is another request
  watch(product, () => {
    if (active())
      void polled.retry()
  })

  // the device's clock, moved every minute while the warnings are wanted, and at each answer
  const clock = ref(Date.now())
  const visibility = useDocumentVisibility()
  let ticker: ReturnType<typeof setTimeout> | undefined
  function stopTicking() {
    clearTimeout(ticker)
    ticker = undefined
  }
  function tick() {
    stopTicking()
    ticker = setTimeout(() => {
      clock.value = Date.now()
      tick()
    }, WARNINGS_CLOCK_MS)
  }
  watch(() => active() && visibility.value !== 'hidden', (wanted) => {
    if (wanted) {
      clock.value = Date.now()
      tick()
    }
    else {
      stopTicking()
    }
  }, { immediate: true })
  watch(polled.now, (at) => {
    clock.value = at
  })
  onScopeDispose(stopTicking)

  /** The server's time: the device's clock and how far the answer said it was from it */
  const now = computed(() => clock.value + (polled.data.value?.clockSkewMs ?? 0))
  const stale = computed(() => {
    const at = polled.data.value?.retrievedAt ? Date.parse(polled.data.value.retrievedAt) : Number.NaN
    return Number.isFinite(at) && now.value - at > WARNINGS_STALE_AFTER_MS
  })
  return { snapshot: polled.data, status: polled.status, error: polled.error, refreshFailed: polled.refreshFailed, now, stale, retry: polled.retry }
}
