import type { EChartsCoreOption } from 'echarts/core'
/**
 * The option of the climate stripes (Apache ECharts, drawn as SVG): a stripe for each year as a `custom` series on a
 * value axis of years (so that a year without a value is a gap, as before), the availability line as a `custom` series
 * of one bar for each run of years with a value (it spans exactly their stripes), the optional lines of the timeseries and
 * the trend as the library's own `line` series, and the title, the years, the source and the availability label as text
 * elements of a `custom` series without a coordinate system, placed in px. Pure: values, a theme, a size and a window in, an option out, so
 * that tests and the image export build it without a browser (GH-4068).
 */
import type { StripesKind } from '#shared/types/api'
import type { ChartTheme } from './chart-theme'
import type { StripesModel, YearRun, YearWindow } from './stripes-model'
import { seriesLabelColor } from './chart-theme'
import { stripeColour } from './stripes'
import { availabilityRuns, MIN_SPAN_STRIPES, visibleYears } from './stripes-model'

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
}

/** Where everything is, in px from the chart's top left */
export interface StripesLayout {
  plot: { left: number, top: number, width: number, height: number }
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

/** The margins round the plot, in px: above it the title, below it the years and the source, as the chart has always had them */
function plotMargins(display: StripesDisplay, titleLineCount: number, extraLines = 0) {
  const lines = Math.max(1, titleLineCount)
  const titleDrop = lines > 1 ? TITLE_DROP : 0
  const top = display.showTitle ? 30 + (lines - 1) * TITLE_LINE + titleDrop : 20
  // below the plot, in px from its bottom edge, so that they keep their distances in an image of another height: the years
  // (18 px type) from 20 px down, the source under them (14 px type, in a margin of a line of 20 px)
  const sourceOffset = display.showYears ? 48 : 28
  // a row of text is 20 px; the source and the extra rows (of a saved image) are the rows, the first at `sourceOffset`
  const rows = (display.showSource ? 1 : 0) + extraLines
  const bottom = rows > 0 ? Math.max(60, sourceOffset + 12 + 20 * rows) : 60
  return { top, bottom, sourceOffset, lines, titleDrop }
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
 * stripes at any width. Whole px, so that the chart's box and its drawing agree.
 */
export function stripesChartHeight(display: StripesDisplay, width: number, titleLineCount: number, options: { clamp?: boolean, extraLines?: number } = {}): number {
  const { top, bottom } = plotMargins(display, titleLineCount, options.extraLines)
  const natural = Math.max(1, width - 40) / STRIPES_RATIO
  const stripes = options.clamp === false ? natural : Math.min(STRIPES_MAX_HEIGHT, Math.max(STRIPES_MIN_HEIGHT, natural))
  return Math.round(top + stripes + 2 * stripesMargin(display) + bottom)
}

/** The room the years and the source take below the stripes, and the margins round them */
export function stripesLayout(display: StripesDisplay, width: number, height: number, titleLineCount: number, extraLines = 0): StripesLayout {
  const { top, bottom, sourceOffset, lines, titleDrop } = plotMargins(display, titleLineCount, extraLines)
  const plot = { left: 20, top, width: Math.max(1, width - 40), height: Math.max(1, height - top - bottom) }
  const margin = Math.min(stripesMargin(display), (plot.height - 1) / 2)
  const stripes = { top: plot.top + margin, height: plot.height - 2 * margin }
  const yRange: [number, number] = [0 - margin / stripes.height, 1 + margin / stripes.height]
  const titleTop = lines > 1 ? 24 + titleDrop : (display.showDataAvailability ? 24 : 6)
  return {
    plot,
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
  baseline: 'top' | 'bottom'
}

/** The pixel of a year's middle on the chart */
export function xOfYear(year: number, layout: StripesLayout, window: YearWindow): number {
  return layout.plot.left + ((year - window.start) / (window.end - window.start)) * layout.plot.width
}

/** The texts of the chart: they move with the window, since the years named are the first and the last stripes in it */
export function stripesTexts(input: StripesOptionInput, layout: StripesLayout): TextSpec[] {
  const { model, theme, display, width, window, titleLines } = input
  const texts: TextSpec[] = []
  if (display.showTitle) {
    titleLines.forEach((line, index) => texts.push({ text: line, x: width / 2, y: layout.titleTop + index * TITLE_LINE, fill: theme.text, size: TITLE_SIZE, align: 'center', baseline: 'top' }))
  }
  const [first, last] = visibleYears(window, model)
  if (display.showYears) {
    texts.push(
      { text: String(first), x: xOfYear(first, layout, window), y: layout.yearsTop, fill: theme.text, size: 18, align: 'left', baseline: 'top' },
      { text: String(last), x: xOfYear(last, layout, window), y: layout.yearsTop, fill: theme.text, size: 18, align: 'right', baseline: 'top' },
    )
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

/** The part of the option that a move of the window changes: the zoom and the years named at the ends. Merged into the chart's option. */
export function windowUpdate(input: StripesOptionInput): EChartsCoreOption {
  const layout = stripesLayout(input.display, input.width, input.height, input.titleLines.length, input.extraLines?.length ?? 0)
  return {
    dataZoom: [{ id: 'zoom', startValue: input.window.start, endValue: input.window.end }],
    series: [labelsSeries(input, layout)],
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
  const layout = stripesLayout(display, input.width, input.height, input.titleLines.length, input.extraLines?.length ?? 0)
  // the classes the backend gives the years, against the station's whole record and not the years shown (GH-4157)
  const colours = model.classes.map(stripeClass => stripeColour(kind, stripeClass))
  const bounds = { start: model.minYear - 0.5, end: model.maxYear + 0.5 }
  const base = { xAxisIndex: 0, yAxisIndex: 0, silent: true, animation: false, clip: true }
  const line = (id: string, data: (number | null)[][], style: Record<string, unknown>, z: number) => ({
    ...base,
    id,
    type: 'line',
    z,
    data,
    showSymbol: false,
    symbol: 'none',
    connectNulls: false,
    lineStyle: { cap: 'butt', ...style },
  })

  const series: any[] = [{
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
  }]
  if (display.showDataAvailability)
    series.push(availabilitySeries(model, layout, base))
  if (display.showTimeseries)
    series.push(line('timeseries', model.years.map((year, index) => [year, model.normalized[index]!]), { color: 'black', width: 2 }, 3))
  if (display.showTrendline && display.showTimeseries)
    series.push(line('trend', model.years.map((year, index) => [year, model.normalizedTrend[index]!]), { color: 'black', width: 4, type: [12, 12] }, 4))
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
