import { afterEach, describe, expect, it, vi } from 'vitest'

// The start-up plugin of the place search (GH-3791): a value of `NUXT_PLACES_SEARCH` that is neither on nor off switches the search off, and the operator
// is told once, with the value.

async function start(placesSearch: unknown) {
  vi.stubGlobal('defineNitroPlugin', (plugin: unknown) => plugin)
  vi.stubGlobal('useRuntimeConfig', () => ({ placesSearch }))
  const warn = vi.spyOn(console, 'warn').mockImplementation(() => {})
  const { default: plugin } = await import('../../server/plugins/places-search')
  ;(plugin as unknown as () => void)()
  return warn
}

afterEach(() => {
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
  vi.resetModules()
})

describe('the start-up warning of the place search', () => {
  it('names a value it does not know and says the search is off', async () => {
    const warn = await start('of')
    expect(warn).toHaveBeenCalledTimes(1)
    expect(warn.mock.calls[0]![0]).toBe('[wetterdienst-app] NUXT_PLACES_SEARCH="of" is not one of on, true, 1, yes, enabled (on) or off, false, 0, no, disabled (off): the place search is switched off.')
  })

  it.each(['on', 'off', 'true', 'false', '', undefined])('says nothing of %s', async (value) => {
    expect(await start(value)).not.toHaveBeenCalled()
  })
})
