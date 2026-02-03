<script setup lang="ts">
import type { StationSelectionState } from '~/types/station-selection-state.type'
import { computed, ref } from 'vue'
import StationSelection from '~/components/StationSelection.vue'

// History is only available for DWD observation
const provider = 'dwd'
const network = 'observation'

const resolution = ref<string>('')
const dataset = ref<string>('')

const stationSelectionState = ref<StationSelectionState>({
  mode: 'station',
  selection: {
    stations: [],
  },
  interpolation: {
    source: 'station',
  },
  dateRange: {},
})

const availableSections = ['name', 'parameter', 'device', 'geography', 'missing_data']
const selectedSections = ref<Array<string>>([])

// Track last fetched parameters to prevent redundant fetches
const lastFetchedParams = ref<{
  resolution: string
  dataset: string
  stationIds: string
  sections: string
} | null>(null)

// Fetch available datasets for DWD observation
const { data: datasetsData, refresh: refreshDatasets } = useFetch<Record<string, Record<string, any>>>('/api/coverage', {
  query: { provider, network },
  immediate: false,
  default: () => ({}),
})

// Fetch the data on component mount
onMounted(() => {
  refreshDatasets()
})

const resolutions = computed(() => {
  if (!datasetsData.value)
    return []
  return Object.keys(datasetsData.value).sort()
})

const datasets = computed(() => {
  if (!datasetsData.value || !resolution.value)
    return []
  return Object.keys(datasetsData.value[resolution.value] || {}).sort()
})

// Watch resolution changes and reset dataset
watch(resolution, () => {
  dataset.value = ''
  stationSelectionState.value.selection.stations = []
})

// Watch dataset changes and reset stations
watch(dataset, () => {
  stationSelectionState.value.selection.stations = []
})

// Compute parameters string from selection
const parametersString = computed(() => {
  if (!resolution.value || !dataset.value) {
    return undefined
  }
  return `${resolution.value}/${dataset.value}`
})

// Compute station IDs from selection
const stationIds = computed(() => {
  const stations = stationSelectionState.value.selection?.stations || []
  return stations.map(s => s.station_id).join(',')
})

// Helper function to extract station_id from history object
function getStationId(history: any): string | null {
  // Try to get station_id from different sections
  if (history.parameter && history.parameter.length > 0 && history.parameter[0].station_id) {
    return history.parameter[0].station_id
  }
  if (history.device && history.device.length > 0 && history.device[0].station_id) {
    return history.device[0].station_id
  }
  if (history.geography && history.geography.length > 0 && history.geography[0].station_id) {
    return history.geography[0].station_id
  }
  return null
}

// Helper function to extract station_name from history object
function getStationName(history: any): string | null {
  if (history.name && history.name.station && history.name.station.length > 0) {
    return history.name.station[0].name || null
  }
  if (history.parameter && history.parameter.length > 0 && history.parameter[0].station_name) {
    return history.parameter[0].station_name
  }
  if (history.device && history.device.length > 0 && history.device[0].station_name) {
    return history.device[0].station_name
  }
  if (history.geography && history.geography.length > 0 && history.geography[0].station_name) {
    return history.geography[0].station_name
  }
  return null
}

// Parameter selection for StationSelection component
// Note: For history, we pass a dummy parameter to trigger station fetch
const parameterSelection = computed(() => ({
  provider,
  network,
  resolution: resolution.value as Resolution,
  dataset: dataset.value,
  parameters: ['_all'], // Dummy parameter to trigger station fetch
}))

// Check if we have minimum required params
const canFetch = computed(() => {
  const hasParameters = resolution.value && dataset.value
  const hasStations = stationIds.value.length > 0

  if (!hasParameters || !hasStations) {
    return false
  }

  // Check if parameters have changed since last fetch
  if (lastFetchedParams.value) {
    const currentParams = {
      resolution: resolution.value,
      dataset: dataset.value,
      stationIds: stationIds.value,
      sections: [...selectedSections.value].sort().join(','),
    }

    const unchanged
      = currentParams.resolution === lastFetchedParams.value.resolution
        && currentParams.dataset === lastFetchedParams.value.dataset
        && currentParams.stationIds === lastFetchedParams.value.stationIds
        && currentParams.sections === lastFetchedParams.value.sections

    if (unchanged) {
      return false
    }
  }

  return true
})

// lazy fetch - trigger with refresh()
const { data, pending, refresh, error } = useFetch<any>('/api/history', {
  lazy: true,
  immediate: false,
  watch: false, // Prevent automatic refetch when query changes
  query: computed(() => ({
    provider,
    network,
    parameters: parametersString.value,
    station: stationIds.value || undefined,
    sections: selectedSections.value.length ? selectedSections.value : undefined,
  })),
  default: () => ({ histories: [] }),
})

function run() {
  if (!canFetch.value) {
    return
  }
  // Store current parameters
  lastFetchedParams.value = {
    resolution: resolution.value,
    dataset: dataset.value,
    stationIds: stationIds.value,
    sections: selectedSections.value.sort().join(','),
  }
  // trigger fetch
  refresh()
}

function clear() {
  resolution.value = ''
  dataset.value = ''
  selectedSections.value = []
  stationSelectionState.value.selection.stations = []
  lastFetchedParams.value = null
}
</script>

<template>
  <UContainer class="mx-auto max-w-3xl px-4 py-6">
    <div class="text-center mb-8">
      <h1 class="text-4xl font-bold mb-4">
        Station History
      </h1>
      <p class="text-gray-600 dark:text-gray-400">
        Retrieve station history like name, operator, devices and parameters.
      </p>
    </div>

    <UCard class="mb-6">
      <template #header>
        <h2 class="text-lg font-semibold">
          Request
        </h2>
      </template>
      <div class="space-y-6 p-4">
        <div>
          <h3 class="text-sm font-semibold mb-3">
            Dataset Selection
          </h3>
          <p class="text-xs text-gray-500 mb-3">
            History is available for DWD Observation datasets only
          </p>
          <div class="space-y-4">
            <div class="grid grid-cols-2 gap-4">
              <UFormField label="Provider" required class="w-full">
                <UInput
                  :model-value="provider"
                  disabled
                  placeholder="Provider"
                  class="w-full"
                />
              </UFormField>
              <UFormField label="Network" required class="w-full">
                <UInput
                  :model-value="network"
                  disabled
                  placeholder="Network"
                  class="w-full"
                />
              </UFormField>
            </div>
            <UFormField label="Resolution" required class="w-full">
              <USelect
                v-model="resolution"
                :items="resolutions"
                placeholder="Select resolution"
                class="w-full"
              />
            </UFormField>
            <UFormField label="Dataset" required :disabled="!resolution" class="w-full">
              <USelect
                v-model="dataset"
                :items="datasets"
                placeholder="Select dataset"
                :disabled="!resolution"
                class="w-full"
              />
            </UFormField>
          </div>
        </div>

        <UDivider />

        <div>
          <h3 class="text-sm font-semibold mb-3">
            Station Selection
          </h3>
          <div v-if="resolution && dataset">
            <StationSelection
              v-model="stationSelectionState.selection"
              :parameter-selection="parameterSelection"
              :multiple="true"
            />
          </div>
          <div v-else class="text-sm text-gray-500">
            Please select resolution and dataset first
          </div>
        </div>

        <UDivider />

        <div>
          <h3 class="text-sm font-semibold mb-3">
            History Sections (optional)
          </h3>
          <USelectMenu
            v-model="selectedSections"
            :items="availableSections"
            multiple
            placeholder="Select sections to include"
            class="w-full"
          />
        </div>

        <UDivider />

        <div class="flex flex-col sm:flex-row gap-2">
          <UButton label="Fetch" color="primary" :disabled="!canFetch" class="w-full" @click="run" />
          <UButton label="Clear" variant="outline" class="w-full" @click="clear" />
        </div>

        <div v-if="pending" class="text-sm text-gray-600 dark:text-gray-400">
          Loading...
        </div>
        <div v-if="error" class="text-sm text-red-600">
          Error: {{ error.message ?? error }}
        </div>
      </div>
    </UCard>

    <UCard>
      <template #header>
        <div class="flex items-center justify-between">
          <h2 class="text-lg font-semibold">
            Results
          </h2>
        </div>
      </template>

      <div class="p-4">
        <div v-if="!data || (data.histories && data.histories.length === 0)" class="text-sm text-gray-600">
          No histories loaded. Click "Fetch" to query the backend.
        </div>
        <div v-else class="space-y-6">
          <!-- Selected Stations Overview -->
          <div v-if="stationSelectionState.selection.stations.length > 0">
            <h3 class="text-md font-semibold mb-3">
              Selected Stations
            </h3>
            <div class="overflow-x-auto">
              <table class="min-w-full divide-y divide-gray-200 dark:divide-gray-700">
                <thead class="bg-gray-50 dark:bg-gray-800">
                  <tr>
                    <th class="px-4 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">
                      Station ID
                    </th>
                    <th class="px-4 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">
                      Name
                    </th>
                    <th class="px-4 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">
                      Latitude
                    </th>
                    <th class="px-4 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">
                      Longitude
                    </th>
                    <th class="px-4 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">
                      Height (m)
                    </th>
                    <th class="px-4 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">
                      State
                    </th>
                  </tr>
                </thead>
                <tbody class="bg-white dark:bg-gray-900 divide-y divide-gray-200 dark:divide-gray-700">
                  <tr v-for="station in stationSelectionState.selection.stations" :key="station.station_id">
                    <td class="px-4 py-2 text-sm font-medium">
                      {{ station.station_id }}
                    </td>
                    <td class="px-4 py-2 text-sm">
                      {{ station.name || '-' }}
                    </td>
                    <td class="px-4 py-2 text-sm">
                      {{ station.latitude != null ? station.latitude.toFixed(4) : '-' }}
                    </td>
                    <td class="px-4 py-2 text-sm">
                      {{ station.longitude != null ? station.longitude.toFixed(4) : '-' }}
                    </td>
                    <td class="px-4 py-2 text-sm">
                      {{ station.height != null ? station.height.toFixed(1) : '-' }}
                    </td>
                    <td class="px-4 py-2 text-sm">
                      {{ station.state || '-' }}
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>

          <!-- History Data by Station -->
          <div v-if="data.histories && data.histories.length > 0">
            <h3 class="text-md font-semibold mb-3">
              Station History
            </h3>
            <div class="space-y-4">
              <div v-for="(history, idx) in data.histories" :key="idx">
                <UCard>
                  <!-- Station Info Card Header displays basic station info -->
                  <template #header>
                    <div class="flex items-center justify-between">
                      <h3 class="font-semibold">
                        Station ID: {{ getStationId(history) }}
                        <span
                          v-if="getStationName(history)"
                          class="text-sm text-gray-600 dark:text-gray-400 font-normal ml-2"
                        >
                          {{ getStationName(history) }}
                        </span>
                      </h3>
                    </div>
                  </template>

                  <!-- Station Basic Info Table -->
                  <div class="mb-6">
                    <div class="overflow-x-auto">
                      <table class="min-w-full divide-y divide-gray-200 dark:divide-gray-700">
                        <!--                        <tbody class="bg-white dark:bg-gray-900"> -->
                        <tr v-if="getStationName(history)" class="border-b border-gray-200 dark:border-gray-700">
                          <td class="px-4 py-2 text-sm font-medium text-gray-500 dark:text-gray-400">
                            Station Name
                          </td>
                          <td class="px-4 py-2 text-sm">
                            {{ getStationName(history) }}
                          </td>
                        </tr>
                        <tr v-if="history.latitude != null" class="border-b border-gray-200 dark:border-gray-700">
                          <td class="px-4 py-2 text-sm font-medium text-gray-500 dark:text-gray-400">
                            Latitude
                          </td>
                          <td class="px-4 py-2 text-sm">
                            {{ history.latitude }}
                          </td>
                        </tr>
                        <tr v-if="history.longitude != null" class="border-b border-gray-200 dark:border-gray-700">
                          <td class="px-4 py-2 text-sm font-medium text-gray-500 dark:text-gray-400">
                            Longitude
                          </td>
                          <td class="px-4 py-2 text-sm">
                            {{ history.longitude }}
                          </td>
                        </tr>
                        <tr v-if="history.station_height != null">
                          <td class="px-4 py-2 text-sm font-medium text-gray-500 dark:text-gray-400">
                            Station Height
                          </td>
                          <td class="px-4 py-2 text-sm">
                            {{ history.station_height }} m
                          </td>
                        </tr>
                        <!--                        </tbody> -->
                      </table>
                    </div>
                  </div>

                  <!-- Name History -->
                  <div
                    v-if="history.name && (history.name.station?.length || history.name.operator?.length)"
                    class="mb-6"
                  >
                    <UCollapsible>
                      <UButton
                        label="Name History"
                        variant="ghost"
                        trailing-icon="i-lucide-chevron-down"
                        block
                        class="mb-2"
                      />
                      <template #content>
                        <!-- Station Name History -->
                        <div v-if="history.name.station?.length" class="mb-4">
                          <h4 class="text-sm font-semibold mb-2 text-gray-700 dark:text-gray-300">
                            Station Names
                          </h4>
                          <div class="overflow-x-auto">
                            <table class="min-w-full divide-y divide-gray-200 dark:divide-gray-700">
                              <thead class="bg-gray-50 dark:bg-gray-800">
                                <tr>
                                  <th class="px-4 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">
                                    Start Date
                                  </th>
                                  <th class="px-4 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">
                                    End Date
                                  </th>
                                  <th class="px-4 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">
                                    Station Name
                                  </th>
                                </tr>
                              </thead>
                              <tbody class="bg-white dark:bg-gray-900 divide-y divide-gray-200 dark:divide-gray-700">
                                <tr v-for="(entry, i) in history.name.station" :key="i">
                                  <td class="px-4 py-2 text-sm">
                                    {{ entry.start_date || '-' }}
                                  </td>
                                  <td class="px-4 py-2 text-sm">
                                    {{ entry.end_date || '-' }}
                                  </td>
                                  <td class="px-4 py-2 text-sm">
                                    {{ entry.station_name || '-' }}
                                  </td>
                                </tr>
                              </tbody>
                            </table>
                          </div>
                        </div>

                        <!-- Operator Name History -->
                        <div v-if="history.name.operator?.length">
                          <h4 class="text-sm font-semibold mb-2 text-gray-700 dark:text-gray-300">
                            Operator Names
                          </h4>
                          <div class="overflow-x-auto">
                            <table class="min-w-full divide-y divide-gray-200 dark:divide-gray-700">
                              <thead class="bg-gray-50 dark:bg-gray-800">
                                <tr>
                                  <th class="px-4 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">
                                    Start Date
                                  </th>
                                  <th class="px-4 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">
                                    End Date
                                  </th>
                                  <th class="px-4 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">
                                    Operator Name
                                  </th>
                                </tr>
                              </thead>
                              <tbody class="bg-white dark:bg-gray-900 divide-y divide-gray-200 dark:divide-gray-700">
                                <tr v-for="(entry, i) in history.name.operator" :key="i">
                                  <td class="px-4 py-2 text-sm">
                                    {{ entry.start_date || '-' }}
                                  </td>
                                  <td class="px-4 py-2 text-sm">
                                    {{ entry.end_date || '-' }}
                                  </td>
                                  <td class="px-4 py-2 text-sm">
                                    {{ entry.operator_name || '-' }}
                                  </td>
                                </tr>
                              </tbody>
                            </table>
                          </div>
                        </div>
                      </template>
                    </UCollapsible>
                  </div>

                  <!-- Parameter History -->
                  <div v-if="history.parameter?.length" class="mb-6">
                    <UCollapsible>
                      <UButton
                        label="Parameter History"
                        variant="ghost"
                        trailing-icon="i-lucide-chevron-down"
                        block
                        class="mb-2"
                      />
                      <template #content>
                        <div class="overflow-x-auto">
                          <table class="min-w-full divide-y divide-gray-200 dark:divide-gray-700">
                            <thead class="bg-gray-50 dark:bg-gray-800">
                              <tr>
                                <th class="px-4 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">
                                  Start Date
                                </th>
                                <th class="px-4 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">
                                  End Date
                                </th>
                                <th class="px-4 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">
                                  Parameter
                                </th>
                                <th class="px-4 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">
                                  Description
                                </th>
                                <th class="px-4 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">
                                  Unit
                                </th>
                              </tr>
                            </thead>
                            <tbody class="bg-white dark:bg-gray-900 divide-y divide-gray-200 dark:divide-gray-700">
                              <tr v-for="(entry, i) in history.parameter" :key="i">
                                <td class="px-4 py-2 text-sm">
                                  {{ entry.start_date || '-' }}
                                </td>
                                <td class="px-4 py-2 text-sm">
                                  {{ entry.end_date || '-' }}
                                </td>
                                <td class="px-4 py-2 text-sm">
                                  {{ entry.parameter || '-' }}
                                </td>
                                <td class="px-4 py-2 text-sm">
                                  {{ entry.description || '-' }}
                                </td>
                                <td class="px-4 py-2 text-sm">
                                  {{ entry.unit || '-' }}
                                </td>
                              </tr>
                            </tbody>
                          </table>
                        </div>
                      </template>
                    </UCollapsible>
                  </div>

                  <!-- Device History -->
                  <div v-if="history.device?.length" class="mb-6">
                    <UCollapsible>
                      <UButton
                        label="Device History"
                        variant="ghost"
                        trailing-icon="i-lucide-chevron-down"
                        block
                        class="mb-2"
                      />
                      <template #content>
                        <div class="overflow-x-auto">
                          <table class="min-w-full divide-y divide-gray-200 dark:divide-gray-700">
                            <thead class="bg-gray-50 dark:bg-gray-800">
                              <tr>
                                <th class="px-4 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">
                                  Start Date
                                </th>
                                <th class="px-4 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">
                                  End Date
                                </th>
                                <th class="px-4 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">
                                  Device Type
                                </th>
                                <th class="px-4 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">
                                  Device Height
                                </th>
                                <th class="px-4 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">
                                  Method
                                </th>
                              </tr>
                            </thead>
                            <tbody class="bg-white dark:bg-gray-900 divide-y divide-gray-200 dark:divide-gray-700">
                              <tr v-for="(entry, i) in history.device" :key="i">
                                <td class="px-4 py-2 text-sm">
                                  {{ entry.start_date || '-' }}
                                </td>
                                <td class="px-4 py-2 text-sm">
                                  {{ entry.end_date || '-' }}
                                </td>
                                <td class="px-4 py-2 text-sm">
                                  {{ entry.device_type || '-' }}
                                </td>
                                <td class="px-4 py-2 text-sm">
                                  {{ entry.device_height || '-' }}
                                </td>
                                <td class="px-4 py-2 text-sm">
                                  {{ entry.method || '-' }}
                                </td>
                              </tr>
                            </tbody>
                          </table>
                        </div>
                      </template>
                    </UCollapsible>
                  </div>

                  <!-- Geography History -->
                  <div v-if="history.geography?.length" class="mb-6">
                    <UCollapsible>
                      <UButton
                        label="Geography History"
                        variant="ghost"
                        trailing-icon="i-lucide-chevron-down"
                        block
                        class="mb-2"
                      />
                      <template #content>
                        <div class="overflow-x-auto">
                          <table class="min-w-full divide-y divide-gray-200 dark:divide-gray-700">
                            <thead class="bg-gray-50 dark:bg-gray-800">
                              <tr>
                                <th class="px-4 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">
                                  Start Date
                                </th>
                                <th class="px-4 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">
                                  End Date
                                </th>
                                <th class="px-4 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">
                                  Latitude
                                </th>
                                <th class="px-4 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">
                                  Longitude
                                </th>
                                <th class="px-4 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">
                                  Station Height
                                </th>
                              </tr>
                            </thead>
                            <tbody class="bg-white dark:bg-gray-900 divide-y divide-gray-200 dark:divide-gray-700">
                              <tr v-for="(entry, i) in history.geography" :key="i">
                                <td class="px-4 py-2 text-sm">
                                  {{ entry.start_date || '-' }}
                                </td>
                                <td class="px-4 py-2 text-sm">
                                  {{ entry.end_date || '-' }}
                                </td>
                                <td class="px-4 py-2 text-sm">
                                  {{ entry.latitude || '-' }}
                                </td>
                                <td class="px-4 py-2 text-sm">
                                  {{ entry.longitude || '-' }}
                                </td>
                                <td class="px-4 py-2 text-sm">
                                  {{ entry.station_height || '-' }}
                                </td>
                              </tr>
                            </tbody>
                          </table>
                        </div>
                      </template>
                    </UCollapsible>
                  </div>

                  <!-- Missing Data History -->
                  <div
                    v-if="history.missing_data && (history.missing_data.summary?.length || history.missing_data.periods?.length)"
                  >
                    <UCollapsible>
                      <UButton
                        label="Missing Data History"
                        variant="ghost"
                        trailing-icon="i-lucide-chevron-down"
                        block
                        class="mb-2"
                      />
                      <template #content>
                        <!-- Summary -->
                        <div v-if="history.missing_data.summary?.length" class="mb-4">
                          <h4 class="text-sm font-semibold mb-2 text-gray-700 dark:text-gray-300">
                            Summary
                          </h4>
                          <div class="overflow-x-auto">
                            <table class="min-w-full divide-y divide-gray-200 dark:divide-gray-700">
                              <thead class="bg-gray-50 dark:bg-gray-800">
                                <tr>
                                  <th class="px-4 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">
                                    Start Date
                                  </th>
                                  <th class="px-4 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">
                                    End Date
                                  </th>
                                  <th class="px-4 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">
                                    Parameter
                                  </th>
                                  <th class="px-4 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">
                                    Missing Count
                                  </th>
                                </tr>
                              </thead>
                              <tbody class="bg-white dark:bg-gray-900 divide-y divide-gray-200 dark:divide-gray-700">
                                <tr v-for="(entry, i) in history.missing_data.summary" :key="i">
                                  <td class="px-4 py-2 text-sm">
                                    {{ entry.start_date || '-' }}
                                  </td>
                                  <td class="px-4 py-2 text-sm">
                                    {{ entry.end_date || '-' }}
                                  </td>
                                  <td class="px-4 py-2 text-sm">
                                    {{ entry.parameter || '-' }}
                                  </td>
                                  <td class="px-4 py-2 text-sm">
                                    {{ entry.missing_count || '-' }}
                                  </td>
                                </tr>
                              </tbody>
                            </table>
                          </div>
                        </div>

                        <!-- Periods -->
                        <div v-if="history.missing_data.periods?.length">
                          <h4 class="text-sm font-semibold mb-2 text-gray-700 dark:text-gray-300">
                            Periods
                          </h4>
                          <div class="overflow-x-auto">
                            <table class="min-w-full divide-y divide-gray-200 dark:divide-gray-700">
                              <thead class="bg-gray-50 dark:bg-gray-800">
                                <tr>
                                  <th class="px-4 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">
                                    Start Date
                                  </th>
                                  <th class="px-4 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">
                                    End Date
                                  </th>
                                  <th class="px-4 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">
                                    Parameter
                                  </th>
                                  <th class="px-4 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">
                                    Missing Count
                                  </th>
                                </tr>
                              </thead>
                              <tbody class="bg-white dark:bg-gray-900 divide-y divide-gray-200 dark:divide-gray-700">
                                <tr v-for="(entry, i) in history.missing_data.periods" :key="i">
                                  <td class="px-4 py-2 text-sm">
                                    {{ entry.start_date || '-' }}
                                  </td>
                                  <td class="px-4 py-2 text-sm">
                                    {{ entry.end_date || '-' }}
                                  </td>
                                  <td class="px-4 py-2 text-sm">
                                    {{ entry.parameter || '-' }}
                                  </td>
                                  <td class="px-4 py-2 text-sm">
                                    {{ entry.missing_count || '-' }}
                                  </td>
                                </tr>
                              </tbody>
                            </table>
                          </div>
                        </div>
                      </template>
                    </UCollapsible>
                  </div>
                </UCard>
              </div>
            </div>
          </div>
        </div>
      </div>
    </UCard>
  </UContainer>
</template>
