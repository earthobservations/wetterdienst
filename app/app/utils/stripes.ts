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
 * The colour of a point of a scale, 0 to 1, mixed between the two stops around it, as Plotly draws it.
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
