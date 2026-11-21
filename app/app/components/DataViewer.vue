<script setup lang="ts">
import type { TableColumn } from '@nuxt/ui'
import type { Station } from '#shared/types/api'
import type { DataSettings } from '~/types/data-settings.type'
import type { ParameterSelectionState } from '~/types/parameter-selection-state.type'
import type { StationMode, StationSelectionState } from '~/types/station-selection-state.type'
import type { ImageFormat } from '~/utils/chart-image'
import type { SvgPart } from '~/utils/explorer-image'
import type { ExplorerSeries } from '~/utils/explorer-model'
import { h } from 'vue'
import ExplorerChart from '~/components/ExplorerChart.vue'
import LimitNotice from '~/components/LimitNotice.vue'
import QueryPanel from '~/components/QueryPanel.vue'
import { describeFetchError } from '~/utils/api-error'
import { downloadBlob, svgToBlob } from '~/utils/chart-image'
import { readDocumentChartTheme } from '~/utils/chart-theme'
import { stackSvgs } from '~/utils/explorer-image'
import { LARGE_THRESHOLD, pointCount, trendOf } from '~/utils/explorer-model'
import { formatDate, formatNumber } from '~/utils/format'
import { limitRefusal } from '~/utils/limit-refusal'
import { processingNote } from '~/utils/processing-note'
import { creditLines, termsOfProvider } from '~/utils/provider-credit'
import { estimateRows, hasNoReadingsYet, untilToday, windowForRefusal } from '~/utils/row-window'
import { timestampDate } from '~/utils/timestamp'
import { requestUnitTargets } from '~/utils/unit-targets'
import { exportColumns, field, fieldText, valuesToCsv, valuesToJson } from '~/utils/values-export'

const props = defineProps<{
  parameterSelection: ParameterSelectionState['selection']
  stationSelection: StationSelectionState
  settings: DataSettings
  /** DWD DMO's run, `lead_time`, where the selection offers a choice of one; every endpoint takes it */
  leadTime?: 'short' | 'long'
}>()

const emit = defineEmits<{
  /** the window that fits what the server refused, to be written to the date fields; the request is asked again by the page */
  applyRange: [range: { startDate: string, endDate: string }]
}>()

const { t, locale } = useI18n()
const serverLimits = useServerLimits()
const { parameterLabel, resolutionLabel, datasetLabel } = useParameterLabel()
const { settings: appSettings } = useSettings()

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

// The charts on the page (GH-4096): the single chart, or one for each facet. Each draws itself (`ExplorerChart.vue`, whose
// ECharts code is fetched when a chart is first drawn, not on mount: the default view is the table); the viewer asks them
// for the image to save.
type ExplorerChartHandle = InstanceType<typeof ExplorerChart>
const chartRef = ref<ExplorerChartHandle | null>(null)
const facetChartRefs = new Map<string, ExplorerChartHandle>()

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

/**
 * A row's parameter as the chart names it, in the format chosen above: `key` is its identity (the raw
 * ids, which tell two parameters apart whatever the labels say), `parts` the same, each as the
 * glossary names it in the active locale, and `label` those joined. With plain-language labels off
 * the parts are the raw ids and the label the path the API takes, `resolution/dataset/parameter`.
 */
function chartParameter(value: Value) {
  const named: [id: string, label: string][] = []
  if (paramLabelFormat.value === 'resolution/dataset/parameter')
    named.push([value.resolution, resolutionLabel(value.resolution)])
  if (paramLabelFormat.value !== 'parameter')
    named.push([value.dataset, datasetLabel(value.dataset)])
  named.push([value.parameter, parameterLabel(value.parameter)])
  const parts = named.map(([, label]) => label)
  return { key: named.map(([id]) => id).join('/'), parts, label: parts.join(appSettings.value.friendlyLabels ? ' / ' : '/') }
}

// Trendline option
const showTrendline = ref(false)

const isInterpolationMode = computed(() => stationSelection.value.mode === 'interpolation')
const isSummaryMode = computed(() => stationSelection.value.mode === 'summary')

/**
 * The two search radii, named for the endpoint that takes them. Sent whatever they are, as every
 * other setting is: the explorer starts them from the server's own (GH-2359), and one left out would
 * be the server's `WD_TS_GEO_STATION_DISTANCE_*` rather than the one the box shows.
 */
function stationDistanceRadii(prefix: 'interpolation' | 'summary'): Record<string, number> {
  const radii: Record<string, number> = {}
  // a cleared number input is null rather than a number, which would be sent as an empty value
  const given = (value: number) => Number.isFinite(value)
  if (given(props.settings.stationDistanceHomogeneous))
    radii[`${prefix}_station_distance_homogeneous`] = props.settings.stationDistanceHomogeneous
  if (given(props.settings.stationDistanceHeterogeneous))
    radii[`${prefix}_station_distance_heterogeneous`] = props.settings.stationDistanceHeterogeneous
  return radii
}

/**
 * The per-parameter radii that hold a number. A cleared input is NaN, which JSON writes as null and
 * the backend refuses with a 422, so the parameter is left out and the general radius applies.
 */
function stationDistancePerParameterGiven(): Record<string, number> {
  return Object.fromEntries(
    Object.entries(props.settings.useStationDistancePerParameter)
      .filter(([_, value]) => typeof value === 'number' && Number.isFinite(value)),
  )
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
    // the readable names, unit conversion and unit targets are the app settings' (GH-3878): read here, at each
    // request, so that a change on the settings page is in the next one. An Explorer link that names its own wins
    humanize: props.settings.humanize ?? appSettings.value.friendlyLabels,
    convert_units: props.settings.convertUnits ?? appSettings.value.convertUnits,
  }
  if (props.leadTime)
    base.lead_time = props.leadTime

  // every unit type the settings page lists, the user's choice there, so the request asks for the same units on any
  // server
  base.unit_targets = JSON.stringify(requestUnitTargets(appSettings.value.units))

  // Add date range if provided
  if (ss.dateRange?.startDate) {
    base.timestamp = ss.dateRange.startDate
    if (ss.dateRange.endDate) {
      base.timestamp = `${ss.dateRange.startDate}/${ss.dateRange.endDate}`
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
    const stationDistancePerParameter = stationDistancePerParameterGiven()

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
    // no use_nearby_station_distance: a summary takes the nearest station anyway, and the backend
    // deprecates it there (GH-2333)
    const query: Record<string, any> = {
      ...base,
      latitude: interp?.latitude,
      longitude: interp?.longitude,
      elevation: interp?.elevation,
    }
    // Add summary station distance if provided (filter out empty values)
    const stationDistancePerParameter = stationDistancePerParameterGiven()

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
      stations: ss.selection?.stations?.map(station => station.station_id).join(',') ?? '',
      shape: props.settings.shape,
      skip_empty: props.settings.skipEmpty,
      skip_threshold: props.settings.skipThreshold,
      skip_criteria: props.settings.skipCriteria,
      drop_nulls: props.settings.dropNulls,
    }
  }
})

// What the selection comes to, as the refusal of a limit needs it to offer a window that fits (see
// `limitNotice`): kept with the request it was sent as, as the selection moves on while the answer is
// on its way. A point (interpolation, summary) has no stations, and its window is the range alone
interface RefusalContext {
  resolution: Resolution | undefined
  records: { start_timestamp?: string | null, end_timestamp?: string | null }[]
  stationCount: number
  parameterCount: number
  tidy: boolean
  range: { startDate?: string, endDate?: string }
  /** the network's data lie ahead of today (a forecast), so a range is not ended at today */
  future: boolean
}

const refusalContext = computed((): RefusalContext => {
  const stations: Partial<Station>[] = stationSelection.value.selection?.stations ?? []
  const point = stationSelection.value.mode !== 'station'
  return {
    resolution: parameterSelection.value.resolution,
    records: point ? [{}] : stations.map(station => ({ start_timestamp: station.start_timestamp, end_timestamp: station.end_timestamp })),
    stationCount: point ? 0 : stations.length,
    parameterCount: parameterSelection.value.parameters.length,
    tidy: point || props.settings.shape !== 'wide',
    range: { startDate: stationSelection.value.dateRange?.startDate, endDate: stationSelection.value.dateRange?.endDate },
    future: parameterSelection.value.kind === 'forecast',
  }
})

// the request the selection makes: what Fetch sends, and what holdsSelection compares with
const selectedRequest = computed(() => ({ ...selectedEndpoint.value, query: apiQuery.value, context: refusalContext.value }))

// The request behind the table: set by Fetch alone, and the one the table's values are fetched with,
// so the table, its error and a GeoJSON download of it answer to the same request whatever is
// selected since. Bound to the live selection instead, the fetch kept a request of its own beside
// this one, which a selection changed mid-fetch, or Clear, could part from what the table showed.
interface ValuesRequest { endpoint: string, filename: string, mode: StationMode, query: Record<string, unknown>, context: RefusalContext }
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
    ...API_FETCH,
    default: () => ({ values: [] }),
  },
)

const allValues = computed(() => valuesData.value?.values ?? [])

const fetchErrorMessage = computed(() => valuesError.value ? describeFetchError(valuesError.value) : null)

const toast = useToast()

// The refusal of a limit (400, `limit-exceeded`) is a state of the table area and not a failure: the
// numbers of the refusal, what can be done and the ways on, in the page's language (GH-3457). Any other
// failure is the error below, with the backend's text. A refusal the page has no wording for stays an
// error: the stream limit, which the page never asks for, and the stations a point reaches, where the
// remedy is the radius and not the selection
function noticeFor(error: unknown, request: ValuesRequest | null) {
  const refusal = limitRefusal(error)
  if (!refusal || !request || refusal.limit === 'stream_rows')
    return null
  if (refusal.limit === 'stations' && request.mode !== 'station')
    return null
  return refusal
}

const limitNotice = computed(() => {
  if (valuesPending.value || allValues.value.length > 0)
    return null
  const request = sentRequest.value
  const refusal = valuesError.value ? noticeFor(valuesError.value, request) : null
  if (!refusal || !request)
    return null
  const { context } = request
  const stationMode = request.mode === 'station'
  // a window helps against the rows, not against the stations
  const window = refusal.limit === 'rows' && context.resolution
    ? windowForRefusal({
        requested: refusal.requested,
        maximum: refusal.maximum,
        resolution: context.resolution,
        records: context.records,
        parameterCount: context.parameterCount,
        tidy: context.tidy,
        range: context.range,
        future: context.future,
      })
    : null
  // a range that reaches past today and has no reading up to it: said, as there is no window to offer
  const noReadings = refusal.limit === 'rows' && !window && !!context.resolution && hasNoReadingsYet({
    resolution: context.resolution,
    records: context.records,
    parameterCount: context.parameterCount,
    tidy: context.tidy,
    range: context.range,
    future: context.future,
  })
  // not even the shortest window fits: said only where the span is known (else the page cannot tell).
  // The span is the one up to today, as the window is (a range that lies wholly after it has none)
  const untilNow = context.future ? context.range : untilToday(context.range)
  const noWindow = refusal.limit === 'rows' && !window && !noReadings && !!context.resolution && untilNow !== null && estimateRows({
    resolution: context.resolution,
    records: context.records,
    parameterCount: context.parameterCount,
    tidy: context.tidy,
    range: untilNow,
  }).span !== null
  const stream = serverLimits.value.max_stream_rows
  // streamed, the rows are held to the stream limit (`values` only): offered where they fit it
  const csv = refusal.limit === 'rows' && stationMode && (stream === 0 || refusal.requested <= stream)
    ? streamedCsvHref(request)
    : null
  return {
    refusal,
    point: !stationMode,
    stationCount: context.stationCount,
    parameterCount: context.parameterCount,
    window,
    noWindow,
    noReadings,
    // the window is for the selection the refusal was for, not one made since
    canApply: requestKey(request) === requestKey(selectedRequest.value),
    csvHref: csv,
    maxStreamRows: stream,
  }
})

// The refused request as a link to its streamed CSV (`format=csv`, which the server holds to its stream
// limit and not to the one of a single body): the browser saves it as it comes, where the app would hold
// every row of it in memory. The same query, so that what is saved is what the table would have shown
function streamedCsvHref(request: ValuesRequest): string {
  const params = new URLSearchParams()
  for (const [key, value] of Object.entries(request.query)) {
    if (value !== undefined && value !== null && value !== '')
      params.append(key, String(value))
  }
  params.set('format', 'csv')
  return `${request.endpoint}?${params}`
}

// the notice takes its buttons with it when a window is applied and the request is made again: the
// focus they held goes on to the table area, where the answer, or the notice again, arrives
const noticeBox = ref<HTMLElement | null>(null)
const card = ref<{ $el: HTMLElement } | null>(null)
// the table area takes the focus (see below), so it has a name of its own to be announced by: the page's
// own heading for it, which is otherwise only a heading to move by (GH-3722)
const dataTitleId = useId()
const contentBox = computed(() => card.value?.$el ?? null)
useFocusAfterRetry(() => limitNotice.value !== null, noticeBox, contentBox)

// Applying a window changes the dates before the request is made again, and the button goes with the
// change (the window is for the selection that was refused): the focus goes to the table area first,
// while the button still has it
function applyWindow(window: { startDate: string, endDate: string }) {
  contentBox.value?.focus()
  emit('applyRange', { startDate: window.startDate, endDate: window.endDate })
}

watch(valuesError, (err) => {
  if (!err || noticeFor(err, sentRequest.value))
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

// The query panel's rows, shown in place of the fetched rows also when a query returned none, where
// the table went on showing the fetched rows (GH-2163); the fetched rows themselves are its way back
function handleDataTransformed(data: Value[]) {
  transformedData.value = data
  isDataTransformed.value = data !== allValues.value
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
  { key: 'quality_flags' },
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

// An integer past 2^53 as plainRows writes it, its digits with no leading zero, as its value; any
// other text is none: digits within 2^53, such as a station's `01048`, and digits with a leading
// zero, which would tie with the same value written without. Text shorter than 2^53's sixteen digits
// is told at once, as the comparator asks for each value many times over
function bigIntegerValue(value: unknown): bigint | undefined {
  if (typeof value !== 'string' || value.length < 16 || !/^-?[1-9]\d*$/.test(value))
    return undefined
  const integer = BigInt(value)
  return Number.isSafeInteger(Number(integer)) ? undefined : integer
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

    // the numbers before the text, each compared within its kind: a number and text compared as text
    // left no one order (2 < 10, '10000000000000000000' < 2, 10 < '10000000000000000000') for a
    // query's column holding both. An integer past 2^53, which plainRows writes as its digits, is a
    // number by its value (GH-2153). A NaN reaches no row, plainRows makes it null
    const aNumber = typeof aVal === 'number' ? aVal : bigIntegerValue(aVal)
    const bNumber = typeof bVal === 'number' ? bVal : bigIntegerValue(bVal)
    let comparison: number
    if (aNumber !== undefined && bNumber !== undefined)
      comparison = aNumber < bNumber ? -1 : aNumber > bNumber ? 1 : 0
    else if (aNumber !== undefined || bNumber !== undefined)
      comparison = aNumber !== undefined ? -1 : 1
    else
      // a query's struct by its JSON text, as a column of the rows' own shows it
      comparison = fieldText(aVal).localeCompare(fieldText(bVal))

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
// the query panel and the chart describe the rows shown, which a mode selected since has not
// fetched, and the column picker hides only its default columns again when it changes. The request
// sent once its answer is in, which the fetch sets together with its rows: fetchedRequest follows a
// few microtasks later, and the new rows were drawn in the mode of the request before until then
const rowsRequest = computed(() => {
  const answered = valuesStatus.value === 'success' ? sentRequest.value : fetchedRequest.value
  return allValues.value.length ? answered : null
})
const rowsMode = computed((): StationMode => rowsRequest.value?.mode ?? stationSelection.value.mode)

// The credit of the rows on screen (GH-4255): the provider they were fetched from, as `GET /api/providers` states its credit line and
// licence, and what wetterdienst did to them, which for the rows of an interpolation or a summary says they were calculated. Written
// under the table and the chart, and into the CSV and JSON files; the copy to the clipboard is rows alone.
const { data: providerList } = useProviders()
const rowsProvider = computed(() => {
  const named = rowsRequest.value?.query.provider
  return typeof named === 'string' && named ? named : (parameterSelection.value.provider ?? null)
})
const rowsDerived = computed(() => rowsMode.value !== 'station')
const rowsTerms = computed(() => termsOfProvider(providerList.value?.providers, rowsProvider.value))

// The columns the table knows, in its order: the ones it, the picker and a download put first
const TABLE_ORDER: string[] = columnDefinitions.map(c => c.key)

// The columns the query panel lists as available: those of the rows it queries, as a download
// orders them. The mode's fixed columns listed a `quality_flags` that interpolated and summarized rows
// lack, and a wide table's `parameter` and `value`, and left out its parameters and a point mode's
// distance
const queryColumns = computed(() => exportColumns(allValues.value, TABLE_ORDER))

// The picker's options: every column the rows shown carry, as a download writes them -- the table's
// own in its order first, then a wide-shaped table's parameters or a query's `avg_value` -- and none
// while the table is empty, when the picker is disabled. The nine fixed columns alone left those out,
// and showed a wide table's `parameter`, `value` and `quality_flags` empty; the mode's long-shaped columns,
// offered while empty whatever the shape, were a guess at columns a Fetch may not bring, and one
// hidden then stayed hidden once it did
const columnOptions = computed(() => exportColumns(displayData.value, TABLE_ORDER))

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
// below `sm` the pager keeps the current page between its first and last page (the edges), has no First and Last
// buttons of its own, which they would repeat, and wraps where even the seven that are left are too wide: from page 2
// of four or more its row of nine buttons was wider than a phone's card (GH-3985)
const pagerFitsRow = useMediaQuery('(min-width: 40rem)')

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
  const note = processingNote(t, rowsDerived.value)
  const terms = rowsTerms.value
  // the credit and the note are in the file, as the stripes' table has them: comment lines before a CSV's header, a `metadata` member
  // before the `values` of the JSON, where a reader of `values` finds the rows as before
  const content = format === 'csv'
    ? valuesToCsv(sortedValues.value, columns, creditLines(terms, (name, url) => t('credit.licence', { name, url }), note))
    : valuesToJson(sortedValues.value, columns, {
        provider: { attribution: terms?.attribution || null, license: terms?.license ? { name: terms.license.name, url: terms.license.url } : null },
        processing_note: note,
      })
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
      ...API_ANSWER,
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

// The date a row is placed at on the chart, or null for a row the chart has no place for. A query
// can put anything under `timestamp`: null; text that is no date, as a time of day or 'n/a', which
// left an Invalid Date that threw once written as ISO text, and the chart was not drawn, or which a
// browser reads as a date by rules of its own, '1' as 2001-01-01 in Chrome; or a number, as epoch
// seconds, which a Date reads as milliseconds, and the point went to 1970. Text without an offset is
// UTC, as the rows the app fetches are, where the browser read a time without one as local time
function rowDate(row: Value): Date | null {
  const timestamp: unknown = row.timestamp
  return typeof timestamp === 'string' ? timestampDate(timestamp) : null
}

// The rows the chart plots, each with its moment: those with a value and a date to place it at, and those with no value
// at a date, which the line is broken at (a gap in the data is a gap in the chart). The series and
// facets are made from these alone, so a series whose rows are all left out is not drawn
// empty, and the large-dataset threshold counts the points drawn, not the rows left out. In the order
// the rows were fetched or queried, not the table's sort: the series take their legend places and
// colours in the order their first row comes, which a sort click swapped, and built the traces anew for.
// A value is a finite number, or an integer past 2^53 as plainRows writes it, its digits: any other
// text a query puts under `value`, `CAST(value AS VARCHAR)` or 'n/a', the trendline added up as
// text, drawing nothing, and text that is no number turned the y axis into one of categories.
// None while the table is shown, the view a Fetch opens: `chartShown` and the series read the
// chart's computeds whatever the view, so every answer was read row by row once more for a
// chart that was not on screen (GH-2560). The rows are read when the view moves to the chart
const chartRows = computed(() => viewMode.value !== 'graph'
  ? []
  : displayData.value.flatMap((row) => {
      const date = rowDate(row)
      const value: unknown = row.value
      const y = value === null ? null : typeof value === 'number' ? value : Number(bigIntegerValue(value) ?? Number.NaN)
      return date && (y === null || Number.isFinite(y)) ? [{ row, moment: date.getTime(), y }] : []
    }))

// A trendline is named for its series in the language of the page: "Mean air temperature (Trendline)"
function trendlineName(series: string) {
  return `${series} (${t('dataViewer.trendline')})`
}

// `resolution` is the one every row of the series has (undefined before its first row, null where they differ): the line is
// broken by it where rows are missing (GH-4100)
interface SeriesData { name: string, x: number[], y: (number | null)[], resolution?: string | null }

function noteResolution(series: SeriesData, resolution: string) {
  series.resolution = series.resolution === undefined || series.resolution === resolution ? resolution : null
}

// The series a chart draws, from what was gathered of the rows: each sorted by time, those with no value at all left out, and a
// trendline after each of them (collected apart, to be drawn on top) where it is on. `colorOf` is the place of a series'
// colour: the order it came in, or what its station was given.
function drawnSeries(gathered: Iterable<[string, SeriesData]>, colorOf: (key: string, index: number) => number): ExplorerSeries[] {
  const values: ExplorerSeries[] = []
  const trends: ExplorerSeries[] = []
  for (const [id, data] of gathered) {
    // sorted by time, rows of one moment as they came
    const order = data.x.map((_, i) => i).sort((a, b) => data.x[a]! - data.x[b]! || a - b)
    const series: ExplorerSeries = {
      id,
      name: data.name,
      colorIndex: colorOf(id, values.length),
      kind: 'values',
      resolution: data.resolution,
      x: order.map(i => data.x[i]!),
      y: order.map(i => data.y[i]!),
    }
    if (pointCount(series) === 0)
      continue
    values.push(series)
    // Add trendline if enabled
    const trend = showTrendline.value ? trendOf(series) : null
    if (trend)
      trends.push({ id: `${id}:trend`, name: trendlineName(data.name), colorIndex: series.colorIndex, kind: 'trend', x: trend.x, y: trend.y })
  }
  // Add trendlines after main traces so they render on top
  return [...values, ...trends]
}

// The series of the single chart
const chartSeries = computed((): ExplorerSeries[] => {
  if (!chartRows.value.length)
    return []

  // Group values by series (station + parameter combination), as the rows shown were fetched: a mode
  // selected since would merge two stations' rows into one series
  const seriesMap = new Map<string, SeriesData>()
  const mode = rowsMode.value

  for (const { row: value, moment, y } of chartRows.value) {
    const parameter = chartParameter(value)
    const seriesKey = mode === 'station'
      ? `${value.station_id} - ${parameter.key}`
      : parameter.key

    let series = seriesMap.get(seriesKey)
    if (!series) {
      series = { name: mode === 'station' ? `${value.station_id} - ${parameter.label}` : parameter.label, x: [], y: [] }
      seriesMap.set(seriesKey, series)
    }
    series.x.push(moment)
    series.y.push(y)
    noteResolution(series, value.resolution)
  }

  return drawnSeries(seriesMap, (_, index) => index)
})

// Many points: a line and no markers, as a chart of more than this many has always been drawn
const isLargeChart = computed(() => chartSeries.value.reduce((sum, series) => sum + (series.kind === 'values' ? pointCount(series) : 0), 0) > LARGE_THRESHOLD)

// Check if chart has data
const hasChartData = computed(() => chartSeries.value.length > 0)

// A facet: `parameter` is its identity (the raw ids), `label` and `parts` what the page names it with
interface FacetedChart { parameter: string, parts: string[], label: string, series: ExplorerSeries[], large: boolean }

// For faceted charts - group data by parameter. Each facet is a chart of its own, large or not by its
// own points: one of a few points was drawn as a large one where the other facets held many
const facetedChartData = computed((): FacetedChart[] => {
  if (!facetByParameter.value || !chartRows.value.length)
    return []

  const parameterGroups = new Map<string, { parts: string[], label: string, stations: Map<string, SeriesData> }>()
  // the mode the rows shown were fetched in, as the single chart's
  const mode = rowsMode.value
  // Each station's colour, the same in every facet: numbered once, in the order its first row comes
  // across all plotted rows. Numbered per facet, a station took another colour in a facet that lacked
  // a station coming before it
  const stationColors = new Map<string, number>()

  for (const { row: value, moment, y } of chartRows.value) {
    const { key: param, parts, label } = chartParameter(value)
    if (!parameterGroups.has(param)) {
      parameterGroups.set(param, { parts, label, stations: new Map() })
    }

    const stationKey = mode === 'station' ? value.station_id : 'interpolated'
    if (!stationColors.has(stationKey))
      stationColors.set(stationKey, stationColors.size)
    const stationMap = parameterGroups.get(param)!.stations

    if (!stationMap.has(stationKey)) {
      stationMap.set(stationKey, { name: stationKey, x: [], y: [] })
    }

    const series = stationMap.get(stationKey)!
    series.x.push(moment)
    series.y.push(y)
    noteResolution(series, value.resolution)
  }

  const result: FacetedChart[] = []

  for (const [parameter, { parts, label, stations: stationMap }] of parameterGroups) {
    const series = drawnSeries(stationMap, key => stationColors.get(key) ?? 0)
    // a parameter none of whose rows can be plotted is no facet
    if (!series.length)
      continue
    const points = series.reduce((sum, item) => sum + (item.kind === 'values' ? pointCount(item) : 0), 0)
    result.push({ parameter, parts, label, series, large: points > LARGE_THRESHOLD })
  }

  return result
})

// a chart is shown: there is none before a Fetch, after Clear, or with no rows to plot
function chartShown() {
  return allValues.value.length > 0 && (facetByParameter.value ? facetedChartData.value.length > 0 : hasChartData.value)
}

// A chart image is the chart as the page shows it (its window, the series its legend has on), in the light theme whatever
// the page shows, at the size it is shown at: the single chart as it is, and the facets, which are charts of their own,
// stacked in the order the page shows them into one image, rather than saved as a file each, a run of downloads a
// browser may stop after the first. Drawn from the chart's own state and not from what is on the screen, so that it needs
// no drawing under way to be done.
async function downloadChartImage(format: ImageFormat) {
  // faceted, one chart per parameter, in the order the page shows them. Taken once: faceting turned
  // on or off while the code of the chart loads would otherwise export these charts the other way
  const faceted = facetByParameter.value
  const charts = faceted
    ? facetedChartData.value.map(facet => facetChartRefs.get(facet.parameter))
    : [chartRef.value]
  // the menu stops offering an image with no chart shown, but a choice made before it has updated
  // still arrives here, where the page has yet to take the chart away, and there is nothing to save
  if (!chartShown() || !charts.every(chart => chart)) {
    toast.add({ title: t('dataViewer.noChartData'), color: 'warning' })
    return
  }

  // the export itself can fail too, such as a stack of many facets past the browser's canvas size,
  // which turning it into PNG or JPEG draws on: nothing is saved, and that is told
  try {
    if (faceted)
      await saveStacked(charts as ExplorerChartHandle[], format)
    else
      await charts[0]!.save({ format, filename: 'chart' })
  }
  catch (error) {
    console.error('The chart image could not be saved', error)
    toast.add({ title: t('dataViewer.chartImageNotSaved'), color: 'error' })
    return
  }

  toast.add({ title: t('dataViewer.downloaded'), description: t('dataViewer.downloadedChart', { format: format.toUpperCase() }), color: 'success' })
}

async function saveStacked(charts: ExplorerChartHandle[], format: ImageFormat) {
  const parts: (SvgPart & { paper?: string })[] = await Promise.all(charts.map(chart => chart.renderSvg()))
  const stack = stackSvgs(parts)
  const paper = parts[0]?.paper ?? readDocumentChartTheme('light').paper ?? '#ffffff'
  const blob = await svgToBlob(stack.svg, { format, width: stack.width, height: stack.height, scale: 1, background: paper })
  downloadBlob(blob, `chart.${format}`)
}

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

// Statistics are taken of long rows alone, those that carry a parameter and a value, numeric or
// missing: a wide-shaped row (a column per parameter) and a query's own columns (`avg_value`) carry
// none, and grouped as long rows they showed one row for an undefined parameter, counting nothing
const parameterStats = computed((): ParameterStats[] => {
  // a running count, min, max and sum: spreading the values into Math.min/max throws past the
  // engine's argument limit (about 120k in V8, 65,536 in JavaScriptCore)
  const statsMap = new Map<string, { count: number, min: number, max: number, sum: number, dataset: string, parameter: string }>()

  for (const row of displayData.value) {
    const parameter = field(row, 'parameter')
    const value = field(row, 'value')
    if (typeof parameter !== 'string' || (typeof value !== 'number' && value !== null))
      continue
    // as the table shows it: a query may leave the dataset out, or give one of its own, a year
    const dataset = fieldText(field(row, 'dataset'))
    const key = `${dataset}/${parameter}`
    let entry = statsMap.get(key)
    if (!entry) {
      entry = { count: 0, min: Infinity, max: -Infinity, sum: 0, dataset, parameter }
      statsMap.set(key, entry)
    }
    if (value !== null) {
      entry.count++
      entry.min = Math.min(entry.min, value)
      entry.max = Math.max(entry.max, value)
      entry.sum += value
    }
  }

  const stats: ParameterStats[] = []
  for (const { count, min, max, sum, dataset, parameter } of statsMap.values()) {
    if (count === 0)
      stats.push({ parameter, dataset, count, min: null, max: null, mean: null, sum: null })
    else
      stats.push({ parameter, dataset, count, min, max, mean: sum / count, sum })
  }

  return stats.sort((a, b) => `${a.dataset}/${a.parameter}`.localeCompare(`${b.dataset}/${b.parameter}`))
})

const statsTableColumns = computed<TableColumn<ParameterStats>[]>(() => [
  { accessorKey: 'dataset', header: t('dataViewer.statDataset'), cell: ({ row }) => datasetLabel(row.original.dataset) },
  { accessorKey: 'parameter', header: t('dataViewer.statParameter'), cell: ({ row }) => parameterLabel(row.original.parameter) },
  { accessorKey: 'count', header: t('dataViewer.statCount') },
  { accessorKey: 'min', header: t('dataViewer.statMin'), cell: ({ row }) => row.original.min != null ? formatNumber(row.original.min, locale.value, 2) : '-' },
  { accessorKey: 'max', header: t('dataViewer.statMax'), cell: ({ row }) => row.original.max != null ? formatNumber(row.original.max, locale.value, 2) : '-' },
  { accessorKey: 'mean', header: t('dataViewer.statMean'), cell: ({ row }) => row.original.mean != null ? formatNumber(row.original.mean, locale.value, 2) : '-' },
  { accessorKey: 'sum', header: t('dataViewer.statSum'), cell: ({ row }) => row.original.sum != null ? formatNumber(row.original.sum, locale.value, 2) : '-' },
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
function setFacetChartRef(parameter: string, chart: ExplorerChartHandle | null) {
  if (chart)
    facetChartRefs.set(parameter, chart)
  else
    facetChartRefs.delete(parameter)
}
</script>

<template>
  <div class="space-y-4">
    <div>
      <h2 :id="dataTitleId" class="sr-only">
        {{ t('dataViewer.dataTitle') }}
      </h2>

      <!-- Query Transform Panel -->
      <QueryPanel
        v-if="allValues.length > 0"
        :data="allValues"
        :expected-columns="queryColumns"
        @data-transformed="handleDataTransformed"
      />

      <!-- View mode toggle -->
      <div class="flex justify-center">
        <div class="flex items-center gap-2 p-1 bg-gray-100 dark:bg-gray-800 rounded-lg">
          <UButton
            icon="i-ph-table"
            :aria-label="t('dataViewer.viewTable')"
            :aria-pressed="viewMode === 'table'"
            size="md"
            :variant="viewMode === 'table' ? 'solid' : 'ghost'"
            :color="viewMode === 'table' ? 'primary' : 'neutral'"
            @click="viewMode = 'table'"
          />
          <UButton
            icon="i-ph-chart-line"
            :aria-label="t('dataViewer.viewChart')"
            :aria-pressed="viewMode === 'graph'"
            size="md"
            :variant="viewMode === 'graph' ? 'solid' : 'ghost'"
            :color="viewMode === 'graph' ? 'primary' : 'neutral'"
            @click="viewMode = 'graph'"
          />
        </div>
      </div>

      <!-- Options bar -->
      <div class="flex flex-wrap items-center justify-between gap-x-4 gap-y-2">
        <span class="text-sm text-gray-500 dark:text-gray-400">
          <template v-if="valuesPending">{{ t('dataViewer.loadingValues') }}</template>
          <template v-else-if="isDataTransformed">{{ t('dataViewer.valuesTransformed', { count: displayData.length, total: allValues.length }) }}</template>
          <template v-else>{{ t('dataViewer.valuesCount', { count: allValues.length }) }}</template>
        </span>
        <div class="flex flex-wrap items-center gap-x-4 gap-y-2">
          <div v-if="viewMode === 'table'" class="flex items-center gap-2">
            <label for="data-viewer-columns" class="text-sm">{{ t('dataViewer.columns') }}{{ t('common.colon') }}</label>
            <USelectMenu id="data-viewer-columns" v-model="selectedColumns" :items="columnOptions" :disabled="!columnOptions.length" multiple class="w-40" />
          </div>
          <div class="flex items-center gap-1">
            <template v-if="viewMode === 'table'">
              <UTooltip :text="t('dataViewer.copyCurrentPage')">
                <UButton
                  size="xs" variant="ghost" icon="i-ph-copy" :aria-label="t('dataViewer.copyCurrentPage')" :disabled="valuesPending || !paginatedValues.length"
                  @click="copyCurrentPage"
                />
              </UTooltip>
              <UTooltip :text="t('dataViewer.copyAllValues')">
                <UButton
                  size="xs" variant="ghost" icon="i-ph-check" :aria-label="t('dataViewer.copyAllValues')" :disabled="valuesPending || !sortedValues.length"
                  @click="copyAllValues"
                />
              </UTooltip>
            </template>
            <UDropdownMenu :items="downloadMenuItems" :modal="false">
              <UButton size="xs" variant="ghost" icon="i-ph-download-simple" :aria-label="viewMode === 'graph' ? t('dataViewer.downloadChart') : t('dataViewer.download')" :disabled="valuesPending" />
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
          trailing-icon="i-ph-caret-down"
          block
          size="sm"
        />
        <template #content>
          <div class="pt-4 space-y-4">
            <!-- Display Options -->
            <div class="flex flex-wrap items-center gap-4">
              <div class="flex items-center gap-2">
                <label for="data-viewer-param-label" class="text-sm text-gray-600 dark:text-gray-300">{{ t('dataViewer.paramLabel') }}{{ t('common.colon') }}</label>
                <USelect id="data-viewer-param-label" v-model="paramLabelFormat" :items="paramLabelItems" class="w-56" />
              </div>
              <UCheckbox v-model="facetByParameter" :label="t('dataViewer.facetByParameter')" />
              <UCheckbox v-model="showTrendline" :label="t('dataViewer.trendline')" />
            </div>
          </div>
        </template>
      </UCollapsible>

      <!-- Content -->
      <UCard ref="card" tabindex="-1" role="group" :aria-labelledby="dataTitleId" class="outline-none" :ui="{ body: valuesPending ? 'flex items-center justify-center min-h-40' : '' }">
        <div v-if="valuesPending" class="flex items-center justify-center py-12">
          <UIcon name="i-ph-circle-notch" class="w-8 h-8 animate-spin text-primary-600 dark:text-primary-500" />
        </div>
        <template v-else>
          <!-- a refusal of a limit, in either view: the table area says what it is and what can be done -->
          <div v-if="limitNotice" ref="noticeBox">
            <LimitNotice v-bind="limitNotice" @apply="applyWindow" />
          </div>
          <div v-else-if="allValues.length === 0 && fetchErrorMessage" class="flex flex-col items-center justify-center gap-1 py-12 text-center text-red-600 dark:text-red-400">
            <span class="font-medium">{{ t('dataViewer.fetchError') }}</span>
            <span class="text-sm">{{ fetchErrorMessage }}</span>
          </div>
          <div v-else-if="allValues.length === 0" class="flex items-center justify-center py-12 text-gray-500 dark:text-gray-400">
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
              class="flex items-center justify-center py-12 text-gray-500 dark:text-gray-400"
            >
              {{ t('dataViewer.emptyHint') }}
            </div>
            <div
              v-else-if="(facetByParameter && facetedChartData.length === 0) || (!facetByParameter && !hasChartData)"
              class="flex items-center justify-center py-12 text-gray-500 dark:text-gray-400"
            >
              {{ t('dataViewer.noChartData') }}
            </div>
            <!-- Faceted charts (one per parameter) -->
            <div v-else-if="facetByParameter" class="space-y-6">
              <div
                v-for="facet in facetedChartData" :key="facet.parameter"
                class="bleed-stop border rounded-lg p-4 dark:border-gray-700"
              >
                <h4 class="text-sm font-medium mb-2">
                  {{ facet.label }}
                </h4>
                <!-- a figure, not an image: its own controls stay reachable; no landmark, one per facet -->
                <ExplorerChart
                  :ref="(chart: unknown) => setFacetChartRef(facet.parameter, chart as ExplorerChartHandle | null)"
                  :series="facet.series" :large="facet.large" :height="300" camera-file="newplot"
                  :label="t('dataViewer.facetChartLabel', { parameter: facet.label })"
                  style="--app-chart-max-width: 760px;"
                />
              </div>
            </div>
            <!-- Single combined chart -->
            <ExplorerChart
              v-else ref="chartRef" :series="chartSeries" :large="isLargeChart" :height="400" camera-file="newplot"
              :label="t('dataViewer.chartLabel')"
            />
          </div>
        </template>
        <template v-if="viewMode === 'table'" #footer>
          <div class="flex flex-wrap items-center justify-center gap-x-4 gap-y-2">
            <div class="flex items-center gap-2">
              <label for="data-viewer-page-size" class="text-sm">{{ t('dataViewer.rowsPerPage') }}{{ t('common.colon') }}</label>
              <USelect id="data-viewer-page-size" v-model="pageSize" :items="pageSizeOptions" class="w-20" />
            </div>
            <UPagination
              v-model:page="currentPage" :total="displayData.length" :items-per-page="pageSize"
              :sibling-count="pagerFitsRow ? 2 : 0" :show-edges="!pagerFitsRow"
              :ui="{ list: 'flex flex-wrap items-center justify-center gap-1', first: pagerFitsRow ? '' : 'hidden', last: pagerFitsRow ? '' : 'hidden' }"
            />
          </div>
        </template>
      </UCard>
      <!-- whose data it is and what was done to it, directly under the table or the chart (GH-4255) -->
      <ProviderCredit
        v-if="!valuesPending && allValues.length > 0"
        :provider="rowsProvider" :derived="rowsDerived"
        class="mt-3 px-1" data-testid="explorer-credit"
      />
    </div>
  </div>
</template>
