import type * as Leaflet from 'leaflet'

// @vue-leaflet/vue-leaflet's `use-global-leaflet` mode and @nuxtjs/leaflet's useLMarkerCluster()
// read `window.L` rather than importing leaflet themselves, and neither sets it. MapStations.vue
// sets it from its own leaflet import, so that leaflet stays in that lazily loaded chunk.
declare global {
  interface Window {
    L: typeof Leaflet
  }
}
