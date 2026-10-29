import type { Place, SkyPhase, SkyWeather } from '~/utils/place'
import { DEFAULT_SKY_POINT, SKY_WEATHER_TTL_MS, SKY_WEATHERS, skyPhase } from '~/utils/place'

/** The key of the place in the browser's storage, named in the privacy policy (i18n/privacy) */
export const PLACE_STORAGE_KEY = 'wd_place'

/** A stored place, or null where what is stored is not one (another version, edited by hand) */
function parsePlace(raw: string | null): Place | null {
  if (!raw)
    return null
  try {
    const value = JSON.parse(raw)
    if (typeof value?.id !== 'string' || typeof value?.name !== 'string' || !Number.isFinite(value?.latitude) || !Number.isFinite(value?.longitude))
      return null
    const place: Place = { id: value.id, name: value.name, latitude: value.latitude, longitude: value.longitude }
    if (SKY_WEATHERS.includes(value.weather) && Number.isFinite(value.weatherAt)) {
      place.weather = value.weather
      place.weatherAt = value.weatherAt
    }
    return place
  }
  catch {
    return null
  }
}

function store(place: Place | null) {
  // storage can be refused (a private window, blocked site data): the place is then this visit's only
  try {
    if (place)
      localStorage.setItem(PLACE_STORAGE_KEY, JSON.stringify(place))
    else
      localStorage.removeItem(PLACE_STORAGE_KEY)
  }
  catch {}
}

/**
 * The place the visitor chose last (GH-3518), shared by the pages and kept in the browser, so that the home
 * page shows it again and the sky of every page is the sky over it. Nothing of it leaves the browser.
 */
export function usePlace() {
  const place = useState<Place | null>('wd-place', () => null)
  const loaded = useState('wd-place-loaded', () => false)

  if (import.meta.client && !loaded.value) {
    loaded.value = true
    try {
      place.value = parsePlace(localStorage.getItem(PLACE_STORAGE_KEY))
    }
    catch {}
  }

  function setPlace(next: Omit<Place, 'weather' | 'weatherAt'>) {
    const same = place.value?.id === next.id
    place.value = { ...next, ...(same && place.value?.weather ? { weather: place.value.weather, weatherAt: place.value.weatherAt } : {}) }
    store(place.value)
  }

  function forgetPlace() {
    place.value = null
    store(null)
  }

  /** The weather of the place's forecast for the hour, which the sky draws for a while */
  function rememberWeather(id: string, weather: SkyWeather) {
    if (!place.value || place.value.id !== id)
      return
    // the same weather told again within ten minutes changes nothing worth a write
    if (place.value.weather === weather && place.value.weatherAt && Date.now() - place.value.weatherAt < 10 * 60 * 1000)
      return
    place.value = { ...place.value, weather, weatherAt: Date.now() }
    store(place.value)
  }

  return { place: readonly(place), setPlace, forgetPlace, rememberWeather }
}

/**
 * The sky of the page (SkyBackdrop.vue): the light of the time of day at the place (or the middle of Germany
 * before one is chosen), reckoned again every ten minutes, and the place's weather while it is fresh.
 */
export function useSky() {
  const { place } = usePlace()
  const now = useNow({ interval: 10 * 60 * 1000 })

  const phase = computed<SkyPhase>(() => {
    const point = place.value ?? DEFAULT_SKY_POINT
    return skyPhase(point.latitude, point.longitude, now.value)
  })
  const weather = computed<SkyWeather>(() => {
    const p = place.value
    if (p?.weather && p.weatherAt && now.value.getTime() - p.weatherAt < SKY_WEATHER_TTL_MS)
      return p.weather
    return 'clear'
  })
  return { phase, weather }
}
