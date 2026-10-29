import type { Station } from '#shared/types/api'

/**
 * The map of the home page (GH-3518): what it shows, how far a place is from a station, and where a
 * station of each kind is opened.
 */

/** What the map shows: the forecast points, the stations that measure, or the stations with climate stripes */
export type AtlasLayer = 'forecast' | 'measured' | 'stripes'

export const ATLAS_LAYERS: AtlasLayer[] = ['forecast', 'measured', 'stripes']

/** A station that has a position, which is all the map can show */
export type PlacedStation = Station & { latitude: number, longitude: number }

/** The source of the measuring stations: a provider's network, one resolution of it and a dataset */
export interface MeasuredSource {
  provider: string
  network: string
  resolution: string
  dataset: string
}

/** The source the map opens with: DWD's daily climate summary, the most complete record the library has */
export const DEFAULT_MEASURED: MeasuredSource = { provider: 'dwd', network: 'observation', resolution: 'daily', dataset: 'climate_summary' }

/** DWD MOSMIX, whose stations are the forecast's points: the same the forecast page asks for */
export const FORECAST_STATIONS_QUERY = { provider: 'dwd', network: 'mosmix', parameters: 'hourly/large', all: 'true' }

/** The kind of stripes the map's stripes stations are listed for: the temperature, as the stripes page opens with */
export const STRIPES_KIND = 'temperature'

const EARTH_RADIUS_KM = 6371.0088

/**
 * The distance of two points along the earth's surface, in kilometres (haversine).
 *
 * @example
 * distanceKm({ latitude: 52.52, longitude: 13.40 }, { latitude: 48.14, longitude: 11.58 }) // about 504
 */
export function distanceKm(a: { latitude: number, longitude: number }, b: { latitude: number, longitude: number }): number {
  const rad = Math.PI / 180
  const dLat = (b.latitude - a.latitude) * rad
  const dLon = (b.longitude - a.longitude) * rad
  const h = Math.sin(dLat / 2) ** 2 + Math.cos(a.latitude * rad) * Math.cos(b.latitude * rad) * Math.sin(dLon / 2) ** 2
  return 2 * EARTH_RADIUS_KM * Math.asin(Math.min(1, Math.sqrt(h)))
}

/** The stations that have a position, the only ones a map can show or a distance be taken to */
export function placed(stations: Station[]): PlacedStation[] {
  return stations.filter((station): station is PlacedStation => station.latitude != null && station.longitude != null)
}

/**
 * The `count` stations nearest to a point, nearest first, each with its distance.
 *
 * A list of a hundred thousand stations (NOAA GHCN) is gone through once, keeping the nearest so far:
 * no sort of the whole list.
 */
export function nearestStations<S extends PlacedStation>(stations: S[], point: { latitude: number, longitude: number }, count = 1): Array<{ station: S, distance: number }> {
  const best: Array<{ station: S, distance: number }> = []
  for (const station of stations) {
    const distance = distanceKm(point, station)
    if (best.length < count || distance < best[best.length - 1]!.distance) {
      const at = best.findIndex(entry => entry.distance > distance)
      best.splice(at === -1 ? best.length : at, 0, { station, distance })
      if (best.length > count)
        best.pop()
    }
  }
  return best
}

/**
 * The stations whose name or id holds every word of a query, case and accents aside, the ones whose name
 * starts with it first. At most `limit`.
 */
export function searchStations<S extends Station>(stations: S[], query: string, limit = 20): S[] {
  const fold = (text: string) => text.normalize('NFD').replace(/\p{Diacritic}/gu, '').toLowerCase()
  const words = fold(query).split(/\s+/).filter(Boolean)
  if (!words.length)
    return []
  const starts: S[] = []
  const contains: S[] = []
  for (const station of stations) {
    const name = fold(station.name ?? '')
    const haystack = `${name} ${fold(station.station_id)}`
    if (!words.every(word => haystack.includes(word)))
      continue
    if (name.startsWith(words[0]!) || fold(station.station_id) === words[0])
      starts.push(station)
    else
      contains.push(station)
    if (starts.length >= limit)
      break
  }
  return [...starts, ...contains].slice(0, limit)
}

/**
 * A distance as a reader says it: metres under one kilometre, one decimal under ten, whole kilometres
 * beyond, in the number format of the language.
 */
export function formatDistance(km: number, locale: string): string {
  if (km < 1)
    return `${new Intl.NumberFormat(locale, { maximumFractionDigits: 0 }).format(Math.round(km * 1000 / 10) * 10)} m`
  const digits = km < 10 ? 1 : 0
  return `${new Intl.NumberFormat(locale, { maximumFractionDigits: digits, minimumFractionDigits: digits }).format(km)} km`
}

/** A position as degrees with a hemisphere, as a reader writes it: 52.52° N, 13.40° E */
export function formatPosition(latitude: number, longitude: number, locale: string): string {
  const format = new Intl.NumberFormat(locale, { maximumFractionDigits: 2, minimumFractionDigits: 2 })
  return `${format.format(Math.abs(latitude))}° ${latitude >= 0 ? 'N' : 'S'}, ${format.format(Math.abs(longitude))}° ${longitude >= 0 ? 'E' : 'W'}`
}

/** Where the forecast of a MOSMIX station is opened */
export function forecastLink(stationId: string): string {
  return `/meteogram?station=${encodeURIComponent(stationId)}`
}

/** Where the climate stripes of a stripes station are opened */
export function stripesLink(stationId: string): string {
  return `/stripes?kind=${STRIPES_KIND}&station=${encodeURIComponent(stationId)}`
}

/** Where the measurements of a station are opened: the explorer, on its source and with the station chosen */
export function measurementsLink(source: MeasuredSource, stationId: string): string {
  const query = new URLSearchParams({ ...source, mode: 'station', stations: stationId })
  return `/explorer?${query}`
}

/** Where the history of a station is opened, which only DWD's observation network has */
export function historyLink(source: MeasuredSource, stationId: string): string | null {
  if (source.provider !== 'dwd' || source.network !== 'observation')
    return null
  const query = new URLSearchParams({ resolution: source.resolution, dataset: source.dataset, stations: stationId })
  return `/history?${query}`
}
