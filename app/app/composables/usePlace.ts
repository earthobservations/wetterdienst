import type { Station } from '#shared/types/api'
import { distanceKm } from '~/utils/map-tool'
import { PLACE_REACH_KM } from '~/utils/place-stations'

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
  /**
   * Where the place is a town or another place found by its name (GH-3791) and no station: `name`, `region`, `latitude` and `longitude` are the town's own,
   * and `id` is the station of the measurements nearest to it, which is told here with how far it is (it may be too far to be the place's, `townTooFar`).
   * The questions that read a station read that one, and the answers name it and say how far it is.
   */
  town?: { station: TownStation }
}

/** The measuring station nearest to a town, and how far it is from it */
export interface TownStation {
  id: string
  name: string
  latitude: number
  longitude: number
  distanceKm: number
}

/** Kiel-Holtenau: the station of the town the first question names */
export const DEFAULT_PLACE: Place = { id: '02564', name: 'Kiel-Holtenau', latitude: 54.3776, longitude: 10.1424, region: 'Schleswig-Holstein' }

/** The network whose stations are places: DWD's measurements, by their daily climate summary */
export const PLACE_NETWORK = { provider: 'dwd', network: 'observation', parameters: 'daily/climate_summary' } as const

export const PLACE_STORAGE_KEY = 'wd-place'

function stored(): Place | null {
  try {
    const raw = JSON.parse(localStorage.getItem(PLACE_STORAGE_KEY) ?? 'null')
    if (raw && typeof raw.id === 'string' && typeof raw.name === 'string' && Number.isFinite(raw.latitude) && Number.isFinite(raw.longitude)) {
      const station = raw.town?.station
      const town = station && typeof station.id === 'string' && typeof station.name === 'string' && Number.isFinite(station.latitude) && Number.isFinite(station.longitude) && Number.isFinite(station.distanceKm)
        ? { station: { id: station.id, name: station.name, latitude: station.latitude, longitude: station.longitude, distanceKm: station.distanceKm } }
        : undefined
      return { id: raw.id, name: raw.name, latitude: raw.latitude, longitude: raw.longitude, region: typeof raw.region === 'string' ? raw.region : null, ...(raw.fromPosition === true ? { fromPosition: true } : {}), ...(town ? { town } : {}) }
    }
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

/**
 * A town found by its name (GH-3791) as the place of the questions, with the measuring station nearest to it: null where there is none to name (the list
 * of stations is empty). The station is used where it is within reach; beyond it the questions say there is no station near, and name this one.
 */
export function townPlace(town: { name: string, region: string | null, latitude: number, longitude: number }, nearest: Station | undefined): Place | null {
  if (!nearest || nearest.latitude == null || nearest.longitude == null)
    return null
  const distance = distanceKm(town, { latitude: nearest.latitude, longitude: nearest.longitude })
  return {
    id: nearest.station_id,
    name: town.name,
    region: town.region,
    latitude: town.latitude,
    longitude: town.longitude,
    town: { station: { id: nearest.station_id, name: nearest.name ?? nearest.station_id, latitude: nearest.latitude, longitude: nearest.longitude, distanceKm: distance } },
  }
}

/** Whether the station nearest to a town is too far to be the town's (`PLACE_REACH_KM`): a place that is a station is never */
export function townTooFar(place: Pick<Place, 'town'>): boolean {
  return !!place.town && place.town.station.distanceKm > PLACE_REACH_KM
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
