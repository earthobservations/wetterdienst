// The spacing of the time labels of the meteogram's top axis (GH-3558). The labels are 12 px type, "19:00" about
// 34 px wide, and a label needs room beside it; a phone's chart is 250 to 300 px wide, which holds three or four.

/** The widths the meteogram leaves at the left and the right of its plot (its `margin` in px) */
export const MARGIN_LEFT = 68
export const MARGIN_RIGHT = 8

/** The room a label of the time axis needs, in px: its 34 px and a gap */
export const TICK_SPACING = 46

/** The steps between two labels, in hours; the last is the coarsest */
export const TICK_STEPS_HOURS = [1, 3, 6, 12, 24, 48, 72, 96, 120]

/** The width of the plot of a chart that is `chartWidth` px wide */
export function plotWidth(chartWidth: number): number {
  return Math.max(0, chartWidth - MARGIN_LEFT - MARGIN_RIGHT)
}

/**
 * The hours between two labels of an axis of `rangeHours` that is `plotWidthPx` px wide: the finest step with
 * a label for each `TICK_SPACING` px, and the coarsest where none does (two labels at least are shown by the
 * 120 h step of any range a forecast has, 240 h)
 */
export function tickStepHours(rangeHours: number, plotWidthPx: number): number {
  const maxTicks = Math.max(1, Math.floor(plotWidthPx / TICK_SPACING))
  return TICK_STEPS_HOURS.find(step => Math.ceil(rangeHours / step) <= maxTicks) ?? TICK_STEPS_HOURS.at(-1)!
}

/** What a character of an axis title is wide, in ems: Inter's average over Latin text, the capitals and digits more */
const TITLE_CHAR_EM = 0.62

/**
 * An axis title written along its panel, which is `panelPx` tall: on one line where it fits, and on two (cut at the
 * space nearest its middle, the way Plotly breaks a line: `<br>`) where it does not, which a German "Niederschlag mm"
 * of 12 px in a panel of 88 px does not. A title of one word stays on one line.
 */
export function fitAxisTitle(text: string, panelPx: number, fontPx: number): { text: string, lines: 1 | 2 } {
  const width = (value: string) => value.length * TITLE_CHAR_EM * fontPx
  if (width(text) <= panelPx)
    return { text, lines: 1 }
  const spaces = [...text.matchAll(/ /g)].map(match => match.index)
  const middle = text.length / 2
  const at = spaces.sort((a, b) => Math.abs(a - middle) - Math.abs(b - middle))[0]
  if (at === undefined)
    return { text, lines: 1 }
  return { text: `${text.slice(0, at)}<br>${text.slice(at + 1)}`, lines: 2 }
}
