import type { Station } from '#shared/types/api'

/**
 * The place the home page's questions are about: a DWD weather station, as `GET /api/stations` lists it for the
 * daily climate summary. A station rather than a town: the answers are its readings, and a town has none. The
 * forecast question takes the MOSMIX station nearest to it.
 *
 * Kept for the visitor in local storage, a convenience: where it cannot be read (a private window, blocked storage),
 * the place is Kiel, which the questions name, and a link that names a place (`/?place=02564`) takes that one.
 */
export interface Place {
  id: string
  name: string
  latitude: number
  longitude: number
  region: string | null
}

/** Kiel-Holtenau: the station of the town the first question names */
export const DEFAULT_PLACE: Place = { id: '02564', name: 'Kiel-Holtenau', latitude: 54.3776, longitude: 10.1424, region: 'Schleswig-Holstein' }

/** The network whose stations are places: DWD's measurements, by their daily climate summary */
export const PLACE_NETWORK = { provider: 'dwd', network: 'observation', parameters: 'daily/climate_summary' } as const

const STORAGE_KEY = 'wd-place'

function stored(): Place | null {
  try {
    const raw = JSON.parse(localStorage.getItem(STORAGE_KEY) ?? 'null')
    if (raw && typeof raw.id === 'string' && typeof raw.name === 'string' && Number.isFinite(raw.latitude) && Number.isFinite(raw.longitude))
      return { id: raw.id, name: raw.name, latitude: raw.latitude, longitude: raw.longitude, region: typeof raw.region === 'string' ? raw.region : null }
  }
  catch {}
  return null
}

/** A station as a place, or null where it has no name or no position to ask about */
export function placeOf(station: Station): Place | null {
  if (!station.name || station.latitude === null || station.longitude === null)
    return null
  return { id: station.station_id, name: station.name, latitude: station.latitude, longitude: station.longitude, region: station.region }
}

export function usePlace() {
  const place = useState<Place>('place', () => stored() ?? DEFAULT_PLACE)

  function setPlace(next: Place) {
    place.value = next
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(next))
    }
    catch {}
  }

  return { place, setPlace }
}
