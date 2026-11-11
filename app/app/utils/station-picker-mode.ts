/**
 * How the station picker is shown per tool, "list" (the search) or "map", remembered in the browser as a
 * view preference (GH-3877): one entry of localStorage, `wd-station-picker`, holding the mode of each tool.
 *
 * A browser that refuses its storage (blocked, a private window, a full quota) is no failure: the mode is
 * then the list, and a change is kept for the visit only, by the caller.
 */

export const STATION_PICKER_MODES = ['list', 'map'] as const
export type StationPickerMode = typeof STATION_PICKER_MODES[number]

/** The tools that have a station picker, each with a mode of its own */
export const STATION_PICKER_TOOLS = ['explorer', 'history', 'forecast', 'stripes'] as const
export type StationPickerTool = typeof STATION_PICKER_TOOLS[number]

export const STATION_PICKER_STORAGE_KEY = 'wd-station-picker'

export const DEFAULT_STATION_PICKER_MODE: StationPickerMode = 'list'

function isMode(value: unknown): value is StationPickerMode {
  return value === 'list' || value === 'map'
}

/** What the storage holds, as the modes it names: anything else (not JSON, not an object, an unknown mode) is left out */
function readAll(): Partial<Record<StationPickerTool, StationPickerMode>> {
  try {
    const raw = localStorage.getItem(STATION_PICKER_STORAGE_KEY)
    const parsed: unknown = raw ? JSON.parse(raw) : null
    if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed))
      return {}
    const modes: Partial<Record<StationPickerTool, StationPickerMode>> = {}
    for (const tool of STATION_PICKER_TOOLS) {
      const value = (parsed as Record<string, unknown>)[tool]
      if (isMode(value))
        modes[tool] = value
    }
    return modes
  }
  catch {
    return {}
  }
}

/**
 * The mode remembered for a tool.
 *
 * @param tool - The tool whose picker it is
 * @returns The remembered mode, the list where none is or the storage cannot be read
 */
export function readStationPickerMode(tool: StationPickerTool): StationPickerMode {
  return readAll()[tool] ?? DEFAULT_STATION_PICKER_MODE
}

/**
 * Remembers the mode of a tool; the other tools' modes are left as they are.
 *
 * @param tool - The tool whose picker it is
 * @param mode - The mode to remember
 */
export function writeStationPickerMode(tool: StationPickerTool, mode: StationPickerMode): void {
  try {
    localStorage.setItem(STATION_PICKER_STORAGE_KEY, JSON.stringify({ ...readAll(), [tool]: mode }))
  }
  catch {
    // the storage refuses: the mode is kept for this visit by the picker, which is all that can be done
  }
}
