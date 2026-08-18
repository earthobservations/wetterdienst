import type * as Leaflet from 'leaflet'

// MapStations.vue and StationSelection.vue reference a bare global `L`
// (`declare const L: typeof import('leaflet')`) because @vue-leaflet/vue-leaflet's
// `use-global-leaflet` mode expects `window.L` to already be set -- it does not
// set it itself. `app/plugins/leaflet.client.ts` provides that global at runtime.
declare global {
  interface Window {
    L: typeof Leaflet
  }
}
