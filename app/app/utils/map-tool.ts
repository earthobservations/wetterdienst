import type { Station } from '#shared/types/api'

/**
 * The map tool (GH-3650): what the map shows, how far a place is from a station, and where each kind of station is
 * opened. Taken from the design of #3580 and fitted to this app: two layers, the forecast points and the DWD stations
 * that measure.
 */

/** What the map shows: the forecast's points (DWD MOSMIX), or the stations that measure (DWD observations) */
export type MapLayer = 'forecast' | 'measured'

export const MAP_LAYERS: MapLayer[] = ['forecast', 'measured']

/** A station that has a position, which is all a map can show and a distance be taken to */
export type PlacedStation = Station & { latitude: number, longitude: number }

/** A point of the earth */
export interface Point {
  latitude: number
  longitude: number
}

/** The measuring stations the map lists: one resolution of DWD's observations, and a dataset of it */
export interface MeasuredSource {
  resolution: string
  dataset: string
}

/** The provider and network of the measuring stations: this change has DWD's, which every link below is made for */
export const MEASURED_NETWORK = { provider: 'dwd', network: 'observation' } as const

/** The source the map opens with: DWD's daily climate summary, the most complete record the library has */
export const DEFAULT_MEASURED: MeasuredSource = { resolution: 'daily', dataset: 'climate_summary' }

/** DWD MOSMIX, whose stations are the forecast's points: the list the forecast page asks for */
export const FORECAST_STATIONS_QUERY = { provider: 'dwd', network: 'mosmix', parameters: 'hourly/large', all: 'true' } as const

/** The kind of stripes the panel's stripes are of: the temperature, as the stripes page opens with */
export const STRIPES_KIND = 'temperature'

/**
 * How far the nearest station of a kind may be for the panel to offer it, in kilometres: beyond it the station is
 * another place's, and the panel says there is none near.
 */
export const REACH_KM = 100

/** The point the map opens on, and how far in: Germany, where DWD's stations are */
export const HOME_VIEW = { latitude: 51.2, longitude: 10.4, zoom: 6 }

/** A place picked on the map that is no more than this far from the station nearest to it is taken for the station itself */
export const SAME_PLACE_KM = 0.5

const EARTH_RADIUS_KM = 6371.0088

/**
 * The distance of two points along the earth's surface, in kilometres (haversine).
 *
 * @example
 * distanceKm({ latitude: 52.52, longitude: 13.40 }, { latitude: 48.14, longitude: 11.58 }) // about 504
 */
export function distanceKm(a: Point, b: Point): number {
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
 * The `count` stations nearest to a point, nearest first, each with its distance in kilometres.
 *
 * The list is gone through once, keeping the nearest so far: no sort of the whole list.
 *
 * @example
 * nearestStations(stations, { latitude: 54.3, longitude: 10.1 }, 1) // [{ station, distance: 3.2 }]
 */
export function nearestStations<S extends PlacedStation>(stations: S[], point: Point, count = 1): Array<{ station: S, distance: number }> {
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
 * The nearest station of a list to a point, if it is within `REACH_KM`.
 *
 * @returns The station and its distance, or null where the list is empty or the nearest station is farther than that
 */
export function nearestWithin(stations: PlacedStation[], point: Point, reach = REACH_KM): { station: PlacedStation, distance: number } | null {
  const [nearest] = nearestStations(stations, point, 1)
  return nearest && nearest.distance <= reach ? nearest : null
}

/**
 * The stations whose name or id holds every word of a query, case and accents aside, the ones whose name starts
 * with it first. At most `limit`.
 */
export function searchStations<S extends Station>(stations: S[], query: string, limit = 20): S[] {
  const fold = (text: string) => text.normalize('NFD').replace(/\p{M}/gu, '').toLowerCase()
  const words = fold(query).split(/\s+/).filter(Boolean)
  if (!words.length)
    return []
  const starts: S[] = []
  const contains: S[] = []
  for (const station of stations) {
    const name = fold(station.name ?? '')
    const id = fold(station.station_id)
    if (!words.every(word => `${name} ${id}`.includes(word)))
      continue
    if (name.startsWith(words[0]!) || id === words[0])
      starts.push(station)
    else
      contains.push(station)
  }
  return [...starts, ...contains].slice(0, limit)
}

/**
 * A distance as a reader says it, in the number format of the language: metres under one kilometre (rounded to ten),
 * one decimal under ten kilometres, whole kilometres beyond.
 *
 * @example
 * formatDistance(0.42, 'en') // '420 m'
 * formatDistance(3.24, 'de') // '3,2 km'
 */
export function formatDistance(km: number, locale: string): string {
  const unit = (value: number, name: 'meter' | 'kilometer', digits: number) =>
    new Intl.NumberFormat(locale, { style: 'unit', unit: name, unitDisplay: 'short', maximumFractionDigits: digits, minimumFractionDigits: digits }).format(value)
  if (km < 1)
    return unit(Math.round(km * 100) * 10, 'meter', 0)
  return unit(km, 'kilometer', km < 10 ? 1 : 0)
}

/**
 * A position as signed degrees with a point, as it is copied into a map or a query: `52.5200, 13.4000`. Not in the
 * number format of the language (i18n/TERMS.md), and no letters for the hemispheres, which the languages write differently.
 */
export function formatPosition(point: Point): string {
  return `${point.latitude.toFixed(4)}, ${point.longitude.toFixed(4)}`
}

/** Where the forecast of a MOSMIX station is opened */
export function forecastLink(stationId: string): string {
  return `/meteogram?station=${encodeURIComponent(stationId)}`
}

/** Where the climate stripes of a station that has them are opened */
export function stripesLink(stationId: string): string {
  return `/stripes?${new URLSearchParams({ kind: STRIPES_KIND, station: stationId })}`
}

/** Where the measurements of a station are opened: the explorer, on its source and with the station chosen */
export function measurementsLink(source: MeasuredSource, stationId: string): string {
  return `/explorer?${new URLSearchParams({ ...MEASURED_NETWORK, ...source, mode: 'station', stations: stationId })}`
}

/** Where the history of a station is opened: the station history, on the source and with the station chosen */
export function historyLink(source: MeasuredSource, stationId: string): string {
  return `/history?${new URLSearchParams({ ...MEASURED_NETWORK, ...source, stations: stationId })}`
}

/**
 * What the map's address says it shows, as the page writes and reads it: the layer, the source of the measurements, the
 * station and the place picked when it is not the station itself. What is the default is left out, so that a
 * link to the plain map is `/map`.
 */
export interface MapState {
  layer: MapLayer
  source: MeasuredSource
  stationId: string | null
  place: Point | null
}

/** The query of a state, with what is the default left out */
export function stateToQuery(state: MapState): Record<string, string> {
  const query: Record<string, string> = {}
  if (state.layer !== 'forecast')
    query.layer = state.layer
  if (state.source.resolution !== DEFAULT_MEASURED.resolution || state.source.dataset !== DEFAULT_MEASURED.dataset) {
    query.resolution = state.source.resolution
    query.dataset = state.source.dataset
  }
  if (state.stationId)
    query.station = state.stationId
  if (state.stationId && state.place) {
    query.lat = state.place.latitude.toFixed(4)
    query.lon = state.place.longitude.toFixed(4)
  }
  return query
}

/** The state an address names; what it does not name, or names wrongly, is the default */
export function stateFromQuery(query: Record<string, unknown>): MapState {
  const text = (value: unknown) => (Array.isArray(value) ? value[0] : value)?.toString() || ''
  const layer = MAP_LAYERS.find(candidate => candidate === text(query.layer)) ?? 'forecast'
  const latitude = text(query.lat) === '' ? Number.NaN : Number(text(query.lat))
  const longitude = text(query.lon) === '' ? Number.NaN : Number(text(query.lon))
  const stationId = text(query.station) || null
  return {
    layer,
    source: {
      resolution: text(query.resolution) || DEFAULT_MEASURED.resolution,
      dataset: text(query.dataset) || DEFAULT_MEASURED.dataset,
    },
    stationId,
    place: stationId && Math.abs(latitude) <= 90 && Math.abs(longitude) <= 180 ? { latitude, longitude } : null,
  }
}
