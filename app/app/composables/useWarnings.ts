import type { PolledStatus } from '~/composables/usePolledAnswer'
import type { WarningSnapshot } from '~/utils/warnings'
import { usePolledAnswer } from '~/composables/usePolledAnswer'
import { API_FETCH } from '~/utils/api-answer'
import { parseWarnings, productFor, WARNINGS_REFRESH_MS, WARNINGS_STALE_AFTER_MS } from '~/utils/warnings'

export type WarningsStatus = PolledStatus

/**
 * DWD's weather warnings (GH-4295): the latest snapshot of `/api/alerts`, asked for while the warnings are `active` and the tab is in
 * front, and again every 5 minutes (`WARNINGS_REFRESH_MS`), which is how long the backend keeps the snapshot: asking sooner asks for
 * the same file. Hidden, nothing is asked for and nothing waits (`usePolledAnswer`), and the answer is asked for at once when it
 * is wanted again.
 *
 * It asks the community product, the one whose areas are the finer, in the language of the page where DWD writes in it
 * (`productFor`); the language of the page changing asks again. A snapshot that fails to refresh is kept, with `refreshFailed`;
 * once it is more than 15 minutes behind by the server's clock (`stale`) the pages say so, as what they show is then not the
 * sky now. `load` is how it is asked for; a test gives its own.
 */
export function useWarnings(active: () => boolean, options: { interval?: number, load?: (product: string) => Promise<unknown> } = {}) {
  // the app's own i18n, not `useI18n()`, which only a component's setup may call: the composable is also run in a scope of its own
  const { $i18n } = useNuxtApp()
  const product = computed(() => productFor($i18n.locale.value).product)
  const polled = usePolledAnswer<WarningSnapshot>(active, {
    interval: options.interval ?? WARNINGS_REFRESH_MS,
    load: () => options.load
      ? options.load(product.value)
      : $fetch('/api/alerts', { query: { granularity: 'community', language: product.value }, ...API_FETCH }),
    parse: parseWarnings,
  })
  // the texts are in the language asked for: another language is another request
  watch(product, () => {
    if (active())
      void polled.retry()
  })
  const stale = computed(() => {
    const at = polled.data.value?.retrievedAt ? Date.parse(polled.data.value.retrievedAt) : Number.NaN
    return Number.isFinite(at) && polled.now.value + polled.data.value!.clockSkewMs - at > WARNINGS_STALE_AFTER_MS
  })
  return { snapshot: polled.data, status: polled.status, error: polled.error, refreshFailed: polled.refreshFailed, now: polled.now, stale, retry: polled.retry }
}
