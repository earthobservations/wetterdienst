<script setup lang="ts">
import type {Resolution, Station} from '#types/api.types'
import type { TableColumn } from '@nuxt/ui'
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
</script>

<template>
  <UContainer class="mx-auto max-w-3xl px-4 py-6 space-y-6">
    <ParameterSelection v-model="parameterSelectionState.selection" />

    <UCard v-if="showModeSelection">
      <template #header>
        <div class="flex items-center justify-between">
          <span>Data Source</span>
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
        </div>
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

    <DataViewer v-if="showDataViewer" ref="dataViewerRef" :parameter-selection="parameterSelectionState.selection" :station-selection="stationSelectionState" />
  </UContainer>
</template>
