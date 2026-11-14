/**
 * The forecast's values as series: what the meteogram's chart, its day cards, its summary and its table are all made from.
 */
import type { Value } from '#shared/types/api'
import { METEOGRAM_SERIES } from './meteogram'

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

/** The steps MOSMIX-SNOW gives every element at, in hours UTC: 00, 03, ..., 21 (it has more for some stations, which are rolling windows) */
export const SNOW_STEP_HOURS = 3

/** Whether a time is one of the steps every snow element is given at: on the hour, at a multiple of three hours UTC */
export function isSnowStep(time: Date): boolean {
  return time.getUTCMinutes() === 0 && time.getUTCSeconds() === 0 && time.getUTCHours() % SNOW_STEP_HOURS === 0
}

/**
 * The snow forecast's series (the three of the snow panel, `METEOGRAM_SERIES.snow*`), kept at the 3-hourly steps and to the span
 * of the forecast they join. DWD gives the new snow, its probabilities and the snow depth at the 00, 03, ..., 21 UTC steps for
 * every station and, for some stations, at further hours: those are windows that overlap the ones before and would be bars
 * on top of each other. The run is its own, so it may start before the forecast it is drawn with or reach past it; what is
 * outside `span` is left out, so that the panel never moves the chart's first and last hour.
 * @param values The values of the snow request
 * @param span The first and last time of the forecast it is drawn with, in ms
 */
export function snowSeries(values: Value[], span: { min: number, max: number } | null): SeriesMap {
  const wanted = new Set<string>([...METEOGRAM_SERIES.snowNew, ...METEOGRAM_SERIES.snowDepth, ...METEOGRAM_SERIES.snowChance])
  const kept = buildSeries(values.filter(v => wanted.has(String(v.parameter))))
  const snow: SeriesMap = new Map()
  for (const [name, series] of kept) {
    const x: Date[] = []
    const y: number[] = []
    series.x.forEach((time, i) => {
      if (!isSnowStep(time) || (span && (time.getTime() < span.min || time.getTime() > span.max)))
        return
      x.push(time)
      y.push(series.y[i]!)
    })
    if (x.length)
      snow.set(name, { x, y })
  }
  return snow
}
