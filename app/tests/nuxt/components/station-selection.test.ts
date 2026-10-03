import type { VueWrapper } from '@vue/test-utils'
import { mockNuxtImport, mountSuspended, registerEndpoint } from '@nuxt/test-utils/runtime'
import { setResponseStatus } from 'h3'
import { afterEach, describe, expect, it, onTestFinished, vi } from 'vitest'
import { h, nextTick } from 'vue'
import StationSelection from '~/components/StationSelection.vue'

const parameterSelection = {
  provider: 'dwd',
  network: 'observation',
  resolution: 'daily' as const,
  dataset: 'climate_summary',
  parameters: ['temperature_air_mean_2m'],
}

const stationsResponse = {
  stations: [{ station_id: '00001', name: 'Test Station', region: 'Berlin', latitude: 52.5, longitude: 13.4 }],
}

describe('stationSelection', () => {
  it('does not fetch the station list until the select menu is opened', async () => {
    let calls = 0
    registerEndpoint('/api/stations', () => {
      calls++
      return stationsResponse
    })

    const wrapper = await mountSuspended(StationSelection, {
      props: { parameterSelection, multiple: true },
      attachTo: document.body,
    })
    await new Promise(resolve => setTimeout(resolve, 50))
    await wrapper.vm.$nextTick()

    expect(calls).toBe(0)

    const vm = wrapper.vm as any
    vm.selectOpen = true
    await wrapper.vm.$nextTick()
    await new Promise(resolve => setTimeout(resolve, 50))
    await wrapper.vm.$nextTick()

    expect(calls).toBe(1)
  })

  it('does not fetch the station list until the map picker is opened', async () => {
    let calls = 0
    registerEndpoint('/api/stations', () => {
      calls++
      return stationsResponse
    })

    // Stub ClientOnly -- it wraps MapStations, which mounts real Leaflet +
    // leaflet.markercluster (CJS/PNG asset code that isn't happy-dom/Node-ESM
    // friendly and isn't what this test is about). The map's own rendering
    // is covered by e2e (real browser) tests instead.
    const wrapper = await mountSuspended(StationSelection, {
      props: { parameterSelection, multiple: true },
      attachTo: document.body,
      global: { stubs: { ClientOnly: true } },
    })
    await new Promise(resolve => setTimeout(resolve, 50))
    await wrapper.vm.$nextTick()

    expect(calls).toBe(0)

    const mapToggle = wrapper.findAll('button').find(b => b.text().includes('Choose on the map'))
    await mapToggle!.trigger('click')
    await wrapper.vm.$nextTick()
    await new Promise(resolve => setTimeout(resolve, 50))
    await wrapper.vm.$nextTick()

    expect(calls).toBe(1)
  })

  it('fetches immediately when stations need to be restored from a shared URL', async () => {
    let calls = 0
    registerEndpoint('/api/stations', () => {
      calls++
      return stationsResponse
    })

    const wrapper = await mountSuspended(StationSelection, {
      props: { parameterSelection, initialStationIds: ['00001'], multiple: true },
      attachTo: document.body,
    })
    await new Promise(resolve => setTimeout(resolve, 50))
    await wrapper.vm.$nextTick()

    expect(calls).toBe(1)
    const vm = wrapper.vm as any
    expect(vm.selectedStations).toEqual([expect.objectContaining({ station_id: '00001' })])
  })

  it('resets stationsLoaded on a failed fetch, so reopening the picker retries', async () => {
    let failing = true
    registerEndpoint('/api/stations', (event) => {
      if (failing) {
        setResponseStatus(event, 500)
        return { error: 'boom' }
      }
      return stationsResponse
    })

    const wrapper = await mountSuspended(StationSelection, {
      props: { parameterSelection, multiple: true },
      attachTo: document.body,
    })
    await new Promise(resolve => setTimeout(resolve, 50))
    await wrapper.vm.$nextTick()

    const vm = wrapper.vm as any
    vm.selectOpen = true
    await wrapper.vm.$nextTick()
    await new Promise(resolve => setTimeout(resolve, 100))
    await wrapper.vm.$nextTick()

    // A failed request must not be treated as "loaded" -- otherwise reopening
    // the picker would never retry, and the empty result would misleadingly
    // look like a confirmed "no stations found" instead of a failed request.
    expect(vm.stationsLoaded).toBe(false)
    expect(wrapper.text()).toContain('Failed to load stations')

    failing = false
    vm.selectOpen = false
    await wrapper.vm.$nextTick()
    vm.selectOpen = true
    await wrapper.vm.$nextTick()
    await new Promise(resolve => setTimeout(resolve, 100))
    await wrapper.vm.$nextTick()

    expect(vm.stationsLoaded).toBe(true)
    expect(wrapper.text()).not.toContain('Failed to load stations')
    expect(vm.allStations).toEqual(stationsResponse.stations)
  })

  it('fetches the station list once, not twice', async () => {
    // `useFetch` refetches on its own when its reactive query changes, and `fetchStations` also
    // refreshes explicitly -- which fetched the whole list (332 kB for dwd daily) twice per open.
    let calls = 0
    registerEndpoint('/api/stations', () => {
      calls++
      return stationsResponse
    })

    const wrapper = await mountSuspended(StationSelection, {
      props: { parameterSelection, multiple: true },
      attachTo: document.body,
    })
    const vm = wrapper.vm as any
    vm.selectOpen = true
    await wrapper.vm.$nextTick()
    await new Promise(resolve => setTimeout(resolve, 100))
    await wrapper.vm.$nextTick()

    expect(calls).toBe(1)
  })

  it('refetches when parameters change while a picker is open', async () => {
    // Changing parameters clears the list, since it is now for the wrong dataset. With a picker
    // open on screen -- the map stays expanded while parameters are edited above it -- that leaves
    // it visibly empty, so the refetch has to happen without waiting for a reopen.
    let calls = 0
    registerEndpoint('/api/stations', () => {
      calls++
      return stationsResponse
    })

    const wrapper = await mountSuspended(StationSelection, {
      props: { parameterSelection, multiple: true },
      attachTo: document.body,
    })
    const vm = wrapper.vm as any
    vm.selectOpen = true
    await wrapper.vm.$nextTick()
    await new Promise(resolve => setTimeout(resolve, 100))
    await wrapper.vm.$nextTick()

    expect(calls).toBe(1)

    await wrapper.setProps({
      parameterSelection: { ...parameterSelection, dataset: 'precipitation_more', parameters: ['precipitation_amount'] },
    })
    await new Promise(resolve => setTimeout(resolve, 100))
    await wrapper.vm.$nextTick()

    expect(calls).toBe(2)
    expect(vm.allStations).toEqual(stationsResponse.stations)
  })

  it.each([true, false])('labels a station without a region by name and id alone (multiple: %s)', async (multiple) => {
    // A network without regions, e.g. DWD MOSMIX, sends `region: null` for every station.
    registerEndpoint('/api/stations', () => ({
      stations: [
        { station_id: '01001', name: 'JAN MAYEN', region: null, latitude: 70.9, longitude: -8.7 },
        ...stationsResponse.stations,
      ],
    }))

    const wrapper = await mountSuspended(StationSelection, {
      props: { parameterSelection, initialStationIds: ['01001'], multiple },
      attachTo: document.body,
    })
    onTestFinished(() => wrapper.unmount())
    const vm = wrapper.vm as any
    await vi.waitFor(() => expect(vm.selectedStations).toHaveLength(1))

    expect(vm.stationItems.map((i: { label: string }) => i.label)).toEqual([
      'JAN MAYEN (ID: 01001)',
      'Test Station (ID: 00001, Berlin)',
    ])
    expect(vm.selectedItems).toEqual([{ label: 'JAN MAYEN (ID: 01001)', value: '01001' }])
  })

  it('does not fetch anything while parameters are unselected', async () => {
    let calls = 0
    registerEndpoint('/api/stations', () => {
      calls++
      return stationsResponse
    })

    const wrapper = await mountSuspended(StationSelection, {
      props: { parameterSelection: { ...parameterSelection, parameters: [] }, multiple: true },
      attachTo: document.body,
    })
    await new Promise(resolve => setTimeout(resolve, 50))
    await wrapper.vm.$nextTick()

    const vm = wrapper.vm as any
    vm.selectOpen = true
    await wrapper.vm.$nextTick()
    await new Promise(resolve => setTimeout(resolve, 50))

    expect(calls).toBe(0)
  })
})

describe('stationSelection with postcode stations', () => {
  // dwd/derived monthly/climate_correction_factor has no station list: its stations are the
  // German postcodes, sent with a null name, region, latitude, longitude and elevation.
  const derivedSelection = {
    provider: 'dwd',
    network: 'derived',
    resolution: 'monthly' as const,
    dataset: 'climate_correction_factor',
    parameters: ['climate_correction_factor'],
  }
  const postcode = { station_id: '01067', name: null, region: null, latitude: null, longitude: null, elevation: null }

  it.each([true, false])('labels a station without a name by its id (multiple: %s)', async (multiple) => {
    registerEndpoint('/api/stations', () => ({ stations: [postcode, { ...postcode, station_id: '01069' }] }))

    const wrapper = await mountSuspended(StationSelection, {
      props: { parameterSelection: derivedSelection, initialStationIds: ['01067'], multiple },
      attachTo: document.body,
    })
    onTestFinished(() => wrapper.unmount())
    const vm = wrapper.vm as any
    await vi.waitFor(() => expect(vm.selectedStations).toHaveLength(1))

    expect(vm.stationItems.map((i: { label: string }) => i.label)).toEqual(['ID: 01067', 'ID: 01069'])
    expect(vm.selectedItems).toEqual([{ label: 'ID: 01067', value: '01067' }])
    // the chip of a chosen station, which a named station shows as "name (id)"
    const chip = wrapper.findAll('.cursor-pointer').find(c => c.text().includes('01067'))
    expect(chip!.text()).toBe('01067 ×')
    expect(wrapper.text()).not.toContain('null')
  })
})

// Nuxt's reload of the page: the test's document does not take it
const { reloadNuxtApp } = vi.hoisted(() => ({ reloadNuxtApp: vi.fn() }))
mockNuxtImport('reloadNuxtApp', () => reloadNuxtApp)

describe('the station selection\'s station map whose code could not be loaded', () => {
  let wrapper: VueWrapper | undefined

  afterEach(() => {
    wrapper?.unmount()
    wrapper = undefined
    vi.doUnmock('~/components/MapStations.vue')
    vi.restoreAllMocks()
    reloadNuxtApp.mockClear()
  })

  it('says so in place of the map, without the hint to tap it, and offers a reload', async () => {
    registerEndpoint('/api/stations', () => ({
      stations: [{ station_id: '01001', name: 'JAN MAYEN', region: 'Norway', latitude: 70.93, longitude: -8.67 }],
    }))
    wrapper = await mountSuspended(StationSelection, { props: { parameterSelection, multiple: true }, attachTo: document.body })
    // the map's chunk fails as it does where a redeploy has replaced it under an open tab, once the
    // hint was seen while it loaded
    let fail!: () => void
    const failing = new Promise<void>((resolve) => {
      fail = resolve
    })
    vi.doMock('~/components/MapStations.vue', async () => {
      await failing
      throw new Error('chunk failed to load')
    })
    vi.spyOn(console, 'error').mockImplementation(() => {})
    vi.spyOn(console, 'warn').mockImplementation(() => {})
    await wrapper.findAll('button').find(b => b.text().includes('Choose on the map'))!.trigger('click')
    await vi.waitFor(() => expect(wrapper!.text()).toContain('Tap markers on the map to add or remove stations.'))
    fail()
    const alert = await vi.waitFor(() => {
      const found = wrapper!.find('[role="alert"]')
      expect(found.exists()).toBe(true)
      return found
    })
    expect(alert.text()).toBe('The stations could not be shown on the map. Reload the page to try again.')
    expect(wrapper.text()).not.toContain('Tap markers on the map to add or remove stations.')
    await wrapper.findAll('button').find(b => b.text() === 'Reload page')!.trigger('click')
    // forced: unforced, Nuxt drops a second click within ten seconds of a first that did not help
    expect(reloadNuxtApp).toHaveBeenCalledExactlyOnceWith({ force: true })

    // where a later opening loads the map, the hint is back: Vue asks for the module again. Not
    // before it has loaded, which may fail again
    let release!: () => void
    const gate = new Promise<void>((resolve) => {
      release = resolve
    })
    let asked = false
    vi.doMock('~/components/MapStations.vue', async () => {
      asked = true
      await gate
      return { __esModule: true, default: { render: () => h('div', 'Leaflet stand-in') } }
    })
    const toggle = wrapper.findAll('button').find(b => b.text().includes('Choose on the map'))!
    await toggle.trigger('click')
    await toggle.trigger('click')
    await vi.waitFor(() => expect(asked).toBe(true))
    await nextTick()
    expect(wrapper.text()).not.toContain('Tap markers on the map to add or remove stations.')
    release()
    await vi.waitFor(() => expect(wrapper!.text()).toContain('Leaflet stand-in'))
    expect(wrapper.text()).toContain('Tap markers on the map to add or remove stations.')
    expect(wrapper.find('[role="alert"]').exists()).toBe(false)
  })
})

describe('stationSelection station list that could not be fetched', () => {
  it('asks /api/stations once for a request answered with a 500, and tells its error', async () => {
    // counted at the endpoint, which a request reaches however it is made
    let asked = 0
    onTestFinished(registerEndpoint('/api/stations', (event) => {
      asked++
      setResponseStatus(event, 500)
      return { detail: 'Upstream failed' }
    }))
    // a dataset of its own, so the list is not one the tests above leave mounted
    const wrapper = await mountSuspended(StationSelection, {
      props: { parameterSelection: { ...parameterSelection, dataset: 'kl' }, multiple: true },
      attachTo: document.body,
    })
    onTestFinished(() => wrapper.unmount())
    ;(wrapper.vm as any).selectOpen = true
    await vi.waitFor(() => expect(wrapper.text()).toContain('Failed to load stations'))
    expect(asked).toBe(1)
  })
})
