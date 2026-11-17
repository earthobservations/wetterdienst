import type { StripesKind } from '#shared/types/api'

/**
 * The words a stripe's class is told in, for the table and the readout: the 16 classes of the colour scale in five bands,
 * symmetric round the centre. Not a second scale: the class is the backend's (`stripe_class`, 0 to 15, from the lowest
 * value to the highest), these only name it.
 */
export const STRIPE_CLASSES = ['veryLow', 'low', 'middle', 'high', 'veryHigh'] as const
export type StripeClass = (typeof STRIPE_CLASSES)[number]

/** How many colours the scale has: 8 below the centre and 8 above (what the backend answers as `reference.classes`) */
export const STRIPE_CLASS_COUNT = 16

/**
 * The band of a class: the classes 0 to 2 (beyond 1.6 standard deviations below the centre) are very low, 3 to 6 low, the
 * two next to the centre (within a third of a standard deviation of it) the middle, and the upper half is the mirror.
 */
export function stripeBand(stripeClass: number): StripeClass {
  if (stripeClass <= 2)
    return 'veryLow'
  if (stripeClass <= 6)
    return 'low'
  if (stripeClass <= 8)
    return 'middle'
  if (stripeClass <= 12)
    return 'high'
  return 'veryHigh'
}

export interface StripeYear {
  year: number
  value: number
  /** the year's distance from the mean of the reference, in the unit of the value */
  anomaly: number
  /** 0 (the lowest) to 15, as the backend classes the year: the colour of its stripe */
  stripeClass: number
  class: StripeClass
}

/** A value of the answer of `/stripes/values`, as far as the stripes read it */
export interface StripesValueInput {
  timestamp: string | null
  value: number | null
  anomaly: number | null
  stripe_class: number | null
}

/**
 * The years a chart of climate stripes draws, as the table that stands for it lists them: each with its value, its anomaly
 * and its class, which the backend has calculated against the station's whole record and not against the years shown.
 * Years without a value are not drawn, so they are not here; each year is read in UTC, as the stripes read it.
 */
export function stripeYears(values: readonly StripesValueInput[]): StripeYear[] {
  return values
    .filter((item): item is { timestamp: string, value: number, anomaly: number, stripe_class: number } => item.value !== null && item.timestamp !== null && item.anomaly !== null && item.stripe_class !== null)
    .map(item => ({
      year: new Date(item.timestamp).getUTCFullYear(),
      value: item.value,
      anomaly: item.anomaly,
      stripeClass: item.stripe_class,
      class: stripeBand(item.stripe_class),
    }))
}

/** What the answer's `reference` says of one number of it: the years it was calculated from, and whether the whole record stood in for the period of the method */
export interface StripesReferenceStatView {
  first_year: number
  last_year: number
  fallback: boolean
}

/** The part of the answer's `reference` the sentence under the stripes reads */
export interface StripesReferenceView {
  centre: StripesReferenceStatView
  spread: StripesReferenceStatView
  range_sigma: number
}

/**
 * The sentence that says what the colours of a set of stripes are relative to (`stripes.reference`): the mean of 1971 to 2000
 * and the standard deviation of 1901 to 2000, or the whole record of a station that has too few years in them
 * (`stripes.referenceWhole`), each with the years of the answer.
 *
 * @param reference - What the answer says the classes are relative to
 * @param t - Writes the sentence in the language of the page
 * @param format - Writes the number of standard deviations the scale reaches to either side, 2.6
 * @param key - The sentence: the whole one under the chart (`stripes.reference`), or the short one of a saved image (`stripes.plotReference`)
 */
export function stripesReferenceText(
  reference: StripesReferenceView,
  t: (key: string, params?: Record<string, unknown>) => string,
  format: (value: number) => string,
  key: 'stripes.reference' | 'stripes.plotReference' = 'stripes.reference',
): string {
  return t(key, { centre: referencePeriod(reference.centre, t), spread: referencePeriod(reference.spread, t), sigma: format(reference.range_sigma) })
}

/** The years one number of the reference was calculated from: the period of the method (`1971–2000`), or the whole record where the station had too few years in it */
export function referencePeriod(stat: StripesReferenceStatView, t: (key: string, params?: Record<string, unknown>) => string): string {
  return stat.fallback
    ? t('stripes.referenceWhole', { from: stat.first_year, to: stat.last_year })
    : `${stat.first_year}–${stat.last_year}`
}

/**
 * What the bars with a scale are relative to, written under their title (`stripes.barsRelativeTo`): the mean of the reference's
 * period, the same the colours are centred on, with the unit of the anomalies in brackets, `[°C]`, where there is one.
 */
export function barsSubtitle(reference: StripesReferenceView, unit: string, t: (key: string, params?: Record<string, unknown>) => string): string {
  const text = t('stripes.barsRelativeTo', { period: referencePeriod(reference.centre, t) })
  return unit ? `${text} [${unit}]` : text
}

/**
 * The 16 colours of the stripes, from the lowest class (0) to the highest (15): the same as the backend's image has
 * (`wetterdienst/ui/stripes_scale.py`, which a test holds this to). Temperature: the eight most saturated classes of
 * ColorBrewer's 9-class Blues, below the mean of the reference, and Reds above it, as Ed Hawkins' stripes have them.
 * Precipitation: the two halves of ColorBrewer's BrBG, brown for dry and teal for wet, eight sampled along each.
 */
export const STRIPE_PALETTES: Record<StripesKind, readonly string[]> = {
  temperature: [
    '#08306b',
    '#08519c',
    '#2171b5',
    '#4292c6',
    '#6baed6',
    '#9ecae1',
    '#c6dbef',
    '#deebf7',
    '#fee0d2',
    '#fcbba1',
    '#fc9272',
    '#fb6a4a',
    '#ef3b2c',
    '#cb181d',
    '#a50f15',
    '#67000d',
  ],
  precipitation: [
    '#543005',
    '#744308',
    '#93580f',
    '#b07323',
    '#c89444',
    '#dab972',
    '#e9d29b',
    '#f6e8c3',
    '#c7eae5',
    '#9ed9d0',
    '#75c5ba',
    '#4aa69d',
    '#268981',
    '#086d65',
    '#01544a',
    '#003c30',
  ],
}

/** The colour of a class of the scale, 0 to 15 (a class outside them takes the end it lies at) */
export function stripeColour(kind: StripesKind, stripeClass: number): string {
  const palette = STRIPE_PALETTES[kind]
  return palette[Math.min(palette.length - 1, Math.max(0, Math.round(stripeClass)))]!
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
 * joined with `<br>`, which the stripes' chart splits again: a title as wide as the chart is cut off by its edges where
 * the chart is narrow (320 px: GH-3961). Breaks at spaces. A word wider than a line is broken after its `-` and `/` (kept at the end
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
