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

/** The WMO's reference period, which the stripes' takeaway compares the latest years with */
export const NORMAL_PERIOD = { from: 1961, to: 1990 } as const
/** How many of the latest years the takeaway averages */
export const RECENT_YEARS = 10

export interface NormalComparison {
  /** the latest years averaged: the last year drawn and the nine before it */
  recentFrom: number
  recentTo: number
  recentMean: number
  normalFrom: number
  normalTo: number
  normalMean: number
  /** the latest years' mean less the normal's */
  difference: number
  /** the difference as a share of the normal's mean, where that is above zero */
  ratio: number | null
}

function mean(numbers: number[]) {
  return numbers.reduce((sum, value) => sum + value, 0) / numbers.length
}

/**
 * What the stripes say in one sentence (GH-3518): the mean of the latest ten years drawn against the mean of
 * 1961-1990, the WMO's reference period, from the years the chart draws and nothing else. None where that cannot
 * be told fairly: fewer than 27 of the normal's 30 years drawn, fewer than 8 of the latest ten, or latest years
 * that reach back into the normal itself.
 */
export function compareWithNormal(years: Pick<StripeYear, 'year' | 'value'>[]): NormalComparison | null {
  if (!years.length)
    return null
  const recentTo = Math.max(...years.map(year => year.year))
  const recentFrom = recentTo - RECENT_YEARS + 1
  if (recentFrom <= NORMAL_PERIOD.to)
    return null
  const normal = years.filter(year => year.year >= NORMAL_PERIOD.from && year.year <= NORMAL_PERIOD.to).map(year => year.value)
  const recent = years.filter(year => year.year >= recentFrom).map(year => year.value)
  if (normal.length < 27 || recent.length < 8)
    return null
  const normalMean = mean(normal)
  const recentMean = mean(recent)
  const difference = recentMean - normalMean
  return {
    recentFrom,
    recentTo,
    recentMean,
    normalFrom: NORMAL_PERIOD.from,
    normalTo: NORMAL_PERIOD.to,
    normalMean,
    difference,
    ratio: normalMean > 0 ? difference / normalMean : null,
  }
}
