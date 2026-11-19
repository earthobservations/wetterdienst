import type { Station } from '#shared/types/api'
import type { ListStatus } from '~/composables/useStationList'
import type { MapBox, PlacedStation } from '~/utils/map-tool'
import { BOX_MAX_AREA, BOX_PAD, boxArea, boxContains, padBox, placed } from '~/utils/map-tool'

/** How long the map rests before the stations of the box it has moved to are asked for, in milliseconds */
export const BOX_DEBOUNCE_MS = 350

export interface BoxStationsOptions {
  /** Asks for the stations of a box; the signal is aborted when the map has moved past the request */
  load: (box: MapBox, signal: AbortSignal) => Promise<Station[]>
  delay?: number
  maxArea?: number
  pad?: number
}

/**
 * The stations of a layer that is too large to be loaded whole (GHCN daily, 133,041 stations, GH-4078): the ones in the part of the
 * map in view, asked for as the map moves.
 *
 * `show(view)` is told the box in view after each move. Where the view is inside the box loaded, or inside one that is on its way,
 * nothing is asked. Where the map has moved past them, the request on its way is cancelled (its signal is aborted, and an answer
 * that comes after it is dropped), and the stations of the view, `pad` larger on each side, are asked for once the map has rested
 * for `delay`: a drag or a run of zooms is one request. The first request of a layer, with no stations to show yet, is not delayed.
 * Where the view is larger than `maxArea` nothing is asked for (`tooWide`: the page says to zoom in) and none is shown: the
 * stations of one part of the world are not the ones of a view that holds most of it.
 *
 * The stations shown stay while the next box is on its way, so that a move does not blank the map (`refreshing`), and are replaced
 * by it when it arrives. `pin` keeps one station in the list whatever box is loaded: the one picked, which a move of the map must
 * not drop.
 */
export function useBoxStations(options: BoxStationsOptions) {
  const delay = options.delay ?? BOX_DEBOUNCE_MS
  const maxArea = options.maxArea ?? BOX_MAX_AREA
  const pad = options.pad ?? BOX_PAD

  const items = shallowRef<PlacedStation[]>([])
  const pinned = shallowRef<PlacedStation | null>(null)
  const state = ref<ListStatus>('idle')
  const error = shallowRef<unknown>(null)
  const tooWide = ref(false)
  /** The box the stations in hand were asked for */
  const loaded = shallowRef<MapBox | null>(null)

  let view: MapBox | null = null
  /** The box of the request on its way, null where none is */
  let inFlight: MapBox | null = null
  let controller: AbortController | null = null
  let timer: ReturnType<typeof setTimeout> | undefined
  let generation = 0

  // the station pinned is the same object whatever box is loaded (the map is not moved to it again for a new copy of it), in its
  // place where the box holds it and at the end where it does not
  const stations = computed(() => {
    const pin = pinned.value
    if (!pin)
      return items.value
    const at = items.value.findIndex(station => station.station_id === pin.station_id)
    if (at === -1)
      return [...items.value, pin]
    const list = items.value.slice()
    list[at] = pin
    return list
  })
  const status = computed<ListStatus>(() => state.value === 'error' ? 'error' : loaded.value ? 'success' : state.value)
  /** The stations shown are those of an earlier box, and the box of the view is being asked for */
  const refreshing = computed(() => state.value === 'pending' && loaded.value !== null)

  /** Cancels the request on its way and the one waiting to be made: an answer that comes after it is dropped */
  function cancel() {
    generation++
    clearTimeout(timer)
    timer = undefined
    controller?.abort()
    controller = null
    inFlight = null
  }

  async function run() {
    timer = undefined
    if (!view)
      return
    const box = padBox(view, pad)
    const mine = ++generation
    const own = new AbortController()
    controller = own
    inFlight = box
    state.value = 'pending'
    error.value = null
    try {
      const list = await options.load(box, own.signal)
      if (mine !== generation)
        return
      items.value = placed(list)
      loaded.value = box
      inFlight = null
      controller = null
      state.value = 'success'
    }
    catch (failure) {
      if (mine !== generation)
        return
      inFlight = null
      controller = null
      error.value = failure
      state.value = 'error'
    }
  }

  function show(next: MapBox) {
    view = next
    if (boxArea(next) > maxArea) {
      cancel()
      tooWide.value = true
      items.value = []
      loaded.value = null
      state.value = 'idle'
      error.value = null
      return
    }
    tooWide.value = false
    // the map is back inside what is shown, or what is on its way holds it
    if (loaded.value && boxContains(loaded.value, next) && state.value !== 'error') {
      cancel()
      state.value = 'success'
      return
    }
    if (inFlight && boxContains(inFlight, next))
      return
    cancel()
    state.value = 'pending'
    error.value = null
    if (loaded.value)
      timer = setTimeout(run, delay)
    else
      void run()
  }

  /** Asks for the box of the view again, as Retry does after a failure */
  function retry() {
    if (!view)
      return
    cancel()
    void run()
  }

  /** The layer is left: nothing is asked for any more, and the request on its way is cancelled */
  function stop() {
    cancel()
    if (state.value === 'pending')
      state.value = 'idle'
    tooWide.value = false
  }

  function pin(station: PlacedStation | null) {
    pinned.value = station
  }

  onScopeDispose(cancel)

  return { stations, status, error, tooWide, refreshing, show, retry, stop, pin }
}
