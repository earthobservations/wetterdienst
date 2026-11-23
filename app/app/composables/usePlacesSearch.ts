import type { MaybeRefOrGetter, Ref } from 'vue'
import type { PlaceMatch, PlacesAnswer } from '#shared/utils/places'
import { isPlaceQuery, photonLang } from '#shared/utils/places'

/** How long the search of places waits after the last key: longer than the stations', since every text asked for is a request to a service of a third party */
export const PLACES_DEBOUNCE_MS = 400

/**
 * The places OpenStreetMap has for a text (GH-3790, GH-3791), as the app's own server finds them (`GET /_search/places?q=&lang=`,
 * `server/utils/placesSearch.ts`, which asks Photon): the one way every field that finds places asks (the header's search, the Forecast's
 * station search, the place of "Ask the weather", the Explorer's point), so that they all follow the same rules. The text is asked for from
 * three letters on and 400 ms after the last key, never when it looks like a position (`isPlaceQuery`), and not at all where the operator
 * has switched the search of places off (the server says so once, `NUXT_PLACES_SEARCH=off`, and the visit asks no more). The reader's
 * browser never reaches the service: the server does, without the reader's address.
 *
 * A key that changes the text gives up what is in flight for the text before it. A failure leaves `places` empty and `failed` set, until
 * the next text asks again; `skip` is a text the caller knows is no place (a position it handles itself).
 */
export function usePlacesSearch(query: Ref<string>, options: { enabled?: MaybeRefOrGetter<boolean>, skip?: (text: string) => boolean } = {}) {
  const { locale } = useI18n()
  const places = shallowRef<PlaceMatch[]>([])
  const failed = ref(false)
  const pending = ref(false)
  /** Where the operator has switched the search of places off, the server says so once and the visit asks no more */
  const off = useState('places-search-off', () => false)
  let ticket = 0
  let request: AbortController | null = null
  let closed = false

  const enabled = () => options.enabled === undefined || toValue(options.enabled)

  function reset() {
    ticket++
    request?.abort()
    places.value = []
    failed.value = false
    pending.value = false
  }

  onBeforeUnmount(() => {
    closed = true
    request?.abort()
  })
  // a key that changes what is asked gives up what is in flight for the text before it: the answer is no longer wanted
  watch(query, () => request?.abort())

  watchDebounced(query, async (value) => {
    const mine = ++ticket
    request?.abort()
    const text = value.trim()
    // a text that is a position or has no letter is no name of a place, and is not sent to anybody
    if (closed || !enabled() || off.value || !isPlaceQuery(text) || options.skip?.(text)) {
      places.value = []
      failed.value = false
      pending.value = false
      return
    }
    const controller = request = new AbortController()
    pending.value = true
    try {
      const answer = await $fetch<PlacesAnswer>('/_search/places', { query: { q: text, lang: photonLang(locale.value) }, signal: controller.signal, retry: 0, ...API_ANSWER })
      if (mine !== ticket || controller.signal.aborted)
        return
      if (answer.state === 'off')
        off.value = true
      places.value = answer.state === 'off' ? [] : answer.places
      failed.value = false
    }
    catch {
      // a failure leaves the rest of the search as it is, and is said in the live region; the next text asks again
      if (mine === ticket && !controller.signal.aborted) {
        places.value = []
        failed.value = true
      }
    }
    finally {
      if (mine === ticket)
        pending.value = false
    }
  }, { debounce: PLACES_DEBOUNCE_MS })

  return { places, failed, pending, off, reset }
}
