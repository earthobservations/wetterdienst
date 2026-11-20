import type { StripesReference, StripesReferenceStat, StripesValueItem } from '#shared/types/api'

/**
 * The colour scale of the climate stripes: Ed Hawkins' method, with a fallback for a short record (GH-4157), and the years the
 * stripes of a station are made of (GH-4258). The app calculates it itself, from the annual values of the API: this is the
 * port of the backend's `ui/stripes_scale.py` and of the years' part of `_get_stripes_data` in `ui/core.py`, which phase 2 of
 * GH-4258 removes there. `tests/unit/stripes-scale.test.ts` holds it to the cases the backend's own tests wrote to
 * `tests/ui/stripes_scale.golden.json` (copied to `tests/unit/stripes_scale.golden.json`).
 *
 * The method, as `showyourstripes.info`'s FAQ states it: "For each country, the average temperature in 1971-2000 is set as the
 * boundary between blue and red colours, and the colour scale varies from +/- 2.6 standard deviations of the annual average
 * temperatures between 1901-2000." A year's class is its anomaly to the mean of 1971-2000 in steps of `2.6 / 8` standard
 * deviations of the annual values of 1901-2000, the two outermost classes taking whatever lies beyond. It depends on the
 * station's record and on no window of years: a year keeps its colour whatever years are shown.
 *
 * A station short of either period takes the whole record in its place, for the mean and for the spread each on its own, and
 * says so in the `reference`. The classes count from the lowest value (0) to the highest (15).
 */

/** The years whose mean is the boundary between the blue and the red classes */
export const CENTRE_PERIOD = [1971, 2000] as const
/** The years whose standard deviation sets the width of the classes */
export const SPREAD_PERIOD = [1901, 2000] as const
/** The scale reaches this many standard deviations to either side of the centre */
export const RANGE_SIGMA = 2.6
/** 8 classes below the centre and 8 above */
export const CLASSES = 16
/** A class is this many standard deviations wide */
export const CLASS_SIGMA = RANGE_SIGMA / (CLASSES / 2)

/** The fewest years with data a period needs to stand for its reference, else the whole record does: 20 of the 30 years of 1971-2000 for the mean ... */
export const MIN_CENTRE_YEARS = 20
/** ... and 30 of the 100 years of 1901-2000 for the standard deviation */
export const MIN_SPREAD_YEARS = 30
/** The fewest years with data a record needs for a scale of its own: a standard deviation of fewer is no spread */
export const MIN_RECORD_YEARS = 10

/**
 * The exact sum of numbers, correctly rounded, as Python's `math.fsum` (Shewchuk's algorithm), which the backend sums with:
 * a plain loop is off by a few units in the last place, which a class that is floored can turn on.
 */
export function fsum(numbers: readonly number[]): number {
  const partials: number[] = []
  for (const number of numbers) {
    let x = number
    let used = 0
    for (let i = 0; i < partials.length; i++) {
      let y = partials[i]!
      if (Math.abs(x) < Math.abs(y)) {
        const swap = x
        x = y
        y = swap
      }
      const high = x + y
      const low = y - (high - x)
      if (low)
        partials[used++] = low
      x = high
    }
    partials.length = used
    partials.push(x)
  }
  // the partials do not overlap, the smallest first: summed from the largest, the first inexact step is the rounding
  let index = partials.length
  if (index === 0)
    return 0
  let total = partials[--index]!
  let low = 0
  while (index > 0) {
    const x = total
    const y = partials[--index]!
    total = x + y
    low = y - (total - x)
    if (low)
      break
  }
  // half-even rounding across several partials
  if (index > 0 && ((low < 0 && partials[index - 1]! < 0) || (low > 0 && partials[index - 1]! > 0))) {
    const y = low * 2
    const x = total + y
    if (y === x - total)
      total = x
  }
  return total
}

/** One year of a record: its value, null where it has none */
export interface YearValue {
  year: number
  value: number | null
}

function referenceStat(years: readonly number[], values: readonly number[], period: readonly [number, number], minimum: number, calculate: 'mean' | 'std'): StripesReferenceStat {
  const pairs = years.map((year, index) => [year, values[index]!] as const)
  const inPeriod = pairs.filter(([year]) => year >= period[0] && year <= period[1])
  const fallback = inPeriod.length < minimum
  const chosen = fallback ? pairs : inPeriod
  const numbers = chosen.map(([, value]) => value)
  const mean = fsum(numbers) / numbers.length
  // the sample standard deviation: an estimate from the years there are
  const value = calculate === 'mean'
    ? mean
    : numbers.length > 1 ? Math.sqrt(fsum(numbers.map(n => (n - mean) * (n - mean))) / (numbers.length - 1)) : 0
  return {
    value,
    first_year: Math.min(...chosen.map(([year]) => year)),
    last_year: Math.max(...chosen.map(([year]) => year)),
    years: chosen.length,
    fallback,
  }
}

/**
 * The reference of a station's whole record of annual values (the years with data, not any window): the mean of 1971-2000 is
 * the centre where that period holds `MIN_CENTRE_YEARS` years, and the standard deviation of 1901-2000 the spread where it
 * holds `MIN_SPREAD_YEARS`; the whole record takes the place of whichever is short. The caller refuses a record shorter than
 * `MIN_RECORD_YEARS`.
 *
 * @param years - The years with data
 * @param values - Their values, one for each year
 */
export function stripesReference(years: readonly number[], values: readonly number[]): StripesReference {
  return {
    centre: referenceStat(years, values, CENTRE_PERIOD, MIN_CENTRE_YEARS, 'mean'),
    spread: referenceStat(years, values, SPREAD_PERIOD, MIN_SPREAD_YEARS, 'std'),
    range_sigma: RANGE_SIGMA,
    classes: CLASSES,
  }
}

/**
 * The class of a value, 0 (the lowest) to 15: its anomaly in steps of `CLASS_SIGMA` standard deviations. The centre is the
 * boundary between the 8th class and the 9th: a value equal to it is in the 9th (the lowest of the upper half). What lies
 * beyond 2.6 standard deviations takes the end class. A spread of 0 (every year alike) puts a value that differs at the end it
 * lies at.
 */
export function stripeClass(value: number, reference: StripesReference): number {
  const anomaly = value - reference.centre.value
  const sigma = reference.spread.value
  const position = sigma <= 0
    ? (anomaly ? Math.sign(anomaly) * Infinity : 0)
    : Math.floor(anomaly / sigma / CLASS_SIGMA)
  return Math.min(CLASSES - 1, Math.max(0, CLASSES / 2 + position))
}

/** A number rounded to `decimals` places, halves away from zero, as polars' `round` does (`round(4)` of the anomalies) */
export function roundHalfAway(value: number, decimals: number): number {
  const factor = 10 ** decimals
  return Math.sign(value) * Math.round(Math.abs(value) * factor) / factor
}

/** The token a soft plausibility check writes in a reading's `quality_flags` (`suspect:source`) */
const SUSPECT_TOKEN = /(?:^|,)suspect:/

/**
 * Whether a soft plausibility check flagged a reading `suspect:` (GH-3676): a number that a check finds implausible has no place
 * in the years, whatever mode the request gave the check; the reading stays a row, as a rejected one does, with no value.
 */
export function isSuspect(qualityFlags: string | null | undefined): boolean {
  return !!qualityFlags && SUSPECT_TOKEN.test(qualityFlags)
}

/** 1 January 00:00 UTC of a year, as the API writes a timestamp */
export function yearTimestamp(year: number): string {
  return `${String(year).padStart(4, '0')}-01-01T00:00:00.000000+00:00`
}

/** One entry of the `errors` of a refusal: where it is and what it says, as the API's 422 lists them */
interface RefusalEntry {
  loc: string[]
  msg: string
}

/**
 * Why the stripes of a station cannot be made, written as the REST API writes its refusals (an RFC 9457 problem and the status
 * it came with) so that the app tells it as any other failure of a request (`describeFetchError`) and the map's panel reads it
 * as "no stripes" (a 400, 404 or 422).
 */
export class StripesRefusedError extends Error {
  statusCode: number
  statusMessage: string
  data: { type: string, title: string, status: number, detail: string, errors?: RefusalEntry[] }

  constructor(statusCode: 400 | 404 | 422, detail: string, errors?: RefusalEntry[]) {
    super(detail)
    this.name = 'StripesRefusedError'
    this.statusCode = statusCode
    this.statusMessage = { 400: 'Bad Request', 404: 'Not Found', 422: 'Unprocessable Content' }[statusCode]
    const kind = { 400: 'request-refused', 404: 'not-found', 422: 'invalid-parameters' }[statusCode]
    this.data = { type: `urn:wetterdienst:problem:${kind}`, title: this.statusMessage, status: statusCode, detail, ...(errors ? { errors } : {}) }
  }
}

/**
 * Refuse a window of years whose end does not follow its start, before anything is read for it, as the API's validation
 * answered it: a 422 that names `end_year`.
 *
 * @throws {StripesRefusedError} The window is no window
 */
export function checkStripesWindow(startYear: number | null | undefined, endYear: number | null | undefined): void {
  if (startYear != null && endYear != null && endYear <= startYear) {
    const msg = `Input should be greater than start_year (${startYear})`
    throw new StripesRefusedError(422, `end_year: ${msg}`, [{ loc: ['query', 'end_year'], msg }])
  }
}

/**
 * The years of a station's stripes, from its record of annual values, as the backend made them (`_get_stripes_data`).
 *
 * The record is the years with a value, in any order; a value that is no finite number is no year with data (it would make the
 * reference NaN, and the class of every year with it). The years run from the first to the last that has a value inside the
 * window, a year in between with none a gap (a row with no value, which the chart draws as one): a start or end year that falls
 * in a gap of the record does not label the stripes with a year none of them shows. The classes are relative to the whole
 * record, never to the window, so a year keeps its colour whatever `startYear` and `endYear` show, and is the same in any unit.
 *
 * @param record - The station's years, with the ones without a value as `null`
 * @param options - The window of years (`startYear`, `endYear`: both inclusive, the second after the first) and the station's id, which the refusals name
 * @param options.stationId - The station's id
 * @param options.startYear - The first year to show
 * @param options.endYear - The last year to show
 * @returns The values of every year of the window, and the reference of the whole record
 * @throws {StripesRefusedError} A window whose end does not follow its start (422), a window with fewer than two years with data, or a record with fewer than `MIN_RECORD_YEARS` (400)
 */
export function stripesFromRecord(
  record: readonly YearValue[],
  options: { stationId: string, startYear?: number | null, endYear?: number | null },
): { values: StripesValueItem[], reference: StripesReference } {
  const { stationId } = options
  const startYear = options.startYear ?? null
  const endYear = options.endYear ?? null
  checkStripesWindow(startYear, endYear)

  const byYear = new Map<number, number | null>()
  for (const item of record)
    byYear.set(item.year, item.value !== null && Number.isFinite(item.value) ? item.value : null)
  const recorded = [...byYear.entries()].filter((entry): entry is [number, number] => entry[1] !== null).sort((a, b) => a[0] - b[0])

  const inWindow = recorded.filter(([year]) => (startYear === null || year >= startYear) && (endYear === null || year <= endYear))
  if (inWindow.length < 2) {
    const text = recorded.length ? `from ${recorded[0]![0]} to ${recorded.at(-1)![0]}` : 'for no year'
    throw new StripesRefusedError(400, `At least two years with data are required to create climate stripes; station ${stationId} has data ${text}`)
  }
  if (recorded.length < MIN_RECORD_YEARS)
    throw new StripesRefusedError(400, `At least ${MIN_RECORD_YEARS} years with data are required to scale climate stripes; station ${stationId} has data for ${recorded.length} (from ${recorded[0]![0]} to ${recorded.at(-1)![0]})`)

  const reference = stripesReference(recorded.map(([year]) => year), recorded.map(([, value]) => value))
  const first = inWindow[0]![0]
  const last = inWindow.at(-1)![0]
  const values: StripesValueItem[] = []
  for (let year = first; year <= last; year++) {
    const value = byYear.get(year) ?? null
    values.push({
      timestamp: yearTimestamp(year),
      value,
      anomaly: value === null ? null : roundHalfAway(value - reference.centre.value, 4),
      stripe_class: value === null ? null : stripeClass(value, reference),
    })
  }
  return { values, reference }
}
