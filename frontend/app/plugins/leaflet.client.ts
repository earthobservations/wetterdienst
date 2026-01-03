import * as L from 'leaflet'
import 'leaflet.markercluster'

export default defineNuxtPlugin(() => ({
  provide: {
    L,
  },
}))
