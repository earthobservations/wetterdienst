/**
 * The geometry and the data shaping of the SVG meteogram prototype (`MeteogramSvg.vue`): what Plotly and
 * the canvas overlay of `Meteogram.vue` do by themselves, as plain functions that a test can call.
 *
 * Everything here is pure: no DOM, no Vue, no `suncalc` (the caller hands it in), so that
 * `tests/unit/meteogram-svg.test.ts` runs it in Node. Times are epoch milliseconds throughout.
 */
import { bisector } from 'd3-array'
import { scaleLinear } from 'd3-scale'
import { area, curveMonotoneX, curveStepBefore, line } from 'd3-shape'
import { DateTime } from 'luxon'
import { withData } from './format'

export interface Series {
  x: number[]
  y: number[]
}

export type PanelId = 'wind' | 'precip' | 'cloud' | 'temp' | 'pressure'

/** The panels from top to bottom, as `Meteogram.vue` stacks them */
export const PANEL_ORDER: readonly PanelId[] = ['wind', 'precip', 'cloud', 'temp', 'pressure']

const HOUR_MS = 3_600_000

export function findFirstAvailable(names: readonly string[], available: ReadonlySet<string>): string | undefined {
  return names.find(name => available.has(name))
}

/** A cloud cover that comes as a fraction or as oktas, on the percent scale the chart labels it in */
export function cloudScaleFactor(values: readonly number[]): number {
  const top = values.length > 0 ? Math.max(...values) : 0
  if (top <= 1.01)
    return 100
  if (top <= 8.01)
    return 12.5
  return 1
}

/** The long rows of `/api/values` as one series for each parameter, sorted by time, nulls dropped */
export function buildSeries(values: readonly { parameter: unknown, timestamp: string, value: number | null }[]): Map<string, Series> {
  const grouped = new Map<string, [number, number][]>()
  for (const row of values) {
    if (row.value === null || row.value === undefined || Number.isNaN(row.value))
      continue
    const ms = Date.parse(row.timestamp)
    if (Number.isNaN(ms))
      continue
    const key = String(row.parameter)
    const points = grouped.get(key) ?? []
    points.push([ms, row.value])
    grouped.set(key, points)
  }
  const series = new Map<string, Series>()
  for (const [key, points] of grouped) {
    points.sort((a, b) => a[0] - b[0])
    series.set(key, { x: points.map(p => p[0]), y: points.map(p => p[1]) })
  }
  return series
}

/**
 * The value of a series at `ms`, linear between its stamps, the end values outside them (what `interpSeries`
 * of `utils/meteogram.ts` does, on the numeric arrays: no Date for each call). Null for an empty series.
 */
export function interpAt(series: Series, ms: number): number | null {
  const n = series.x.length
  if (!n)
    return null
  if (ms <= series.x[0]!)
    return series.y[0]!
  if (ms >= series.x[n - 1]!)
    return series.y[n - 1]!
  const i = bisector((t: number) => t).left(series.x, ms)
  const t0 = series.x[i - 1]!
  const t1 = series.x[i]!
  const v0 = series.y[i - 1]!
  const v1 = series.y[i]!
  return v0 + ((ms - t0) / (t1 - t0)) * (v1 - v0)
}

/** The series with each cloud cover scaled to percent, which the chart and its tooltip both read */
export function scaleCloud(series: Series): Series {
  const factor = cloudScaleFactor(series.y)
  return factor === 1 ? series : { x: series.x, y: series.y.map(v => v * factor) }
}

/** The dew point of a temperature and a relative humidity (Magnus, as `Meteogram.vue` computes it) */
export function dewPointFromHumidity(temperature: number, humidity: number): number | null {
  const rh = humidity <= 1 ? humidity * 100 : humidity
  if (rh <= 0)
    return null
  const a = 17.27
  const b = 237.7
  const alpha = (a * temperature) / (b + temperature) + Math.log(rh / 100)
  return (b * alpha) / (a - alpha)
}

/**
 * `formatNumber` of `utils/format.ts` with the `Intl.NumberFormat` kept for each number of digits: the same
 * text, without building a formatter for every cell of a table of 3,000 (that was 17 ms of a 40 ms mount).
 */
export function numberFormatter(locale: string): (value: number, digits: number) => string {
  const tag = withData(locale, Intl.NumberFormat.supportedLocalesOf)
  const cache = new Map<number, Intl.NumberFormat>()
  return (value, digits) => {
    let nf = cache.get(digits)
    if (!nf) {
      nf = new Intl.NumberFormat(tag, { minimumFractionDigits: digits, maximumFractionDigits: digits })
      cache.set(digits, nf)
    }
    return nf.format(value)
  }
}

/** `DateTime#toLocaleString(DateTime.DATETIME_SHORT)` in `zone`, with one `Intl.DateTimeFormat` for all the calls */
export function shortDateTimeFormatter(language: string, zone: string): (ms: number) => string {
  const nf = new Intl.DateTimeFormat(withData(language, Intl.DateTimeFormat.supportedLocalesOf), {
    year: 'numeric',
    month: 'numeric',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
    timeZone: zone,
  })
  return ms => nf.format(ms)
}

// ---------------------------------------------------------------------------------------------------
// wind barbs

export interface WindBarb {
  /** Below 2.5 kt: a circle of `radius` at the tip */
  calm: boolean
  radius: number
  /** Path data of the shaft, the tip at 0,0 */
  shaft: string
  /** Path data of the full and half barbs (strokes) */
  barbs: string
  /** Path data of each pennant (filled triangles) */
  pennants: string[]
}

const fixed = (n: number) => Number(n.toFixed(2))

/**
 * The shapes of one wind barb with its tip at the origin and its tail towards the direction the wind
 * blows from: a pennant is 50 kt, a full barb 10 kt, a half barb 5 kt, and a speed under 2.5 kt a circle.
 * A knot is 1852 m per hour exactly, and the counts floor as `Meteogram.vue`'s canvas barbs do (a barb is
 * not rounded up to the next 5 kt, as the WMO's convention has it). The barbs point to the left of the wind
 * (northern hemisphere). The geometry is the canvas code's, in the same pixels, as SVG path data.
 * @param dirFrom Degrees, 0 = from the north, clockwise
 * @param speed Metres per second
 * @param scale 1 for the full-size barb, less for a compact one
 */
export function windBarb(dirFrom: number, speed: number, scale = 1): WindBarb {
  const kt = (speed * 3600) / 1852
  if (kt < 2.5)
    return { calm: true, radius: Math.round(4 * scale), shaft: '', barbs: '', pennants: [] }

  const rad = (dirFrom * Math.PI) / 180
  const shaftLen = Math.round(20 * scale)
  const ux = Math.sin(rad)
  const uy = -Math.cos(rad)
  const tailX = shaftLen * ux
  const tailY = shaftLen * uy
  // 90 degrees clockwise from tip to tail: left of the wind
  const px = -Math.cos(rad)
  const py = -Math.sin(rad)
  const barbLen = Math.round(8 * scale)
  const spacing = Math.round(5 * scale)

  let remaining = kt
  const pennants = Math.floor(remaining / 50)
  remaining -= pennants * 50
  const full = Math.floor(remaining / 10)
  remaining -= full * 10
  const half = remaining >= 5 ? 1 : 0

  const at = (offset: number): [number, number] => [tailX - offset * ux, tailY - offset * uy]
  const pennantPaths: string[] = []
  const barbPaths: string[] = []
  let offset = 0
  for (let i = 0; i < pennants; i++) {
    const [bx, by] = at(offset)
    const [cx, cy] = at(offset + spacing * 2)
    pennantPaths.push(`M${fixed(bx)},${fixed(by)}L${fixed(bx + barbLen * px)},${fixed(by + barbLen * py)}L${fixed(cx)},${fixed(cy)}Z`)
    offset += spacing * 2 + Math.round(2 * scale)
  }
  for (let i = 0; i < full; i++) {
    const [bx, by] = at(offset)
    barbPaths.push(`M${fixed(bx)},${fixed(by)}L${fixed(bx + barbLen * px)},${fixed(by + barbLen * py)}`)
    offset += spacing
  }
  if (half > 0) {
    // a lone half barb is set in from the tail, so that it is not read as a feather of a full one
    if (pennants === 0 && full === 0)
      offset += spacing
    const [bx, by] = at(offset)
    const len = Math.round(barbLen * 0.5)
    barbPaths.push(`M${fixed(bx)},${fixed(by)}L${fixed(bx + len * px)},${fixed(by + len * py)}`)
  }
  return {
    calm: false,
    radius: 0,
    shaft: `M0,0L${fixed(tailX)},${fixed(tailY)}`,
    barbs: barbPaths.join(''),
    pennants: pennantPaths,
  }
}

/**
 * The indices of the points that get a barb: as many as leave `minGapPx` between two barbs, spread
 * evenly from the first. Plotly's version drew every third point whatever the zoom; here a zoomed-in
 * chart gets a barb for every hour it has room for.
 */
export function barbIndices(times: readonly number[], domain: readonly [number, number], widthPx: number, minGapPx = 24): number[] {
  const visible: number[] = []
  times.forEach((t, i) => {
    if (t >= domain[0] && t <= domain[1])
      visible.push(i)
  })
  if (!visible.length)
    return []
  const span = Math.max(1, domain[1] - domain[0])
  const typical = times.length > 1 ? (times.at(-1)! - times[0]!) / (times.length - 1) : HOUR_MS
  const gapPx = (typical / span) * widthPx
  const every = Math.max(1, Math.ceil(minGapPx / Math.max(gapPx, 0.001)))
  return visible.filter((_, n) => n % every === 0)
}

// ---------------------------------------------------------------------------------------------------
// scales and panels

/** The value range of each panel, the same defaults as the Plotly layout of `Meteogram.vue` */
export function panelDomain(id: PanelId, values: readonly number[]): [number, number] {
  const lo = values.length ? Math.min(...values) : 0
  const hi = values.length ? Math.max(...values) : 0
  switch (id) {
    case 'wind':
      return [0, Math.max(hi, 5) * 1.6]
    case 'precip':
      return [0, Math.max(1, hi * 1.15)]
    case 'cloud':
      return [0, 100]
    case 'temp':
      return values.length ? [Math.min(0, lo) - 1, hi + 3] : [-1, 28]
    case 'pressure':
      return values.length ? [lo - 2, hi + 2] : [998, 1022]
  }
}

/** Ticks of a panel's value axis: d3's nice values, never more than `count` + 1, inside the domain */
export function valueTicks(domain: readonly [number, number], count: number): number[] {
  return scaleLinear().domain([...domain]).ticks(count).filter(v => v >= domain[0] && v <= domain[1])
}

export interface PanelBox {
  id: PanelId
  top: number
  bottom: number
  height: number
}

/** The panels stacked into `height` pixels, equal heights with `gap` between them */
export function layoutPanels(ids: readonly PanelId[], height: number, gap: number): PanelBox[] {
  const n = ids.length
  if (!n)
    return []
  const each = (height - gap * (n - 1)) / n
  return ids.map((id, i) => {
    const top = i * (each + gap)
    return { id, top, bottom: top + each, height: each }
  })
}

/** A line over `points`, monotone between the stamps (no overshoot, as Plotly's spline has), gaps where `y` is null */
export function linePath(xs: readonly number[], ys: readonly (number | null)[], x: (ms: number) => number, y: (v: number) => number, step = false): string {
  const idx = xs.map((_, i) => i)
  const gen = line<number>()
    .defined(i => ys[i] !== null && ys[i] !== undefined && !Number.isNaN(ys[i]))
    .x(i => x(xs[i]!))
    .y(i => y(ys[i] as number))
    .curve(step ? curveStepBefore : curveMonotoneX)
  return gen(idx) ?? ''
}

/** The area between a line and `baseline` (pixels) */
export function areaPath(xs: readonly number[], ys: readonly (number | null)[], x: (ms: number) => number, y: (v: number) => number, baseline: number): string {
  const idx = xs.map((_, i) => i)
  const gen = area<number>()
    .defined(i => ys[i] !== null && ys[i] !== undefined && !Number.isNaN(ys[i]))
    .x(i => x(xs[i]!))
    .y0(baseline)
    .y1(i => y(ys[i] as number))
    .curve(curveMonotoneX)
  return gen(idx) ?? ''
}

// ---------------------------------------------------------------------------------------------------
// the time axis

export interface HourTick {
  ms: number
  label: string
}

/**
 * Ticks of the shared time axis at whole local hours that divide the day, as dense as `widthPx` allows
 * (a label needs 36 px, as in `Meteogram.vue`): every hour up to a day, then 3, 6, 12 or 24 hours.
 * The labels are the station's local time. `Meteogram.vue` placed them at multiples of the UTC step,
 * which is not a round local hour anywhere east or west of Greenwich.
 */
export function hourTicks(fromMs: number, toMs: number, widthPx: number, zone: string): HourTick[] {
  const rangeHours = (toMs - fromMs) / HOUR_MS
  const maxTicks = Math.max(1, Math.floor(widthPx / 36))
  const steps = [1, 3, 6, 12, 24, 48]
  const step = steps.find(s => Math.ceil(rangeHours / s) + 1 <= maxTicks) ?? 48
  const ticks: HourTick[] = []
  let dt = DateTime.fromMillis(fromMs, { zone }).startOf('hour')
  if (dt.toMillis() < fromMs)
    dt = dt.plus({ hours: 1 })
  for (; dt.toMillis() <= toMs; dt = dt.plus({ hours: 1 })) {
    const aligned = step >= 24 ? dt.hour === 0 && (step === 24 || dt.ordinal % 2 === 0) : dt.hour % step === 0
    if (aligned)
      ticks.push({ ms: dt.toMillis(), label: dt.toFormat('HH:mm') })
  }
  return ticks
}

export interface LocalDay {
  /** Local midnight */
  startMs: number
  endMs: number
  dt: DateTime
}

/** The calendar days, in the station's zone, that `[fromMs, toMs]` touches */
export function localDays(fromMs: number, toMs: number, zone: string): LocalDay[] {
  const days: LocalDay[] = []
  let dt = DateTime.fromMillis(fromMs, { zone }).startOf('day')
  const last = DateTime.fromMillis(toMs, { zone }).startOf('day').toMillis()
  while (dt.toMillis() <= last) {
    const next = dt.plus({ days: 1 })
    days.push({ startMs: dt.toMillis(), endMs: next.toMillis(), dt })
    dt = next
  }
  return days
}

export interface SunLike {
  getTimes: (date: Date, latitude: number, longitude: number) => { sunrise?: Date | null, sunset?: Date | null, sunriseEnd?: Date | null, sunsetStart?: Date | null }
  getPosition: (date: Date, latitude: number, longitude: number) => { altitude: number }
}

export interface DaySpan {
  /** The span the day band covers, null for a polar night */
  fromMs: number | null
  toMs: number | null
  sunriseMs: number | null
  sunsetMs: number | null
}

/**
 * The band of daylight of one day. At a station inside the polar circle the sun may not rise or set:
 * the band then covers the whole day (sun above the horizon at noon) or none. `Meteogram.vue` gives
 * `toISOString()` an invalid date there. Without coordinates, 04:00 to 20:00 local.
 */
export function daySpan(day: LocalDay, coords: { latitude: number, longitude: number } | null, sun: SunLike | null): DaySpan {
  if (!coords || !sun) {
    return { fromMs: day.dt.plus({ hours: 4 }).toMillis(), toMs: day.dt.plus({ hours: 20 }).toMillis(), sunriseMs: null, sunsetMs: null }
  }
  const noon = day.dt.plus({ hours: 12 }).toJSDate()
  const times = sun.getTimes(noon, coords.latitude, coords.longitude)
  const rise = times.sunrise ?? times.sunriseEnd
  const set = times.sunset ?? times.sunsetStart
  const riseMs = rise && !Number.isNaN(rise.getTime()) ? rise.getTime() : null
  const setMs = set && !Number.isNaN(set.getTime()) ? set.getTime() : null
  if (riseMs !== null && setMs !== null)
    return { fromMs: riseMs, toMs: setMs, sunriseMs: riseMs, sunsetMs: setMs }
  const up = sun.getPosition(noon, coords.latitude, coords.longitude).altitude > 0
  return up
    ? { fromMs: day.startMs, toMs: day.endMs, sunriseMs: null, sunsetMs: null }
    : { fromMs: null, toMs: null, sunriseMs: null, sunsetMs: null }
}

/** The opacity of a day band, less for a cloudier noon (the formula of `Meteogram.vue`), `cloud` a fraction */
export function dayAlpha(cloud: number): number {
  return 0.55 - Math.min(0.35, cloud * 0.5)
}

// ---------------------------------------------------------------------------------------------------
// zoom, and stepping by keys

export type Domain = [number, number]

/** The window zoomed by `factor` (> 1 zooms in) around `anchorMs`, kept inside `full` and at least `minSpanMs` wide */
export function zoomDomain(domain: Domain, full: Domain, factor: number, anchorMs: number, minSpanMs = 6 * HOUR_MS): Domain {
  const span = domain[1] - domain[0]
  const fullSpan = full[1] - full[0]
  const next = Math.min(fullSpan, Math.max(Math.min(minSpanMs, fullSpan), span / factor))
  const ratio = span > 0 ? (anchorMs - domain[0]) / span : 0.5
  return clampDomain([anchorMs - ratio * next, anchorMs - ratio * next + next], full)
}

/** The window moved by `deltaMs` and kept inside `full`, its width unchanged */
export function panDomain(domain: Domain, full: Domain, deltaMs: number): Domain {
  return clampDomain([domain[0] + deltaMs, domain[1] + deltaMs], full)
}

function clampDomain(domain: Domain, full: Domain): Domain {
  const span = Math.min(domain[1] - domain[0], full[1] - full[0])
  const start = Math.min(Math.max(domain[0], full[0]), full[1] - span)
  return [start, start + span]
}

/** The window that holds `ms`, moved the least that does it */
export function revealInDomain(domain: Domain, full: Domain, ms: number): Domain {
  if (ms < domain[0])
    return panDomain(domain, full, ms - domain[0])
  if (ms > domain[1])
    return panDomain(domain, full, ms - domain[1])
  return domain
}

/**
 * The index the arrow keys step to: left and right by one stamp, Shift with them or Page Up and Down by
 * a day's worth (24 stamps at an hourly step; `pageSize` says), Home and End to the ends. `current` null
 * (nothing selected yet) starts at the first stamp that is `start`. Null for any other key.
 */
export function stepIndex(current: number | null, key: string, shift: boolean, length: number, pageSize = 24, start = 0): number | null {
  if (length <= 0)
    return null
  const from = current ?? start
  const clamp = (i: number) => Math.min(length - 1, Math.max(0, i))
  switch (key) {
    case 'ArrowRight':
      return current === null ? clamp(start) : clamp(from + (shift ? pageSize / 4 : 1))
    case 'ArrowLeft':
      return current === null ? clamp(start) : clamp(from - (shift ? pageSize / 4 : 1))
    case 'PageDown':
      return clamp(from + pageSize)
    case 'PageUp':
      return clamp(from - pageSize)
    case 'Home':
      return 0
    case 'End':
      return length - 1
    default:
      return null
  }
}

const bisectTime = bisector((t: number) => t).center

/** The index of the stamp nearest to `ms` in the sorted `times`, -1 for none */
export function nearestTimeIndex(times: readonly number[], ms: number): number {
  if (!times.length)
    return -1
  return bisectTime(times as number[], ms)
}

/** Where the tooltip's left edge goes: right of the crosshair, left of it where it would leave the chart */
export function tooltipLeft(crossX: number, tooltipWidth: number, frameWidth: number, offset = 12): number {
  const right = crossX + offset
  if (right + tooltipWidth <= frameWidth)
    return right
  return Math.max(0, crossX - offset - tooltipWidth)
}
