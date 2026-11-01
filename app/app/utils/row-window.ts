import type { Resolution } from '#shared/types/api'
import { timestampDate } from './timestamp'

// The rows a request for values comes to, and the window of dates that makes it fit what the server
// sends as one answer (GH-3457). The server refuses a request over its limit before it downloads
// anything (`wetterdienst/ui/limits.py`); the explorer asks the same question first, with the same
// rule, so that it can start from a range that is not refused, and falls back on the server's own
// number (`requested` of the refusal) where it is refused anyway.
//
// All dates are UTC days, as the REST API reads a date (`2026-01-31` names the whole day), written
// `YYYY-MM-DD`.

const DAY = 86_400_000
const MINUTE = 60_000

/** The share of a limit a window is fitted to: an estimate is an upper bound, but not an exact one. */
export const ROW_MARGIN = 0.9

/**
 * What the explorer holds a high resolution (1, 5 and 10 minutes) to, whatever the server's limit is:
 * the date range selector refuses a range of more values than this (`DateRangeSelector.vue`), so a
 * window above it would be a default the page itself calls invalid.
 */
export const HIGH_RESOLUTION_MAX_VALUES = 100_000

const HIGH_RESOLUTIONS: readonly Resolution[] = ['1_minute', '5_minutes', '10_minutes']

/** The server's limits as `GET /api/version` reports them, 0 meaning none. */
export interface RowLimits {
  max_rows: number
  max_stations: number
  max_stream_rows: number
}

/** The limits of a server that sets none of its own (`RESTAPI_MAX_*` of `wetterdienst.settings`). */
export const DEFAULT_ROW_LIMITS: Readonly<RowLimits> = { max_rows: 500_000, max_stations: 100, max_stream_rows: 10_000_000 }

/** The minutes between two readings of a resolution: none for `subdaily`, which names no interval. */
const STEP_MINUTES: Partial<Record<Resolution, number>> = {
  '1_minute': 1,
  '5_minutes': 5,
  '6_minutes': 6,
  '10_minutes': 10,
  '15_minutes': 15,
  'hourly': 60,
  '6_hours': 360,
  'daily': 1440,
}

/** Whether a resolution names an interval between its readings, the way the server counts them. */
function hasInterval(resolution: Resolution): boolean {
  return STEP_MINUTES[resolution] !== undefined || resolution === 'monthly' || resolution === 'annual'
}

/** The span a window is counted in, and the smallest one a resolution has a use for. */
export type WindowUnit = 'days' | 'months' | 'years'

/** The units a window of a resolution is written in, the largest first: a month of annual data is no window. */
function unitsOf(resolution: Resolution): WindowUnit[] {
  if (resolution === 'annual')
    return ['years']
  if (resolution === 'monthly')
    return ['years', 'months']
  return ['years', 'months', 'days']
}

/** The limit a resolution's window is held to: the server's, and for a high resolution also the page's own. */
export function effectiveMaximum(resolution: Resolution | undefined, maximum: number): number {
  const high = resolution !== undefined && HIGH_RESOLUTIONS.includes(resolution)
  if (!high)
    return maximum
  return maximum > 0 ? Math.min(maximum, HIGH_RESOLUTION_MAX_VALUES) : HIGH_RESOLUTION_MAX_VALUES
}

/**
 * The readings a resolution can hold between two instants, both ends included, as the server counts
 * them (`count_readings`): a fixed step from the step alone, a month or a year by the first days of
 * them the window contains. 0 for a resolution that has no interval (`subdaily`).
 */
export function countReadings(resolution: Resolution, start: number, end: number): number {
  if (end < start)
    return 0
  const minutes = STEP_MINUTES[resolution]
  if (minutes !== undefined)
    return Math.floor((end - start) / (minutes * MINUTE)) + 1
  if (!hasInterval(resolution))
    return 0
  const from = new Date(start)
  const to = new Date(end)
  // the first anchor, a first of the month or of January, on or after the start
  const anchor = new Date(Date.UTC(from.getUTCFullYear(), resolution === 'annual' ? 0 : from.getUTCMonth(), 1))
  if (anchor.getTime() < start) {
    if (resolution === 'annual')
      anchor.setUTCFullYear(anchor.getUTCFullYear() + 1)
    else
      anchor.setUTCMonth(anchor.getUTCMonth() + 1)
  }
  if (anchor.getTime() > end)
    return 0
  if (resolution === 'annual')
    return to.getUTCFullYear() - anchor.getUTCFullYear() + 1
  return (to.getUTCFullYear() - anchor.getUTCFullYear()) * 12 + to.getUTCMonth() - anchor.getUTCMonth() + 1
}

/** A station's record as the station list has it: where its readings begin and end, null where it publishes none. */
export interface SelectionRecord {
  start_timestamp?: string | null
  end_timestamp?: string | null
}

/** The dates the user gave, as the date fields hold them. */
export interface DateWindow {
  startDate?: string
  endDate?: string
}

/** The days a selection reaches, both ends included. */
export interface Span {
  start: number
  end: number
}

export interface RowEstimateInput {
  resolution: Resolution
  /** the selected stations' records */
  records: readonly SelectionRecord[]
  parameterCount: number
  /** the wide shape holds a row for every timestamp rather than for every value */
  tidy?: boolean
  /** the window the user gave: only one with both dates counts (a start alone is read by the server as that one day) */
  range?: DateWindow
  /** where a record that is still going on ends */
  now?: number
  /**
   * Count as the date range form does for a high resolution (`DateRangeSelector`): every selected
   * station over the whole window, whatever its record, and every parameter, whatever the shape.
   * What the form accepts is the page's own rule, which the server's count (never more) does not replace.
   */
  asForm?: boolean
}

export interface RowEstimate {
  /** null where nothing can be said: a resolution with no interval, or no station with a record to count */
  rows: number | null
  /** the days the stations' records reach within the window, null where there are none */
  span: Span | null
  /** the stations whose record begins nowhere and whom no window bounds, which add nothing to the rows */
  unknown: number
}

function dayOf(date: Date): number {
  return Math.floor(date.getTime() / DAY) * DAY
}

/** The first and the last instant of the days a window names, or null for no usable window. */
function rangeBounds(range: DateWindow | undefined): { start: number, end: number } | null {
  if (!range?.startDate || !range.endDate)
    return null
  const start = timestampDate(range.startDate)
  const end = timestampDate(range.endDate)
  if (!start || !end)
    return null
  const bounds = { start: dayOf(start), end: dayOf(end) + DAY - 1 }
  return bounds.end >= bounds.start ? bounds : null
}

/**
 * The rows `values` returns for a selection, estimated as the server does: for each station the
 * readings its resolution can hold between the start and the end of its record within the window of
 * the request, times the parameters (once for each timestamp in the wide shape). An upper bound: a
 * station that has less data than its record makes the answer smaller.
 *
 * A station without a start of its record is counted within the window where there is one, and
 * otherwise adds nothing and is counted as `unknown`: the server assumes a start from the periods of
 * the dataset, which the page does not know. Nor does one without an end know where it ends: it
 * ends today.
 */
export function estimateRows(input: RowEstimateInput): RowEstimate {
  const now = input.now ?? Date.now()
  const bounds = rangeBounds(input.range)
  const factor = input.tidy === false && !input.asForm ? 1 : Math.max(input.parameterCount, 0)
  let rows = 0
  let counted = false
  let unknown = 0
  let first = Infinity
  let last = -Infinity
  for (const record of input.records) {
    const recordStart = record.start_timestamp ? timestampDate(record.start_timestamp)?.getTime() : undefined
    const recordEnd = record.end_timestamp ? timestampDate(record.end_timestamp)?.getTime() : undefined
    let start = recordStart ?? bounds?.start
    if (start === undefined) {
      unknown++
      continue
    }
    let end = recordEnd ?? now
    if (bounds) {
      start = Math.max(start, bounds.start)
      end = recordEnd === undefined ? bounds.end : Math.min(end, bounds.end)
    }
    if (end < start)
      continue
    counted = true
    first = Math.min(first, start)
    last = Math.max(last, end)
    rows += countReadings(input.resolution, start, end) * factor
  }
  if (!counted)
    return { rows: null, span: null, unknown }
  const span = { start: dayOf(new Date(first)), end: dayOf(new Date(last)) }
  if (input.asForm)
    rows = input.records.length * factor * countReadings(input.resolution, bounds?.start ?? first, bounds?.end ?? last)
  return { rows: hasInterval(input.resolution) ? rows : null, span, unknown }
}

/** A window of the newest part of a record, as the date fields take it. */
export interface FittingWindow {
  unit: WindowUnit
  /** how many of the unit the window spans */
  count: number
  startDate: string
  endDate: string
  /** the rows the window comes to, as far as it can be told */
  rows: number
}

export interface FittingWindowInput {
  /** the rows of the whole span, the server's own number or an estimate */
  requested: number
  /** the most rows one answer holds */
  maximum: number
  resolution: Resolution
  /** the days the request reaches: the selected stations' records within the window given */
  span: Span | null
  /**
   * How many rows a window of the span holds, where the page knows more than that they are spread
   * evenly (stations whose records end before the span does). The window's share of `requested` is
   * taken from it. Left out, the rows are spread evenly over the days.
   */
  rowsWithin?: (start: number, end: number) => number | null
  margin?: number
}

function isoDay(ms: number): string {
  return new Date(ms).toISOString().slice(0, 10)
}

/** The day `count` units before `end`, the end itself being the window's last day, so that the window holds `count` units. */
function windowStart(end: number, count: number, unit: WindowUnit): number {
  const last = new Date(end)
  if (unit === 'days')
    return end - (count - 1) * DAY
  const months = unit === 'years' ? count * 12 : count
  const target = new Date(Date.UTC(last.getUTCFullYear(), last.getUTCMonth() - months, 1))
  // a day the month does not have (31 March less a month) is its last: 28 February
  const lastDayOfTarget = new Date(Date.UTC(target.getUTCFullYear(), target.getUTCMonth() + 1, 0)).getUTCDate()
  target.setUTCDate(Math.min(last.getUTCDate(), lastDayOfTarget))
  return target.getTime() + DAY
}

/** Two significant digits, for a number that is said as "about": 476,321 is about 480,000. */
export function aboutRows(rows: number): number {
  if (rows < 100)
    return Math.round(rows)
  const magnitude = 10 ** (Math.floor(Math.log10(rows)) - 1)
  return Math.round(rows / magnitude) * magnitude
}

/**
 * The newest part of a span that fits into one answer: the largest window ending where the span
 * ends, in whole days, months or years of the unit the resolution is read in (not days for monthly
 * data, nor months for annual), whose rows are at most `margin` (90 %) of `maximum`.
 *
 * The share of the rows a window holds is its days' share of the span's, or what `rowsWithin` says.
 * The largest unit that has a window comes first: 2 years rather than 24 months, and rounded
 * down, never up. Null where the rows already fit, where there is no limit or no span, and where not
 * even one unit of the smallest does fit (one day of 1-minute data of a hundred stations is
 * 144,000 values).
 */
export function fittingWindow(input: FittingWindowInput): FittingWindow | null {
  const { requested, maximum, resolution, span } = input
  const target = Math.floor(maximum * (input.margin ?? ROW_MARGIN))
  if (!span || maximum <= 0 || !(requested > target) || target < 1)
    return null
  const spanDays = (span.end - span.start) / DAY + 1
  const total = input.rowsWithin?.(span.start, span.end + DAY - 1)
  const rowsOf = (start: number, end: number): number => {
    // a window that reaches back past the span is the span
    const from = Math.max(start, span.start)
    const within = input.rowsWithin?.(from, end + DAY - 1)
    if (within !== null && within !== undefined && total)
      return requested * within / total
    return requested * ((end - from) / DAY + 1) / spanDays
  }
  const dayLength: Record<WindowUnit, number> = { days: 1, months: 28, years: 365 }
  for (const unit of unitsOf(resolution)) {
    // the most units that could be in the span, from the shortest a unit can be
    let low = 0
    let high = Math.ceil(spanDays / dayLength[unit]) + 1
    // the largest count whose rows are within the target: rows grow with the count
    while (low < high) {
      const middle = Math.ceil((low + high) / 2)
      if (rowsOf(windowStart(span.end, middle, unit), span.end) <= target)
        low = middle
      else
        high = middle - 1
    }
    if (low >= 1) {
      const start = windowStart(span.end, low, unit)
      return { unit, count: low, startDate: isoDay(start), endDate: isoDay(span.end), rows: aboutRows(rowsOf(start, span.end)) }
    }
  }
  return null
}

export interface RefusalWindowInput extends Omit<RowEstimateInput, 'range'> {
  /** the rows the server counted, and the limit it holds them to */
  requested: number
  maximum: number
  range?: DateWindow
}

/**
 * The window that fits what the server refused (`limit-exceeded`, `rows`): the stations' records
 * within the window the user gave, the newest part of it that comes to 90 % of the limit by the
 * server's own count. The shape of the rows over time is the page's estimate, scaled to the server's
 * total, as the server counts what the page does not know (the periods a dataset reads).
 */
export function windowForRefusal(input: RefusalWindowInput): FittingWindow | null {
  const { range, ...base } = input
  // a high resolution is held to the form's count, which is never below the server's: what fits it fits the server
  const asForm = HIGH_RESOLUTIONS.includes(input.resolution)
  const { requested, ...rest } = { ...base, asForm }
  const whole = estimateRows({ ...rest, range })
  const maximum = effectiveMaximum(input.resolution, input.maximum)
  return fittingWindow({
    requested: asForm ? (whole.rows ?? requested) : requested,
    maximum,
    resolution: input.resolution,
    span: whole.span,
    rowsWithin: (start, end) => estimateRows({ ...rest, range: { startDate: isoDay(start), endDate: isoDay(end) } }).rows,
  })
}

/** What the explorer starts the date range with, once a selection is made. */
export type DefaultRange
  = | { kind: 'none' }
    | { kind: 'window', window: FittingWindow }
    | { kind: 'whole', startDate: string, endDate: string }

export interface DefaultRangeInput extends Omit<RowEstimateInput, 'range'> {
  /** the server's `max_rows`, 0 for none */
  maxRows: number
  /** a date range is asked for whatever it comes to (a high resolution), so one that fits is the whole span */
  required: boolean
}

/**
 * The range the date fields start with for a selection: none (the fields stay empty, and the request
 * is unbounded) where the whole span of the stations' records fits under 90 % of the limit, or where
 * the page cannot tell; otherwise the newest window that fits. A range that is required is the whole
 * span where that fits, and the window where it does not.
 */
export function defaultRange(input: DefaultRangeInput): DefaultRange {
  const { maxRows, required, ...base } = input
  const rest = { ...base, asForm: HIGH_RESOLUTIONS.includes(input.resolution) }
  const whole = estimateRows(rest)
  const wholeRange = (): DefaultRange => whole.span
    ? { kind: 'whole', startDate: isoDay(whole.span.start), endDate: isoDay(whole.span.end) }
    : { kind: 'none' }
  const maximum = effectiveMaximum(input.resolution, maxRows)
  if (whole.rows === null || !whole.span || maximum <= 0 || whole.rows <= Math.floor(maximum * ROW_MARGIN))
    return required ? wholeRange() : { kind: 'none' }
  const window = fittingWindow({
    requested: whole.rows,
    maximum,
    resolution: input.resolution,
    span: whole.span,
    rowsWithin: (start, end) => estimateRows({ ...rest, range: { startDate: isoDay(start), endDate: isoDay(end) } }).rows,
  })
  if (window)
    return { kind: 'window', window }
  return required ? wholeRange() : { kind: 'none' }
}
