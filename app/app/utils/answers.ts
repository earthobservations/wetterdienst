import type { Provider, ProviderNetworkCoverageResponse } from '#shared/types/api'
import { DateTime } from 'luxon'
import { METEOGRAM_SERIES } from './meteogram'
import { planPrecipitation, precipitationOver } from './meteogram-precipitation'
import { buildSeries } from './meteogram-series'
import { CANONICAL_UNITS, differenceIn, fromCanonical, toCanonical } from './units'

// The answers of the home page's questions (components/AnswerPanel.vue), worked out from the values the backend
// answers with. Pure: the page fetches, these read. Nothing here is a number of its own; where the data does not
// carry an answer, the function says so (null) rather than make one up.
//
// The numbers come in the units the app settings choose and are written in them (GH-3980): each function takes the unit
// the answer reports its readings in (`metadata.parameters[].unit`) and says it in the answer's `unit`. What a number is
// compared with (a millimetre of rain, half a degree, Beaufort 9) is judged in the canonical unit of its quantity, so
// that the verdict is the same in every unit.

/** A reading as `/api/values` answers it in the long shape: the parameter, the time and the value */
export interface Reading {
  parameter: string
  timestamp: string
  value: number | null
}

/** One bar of the chart that backs an answer */
export interface Bar {
  key: string
  /** What the bar stands for, written for a reader: an hour, a year, a day */
  label: string
  /**
   * Where the bar is on the axis it is labelled by, where that is not its place in the series: its year (a series
   * with gaps is labelled at round years, not at every n-th bar)
   */
  at?: number
  value: number | null
  /** The bar the question is about */
  highlight?: boolean
}

// ---------------------------------------------------------------------------------------------------------------
// Will it rain tomorrow? DWD MOSMIX, the station forecast nearest the place
// ---------------------------------------------------------------------------------------------------------------

/** MOSMIX's hourly precipitation (the hour before the timestamp) and the chance of more than 0.1 mm in that hour */
export const RAIN_AMOUNT = 'precipitation_amount_significant_weather_last_1h'
export const RAIN_CHANCE = 'probability_precipitation_amount_gt_0_1mm_last_1h'

/** The precipitation series the day's rain is worked out from: the hourly amount and its 6, 12 and 24 hour totals (`rr1c`, `rr6c`, `rrhc`, `rrdc`) */
export const RAIN_AMOUNTS = ['rr1c', 'rr6c', 'rrhc', 'rrdc'] as const
const AMOUNTS = new Set<string>([...METEOGRAM_SERIES.precipitation, ...METEOGRAM_SERIES.precipitation6h, ...METEOGRAM_SERIES.precipitation12h, ...METEOGRAM_SERIES.precipitation24h])

export type RainVerdict = 'yes' | 'maybe' | 'no'

export interface RainAnswer {
  verdict: RainVerdict
  /** The day asked about, `YYYY-MM-DD` in the place's time zone */
  day: string
  /** Precipitation of the day, the sum of its hours, in `unit` */
  total: number
  /** The unit `total`, the wettest hour and the hours are in */
  unit: string
  /** Hours with 0.1 mm or more */
  wetHours: number
  /** The highest chance of rain in any one hour, 0 to 1 whatever unit the forecast gives it in; null where the forecast carries none */
  maxChance: number | null
  /** The hour with the most rain, by its start (0 to 23), where any falls */
  wettest: { hour: number, amount: number } | null
  /** The hours of the day, in order */
  hours: Bar[]
}

/** How many hours of the day the forecast must reach for an answer about the whole day */
export const RAIN_MIN_HOURS = 18
/**
 * The bands of the rain verdict (GH-3764, which gives each its source or marks it as wetterdienst's own: `ask/chips/rain.ts`):
 * yes for a millimetre of the day or an hour with a chance of 70 %, maybe for 0.2 mm or a chance of 30 %; an hour with 0.1 mm
 * is a wet hour.
 */
export const RAIN_YES_MM = 1
export const RAIN_YES_CHANCE = 0.7
export const RAIN_MAYBE_MM = 0.2
export const RAIN_MAYBE_CHANCE = 0.3
export const RAIN_WET_HOUR_MM = 0.1

/**
 * Whether it rains tomorrow, in the place's time zone, from MOSMIX's hourly values. Yes for a millimetre or more, or
 * an hour with a chance of 70 % or more; maybe for 0.2 mm or a chance of 30 %; no otherwise. Null where the forecast
 * does not reach most of the day.
 */
export function rainTomorrow(
  readings: Reading[],
  zone: string,
  now: DateTime,
  units: { precipitation?: string, fraction?: string } = {},
): RainAnswer | null {
  const unit = units.precipitation ?? CANONICAL_UNITS.precipitation
  // the verdict is judged in millimetres, and the chance as a share from 0 to 1 (the app asks it as a decimal: so it is read
  // where the answer says no unit)
  const inMillimeters = (amount: number) => toCanonical('precipitation', unit, amount)
  const asShare = (chance: number) => toCanonical('fraction', units.fraction ?? '-', chance) / 100
  const start = now.setZone(zone).startOf('day').plus({ days: 1 })
  const end = start.plus({ days: 1 })
  const chanceAt = new Map<number, number>()
  for (const reading of readings) {
    if (reading.value !== null && reading.parameter === RAIN_CHANCE)
      chanceAt.set(DateTime.fromISO(reading.timestamp).toMillis(), reading.value)
  }
  // the rain of the day is the one the forecast's day rows have (GH-4175): the plan of blocks of 1, 6, 12 or 24 hours that account for
  // MOSMIX's 24 hour total, with each block's share of the hours in the day. Tomorrow is within the hourly amounts' reach, so these are
  // hours; where they were not, the hours of a longer block have its share each, and only an hour's own amount is "wet" or "wettest"
  const plan = planPrecipitation(buildSeries(readings.filter(reading => AMOUNTS.has(reading.parameter)) as never), inMillimeters)
  const blockOf = (stamp: number) => plan?.blocks.find(block => block.start < stamp && stamp <= block.end)
  const over = plan ? precipitationOver(plan, start.toMillis(), end.toMillis()) : null

  const hours: Bar[] = []
  let wetHours = 0
  let maxChance: number | null = null
  let wettest: RainAnswer['wettest'] = null
  // the value at a full hour is the precipitation of the hour before it, so the day's first is the one at 01:00
  for (let hour = start; hour < end; hour = hour.plus({ hours: 1 })) {
    const at = hour.plus({ hours: 1 }).toMillis()
    const block = blockOf(at)
    const amount = block ? block.amount / block.hours : null
    const chance = chanceAt.get(at)
    if (chance !== undefined)
      maxChance = Math.max(maxChance ?? 0, asShare(chance))
    if (amount !== null && block!.hours === 1) {
      if (inMillimeters(amount) >= RAIN_WET_HOUR_MM)
        wetHours++
      if (amount > 0 && (!wettest || amount > wettest.amount))
        wettest = { hour: hour.hour, amount }
    }
    hours.push({ key: hour.toISO()!, label: hour.toFormat('HH'), value: amount })
  }
  if (!over || over.given < RAIN_MIN_HOURS)
    return null
  let total = over.amount ?? 0
  let totalMillimeters = inMillimeters(total)

  total = Math.round(total * 10) / 10
  totalMillimeters = Math.round(totalMillimeters * 10) / 10
  const chance = maxChance ?? 0
  const verdict: RainVerdict = totalMillimeters >= RAIN_YES_MM || chance >= RAIN_YES_CHANCE
    ? 'yes'
    : totalMillimeters >= RAIN_MAYBE_MM || chance >= RAIN_MAYBE_CHANCE ? 'maybe' : 'no'
  return { verdict, day: start.toISODate()!, total, unit, wetHours, maxChance, wettest, hours }
}

// ---------------------------------------------------------------------------------------------------------------
// Was last summer hotter than usual? DWD's monthly means of the place's station
// ---------------------------------------------------------------------------------------------------------------

export type SummerVerdict = 'hotter' | 'cooler' | 'usual'

export interface SummerAnswer {
  verdict: SummerVerdict
  year: number
  /** Mean temperature of June, July and August, in `unit` */
  mean: number
  /** The unit of the temperatures, and of the differences (`anomaly`, the bars): degrees of it */
  unit: string
  /** The mean of the summers it is compared with, and the first and last of them */
  normal: number
  normalFrom: number
  normalTo: number
  /** `mean - normal`, in degrees of `unit` */
  anomaly: number
  /** 1 for the warmest summer of the record */
  rank: number
  /** How many complete summers the record has */
  summers: number
  /** How many summers the normal is the mean of, and whether they are the summers before the one asked about (the station has too few of the WMO normal) */
  referenceCount: number
  fallback: boolean
  /** One bar per summer: its difference from the normal */
  bars: Bar[]
}

/** The reference period of the WMO, and how many of its summers a station must have for it */
export const NORMAL_FROM = 1991
export const NORMAL_TO = 2020
export const NORMAL_MIN_SUMMERS = 20
/** Where a station has too few, the summers before the one asked about, if there are this many */
export const FALLBACK_MIN_SUMMERS = 10
/** Within half a degree is "as usual": smaller than the year-to-year noise of a summer mean */
export const USUAL_BAND = 0.5

/** The last complete summer (June to August, over by `now`) against the summers of 1991 to 2020, or of the record before it */
export function lastSummer(readings: Reading[], now: DateTime, unit: string = CANONICAL_UNITS.temperature): SummerAnswer | null {
  const months = new Map<number, Map<number, number>>()
  for (const reading of readings) {
    if (reading.value === null)
      continue
    const at = DateTime.fromISO(reading.timestamp, { zone: 'utc' })
    if (at.month < 6 || at.month > 8)
      continue
    const year = months.get(at.year) ?? new Map<number, number>()
    // worked out in degrees Celsius, where the half degree of "as usual" is
    year.set(at.month, toCanonical('temperature', unit, reading.value))
    months.set(at.year, year)
  }
  const summers = [...months.entries()]
    .filter(([year, values]) => values.size === 3 && now >= DateTime.utc(year, 9, 1))
    .map(([year, values]) => ({ year, mean: ([...values.values()].reduce((a, b) => a + b, 0)) / 3 }))
    .sort((a, b) => a.year - b.year)
  const last = summers.at(-1)
  if (!last)
    return null

  let reference = summers.filter(summer => summer.year >= NORMAL_FROM && summer.year <= NORMAL_TO)
  let fallback = false
  if (reference.length < NORMAL_MIN_SUMMERS) {
    fallback = true
    reference = summers.filter(summer => summer.year < last.year)
    if (reference.length < FALLBACK_MIN_SUMMERS)
      return null
  }
  const normal = reference.reduce((sum, summer) => sum + summer.mean, 0) / reference.length
  // to three decimals, as `toCanonical` is, so that an anomaly on the edge of the band is on it in any unit
  const anomaly = Math.round((last.mean - normal) * 1e3) / 1e3
  // a difference in degrees of the unit, not a temperature in it: 1 K is 1.8 °F
  const degrees = (difference: number) => round1(differenceIn('temperature', unit, difference))
  const verdict: SummerVerdict = anomaly >= USUAL_BAND ? 'hotter' : anomaly <= -USUAL_BAND ? 'cooler' : 'usual'
  return {
    verdict,
    year: last.year,
    mean: round1(fromCanonical('temperature', unit, last.mean)),
    unit,
    normal: round1(fromCanonical('temperature', unit, normal)),
    normalFrom: reference[0]!.year,
    normalTo: reference.at(-1)!.year,
    anomaly: degrees(anomaly),
    rank: 1 + summers.filter(summer => summer.mean > last.mean).length,
    summers: summers.length,
    referenceCount: reference.length,
    fallback,
    bars: summers.map(summer => ({
      key: String(summer.year),
      label: String(summer.year),
      at: summer.year,
      value: degrees(summer.mean - normal),
      highlight: summer.year === last.year,
    })),
  }
}

// ---------------------------------------------------------------------------------------------------------------
// How windy was it on a day? DWD's daily climate summary of the place's station
// ---------------------------------------------------------------------------------------------------------------

export const WIND_MEAN = 'wind_speed_mean'
export const WIND_GUST = 'wind_gust_max'

export type WindVerdict = 'calm' | 'breezy' | 'windy' | 'stormy'

export interface WindAnswer {
  verdict: WindVerdict
  day: string
  /** Daily mean wind speed and the strongest gust, in `unit`; either can be missing */
  mean: number | null
  gust: number | null
  /** The unit of the speeds, and of the bars */
  unit: string
  /** The Beaufort force of the mean and of the gust */
  beaufort: number | null
  gustBeaufort: number | null
  /** The days around it (a week either side) with a gust, and how many of them had a stronger one */
  around: number
  stronger: number
  /** One bar per day around it: its strongest gust (or mean where no gust is published) */
  bars: Bar[]
  /** Whether the bars are gusts (true) or means */
  barsAreGusts: boolean
}

/** The lower edge of Beaufort 1 to 12, m/s (WMO-No. 8, Volume I, Table 5.1) */
export const BEAUFORT = [0.3, 1.6, 3.4, 5.5, 8.0, 10.8, 13.9, 17.2, 20.8, 24.5, 28.5, 32.7]

/**
 * The force from which a day is breezy, windy and stormy: by its strongest gust, and by its mean where there is no gust. The words
 * are wetterdienst's own grouping of Beaufort's forces (GH-3764: `ask/chips/wind.ts`).
 */
export const WIND_FORCES_OF_GUST = { breezy: 5, windy: 7, stormy: 9 } as const
export const WIND_FORCES_OF_MEAN = { breezy: 4, windy: 6, stormy: 8 } as const
/** The days either side of the day asked about that the wind answer fetches and compares with */
export const WIND_WINDOW_DAYS = 7

export function beaufort(speed: number): number {
  return BEAUFORT.filter(edge => speed >= edge).length
}

/**
 * How windy `day` was: by its strongest gust where there is one (under Beaufort 5 calm, under 7 breezy, under 9
 * windy, from 9, a strong gale, stormy), else by its mean (under 4, under 6, under 8, from 8).
 */
export function windOnDay(readings: Reading[], day: string, unit: string = CANONICAL_UNITS.speed): WindAnswer | null {
  const byDay = new Map<string, { mean: number | null, gust: number | null }>()
  for (const reading of readings) {
    if (reading.value === null || (reading.parameter !== WIND_MEAN && reading.parameter !== WIND_GUST))
      continue
    const date = reading.timestamp.slice(0, 10)
    const entry = byDay.get(date) ?? { mean: null, gust: null }
    if (reading.parameter === WIND_MEAN)
      entry.mean = reading.value
    else
      entry.gust = reading.value
    byDay.set(date, entry)
  }
  const that = byDay.get(day)
  if (!that || (that.mean === null && that.gust === null))
    return null

  // Beaufort's force is a range of metres per second: the speed is converted to it from whatever unit it is in
  const gustBeaufort = that.gust === null ? null : beaufort(toCanonical('speed', unit, that.gust))
  const meanBeaufort = that.mean === null ? null : beaufort(toCanonical('speed', unit, that.mean))
  let verdict: WindVerdict
  if (gustBeaufort !== null)
    verdict = gustBeaufort >= WIND_FORCES_OF_GUST.stormy ? 'stormy' : gustBeaufort >= WIND_FORCES_OF_GUST.windy ? 'windy' : gustBeaufort >= WIND_FORCES_OF_GUST.breezy ? 'breezy' : 'calm'
  else
    verdict = meanBeaufort! >= WIND_FORCES_OF_MEAN.stormy ? 'stormy' : meanBeaufort! >= WIND_FORCES_OF_MEAN.windy ? 'windy' : meanBeaufort! >= WIND_FORCES_OF_MEAN.breezy ? 'breezy' : 'calm'

  const barsAreGusts = that.gust !== null
  const days = [...byDay.keys()].sort()
  const measure = (date: string) => barsAreGusts ? byDay.get(date)!.gust : byDay.get(date)!.mean
  const own = measure(day)!
  const others = days.filter(date => date !== day && measure(date) !== null)
  return {
    verdict,
    day,
    mean: that.mean,
    gust: that.gust,
    unit,
    beaufort: meanBeaufort,
    gustBeaufort,
    around: others.length,
    stronger: others.filter(date => measure(date)! > own).length,
    bars: days.map(date => ({ key: date, label: date, value: measure(date), highlight: date === day })),
    barsAreGusts,
  }
}

/** The 26 December the question means: this year's once its readings can be in, else last year's */
export function lastBoxingDay(now: DateTime): string {
  const year = now.month === 12 && now.day >= 28 ? now.year : now.year - 1
  return `${year}-12-26`
}

/** A week either side of `day`, and none of it in the future: the span the wind answer fetches */
export function windWindow(day: string, now: DateTime): { from: string, to: string } {
  const at = DateTime.fromISO(day, { zone: 'utc' })
  const yesterday = now.toUTC().startOf('day').minus({ days: 1 })
  const to = DateTime.min(at.plus({ days: WIND_WINDOW_DAYS }), yesterday)
  return { from: at.minus({ days: WIND_WINDOW_DAYS }).toISODate()!, to: DateTime.max(to, at).toISODate()! }
}

// ---------------------------------------------------------------------------------------------------------------
// Where can I download hourly temperatures? The backend's providers and their coverage
// ---------------------------------------------------------------------------------------------------------------

/** The names a provider gives the hourly air temperature at 2 m: a reading at the hour, or the mean of the hour */
export const HOURLY_TEMPERATURE = ['temperature_air_mean_2m', 'temperature_air_2m']

export interface TemperatureSource {
  provider: string
  name: string
  countryCode: string | null
  network: string
  dataset: string
  parameter: string
}

/**
 * The measurement networks of `providers`: the ones whose coverage to ask for an hourly resolution. The list of
 * providers does not say which have one (that is the coverage of each), so a network without it is told by its 404.
 */
export function hourlyNetworks(providers: Provider[]): Array<{ provider: Provider, network: string }> {
  return providers.flatMap(provider => provider.networks
    .filter(network => network.kind === 'observation')
    .map(network => ({ provider, network: network.network })))
}

/** How many coverages the download question asks for at once: the server serves 32 requests at a time, for every client */
export const COVERAGE_REQUESTS_AT_ONCE = 4

/** The results of `work` for each item, in order, with at most `limit` of them under way at once */
export async function mapLimited<T, R>(items: readonly T[], limit: number, work: (item: T) => Promise<R>): Promise<R[]> {
  const results: R[] = Array.from({ length: items.length })
  let next = 0
  async function lane() {
    while (next < items.length) {
      const index = next++
      results[index] = await work(items[index]!)
    }
  }
  await Promise.all(Array.from({ length: Math.min(limit, items.length) }, lane))
  return results
}

/**
 * The dataset and parameter of a network's coverage that hold the hourly air temperature, the dataset named for it
 * first (DWD's `temperature_air`), or null where it has none
 */
export function hourlyTemperatureIn(coverage: ProviderNetworkCoverageResponse): { dataset: string, parameter: string } | null {
  const datasets = Object.entries(coverage.hourly?.datasets ?? {})
    .sort(([a], [b]) => Number(b === 'temperature_air') - Number(a === 'temperature_air'))
  for (const [dataset, content] of datasets) {
    const found = HOURLY_TEMPERATURE.find(name => content.parameters.some(parameter => parameter.name === name))
    if (found)
      return { dataset, parameter: found }
  }
  return null
}

function round1(value: number): number {
  return Math.round(value * 10) / 10
}
