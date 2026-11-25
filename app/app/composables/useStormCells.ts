import type { PolledStatus } from '~/composables/usePolledAnswer'
import type { StormScan } from '~/utils/storm-cells'
import { usePolledAnswer } from '~/composables/usePolledAnswer'
import { API_FETCH } from '~/utils/api-answer'
import { isOutdated, parseScan, REFRESH_MS } from '~/utils/storm-cells'

export type StormCellsStatus = PolledStatus

/**
 * The newest scan of DWD's thunderstorm cells for the radar page (GH-4208, moved into the Radar tool by GH-3788), asked for
 * while the cells are `active` and the tab is in front, and asked for again `interval` after each answer, which is how often
 * DWD writes a scan (`usePolledAnswer`).
 *
 * Most scans hold no cell, so an empty list is a scan like any other: `scan` is then a scan with no cells and the time
 * it is of, which is what the panel says. A scan that fails to refresh is kept, with `refreshFailed`, so that the map
 * does not lose its cells for one failed request; one that has never come is an `error`, which `retry` asks again.
 *
 * A scan that is kept ages: once its reference time is more than 20 minutes behind (the backend's own stale threshold)
 * it is `outdated`, and the page takes its cells off the map while the list says so.
 *
 * The cells are asked without their forecast track (`track=false`): the map draws the outline, the severity and the
 * direction of the motion, which stay. `load` is how the answer is asked for, by default that request; a test gives its own.
 */
export function useStormCells(active: () => boolean, options: { interval?: number, load?: () => Promise<unknown> } = {}) {
  const polled = usePolledAnswer<StormScan>(active, {
    interval: options.interval ?? REFRESH_MS,
    load: options.load ?? (() => $fetch<unknown>('/api/storm-cells', { query: { track: 'false' }, ...API_FETCH })),
    parse: parseScan,
  })
  // the age is the server's time (`clockSkewMs`), not a device clock that may be wrong
  const outdated = computed(() => Boolean(polled.data.value) && isOutdated(polled.data.value!.referenceTime, polled.now.value + polled.data.value!.clockSkewMs))
  return { scan: polled.data, status: polled.status, error: polled.error, refreshFailed: polled.refreshFailed, loading: polled.loading, outdated, retry: polled.retry }
}
