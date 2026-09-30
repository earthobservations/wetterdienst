<script setup lang="ts">
import * as L from 'leaflet'
import { computed, ref, watch } from 'vue'

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

function isSelected(stationId: string) {
  return props.selectedStations.some((s: any) => s.station_id === stationId)
}

// A station without a position, e.g. a postcode of dwd/derived climate_correction_factor, has
// no place on the map: it is left off it, and out of its centre and bounds.
function positioned(stations: any[]) {
  return stations.filter(s => s.latitude != null && s.longitude != null)
}

const mappedStations = computed(() => positioned(props.stations))

const mapCenter = computed<[number, number]>(() => {
  const stations = mappedStations.value
  if (!stations.length)
    return [51.1657, 10.4515]
  const latSum = stations.reduce((a, s) => a + s.latitude, 0)
  const lngSum = stations.reduce((a, s) => a + s.longitude, 0)
  return [latSum / stations.length, lngSum / stations.length]
})

const mapBounds = computed(() => {
  const stations = centerOnSelectedStations.value ? positioned(props.selectedStations) : mappedStations.value
  if (!stations.length)
    return null
  const latitudes = stations.map(s => s.latitude)
  const longitudes = stations.map(s => s.longitude)
  return L.latLngBounds(
    L.latLng(Math.min(...latitudes), Math.min(...longitudes)),
    L.latLng(Math.max(...latitudes), Math.max(...longitudes)),
  )
})

async function createMarkers() {
  if (!map.value?.leafletObject)
    return
  // The previous list's markers go first, even when the new list has none to show: left in
  // place, a dataset whose stations have no position would show, and select, another's.
  if (markerClusterGroup) {
    map.value.leafletObject.removeLayer(markerClusterGroup)
    markerClusterGroup = null
    markersMap.clear()
  }
  const stations = mappedStations.value
  if (!stations.length)
    return
  const result = await useLMarkerCluster({
    leafletObject: map.value.leafletObject,
    markers: stations.map(station => ({
      name: station.name,
      lat: station.latitude,
      lng: station.longitude,
      options: {
        title: stationLabel(station),
      },
    })),
  })
  markerClusterGroup = result.markerCluster
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
  // avoid noisy logs in production; keep a warn for visibility when needed
  console.warn('selectedStations changed', props.selectedStations)
  updateMarkerIcons()
  // when user selects stations by clicking, indicate map is centered on selection
  if (props.selectedStations && props.selectedStations.length > 0) {
    centerOnSelectedStations.value = true
  }
}, { deep: true })

watch([
  () => centerOnSelectedStations.value,
  () => props.selectedStations,
], () => {
  if (map.value?.leafletObject && mapBounds.value) {
    map.value.leafletObject.fitBounds(mapBounds.value)
  }
}, { deep: true })
</script>

<template>
  <div>
    <div class="p-4 space-y-4">
      <UButton
        :label="centerOnSelectedStations ? t('map.centerAll') : (props.selectedStations.length === 1 ? t('map.centerSelected') : t('map.centerSelectedPlural'))"
        color="neutral"
        variant="ghost"
        size="sm"
        block
        :disabled="!props.selectedStations.length && !centerOnSelectedStations"
        @click="toggleCenter"
      />
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
