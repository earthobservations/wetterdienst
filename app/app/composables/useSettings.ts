import type { RemovableRef } from '@vueuse/core'
import { useStorage } from '@vueuse/core'
import { z } from 'zod'
import { DEFAULT_TOOL_ORDER, normalizeToolOrder } from '../utils/tab-bar'
import { UNIT_TARGET_TYPES } from '../utils/unit-targets'

// Zod compiles a faster parser of an object with `new Function`, and finds out whether it may by trying it. The
// app's Content Security Policy has no `'unsafe-eval'` (GH-3094), so the try is a violation that the browser
// reports, though Zod catches it and parses without. The settings are a few fields: no parser to speed up.
z.config({ jitless: true })

/**
 * Persistent, app-wide user settings.
 *
 * Backed by localStorage (the app runs as an SPA with `ssr: false`, so there is
 * no hydration concern). A zod schema validates and repairs whatever was loaded:
 * unknown/legacy or corrupted data is coerced back onto the current defaults
 * field by field, and a version bump forces a clean migration.
 *
 * Language lives in the i18n cookie (so browser detection keeps working) and is
 * surfaced through the settings UI rather than stored here twice. Theme is owned
 * by the color-mode module and likewise only surfaced in the UI.
 */

export const SETTINGS_VERSION = 2

// The unit choices the settings page stores, for each type of `UNIT_TARGET_TYPES`: what the requests of the Explorer
// send as `unit_targets` (GH-3878). Each default is the backend's own for the type: the catalogue's are held to the
// settings' by tests/unit/unit-targets.test.ts and to `UnitConverter.targets` by tests/model/test_app_unit_target_defaults.py.
export const unitSettingsSchema = z.object({
  temperature: z.string(),
  precipitation: z.string(),
  precipitation_intensity: z.string(),
  pressure: z.string(),
  speed: z.string(),
  angle: z.string(),
  fraction: z.string(),
  length_short: z.string(),
  length_medium: z.string(),
  length_long: z.string(),
  energy_per_area: z.string(),
  power_per_area: z.string(),
  time: z.string(),
  // a default, so that what an earlier version stored, which has no such field, is read rather than dropped
  duration: z.string().default('hour'),
  degree_day: z.string(),
  concentration: z.string(),
  conductivity: z.string(),
  volume_per_time: z.string(),
})
export type UnitSettings = z.infer<typeof unitSettingsSchema>

export const stripesDisplaySchema = z.object({
  showTitle: z.boolean(),
  showYears: z.boolean(),
  showSource: z.boolean(),
  showDataAvailability: z.boolean(),
  showTimeseries: z.boolean(),
  showTrendline: z.boolean(),
})
export type StripesDisplaySettings = z.infer<typeof stripesDisplaySchema>

export const wdSettingsSchema = z.object({
  version: z.number(),
  /** Show friendly parameter names (e.g. "Air temperature") instead of raw ids. */
  friendlyLabels: z.boolean(),
  /** Convert raw values to the chosen target units. */
  convertUnits: z.boolean(),
  units: unitSettingsSchema,
  stripes: stripesDisplaySchema,
  /**
   * The keys of all the tools in the order of the phone's tab bar, of which the first four are in the bar and the rest
   * only in the Menu (GH-3846). A default, so that what an earlier version stored, which has none, is read; whatever
   * is stored is made a valid order by `normalizeToolOrder` where it is read and here.
   */
  tabBar: z.array(z.string()).default([...DEFAULT_TOOL_ORDER]),
})
export type WdSettings = z.infer<typeof wdSettingsSchema>

export const SETTINGS_DEFAULTS: WdSettings = {
  version: SETTINGS_VERSION,
  friendlyLabels: true,
  convertUnits: true,
  units: {
    temperature: 'degree_celsius',
    precipitation: 'millimeter',
    precipitation_intensity: 'millimeter_per_hour',
    pressure: 'hectopascal',
    speed: 'meter_per_second',
    angle: 'degree',
    fraction: 'percent',
    length_short: 'centimeter',
    length_medium: 'meter',
    length_long: 'kilometer',
    energy_per_area: 'megajoule_per_square_meter',
    power_per_area: 'watt_per_square_meter',
    time: 'second',
    duration: 'hour',
    degree_day: 'degree_celsius_day',
    concentration: 'milligram_per_liter',
    conductivity: 'microsiemens_per_centimeter',
    volume_per_time: 'cubic_meter_per_second',
  },
  stripes: {
    showTitle: true,
    showYears: true,
    showSource: true,
    showDataAvailability: true,
    showTimeseries: false,
    showTrendline: false,
  },
  tabBar: [...DEFAULT_TOOL_ORDER],
}

const STORAGE_KEY = 'wd_settings'

// What settings of version 1 held for four types: a default that is not the backend's, or one that was and no longer
// is. Version 1 was never bumped when the defaults changed, so a blob written before GH-3753 (2026-11-02) holds
// `fraction: decimal` and `energy_per_area: joule_per_square_centimeter`, and one written before GH-3878 holds the
// W/cm² and S/m the page started with. Nobody could tell one from a choice, and nothing was converted by it. Now that
// a request names the unit, a stored one of these is the backend's default for the type again, so that a visitor who
// never opened the page gets what the Explorer sent before; one who chose it on the page chooses again.
const VERSION_1_DEFAULTS = {
  fraction: 'decimal',
  energy_per_area: 'joule_per_square_centimeter',
  power_per_area: 'watt_per_square_centimeter',
  conductivity: 'siemens_per_meter',
} as const

/**
 * Validate and repair a loaded settings blob. A fully valid, current-version
 * payload is returned as-is; anything else is rebuilt from defaults while
 * salvaging each individually valid field.
 */
export function coerceSettings(raw: unknown): WdSettings {
  const parsed = wdSettingsSchema.safeParse(raw)
  if (parsed.success && parsed.data.version === SETTINGS_VERSION) {
    return { ...parsed.data, tabBar: normalizeToolOrder(parsed.data.tabBar) }
  }

  const result = structuredClone(SETTINGS_DEFAULTS)
  if (raw && typeof raw === 'object') {
    const r = raw as Record<string, unknown>
    if (typeof r.friendlyLabels === 'boolean')
      result.friendlyLabels = r.friendlyLabels
    if (typeof r.convertUnits === 'boolean')
      result.convertUnits = r.convertUnits
    const units = unitSettingsSchema.safeParse(r.units)
    if (units.success) {
      result.units = units.data
      if (r.version === 1) {
        for (const [type, old] of Object.entries(VERSION_1_DEFAULTS)) {
          if (result.units[type as keyof UnitSettings] === old)
            result.units[type as keyof UnitSettings] = SETTINGS_DEFAULTS.units[type as keyof UnitSettings]
        }
      }
    }
    const stripes = stripesDisplaySchema.safeParse(r.stripes)
    if (stripes.success)
      result.stripes = stripes.data
    result.tabBar = normalizeToolOrder(r.tabBar)
  }
  return result
}

/**
 * The settings a server reports (`GET /api/settings`, its `values` block) that the app settings hold: whether the names
 * are readable (`humanize`), whether the values are converted (`convert_units`) and the unit of each type the
 * settings page lists, for a unit that is on the list of its type. Anything else the answer holds, or holds wrongly, is
 * left out.
 */
export function settingsFromServer(server: unknown): Pick<Partial<WdSettings>, 'friendlyLabels' | 'convertUnits'> & { units: Partial<UnitSettings> } {
  const values = (server as { values?: Record<string, unknown> } | null)?.values
  const seeded: ReturnType<typeof settingsFromServer> = { units: {} }
  if (!values || typeof values !== 'object')
    return seeded
  if (typeof values.humanize === 'boolean')
    seeded.friendlyLabels = values.humanize
  if (typeof values.convert_units === 'boolean')
    seeded.convertUnits = values.convert_units
  const targets = values.unit_targets
  if (targets && typeof targets === 'object') {
    for (const { type, units } of UNIT_TARGET_TYPES) {
      const unit = (targets as Record<string, unknown>)[type]
      if (typeof unit === 'string' && units.includes(unit))
        seeded.units[type as keyof UnitSettings] = unit
    }
  }
  return seeded
}

/**
 * `current` with the server's settings laid over it, each only where `current` still holds the app's default: what the
 * visitor chose while the answer was on its way stays.
 */
export function seedFromServer(current: WdSettings, server: unknown): WdSettings {
  const seeded = settingsFromServer(server)
  // `current` may be the store's reactive object, which `structuredClone` refuses: the settings are plain JSON
  const result: WdSettings = JSON.parse(JSON.stringify(current))
  if (seeded.friendlyLabels !== undefined && current.friendlyLabels === SETTINGS_DEFAULTS.friendlyLabels)
    result.friendlyLabels = seeded.friendlyLabels
  if (seeded.convertUnits !== undefined && current.convertUnits === SETTINGS_DEFAULTS.convertUnits)
    result.convertUnits = seeded.convertUnits
  for (const [type, unit] of Object.entries(seeded.units)) {
    const key = type as keyof UnitSettings
    if (current.units[key] === SETTINGS_DEFAULTS.units[key])
      result.units[key] = unit
  }
  return result
}

/** Whether the browser holds no settings of the app yet: a first visit. A storage that cannot be read holds none. */
function holdsNoSettings(): boolean {
  try {
    return window.localStorage.getItem(STORAGE_KEY) === null
  }
  catch {
    return true
  }
}

let store: RemovableRef<WdSettings> | null = null

export function useSettings() {
  if (!store) {
    // asked before `useStorage` writes the defaults under the key
    const firstVisit = holdsNoSettings()
    // The storage is left to `useStorage`, which looks `window.localStorage` up itself, in a try: a browser that refuses
    // the property (its storage blocked) gets settings kept in memory for the visit. `useLocalStorage` reads the property
    // before it, outside any try, and the whole app fails to start. A read or a write that fails later (a full storage,
    // a private window that refuses it) is caught by the library as well; nothing a visitor can do about it, so no error.
    store = useStorage<WdSettings>(STORAGE_KEY, structuredClone(SETTINGS_DEFAULTS), undefined, {
      mergeDefaults: true,
      onError: () => {},
    })
    // Repair legacy/corrupted payloads against the schema on first read.
    store.value = coerceSettings(store.value)
    // A first visit starts from what the server reports (GH-3878), so that an instance that converts to Fahrenheit
    // shows its readers Fahrenheit. The page is not held for it: until the answer comes, and where it does not, the app's
    // defaults are the settings, and what the visitor chose meanwhile is kept. From the next visit on, the stored
    // settings are the visitor's.
    if (firstVisit)
      void seedStoreFromServer(store)
  }

  function reset() {
    store!.value = structuredClone(SETTINGS_DEFAULTS)
  }

  return { settings: store, reset }
}

async function seedStoreFromServer(target: RemovableRef<WdSettings>) {
  try {
    const server = await useServerSettings()
    if (server)
      target.value = seedFromServer(target.value, server)
  }
  catch {
    // no answer, or no app to ask it in: the app's defaults stay
  }
}
