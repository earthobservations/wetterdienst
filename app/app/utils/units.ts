// The units an answer reports its numbers in, and the one each kind of number is judged in (GH-3980).
//
// The forecast, the widget, the map's panel and the questions of the start page ask the backend for the units the app
// settings choose, so a number can come back in °F, in km/h or in Pa. What such a number is called is what the answer
// says (`metadata.parameters[].unit`, the symbol of the unit of its values), never a constant. What a number is
// compared with is another matter: a threshold ("rain from a millimetre", "snow below 0.5 °C", "a gale from Beaufort 9")
// is a fact about the weather and has one value. The code that judges a number converts it to the canonical unit of its
// quantity first (`toCanonical`) and converts to the unit of the answer only to write it (`fromCanonical`), so that a
// verdict is the same in every unit.

/** The quantities (the backend's unit types) the forecast and the questions read, and the unit each is judged in */
export const CANONICAL_UNITS = {
  temperature: '°C',
  precipitation: 'mm',
  speed: 'm/s',
  pressure: 'hPa',
  angle: '°',
  fraction: '%',
} as const

export type Quantity = keyof typeof CANONICAL_UNITS

interface Scale {
  toCanonical: (value: number) => number
  fromCanonical: (value: number) => number
}

const linear = (factor: number): Scale => ({ toCanonical: v => v * factor, fromCanonical: v => v / factor })
const identity: Scale = { toCanonical: v => v, fromCanonical: v => v }

/** Beaufort's scale is not linear: `v = 0.836 * B^(3/2)` m/s, which the backend converts by too */
const BEAUFORT: Scale = { toCanonical: b => 0.836 * b ** 1.5, fromCanonical: v => (v / 0.836) ** (2 / 3) }
/** A knot is a nautical mile (1852 m) an hour, which is how the backend converts it */
const METERS_PER_SECOND_PER_KNOT = 1852 / 3600

/** How to convert each unit symbol of a quantity, as the backend writes the symbol (`UnitConverter.units`) */
const SCALES: Record<Quantity, Record<string, Scale>> = {
  temperature: {
    '°C': identity,
    'K': { toCanonical: v => v - 273.15, fromCanonical: v => v + 273.15 },
    '°F': { toCanonical: v => (v - 32) / 1.8, fromCanonical: v => v * 1.8 + 32 },
  },
  precipitation: { 'mm': identity, 'l/m²': identity },
  speed: {
    'm/s': identity,
    'km/h': linear(1 / 3.6),
    'kn': { toCanonical: v => v * METERS_PER_SECOND_PER_KNOT, fromCanonical: v => v / METERS_PER_SECOND_PER_KNOT },
    'bft': BEAUFORT,
  },
  pressure: { hPa: identity, Pa: linear(0.01), kPa: linear(10) },
  angle: {
    '°': identity,
    'rad': { toCanonical: v => v * 180 / Math.PI, fromCanonical: v => v * Math.PI / 180 },
    'grad': { toCanonical: v => v * 0.9, fromCanonical: v => v / 0.9 },
  },
  // the backend writes a fraction as the symbol `-` (0 to 1), `%` or `1/8` (oktas)
  fraction: {
    '%': identity,
    '-': linear(100),
    '1/8': { toCanonical: v => v * 12.5, fromCanonical: v => v / 12.5 },
  },
}

/** The symbols of the units of a quantity this file converts: the units the settings page offers, and those of the sources */
export function knownUnits(quantity: Quantity): string[] {
  return Object.keys(SCALES[quantity])
}

/**
 * The scale of a unit symbol. A symbol that is not known is taken to be the canonical unit of the quantity: its numbers
 * are written with their own symbol all the same, and are judged as they are.
 */
function scaleOf(quantity: Quantity, unit: string): Scale {
  return SCALES[quantity][unit] ?? identity
}

/**
 * `value`, which is in `unit`, in the canonical unit of its quantity: the one thresholds are written in. Rounded to three
 * decimals, which is finer than any reading is but coarser than what the conversions add: floating point (61.92 km/h is
 * 17.2 m/s, not 17.199999999999996) and the backend's own rounding of a converted value to four decimals (13.9 m/s comes
 * back as 27.0194 kn, which is 13.89998 m/s). Either would otherwise put a value that sits on a threshold on the wrong
 * side of it, a Beaufort force less than the one the same wind has in m/s.
 */
export function toCanonical(quantity: Quantity, unit: string, value: number): number {
  return Math.round(scaleOf(quantity, unit).toCanonical(value) * 1e3) / 1e3
}

/** `value`, which is in the canonical unit of its quantity, in `unit` */
export function fromCanonical(quantity: Quantity, unit: string, value: number): number {
  return scaleOf(quantity, unit).fromCanonical(value)
}

/**
 * The size of a canonical difference in `unit`: 1 K is 1.8 °F, 1 hPa is 100 Pa. For the quantities whose units differ
 * by a factor and an offset or a factor only (temperature, pressure, precipitation); not for Beaufort.
 */
export function differenceIn(quantity: Quantity, unit: string, delta: number): number {
  return fromCanonical(quantity, unit, delta) - fromCanonical(quantity, unit, 0)
}

/**
 * How a unit is written next to a name: its symbol, and `0–1` for a fraction written as a decimal, whose symbol (`-`)
 * says nothing
 */
export function unitText(unit: string): string {
  return unit === '-' ? '0–1' : unit
}

/**
 * How a unit is written after a number: a degree sign and a percent sign follow it closely (`14°C`, `60%`), any other
 * unit a space after it (`6.0 mm`). Nothing for a fraction as a decimal, which has no symbol to write.
 */
export function withUnit(text: string, unit: string): string {
  if (unit === '-')
    return text
  return /^[°%]/.test(unit) ? `${text}${unit}` : `${text} ${unit}`
}

/** The decimals a number is written with in a unit: the finer the unit is, the fewer it needs, the coarser the more */
export function digitsOf(quantity: Quantity, unit: string): number {
  switch (quantity) {
    case 'temperature': return 1
    case 'precipitation': return 2
    case 'speed': return 1
    case 'pressure': return unit === 'Pa' ? 0 : unit === 'kPa' ? 2 : 1
    case 'angle': return unit === 'rad' ? 2 : 0
    case 'fraction': return unit === '-' ? 2 : unit === '1/8' ? 1 : 0
  }
}

/**
 * The symbols of the parameters of an answer, by the canonical name of the parameter: what `metadata.parameters` of an
 * answer to a request `with_metadata` says each is in. Empty where the answer carries none.
 */
export function unitsOfAnswer(answer: { metadata?: { parameters?: ReadonlyArray<{ name: string, unit: string }> | null } | null } | null | undefined): Record<string, string> {
  return Object.fromEntries((answer?.metadata?.parameters ?? []).map(parameter => [parameter.name, parameter.unit]))
}
