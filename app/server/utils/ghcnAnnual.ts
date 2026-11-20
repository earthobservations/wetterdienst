import { isSuspect, roundHalfAway, yearTimestamp } from '../../app/utils/stripes-scale'

// The annual values of the climate stripes for a source that publishes days only: NOAA GHCN daily (GH-4222, moved to the app's
// server by GH-4258). The port of the backend's `ui/stripes_annual.py`, which phase 2 of GH-4258 removes there;
// `tests/unit/stripes-annual.test.ts` holds it to that module's own tests.
//
// DWD publishes annual values, which the stripes read as they are. GHCN-Daily has daily values only, so the year is built
// from the days, by the rules of the WMO Guidelines on the Calculation of Climate Normals (WMO-No. 1203):
//
// - Temperature: a month counts with at most `MAX_MISSING_DAYS` days missing and at most `MAX_MISSING_IN_A_ROW` of them in a
//   row. A day's mean is the midrange (TMAX + TMIN) / 2, and a day without both TMAX and TMIN is missing. The month's mean
//   is the mean of the days' means, and a year with all 12 months counting is the mean of the 12 monthly means (each month
//   weighs the same, whatever its length).
// - Precipitation: a month counts only when complete, every one of its days has a value. A year with all 12 months counting
//   is the sum of the 12 monthly sums.
// - A year that fails is a gap, as a year DWD has no value for is, and is never filled.
//
// The midrange is no 24-hour mean, and it is used for every day, never mixed with the source's TAVG: GHCN's TAVG covers only
// part of most records (mostly the 1990s on) and differs systematically from the midrange (at Los Angeles the recent years
// read about 0.4 degrees cooler by it), so a series that took TAVG where it is given and the midrange elsewhere would change
// its method along the record and show it as a false step. A steady method matters more for the anomalies than the accuracy
// of each day: a constant bias cancels against the station's own reference. TAVG is used only at a station whose data has no
// day with both TMAX and TMIN (`temperatureMethod`), for every day. That is decided from the days that were read, not from
// the inventory of the station, whose spans of TAVG are stale.
//
// A day the source has no row for, or whose value is null, is missing: that is what a station that did not report looks like
// in the daily files. A value whose quality flag names a check it failed (`leaveOutFailed`) is no value either, as the readme
// of GHCN-Daily asks for.

/** A month counts for the temperature with no more than this many days missing, ... */
export const MAX_MISSING_DAYS = 10
/** ... and no more than this many of them in a row */
export const MAX_MISSING_IN_A_ROW = 4
/** A year counts with all of its months */
export const MONTHS = 12
/** The decimals of an annual value: the source's tenths, averaged */
export const DECIMALS = 3

export const TEMPERATURE_MEAN = 'temperature_air_mean_2m'
export const TEMPERATURE_MAX = 'temperature_air_max_2m'
export const TEMPERATURE_MIN = 'temperature_air_min_2m'
export const PRECIPITATION = 'precipitation_amount'

export type AnnualKind = 'temperature' | 'precipitation'
/** How the days of a temperature series were calculated: the midrange of TMAX and TMIN, or the source's TAVG */
export type DayMethod = 'midrange' | 'tavg'

/** One reading of the long frame `/api/values` gives for a station: `timestamp` is the day, at 00:00 */
export interface DailyRow {
  parameter: string
  timestamp: string
  value: number | null
  quality_flags?: string | null
}

/** One year of the annual values: its value, null where the year fails the rules */
export interface AnnualYear {
  year: number
  value: number | null
}

/**
 * A plain code in `quality_flags` (the source's own quality flag, one that is no `kind:code` token) is a check the value
 * failed: GHCN-Daily writes a letter only where one failed, and blank where it passed all
 */
const FAILED_CHECK = /(?:^|,)[^,:]+(?:,|$)/

/** The rows with the value nulled where `flagged` holds of the row's quality flags: the rows themselves stay */
function nullWhere(rows: readonly DailyRow[], flagged: (flags: string) => boolean): DailyRow[] {
  return rows.map(row => row.quality_flags && flagged(row.quality_flags) ? { ...row, value: null } : row)
}

/**
 * Null the value of every reading a soft plausibility check flagged `suspect:` (GH-3676): a number that a check finds
 * implausible has no place in the years, whatever mode the request gave the check. The reading stays a row, as a rejected one
 * does, with no value.
 */
export function leaveOutSuspect(rows: readonly DailyRow[]): DailyRow[] {
  return nullWhere(rows, isSuspect)
}

/** Null the value of every reading whose quality flag names a check it failed */
export function leaveOutFailed(rows: readonly DailyRow[]): DailyRow[] {
  return nullWhere(rows, flags => FAILED_CHECK.test(flags))
}

/** The days of a temperature series: for each date, the value of each of TAVG, TMAX and TMIN, null where it has none */
interface WideDay {
  [TEMPERATURE_MEAN]: number | null
  [TEMPERATURE_MAX]: number | null
  [TEMPERATURE_MIN]: number | null
}

const finiteOrNull = (value: number | null): number | null => value !== null && Number.isFinite(value) ? value : null
const dateOf = (row: DailyRow): string => row.timestamp.slice(0, 10)

/** A value that is no finite number is left null; of several rows of one date and parameter the first is taken */
function wide(rows: readonly DailyRow[]): Map<string, WideDay> {
  const days = new Map<string, WideDay>()
  const seen = new Set<string>()
  for (const row of rows) {
    if (row.parameter !== TEMPERATURE_MEAN && row.parameter !== TEMPERATURE_MAX && row.parameter !== TEMPERATURE_MIN)
      continue
    const date = dateOf(row)
    let day = days.get(date)
    if (!day) {
      day = { [TEMPERATURE_MEAN]: null, [TEMPERATURE_MAX]: null, [TEMPERATURE_MIN]: null }
      days.set(date, day)
    }
    // the first row of a date and parameter, a null one included, as the pivot of the backend takes it
    const key = `${date}|${row.parameter}`
    if (!seen.has(key)) {
      seen.add(key)
      day[row.parameter] = finiteOrNull(row.value)
    }
  }
  return days
}

function methodOf(days: Map<string, WideDay>): DayMethod | null {
  let mean = false
  for (const day of days.values()) {
    if (day[TEMPERATURE_MAX] !== null && day[TEMPERATURE_MIN] !== null)
      return 'midrange'
    if (day[TEMPERATURE_MEAN] !== null)
      mean = true
  }
  return mean ? 'tavg' : null
}

/**
 * Say which method the days of a temperature series are calculated by, from the days that were read: the midrange of TMAX and
 * TMIN where the station has a day with both, else its TAVG where it has one, else null.
 */
export function temperatureMethod(rows: readonly DailyRow[]): DayMethod | null {
  return rows.length === 0 ? null : methodOf(wide(rows))
}

/** One value per day, as epoch days to values, null for a day the source has no usable value of */
function dailyValues(rows: readonly DailyRow[], kind: AnnualKind): Map<string, number | null> {
  if (kind === 'precipitation') {
    const days = new Map<string, number | null>()
    for (const row of rows) {
      if (row.parameter === PRECIPITATION && !days.has(dateOf(row)))
        days.set(dateOf(row), finiteOrNull(row.value))
    }
    return days
  }
  const days = wide(rows)
  const tavg = methodOf(days) === 'tavg'
  const values = new Map<string, number | null>()
  for (const [date, day] of days) {
    if (tavg) {
      values.set(date, day[TEMPERATURE_MEAN])
    }
    else {
      const high = day[TEMPERATURE_MAX]
      const low = day[TEMPERATURE_MIN]
      values.set(date, high === null || low === null ? null : (high + low) / 2)
    }
  }
  return values
}

const DAY_MS = 86_400_000
const epochDay = (year: number, month: number, day: number): number => Date.UTC(year, month - 1, day) / DAY_MS
const daysInMonth = (year: number, month: number): number => new Date(Date.UTC(year, month, 0)).getUTCDate()

/**
 * Build the annual values of one station from its daily values, by the WMO rules of this module.
 *
 * `rows` is the long frame of the station's values (`parameter` with the canonical names of `TEMPERATURE_MEAN`,
 * `TEMPERATURE_MAX` and `TEMPERATURE_MIN`, or `PRECIPITATION`; `timestamp`, the day, and `value`, in the unit wanted: the mean
 * of a unit that is a linear change of another is that unit's, so the conversion can come first).
 *
 * @param rows - The station's days
 * @param kind - The annual mean temperature, or the annual precipitation sum
 * @returns Every year from the first to the last the daily values have a value in, the value null where the year fails; empty for no days
 */
export function annualFromDaily(rows: readonly DailyRow[], kind: AnnualKind): AnnualYear[] {
  if (rows.length === 0)
    return []
  // the years run from the first day with a usable value to the last: a station that has rows of other parameters only has
  // no years
  const usable: Array<[number, number]> = []
  for (const [date, value] of dailyValues(rows, kind)) {
    if (value !== null)
      usable.push([epochDay(Number(date.slice(0, 4)), Number(date.slice(5, 7)), Number(date.slice(8, 10))), value])
  }
  if (usable.length === 0)
    return []
  let first = Infinity
  let last = -Infinity
  for (const [day] of usable) {
    first = Math.min(first, day)
    last = Math.max(last, day)
  }
  const firstYear = new Date(first * DAY_MS).getUTCFullYear()
  const lastYear = new Date(last * DAY_MS).getUTCFullYear()
  // every day of every year between, so that a day without a row is a missing one, and a year not complete in the record (the
  // first, the one still running) fails
  const origin = epochDay(firstYear, 1, 1)
  const calendar = new Float64Array(epochDay(lastYear, 12, 31) - origin + 1).fill(Number.NaN)
  for (const [day, value] of usable)
    calendar[day - origin] = value

  const years: AnnualYear[] = []
  for (let year = firstYear; year <= lastYear; year++) {
    let counting = 0
    let total = 0
    for (let month = 1; month <= 12; month++) {
      const start = epochDay(year, month, 1) - origin
      const length = daysInMonth(year, month)
      let missing = 0
      let longest = 0
      let run = 0
      let sum = 0
      let present = 0
      for (let index = start; index < start + length; index++) {
        const value = calendar[index]!
        if (Number.isNaN(value)) {
          missing++
          run++
          longest = Math.max(longest, run)
        }
        else {
          run = 0
          sum += value
          present++
        }
      }
      // a run over the turn of a month is two, one in each: the runs are counted in their month
      if (kind === 'temperature') {
        if (missing <= MAX_MISSING_DAYS && longest <= MAX_MISSING_IN_A_ROW) {
          counting++
          if (present)
            total += sum / present
        }
      }
      else if (missing === 0) {
        counting++
        total += sum
      }
    }
    const value = counting === MONTHS
      ? roundHalfAway(kind === 'temperature' ? total / counting : total, DECIMALS)
      : null
    years.push({ year, value })
  }
  return years
}

/** The annual values as the answer of the server writes them: a row for every year, at 1 January 00:00 UTC */
export function annualRows(years: readonly AnnualYear[]): Array<{ timestamp: string, value: number | null }> {
  return years.map(item => ({ timestamp: yearTimestamp(item.year), value: item.value }))
}
