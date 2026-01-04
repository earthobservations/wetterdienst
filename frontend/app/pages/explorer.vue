<script setup lang="ts">
import type { TableColumn } from '@nuxt/ui'
import type { DataSettings } from '~/types/data-settings.type'
import type { ParameterSelectionState } from '~/types/parameter-selection-state.type'
import type { StationMode, StationSelectionState } from '~/types/station-selection-state.type'
import DataViewer from '~/components/DataViewer.vue'
import DateRangeSelector from '~/components/DateRangeSelector.vue'
import InterpolationSummarySelection from '~/components/InterpolationSummarySelection.vue'
import ParameterSelection from '~/components/ParameterSelection.vue'
import StationSelection from '~/components/StationSelection.vue'

const stationTableColumns: TableColumn<Station>[] = [
  { accessorKey: 'station_id', header: 'Station ID' },
  { accessorKey: 'name', header: 'Name' },
  { accessorKey: 'state', header: 'State' },
  { accessorKey: 'latitude', header: 'Latitude' },
  { accessorKey: 'longitude', header: 'Longitude' },
  { accessorKey: 'start_date', header: 'Start Date' },
  { accessorKey: 'end_date', header: 'End Date' },
]

const route = useRoute()
const router = useRouter()

// Available unit types and their possible units (from backend UnitConverter)
const unitTypes = [
  { type: 'temperature', units: ['degree_celsius', 'degree_kelvin', 'degree_fahrenheit'], default: 'degree_celsius' },
  { type: 'speed', units: ['meter_per_second', 'kilometer_per_hour', 'knots', 'beaufort'], default: 'meter_per_second' },
  { type: 'pressure', units: ['pascal', 'hectopascal', 'kilopascal'], default: 'hectopascal' },
  { type: 'precipitation', units: ['millimeter', 'liter_per_square_meter'], default: 'millimeter' },
  { type: 'precipitation_intensity', units: ['millimeter_per_hour', 'liter_per_square_meter_per_hour'], default: 'millimeter_per_hour' },
  { type: 'length_short', units: ['millimeter', 'centimeter', 'meter'], default: 'centimeter' },
  { type: 'length_medium', units: ['millimeter', 'centimeter', 'meter', 'kilometer'], default: 'meter' },
  { type: 'length_long', units: ['meter', 'kilometer', 'mile', 'nautical_mile'], default: 'kilometer' },
]

function stationIdsFromQuery(q: Record<string, any>): string[] {
  return q.stations ? q.stations.toString().split(',').filter(Boolean) : []
}

function modeFromQuery(q: Record<string, any>): StationMode {
  if (q.mode === 'interpolation')
    return 'interpolation'
  if (q.mode === 'summary')
    return 'summary'
  return 'station'
}

function fromQuery(q: Record<string, any>): ParameterSelectionState {
  return {
    selection: {
      provider: q.provider?.toString(),
      network: q.network?.toString(),
      resolution: q.resolution?.toString() as Resolution | undefined,
      dataset: q.dataset?.toString(),
      parameters: q.parameters
        ? q.parameters.toString().split(',').filter(Boolean)
        : [],
    },
  }
}

function toQuery(paramSel: ParameterSelectionState, stationSel: StationSelectionState): Record<string, string> {
  const q: Record<string, string> = {}
  if (paramSel.selection.provider)
    q.provider = paramSel.selection.provider
  if (paramSel.selection.network)
    q.network = paramSel.selection.network
  if (paramSel.selection.resolution)
    q.resolution = paramSel.selection.resolution
  if (paramSel.selection.dataset)
    q.dataset = paramSel.selection.dataset
  if (paramSel.selection.parameters.length)
    q.parameters = paramSel.selection.parameters.join(',')
  q.mode = stationSel.mode
  if (stationSel.mode === 'station' && stationSel.selection.stations.length) {
    q.stations = stationSel.selection.stations.map(s => s.station_id).join(',')
  }
  if (stationSel.mode === 'interpolation' || stationSel.mode === 'summary') {
    q.interpolationSource = stationSel.interpolation.source
    if (stationSel.interpolation.source === 'manual') {
      if (stationSel.interpolation.latitude !== undefined)
        q.lat = stationSel.interpolation.latitude.toString()
      if (stationSel.interpolation.longitude !== undefined)
        q.lon = stationSel.interpolation.longitude.toString()
    }
    else if (stationSel.interpolation.station) {
      q.interpolationStation = stationSel.interpolation.station.station_id
    }
  }
  if (stationSel.dateRange.startDate)
    q.startDate = stationSel.dateRange.startDate
  if (stationSel.dateRange.endDate)
    q.endDate = stationSel.dateRange.endDate
  return q
}

const parameterSelectionState = ref<ParameterSelectionState>(fromQuery(route.query))
const stationSelectionState = ref<StationSelectionState>({
  mode: modeFromQuery(route.query),
  selection: { stations: [] },
  interpolation: { source: (route.query.interpolationSource as 'manual' | 'station') || 'manual' },
  dateRange: {
    startDate: route.query.startDate?.toString(),
    endDate: route.query.endDate?.toString(),
  },
})
const initialStationIds = ref<string[]>(stationIdsFromQuery(route.query))

// Data settings
const dataSettings = ref<DataSettings>({
  humanize: true,
  convertUnits: true,
  unitTargets: {},
  shape: 'long',
  skipEmpty: false,
  skipThreshold: 0.95,
  skipCriteria: 'min',
  dropNulls: true,
  useNearbyStationDistance: 1.0,
  interpolationStationDistance: {},
  minGainOfValuePairs: 0.10,
  numAdditionalStations: 3,
})

// Track parameter distance entries with stable IDs
const parameterDistanceEntries = ref<Array<{ id: string, paramName: string, distance: number }>>([])

// Sync with dataSettings.interpolationStationDistance
watch(() => dataSettings.value.interpolationStationDistance, (newVal) => {
  // Update entries from the object, but keep stable IDs
  const existingIds = new Set(parameterDistanceEntries.value.map(e => e.paramName))
  const newParams = Object.keys(newVal).filter(k => k !== 'default' && !existingIds.has(k))

  // Add new params
  newParams.forEach((param) => {
    parameterDistanceEntries.value.push({
      id: `${param}_${Date.now()}`,
      paramName: param,
      distance: newVal[param] ?? 20,
    })
  })

  // Remove deleted params
  parameterDistanceEntries.value = parameterDistanceEntries.value.filter(e =>
    newVal[e.paramName] !== undefined,
  )

  // Update distances
  parameterDistanceEntries.value.forEach((entry) => {
    entry.distance = newVal[entry.paramName] ?? entry.distance
  })
}, { deep: true, immediate: true })

// Reference to DateRangeSelector for validation
const dateRangeSelectorRef = ref<InstanceType<typeof DateRangeSelector> | null>(null)

// Track initial parameter values to detect actual changes vs initialization
const initialParamKey = `${route.query.provider}|${route.query.network}|${route.query.resolution}|${route.query.dataset}`
const lastParamKey = ref(initialParamKey)

// Clear station selection when parameter selection changes (but not on initial load)
watch(
  () => [
    parameterSelectionState.value.selection.provider,
    parameterSelectionState.value.selection.network,
    parameterSelectionState.value.selection.resolution,
    parameterSelectionState.value.selection.dataset,
  ],
  (newVals) => {
    const newKey = newVals.join('|')
    if (newKey === lastParamKey.value)
      return
    lastParamKey.value = newKey
    stationSelectionState.value = {
      mode: stationSelectionState.value.mode,
      selection: { stations: [] },
      interpolation: { source: 'manual' },
      dateRange: {},
    }
    initialStationIds.value = []
  },
)

// Update URL when parameter or station selection changes
watch(
  [parameterSelectionState, stationSelectionState],
  () => router.replace({ query: toQuery(parameterSelectionState.value, stationSelectionState.value) }),
  { deep: true },
)

// Mode options for toggle
const modeOptions = [
  { value: 'station', label: 'Station', icon: 'i-lucide-map-pin' },
  { value: 'interpolation', label: 'Interpolation', icon: 'i-lucide-locate' },
  { value: 'summary', label: 'Summary', icon: 'i-lucide-bar-chart-3' },
] as const

// once parameters are selected, we have all information to continue with station/interpolation selection
const showModeSelection = computed(() => {
  return parameterSelectionState.value.selection.parameters.length > 0
})

// High resolution thresholds that require date filtering
const HIGH_RESOLUTION_THRESHOLDS: Resolution[] = ['1_minute', '5_minutes', '10_minutes']

const isHighResolution = computed(() => {
  const resolution = parameterSelectionState.value.selection.resolution
  if (!resolution)
    return false
  return HIGH_RESOLUTION_THRESHOLDS.includes(resolution)
})

const isInterpolationMode = computed(() => stationSelectionState.value.mode === 'interpolation')
const isSummaryMode = computed(() => stationSelectionState.value.mode === 'summary')

// Date range is required for interpolation, summary, or high resolution
const dateRangeRequired = computed(() => isInterpolationMode.value || isSummaryMode.value || isHighResolution.value)

// Check if station/interpolation/summary selection is complete
const hasLocationSelection = computed(() => {
  if (stationSelectionState.value.mode === 'station') {
    return stationSelectionState.value.selection.stations.length > 0
  }
  else {
    // Both interpolation and summary use the same interpolation selection
    const interp = stationSelectionState.value.interpolation
    if (interp.source === 'manual') {
      return interp.latitude !== undefined && interp.longitude !== undefined
    }
    else {
      return interp.station !== undefined
    }
  }
})

// Show date range selector after location is selected
const showDateRangeSelector = computed(() => hasLocationSelection.value)

// Validate date range
const isDateRangeValid = computed(() => {
  if (!dateRangeRequired.value)
    return true
  const { startDate, endDate } = stationSelectionState.value.dateRange
  if (!startDate || !endDate)
    return false

  const start = new Date(startDate)
  const end = new Date(endDate)
  if (end < start)
    return false

  // Check value limit for high resolution
  if (isHighResolution.value) {
    const diffMs = end.getTime() - start.getTime()
    const diffDays = diffMs / (1000 * 60 * 60 * 24)
    const resolution = parameterSelectionState.value.selection.resolution

    const valuesPerDay: Partial<Record<Resolution, number>> = {
      '1_minute': 1440,
      '5_minutes': 288,
      '10_minutes': 144,
    }

    const perDay = resolution ? (valuesPerDay[resolution] ?? 1) : 1
    const stationCount = stationSelectionState.value.mode === 'station'
      ? stationSelectionState.value.selection.stations.length
      : 1
    const paramCount = parameterSelectionState.value.selection.parameters.length

    const estimated = diffDays * perDay * stationCount * paramCount
    if (estimated > 100000)
      return false
  }

  return true
})

// Show data viewer when everything is valid
const showDataViewer = computed(() => {
  if (!hasLocationSelection.value)
    return false
  if (dateRangeRequired.value && !isDateRangeValid.value)
    return false
  return true
})

// Reference to DataViewer for accessing exposed stats
const dataViewerRef = ref<InstanceType<typeof DataViewer> | null>(null)

// Get list of selected parameters for validation
const selectedParameters = computed(() => {
  return parameterSelectionState.value.selection.parameters
})

// Validate parameter names in station distance mapping
function isValidParameter(paramName: string): boolean {
  if (paramName === 'default')
    return true
  // Check if parameter name matches any selected parameter
  return selectedParameters.value.some(p => p === paramName || p.toLowerCase() === paramName.toLowerCase())
}

// Helper functions for interpolation station distance mapping
function addParameterDistance() {
  const id = `param_${Date.now()}`
  const newKey = `new_parameter`
  dataSettings.value.interpolationStationDistance[newKey] = 20
  parameterDistanceEntries.value.push({
    id,
    paramName: newKey,
    distance: 20,
  })
}

function updateParameterName(id: string, oldKey: string, newKey: string) {
  if (oldKey === newKey || !newKey.trim())
    return

  const entry = parameterDistanceEntries.value.find(e => e.id === id)
  if (!entry)
    return

  const value = dataSettings.value.interpolationStationDistance[oldKey]
  if (value !== undefined) {
    delete dataSettings.value.interpolationStationDistance[oldKey]
    dataSettings.value.interpolationStationDistance[newKey] = value
    entry.paramName = newKey
  }
}

function updateParameterDistance(id: string, paramName: string, distance: number) {
  dataSettings.value.interpolationStationDistance[paramName] = distance
  const entry = parameterDistanceEntries.value.find(e => e.id === id)
  if (entry) {
    entry.distance = distance
  }
}

function removeParameterDistance(id: string, paramName: string) {
  delete dataSettings.value.interpolationStationDistance[paramName]
  parameterDistanceEntries.value = parameterDistanceEntries.value.filter(e => e.id !== id)
}

// Helper function for unit target changes
function handleUnitTargetChange(unitType: string, value: string) {
  if (value === '') {
    delete dataSettings.value.unitTargets[unitType]
  }
  else {
    dataSettings.value.unitTargets[unitType] = value
  }
}
</script>

<template>
  <UContainer class="mx-auto max-w-3xl px-4 py-6 space-y-6">
    <div class="text-center mb-6">
      <h1 class="text-3xl font-bold mb-4">
        Explorer
      </h1>
    </div>

    <UCard class="mb-6">
      <template #header>
        <h2 class="text-lg font-semibold">
          Getting Started
        </h2>
      </template>
      <ol class="list-decimal list-inside space-y-2 text-gray-600 dark:text-gray-400">
        <li>Select a <strong>Provider</strong> (e.g., DWD for German Weather Service)</li>
        <li>Choose a <strong>Network</strong> (e.g., observation for historical data)</li>
        <li>Pick a <strong>Resolution</strong> and <strong>Dataset</strong></li>
        <li>Select the <strong>Parameters</strong> you want to retrieve</li>
        <li>Browse and select <strong>Stations</strong> from the map or list</li>
        <li>Explore the <strong>Values</strong></li>
      </ol>
    </UCard>

    <ParameterSelection v-model="parameterSelectionState.selection" />

    <!-- Mode Selection -->
    <UCard v-if="showModeSelection">
      <template #header>
        <span>Mode</span>
      </template>
      <UFieldGroup>
        <UButton
          v-for="option in modeOptions"
          :key="option.value"
          :icon="option.icon"
          :label="option.label"
          color="neutral"
          :variant="stationSelectionState.mode === option.value ? 'solid' : 'ghost'"
          size="sm"
          @click="stationSelectionState.mode = option.value"
        />
      </UFieldGroup>
    </UCard>

    <!-- Data Settings -->
    <UCollapsible v-if="showModeSelection">
      <UButton
        label="Settings"
        variant="subtle"
        color="neutral"
        trailing-icon="i-lucide-chevron-down"
        block
        size="sm"
      />
      <template #content>
        <div class="pt-4 space-y-6">
          <!-- Common settings -->
          <div class="p-4 rounded-lg border-2 border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800/50">
            <div class="flex items-center gap-2 mb-3">
              <UIcon name="i-lucide-settings" class="w-4 h-4 text-primary-500" />
              <div class="text-sm font-semibold text-gray-900 dark:text-white">
                General Settings
              </div>
            </div>
            <div class="space-y-3">
              <div class="flex flex-wrap gap-4">
                <UCheckbox v-model="dataSettings.humanize" label="Humanize parameters" />
                <UCheckbox v-model="dataSettings.convertUnits" label="Convert to SI units" />
              </div>

              <!-- Unit Targets -->
              <UCollapsible v-if="dataSettings.convertUnits">
                <UButton
                  label="Unit Targets"
                  variant="ghost"
                  color="neutral"
                  trailing-icon="i-lucide-chevron-down"
                  size="xs"
                />
                <template #content>
                  <div class="pt-3 space-y-2">
                    <p class="text-xs text-gray-500 mb-2">
                      Override default target units for specific unit types. Leave empty to use defaults.
                    </p>
                    <div
                      v-for="unitType in unitTypes"
                      :key="unitType.type"
                      class="flex items-center gap-2"
                    >
                      <label class="text-xs text-gray-600 dark:text-gray-400 w-40">
                        {{ unitType.type }}:
                      </label>
                      <select
                        :value="dataSettings.unitTargets[unitType.type] ?? ''"
                        class="px-2 py-1 text-xs border rounded dark:bg-gray-800 dark:border-gray-700"
                        @change="handleUnitTargetChange(unitType.type, ($event.target as HTMLSelectElement).value)"
                      >
                        <option value="">
                          Default ({{ unitType.default }})
                        </option>
                        <option v-for="unit in unitType.units" :key="unit" :value="unit">
                          {{ unit }}
                        </option>
                      </select>
                    </div>
                  </div>
                </template>
              </UCollapsible>
            </div>
          </div>

          <!-- Values-specific settings -->
          <div v-if="stationSelectionState.mode === 'station'" class="p-4 rounded-lg border-2 border-primary-200 dark:border-primary-800 bg-primary-50 dark:bg-primary-950/30">
            <div class="flex items-center gap-2 mb-3">
              <UIcon name="i-lucide-table" class="w-4 h-4 text-primary-500" />
              <div class="text-sm font-semibold text-gray-900 dark:text-white">
                Values Options
              </div>
            </div>
            <div class="space-y-3">
              <div class="flex items-center gap-4">
                <label class="text-sm">Shape:</label>
                <UFieldGroup>
                  <UButton
                    label="Long"
                    color="neutral"
                    :variant="dataSettings.shape === 'long' ? 'solid' : 'ghost'"
                    size="xs"
                    @click="dataSettings.shape = 'long'"
                  />
                  <UButton
                    label="Wide"
                    color="neutral"
                    :variant="dataSettings.shape === 'wide' ? 'solid' : 'ghost'"
                    size="xs"
                    @click="dataSettings.shape = 'wide'"
                  />
                </UFieldGroup>
              </div>
              <div class="flex flex-wrap gap-4">
                <UCheckbox v-model="dataSettings.skipEmpty" label="Skip empty stations" />
                <UCheckbox v-model="dataSettings.dropNulls" label="Drop null values" />
              </div>
              <div v-if="dataSettings.skipEmpty" class="flex items-center gap-4">
                <label class="text-sm">Skip criteria:</label>
                <UFieldGroup>
                  <UButton
                    v-for="criteria in ['min', 'mean', 'max']"
                    :key="criteria"
                    :label="criteria"
                    color="neutral"
                    :variant="dataSettings.skipCriteria === criteria ? 'solid' : 'ghost'"
                    size="xs"
                    @click="dataSettings.skipCriteria = criteria as 'min' | 'mean' | 'max'"
                  />
                </UFieldGroup>
                <label class="text-sm">Threshold:</label>
                <input
                  v-model.number="dataSettings.skipThreshold"
                  type="number"
                  min="0"
                  max="1"
                  step="0.05"
                  class="w-20 px-2 py-1 text-sm border rounded dark:bg-gray-800 dark:border-gray-700"
                >
              </div>
            </div>
          </div>

          <!-- Interpolation-specific settings -->
          <div v-if="stationSelectionState.mode === 'interpolation'" class="p-4 rounded-lg border-2 border-primary-200 dark:border-primary-800 bg-primary-50 dark:bg-primary-950/30">
            <div class="flex items-center gap-2 mb-3">
              <UIcon name="i-lucide-locate" class="w-4 h-4 text-primary-500" />
              <div class="text-sm font-semibold text-gray-900 dark:text-white">
                Interpolation Options
              </div>
            </div>
            <div class="space-y-3">
              <div class="space-y-2">
                <div class="flex items-center gap-4">
                  <label class="text-sm font-medium">Nearby station distance:</label>
                  <input
                    v-model.number="dataSettings.useNearbyStationDistance"
                    type="number"
                    min="0"
                    step="0.1"
                    class="w-24 px-2 py-1 text-sm border rounded dark:bg-gray-800 dark:border-gray-700"
                  >
                  <span class="text-sm text-gray-500">km</span>
                </div>
                <p class="text-xs text-gray-500">
                  Maximum distance to consider nearby stations for interpolation. If a station is within this distance, its actual value will be used instead of interpolating.
                </p>
              </div>

              <UCollapsible>
                <UButton
                  label="Advanced Settings"
                  variant="ghost"
                  color="neutral"
                  trailing-icon="i-lucide-chevron-down"
                  size="xs"
                />
                <template #content>
                  <div class="pt-3 space-y-4">
                    <!-- Station Distance Mapping -->
                    <div class="space-y-2">
                      <label class="text-sm font-medium">Station distance by parameter:</label>
                      <p class="text-xs text-gray-500 mb-2">
                        Maximum distance (km) for stations used in interpolation per parameter. Backend defaults: 40km general, 20km for precipitation_height.
                      </p>

                      <!-- Default distance -->
                      <div class="flex items-center gap-2">
                        <span class="text-xs text-gray-600 w-32">Default (all):</span>
                        <input
                          v-model.number="dataSettings.interpolationStationDistance.default"
                          type="number"
                          min="0"
                          step="1"
                          placeholder="40"
                          class="w-20 px-2 py-1 text-xs border rounded dark:bg-gray-800 dark:border-gray-700"
                        >
                        <span class="text-xs text-gray-500">km</span>
                      </div>

                      <!-- Parameter-specific distances -->
                      <div
                        v-for="entry in parameterDistanceEntries"
                        :key="entry.id"
                        class="flex items-center gap-2"
                      >
                        <div class="relative w-32">
                          <input
                            :value="entry.paramName"
                            type="text"
                            list="parameter-suggestions"
                            placeholder="parameter_name"
                            class="w-full px-2 py-1 text-xs border rounded dark:bg-gray-800" :class="[
                              isValidParameter(entry.paramName)
                                ? 'border-gray-300 dark:border-gray-700'
                                : 'border-red-500 dark:border-red-500',
                            ]"
                            @input="updateParameterName(entry.id, entry.paramName, ($event.target as HTMLInputElement).value)"
                          >
                          <datalist id="parameter-suggestions">
                            <option v-for="p in selectedParameters" :key="p" :value="p" />
                          </datalist>
                        </div>
                        <input
                          :value="entry.distance"
                          type="number"
                          min="0"
                          step="1"
                          placeholder="20"
                          class="w-20 px-2 py-1 text-xs border rounded dark:bg-gray-800 dark:border-gray-700"
                          @input="updateParameterDistance(entry.id, entry.paramName, Number(($event.target as HTMLInputElement).value))"
                        >
                        <span class="text-xs text-gray-500">km</span>
                        <UButton
                          icon="i-lucide-trash-2"
                          color="error"
                          variant="ghost"
                          size="xs"
                          @click="removeParameterDistance(entry.id, entry.paramName)"
                        />
                        <UTooltip v-if="!isValidParameter(entry.paramName)" text="Parameter not in selected parameters">
                          <UIcon name="i-lucide-alert-circle" class="text-red-500 w-4 h-4" />
                        </UTooltip>
                      </div>

                      <!-- Add new parameter button -->
                      <div class="flex items-center gap-2">
                        <UButton
                          label="Add parameter"
                          icon="i-lucide-plus"
                          color="neutral"
                          variant="ghost"
                          size="xs"
                          @click="addParameterDistance"
                        />
                        <span v-if="selectedParameters.length > 0" class="text-xs text-gray-500">
                          Available: {{ selectedParameters.join(', ') }}
                        </span>
                      </div>
                    </div>

                    <div class="space-y-2">
                      <div class="flex items-center gap-4">
                        <label class="text-sm font-medium">Min gain of value pairs:</label>
                        <input
                          v-model.number="dataSettings.minGainOfValuePairs"
                          type="number"
                          min="0"
                          max="1"
                          step="0.01"
                          class="w-24 px-2 py-1 text-sm border rounded dark:bg-gray-800 dark:border-gray-700"
                        >
                      </div>
                      <p class="text-xs text-gray-500">
                        Minimum gain threshold for adding additional stations. Considers the extra effort against the gain of additional interpolated timestamps. (Default: 0.10)
                      </p>
                    </div>

                    <div class="space-y-2">
                      <div class="flex items-center gap-4">
                        <label class="text-sm font-medium">Additional stations:</label>
                        <input
                          v-model.number="dataSettings.numAdditionalStations"
                          type="number"
                          min="0"
                          step="1"
                          class="w-24 px-2 py-1 text-sm border rounded dark:bg-gray-800 dark:border-gray-700"
                        >
                      </div>
                      <p class="text-xs text-gray-500">
                        Number of additional stations to use in interpolation regardless of gain threshold. (Default: 3)
                      </p>
                    </div>
                  </div>
                </template>
              </UCollapsible>
            </div>
          </div>
        </div>
      </template>
    </UCollapsible>

    <!-- Data Source Selection -->
    <UCard v-if="showModeSelection">
      <template #header>
        <span>Data Source</span>
      </template>

      <div class="space-y-6">
        <StationSelection
          v-if="stationSelectionState.mode === 'station'"
          v-model="stationSelectionState.selection"
          :parameter-selection="parameterSelectionState.selection"
          :initial-station-ids="initialStationIds"
        />
        <InterpolationSummarySelection
          v-else
          v-model="stationSelectionState.interpolation"
          :parameter-selection="parameterSelectionState.selection"
        />

        <USeparator v-if="showDateRangeSelector" />

        <DateRangeSelector
          v-if="showDateRangeSelector"
          ref="dateRangeSelectorRef"
          v-model="stationSelectionState.dateRange"
          :required="dateRangeRequired"
          :resolution="parameterSelectionState.selection.resolution"
          :station-count="stationSelectionState.mode === 'station' ? stationSelectionState.selection.stations.length : 1"
          :parameter-count="parameterSelectionState.selection.parameters.length"
        />
      </div>
    </UCard>

    <UCollapsible v-if="stationSelectionState.mode === 'station' && stationSelectionState.selection.stations.length > 0">
      <UButton
        label="Stations Details"
        variant="subtle"
        color="neutral"
        trailing-icon="i-lucide-chevron-down"
        block
      />
      <template #content>
        <div class="pt-4">
          <UTable
            :data="stationSelectionState.selection.stations"
            :columns="stationTableColumns"
          >
            <template #latitude-cell="{ row }">
              {{ row.original.latitude.toFixed(4) }}
            </template>
            <template #longitude-cell="{ row }">
              {{ row.original.longitude.toFixed(4) }}
            </template>
            <template #start_date-cell="{ row }">
              {{ row.original.start_date?.slice(0, 10) ?? '-' }}
            </template>
            <template #end_date-cell="{ row }">
              {{ row.original.end_date?.slice(0, 10) ?? '-' }}
            </template>
          </UTable>
        </div>
      </template>
    </UCollapsible>

    <UCollapsible v-if="dataViewerRef?.parameterStats?.length">
      <UButton
        label="Values Details"
        variant="subtle"
        color="neutral"
        trailing-icon="i-lucide-chevron-down"
        block
      />
      <template #content>
        <div class="pt-4">
          <UTable
            :data="dataViewerRef.parameterStats"
            :columns="dataViewerRef.statsTableColumns"
            :ui="{ td: 'py-1 px-2', th: 'py-1 px-2' }"
          />
        </div>
      </template>
    </UCollapsible>

    <DataViewer v-if="showDataViewer" ref="dataViewerRef" :parameter-selection="parameterSelectionState.selection" :station-selection="stationSelectionState" :settings="dataSettings" />
  </UContainer>
</template>
