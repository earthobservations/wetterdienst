import type { VueWrapper } from '@vue/test-utils'
import { mockNuxtImport, mountSuspended, registerEndpoint } from '@nuxt/test-utils/runtime'
import { afterEach, describe, expect, it, vi } from 'vitest'
import StationSelection from '~/components/StationSelection.vue'
import MeteogramPage from '~/pages/meteogram.vue'

const { reloadNuxtApp } = vi.hoisted(() => ({ reloadNuxtApp: vi.fn() }))
mockNuxtImport('reloadNuxtApp', () => reloadNuxtApp)

const stations = [{ station_id: '01001', name: 'JAN MAYEN', region: 'Norway', latitude: 70.93, longitude: -8.67 }]

describe('the station map whose code could not be loaded', () => {
  let wrapper: VueWrapper | undefined

  afterEach(() => {
    wrapper?.unmount()
    wrapper = undefined
    vi.doUnmock('~/components/MapStations.vue')
    vi.restoreAllMocks()
    reloadNuxtApp.mockClear()
  })

  async function openMap(mounted: VueWrapper, toggle: string) {
    // the map's chunk fails as it does where a redeploy has replaced it under an open tab
    vi.doMock('~/components/MapStations.vue', () => {
      throw new Error('chunk failed to load')
    })
    vi.spyOn(console, 'error').mockImplementation(() => {})
    vi.spyOn(console, 'warn').mockImplementation(() => {})
    await mounted.findAll('button').find(b => b.text().includes(toggle))!.trigger('click')
    const alert = await vi.waitFor(() => {
      const found = mounted.find('[role="alert"]')
      expect(found.exists()).toBe(true)
      return found
    })
    expect(alert.text()).toBe('The stations could not be shown on the map. Reload the page to try again.')
    await mounted.findAll('button').find(b => b.text() === 'Reload page')!.trigger('click')
    // forced: unforced, Nuxt drops a second click within ten seconds of a first that did not help
    expect(reloadNuxtApp).toHaveBeenCalledExactlyOnceWith({ force: true })
  }

  it('says so in the station selection, and offers a reload', async () => {
    registerEndpoint('/api/stations', () => ({ stations }))
    wrapper = await mountSuspended(StationSelection, {
      props: {
        parameterSelection: { provider: 'dwd', network: 'observation', resolution: 'daily', dataset: 'climate_summary', parameters: ['temperature_air_mean_2m'] },
        multiple: true,
      },
      attachTo: document.body,
    })
    await openMap(wrapper, 'Choose on the map')
  })

  it('says so on the meteogram page, and offers a reload', async () => {
    registerEndpoint('/api/stations', () => ({ stations }))
    wrapper = await mountSuspended(MeteogramPage, { attachTo: document.body })
    await openMap(wrapper, 'Choose a station on the map')
  })
})
