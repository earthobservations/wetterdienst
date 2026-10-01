import { defineAsyncComponent } from 'vue'
import MapStationsNotLoaded from '~/components/MapStationsNotLoaded.vue'

// The station map, loaded lazily, as Leaflet is only wanted once the map is opened. Where its code
// fails to load, as after a redeploy replaced the chunk under an open tab, the map area says so and
// offers a reload; `notLoaded` is set meanwhile, for the caller to hide what speaks of the map.
export function useMapStations() {
  const notLoaded = ref(false)
  const MapStations = defineAsyncComponent({
    loader: () => {
      notLoaded.value = false
      return import('~/components/MapStations.vue').catch((error) => {
        notLoaded.value = true
        throw error
      })
    },
    errorComponent: MapStationsNotLoaded,
  })
  return { MapStations, notLoaded }
}
