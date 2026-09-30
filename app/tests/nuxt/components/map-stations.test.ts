import { mockNuxtImport, mountSuspended } from '@nuxt/test-utils/runtime'
import { afterEach, describe, expect, it, vi } from 'vitest'
import MapStations from '~/components/MapStations.vue'

// The markers handed to leaflet.markercluster; the map itself is left to the e2e tests.
const { markerCluster } = vi.hoisted(() => ({
  markerCluster: vi.fn(async ({ markers }: { markers: unknown[] }) => ({
    markerCluster: { refreshClusters: () => {} },
    markers: markers.map(() => ({ on: () => {}, setIcon: () => {} })),
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
