import { afterEach, describe, expect, it, vi } from 'vitest'
import {
  readStationPickerMode,
  STATION_PICKER_STORAGE_KEY,
  STATION_PICKER_TOOLS,
  writeStationPickerMode,
} from '../../app/utils/station-picker-mode'

// The mode each tool's station picker is shown in, as the browser keeps it (GH-3877)

function memoryStorage(initial: Record<string, string> = {}) {
  const items = new Map(Object.entries(initial))
  vi.stubGlobal('localStorage', {
    getItem: (key: string) => items.get(key) ?? null,
    setItem: (key: string, value: string) => void items.set(key, String(value)),
  })
  return items
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('the remembered mode of a station picker', () => {
  it('is the list for every tool where nothing was kept', () => {
    memoryStorage()
    for (const tool of STATION_PICKER_TOOLS)
      expect(readStationPickerMode(tool)).toBe('list')
  })

  it('is kept for the tool it was chosen for, and no other', () => {
    const items = memoryStorage()
    writeStationPickerMode('stripes', 'map')
    expect(readStationPickerMode('stripes')).toBe('map')
    expect(readStationPickerMode('explorer')).toBe('list')

    writeStationPickerMode('explorer', 'map')
    writeStationPickerMode('stripes', 'list')
    expect(JSON.parse(items.get(STATION_PICKER_STORAGE_KEY)!)).toEqual({ explorer: 'map', stripes: 'list' })
  })

  it('leaves out what is stored that is no mode of a tool, and keeps the rest', () => {
    memoryStorage({ [STATION_PICKER_STORAGE_KEY]: JSON.stringify({ explorer: 'map', history: 'satellite', forecast: 1, elsewhere: 'map' }) })
    expect(readStationPickerMode('explorer')).toBe('map')
    expect(readStationPickerMode('history')).toBe('list')
    expect(readStationPickerMode('forecast')).toBe('list')
    writeStationPickerMode('stripes', 'map')
    // what was no mode is gone from the entry once it is written again
    expect(JSON.parse(localStorage.getItem(STATION_PICKER_STORAGE_KEY)!)).toEqual({ explorer: 'map', stripes: 'map' })
  })

  it.each(['', 'map', 'null', '[]', '"map"', '{'])('is the list where the entry is %j', (stored) => {
    memoryStorage({ [STATION_PICKER_STORAGE_KEY]: stored })
    expect(readStationPickerMode('explorer')).toBe('list')
  })

  it('is the list, and a write is no failure, where the storage is blocked', () => {
    Object.defineProperty(globalThis, 'localStorage', {
      configurable: true,
      get() {
        throw new DOMException('The operation is insecure.', 'SecurityError')
      },
    })
    expect(readStationPickerMode('explorer')).toBe('list')
    expect(() => writeStationPickerMode('explorer', 'map')).not.toThrow()
  })

  it('is the list, and a write is no failure, where the storage throws on a read and a write', () => {
    const refuse = () => {
      throw new DOMException('The quota has been exceeded.', 'QuotaExceededError')
    }
    vi.stubGlobal('localStorage', { getItem: refuse, setItem: refuse })
    expect(readStationPickerMode('explorer')).toBe('list')
    expect(() => writeStationPickerMode('explorer', 'map')).not.toThrow()
  })
})
