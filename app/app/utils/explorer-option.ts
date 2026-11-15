import type { EChartsCoreOption } from 'echarts/core'
/**
 * The option of the Explorer's chart (Apache ECharts, drawn as SVG): a line, with markers where the series are few, for
 * each series on a time axis (UTC, as the chart has always been) with a y axis of its own scale, the legend as the
 * `custom` series of a layer without a coordinate system (so that it is in a saved image too), and a crosshair that the
 * keys and the pointer move. Pure: series, a theme, a size and a window in, an option out, so that tests and the image
 * export build it without a browser (GH-4096).
 */
import type { ChartTheme } from './chart-theme'
import type { DrawnPoints, ExplorerSeries, ExplorerWindow, Scale } from './explorer-model'
import type { TextMeasure } from './stripes'
import { withAlpha } from './chart-theme'
import { drawnPoints, minSpanOf, niceScale, seriesColour, shownSeries, valueExtent } from './explorer-model'
import { withData } from './format'
import { measureWithCanvas } from './stripes'

/** The font of the chart, on the page and in a saved image, which has no web font of the page's to draw with */
export const EXPLORER_FONT_FAMILY = 'Arial, sans-serif'
/** The height of the chart on the page: the single chart's, and a facet's (as with Plotly) */
export const EXPLORER_HEIGHT = 400
export const EXPLORER_FACET_HEIGHT = 300
/** The plot never gets lower than this, however many rows of legend the width makes */
export const MIN_PLOT_HEIGHT = 120
/** The room at the right and below the plot (the time labels), and above the legend */
export const MARGIN_RIGHT = 20
export const MARGIN_BOTTOM = 34
const LEGEND_PAD = 6

/** The legend's measures in px: a row, the line that is the swatch, the gap after it and between two items, the type */
export const LEGEND_ROW = 24
export const LEGEND_SWATCH = 24
const LEGEND_GAP = 6
const LEGEND_BETWEEN = 18
export const LEGEND_FONT_SIZE = 13
const AXIS_FONT_SIZE = 12

/** The size of the marker of a point, in px, where a series has few enough to be marked */
const MARKER_SIZE = 6

export interface ExplorerOptionInput {
  /** every series, those the legend turned off too */
  series: readonly ExplorerSeries[]
  hidden: ReadonlySet<string>
  theme: ChartTheme
  /** the window shown and the whole chart */
  window: ExplorerWindow
  bounds: ExplorerWindow
  /** the chart's size in px: its height may grow where the legend takes many rows */
  width: number
  height: number
  /** a chart of many points: a thin line and no markers */
  large: boolean
  locale: string
  fontFamily?: string
  /** The paper behind the chart: the page's own shows through on the page (none), a saved image has its own */
  background?: string
  measure?: TextMeasure
}

// -- numbers and times, as the page writes them ---------------------------------------------------------------------

const numberFormats = new Map<string, Intl.NumberFormat>()
/** A number with as many fraction digits as it has, up to `digits`: 12.3, not 12.30 */
export function valueFormat(locale: string, digits = 3): Intl.NumberFormat {
  const key = `${locale}|${digits}`
  let format = numberFormats.get(key)
  if (!format) {
    format = new Intl.NumberFormat(withData(locale, Intl.NumberFormat.supportedLocalesOf), { minimumFractionDigits: 0, maximumFractionDigits: digits })
    numberFormats.set(key, format)
  }
  return format
}
const tickFormats = new Map<string, Intl.NumberFormat>()
function tickFormat(locale: string, decimals: number): Intl.NumberFormat {
  const key = `${locale}|${decimals}`
  let format = tickFormats.get(key)
  if (!format) {
    format = new Intl.NumberFormat(withData(locale, Intl.NumberFormat.supportedLocalesOf), { minimumFractionDigits: decimals, maximumFractionDigits: decimals })
    tickFormats.set(key, format)
  }
  return format
}

const timeFormats = new Map<string, Intl.DateTimeFormat>()
function timeFormat(locale: string, name: string, options: Intl.DateTimeFormatOptions): Intl.DateTimeFormat {
  const key = `${locale}|${name}`
  let format = timeFormats.get(key)
  if (!format) {
    format = new Intl.DateTimeFormat(withData(locale, Intl.DateTimeFormat.supportedLocalesOf), { timeZone: 'UTC', ...options })
    timeFormats.set(key, format)
  }
  return format
}

const DAY = 86_400_000

/** The label of a tick of the time axis: what a window of `span` ms is read by (years, months, days, then hours, with the day where midnight is) */
export function tickLabel(ms: number, span: number, locale: string): string {
  if (span >= 900 * DAY)
    return timeFormat(locale, 'year', { year: 'numeric' }).format(ms)
  if (span >= 150 * DAY)
    return timeFormat(locale, 'month-year', { month: 'short', year: 'numeric' }).format(ms)
  if (span >= 40 * DAY)
    return timeFormat(locale, 'day-month-year', { day: 'numeric', month: 'short', year: 'numeric' }).format(ms)
  if (span >= 3 * DAY || ms % DAY === 0)
    return timeFormat(locale, 'day-month', { day: 'numeric', month: 'short' }).format(ms)
  return timeFormat(locale, 'hour-minute', { hour: '2-digit', minute: '2-digit', hourCycle: 'h23' }).format(ms)
}

/**
 * The moment a readout and a screen reader name, in UTC: the day where every reading of the chart is at midnight (a daily
 * series, a monthly one), the day and the time with "UTC" where any is not.
 */
export function momentLabel(ms: number, locale: string, withTime: boolean): string {
  if (!withTime)
    return timeFormat(locale, 'date', { dateStyle: 'medium' }).format(ms)
  return `${timeFormat(locale, 'date-time', { dateStyle: 'medium', timeStyle: 'short', hourCycle: 'h23' }).format(ms)} UTC`
}

/** Whether any moment of the series is not at midnight UTC, so that a readout has to give the time */
export function hasTimeOfDay(series: readonly ExplorerSeries[]): boolean {
  for (const item of series) {
    if (item.kind !== 'values')
      continue
    for (let i = 0; i < item.x.length; i++) {
      if (item.x[i]! % DAY !== 0)
        return true
    }
  }
  return false
}

// -- the frame: where everything is ---------------------------------------------------------------------------------

export interface LegendItem {
  index: number
  id: string
  x: number
  y: number
  width: number
  height: number
  text: string
}

export interface LegendLayout {
  items: LegendItem[]
  /** the height the legend takes above the plot, with its padding; 0 with no series */
  height: number
}

/** `text` as long as it fits `maxPx` in `font`, with an ellipsis where it was cut */
export function fitText(text: string, maxPx: number, font: string, size: number, measure: TextMeasure): string {
  const widthOf = (value: string) => measure(value, font) ?? value.length * size * 0.55
  if (widthOf(text) <= maxPx)
    return text
  let end = text.length
  while (end > 1 && widthOf(`${text.slice(0, end)}…`) > maxPx)
    end--
  return `${text.slice(0, end).trimEnd()}…`
}

/** The legend's items in rows as wide as the chart lets them be, each row in the middle of it as Plotly's was */
export function legendLayout(names: readonly { id: string, name: string }[], width: number, measure: TextMeasure = measureWithCanvas): LegendLayout {
  if (!names.length)
    return { items: [], height: 0 }
  const font = `${LEGEND_FONT_SIZE}px ${EXPLORER_FONT_FAMILY}`
  const room = Math.max(60, width - 2 * LEGEND_PAD)
  const taken = LEGEND_SWATCH + LEGEND_GAP
  const rows: { index: number, id: string, text: string, width: number }[][] = [[]]
  let used = 0
  names.forEach(({ id, name }, index) => {
    const text = fitText(name, room - taken, font, LEGEND_FONT_SIZE, measure)
    const textPx = measure(text, font) ?? text.length * LEGEND_FONT_SIZE * 0.55
    const itemPx = taken + textPx
    const row = rows[rows.length - 1]!
    if (row.length && used + LEGEND_BETWEEN + itemPx > room) {
      rows.push([{ index, id, text, width: itemPx }])
      used = itemPx
    }
    else {
      used += (row.length ? LEGEND_BETWEEN : 0) + itemPx
      row.push({ index, id, text, width: itemPx })
    }
  })
  const items: LegendItem[] = []
  rows.forEach((row, rowIndex) => {
    const rowPx = row.reduce((sum, item) => sum + item.width, 0) + LEGEND_BETWEEN * (row.length - 1)
    let x = Math.max(LEGEND_PAD, (width - rowPx) / 2)
    for (const item of row) {
      items.push({ index: item.index, id: item.id, text: item.text, x, y: LEGEND_PAD + rowIndex * LEGEND_ROW, width: item.width, height: LEGEND_ROW })
      x += item.width + LEGEND_BETWEEN
    }
  })
  return { items, height: LEGEND_PAD * 2 + rows.length * LEGEND_ROW - 4 }
}

export interface ExplorerFrame {
  width: number
  height: number
  plot: { left: number, top: number, width: number, height: number }
  legend: LegendLayout
  scale: Scale
  /** what is drawn of each shown series */
  drawn: Map<string, DrawnPoints>
  /** the labels of the y axis, as written */
  yLabels: string[]
  hasZero: boolean
}

/** Where everything is, in px from the chart's top left, and what is drawn: the data is cut to the window and to the plot's width */
export function explorerFrame(input: ExplorerOptionInput): ExplorerFrame {
  const { series, hidden, window: win, width, locale } = input
  const measure = input.measure ?? measureWithCanvas
  const shown = shownSeries(series, hidden)
  const legend = legendLayout(series.map(({ id, name }) => ({ id, name })), width, measure)
  // the points are cut to a plot that is about as wide as the chart: the gutter is not known before the labels are
  const estimate = Math.max(100, width - 70)
  const drawn = new Map<string, DrawnPoints>()
  const extents: [number, number][] = []
  for (const item of shown) {
    const points = drawnPoints(item, win, estimate)
    drawn.set(item.id, points)
    const extent = valueExtent([points])
    if (extent && item.kind === 'values')
      extents.push(extent)
  }
  // a trendline within the window reaches as far as the values do; its ends are in the range where they are in the window
  for (const item of shown) {
    if (item.kind !== 'trend')
      continue
    for (let i = 0; i < item.x.length; i++) {
      const y = item.y[i]
      if (y !== null && y !== undefined && item.x[i]! >= win.start && item.x[i]! <= win.end)
        extents.push([y, y])
    }
  }
  const min = Math.min(...extents.map(extent => extent[0]))
  const max = Math.max(...extents.map(extent => extent[1]))
  const scale = extents.length ? niceScale(min, max) : niceScale(0, 1)
  const yLabels: string[] = []
  const format = tickFormat(locale, scale.decimals)
  const steps = Math.min(40, Math.round((scale.max - scale.min) / scale.interval))
  for (let i = 0; i <= steps; i++)
    yLabels.push(format.format(scale.min + i * scale.interval))
  const font = `${AXIS_FONT_SIZE}px ${EXPLORER_FONT_FAMILY}`
  const widest = Math.max(...yLabels.map(label => measure(label, font) ?? label.length * AXIS_FONT_SIZE * 0.6))
  const left = Math.min(120, Math.max(40, Math.ceil(widest) + 18))
  const top = legend.height + LEGEND_PAD
  const plotHeight = Math.max(MIN_PLOT_HEIGHT, input.height - top - MARGIN_BOTTOM)
  return {
    width,
    height: top + plotHeight + MARGIN_BOTTOM,
    plot: { left, top, width: Math.max(1, width - left - MARGIN_RIGHT), height: plotHeight },
    legend,
    scale,
    drawn,
    yLabels,
    hasZero: scale.min <= 0 && scale.max >= 0,
  }
}

/** The pixel of the moment `t` on the chart, left to right */
export function xOfTime(t: number, frame: ExplorerFrame, win: ExplorerWindow): number {
  return frame.plot.left + ((t - win.start) / (win.end - win.start)) * frame.plot.width
}

/** The moment at the pixel `x` of the chart */
export function timeAtX(x: number, frame: ExplorerFrame, win: ExplorerWindow): number {
  return win.start + ((x - frame.plot.left) / frame.plot.width) * (win.end - win.start)
}

// -- the option -----------------------------------------------------------------------------------------------------

function legendSeries(input: ExplorerOptionInput, frame: ExplorerFrame, ink: Inks) {
  const { series, hidden, theme, large } = input
  const font = `${LEGEND_FONT_SIZE}px ${input.fontFamily ?? EXPLORER_FONT_FAMILY}`
  return {
    id: 'legend',
    type: 'custom',
    coordinateSystem: 'none',
    silent: true,
    animation: false,
    z: 30,
    data: frame.legend.items.map(item => [item.index]),
    renderItem: (_params: unknown, api: { value: (dimension: number) => number }) => {
      const item = frame.legend.items[api.value(0)]!
      const entry = series[item.index]!
      const off = hidden.has(entry.id)
      const colour = seriesColour(entry.colorIndex, theme.dark)
      const middle = item.y + LEGEND_ROW / 2 - 2
      const children: Record<string, unknown>[] = [
        // a swatch drawn as the line is: a dash for a trendline, a dot on it for a series that has markers; one that is off is a thin ring
        {
          type: 'line',
          silent: true,
          shape: { x1: item.x, y1: middle, x2: item.x + LEGEND_SWATCH, y2: middle },
          style: { stroke: off ? ink.muted : colour, lineWidth: entry.kind === 'trend' ? 3 : 2, lineDash: entry.kind === 'trend' || off ? [5, 3] : undefined, lineCap: 'butt' },
        },
      ]
      if (entry.kind === 'values' && !large) {
        children.push({
          type: 'circle',
          silent: true,
          shape: { cx: item.x + LEGEND_SWATCH / 2, cy: middle, r: 3.5 },
          style: { fill: off ? 'transparent' : colour, stroke: off ? ink.muted : colour, lineWidth: 1.5 },
        })
      }
      children.push({
        type: 'text',
        silent: true,
        style: { text: item.text, x: item.x + LEGEND_SWATCH + LEGEND_GAP, y: middle, fill: off ? ink.muted : ink.text, font, textVerticalAlign: 'middle', textAlign: 'left' },
      })
      // what is off is struck out as well as grey: the state is not the colour's alone
      if (off) {
        const textPx = item.width - LEGEND_SWATCH - LEGEND_GAP
        children.push({
          type: 'line',
          silent: true,
          shape: { x1: item.x + LEGEND_SWATCH + LEGEND_GAP, y1: middle, x2: item.x + LEGEND_SWATCH + LEGEND_GAP + textPx, y2: middle },
          style: { stroke: ink.muted, lineWidth: 1 },
        })
      }
      return { type: 'group', silent: true, children }
    },
  }
}

interface Inks {
  text: string
  muted: string
  grid: string
  zero: string
  paper: string
}

function inksOf(theme: ChartTheme): Inks {
  const text = theme.text || '#0f172b'
  return {
    text,
    muted: theme.textMuted || text,
    grid: theme.grid || withAlpha(text, 0.15),
    zero: theme.zeroline || theme.textMuted || text,
    paper: theme.paper || '#ffffff',
  }
}

/** A cursor at the moment `t` (the crosshair and a dot on each row's value): the part of the option that a key or the pointer changes. Merged into the chart's option. */
export function cursorUpdate(theme: ChartTheme, t: number | null, rows: readonly { colorIndex: number, value: number }[]): EChartsCoreOption {
  const ink = inksOf(theme)
  return {
    series: [{
      id: 'cursor',
      type: 'custom',
      xAxisIndex: 0,
      yAxisIndex: 0,
      silent: true,
      animation: false,
      clip: false,
      z: 20,
      data: t === null ? [] : [[t]],
      renderItem: (params: any, api: any) => {
        const x = api.coord([t, 0])[0]
        const { y: top, height } = params.coordSys
        const children: Record<string, unknown>[] = [
          { type: 'line', silent: true, shape: { x1: x, y1: top, x2: x, y2: top + height }, style: { stroke: ink.muted, lineWidth: 1, lineDash: [4, 3] } },
        ]
        for (const row of rows) {
          children.push({
            type: 'circle',
            silent: true,
            shape: { cx: x, cy: api.coord([t, row.value])[1], r: 5 },
            // the paper round the dot lifts it off the line it is on
            style: { fill: seriesColour(row.colorIndex, theme.dark), stroke: ink.paper, lineWidth: 2 },
          })
        }
        return { type: 'group', silent: true, children }
      },
    }],
  }
}

/** The option of the chart in `input`, in the frame it makes (the chart's own, which the component has made already, or one made here) */
export function buildExplorerOption(input: ExplorerOptionInput, frame: ExplorerFrame = explorerFrame(input)): EChartsCoreOption {
  const { series, hidden, theme, window: win, bounds, large, locale } = input
  const ink = inksOf(theme)
  const fontFamily = input.fontFamily ?? EXPLORER_FONT_FAMILY
  const span = win.end - win.start
  const base = { xAxisIndex: 0, yAxisIndex: 0, silent: true, animation: false, clip: true }

  const lines: Record<string, unknown>[] = []
  for (const item of shownSeries(series, hidden)) {
    const points = frame.drawn.get(item.id)!
    const colour = seriesColour(item.colorIndex, theme.dark)
    const trend = item.kind === 'trend'
    lines.push({
      ...base,
      id: item.id,
      name: item.name,
      type: 'line',
      // a trendline is on top of the values, as it was
      z: trend ? 3 : 2,
      data: points.x.map((moment, index) => [moment, points.y[index]]),
      showSymbol: !trend && !large,
      symbol: 'circle',
      symbolSize: MARKER_SIZE,
      // a gap in the data is a gap in the line
      connectNulls: false,
      itemStyle: { color: colour },
      lineStyle: { color: colour, width: trend ? 4 : large ? 1 : 2, type: trend ? 'dashed' : 'solid' },
    })
  }
  if (frame.hasZero) {
    lines.push({
      ...base,
      id: 'zero',
      type: 'line',
      z: 1,
      data: [[bounds.start, 0], [bounds.end, 0]],
      showSymbol: false,
      lineStyle: { color: ink.zero, width: 1 },
    })
  }

  return {
    // none: a chart that moves on its own is a motion nobody asked for (`prefers-reduced-motion` has nothing to switch off)
    animation: false,
    useUTC: true,
    backgroundColor: input.background ?? 'transparent',
    textStyle: { fontFamily, color: ink.text },
    grid: [{ left: frame.plot.left, top: frame.plot.top, width: frame.plot.width, height: frame.plot.height, show: false, outerBoundsMode: 'none' }],
    xAxis: [{
      type: 'time',
      gridIndex: 0,
      min: bounds.start,
      max: bounds.end,
      splitNumber: Math.max(2, Math.floor(frame.plot.width / 100)),
      axisLine: { show: false },
      axisTick: { show: false },
      splitLine: { show: true, lineStyle: { color: ink.grid, width: 1 } },
      axisLabel: {
        color: ink.muted,
        fontSize: AXIS_FONT_SIZE,
        fontFamily,
        margin: 10,
        hideOverlap: true,
        // one format for the window, from what it spans: Intl in UTC, in the language of the page
        formatter: (value: number) => tickLabel(value, span, locale),
      },
    }],
    yAxis: [{
      type: 'value',
      gridIndex: 0,
      min: frame.scale.min,
      max: frame.scale.max,
      interval: frame.scale.interval,
      axisLine: { show: false },
      axisTick: { show: false },
      splitLine: { show: true, lineStyle: { color: ink.grid, width: 1 } },
      axisLabel: {
        color: ink.muted,
        fontSize: AXIS_FONT_SIZE,
        fontFamily,
        margin: 8,
        formatter: (value: number) => tickFormat(locale, frame.scale.decimals).format(value),
      },
    }],
    // a wheel with Ctrl (a trackpad's pinch) and a pinch zoom; a drag is the zoom box, which the component draws
    dataZoom: [{
      id: 'zoom',
      type: 'inside',
      xAxisIndex: [0],
      startValue: win.start,
      endValue: win.end,
      filterMode: 'none',
      zoomOnMouseWheel: 'ctrl',
      moveOnMouseMove: false,
      moveOnMouseWheel: false,
      preventDefaultMouseMove: false,
      minValueSpan: minSpanOf(series),
      maxValueSpan: bounds.end - bounds.start,
    }],
    series: [
      ...lines,
      legendSeries(input, frame, ink),
      // the crosshair, empty until the keys or the pointer put it somewhere
      ...(cursorUpdate(theme, null, []).series as Record<string, unknown>[]),
    ],
  }
}
