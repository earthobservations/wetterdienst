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

/** The radius of a station's dot in pixels, by zoom: points at the scale of a continent, discs at the scale of a town */
export function dotRadius(zoom: number): number {
  return zoom < 5 ? 1.75 : zoom < 7 ? 2.75 : zoom < 9 ? 3.75 : 5
}

/** How far outside its drawn edge a click still is on a dot, in pixels: the pointer's own width */
export const DOT_SLOP_PX = 2

/** How far a finger's tap reaches, in pixels, which a dot cannot be as small as: a tap in the ring beside a dot prefers a station that reports */
export const TAP_RADIUS_PX = 12

/** The radius and the edge of the disc drawn for the station picked, in pixels (the edge is drawn half outside the radius) */
export const SELECTED_RADIUS_PX = 9
export const SELECTED_EDGE_PX = 3

/**
 * What a click at a zoom reaches, in pixels from it: a dot under it (its drawn radius and a little more, so that a click
 * on empty map at the opening zoom, where a circle of 12 px radius is about 37 km across and took 89 % of the clicks
 * for one on a dot, is not one), and, for a finger (a coarse pointer), the wider ring a tap has, which is no hit on a
 * dot but the reach in which the station for the tap is chosen with the reporting ones first.
 */
export function clickReach(zoom: number, coarse: boolean): { dot: number, tap: number, disc: number } {
  const dot = dotRadius(zoom) + DOT_SLOP_PX
  // the yellow disc of the station picked is larger than a dot, and a click on it is on that station
  return { dot, tap: coarse ? Math.max(TAP_RADIUS_PX, dot) : 0, disc: SELECTED_RADIUS_PX + SELECTED_EDGE_PX / 2 + DOT_SLOP_PX }
}

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

const DAY_MS = 86_400_000

/**
 * How far behind the newest end of its list a station may be and still be reporting, in days. The REST API gives
 * every station an `end_timestamp`, a running one too: the day (or month, or year) of its last value. How far behind
 * today that is depends on the dataset, not on the resolution: the daily climate summary is a day or two behind, the
 * solar radiation 38 days, the snow water equivalent 215 days (DWD's files of two of its stations have continuous
 * daily rows through the summer of 2025 and stop in April 2026, which looks like a publication lag; why is not
 * known), the annual datasets 311 (the end of last year), and the stations of one list are up to two months apart
 * (the daily precipitation, the monthly lists). So a station is compared with the newest end of the list it is in,
 * which is the clock of that dataset, and the tolerance is generous: a station that stopped within 90 days of it still
 * reads as reporting (a little harm), where one that is running and a publication behind must never read as closed
 * (the harm of the fixed tolerance by resolution it replaces).
 *
 * Measured on the 62 observation lists of 2026-11-07 (the PR's table): of the 61 that are running, 90 days takes in the
 * stations that are running in each, but the 498 of the snow water equivalent, where one is 92 days behind and reads
 * as closed; beyond 90 days a list has between 1 and 271 stations that ended within the year, which read as
 * closed, and may be running late or have stopped (that cannot be told from the list).
 *
 * The clock is the newest end of the list, one station's: a single end that is far ahead of the others (but not
 * later than today) moves it, and takes a list's stations out of the tolerance (a simulation on the snow water
 * equivalent: one station moved 30 days ahead takes it from 497 stations reporting to 381). The lists are
 * not like that today. A later end than the newest ones, such as the 10th newest, as the clock would close
 * the one running station of `daily/weather_phenomena`, so the rule stays as it is.
 */
export const REPORTING_WITHIN_DAYS = 90

/**
 * How far behind today the newest end of a list may be for the list to be running at all, in days. A list whose newest
 * end is older than this has stopped as a whole (the annual weather phenomena end in 2024), and every station of it
 * reads as closed; the lists that are only behind (the snow water equivalent, 215 days; the annual datasets, 311, and up
 * to 365 before the new year's files) are within it.
 */
export const LIST_RUNNING_WITHIN_DAYS = 450

/** Whether a station of a list is still reporting, as `reportingRule` decides it for the list */
export type ReportingRule = (station: Pick<Station, 'end_timestamp'>) => boolean

/**
 * The rule of whether a station is still reporting, for the list it is in: its end is within `REPORTING_WITHIN_DAYS`
 * of the newest end of the list (taken over the ends that are not later than `now`), and the list is running
 * (`LIST_RUNNING_WITHIN_DAYS`). A station with no end, or one that is no date, is not reporting: its status is not
 * known, and a station of a layer that has none (the forecast's points) is not asked.
 *
 * @example
 * const reporting = reportingRule(stations) // the stations of dwd/observation daily/solar
 * stations.filter(reporting) // the 41 of the 56 that are running, though the newest end is 38 days ago
 */
export function reportingRule(stations: Array<Pick<Station, 'end_timestamp'>>, now: number = Date.now()): ReportingRule {
  // an end that is later than today is no clock: it would take the stations that are running out of the tolerance
  let clock = Number.NEGATIVE_INFINITY
  for (const station of stations) {
    const end = station.end_timestamp ? Date.parse(station.end_timestamp) : Number.NaN
    if (end <= now && end > clock)
      clock = end
  }
  const running = Number.isFinite(clock) && now - clock <= LIST_RUNNING_WITHIN_DAYS * DAY_MS
  return (station) => {
    const end = station.end_timestamp ? Date.parse(station.end_timestamp) : Number.NaN
    return running && !Number.isNaN(end) && clock - end <= REPORTING_WITHIN_DAYS * DAY_MS
  }
}

/**
 * The station the tool picks for a point (a click on the map that is not on a dot, the centre of the map, the place a
 * layer is changed at, the station of another kind near a station): the nearest one within `reach` kilometres, a
 * reporting one before a closed one where `reporting` says which are, so that the nearest closed station is only
 * offered when no reporting one is in reach. A station that is picked directly (a click on its dot) is the station
 * itself, whatever it is.
 *
 * @returns The station and its distance, or null where none is within reach
 */
export function stationFor(stations: PlacedStation[], point: Point, reporting?: ReportingRule, reach = REACH_KM): { station: PlacedStation, distance: number } | null {
  if (reporting) {
    const running = nearestWithin(stations.filter(reporting), point, reach)
    if (running)
      return running
  }
  return nearestWithin(stations, point, reach)
}

/** The calendar year (UTC) of a timestamp, or null where there is none or it is no date (it would read "NaN") */
export function yearOf(timestamp?: string | null): number | null {
  const date = timestamp ? new Date(timestamp) : null
  return date && !Number.isNaN(date.getTime()) ? date.getUTCFullYear() : null
}

/** A station that is nearer to a place than the one picked for it, and has stopped reporting */
export interface CloserStation {
  station: PlacedStation
  /** From the place, in kilometres */
  distance: number
  /** The year its record ends in, null where its list gives it no end */
  endYear: number | null
}

/**
 * Why a farther station was picked (GH-3875): the nearest station of the list to a place, when the station picked is
 * one that reports and the nearest has stopped, since `stationFor` takes the nearest that reports before a nearer one
 * that has stopped. Null where the station picked is the nearest, or has itself stopped (no rule put it before a
 * nearer one), or the nearer one reports (it is not that rule that passed it over).
 *
 * @example
 * closerStoppedStation(stations, place, fuhlsbuettel, reporting) // { station: sanktPauli, distance: 1.9, endYear: 2000 }
 */
export function closerStoppedStation(stations: PlacedStation[], point: Point, picked: PlacedStation, reporting: ReportingRule): CloserStation | null {
  // only the station that the rule picks for the place has a reason to tell: one picked another way (a dot, the list, the
  // address) is the reader's choice, and nothing was passed over for it
  if (stationFor(stations, point, reporting)?.station.station_id !== picked.station_id || !reporting(picked))
    return null
  const [nearest] = nearestStations(stations, point, 1)
  if (!nearest || nearest.station.station_id === picked.station_id || nearest.distance >= distanceKm(point, picked) || reporting(nearest.station))
    return null
  return { station: nearest.station, distance: nearest.distance, endYear: yearOf(nearest.station.end_timestamp) }
}

/**
 * Where the place of a pick came from, which the panel says (GH-3875): a click on the map, the centre of the map (the
 * keyboard's click), the position of a station the reader chose (a search, the list, a dot, the forecast station a
 * layer was changed from), which is no click and is not told as one, or of no known origin (a place the address
 * brings: a link, a reload, the browser's Back).
 */
export type PlaceOrigin = { kind: 'point' | 'centre' | 'unknown' } | { kind: 'station', name: string }

/** The station a point is on, within `tolerance` kilometres of it, or null: the nearest, whatever its status */
export function stationAt(stations: PlacedStation[], point: Point, tolerance: number): PlacedStation | null {
  const [nearest] = nearestStations(stations, point, 1)
  return nearest && nearest.distance <= tolerance ? nearest.station : null
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
