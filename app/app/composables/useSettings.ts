import type { RemovableRef } from '@vueuse/core'
import { z } from 'zod'

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

export const SETTINGS_VERSION = 1

// Target units for every convertible unit type the backend UnitConverter knows
// (types with more than one possible unit). Single-unit types are omitted.
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
    fraction: 'decimal',
    length_short: 'centimeter',
    length_medium: 'meter',
    length_long: 'kilometer',
    energy_per_area: 'joule_per_square_centimeter',
    power_per_area: 'watt_per_square_centimeter',
    time: 'second',
    degree_day: 'degree_celsius_day',
    concentration: 'milligram_per_liter',
    conductivity: 'siemens_per_meter',
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
}

const STORAGE_KEY = 'wd_settings'

/**
 * Validate and repair a loaded settings blob. A fully valid, current-version
 * payload is returned as-is; anything else is rebuilt from defaults while
 * salvaging each individually valid field.
 */
export function coerceSettings(raw: unknown): WdSettings {
  const parsed = wdSettingsSchema.safeParse(raw)
  if (parsed.success && parsed.data.version === SETTINGS_VERSION) {
    return parsed.data
  }

  const result = structuredClone(SETTINGS_DEFAULTS)
  if (raw && typeof raw === 'object') {
    const r = raw as Record<string, unknown>
    if (typeof r.friendlyLabels === 'boolean')
      result.friendlyLabels = r.friendlyLabels
    if (typeof r.convertUnits === 'boolean')
      result.convertUnits = r.convertUnits
    const units = unitSettingsSchema.safeParse(r.units)
    if (units.success)
      result.units = units.data
    const stripes = stripesDisplaySchema.safeParse(r.stripes)
    if (stripes.success)
      result.stripes = stripes.data
  }
  return result
}

let store: RemovableRef<WdSettings> | null = null

export function useSettings() {
  if (!store) {
    store = useLocalStorage<WdSettings>(STORAGE_KEY, structuredClone(SETTINGS_DEFAULTS), {
      mergeDefaults: true,
    })
    // Repair legacy/corrupted payloads against the schema on first read.
    store.value = coerceSettings(store.value)
  }

  function reset() {
    store!.value = structuredClone(SETTINGS_DEFAULTS)
  }

  return { settings: store, reset }
}
