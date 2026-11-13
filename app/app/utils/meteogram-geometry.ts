/**
 * The shape of the meteogram, in pixels: fixed heights for the panels and a fixed width for each hour, so that the
 * size of the screen and the way it is held never change what the chart looks like (GH-4059). A narrow screen shows
 * a part of the forecast and the rest is a scroll away, with the axes in view; a wide one shows more of it, and
 * only a short forecast is drawn wider than the spacing, up to a cap.
 *
 * Everything here is plain arithmetic, held by tests; the chart reads it, and never the screen, to place anything.
 */

/** The panels, from the top of the chart to its foot */
export const PANEL_ORDER = ['wind', 'precip', 'cloud', 'temp', 'pressure'] as const
export type PanelName = typeof PANEL_ORDER[number]

/** The height of each panel's plot in px, whatever the screen */
export const PANEL_HEIGHT: Record<PanelName, number> = { wind: 124, precip: 88, cloud: 80, temp: 156, pressure: 84 }
/** The room between two panels, in which the lower one's top label sits */
export const PANEL_GAP = 14
/** The strip above the panels: the day names, the hours and the weather symbols */
export const HEADER_ROWS = { days: 20, hours: 18, symbols: 36 } as const
export const HEADER_PAD = 6
/** The room under the last panel */
export const FOOT_PAD = 6

/** The width of an hour in px: what a forecast is drawn at on any screen it does not fit */
export const HOUR_PX = 10
/** The widest an hour is drawn, which a short forecast on a wide screen is stretched to */
export const HOUR_MAX_PX = 22
/** The widths the plot leaves at the left, for the axis' title and labels, and at the right */
export const GUTTER_LEFT = 68
export const GUTTER_RIGHT = 10
/** The hours the chart can be zoomed in to, across its plot */
export const MIN_SPAN_HOURS = 6

export const HOUR_MS = 3_600_000

export interface PanelRow { id: PanelName, top: number, height: number }
export interface ChartLayout {
  /** the strip of day names, hours and symbols: its top and height, and where each row of it is */
  header: { top: number, height: number, daysTop: number, hoursTop: number, symbolsTop: number | null }
  rows: PanelRow[]
  /** the height of the whole chart in px */
  height: number
}

/**
 * Where everything stands: the header, then the panels that are shown in their order, each at its fixed height
 * and a gap below the one before. The symbols' row is left out of the header where the forecast has none.
 */
export function chartLayout(panels: readonly PanelName[], symbols: boolean): ChartLayout {
  const headerHeight = HEADER_ROWS.days + HEADER_ROWS.hours + (symbols ? HEADER_ROWS.symbols : 0) + HEADER_PAD
  const header = {
    top: 0,
    height: headerHeight,
    daysTop: 0,
    hoursTop: HEADER_ROWS.days,
    symbolsTop: symbols ? HEADER_ROWS.days + HEADER_ROWS.hours : null,
  }
  const rows: PanelRow[] = []
  let top = headerHeight
  for (const id of PANEL_ORDER.filter(panel => panels.includes(panel))) {
    rows.push({ id, top, height: PANEL_HEIGHT[id] })
    top += PANEL_HEIGHT[id] + PANEL_GAP
  }
  return { header, rows, height: rows.length ? top - PANEL_GAP + FOOT_PAD : headerHeight + FOOT_PAD }
}

/**
 * The width of an hour of a forecast of `hours` hours on a plot `plotPx` wide: `HOUR_PX`, or, where the whole
 * forecast is narrower than the plot at that spacing, the width that fills the plot, up to `HOUR_MAX_PX`.
 */
export function hourWidth(plotPx: number, hours: number): number {
  if (hours <= 0 || plotPx <= 0)
    return HOUR_PX
  if (hours * HOUR_PX >= plotPx)
    return HOUR_PX
  return Math.min(HOUR_MAX_PX, plotPx / hours)
}

/** The width of the plot a forecast is drawn in: all of it where it needs it, never wider than the screen gives */
export function plotWidthFor(availablePx: number, hours: number, gutterLeft = GUTTER_LEFT): number {
  const available = Math.max(0, availablePx - gutterLeft - GUTTER_RIGHT)
  return Math.min(available, hours * hourWidth(available, hours))
}

/** A span of time, in ms since the epoch */
export interface TimeWindow { start: number, end: number }

/** The window a chart opens in: from the first hour, `plotPx` wide at the spacing of an hour, or all the forecast where that is less */
export function defaultWindow(bounds: TimeWindow, plotPx: number): TimeWindow {
  const hours = (bounds.end - bounds.start) / HOUR_MS
  const span = Math.min(hours, plotPx / hourWidth(plotPx, hours)) * HOUR_MS
  return { start: bounds.start, end: bounds.start + span }
}

/** The window moved to lie inside `bounds` with at least `MIN_SPAN_HOURS` and at most all of it, keeping its centre where it can */
export function clampWindow(win: TimeWindow, bounds: TimeWindow): TimeWindow {
  const full = bounds.end - bounds.start
  const span = Math.min(full, Math.max(Math.min(MIN_SPAN_HOURS * HOUR_MS, full), win.end - win.start))
  const start = Math.min(bounds.end - span, Math.max(bounds.start, win.start))
  return { start, end: start + span }
}

/** The window grown (`factor` above 1) or shrunk (below 1) around the instant `anchor`, which stays where it is on the screen */
export function zoomWindow(win: TimeWindow, factor: number, anchor: number, bounds: TimeWindow): TimeWindow {
  const span = win.end - win.start
  const next = span * factor
  const ratio = span > 0 ? (anchor - win.start) / span : 0.5
  const start = anchor - ratio * next
  return clampWindow({ start, end: start + next }, bounds)
}

/** The window moved by `deltaMs` and held inside `bounds` */
export function panWindow(win: TimeWindow, deltaMs: number, bounds: TimeWindow): TimeWindow {
  return clampWindow({ start: win.start + deltaMs, end: win.end + deltaMs }, bounds)
}

/** The window moved the least that shows the instant `t` */
export function revealInstant(win: TimeWindow, t: number, bounds: TimeWindow, marginMs = 2 * HOUR_MS): TimeWindow {
  if (t - marginMs < win.start)
    return panWindow(win, t - marginMs - win.start, bounds)
  if (t + marginMs > win.end)
    return panWindow(win, t + marginMs - win.end, bounds)
  return win
}

/**
 * The strip that scrolls sideways under the chart, which stays in view while it does: its width, and how far it is
 * scrolled for a window. A window `plotPx` wide holds `win`'s span; scrolling by a pixel moves it by a pixel at that
 * spacing, so the strip is as wide as the forecast would be at the spacing, plus the gutters.
 */
export function scrollStrip(win: TimeWindow, bounds: TimeWindow, plotPx: number, outerPx: number): { width: number, left: number } {
  const pxPerMs = plotPx / Math.max(1, win.end - win.start)
  return {
    width: Math.round((bounds.end - bounds.start) * pxPerMs + (outerPx - plotPx)),
    left: Math.round((win.start - bounds.start) * pxPerMs),
  }
}

/** The window a strip scrolled to `left` px stands for, the width of the window being `span` ms */
export function windowFromScroll(left: number, span: number, bounds: TimeWindow, plotPx: number): TimeWindow {
  const msPerPx = span / Math.max(1, plotPx)
  const start = bounds.start + left * msPerPx
  return clampWindow({ start, end: start + span }, bounds)
}

/**
 * How many of the items of a row to skip, so that two drawn are `minPx` apart: an item every `step`-th of those
 * `cadenceHours` apart. A row of barbs or symbols thins with the zoom by this, and never overlaps.
 */
export function every(pxPerHour: number, cadenceHours: number, minPx: number): number {
  return Math.max(1, Math.ceil(minPx / Math.max(1e-6, pxPerHour * cadenceHours)))
}

/** The hours between two labels of the time axis, the finest of these with `minPx` for each */
export const LABEL_STEPS_HOURS = [1, 2, 3, 6, 12, 24] as const
export function labelStepHours(pxPerHour: number, minPx: number): number {
  return LABEL_STEPS_HOURS.find(step => step * pxPerHour >= minPx) ?? LABEL_STEPS_HOURS.at(-1)!
}

// -- wind barbs ----------------------------------------------------------------------------------------------------

/** What of a barb is drawn, in px from the point it marks (its tip): the shaft, the full and half barbs and the pennants */
export interface Barb {
  /** a circle of this radius, for a calm */
  calm: number | null
  shaft: [number, number, number, number] | null
  /** each a line from the shaft out */
  ticks: [number, number, number, number][]
  /** each a triangle */
  pennants: [number, number][][]
  lineWidth: number
}

/**
 * The barb of a wind from `dirFrom` degrees of `knots` knots: standard meteorological barbs, the tip at the point,
 * the shaft towards the direction the wind comes from, a pennant for 50 kt, a full barb for 10 and a half for 5, the
 * barbs on the left of the wind (the northern hemisphere's convention), under 2.5 kt a circle. The speed is the one
 * in knots whatever unit the chart shows: a barb is a drawing of the wind, not of a number.
 */
export function windBarb(dirFrom: number, knots: number, scale = 1): Barb {
  const lineWidth = Math.max(1, 1.5 * scale)
  if (knots < 2.5)
    return { calm: Math.round(4 * scale), shaft: null, ticks: [], pennants: [], lineWidth }

  const rad = (dirFrom * Math.PI) / 180
  const shaftLen = Math.round(20 * scale)
  const tailX = shaftLen * Math.sin(rad)
  const tailY = -shaftLen * Math.cos(rad)
  const ux = tailX / shaftLen
  const uy = tailY / shaftLen
  // 90 degrees clockwise from the tip towards the tail: the left of the wind
  const px = -Math.cos(rad)
  const py = -Math.sin(rad)
  const barbLen = Math.round(8 * scale)
  const spacing = Math.round(5 * scale)

  let remaining = knots
  const pennantCount = Math.floor(remaining / 50)
  remaining -= pennantCount * 50
  const fullCount = Math.floor(remaining / 10)
  remaining -= fullCount * 10
  const half = remaining >= 5

  const ticks: Barb['ticks'] = []
  const pennants: Barb['pennants'] = []
  let offset = 0
  for (let i = 0; i < pennantCount; i++) {
    const bx = tailX - offset * ux
    const by = tailY - offset * uy
    const bx2 = tailX - (offset + spacing * 2) * ux
    const by2 = tailY - (offset + spacing * 2) * uy
    pennants.push([[bx, by], [bx + barbLen * px, by + barbLen * py], [bx2, by2]])
    offset += spacing * 2 + Math.round(2 * scale)
  }
  for (let i = 0; i < fullCount; i++) {
    const bx = tailX - offset * ux
    const by = tailY - offset * uy
    ticks.push([bx, by, bx + barbLen * px, by + barbLen * py])
    offset += spacing
  }
  if (half) {
    if (pennantCount === 0 && fullCount === 0)
      offset += spacing
    const bx = tailX - offset * ux
    const by = tailY - offset * uy
    const len = Math.round(barbLen * 0.5)
    ticks.push([bx, by, bx + len * px, by + len * py])
  }
  return { calm: null, shaft: [0, 0, tailX, tailY], ticks, pennants, lineWidth }
}

/** Metres per second as knots, which a barb counts in */
export function knotsOf(metresPerSecond: number): number {
  return (metresPerSecond * 3600) / 1852
}
