/**
 * The unit each of the meteogram's quantities is in, and the conversions between it and the canonical unit the
 * verdicts are judged in (GH-3980): one set of helpers for the chart, the day cards, the summary and the table.
 */
import type { Quantity } from './units'
import { METEOGRAM_SERIES } from './meteogram'
import { CANONICAL_UNITS, differenceIn, digitsOf, fromCanonical, toCanonical, unitText } from './units'

/** The quantity each group of series is of: what the unit of a series is looked up by */
const GROUP_QUANTITY: Partial<Record<keyof typeof METEOGRAM_SERIES, Quantity>> = {
  precipitation: 'precipitation',
  temperature: 'temperature',
  temperatureMax: 'temperature',
  temperatureMin: 'temperature',
  dewPoint: 'temperature',
  humidity: 'fraction',
  windSpeed: 'speed',
  gust: 'speed',
  windDirection: 'angle',
  cloudCover: 'fraction',
  cloudCoverLow: 'fraction',
  cloudCoverMid: 'fraction',
  cloudCoverHigh: 'fraction',
  pressure: 'pressure',
}

/** The translation function the helpers write names with */
export type Translate = (key: string, named?: Record<string, unknown>) => string

export interface MeteogramUnits {
  /** The unit the answer's numbers of a quantity are in */
  unitOf: (quantity: Quantity) => string
  /** A number of the answer, in the canonical unit of its quantity: what thresholds are compared with */
  canon: (quantity: Quantity, value: number) => number
  /** A number in the canonical unit of its quantity, in the unit of the answer */
  shown: (quantity: Quantity, value: number) => number
  /** A canonical difference (a degree, a hectopascal), in the unit of the answer */
  stretch: (quantity: Quantity, delta: number) => number
  /** The unit of a quantity as a name has it: `Temperature °C` */
  unitName: (quantity: Quantity) => string
  /** The decimals the numbers of a quantity are written with in the unit of the answer */
  digits: (quantity: Quantity) => number
  /** A name that carries the unit of its quantity (the translation has the place `{unit}` for it), trimmed where there is none */
  named: (key: string, quantity: Quantity) => string
  /**
   * The title of an axis, always by one rule: the name on the first line and the unit on its own second line, whatever the
   * language, the width and the panel; a title with no unit (the translation has the place `{unit}` for it) is one line
   */
  title: (key: string, quantity: Quantity) => string
}

/**
 * The unit the answer reports for each quantity: that of the first of its series the answer states a unit for (every
 * series of a quantity is asked for in the one unit), else the canonical unit of the quantity
 */
export function quantityUnits(units: Record<string, string> | undefined): Record<Quantity, string> {
  const found: Record<Quantity, string> = { ...CANONICAL_UNITS }
  const done = new Set<Quantity>()
  for (const [group, quantity] of Object.entries(GROUP_QUANTITY) as [keyof typeof METEOGRAM_SERIES, Quantity][]) {
    if (done.has(quantity))
      continue
    const stated = METEOGRAM_SERIES[group].map(name => units?.[name]).find((unit): unit is string => !!unit)
    if (stated) {
      found[quantity] = stated
      done.add(quantity)
    }
  }
  return found
}

/** The helpers of an answer whose units are `units` (by the parameter's canonical name), named in the language of `t` */
export function meteogramUnits(units: Record<string, string> | undefined, t: Translate): MeteogramUnits {
  const found = quantityUnits(units)
  const unitOf = (quantity: Quantity) => found[quantity]
  const unitName = (quantity: Quantity) => unitText(unitOf(quantity))
  return {
    unitOf,
    canon: (quantity, value) => toCanonical(quantity, unitOf(quantity), value),
    shown: (quantity, value) => fromCanonical(quantity, unitOf(quantity), value),
    stretch: (quantity, delta) => differenceIn(quantity, unitOf(quantity), delta),
    unitName,
    digits: quantity => digitsOf(quantity, unitOf(quantity)),
    named: (key, quantity) => t(key, { unit: unitName(quantity) }).trim(),
    title: (key, quantity) => {
      const unit = unitName(quantity).trim()
      const name = t(key, { unit: '' }).trim()
      return unit ? `${name}\n${unit}` : name
    },
  }
}
