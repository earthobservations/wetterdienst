import { describe, expect, it } from 'vitest'
import { coerceSettings, SETTINGS_DEFAULTS, SETTINGS_VERSION, wdSettingsSchema } from '../../app/composables/useSettings'

describe('settings schema', () => {
  it('accepts a valid current-version payload unchanged', () => {
    const valid = structuredClone(SETTINGS_DEFAULTS)
    valid.convertUnits = false
    valid.friendlyLabels = false
    expect(coerceSettings(valid)).toEqual(valid)
  })

  it('falls back to defaults for non-object input', () => {
    expect(coerceSettings(null)).toEqual(SETTINGS_DEFAULTS)
    expect(coerceSettings('nonsense')).toEqual(SETTINGS_DEFAULTS)
    expect(coerceSettings(undefined)).toEqual(SETTINGS_DEFAULTS)
  })

  it('returns defaults for an empty object', () => {
    expect(coerceSettings({})).toEqual(SETTINGS_DEFAULTS)
  })

  it('migrates an outdated version while salvaging valid fields', () => {
    const legacy = {
      ...structuredClone(SETTINGS_DEFAULTS),
      version: 99,
      convertUnits: false,
      friendlyLabels: false,
    }
    const result = coerceSettings(legacy)
    expect(result.version).toBe(SETTINGS_VERSION)
    expect(result.convertUnits).toBe(false)
    expect(result.friendlyLabels).toBe(false)
  })

  it('drops invalid individual fields back to defaults', () => {
    const corrupted = {
      ...structuredClone(SETTINGS_DEFAULTS),
      version: 2,
      friendlyLabels: 'nope', // not a boolean
      units: 'not-an-object',
    }
    const result = coerceSettings(corrupted)
    expect(result.friendlyLabels).toBe(SETTINGS_DEFAULTS.friendlyLabels)
    expect(result.units).toEqual(SETTINGS_DEFAULTS.units)
  })

  it('reads what an earlier version stored, which has no duration unit, with the others kept', () => {
    const { duration: _duration, ...units } = structuredClone(SETTINGS_DEFAULTS.units)
    const stored = { ...structuredClone(SETTINGS_DEFAULTS), units: { ...units, temperature: 'degree_fahrenheit' } }
    const result = coerceSettings(stored)
    expect(result.units.temperature).toBe('degree_fahrenheit')
    expect(result.units.duration).toBe('hour')
  })

  it('names the backend\'s default of the unit types whose default changed (GH-3702)', () => {
    // UnitConverter().targets: sunshine and the like in hours, a sum of radiation in MJ/m², a share in percent
    expect(SETTINGS_DEFAULTS.units).toMatchObject({
      duration: 'hour',
      time: 'second',
      energy_per_area: 'megajoule_per_square_meter',
      fraction: 'percent',
    })
  })

  it('the defaults satisfy the schema', () => {
    expect(wdSettingsSchema.safeParse(SETTINGS_DEFAULTS).success).toBe(true)
  })
})
