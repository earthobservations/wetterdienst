import type { RadarLoop } from '~/utils/radar'
import { usePolledAnswer } from '~/composables/usePolledAnswer'
import { API_FETCH } from '~/utils/api-answer'
import { isStale, parseLoop, PAST_MINUTES, RADAR_PRODUCT, RADAR_REFRESH_MS } from '~/utils/radar'

/**
 * The list of the frames of DWD's precipitation radar (GH-3788): the last two hours of the analysis and the forecast of the newest
 * run, asked for while the page is `active` and the tab is in front, and asked for again every 5 minutes, which is how often DWD
 * writes a run (`usePolledAnswer`). A list that fails to refresh is kept, with `refreshFailed`, so that the loop on the screen does
 * not vanish for one failed request.
 *
 * `stale` is the newest analysis frame being more than 20 minutes old at the moment the list was read (DWD's feed has stopped,
 * or the list is old because the refreshes have failed): the loop is shown and says so. The backend says the same in a
 * `radar-stale` warning, which `loop.stale` carries; either is a stale loop.
 */
export function useRadarFrames(active: () => boolean, options: { interval?: number, load?: () => Promise<unknown> } = {}) {
  const polled = usePolledAnswer<RadarLoop>(active, {
    interval: options.interval ?? RADAR_REFRESH_MS,
    load: options.load ?? (() => $fetch('/api/radar/frames', { query: { product: RADAR_PRODUCT, past: PAST_MINUTES, forecast: true }, ...API_FETCH })),
    parse: parseLoop,
  })
  const stale = computed(() => Boolean(polled.data.value) && (polled.data.value!.stale || isStale(polled.data.value!.frames, polled.now.value)))
  return { loop: polled.data, status: polled.status, error: polled.error, refreshFailed: polled.refreshFailed, loading: polled.loading, now: polled.now, stale, retry: polled.retry }
}
