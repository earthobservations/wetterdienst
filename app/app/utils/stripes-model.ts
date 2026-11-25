/**
 * What the climate stripes are made of, and the window of years they show: pure functions of the years the app makes of the annual values
 * (`stripes-source.ts`), so that the chart's option, its readout and its keys are tested without a browser (GH-4068).
 */

/** The years of the stripes of a station (`stripes-source.ts`), as far as the stripes read them */
export interface StripesInput {
  timestamp: string | null
  value: number | null
  /** the value's distance from the mean of the reference, in the unit of the value */
  anomaly: number | null
  /** the class `stripes-scale.ts` puts the value in, 0 (the lowest) to 15: the colour of its stripe */
  stripe_class: number | null
}

/**
 * The ways the same years are drawn (GH-4156): as stripes, as bars (the year's anomaly as the height, in the colour of its
 * class, with no axes) and as bars with a scale (a y axis in the unit of the anomaly, and a year axis with round ticks).
 */
export const STRIPES_VARIANTS = ['stripes', 'bars', 'barsScale'] as const
export type StripesVariant = (typeof STRIPES_VARIANTS)[number]

/**
 * What the page shows of the years (GH-4233): the three ways to draw them, and the table, which is a view of its own beside
 * them and draws nothing. It is the fourth choice of the same switch; the drawing keeps `StripesVariant`.
 */
export const STRIPES_VIEWS = [...STRIPES_VARIANTS, 'table'] as const
export type StripesView = (typeof STRIPES_VIEWS)[number]

/** How a view is written in the link (`variant=bars_scale`): `bars_scale` for the bars with a scale, the others by their name */
export const STRIPES_VIEW_QUERY: Record<StripesView, string> = { stripes: 'stripes', bars: 'bars', barsScale: 'bars_scale', table: 'table' }

/** The view a `variant` of the link names; a name that is none of them is no choice, and the reader gets the stripes */
export function stripesViewFromQuery(value: unknown): StripesView {
  const name = Array.isArray(value) ? value[0] : value
  return STRIPES_VIEWS.find(view => STRIPES_VIEW_QUERY[view] === name) ?? 'stripes'
}

/**
 * The year a `start_year` or `end_year` of the link names (GH-4388): a repeated one reads as its first value, and one that is no whole
 * number (`abc`, `2000.5`, `1e3`, an empty one) as none, so that no `NaN` reaches the model or is written back into the link
 */
export function stripesYearFromQuery(value: unknown): number | null {
  const first = Array.isArray(value) ? value[0] : value
  if (typeof first !== 'string' || !/^-?\d+$/.test(first.trim()))
    return null
  const year = Number(first)
  return Number.isSafeInteger(year) ? year : null
}

/** The view is one of the drawings, which have a chart, a toolbar and an image to save (the table has none) */
export function isStripesDrawing(view: StripesView): view is StripesVariant {
  return view !== 'table'
}

export interface StripesModel {
  /** the years that have a value, in the order of the answer */
  years: number[]
  values: number[]
  /** each value's class, 0 to 15, as `stripes-scale.ts` classes it: what its colour is chosen by */
  classes: number[]
  /** each value's distance from the mean of the reference, as `stripes-scale.ts` has it, in the unit of the values */
  anomalies: number[]
  minYear: number
  maxYear: number
  /** every year from the first to the last, `null` where there is no value: the data-availability line breaks there */
  availability: (number | null)[]
}

/**
 * The stripes of an answer: the years with a value (each year's value comes at its first moment in UTC, read in UTC, as in a
 * browser west of UTC that moment is still the year before). Null where there is none to draw.
 *
 * The model calculates nothing beyond the years: the classes and the anomalies are the ones `stripes-scale.ts` gives them, and the stripes
 * draw no line over them (no time series, no trend), as in Ed Hawkins' design (GH-4170).
 */
export function buildStripesModel(data: readonly StripesInput[]): StripesModel | null {
  const drawn = data.filter((item): item is { timestamp: string, value: number, anomaly: number, stripe_class: number } => item.value !== null && item.timestamp !== null && item.anomaly !== null && item.stripe_class !== null)
  if (!drawn.length)
    return null
  const years = drawn.map(item => new Date(item.timestamp).getUTCFullYear())
  const values = drawn.map(item => item.value)
  const minYear = Math.min(...years)
  const maxYear = Math.max(...years)

  const present = new Set(years)
  return {
    years,
    values,
    classes: drawn.map(item => item.stripe_class),
    anomalies: drawn.map(item => item.anomaly),
    minYear,
    maxYear,
    availability: Array.from({ length: maxYear - minYear + 1 }, (_, i) => present.has(minYear + i) ? -0.02 : null),
  }
}

/** A run of years that each have a value, from the first to the last (a lone year is a run of one) */
export interface YearRun {
  first: number
  last: number
}

/**
 * The runs of years with a value in `availability` (a value for a year that has one, `null` for one that has none, from
 * `minYear` on), in order: the stretches the data-availability line covers, so that it spans exactly their stripes (GH-4153).
 */
export function availabilityRuns(availability: readonly (number | null)[], minYear: number): YearRun[] {
  const runs: YearRun[] = []
  availability.forEach((value, index) => {
    if (value === null)
      return
    const year = minYear + index
    const open = runs.at(-1)
    if (open && open.last === year - 1)
      open.last = year
    else
      runs.push({ first: year, last: year })
  })
  return runs
}

/** The y axis of the bars: the range of the anomalies (zero in it) rounded out to the ticks that mark it */
export interface AnomalyAxis {
  min: number
  max: number
  step: number
  /** from `min` to `max`, a tick every `step` */
  ticks: number[]
  /** the decimals a tick is written with, so that no two read alike (a step of 0.5 needs one) */
  decimals: number
}

/**
 * The range the bars of `anomalies` are drawn on: from the lowest to the highest of them, zero included, rounded out to a
 * step of 1, 2 or 5 times a power of ten that gives about five intervals. It lies on the years of the whole answer and not on
 * those in the window, so that the bars keep their height as the chart is zoomed. The anomalies are those of `stripes-scale.ts`; this
 * sets only where the axis runs.
 */
export function anomalyAxis(anomalies: readonly number[]): AnomalyAxis {
  const low = Math.min(0, ...anomalies)
  const high = Math.max(0, ...anomalies)
  const raw = (high - low || 1) / 5
  const magnitude = 10 ** Math.floor(Math.log10(raw))
  const step = [1, 2, 5, 10].map(factor => factor * magnitude).find(candidate => candidate >= raw * (1 - 1e-9))!
  const min = Math.floor(low / step + 1e-9) * step
  let max = Math.ceil(high / step - 1e-9) * step
  if (max <= min)
    max = min + step
  const count = Math.round((max - min) / step)
  const clean = (value: number) => Number(value.toPrecision(12))
  return {
    min: clean(min),
    max: clean(max),
    step: clean(step),
    ticks: Array.from({ length: count + 1 }, (_, index) => clean(min + index * step)),
    decimals: Math.max(0, -Math.floor(Math.log10(step) + 1e-9)),
  }
}

/** The axis of the bars of `model`: the range of the anomalies of the years, which no window moves */
export function barAxis(model: Pick<StripesModel, 'anomalies'>): AnomalyAxis {
  return anomalyAxis(model.anomalies)
}

/** The steps the ticks of the year axis are a multiple of: the finest that leaves the labels room is taken */
const YEAR_TICK_STEPS = [1, 2, 5, 10, 20, 25, 50, 100, 200]

/**
 * The years the year axis of the bars with a scale labels: the multiples of a round step (5, 10, 20, 25, 50, ...) whose
 * bar's middle is in `window`, the step the finest that leaves each label `spacing` px (a label is four digits at 14 px: about
 * 48 with the room between). They move with the window, so a zoomed chart gets finer ticks.
 */
export function yearTicks(window: YearWindow, plotWidth: number, spacing = 48): number[] {
  const span = window.end - window.start
  if (!(span > 0) || !(plotWidth > 0))
    return []
  const step = YEAR_TICK_STEPS.find(candidate => plotWidth / (span / candidate) >= spacing) ?? YEAR_TICK_STEPS.at(-1)!
  const first = Math.ceil((window.start - 1e-9) / step)
  const last = Math.floor((window.end + 1e-9) / step)
  return Array.from({ length: Math.max(0, last - first + 1) }, (_, index) => (first + index) * step)
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

/**
 * The first and the last year that has a stripe whose middle is in `window`, which the chart names at its ends. Where the window
 * starts in a gap (years without a value) the first is the first year with a stripe after it, not a year that has none. Where
 * the model lists no years, or none is in the window, the first and the last year the window reaches.
 */
export function visibleYears(window: YearWindow, model: Pick<StripesModel, 'minYear' | 'maxYear'> & { years?: readonly number[] }): [number, number] {
  const low = Math.ceil(window.start - 1e-9)
  const high = Math.floor(window.end + 1e-9)
  const inView = (model.years ?? []).filter(year => year >= low && year <= high)
  if (inView.length)
    return [Math.min(...inView), Math.max(...inView)]
  const first = Math.max(model.minYear, low)
  return [first, Math.max(first, Math.min(model.maxYear, high))]
}

/** Whether two windows are the same to a hundredth of a year */
export function sameWindow(a: YearWindow, b: YearWindow): boolean {
  return Math.abs(a.start - b.start) < 0.01 && Math.abs(a.end - b.end) < 0.01
}
