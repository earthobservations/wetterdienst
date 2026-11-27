import type { ChartTheme } from './chart-theme'
import type { KostraQuantity, KostraTable } from './kostra'
import { KOSTRA_CURVE_COLOURS, KOSTRA_DURATIONS, KOSTRA_RETURN_PERIODS, quantityOf } from './kostra'

/**
 * The chart of the Heavy-rainfall tool (GH-4500) as the option ECharts is given: one depth-duration curve for each return period, the
 * duration on a logarithmic axis (5 minutes to 7 days) labelled in min, h and d, the depth in mm or the intensity in l/(s·ha) on a
 * linear one that starts at 0. The curves are one hue from light to dark in the order of the return periods (`KOSTRA_CURVE_COLOURS`);
 * the legend and the readout are the component's own (real elements a pointer can move onto), as in the other charts, so no tooltip
 * is drawn here, only the crosshair and the marks of the duration the reader is at.
 *
 * Pure, so that a test holds the option to the answer without a browser. The x axis is a value axis of log10 of the minutes: ECharts'
 * own log axis puts its ticks at the powers of ten, and a duration is read at 5 min, 1 h, 1 d.
 */

const LOG_FIRST = Math.log10(KOSTRA_DURATIONS[0])
const LOG_LAST = Math.log10(KOSTRA_DURATIONS.at(-1)!)

/** The margins of the plot, in px */
export const KOSTRA_PLOT = { left: 48, right: 14, top: 12, bottom: 34 }

/** The durations the axis is labelled at: fewer on a narrow chart, where 5 and 15 minutes would run together */
export function kostraTicks(width: number): number[] {
  return width >= 520 ? [5, 15, 60, 360, 1440, 10080] : [5, 60, 360, 1440, 10080]
}

/** The height of the chart for its width: lower on a phone, where the page is a column */
export function kostraHeight(width: number): number {
  return width >= 520 ? 360 : 300
}

/** The x value of a duration on the axis */
export function xOfDuration(minutes: number): number {
  return Math.log10(minutes)
}

/** The pixel of a duration, from the left of the chart of `width` px */
export function pixelOfDuration(minutes: number, width: number): number {
  const plot = width - KOSTRA_PLOT.left - KOSTRA_PLOT.right
  return KOSTRA_PLOT.left + (xOfDuration(minutes) - LOG_FIRST) / (LOG_LAST - LOG_FIRST) * plot
}

/**
 * The index of the duration of the table nearest to a pixel from the left of the chart of `width` px, nearest as the axis shows them
 * (on the logarithm); a pixel outside the plot is the first or the last.
 */
export function nearestDurationIndex(pixel: number, width: number): number {
  const plot = width - KOSTRA_PLOT.left - KOSTRA_PLOT.right
  const at = LOG_FIRST + (pixel - KOSTRA_PLOT.left) / plot * (LOG_LAST - LOG_FIRST)
  let best = 0
  KOSTRA_DURATIONS.forEach((minutes, index) => {
    if (Math.abs(xOfDuration(minutes) - at) < Math.abs(xOfDuration(KOSTRA_DURATIONS[best]!) - at))
      best = index
  })
  return best
}

/** The colour of the curve of the return period at `index`, for the page's scheme */
export function curveColour(index: number, dark: boolean): string {
  return KOSTRA_CURVE_COLOURS[dark ? 'dark' : 'light'][index]!
}

/** The values of a duration, one for each return period, in the quantity shown: what the readout lists */
export function kostraReadoutRows(table: KostraTable, quantity: KostraQuantity, durationIndex: number): { years: number, value: number | null, colourIndex: number }[] {
  return KOSTRA_RETURN_PERIODS.map((years, colourIndex) => ({ years, value: quantityOf(table.rows[durationIndex]?.[colourIndex] ?? null, quantity), colourIndex }))
}

export interface KostraOptionInput {
  table: KostraTable
  quantity: KostraQuantity
  theme: ChartTheme
  width: number
  height: number
  /** The index of the duration the crosshair is at, null for none */
  cursor: number | null
  /** The number as the page writes it, with the digits given */
  format: (value: number, digits: number) => string
  /** A duration as it is read (`1 h`) */
  durationLabel: (minutes: number) => string
}

/** The option for the chart: a plain object, so that a test reads it without the library */
export function buildKostraOption(input: KostraOptionInput) {
  const { table, quantity, theme, cursor } = input
  const ticks = kostraTicks(input.width).map(xOfDuration)
  const labelOf = (value: number) => input.durationLabel(Math.round(10 ** value))
  const text = theme.textMuted || undefined
  const grid = theme.grid || undefined

  const curves = KOSTRA_RETURN_PERIODS.map((years, periodIndex) => ({
    id: `curve-${years}`,
    name: String(years),
    type: 'line' as const,
    silent: true,
    showSymbol: false,
    // a value DWD gives none for leaves a gap in the curve, never a zero
    data: KOSTRA_DURATIONS.map((minutes, durationIndex) => [xOfDuration(minutes), quantityOf(table.rows[durationIndex]?.[periodIndex] ?? null, quantity)]),
    lineStyle: { width: 2, color: curveColour(periodIndex, theme.dark) },
    itemStyle: { color: curveColour(periodIndex, theme.dark) },
    z: 2 + periodIndex,
  }))

  // the crosshair reaches the highest value of the chart, so that it does not lift the axis
  const top = Math.max(0, ...table.rows.flat().map(entry => quantityOf(entry, quantity) ?? 0))
  const at = cursor === null ? null : KOSTRA_DURATIONS[cursor] ?? null
  const marks = at === null
    ? []
    : [
        {
          id: 'cursor-line',
          type: 'line' as const,
          silent: true,
          showSymbol: false,
          data: [[xOfDuration(at), 0], [xOfDuration(at), top]],
          lineStyle: { width: 1, color: theme.axis || undefined, type: 'dashed' as const },
          z: 1,
        },
        {
          id: 'cursor-points',
          type: 'line' as const,
          silent: true,
          symbol: 'circle',
          symbolSize: 9,
          // a line of no width: only the nine marks, each in its curve's colour with a ring of the paper round it
          lineStyle: { width: 0, opacity: 0 },
          data: kostraReadoutRows(table, quantity, cursor!)
            .filter(row => row.value !== null)
            .map(row => ({ value: [xOfDuration(at), row.value], itemStyle: { color: curveColour(row.colourIndex, theme.dark), borderColor: theme.paper || '#ffffff', borderWidth: 2 } })),
          z: 20,
        },
      ]

  return {
    animation: false,
    textStyle: { fontFamily: 'inherit', fontSize: 12 },
    grid: { left: KOSTRA_PLOT.left, right: KOSTRA_PLOT.right, top: KOSTRA_PLOT.top, bottom: KOSTRA_PLOT.bottom },
    xAxis: {
      type: 'value' as const,
      min: LOG_FIRST,
      max: LOG_LAST,
      axisLine: { lineStyle: { color: theme.axis || undefined } },
      axisTick: { customValues: ticks, lineStyle: { color: theme.axis || undefined } },
      axisLabel: { customValues: ticks, formatter: labelOf, color: text, margin: 10, hideOverlap: true },
      splitLine: { show: true, lineStyle: { color: grid } },
    },
    yAxis: {
      type: 'value' as const,
      min: 0,
      axisLabel: { color: text, formatter: (value: number) => input.format(value, 0) },
      splitLine: { lineStyle: { color: grid } },
    },
    series: [...curves, ...marks],
  }
}
