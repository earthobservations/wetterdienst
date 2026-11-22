import type { Bar, Reading } from './answers'
import { DateTime } from 'luxon'
import { USUAL_BAND } from './answers'
import { DAY_PARAMETERS } from './day'
import { differenceIn, fromCanonical, toCanonical } from './units'

// The two comparisons of "Ask the weather" (GH-4296): was this month wetter than the same month last year, and is it warmer here than at a
// station nearby. Pure like `answers.ts`: the page fetches, these read, and where the data does not carry an answer they say so (null)
// rather than make one up. What a number is judged by is judged in the canonical unit of its quantity, so a verdict is the same in every
// unit the reader picks. Every figure is one constant that the rule of the chip's explanation (`ask/chips/monthrain.ts`, `nearby.ts`)
// takes its value from, and that rule cites its source or is marked as wetterdienst's own.

/** The daily readings the two questions read, as DWD's daily climate summary names them */
export const MONTH_RAIN_PARAMETER = DAY_PARAMETERS.rain
export const NEARBY_PARAMETER = 'temperature_air_mean_2m'

/** A reading of a station, as `/api/values` answers it for several stations at once */
export interface StationReading extends Reading {
  station_id?: string
}

/** The date of a reading, `YYYY-MM-DD`: the day a daily value is of */
const dayOf = (reading: Reading) => reading.timestamp.slice(0, 10)

/** The values of a parameter by day: a day with no value is left out, so that "no reading" is never zero */
function valuesByDay(readings: readonly Reading[], parameter: string): Map<string, number> {
  const byDay = new Map<string, number>()
  for (const reading of readings) {
    if (reading.parameter === parameter && reading.value !== null && Number.isFinite(reading.value))
      byDay.set(dayOf(reading), reading.value)
  }
  return byDay
}

// ---------------------------------------------------------------------------------------------------------------
// Was this month wetter than the same month last year?
// ---------------------------------------------------------------------------------------------------------------

/**
 * How many days of the month both years must have a reading for, for the month to be compared: a week. With fewer (the first days of a
 * month) the question is about the last complete month instead. Wetterdienst's own line; no source gives one.
 */
export const MONTH_MIN_DAYS = 7

/**
 * "About as wet": the two sums are this near: within a millimetre, or within a tenth of the larger one where that is more. Wetterdienst's
 * own line, as the other bands of the questions are; a month of 100 mm is as wet as one of 108.
 */
export const MONTH_SIMILAR_MM = 1
export const MONTH_SIMILAR_SHARE = 0.1

export type MonthRainVerdict = 'wetter' | 'drier' | 'similar'

export interface MonthRainAnswer {
  verdict: MonthRainVerdict
  /** The month compared, `YYYY-MM`, and the same month a year before */
  month: string
  lastMonth: string
  /** How many days of the month both years have a reading for: the days that were added up */
  days: number
  /** The rain of those days this year and last year, in `unit`, and the first minus the second */
  sum: number
  lastSum: number
  difference: number
  unit: string
  /** The month is the last complete one, because the running one has too few days to compare */
  fallback: boolean
  /** How many days of the running month had a reading in both years, which is what the fallback says it lacked */
  runningDays: number
  /** The two sums as bars: last year's, then this year's, which is marked */
  bars: Bar[]
}

/** The first day `YYYY-MM-01` of the month, and its number of days, of a year and month */
function monthDays(year: number, month: number): number {
  return DateTime.utc(year, month, 1).daysInMonth!
}

/**
 * The days of a month for which this year and the year before both have a reading, and their sums. A day that exists in one year and not
 * in the other (29 February) is no pair and is left out, as is a day with no reading on either side.
 */
function monthSums(byDay: ReadonlyMap<string, number>, year: number, month: number): { days: number, sum: number, lastSum: number } {
  const pad = (n: number) => String(n).padStart(2, '0')
  let days = 0
  let sum = 0
  let lastSum = 0
  for (let day = 1; day <= Math.min(monthDays(year, month), monthDays(year - 1, month)); day++) {
    const now = byDay.get(`${year}-${pad(month)}-${pad(day)}`)
    const before = byDay.get(`${year - 1}-${pad(month)}-${pad(day)}`)
    if (now === undefined || before === undefined)
      continue
    days++
    sum += now
    lastSum += before
  }
  // the sums of tenths of a millimetre, free of the floating point noise
  return { days, sum: Math.round(sum * 1e3) / 1e3, lastSum: Math.round(lastSum * 1e3) / 1e3 }
}

/** Where two sums of rain, in millimetres, are about the same: within `MONTH_SIMILAR_MM` or `MONTH_SIMILAR_SHARE` of the larger */
export function monthRainVerdict(sumMm: number, lastSumMm: number): MonthRainVerdict {
  const band = Math.max(MONTH_SIMILAR_MM, MONTH_SIMILAR_SHARE * Math.max(sumMm, lastSumMm))
  const delta = sumMm - lastSumMm
  if (Math.abs(delta) <= band)
    return 'similar'
  return delta > 0 ? 'wetter' : 'drier'
}

/**
 * This month's rain so far against the same days of the month last year: the daily precipitation of one station. The days compared are
 * those both years have a reading for. Where fewer than `MONTH_MIN_DAYS` of the running month are, the last complete month is compared
 * with the same month a year before it (`fallback`), and where that has too few as well there is no answer.
 */
export function monthRain(readings: readonly Reading[], now: DateTime, unit = 'mm'): MonthRainAnswer | null {
  const byDay = valuesByDay(readings, MONTH_RAIN_PARAMETER)
  const today = now.toUTC()
  const running = monthSums(byDay, today.year, today.month)
  let year = today.year
  let month = today.month
  let { days, sum, lastSum } = running
  let fallback = false
  if (days < MONTH_MIN_DAYS) {
    const previous = today.startOf('month').minus({ months: 1 })
    year = previous.year
    month = previous.month
    ;({ days, sum, lastSum } = monthSums(byDay, year, month))
    fallback = true
  }
  if (days < MONTH_MIN_DAYS)
    return null
  const text = `${year}-${String(month).padStart(2, '0')}`
  const lastText = `${year - 1}-${String(month).padStart(2, '0')}`
  return {
    verdict: monthRainVerdict(toCanonical('precipitation', unit, sum), toCanonical('precipitation', unit, lastSum)),
    month: text,
    lastMonth: lastText,
    days,
    sum,
    lastSum,
    difference: Math.round((sum - lastSum) * 1e3) / 1e3,
    unit,
    fallback,
    runningDays: running.days,
    bars: [
      { key: lastText, label: lastText, value: lastSum },
      { key: text, label: text, value: sum, highlight: true },
    ],
  }
}

// ---------------------------------------------------------------------------------------------------------------
// Is it warmer here than at a station nearby?
// ---------------------------------------------------------------------------------------------------------------

/** The days the two stations are compared over: the last thirty, up to yesterday. Wetterdienst's own window: a month is what "lately" is */
export const NEARBY_WINDOW_DAYS = 30
/** How many of them both stations must have a reading for: two thirds. Wetterdienst's own line */
export const NEARBY_MIN_DAYS = 20
/** How far away a station still counts as nearby, in kilometres: where the weather is still the same weather. Wetterdienst's own line */
export const NEARBY_MAX_KM = 50
/** "About the same": the means are within half a degree, the band the season question calls "as usual" (`USUAL_BAND`) */
export const NEARBY_SAME_BAND = USUAL_BAND

export type NearbyVerdict = 'warmer' | 'cooler' | 'same'

export interface NearbyAnswer {
  verdict: NearbyVerdict
  /** How many days both stations have a reading for: the days that were averaged */
  days: number
  /** The mean air temperature of those days at each station, and here minus there, in `unit` (the difference of two temperatures is in the same unit's degrees) */
  here: number
  there: number
  difference: number
  unit: string
  /** The first and the last day of the window */
  from: string
  to: string
  /** The difference of each day (here minus there), in `unit` */
  bars: Bar[]
}

/** The days of the window: thirty, ending yesterday (the newest day DWD has published is not today's) */
export function nearbyWindow(now: DateTime): { from: string, to: string } {
  const yesterday = now.toUTC().startOf('day').minus({ days: 1 })
  return { from: yesterday.minus({ days: NEARBY_WINDOW_DAYS - 1 }).toISODate()!, to: yesterday.toISODate()! }
}

/** The verdict of a difference of means, in degrees Celsius: the band is the same either side */
export function nearbyVerdict(differenceCelsius: number): NearbyVerdict {
  if (Math.abs(differenceCelsius) <= NEARBY_SAME_BAND)
    return 'same'
  return differenceCelsius > 0 ? 'warmer' : 'cooler'
}

/**
 * The mean air temperature of the last thirty days here and at the other station, over the days both have a reading for. The verdict is
 * judged in degrees Celsius whatever the unit of the answer; the difference is written in that unit's degrees (1 K is 1.8 °F).
 */
export function nearbyWarmer(readings: readonly StationReading[], here: string, there: string, now: DateTime, unit = '°C'): NearbyAnswer | null {
  const { from, to } = nearbyWindow(now)
  const own = (id: string) => valuesByDay(readings.filter(reading => reading.station_id === id), NEARBY_PARAMETER)
  const valuesHere = own(here)
  const valuesThere = own(there)
  const bars: Bar[] = []
  let days = 0
  let sumHere = 0
  let sumThere = 0
  for (let day = DateTime.fromISO(from, { zone: 'utc' }); day.toISODate()! <= to; day = day.plus({ days: 1 })) {
    const date = day.toISODate()!
    const a = valuesHere.get(date)
    const b = valuesThere.get(date)
    if (a === undefined || b === undefined) {
      bars.push({ key: date, label: date, value: null })
      continue
    }
    days++
    sumHere += toCanonical('temperature', unit, a)
    sumThere += toCanonical('temperature', unit, b)
    bars.push({ key: date, label: date, value: Math.round(differenceIn('temperature', unit, toCanonical('temperature', unit, a) - toCanonical('temperature', unit, b)) * 100) / 100 })
  }
  if (days < NEARBY_MIN_DAYS)
    return null
  const meanHere = sumHere / days
  const meanThere = sumThere / days
  return {
    verdict: nearbyVerdict(meanHere - meanThere),
    days,
    here: Math.round(fromCanonical('temperature', unit, meanHere) * 100) / 100,
    there: Math.round(fromCanonical('temperature', unit, meanThere) * 100) / 100,
    difference: Math.round(differenceIn('temperature', unit, meanHere - meanThere) * 100) / 100,
    unit,
    from,
    to,
    bars,
  }
}

/** The days with a reading at both stations of the window, which a chip that has too few says: for the "only N days" line */
export function nearbyDaysWithBoth(readings: readonly StationReading[], here: string, there: string, now: DateTime): number {
  const { from, to } = nearbyWindow(now)
  const own = (id: string) => valuesByDay(readings.filter(reading => reading.station_id === id), NEARBY_PARAMETER)
  const a = own(here)
  const b = own(there)
  let count = 0
  for (const date of a.keys()) {
    if (date >= from && date <= to && b.has(date))
      count++
  }
  return count
}
