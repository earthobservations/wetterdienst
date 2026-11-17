import type { EChartsCoreOption } from 'echarts/core'
/**
 * The option of the climate stripes (Apache ECharts, drawn as SVG): a stripe for each year as a `custom` series on a
 * value axis of years (so that a year without a value is a gap, as before), the availability line as a `custom` series
 * of one bar for each run of years with a value (it spans exactly their stripes), the optional lines of the timeseries and
 * the trend as the library's own `line` series, and the title, the years, the source and the availability label as text
 * elements of a `custom` series without a coordinate system, placed in px. Pure: values, a theme, a size and a window in, an option out, so
 * that tests and the image export build it without a browser (GH-4068).
 *
 * The same years can be drawn as bars (GH-4156): a bar for each year, as high as its anomaly (the backend's, from the mean of the
 * reference) and in the colour of its class, on a range with zero in it (the zero line is drawn); with a scale, a y axis in the unit
 * of the anomaly (grid lines and labels, and a subtitle that says what the bars are relative to), and a year axis with round ticks
 * in place of the first and the last year. The window, the title, the availability line, the source and the lines carry over.
 */
import type { StripesKind } from '#shared/types/api'
import type { ChartTheme } from './chart-theme'
import type { StripesModel, StripesVariant, YearRun, YearWindow } from './stripes-model'
import { seriesLabelColor } from './chart-theme'
import { stripeColour } from './stripes'
import { anomalyAxis, availabilityRuns, brokenLine, MIN_SPAN_STRIPES, visibleYears, yearTicks } from './stripes-model'

/** The font of the chart, on the page and in a saved image, which has no web font of the page's to draw with */
export const STRIPES_FONT_FAMILY = 'Arial, sans-serif'
/** The title's type size, the line it takes, the room it leaves at either side and the drop of a title of several lines, in px */
export const TITLE_SIZE = 16
export const TITLE_LINE = 20
export const TITLE_PADDING = 10
export const TITLE_DROP = 18
/**
 * The shape of the stripes (GH-4133): their width over their height, the one number that sets how tall they are. The
 * height follows the width of the column, so the stripes keep their shape on a phone and on a wide screen; the title, the
 * years, the availability line and the source are on top of it.
 */
export const STRIPES_RATIO = 16 / 9
/** The least and the most the stripes are high on the page, in px: a narrow window keeps stripes that read as stripes, a wide one does not grow without end */
export const STRIPES_MIN_HEIGHT = 160
export const STRIPES_MAX_HEIGHT = 480
/** The size of the camera's image and its pixel ratio, and the ratio of the menu's raster images */
export const CAMERA_WIDTH = 1400
export const CAMERA_SCALE = 2
export const MENU_SCALE = 3

/** What the page offers to draw */
export interface StripesDisplay {
  showTitle: boolean
  showYears: boolean
  showSource: boolean
  showDataAvailability: boolean
  showTimeseries: boolean
  showTrendline: boolean
}

/**
 * The room above and below the stripes where the availability line lies, in px, so that the title keeps its distance to them
 * and the years theirs on a small chart too (it was 5 % of the plot's height, which is 22 px at the chart's old height of 600 px)
 */
const AVAILABILITY_MARGIN = 20

/** The gold of the availability line, which is data and the same in both schemes, and how thick it is, in px */
const GOLD = '#FFD700'
const AVAILABILITY_WIDTH = 3
/** The dot of a year that stands alone in the time series line, in px: wider than the line (2 px), so that it reads as a point */
export const TIMESERIES_DOT = 6

export interface StripesOptionInput {
  model: StripesModel
  kind: StripesKind
  theme: ChartTheme
  display: StripesDisplay
  /** the chart's size in px */
  width: number
  height: number
  window: YearWindow
  /** the title broken into lines, and as many as it has; empty where it is not shown */
  titleLines: string[]
  availabilityText: string
  sourceText: string
  fontFamily?: string
  /** The paper behind the chart: the page's own shows through on the page (none), a saved image has its own */
  background?: string
  /**
   * Rows of text under the source, each on a line of its own: what a saved image says of its colours (what they are relative
   * to), which the page says under the chart. The chart on the page has none (GH-4157).
   */
  extraLines?: readonly string[]
  /** How the years are drawn: the stripes (the default), the bars, or the bars with a scale (GH-4156) */
  variant?: StripesVariant
  /** Under the title of the bars with a scale, as many as it has: what the bars are relative to, broken into lines; empty for the others */
  subtitleLines?: readonly string[]
  /** Writes a number of the bars' y axis with the decimals its step needs; the default writes the sign and `toFixed` */
  formatTick?: (value: number, decimals: number) => string
}

/** What of the page's choices changes the room round the plot: the variant, and the lines the subtitle of the scale takes */
export interface StripesFrame {
  variant?: StripesVariant
  subtitleLines?: number
}

/** The bars' scale takes room left of the plot for its labels, and a little right of it for the last year's label, in px */
const SCALE_LEFT = 52
const SCALE_RIGHT = 24
const PLAIN_SIDE = 20
/** The grid of the bars' scale lies back: the bars are the data */
const GRID_OPACITY = 0.55
/** A row of the subtitle: its type size and the line it takes, in px */
export const SUBTITLE_SIZE = 13
const SUBTITLE_LINE = 17

/** Where everything is, in px from the chart's top left */
export interface StripesLayout {
  plot: { left: number, top: number, width: number, height: number }
  /** the first line of the subtitle of the scale */
  subtitleTop: number
  /** where the stripes are in the plot's height: with the availability line the plot reaches a margin above and below them */
  stripes: { top: number, height: number }
  /** the range of the plot's y axis, in which the stripes run from 0 to 1 */
  yRange: [number, number]
  /** the first line of the title, and each one after it */
  titleTop: number
  yearsTop: number
  availabilityBottom: number
  sourceTop: number
}

/** The width of the margin left of the plot and right of it, in px: the bars' scale takes room for its labels */
function sideMargins(frame: StripesFrame): [number, number] {
  return frame.variant === 'barsScale' ? [SCALE_LEFT, SCALE_RIGHT] : [PLAIN_SIDE, PLAIN_SIDE]
}

/** Where the first line of the title is, in px from the chart's top */
function titleTopOf(display: StripesDisplay, lines: number): number {
  return lines > 1 ? 24 + TITLE_DROP : (display.showDataAvailability ? 24 : 6)
}

/** The margins round the plot, in px: above it the title, below it the years and the source, as the chart has always had them */
function plotMargins(display: StripesDisplay, titleLineCount: number, extraLines = 0, frame: StripesFrame = {}) {
  const lines = Math.max(1, titleLineCount)
  const titleDrop = lines > 1 ? TITLE_DROP : 0
  let top = display.showTitle ? 30 + (lines - 1) * TITLE_LINE + titleDrop : 20
  // the subtitle of the bars' scale lies under the title, and the stripes (the margin of the availability line is the plot's, above them) 8 px under it
  const subtitleRows = frame.variant === 'barsScale' ? (frame.subtitleLines ?? 0) : 0
  const titleTop = titleTopOf(display, lines)
  const subtitleTop = display.showTitle ? titleTop + lines * TITLE_LINE + 1 : titleTop
  if (subtitleRows > 0)
    top = Math.max(top, Math.ceil(subtitleTop + subtitleRows * SUBTITLE_LINE + 8 - stripesMargin(display)))
  // below the plot, in px from its bottom edge, so that they keep their distances in an image of another height: the years
  // (18 px type) from 20 px down, the source under them (14 px type, in a margin of a line of 20 px)
  const sourceOffset = display.showYears ? 48 : 28
  // a row of text is 20 px; the source and the extra rows (of a saved image) are the rows, the first at `sourceOffset`
  const rows = (display.showSource ? 1 : 0) + extraLines
  const bottom = rows > 0 ? Math.max(60, sourceOffset + 12 + 20 * rows) : 60
  return { top, bottom, sourceOffset, lines, titleDrop, titleTop, subtitleTop }
}

/** How much more room below the plot `extraLines` rows of text take, in px: what a saved image is made higher by */
export function extraLinesHeight(display: StripesDisplay, extraLines: number): number {
  return plotMargins(display, 1, extraLines).bottom - plotMargins(display, 1).bottom
}

/** The margin above and below the stripes in the plot: where the availability line lies, none without it */
function stripesMargin(display: StripesDisplay): number {
  return display.showDataAvailability ? AVAILABILITY_MARGIN : 0
}

/**
 * How high the chart is for a width: the stripes are as high as they are wide (the plot's width) over `STRIPES_RATIO`, and
 * the title, the years, the availability line and the source are on top of that. On the page the stripes are kept between
 * `STRIPES_MIN_HEIGHT` and `STRIPES_MAX_HEIGHT`; a saved image is not (`clamp: false`), so that it has the ratio of the
 * stripes at any width. Whole px, so that the chart's box and its drawing agree. The bars are as high as the stripes
 * (`frame`: the room of the scale narrows the plot and its subtitle lowers it).
 */
export function stripesChartHeight(display: StripesDisplay, width: number, titleLineCount: number, options: { clamp?: boolean, extraLines?: number, frame?: StripesFrame } = {}): number {
  const frame = options.frame ?? {}
  const { top, bottom } = plotMargins(display, titleLineCount, options.extraLines, frame)
  const [left, right] = sideMargins(frame)
  const natural = Math.max(1, width - left - right) / STRIPES_RATIO
  const stripes = options.clamp === false ? natural : Math.min(STRIPES_MAX_HEIGHT, Math.max(STRIPES_MIN_HEIGHT, natural))
  return Math.round(top + stripes + 2 * stripesMargin(display) + bottom)
}

/** The room the years and the source take below the stripes, and the margins round them */
export function stripesLayout(display: StripesDisplay, width: number, height: number, titleLineCount: number, extraLines = 0, frame: StripesFrame = {}): StripesLayout {
  const { top, bottom, sourceOffset, titleTop, subtitleTop } = plotMargins(display, titleLineCount, extraLines, frame)
  const [left, right] = sideMargins(frame)
  const plot = { left, top, width: Math.max(1, width - left - right), height: Math.max(1, height - top - bottom) }
  const margin = Math.min(stripesMargin(display), (plot.height - 1) / 2)
  const stripes = { top: plot.top + margin, height: plot.height - 2 * margin }
  const yRange: [number, number] = [0 - margin / stripes.height, 1 + margin / stripes.height]
  return {
    plot,
    subtitleTop,
    stripes,
    yRange,
    titleTop,
    yearsTop: plot.top + plot.height + 20,
    availabilityBottom: plot.top + plot.height + 14,
    sourceTop: plot.top + plot.height + sourceOffset,
  }
}

interface TextSpec {
  text: string
  x: number
  y: number
  fill: string
  size: number
  align: 'left' | 'center' | 'right'
  baseline: 'top' | 'middle' | 'bottom'
}

/** A line of the axes of the bars, in px from the chart's top left */
interface LineSpec {
  x0: number
  y0: number
  x1: number
  y1: number
  color: string
  /** how much of the colour shows, 0 to 1: a grid line lies back */
  opacity?: number
  width: number
}

/** What of an input changes the room round the plot: the variant and the lines of the subtitle */
export function frameOf(input: Pick<StripesOptionInput, 'variant' | 'subtitleLines'>): StripesFrame {
  return { variant: input.variant ?? 'stripes', subtitleLines: input.subtitleLines?.length ?? 0 }
}

function layoutOf(input: StripesOptionInput): StripesLayout {
  return stripesLayout(input.display, input.width, input.height, input.titleLines.length, input.extraLines?.length ?? 0, frameOf(input))
}

/** The pixel of a year's middle on the chart */
export function xOfYear(year: number, layout: StripesLayout, window: YearWindow): number {
  return layout.plot.left + ((year - window.start) / (window.end - window.start)) * layout.plot.width
}

/** The writing of a number of the y axis where the page gives no `formatTick`: a sign for what is not zero, and the decimals the step needs */
function defaultTick(value: number, decimals: number): string {
  return value === 0 ? '0' : `${value > 0 ? '+' : '\u2212'}${Math.abs(value).toFixed(decimals)}`
}

/**
 * Where on the stripes' height (0 at their foot, 1 at their top) an anomaly of the bars is: on the range the axis runs over,
 * which the anomalies of the whole answer set and not the window.
 */
function barHeights(model: StripesModel) {
  const axis = anomalyAxis(model.anomalies)
  const place = (anomaly: number) => (anomaly - axis.min) / (axis.max - axis.min)
  return { axis, place }
}

/** The px of a height on the stripes' height, rounded to the pixel: bars and lines that meet share the edge */
function pixelOfHeight(height: number, layout: StripesLayout): number {
  return Math.round(layout.stripes.top + layout.stripes.height * (1 - height))
}

/** The texts of the chart: they move with the window, since the years named are the first and the last stripes in it */
export function stripesTexts(input: StripesOptionInput, layout: StripesLayout): TextSpec[] {
  const { model, theme, display, width, window, titleLines } = input
  const texts: TextSpec[] = []
  const scale = input.variant === 'barsScale'
  if (display.showTitle) {
    titleLines.forEach((line, index) => texts.push({ text: line, x: width / 2, y: layout.titleTop + index * TITLE_LINE, fill: theme.text, size: TITLE_SIZE, align: 'center', baseline: 'top' }))
  }
  // what the bars are relative to, under the title
  if (scale)
    input.subtitleLines?.forEach((line, index) => texts.push({ text: line, x: width / 2, y: layout.subtitleTop + index * SUBTITLE_LINE, fill: theme.textMuted, size: SUBTITLE_SIZE, align: 'center', baseline: 'top' }))
  const [first, last] = visibleYears(window, model)
  if (display.showYears && scale) {
    // round years along the axis, in place of the first and the last year
    for (const year of yearTicks(window, layout.plot.width))
      texts.push({ text: String(year), x: xOfYear(year, layout, window), y: layout.yearsTop, fill: theme.text, size: 14, align: 'center', baseline: 'top' })
  }
  else if (display.showYears) {
    texts.push(
      { text: String(first), x: xOfYear(first, layout, window), y: layout.yearsTop, fill: theme.text, size: 18, align: 'left', baseline: 'top' },
      { text: String(last), x: xOfYear(last, layout, window), y: layout.yearsTop, fill: theme.text, size: 18, align: 'right', baseline: 'top' },
    )
  }
  // the numbers of the y axis, right-aligned at the plot's left edge, each level with its grid line
  if (scale) {
    const { axis, place } = barHeights(model)
    const write = input.formatTick ?? defaultTick
    for (const tick of axis.ticks)
      texts.push({ text: write(tick, axis.decimals), x: layout.plot.left - 8, y: pixelOfHeight(place(tick), layout), fill: theme.textMuted, size: 12, align: 'right', baseline: 'middle' })
  }
  if (display.showDataAvailability)
    texts.push({ text: input.availabilityText, x: xOfYear(first, layout, window), y: layout.availabilityBottom, fill: seriesLabelColor('gold', theme.dark), size: 12, align: 'left', baseline: 'bottom' })
  // on a row of its own below the years, as it is on a chart too narrow to hold the two side by side
  if (display.showSource)
    texts.push({ text: input.sourceText, x: layout.plot.left + layout.plot.width / 2, y: layout.sourceTop, fill: theme.textMuted, size: 14, align: 'center', baseline: 'top' })
  // what a saved image says of its colours, under the source (or in its place where the source is not shown)
  const first_row = display.showSource ? 1 : 0
  input.extraLines?.forEach((text, index) => texts.push({ text, x: layout.plot.left + layout.plot.width / 2, y: layout.sourceTop + 20 * (first_row + index), fill: theme.textMuted, size: 14, align: 'center', baseline: 'top' }))
  return texts
}

/**
 * The grid of the bars with a scale, which lies under the bars: a line across the plot at each tick of the y axis and, where the
 * years are shown, one down it at each round year. Moves with the window (the years).
 */
export function stripesGridLines(input: StripesOptionInput, layout: StripesLayout): LineSpec[] {
  if (input.variant !== 'barsScale')
    return []
  const { axis, place } = barHeights(input.model)
  const color = input.theme.grid
  const { left, width } = layout.plot
  const lines: LineSpec[] = axis.ticks.map((tick) => {
    const y = pixelOfHeight(place(tick), layout) + 0.5
    return { x0: left, y0: y, x1: left + width, y1: y, color, width: 1, opacity: GRID_OPACITY }
  })
  if (input.display.showYears) {
    for (const year of yearTicks(input.window, width)) {
      const x = Math.round(xOfYear(year, layout, input.window)) + 0.5
      lines.push({ x0: x, y0: layout.stripes.top, x1: x, y1: layout.stripes.top + layout.stripes.height, color, width: 1, opacity: GRID_OPACITY })
    }
  }
  return lines
}

/** The zero line of the bars, over them: where the anomaly is nought, the mean of the reference */
export function stripesZeroLine(input: StripesOptionInput, layout: StripesLayout): LineSpec[] {
  if (input.variant !== 'bars' && input.variant !== 'barsScale')
    return []
  const y = pixelOfHeight(barHeights(input.model).place(0), layout) + 0.5
  return [{ x0: layout.plot.left, y0: y, x1: layout.plot.left + layout.plot.width, y1: y, color: input.theme.zeroline, width: 1 }]
}

function labelsSeries(input: StripesOptionInput, layout: StripesLayout) {
  const fontFamily = input.fontFamily ?? STRIPES_FONT_FAMILY
  const texts = stripesTexts(input, layout)
  return {
    id: 'labels',
    type: 'custom',
    coordinateSystem: 'none',
    silent: true,
    animation: false,
    z: 10,
    data: texts.map((_, index) => [index]),
    renderItem: (_params: unknown, api: { value: (dimension: number) => number }) => {
      const spec = texts[api.value(0)]!
      return {
        type: 'text',
        silent: true,
        style: { text: spec.text, x: spec.x, y: spec.y, fill: spec.fill, font: `${spec.size}px ${fontFamily}`, textAlign: spec.align, textVerticalAlign: spec.baseline },
      }
    },
  }
}

/** Lines in px, in a series of their own: `z` puts them under the bars (the grid) or over them (the zero line) */
function linesSeries(id: string, lines: LineSpec[], z: number) {
  return {
    id,
    type: 'custom',
    coordinateSystem: 'none',
    silent: true,
    animation: false,
    z,
    data: lines.map((_, index) => [index]),
    renderItem: (_params: unknown, api: { value: (dimension: number) => number }) => {
      const spec = lines[api.value(0)]!
      return { type: 'line', silent: true, shape: { x1: spec.x0, y1: spec.y0, x2: spec.x1, y2: spec.y1 }, style: { stroke: spec.color, lineWidth: spec.width, fill: 'none', opacity: spec.opacity ?? 1 } }
    },
  }
}

/** The part of the option that a move of the window changes: the zoom, the years named at the ends or along the axis, and the grid's lines for them. Merged into the chart's option. */
export function windowUpdate(input: StripesOptionInput): EChartsCoreOption {
  const layout = layoutOf(input)
  const series: unknown[] = [labelsSeries(input, layout)]
  if (input.variant === 'barsScale')
    series.push(linesSeries('grid', stripesGridLines(input, layout), 0))
  return {
    dataZoom: [{ id: 'zoom', startValue: input.window.start, endValue: input.window.end }],
    series,
  }
}

/**
 * The edges of the stripe of `year`, in whole pixels: it is at least a px wide, so that a stripe of a crowded chart is not
 * lost, and two stripes that meet share an edge.
 */
function stripeEdges(year: number, coordOf: (year: number) => number): [number, number] {
  const x0 = Math.round(coordOf(year - 0.5))
  const x1 = Math.round(coordOf(year + 0.5))
  return [x0, Math.max(x0 + 1, x1)]
}

/**
 * The edges of the bar of a run of years, in whole pixels: the left edge of its first stripe to the right edge of its last,
 * as they are drawn (a stripe is the run of its year), so that the bar ends where its stripes do, to the pixel, however
 * narrow they are. A lone year is as wide as its stripe.
 */
export function runEdges(run: YearRun, coordOf: (year: number) => number): [number, number] {
  return [stripeEdges(run.first, coordOf)[0], stripeEdges(run.last, coordOf)[1]]
}

/**
 * The availability line: one bar of gold for each run of years with a value, in the middle of the margin below the stripes, so
 * 10 px under them whatever their height (the model's own value is a proportion of it, which lies 3 px under them on a phone);
 * the model says only which years have a value. Not a `line` series: that runs from the middle of the first year's stripe to the
 * middle of the last's, half a stripe short at each end, and draws nothing for a run of one year (GH-4153).
 */
function availabilitySeries(model: StripesModel, layout: StripesLayout, base: Record<string, unknown>) {
  const y = layout.yRange[0] / 2
  return {
    ...base,
    id: 'availability',
    type: 'custom',
    z: 2,
    encode: { x: [0, 1], y: 2 },
    data: availabilityRuns(model.availability, model.minYear).map(run => [run.first, run.last, y]),
    renderItem: (_params: unknown, api: any) => {
      const [x0, x1] = runEdges({ first: api.value(0), last: api.value(1) }, year => api.coord([year, 0])[0])
      const centre = api.coord([0, api.value(2)])[1]
      return { type: 'rect', silent: true, shape: { x: x0, y: Math.round(centre - AVAILABILITY_WIDTH / 2), width: x1 - x0, height: AVAILABILITY_WIDTH }, style: { fill: GOLD } }
    },
  }
}

/** The option of the stripes in `input` */
export function buildStripesOption(input: StripesOptionInput): EChartsCoreOption {
  const { model, kind, display, window: win } = input
  const layout = layoutOf(input)
  const variant = input.variant ?? 'stripes'
  const bars = variant !== 'stripes'
  const { place: barPlace } = barHeights(model)
  // the classes the backend gives the years, against the station's whole record and not the years shown (GH-4157)
  const colours = model.classes.map(stripeClass => stripeColour(kind, stripeClass))
  const bounds = { start: model.minYear - 0.5, end: model.maxYear + 0.5 }
  const base = { xAxisIndex: 0, yAxisIndex: 0, silent: true, animation: false, clip: true }
  const line = (id: string, data: unknown[], style: Record<string, unknown>, z: number) => ({
    ...base,
    id,
    type: 'line',
    z,
    data,
    // the symbols are shown and none by default: only a year that stands alone has one (a dot), which a line cannot draw
    showSymbol: true,
    symbol: 'none',
    connectNulls: false,
    lineStyle: { cap: 'butt', ...style },
  })
  // the time series breaks at every year without a value, as the stripes do; a lone year is a dot (GH-4164). The trend is a fit
  // over the years and stays one line.
  // the lines lie where the colours are on the stripes (the scale of the reference); on the bars they lie where the bars' tops are
  const lineHeights = bars ? model.anomalies.map(barPlace) : model.normalized
  const trendHeights = bars ? model.trendAnomalies.map(barPlace) : model.normalizedTrend
  const timeseriesPoints = brokenLine(model.years, lineHeights).map(point => point.lone
    ? { value: [point.year, point.height], symbol: 'circle', symbolSize: TIMESERIES_DOT, itemStyle: { color: 'black' } }
    : [point.year, point.height])

  const series: any[] = []
  if (bars) {
    // a bar for each year with a value (none for a year without): from the zero line to the year's anomaly, in the colour of its class
    series.push({
      ...base,
      id: 'bars',
      type: 'custom',
      z: 1,
      encode: { x: 0, y: 1 },
      data: model.years.map((year, index) => [year, barPlace(model.anomalies[index]!), index]),
      renderItem: (_params: unknown, api: any) => {
        const [x0, x1] = runEdges({ first: api.value(0), last: api.value(0) }, at => api.coord([at, 0])[0])
        // whole pixels, as the zero line is: a bar of a small anomaly is at least a px high, one of none is none
        const zero = Math.round(api.coord([0, barPlace(0)])[1])
        const top = Math.round(api.coord([0, api.value(1)])[1])
        const height = Math.abs(zero - top) || (api.value(1) === barPlace(0) ? 0 : 1)
        const y = top <= zero ? top : zero
        return { type: 'rect', silent: true, shape: { x: x0, y, width: x1 - x0, height }, style: { fill: colours[api.value(2)] } }
      },
    })
  }
  else {
    series.push({
      ...base,
      id: 'stripes',
      type: 'custom',
      z: 1,
      encode: { x: 0, y: 1 },
      data: model.years.map((year, index) => [year, 1, index]),
      renderItem: (params: any, api: any) => {
        const year = api.value(0)
        // whole pixels, so that two stripes that meet share an edge and no hairline of the paper shows between them
        const [x0, x1] = runEdges({ first: year, last: year }, at => api.coord([at, 0])[0])
        const y0 = api.coord([0, 0])[1]
        const y1 = api.coord([0, 1])[1]
        return { type: 'rect', silent: true, shape: { x: x0, y: y1, width: x1 - x0, height: y0 - y1 }, style: { fill: colours[api.value(2)] } }
      },
    })
  }
  if (variant === 'barsScale')
    series.push(linesSeries('grid', stripesGridLines(input, layout), 0))
  if (bars)
    series.push(linesSeries('zeroline', stripesZeroLine(input, layout), 2))
  if (display.showDataAvailability)
    series.push(availabilitySeries(model, layout, base))
  if (display.showTimeseries)
    series.push(line('timeseries', timeseriesPoints, { color: 'black', width: 2 }, 3))
  if (display.showTrendline && display.showTimeseries)
    series.push(line('trend', model.years.map((year, index) => [year, trendHeights[index]!]), { color: 'black', width: 4, type: [12, 12] }, 4))
  series.push(labelsSeries(input, layout))

  return {
    // none: the stripes are the data and an animation of them is a motion nobody asked for (`prefers-reduced-motion` has nothing to switch off)
    animation: false,
    backgroundColor: input.background ?? 'transparent',
    textStyle: { fontFamily: input.fontFamily ?? STRIPES_FONT_FAMILY, color: input.theme.text },
    grid: [{ left: layout.plot.left, top: layout.plot.top, width: layout.plot.width, height: layout.plot.height, show: false }],
    xAxis: [{ type: 'value', gridIndex: 0, min: bounds.start, max: bounds.end, show: false }],
    // the stripes run from 0 to 1; the availability line lies in the margin below them
    yAxis: [{ type: 'value', gridIndex: 0, min: layout.yRange[0], max: layout.yRange[1], show: false }],
    dataZoom: [{
      id: 'zoom',
      type: 'inside',
      xAxisIndex: [0],
      startValue: win.start,
      endValue: win.end,
      filterMode: 'none',
      // a drag is the zoom box, a wheel the page's: a pinch, and Ctrl and the wheel (a trackpad's pinch), zoom
      zoomOnMouseWheel: 'ctrl',
      moveOnMouseMove: false,
      moveOnMouseWheel: false,
      preventDefaultMouseMove: false,
      minValueSpan: MIN_SPAN_STRIPES,
      maxValueSpan: bounds.end - bounds.start,
    }],
    series,
  }
}
