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
// Was last summer, winter ... warmer than usual? DWD's monthly means of the place's station (GH-3518, GH-3764)
// ---------------------------------------------------------------------------------------------------------------

/** The meteorological seasons of the northern hemisphere: three whole months each (DWD) */
export type Season = 'spring' | 'summer' | 'autumn' | 'winter'
export const SEASONS: readonly Season[] = ['spring', 'summer', 'autumn', 'winter']
/**
 * The months of each season. The winter has the December of the year before the one it is named for: the winter 2025/26 is
 * named 2026, the year of its January and February, and is over on 1 March 2026.
 */
export const SEASON_MONTHS: Readonly<Record<Season, readonly [number, number, number]>> = {
  spring: [3, 4, 5],
  summer: [6, 7, 8],
  autumn: [9, 10, 11],
  winter: [12, 1, 2],
}

export function isSeason(value: unknown): value is Season {
  return typeof value === 'string' && (SEASONS as readonly string[]).includes(value)
}

/** The year a season is named for: that of the month, except for the December of a winter, which belongs to the winter of the next year */
function seasonYearOf(season: Season, at: DateTime): number {
  return season === 'winter' && at.month === 12 ? at.year + 1 : at.year
}

/** The first moment at which a season of a year is over: 1 June, 1 September, 1 December, and 1 March of the year the winter is named for */
export function seasonOver(season: Season, year: number): DateTime {
  return DateTime.utc(year, SEASON_MONTHS[season][2], 1).plus({ months: 1 })
}

/** How a season of a year is written: the year, and for a winter both years it spans (`2025/26`) */
export function seasonLabel(season: Season, year: number): string {
  return season === 'winter' ? `${year - 1}/${String(year).slice(2)}` : String(year)
}

/** The WMO normals: 30 years that end in a year ending in 0, from 1961 to 1990 onward (the reference normal of WMO-No. 1203, §2) */
export const NORMAL_FIRST_TO = 1990
export const NORMAL_YEARS = 30
/** How many of the seasons of a normal a station must have for it */
export const NORMAL_MIN_SEASONS = 20
/** Where the newest normal is short, the seasons before the one asked about, if there are this many */
export const FALLBACK_MIN_SEASONS = 10
/** Within half a degree is "as usual": smaller than the year-to-year noise of a season mean */
export const USUAL_BAND = 0.5

/** One normal: `key` is how a link names it (`1961-1990`) */
export interface Normal {
  from: number
  to: number
  key: string
}

function normalEndingIn(to: number): Normal {
  const from = to - NORMAL_YEARS + 1
  return { from, to, key: `${from}-${to}` }
}

/** The year the newest complete normal ends in: `floor((year - 1) / 10) * 10`, since a normal is complete on 31 December of its last year */
export function newestNormalEnd(now: DateTime): number {
  return Math.max(NORMAL_FIRST_TO, Math.floor((now.toUTC().year - 1) / 10) * 10)
}

/** Every normal that is complete at `now`, the oldest first: 1961-1990, 1971-2000, 1981-2010 and 1991-2020 in 2026, and 2001-2030 from 2031 */
export function normalsAt(now: DateTime): Normal[] {
  const newest = newestNormalEnd(now)
  const normals: Normal[] = []
  for (let to = NORMAL_FIRST_TO; to <= newest; to += 10)
    normals.push(normalEndingIn(to))
  return normals
}

/** The newest complete normal: the one a link without `&ref=` means */
export function newestNormal(now: DateTime): Normal {
  return normalEndingIn(newestNormalEnd(now))
}

/** The normal a link names, or null where it names none that is complete at `now` */
export function normalOf(key: unknown, now: DateTime): Normal | null {
  return normalsAt(now).find(normal => normal.key === key) ?? null
}

export type SeasonVerdict = 'warmer' | 'cooler' | 'usual'

export interface SeasonAnswer {
  verdict: SeasonVerdict
  season: Season
  /** The year the season is named for: the one of its January for a winter */
  year: number
  /** Mean temperature of the three months, in `unit` */
  mean: number
  /** The unit of the temperatures, and of the differences (`anomaly`, the bars): degrees of it */
  unit: string
  /** The mean of the seasons it is compared with, and the first and last year of them (of the normal asked for, or of the seasons before where the station had too few) */
  normal: number
  normalFrom: number
  normalTo: number
  /** The normal that was asked for (the newest one where the link named none): the answer is not of it where `fallback` */
  asked: { from: number, to: number }
  /** `mean - normal`, in degrees of `unit` */
  anomaly: number
  /** 1 for the warmest season of the record */
  rank: number
  /** How many complete seasons the record has */
  seasons: number
  /** How many seasons the normal is the mean of, and whether they are the seasons before the one asked about (the station has too few of the newest normal) */
  referenceCount: number
  fallback: boolean
  /** One bar per season: its difference from the normal */
  bars: Bar[]
}

/** One complete season of a station: the year it is named for, and the mean of its three months, in degrees Celsius */
export interface SeasonMean {
  year: number
  mean: number
}

/** The complete seasons of a kind in the monthly means (`now` at or after the end of the season; every month of it there), the oldest first, worked out in degrees Celsius, where the half degree of "as usual" is */
export function seasonMeans(readings: Reading[], season: Season, now: DateTime, unit: string = CANONICAL_UNITS.temperature): SeasonMean[] {
  const months = new Map<number, Map<number, number>>()
  for (const reading of readings) {
    if (reading.value === null)
      continue
    const at = DateTime.fromISO(reading.timestamp, { zone: 'utc' })
    if (!SEASON_MONTHS[season].includes(at.month))
      continue
    const year = seasonYearOf(season, at)
    const values = months.get(year) ?? new Map<number, number>()
    values.set(at.month, toCanonical('temperature', unit, reading.value))
    months.set(year, values)
  }
  return [...months.entries()]
    .filter(([year, values]) => values.size === 3 && now >= seasonOver(season, year))
    .map(([year, values]) => ({ year, mean: ([...values.values()].reduce((a, b) => a + b, 0)) / 3 }))
    .sort((a, b) => a.year - b.year)
}

/** How many seasons of a normal a station has (those of the years of the normal) */
export function countIn(seasons: readonly SeasonMean[], normal: Normal): number {
  return seasons.filter(each => each.year >= normal.from && each.year <= normal.to).length
}

/** What a station has of one normal: its seasons of the kind in it, whether that is enough (`NORMAL_MIN_SEASONS`), and whether an answer is possible at all (enough, or the newest normal with enough seasons before the last to stand in for it) */
export interface NormalAvailability {
  normal: Normal
  count: number
  enough: boolean
  /** Where the normal is short: whether the seasons before the one asked about stand in for it (the newest normal only, with `FALLBACK_MIN_SEASONS` of them) */
  fallback: boolean
}

/** The normals at `now` with how many seasons of a kind the station has of each, and whether that is enough or something stands in for it */
export function normalAvailability(readings: Reading[], season: Season, now: DateTime): NormalAvailability[] {
  const seasons = seasonMeans(readings, season, now)
  const last = seasons.at(-1)
  const newest = newestNormal(now)
  const earlier = last ? seasons.filter(each => each.year < last.year).length : 0
  return normalsAt(now).map((normal) => {
    const count = countIn(seasons, normal)
    const enough = count >= NORMAL_MIN_SEASONS
    return { normal, count, enough, fallback: !enough && normal.key === newest.key && earlier >= FALLBACK_MIN_SEASONS }
  })
}

/** A normal as it is written for a season: the years of its seasons, a winter's by both years (the normal 1961-1990 is the winters 1960/61 to 1989/90, as the bars are labelled) */
export function normalSpan(season: Season, from: number, to: number): { from: string, to: string } {
  return { from: seasonLabel(season, from), to: seasonLabel(season, to) }
}

/** What a question asks: the season, and the normal it is compared with (`1991-2020`; the newest one where it is none that is complete) */
export interface SeasonRequest {
  season: Season
  normal: string
}

/**
 * The last complete season of a kind (over by `now`) against the normal asked for. A normal the station has too few
 * seasons of is no answer (null), except the newest one: there the seasons before the one asked about stand in for it, if
 * there are enough of them. Null too where the station has no complete season.
 */
export function lastSeason(readings: Reading[], now: DateTime, { season, normal: asked }: SeasonRequest, unit: string = CANONICAL_UNITS.temperature): SeasonAnswer | null {
  const seasons = seasonMeans(readings, season, now, unit)
  const last = seasons.at(-1)
  if (!last)
    return null

  const newest = newestNormal(now)
  const chosen = normalOf(asked, now) ?? newest
  let reference = seasons.filter(each => each.year >= chosen.from && each.year <= chosen.to)
  let fallback = false
  if (reference.length < NORMAL_MIN_SEASONS) {
    if (chosen.key !== newest.key)
      return null
    fallback = true
    reference = seasons.filter(each => each.year < last.year)
    if (reference.length < FALLBACK_MIN_SEASONS)
      return null
  }
  const normal = reference.reduce((sum, each) => sum + each.mean, 0) / reference.length
  // to three decimals, as `toCanonical` is, so that an anomaly on the edge of the band is on it in any unit
  const anomaly = Math.round((last.mean - normal) * 1e3) / 1e3
  // a difference in degrees of the unit, not a temperature in it: 1 K is 1.8 °F
  const degrees = (difference: number) => round1(differenceIn('temperature', unit, difference))
  const verdict: SeasonVerdict = anomaly >= USUAL_BAND ? 'warmer' : anomaly <= -USUAL_BAND ? 'cooler' : 'usual'
  return {
    verdict,
    season,
    year: last.year,
    mean: round1(fromCanonical('temperature', unit, last.mean)),
    unit,
    normal: round1(fromCanonical('temperature', unit, normal)),
    normalFrom: fallback ? reference[0]!.year : chosen.from,
    normalTo: fallback ? reference.at(-1)!.year : chosen.to,
    asked: { from: chosen.from, to: chosen.to },
    anomaly: degrees(anomaly),
    rank: 1 + seasons.filter(each => each.mean > last.mean).length,
    seasons: seasons.length,
    referenceCount: reference.length,
    fallback,
    bars: seasons.map(each => ({
      key: String(each.year),
      label: seasonLabel(season, each.year),
      at: each.year,
      value: degrees(each.mean - normal),
      highlight: each.year === last.year,
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
