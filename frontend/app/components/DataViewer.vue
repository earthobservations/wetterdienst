<script setup lang="ts">
import type { TableColumn } from '@nuxt/ui'
import type { Config as PlotlyConfig, Data as PlotlyData, Layout as PlotlyLayout } from 'plotly.js-dist-min'
import type { DataSettings } from '~/types/data-settings.type'
import type { ParameterSelectionState } from '~/types/parameter-selection-state.type'
import type { StationSelectionState } from '~/types/station-selection-state.type'
import { h } from 'vue'
import { formatDate } from '~/utils/format'

const props = defineProps<{
  parameterSelection: ParameterSelectionState['selection']
  stationSelection: StationSelectionState
  settings: DataSettings
}>()

// Safe accessors for props to prevent reactivity issues
const stationSelection = computed(() => {
  if (!props.stationSelection) {
    return {
      mode: 'station' as const,
      selection: { stations: [] as { station_id: string }[] },
      interpolation: { source: 'manual' as const, latitude: undefined, longitude: undefined, station: undefined },
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
const plotlyLoaded = ref(false)
let Plotly: typeof import('plotly.js-dist-min') | null = null

// Parameter label format options and chart display
// Options: 'parameter' (default), 'dataset/parameter', 'resolution/dataset/parameter'
type ParamLabelFormat = 'parameter' | 'dataset/parameter' | 'resolution/dataset/parameter'
const paramLabelFormat = ref<ParamLabelFormat>('parameter')
const facetByParameter = ref(false)

// Available items for the parameter label selector
const paramLabelItems = computed(() => [
  { label: 'Parameter', value: 'parameter' },
  { label: 'Dataset / Parameter', value: 'dataset/parameter' },
  { label: 'Resolution / Dataset / Parameter', value: 'resolution/dataset/parameter' },
])

// Trendline option
const showTrendline = ref(false)

const isInterpolationMode = computed(() => stationSelection.value.mode === 'interpolation')
const isSummaryMode = computed(() => stationSelection.value.mode === 'summary')

const apiEndpoint = computed(() => {
  if (isInterpolationMode.value)
    return '/api/interpolate'
  if (isSummaryMode.value)
    return '/api/summarize'
  return '/api/values'
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
    .filter(([_, value]) => value != null && value !== undefined && String(value).trim() !== '')
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

  if (isInterpolationMode.value || isSummaryMode.value) {
    const interp = ss.interpolation
    // Add interpolation-specific settings
    if (isInterpolationMode.value) {
      const query: Record<string, any> = {
        ...base,
        latitude: interp?.latitude,
        longitude: interp?.longitude,
        use_nearby_station_distance: props.settings.useNearbyStationDistance,
      }
      // Add interpolation station distance if provided (filter out empty values)
      const stationDistance = Object.entries(props.settings.interpolationStationDistance)
        .filter(([_, value]) => value != null && value !== undefined && String(value).trim() !== '')
        .reduce((acc, [key, value]) => ({ ...acc, [key]: value }), {})

      if (Object.keys(stationDistance).length > 0) {
        query.interpolation_station_distance = JSON.stringify(stationDistance)
      }
      // Add advanced interpolation settings if different from defaults
      if (props.settings.minGainOfValuePairs !== 0.10) {
        query.min_gain_of_value_pairs = props.settings.minGainOfValuePairs
      }
      if (props.settings.numAdditionalStations !== 3) {
        query.num_additional_stations = props.settings.numAdditionalStations
      }
      return query
    }
    return {
      ...base,
      latitude: interp?.latitude,
      longitude: interp?.longitude,
    }
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

const { data: valuesData, pending: valuesPending, refresh: refreshValues } = useFetch<ValuesResponse>(
  apiEndpoint,
  {
    method: 'GET',
    query: apiQuery,
    immediate: false,
    default: () => ({ values: [] }),
  },
)

const allValues = computed(() => valuesData.value?.values ?? [])

const columnDefinitions: { key: keyof Value, column: TableColumn<Value> }[] = [
  { key: 'station_id', column: { accessorKey: 'station_id', header: 'station_id' } },
  { key: 'resolution', column: { accessorKey: 'resolution', header: 'resolution' } },
  { key: 'dataset', column: { accessorKey: 'dataset', header: 'dataset' } },
  { key: 'parameter', column: { accessorKey: 'parameter', header: 'parameter' } },
  { key: 'date', column: { accessorKey: 'date', header: 'date', cell: ({ row }) => formatDate(row.original.date) } },
  { key: 'value', column: { accessorKey: 'value', header: 'value' } },
  { key: 'quality', column: { accessorKey: 'quality', header: 'quality' } },
  { key: 'taken_station_id', column: { accessorKey: 'taken_station_id', header: 'taken_station_id' } },
  { key: 'taken_station_ids', column: { accessorKey: 'taken_station_ids', header: 'taken_station_ids' } },
]

// Sorting
const sortColumn = ref<keyof Value | null>(null)
const sortDirection = ref<'asc' | 'desc'>('asc')

function toggleSort(column: keyof Value) {
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

function getSortIcon(column: keyof Value) {
  if (sortColumn.value !== column)
    return '↕'
  return sortDirection.value === 'asc' ? '↑' : '↓'
}

const sortedValues = computed(() => {
  if (!sortColumn.value)
    return allValues.value

  return [...allValues.value].sort((a, b) => {
    const aVal = a[sortColumn.value!]
    const bVal = b[sortColumn.value!]

    if (aVal === null || aVal === undefined)
      return 1
    if (bVal === null || bVal === undefined)
      return -1

    let comparison = 0
    if (typeof aVal === 'number' && typeof bVal === 'number') {
      comparison = aVal - bVal
    }
    else {
      comparison = String(aVal).localeCompare(String(bVal))
    }

    return sortDirection.value === 'asc' ? comparison : -comparison
  })
})

const columnOptions = columnDefinitions.map(c => c.key)

// Default columns based on mode
const defaultColumns = computed((): (keyof Value)[] => {
  const base: (keyof Value)[] = ['station_id', 'parameter', 'date', 'value', 'quality']
  if (isSummaryMode.value) {
    return [...base, 'taken_station_id']
  }
  if (isInterpolationMode.value) {
    return [...base, 'taken_station_ids']
  }
  return base
})

const selectedColumns = ref<(keyof Value)[]>([...defaultColumns.value])

// Update selected columns when mode changes
watch([isInterpolationMode, isSummaryMode], () => {
  selectedColumns.value = [...defaultColumns.value]
})

const columns = computed(() =>
  columnDefinitions.filter(c => selectedColumns.value.includes(c.key)).map((c) => {
    const key = c.key
    return {
      ...c.column,
      header: () => h('span', {
        class: 'cursor-pointer select-none flex items-center gap-1',
        onClick: () => toggleSort(key),
      }, [
        c.key,
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

watch(pageSize, () => {
  currentPage.value = 1
})

const toast = useToast()

function valuesToCsv(values: Value[]) {
  if (!values.length)
    return ''
  const headers = selectedColumns.value
  const rows = values.map(row => headers.map(h => row[h] ?? '').join(','))
  return [headers.join(','), ...rows].join('\n')
}

async function copyCurrentPage() {
  await navigator.clipboard.writeText(valuesToCsv(paginatedValues.value))
  toast.add({ title: 'Copied', description: `${paginatedValues.value.length} rows copied to clipboard`, color: 'success' })
}

async function copyAllValues() {
  await navigator.clipboard.writeText(valuesToCsv(sortedValues.value))
  toast.add({ title: 'Copied', description: `${sortedValues.value.length} rows copied to clipboard`, color: 'success' })
}

async function downloadValues(format: string, extension: string) {
  const ps = parameterSelection.value
  const ss = stationSelection.value
  const params = new URLSearchParams()
  params.set('provider', ps.provider ?? '')
  params.set('network', ps.network ?? '')
  params.set('parameters', ps.parameters.map(parameter => `${ps.resolution}/${ps.dataset}/${parameter}`).join(','))
  params.set('format', format)

  // Add date range if provided
  if (ss.dateRange?.startDate) {
    let dateParam = ss.dateRange.startDate
    if (ss.dateRange.endDate) {
      dateParam = `${ss.dateRange.startDate}/${ss.dateRange.endDate}`
    }
    params.set('date', dateParam)
  }

  let endpoint = '/api/values'
  let filename = 'values'
  if (isInterpolationMode.value) {
    endpoint = '/api/interpolate'
    filename = 'interpolated'
    const interp = ss.interpolation
    if (interp?.latitude !== undefined)
      params.set('latitude', interp.latitude.toString())
    if (interp?.longitude !== undefined)
      params.set('longitude', interp.longitude.toString())
  }
  else if (isSummaryMode.value) {
    endpoint = '/api/summary'
    filename = 'summary'
    const interp = ss.interpolation
    if (interp?.latitude !== undefined)
      params.set('latitude', interp.latitude.toString())
    if (interp?.longitude !== undefined)
      params.set('longitude', interp.longitude.toString())
  }
  else {
    params.set('station', ss.selection?.stations?.map(station => station.station_id).join(',') ?? '')
  }

  const response = await fetch(`${endpoint}?${params.toString()}`)
  const data = await response.text()

  const blob = new Blob([data], { type: 'application/octet-stream' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = `${filename}.${extension}`
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  URL.revokeObjectURL(url)

  toast.add({ title: 'Downloaded', description: `Values downloaded as ${format.toUpperCase()}`, color: 'success' })
}

async function downloadChartImage(format: 'png' | 'jpeg' | 'svg') {
  if (!Plotly || !chartRef.value)
    return

  await Plotly.downloadImage(chartRef.value, {
    format: format === 'jpeg' ? 'jpeg' : format === 'svg' ? 'svg' : 'png',
    filename: 'chart',
    // Plotly expects number | undefined for width/height; use undefined to let it auto-size
    width: undefined,
    height: undefined,
  })

  toast.add({ title: 'Downloaded', description: `Chart downloaded as ${format.toUpperCase()}`, color: 'success' })
}

const downloadMenuItems = computed(() => {
  if (viewMode.value === 'graph') {
    return [
      [
        { label: 'PNG', onSelect: () => downloadChartImage('png') },
        { label: 'JPEG', onSelect: () => downloadChartImage('jpeg') },
        { label: 'SVG', onSelect: () => downloadChartImage('svg') },
      ],
    ]
  }
  return [
    [
      { label: 'CSV', onSelect: () => downloadValues('csv', 'csv') },
      { label: 'JSON', onSelect: () => downloadValues('json', 'json') },
      { label: 'GeoJSON', onSelect: () => downloadValues('geojson', 'geojson') },
    ],
  ]
})

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

// Watch specific properties to trigger data fetching
watch(
  () => {
    const ps = parameterSelection.value
    const ss = stationSelection.value
    return [
      ps?.provider,
      ps?.network,
      ps?.resolution,
      ps?.dataset,
      ps?.parameters?.join(','),
      ss?.mode,
      ss?.selection?.stations?.map(s => s.station_id).join(','),
      ss?.interpolation?.latitude,
      ss?.interpolation?.longitude,
      ss?.dateRange?.startDate,
      ss?.dateRange?.endDate,
      props.settings.humanize,
      props.settings.convertUnits,
      JSON.stringify(props.settings.unitTargets),
      props.settings.shape,
      props.settings.skipEmpty,
      props.settings.skipThreshold,
      props.settings.skipCriteria,
      props.settings.dropNulls,
      props.settings.useNearbyStationDistance,
      JSON.stringify(props.settings.interpolationStationDistance),
      props.settings.minGainOfValuePairs,
      props.settings.numAdditionalStations,
    ]
  },
  () => {
    if (!canFetchData.value) {
      valuesData.value = { values: [] }
      return
    }
    refreshValues()
    currentPage.value = 1
  },
  { immediate: true },
)

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

// Plotly traces for single chart
const chartTraces = computed(() => {
  const ss = stationSelection.value
  if (!sortedValues.value.length || !ss.mode)
    return []

  // Group values by series (station + parameter combination)
  const seriesMap = new Map<string, { x: Date[], y: number[] }>()
  const mode = ss.mode

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

    if (value.value !== null && value.value !== undefined) {
      const series = seriesMap.get(seriesKey)!
      series.x.push(new Date(value.date))
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
  const ss = stationSelection.value
  if (!facetByParameter.value || !sortedValues.value.length || !ss.mode)
    return []

  const parameterGroups = new Map<string, Map<string, { x: Date[], y: number[] }>>()
  const mode = ss.mode

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

    if (value.value !== null && value.value !== undefined) {
      const series = stationMap.get(stationKey)!
      series.x.push(new Date(value.date))
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

// Plotly layout - optimized for large datasets
const chartLayout = computed((): Partial<PlotlyLayout> => {
  const isLargeDataset = sortedValues.value.length > LARGE_DATASET_THRESHOLD
  return {
    autosize: true,
    margin: { l: 60, r: 20, t: 40, b: 60 },
    xaxis: {
      title: 'Date',
      type: 'date',
    },
    yaxis: {
      title: 'Value',
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

// Render chart helper functions
async function renderMainChart() {
  if (!Plotly || !plotlyLoaded.value || viewMode.value !== 'graph' || facetByParameter.value)
    return

  await nextTick()
  if (chartRef.value && chartTraces.value.length > 0) {
    // Use newPlot for clean initialization
    Plotly.purge(chartRef.value)
    await Plotly.newPlot(chartRef.value, chartTraces.value, chartLayout.value, plotlyConfig)
  }
}

async function renderFacetedCharts() {
  if (!Plotly || !plotlyLoaded.value || viewMode.value !== 'graph' || !facetByParameter.value)
    return

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
      await Plotly.react(el, facet.traces, layout, plotlyConfig)
    }
  }
}

// Load Plotly and render charts
onMounted(async () => {
  Plotly = await import('plotly.js-dist-min')
  plotlyLoaded.value = true

  // Initial render after Plotly loads
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
  if (!allValues.value.length)
    return []

  const statsMap = new Map<string, { values: number[], dataset: string }>()

  for (const value of allValues.value) {
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

const statsTableColumns: TableColumn<ParameterStats>[] = [
  { accessorKey: 'dataset', header: 'Dataset' },
  { accessorKey: 'parameter', header: 'Parameter' },
  { accessorKey: 'count', header: 'Count' },
  { accessorKey: 'min', header: 'Min', cell: ({ row }) => row.original.min?.toFixed(2) ?? '-' },
  { accessorKey: 'max', header: 'Max', cell: ({ row }) => row.original.max?.toFixed(2) ?? '-' },
  { accessorKey: 'mean', header: 'Mean', cell: ({ row }) => row.original.mean?.toFixed(2) ?? '-' },
  { accessorKey: 'sum', header: 'Sum', cell: ({ row }) => row.original.sum?.toFixed(2) ?? '-' },
]

// Expose stats for parent component
defineExpose({
  parameterStats,
  statsTableColumns,
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
        <template v-if="valuesPending">Loading values...</template>
        <template v-else>{{ allValues.length }} values</template>
      </span>
      <div class="flex items-center gap-4">
        <div v-if="viewMode === 'table'" class="flex items-center gap-2">
          <span class="text-sm">Columns:</span>
          <USelectMenu v-model="selectedColumns" :items="columnOptions" multiple class="w-40" />
        </div>
        <div class="flex items-center gap-1">
          <template v-if="viewMode === 'table'">
            <UTooltip text="Copy current page">
              <UButton size="xs" variant="ghost" icon="i-lucide-copy" :disabled="valuesPending" @click="copyCurrentPage" />
            </UTooltip>
            <UTooltip text="Copy all values">
              <UButton size="xs" variant="ghost" icon="i-lucide-copy-check" :disabled="valuesPending" @click="copyAllValues" />
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
        label="Chart Settings"
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
              <label class="text-sm text-gray-600 dark:text-gray-300">Parameter label:</label>
              <USelect v-model="paramLabelFormat" :items="paramLabelItems" class="w-56" />
            </div>
            <UCheckbox v-model="facetByParameter" label="Facet by parameter" />
            <UCheckbox v-model="showTrendline" label="Trendline" />
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
        <UTable v-if="viewMode === 'table'" :data="paginatedValues" :columns="columns" sticky :ui="{ td: 'py-1 px-2', th: 'py-1 px-2' }" />
        <div v-else class="py-4">
          <div v-if="(facetByParameter && facetedChartData.length === 0) || (!facetByParameter && !hasChartData)" class="flex items-center justify-center py-12 text-gray-500">
            No data available for chart
          </div>
          <!-- Faceted charts (one per parameter) -->
          <div v-else-if="facetByParameter" class="space-y-6">
            <div v-for="facet in facetedChartData" :key="facet.parameter" class="border rounded-lg p-4 dark:border-gray-700">
              <h4 class="text-sm font-medium mb-2">
                {{ facet.parameter }}
              </h4>
              <div :ref="el => setFacetChartRef(facet.parameter, el as HTMLDivElement)" class="w-full" style="height: 300px;" />
            </div>
          </div>
          <!-- Single combined chart -->
          <div v-else ref="chartRef" class="w-full overflow-visible" style="height: 400px;" />
        </div>
      </template>
      <template v-if="viewMode === 'table'" #footer>
        <div class="flex items-center justify-center gap-4">
          <div class="flex items-center gap-2">
            <span class="text-sm">Rows per page:</span>
            <USelect v-model="pageSize" :items="pageSizeOptions" class="w-20" />
          </div>
          <UPagination v-model:page="currentPage" :total="allValues.length" :items-per-page="pageSize" />
        </div>
      </template>
    </UCard>
  </div>
</template>
