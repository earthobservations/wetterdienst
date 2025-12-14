<script setup lang="ts">
import type { TableColumn } from '@nuxt/ui'
import type { ParameterSelectionState } from '~/types/parameter-selection-state.type'
import type { StationSelectionState } from '~/types/station-selection-state.type'
import type { Value } from '~/types/value.type'
import { h } from 'vue'
import type { LineSeriesOption } from 'echarts/charts'
import type { ComposeOption } from 'echarts/core'
import type {
  TitleComponentOption,
  TooltipComponentOption,
  LegendComponentOption,
  GridComponentOption,
  DataZoomComponentOption,
  ToolboxComponentOption,
} from 'echarts/components'

type ChartOption = ComposeOption<
  | LineSeriesOption
  | TitleComponentOption
  | TooltipComponentOption
  | LegendComponentOption
  | GridComponentOption
  | DataZoomComponentOption
  | ToolboxComponentOption
>

const { parameterSelection, stationSelection } = defineProps<{
  parameterSelection: ParameterSelectionState['selection']
  stationSelection: StationSelectionState
}>()

// View mode toggle
type ViewMode = 'table' | 'graph'
const viewMode = ref<ViewMode>('table')

// Chart ref for image export
const chartRef = ref<{ getDataURL: (opts: { type: string, pixelRatio: number, backgroundColor: string }) => string } | null>(null)

// Chart display options
const showDatasetPrefix = ref(false)
const facetByParameter = ref(false)

// Trendline options
type TrendlineType = 'none' | 'linear' | 'moving-average'
const trendlineType = ref<TrendlineType>('none')
const trendlineOptions = [
  { label: 'None', value: 'none' },
  { label: 'Linear', value: 'linear' },
  { label: 'Moving Average', value: 'moving-average' },
]
const movingAverageWindow = ref(5)

// Performance options
const enableAnimation = ref(false)
const enableSampling = ref(true)
type SamplingType = 'lttb' | 'average' | 'max' | 'min' | 'sum'
const samplingType = ref<SamplingType>('lttb')
const samplingOptions = [
  { label: 'LTTB (best visual)', value: 'lttb' },
  { label: 'Average', value: 'average' },
  { label: 'Max', value: 'max' },
  { label: 'Min', value: 'min' },
  { label: 'Sum', value: 'sum' },
]

// Large data threshold - when to enable optimizations
const LARGE_DATA_THRESHOLD = 1000

// Data settings (API options)
const humanize = ref(true)
const convertUnits = ref(true)

// Parameter filter (initialized after allValues is defined)
const selectedParameters = ref<string[]>([])

const isInterpolationMode = computed(() => stationSelection.mode === 'interpolation')
const isSummaryMode = computed(() => stationSelection.mode === 'summary')

const apiEndpoint = computed(() => {
  if (isInterpolationMode.value)
    return '/api/interpolate'
  if (isSummaryMode.value)
    return '/api/summarize'
  return '/api/values'
})

const apiQuery = computed(() => {
  const base: Record<string, string | number | boolean | undefined> = {
    provider: parameterSelection.provider,
    network: parameterSelection.network,
    parameters: parameterSelection.parameters.map(parameter => `${parameterSelection.resolution}/${parameterSelection.dataset}/${parameter}`).join(','),
    humanize: humanize.value,
    convert_units: convertUnits.value,
  }

  // Add date range if provided
  if (stationSelection.dateRange.startDate) {
    base.date = stationSelection.dateRange.startDate
    if (stationSelection.dateRange.endDate) {
      base.date = `${stationSelection.dateRange.startDate}/${stationSelection.dateRange.endDate}`
    }
  }

  if (isInterpolationMode.value || isSummaryMode.value) {
    const interp = stationSelection.interpolation
    return {
      ...base,
      latitude: interp.latitude,
      longitude: interp.longitude,
    }
  }
  else {
    return {
      ...base,
      station: stationSelection.selection.stations.map(station => station.station_id).join(','),
    }
  }
})

const { data: valuesData, pending: valuesPending, refresh: refreshValues } = useFetch<{
  values: Value[]
}>(
  apiEndpoint,
  {
    method: 'GET',
    query: apiQuery,
    immediate: false,
    default: () => ({ values: [] }),
  },
)

const allValues = computed(() => valuesData.value?.values ?? [])

function formatDate(dateStr: string) {
  // Remove unnecessary microseconds (.000000) and simplify timezone
  // 1934-01-01T00:00:00.000000+00:00 -> 1934-01-01T00:00:00Z
  return dateStr.replace(/\.0+([+-])/, '$1').replace(/[+-]00:00$/, 'Z')
}

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

// Parameter filter computeds (must be after allValues and sortedValues)
const availableParameters = computed(() => {
  const params = new Set<string>()
  for (const value of allValues.value) {
    params.add(value.parameter)
  }
  return Array.from(params).sort()
})

// Initialize selected parameters when data loads
watch(availableParameters, (params) => {
  if (params.length > 0 && selectedParameters.value.length === 0) {
    selectedParameters.value = [...params]
  }
}, { immediate: true })

// Filtered values based on selected parameters
const filteredValues = computed(() => {
  if (selectedParameters.value.length === 0)
    return sortedValues.value
  return sortedValues.value.filter(v => selectedParameters.value.includes(v.parameter))
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
  const params = new URLSearchParams()
  params.set('provider', parameterSelection.provider ?? '')
  params.set('network', parameterSelection.network ?? '')
  params.set('parameters', parameterSelection.parameters.map(parameter => `${parameterSelection.resolution}/${parameterSelection.dataset}/${parameter}`).join(','))
  params.set('format', format)

  // Add date range if provided
  if (stationSelection.dateRange.startDate) {
    let dateParam = stationSelection.dateRange.startDate
    if (stationSelection.dateRange.endDate) {
      dateParam = `${stationSelection.dateRange.startDate}/${stationSelection.dateRange.endDate}`
    }
    params.set('date', dateParam)
  }

  let endpoint = '/api/values'
  let filename = 'values'
  if (isInterpolationMode.value) {
    endpoint = '/api/interpolate'
    filename = 'interpolated'
    const interp = stationSelection.interpolation
    if (interp.latitude !== undefined)
      params.set('latitude', interp.latitude.toString())
    if (interp.longitude !== undefined)
      params.set('longitude', interp.longitude.toString())
  }
  else if (isSummaryMode.value) {
    endpoint = '/api/summary'
    filename = 'summary'
    const interp = stationSelection.interpolation
    if (interp.latitude !== undefined)
      params.set('latitude', interp.latitude.toString())
    if (interp.longitude !== undefined)
      params.set('longitude', interp.longitude.toString())
  }
  else {
    params.set('station', stationSelection.selection.stations.map(station => station.station_id).join(','))
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

function downloadChartImage(format: 'png' | 'jpeg' | 'svg') {
  const chart = chartRef.value
  if (!chart)
    return

  const dataUrl = chart.getDataURL({
    type: format === 'jpeg' ? 'jpeg' : 'png',
    pixelRatio: 2,
    backgroundColor: '#fff',
  })

  const link = document.createElement('a')
  link.href = dataUrl
  link.download = `chart.${format}`
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)

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
  if (!parameterSelection.parameters.length)
    return false

  if (stationSelection.mode === 'station') {
    return stationSelection.selection.stations.length > 0
  }
  else {
    const interp = stationSelection.interpolation
    return interp.latitude !== undefined && interp.longitude !== undefined
  }
})

watch(
  () => [parameterSelection, stationSelection],
  () => {
    if (!canFetchData.value) {
      valuesData.value = { values: [] }
      return
    }
    refreshValues()
    currentPage.value = 1
  },
  { deep: true, immediate: true },
)

// ECharts data preparation
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
function calculateLinearRegression(data: [number, number][]): [number, number][] {
  if (data.length < 2)
    return []

  const n = data.length
  let sumX = 0
  let sumY = 0
  let sumXY = 0
  let sumXX = 0

  for (const [x, y] of data) {
    sumX += x
    sumY += y
    sumXY += x * y
    sumXX += x * x
  }

  const slope = (n * sumXY - sumX * sumY) / (n * sumXX - sumX * sumX)
  const intercept = (sumY - slope * sumX) / n

  const minX = Math.min(...data.map(d => d[0]))
  const maxX = Math.max(...data.map(d => d[0]))

  return [
    [minX, slope * minX + intercept],
    [maxX, slope * maxX + intercept],
  ]
}

// Moving average calculation
function calculateMovingAverage(data: [number, number][], windowSize: number): [number, number][] {
  if (data.length < windowSize)
    return []

  const sorted = [...data].sort((a, b) => a[0] - b[0])
  const result: [number, number][] = []

  for (let i = windowSize - 1; i < sorted.length; i++) {
    let sum = 0
    for (let j = 0; j < windowSize; j++) {
      sum += sorted[i - j]![1]
    }
    result.push([sorted[i]![0], sum / windowSize])
  }

  return result
}

// Helper to adjust color opacity
function hexToRgba(hex: string, alpha: number): string {
  const r = Number.parseInt(hex.slice(1, 3), 16)
  const g = Number.parseInt(hex.slice(3, 5), 16)
  const b = Number.parseInt(hex.slice(5, 7), 16)
  return `rgba(${r}, ${g}, ${b}, ${alpha})`
}

// ECharts options for single chart
const chartOptions = computed((): ChartOption => {
  if (!filteredValues.value.length)
    return {}

  // Group values by series (station + parameter combination)
  const seriesMap = new Map<string, [number, number][]>()

  for (const value of filteredValues.value) {
    const parameterLabel = showDatasetPrefix.value
      ? `${value.dataset}/${value.parameter}`
      : value.parameter
    const seriesKey = stationSelection.mode === 'station'
      ? `${value.station_id} - ${parameterLabel}`
      : parameterLabel

    if (!seriesMap.has(seriesKey)) {
      seriesMap.set(seriesKey, [])
    }

    if (value.value !== null && value.value !== undefined) {
      seriesMap.get(seriesKey)!.push([new Date(value.date).getTime(), value.value])
    }
  }

  // Convert to ECharts series
  const series: LineSeriesOption[] = []
  let colorIndex = 0

  for (const [seriesKey, data] of seriesMap) {
    const color = chartColors[colorIndex % chartColors.length] ?? '#3b82f6'

    // Sort data by time
    const sortedData = [...data].sort((a, b) => a[0] - b[0])

    // Performance optimizations for large datasets
    const seriesIsLarge = sortedData.length > LARGE_DATA_THRESHOLD

    // Main data series
    series.push({
      name: seriesKey,
      type: 'line',
      data: sortedData,
      // Disable smooth for large datasets (CPU intensive)
      smooth: !seriesIsLarge,
      // Hide symbols for large datasets
      symbol: seriesIsLarge ? 'none' : 'circle',
      symbolSize: 8,
      // Enable sampling for large datasets
      sampling: enableSampling.value ? samplingType.value : undefined,
      itemStyle: {
        color,
      },
      lineStyle: {
        color,
        width: seriesIsLarge ? 1 : 2,
      },
    })

    // Add trendline if enabled
    if (trendlineType.value === 'linear' && sortedData.length >= 2) {
      const trendData = calculateLinearRegression(sortedData)
      series.push({
        name: `${seriesKey} (trend)`,
        type: 'line',
        data: trendData,
        smooth: false,
        symbol: 'none',
        lineStyle: {
          color: hexToRgba(color, 0.5),
          width: 2,
          type: 'dashed',
        },
      })
    }
    else if (trendlineType.value === 'moving-average' && sortedData.length >= movingAverageWindow.value) {
      const maData = calculateMovingAverage(sortedData, movingAverageWindow.value)
      series.push({
        name: `${seriesKey} (MA${movingAverageWindow.value})`,
        type: 'line',
        data: maData,
        smooth: !seriesIsLarge,
        symbol: 'none',
        sampling: enableSampling.value ? samplingType.value : undefined,
        lineStyle: {
          color: hexToRgba(color, 0.7),
          width: 2,
          type: 'dotted',
        },
      })
    }

    colorIndex++
  }

  return {
    // Disable animation for better performance
    animation: enableAnimation.value,
    animationThreshold: LARGE_DATA_THRESHOLD,
    tooltip: {
      trigger: 'axis',
      axisPointer: {
        type: 'cross',
      },
      // Limit tooltip items for large datasets
      confine: true,
    },
    legend: {
      type: 'scroll',
      bottom: 0,
    },
    grid: {
      left: '3%',
      right: '4%',
      bottom: '15%',
      containLabel: true,
    },
    toolbox: {
      feature: {
        dataZoom: {
          yAxisIndex: 'none',
        },
        restore: {},
      },
    },
    dataZoom: [
      {
        type: 'inside',
        start: 0,
        end: 100,
        // Throttle for performance
        throttle: 100,
      },
      {
        start: 0,
        end: 100,
        throttle: 100,
      },
    ],
    xAxis: {
      type: 'time',
      name: 'Date',
      nameLocation: 'middle',
      nameGap: 30,
    },
    yAxis: {
      type: 'value',
      name: 'Value',
      nameLocation: 'middle',
      nameGap: 50,
    },
    series,
  }
})

// Check if chart has data
const hasChartData = computed(() => {
  const options = chartOptions.value
  return options.series && Array.isArray(options.series) && options.series.length > 0
})

// For faceted charts - group data by parameter
const facetedChartOptions = computed((): { parameter: string, options: ChartOption }[] => {
  if (!facetByParameter.value || !filteredValues.value.length)
    return []

  const parameterGroups = new Map<string, Map<string, [number, number][]>>()

  for (const value of filteredValues.value) {
    const param = value.parameter
    if (!parameterGroups.has(param)) {
      parameterGroups.set(param, new Map())
    }

    const stationKey = stationSelection.mode === 'station' ? value.station_id : 'interpolated'
    const stationMap = parameterGroups.get(param)!

    if (!stationMap.has(stationKey)) {
      stationMap.set(stationKey, [])
    }

    if (value.value !== null && value.value !== undefined) {
      stationMap.get(stationKey)!.push([new Date(value.date).getTime(), value.value])
    }
  }

  const result: { parameter: string, options: ChartOption }[] = []

  for (const [parameter, stationMap] of parameterGroups) {
    const series: LineSeriesOption[] = []
    let colorIndex = 0

    for (const [stationKey, data] of stationMap) {
      const color = chartColors[colorIndex % chartColors.length] ?? '#3b82f6'
      const sortedData = [...data].sort((a, b) => a[0] - b[0])

      // Performance optimizations for large datasets
      const seriesIsLarge = sortedData.length > LARGE_DATA_THRESHOLD

      series.push({
        name: stationKey,
        type: 'line',
        data: sortedData,
        smooth: !seriesIsLarge,
        symbol: seriesIsLarge ? 'none' : 'circle',
        symbolSize: 8,
        sampling: enableSampling.value ? samplingType.value : undefined,
        itemStyle: {
          color,
        },
        lineStyle: {
          color,
          width: seriesIsLarge ? 1 : 2,
        },
      })

      // Add trendline if enabled
      if (trendlineType.value === 'linear' && sortedData.length >= 2) {
        const trendData = calculateLinearRegression(sortedData)
        series.push({
          name: `${stationKey} (trend)`,
          type: 'line',
          data: trendData,
          smooth: false,
          symbol: 'none',
          lineStyle: {
            color: hexToRgba(color, 0.5),
            width: 2,
            type: 'dashed',
          },
        })
      }
      else if (trendlineType.value === 'moving-average' && sortedData.length >= movingAverageWindow.value) {
        const maData = calculateMovingAverage(sortedData, movingAverageWindow.value)
        series.push({
          name: `${stationKey} (MA${movingAverageWindow.value})`,
          type: 'line',
          data: maData,
          smooth: !seriesIsLarge,
          symbol: 'none',
          sampling: enableSampling.value ? samplingType.value : undefined,
          lineStyle: {
            color: hexToRgba(color, 0.7),
            width: 2,
            type: 'dotted',
          },
        })
      }

      colorIndex++
    }

    result.push({
      parameter,
      options: {
        animation: enableAnimation.value,
        animationThreshold: LARGE_DATA_THRESHOLD,
        tooltip: {
          trigger: 'axis',
          axisPointer: {
            type: 'cross',
          },
          confine: true,
        },
        legend: {
          type: 'scroll',
          bottom: 0,
        },
        grid: {
          left: '3%',
          right: '4%',
          bottom: '15%',
          containLabel: true,
        },
        dataZoom: [
          {
            type: 'inside',
            start: 0,
            end: 100,
            throttle: 100,
          },
        ],
        xAxis: {
          type: 'time',
          name: 'Date',
          nameLocation: 'middle',
          nameGap: 30,
        },
        yAxis: {
          type: 'value',
          name: parameter,
          nameLocation: 'middle',
          nameGap: 50,
        },
        series,
      },
    })
  }

  return result
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
</script>

<template>
  <div class="space-y-4">
    <!-- Data Options (applies to both table and graph) -->
    <div class="flex justify-center gap-4">
      <UCheckbox v-model="humanize" label="Humanize parameters" />
      <UCheckbox v-model="convertUnits" label="Convert to SI units" />
    </div>

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
        <template v-else>{{ filteredValues.length }} / {{ allValues.length }} values</template>
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
          <!-- Parameter Filter -->
          <div class="flex flex-wrap items-center gap-2">
            <span class="text-sm font-medium">Parameters:</span>
            <USelectMenu
              v-model="selectedParameters"
              :items="availableParameters"
              multiple
              class="min-w-40"
              placeholder="Select parameters"
            />
            <UButton size="xs" variant="ghost" @click="selectedParameters = [...availableParameters]">
              All
            </UButton>
            <UButton size="xs" variant="ghost" @click="selectedParameters = []">
              None
            </UButton>
          </div>

          <!-- Display Options -->
          <div class="flex flex-wrap items-center gap-4">
            <UCheckbox v-model="showDatasetPrefix" label="Dataset prefix" />
            <UCheckbox v-model="facetByParameter" label="Facet by parameter" />
          </div>

          <!-- Trendline Settings -->
          <div class="flex flex-wrap items-center gap-4">
            <div class="flex items-center gap-2">
              <span class="text-sm">Trendline:</span>
              <USelect v-model="trendlineType" :items="trendlineOptions" class="w-40" />
            </div>
            <div v-if="trendlineType === 'moving-average'" class="flex items-center gap-2">
              <span class="text-sm">Window:</span>
              <input
                v-model.number="movingAverageWindow"
                type="number"
                min="2"
                max="50"
                class="w-16 px-2 py-1 border rounded text-sm dark:bg-gray-800 dark:border-gray-700"
              >
            </div>
          </div>

          <!-- Performance Settings -->
          <div class="border-t pt-4 dark:border-gray-700">
            <span class="text-sm font-medium text-gray-600 dark:text-gray-400">Performance</span>
            <div class="flex flex-wrap items-center gap-4 mt-2">
              <UCheckbox v-model="enableAnimation" label="Animation" />
              <UCheckbox v-model="enableSampling" label="Sampling" />
              <div v-if="enableSampling" class="flex items-center gap-2">
                <span class="text-sm">Method:</span>
                <USelect v-model="samplingType" :items="samplingOptions" class="w-40" />
              </div>
            </div>
            <p class="text-xs text-gray-500 mt-2">
              Large datasets (>{{ LARGE_DATA_THRESHOLD }} points) auto-optimize: no smooth curves, no markers, progressive rendering
            </p>
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
          <div v-if="(facetByParameter && facetedChartOptions.length === 0) || (!facetByParameter && !hasChartData)" class="flex items-center justify-center py-12 text-gray-500">
            No data available for chart
          </div>
          <!-- Faceted charts (one per parameter) -->
          <div v-else-if="facetByParameter" class="space-y-6">
            <div v-for="facet in facetedChartOptions" :key="facet.parameter" class="border rounded-lg p-4 dark:border-gray-700">
              <h4 class="text-sm font-medium mb-2">{{ facet.parameter }}</h4>
              <div class="w-full" style="height: 300px;">
                <VChart :option="facet.options" autoresize />
              </div>
            </div>
          </div>
          <!-- Single combined chart -->
          <div v-else class="w-full" style="height: 400px;">
            <VChart ref="chartRef" :option="chartOptions" autoresize />
          </div>
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
