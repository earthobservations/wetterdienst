<script setup lang="ts">
import type { TableColumn } from '@nuxt/ui'
import type { Station } from '#shared/types/api'
import type { DataSettings } from '~/types/data-settings.type'
import type { ParameterSelectionState } from '~/types/parameter-selection-state.type'
import type { StationMode, StationSelectionState } from '~/types/station-selection-state.type'
import DataViewer from '~/components/DataViewer.vue'
import DateRangeSelector from '~/components/DateRangeSelector.vue'
import InterpolationSummarySelection from '~/components/InterpolationSummarySelection.vue'
import ParameterSelection from '~/components/ParameterSelection.vue'
import StationSelection from '~/components/StationSelection.vue'
import { STATION_DISTANCE_DEFAULTS } from '~/types/data-settings.type'
import { defaultUnitTargets, serverDataSettings } from '~/utils/server-settings'
import { UNIT_TARGET_TYPES } from '~/utils/unit-targets'

const { t, te } = useI18n()

const stationTableColumns = computed<TableColumn<Station>[]>(() => [
  { accessorKey: 'station_id', header: t('stationTable.stationId') },
  { accessorKey: 'name', header: t('stationTable.name') },
  { accessorKey: 'region', header: t('stationTable.region') },
  { accessorKey: 'latitude', header: t('stationTable.latitude') },
  { accessorKey: 'longitude', header: t('stationTable.longitude') },
  { accessorKey: 'start_date', header: t('stationTable.startDate') },
  { accessorKey: 'end_date', header: t('stationTable.endDate') },
])

const route = useRoute()
const router = useRouter()

// Friendly labels for units, reusing the shared catalog (e.g. "degree_celsius" -> units.degree_celsius).
// Unit *types* come from the shared composable, which the glossary filter uses too.
const { unitTypeLabel } = useUnitTypeLabel()

function unitLabel(unit: string): string {
  // a server's default may be a unit the catalog has no name for, which is then named as it is
  return te(`units.${unit}`) ? t(`units.${unit}`) : unit
}

// the unit types the Unit Targets setting lists, each request naming every one (see pinnedUnitTargets)
const unitTypes = UNIT_TARGET_TYPES

// the unit each type left at "Default" comes in: the server's once it has said, else the listed one
const unitTargetDefaults = ref<Record<string, string>>(defaultUnitTargets(null))

// the value of the "Default (...)" choice, which stands for no entry in `unitTargets`: a select item
// refuses an empty value (reka-ui throws), and no unit is named this
const UNIT_TARGET_DEFAULT = 'default'

/** Select items for one unit type: the server's default first, then the units listed for it. */
function unitTargetItems(unitType: { type: string, units: string[] }) {
  return [
    {
      label: t('explorer.unitDefault', { unit: unitLabel(unitTargetDefaults.value[unitType.type]!) }),
      value: UNIT_TARGET_DEFAULT,
    },
    ...unitType.units.map(unit => ({ label: unitLabel(unit), value: unit })),
  ]
}

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
    // outside the branch: the box is shown for either source and sent for either, and an elevation
    // the user typed over a station's is theirs rather than the station's. It survives the round
    // trip only for a point given by coordinates: picking the station again names its own elevation,
    // which is what choosing a station means
    if (stationSel.interpolation.elevation !== undefined)
      q.elevation = stationSel.interpolation.elevation.toString()
  }
  if (stationSel.dateRange.startDate)
    q.startDate = stationSel.dateRange.startDate
  if (stationSel.dateRange.endDate)
    q.endDate = stationSel.dateRange.endDate
  return q
}

// Every one written, whatever it is: one left out is read back as the server's default, which may
// not be the value the link was copied with (GH-2359)
function dataSettingsToQuery(settings: DataSettings): Record<string, string> {
  return {
    humanize: String(settings.humanize),
    convertUnits: String(settings.convertUnits),
    shape: settings.shape,
    skipEmpty: String(settings.skipEmpty),
    dropNulls: String(settings.dropNulls),
  }
}

const showAbout = ref(false)
const parameterSelectionState = ref<ParameterSelectionState>(fromQuery(route.query))
function numberFromQuery(value: unknown): number | undefined {
  // a repeated key arrives as an array, and `1e400` parses to Infinity, which travels back into
  // the URL and on to the API as a number no answer can be given for
  const first = Array.isArray(value) ? value[0] : value
  const parsed = Number.parseFloat(String(first ?? ''))
  return Number.isFinite(parsed) ? parsed : undefined
}

const stationSelectionState = ref<StationSelectionState>({
  mode: modeFromQuery(route.query),
  selection: { stations: [] },
  interpolation: {
    source: (route.query.interpolationSource as 'manual' | 'station') || 'manual',
    // read back what `toQuery` writes for a point given by coordinates, so a shared link
    // reproduces the answer it was copied from. A point given by a station is written as an id
    // and not restored -- the station itself has to be fetched before it can be selected, which
    // `initialStationIds` does for station mode and nothing does for this one yet
    latitude: numberFromQuery(route.query.lat),
    longitude: numberFromQuery(route.query.lon),
    elevation: numberFromQuery(route.query.elevation),
  },
  dateRange: {
    startDate: route.query.startDate?.toString(),
    endDate: route.query.endDate?.toString(),
  },
})
const initialStationIds = ref<string[]>(stationIdsFromQuery(route.query))

// DWD DMO's `icon` is published as two runs, and which one is read is the request's `lead_time`
// (GH-2227): the short run (the backend's default) carries the 1-hourly precipitation, radiation and
// snow, the long one the 3-hourly ones in their place, and a parameter the run does not carry is
// refused. `icon_eu` publishes only the short run, so the choice is offered for `icon` alone, and it
// is sent, and kept in the URL, only where it is offered
type LeadTime = 'short' | 'long'
const leadTime = ref<LeadTime>(route.query.leadTime === 'long' ? 'long' : 'short')
const offersLeadTime = computed(() => {
  const { provider, network, dataset } = parameterSelectionState.value.selection
  return provider === 'dwd' && network === 'dmo' && dataset === 'icon'
})
const selectedLeadTime = computed(() => offersLeadTime.value ? leadTime.value : undefined)
const leadTimeOptions = computed(() => [
  { value: 'short' as const, label: t('explorer.leadTimeShort') },
  { value: 'long' as const, label: t('explorer.leadTimeLong') },
])

// Data settings: wetterdienst's defaults, the server's in their place once it reports them, and the
// link's over both
const startingSettings = ref<DataSettings>({
  humanize: true,
  convertUnits: true,
  unitTargets: {},
  shape: 'long',
  skipEmpty: false,
  skipThreshold: 0.95,
  skipCriteria: 'min',
  dropNulls: true,
  useNearbyStationDistance: 1.0,
  stationDistanceHomogeneous: STATION_DISTANCE_DEFAULTS.homogeneous,
  stationDistanceHeterogeneous: STATION_DISTANCE_DEFAULTS.heterogeneous,
  useStationDistancePerParameter: {},
  minGainOfValuePairs: 0.10,
  numAdditionalStations: 3,
})
const settingsFromLink: Partial<DataSettings> = {}
if (route.query.humanize != null)
  settingsFromLink.humanize = route.query.humanize.toString() === 'true'
if (route.query.convertUnits != null)
  settingsFromLink.convertUnits = route.query.convertUnits.toString() === 'true'
const shapeFromLink = route.query.shape?.toString()
if (shapeFromLink === 'long' || shapeFromLink === 'wide')
  settingsFromLink.shape = shapeFromLink
if (route.query.skipEmpty != null)
  settingsFromLink.skipEmpty = route.query.skipEmpty.toString() === 'true'
if (route.query.dropNulls != null)
  settingsFromLink.dropNulls = route.query.dropNulls.toString() !== 'false'
const dataSettings = ref<DataSettings>({ ...structuredClone(toRaw(startingSettings.value)), ...settingsFromLink })

// the settings the user has changed, ever: one changed and changed back is still theirs. The
// server's, written by `seedSettings`, are not
const changedSettings = new Set<keyof DataSettings>()
let seeding = false
watch(() => ({ ...dataSettings.value }), (now, before) => {
  if (seeding)
    return
  for (const key of Object.keys(now) as (keyof DataSettings)[]) {
    if (now[key] !== before[key])
      changedSettings.add(key)
  }
  if (now.shape !== before.shape)
    void reseedForShape(now.shape)
}, { flush: 'sync' })

/** Each of `reported` in place of a setting the link does not name and the user has not changed. */
function seedSettings(reported: Partial<DataSettings>) {
  const settings: Record<keyof DataSettings, unknown> = dataSettings.value
  seeding = true
  for (const key of Object.keys(reported) as (keyof DataSettings)[]) {
    if (!(key in settingsFromLink) && !changedSettings.has(key))
      settings[key] = reported[key]
  }
  seeding = false
}

// The server's defaults (GH-2359), once it reports them: each takes the place of a setting the link
// does not name and the user has not changed while the answer was on its way. A server without
// the endpoint, or one that fails, leaves wetterdienst's. The request still names every setting, so
// a copied link or API URL asks for the same on any server. Whether there was an answer
const seededFromServer = useServerSettings().then((server) => {
  if (!server)
    return false
  unitTargetDefaults.value = defaultUnitTargets(server)
  const reported = serverDataSettings(server)
  seedSettings(reported)
  Object.assign(startingSettings.value, reported)
  return true
})

let shapeAsked = 0

// A shape the user switches to has its own server settings (GH-2398), as the wide shape turns
// drop_nulls off: the server's, for that shape, take the place of the ones it reported for the shape
// before, under the same rule as its first answer. They are asked after that answer, so they are
// laid over it, and only of a backend that gave one. A backend that refuses the parameter, or fails,
// leaves the settings as they are, as does the answer to a switch the user has made again since
async function reseedForShape(shape: DataSettings['shape']) {
  const asked = ++shapeAsked
  if (!await seededFromServer)
    return
  const server = await serverSettingsFor({ shape })
  if (asked === shapeAsked && server)
    seedSettings(serverDataSettings(server))
}

// Track parameter distance entries with stable IDs
const parameterDistanceEntries = ref<Array<{ id: string, paramName: string, distance: number }>>([])

// Sync with dataSettings.interpolationStationDistance
watch(() => dataSettings.value.useStationDistancePerParameter, (newVal) => {
  // Update entries from the object, but keep stable IDs
  const existingIds = new Set(parameterDistanceEntries.value.map(e => e.paramName))
  const newParams = Object.keys(newVal).filter(k => !existingIds.has(k))

  // Add new params
  newParams.forEach((param) => {
    parameterDistanceEntries.value.push({
      id: `${param}_${Date.now()}`,
      paramName: param,
      distance: newVal[param] ?? 20,
    })
  })

  // Remove deleted params, keeping rows that have not been named yet
  parameterDistanceEntries.value = parameterDistanceEntries.value.filter(e =>
    !e.paramName || newVal[e.paramName] !== undefined,
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
    // a run chosen for one product is not carried over to the next one that offers the choice
    leadTime.value = 'short'
  },
)

// Update URL when parameter, station selection, or data settings change
watch(
  [
    parameterSelectionState,
    () => stationSelectionState.value.selection.stations,
    () => stationSelectionState.value.interpolation,
    () => dataSettings.value.humanize,
    () => dataSettings.value.convertUnits,
    () => dataSettings.value.shape,
    () => dataSettings.value.skipEmpty,
    () => dataSettings.value.dropNulls,
    selectedLeadTime,
  ],
  // A rejected navigation (e.g. superseded by a subsequent replace() before
  // this one resolves) would otherwise be an unhandled promise rejection.
  () => router.replace({
    query: {
      ...toQuery(parameterSelectionState.value, stationSelectionState.value),
      ...dataSettingsToQuery(dataSettings.value),
      // the default run is left out: unlike the data settings, it is no server setting, so a link
      // without it reads back the same run on any server
      ...(selectedLeadTime.value === 'long' ? { leadTime: 'long' } : {}),
    },
  }).catch(() => {}),
  { deep: true },
)

// Mode options for toggle
const modeOptions = computed(() => [
  { value: 'station' as const, label: t('explorer.modeStation'), icon: 'i-lucide-map-pin' },
  { value: 'interpolation' as const, label: t('explorer.modeInterpolation'), icon: 'i-lucide-locate' },
  { value: 'summary' as const, label: t('explorer.modeSummary'), icon: 'i-lucide-bar-chart-3' },
])

// show mode/station/datasource cards once a dataset is chosen; parameters are needed only for the actual fetch
const showModeSelection = computed(() => {
  return !!parameterSelectionState.value.selection.dataset
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

// Date range is required for interpolation, summary, high resolution, or date_required providers
const dateRangeRequired = computed(() =>
  isInterpolationMode.value
  || isSummaryMode.value
  || isHighResolution.value
  || parameterSelectionState.value.selection.dateRequired === true,
)

// When dates are required and stations are selected, auto-fill from min(start_date) / max(end_date).
watch(
  [
    () => stationSelectionState.value.selection.stations,
    dateRangeRequired,
  ],
  ([stations, required]) => {
    if (!required || !(stations as Station[]).length)
      return
    const today = new Date().toISOString().slice(0, 10)
    const toDate = (iso: string | undefined | null) => iso ? iso.slice(0, 10) : null
    const starts = (stations as Station[]).map(s => toDate(s.start_date)).filter(Boolean) as string[]
    // Active stations have no end_date — treat them as ending today
    const ends = (stations as Station[]).map(s => toDate(s.end_date) ?? today)
    if (starts.length)
      stationSelectionState.value.dateRange.startDate = starts.reduce((a, b) => a < b ? a : b)
    if (ends.length)
      stationSelectionState.value.dateRange.endDate = ends.reduce((a, b) => a > b ? a : b)
  },
  { deep: true },
)

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

// Reference to DataViewer for accessing exposed stats
const dataViewerRef = ref<InstanceType<typeof DataViewer> | null>(null)

// Check if we can fetch
const canFetch = computed(() => {
  if (!dataViewerRef.value?.canFetchData)
    return false

  // Check minimum requirements
  if (!hasLocationSelection.value)
    return false
  if (dateRangeRequired.value && !isDateRangeValid.value)
    return false

  // Nothing new to fetch where the selection is what Fetch sent last, still under way or answered. The
  // viewer holds that, so a fetch that failed, Reset and a viewer mounted afresh offer Fetch again
  return !dataViewerRef.value.holdsSelection
})

function fetchData() {
  if (!canFetch.value || !dataViewerRef.value)
    return
  dataViewerRef.value.fetchData()
}

function clear() {
  dataViewerRef.value?.clearData()
}

// Get list of selected parameters for validation
const selectedParameters = computed(() => {
  return parameterSelectionState.value.selection.parameters
})

// Validate parameter names in station distance mapping. "default" used to be accepted here as a
// catch-all key; the two radii above carry that now, and the backend rejects the key.
function isValidParameter(paramName: string): boolean {
  // Check if parameter name matches any selected parameter
  return selectedParameters.value.some(p => p === paramName || p.toLowerCase() === paramName.toLowerCase())
}

// Helper functions for interpolation station distance mapping. A row exists in the UI before it
// has a name; it only reaches `useStationDistancePerParameter`, and thus the request, once one is
// typed -- the backend rejects a name that is not a canonical parameter, and a placeholder is not
// one.
function addParameterDistance() {
  const id = `param_${Date.now()}`
  // the server's heterogeneous radius, but not an infinite one, which a per-parameter radius sent
  // as JSON would be written as null for, and refused
  const heterogeneous = startingSettings.value.stationDistanceHeterogeneous
  parameterDistanceEntries.value.push({
    id,
    paramName: '',
    distance: Number.isFinite(heterogeneous) ? heterogeneous : STATION_DISTANCE_DEFAULTS.heterogeneous,
  })
}

function updateParameterName(id: string, oldKey: string, newKey: string) {
  if (oldKey === newKey)
    return

  const entry = parameterDistanceEntries.value.find(e => e.id === id)
  if (!entry)
    return

  // the input fires per keystroke, so a name being cleared passes through here. The row stays,
  // but it leaves the request rather than being sent under an empty name
  if (!newKey.trim()) {
    delete dataSettings.value.useStationDistancePerParameter[oldKey]
    entry.paramName = ''
    return
  }

  const value = dataSettings.value.useStationDistancePerParameter[oldKey] ?? entry.distance
  if (oldKey)
    delete dataSettings.value.useStationDistancePerParameter[oldKey]
  dataSettings.value.useStationDistancePerParameter[newKey] = value
  entry.paramName = newKey
}

function updateParameterDistance(id: string, paramName: string, distance: number) {
  if (paramName)
    dataSettings.value.useStationDistancePerParameter[paramName] = distance
  const entry = parameterDistanceEntries.value.find(e => e.id === id)
  if (entry) {
    entry.distance = distance
  }
}

function removeParameterDistance(id: string, paramName: string) {
  if (paramName)
    delete dataSettings.value.useStationDistancePerParameter[paramName]
  parameterDistanceEntries.value = parameterDistanceEntries.value.filter(e => e.id !== id)
}

// Helper function for unit target changes
function handleUnitTargetChange(unitType: string, value: string) {
  if (value === UNIT_TARGET_DEFAULT) {
    delete dataSettings.value.unitTargets[unitType]
  }
  else {
    dataSettings.value.unitTargets[unitType] = value
  }
}
</script>

<template>
  <UContainer class="mx-auto max-w-3xl px-4 py-6 space-y-6">
    <div class="text-center mb-8">
      <h1 class="text-3xl font-bold mb-4">
        {{ t('explorer.title') }}
      </h1>
      <p class="text-gray-600 dark:text-gray-400">
        {{ t('explorer.subtitle') }}
      </p>
    </div>

    <UCollapsible v-model="showAbout">
      <UButton
        :label="t('explorer.aboutButton')" icon="i-lucide-info" variant="subtle" color="neutral" trailing-icon="i-lucide-chevron-down" block
        size="sm"
      />
      <template #content>
        <div class="space-y-3 text-gray-600 dark:text-gray-400 p-4">
          <p>
            {{ t('explorer.aboutIntro') }}
          </p>

          <div>
            <div class="font-semibold">
              {{ t('explorer.workflowTitle') }}
            </div>
            <ol class="list-decimal list-inside ml-4">
              <li>{{ t('explorer.workflow1') }}</li>
              <li>{{ t('explorer.workflow2') }}</li>
              <li>{{ t('explorer.workflow3') }}</li>
              <li>{{ t('explorer.workflow4') }}</li>
              <li>{{ t('explorer.workflow5') }}</li>
            </ol>
          </div>

          <div>
            <div class="font-semibold">
              {{ t('explorer.tipsTitle') }}
            </div>
            <ul class="list-disc list-inside ml-4">
              <li>{{ t('explorer.tip1') }}</li>
              <li>{{ t('explorer.tip2') }}</li>
              <li>{{ t('explorer.tip3') }}</li>
              <li>{{ t('explorer.tip4') }}</li>
            </ul>
          </div>

          <p class="text-sm text-gray-500">
            {{ t('explorer.aboutFooter') }}
          </p>
        </div>
      </template>
    </UCollapsible>

    <ParameterSelection v-model="parameterSelectionState.selection" :lead-time="selectedLeadTime" />

    <UCard v-if="offersLeadTime" data-testid="lead-time">
      <template #header>
        <div class="flex items-center gap-2">
          <UIcon name="i-lucide-clock" class="text-primary-500 shrink-0" />
          <h2 class="text-lg font-bold">
            {{ t('explorer.leadTime') }}
          </h2>
        </div>
      </template>
      <div class="space-y-3">
        <UFieldGroup>
          <UButton
            v-for="option in leadTimeOptions"
            :key="option.value"
            :label="option.label"
            color="neutral"
            :variant="leadTime === option.value ? 'solid' : 'ghost'"
            size="sm"
            @click="leadTime = option.value"
          />
        </UFieldGroup>
        <p class="text-sm text-gray-500 dark:text-gray-400">
          {{ t('explorer.leadTimeHint') }}
        </p>
      </div>
    </UCard>

    <!-- Mode Selection -->
    <UCard v-if="showModeSelection">
      <template #header>
        <div class="flex items-center gap-2">
          <UIcon name="i-lucide-layers" class="text-primary-500 shrink-0" />
          <h2 class="text-lg font-bold">
            {{ t('explorer.mode') }}
          </h2>
        </div>
      </template>
      <div class="space-y-3">
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
        <p class="text-sm text-gray-500 dark:text-gray-400">
          <span v-if="stationSelectionState.mode === 'interpolation'">{{ t('explorer.modeInterpolationDesc') }}</span>
          <span v-else-if="stationSelectionState.mode === 'summary'">{{ t('explorer.modeSummaryDesc') }}</span>
          <span v-else>{{ t('explorer.modeStationDesc') }}</span>
        </p>
        <UCollapsible v-if="stationSelectionState.mode !== 'station'">
          <UButton
            :label="t('explorer.modeHowItWorks')"
            icon="i-lucide-info"
            variant="ghost"
            color="neutral"
            trailing-icon="i-lucide-chevron-down"
            size="xs"
          />
          <template #content>
            <p class="mt-2 text-sm text-gray-500 dark:text-gray-400 leading-relaxed">
              <span v-if="stationSelectionState.mode === 'interpolation'">{{ t('explorer.modeInterpolationHow') }}</span>
              <span v-else>{{ t('explorer.modeSummaryHow') }}</span>
            </p>
          </template>
        </UCollapsible>
      </div>
    </UCard>

    <!-- Data Settings -->
    <UCollapsible v-if="showModeSelection">
      <UButton
        :label="t('explorer.settings')"
        icon="i-lucide-settings-2"
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
                {{ t('explorer.generalSettings') }}
              </div>
            </div>
            <div class="space-y-3">
              <div class="flex flex-wrap gap-4">
                <UCheckbox v-model="dataSettings.humanize" :label="t('explorer.humanize')" />
                <UCheckbox v-model="dataSettings.convertUnits" :label="t('explorer.convertUnits')" />
              </div>

              <!-- Unit Targets -->
              <UCollapsible v-if="dataSettings.convertUnits">
                <UButton
                  :label="t('explorer.unitTargets')"
                  variant="ghost"
                  color="neutral"
                  trailing-icon="i-lucide-chevron-down"
                  size="xs"
                />
                <template #content>
                  <div class="pt-3 space-y-2">
                    <p class="text-xs text-gray-500 mb-2">
                      {{ t('explorer.unitTargetsHint') }}
                    </p>
                    <div
                      v-for="unitType in unitTypes"
                      :key="unitType.type"
                      class="flex items-center gap-2"
                    >
                      <label class="text-xs text-gray-600 dark:text-gray-400 w-40">
                        {{ unitTypeLabel(unitType.type) }}:
                      </label>
                      <USelect
                        :model-value="dataSettings.unitTargets[unitType.type] ?? UNIT_TARGET_DEFAULT"
                        :items="unitTargetItems(unitType)"
                        size="xs"
                        class="w-44"
                        @update:model-value="handleUnitTargetChange(unitType.type, String($event))"
                      />
                    </div>
                  </div>
                </template>
              </UCollapsible>
            </div>
          </div>

          <!-- Values-specific settings -->
          <div
            v-if="stationSelectionState.mode === 'station'"
            class="p-4 rounded-lg border-2 border-primary-200 dark:border-primary-800 bg-primary-50 dark:bg-primary-950/30"
          >
            <div class="flex items-center gap-2 mb-3">
              <UIcon name="i-lucide-table" class="w-4 h-4 text-primary-500" />
              <div class="text-sm font-semibold text-gray-900 dark:text-white">
                {{ t('explorer.valuesOptions') }}
              </div>
            </div>
            <div class="space-y-3">
              <div class="flex items-center gap-4">
                <label class="text-sm">{{ t('explorer.shape') }}:</label>
                <UFieldGroup>
                  <UButton
                    :label="t('explorer.shapeLong')"
                    color="neutral"
                    :variant="dataSettings.shape === 'long' ? 'solid' : 'ghost'"
                    size="xs"
                    @click="dataSettings.shape = 'long'"
                  />
                  <UButton
                    :label="t('explorer.shapeWide')"
                    color="neutral"
                    :variant="dataSettings.shape === 'wide' ? 'solid' : 'ghost'"
                    size="xs"
                    @click="dataSettings.shape = 'wide'"
                  />
                </UFieldGroup>
              </div>
              <div class="flex flex-wrap gap-4">
                <UCheckbox v-model="dataSettings.skipEmpty" :label="t('explorer.skipEmpty')" />
                <UCheckbox v-model="dataSettings.dropNulls" :label="t('explorer.dropNulls')" />
              </div>
              <div v-if="dataSettings.skipEmpty" class="flex items-center gap-4">
                <label class="text-sm">{{ t('explorer.skipCriteria') }}:</label>
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
                <label class="text-sm">{{ t('explorer.threshold') }}:</label>
                <UInputNumber
                  v-model="dataSettings.skipThreshold"
                  :min="0.05"
                  :max="1"
                  :step="0.05"
                  size="sm"
                  class="w-28"
                />
              </div>
            </div>
          </div>

          <!-- Interpolation & Summary settings -->
          <div
            v-if="stationSelectionState.mode === 'interpolation' || stationSelectionState.mode === 'summary'"
            class="p-4 rounded-lg border-2 border-primary-200 dark:border-primary-800 bg-primary-50 dark:bg-primary-950/30"
          >
            <div class="flex items-center gap-2 mb-3">
              <UIcon name="i-lucide-locate" class="w-4 h-4 text-primary-500" />
              <div class="text-sm font-semibold text-gray-900 dark:text-white">
                {{ t('explorer.interpolationOptions') }}
              </div>
            </div>
            <div class="space-y-3">
              <!-- interpolation only: a summary takes the nearest station anyway (GH-2333) -->
              <div v-if="isInterpolationMode" class="space-y-2">
                <div class="flex items-center gap-4">
                  <label class="text-sm font-medium">{{ t('explorer.nearbyDistance') }}:</label>
                  <UInputNumber
                    v-model="dataSettings.useNearbyStationDistance"
                    :min="0"
                    :step="0.1"
                    size="sm"
                    class="w-32"
                  />
                  <span class="text-sm text-gray-500">km</span>
                </div>
                <p class="text-xs text-gray-500">
                  {{ t('explorer.nearbyDistanceHint') }}
                </p>
              </div>

              <UCollapsible>
                <UButton
                  :label="t('explorer.advancedSettings')"
                  variant="ghost"
                  color="neutral"
                  trailing-icon="i-lucide-chevron-down"
                  size="xs"
                />
                <template #content>
                  <div class="pt-3 space-y-4">
                    <!-- Station Distance Mapping -->
                    <div class="space-y-2">
                      <label class="text-sm font-medium">{{ t('explorer.stationDistanceByParam') }}:</label>
                      <p class="text-xs text-gray-500 mb-2">
                        {{ t('explorer.stationDistanceHint') }}
                      </p>

                      <!-- The two default radii, one per kind of parameter -->
                      <div class="flex items-center gap-2">
                        <span class="text-xs text-gray-600 w-32">{{ t('explorer.stationDistanceHomogeneous') }}:</span>
                        <UInputNumber
                          v-model="dataSettings.stationDistanceHomogeneous"
                          :min="0"
                          :step="1"
                          :placeholder="String(startingSettings.stationDistanceHomogeneous)"
                          size="xs"
                          class="w-28"
                        />
                        <span class="text-xs text-gray-500">km</span>
                      </div>
                      <div class="flex items-center gap-2">
                        <span class="text-xs text-gray-600 w-32">{{ t('explorer.stationDistanceHeterogeneous') }}:</span>
                        <UInputNumber
                          v-model="dataSettings.stationDistanceHeterogeneous"
                          :min="0"
                          :step="1"
                          :placeholder="String(startingSettings.stationDistanceHeterogeneous)"
                          size="xs"
                          class="w-28"
                        />
                        <span class="text-xs text-gray-500">km</span>
                      </div>

                      <!-- One list for every row: it used to be rendered inside the loop, so each
                           row repeated the same element id -->
                      <datalist id="parameter-suggestions">
                        <option v-for="p in selectedParameters" :key="p" :value="p" />
                      </datalist>

                      <!-- Parameter-specific distances -->
                      <div
                        v-for="entry in parameterDistanceEntries"
                        :key="entry.id"
                        class="flex items-center gap-2"
                      >
                        <UInput
                          :model-value="entry.paramName"
                          list="parameter-suggestions"
                          placeholder="parameter_name"
                          size="xs"
                          class="w-32"
                          :color="isValidParameter(entry.paramName) ? 'neutral' : 'error'"
                          :highlight="!isValidParameter(entry.paramName)"
                          @update:model-value="updateParameterName(entry.id, entry.paramName, String($event))"
                        />
                        <UInputNumber
                          :model-value="entry.distance"
                          :min="0"
                          :step="1"
                          placeholder="20"
                          size="xs"
                          class="w-28"
                          @update:model-value="updateParameterDistance(entry.id, entry.paramName, Number($event))"
                        />
                        <span class="text-xs text-gray-500">km</span>
                        <UButton
                          icon="i-lucide-trash-2"
                          color="error"
                          variant="ghost"
                          size="xs"
                          @click="removeParameterDistance(entry.id, entry.paramName)"
                        />
                        <UTooltip v-if="!isValidParameter(entry.paramName)" :text="t('explorer.paramNotSelected')">
                          <UIcon name="i-lucide-alert-circle" class="text-red-500 w-4 h-4" />
                        </UTooltip>
                      </div>

                      <!-- Add new parameter button -->
                      <div class="flex items-center gap-2">
                        <UButton
                          :label="t('explorer.addParameter')"
                          icon="i-lucide-plus"
                          color="neutral"
                          variant="ghost"
                          size="xs"
                          @click="addParameterDistance"
                        />
                        <span v-if="selectedParameters.length > 0" class="text-xs text-gray-500">
                          {{ t('explorer.available') }}: {{ selectedParameters.join(', ') }}
                        </span>
                      </div>
                    </div>

                    <div class="space-y-2">
                      <div class="flex items-center gap-4">
                        <label class="text-sm font-medium">{{ t('explorer.minGain') }}:</label>
                        <UInputNumber
                          v-model="dataSettings.minGainOfValuePairs"
                          :min="0"
                          :max="1"
                          :step="0.01"
                          size="sm"
                          class="w-32"
                        />
                      </div>
                      <p class="text-xs text-gray-500">
                        {{ t('explorer.minGainHint') }}
                      </p>
                    </div>

                    <div class="space-y-2">
                      <div class="flex items-center gap-4">
                        <label class="text-sm font-medium">{{ t('explorer.additionalStations') }}:</label>
                        <UInputNumber
                          v-model="dataSettings.numAdditionalStations"
                          :min="0"
                          :step="1"
                          size="sm"
                          class="w-32"
                        />
                      </div>
                      <p class="text-xs text-gray-500">
                        {{ t('explorer.additionalStationsHint') }}
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
        <div class="flex items-center gap-2">
          <UIcon name="i-lucide-map-pin" class="text-primary-500 shrink-0" />
          <h2 class="text-lg font-bold">
            {{ t('explorer.dataSource') }}
          </h2>
        </div>
      </template>

      <div class="space-y-6">
        <StationSelection
          v-if="stationSelectionState.mode === 'station'"
          v-model="stationSelectionState.selection"
          :parameter-selection="parameterSelectionState.selection"
          :initial-station-ids="initialStationIds"
          :multiple="true"
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

        <USeparator v-if="showDateRangeSelector" />

        <div v-if="showDateRangeSelector" class="flex flex-col sm:flex-row gap-2">
          <UButton :label="t('common.fetch')" icon="i-lucide-play" color="primary" :disabled="!canFetch" class="w-full" @click="fetchData" />
          <UButton :label="t('common.clear')" icon="i-lucide-x" variant="outline" class="w-full" @click="clear" />
        </div>

        <div v-if="dataViewerRef?.valuesPending" class="flex items-center gap-2 text-sm text-gray-600 dark:text-gray-400">
          <UIcon name="i-lucide-loader-circle" class="animate-spin shrink-0" />
          {{ t('common.loading') }}
        </div>
      </div>
    </UCard>

    <UCollapsible
      v-if="stationSelectionState.mode === 'station' && stationSelectionState.selection.stations.length > 0"
    >
      <UButton
        :label="t('explorer.stationsDetails')"
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
              {{ row.original.latitude?.toFixed(4) ?? '-' }}
            </template>
            <template #longitude-cell="{ row }">
              {{ row.original.longitude?.toFixed(4) ?? '-' }}
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
        :label="t('explorer.valuesDetails')"
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

    <DataViewer
      v-if="hasLocationSelection" ref="dataViewerRef" :parameter-selection="parameterSelectionState.selection"
      :station-selection="stationSelectionState" :settings="dataSettings" :lead-time="selectedLeadTime"
      :unit-target-defaults="unitTargetDefaults"
    />
  </UContainer>
</template>
