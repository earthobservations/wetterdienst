<script setup lang="ts">
import * as L from 'leaflet'

const map = ref(null) as any
let markerClusterGroup: any = null

interface Station {
  station_id: string
  name: string
  state: string
  latitude: number
  longitude: number
}

interface Props {
  stations: Station[]
  selectedStations: Station[]
}

const props = defineProps<Props>()
const emit = defineEmits<{
  (e: 'toggle', station: Station): void
}>()

// Check if a station is selected
const isSelected = (stationId: string) => {
  return props.selectedStations.some(s => s.station_id === stationId)
}

const centerOfGermany: [number, number] = [51.1657, 10.4515]

// Center of Germany
const mapCenter = computed<[number, number]>(() => {
  const list = props.stations
  if (!list.length) return centerOfGermany
  const latSum = list.reduce((a, s) => a + s.latitude, 0)
  const lngSum = list.reduce((a, s) => a + s.longitude, 0)
  return [latSum / list.length, lngSum / list.length]
})

const createMarkers = async () => {
  if (!map.value?.leafletObject) return

  // Remove existing cluster if it exists
  if (markerClusterGroup) {
    map.value.leafletObject.removeLayer(markerClusterGroup)
  }

  const result = await useLMarkerCluster({
    leafletObject: map.value.leafletObject,
    markers: props.stations.map((station) => {
      const isStationSelected = isSelected(station.station_id)

      // Create custom icon for selected stations
      const markerOptions: any = {
        title: `${station.name} (ID: ${station.station_id}, ${station.state})`
      }

      if (isStationSelected) {
        // Use green marker for selected stations
        markerOptions.icon = L.icon({
          iconUrl: 'https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-2x-green.png',
          shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-shadow.png',
          iconSize: [25, 41],
          iconAnchor: [12, 41],
          popupAnchor: [1, -34],
          shadowSize: [41, 41]
        })
      }

      return {
        name: station.name,
        lat: station.latitude,
        lng: station.longitude,
        options: markerOptions
      }
    })
  })

  markerClusterGroup = result.markerCluster

  // Add click handlers to each marker for toggle functionality
  result.markers.forEach((marker, index) => {
    const station = props.stations[index]
    if (station) {
      marker.on('click', () => {
        emit('toggle', station)
      })
    }
  })
}

// When the map is ready, initialize clustering
const onMapReady = async () => {
  await createMarkers()
}

// Watch for selection changes and regenerate markers
watch(() => props.selectedStations, async () => {
  await createMarkers()
}, { deep: true })

</script>

<template>
  <div style="height:100vh; width:100vw">
    <LMap
      ref="map"
      :zoom="6"
      :max-zoom="18"
      :center="mapCenter"
      :use-global-leaflet="true"
      @ready="onMapReady"
    >
      <LTileLayer
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        attribution="&copy; <a href='https://www.openstreetmap.org/'>OpenStreetMap</a> contributors"
        layer-type="base"
        name="OpenStreetMap"
      />
<!--       <LMarker-->
<!--         v-for="station in stations"-->
<!--         :key="station.station_id"-->
<!--         :lat-lng="[station.latitude, station.longitude]"-->
<!--         @click="emit('toggle', station)"-->
<!--       >-->
<!--         <LTooltip>-->
<!--           <div class="text-sm">-->
<!--             <div class="font-semibold">{{ station.name }}</div>-->
<!--             <div>ID: {{ station.station_id }}</div>-->
<!--             <div>{{ station.state }}</div>-->
<!--             <div v-if="isSelected(station.station_id)" class="text-blue-600 font-medium mt-1">-->
<!--               ✓ Selected-->
<!--             </div>-->
<!--           </div>-->
<!--         </LTooltip>-->
<!--       </LMarker>-->
    </LMap>
  </div>
</template>

<style>
@import 'leaflet.markercluster/dist/MarkerCluster.css';
@import 'leaflet.markercluster/dist/MarkerCluster.Default.css';
</style>