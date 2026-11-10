import { describe, expect, it } from 'vitest'
import { SETTINGS_DEFAULTS, unitSettingsSchema } from '../../app/composables/useSettings'
import { requestUnitTargets, UNIT_TARGET_TYPES } from '../../app/utils/unit-targets'
import backend from './unit-target-defaults.json'

// The list the settings page offers its rows from and the requests of the Explorer send their `unit_targets` from
// (GH-3878): the two cannot disagree, as the settings page is the only place that chooses.
describe('unit targets', () => {
  it('list the types the settings store, no more and no fewer', () => {
    expect(UNIT_TARGET_TYPES.map(({ type }) => type).sort()).toEqual(Object.keys(unitSettingsSchema.shape).sort())
  })

  it('start the settings from the default of each type, which is one of its units', () => {
    for (const { type, units, default: listed } of UNIT_TARGET_TYPES) {
      expect(units, type).toContain(listed)
      expect(SETTINGS_DEFAULTS.units[type as keyof typeof SETTINGS_DEFAULTS.units], type).toBe(listed)
    }
  })

  it('are the fixture that the backend\'s test holds to `UnitConverter.targets` (tests/model/test_app_unit_target_defaults.py)', () => {
    // regenerated from the catalogue when it changes: a default or a unit that is not in both fails one of the two tests
    expect(backend).toEqual(Object.fromEntries(UNIT_TARGET_TYPES.map(({ type, default: listed, units }) => [type, { default: listed, units }])))
  })

  it('list a unit once per type, and every type with a name on the settings page', () => {
    for (const { type, units, label } of UNIT_TARGET_TYPES) {
      expect(new Set(units).size, type).toBe(units.length)
      expect(label, type).toMatch(/^settings\.unit[A-Z]/)
    }
  })

  it('offer every unit the Explorer\'s own picker offered before, which the settings page now does', () => {
    const picker: Record<string, string[]> = {
      temperature: ['degree_celsius', 'degree_kelvin', 'degree_fahrenheit'],
      speed: ['meter_per_second', 'kilometer_per_hour', 'knots', 'beaufort'],
      pressure: ['pascal', 'hectopascal', 'kilopascal'],
      precipitation: ['millimeter', 'liter_per_square_meter'],
      precipitation_intensity: ['millimeter_per_hour', 'liter_per_square_meter_per_hour'],
      length_short: ['millimeter', 'centimeter', 'meter'],
      length_medium: ['millimeter', 'centimeter', 'meter', 'kilometer'],
      length_long: ['meter', 'kilometer', 'mile', 'nautical_mile'],
    }
    for (const [type, units] of Object.entries(picker))
      expect(UNIT_TARGET_TYPES.find(unitType => unitType.type === type)!.units, type).toEqual(expect.arrayContaining(units))
  })

  describe('as a request names them', () => {
    it('are one unit for every type, the settings\' choice', () => {
      expect(requestUnitTargets(SETTINGS_DEFAULTS.units)).toEqual(SETTINGS_DEFAULTS.units)
      expect(requestUnitTargets({ temperature: 'degree_kelvin' })).toMatchObject({ temperature: 'degree_kelvin', speed: 'meter_per_second' })
    })

    it('take the default for a type left out, blank, or set to a unit that is not on its list', () => {
      const targets = requestUnitTargets({ temperature: '', speed: 'furlong', pressure: undefined })
      expect(targets).toMatchObject({ temperature: 'degree_celsius', speed: 'meter_per_second', pressure: 'hectopascal' })
      expect(Object.keys(targets)).toHaveLength(UNIT_TARGET_TYPES.length)
    })
  })
})
