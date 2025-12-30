<script setup lang="ts">
import type { StationsResponse, Station  } from '#types/api.types'
import type { ParameterSelectionState } from '~/types/parameter-selection-state.type'

declare const L: typeof import('leaflet')

const props = defineProps<{
  parameterSelection: ParameterSelectionState['selection']
  initialStationIds?: string[]
}>()
const emit = defineEmits(['update:modelValue'])

const selectedStations = ref<Station[]>([])

const map = ref(null) as any
let markerClusterGroup: any = null
const markersMap: Map<string, any> = new Map() // station_id -> marker

const showMap = ref(true)
const centerOnSelectedStations = ref(false)

watch(selectedStations, () => {
  emit('update:modelValue', {
    stations: [...selectedStations.value],
  })
})

// Track whether we've already restored initial stations
const hasRestoredInitialStations = ref(false)

const { data: stationsData, pending: stationsPending, refresh: refreshStations } = useFetch<StationsResponse>(
  '/api/stations',
  {
    query: computed(() => ({
      provider: props.parameterSelection.provider,
      network: props.parameterSelection.network,
      parameters: `${props.parameterSelection.resolution}/${props.parameterSelection.dataset}`,
      all: 'true',
    })),
    immediate: false,
    default: () => ({ stations: [] }),
  },
)

const allStations = computed(() => stationsData.value?.stations ?? [])

// Restore initial stations when stations data is loaded
watch(allStations, (stations) => {
  if (hasRestoredInitialStations.value)
    return
  if (!stations.length)
    return
  if (!props.initialStationIds?.length)
    return

  // Find stations matching the initial IDs
  const restoredStations = props.initialStationIds
    .map(id => stations.find(s => s.station_id === id))
    .filter((s): s is Station => s !== undefined)
    .sort((a, b) => a.station_id.localeCompare(b.station_id))

  if (restoredStations.length > 0) {
    selectedStations.value = restoredStations
  }
  hasRestoredInitialStations.value = true
})

watch(() => props.parameterSelection, (ps) => {
  if (!ps.parameters?.length) {
    // No parameters selected, clear stations data
    stationsData.value = { stations: [] }
    selectedStations.value = []
    return
  }
  // Clear selected stations when parameters change (but not on initial load)
  if (hasRestoredInitialStations.value) {
    selectedStations.value = []
  }
  // Refresh stations data
  refreshStations()
}, { deep: true, immediate: true })

// Items for the select menu
const stationItems = computed(() =>
  allStations.value.map(station => ({
    label: `${station.name} (ID: ${station.station_id}, ${station.state})`,
    value: station.station_id,
  })),
)

// Bridge between Station[] and item objects
const selectedItems = computed({
  get: () => selectedStations.value.map(s => ({
    label: `${s.name} (ID: ${s.station_id}, ${s.state})`,
    value: s.station_id,
  })),
  set: (items: { label: string, value: string }[]) => {
    selectedStations.value = items
      .map(item => allStations.value.find(s => s.station_id === item.value))
      .filter((s): s is Station => s !== undefined)
      .sort((a, b) => a.station_id.localeCompare(b.station_id))
  },
})

function removeStation(station: Station) {
  const index = selectedStations.value.findIndex(s => s.station_id === station.station_id)
  if (index >= 0) {
    selectedStations.value.splice(index, 1)
  }
}

// map features
// Check if a station is selected
function isSelected(stationId: string) {
  return selectedStations.value.some(s => s.station_id === stationId)
}

const mapCenter = computed<[number, number]>(() => {
  if (!allStations.value.length)
    return [51.1657, 10.4515] // Center of Germany
  const latSum = allStations.value.reduce((a, s) => a + s.latitude, 0)
  const lngSum = allStations.value.reduce((a, s) => a + s.longitude, 0)
  return [latSum / allStations.value.length, lngSum / allStations.value.length]
})

const mapBounds = computed(() => {
  if (!allStations.value.length)
    return null
  if (!centerOnSelectedStations.value) {
    const latitudes = allStations.value.map(s => s.latitude)
    const longitudes = allStations.value.map(s => s.longitude)
    return L.latLngBounds(
      L.latLng(Math.min(...latitudes), Math.min(...longitudes)),
      L.latLng(Math.max(...latitudes), Math.max(...longitudes)),
    )
  }
  else {
    if (!selectedStations.value.length)
      return null
    const latitudes = selectedStations.value.map(s => s.latitude)
    const longitudes = selectedStations.value.map(s => s.longitude)
    return L.latLngBounds(
      L.latLng(Math.min(...latitudes), Math.min(...longitudes)),
      L.latLng(Math.max(...latitudes), Math.max(...longitudes)),
    )
  }
})

async function createMarkers() {
  if (!map.value?.leafletObject)
    return
  if (!allStations.value.length)
    return

  // Remove existing cluster if it exists
  if (markerClusterGroup) {
    map.value.leafletObject.removeLayer(markerClusterGroup)
    markerClusterGroup = null
    markersMap.clear()
  }

  const result = await useLMarkerCluster({
    leafletObject: map.value.leafletObject,
    markers: allStations.value.map(station => ({
      name: station.name,
      lat: station.latitude,
      lng: station.longitude,
      options: {
        title: `${station.name} (ID: ${station.station_id}, ${station.state})`,
      },
    })),
  })

  markerClusterGroup = result.markerCluster

  // Store markers and add click handlers
  result.markers.forEach((marker, index) => {
    const station = allStations.value[index]
    if (station) {
      markersMap.set(station.station_id, marker)
      marker.on('click', () => {
        if (isSelected(station.station_id)) {
          removeStation(station)
        }
        else {
          selectedStations.value.push(station)
        }
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

  // Refresh clusters to update display
  markerClusterGroup.refreshClusters()
}

// When the map is ready, initialize clustering
async function onMapReady() {
  await createMarkers()
  updateMarkerIcons()
  // Restore bounds if centering on selected stations
  if (centerOnSelectedStations.value && mapBounds.value) {
    map.value.leafletObject.fitBounds(mapBounds.value)
  }
}

// Watch for selection changes and update marker icons
watch(() => selectedStations, () => {
  updateMarkerIcons()
}, { deep: true })

// Watch for centerOnSelectedStations changes and fit bounds
watch(() => centerOnSelectedStations.value, () => {
  if (map.value?.leafletObject && mapBounds.value) {
    map.value.leafletObject.fitBounds(mapBounds.value)
  }
})

// Also fit bounds when selected stations change (if centering on selected)
watch(() => selectedStations.value, () => {
  if (centerOnSelectedStations.value && map.value?.leafletObject && mapBounds.value) {
    map.value.leafletObject.fitBounds(mapBounds.value)
  }
}, { deep: true })
</script>

<template>
  <div v-if="stationsPending" class="flex justify-center py-8">
    <span class="text-gray-500">Loading stations...</span>
  </div>
  <div v-else-if="!allStations?.length" class="flex justify-center py-8">
    <span class="text-gray-500">No stations found for the selected parameters</span>
  </div>
  <div v-else class="flex flex-col gap-4">
    <USelectMenu
      v-model="selectedItems"
      :items="stationItems"
      placeholder="Select stations"
      multiple
      searchable
      color="primary"
      class="w-full"
    />
    <UContainer v-if="selectedStations.length > 0" class="mt-2">
      <div class="flex items-center justify-between mb-2">
        <h4 class="text-sm font-medium">
          Selected Stations:
        </h4>
        <UButton size="xs" color="neutral" variant="ghost" @click="selectedStations = []">
          Clear all
        </UButton>
      </div>
      <div class="flex flex-wrap gap-2">
        <UBadge
          v-for="station in selectedStations"
          :key="station.station_id"
          variant="subtle"
          class="cursor-pointer"
          @click="removeStation(station)"
        >
          {{ station.name }} ({{ station.station_id }})
          <span class="ml-1">×</span>
        </UBadge>
      </div>
    </UContainer>
    <UCollapsible v-model="showMap" class="mt-4">
      <UButton
        label="Show map"
        variant="subtle"
        color="neutral"
        trailing-icon="i-lucide-chevron-down"
        block
      />
      <template #content>
        <div class="p-4 space-y-4">
          <UButton
            :label="centerOnSelectedStations ? 'Center on all stations' : 'Center on selected stations'"
            variant="subtle"
            color="neutral"
            :disabled="!selectedStations.length"
            block
            @click="centerOnSelectedStations = !centerOnSelectedStations"
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
      </template>
    </UCollapsible>
  </div>
</template>

<style>
@import 'leaflet.markercluster/dist/MarkerCluster.css';
@import 'leaflet.markercluster/dist/MarkerCluster.Default.css';
</style>
