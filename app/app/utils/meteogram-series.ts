/**
 * The forecast's values as series, and the grid they are drawn on: what the meteogram's chart, its day cards, its
 * summary and its table are all made from.
 */
import type { Value } from '#shared/types/api'
import { interpSeries, nearestNeighbor, resampleCadenceMs } from './meteogram'

/** One parameter's values in time order: the dates and the values at them */
export interface Series { x: Date[], y: number[] }
/** The series of a forecast by the name of the parameter */
export type SeriesMap = Map<string, Series>

/** The first of `names` that the forecast has a series for (`METEOGRAM_SERIES` lists them in order of preference) */
export function findFirstAvailable(names: readonly string[], available: Set<string>): string | undefined {
  for (const n of names) {
    if (available.has(n))
      return n
  }
  return undefined
}

/** The values of the forecast by parameter, in time order, with the values that hold no number left out */
export function buildSeries(values: Value[]): SeriesMap {
  const series: SeriesMap = new Map()
  for (const v of values) {
    const p = String(v.parameter)
    if (!series.has(p))
      series.set(p, { x: [], y: [] })
    if (v.value !== null && v.value !== undefined) {
      series.get(p)!.x.push(new Date(v.timestamp))
      series.get(p)!.y.push(v.value)
    }
  }
  for (const [, s] of series) {
    const pairs = s.x.map((d, i) => ({ d, y: s.y[i]! })).sort((a, b) => a.d.getTime() - b.d.getTime())
    s.x = pairs.map(p => p.d)
    s.y = pairs.map(p => p.y)
  }
  return series
}

/** Every time any series has a value at, first to last, in ms; empty where the forecast holds none */
export function seriesSpan(series: SeriesMap): { min: number, max: number } | null {
  let min = Number.POSITIVE_INFINITY
  let max = Number.NEGATIVE_INFINITY
  for (const s of series.values()) {
    if (!s.x.length)
      continue
    min = Math.min(min, s.x[0]!.getTime())
    max = Math.max(max, s.x.at(-1)!.getTime())
  }
  return Number.isFinite(min) ? { min, max } : null
}

/**
 * Every series on one grid, hourly and every 3 hours past 5 days (`resampleCadenceMs`): linear between the stamps,
 * and for the series named in `stepKeys` (the precipitation) the value of the nearest stamp, which is no curve.
 */
export function resampleSeries(series: SeriesMap, minTime: number, maxTime: number, stepKeys: Set<string> = new Set()): SeriesMap {
  const cadenceMs = resampleCadenceMs(minTime, maxTime)
  const resampled: SeriesMap = new Map()

  for (const [key, s] of series) {
    const newX: Date[] = []
    const newY: number[] = []
    const startTick = Math.ceil(minTime / cadenceMs) * cadenceMs
    for (let t = startTick; t <= maxTime; t += cadenceMs) {
      const val = stepKeys.has(key) ? nearestNeighbor(s.x, s.y, t) : interpSeries(s.x, s.y, t)
      if (val !== null) {
        newX.push(new Date(t))
        newY.push(val)
      }
    }
    if (newX.length > 0)
      resampled.set(key, { x: newX, y: newY })
  }
  return resampled
}
