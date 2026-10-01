<script setup lang="ts">
import * as L from 'leaflet'
import { computed, onBeforeUnmount, ref, watch } from 'vue'

const props = defineProps<{
  stations: any[]
  selectedStations: any[]
  multiple?: boolean
}>()
const emit = defineEmits(['update:selectedStations'])

// <LMap use-global-leaflet> and useLMarkerCluster() (from @nuxtjs/leaflet) both
// read `window.L` directly rather than importing leaflet themselves. Setting it
// here -- inside this already-lazy-loaded component -- rather than in a global
// plugin keeps leaflet code-split into this chunk instead of bundled into every
// page's initial load.
if (import.meta.client && !window.L)
  window.L = L

const { t } = useI18n()

const map = ref(null) as any
let markerClusterGroup: any = null
const markersMap: Map<string, any> = new Map()

const centerOnSelectedStations = ref(false)
// The newest list's markers could not be built: leaflet.markercluster failed to load, as when a
// redeploy has replaced its chunk under an open tab, or the network dropped. Null while it has not
// failed, else the failure's number, so a newer list that fails too is told again
const markersFailure = ref<number | null>(null)
let markersFailures = 0

function isSelected(stationId: string) {
  return props.selectedStations.some((s: any) => s.station_id === stationId)
}

// A station without a position, e.g. a postcode of dwd/derived climate_correction_factor, has
// no place on the map: it is left off it, and out of its centre and bounds.
const mappedStations = computed(() => props.stations.filter(hasPosition))
// The selected stations the map can centre on.
const mappedSelectedStations = computed(() => props.selectedStations.filter(hasPosition))

const mapCenter = computed<[number, number]>(() => {
  const stations = mappedStations.value
  if (!stations.length)
    return [51.1657, 10.4515]
  const latSum = stations.reduce((a, s) => a + s.latitude, 0)
  const lngSum = stations.reduce((a, s) => a + s.longitude, 0)
  return [latSum / stations.length, lngSum / stations.length]
})

const mapBounds = computed(() => {
  const stations = centerOnSelectedStations.value ? mappedSelectedStations.value : mappedStations.value
  if (!stations.length)
    return null
  // Leaflet extends the bounds by each position in turn, where Math.min(...latitudes) threw past
  // about 120k stations (65,536 in Safari), as NOAA GHCN daily lists
  return L.latLngBounds(stations.map(s => [s.latitude, s.longitude]))
})

// Counts the calls to createMarkers(), and the map's removal, so that a call overtaken by either
// while it waits can tell.
let markersGeneration = 0
onBeforeUnmount(() => {
  markersGeneration++
})

async function createMarkers() {
  const generation = ++markersGeneration
  const leafletMap = map.value?.leafletObject
  if (!leafletMap)
    return
  // The previous list's markers go first, even when the new list has none to show: left in
  // place, a dataset whose stations have no position would show, and select, another's.
  if (markerClusterGroup) {
    leafletMap.removeLayer(markerClusterGroup)
    markerClusterGroup = null
    markersMap.clear()
  }
  const stations = mappedStations.value
  if (!stations.length) {
    markersFailure.value = null
    return
  }
  // useLMarkerCluster() adds the cluster to the map it is handed itself, as soon as
  // leaflet.markercluster has loaded, before it returns. It is handed a stand-in that ignores the
  // add: the cluster is added below, once this call is known to be still the current one.
  let result
  try {
    result = await useLMarkerCluster({
      leafletObject: { addLayer: () => leafletMap } as unknown as L.Map,
      markers: stations.map(station => ({
        name: station.name,
        lat: station.latitude,
        lng: station.longitude,
        options: {
          title: stationLabel(station),
        },
      })),
    })
  }
  catch (error) {
    console.error('The station markers could not be built', error)
    // told on the map for the newest list only: an older list's failure says nothing about the map
    // shown
    if (generation === markersGeneration)
      markersFailure.value = ++markersFailures
    return
  }
  // The list changed, or the map was removed (its section collapsed, the page left), while
  // leaflet.markercluster was loading: the cluster is an older list's, or has no map to go on -- a
  // removed map has no panes to draw it on.
  if (generation !== markersGeneration)
    return
  markersFailure.value = null
  markerClusterGroup = result.markerCluster
  leafletMap.addLayer(markerClusterGroup)
  result.markers.forEach((marker, index) => {
    const station = stations[index]
    if (station) {
      markersMap.set(station.station_id, marker)
      marker.on('click', () => {
        let newSelection
        if (props.multiple) {
          if (isSelected(station.station_id)) {
            newSelection = props.selectedStations.filter((s: any) => s.station_id !== station.station_id)
          }
          else {
            newSelection = [...props.selectedStations, station]
          }
        }
        else {
          newSelection = [station]
        }
        emit('update:selectedStations', newSelection)
      })
    }
  })
}

function updateMarkerIcons() {
  if (!markerClusterGroup)
    return
  const defaultIcon = L.icon({
    iconUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon.png',
    shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-shadow.png',
    iconSize: [25, 41],
    iconAnchor: [12, 41],
    popupAnchor: [1, -34],
    shadowSize: [41, 41],
  })
  const selectedIcon = L.icon({
    iconUrl: 'https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-2x-green.png',
    shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-shadow.png',
    iconSize: [25, 41],
    iconAnchor: [12, 41],
    popupAnchor: [1, -34],
    shadowSize: [41, 41],
  })
  markersMap.forEach((marker, stationId) => {
    const icon = isSelected(stationId) ? selectedIcon : defaultIcon
    marker.setIcon(icon)
  })
  markerClusterGroup.refreshClusters()
}

async function onMapReady() {
  await createMarkers()
  updateMarkerIcons()
}

function toggleCenter() {
  centerOnSelectedStations.value = !centerOnSelectedStations.value
  if (map.value?.leafletObject && mapBounds.value) {
    map.value.leafletObject.fitBounds(mapBounds.value)
  }
}

watch(() => props.stations, async () => {
  await createMarkers()
  updateMarkerIcons()
})

watch(() => props.selectedStations, () => {
  updateMarkerIcons()
  // when user selects stations by clicking, indicate map is centered on selection -- for a selection
  // with a position, as one without leaves nothing to centre on. Centring already on stays on, so
  // its button still offers to fit the map to all stations.
  if (mappedSelectedStations.value.length > 0)
    centerOnSelectedStations.value = true
}, { deep: true })

// Follows the selection while the map is centred on it. Off, the map is left where the user put it:
// toggleCenter() fits it to all stations itself, and a selection without a position leaves
// centring off, where refitting on it zoomed out to all stations.
watch([
  () => centerOnSelectedStations.value,
  () => props.selectedStations,
], () => {
  if (!centerOnSelectedStations.value)
    return
  if (map.value?.leafletObject && mapBounds.value) {
    map.value.leafletObject.fitBounds(mapBounds.value)
  }
}, { deep: true })
</script>

<template>
  <div>
    <div class="p-4 space-y-4">
      <UButton
        :label="centerOnSelectedStations ? t('map.centerAll') : (mappedSelectedStations.length === 1 ? t('map.centerSelected') : t('map.centerSelectedPlural'))"
        color="neutral"
        variant="ghost"
        size="sm"
        block
        :disabled="!mappedSelectedStations.length && !centerOnSelectedStations"
        @click="toggleCenter"
      />
      <!-- mounted anew for each failure, so a newer list that fails too is announced again -->
      <p v-if="markersFailure !== null" :key="markersFailure" role="alert" class="text-sm font-medium text-center text-red-600 dark:text-red-400">
        {{ t('map.markersNotShown') }}
      </p>
      <LMap
        ref="map"
        :zoom="6"
        :max-zoom="18"
        :center="mapCenter"
        :use-global-leaflet="true"
        style="height: 400px; width: 100%;"
        @ready="onMapReady"
      >
        <LTileLayer
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          attribution="&copy; <a href='https://www.openstreetmap.org/'>OpenStreetMap</a> contributors"
          layer-type="base"
          name="OpenStreetMap"
        />
      </LMap>
    </div>
  </div>
</template>

<style>
@import 'leaflet.markercluster/dist/MarkerCluster.css';
@import 'leaflet.markercluster/dist/MarkerCluster.Default.css';
</style>
