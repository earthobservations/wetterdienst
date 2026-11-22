import type { Bar, Reading } from './answers'
import { DateTime } from 'luxon'
import { toCanonical } from './units'

// The day question's measures besides the wind (GH-3764, step 2b): how sunny, how wet, how hot or cold, and how snowy a day was at the
// place's station, from DWD's daily readings. Pure like `answers.ts`: the page fetches, these read, and where a day has no reading
// they say so (null) rather than make one up. What a number is judged by (a millimetre, a degree, a share of the day) is judged
// in the canonical unit of its quantity, so a verdict is the same in every unit the reader picks.
//
// Every band is one constant that the rule of the chip's explanation (`ask/chips/day.ts`) takes its figure from, and that rule cites
// its source or is marked as wetterdienst's own.

/** The measures the day question can be asked about, in the order of the control and of the link (`&measure=sun`) */
export const MEASURES = ['wind', 'sun', 'rain', 'temperature', 'snow'] as const
export type Measure = (typeof MEASURES)[number]

export function isMeasure(value: unknown): value is Measure {
  return typeof value === 'string' && (MEASURES as readonly string[]).includes(value)
}

/** The parameters of DWD's daily data (`daily/climate_summary`, and `daily/precipitation_more` for the fresh snow) the measures are read from */
export const DAY_PARAMETERS = {
  sun: 'sunshine_duration',
  rain: 'precipitation_amount',
  tmax: 'temperature_air_max_2m',
  tmin: 'temperature_air_min_2m',
  snow: 'snow_depth',
  newSnow: 'snow_depth_new',
} as const

/** The readings of each day, by the day `YYYY-MM-DD` and the parameter: a missing value is null, an absent one is absent */
type ByDay = Map<string, Map<string, number | null>>

function readingsByDay(readings: Reading[], parameters: readonly string[]): ByDay {
  const byDay: ByDay = new Map()
  for (const reading of readings) {
    if (!parameters.includes(reading.parameter))
      continue
    const date = reading.timestamp.slice(0, 10)
    const entry = byDay.get(date) ?? new Map()
    entry.set(reading.parameter, reading.value)
    byDay.set(date, entry)
  }
  return byDay
}

/** One bar per day around the one asked about, in order, the day marked: the chart of an answer */
function barsOf(byDay: ByDay, parameter: string, day: string, convert: (value: number) => number = value => value): Bar[] {
  return [...byDay.keys()].sort().map((date) => {
    const value = byDay.get(date)!.get(parameter) ?? null
    return { key: date, label: date, value: value === null ? null : convert(value), highlight: date === day }
  })
}

// ---------------------------------------------------------------------------------------------------------------
// Sun: the share of the possible sunshine
// ---------------------------------------------------------------------------------------------------------------

/**
 * Where a day is "dull", "mixed" and "sunny": by the share of the possible sunshine, below 30 %, from 30 % and from 70 %. The edges are
 * the ranges WMO-No. 8 (Volume I, §8.1.3) gives of the relative daily sunshine duration SD/SD0 ("cloudy sky" below 0.3, "scattered
 * clouds" from 0.3, "fair weather" from 0.7); the three words are wetterdienst's own use of them (`ask/chips/day.ts`).
 */
export const SUN_SHARE_DULL_BELOW = 0.3
export const SUN_SHARE_SUNNY_FROM = 0.7

export type SunVerdict = 'dull' | 'mixed' | 'sunny'

export interface SunAnswer {
  verdict: SunVerdict
  day: string
  /** The sunshine of the day, in hours */
  hours: number
  /** The sunshine that was possible at the station's latitude on that day, in hours: the day from sunrise to sunset on a mathematical horizon */
  possible: number
  /** The share of it from 0 to 1 (not above 1: a recorder can read a little more than the astronomical day) */
  share: number
  /** The days around it, one bar each: the sunshine in hours */
  bars: Bar[]
}

/** The ratio of 1 h to a unit of time the backend can write the sunshine in */
const HOURS_PER = { h: 1, min: 1 / 60, s: 1 / 3600 } as const

/** A duration in `unit` as hours (an unknown symbol is taken to be hours, as the data is in them) */
function inHours(value: number, unit: string): number {
  return value * (HOURS_PER[unit as keyof typeof HOURS_PER] ?? 1)
}

/**
 * The Sun's declination on a day, in radians, by the approximate formulae of the Astronomical Almanac that WMO-No. 8 (Volume I,
 * Annex 7.F) gives for practical use: from the days since 1 January 2000, 12:00 UT, the mean longitude and anomaly of the Sun give its
 * ecliptic longitude `l`, and `sin(declination) = sin(obliquity) · sin(l)`. Taken at noon UT of the day.
 */
export function solarDeclination(day: string): number {
  const noon = DateTime.fromISO(day, { zone: 'utc' }).set({ hour: 12 })
  const n = noon.diff(DateTime.utc(2000, 1, 1, 12), 'days').days
  const rad = Math.PI / 180
  const meanLongitude = 280.460 + 0.9856474 * n
  const anomaly = (357.528 + 0.9856003 * n) * rad
  const longitude = (meanLongitude + 1.915 * Math.sin(anomaly) + 0.020 * Math.sin(2 * anomaly)) * rad
  const obliquity = (23.439 - 0.0000004 * n) * rad
  return Math.asin(Math.sin(obliquity) * Math.sin(longitude))
}

/**
 * The length of the day at a latitude, in hours: the time the Sun is above the horizon. The hour angle of sunrise follows from
 * `cos(t) = −tan(latitude) · tan(declination)` for a mathematical horizon (WMO-No. 8, Volume I, Annex 7.G), the day is `2t` and an
 * hour is 15 degrees of it. 24 hours where the Sun does not set, 0 where it does not rise. `horizon` is the Sun's elevation at
 * which the day is taken to start (default 0: the mathematical horizon, WMO's "extra-terrestrial possible" sunshine, SD0 of
 * §8.1.2); sunrise as it is announced is at −0.833° (refraction and the Sun's radius), which a test compares with printed tables.
 */
export function dayLengthHours(latitude: number, day: string, horizon = 0): number {
  const rad = Math.PI / 180
  const declination = solarDeclination(day)
  const cosine = (Math.sin(horizon * rad) - Math.sin(latitude * rad) * Math.sin(declination)) / (Math.cos(latitude * rad) * Math.cos(declination))
  if (cosine <= -1)
    return 24
  if (cosine >= 1)
    return 0
  return 2 * Math.acos(cosine) / rad / 15
}

/** The word of a share of the possible sunshine */
export function sunVerdictOf(share: number): SunVerdict {
  return share < SUN_SHARE_DULL_BELOW ? 'dull' : share < SUN_SHARE_SUNNY_FROM ? 'mixed' : 'sunny'
}

/** How sunny `day` was at a station at `latitude`: the sunshine of the day against the sunshine that was possible. Null without a reading, or on a day with no sunrise */
export function sunOnDay(readings: Reading[], day: string, latitude: number, unit = 'h'): SunAnswer | null {
  const byDay = readingsByDay(readings, [DAY_PARAMETERS.sun])
  const value = byDay.get(day)?.get(DAY_PARAMETERS.sun) ?? null
  const possible = dayLengthHours(latitude, day)
  if (value === null || possible <= 0)
    return null
  const hours = inHours(value, unit)
  const share = Math.min(1, hours / possible)
  return { verdict: sunVerdictOf(share), day, hours, possible, share, bars: barsOf(byDay, DAY_PARAMETERS.sun, day, each => inHours(each, unit)) }
}

// ---------------------------------------------------------------------------------------------------------------
// Rain: the bands of a day's precipitation
// ---------------------------------------------------------------------------------------------------------------

/**
 * The bands of a day's precipitation, in millimetres: dry below 0.1 mm (WMO-No. 8, §6.1.2: amounts below it are "trace amounts"),
 * light from there, wet from 1 mm (the count of days WMO-No. 1203 asks for, Table 1) and very wet from 10 mm (a threshold of the same
 * table; the name is wetterdienst's own).
 */
export const RAIN_DRY_BELOW_MM = 0.1
export const RAIN_WET_FROM_MM = 1
export const RAIN_VERY_WET_FROM_MM = 10

export type RainDayVerdict = 'dry' | 'light' | 'wet' | 'veryWet'

export interface RainDayAnswer {
  verdict: RainDayVerdict
  day: string
  /** The precipitation of the day, in `unit` */
  amount: number
  unit: string
  bars: Bar[]
}

export function rainVerdictOf(millimeters: number): RainDayVerdict {
  return millimeters < RAIN_DRY_BELOW_MM ? 'dry' : millimeters < RAIN_WET_FROM_MM ? 'light' : millimeters < RAIN_VERY_WET_FROM_MM ? 'wet' : 'veryWet'
}

/** How wet `day` was: its precipitation (the 24 hours from 06:00 UTC of the day) in a band. Null without a reading */
export function rainOnDay(readings: Reading[], day: string, unit = 'mm'): RainDayAnswer | null {
  const byDay = readingsByDay(readings, [DAY_PARAMETERS.rain])
  const amount = byDay.get(day)?.get(DAY_PARAMETERS.rain) ?? null
  if (amount === null)
    return null
  return { verdict: rainVerdictOf(toCanonical('precipitation', unit, amount)), day, amount, unit, bars: barsOf(byDay, DAY_PARAMETERS.rain, day) }
}

// ---------------------------------------------------------------------------------------------------------------
// Heat and cold: the climatological days
// ---------------------------------------------------------------------------------------------------------------

/**
 * The days that DWD names by their temperature, in °C: an ice day has a maximum below 0, a frost day a minimum below 0, a summer day a
 * maximum of 25 or more, a hot day of 30 or more and a tropical night a minimum of 20 or more (`ask/chips/day.ts` cites each).
 */
export const ICE_DAY_MAX_BELOW = 0
export const FROST_DAY_MIN_BELOW = 0
export const SUMMER_DAY_MAX_FROM = 25
export const HOT_DAY_MAX_FROM = 30
export const TROPICAL_NIGHT_MIN_FROM = 20

export type TemperatureClass = 'ice' | 'frost' | 'summer' | 'hot' | 'tropical'
/** The word of the day: the class that names it, or none of them */
export type TemperatureVerdict = TemperatureClass | 'ordinary'

/** The order the classes name a day by: the extremes of the heat first, then the cold, a tropical night where nothing else is. An ice day is a frost day too, and a hot day a summer day */
export const TEMPERATURE_VERDICT_ORDER: readonly TemperatureClass[] = ['hot', 'summer', 'tropical', 'ice', 'frost']

export interface TemperatureAnswer {
  verdict: TemperatureVerdict
  day: string
  /** The highest and the lowest air temperature of the day at 2 m, in `unit` */
  max: number
  min: number
  unit: string
  /** Every class the day is, in the order of `TEMPERATURE_VERDICT_ORDER` (an ice day is also a frost day) */
  classes: TemperatureClass[]
  /** The days around it, one bar each: the maximum, or the minimum where the day is a frost day */
  bars: Bar[]
  /** Which temperature the bars are */
  barsAre: 'max' | 'min'
}

/** The classes a day with this highest and lowest temperature (in °C) is */
export function temperatureClasses(max: number, min: number): TemperatureClass[] {
  const found: TemperatureClass[] = []
  for (const kind of TEMPERATURE_VERDICT_ORDER) {
    if (kind === 'hot'
      ? max >= HOT_DAY_MAX_FROM
      : kind === 'summer'
        ? max >= SUMMER_DAY_MAX_FROM
        : kind === 'tropical'
          ? min >= TROPICAL_NIGHT_MIN_FROM
          : kind === 'ice'
            ? max < ICE_DAY_MAX_BELOW
            : min < FROST_DAY_MIN_BELOW) {
      found.push(kind)
    }
  }
  return found
}

/** How hot or cold `day` was: its highest and lowest temperature against the days DWD names. Null where either is missing (no frost can be ruled out without the minimum) */
export function temperatureOnDay(readings: Reading[], day: string, unit = '°C'): TemperatureAnswer | null {
  const byDay = readingsByDay(readings, [DAY_PARAMETERS.tmax, DAY_PARAMETERS.tmin])
  const max = byDay.get(day)?.get(DAY_PARAMETERS.tmax) ?? null
  const min = byDay.get(day)?.get(DAY_PARAMETERS.tmin) ?? null
  if (max === null || min === null)
    return null
  const classes = temperatureClasses(toCanonical('temperature', unit, max), toCanonical('temperature', unit, min))
  // the cold that names the day is its minimum, except for an ice day, which its maximum names
  const barsAre = classes.includes('frost') && !classes.includes('ice') ? 'min' : 'max'
  return {
    verdict: classes[0] ?? 'ordinary',
    day,
    max,
    min,
    unit,
    classes,
    bars: barsOf(byDay, barsAre === 'min' ? DAY_PARAMETERS.tmin : DAY_PARAMETERS.tmax, day),
    barsAre,
  }
}

// ---------------------------------------------------------------------------------------------------------------
// Snow: the depth that lay, and the fresh snow
// ---------------------------------------------------------------------------------------------------------------

/** Snow lies where the depth is above 0 cm (the first of the depths WMO-No. 1203, Table 1, counts days by: above 0, 1, 10 and 50 cm) */
export const SNOW_LIES_ABOVE_CM = 0

export type SnowVerdict = 'none' | 'cover'

export interface SnowAnswer {
  verdict: SnowVerdict
  day: string
  /** The snow depth of the day (the 06 UTC reading), and the fresh snow where the station has it, in `unit` */
  depth: number
  fresh: number | null
  unit: string
  bars: Bar[]
}

/** How snowy `day` was: the snow depth that lay. Null without a depth reading; the fresh snow is added where the station has it */
export function snowOnDay(readings: Reading[], day: string, unit = 'cm'): SnowAnswer | null {
  const byDay = readingsByDay(readings, [DAY_PARAMETERS.snow, DAY_PARAMETERS.newSnow])
  const depth = byDay.get(day)?.get(DAY_PARAMETERS.snow) ?? null
  if (depth === null)
    return null
  const fresh = byDay.get(day)?.get(DAY_PARAMETERS.newSnow) ?? null
  const lies = toCanonical('length_short', unit, depth) > SNOW_LIES_ABOVE_CM
  return { verdict: lies ? 'cover' : 'none', day, depth, fresh, unit, bars: barsOf(byDay, DAY_PARAMETERS.snow, day) }
}

// ---------------------------------------------------------------------------------------------------------------
// Which measures a station has a reading of on a day
// ---------------------------------------------------------------------------------------------------------------

/** The parameters of each measure a day needs a reading of for an answer (the wind needs either of its two) */
const NEEDS: Record<Measure, { all?: readonly string[], any?: readonly string[] }> = {
  wind: { any: ['wind_gust_max', 'wind_speed_mean'] },
  sun: { all: [DAY_PARAMETERS.sun] },
  rain: { all: [DAY_PARAMETERS.rain] },
  temperature: { all: [DAY_PARAMETERS.tmax, DAY_PARAMETERS.tmin] },
  snow: { all: [DAY_PARAMETERS.snow] },
}

/** Whether the readings have what the measure needs on `day` */
export function hasMeasure(readings: Reading[], measure: Measure, day: string): boolean {
  const need = NEEDS[measure]
  const present = new Set(readings.filter(reading => reading.value !== null && reading.timestamp.slice(0, 10) === day).map(reading => reading.parameter))
  return (need.all ?? []).every(parameter => present.has(parameter)) && (!need.any || need.any.some(parameter => present.has(parameter)))
}

/** The measures that have a reading on `day`, in the order of `MEASURES` */
export function measuresWithData(readings: Reading[], day: string): Measure[] {
  return MEASURES.filter(measure => hasMeasure(readings, measure, day))
}
