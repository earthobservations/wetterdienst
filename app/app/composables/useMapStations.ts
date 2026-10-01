import { defineAsyncComponent } from 'vue'
import MapStationsNotLoaded from '~/components/MapStationsNotLoaded.vue'

// The station map, loaded lazily, as Leaflet is only wanted once the map is opened. Where its code
// fails to load, as after a redeploy replaced the chunk under an open tab, the map area says so and
// offers a reload; `notLoaded` is set until a later attempt loads it, for the caller to hide what
// speaks of the map.
export function useMapStations() {
  const notLoaded = ref(false)
  const MapStations = defineAsyncComponent({
    loader: () => import('~/components/MapStations.vue').then(
      (module) => {
        notLoaded.value = false
        return module
      },
      (error) => {
        notLoaded.value = true
        throw error
      },
    ),
    errorComponent: MapStationsNotLoaded,
  })
  return { MapStations, notLoaded }
}
