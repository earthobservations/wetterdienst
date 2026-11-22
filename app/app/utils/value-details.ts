import type { Aggregation } from '#shared/types/api'
import { field, fieldText } from './values-export'

// The Explorer's value details (GH-4296): count, min, max, mean and sum of the values shown, of each parameter and, where
// stations were asked for, of each station, with the difference of two. Pure: the table and the tests read it from here.

/** What the answer says of a parameter (`metadata.parameters` of a `with_metadata` answer): the unit its values are in, and what they are relative to their interval */
export interface ParameterFact {
  dataset: string
  /** The canonical name */
  name: string
  /** The name the source gives it, which the rows carry where the answer is not humanized */
  name_original?: string | null
  unit?: string | null
  aggregation?: Aggregation | null
}

/** A station of the request, in the order the picker lists it */
export interface DetailStation {
  /** `''` for the values that are no station's: a point's, or those a query left the station out of */
  id: string
  name: string | null
}

/** One station's numbers of one parameter; `count` 0 and the rest null where it has no value of it */
export interface DetailRow {
  station: DetailStation
  count: number
  min: number | null
  max: number | null
  mean: number | null
  /** Null where the parameter is no amount that adds up (`sums` of its group), as well as where the station has no value */
  sum: number | null
}

/** The second station's numbers less the first's, each null where either has none */
export interface DetailDifference {
  min: number | null
  max: number | null
  mean: number | null
  sum: number | null
  /** The difference of the sums as a fraction of the first's (0.1 is +10 %); null where the first is 0 or has none */
  sumShare: number | null
}

export interface DetailGroup {
  dataset: string
  parameter: string
  /** The unit of the values, where the answer names it */
  unit: string | null
  /** Whether the sum is shown: the parameter's `aggregation` is `sum` or `count` */
  sums: boolean
  rows: DetailRow[]
  /** Of exactly two stations, the second less the first */
  difference: DetailDifference | null
}

export interface ValueDetails {
  /** Whether the rows are by station: the values of stations asked for, and not a point's or a query's */
  split: boolean
  stations: DetailStation[]
  groups: DetailGroup[]
}

/**
 * The aggregations whose values add up to a total of the period: a rainfall or a sunshine duration (`sum`), the number of
 * hours or days of something (`count`). A mean, a reading, a maximum or a minimum added up means nothing, and so does an
 * aggregation the answer does not state: never guessed from a name.
 */
const SUMMED: ReadonlySet<string> = new Set<Aggregation>(['sum', 'count'])

export function sumsUp(aggregation: string | null | undefined): boolean {
  return aggregation != null && SUMMED.has(aggregation)
}

interface Running {
  count: number
  min: number
  max: number
  sum: number
}

function difference(first: DetailRow, second: DetailRow, sums: boolean): DetailDifference {
  const less = (a: number | null, b: number | null) => a === null || b === null ? null : b - a
  const sum = sums ? less(first.sum, second.sum) : null
  return {
    min: less(first.min, second.min),
    max: less(first.max, second.max),
    mean: less(first.mean, second.mean),
    sum,
    sumShare: sum !== null && first.sum !== null && first.sum !== 0 ? sum / Math.abs(first.sum) : null,
  }
}

/**
 * The details of the rows shown. Statistics are taken of long rows alone, those that carry a parameter and a value,
 * numeric or missing: a wide-shaped row (a column per parameter) and a query's own columns (`avg_value`) carry none.
 *
 * `split` takes them by station, the stations of the request first in their order and any other the rows name after
 * them, with each of the stations in every parameter's group, empty where it has no value, so that the stations compare
 * row by row. A point's rows (interpolation, summary) are one series, and so are rows that carry no station.
 *
 * @param rows - The rows shown
 * @param options - what to split by
 * @param options.split - Whether to take the rows by station
 * @param options.stations - The stations of the request, in the order listed
 * @param options.parameters - The answer's own facts of its parameters
 */
export function valueDetails(
  rows: readonly object[],
  options: { split: boolean, stations: readonly DetailStation[], parameters: readonly ParameterFact[] },
): ValueDetails {
  // a running count, min, max and sum: spreading the values into Math.min/max throws past the
  // engine's argument limit (about 120k in V8, 65,536 in JavaScriptCore)
  const running = new Map<string, Map<string, Running>>()
  const parameters = new Map<string, { dataset: string, parameter: string }>()
  const seen: string[] = []

  for (const row of rows) {
    const parameter = field(row, 'parameter')
    const value = field(row, 'value')
    if (typeof parameter !== 'string' || (typeof value !== 'number' && value !== null))
      continue
    // as the table shows it: a query may leave the dataset out, or give one of its own, a year
    const dataset = fieldText(field(row, 'dataset'))
    const station = options.split ? fieldText(field(row, 'station_id')) : ''
    const key = `${dataset}/${parameter}`
    parameters.set(key, { dataset, parameter })
    let ofStation = running.get(key)
    if (!ofStation)
      running.set(key, ofStation = new Map())
    let entry = ofStation.get(station)
    if (!entry) {
      ofStation.set(station, entry = { count: 0, min: Infinity, max: -Infinity, sum: 0 })
      if (!seen.includes(station))
        seen.push(station)
    }
    if (value !== null) {
      entry.count++
      entry.min = Math.min(entry.min, value)
      entry.max = Math.max(entry.max, value)
      entry.sum += value
    }
  }

  // by station where the rows say which, else one series
  const split = options.split && seen.some(id => id !== '')
  const stations: DetailStation[] = split
    ? [...options.stations.filter(({ id }) => id !== ''), ...seen.filter(id => id !== '' && !options.stations.some(station => station.id === id)).map(id => ({ id, name: null }))]
    : [{ id: '', name: null }]
  // the rows of a query that left the station out of some of them are one more series, last
  if (split && seen.includes(''))
    stations.push({ id: '', name: null })

  const facts = new Map<string, ParameterFact>()
  for (const fact of options.parameters) {
    facts.set(`${fact.dataset}/${fact.name}`, fact)
    if (fact.name_original)
      facts.set(`${fact.dataset}/${fact.name_original}`, fact)
  }

  const groups: DetailGroup[] = []
  for (const [key, { dataset, parameter }] of [...parameters].sort(([a], [b]) => a.localeCompare(b))) {
    const fact = facts.get(key)
    const sums = sumsUp(fact?.aggregation)
    const rowsOf = stations.map((station): DetailRow => {
      const entry = running.get(key)?.get(station.id)
      if (!entry || entry.count === 0)
        return { station, count: 0, min: null, max: null, mean: null, sum: null }
      return { station, count: entry.count, min: entry.min, max: entry.max, mean: entry.sum / entry.count, sum: sums ? entry.sum : null }
    })
    groups.push({
      dataset,
      parameter,
      unit: fact?.unit ?? null,
      sums,
      rows: rowsOf,
      difference: split && rowsOf.length === 2 ? difference(rowsOf[0]!, rowsOf[1]!, sums) : null,
    })
  }

  return { split, stations, groups }
}
