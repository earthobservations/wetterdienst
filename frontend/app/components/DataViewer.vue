<script setup lang="ts">
import type { TableColumn } from '@nuxt/ui'
import type { ParameterSelectionState } from '~/types/parameter-selection-state.type'
import type { StationSelectionState } from '~/types/station-selection-state.type'
import type { Value } from '~/types/value.type'
import { h } from 'vue'

const { parameterSelection, stationSelection } = defineProps<{
  parameterSelection: ParameterSelectionState['selection']
  stationSelection: StationSelectionState
}>()

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
  const base: Record<string, string | number | undefined> = {
    provider: parameterSelection.provider,
    network: parameterSelection.network,
    parameters: parameterSelection.parameters.map(parameter => `${parameterSelection.resolution}/${parameterSelection.dataset}/${parameter}`).join(','),
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

const downloadMenuItems = computed(() => [
  [
    { label: 'CSV', onSelect: () => downloadValues('csv', 'csv') },
    { label: 'JSON', onSelect: () => downloadValues('json', 'json') },
    { label: 'GeoJSON', onSelect: () => downloadValues('geojson', 'geojson') },
  ],
])

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
</script>

<template>
  <UCard :ui="{ body: valuesPending ? 'flex items-center justify-center min-h-40' : '' }">
    <template #header>
      <div class="flex items-center justify-between">
        <span class="text-sm text-gray-500">
          <template v-if="valuesPending">Loading values...</template>
          <template v-else>{{ allValues.length }} total values</template>
        </span>
        <div class="flex items-center gap-4">
          <div class="flex items-center gap-2">
            <span class="text-sm">Columns:</span>
            <USelectMenu v-model="selectedColumns" :items="columnOptions" multiple class="w-40" />
          </div>
          <div class="flex items-center gap-1">
            <UTooltip text="Copy current page">
              <UButton size="xs" variant="ghost" icon="i-lucide-copy" :disabled="valuesPending" @click="copyCurrentPage" />
            </UTooltip>
            <UTooltip text="Copy all values">
              <UButton size="xs" variant="ghost" icon="i-lucide-copy-check" :disabled="valuesPending" @click="copyAllValues" />
            </UTooltip>
            <UDropdownMenu :items="downloadMenuItems">
              <UButton size="xs" variant="ghost" icon="i-lucide-download" :disabled="valuesPending" />
            </UDropdownMenu>
          </div>
        </div>
      </div>
    </template>
    <div v-if="valuesPending" class="flex items-center justify-center py-12">
      <UIcon name="i-lucide-loader-circle" class="w-8 h-8 animate-spin text-primary-500" />
    </div>
    <UTable v-else :data="paginatedValues" :columns="columns" sticky :ui="{ td: 'py-1 px-2', th: 'py-1 px-2' }" />
    <template #footer>
      <div class="flex items-center justify-center gap-4">
        <div class="flex items-center gap-2">
          <span class="text-sm">Rows per page:</span>
          <USelect v-model="pageSize" :items="pageSizeOptions" class="w-20" />
        </div>
        <UPagination v-model:page="currentPage" :total="allValues.length" :items-per-page="pageSize" />
      </div>
    </template>
  </UCard>
</template>
