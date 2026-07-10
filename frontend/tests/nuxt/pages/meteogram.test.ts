import { mountSuspended, registerEndpoint } from '@nuxt/test-utils/runtime'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import MeteogramPage from '~/pages/meteogram.vue'

describe('meteogram Page', () => {
  beforeEach(() => {
    globalThis.fetch = vi.fn()
    registerEndpoint('/api/stations', () => ({ stations: [] }))
  })

  it('renders the page', async () => {
    const wrapper = await mountSuspended(MeteogramPage)
    expect(wrapper.exists()).toBe(true)
  })

  it('displays the forecast heading', async () => {
    const wrapper = await mountSuspended(MeteogramPage)
    expect(wrapper.text()).toContain('Weather forecast')
  })

  it('shows the empty-state hint before a station is selected', async () => {
    const wrapper = await mountSuspended(MeteogramPage)
    expect(wrapper.text()).toContain('Search for a station above to generate a forecast')
  })

  it('has a station search and map picker', async () => {
    const wrapper = await mountSuspended(MeteogramPage)
    expect(wrapper.text()).toContain('Choose a station on the map')
  })

  it('fetches the meteogram when a station is selected', async () => {
    vi.mocked(globalThis.fetch).mockResolvedValue(
      new Response(JSON.stringify({ values: [] }), { status: 200 }),
    )

    const wrapper = await mountSuspended(MeteogramPage)
    const vm = wrapper.vm as any

    vm.selectedStation = { station_id: '00001', name: 'Test Station', latitude: 52.5, longitude: 13.4 }
    await wrapper.vm.$nextTick()
    await new Promise(resolve => setTimeout(resolve, 0))

    expect(globalThis.fetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/values?'),
    )
  })

  it('surfaces backend errors', async () => {
    vi.mocked(globalThis.fetch).mockResolvedValue(
      new Response('boom', { status: 500 }),
    )

    const wrapper = await mountSuspended(MeteogramPage)
    const vm = wrapper.vm as any

    vm.selectedStation = { station_id: '00001', name: 'Test Station', latitude: 52.5, longitude: 13.4 }
    await wrapper.vm.$nextTick()
    await new Promise(resolve => setTimeout(resolve, 0))
    await wrapper.vm.$nextTick()

    expect(vm.error).toContain('Backend error 500')
  })

  it('clears state and URL query when the station is deselected', async () => {
    vi.mocked(globalThis.fetch).mockResolvedValue(
      new Response(JSON.stringify({ values: [] }), { status: 200 }),
    )

    const wrapper = await mountSuspended(MeteogramPage)
    const vm = wrapper.vm as any

    vm.selectedStation = { station_id: '00001', name: 'Test Station', latitude: 52.5, longitude: 13.4 }
    await wrapper.vm.$nextTick()
    await new Promise(resolve => setTimeout(resolve, 0))

    vm.selectedStation = null
    await wrapper.vm.$nextTick()

    expect(vm.values).toEqual([])
    expect(vm.error).toBeNull()
  })

  it('clicking the about toggle reveals the explanatory text', async () => {
    const wrapper = await mountSuspended(MeteogramPage, { attachTo: document.body })
    expect(wrapper.text()).not.toContain('multi-day weather forecast from DWD MOSMIX')

    const aboutButton = wrapper.findAll('button').find(b => b.text().includes('About the forecast'))
    await aboutButton!.trigger('click')
    await wrapper.vm.$nextTick()

    expect(wrapper.text()).toContain('multi-day weather forecast from DWD MOSMIX')
  })

  it('clicking "Choose a station on the map" loads and reveals the map picker', async () => {
    registerEndpoint('/api/stations', () => ({
      stations: [{ station_id: '01001', name: 'JAN MAYEN', latitude: 70.93, longitude: -8.67 }],
    }))

    // Stub ClientOnly -- it wraps MapStations, which mounts real Leaflet +
    // leaflet.markercluster (CJS/PNG asset code that isn't happy-dom/Node-ESM
    // friendly and isn't what this test is about). The map's own rendering
    // is covered by e2e (real browser) tests instead.
    const wrapper = await mountSuspended(MeteogramPage, { attachTo: document.body, global: { stubs: { ClientOnly: true } } })
    const vm = wrapper.vm as any
    expect(vm.mapStations).toEqual([])

    const mapToggle = wrapper.findAll('button').find(b => b.text().includes('Choose a station on the map'))
    await mapToggle!.trigger('click')
    await wrapper.vm.$nextTick()
    await new Promise(resolve => setTimeout(resolve, 0))
    await wrapper.vm.$nextTick()

    expect(vm.showMap).toBe(true)
    expect(vm.mapStations).toEqual([
      { station_id: '01001', name: 'JAN MAYEN', latitude: 70.93, longitude: -8.67 },
    ])
  })
})
