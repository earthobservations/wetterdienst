import type { Quantity } from '../../app/utils/units'
import { describe, expect, it } from 'vitest'
import { requestUnitTargets, UNIT_TARGET_TYPES } from '../../app/utils/unit-targets'
import { CANONICAL_UNITS, differenceIn, digitsOf, fromCanonical, knownUnits, toCanonical, unitsOfAnswer, unitText, withUnit } from '../../app/utils/units'

// What a number is judged in and what it is written in are two things (GH-3980): these hold the conversion between them to
// what the backend's UnitConverter does, so that a threshold in canonical units reads a number of any unit the settings offer.
describe('the units of an answer', () => {
  it('converts every unit the settings offer for the quantities the forecast and the answers read, and no fewer', () => {
    for (const quantity of Object.keys(CANONICAL_UNITS) as Quantity[]) {
      const offered = UNIT_TARGET_TYPES.find(({ type }) => type === quantity)!.units
      expect(knownUnits(quantity), quantity).toHaveLength(offered.length)
    }
  })

  it('has the canonical unit of a quantity as one of its units, with the scale of the identity', () => {
    for (const [quantity, unit] of Object.entries(CANONICAL_UNITS) as [Quantity, string][]) {
      expect(knownUnits(quantity)).toContain(unit)
      expect(toCanonical(quantity, unit, 12.5)).toBe(12.5)
      expect(fromCanonical(quantity, unit, 12.5)).toBe(12.5)
    }
  })

  // the same weather in each unit the settings offer: the canonical value goes to it and back, and the unit's value comes
  // to the canonical one
  it.each([
    ['temperature', '°C', 20, 20],
    ['temperature', '°F', 20, 68],
    ['temperature', 'K', 20, 293.15],
    ['precipitation', 'l/m²', 3.5, 3.5],
    ['speed', 'km/h', 10, 36],
    ['speed', 'kn', 10, 10 / (1852 / 3600)],
    ['speed', 'bft', 3.4, (3.4 / 0.836) ** (2 / 3)],
    ['pressure', 'Pa', 1013.25, 101325],
    ['pressure', 'kPa', 1013.25, 101.325],
    ['angle', 'rad', 180, Math.PI],
    ['angle', 'grad', 90, 100],
    ['fraction', '-', 50, 0.5],
    ['fraction', '1/8', 50, 4],
  ] as const)('converts %s in %s: %d canonical is %d', (quantity, unit, canonical, written) => {
    expect(fromCanonical(quantity, unit, canonical)).toBeCloseTo(written, 9)
    expect(toCanonical(quantity, unit, written)).toBeCloseTo(canonical, 3)
  })

  it('does not let floating point move a value across a threshold: 61.92 km/h is Beaufort 8, as 17.2 m/s is', () => {
    expect(toCanonical('speed', 'km/h', 61.92)).toBe(17.2)
    expect(toCanonical('temperature', '°F', 32.9)).toBeCloseTo(0.5, 8)
  })

  it('does not let the backend\'s rounding of a converted value move it across a threshold either', () => {
    // as the backend answers them, to four decimals
    expect(toCanonical('speed', 'kn', 27.0194)).toBe(13.9)
    expect(toCanonical('speed', 'kn', 33.4341)).toBe(17.2)
    expect(toCanonical('speed', 'bft', 7.5084)).toBe(17.2)
    expect(toCanonical('speed', 'kn', 10.6911)).toBe(5.5)
  })

  it('takes a difference by its factor and not by its offset: a Kelvin is 1.8 degrees Fahrenheit', () => {
    expect(differenceIn('temperature', '°C', 3)).toBe(3)
    expect(differenceIn('temperature', 'K', 3)).toBeCloseTo(3, 9)
    expect(differenceIn('temperature', '°F', 3)).toBeCloseTo(5.4, 9)
    expect(differenceIn('pressure', 'Pa', 2)).toBeCloseTo(200, 9)
  })

  it('reads a unit it does not know as the canonical one, and writes it as it is', () => {
    expect(toCanonical('speed', 'furlongs per fortnight', 7)).toBe(7)
    expect(withUnit('7.0', 'furlongs per fortnight')).toBe('7.0 furlongs per fortnight')
  })

  it('writes a unit after a number as the unit asks', () => {
    expect(withUnit('14', '°C')).toBe('14°C')
    expect(withUnit('14', '°F')).toBe('14°F')
    expect(withUnit('60', '%')).toBe('60%')
    expect(withUnit('6.0', 'mm')).toBe('6.0 mm')
    expect(withUnit('287', 'K')).toBe('287 K')
    // a decimal fraction has no symbol to write
    expect(withUnit('0.45', '-')).toBe('0.45')
    expect(unitText('-')).toBe('0–1')
    expect(unitText('hPa')).toBe('hPa')
  })

  it('gives each unit the decimals it needs', () => {
    expect([digitsOf('pressure', 'hPa'), digitsOf('pressure', 'Pa'), digitsOf('pressure', 'kPa')]).toEqual([1, 0, 2])
    expect([digitsOf('fraction', '%'), digitsOf('fraction', '-'), digitsOf('fraction', '1/8')]).toEqual([0, 2, 1])
    expect([digitsOf('angle', '°'), digitsOf('angle', 'rad')]).toEqual([0, 2])
  })

  it('reads the unit of each parameter from the metadata of an answer, and nothing from one without', () => {
    expect(unitsOfAnswer({ metadata: { parameters: [{ name: 'temperature_air_2m', unit: '°F' }, { name: 'wind_speed', unit: 'bft' }] } }))
      .toEqual({ temperature_air_2m: '°F', wind_speed: 'bft' })
    expect(unitsOfAnswer({ metadata: {} })).toEqual({})
    expect(unitsOfAnswer({})).toEqual({})
    expect(unitsOfAnswer(null)).toEqual({})
  })

  it('asks the six quantities in the unit the settings choose, and every other quantity in its default', () => {
    const targets = requestUnitTargets({ temperature: 'degree_fahrenheit', speed: 'beaufort' })
    expect([targets.temperature, targets.speed, targets.precipitation]).toEqual(['degree_fahrenheit', 'beaufort', 'millimeter'])
  })
})
