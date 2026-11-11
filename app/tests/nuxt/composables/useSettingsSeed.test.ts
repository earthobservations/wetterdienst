import { registerEndpoint } from '@nuxt/test-utils/runtime'
import { createError } from 'h3'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { nextTick } from 'vue'
import { clearNuxtState, useServerSettings } from '#imports'
import { SETTINGS_DEFAULTS } from '~/composables/useSettings'

// A first visit starts from the server's settings (`GET /api/settings`, GH-3878); from then on the stored settings are
// the visitor's. `useSettings` keeps its store in the module, so each test loads a module of its own, and gives the
// page a storage of its own (the test environment's has no file to keep it in).

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
let storage = memoryStorage()
let answer: () => unknown | Promise<unknown>
let asked = 0
let remove: () => void

beforeEach(() => {
  storage = memoryStorage()
  Object.defineProperty(window, 'localStorage', { configurable: true, value: storage })
  clearNuxtState('server-settings')
  asked = 0
  remove = registerEndpoint('/api/settings', () => {
    asked += 1
    return answer()
  })
})

afterEach(() => {
  remove()
  if (original)
    Object.defineProperty(window, 'localStorage', original)
  else
    delete (window as any).localStorage
})

function FAHRENHEIT() {
  return {
    values: { humanize: false, convert_units: true, unit_targets: { temperature: 'degree_fahrenheit', speed: 'knots', length_long: 'furlong' } },
  }
}

async function visit() {
  vi.resetModules()
  const { useSettings } = await import('~/composables/useSettings')
  return useSettings()
}

const stored = () => JSON.parse(storage.getItem('wd_settings')!)

describe('the settings of a first visit', () => {
  it('start from the server\'s settings, and are stored', async () => {
    answer = FAHRENHEIT
    const { settings } = await visit()
    await useServerSettings()
    await vi.waitFor(() => expect(settings.value.units.temperature).toBe('degree_fahrenheit'))
    expect(settings.value).toMatchObject({ friendlyLabels: false, convertUnits: true })
    expect(settings.value.units).toMatchObject({ speed: 'knots', pressure: 'hectopascal' })
    // a unit that is not on the list of its type is not taken
    expect(settings.value.units.length_long).toBe('kilometer')
    await nextTick()
    expect(stored().units.temperature).toBe('degree_fahrenheit')
  })

  it('hold the visitor\'s own from the second visit on, whatever the server says then', async () => {
    answer = FAHRENHEIT
    const first = await visit()
    await vi.waitFor(() => expect(first.settings.value.units.temperature).toBe('degree_fahrenheit'))
    await nextTick()
    expect(asked).toBe(1)

    clearNuxtState('server-settings')
    answer = () => ({ values: { humanize: true, convert_units: false, unit_targets: { temperature: 'degree_kelvin' } } })
    const second = await visit()
    await nextTick()
    expect(second.settings.value.units.temperature).toBe('degree_fahrenheit')
    expect(second.settings.value.convertUnits).toBe(true)
    expect(asked).toBe(1)
  })

  it('are the app\'s defaults where the server fails, with no error', async () => {
    answer = () => {
      throw createError({ statusCode: 500 })
    }
    const { settings } = await visit()
    await expect(useServerSettings()).resolves.toBeNull()
    await nextTick()
    expect(settings.value).toMatchObject({ friendlyLabels: true, convertUnits: true })
    expect(settings.value.units.temperature).toBe('degree_celsius')
    expect(stored().units.temperature).toBe('degree_celsius')
  })

  it('are the app\'s defaults where the server has none of them', async () => {
    answer = () => ({ values: { shape: 'long' } })
    const { settings } = await visit()
    await useServerSettings()
    await nextTick()
    expect(settings.value.units.temperature).toBe('degree_celsius')
    expect(settings.value.friendlyLabels).toBe(true)
  })

  it('keep what the visitor chose while the answer was on its way, and take the rest from it', async () => {
    let release!: () => void
    const held = new Promise<void>((resolve) => {
      release = resolve
    })
    answer = async () => {
      await held
      return FAHRENHEIT()
    }
    const { settings } = await visit()
    // the page is not held for the answer: the settings are the defaults, and can be changed
    expect(settings.value.units.temperature).toBe('degree_celsius')
    settings.value.units.temperature = 'degree_kelvin'
    release()
    await vi.waitFor(() => expect(settings.value.units.speed).toBe('knots'))
    expect(settings.value.units.temperature).toBe('degree_kelvin')
  })

  it('are not asked for by a visitor who has settings stored', async () => {
    storage.setItem('wd_settings', JSON.stringify({ version: 2, friendlyLabels: false, convertUnits: true }))
    answer = FAHRENHEIT
    const { settings } = await visit()
    await nextTick()
    expect(asked).toBe(0)
    expect(settings.value.friendlyLabels).toBe(false)
    expect(settings.value.units.temperature).toBe('degree_celsius')
  })

  it('mark themselves as started from the server once it has answered, and keep the mark from then on', async () => {
    answer = FAHRENHEIT
    const { settings } = await visit()
    expect(settings.value.seededFromServer).toBe(false)
    await vi.waitFor(() => expect(settings.value.seededFromServer).toBe(true))
    await nextTick()
    expect(stored().seededFromServer).toBe(true)
  })

  it('are tried again at the next load where the server failed, and take its settings then', async () => {
    answer = () => {
      throw createError({ statusCode: 500 })
    }
    const first = await visit()
    await expect(useServerSettings()).resolves.toBeNull()
    await nextTick()
    expect(first.settings.value.units.temperature).toBe('degree_celsius')
    expect(stored().seededFromServer).toBe(false)

    clearNuxtState('server-settings')
    answer = FAHRENHEIT
    const second = await visit()
    await vi.waitFor(() => expect(second.settings.value.units.temperature).toBe('degree_fahrenheit'))
    expect(second.settings.value.seededFromServer).toBe(true)
    await nextTick()
    expect(stored().units.temperature).toBe('degree_fahrenheit')
    expect(asked).toBe(2)
  })

  it('keep a choice made meanwhile when the retry comes, and take the rest', async () => {
    answer = () => {
      throw createError({ statusCode: 500 })
    }
    const first = await visit()
    await expect(useServerSettings()).resolves.toBeNull()
    first.settings.value.units.temperature = 'degree_kelvin'
    await nextTick()

    clearNuxtState('server-settings')
    answer = FAHRENHEIT
    const second = await visit()
    await vi.waitFor(() => expect(second.settings.value.units.speed).toBe('knots'))
    expect(second.settings.value.units.temperature).toBe('degree_kelvin')
  })

  it('are not tried again where the server has no such endpoint (404)', async () => {
    answer = () => {
      throw createError({ statusCode: 404 })
    }
    const first = await visit()
    await expect(useServerSettings()).resolves.toBeNull()
    await vi.waitFor(() => expect(first.settings.value.seededFromServer).toBe(true))
    await nextTick()
    expect(stored().seededFromServer).toBe(true)

    clearNuxtState('server-settings')
    answer = FAHRENHEIT
    const second = await visit()
    await nextTick()
    expect(asked).toBe(1)
    expect(second.settings.value.units.temperature).toBe('degree_celsius')
  })

  describe('reset', () => {
    it('goes back to the server\'s settings where it has answered in this load, not to the app\'s defaults', async () => {
      answer = FAHRENHEIT
      const { settings, reset } = await visit()
      await vi.waitFor(() => expect(settings.value.seededFromServer).toBe(true))
      settings.value.units.temperature = 'degree_kelvin'
      settings.value.friendlyLabels = true
      reset()
      expect(settings.value.units.temperature).toBe('degree_fahrenheit')
      expect(settings.value.friendlyLabels).toBe(false)
      expect(settings.value.seededFromServer).toBe(true)
    })

    it('goes back to the app\'s defaults with no answer, and has the next load ask again', async () => {
      storage.setItem('wd_settings', JSON.stringify({ version: 2, units: { ...SETTINGS_DEFAULTS.units, temperature: 'degree_kelvin' } }))
      answer = FAHRENHEIT
      const { settings, reset } = await visit()
      reset()
      expect(settings.value.units.temperature).toBe('degree_celsius')
      expect(settings.value.seededFromServer).toBe(false)
    })
  })
})
