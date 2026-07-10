import { mountSuspended, registerEndpoint } from '@nuxt/test-utils/runtime'
import { describe, expect, it } from 'vitest'
import StationSelection from '~/components/StationSelection.vue'

const parameterSelection = {
  provider: 'dwd',
  network: 'observation',
  resolution: 'daily' as const,
  dataset: 'climate_summary',
  parameters: ['temperature_air_mean_2m'],
}

const stationsResponse = {
  stations: [{ station_id: '00001', name: 'Test Station', state: 'Berlin', latitude: 52.5, longitude: 13.4 }],
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
