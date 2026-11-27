import type { Ref } from 'vue'
import type { KostraTable } from '~/utils/kostra'
import type { Point } from '~/utils/map-tool'
import { API_FETCH } from '~/utils/api-answer'
import { describeFetchError } from '~/utils/api-error'
import { parseKostra } from '~/utils/kostra'

/** Where the table is: not asked for yet, on its way, in hand, the point is outside DWD's grid, or the request failed */
export type KostraStatus = 'idle' | 'pending' | 'success' | 'outside' | 'error'

/**
 * DWD's design rainfall of a point (`GET /api/kostra`, GH-4500), asked for again whenever the point changes. The whole table is asked
 * for (no `duration`, no `return_period`): 22 tables of DWD, about 2 s the first time and then from the backend's cache.
 *
 * A point outside the grid (outside Germany and about 10 km, or in the sea) is a 400 of the backend, and is the status `outside`, not
 * an error: it is a fact about the place the reader chose, which the page tells in its own words (the backend's sentence is English only,
 * and says the same). Any other failure is `error` with what the backend said (`detail`), which `retry` asks again. An answer of an earlier point that
 * arrives after the point has moved is dropped, and the request it was is cancelled.
 *
 * `load` is how it is asked for, by default that request; a test gives its own.
 */
export function useKostra(point: Ref<Point | null>, options: { load?: (point: Point, signal: AbortSignal) => Promise<unknown> } = {}) {
  const table = shallowRef<KostraTable | null>(null)
  const status = ref<KostraStatus>('idle')
  /** What the backend said of a failure */
  const detail = ref('')

  const load = options.load ?? ((at: Point, signal: AbortSignal) => $fetch<unknown>('/api/kostra', { query: { latitude: at.latitude, longitude: at.longitude }, signal, ...API_FETCH }))

  let generation = 0
  let controller: AbortController | null = null

  async function ask(at: Point | null) {
    const mine = ++generation
    controller?.abort()
    controller = null
    detail.value = ''
    if (!at) {
      table.value = null
      status.value = 'idle'
      return
    }
    const own = new AbortController()
    controller = own
    // the table of the earlier point is not the answer for this one: it goes while the new one is on its way
    table.value = null
    status.value = 'pending'
    try {
      const answer = parseKostra(await load(at, own.signal))
      if (mine !== generation)
        return
      if (!answer)
        throw new Error('The answer of the API is not the table of a cell.')
      table.value = answer
      status.value = 'success'
    }
    catch (error) {
      if (mine !== generation)
        return
      const failed = error as { statusCode?: number, status?: number, response?: { status?: number } } | null
      const code = failed?.statusCode ?? failed?.status ?? failed?.response?.status
      if (code === 400) {
        status.value = 'outside'
        return
      }
      detail.value = describeFetchError(error)
      status.value = 'error'
    }
  }

  // the point's values, not the object: a route that changes for another reason makes a new one for the same place
  watch(() => point.value ? `${point.value.latitude},${point.value.longitude}` : null, () => void ask(point.value), { immediate: true })
  onBeforeUnmount(() => {
    generation++
    controller?.abort()
  })

  return { table, status, detail, retry: () => ask(point.value) }
}
