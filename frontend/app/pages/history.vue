<script setup lang="ts">
import type { StationSelectionState } from '~/types/station-selection-state.type'
import { computed, ref } from 'vue'
import ParameterSelection from '~/components/ParameterSelection.vue'
import StationSelection from '~/components/StationSelection.vue'

const { t } = useI18n()

const route = useRoute()
const router = useRouter()

// Parameter selection state — driven by ParameterSelection component
const paramSel = ref({
  provider: route.query.provider?.toString() ?? 'dwd',
  network: route.query.network?.toString() ?? 'observation',
  resolution: route.query.resolution?.toString() ?? '',
  dataset: route.query.dataset?.toString() ?? '',
  parameters: [] as string[],
})

const provider = computed(() => paramSel.value.provider ?? '')
const network = computed(() => paramSel.value.network ?? '')
const resolution = computed(() => paramSel.value.resolution ?? '')
const dataset = computed(() => paramSel.value.dataset ?? '')

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
const selectedSections = ref<Array<string>>(
  route.query.sections ? route.query.sections.toString().split(',').filter(Boolean) : [],
)

const initialStationIds = ref<string[]>(
  route.query.stations ? route.query.stations.toString().split(',').filter(Boolean) : [],
)

const showAbout = ref(false)

// Track last fetched parameters to prevent redundant fetches
const lastFetchedParams = ref<{
  provider: string
  network: string
  resolution: string
  dataset: string
  stationIds: string
  sections: string
} | null>(null)

// Reset stations when resolution or dataset changes via ParameterSelection
watch(() => paramSel.value.resolution, () => {
  stationSelectionState.value.selection.stations = []
})
watch(() => paramSel.value.dataset, () => {
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

// Serialize current state to URL query params
function historyToQuery(): Record<string, string> {
  const q: Record<string, string> = {}
  if (provider.value)
    q.provider = provider.value
  if (network.value)
    q.network = network.value
  if (resolution.value)
    q.resolution = resolution.value
  if (dataset.value)
    q.dataset = dataset.value
  if (stationIds.value)
    q.stations = stationIds.value
  if (selectedSections.value.length)
    q.sections = selectedSections.value.join(',')
  return q
}

// Sync state → URL (replace so browser back/forward stack stays clean)
watch(
  [paramSel, () => stationIds.value, selectedSections],
  () => router.replace({ query: historyToQuery() }),
  { deep: true },
)

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

const parameterSelection = computed(() => ({
  provider: provider.value,
  network: network.value,
  resolution: resolution.value as Resolution,
  dataset: dataset.value,
  parameters: ['_all'],
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
      provider: provider.value,
      network: network.value,
      resolution: resolution.value,
      dataset: dataset.value,
      stationIds: stationIds.value,
      sections: [...selectedSections.value].sort().join(','),
    }

    const unchanged
      = currentParams.provider === lastFetchedParams.value.provider
        && currentParams.network === lastFetchedParams.value.network
        && currentParams.resolution === lastFetchedParams.value.resolution
        && currentParams.dataset === lastFetchedParams.value.dataset
        && currentParams.stationIds === lastFetchedParams.value.stationIds
        && currentParams.sections === lastFetchedParams.value.sections

    if (unchanged) {
      return false
    }
  }

  return true
})

const { data, pending, refresh, error } = useFetch<any>('/api/history', {
  lazy: true,
  immediate: false,
  watch: false,
  query: computed(() => ({
    provider: provider.value,
    network: network.value,
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
  lastFetchedParams.value = {
    provider: provider.value,
    network: network.value,
    resolution: resolution.value,
    dataset: dataset.value,
    stationIds: stationIds.value,
    sections: selectedSections.value.sort().join(','),
  }
  refresh()
}

function clear() {
  // Clear the fetched results and reset tracking
  lastFetchedParams.value = null
  data.value = { histories: [] }
}
</script>

<template>
  <UContainer class="mx-auto max-w-3xl px-4 py-6 space-y-6">
    <div class="text-center mb-8">
      <h1 class="text-3xl font-bold mb-4">
        {{ t('history.title') }}
      </h1>
      <p class="text-gray-600 dark:text-gray-400">
        {{ t('history.subtitle') }}
      </p>
    </div>

    <UCollapsible v-model="showAbout">
      <UButton
        :label="t('history.aboutButton')"
        variant="subtle"
        color="neutral"
        trailing-icon="i-lucide-chevron-down"
        block
        size="sm"
      />
      <template #content>
        <UCard>
          <p class="text-gray-600 dark:text-gray-400 mb-4">
            {{ t('history.about1') }}
          </p>
          <p class="text-gray-600 dark:text-gray-400 mb-4">
            {{ t('history.about2') }}
          </p>
          <p class="text-gray-600 dark:text-gray-400">
            {{ t('history.about3') }}
          </p>
        </UCard>
      </template>
    </UCollapsible>

    <ParameterSelection v-model="paramSel" :show-parameters="false" />

    <UCard>
      <template #header>
        <h2 class="text-lg font-bold">
          {{ t('explorer.dataSource') }}
        </h2>
      </template>
      <div v-if="resolution && dataset">
        <StationSelection
          v-model="stationSelectionState.selection"
          :parameter-selection="parameterSelection"
          :initial-station-ids="initialStationIds"
          :multiple="true"
        />
      </div>
      <div v-else class="text-sm text-gray-500">
        {{ t('history.selectFirst') }}
      </div>
    </UCard>

    <UCard>
      <template #header>
        <h2 class="text-lg font-bold">
          {{ t('history.sectionsTitle') }}
        </h2>
      </template>
      <div class="space-y-4">
        <USelectMenu
          v-model="selectedSections"
          :items="availableSections"
          multiple
          :placeholder="t('history.selectSections')"
          class="w-full"
        />
        <div class="flex flex-col sm:flex-row gap-2">
          <UButton :label="t('common.fetch')" color="primary" :disabled="!canFetch" class="w-full" @click="run" />
          <UButton :label="t('common.clear')" variant="outline" class="w-full" @click="clear" />
        </div>
        <div v-if="pending" class="text-sm text-gray-600 dark:text-gray-400">
          {{ t('common.loading') }}
        </div>
        <div v-if="error" class="text-sm text-red-600">
          {{ t('history.error') }}: {{ error.message ?? error }}
        </div>
      </div>
    </UCard>

    <UCard>
      <template #header>
        <div class="flex items-center justify-between">
          <h2 class="text-lg font-bold">
            {{ t('history.resultsTitle') }}
          </h2>
        </div>
      </template>

      <div>
        <div v-if="!data || (data.histories && data.histories.length === 0)" class="text-sm text-gray-600">
          {{ t('history.noHistories') }}
        </div>
        <div v-else class="space-y-6">
          <!-- Selected Stations Overview -->
          <div v-if="stationSelectionState.selection.stations.length > 0">
            <h3 class="text-base font-bold mb-3">
              {{ t('history.selectedStations') }}
            </h3>
            <div class="overflow-x-auto">
              <table class="min-w-full divide-y divide-gray-200 dark:divide-gray-700">
                <thead class="bg-gray-50 dark:bg-gray-800">
                  <tr>
                    <th class="px-4 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">
                      {{ t('history.colStationId') }}
                    </th>
                    <th class="px-4 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">
                      {{ t('history.colName') }}
                    </th>
                    <th class="px-4 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">
                      {{ t('history.colLatitude') }}
                    </th>
                    <th class="px-4 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">
                      {{ t('history.colLongitude') }}
                    </th>
                    <th class="px-4 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">
                      {{ t('history.colHeightM') }}
                    </th>
                    <th class="px-4 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">
                      {{ t('history.colState') }}
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
            <h3 class="text-base font-bold mb-3">
              {{ t('history.stationHistoryTitle') }}
            </h3>
            <div class="space-y-4">
              <div v-for="(history, idx) in data.histories" :key="idx">
                <UCard>
                  <!-- Station Info Card Header displays basic station info -->
                  <template #header>
                    <div class="flex items-center justify-between">
                      <h3 class="text-lg font-bold">
                        {{ t('history.stationIdPrefix') }}: {{ getStationId(history) }}
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
                        <tr v-if="getStationName(history)" class="border-b border-gray-200 dark:border-gray-700">
                          <td class="px-4 py-2 text-sm font-medium text-gray-500 dark:text-gray-400">
                            {{ t('history.rowStationName') }}
                          </td>
                          <td class="px-4 py-2 text-sm">
                            {{ getStationName(history) }}
                          </td>
                        </tr>
                        <tr v-if="history.latitude != null" class="border-b border-gray-200 dark:border-gray-700">
                          <td class="px-4 py-2 text-sm font-medium text-gray-500 dark:text-gray-400">
                            {{ t('history.colLatitude') }}
                          </td>
                          <td class="px-4 py-2 text-sm">
                            {{ history.latitude }}
                          </td>
                        </tr>
                        <tr v-if="history.longitude != null" class="border-b border-gray-200 dark:border-gray-700">
                          <td class="px-4 py-2 text-sm font-medium text-gray-500 dark:text-gray-400">
                            {{ t('history.colLongitude') }}
                          </td>
                          <td class="px-4 py-2 text-sm">
                            {{ history.longitude }}
                          </td>
                        </tr>
                        <tr v-if="history.station_height != null">
                          <td class="px-4 py-2 text-sm font-medium text-gray-500 dark:text-gray-400">
                            {{ t('history.rowStationHeight') }}
                          </td>
                          <td class="px-4 py-2 text-sm">
                            {{ history.station_height }} m
                          </td>
                        </tr>
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
                        :label="t('history.nameHistory')"
                        variant="ghost"
                        trailing-icon="i-lucide-chevron-down"
                        block
                        class="mb-2"
                      />
                      <template #content>
                        <!-- Station Name History -->
                        <div v-if="history.name.station?.length" class="mb-4">
                          <h4 class="text-sm font-bold mb-2 text-gray-700 dark:text-gray-300">
                            {{ t('history.stationNames') }}
                          </h4>
                          <div class="overflow-x-auto">
                            <table class="min-w-full divide-y divide-gray-200 dark:divide-gray-700">
                              <thead class="bg-gray-50 dark:bg-gray-800">
                                <tr>
                                  <th class="px-4 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">
                                    {{ t('history.colStartDate') }}
                                  </th>
                                  <th class="px-4 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">
                                    {{ t('history.colEndDate') }}
                                  </th>
                                  <th class="px-4 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">
                                    {{ t('history.rowStationName') }}
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
                          <h4 class="text-sm font-bold mb-2 text-gray-700 dark:text-gray-300">
                            {{ t('history.operatorNames') }}
                          </h4>
                          <div class="overflow-x-auto">
                            <table class="min-w-full divide-y divide-gray-200 dark:divide-gray-700">
                              <thead class="bg-gray-50 dark:bg-gray-800">
                                <tr>
                                  <th class="px-4 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">
                                    {{ t('history.colStartDate') }}
                                  </th>
                                  <th class="px-4 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">
                                    {{ t('history.colEndDate') }}
                                  </th>
                                  <th class="px-4 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">
                                    {{ t('history.colOperatorName') }}
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
                        :label="t('history.parameterHistory')"
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
                                  {{ t('history.colStartDate') }}
                                </th>
                                <th class="px-4 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">
                                  {{ t('history.colEndDate') }}
                                </th>
                                <th class="px-4 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">
                                  {{ t('history.colParameter') }}
                                </th>
                                <th class="px-4 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">
                                  {{ t('history.colDescription') }}
                                </th>
                                <th class="px-4 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">
                                  {{ t('history.colUnit') }}
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
                        :label="t('history.deviceHistory')"
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
                                  {{ t('history.colStartDate') }}
                                </th>
                                <th class="px-4 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">
                                  {{ t('history.colEndDate') }}
                                </th>
                                <th class="px-4 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">
                                  {{ t('history.colDeviceType') }}
                                </th>
                                <th class="px-4 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">
                                  {{ t('history.colDeviceHeight') }}
                                </th>
                                <th class="px-4 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">
                                  {{ t('history.colMethod') }}
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
                        :label="t('history.geographyHistory')"
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
                                  {{ t('history.colStartDate') }}
                                </th>
                                <th class="px-4 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">
                                  {{ t('history.colEndDate') }}
                                </th>
                                <th class="px-4 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">
                                  {{ t('history.colLatitude') }}
                                </th>
                                <th class="px-4 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">
                                  {{ t('history.colLongitude') }}
                                </th>
                                <th class="px-4 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">
                                  {{ t('history.rowStationHeight') }}
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
                        :label="t('history.missingDataHistory')"
                        variant="ghost"
                        trailing-icon="i-lucide-chevron-down"
                        block
                        class="mb-2"
                      />
                      <template #content>
                        <!-- Summary -->
                        <div v-if="history.missing_data.summary?.length" class="mb-4">
                          <h4 class="text-sm font-bold mb-2 text-gray-700 dark:text-gray-300">
                            {{ t('history.summary') }}
                          </h4>
                          <div class="overflow-x-auto">
                            <table class="min-w-full divide-y divide-gray-200 dark:divide-gray-700">
                              <thead class="bg-gray-50 dark:bg-gray-800">
                                <tr>
                                  <th class="px-4 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">
                                    {{ t('history.colStartDate') }}
                                  </th>
                                  <th class="px-4 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">
                                    {{ t('history.colEndDate') }}
                                  </th>
                                  <th class="px-4 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">
                                    {{ t('history.colParameter') }}
                                  </th>
                                  <th class="px-4 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">
                                    {{ t('history.colMissingCount') }}
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
                          <h4 class="text-sm font-bold mb-2 text-gray-700 dark:text-gray-300">
                            {{ t('history.periods') }}
                          </h4>
                          <div class="overflow-x-auto">
                            <table class="min-w-full divide-y divide-gray-200 dark:divide-gray-700">
                              <thead class="bg-gray-50 dark:bg-gray-800">
                                <tr>
                                  <th class="px-4 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">
                                    {{ t('history.colStartDate') }}
                                  </th>
                                  <th class="px-4 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">
                                    {{ t('history.colEndDate') }}
                                  </th>
                                  <th class="px-4 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">
                                    {{ t('history.colParameter') }}
                                  </th>
                                  <th class="px-4 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">
                                    {{ t('history.colMissingCount') }}
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
