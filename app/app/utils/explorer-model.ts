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
   * How the line is drawn besides its colour, so that two series are told apart by more than the colour (WCAG 1.4.1): dashed, and the
   * shape of its markers. Absent: a solid line with round markers. The Compare tool's side B is dashed with square markers.
   */
  look?: { dashed?: boolean, symbol?: 'circle' | 'rect' | 'triangle' | 'diamond' }
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

/**
 * Whether the step between two consecutive moments (in ms) is a gap: a reading is missing there. `index` is the place of `next`
 * in the series' moments where the caller has it, which saves the rule a search.
 */
export type GapRule = (previous: number, next: number, index?: number) => boolean

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
/**
 * Where the usual step is the one from the same time of day (readings at 06, 12 and 18 UTC are 6, 6 and 12 h apart) it is exact,
 * and a step of one and a half of it, which is what a missing 06:00 leaves between the 18:00 and the 12:00 of the day after, is a gap
 */
const TIME_OF_DAY_GAP_FACTOR = 1.25
/** A step is the usual one within this share of it; where fewer than half the steps are, the series is irregular */
const REGULAR_TOLERANCE = 0.1
/** The usual step is the median of this many steps either side of a step (the local cadence), or of the same time of day on this many days */
const CADENCE_RADIUS = 10
const TIME_OF_DAY_RADIUS = 5
/** A series that is not regular by its steps is still one of readings if this share of its moments lie on its resolution's grid */
const GRID_SHARE = 0.8
/** A thousand moments are enough to tell where a series lies */
const SAMPLE_STEPS = 1000

const DAY_MS = 86_400_000

/** The calendar month (UTC) a moment is in, counted from year 0 */
function monthOf(ms: number): number {
  const date = new Date(ms)
  return date.getUTCFullYear() * 12 + date.getUTCMonth()
}

function median(values: number[]): number {
  values.sort((a, b) => a - b)
  return values[Math.floor(values.length / 2)]!
}

/** The median of the steps within `CADENCE_RADIUS` steps of each step: the cadence of the series where the step is, which a change of it moves and one gap does not */
function localCadence(steps: Float64Array): Float64Array {
  const cadence = new Float64Array(steps.length)
  // the window's positive steps, sorted: one enters and one leaves as it moves
  const window: number[] = []
  const insert = (value: number) => {
    let low = 0
    let high = window.length
    while (low < high) {
      const middle = (low + high) >> 1
      if (window[middle]! < value)
        low = middle + 1
      else
        high = middle
    }
    window.splice(low, 0, value)
  }
  const remove = (value: number) => {
    let low = 0
    let high = window.length
    while (low < high) {
      const middle = (low + high) >> 1
      if (window[middle]! < value)
        low = middle + 1
      else
        high = middle
    }
    window.splice(low, 1)
  }
  for (let i = 1; i < Math.min(CADENCE_RADIUS, steps.length); i++) {
    if (steps[i]! > 0)
      insert(steps[i]!)
  }
  for (let i = 1; i < steps.length; i++) {
    // the window is of an even number of steps, CADENCE_RADIUS either side, so that the lower median is the same in every place of a pattern
    const entering = i + CADENCE_RADIUS - 1
    if (entering < steps.length && steps[entering]! > 0)
      insert(steps[entering]!)
    const leaving = i - CADENCE_RADIUS - 1
    if (leaving >= 1 && steps[leaving]! > 0)
      remove(steps[leaving]!)
    // the lower median: readings in pairs far apart are steps of an hour and of days, and the days are not the cadence
    cadence[i] = window.length ? window[(window.length - 1) >> 1]! : 0
  }
  return cadence
}

/** The share of the steps round a step that must be the cadence for the series to be one of a single cadence there: 06, 12 and 18 UTC of two days are 4 steps in 5, which are not; one gap in seven steps is 6 in 7, which is */
const STEADY_SHARE = 0.85

/** Whether the steps within the window of the cadence round the step at `i` are, nine in ten of them, the cadence there: a series of one cadence, not of readings at fixed times */
function steadyCadence(steps: Float64Array, cadence: Float64Array, i: number): boolean {
  let counted = 0
  let steady = 0
  for (let k = Math.max(1, i - CADENCE_RADIUS); k <= Math.min(steps.length - 1, i + CADENCE_RADIUS - 1); k++) {
    if (steps[k]! <= 0)
      continue
    counted++
    if (Math.abs(steps[k]! - cadence[i]!) <= cadence[i]! * REGULAR_TOLERANCE)
      steady++
  }
  return counted > 0 && steady / counted >= STEADY_SHARE
}

/** Whether most of the moments lie on a grid of `interval` ms, as readings do whatever the steps between those that are there: the phases within a seventh of it of one another */
function onGrid(x: readonly number[], interval: number): boolean {
  const buckets = 20
  const counts = Array.from<number>({ length: buckets }).fill(0)
  const stride = Math.max(1, Math.floor(x.length / SAMPLE_STEPS))
  let total = 0
  for (let i = 0; i < x.length; i += stride) {
    counts[Math.min(buckets - 1, Math.floor((((x[i]! % interval) + interval) % interval) / interval * buckets))]!++
    total++
  }
  // three buckets in a row, wrapping round: 15 % of the interval
  let best = 0
  for (let b = 0; b < buckets; b++)
    best = Math.max(best, counts[b]! + counts[(b + 1) % buckets]! + counts[(b + 2) % buckets]!)
  return best / total >= GRID_SHARE
}

/** The gaps of a series as a flag for each step into a moment, or null where its steps are those of events and not of readings */
function computeGaps(x: readonly number[], resolution: string | null | undefined): Uint8Array | null {
  if (x.length < 2)
    return null
  const flags = new Uint8Array(x.length)
  // the calendar's months and years are not as long as each other: a month is missing where the next moment is two on
  if (resolution === 'monthly' || resolution === 'annual') {
    const unit = resolution === 'monthly' ? 1 : 12
    let steps = 0
    let regular = 0
    const stride = Math.max(1, Math.floor((x.length - 1) / SAMPLE_STEPS))
    for (let i = 1; i < x.length; i += stride) {
      const months = monthOf(x[i]!) - monthOf(x[i - 1]!)
      if (months <= 0)
        continue
      steps++
      // a whole number of years is a series with some of them missing, not one of events that fall in other months (every step is one of months)
      if (months % unit === 0)
        regular++
    }
    if (!steps || regular / steps < 0.5)
      return null
    let before = monthOf(x[0]!)
    for (let i = 1; i < x.length; i++) {
      const month = monthOf(x[i]!)
      flags[i] = month - before > unit ? 1 : 0
      before = month
    }
    return flags
  }

  const steps = new Float64Array(x.length)
  for (let i = 1; i < x.length; i++)
    steps[i] = x[i]! - x[i - 1]!
  const nominal = resolution ? RESOLUTION_STEPS[resolution] ?? 0 : 0
  const cadence = localCadence(steps)
  // the usual step of each: the interval of the resolution where it has one, never less than what the series does round there (a station that
  // reports less often than its resolution is held to that, and one whose cadence changed to the one it has then); with none, the step from the
  // same time of day on the days round it where there are some (06, 12 and 18 UTC are 6, 6 and 12 h apart, and no step of 12 h is a gap there),
  // else the cadence round it
  const usual = new Float64Array(x.length)
  // what the regularity of the series is judged by: the usual step, but for a step alone at its time of day the cadence round it only, since a step is always its own
  const reference = new Float64Array(x.length)
  const exact = new Uint8Array(x.length)
  if (nominal > 0) {
    for (let i = 1; i < x.length; i++)
      usual[i] = reference[i] = Math.max(nominal, cadence[i]!)
  }
  else {
    const days = new Map<number, number[]>()
    for (let i = 1; i < x.length; i++) {
      if (steps[i]! <= 0)
        continue
      const key = Math.round((((x[i - 1]! % DAY_MS) + DAY_MS) % DAY_MS) / 60_000)
      const group = days.get(key)
      if (group)
        group.push(i)
      else
        days.set(key, [i])
    }
    for (const group of days.values()) {
      group.forEach((i, place) => {
        if (group.length < 3) {
          // too few days to tell by the time of day: the cadence round it where it is the one cadence of the series there (nine in ten of
          // the steps round it are within the tolerance of it: a short series of hours with an hour missing); where it is not, the readings
          // are at fixed times, and the cadence is never less than the steps there are from this time of day, up to a day (the one step of
          // 12 h from 18:00 of a series of two days is the usual one, not a gap, and a step of 84 h, over three days, is)
          usual[i] = steadyCadence(steps, cadence, i) ? cadence[i]! : Math.max(cadence[i]!, Math.min(DAY_MS, median(group.map(at => steps[at]!))))
          reference[i] = cadence[i]!
          return
        }
        const near = group.slice(Math.max(0, place - TIME_OF_DAY_RADIUS), place + TIME_OF_DAY_RADIUS + 1).map(at => steps[at]!)
        usual[i] = reference[i] = median(near)
        exact[i] = 1
      })
    }
  }
  let counted = 0
  let regular = 0
  const stride = Math.max(1, Math.floor((x.length - 1) / SAMPLE_STEPS))
  for (let i = 1; i < x.length; i += stride) {
    if (steps[i]! <= 0 || reference[i] === 0)
      continue
    counted++
    if (Math.abs(steps[i]! - reference[i]!) <= reference[i]! * REGULAR_TOLERANCE)
      regular++
  }
  // fewer than half the steps are the usual one, and the moments are not on the grid of the resolution either: events, not readings
  if (!counted || (regular / counted < 0.5 && !(nominal > 0 && onGrid(x, nominal))))
    return null
  for (let i = 1; i < x.length; i++) {
    if (steps[i]! > 0 && usual[i]! > 0)
      flags[i] = steps[i]! > usual[i]! * (exact[i] ? TIME_OF_DAY_GAP_FACTOR : GAP_FACTOR) ? 1 : 0
  }
  return flags
}

const gapRules = new WeakMap<readonly number[], { resolution: string | null | undefined, rule: GapRule | null }>()

/** The place of `moment` in the sorted `x` (the first at or after it) */
function indexOfMoment(x: readonly number[], moment: number): number {
  let low = 0
  let high = x.length
  while (low < high) {
    const middle = (low + high) >> 1
    if (x[middle]! < moment)
      low = middle + 1
    else
      high = middle
  }
  return low
}

/**
 * Where a series has gaps: a step longer than one and a half times the usual one there, which is a reading missing at the least
 * (GH-4100). The usual step is a calendar month or year for `monthly` and `annual`; the resolution's interval where the answer names
 * one, never less than the series' own cadence round that step (the median of the steps either side, so that a station that reports
 * less often than its resolution, or whose cadence changed once, has no gaps for it); with no interval, the step from the same time
 * of day on the days round it (readings at 06, 12 and 18 UTC are 6, 6 and 12 h apart, and only a missing one is a gap), else the cadence
 * round it. A series whose steps are not the usual ones for the most part, and whose moments are not on its resolution's grid
 * (events, not readings), has no gaps, and nor has a trendline or one of a single moment. The steps are in UTC, so that a change of clocks
 * is none. Kept for the series' moments, which a drag of the window does not change.
 */
export function gapRuleOf(series: Pick<ExplorerSeries, 'x'> & Partial<Pick<ExplorerSeries, 'kind' | 'resolution'>>): GapRule | null {
  if (series.kind === 'trend')
    return null
  const kept = gapRules.get(series.x)
  if (kept && kept.resolution === series.resolution)
    return kept.rule
  const flags = computeGaps(series.x, series.resolution)
  const x = series.x
  const rule: GapRule | null = flags ? (previous, next, index) => next > previous && flags[index !== undefined && x[index] === next ? index : indexOfMoment(x, next)] === 1 : null
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
 * cutting down of the points joins what the data does not (GH-4100). Where the points are cut down, only a gap that is a column
 * wide or more is kept as one: a narrower one is not to be seen, and a break for each of the many a decade of readings has would
 * keep nearly every point. A series that fits is otherwise not touched.
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
      if (i > from && y[i] !== null && keptY[keptY.length - 1] !== null && gap(x[i - 1]!, x[i]!, i)) {
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
    // a gap narrower than a column of the plot is not to be seen, and a break for each would keep every point of a series with many of them
    if (gap && i > from && value !== null && value !== undefined && x[i]! - x[i - 1]! >= span / columns && gap(x[i - 1]!, x[i]!, i)) {
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
