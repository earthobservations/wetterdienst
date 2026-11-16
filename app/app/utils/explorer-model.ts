/**
 * What the Explorer's chart is made of (GH-4096): the series it draws, the window of time it shows, the moments a key
 * steps through and the points that are drawn of a long series. Pure functions of the values the backend answered, so
 * that the chart's option, its readout and its keys are tested without a browser.
 */

/** One line of the chart: a station's parameter, or a trendline through one */
export interface ExplorerSeries {
  /** tells two series apart, whatever their names say; the one the legend toggles */
  id: string
  /** what the legend, the readout and a screen reader call it */
  name: string
  /** the place of its colour in the palette (`seriesColour`) */
  colorIndex: number
  kind: 'values' | 'trend'
  /**
   * The resolution the answer gave the series' rows (`hourly`, `monthly`, ...), where they all have one: what a line is
   * broken by where rows are missing (`gapRuleOf`). Absent for a trendline and where the rows' resolutions differ.
   */
  resolution?: string | null
  /** the moments in ms since the epoch, in order */
  x: number[]
  /** the value at each, `null` where there is none: a gap, which the line does not join */
  y: (number | null)[]
}

/** A span of time on the chart's axis, in ms since the epoch */
export interface ExplorerWindow {
  start: number
  end: number
}

/** From this many points on a chart is drawn as a line only, as it was with Plotly: no markers, a thin line */
export const LARGE_THRESHOLD = 500

// -- the colours of the series --------------------------------------------------------------------------------------

/**
 * The colours of the stations, in the order they are given out. A series' colour is data, and the same hue on the
 * light page and on the dark one; where the hue itself is under 3:1 on the white paper (WCAG 1.4.11: green 2.3, amber
 * 2.2, cyan 2.4, lime 2.0, orange 2.8) the light page has the same hue one step darker (Tailwind 600), at 3.1:1 to
 * 3.7:1. On the dark paper (`--ui-bg`, #12233f) every one is 3.5:1 or more (indigo 3.5, violet 3.7). `tests/unit/explorer-model.test.ts` holds both.
 */
export const SERIES_COLOURS = [
  { light: '#3b82f6', dark: '#3b82f6' },
  { light: '#16a34a', dark: '#22c55e' },
  { light: '#d97706', dark: '#f59e0b' },
  { light: '#ef4444', dark: '#ef4444' },
  { light: '#8b5cf6', dark: '#8b5cf6' },
  { light: '#0891b2', dark: '#06b6d4' },
  { light: '#ec4899', dark: '#ec4899' },
  { light: '#65a30d', dark: '#84cc16' },
  { light: '#ea580c', dark: '#f97316' },
  { light: '#6366f1', dark: '#6366f1' },
] as const

export function seriesColour(index: number, dark: boolean): string {
  return SERIES_COLOURS[index % SERIES_COLOURS.length]![dark ? 'dark' : 'light']
}

// -- the series -----------------------------------------------------------------------------------------------------

/** The points of a series that have a value */
export function pointCount(series: ExplorerSeries): number {
  let count = 0
  for (const value of series.y) {
    if (value !== null)
      count++
  }
  return count
}

/** The least-squares line through a series' points, as a series of two points from its first moment to its last; null where there is no line */
export function trendOf(series: Pick<ExplorerSeries, 'x' | 'y'>): { x: number[], y: number[] } | null {
  let n = 0
  let sumX = 0
  let sumY = 0
  let sumXY = 0
  let sumXX = 0
  // taken in the loop, where Math.min(...x) threw past about 120k points (65,536 in Safari)
  let minX = Infinity
  let maxX = -Infinity
  for (let i = 0; i < series.x.length; i++) {
    const y = series.y[i]
    if (y === null || y === undefined)
      continue
    const x = series.x[i]!
    n++
    sumX += x
    sumY += y
    sumXY += x * y
    sumXX += x * x
    minX = Math.min(minX, x)
    maxX = Math.max(maxX, x)
  }
  if (n < 2)
    return null
  const divisor = n * sumXX - sumX * sumX
  const slope = divisor === 0 ? 0 : (n * sumXY - sumX * sumY) / divisor
  const intercept = (sumY - slope * sumX) / n
  return { x: [minX, maxX], y: [slope * minX + intercept, slope * maxX + intercept] }
}

/** The series that are shown: the legend can turn one off */
export function shownSeries(series: readonly ExplorerSeries[], hidden: ReadonlySet<string>): ExplorerSeries[] {
  return series.filter(item => !hidden.has(item.id))
}

// -- the window -----------------------------------------------------------------------------------------------------

/** The whole chart: from the first moment of any series to the last; a lone moment gets a day round it */
export function boundsOf(series: readonly ExplorerSeries[]): ExplorerWindow | null {
  let start = Infinity
  let end = -Infinity
  for (const item of series) {
    if (!item.x.length)
      continue
    start = Math.min(start, item.x[0]!)
    end = Math.max(end, item.x[item.x.length - 1]!)
  }
  if (!Number.isFinite(start))
    return null
  return start === end ? { start: start - 43_200_000, end: end + 43_200_000 } : { start, end }
}

/** How far apart the points of the series are, typically: the median gap of the series with the finest one, in ms; null with no two points */
export function typicalStep(series: readonly ExplorerSeries[]): number | null {
  let finest: number | null = null
  for (const item of series) {
    if (item.kind !== 'values' || item.x.length < 2)
      continue
    // a thousand gaps are enough to tell
    const gaps: number[] = []
    const stride = Math.max(1, Math.floor((item.x.length - 1) / 1000))
    for (let i = 1; i < item.x.length; i += stride) {
      const gap = item.x[i]! - item.x[i - 1]!
      if (gap > 0)
        gaps.push(gap)
    }
    if (!gaps.length)
      continue
    gaps.sort((a, b) => a - b)
    const median = gaps[Math.floor(gaps.length / 2)]!
    finest = finest === null ? median : Math.min(finest, median)
  }
  return finest
}

/** The shortest span the chart zooms in to: a few points of its finest series, never under ten minutes */
export function minSpanOf(series: readonly ExplorerSeries[]): number {
  const step = typicalStep(series)
  return Math.max(600_000, step === null ? 6 * 3_600_000 : 3 * step)
}

/** `win` moved into `bounds` and no wider than they are or narrower than `minSpan` */
export function clampExplorerWindow(win: ExplorerWindow, bounds: ExplorerWindow, minSpan: number): ExplorerWindow {
  const whole = bounds.end - bounds.start
  const span = Math.min(whole, Math.max(Math.min(minSpan, whole), win.end - win.start))
  const start = Math.min(bounds.end - span, Math.max(bounds.start, win.start))
  return { start, end: start + span }
}

/** `win` scaled by `factor` (below 1 zooms in) round `anchor`, which keeps its place in it */
export function zoomExplorerWindow(win: ExplorerWindow, factor: number, anchor: number, bounds: ExplorerWindow, minSpan: number): ExplorerWindow {
  const span = win.end - win.start
  const share = span > 0 ? (anchor - win.start) / span : 0.5
  const next = span * factor
  const start = anchor - share * next
  return clampExplorerWindow({ start, end: start + next }, bounds, minSpan)
}

/** `win` moved by `deltaMs`, stopped at the bounds */
export function panExplorerWindow(win: ExplorerWindow, deltaMs: number, bounds: ExplorerWindow, minSpan: number): ExplorerWindow {
  return clampExplorerWindow({ start: win.start + deltaMs, end: win.end + deltaMs }, bounds, minSpan)
}

/** `win` moved the least that brings `t` into it, with a twentieth of the window to spare */
export function revealMoment(win: ExplorerWindow, t: number, bounds: ExplorerWindow, minSpan: number): ExplorerWindow {
  const span = win.end - win.start
  const margin = span / 20
  if (t - margin >= win.start && t + margin <= win.end)
    return win
  const start = t - margin < win.start ? t - margin : t + margin - span
  return clampExplorerWindow({ start, end: start + span }, bounds, minSpan)
}

/** Whether two windows are the same to a thousandth of their width */
export function sameExplorerWindow(a: ExplorerWindow, b: ExplorerWindow): boolean {
  const tolerance = Math.max(1, (a.end - a.start) / 1000)
  return Math.abs(a.start - b.start) < tolerance && Math.abs(a.end - b.end) < tolerance
}

// -- the moments a key steps through --------------------------------------------------------------------------------

/** The moments that have a value in a series that is shown, in order, each once: what the arrow keys step through and the pointer picks from */
export function buildTimeline(series: readonly ExplorerSeries[]): number[] {
  let total = 0
  for (const item of series) {
    if (item.kind === 'values')
      total += item.x.length
  }
  const all = new Float64Array(total)
  let at = 0
  for (const item of series) {
    if (item.kind !== 'values')
      continue
    for (let i = 0; i < item.x.length; i++) {
      if (item.y[i] !== null)
        all[at++] = item.x[i]!
    }
  }
  const sorted = all.subarray(0, at).sort()
  const moments: number[] = []
  for (let i = 0; i < sorted.length; i++) {
    if (i === 0 || sorted[i] !== sorted[i - 1])
      moments.push(sorted[i]!)
  }
  return moments
}

/** The index of the moment nearest to `t` in a sorted list, -1 for an empty one */
export function nearestIndex(sorted: readonly number[], t: number): number {
  if (!sorted.length)
    return -1
  let low = 0
  let high = sorted.length - 1
  while (low < high) {
    const middle = (low + high) >> 1
    if (sorted[middle]! < t)
      low = middle + 1
    else
      high = middle
  }
  return low > 0 && t - sorted[low - 1]! <= sorted[low]! - t ? low - 1 : low
}

/** The value of a series at exactly the moment `t`, `null` where it has none there */
export function valueAt(series: Pick<ExplorerSeries, 'x' | 'y'>, t: number): number | null {
  let low = 0
  let high = series.x.length - 1
  while (low <= high) {
    const middle = (low + high) >> 1
    const here = series.x[middle]!
    if (here === t)
      return series.y[middle] ?? null
    if (here < t)
      low = middle + 1
    else
      high = middle - 1
  }
  return null
}

export interface ReadoutRow {
  id: string
  name: string
  colorIndex: number
  value: number
}

/** The values of the shown series at the moment `t`, those that have one: what a hover label of the chart lists */
export function readoutRows(series: readonly ExplorerSeries[], t: number): ReadoutRow[] {
  const rows: ReadoutRow[] = []
  for (const item of series) {
    if (item.kind !== 'values')
      continue
    const value = valueAt(item, t)
    if (value !== null)
      rows.push({ id: item.id, name: item.name, colorIndex: item.colorIndex, value })
  }
  return rows
}

// -- where rows are missing -----------------------------------------------------------------------------------------

/** Whether the step between two consecutive moments (in ms) is a gap: a reading is missing there */
export type GapRule = (previous: number, next: number) => boolean

/** The ms between two readings of a resolution that has a fixed interval; `subdaily`, `monthly` and `annual` have none */
const RESOLUTION_STEPS: Readonly<Record<string, number>> = {
  '1_minute': 60_000,
  '5_minutes': 300_000,
  '6_minutes': 360_000,
  '10_minutes': 600_000,
  '15_minutes': 900_000,
  'hourly': 3_600_000,
  '6_hours': 21_600_000,
  'daily': 86_400_000,
}

/** A step longer than this many times the usual one is a gap: it is two steps long where one reading is missing */
const GAP_FACTOR = 1.5
/** A step is the usual one within this share of it; where fewer than half the steps are, the series is irregular */
const REGULAR_TOLERANCE = 0.1
/** A thousand steps are enough to tell what is usual */
const SAMPLE_STEPS = 1000

/** The calendar month (UTC) a moment is in, counted from year 0 */
function monthOf(ms: number): number {
  const date = new Date(ms)
  return date.getUTCFullYear() * 12 + date.getUTCMonth()
}

function computeGapRule(x: readonly number[], resolution: string | null | undefined): GapRule | null {
  if (x.length < 2)
    return null
  const stride = Math.max(1, Math.floor((x.length - 1) / SAMPLE_STEPS))
  // the calendar's months and years are not as long as each other: a month is missing where the next moment is two on
  if (resolution === 'monthly' || resolution === 'annual') {
    const unit = resolution === 'monthly' ? 1 : 12
    let steps = 0
    let usual = 0
    for (let i = 1; i < x.length; i += stride) {
      const months = monthOf(x[i]!) - monthOf(x[i - 1]!)
      if (months <= 0)
        continue
      steps++
      if (months === unit)
        usual++
    }
    return steps && usual / steps >= 0.5 ? (previous, next) => monthOf(next) - monthOf(previous) > unit : null
  }
  const steps: number[] = []
  for (let i = 1; i < x.length; i += stride) {
    const step = x[i]! - x[i - 1]!
    if (step > 0)
      steps.push(step)
  }
  if (!steps.length)
    return null
  steps.sort((a, b) => a - b)
  const median = steps[Math.floor(steps.length / 2)]!
  // a station that reports less often than its resolution is held to what it does
  const usual = Math.max(median, resolution ? RESOLUTION_STEPS[resolution] ?? 0 : 0)
  const regular = steps.filter(step => Math.abs(step - usual) <= usual * REGULAR_TOLERANCE).length
  if (regular / steps.length < 0.5)
    return null
  const limit = usual * GAP_FACTOR
  return (previous, next) => next - previous > limit
}

const gapRules = new WeakMap<readonly number[], { resolution: string | null | undefined, rule: GapRule | null }>()

/**
 * Where a series has gaps: a step longer than one and a half times its usual spacing, which is a reading missing at the
 * least (GH-4100). The usual spacing is a calendar month or year for `monthly` and `annual`, the resolution's interval where
 * the answer names one (never less than the series' own median step), else the median step. A series where fewer than half
 * the steps are the usual one (events, not readings) has no gaps, and nor has a trendline or one of a single moment. The
 * steps are in UTC, so that a change of clocks is none. Kept for the series' moments, which a drag of the window does not change.
 */
export function gapRuleOf(series: Pick<ExplorerSeries, 'x'> & Partial<Pick<ExplorerSeries, 'kind' | 'resolution'>>): GapRule | null {
  if (series.kind === 'trend')
    return null
  const kept = gapRules.get(series.x)
  if (kept && kept.resolution === series.resolution)
    return kept.rule
  const rule = computeGapRule(series.x, series.resolution)
  gapRules.set(series.x, { resolution: series.resolution, rule })
  return rule
}

// -- what is drawn of a long series ---------------------------------------------------------------------------------

/** A chart of this many points per px of its width and fewer is drawn as it is */
export const POINTS_PER_PX = 4

export interface DrawnPoints {
  x: number[]
  y: (number | null)[]
}

/**
 * The points of a series that the window shows (and the one on each side of it, so that the line runs to the edge), cut
 * down to what a plot `plotPx` wide can tell apart. A series of a decade of hourly readings is 87,000 points on a plot of
 * 700 px: each px column of it keeps its first and last point and its lowest and highest (min-max with the ends, the
 * "M4" of time series charts), so the peaks and the troughs a reader looks for are all still there, which a sampling
 * that picks the points that shape the line (`lttb`) does not promise. A gap is kept as one: a point without a value ends
 * the column before it and stays in the list, so the line is broken where the data is. So is a step that `gap` calls one,
 * where rows are missing: a point without a value is put between the two moments, before the columns are made, so that no
 * cutting down of the points joins what the data does not (GH-4100). A series that fits is otherwise not touched.
 */
export function drawnPoints(series: Pick<ExplorerSeries, 'x' | 'y'>, win: ExplorerWindow, plotPx: number, gap: GapRule | null = null): DrawnPoints {
  const { x, y } = series
  // the first point at or after the window's start, and the last at or before its end
  let low = 0
  let high = x.length
  while (low < high) {
    const middle = (low + high) >> 1
    if (x[middle]! < win.start)
      low = middle + 1
    else
      high = middle
  }
  const from = Math.max(0, low - 1)
  low = from
  high = x.length
  while (low < high) {
    const middle = (low + high) >> 1
    if (x[middle]! <= win.end)
      low = middle + 1
    else
      high = middle
  }
  const to = Math.min(x.length - 1, low)
  const count = to - from + 1
  if (count <= 0)
    return { x: [], y: [] }
  const columns = Math.max(1, Math.round(plotPx))
  if (count <= columns * POINTS_PER_PX) {
    if (!gap)
      return { x: x.slice(from, to + 1), y: y.slice(from, to + 1) }
    const keptX: number[] = []
    const keptY: (number | null)[] = []
    for (let i = from; i <= to; i++) {
      if (i > from && y[i] !== null && keptY[keptY.length - 1] !== null && gap(x[i - 1]!, x[i]!)) {
        keptX.push(Math.round((x[i - 1]! + x[i]!) / 2))
        keptY.push(null)
      }
      keptX.push(x[i]!)
      keptY.push(y[i]!)
    }
    return { x: keptX, y: keptY }
  }

  const outX: number[] = []
  const outY: (number | null)[] = []
  const span = Math.max(1, win.end - win.start)
  const columnOf = (t: number) => Math.min(columns - 1, Math.max(0, Math.floor(((t - win.start) / span) * columns)))
  // the indices of the open column: its first, its last, its lowest and its highest
  let column = -1
  let first = -1
  let last = -1
  let lowest = -1
  let highest = -1
  const flush = () => {
    if (first < 0)
      return
    const kept = [...new Set([first, lowest, highest, last])].sort((a, b) => a - b)
    for (const index of kept) {
      outX.push(x[index]!)
      outY.push(y[index]!)
    }
    first = last = lowest = highest = -1
  }
  for (let i = from; i <= to; i++) {
    const value = y[i]
    if (gap && i > from && value !== null && value !== undefined && gap(x[i - 1]!, x[i]!)) {
      // the columns are cut at the gap, as at a missing value: nothing of one is joined to the next
      flush()
      if (outY.length > 0 && outY[outY.length - 1] !== null) {
        outX.push(Math.round((x[i - 1]! + x[i]!) / 2))
        outY.push(null)
      }
      column = -1
    }
    if (value === null || value === undefined) {
      flush()
      // a run of missing values is one gap
      if (outY.length === 0 || outY[outY.length - 1] !== null) {
        outX.push(x[i]!)
        outY.push(null)
      }
      column = -1
      continue
    }
    const here = columnOf(x[i]!)
    if (here !== column) {
      flush()
      column = here
    }
    if (first < 0) {
      first = lowest = highest = i
    }
    else {
      if (value < y[lowest]!)
        lowest = i
      if (value > y[highest]!)
        highest = i
    }
    last = i
  }
  flush()
  return { x: outX, y: outY }
}

/** The lowest and the highest value among points, null where there is none */
export function valueExtent(points: readonly Pick<DrawnPoints, 'y'>[]): [number, number] | null {
  let min = Infinity
  let max = -Infinity
  for (const { y } of points) {
    for (const value of y) {
      if (value === null)
        continue
      if (value < min)
        min = value
      if (value > max)
        max = value
    }
  }
  return Number.isFinite(min) ? [min, max] : null
}

// -- the y axis -----------------------------------------------------------------------------------------------------

export interface Scale {
  min: number
  max: number
  interval: number
  /** the fraction digits its tick labels need */
  decimals: number
}

/** The scale of a y axis for values from `min` to `max`: round ends and a round step (1, 2 or 5 times a power of ten), about `ticks` of them */
export function niceScale(min: number, max: number, ticks = 6): Scale {
  if (!Number.isFinite(min) || !Number.isFinite(max))
    return { min: 0, max: 1, interval: 0.25, decimals: 2 }
  if (min === max) {
    const pad = min === 0 ? 1 : Math.abs(min) * 0.1
    min -= pad
    max += pad
  }
  const raw = (max - min) / Math.max(1, ticks - 1)
  const power = 10 ** Math.floor(Math.log10(raw))
  // the step nearest to the raw one on the scale of 1, 2, 5 and 10 (the thresholds are the geometric means between them)
  const fraction = raw / power
  const interval = (fraction >= 7.07 ? 10 : fraction >= 3.16 ? 5 : fraction >= 1.41 ? 2 : 1) * power
  // the ends are put to the ticks; a division's error does not pull one a step too far
  const lower = Math.floor(min / interval + 1e-9) * interval
  const upper = Math.ceil(max / interval - 1e-9) * interval
  const decimals = Math.max(0, -Math.floor(Math.log10(interval) + 1e-9))
  const round = (value: number) => Number(value.toFixed(Math.min(12, decimals + 2)))
  return { min: round(lower), max: round(upper), interval: round(interval) || interval, decimals }
}
