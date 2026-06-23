import type { RemovableRef } from '@vueuse/core'

/**
 * Persistent, app-wide user settings.
 *
 * Backed by localStorage (the app runs as an SPA with `ssr: false`, so there is
 * no hydration concern). A versioned schema lets us evolve the shape safely:
 * unknown/legacy data is merged onto the current defaults on read.
 *
 * Language lives in the i18n cookie (so browser detection keeps working) and is
 * surfaced through the settings UI rather than stored here twice. Theme is owned
 * by the color-mode module and likewise only surfaced in the UI.
 */

export const SETTINGS_VERSION = 1

export type ExplorerMode = 'simple' | 'expert'

export interface StripesDisplaySettings {
  showTitle: boolean
  showYears: boolean
  showSource: boolean
  showDataAvailability: boolean
  showTimeseries: boolean
  showTrendline: boolean
}

export interface UnitSettings {
  temperature: string
  speed: string
  pressure: string
  precipitation: string
}

export interface WdSettings {
  version: number
  /** Show friendly parameter names (e.g. "Air temperature") instead of raw ids. */
  friendlyLabels: boolean
  /** Default mode the Explorer opens in. */
  explorerMode: ExplorerMode
  /** Convert raw values to the chosen target units. */
  convertUnits: boolean
  units: UnitSettings
  stripes: StripesDisplaySettings
}

export const SETTINGS_DEFAULTS: WdSettings = {
  version: SETTINGS_VERSION,
  friendlyLabels: true,
  explorerMode: 'simple',
  convertUnits: true,
  units: {
    temperature: 'degree_celsius',
    speed: 'meter_per_second',
    pressure: 'hectopascal',
    precipitation: 'millimeter',
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

let store: RemovableRef<WdSettings> | null = null

export function useSettings() {
  if (!store) {
    store = useLocalStorage<WdSettings>(STORAGE_KEY, structuredClone(SETTINGS_DEFAULTS), {
      mergeDefaults: true,
    })

    // Migrate older payloads: keep what is still valid, fill gaps from defaults.
    if (store.value.version !== SETTINGS_VERSION) {
      store.value = {
        ...structuredClone(SETTINGS_DEFAULTS),
        ...store.value,
        units: { ...SETTINGS_DEFAULTS.units, ...store.value.units },
        stripes: { ...SETTINGS_DEFAULTS.stripes, ...store.value.stripes },
        version: SETTINGS_VERSION,
      }
    }
  }

  function reset() {
    store!.value = structuredClone(SETTINGS_DEFAULTS)
  }

  return { settings: store, reset }
}
