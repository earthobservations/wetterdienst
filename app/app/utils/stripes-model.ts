/**
 * What the climate stripes are made of, and the window of years they show: pure functions of the values the backend
 * answers, so that the chart's option, its readout and its keys are tested without a browser (GH-4068).
 */

/** The values of an answer of `/stripes/values`, as far as the stripes read them */
export interface StripesInput {
  timestamp: string | null
  value: number | null
}

export interface StripesModel {
  /** the years that have a value, in the order of the answer */
  years: number[]
  values: number[]
  /** each value's place between the lowest and the highest year, 0 to 1: what its colour is chosen by, and the height of the lines */
  normalized: number[]
  min: number
  max: number
  minYear: number
  maxYear: number
  /** the least-squares line through the years, for each year */
  trend: number[]
  normalizedTrend: number[]
  /** every year from the first to the last, `null` where there is no value: the data-availability line breaks there */
  availability: (number | null)[]
}

/**
 * The stripes of an answer: the years with a value (each year's value comes at its first moment in UTC, read in UTC, as in a
 * browser west of UTC that moment is still the year before). Null where there is none to draw.
 */
export function buildStripesModel(data: readonly StripesInput[]): StripesModel | null {
  const drawn = data.filter((item): item is { timestamp: string, value: number } => item.value !== null && item.timestamp !== null)
  if (!drawn.length)
    return null
  const years = drawn.map(item => new Date(item.timestamp).getUTCFullYear())
  const values = drawn.map(item => item.value)
  const min = Math.min(...values)
  const max = Math.max(...values)
  const minYear = Math.min(...years)
  const maxYear = Math.max(...years)
  // years all alike have no range to place a value in: the middle of the scale
  const place = (value: number) => max > min ? (value - min) / (max - min) : 0.5

  // simple linear regression: y = slope * x + intercept
  const n = years.length
  const sumX = years.reduce((a, b) => a + b, 0)
  const sumY = values.reduce((a, b) => a + b, 0)
  const sumXY = years.reduce((sum, x, i) => sum + x * values[i]!, 0)
  const sumX2 = years.reduce((sum, x) => sum + x * x, 0)
  const divisor = n * sumX2 - sumX * sumX
  const slope = divisor === 0 ? 0 : (n * sumXY - sumX * sumY) / divisor
  const intercept = (sumY - slope * sumX) / n
  const trend = years.map(year => slope * year + intercept)

  const present = new Set(years)
  return {
    years,
    values,
    normalized: values.map(place),
    min,
    max,
    minYear,
    maxYear,
    trend,
    normalizedTrend: trend.map(place),
    availability: Array.from({ length: maxYear - minYear + 1 }, (_, i) => present.has(minYear + i) ? -0.02 : null),
  }
}

/** A span of years on the chart's axis: a stripe is the year plus and minus half */
export interface YearWindow {
  start: number
  end: number
}

/** The whole chart: from the first stripe's left edge to the last one's right edge */
export function fullWindow(model: Pick<StripesModel, 'minYear' | 'maxYear'>): YearWindow {
  return { start: model.minYear - 0.5, end: model.maxYear + 0.5 }
}

/** The fewest stripes the chart zooms in to */
export const MIN_SPAN_STRIPES = 3

/** `window` moved into `bounds` and no wider than they are or narrower than `MIN_SPAN_STRIPES` */
export function clampWindow(window: YearWindow, bounds: YearWindow): YearWindow {
  const whole = bounds.end - bounds.start
  const span = Math.min(whole, Math.max(Math.min(MIN_SPAN_STRIPES, whole), window.end - window.start))
  const start = Math.min(bounds.end - span, Math.max(bounds.start, window.start))
  return { start, end: start + span }
}

/** `window` scaled by `factor` (below 1 zooms in) round `anchor`, which keeps its place in it */
export function zoomWindow(window: YearWindow, factor: number, anchor: number, bounds: YearWindow): YearWindow {
  const span = window.end - window.start
  const share = span > 0 ? (anchor - window.start) / span : 0.5
  const next = span * factor
  const start = anchor - share * next
  return clampWindow({ start, end: start + next }, bounds)
}

/** `window` moved by `years`, stopped at the bounds */
export function panWindow(window: YearWindow, years: number, bounds: YearWindow): YearWindow {
  return clampWindow({ start: window.start + years, end: window.end + years }, bounds)
}

/** `window` moved the least that brings `year`'s stripe into it */
export function revealYear(window: YearWindow, year: number, bounds: YearWindow): YearWindow {
  if (year - 0.5 >= window.start && year + 0.5 <= window.end)
    return window
  const span = window.end - window.start
  const start = year - 0.5 < window.start ? year - 0.5 : year + 0.5 - span
  return clampWindow({ start, end: start + span }, bounds)
}

/** The years whose stripes' middle is in `window`: the first and the last */
export function visibleYears(window: YearWindow, model: Pick<StripesModel, 'minYear' | 'maxYear'>): [number, number] {
  const first = Math.max(model.minYear, Math.ceil(window.start - 1e-9))
  const last = Math.min(model.maxYear, Math.floor(window.end + 1e-9))
  return [first, Math.max(first, last)]
}

/** Whether two windows are the same to a hundredth of a year */
export function sameWindow(a: YearWindow, b: YearWindow): boolean {
  return Math.abs(a.start - b.start) < 0.01 && Math.abs(a.end - b.end) < 0.01
}
