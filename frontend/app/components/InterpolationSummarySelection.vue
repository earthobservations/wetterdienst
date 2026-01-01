<script setup lang="ts">
import type { ParameterSelectionState } from '~/types/parameter-selection-state.type'
import type { InterpolationSelection, InterpolationSource } from '~/types/station-selection-state.type'

const props = defineProps<{
  parameterSelection: ParameterSelectionState['selection']
}>()

const modelValue = defineModel<InterpolationSelection>({ required: true })

const sourceOptions = [
  { value: 'manual', label: 'Manual coordinates', icon: 'i-lucide-pencil' },
  { value: 'station', label: 'From station', icon: 'i-lucide-map-pin' },
] as const

// For manual input
const latitudeInput = ref<string>(modelValue.value.latitude?.toString() ?? '')
const longitudeInput = ref<string>(modelValue.value.longitude?.toString() ?? '')

// Watch inputs and update model
watch([latitudeInput, longitudeInput], ([lat, lon]) => {
  const latNum = Number.parseFloat(lat)
  const lonNum = Number.parseFloat(lon)
  modelValue.value = {
    ...modelValue.value,
    latitude: Number.isNaN(latNum) ? undefined : latNum,
    longitude: Number.isNaN(lonNum) ? undefined : lonNum,
  }
})

// For station selection
const selectedStation = ref<Station | undefined>(modelValue.value.station)

watch(selectedStation, (station) => {
  modelValue.value = {
    ...modelValue.value,
    station,
    latitude: station?.latitude,
    longitude: station?.longitude,
  }
})

// Fetch stations for station source
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

const stationItems = computed(() =>
  allStations.value.map(station => ({
    label: `${station.name} (${station.station_id})`,
    value: station.station_id,
  })),
)

const selectedStationItem = computed({
  get: () => selectedStation.value
    ? {
        label: `${selectedStation.value.name} (${selectedStation.value.station_id})`,
        value: selectedStation.value.station_id,
      }
    : undefined,
  set: (item: { label: string, value: string } | undefined) => {
    selectedStation.value = item ? allStations.value.find(s => s.station_id === item.value) : undefined
  },
})

watch(() => props.parameterSelection, () => {
  if (props.parameterSelection.parameters?.length) {
    refreshStations()
  }
}, { deep: true, immediate: true })

function setSource(source: InterpolationSource) {
  modelValue.value = {
    ...modelValue.value,
    source,
  }
}

// Display coordinates
const displayCoords = computed(() => {
  if (modelValue.value.latitude !== undefined && modelValue.value.longitude !== undefined) {
    return `${modelValue.value.latitude.toFixed(4)}, ${modelValue.value.longitude.toFixed(4)}`
  }
  return null
})
</script>

<template>
  <div class="space-y-4">
    <div class="flex items-center gap-2">
      <span class="text-sm text-gray-500">Source:</span>
      <UFieldGroup>
        <UButton
          v-for="option in sourceOptions"
          :key="option.value"
          :icon="option.icon"
          :label="option.label"
          color="neutral"
          :variant="modelValue.source === option.value ? 'subtle' : 'ghost'"
          size="xs"
          @click="setSource(option.value)"
        />
      </UFieldGroup>
    </div>

    <div v-if="modelValue.source === 'manual'" class="flex gap-4">
      <UFormField label="Latitude" class="flex-1">
        <UInput
          v-model="latitudeInput"
          type="number"
          step="0.0001"
          placeholder="e.g. 52.5200"
          class="w-full"
        />
      </UFormField>
      <UFormField label="Longitude" class="flex-1">
        <UInput
          v-model="longitudeInput"
          type="number"
          step="0.0001"
          placeholder="e.g. 13.4050"
          class="w-full"
        />
      </UFormField>
    </div>

    <div v-else>
      <UFormField label="Select station for coordinates">
        <USelectMenu
          v-if="!stationsPending"
          v-model="selectedStationItem"
          :items="stationItems"
          placeholder="Select a station"
          searchable
          class="w-full"
        />
        <div v-else class="text-sm text-gray-500">
          Loading stations...
        </div>
      </UFormField>
    </div>

    <div v-if="displayCoords" class="text-sm text-gray-500">
      Interpolation coordinates: {{ displayCoords }}
    </div>
  </div>
</template>
