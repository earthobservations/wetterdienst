import { mockNuxtImport, mountSuspended } from '@nuxt/test-utils/runtime'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { nextTick } from 'vue'
import MapStations from '~/components/MapStations.vue'

// The markers handed to leaflet.markercluster; the map itself is left to the e2e tests.
const { markerCluster } = vi.hoisted(() => ({
  markerCluster: vi.fn(async ({ markers }: { markers: unknown[] }) => ({
    markerCluster: { refreshClusters: () => {} },
    markers: markers.map(() => ({ on: (_event: string, _handler: () => void) => {}, setIcon: () => {} })),
  })),
}))
mockNuxtImport('useLMarkerCluster', () => markerCluster)
// Real Leaflet draws nothing in happy-dom, and LMap imports its marker images, which Node can't.
vi.mock('@vue-leaflet/vue-leaflet', async () => {
  const { defineComponent, h } = await import('vue')
  return {
    LMap: defineComponent({ setup: (_, { slots }) => () => h('div', slots.default?.()) }),
    LTileLayer: defineComponent({ setup: () => () => null }),
  }
})

describe('mapStations', () => {
  let wrapper: Awaited<ReturnType<typeof mountSuspended>> | undefined

  afterEach(() => {
    wrapper?.unmount()
    wrapper = undefined
    markerCluster.mockClear()
  })

  it('titles a marker without a region by name and id alone', async () => {
    const stations = [
      { station_id: '01001', name: 'JAN MAYEN', region: null, latitude: 70.9, longitude: -8.7 },
      { station_id: '00001', name: 'Test Station', region: 'Berlin', latitude: 52.5, longitude: 13.4 },
    ]
    wrapper = await mountSuspended(MapStations, {
      props: { stations, selectedStations: [] },
    })
    const vm = wrapper.vm as any
    vm.map = { leafletObject: { removeLayer: () => {}, fitBounds: () => {} } }
    await vm.onMapReady()

    const { markers } = markerCluster.mock.calls[0]![0] as { markers: { options: { title: string } }[] }
    expect(markers.map(m => m.options.title)).toEqual([
      'JAN MAYEN (ID: 01001)',
      'Test Station (ID: 00001, Berlin)',
    ])
  })
})

describe('mapStations with stations that have no position', () => {
  // dwd/derived monthly/climate_correction_factor has no station list: its stations are the
  // German postcodes, sent with a null name, region, latitude, longitude and elevation.
  const postcode = { station_id: '01067', name: null, region: null, latitude: null, longitude: null, elevation: null }
  const berlin = { station_id: '00001', name: 'Test Station', region: 'Berlin', latitude: 52.5, longitude: 13.4 }
  const jan = { station_id: '01001', name: 'JAN MAYEN', region: null, latitude: 70.9, longitude: -8.7 }

  let wrapper: Awaited<ReturnType<typeof mountSuspended>> | undefined

  afterEach(() => {
    wrapper?.unmount()
    wrapper = undefined
    markerCluster.mockClear()
  })

  async function mountReady(stations: unknown[], selectedStations: unknown[] = []) {
    wrapper = await mountSuspended(MapStations, { props: { stations, selectedStations, multiple: true } })
    const vm = wrapper.vm as any
    const removeLayer = vi.fn()
    vm.map = { leafletObject: { removeLayer, fitBounds: () => {} } }
    await vm.onMapReady()
    return { vm, removeLayer }
  }

  it('leaves them off the map, and a click on a marker selects the station it stands for', async () => {
    const clicks: (() => void)[] = []
    markerCluster.mockImplementationOnce(async ({ markers }: { markers: unknown[] }) => ({
      markerCluster: { refreshClusters: () => {} },
      markers: markers.map(() => ({
        on: (_event: string, handler: () => void) => {
          clicks.push(handler)
        },
        setIcon: () => {},
      })),
    }))
    await mountReady([postcode, berlin, { ...postcode, station_id: '01069' }, jan])

    const { markers } = markerCluster.mock.calls[0]![0] as { markers: { lat: number, lng: number, options: { title: string } }[] }
    expect(markers.map(m => [m.lat, m.lng, m.options.title])).toEqual([
      [52.5, 13.4, 'Test Station (ID: 00001, Berlin)'],
      [70.9, -8.7, 'JAN MAYEN (ID: 01001)'],
    ])

    clicks[1]!()
    expect(wrapper!.emitted('update:selectedStations')).toEqual([[[jan]]])
  })

  it('centres and bounds the map on the stations that have a position', async () => {
    const { vm } = await mountReady([postcode, berlin, jan])

    expect(vm.mapCenter).toEqual([(52.5 + 70.9) / 2, (13.4 + -8.7) / 2])
    const bounds = vm.mapBounds
    expect([bounds.getSouth(), bounds.getWest(), bounds.getNorth(), bounds.getEast()]).toEqual([52.5, -8.7, 70.9, 13.4])
  })

  it('has no bounds, and the default centre, when no station has a position', async () => {
    const { vm } = await mountReady([postcode], [postcode])

    expect(vm.mapCenter).toEqual([51.1657, 10.4515])
    expect(vm.mapBounds).toBeNull()
    vm.centerOnSelectedStations = true
    expect(vm.mapBounds).toBeNull()
    expect(markerCluster).not.toHaveBeenCalled()
  })

  it('takes the previous list\'s markers off when the next has none with a position', async () => {
    const { removeLayer } = await mountReady([berlin])
    const { markerCluster: cluster } = await markerCluster.mock.results[0]!.value

    await wrapper!.setProps({ stations: [postcode] })
    await vi.waitFor(() => expect(removeLayer).toHaveBeenCalledWith(cluster))
    expect(markerCluster).toHaveBeenCalledTimes(1)
  })
})

describe('mapStations when its list changes while the markers are built', () => {
  const berlin = { station_id: '00001', name: 'Test Station', region: 'Berlin', latitude: 52.5, longitude: 13.4 }
  const jan = { station_id: '01001', name: 'JAN MAYEN', region: null, latitude: 70.9, longitude: -8.7 }

  let wrapper: Awaited<ReturnType<typeof mountSuspended>> | undefined

  afterEach(() => {
    wrapper?.unmount()
    wrapper = undefined
    // back to the implementation the mock was made with
    markerCluster.mockReset()
  })

  // A cluster per call, whose markers keep their click handlers. The first call is held on a gate
  // until the test releases it, as the import of leaflet.markercluster holds it on a cold load.
  function clustersWithFirstHeld() {
    const clusters: { markerCluster: object, clicks: (() => void)[] }[] = []
    let release!: () => void
    const gate = new Promise<void>((resolve) => {
      release = resolve
    })
    markerCluster.mockImplementation(async ({ markers }: { markers: unknown[] }) => {
      const cluster = { markerCluster: { refreshClusters: () => {} }, clicks: [] as (() => void)[] }
      const first = clusters.length === 0
      clusters.push(cluster)
      if (first)
        await gate
      return {
        markerCluster: cluster.markerCluster,
        markers: markers.map(() => ({
          on: (_event: string, handler: () => void) => {
            cluster.clicks.push(handler)
          },
          setIcon: () => {},
        })),
      }
    })
    return { clusters, release }
  }

  async function mountBuilding(stations: unknown[]) {
    wrapper = await mountSuspended(MapStations, { props: { stations, selectedStations: [] } })
    const vm = wrapper.vm as any
    const removeLayer = vi.fn()
    vm.map = { leafletObject: { removeLayer, fitBounds: () => {} } }
    const ready: Promise<void> = vm.onMapReady()
    return { removeLayer, ready }
  }

  it('takes the older list\'s cluster off the map when it arrives after the newer one', async () => {
    const { clusters, release } = clustersWithFirstHeld()
    const { removeLayer, ready } = await mountBuilding([berlin])

    await wrapper!.setProps({ stations: [jan] })
    await vi.waitFor(() => expect(clusters).toHaveLength(2))
    release()
    await ready

    expect(removeLayer).toHaveBeenCalledWith(clusters[0]!.markerCluster)
    expect(removeLayer).not.toHaveBeenCalledWith(clusters[1]!.markerCluster)
    // the older list's markers were never wired up, and the newer one's select their own station
    expect(clusters[0]!.clicks).toEqual([])
    clusters[1]!.clicks[0]!()
    expect(wrapper!.emitted('update:selectedStations')).toEqual([[[jan]]])
  })

  it('leaves the map empty when the list is cleared while the markers are built', async () => {
    const { clusters, release } = clustersWithFirstHeld()
    const { removeLayer, ready } = await mountBuilding([berlin])

    await wrapper!.setProps({ stations: [] })
    release()
    await ready

    expect(clusters).toHaveLength(1)
    expect(removeLayer).toHaveBeenCalledWith(clusters[0]!.markerCluster)
    expect(clusters[0]!.clicks).toEqual([])
  })
})

describe('mapStations centring on selected stations that have no position', () => {
  // a postcode of dwd/derived climate_correction_factor, which has no place on the map
  const postcode = { station_id: '01067', name: null, region: null, latitude: null, longitude: null, elevation: null }
  const berlin = { station_id: '00001', name: 'Test Station', region: 'Berlin', latitude: 52.5, longitude: 13.4 }

  let wrapper: Awaited<ReturnType<typeof mountSuspended>> | undefined

  afterEach(() => {
    wrapper?.unmount()
    wrapper = undefined
    markerCluster.mockClear()
  })

  const button = () => wrapper!.find('button')

  async function mountWith(selectedStations: unknown[]) {
    wrapper = await mountSuspended(MapStations, { props: { stations: [postcode, berlin], selectedStations: [], multiple: true } })
    const vm = wrapper.vm as any
    const fitBounds = vi.fn()
    vm.map = { leafletObject: { removeLayer: () => {}, fitBounds } }
    await wrapper.setProps({ selectedStations })
    return { vm, fitBounds }
  }

  it('offers no centring for a selection without a position', async () => {
    const { vm, fitBounds } = await mountWith([postcode])

    // it switched to "centre all", with nothing to centre on
    expect(vm.centerOnSelectedStations).toBe(false)
    expect(button().attributes('disabled')).toBeDefined()
    // and the map stays where the user put it, rather than zooming out to all stations
    expect(fitBounds).not.toHaveBeenCalled()
  })

  it('centres on, and counts, the selected stations that have one', async () => {
    const { vm, fitBounds } = await mountWith([postcode, berlin])

    expect(vm.centerOnSelectedStations).toBe(true)
    const bounds = fitBounds.mock.lastCall![0]
    expect([bounds.getSouth(), bounds.getWest(), bounds.getNorth(), bounds.getEast()]).toEqual([52.5, 13.4, 52.5, 13.4])

    vm.toggleCenter()
    await nextTick()
    expect(button().text()).toBe('Center on selected station')
    expect(button().attributes('disabled')).toBeUndefined()
  })

  it('stops centring when the selection moves on to stations without a position', async () => {
    const { vm, fitBounds } = await mountWith([berlin])
    expect(vm.centerOnSelectedStations).toBe(true)
    const fits = fitBounds.mock.calls.length

    await wrapper!.setProps({ selectedStations: [postcode] })
    // it stayed on, offering "centre all" for a centring with no bounds
    expect(vm.centerOnSelectedStations).toBe(false)
    expect(button().attributes('disabled')).toBeDefined()
    expect(fitBounds).toHaveBeenCalledTimes(fits)
  })
})
