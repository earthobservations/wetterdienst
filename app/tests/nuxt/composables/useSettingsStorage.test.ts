import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { nextTick } from 'vue'

// What the settings do where the browser's storage fails (GH-3846, which keeps the phone bar's tools in them): a
// storage that refuses `window.localStorage` (blocked), a read or a write that throws (a full storage, a private
// window that refuses it), and a stored value that is nonsense. In every case the app has the defaults, and the choice
// can be made and holds for as long as the page does. `useSettings` keeps its store in the module, so each test
// loads a module of its own. Every test starts with the empty storage of tests/setup/storage.ts; the tests here put a
// storage of their own over it, one they can make fail, and give the shared one back afterwards.

const DEFAULT_BAR = ['forecast', 'explorer', 'stripes', 'history', 'map']

function memoryStorage() {
  const items = new Map<string, string>()
  return {
    items,
    getItem: (key: string) => items.get(key) ?? null,
    setItem: (key: string, value: string) => void items.set(key, String(value)),
    removeItem: (key: string) => void items.delete(key),
    clear: () => items.clear(),
    key: (index: number) => [...items.keys()][index] ?? null,
    get length() {
      return items.size
    },
  }
}

const original = Object.getOwnPropertyDescriptor(window, 'localStorage')

function install(descriptor: PropertyDescriptor) {
  Object.defineProperty(window, 'localStorage', { configurable: true, ...descriptor })
}

async function freshSettings() {
  vi.resetModules()
  return (await import('~/composables/useSettings')).useSettings()
}

let storage = memoryStorage()

beforeEach(() => {
  storage = memoryStorage()
  install({ value: storage })
})

afterEach(() => {
  if (original)
    Object.defineProperty(window, 'localStorage', original)
  else
    delete (window as any).localStorage
})

describe('the settings where the storage fails', () => {
  it('start with the defaults where the browser refuses the storage altogether (blocked), and keep a choice in memory', async () => {
    install({
      get() {
        throw new DOMException('The operation is insecure.', 'SecurityError')
      },
    })
    const { settings, reset } = await freshSettings()
    expect(settings.value.tabBar).toEqual(DEFAULT_BAR)
    expect(settings.value.friendlyLabels).toBe(true)
    settings.value.tabBar = ['map', 'forecast', 'explorer', 'stripes', 'history']
    await nextTick()
    expect(settings.value.tabBar[0]).toBe('map')
    reset()
    expect(settings.value.tabBar).toEqual(DEFAULT_BAR)
  })

  it('start with the defaults where a read throws', async () => {
    storage.getItem = () => {
      throw new DOMException('denied', 'SecurityError')
    }
    const { settings } = await freshSettings()
    expect(settings.value.tabBar).toEqual(DEFAULT_BAR)
  })

  it('keep a choice made where a write throws (a full storage), with no error', async () => {
    storage.setItem = () => {
      throw new DOMException('The quota has been exceeded.', 'QuotaExceededError')
    }
    const { settings } = await freshSettings()
    expect(() => {
      settings.value.tabBar = ['history', 'map', 'forecast', 'explorer', 'stripes']
    }).not.toThrow()
    await nextTick()
    expect(settings.value.tabBar).toEqual(['history', 'map', 'forecast', 'explorer', 'stripes'])
  })

  it.each([
    ['text that is no JSON', '{not json'],
    ['a string', '"forecast"'],
    ['a number', '42'],
    ['null', 'null'],
    ['a list', '[1,2]'],
  ])('start with the defaults for %s in the storage', async (_name, raw) => {
    storage.setItem('wd_settings', raw)
    const { settings } = await freshSettings()
    expect(settings.value.tabBar).toEqual(DEFAULT_BAR)
    expect(settings.value.convertUnits).toBe(true)
  })

  it('repair a choice that names a tool that is gone, or too few, and keep what else is stored', async () => {
    storage.setItem('wd_settings', JSON.stringify({ version: 1, friendlyLabels: false, tabBar: ['radar', 'map'] }))
    const { settings } = await freshSettings()
    expect(settings.value.tabBar).toEqual(['map', 'forecast', 'explorer', 'stripes', 'history'])
    expect(settings.value.friendlyLabels).toBe(false)
  })

  it('keep a choice in the storage, which the next load reads', async () => {
    const first = await freshSettings()
    first.settings.value.tabBar = ['stripes', 'history', 'explorer', 'forecast', 'map']
    await nextTick()
    expect(JSON.parse(storage.getItem('wd_settings')!).tabBar).toEqual(['stripes', 'history', 'explorer', 'forecast', 'map'])
    const next = await freshSettings()
    expect(next.settings.value.tabBar).toEqual(['stripes', 'history', 'explorer', 'forecast', 'map'])
  })
})
