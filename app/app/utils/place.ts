import type { WeatherKind } from './weather-kind'
import { getPosition } from 'suncalc'
import { METEOGRAM_SERIES } from './meteogram'
import { weatherCodeToKind } from './weather-kind'

/**
 * The place a visitor chose (GH-3518): a station of the DWD MOSMIX forecast, which covers Germany and
 * places worldwide. The home page and the forecast remember it in the browser (`wd_place`), and the
 * sky of the page takes its time of day and its weather.
 */
export interface Place {
  id: string
  name: string
  latitude: number
  longitude: number
  /** The weather of its forecast for the hour, when it was last shown, and when (ms since the epoch) */
  weather?: SkyWeather
  weatherAt?: number
}

/** A station as a place, or null where the station list gives it no position */
export function placeOfStation(station: { station_id: string, name: string | null, latitude: number | null, longitude: number | null }): Omit<Place, 'weather' | 'weatherAt'> | null {
  if (station.latitude === null || station.longitude === null || !Number.isFinite(station.latitude) || !Number.isFinite(station.longitude))
    return null
  return { id: station.station_id, name: station.name ?? station.station_id, latitude: station.latitude, longitude: station.longitude }
}

/** The light of the sky: the sun more than 6° up, between 6° up and 6° down (morning or evening), or below */
export type SkyPhase = 'day' | 'dawn' | 'dusk' | 'night'

/** The sky's weather, coarser than the forecast's: what the band can draw */
export type SkyWeather = 'clear' | 'partly' | 'cloudy' | 'rain' | 'snow' | 'storm' | 'fog'

export const SKY_WEATHERS: readonly SkyWeather[] = ['clear', 'partly', 'cloudy', 'rain', 'snow', 'storm', 'fog']

/** Where the sky's light is reckoned before a place is chosen: the middle of Germany, the forecast's home */
export const DEFAULT_SKY_POINT = { latitude: 51.16, longitude: 10.45 }

/** A weather a forecast told is the sky's for three hours; after that the sky is the time of day alone */
export const SKY_WEATHER_TTL_MS = 3 * 60 * 60 * 1000

/** The light of the sky at a point at a time, from the height and side of the sun */
export function skyPhase(latitude: number, longitude: number, at: Date): SkyPhase {
  // suncalc 2 gives both in degrees, the azimuth clockwise from north
  const { altitude, azimuth } = getPosition(at, latitude, longitude)
  if (altitude > 6)
    return 'day'
  if (altitude < -6)
    return 'night'
  // the sun is in the east in the morning
  return azimuth < 180 ? 'dawn' : 'dusk'
}

/** What the sky draws for a kind of weather, and from the cloud cover (0..1) where the kind is unknown */
export function skyWeather(kind: WeatherKind | null, cloudCover: number | null): SkyWeather {
  switch (kind) {
    case 'thunderstorm':
      return 'storm'
    case 'rain':
    case 'drizzle':
    case 'sleet':
      return 'rain'
    case 'snow':
    case 'blowingSnow':
      return 'snow'
    case 'fog':
    case 'dust':
      return 'fog'
    case 'cloudy':
    case 'wind':
      return 'cloudy'
    case 'partlyCloudy':
      return 'partly'
    case 'clear':
      return 'clear'
  }
  if (cloudCover === null)
    return 'clear'
  if (cloudCover < 0.3)
    return 'clear'
  return cloudCover < 0.75 ? 'partly' : 'cloudy'
}

/**
 * A MOSMIX station's name as a place is written: `BERLIN-TEMPELHOF` as `Berlin-Tempelhof`. Names that are
 * not all capitals are left as they are, and so are the words with no vowel (abbreviations).
 */
export function placeName(name: string): string {
  if (name !== name.toUpperCase())
    return name
  return name.toLowerCase().replace(/(^|[\s\-/(.])(\p{L})/gu, (_, before: string, letter: string) => before + letter.toUpperCase())
}

/** One row of the long answer of `/api/values` */
export interface ValueRow {
  parameter: string
  timestamp?: string
  date?: string
  value: number | null
}

export interface HourConditions {
  at: Date
  temperature: number | null
  kind: WeatherKind | null
  sky: SkyWeather
}

export interface CurrentConditions extends HourConditions {
  windSpeed: number | null
  /** The precipitation of the next six hours, in millimetres, null where the forecast has none */
  precipitationNext6h: number | null
  /** Every second hour of the next twelve, after this one */
  next: HourConditions[]
}

/** The series of the rows by the name `METEOGRAM_SERIES` gives them, each by its time */
function seriesOf(rows: ValueRow[]) {
  const byParameter = new Map<string, Map<number, number | null>>()
  for (const row of rows) {
    const stamp = row.timestamp ?? row.date
    if (!stamp)
      continue
    const time = Date.parse(stamp)
    if (Number.isNaN(time))
      continue
    let series = byParameter.get(row.parameter)
    if (!series) {
      series = new Map()
      byParameter.set(row.parameter, series)
    }
    series.set(time, row.value)
  }
  const pick = (names: readonly string[]) => names.map(name => byParameter.get(name)).find(Boolean) ?? new Map<number, number | null>()
  return {
    temperature: pick(METEOGRAM_SERIES.temperature),
    weather: pick(METEOGRAM_SERIES.weather),
    cloudCover: pick(METEOGRAM_SERIES.cloudCover),
    windSpeed: pick(METEOGRAM_SERIES.windSpeed),
    precipitation: pick(METEOGRAM_SERIES.precipitation),
  }
}

/**
 * The weather of a forecast for the hour that is under way at `now` and for the hours after it: the row of
 * the first hour that has not ended (a MOSMIX value is for the hour that ends at its time). Null where the
 * forecast has no hour that has not ended.
 */
export function currentConditions(rows: ValueRow[], now: Date): CurrentConditions | null {
  const series = seriesOf(rows)
  const times = [...new Set([...series.temperature.keys(), ...series.weather.keys()])].sort((a, b) => a - b)
  const index = times.findIndex(time => time >= now.getTime())
  if (index < 0)
    return null
  const value = (map: Map<number, number | null>, time: number) => {
    const v = map.get(time)
    return v === undefined || v === null || !Number.isFinite(v) ? null : v
  }
  const hour = (time: number): HourConditions => {
    const kind = weatherCodeToKind(value(series.weather, time))
    return { at: new Date(time), temperature: value(series.temperature, time), kind, sky: skyWeather(kind, value(series.cloudCover, time)) }
  }
  const first = times[index]!
  const ahead = times.slice(index, index + 6).map(time => value(series.precipitation, time))
  const known = ahead.filter((v): v is number => v !== null)
  return {
    ...hour(first),
    windSpeed: value(series.windSpeed, first),
    precipitationNext6h: known.length ? Math.round(known.reduce((sum, v) => sum + v, 0) * 10) / 10 : null,
    next: times.slice(index + 2, index + 13).filter((_, i) => i % 2 === 0).slice(0, 6).map(hour),
  }
}

/**
 * The colour of a temperature (°C) for the place card's edge, from the logo's blue through its teal and
 * yellow to its coral. Decoration beside the number, which says the temperature.
 */
export function temperatureColor(celsius: number | null): string {
  if (celsius === null)
    return 'var(--color-brand-500)'
  const stops: Array<[number, string]> = [[-10, 'var(--color-brand-700)'], [0, 'var(--color-brand-400)'], [10, 'var(--color-lagoon)'], [20, 'var(--color-sun)'], [30, 'var(--color-ember)']]
  if (celsius <= stops[0]![0])
    return stops[0]![1]
  for (let i = 1; i < stops.length; i++) {
    const [upper, colour] = stops[i]!
    const [lower, previous] = stops[i - 1]!
    if (celsius <= upper) {
      const share = Math.round((celsius - lower) / (upper - lower) * 100)
      return `color-mix(in oklab, ${colour} ${share}%, ${previous})`
    }
  }
  return stops.at(-1)![1]
}

/** The distance between two points on the earth, in kilometres */
export function distanceKm(a: { latitude: number, longitude: number }, b: { latitude: number, longitude: number }): number {
  const rad = Math.PI / 180
  const dLat = (b.latitude - a.latitude) * rad
  const dLon = (b.longitude - a.longitude) * rad
  const h = Math.sin(dLat / 2) ** 2 + Math.cos(a.latitude * rad) * Math.cos(b.latitude * rad) * Math.sin(dLon / 2) ** 2
  return 2 * 6371 * Math.asin(Math.min(1, Math.sqrt(h)))
}

/** The station of a list nearest to a point, with its distance; null for an empty list */
export function nearestStation<T extends { latitude: number, longitude: number }>(stations: T[], point: { latitude: number, longitude: number }): { station: T, km: number } | null {
  let best: { station: T, km: number } | null = null
  for (const station of stations) {
    const km = distanceKm(point, station)
    if (!best || km < best.km)
      best = { station, km }
  }
  return best
}
