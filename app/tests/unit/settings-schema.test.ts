import { describe, expect, it } from 'vitest'
import { coerceSettings, SETTINGS_DEFAULTS, SETTINGS_VERSION, wdSettingsSchema } from '../../app/composables/useSettings'
import { DEFAULT_TOOL_ORDER } from '../../app/utils/tab-bar'

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

  describe('the tools of the phone bar (GH-3846)', () => {
    const withBar = (tabBar: unknown) => ({ ...structuredClone(SETTINGS_DEFAULTS), tabBar })

    it('is the default order, Forecast, Explorer, Stripes and History in the bar', () => {
      expect(SETTINGS_DEFAULTS.tabBar).toEqual(['forecast', 'explorer', 'stripes', 'history', 'map'])
      expect(SETTINGS_DEFAULTS.tabBar).toEqual([...DEFAULT_TOOL_ORDER])
    })

    it('reads what an earlier version stored, which has no choice, as the default with the rest kept', () => {
      const { tabBar: _tabBar, ...earlier } = structuredClone(SETTINGS_DEFAULTS)
      const stored = { ...earlier, friendlyLabels: false }
      expect(wdSettingsSchema.safeParse(stored).success).toBe(true)
      const result = coerceSettings(stored)
      expect(result.tabBar).toEqual(SETTINGS_DEFAULTS.tabBar)
      expect(result.friendlyLabels).toBe(false)
    })

    it('keeps a valid choice', () => {
      expect(coerceSettings(withBar(['map', 'history', 'explorer', 'forecast', 'stripes'])).tabBar).toEqual(['map', 'history', 'explorer', 'forecast', 'stripes'])
    })

    it('ignores a tool that does not exist, and fills a short list from the default, with no error', () => {
      expect(coerceSettings(withBar(['map', 'radar', 'forecast', 'explorer', 'stripes'])).tabBar).toEqual(['map', 'forecast', 'explorer', 'stripes', 'history'])
      expect(coerceSettings(withBar(['map'])).tabBar).toEqual(['map', 'forecast', 'explorer', 'stripes', 'history'])
      expect(coerceSettings(withBar([])).tabBar).toEqual(SETTINGS_DEFAULTS.tabBar)
    })

    it('repairs a list of the wrong kind to the default, and keeps the other fields it can read', () => {
      for (const bad of ['map', 3, null, { 0: 'map' }, [1, 2, 3], [['map']]]) {
        const result = coerceSettings({ ...withBar(bad), friendlyLabels: false })
        expect(result.tabBar, JSON.stringify(bad)).toEqual(SETTINGS_DEFAULTS.tabBar)
        expect(result.friendlyLabels).toBe(false)
      }
    })

    it('repairs it also in a payload of another version', () => {
      expect(coerceSettings({ ...withBar(['map', 'nope']), version: 99 }).tabBar).toEqual(['map', 'forecast', 'explorer', 'stripes', 'history'])
    })

    it('repairs a repeated tool, and the list never holds a tool twice', () => {
      const result = coerceSettings(withBar(['map', 'map', 'map', 'map', 'map'])).tabBar
      expect(result).toEqual(['map', 'forecast', 'explorer', 'stripes', 'history'])
      expect(new Set(result).size).toBe(result.length)
    })
  })

  it('the defaults satisfy the schema', () => {
    expect(wdSettingsSchema.safeParse(SETTINGS_DEFAULTS).success).toBe(true)
  })
})
