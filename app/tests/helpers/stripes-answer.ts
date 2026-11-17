/**
 * What the backend answers for a station's stripes, written out for the tests' fixtures: the reference (the mean of 1971-2000
 * and the standard deviation of 1901-2000, the whole record where the station has too few years in them) and each year's
 * anomaly and class (GH-4157). The app calculates none of this: the page reads it from the answer. This is a port of
 * `wetterdienst/ui/stripes_scale.py` for fixtures, which `tests/unit/stripes-answer.test.ts` holds to the cases the backend's
 * own test (`tests/ui/test_stripes_scale.py`) writes to `tests/ui/stripes_scale.golden.json`.
 */
import type { StripesReference, StripesValueItem } from '#shared/types/api'

const CENTRE_PERIOD = [1971, 2000] as const
const SPREAD_PERIOD = [1901, 2000] as const
const MIN_CENTRE_YEARS = 20
const MIN_SPREAD_YEARS = 30
const RANGE_SIGMA = 2.6
const CLASSES = 16

export interface YearValue {
  year: number
  value: number | null
}

function statOf(drawn: YearValue[], period: readonly [number, number], minimum: number, calculate: 'mean' | 'std') {
  const inPeriod = drawn.filter(item => item.year >= period[0] && item.year <= period[1])
  const fallback = inPeriod.length < minimum
  const chosen = fallback ? drawn : inPeriod
  const numbers = chosen.map(item => item.value!)
  const mean = numbers.reduce((sum, value) => sum + value, 0) / numbers.length
  const value = calculate === 'mean'
    ? mean
    : numbers.length > 1 ? Math.sqrt(numbers.reduce((sum, n) => sum + (n - mean) ** 2, 0) / (numbers.length - 1)) : 0
  return {
    value,
    first_year: Math.min(...chosen.map(item => item.year)),
    last_year: Math.max(...chosen.map(item => item.year)),
    years: chosen.length,
    fallback,
  }
}

/** The reference of a record: its years with a value */
export function referenceOf(values: YearValue[]): StripesReference {
  const drawn = values.filter(item => item.value !== null)
  return {
    centre: statOf(drawn, CENTRE_PERIOD, MIN_CENTRE_YEARS, 'mean'),
    spread: statOf(drawn, SPREAD_PERIOD, MIN_SPREAD_YEARS, 'std'),
    range_sigma: RANGE_SIGMA,
    classes: CLASSES,
  }
}

/** The class of a value, 0 to 15: its anomaly in steps of `RANGE_SIGMA / 8` standard deviations, the end classes taking what lies beyond */
export function classOf(value: number, reference: StripesReference): number {
  const anomaly = value - reference.centre.value
  const sigma = reference.spread.value
  const position = sigma <= 0
    ? (anomaly === 0 ? 0 : Math.sign(anomaly) * Infinity)
    : Math.floor(anomaly / sigma / (RANGE_SIGMA / (CLASSES / 2)))
  return Math.min(CLASSES - 1, Math.max(0, CLASSES / 2 + position))
}

/**
 * The answer of `/api/stripes/values` for a record, as far as the app reads it: the values with their anomaly and class, from
 * a reference calculated over the whole record. `start` and `end` cut the years returned and change nothing of the classes.
 */
export function stripesAnswer(record: YearValue[], window: { start?: number, end?: number } = {}): { values: StripesValueItem[], reference: StripesReference } {
  const reference = referenceOf(record)
  const values = record
    .filter(item => item.year >= (window.start ?? -Infinity) && item.year <= (window.end ?? Infinity))
    .map(item => ({
      timestamp: `${item.year}-01-01T00:00:00+00:00`,
      value: item.value,
      anomaly: item.value === null ? null : Math.round((item.value - reference.centre.value) * 1e4) / 1e4,
      stripe_class: item.value === null ? null : classOf(item.value, reference),
    }))
  return { values, reference }
}

/** A record of the years `first` to `last`, a value for each from `valueOf` (the years in `gaps` have none) */
export function recordOf(first: number, last: number, valueOf: (year: number) => number, gaps: number[] = []): YearValue[] {
  return Array.from({ length: last - first + 1 }, (_, index) => first + index)
    .map(year => ({ year, value: gaps.includes(year) ? null : valueOf(year) }))
}
