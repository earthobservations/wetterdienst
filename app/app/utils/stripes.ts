import type { StripesKind } from '#shared/types/api'

/** The classes a stripe is put in by its colour: fifths of the range between the lowest and the highest year shown */
export const STRIPE_CLASSES = ['veryLow', 'low', 'middle', 'high', 'veryHigh'] as const
export type StripeClass = (typeof STRIPE_CLASSES)[number]

/**
 * The class of a year's stripe, as its colour is chosen: the value's place between the lowest and the
 * highest year drawn (the stripes' colour scale runs over that range), in fifths. A series whose years are
 * all alike is in the middle.
 */
export function stripeClass(value: number, min: number, max: number): StripeClass {
  if (max <= min)
    return 'middle'
  const fifth = Math.floor((value - min) / (max - min) * STRIPE_CLASSES.length)
  return STRIPE_CLASSES[Math.min(STRIPE_CLASSES.length - 1, Math.max(0, fifth))]!
}

export interface StripeYear {
  year: number
  value: number
  class: StripeClass
}

/**
 * The years a chart of climate stripes draws, as the table that stands for it lists them: each with its value
 * and class. Years without a value are not drawn, so they are not here; each year is read in UTC, as the
 * stripes read it.
 */
export function stripeYears(values: { timestamp: string | null, value: number | null }[]): StripeYear[] {
  const drawn = values.filter((item): item is { timestamp: string, value: number } => item.value !== null && item.timestamp !== null)
  const numbers = drawn.map(item => item.value)
  const min = Math.min(...numbers)
  const max = Math.max(...numbers)
  return drawn.map(item => ({
    year: new Date(item.timestamp).getUTCFullYear(),
    value: item.value,
    class: stripeClass(item.value, min, max),
  }))
}

/** The colour scales of the stripes, from the lowest year (0) to the highest (1): the stripes page's and the map panel's */
export const COLOR_MAPS: Record<StripesKind, Array<[number, string]>> = {
  temperature: [
    [0, 'rgb(5,48,97)'],
    [0.2, 'rgb(33,102,172)'],
    [0.4, 'rgb(146,197,222)'],
    [0.5, 'rgb(247,247,247)'],
    [0.6, 'rgb(253,219,199)'],
    [0.8, 'rgb(239,138,98)'],
    [1, 'rgb(178,24,43)'],
  ],
  precipitation: [
    [0, 'rgb(84,48,5)'],
    [0.2, 'rgb(140,81,10)'],
    [0.4, 'rgb(191,129,45)'],
    [0.5, 'rgb(246,232,195)'],
    [0.6, 'rgb(199,234,229)'],
    [0.8, 'rgb(90,180,172)'],
    [1, 'rgb(1,102,94)'],
  ],
}

/**
 * The colour of a point of a scale, 0 to 1, mixed between the two stops around it (the scale's colours in RGB, as the stripes have always been drawn).
 *
 * @example
 * stripeColour(COLOR_MAPS.temperature, 0.5) // 'rgb(247, 247, 247)'
 */
export function stripeColour(scale: Array<[number, string]>, position: number): string {
  const at = Math.min(1, Math.max(0, position))
  const rgb = (css: string) => css.match(/\d+/g)!.map(Number)
  for (let index = 1; index < scale.length; index++) {
    const [stop, colour] = scale[index]!
    if (at <= stop) {
      const [previous, previousColour] = scale[index - 1]!
      const share = stop === previous ? 0 : (at - previous) / (stop - previous)
      const [a, b] = [rgb(previousColour), rgb(colour)]
      return `rgb(${a.map((channel, i) => Math.round(channel + (b[i]! - channel) * share)).join(', ')})`
    }
  }
  return `rgb(${rgb(scale[scale.length - 1]![1]).join(', ')})`
}

/**
 * The named values of the sentence that says what a set of stripes shows (`stripes.summary`): the span of the years, and
 * the lowest and highest year with its value, written by `format`. The stripes page and the map's panel say it the same way.
 *
 * @param years - The years drawn, as `stripeYears` lists them; not empty
 */
export function stripesSummaryParams(years: StripeYear[], format: (value: number) => string) {
  const lowest = years.reduce((low, year) => year.value < low.value ? year : low)
  const highest = years.reduce((high, year) => year.value > high.value ? year : high)
  return {
    from: Math.min(...years.map(year => year.year)),
    to: Math.max(...years.map(year => year.year)),
    min: format(lowest.value),
    minYear: lowest.year,
    max: format(highest.value),
    maxYear: highest.year,
  }
}

/** How wide `text` is in px in `font` (a CSS font shorthand, `16px Arial, sans-serif`): null where there is no canvas to measure with */
export type TextMeasure = (text: string, font: string) => number | null

let measureContext: CanvasRenderingContext2D | null | undefined

/** The browser's own measure, in the font the chart draws with; null without a canvas (a unit test, a server) */
export const measureWithCanvas: TextMeasure = (text, font) => {
  if (measureContext === undefined) {
    try {
      measureContext = typeof document === 'undefined' ? null : document.createElement('canvas').getContext('2d')
    }
    catch {
      measureContext = null
    }
  }
  if (!measureContext)
    return null
  measureContext.font = font
  return measureContext.measureText(text).width
}

/**
 * `text` broken into lines no wider than `width` px in `font` (a CSS font shorthand such as `16px Arial, sans-serif`),
 * joined with the `<br>` Plotly's titles take: a title as wide as the chart is cut off by its edges where the chart is
 * narrow (320 px: GH-3961). Breaks at spaces. A word wider than a line is broken after its `-` and `/` (kept at the end
 * of the line: `Mallersdorf-` / `Pfaffenberg-`), and one without either stays whole on a line of its own. The width is
 * measured with `measure` (the canvas's, in the font the chart draws with); where that has none the width of a
 * character is estimated at 0.5 em, a little above what a title in Arial measures (0.47 em), so that a line is rather
 * short than cut.
 */
export function wrapChartTitle(text: string, width: number, font: string, measure: TextMeasure = measureWithCanvas): { text: string, lines: number } {
  const size = Number.parseFloat(/(\d+(?:\.\d+)?)px/.exec(font)?.[1] ?? '16')
  const widthOf = (value: string) => measure(value, font) ?? value.length * size * 0.5
  // [the text, whether a space comes before it]: the pieces of a word that is too wide are joined to each other
  const pieces: [string, boolean][] = []
  for (const word of text.split(' ')) {
    const parts = widthOf(word) > width ? word.split(/(?<=[-/])/) : [word]
    parts.forEach((part, index) => pieces.push([part, index === 0]))
  }
  const lines: string[] = []
  let line = ''
  for (const [piece, spaced] of pieces) {
    const joined = line && spaced ? `${line} ${piece}` : `${line}${piece}`
    if (line && widthOf(joined) > width) {
      lines.push(line)
      line = piece
    }
    else {
      line = joined
    }
  }
  lines.push(line)
  return { text: lines.join('<br>'), lines: lines.length }
}
