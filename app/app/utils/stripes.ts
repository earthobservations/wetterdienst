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
