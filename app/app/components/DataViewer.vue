<script setup lang="ts">
import type { TableColumn } from '@nuxt/ui'
import type { Config as PlotlyConfig, Data as PlotlyData, Layout as PlotlyLayout } from 'plotly.js-basic-dist-min'
import type { DataSettings } from '~/types/data-settings.type'
import type { ParameterSelectionState } from '~/types/parameter-selection-state.type'
import type { StationMode, StationSelectionState } from '~/types/station-selection-state.type'
import { h } from 'vue'
import QueryPanel from '~/components/QueryPanel.vue'
import { STATION_DISTANCE_DEFAULTS } from '~/types/data-settings.type'
import { describeFetchError } from '~/utils/api-error'
import { formatDate } from '~/utils/format'
import { exportColumns, field, fieldText, valuesToCsv, valuesToJson } from '~/utils/values-export'

const props = defineProps<{
  parameterSelection: ParameterSelectionState['selection']
  stationSelection: StationSelectionState
  settings: DataSettings
}>()

const { t } = useI18n()
const { parameterLabel, datasetLabel } = useParameterLabel()

// Safe accessors for props to prevent reactivity issues
const stationSelection = computed(() => {
  if (!props.stationSelection) {
    return {
      mode: 'station' as const,
      selection: { stations: [] as { station_id: string }[] },
      interpolation: { source: 'manual' as const, latitude: undefined, longitude: undefined, elevation: undefined, station: undefined },
      dateRange: { startDate: undefined, endDate: undefined },
    }
  }
  return props.stationSelection
})

const parameterSelection = computed(() => {
  if (!props.parameterSelection) {
    return {
      provider: undefined,
      network: undefined,
      resolution: undefined,
      dataset: undefined,
      parameters: [] as string[],
    }
  }
  return props.parameterSelection
})

// View mode toggle
type ViewMode = 'table' | 'graph'
const viewMode = ref<ViewMode>('table')

// Chart container refs
const chartRef = ref<HTMLDivElement | null>(null)
const facetChartRefs = ref<Map<string, HTMLDivElement>>(new Map())

// Plotly instance (loaded client-side only)
let Plotly: typeof import('plotly.js-basic-dist-min') | null = null
// Plotly is ~1 MB, and the default view is the table -- so it is fetched when a chart is first
// actually wanted rather than on mount. The promise is kept so concurrent callers share one import.
let plotlyImport: Promise<typeof import('plotly.js-basic-dist-min')> | null = null

async function ensurePlotly(): Promise<typeof import('plotly.js-basic-dist-min')> {
  if (Plotly)
    return Plotly
  // A rejected import must not stay cached: every later call would await the same rejection and the
  // chart would never render again, though a retry would have worked. The realistic cause is a
  // redeploy invalidating the hashed chunk under an open tab.
  plotlyImport ??= import('plotly.js-basic-dist-min').catch((error) => {
    plotlyImport = null
    throw error
  })
  Plotly = await plotlyImport
  return Plotly
}

// Parameter label format options and chart display
// Options: 'parameter' (default), 'dataset/parameter', 'resolution/dataset/parameter'
type ParamLabelFormat = 'parameter' | 'dataset/parameter' | 'resolution/dataset/parameter'
const paramLabelFormat = ref<ParamLabelFormat>('parameter')
const facetByParameter = ref(false)

// Available items for the parameter label selector
const paramLabelItems = computed(() => [
  { label: t('dataViewer.paramLabelParameter'), value: 'parameter' },
  { label: t('dataViewer.paramLabelDatasetParameter'), value: 'dataset/parameter' },
  { label: t('dataViewer.paramLabelFull'), value: 'resolution/dataset/parameter' },
])

// Trendline option
const showTrendline = ref(false)

const isInterpolationMode = computed(() => stationSelection.value.mode === 'interpolation')
const isSummaryMode = computed(() => stationSelection.value.mode === 'summary')

/**
 * The two search radii, named for the endpoint that takes them, and only when the user moved them
 * off the backend's own defaults -- an untouched setting is not sent, so a server configured
 * through `WD_TS_GEO_STATION_DISTANCE_*` keeps its values.
 */
function stationDistanceRadii(prefix: 'interpolation' | 'summary'): Record<string, number> {
  const radii: Record<string, number> = {}
  // a cleared number input is null rather than a number, which would be sent as an empty value
  const given = (value: number) => Number.isFinite(value)
  if (given(props.settings.stationDistanceHomogeneous) && props.settings.stationDistanceHomogeneous !== STATION_DISTANCE_DEFAULTS.homogeneous)
    radii[`${prefix}_station_distance_homogeneous`] = props.settings.stationDistanceHomogeneous
  if (given(props.settings.stationDistanceHeterogeneous) && props.settings.stationDistanceHeterogeneous !== STATION_DISTANCE_DEFAULTS.heterogeneous)
    radii[`${prefix}_station_distance_heterogeneous`] = props.settings.stationDistanceHeterogeneous
  return radii
}

// each mode's endpoint, the name its values are saved under, and the mode itself
const ENDPOINTS = {
  values: { endpoint: '/api/values', filename: 'values', mode: 'station' },
  interpolate: { endpoint: '/api/interpolate', filename: 'interpolated', mode: 'interpolation' },
  summarize: { endpoint: '/api/summarize', filename: 'summary', mode: 'summary' },
} as const

const selectedEndpoint = computed(() => {
  if (isInterpolationMode.value)
    return ENDPOINTS.interpolate
  if (isSummaryMode.value)
    return ENDPOINTS.summarize
  return ENDPOINTS.values
})

const apiQuery = computed(() => {
  const ps = parameterSelection.value
  const ss = stationSelection.value
  const base: Record<string, any> = {
    provider: ps.provider,
    network: ps.network,
    parameters: ps.parameters.map(parameter => `${ps.resolution}/${ps.dataset}/${parameter}`).join(','),
    humanize: props.settings.humanize,
    convert_units: props.settings.convertUnits,
  }

  // Add unit targets if provided (filter out empty values)
  const unitTargets = Object.entries(props.settings.unitTargets)
    .filter(([_, value]) => value != null && true && String(value).trim() !== '')
    .reduce((acc, [key, value]) => ({ ...acc, [key]: value }), {})

  if (Object.keys(unitTargets).length > 0) {
    base.unit_targets = JSON.stringify(unitTargets)
  }

  // Add date range if provided
  if (ss.dateRange?.startDate) {
    base.date = ss.dateRange.startDate
    if (ss.dateRange.endDate) {
      base.date = `${ss.dateRange.startDate}/${ss.dateRange.endDate}`
    }
  }

  if (isInterpolationMode.value) {
    const interp = ss.interpolation
    const query: Record<string, any> = {
      ...base,
      latitude: interp?.latitude,
      longitude: interp?.longitude,
      elevation: interp?.elevation,
      use_nearby_station_distance: props.settings.useNearbyStationDistance,
    }
    // Add interpolation station distance if provided (filter out empty values)
    const stationDistancePerParameter = Object.entries(props.settings.useStationDistancePerParameter)
      .filter(([_, value]) => value != null && true && String(value).trim() !== '')
      .reduce((acc, [key, value]) => ({ ...acc, [key]: value }), {})

    if (Object.keys(stationDistancePerParameter).length > 0) {
      query.interpolation_station_distance = JSON.stringify(stationDistancePerParameter)
    }
    Object.assign(query, stationDistanceRadii('interpolation'))
    // Always send interpolation settings (backend has matching defaults)
    query.min_gain_of_value_pairs = props.settings.minGainOfValuePairs
    query.num_additional_stations = props.settings.numAdditionalStations
    return query
  }
  else if (isSummaryMode.value) {
    const interp = ss.interpolation
    const query: Record<string, any> = {
      ...base,
      latitude: interp?.latitude,
      longitude: interp?.longitude,
      elevation: interp?.elevation,
      use_nearby_station_distance: props.settings.useNearbyStationDistance,
    }
    // Add summary station distance if provided (filter out empty values)
    const stationDistancePerParameter = Object.entries(props.settings.useStationDistancePerParameter)
      .filter(([_, value]) => value != null && true && String(value).trim() !== '')
      .reduce((acc, [key, value]) => ({ ...acc, [key]: value }), {})

    if (Object.keys(stationDistancePerParameter).length > 0) {
      query.summary_station_distance = JSON.stringify(stationDistancePerParameter)
    }
    Object.assign(query, stationDistanceRadii('summary'))
    // Always send summary settings (backend has matching defaults)
    query.min_gain_of_value_pairs = props.settings.minGainOfValuePairs
    query.num_additional_stations = props.settings.numAdditionalStations
    return query
  }
  else {
    // Values mode - add values-specific settings
    return {
      ...base,
      station: ss.selection?.stations?.map(station => station.station_id).join(',') ?? '',
      shape: props.settings.shape,
      skip_empty: props.settings.skipEmpty,
      skip_threshold: props.settings.skipThreshold,
      skip_criteria: props.settings.skipCriteria,
      drop_nulls: props.settings.dropNulls,
    }
  }
})

// the request the selection makes: what Fetch sends, and what holdsSelection compares with
const selectedRequest = computed(() => ({ ...selectedEndpoint.value, query: apiQuery.value }))

// The request behind the table: set by Fetch alone, and the one the table's values are fetched with,
// so the table, its error and a GeoJSON download of it answer to the same request whatever is
// selected since. Bound to the live selection instead, the fetch kept a request of its own beside
// this one, which a selection changed mid-fetch, or Clear, could part from what the table showed.
interface ValuesRequest { endpoint: string, filename: string, mode: StationMode, query: Record<string, unknown> }
const fetchedRequest = shallowRef<ValuesRequest | null>(null)
// the request Fetch sent last, which the table's values are fetched with; it becomes fetchedRequest
// only once it has answered, so until then the table, the file name and GeoJSON keep to the last one
// shallow, so the one sent compares as itself rather than as Vue's proxy of it
const sentRequest = shallowRef<ValuesRequest | null>(null)
// a GeoJSON download under way, which the menu does not offer again until it is saved
const geojsonDownload = shallowRef<AbortController | null>(null)
const downloadingGeojson = computed(() => geojsonDownload.value !== null)
// why a download is aborted: the table it describes changed, which is told, or the viewer is gone,
// when there is no one to tell
const TABLE_CHANGED = 'table-changed'

// Abort the GeoJSON download under way: the table it describes is going. The synchronous watcher on
// displayData below calls it for every change to the table
function abortGeojson(reason: string = TABLE_CHANGED) {
  geojsonDownload.value?.abort(reason)
}
onScopeDispose(() => abortGeojson('unmounted'))

// One key for the table's values, whatever the request: a newer Fetch cancels one still under way
// (useFetch's default `dedupe: 'cancel'`) and Clear aborts it (`clear`), so an answer they overtook never
// reaches the table. Keyed by the request instead, as useFetch is by default, each request left an
// entry behind for the rest of the session.
const { data: valuesData, pending: valuesPending, error: valuesError, status: valuesStatus, refresh: refreshValues, clear: clearValues } = useFetch<ValuesResponse>(
  () => sentRequest.value?.endpoint ?? '/api/values',
  {
    key: `${useId()}-values`,
    method: 'GET',
    query: computed(() => sentRequest.value?.query ?? {}),
    lazy: true,
    immediate: false,
    // fetched by Fetch alone, not whenever the request it reads changes
    watch: false,
    default: () => ({ values: [] }),
  },
)

const allValues = computed(() => valuesData.value?.values ?? [])

const fetchErrorMessage = computed(() => valuesError.value ? describeFetchError(valuesError.value) : null)

const toast = useToast()

watch(valuesError, (err) => {
  if (!err)
    return
  toast.add({
    title: t('dataViewer.fetchErrorToastTitle'),
    description: fetchErrorMessage.value ?? undefined,
    color: 'error',
  })
})

// Query transformed data
const transformedData = ref<Value[]>([])
const isDataTransformed = ref(false)

// Display data (either original or transformed)
const displayData = computed(() => isDataTransformed.value ? transformedData.value : allValues.value)

// A GeoJSON download describes the table it was chosen for: whatever replaces that table -- a Fetch's
// answer, Clear, a query's own rows -- aborts it, from one place rather than each. Synchronously, as
// a watcher run after the change would let an answer that came in between be saved. A query that
// hands back the fetched rows themselves changes nothing shown and aborts nothing.
watch(displayData, () => abortGeojson(), { flush: 'sync' })

function handleDataTransformed(data: Value[]) {
  transformedData.value = data
  isDataTransformed.value = data.length > 0 && data !== allValues.value
}

// The table's own columns, in its order, each with the cell it shows where that is other than the
// value's text
const columnDefinitions: { key: keyof Value, cell?: TableColumn<Value>['cell'] }[] = [
  { key: 'station_id' },
  { key: 'resolution' },
  { key: 'dataset' },
  { key: 'parameter' },
  // a query's null timestamp empty, as the other cells show a missing value, where formatDate threw on it
  { key: 'timestamp', cell: ({ row }) => formatDate(fieldText(row.original.timestamp)) },
  { key: 'value' },
  { key: 'quality' },
  { key: 'taken_station_id' },
  { key: 'taken_station_ids' },
]

// Sorting
const sortColumn = ref<string | null>(null)
const sortDirection = ref<'asc' | 'desc'>('asc')

function toggleSort(column: string) {
  if (sortColumn.value === column) {
    if (sortDirection.value === 'asc') {
      sortDirection.value = 'desc'
    }
    else {
      sortColumn.value = null
      sortDirection.value = 'asc'
    }
  }
  else {
    sortColumn.value = column
    sortDirection.value = 'asc'
  }
}

function getSortIcon(column: string) {
  if (sortColumn.value !== column)
    return '↕'
  return sortDirection.value === 'asc' ? '↑' : '↓'
}

const sortedValues = computed(() => {
  const column = sortColumn.value
  // by a column the rows shown carry: one sorted by in other rows (a query's, left since) compares
  // every row as the greater, whose order each engine's sort makes something else of
  if (!column || !displayData.value.some(row => Object.hasOwn(row, column)))
    return displayData.value

  return [...displayData.value].sort((a, b) => {
    const aVal = field(a, column)
    const bVal = field(b, column)

    // a missing value last in either direction, and two of them equal, so they keep their order: one
    // compared as the greater both ways round left it to each engine's sort, which V8 keeps and
    // SpiderMonkey reverses
    const aMissing = aVal === null || aVal === undefined
    const bMissing = bVal === null || bVal === undefined
    if (aMissing || bMissing)
      return Number(aMissing) - Number(bMissing)

    let comparison = 0
    if (typeof aVal === 'number' && typeof bVal === 'number') {
      comparison = aVal - bVal
    }
    else {
      // a query's struct by its JSON text, as a column of the rows' own shows it
      comparison = fieldText(aVal).localeCompare(fieldText(bVal))
    }

    return sortDirection.value === 'asc' ? comparison : -comparison
  })
})

function resetTransform() {
  isDataTransformed.value = false
  transformedData.value = []
}

// Reset transform when new data is fetched
watch(allValues, () => {
  resetTransform()
})

// The mode the rows on screen were fetched in, and the selected one only while the table is empty:
// the column picker, the query panel and the chart describe the rows shown, which a mode selected
// since has not fetched. The request sent once its answer is in, which the fetch sets together with
// its rows: fetchedRequest follows a few microtasks later, and the new rows were drawn in the mode of
// the request before until then
const rowsMode = computed((): StationMode => {
  const answered = valuesStatus.value === 'success' ? sentRequest.value : fetchedRequest.value
  const request = allValues.value.length ? answered : null
  return request?.mode ?? stationSelection.value.mode
})

// The columns of the rows' mode, the mode-specific one only for rows of that mode: what the picker
// offers while the table is empty
const modeColumns = computed(() => {
  const base: (keyof Value)[] = ['station_id', 'resolution', 'dataset', 'parameter', 'timestamp', 'value', 'quality']
  if (rowsMode.value === 'summary') {
    return [...base, 'taken_station_id']
  }
  if (rowsMode.value === 'interpolation') {
    return [...base, 'taken_station_ids']
  }
  return base
})

// The columns the table knows, in its order: the ones it, the picker and a download put first
const TABLE_ORDER: string[] = columnDefinitions.map(c => c.key)

// The columns the query panel lists as available: those of the rows it queries, as a download
// orders them. The mode's fixed columns listed a `quality` that interpolated and summarized rows
// lack, and a wide table's `parameter` and `value`, and left out its parameters and a point mode's
// distance
const queryColumns = computed(() => exportColumns(allValues.value, TABLE_ORDER))

// The picker's options: every column the rows shown carry, as a download writes them -- the table's
// own in its order first, then a wide-shaped table's parameters or a query's `avg_value` -- and the
// mode's own while the table is empty. The nine fixed columns alone left those out, and showed a
// wide table's `parameter`, `value` and `quality` empty
const columnOptions = computed(() => displayData.value.length ? exportColumns(displayData.value, TABLE_ORDER) : modeColumns.value)

// The picker keeps the columns it hides rather than those it shows, so a column the rows bring along
// is shown as it comes in; by default only `resolution` and `dataset` are hidden
const HIDDEN_BY_DEFAULT = ['resolution', 'dataset']
const hiddenColumns = ref<string[]>([...HIDDEN_BY_DEFAULT])
// The columns the picker shows, in the table's order: what the table shows, and a copy writes
const selectedColumns = computed({
  get: () => columnOptions.value.filter(column => !hiddenColumns.value.includes(column)),
  // a column hidden that the rows shown do not carry stays hidden for rows that do
  set: (picked: string[]) => {
    hiddenColumns.value = [
      ...hiddenColumns.value.filter(column => !columnOptions.value.includes(column)),
      ...columnOptions.value.filter(column => !picked.includes(column)),
    ]
  },
})

// Show the default columns again when the rows' mode changes
watch(rowsMode, () => {
  hiddenColumns.value = [...HIDDEN_BY_DEFAULT]
})

const columns = computed(() =>
  selectedColumns.value.map((key) => {
    // every column is read by its name as it is -- an accessorKey reads `a.b` as a path -- and shown
    // as a copy writes it: a query's struct or list as its text, under one of the table's own names as
    // under a name of its own, where the table's cell wrote `[object Object]`
    const cell = columnDefinitions.find(c => c.key === key)?.cell
    return {
      id: key,
      accessorFn: (row: Value) => fieldText(field(row, key)),
      ...(cell ? { cell } : {}),
      header: () => h('span', {
        class: 'cursor-pointer select-none flex items-center gap-1',
        onClick: () => toggleSort(key),
      }, [
        key,
        h('span', { class: sortColumn.value === key ? 'opacity-100' : 'opacity-30' }, getSortIcon(key)),
      ]),
    } as TableColumn<Value>
  }),
)

// Pagination
const pageSizeOptions = [50, 100, 200]
const pageSize = ref(50)
const currentPage = ref(1)

const paginatedValues = computed(() => {
  const start = (currentPage.value - 1) * pageSize.value
  const end = start + pageSize.value
  return sortedValues.value.slice(start, end)
})

// A page belongs to the rows it was chosen in and the page size that cut them: new rows or a new size
// start again at the first page, so one chosen before is not kept past the end and shown empty
watch([displayData, pageSize], () => {
  currentPage.value = 1
})

async function copyCurrentPage() {
  await navigator.clipboard.writeText(valuesToCsv(paginatedValues.value, selectedColumns.value))
  toast.add({
    title: t('dataViewer.copied'),
    description: t('dataViewer.copiedRows', { count: paginatedValues.value.length }),
    color: 'success',
  })
}

async function copyAllValues() {
  await navigator.clipboard.writeText(valuesToCsv(sortedValues.value, selectedColumns.value))
  toast.add({ title: t('dataViewer.copied'), description: t('dataViewer.copiedRows', { count: sortedValues.value.length }), color: 'success' })
}

const canFetchData = computed(() => {
  const ps = parameterSelection.value
  const ss = stationSelection.value
  // Safety checks for props
  if (!ps.parameters?.length)
    return false

  if (!ss.mode)
    return false

  if (ss.mode === 'station') {
    return (ss.selection?.stations?.length ?? 0) > 0
  }
  else {
    const interp = ss.interpolation
    return interp?.latitude !== undefined && interp?.longitude !== undefined
  }
})

// A download saves what the table holds -- its rows, after the query panel and the sorting, with every
// column they carry, the table's own in its order first -- rather than asking the backend again
// for whatever is selected now: that answered a different selection, or units, once either had
// changed since the table was filled (GH-2065). GeoJSON needs the station positions the backend
// adds, so it is asked for again, but for the request that filled the table.
async function downloadValues(format: 'csv' | 'json' | 'geojson') {
  // the menu stops offering a format the table cannot be saved as, but a choice made before it has
  // updated still arrives here: an emptied table saves nothing, nor GeoJSON a table the query panel
  // has rewritten, whose answer describes rows no longer shown
  if (!sortedValues.value.length)
    return
  if (format === 'geojson') {
    const request = fetchedRequest.value
    if (request && !isDataTransformed.value)
      await downloadGeojson(request)
    return
  }
  const columns = columnOptions.value
  const content = format === 'csv' ? valuesToCsv(sortedValues.value, columns) : valuesToJson(sortedValues.value, columns)
  saveFile(content, fetchedRequest.value?.filename ?? ENDPOINTS.values.filename, format)
}

function saveFile(content: string, filename: string, format: 'csv' | 'json' | 'geojson') {
  saveBlob(new Blob([content], { type: 'application/octet-stream' }), `${filename}.${format}`)
  toast.add({ title: t('dataViewer.downloaded'), description: t('dataViewer.downloadedValues', { format: format.toUpperCase() }), color: 'success' })
}

function saveBlob(blob: Blob, name: string) {
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = name
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  // later, not at once: some browsers start the download after the click returns, and a large file
  // whose URL is already gone fails
  setTimeout(() => URL.revokeObjectURL(url), 10_000)
}

// Ask again for the request that filled the table, as GeoJSON, and save it. Nothing is saved where the
// answer failed, which is told, or where the table moved on -- Fetch, Clear, the query panel -- which
// aborts it, and is told as a cancelled download
async function downloadGeojson(request: NonNullable<typeof fetchedRequest.value>) {
  // one at a time: the menu does not offer another, and a second chosen before it has updated waits
  // on nothing and keeps the first one's controller, which Fetch and Clear abort
  if (geojsonDownload.value)
    return
  const download = new AbortController()
  geojsonDownload.value = download
  try {
    // as the table's own request was sent, so the query reads the same; once, as a failed answer is
    // told at once rather than asked for again
    const geojson = await $fetch<string>(request.endpoint, {
      query: { ...request.query, format: 'geojson' },
      responseType: 'text',
      retry: 0,
      signal: download.signal,
    })
    // an answer that came in as the table moved on is not saved either. Looked at and saved in one
    // go: a change to the table aborts at once, and none can come in between
    if (!download.signal.aborted) {
      saveFile(geojson, request.filename, 'geojson')
      return
    }
  }
  catch (error) {
    if (!download.signal.aborted) {
      toast.add({ title: t('dataViewer.fetchErrorToastTitle'), description: describeFetchError(error), color: 'error' })
      return
    }
  }
  finally {
    // not a newer download's, which an aborted one can finish after
    if (geojsonDownload.value === download)
      geojsonDownload.value = null
  }
  // aborted: said so where the table changed, the download having been asked for and never coming
  if (download.signal.reason === TABLE_CHANGED)
    toast.add({ title: t('dataViewer.downloadCancelled'), color: 'warning' })
}

const downloadMenuItems = computed(() => {
  if (viewMode.value === 'graph') {
    const noChart = !chartShown()
    return [
      [
        { label: 'PNG', disabled: noChart, onSelect: () => downloadChartImage('png') },
        { label: 'JPEG', disabled: noChart, onSelect: () => downloadChartImage('jpeg') },
        { label: 'SVG', disabled: noChart, onSelect: () => downloadChartImage('svg') },
      ],
    ]
  }
  // offered while the table shows rows to save; GeoJSON also needs the request that filled the table,
  // and a table the query panel has rewritten is no longer what that request answers
  const nothingShown = sortedValues.value.length === 0
  return [
    [
      { label: 'CSV', disabled: nothingShown, onSelect: () => downloadValues('csv') },
      { label: 'JSON', disabled: nothingShown, onSelect: () => downloadValues('json') },
      {
        label: 'GeoJSON',
        disabled: nothingShown || isDataTransformed.value || downloadingGeojson.value || !fetchedRequest.value,
        onSelect: () => downloadValues('geojson'),
      },
    ],
  ]
})

// Manual fetch function
async function fetchData() {
  if (!canFetchData.value) {
    clearData()
    return
  }
  // a request of its own, so a Fetch of the same selection again is told apart by the checks below, with
  // a query of its own, so nothing done to the one sent reaches the selection it is compared with
  const request = { ...selectedRequest.value, query: { ...selectedRequest.value.query } }
  sentRequest.value = request
  // the table is hidden until the answer, which starts at the first page again, whatever page is moved
  // to meanwhile
  currentPage.value = 1
  await refreshValues()
  // a newer Fetch or a Clear since has its own; this one answers for the table only if it is still the
  // last one sent
  if (sentRequest.value === request)
    fetchedRequest.value = valuesStatus.value === 'success' ? request : null
}

// A request as it compares with another: the query is built in one fixed order, and a field left unset
// is dropped. Values compare as they are, so a number and its text differ where the URL would not, but
// NaN and the infinities as the URL writes them, where JSON would make each of them null
function requestKey(request: { endpoint: string, query: Record<string, unknown> }) {
  return JSON.stringify([request.endpoint, request.query], (_, value) =>
    typeof value === 'number' && !Number.isFinite(value) ? String(value) : value)
}

// Whether what is selected is already asked for: the request Fetch sent last, while it is under way or
// once it has answered without error. A fetch that failed or was aborted, Clear and a viewer mounted
// afresh hold none, so the selection can be fetched again. Read from the fetch's own status rather than
// fetchedRequest, which is set a few microtasks after it
const holdsSelection = computed(() => {
  const request = valuesStatus.value === 'pending' || valuesStatus.value === 'success' ? sentRequest.value : null
  return request !== null && requestKey(request) === requestKey(selectedRequest.value)
})

// Clear function to reset data
function clearData() {
  // aborts a fetch still under way, and empties the table and its error
  fetchedRequest.value = null
  sentRequest.value = null
  clearValues()
}

// Plotly data preparation
const chartColors = [
  '#3b82f6',
  '#22c55e',
  '#f59e0b',
  '#ef4444',
  '#8b5cf6',
  '#06b6d4',
  '#ec4899',
  '#84cc16',
  '#f97316',
  '#6366f1',
]

// Linear regression calculation
function calculateLinearRegression(xData: Date[], yData: number[]): { x: Date[], y: number[] } {
  if (xData.length < 2)
    return { x: [], y: [] }

  const n = xData.length
  const xNums = xData.map(d => d.getTime())
  let sumX = 0
  let sumY = 0
  let sumXY = 0
  let sumXX = 0

  for (let i = 0; i < n; i++) {
    sumX += xNums[i]!
    sumY += yData[i]!
    sumXY += xNums[i]! * yData[i]!
    sumXX += xNums[i]! * xNums[i]!
  }

  const slope = (n * sumXY - sumX * sumY) / (n * sumXX - sumX * sumX)
  const intercept = (sumY - slope * sumX) / n

  const minX = Math.min(...xNums)
  const maxX = Math.max(...xNums)

  return {
    x: [new Date(minX), new Date(maxX)],
    y: [slope * minX + intercept, slope * maxX + intercept],
  }
}

// Performance threshold - use WebGL and simplified rendering for large datasets
const LARGE_DATASET_THRESHOLD = 500

// The date a row is placed at on the chart, or null for a row the chart has no place for. A query
// can put anything under `timestamp`: null; text that is no date, as a time of day or 'n/a', which
// left an Invalid Date that threw once written as ISO text, and the chart was not drawn; or a
// number, as epoch seconds, which a Date reads as milliseconds, and the point went to 1970
function rowDate(row: Value): Date | null {
  const timestamp: unknown = row.timestamp
  if (typeof timestamp !== 'string')
    return null
  const date = new Date(timestamp)
  return Number.isNaN(date.getTime()) ? null : date
}

// Plotly traces for single chart
const chartTraces = computed(() => {
  if (!sortedValues.value.length)
    return []

  // Group values by series (station + parameter combination), as the rows shown were fetched: a mode
  // selected since would merge two stations' rows into one series
  const seriesMap = new Map<string, { x: Date[], y: number[] }>()
  const mode = rowsMode.value

  for (const value of sortedValues.value) {
    let parameterLabel = value.parameter
    if (paramLabelFormat.value === 'dataset/parameter') {
      parameterLabel = `${value.dataset}/${value.parameter}`
    }
    else if (paramLabelFormat.value === 'resolution/dataset/parameter') {
      parameterLabel = `${value.resolution}/${value.dataset}/${value.parameter}`
    }
    const seriesKey = mode === 'station'
      ? `${value.station_id} - ${parameterLabel}`
      : parameterLabel

    if (!seriesMap.has(seriesKey)) {
      seriesMap.set(seriesKey, { x: [], y: [] })
    }

    const date = rowDate(value)
    if (value.value !== null && value.value !== undefined && date) {
      const series = seriesMap.get(seriesKey)!
      series.x.push(date)
      series.y.push(value.value)
    }
  }

  // Convert to Plotly traces
  const traces: PlotlyData[] = []
  const trendlineTraces: PlotlyData[] = []
  let colorIndex = 0
  const totalPoints = sortedValues.value.length
  const isLargeDataset = totalPoints > LARGE_DATASET_THRESHOLD

  for (const [seriesKey, data] of seriesMap) {
    const color = chartColors[colorIndex % chartColors.length] ?? '#3b82f6'

    // Sort data by time
    const pairs = data.x.map((x, i) => ({ x, y: data.y[i]! })).sort((a, b) => a.x.getTime() - b.x.getTime())
    const sortedXDates = pairs.map(p => p.x)
    const sortedY = pairs.map(p => p.y)
    // Convert to ISO strings for Plotly compatibility
    const sortedX = sortedXDates.map(d => d.toISOString())

    // For large datasets: skip markers and use thinner lines for performance
    const trace: PlotlyData = {
      name: seriesKey,
      x: sortedX,
      y: sortedY,
      type: 'scatter',
      mode: isLargeDataset ? 'lines' : 'lines+markers',
      line: { color, width: isLargeDataset ? 1 : 2 },
      showlegend: true,
    }
    if (!isLargeDataset) {
      trace.marker = { size: 6, color }
    }
    traces.push(trace)

    // Add trendline if enabled (collect separately to render on top)
    if (showTrendline.value && sortedX.length >= 2) {
      const trend = calculateLinearRegression(sortedXDates, sortedY)
      trendlineTraces.push({
        name: `${seriesKey} (trend)`,
        x: trend.x.map(d => d.toISOString()),
        y: trend.y,
        type: 'scatter',
        mode: 'lines',
        line: { color, width: 4, dash: 'dash' },
        showlegend: true,
      })
    }

    colorIndex++
  }

  // Add trendlines after main traces so they render on top
  return [...traces, ...trendlineTraces]
})

// Check if chart has data
const hasChartData = computed(() => chartTraces.value.length > 0)

// For faceted charts - group data by parameter
const facetedChartData = computed((): { parameter: string, traces: PlotlyData[] }[] => {
  if (!facetByParameter.value || !sortedValues.value.length)
    return []

  const parameterGroups = new Map<string, Map<string, { x: Date[], y: number[] }>>()
  // the mode the rows shown were fetched in, as the single chart's
  const mode = rowsMode.value

  for (const value of sortedValues.value) {
    let param = value.parameter
    if (paramLabelFormat.value === 'dataset/parameter') {
      param = `${value.dataset}/${value.parameter}`
    }
    else if (paramLabelFormat.value === 'resolution/dataset/parameter') {
      param = `${value.resolution}/${value.dataset}/${value.parameter}`
    }
    if (!parameterGroups.has(param)) {
      parameterGroups.set(param, new Map())
    }

    const stationKey = mode === 'station' ? value.station_id : 'interpolated'
    const stationMap = parameterGroups.get(param)!

    if (!stationMap.has(stationKey)) {
      stationMap.set(stationKey, { x: [], y: [] })
    }

    const date = rowDate(value)
    if (value.value !== null && value.value !== undefined && date) {
      const series = stationMap.get(stationKey)!
      series.x.push(date)
      series.y.push(value.value)
    }
  }

  const result: { parameter: string, traces: PlotlyData[] }[] = []
  const totalPoints = sortedValues.value.length
  const isLargeDataset = totalPoints > LARGE_DATASET_THRESHOLD

  for (const [parameter, stationMap] of parameterGroups) {
    const traces: PlotlyData[] = []
    const trendlineTraces: PlotlyData[] = []
    let colorIndex = 0

    for (const [stationKey, data] of stationMap) {
      const color = chartColors[colorIndex % chartColors.length] ?? '#3b82f6'

      const pairs = data.x.map((x, i) => ({ x, y: data.y[i]! })).sort((a, b) => a.x.getTime() - b.x.getTime())
      const sortedXDates = pairs.map(p => p.x)
      const sortedY = pairs.map(p => p.y)
      // Convert to ISO strings for Plotly compatibility
      const sortedX = sortedXDates.map(d => d.toISOString())

      // For large datasets: skip markers and use thinner lines for performance
      const trace: PlotlyData = {
        name: stationKey,
        x: sortedX,
        y: sortedY,
        type: 'scatter',
        mode: isLargeDataset ? 'lines' : 'lines+markers',
        line: { color, width: isLargeDataset ? 1 : 2 },
      }
      if (!isLargeDataset) {
        trace.marker = { size: 6, color }
      }
      traces.push(trace)

      // Add trendline if enabled (collect separately to render on top)
      if (showTrendline.value && sortedX.length >= 2) {
        const trend = calculateLinearRegression(sortedXDates, sortedY)
        trendlineTraces.push({
          name: `${stationKey} (trend)`,
          x: trend.x.map(d => d.toISOString()),
          y: trend.y,
          type: 'scatter',
          mode: 'lines',
          line: { color, width: 4, dash: 'dash' },
          showlegend: true,
        })
      }

      colorIndex++
    }

    // Add trendlines after main traces so they render on top
    result.push({ parameter, traces: [...traces, ...trendlineTraces] })
  }

  return result
})

// a chart is shown: there is none before a Fetch, after Clear, or with no rows to plot
function chartShown() {
  return allValues.value.length > 0 && (facetByParameter.value ? facetedChartData.value.length > 0 : hasChartData.value)
}

// The charts' renders under way, which a chart image waits for. Each watcher starts one of its own,
// so a newer one can start while another is under way
const chartRenders = new Set<Promise<void>>()

function tracked(render: Promise<void>): Promise<void> {
  chartRenders.add(render)
  const settled = () => {
    chartRenders.delete(render)
  }
  render.then(settled, settled)
  return render
}

// every render under way settled, and any a render started meanwhile
async function chartsDrawn() {
  while (chartRenders.size > 0)
    await Promise.allSettled(chartRenders)
}

async function downloadChartImage(format: 'png' | 'jpeg' | 'svg') {
  // a chart still being drawn holds no graph, which Plotly exports as an empty figure of its default
  // size: with a drawing under way, the charts are taken once it is done, as the page shows them then
  if (chartRenders.size > 0)
    await chartsDrawn()
  // faceted, one chart per parameter, in the order the page shows them. Taken once: faceting turned
  // on or off while Plotly loads would otherwise export these charts the other way
  const faceted = facetByParameter.value
  const charts = faceted
    ? facetedChartData.value.map(facet => facetChartRefs.value.get(facet.parameter))
    : [chartRef.value]
  // the menu stops offering an image with no chart shown, but a choice made before it has updated
  // still arrives here, where the page has yet to take the chart away, and there is nothing to save
  if (!chartShown() || !charts.every(chart => chart)) {
    toast.add({ title: t('dataViewer.noChartData'), color: 'warning' })
    return
  }

  const plotly = await ensurePlotly()
  if (faceted) {
    saveBlob(await stackCharts(plotly, charts as HTMLDivElement[], format), `chart.${format}`)
  }
  else {
    await plotly.downloadImage(charts[0]!, {
      format,
      filename: 'chart',
      // Plotly expects number | undefined for width/height; use undefined to let it auto-size
      width: undefined,
      height: undefined,
    })
  }

  toast.add({ title: t('dataViewer.downloaded'), description: t('dataViewer.downloadedChart', { format: format.toUpperCase() }), color: 'success' })
}

// Plotly exports one chart at a time. The facets' charts are stacked into one image, in the page's
// order, rather than saved as a file each, a run of downloads a browser may stop after the first.
// Stacked as SVG, each chart's own drawing, and turned into PNG or JPEG by the step Plotly's own
// export takes
async function stackCharts(plotly: typeof import('plotly.js-basic-dist-min'), charts: HTMLDivElement[], format: 'png' | 'jpeg' | 'svg'): Promise<Blob> {
  // null: each at the size it is shown, not at Plotly's default
  const urls = await Promise.all(charts.map(chart => plotly.toImage(chart, { format: 'svg', width: null, height: null })))
  const sheet = new DOMParser().parseFromString('<svg xmlns="http://www.w3.org/2000/svg"/>', 'image/svg+xml')
  const stack = sheet.documentElement
  let width = 0
  let height = 0
  for (const url of urls) {
    const svg = decodeURIComponent(url.slice(url.indexOf(',') + 1))
    const chart = new DOMParser().parseFromString(svg, 'image/svg+xml').documentElement
    chart.setAttribute('y', String(height))
    width = Math.max(width, Number(chart.getAttribute('width')))
    height += Number(chart.getAttribute('height'))
    stack.appendChild(sheet.importNode(chart, true))
  }
  stack.setAttribute('width', String(width))
  stack.setAttribute('height', String(height))
  const svg = new XMLSerializer().serializeToString(sheet)
  if (format === 'svg')
    return new Blob([svg], { type: 'image/svg+xml' })
  const image = await plotly.Snapshot.svgToImg({ svg, format, width, height, canvas: document.createElement('canvas'), promise: true })
  // a data URL, decoded rather than linked to, as a browser refuses a long one as a download link
  return new Blob([Uint8Array.from(atob(image.slice(image.indexOf(',') + 1)), c => c.charCodeAt(0))], { type: `image/${format}` })
}

// Plotly layout - optimized for large datasets
const chartLayout = computed((): Partial<PlotlyLayout> => {
  const isLargeDataset = sortedValues.value.length > LARGE_DATASET_THRESHOLD
  return {
    autosize: true,
    margin: { l: 60, r: 20, t: 40, b: 60 },
    xaxis: {
      title: t('dataViewer.axisDate'),
      type: 'date',
    },
    yaxis: {
      title: t('dataViewer.axisValue'),
    },
    showlegend: true,
    legend: {
      orientation: 'h',
      x: 0.5,
      xanchor: 'center',
      y: 1.02,
      yanchor: 'bottom',
    },
    // Use 'closest' for large datasets - 'x unified' is very slow
    hovermode: isLargeDataset ? 'closest' : 'x unified',
  }
})

const plotlyConfig: Partial<PlotlyConfig> = {
  responsive: true,
  displayModeBar: true,
  modeBarButtonsToRemove: ['lasso2d', 'select2d'],
}

function renderMainChart() {
  return tracked(drawMainChart())
}

function renderFacetedCharts() {
  return tracked(drawFacetedCharts())
}

// Render chart helper functions
async function drawMainChart() {
  if (viewMode.value !== 'graph' || facetByParameter.value)
    return
  const plotly = await ensurePlotly()

  await nextTick()
  if (chartRef.value && chartTraces.value.length > 0) {
    // Use newPlot for clean initialization
    plotly.purge(chartRef.value)
    await plotly.newPlot(chartRef.value, chartTraces.value, chartLayout.value, plotlyConfig)
  }
}

async function drawFacetedCharts() {
  if (viewMode.value !== 'graph' || !facetByParameter.value)
    return
  const plotly = await ensurePlotly()

  await nextTick()
  for (const facet of facetedChartData.value) {
    const el = facetChartRefs.value.get(facet.parameter)
    if (el) {
      // Ensure y-axis title does not overflow by enabling automargin and using standoff
      // For long parameter labels (e.g., resolution/dataset/parameter) split title into multiple lines
      // For long parameter labels (e.g., resolution/dataset/parameter) split title into multiple lines
      const splitTitle = String(facet.parameter).split('/').join('<br>')
      const layout: Partial<PlotlyLayout> = {
        ...chartLayout.value,
        yaxis: {
          // Plotly yaxis.title can be either string or object; ensure we pass a string for typing
          title: splitTitle,
          automargin: true,
          // Use standoff via layout annotations when necessary instead of nested object to satisfy types
        },
        autosize: true,
      }
      await plotly.react(el, facet.traces, layout, plotlyConfig)
    }
  }
}

// Render whatever the current view calls for. In table view -- the default -- this does no work
// and, importantly, does not reach for Plotly.
onMounted(async () => {
  if (facetByParameter.value) {
    await renderFacetedCharts()
  }
  else {
    await renderMainChart()
  }
})

// Render main chart when data changes
watch([chartTraces, chartLayout, viewMode, facetByParameter, paramLabelFormat, showTrendline], async () => {
  await renderMainChart()
})

// Render faceted charts when data changes
watch([facetedChartData, chartLayout, viewMode, facetByParameter, paramLabelFormat, showTrendline], async () => {
  await renderFacetedCharts()
})

// Parameter statistics
interface ParameterStats {
  parameter: string
  dataset: string
  count: number
  min: number | null
  max: number | null
  mean: number | null
  sum: number | null
}

const parameterStats = computed((): ParameterStats[] => {
  if (!displayData.value.length)
    return []

  const statsMap = new Map<string, { values: number[], dataset: string }>()

  for (const value of displayData.value) {
    const key = `${value.dataset}/${value.parameter}`
    if (!statsMap.has(key)) {
      statsMap.set(key, { values: [], dataset: value.dataset })
    }
    if (value.value !== null && value.value !== undefined) {
      statsMap.get(key)!.values.push(value.value)
    }
  }

  const stats: ParameterStats[] = []
  for (const [key, data] of statsMap) {
    const parameter = key.split('/').slice(1).join('/')
    const { values, dataset } = data
    const count = values.length

    if (count === 0) {
      stats.push({ parameter, dataset, count, min: null, max: null, mean: null, sum: null })
    }
    else {
      const min = Math.min(...values)
      const max = Math.max(...values)
      const sum = values.reduce((a, b) => a + b, 0)
      const mean = sum / count
      stats.push({ parameter, dataset, count, min, max, mean, sum })
    }
  }

  return stats.sort((a, b) => `${a.dataset}/${a.parameter}`.localeCompare(`${b.dataset}/${b.parameter}`))
})

const statsTableColumns = computed<TableColumn<ParameterStats>[]>(() => [
  { accessorKey: 'dataset', header: t('dataViewer.statDataset'), cell: ({ row }) => datasetLabel(row.original.dataset) },
  { accessorKey: 'parameter', header: t('dataViewer.statParameter'), cell: ({ row }) => parameterLabel(row.original.parameter) },
  { accessorKey: 'count', header: t('dataViewer.statCount') },
  { accessorKey: 'min', header: t('dataViewer.statMin'), cell: ({ row }) => row.original.min?.toFixed(2) ?? '-' },
  { accessorKey: 'max', header: t('dataViewer.statMax'), cell: ({ row }) => row.original.max?.toFixed(2) ?? '-' },
  { accessorKey: 'mean', header: t('dataViewer.statMean'), cell: ({ row }) => row.original.mean?.toFixed(2) ?? '-' },
  { accessorKey: 'sum', header: t('dataViewer.statSum'), cell: ({ row }) => row.original.sum?.toFixed(2) ?? '-' },
])

// Expose stats and fetch function for parent component
defineExpose({
  parameterStats,
  statsTableColumns,
  fetchData,
  clearData,
  canFetchData,
  holdsSelection,
  valuesPending,
  fetchErrorMessage,
})

// Set facet chart ref
function setFacetChartRef(parameter: string, el: HTMLDivElement | null) {
  if (el) {
    facetChartRefs.value.set(parameter, el)
  }
  else {
    facetChartRefs.value.delete(parameter)
  }
}
</script>

<template>
  <div class="space-y-4">
    <UCollapsible default-open>
      <template #summary>
        <div class="flex items-center justify-between w-full">
          <h3 class="text-lg font-bold">
            {{ t('dataViewer.dataTitle') }}
          </h3>
        </div>
      </template>

      <!-- Query Transform Panel - Inside collapsible for full width -->
      <QueryPanel
        v-if="allValues.length > 0"
        :data="allValues"
        :expected-columns="queryColumns"
        :mode="rowsMode"
        @data-transformed="handleDataTransformed"
      />

      <!-- View mode toggle -->
      <div class="flex justify-center">
        <div class="flex items-center gap-2 p-1 bg-gray-100 dark:bg-gray-800 rounded-lg">
          <UButton
            icon="i-lucide-table"
            size="md"
            :variant="viewMode === 'table' ? 'solid' : 'ghost'"
            :color="viewMode === 'table' ? 'primary' : 'neutral'"
            @click="viewMode = 'table'"
          />
          <UButton
            icon="i-lucide-chart-line"
            size="md"
            :variant="viewMode === 'graph' ? 'solid' : 'ghost'"
            :color="viewMode === 'graph' ? 'primary' : 'neutral'"
            @click="viewMode = 'graph'"
          />
        </div>
      </div>

      <!-- Options bar -->
      <div class="flex items-center justify-between">
        <span class="text-sm text-gray-500">
          <template v-if="valuesPending">{{ t('dataViewer.loadingValues') }}</template>
          <template v-else-if="isDataTransformed">{{ t('dataViewer.valuesTransformed', { count: displayData.length, total: allValues.length }) }}</template>
          <template v-else>{{ t('dataViewer.valuesCount', { count: allValues.length }) }}</template>
        </span>
        <div class="flex items-center gap-4">
          <div v-if="viewMode === 'table'" class="flex items-center gap-2">
            <span class="text-sm">{{ t('dataViewer.columns') }}:</span>
            <USelectMenu v-model="selectedColumns" :items="columnOptions" multiple class="w-40" />
          </div>
          <div class="flex items-center gap-1">
            <template v-if="viewMode === 'table'">
              <UTooltip :text="t('dataViewer.copyCurrentPage')">
                <UButton
                  size="xs" variant="ghost" icon="i-lucide-copy" :disabled="valuesPending || !paginatedValues.length"
                  @click="copyCurrentPage"
                />
              </UTooltip>
              <UTooltip :text="t('dataViewer.copyAllValues')">
                <UButton
                  size="xs" variant="ghost" icon="i-lucide-copy-check" :disabled="valuesPending || !sortedValues.length"
                  @click="copyAllValues"
                />
              </UTooltip>
            </template>
            <UDropdownMenu :items="downloadMenuItems">
              <UButton size="xs" variant="ghost" icon="i-lucide-download" :disabled="valuesPending" />
            </UDropdownMenu>
          </div>
        </div>
      </div>

      <!-- Chart Settings (only in graph mode) -->
      <UCollapsible v-if="viewMode === 'graph'" :default-open="true">
        <UButton
          :label="t('dataViewer.chartSettings')"
          variant="subtle"
          color="neutral"
          trailing-icon="i-lucide-chevron-down"
          block
          size="sm"
        />
        <template #content>
          <div class="pt-4 space-y-4">
            <!-- Display Options -->
            <div class="flex flex-wrap items-center gap-4">
              <div class="flex items-center gap-2">
                <label class="text-sm text-gray-600 dark:text-gray-300">{{ t('dataViewer.paramLabel') }}:</label>
                <USelect v-model="paramLabelFormat" :items="paramLabelItems" class="w-56" />
              </div>
              <UCheckbox v-model="facetByParameter" :label="t('dataViewer.facetByParameter')" />
              <UCheckbox v-model="showTrendline" :label="t('dataViewer.trendline')" />
            </div>
          </div>
        </template>
      </UCollapsible>

      <!-- Content -->
      <UCard :ui="{ body: valuesPending ? 'flex items-center justify-center min-h-40' : '' }">
        <div v-if="valuesPending" class="flex items-center justify-center py-12">
          <UIcon name="i-lucide-loader-circle" class="w-8 h-8 animate-spin text-primary-500" />
        </div>
        <template v-else>
          <div v-if="allValues.length === 0 && fetchErrorMessage" class="flex flex-col items-center justify-center gap-1 py-12 text-center text-red-600 dark:text-red-400">
            <span class="font-medium">{{ t('dataViewer.fetchError') }}</span>
            <span class="text-sm">{{ fetchErrorMessage }}</span>
          </div>
          <div v-else-if="allValues.length === 0" class="flex items-center justify-center py-12 text-gray-500">
            {{ t('dataViewer.emptyHint') }}
          </div>
          <UTable
            v-else-if="viewMode === 'table'" :data="paginatedValues" :columns="columns" sticky
            :ui="{ td: 'py-1 px-2', th: 'py-1 px-2' }"
          />
          <div v-else class="py-4">
            <div
              v-if="allValues.length === 0 && fetchErrorMessage"
              class="flex flex-col items-center justify-center gap-1 py-12 text-center text-red-600 dark:text-red-400"
            >
              <span class="font-medium">{{ t('dataViewer.fetchError') }}</span>
              <span class="text-sm">{{ fetchErrorMessage }}</span>
            </div>
            <div
              v-else-if="allValues.length === 0"
              class="flex items-center justify-center py-12 text-gray-500"
            >
              {{ t('dataViewer.emptyHint') }}
            </div>
            <div
              v-else-if="(facetByParameter && facetedChartData.length === 0) || (!facetByParameter && !hasChartData)"
              class="flex items-center justify-center py-12 text-gray-500"
            >
              {{ t('dataViewer.noChartData') }}
            </div>
            <!-- Faceted charts (one per parameter) -->
            <div v-else-if="facetByParameter" class="space-y-6">
              <div
                v-for="facet in facetedChartData" :key="facet.parameter"
                class="border rounded-lg p-4 dark:border-gray-700"
              >
                <h4 class="text-sm font-medium mb-2">
                  {{ facet.parameter }}
                </h4>
                <div
                  :ref="el => setFacetChartRef(facet.parameter, el as HTMLDivElement)" class="w-full"
                  style="height: 300px;"
                />
              </div>
            </div>
            <!-- Single combined chart -->
            <div v-else ref="chartRef" class="w-full overflow-visible" style="height: 400px;" />
          </div>
        </template>
        <template v-if="viewMode === 'table'" #footer>
          <div class="flex items-center justify-center gap-4">
            <div class="flex items-center gap-2">
              <span class="text-sm">{{ t('dataViewer.rowsPerPage') }}:</span>
              <USelect v-model="pageSize" :items="pageSizeOptions" class="w-20" />
            </div>
            <UPagination v-model:page="currentPage" :total="displayData.length" :items-per-page="pageSize" />
          </div>
        </template>
      </UCard>
    </ucollapsible>
  </div>
</template>
