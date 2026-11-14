import type { EChartsCoreOption } from 'echarts/core'
/**
 * The option of the climate stripes (Apache ECharts, drawn as SVG): a stripe for each year as a `custom` series on a
 * value axis of years (so that a year without a value is a gap, as before), the optional lines as the library's own
 * `line` series, and the title, the years, the source and the availability label as text elements of a `custom`
 * series without a coordinate system, placed in px. Pure: values, a theme, a size and a window in, an option out, so
 * that tests and the image export build it without a browser (GH-4068).
 */
import type { StripesKind } from '#shared/types/api'
import type { ChartTheme } from './chart-theme'
import type { StripesModel, YearWindow } from './stripes-model'
import { seriesLabelColor } from './chart-theme'
import { COLOR_MAPS, stripeColour } from './stripes'
import { MIN_SPAN_STRIPES, visibleYears } from './stripes-model'

/** The font of the chart, on the page and in a saved image, which has no web font of the page's to draw with */
export const STRIPES_FONT_FAMILY = 'Arial, sans-serif'
/** The title's type size, the line it takes, the room it leaves at either side and the drop of a title of several lines, in px */
export const TITLE_SIZE = 16
export const TITLE_LINE = 20
export const TITLE_PADDING = 10
export const TITLE_DROP = 18
/** The height of the chart on the page: with a title, and without */
export const STRIPES_HEIGHT_TITLE = 600
export const STRIPES_HEIGHT = 550
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

/** The gold of the availability line, which is data and the same in both schemes */
const GOLD = '#FFD700'

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
}

/** Where everything is, in px from the chart's top left */
export interface StripesLayout {
  plot: { left: number, top: number, width: number, height: number }
  /** the first line of the title, and each one after it */
  titleTop: number
  yearsTop: number
  availabilityBottom: number
  sourceTop: number
}

/** The room the years and the source take below the stripes, and the margins round them, as the chart has always had them */
export function stripesLayout(display: StripesDisplay, width: number, height: number, titleLineCount: number): StripesLayout {
  const lines = Math.max(1, titleLineCount)
  const titleDrop = lines > 1 ? TITLE_DROP : 0
  const top = display.showTitle ? 30 + (lines - 1) * TITLE_LINE + titleDrop : 20
  // below the plot, in px from its bottom edge, so that they keep their distances in an image of another height: the years
  // (18 px type) from 20 px down, the source under them (14 px type, in a margin of a line of 20 px)
  const sourceOffset = display.showYears ? 48 : 28
  const bottom = display.showSource ? Math.max(60, sourceOffset + 32) : 60
  const plot = { left: 20, top, width: Math.max(1, width - 40), height: Math.max(1, height - top - bottom) }
  const titleTop = lines > 1 ? 24 + titleDrop : (display.showDataAvailability ? 24 : 6)
  return {
    plot,
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
  const layout = stripesLayout(input.display, input.width, input.height, input.titleLines.length)
  return {
    dataZoom: [{ id: 'zoom', startValue: input.window.start, endValue: input.window.end }],
    series: [labelsSeries(input, layout)],
  }
}

/** The option of the stripes in `input` */
export function buildStripesOption(input: StripesOptionInput): EChartsCoreOption {
  const { model, kind, display, window: win } = input
  const layout = stripesLayout(display, input.width, input.height, input.titleLines.length)
  const scale = COLOR_MAPS[kind]
  const colours = model.normalized.map(position => stripeColour(scale, position))
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
      const x0 = Math.round(api.coord([year - 0.5, 0])[0])
      const x1 = Math.round(api.coord([year + 0.5, 0])[0])
      const y0 = api.coord([0, 0])[1]
      const y1 = api.coord([0, 1])[1]
      return { type: 'rect', silent: true, shape: { x: x0, y: y1, width: Math.max(1, x1 - x0), height: y0 - y1 }, style: { fill: colours[api.value(2)] } }
    },
  }]
  if (display.showDataAvailability)
    series.push(line('availability', model.availability.map((value, index) => [model.minYear + index, value]), { color: GOLD, width: 3 }, 2))
  if (display.showTimeseries)
    series.push(line('timeseries', model.years.map((year, index) => [year, model.normalized[index]!]), { color: 'black', width: 2 }, 3))
  if (display.showTrendline && display.showTimeseries)
    series.push(line('trend', model.years.map((year, index) => [year, model.normalizedTrend[index]!]), { color: 'black', width: 4, type: [12, 12] }, 4))
  series.push(labelsSeries(input, layout))

  return {
    // none: the stripes are the data and an animation of them is a motion nobody asked for (`prefers-reduced-motion` has nothing to switch off)
    animation: false,
    backgroundColor: 'transparent',
    textStyle: { fontFamily: input.fontFamily ?? STRIPES_FONT_FAMILY, color: input.theme.text },
    grid: [{ left: layout.plot.left, top: layout.plot.top, width: layout.plot.width, height: layout.plot.height, show: false }],
    xAxis: [{ type: 'value', gridIndex: 0, min: bounds.start, max: bounds.end, show: false }],
    // the stripes run from 0 to 1; the availability line lies in the margin below them
    yAxis: [{ type: 'value', gridIndex: 0, min: display.showDataAvailability ? -0.05 : 0, max: display.showDataAvailability ? 1.05 : 1, show: false }],
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
