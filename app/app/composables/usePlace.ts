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
  /** The station nearest to the reader's own position (GH-3651): kept in the browser only with "remember", and forgotten with the position */
  fromPosition?: boolean
}

/** Kiel-Holtenau: the station of the town the first question names */
export const DEFAULT_PLACE: Place = { id: '02564', name: 'Kiel-Holtenau', latitude: 54.3776, longitude: 10.1424, region: 'Schleswig-Holstein' }

/** The network whose stations are places: DWD's measurements, by their daily climate summary */
export const PLACE_NETWORK = { provider: 'dwd', network: 'observation', parameters: 'daily/climate_summary' } as const

export const PLACE_STORAGE_KEY = 'wd-place'

function stored(): Place | null {
  try {
    const raw = JSON.parse(localStorage.getItem(PLACE_STORAGE_KEY) ?? 'null')
    if (raw && typeof raw.id === 'string' && typeof raw.name === 'string' && Number.isFinite(raw.latitude) && Number.isFinite(raw.longitude))
      return { id: raw.id, name: raw.name, latitude: raw.latitude, longitude: raw.longitude, region: typeof raw.region === 'string' ? raw.region : null, ...(raw.fromPosition === true ? { fromPosition: true } : {}) }
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

  /**
   * Makes `next` the place. It is kept in the browser unless `keep` is false: the station nearest to the reader's own
   * position (GH-3651) is a place for this visit only, as the position is, unless the reader ticked "remember".
   */
  function setPlace(next: Place, keep = true) {
    place.value = next
    if (!keep)
      return
    try {
      localStorage.setItem(PLACE_STORAGE_KEY, JSON.stringify(next))
    }
    catch {}
  }

  /**
   * The entry in the browser goes where it is the one that came from the position (GH-4014), whenever the position's own
   * entry is removed: a station must not outlive the position it was made from. The place of the page is left as it is.
   */
  function forgetStoredPositionPlace() {
    try {
      if (stored()?.fromPosition)
        localStorage.removeItem(PLACE_STORAGE_KEY)
    }
    catch {}
  }

  /**
   * What the reader's position made of the place is taken back (GH-3651): the entry in the browser goes where it is the
   * one that came from the position (the reader's own choice of a place is theirs), and the place of the page is the
   * one the browser still keeps, or Kiel, as the position it was derived from is forgotten.
   */
  function dropPositionPlace() {
    forgetStoredPositionPlace()
    if (place.value.fromPosition)
      place.value = stored() ?? DEFAULT_PLACE
  }

  /**
   * Another tab changed what the browser keeps (GH-4014): a place that the position made, and that the browser no longer
   * keeps as such (forgotten, replaced by another place, or by the place a newer position made), gives way to the one it
   * keeps, or to Kiel.
   */
  function followStoredPlace() {
    if (!place.value.fromPosition)
      return
    const kept = stored()
    if (!kept?.fromPosition || kept.id !== place.value.id)
      place.value = kept ?? DEFAULT_PLACE
  }

  return { place, setPlace, dropPositionPlace, forgetStoredPositionPlace, followStoredPlace }
}
