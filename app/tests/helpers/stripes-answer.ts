/**
 * The stripes the app makes for a station's record, written out for the tests' fixtures: the reference (the mean of 1971-2000
 * and the standard deviation of 1901-2000, the whole record where the station has too few years in them) and each year's
 * anomaly and class (GH-4157). It is made by the app's own functions (`app/utils/stripes-scale.ts`, GH-4258), which
 * `tests/unit/stripes-scale.test.ts` holds to the cases of the backend's own test. Unlike `stripesFromRecord` it refuses no
 * short record, since the chart's fixtures are often of a few years.
 */
import type { StripesReference, StripesValueItem } from '#shared/types/api'
import type { YearValue } from '../../app/utils/stripes-scale'
import { roundHalfAway, stripeClass, stripesReference, yearTimestamp } from '../../app/utils/stripes-scale'

export type { YearValue }

/** The reference of a record: its years with a value */
export function referenceOf(values: YearValue[]): StripesReference {
  const drawn = values.filter((item): item is { year: number, value: number } => item.value !== null)
  return stripesReference(drawn.map(item => item.year), drawn.map(item => item.value))
}

/** The class of a value, 0 to 15 */
export const classOf = stripeClass

/**
 * The stripes of a record, as far as the app reads them: the values with their anomaly and class, from a reference calculated
 * over the whole record. `start` and `end` cut the years returned and change nothing of the classes.
 */
export function stripesAnswer(record: YearValue[], window: { start?: number, end?: number } = {}): { values: StripesValueItem[], reference: StripesReference } {
  const reference = referenceOf(record)
  const values = record
    .filter(item => item.year >= (window.start ?? -Infinity) && item.year <= (window.end ?? Infinity))
    .map(item => ({
      timestamp: yearTimestamp(item.year),
      value: item.value,
      anomaly: item.value === null ? null : roundHalfAway(item.value - reference.centre.value, 4),
      stripe_class: item.value === null ? null : stripeClass(item.value, reference),
    }))
  return { values, reference }
}

/** A record of the years `first` to `last`, a value for each from `valueOf` (the years in `gaps` have none) */
export function recordOf(first: number, last: number, valueOf: (year: number) => number, gaps: number[] = []): YearValue[] {
  return Array.from({ length: last - first + 1 }, (_, index) => first + index)
    .map(year => ({ year, value: gaps.includes(year) ? null : valueOf(year) }))
}
