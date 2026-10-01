import { mockNuxtImport, mountSuspended } from '@nuxt/test-utils/runtime'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { nextTick } from 'vue'
import MapStations from '~/components/MapStations.vue'

// The markers handed to leaflet.markercluster; the map itself is left to the e2e tests. Like
// useLMarkerCluster(), it adds its cluster to the map it is handed before returning.
const { markerCluster } = vi.hoisted(() => ({
  markerCluster: vi.fn(async ({ leafletObject, markers }: { leafletObject: { addLayer: (layer: object) => unknown }, markers: unknown[] }) => {
    const cluster = { refreshClusters: () => {} }
    leafletObject.addLayer(cluster)
    return {
      markerCluster: cluster,
      markers: markers.map(() => ({ on: (_event: string, _handler: () => void) => {}, setIcon: () => {} })),
    }
  }),
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
    vm.map = { leafletObject: { addLayer: () => {}, removeLayer: () => {}, fitBounds: () => {} } }
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
    vm.map = { leafletObject: { addLayer: () => {}, removeLayer, fitBounds: () => {} } }
    await vm.onMapReady()
    return { vm, removeLayer }
  }

  it('leaves them off the map, and a click on a marker selects the station it stands for', async () => {
    const clicks: (() => void)[] = []
    markerCluster.mockImplementationOnce(async ({ leafletObject, markers }: { leafletObject: { addLayer: (layer: object) => unknown }, markers: unknown[] }) => {
      const cluster = { refreshClusters: () => {} }
      leafletObject.addLayer(cluster)
      return {
        markerCluster: cluster,
        markers: markers.map(() => ({
          on: (_event: string, handler: () => void) => {
            clicks.push(handler)
          },
          setIcon: () => {},
        })),
      }
    })
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
  // Like useLMarkerCluster(), each call adds its cluster to the map it is handed before returning.
  function clustersWithFirstHeld() {
    const clusters: { markerCluster: object, clicks: (() => void)[] }[] = []
    let release!: () => void
    const gate = new Promise<void>((resolve) => {
      release = resolve
    })
    markerCluster.mockImplementation(async ({ leafletObject, markers }: { leafletObject: { addLayer: (layer: object) => unknown }, markers: unknown[] }) => {
      const cluster = { markerCluster: { refreshClusters: () => {} }, clicks: [] as (() => void)[] }
      const first = clusters.length === 0
      clusters.push(cluster)
      if (first)
        await gate
      leafletObject.addLayer(cluster.markerCluster)
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
    const addLayer = vi.fn()
    const removeLayer = vi.fn()
    vm.map = { leafletObject: { addLayer, removeLayer, fitBounds: () => {} } }
    const ready: Promise<void> = vm.onMapReady()
    return { addLayer, removeLayer, ready }
  }

  it('keeps the older list\'s cluster off the map when it arrives after the newer one', async () => {
    const { clusters, release } = clustersWithFirstHeld()
    const { addLayer, removeLayer, ready } = await mountBuilding([berlin])

    await wrapper!.setProps({ stations: [jan] })
    await vi.waitFor(() => expect(clusters).toHaveLength(2))
    release()
    await ready

    expect(addLayer.mock.calls).toEqual([[clusters[1]!.markerCluster]])
    expect(removeLayer).not.toHaveBeenCalled()
    // the older list's markers were never wired up, and the newer one's select their own station
    expect(clusters[0]!.clicks).toEqual([])
    clusters[1]!.clicks[0]!()
    expect(wrapper!.emitted('update:selectedStations')).toEqual([[[jan]]])
  })

  it('leaves the map empty when the list is cleared while the markers are built', async () => {
    const { clusters, release } = clustersWithFirstHeld()
    const { addLayer, ready } = await mountBuilding([berlin])

    await wrapper!.setProps({ stations: [] })
    release()
    await ready

    expect(clusters).toHaveLength(1)
    expect(addLayer).not.toHaveBeenCalled()
    expect(clusters[0]!.clicks).toEqual([])
  })

  it('leaves a removed map alone when it goes while the markers are built', async () => {
    const { clusters, release } = clustersWithFirstHeld()
    const { addLayer, removeLayer, ready } = await mountBuilding([berlin])

    // the "Choose on the map" section is collapsed: LMap removes its map
    wrapper!.unmount()
    wrapper = undefined
    release()
    await ready

    expect(addLayer).not.toHaveBeenCalled()
    expect(removeLayer).not.toHaveBeenCalled()
    expect(clusters[0]!.clicks).toEqual([])
  })

  it('keeps a cluster off the map when a newer call comes as useLMarkerCluster() returns', async () => {
    const clusters: { markerCluster: object, clicks: (() => void)[] }[] = []
    // runs once, as the first call's useLMarkerCluster() adds its cluster and returns: the newer
    // call made by a scheduler flush that runs before the first call resumes
    let overtake: (() => Promise<void>) | undefined
    let overtaking: Promise<void> | undefined
    markerCluster.mockImplementation(async ({ leafletObject, markers }: { leafletObject: { addLayer: (layer: object) => unknown }, markers: unknown[] }) => {
      const cluster = { markerCluster: { refreshClusters: () => {} }, clicks: [] as (() => void)[] }
      clusters.push(cluster)
      leafletObject.addLayer(cluster.markerCluster)
      const newer = overtake
      overtake = undefined
      overtaking = newer?.()
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
    wrapper = await mountSuspended(MapStations, { props: { stations: [berlin], selectedStations: [] } })
    const vm = wrapper.vm as any
    const addLayer = vi.fn()
    const removeLayer = vi.fn()
    vm.map = { leafletObject: { addLayer, removeLayer, fitBounds: () => {} } }
    overtake = () => vm.createMarkers()

    await vm.onMapReady()
    await overtaking

    expect(clusters).toHaveLength(2)
    expect(addLayer.mock.calls).toEqual([[clusters[1]!.markerCluster]])
    expect(removeLayer).not.toHaveBeenCalled()
    // the overtaken call's markers were never wired up, and the newer call's select their station
    expect(clusters[0]!.clicks).toEqual([])
    clusters[1]!.clicks[0]!()
    expect(wrapper!.emitted('update:selectedStations')).toEqual([[[berlin]]])
  })

  it('leaves a map removed as useLMarkerCluster() returns alone', async () => {
    const refreshClusters = vi.fn()
    const setIcon = vi.fn()
    let unmount: (() => void) | undefined
    markerCluster.mockImplementation(async ({ leafletObject, markers }: { leafletObject: { addLayer: (layer: object) => unknown }, markers: unknown[] }) => {
      const cluster = { refreshClusters }
      leafletObject.addLayer(cluster)
      // the map's section is collapsed in a scheduler flush that runs before this call resumes
      unmount?.()
      return { markerCluster: cluster, markers: markers.map(() => ({ on: () => {}, setIcon })) }
    })
    wrapper = await mountSuspended(MapStations, { props: { stations: [berlin], selectedStations: [] } })
    const vm = wrapper.vm as any
    const addLayer = vi.fn()
    vm.map = { leafletObject: { addLayer, removeLayer: () => {}, fitBounds: () => {} } }
    unmount = () => {
      wrapper!.unmount()
      wrapper = undefined
    }

    await vm.onMapReady()

    expect(addLayer).not.toHaveBeenCalled()
    expect(refreshClusters).not.toHaveBeenCalled()
    expect(setIcon).not.toHaveBeenCalled()
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
    vm.map = { leafletObject: { addLayer: () => {}, removeLayer: () => {}, fitBounds } }
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

  it('keeps offering to fit all stations when a centred selection moves on to one without a position', async () => {
    const { vm, fitBounds } = await mountWith([berlin])
    expect(vm.centerOnSelectedStations).toBe(true)
    const fits = fitBounds.mock.calls.length

    await wrapper!.setProps({ selectedStations: [postcode] })
    // the map stays where it is, and the button can still zoom it out to every station
    expect(fitBounds).toHaveBeenCalledTimes(fits)
    expect(button().text()).toBe('Center on all stations')
    expect(button().attributes('disabled')).toBeUndefined()
    vm.toggleCenter()
    const bounds = fitBounds.mock.lastCall![0]
    expect([bounds.getSouth(), bounds.getWest(), bounds.getNorth(), bounds.getEast()]).toEqual([52.5, 13.4, 52.5, 13.4])
    expect(vm.centerOnSelectedStations).toBe(false)
  })
})

describe('mapStations when the selection changes', () => {
  const berlin = { station_id: '00001', name: 'Test Station', region: 'Berlin', latitude: 52.5, longitude: 13.4 }
  const jan = { station_id: '01001', name: 'JAN MAYEN', region: null, latitude: 70.9, longitude: -8.7 }

  let wrapper: Awaited<ReturnType<typeof mountSuspended>> | undefined

  afterEach(() => {
    wrapper?.unmount()
    wrapper = undefined
    vi.restoreAllMocks()
  })

  it('writes no warning of its own to the console', async () => {
    const warn = vi.spyOn(console, 'warn')
    wrapper = await mountSuspended(MapStations, { props: { stations: [berlin, jan], selectedStations: [], multiple: true } })

    await wrapper.setProps({ selectedStations: [berlin] })
    await wrapper.setProps({ selectedStations: [berlin, jan] })

    // Vue's own warnings, which an unrelated change can bring, are not the map's
    expect(warn.mock.calls.filter(([message]) => !String(message).startsWith('[Vue warn]'))).toEqual([])
  })
})

describe('mapStations when leaflet.markercluster fails to load', () => {
  const berlin = { station_id: '00001', name: 'Test Station', region: 'Berlin', latitude: 52.5, longitude: 13.4 }
  const jan = { station_id: '01001', name: 'JAN MAYEN', region: null, latitude: 70.9, longitude: -8.7 }
  // what a browser rejects the import with once a redeploy has replaced the chunk
  const chunkError = () => new TypeError('Failed to fetch dynamically imported module')
  const message = 'The stations could not be shown on the map. Reload the page to try again.'

  let wrapper: Awaited<ReturnType<typeof mountSuspended>> | undefined

  afterEach(() => {
    wrapper?.unmount()
    wrapper = undefined
    // back to the implementation the mock was made with
    markerCluster.mockReset()
    vi.restoreAllMocks()
  })

  const alert = () => wrapper!.find('[role="alert"]')

  async function mountWith(stations: unknown[]) {
    wrapper = await mountSuspended(MapStations, { props: { stations, selectedStations: [] } })
    const vm = wrapper.vm as any
    const addLayer = vi.fn()
    // set again after the message comes or goes: re-rendering sets the ref back to the LMap stub,
    // which holds no map
    const setMap = () => {
      vm.map = { leafletObject: { addLayer, removeLayer: () => {}, fitBounds: () => {} } }
    }
    setMap()
    return { vm, addLayer, setMap }
  }

  it('says so above the map, and settles rather than rejecting', async () => {
    const error = vi.spyOn(console, 'error').mockImplementation(() => {})
    markerCluster.mockImplementation(async () => {
      throw chunkError()
    })
    const { vm, addLayer } = await mountWith([berlin])

    await expect(vm.onMapReady()).resolves.toBeUndefined()

    expect(alert().text()).toBe(message)
    expect(addLayer).not.toHaveBeenCalled()
    expect(error).toHaveBeenCalledWith('The station markers could not be built', expect.any(TypeError))
  })

  it('tells a newer list that fails too anew', async () => {
    vi.spyOn(console, 'error').mockImplementation(() => {})
    markerCluster.mockImplementation(async () => {
      throw chunkError()
    })
    const { vm, setMap } = await mountWith([berlin])
    await vm.onMapReady()
    const first = alert().element

    setMap()
    await wrapper!.setProps({ stations: [jan] })
    await vi.waitFor(() => expect(markerCluster).toHaveBeenCalledTimes(2))
    // a new alert, which a screen reader announces, where the old one stayed silent
    await vi.waitFor(() => expect(alert().element).not.toBe(first))
    expect(alert().text()).toBe(message)
  })

  it('takes the message away once a newer list\'s markers are built, or it has none to show', async () => {
    vi.spyOn(console, 'error').mockImplementation(() => {})
    markerCluster.mockImplementationOnce(async () => {
      throw chunkError()
    })
    const { vm, addLayer, setMap } = await mountWith([berlin])
    await vm.onMapReady()
    expect(alert().exists()).toBe(true)

    setMap()
    await wrapper!.setProps({ stations: [jan] })
    await vi.waitFor(() => expect(addLayer).toHaveBeenCalledTimes(1))
    expect(alert().exists()).toBe(false)

    markerCluster.mockImplementationOnce(async () => {
      throw chunkError()
    })
    setMap()
    await wrapper!.setProps({ stations: [berlin] })
    await vi.waitFor(() => expect(alert().exists()).toBe(true))
    setMap()
    await wrapper!.setProps({ stations: [] })
    await vi.waitFor(() => expect(alert().exists()).toBe(false))
  })

  it('says nothing of an older list\'s failure that comes after the newer list\'s markers', async () => {
    const error = vi.spyOn(console, 'error').mockImplementation(() => {})
    let fail!: () => void
    const gate = new Promise<void>((resolve) => {
      fail = resolve
    })
    markerCluster.mockImplementationOnce(async () => {
      await gate
      throw chunkError()
    })
    const { vm, addLayer } = await mountWith([berlin])
    const ready: Promise<void> = vm.onMapReady()

    await wrapper!.setProps({ stations: [jan] })
    await vi.waitFor(() => expect(addLayer).toHaveBeenCalledTimes(1))
    fail()
    await ready

    expect(alert().exists()).toBe(false)
    expect(error).not.toHaveBeenCalled()
  })
})
