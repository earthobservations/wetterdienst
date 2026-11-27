import { describe, expect, it } from 'vitest'
import { coerceSettings, SEARCH_STATIONS_DEFAULTS, seedFromServer, SETTINGS_DEFAULTS, SETTINGS_VERSION, settingsFromServer, wdSettingsSchema } from '../../app/composables/useSettings'
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

  describe('the lists of stations the search looks in by name (GH-3790)', () => {
    it('are the forecast\'s points and GHCN daily on and DWD\'s measuring stations off, which the defaults and an empty blob say', () => {
      expect(SEARCH_STATIONS_DEFAULTS).toEqual({ forecast: true, measured: false, ghcn: true })
      expect(SETTINGS_DEFAULTS.searchStations).toEqual(SEARCH_STATIONS_DEFAULTS)
      expect(coerceSettings({}).searchStations).toEqual(SEARCH_STATIONS_DEFAULTS)
    })

    it('are read from what an earlier version stored, which has none, with the other settings kept', () => {
      const { searchStations: _none, ...earlier } = structuredClone(SETTINGS_DEFAULTS)
      const result = coerceSettings({ ...earlier, friendlyLabels: false })
      expect(result.searchStations).toEqual(SEARCH_STATIONS_DEFAULTS)
      expect(result.friendlyLabels).toBe(false)
    })

    it('keep a choice, and a field that is no choice is the default for that list alone', () => {
      expect(coerceSettings({ ...structuredClone(SETTINGS_DEFAULTS), searchStations: { forecast: false, measured: true, ghcn: false } }).searchStations).toEqual({ forecast: false, measured: true, ghcn: false })
      expect(coerceSettings({ ...structuredClone(SETTINGS_DEFAULTS), searchStations: { forecast: 'no', measured: true } }).searchStations).toEqual(SEARCH_STATIONS_DEFAULTS)
      // an outdated version is salvaged field by field
      expect(coerceSettings({ version: 1, searchStations: { forecast: false, measured: false, ghcn: true } }).searchStations).toEqual({ forecast: false, measured: false, ghcn: true })
    })
  })

  describe('the stripes\' time series and trend line, which are no options any more (GH-4170)', () => {
    // what a browser that visited before the change holds: the two choices beside the four that stay
    const stored = (version: number) => ({
      ...structuredClone(SETTINGS_DEFAULTS),
      version,
      friendlyLabels: false,
      stripes: { showTitle: false, showYears: true, showSource: false, showDataAvailability: true, showTimeseries: true, showTrendline: true },
    })

    it('has neither choice in the defaults', () => {
      expect(SETTINGS_DEFAULTS.stripes).toEqual({ showTitle: true, showYears: true, showSource: true, showDataAvailability: true })
    })

    it.each([SETTINGS_VERSION, 1, 99])('reads settings of version %i that still hold them, drops the two and keeps every other choice', (version) => {
      const result = coerceSettings(stored(version))
      expect(result.stripes).toEqual({ showTitle: false, showYears: true, showSource: false, showDataAvailability: true })
      expect(Object.keys(result.stripes)).not.toContain('showTimeseries')
      expect(Object.keys(result.stripes)).not.toContain('showTrendline')
      expect(result.friendlyLabels).toBe(false)
      expect(result.version).toBe(SETTINGS_VERSION)
    })

    it('does not reset the stripes\' other choices for the two it no longer has', () => {
      expect(coerceSettings(stored(SETTINGS_VERSION)).stripes.showTitle).toBe(false)
      expect(wdSettingsSchema.safeParse(stored(SETTINGS_VERSION)).success).toBe(true)
    })
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

  describe('the units the requests send (GH-3878)', () => {
    it('are the backend\'s own default for the two types where the settings held another', () => {
      expect(SETTINGS_DEFAULTS.units.power_per_area).toBe('watt_per_square_meter')
      expect(SETTINGS_DEFAULTS.units.conductivity).toBe('microsiemens_per_centimeter')
    })

    it('are made the backend\'s default again for a settings of version 1 that holds the old default', () => {
      const stored = {
        ...structuredClone(SETTINGS_DEFAULTS),
        version: 1,
        units: { ...SETTINGS_DEFAULTS.units, power_per_area: 'watt_per_square_centimeter', conductivity: 'siemens_per_meter', temperature: 'degree_fahrenheit' },
      }
      const result = coerceSettings(stored)
      expect(result.version).toBe(SETTINGS_VERSION)
      expect(result.units.power_per_area).toBe('watt_per_square_meter')
      expect(result.units.conductivity).toBe('microsiemens_per_centimeter')
      // what else was chosen is kept
      expect(result.units.temperature).toBe('degree_fahrenheit')
    })

    it('are made the backend\'s default again for the two types GH-3753 changed without a bump (fraction, energy per area)', () => {
      // a settings of version 1 written before 2026-11-02 holds what the defaults were then
      const stored = {
        ...structuredClone(SETTINGS_DEFAULTS),
        version: 1,
        units: { ...SETTINGS_DEFAULTS.units, fraction: 'decimal', energy_per_area: 'joule_per_square_centimeter' },
      }
      const result = coerceSettings(stored)
      expect(result.units.fraction).toBe('percent')
      expect(result.units.energy_per_area).toBe('megajoule_per_square_meter')
    })

    it('keeps another unit of fraction and energy per area in a settings of version 1, and these in version 2', () => {
      const chosen = { fraction: 'one_eighth', energy_per_area: 'kilojoule_per_square_meter' }
      expect(coerceSettings({ ...structuredClone(SETTINGS_DEFAULTS), version: 1, units: { ...SETTINGS_DEFAULTS.units, ...chosen } }).units)
        .toMatchObject(chosen)
      const decimal = { ...structuredClone(SETTINGS_DEFAULTS), units: { ...SETTINGS_DEFAULTS.units, fraction: 'decimal' } }
      expect(coerceSettings(decimal).units.fraction).toBe('decimal')
    })

    it('keeps a choice of another unit of those two in a settings of version 1', () => {
      const stored = {
        ...structuredClone(SETTINGS_DEFAULTS),
        version: 1,
        units: { ...SETTINGS_DEFAULTS.units, power_per_area: 'kilowatt_per_square_meter', conductivity: 'microsiemens_per_meter' },
      }
      expect(coerceSettings(stored).units).toMatchObject({ power_per_area: 'kilowatt_per_square_meter', conductivity: 'microsiemens_per_meter' })
    })

    it('keeps W/cm² and S/m where a settings of the current version holds them: they are a choice by now', () => {
      const stored = {
        ...structuredClone(SETTINGS_DEFAULTS),
        units: { ...SETTINGS_DEFAULTS.units, power_per_area: 'watt_per_square_centimeter', conductivity: 'siemens_per_meter' },
      }
      expect(coerceSettings(stored)).toEqual(stored)
    })
  })

  describe('the mark of a start from the server (GH-3878)', () => {
    it('is true for settings stored before it, which are the visitor\'s already, and kept where stored', () => {
      const { seededFromServer: _seeded, ...earlier } = structuredClone(SETTINGS_DEFAULTS)
      expect(coerceSettings(earlier).seededFromServer).toBe(true)
      expect(coerceSettings({ ...earlier, version: 1 }).seededFromServer).toBe(true)
      expect(coerceSettings({ ...structuredClone(SETTINGS_DEFAULTS), seededFromServer: false }).seededFromServer).toBe(false)
      expect(coerceSettings({ ...structuredClone(SETTINGS_DEFAULTS), seededFromServer: 'no' }).seededFromServer).toBe(true)
    })
  })

  describe('the settings a server reports (GH-3878)', () => {
    const server = { values: { humanize: false, convert_units: false, unit_targets: { temperature: 'degree_fahrenheit', speed: 'furlong', duration: 'minute', nothing: 'x' } } }

    it('are the names, the conversion and the units on the list of their type', () => {
      expect(settingsFromServer(server)).toEqual({
        friendlyLabels: false,
        convertUnits: false,
        units: { temperature: 'degree_fahrenheit', duration: 'minute' },
      })
    })

    it.each([null, undefined, 'nope', 3, {}, { values: null }, { values: { humanize: 'yes', unit_targets: 'x' } }])('are none where the answer is %j', (answer) => {
      expect(settingsFromServer(answer)).toEqual({ units: {} })
    })

    it('are laid over settings that still hold the defaults, and not over a choice', () => {
      const current = { ...structuredClone(SETTINGS_DEFAULTS), friendlyLabels: false }
      current.units.speed = 'knots'
      const result = seedFromServer({ ...current, convertUnits: true }, { values: { humanize: true, convert_units: true, unit_targets: { temperature: 'degree_fahrenheit', speed: 'beaufort' } } })
      // humanize: the visitor's (off, the default being on) stays; temperature was the default; speed was chosen
      expect(result.friendlyLabels).toBe(false)
      expect(result.units).toMatchObject({ temperature: 'degree_fahrenheit', speed: 'knots' })
    })
  })

  describe('the tools of the phone bar (GH-3846)', () => {
    const withBar = (tabBar: unknown) => ({ ...structuredClone(SETTINGS_DEFAULTS), tabBar })

    it('is the default order, Forecast, Explorer, Stripes and Radar in the bar', () => {
      expect(SETTINGS_DEFAULTS.tabBar).toEqual(['forecast', 'explorer', 'stripes', 'radar', 'history', 'map', 'kostra'])
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
      expect(coerceSettings(withBar(['map', 'history', 'radar', 'explorer', 'forecast', 'stripes', 'kostra'])).tabBar).toEqual(['map', 'history', 'radar', 'explorer', 'forecast', 'stripes', 'kostra'])
    })

    it('puts a tool that a choice saved before it existed does not name below the line: the Map of GH-3788', () => {
      expect(coerceSettings(withBar(['history', 'radar', 'explorer', 'forecast', 'stripes'])).tabBar).toEqual(['history', 'radar', 'explorer', 'forecast', 'stripes', 'map', 'kostra'])
    })

    it('ignores a tool that does not exist, and fills a short list from the default, with no error', () => {
      expect(coerceSettings(withBar(['history', 'satellite', 'forecast', 'explorer', 'stripes'])).tabBar).toEqual(['history', 'forecast', 'explorer', 'stripes', 'radar', 'map', 'kostra'])
      expect(coerceSettings(withBar(['history'])).tabBar).toEqual(['history', 'forecast', 'explorer', 'stripes', 'radar', 'map', 'kostra'])
      expect(coerceSettings(withBar([])).tabBar).toEqual(SETTINGS_DEFAULTS.tabBar)
    })

    it('repairs a list of the wrong kind to the default, and keeps the other fields it can read', () => {
      for (const bad of ['history', 3, null, { 0: 'history' }, [1, 2, 3], [['history']]]) {
        const result = coerceSettings({ ...withBar(bad), friendlyLabels: false })
        expect(result.tabBar, JSON.stringify(bad)).toEqual(SETTINGS_DEFAULTS.tabBar)
        expect(result.friendlyLabels).toBe(false)
      }
    })

    it('repairs it also in a payload of another version', () => {
      expect(coerceSettings({ ...withBar(['history', 'nope']), version: 99 }).tabBar).toEqual(['history', 'forecast', 'explorer', 'stripes', 'radar', 'map', 'kostra'])
    })

    it('repairs a repeated tool, and the list never holds a tool twice', () => {
      const result = coerceSettings(withBar(['history', 'history', 'history', 'history', 'history'])).tabBar
      expect(result).toEqual(['history', 'forecast', 'explorer', 'stripes', 'radar', 'map', 'kostra'])
      expect(new Set(result).size).toBe(result.length)
    })
  })

  it('the defaults satisfy the schema', () => {
    expect(wdSettingsSchema.safeParse(SETTINGS_DEFAULTS).success).toBe(true)
  })
})
