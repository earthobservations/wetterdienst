<script setup lang="ts">
import { computed, ref, watch } from 'vue'

declare const L: typeof import('leaflet')

const props = defineProps<{
  stations: any[]
  selectedStations: any[]
  multiple?: boolean
}>()
const emit = defineEmits(['update:selectedStations'])

const map = ref(null) as any
let markerClusterGroup: any = null
const markersMap: Map<string, any> = new Map()

const centerOnSelectedStations = ref(false)
const boundsVersion = ref(0)

function isSelected(stationId: string) {
  return props.selectedStations.some((s: any) => s.station_id === stationId)
}

const mapCenter = computed<[number, number]>(() => {
  if (!props.stations.length)
    return [51.1657, 10.4515]
  const latSum = props.stations.reduce((a, s) => a + s.latitude, 0)
  const lngSum = props.stations.reduce((a, s) => a + s.longitude, 0)
  return [latSum / props.stations.length, lngSum / props.stations.length]
})

const mapBounds = computed(() => {
  if (!props.stations.length)
    return null
  if (!centerOnSelectedStations.value) {
    const latitudes = props.stations.map(s => s.latitude)
    const longitudes = props.stations.map(s => s.longitude)
    return L.latLngBounds(
      L.latLng(Math.min(...latitudes), Math.min(...longitudes)),
      L.latLng(Math.max(...latitudes), Math.max(...longitudes)),
    )
  }
  else {
    if (!props.selectedStations.length)
      return null
    const latitudes = props.selectedStations.map(s => s.latitude)
    const longitudes = props.selectedStations.map(s => s.longitude)
    return L.latLngBounds(
      L.latLng(Math.min(...latitudes), Math.min(...longitudes)),
      L.latLng(Math.max(...latitudes), Math.max(...longitudes)),
    )
  }
})

// Compute whether current map bounds are approximately equal to selected stations bounds
const isCenteredOnSelected = computed(() => {
  // depend on boundsVersion to re-evaluate when map moves
  const _boundsVersion = boundsVersion.value
  if (!map.value?.leafletObject || !mapBounds.value || !props.selectedStations?.length)
    return false
  const currentBounds = map.value.leafletObject.getBounds()
  const selectedBounds = mapBounds.value
  // small tolerance for floating point differences
  const tol = 1e-6
  return Math.abs(currentBounds.getWest() - selectedBounds.getWest()) < tol
    && Math.abs(currentBounds.getEast() - selectedBounds.getEast()) < tol
    && Math.abs(currentBounds.getNorth() - selectedBounds.getNorth()) < tol
    && Math.abs(currentBounds.getSouth() - selectedBounds.getSouth()) < tol
})

async function createMarkers() {
  if (!map.value?.leafletObject)
    return
  if (!props.stations.length)
    return
  if (markerClusterGroup) {
    map.value.leafletObject.removeLayer(markerClusterGroup)
    markerClusterGroup = null
    markersMap.clear()
  }
  const result = await useLMarkerCluster({
    leafletObject: map.value.leafletObject,
    markers: props.stations.map(station => ({
      name: station.name,
      lat: station.latitude,
      lng: station.longitude,
      options: {
        title: `${station.name} (ID: ${station.station_id}, ${station.state})`,
      },
    })),
  })
  markerClusterGroup = result.markerCluster
  result.markers.forEach((marker, index) => {
    const station = props.stations[index]
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
  // update label when user pans/zooms
  if (map.value?.leafletObject) {
    map.value.leafletObject.on('moveend', () => {
      // Increment boundsVersion to trigger recomputation of isCenteredOnSelected
      boundsVersion.value++
    })
  }
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
        :label="isCenteredOnSelected ? 'Center on all stations' : (props.selectedStations.length === 1 ? 'Center on selected station' : 'Center on selected stations')"
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
