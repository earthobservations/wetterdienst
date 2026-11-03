import type { Provider, ProviderNetworkCoverageResponse } from '#shared/types/api'
import { DateTime } from 'luxon'

// The answers of the home page's questions (components/AnswerPanel.vue), worked out from the values the backend
// answers with. Pure: the page fetches, these read. Nothing here is a number of its own; where the data does not
// carry an answer, the function says so (null) rather than make one up.

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

export type RainVerdict = 'yes' | 'maybe' | 'no'

export interface RainAnswer {
  verdict: RainVerdict
  /** The day asked about, `YYYY-MM-DD` in the place's time zone */
  day: string
  /** Precipitation of the day in millimetres, the sum of its hours */
  total: number
  /** Hours with 0.1 mm or more */
  wetHours: number
  /** The highest chance of rain in any one hour, 0 to 1; null where the forecast carries none */
  maxChance: number | null
  /** The hour with the most rain, by its start (0 to 23), where any falls */
  wettest: { hour: number, amount: number } | null
  /** The hours of the day, in order */
  hours: Bar[]
}

/** How many hours of the day the forecast must reach for an answer about the whole day */
const RAIN_MIN_HOURS = 18

/**
 * Whether it rains tomorrow, in the place's time zone, from MOSMIX's hourly values. Yes for a millimetre or more, or
 * an hour with a chance of 70 % or more; maybe for 0.2 mm or a chance of 30 %; no otherwise. Null where the forecast
 * does not reach most of the day.
 */
export function rainTomorrow(readings: Reading[], zone: string, now: DateTime): RainAnswer | null {
  const start = now.setZone(zone).startOf('day').plus({ days: 1 })
  const end = start.plus({ days: 1 })
  const amountAt = new Map<number, number>()
  const chanceAt = new Map<number, number>()
  for (const reading of readings) {
    if (reading.value === null)
      continue
    const at = DateTime.fromISO(reading.timestamp).toMillis()
    if (reading.parameter === RAIN_AMOUNT)
      amountAt.set(at, reading.value)
    else if (reading.parameter === RAIN_CHANCE)
      chanceAt.set(at, reading.value)
  }

  const hours: Bar[] = []
  let total = 0
  let wetHours = 0
  let covered = 0
  let maxChance: number | null = null
  let wettest: RainAnswer['wettest'] = null
  // the value at a full hour is the precipitation of the hour before it, so the day's first is the one at 01:00
  for (let hour = start; hour < end; hour = hour.plus({ hours: 1 })) {
    const at = hour.plus({ hours: 1 }).toMillis()
    const amount = amountAt.get(at) ?? null
    const chance = chanceAt.get(at)
    if (chance !== undefined)
      maxChance = Math.max(maxChance ?? 0, chance)
    if (amount !== null) {
      covered++
      total += amount
      if (amount >= 0.1)
        wetHours++
      if (amount > 0 && (!wettest || amount > wettest.amount))
        wettest = { hour: hour.hour, amount }
    }
    hours.push({ key: hour.toISO()!, label: hour.toFormat('HH'), value: amount })
  }
  if (covered < RAIN_MIN_HOURS)
    return null

  total = Math.round(total * 10) / 10
  const chance = maxChance ?? 0
  const verdict: RainVerdict = total >= 1 || chance >= 0.7
    ? 'yes'
    : total >= 0.2 || chance >= 0.3 ? 'maybe' : 'no'
  return { verdict, day: start.toISODate()!, total, wetHours, maxChance, wettest, hours }
}

// ---------------------------------------------------------------------------------------------------------------
// Was last summer hotter than usual? DWD's monthly means of the place's station
// ---------------------------------------------------------------------------------------------------------------

export type SummerVerdict = 'hotter' | 'cooler' | 'usual'

export interface SummerAnswer {
  verdict: SummerVerdict
  year: number
  /** Mean temperature of June, July and August, °C */
  mean: number
  /** The mean of the summers it is compared with, and the first and last of them */
  normal: number
  normalFrom: number
  normalTo: number
  /** `mean - normal`, K */
  anomaly: number
  /** 1 for the warmest summer of the record */
  rank: number
  /** How many complete summers the record has */
  summers: number
  /** One bar per summer: its difference from the normal */
  bars: Bar[]
}

/** The reference period of the WMO, and how many of its summers a station must have for it */
const NORMAL_FROM = 1991
const NORMAL_TO = 2020
const NORMAL_MIN_SUMMERS = 20
/** Where a station has too few, the summers before the one asked about, if there are this many */
const FALLBACK_MIN_SUMMERS = 10
/** Within half a degree is "as usual": smaller than the year-to-year noise of a summer mean */
const USUAL_BAND = 0.5

/** The last complete summer (June to August, over by `now`) against the summers of 1991 to 2020, or of the record before it */
export function lastSummer(readings: Reading[], now: DateTime): SummerAnswer | null {
  const months = new Map<number, Map<number, number>>()
  for (const reading of readings) {
    if (reading.value === null)
      continue
    const at = DateTime.fromISO(reading.timestamp, { zone: 'utc' })
    if (at.month < 6 || at.month > 8)
      continue
    const year = months.get(at.year) ?? new Map<number, number>()
    year.set(at.month, reading.value)
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
  if (reference.length < NORMAL_MIN_SUMMERS) {
    reference = summers.filter(summer => summer.year < last.year)
    if (reference.length < FALLBACK_MIN_SUMMERS)
      return null
  }
  const normal = reference.reduce((sum, summer) => sum + summer.mean, 0) / reference.length
  const anomaly = last.mean - normal
  const verdict: SummerVerdict = anomaly >= USUAL_BAND ? 'hotter' : anomaly <= -USUAL_BAND ? 'cooler' : 'usual'
  return {
    verdict,
    year: last.year,
    mean: round1(last.mean),
    normal: round1(normal),
    normalFrom: reference[0]!.year,
    normalTo: reference.at(-1)!.year,
    anomaly: round1(anomaly),
    rank: 1 + summers.filter(summer => summer.mean > last.mean).length,
    summers: summers.length,
    bars: summers.map(summer => ({
      key: String(summer.year),
      label: String(summer.year),
      value: round1(summer.mean - normal),
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
  /** Daily mean wind speed and the strongest gust, m/s; either can be missing */
  mean: number | null
  gust: number | null
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

/** The lower edge of Beaufort 1 to 12, m/s (WMO) */
const BEAUFORT = [0.3, 1.6, 3.4, 5.5, 8.0, 10.8, 13.9, 17.2, 20.8, 24.5, 28.5, 32.7]

export function beaufort(speed: number): number {
  return BEAUFORT.filter(edge => speed >= edge).length
}

/**
 * How windy `day` was: by its strongest gust where there is one (under Beaufort 5 calm, under 7 breezy, under 9
 * windy, from 9, a strong gale, stormy), else by its mean (under 4, under 6, under 8, from 8).
 */
export function windOnDay(readings: Reading[], day: string): WindAnswer | null {
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

  const gustBeaufort = that.gust === null ? null : beaufort(that.gust)
  const meanBeaufort = that.mean === null ? null : beaufort(that.mean)
  let verdict: WindVerdict
  if (gustBeaufort !== null)
    verdict = gustBeaufort >= 9 ? 'stormy' : gustBeaufort >= 7 ? 'windy' : gustBeaufort >= 5 ? 'breezy' : 'calm'
  else
    verdict = meanBeaufort! >= 8 ? 'stormy' : meanBeaufort! >= 6 ? 'windy' : meanBeaufort! >= 4 ? 'breezy' : 'calm'

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
  const to = DateTime.min(at.plus({ days: 7 }), yesterday)
  return { from: at.minus({ days: 7 }).toISODate()!, to: DateTime.max(to, at).toISODate()! }
}

// ---------------------------------------------------------------------------------------------------------------
// Where can I download hourly temperatures? The backend's providers and their coverage
// ---------------------------------------------------------------------------------------------------------------

/** The names a provider gives the hourly air temperature at 2 m: a reading at the hour, or the mean of the hour */
const HOURLY_TEMPERATURE = ['temperature_air_mean_2m', 'temperature_air_2m']

export interface TemperatureSource {
  provider: string
  name: string
  countryCode: string | null
  network: string
  dataset: string
  parameter: string
}

/** The measurement networks of `providers` that publish an hourly resolution: the ones whose coverage to ask */
export function hourlyNetworks(providers: Provider[]): Array<{ provider: Provider, network: string }> {
  return providers.flatMap(provider => provider.networks
    .filter(network => network.kind === 'observation' && network.resolutions.some(resolution => resolution.name === 'hourly'))
    .map(network => ({ provider, network: network.network })))
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
