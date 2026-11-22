/**
 * The Compare tool (GH-4296): two sides of the same parameter, side by side. A side is a station (two stations, one period) or a
 * period (two periods, one station). Everything that is arithmetic or an address is here, pure, so that it is tested without a
 * browser; `components/ComparePanel.vue` fetches and draws, `pages/compare.vue` holds the address.
 *
 * What a comparison is, in one place:
 * - **Which data.** Approach C (GH-3789): `dwd/observation`, the daily and the monthly `climate_summary`. Others follow one at a
 *   time, once they pass the same checks.
 * - **Alignment.** Two stations are aligned by calendar date (the same day, or the same month, of each). Two periods are aligned by
 *   the position in the period: the first day of A with the first day of B, the second with the second (the first month with the
 *   first month, at monthly). Periods of unequal length are compared as far as the shorter reaches; the days of the longer one past
 *   it have no partner and no difference (`alignPeriods`).
 * - **The difference** is always side B minus side A, in the unit of the values, and where a side has no value it is none: a
 *   missing value is never counted as zero (`difference`).
 * - **When the two sides are not the same kind of number** (another resolution, dataset, unit, or a value that stands for another
 *   stretch of time), the comparison is refused with the reason (`sidesDiffer`); one dataset of one network makes it rare, but
 *   a link can carry anything.
 */

import { withData } from './format'
import { timestampDate } from './timestamp'

/** What the sides are: two stations over one period, or one station over two periods */
export type CompareBy = 'stations' | 'periods'

export const COMPARE_BY: readonly CompareBy[] = ['stations', 'periods']

export function isCompareBy(value: unknown): value is CompareBy {
  return typeof value === 'string' && (COMPARE_BY as readonly string[]).includes(value)
}

/** A stretch of days: `start` to `end`, both included, each `YYYY-MM-DD` */
export interface ComparePeriod {
  start: string
  end: string
}

/** The comparison as the address holds it: what it is about, and the sides */
export interface CompareAddress {
  by: CompareBy
  /** The resolution of the values, daily where the link names none */
  resolution: CompareResolution
  /** The parameter, as the glossary names it (`temperature_air_mean_2m`) */
  parameter?: string
  /** The station ids: two for `stations` (A, B), one for `periods` */
  stations: string[]
  /** The period of both stations (`stations`) */
  period?: ComparePeriod
  /** The periods of the one station (`periods`) */
  periodA?: ComparePeriod
  periodB?: ComparePeriod
}

// -- the networks that can be compared ------------------------------------------------------------------------------

/**
 * What Compare offers (GH-3789, approach C): the networks it was built and tested on. Others are shown greyed out with the reason,
 * and follow one at a time once they pass the same checks.
 */
export const COMPARE_SOURCE = {
  provider: 'dwd',
  network: 'observation',
  dataset: 'climate_summary',
  resolutions: ['daily', 'monthly'],
} as const

/** The resolutions Compare aligns: a day, or a month */
export type CompareResolution = (typeof COMPARE_SOURCE.resolutions)[number]

/**
 * The longest period a comparison holds, in steps of the resolution: ten years of days, a hundred years of months. A table and a chart of
 * more would be more than a reader looks at, and the server refuses a request past its own limit of rows (the table says so); an own
 * rule of the app, not a limit of the data.
 */
export const MAX_STEPS: Readonly<Record<CompareResolution, number>> = { daily: 3660, monthly: 1200 }

/**
 * A value as the table writes it: up to two decimals in the language of the page, none that is not there (12.3, not 12.30), and for a
 * difference the sign written out (`+0.8`). A value that rounds to zero has no sign.
 */
export function valueText(value: number, language: string, signed = false): string {
  const rounded = Math.round(value * 100) / 100
  return new Intl.NumberFormat(withData(language, Intl.NumberFormat.supportedLocalesOf), { maximumFractionDigits: 2, signDisplay: signed ? 'exceptZero' : 'auto' }).format(rounded === 0 ? 0 : rounded)
}

export type CompareRefusal = 'resolution' | 'dataset' | 'parameter' | 'unit' | 'aggregation' | 'position'

/** Whether a text names a resolution the tool compares */
export function isCompareResolution(value: unknown): value is CompareResolution {
  return typeof value === 'string' && (COMPARE_SOURCE.resolutions as readonly string[]).includes(value)
}

// -- days and months ------------------------------------------------------------------------------------------------

const DAY_MS = 86_400_000

/** A day `YYYY-MM-DD` as the number of days since the epoch, or null for text that is no calendar day */
export function dayNumber(text: string): number | null {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(text))
    return null
  const date = timestampDate(text)
  return date ? Math.round(date.getTime() / DAY_MS) : null
}

/** The day `YYYY-MM-DD` of a number of days since the epoch */
export function dayText(number: number): string {
  return new Date(number * DAY_MS).toISOString().slice(0, 10)
}

/** The month of a day as the number of months since the epoch, from 0 for January 1970 */
function monthNumber(day: string): number {
  return (Number(day.slice(0, 4)) - 1970) * 12 + Number(day.slice(5, 7)) - 1
}

/** The first day of the month `number` months since the epoch */
function monthStart(number: number): string {
  const year = 1970 + Math.floor(number / 12)
  const month = ((number % 12) + 12) % 12 + 1
  return `${String(year).padStart(4, '0')}-${String(month).padStart(2, '0')}-01`
}

/** A period `YYYY-MM-DD/YYYY-MM-DD`, or null for text that is not two calendar days, the second not before the first */
export function readPeriod(text: unknown): ComparePeriod | null {
  if (typeof text !== 'string')
    return null
  const [start, end, ...rest] = text.split('/')
  if (!start || !end || rest.length)
    return null
  const from = dayNumber(start)
  const to = dayNumber(end)
  return from !== null && to !== null && to >= from ? { start, end } : null
}

export function periodText(period: ComparePeriod): string {
  return `${period.start}/${period.end}`
}

/** How many steps (days, or months) a period holds at a resolution, both ends included */
export function periodLength(period: ComparePeriod, resolution: CompareResolution): number {
  if (resolution === 'monthly')
    return monthNumber(period.end) - monthNumber(period.start) + 1
  return dayNumber(period.end)! - dayNumber(period.start)! + 1
}

/** The `index`-th step of a period (a day, or the first of a month), as the date it falls on */
export function stepOf(period: ComparePeriod, resolution: CompareResolution, index: number): string {
  return resolution === 'monthly' ? monthStart(monthNumber(period.start) + index) : dayText(dayNumber(period.start)! + index)
}

/**
 * The window a request asks for: a period as it is for days, and the whole of its first and last month for months, since a month's
 * value is stamped at its first day and a window that starts on the 15th would leave that month's value out.
 */
export function requestWindow(period: ComparePeriod, resolution: CompareResolution): ComparePeriod {
  if (resolution === 'daily')
    return period
  const first = monthStart(monthNumber(period.start))
  return { start: first, end: dayText(dayNumber(monthStart(monthNumber(period.end) + 1))! - 1) }
}

/** The `months` whole calendar months that end with the month (`month`, 1 to 12) of `year`, as a period of days */
function monthsEndingWith(year: number, month: number, months: number): ComparePeriod {
  const first = monthNumber(`${String(year).padStart(4, '0')}-${String(month).padStart(2, '0')}-01`) - (months - 1)
  const next = monthStart(monthNumber(`${String(year).padStart(4, '0')}-${String(month).padStart(2, '0')}-01`) + 1)
  return { start: monthStart(first), end: dayText(dayNumber(next)! - 1) }
}

/**
 * The periods the fields are started with, so that a comparison is one choice of station away: the last complete month (the last twelve
 * where the values are monthly), and the same stretch a year before it. Today's month is not complete, and DWD's newest days are not yet
 * published.
 */
export function suggestedPeriods(resolution: CompareResolution, now: Date = new Date()): { latest: ComparePeriod, yearBefore: ComparePeriod } {
  const year = now.getUTCFullYear()
  const month = now.getUTCMonth() + 1
  const [lastYear, lastMonth] = month === 1 ? [year - 1, 12] : [year, month - 1]
  const months = resolution === 'monthly' ? 12 : 1
  return { latest: monthsEndingWith(lastYear, lastMonth, months), yearBefore: monthsEndingWith(lastYear - 1, lastMonth, months) }
}

// -- the address ------------------------------------------------------------------------------------------------------

type Query = Record<string, unknown>

function text(value: unknown): string {
  const first = Array.isArray(value) ? value[0] : value
  return typeof first === 'string' ? first : ''
}

/**
 * The comparison a link names. The sides are `stations=A,B` over `startDate`/`endDate` (two stations), or `stations=A` over
 * `periodA=2025-03-01/2025-03-31` and `periodB=2026-03-01/2026-03-31` (two periods). `compare=periods` says it where no period is
 * given yet; a link that has `periodA` or `periodB` and no `compare` is the periods too. What is not a station id, a calendar day
 * or a period is left out, never an error: the sides that are given are kept and the page asks for the rest.
 */
export function compareFromQuery(query: Query): CompareAddress {
  const named = text(query.compare)
  const by: CompareBy = isCompareBy(named) ? named : (query.periodA || query.periodB) ? 'periods' : 'stations'
  const ids = text(query.stations).split(',').map(id => id.trim()).filter(Boolean)
  const resolution = isCompareResolution(query.resolution) ? query.resolution : 'daily'
  const parameter = text(query.parameter)
  const address: CompareAddress = { by, resolution, stations: ids.slice(0, by === 'stations' ? 2 : 1) }
  // a parameter is a canonical name: lower case words and digits, nothing else is sent to the backend
  if (/^[a-z][a-z0-9_]*$/.test(parameter))
    address.parameter = parameter
  if (by === 'stations') {
    const start = text(query.startDate)
    const end = text(query.endDate)
    const period = readPeriod(`${start}/${end}`)
    if (period)
      address.period = period
  }
  else {
    const a = readPeriod(query.periodA)
    const b = readPeriod(query.periodB)
    if (a)
      address.periodA = a
    if (b)
      address.periodB = b
  }
  return address
}

/** The query the comparison writes into the address: `compareFromQuery` reads it back as it was */
export function compareToQuery(address: CompareAddress): Record<string, string> {
  const query: Record<string, string> = { compare: address.by, resolution: address.resolution }
  if (address.parameter)
    query.parameter = address.parameter
  if (address.stations.length)
    query.stations = address.stations.join(',')
  if (address.by === 'stations') {
    if (address.period) {
      query.startDate = address.period.start
      query.endDate = address.period.end
    }
  }
  else {
    if (address.periodA)
      query.periodA = periodText(address.periodA)
    if (address.periodB)
      query.periodB = periodText(address.periodB)
  }
  return query
}

/** The query keys a comparison owns, which the page takes out of the address when it leaves the mode */
/** Whether the address names everything the comparison needs to be fetched */
export function isComplete(address: CompareAddress): boolean {
  if (!address.parameter)
    return false
  if (address.by === 'stations')
    return address.stations.length === 2 && address.stations[0] !== address.stations[1] && !!address.period
  return address.stations.length === 1 && !!address.periodA && !!address.periodB
}

// -- the rows ---------------------------------------------------------------------------------------------------------

/** A reading as the comparison takes it: the date it is for, and its value (null where the source has none) */
export interface CompareReading {
  /** `YYYY-MM-DD`, the day a daily value is of and the first day of the month for a monthly one */
  date: string
  value: number | null
}

/** One row of the table: the same step of both sides and what is between them */
export interface CompareRow {
  /** The step, from 1: a day or a month of the period */
  step: number
  /** The date of side A and of side B at this step, null where a side's period does not reach it */
  dateA: string | null
  dateB: string | null
  a: number | null
  b: number | null
  /** B minus A; null where either has no value */
  difference: number | null
}

/**
 * B minus A, as plain arithmetic would write it to the precision the values have: null where either side has none (a missing day is
 * not zero), and rounded to ten decimals so that 0.3 − 0.1 is 0.2 and not 0.19999999999999998.
 */
export function difference(a: number | null, b: number | null): number | null {
  if (a === null || b === null || !Number.isFinite(a) || !Number.isFinite(b))
    return null
  const delta = Math.round((b - a) * 1e10) / 1e10
  // no minus zero
  return delta === 0 ? 0 : delta
}

function row(step: number, dateA: string | null, dateB: string | null, a: number | null, b: number | null): CompareRow {
  return { step, dateA, dateB, a, b, difference: difference(a, b) }
}

/** The values of readings by their date; a second reading of a date replaces the first, which a request does not give */
function byDate(readings: readonly CompareReading[]): Map<string, number | null> {
  const map = new Map<string, number | null>()
  for (const reading of readings)
    map.set(reading.date, reading.value)
  return map
}

/**
 * Two stations over one period, aligned by calendar date: a row for every day (or month) of the period, so that a day neither has a
 * value for is a row with two empty cells and no difference, not a day left out.
 */
export function alignStations(a: readonly CompareReading[], b: readonly CompareReading[], period: ComparePeriod, resolution: CompareResolution): CompareRow[] {
  const valuesA = byDate(a)
  const valuesB = byDate(b)
  const length = periodLength(period, resolution)
  return Array.from({ length }, (_, index) => {
    const date = stepOf(period, resolution, index)
    return row(index + 1, date, date, valuesA.get(date) ?? null, valuesB.get(date) ?? null)
  })
}

/**
 * Two periods of one station, aligned by the position in the period: the first day of A with the first day of B. Periods of unequal
 * length have as many rows as the longer one; the steps past the shorter have an empty cell and no difference.
 */
export function alignPeriods(a: readonly CompareReading[], periodA: ComparePeriod, b: readonly CompareReading[], periodB: ComparePeriod, resolution: CompareResolution): CompareRow[] {
  const valuesA = byDate(a)
  const valuesB = byDate(b)
  const lengthA = periodLength(periodA, resolution)
  const lengthB = periodLength(periodB, resolution)
  return Array.from({ length: Math.max(lengthA, lengthB) }, (_, index) => {
    const dateA = index < lengthA ? stepOf(periodA, resolution, index) : null
    const dateB = index < lengthB ? stepOf(periodB, resolution, index) : null
    return row(index + 1, dateA, dateB, dateA ? valuesA.get(dateA) ?? null : null, dateB ? valuesB.get(dateB) ?? null : null)
  })
}

/** The readings of a request's rows that belong to a station, as the comparison takes them: dated by the day, or the month, they are of */
export function readingsOf(rows: readonly { station_id?: string, timestamp?: unknown, value?: unknown }[], station: string | null, resolution: CompareResolution): CompareReading[] {
  const readings: CompareReading[] = []
  for (const item of rows) {
    if (station !== null && item.station_id !== station)
      continue
    if (typeof item.timestamp !== 'string')
      continue
    const moment = timestampDate(item.timestamp)
    if (!moment)
      continue
    const date = moment.toISOString().slice(0, 10)
    // a month is its first day, whichever day of it the source stamps it at
    const value = typeof item.value === 'number' && Number.isFinite(item.value) ? item.value : null
    readings.push({ date: resolution === 'monthly' ? `${date.slice(0, 7)}-01` : date, value })
  }
  return readings
}

// -- what the two sides are ---------------------------------------------------------------------------------------------

/** What kind of number a side holds, as the answer states it: what is compared must be the same kind */
export interface SideKind {
  resolution: string | null
  dataset: string | null
  parameter: string | null
  unit: string | null
  /** What the value is relative to its interval (`mean`, `sum`, `max`, ...), null where the source does not say */
  aggregation: string | null
  /** Where the timestamp sits in the interval (`start`, `end`, ...): a day that ends at 06:00 is not a day that ends at midnight */
  timestampPosition: string | null
}

/**
 * Why two sides are not the same kind of number, or null where they are. The same dataset of one network makes it rare; it is
 * checked all the same, since a link can carry anything and a table of two columns says they can be subtracted.
 */
export function sidesDiffer(a: SideKind, b: SideKind): CompareRefusal | null {
  if (a.resolution !== b.resolution)
    return 'resolution'
  if (a.dataset !== b.dataset)
    return 'dataset'
  if (a.parameter !== b.parameter)
    return 'parameter'
  if (a.unit !== b.unit)
    return 'unit'
  if (a.aggregation !== b.aggregation)
    return 'aggregation'
  if (a.timestampPosition !== b.timestampPosition)
    return 'position'
  return null
}

/** What `metadata.parameters` of an answer says of a parameter, as far as the comparison reads it */
export interface ParameterMetadata {
  name: string
  unit?: string | null
  aggregation?: string | null
  timestamp_position?: string | null
  resolution?: string | null
  dataset?: string | null
}

/** The kind of number a side holds: from the answer's `metadata.parameters` (the unit, the aggregation, the position of the timestamp) and its rows (the resolution and the dataset) */
export function sideKindOf(parameter: string, metadata: readonly ParameterMetadata[] | null | undefined, rows: readonly { resolution?: unknown, dataset?: unknown, parameter?: unknown }[]): SideKind {
  const info = metadata?.find(item => item.name === parameter) ?? null
  const first = rows.find(item => item.parameter === parameter)
  const word = (value: unknown) => typeof value === 'string' ? value : null
  return {
    resolution: info?.resolution ?? word(first?.resolution),
    dataset: info?.dataset ?? word(first?.dataset),
    parameter: info ? info.name : word(first?.parameter),
    unit: info?.unit ?? null,
    aggregation: info?.aggregation ?? null,
    timestampPosition: info?.timestamp_position ?? null,
  }
}

// -- what the table comes to --------------------------------------------------------------------------------------------

/** The aggregations whose values are added up over the stretch they stand for: a count or a total, where a difference is of totals */
export const SUMMED_AGGREGATIONS: readonly string[] = ['sum', 'count']

/** Whether the values of a parameter are totals or counts (of the day, of the month): what its difference subtracts is then a total */
export function isTotal(aggregation: string | null | undefined): boolean {
  return !!aggregation && SUMMED_AGGREGATIONS.includes(aggregation)
}

export interface CompareSummary {
  /** The rows of the table */
  rows: number
  /** The rows both sides have a value in: the only ones that are compared */
  compared: number
  /** The rows only one side has a value in, or that a period too short does not reach */
  unpaired: number
  /** The mean of A and of B over the compared rows, and the mean of the differences (B − A) */
  meanA: number | null
  meanB: number | null
  meanDifference: number | null
  /** For totals and counts: the sum of A and of B over the compared rows, and the difference of the sums */
  sumA: number | null
  sumB: number | null
  sumDifference: number | null
}

/**
 * The numbers under the table. They are taken over the compared rows alone, the steps both sides have a value for, so that the two
 * means (or sums) are of the same days and their difference is exactly the mean (the sum) of the table's differences.
 */
export function summarize(rows: readonly CompareRow[]): CompareSummary {
  let compared = 0
  let sumA = 0
  let sumB = 0
  for (const item of rows) {
    if (item.difference === null)
      continue
    compared++
    sumA += item.a!
    sumB += item.b!
  }
  const mean = (sum: number) => compared ? Math.round((sum / compared) * 1e10) / 1e10 : null
  return {
    rows: rows.length,
    compared,
    unpaired: rows.length - compared,
    meanA: mean(sumA),
    meanB: mean(sumB),
    meanDifference: compared ? difference(mean(sumA), mean(sumB)) : null,
    sumA: compared ? Math.round(sumA * 1e10) / 1e10 : null,
    sumB: compared ? Math.round(sumB * 1e10) / 1e10 : null,
    sumDifference: compared ? difference(sumA, sumB) : null,
  }
}

// -- the chart --------------------------------------------------------------------------------------------------------

/** The moment a step is drawn at, in ms since the epoch: 00:00 UTC of its date */
export function momentOf(date: string): number {
  return dayNumber(date)! * DAY_MS
}

/**
 * The two series of the chart, as arrays of the chart's own: x in ms since the epoch, and y. Two stations are drawn on their own
 * dates. Two periods are drawn on the dates of side A, step by step: step n of B is at the x of step n of A, a period too short for
 * the longer one carrying A's calendar on (`stepOf` counts past the end). The chart says so in its note; B's own dates are in the
 * legend and the table.
 */
export function chartPoints(rows: readonly CompareRow[], by: CompareBy, periodA: ComparePeriod | undefined, resolution: CompareResolution): { a: { x: number[], y: (number | null)[] }, b: { x: number[], y: (number | null)[] } } {
  const a = { x: [] as number[], y: [] as (number | null)[] }
  const b = { x: [] as number[], y: [] as (number | null)[] }
  for (const item of rows) {
    const x = momentOf(by === 'periods' && periodA ? stepOf(periodA, resolution, item.step - 1) : (item.dateA ?? item.dateB)!)
    if (item.dateA !== null) {
      a.x.push(x)
      a.y.push(item.a)
    }
    if (item.dateB !== null) {
      b.x.push(x)
      b.y.push(item.b)
    }
  }
  return { a, b }
}

// -- what the page holds while the reader is still choosing -------------------------------------------------------------

/** A stretch of days as the date fields hold it: either end may still be empty */
export interface PeriodFields {
  start?: string
  end?: string
}

/**
 * What the page holds of a comparison: the station ids (A, B; for two periods A alone) and the dates as the fields have them. The
 * address is made of what is valid of it (`addressOf`), and an id that is in the link stays in it until the reader changes it,
 * whether or not the list of stations it is looked up in has come.
 */
export interface CompareState {
  by: CompareBy
  resolution: CompareResolution
  parameter?: string
  idA?: string
  idB?: string
  /** The period of both stations (`stations`) */
  period: PeriodFields
  periodA: PeriodFields
  periodB: PeriodFields
}

function fieldsOf(period: ComparePeriod | undefined): PeriodFields {
  return period ? { start: period.start, end: period.end } : {}
}

/** The state a link names */
export function stateOfAddress(address: CompareAddress): CompareState {
  return {
    by: address.by,
    resolution: address.resolution,
    parameter: address.parameter,
    idA: address.stations[0],
    idB: address.by === 'stations' ? address.stations[1] : undefined,
    period: fieldsOf(address.period),
    periodA: fieldsOf(address.periodA),
    periodB: fieldsOf(address.periodB),
  }
}

/** The period of the fields where both are calendar days and the end is not before the start */
export function periodOfFields(fields: PeriodFields): ComparePeriod | undefined {
  return readPeriod(`${fields.start ?? ''}/${fields.end ?? ''}`) ?? undefined
}

/** The address of the state: its ids and the periods that are valid */
export function addressOf(state: CompareState): CompareAddress {
  const stations = [state.idA, state.by === 'stations' ? state.idB : undefined].filter((id): id is string => !!id)
  const address: CompareAddress = { by: state.by, resolution: state.resolution, stations }
  if (state.parameter)
    address.parameter = state.parameter
  if (state.by === 'stations') {
    const period = periodOfFields(state.period)
    if (period)
      address.period = period
  }
  else {
    const a = periodOfFields(state.periodA)
    const b = periodOfFields(state.periodB)
    if (a)
      address.periodA = a
    if (b)
      address.periodB = b
  }
  return address
}
