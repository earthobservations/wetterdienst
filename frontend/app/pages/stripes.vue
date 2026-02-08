<script setup lang="ts">
import { defineAsyncComponent } from 'vue'

const MapStations = defineAsyncComponent(() => import('~/components/MapStations.vue'))

// Plotly instance (loaded client-side only)
const plotlyLoaded = ref(false)
let Plotly: typeof import('plotly.js-dist-min') | null = null

const kind = ref<StripesKind>('temperature')
const selectedStation = ref<StripesStation | null>(null)
const startYear = ref<number | null>(null)
const endYear = ref<number | null>(null)
const showTitle = ref(true)
const showYears = ref(true)
const showDataAvailability = ref(true)
const showTimeseries = ref(false)
const showTrendline = ref(false)
const showSource = ref(true)

const _stationSelectionModel = undefined // kept for future use

const { data: stationsData, pending: stationsPending } = useFetch<StripesStationsResponse>(
  '/api/stripes/stations',
  {
    query: { kind },
  },
)

const stations = computed(() => stationsData.value?.stations ?? [])

const stationItems = computed(() => stations.value.map(s => ({
  label: `${s.name} (ID: ${s.station_id})`,
  value: s.station_id,
})))

const selectedStationId = computed({
  get: () => selectedStation.value ? selectedStation.value.station_id : null,
  set: (id: string | null) => {
    selectedStation.value = id ? stations.value.find(s => s.station_id === id) ?? null : null
  },
})

// USelectMenu (when used with :multiple="false") expects a single item or undefined
const selectedStationItem = computed<{ label: string, value: string } | undefined>({
  get: () => selectedStation.value
    ? {
        label: `${selectedStation.value.name} (ID: ${selectedStation.value.station_id})`,
        value: selectedStation.value.station_id,
      }
    : undefined,
  set: (item: { label: string, value: string } | undefined) => {
    if (!item) {
      selectedStationId.value = null
    }
    else {
      selectedStationId.value = item.value
    }
  },
})

const showMap = ref(false)
const showSettings = ref(true)
const showAbout = ref(false)
const plotContainer = ref<HTMLElement | null>(null)
const isLoading = ref(false)
const hasPlot = ref(false)
const lastFetchedData = ref<StripesValuesResponse | null>(null)

// Color maps
const COLOR_MAPS: Record<StripesKind, Array<[number, string]>> = {
  temperature: [
    [0, 'rgb(5,48,97)'],
    [0.2, 'rgb(33,102,172)'],
    [0.4, 'rgb(146,197,222)'],
    [0.5, 'rgb(247,247,247)'],
    [0.6, 'rgb(253,219,199)'],
    [0.8, 'rgb(239,138,98)'],
    [1, 'rgb(178,24,43)'],
  ],
  precipitation: [
    [0, 'rgb(84,48,5)'],
    [0.2, 'rgb(140,81,10)'],
    [0.4, 'rgb(191,129,45)'],
    [0.5, 'rgb(246,232,195)'],
    [0.6, 'rgb(199,234,229)'],
    [0.8, 'rgb(90,180,172)'],
    [1, 'rgb(1,102,94)'],
  ],
}

async function fetchAndPlotStripes() {
  if (!selectedStation.value)
    return

  isLoading.value = true

  try {
    const params: StripesValuesQuery = {
      kind: kind.value,
      station: selectedStation.value.station_id,
      format: 'json',
    }

    if (startYear.value)
      params.start_year = startYear.value
    if (endYear.value)
      params.end_year = endYear.value

    const response = await $fetch<StripesValuesResponse>('/api/stripes/values', {
      query: params,
    })

    // Wait for next tick to ensure DOM is updated
    await nextTick()

    // Show the container before plotting so Plotly can measure its width
    hasPlot.value = true
    await nextTick()

    lastFetchedData.value = response
    await plotStripes(response)
  }
  catch (error) {
    console.error('Failed to fetch stripes data:', error)
    // You might want to show a toast notification here
  }
  finally {
    isLoading.value = false
  }
}

async function plotStripes(data: StripesValuesResponse) {
  if (!plotContainer.value || !Plotly || !plotlyLoaded.value)
    return

  // Purge any existing plot first to ensure clean render
  Plotly.purge(plotContainer.value)

  // Filter out null values and prepare data
  const validData = data.values.filter(v => v.value !== null && v.date !== null)

  if (validData.length === 0) {
    console.warn('No valid data to plot')
    return
  }

  // Extract years and values
  const years = validData.map(v => new Date(v.date!).getFullYear())
  const values = validData.map(v => v.value!)

  // Calculate min and max for normalization
  const minValue = Math.min(...values)
  const maxValue = Math.max(...values)

  // Normalize values to 0-1 range
  const normalizedValues = values.map(v => (v - minValue) / (maxValue - minValue))

  const minYear = Math.min(...years)
  const maxYear = Math.max(...years)

  // Create annotations array BEFORE creating layout
  const annotations: Partial<Plotly.Annotations>[] = []

  // Add year annotations at the bottom
  if (showYears.value) {
    annotations.push(
      {
        x: minYear,
        y: -0.04,
        xref: 'x',
        yref: 'paper',
        text: String(minYear),
        showarrow: false,
        xanchor: 'left',
        yanchor: 'top',
        font: { size: 18, color: 'black' },
      },
      {
        x: maxYear,
        y: -0.04,
        xref: 'x',
        yref: 'paper',
        text: String(maxYear),
        showarrow: false,
        xanchor: 'right',
        yanchor: 'top',
        font: { size: 18, color: 'black' },
      },
    )
  }

  // Add data availability label
  if (showDataAvailability.value) {
    annotations.push({
      x: minYear,
      y: -0.03,
      xref: 'x',
      yref: 'paper',
      text: 'Data availability',
      showarrow: false,
      xanchor: 'left',
      yanchor: 'bottom',
      font: { color: 'goldenrod', size: 11 },
    })
  }

  // Add source annotation
  if (showSource.value) {
    annotations.push({
      x: 0.5,
      y: -0.05,
      text: 'Source: Deutscher Wetterdienst',
      showarrow: false,
      xref: 'paper',
      yref: 'paper',
      xanchor: 'center',
      yanchor: 'top',
      font: { size: 14, color: '#666' },
    })
  }

  // Create bar trace
  const trace = {
    x: years,
    y: Array.from({ length: years.length }, () => 1),
    type: 'bar' as const,
    marker: {
      color: normalizedValues,
      colorscale: COLOR_MAPS[kind.value],
      cmin: 0,
      cmax: 1,
      showscale: false,
      line: { width: 0 },
    },
    width: 1.0,
    hovertemplate: '<b>%{x}</b><br>Value: %{customdata}<extra></extra>',
    customdata: values,
    showlegend: false,
  }

  // Data availability trace (golden line at bottom)
  const allYears = Array.from({ length: maxYear - minYear + 1 }, (_, i) => minYear + i)
  const availability = allYears.map(year => years.includes(year) ? -0.02 : null)

  const availabilityTrace = {
    x: allYears,
    y: availability,
    type: 'scatter' as const,
    mode: 'lines' as const,
    line: { color: 'gold', width: 3 },
    showlegend: false,
    hoverinfo: 'skip' as const,
  }

  // Timeseries trace (line overlay showing normalized values)
  const normalizedTimeseriesY = values.map(v => (v - minValue) / (maxValue - minValue))
  const timeseriesTrace = {
    x: years,
    y: normalizedTimeseriesY,
    type: 'scatter' as const,
    mode: 'lines' as const,
    line: { color: 'black', width: 2 },
    showlegend: false,
    hovertemplate: '<b>%{x}</b><br>Value: %{customdata:.2f}<extra></extra>',
    customdata: values,
  }

  // Calculate trendline using linear regression
  let trendlineTrace
  if (showTrendline.value && showTimeseries.value) {
    // Simple linear regression: y = mx + b
    const n = years.length
    const sumX = years.reduce((a, b) => a + b, 0)
    const sumY = values.reduce((a, b) => a + b, 0)
    const sumXY = years.reduce((sum, x, i) => sum + x * (values[i] ?? 0), 0)
    const sumX2 = years.reduce((sum, x) => sum + x * x, 0)

    const slope = (n * sumXY - sumX * sumY) / (n * sumX2 - sumX * sumX)
    const intercept = (sumY - slope * sumX) / n

    const trendlineValues = years.map(x => slope * x + intercept)
    const normalizedTrendline = trendlineValues.map(v => (v - minValue) / (maxValue - minValue))

    trendlineTrace = {
      x: years,
      y: normalizedTrendline,
      type: 'scatter' as const,
      mode: 'lines' as const,
      line: { color: 'black', width: 4, dash: 'dash' },
      showlegend: false,
      hovertemplate: '<b>%{x}</b><br>Trend: %{customdata:.2f}<extra></extra>',
      customdata: trendlineValues,
    }
  }

  const traces: Plotly.Data[] = [trace]
  if (showDataAvailability.value)
    traces.push(availabilityTrace as Plotly.Data)
  if (showTimeseries.value)
    traces.push(timeseriesTrace as Plotly.Data)
  if (trendlineTrace)
    traces.push(trendlineTrace as Plotly.Data)

  // Layout configuration
  const titleText = `Climate stripes (${kind.value}) for ${data.metadata.station.name}, Germany (${data.metadata.station.station_id})`
  const containerWidth = plotContainer.value.clientWidth

  const layout: Partial<Plotly.Layout> = {
    font: {
      family: 'Arial, sans-serif',
      size: 14,
      color: 'black',
    },
    xaxis: {
      showgrid: false,
      zeroline: false,
      showticklabels: false,
      showline: false,
      range: [minYear - 0.5, maxYear + 0.5],
    },
    yaxis: {
      showgrid: false,
      zeroline: false,
      showticklabels: false,
      showline: false,
      range: showDataAvailability.value ? [-0.05, 1.05] : [0, 1],
    },
    bargap: 0,
    bargroupgap: 0,
    margin: {
      l: 20,
      r: 20,
      t: showTitle.value ? 30 : 20,
      b: 60,
    },
    paper_bgcolor: 'white',
    plot_bgcolor: 'white',
    showlegend: false,
    autosize: false,
    width: containerWidth,
    height: showTitle.value ? 600 : 550,
    annotations,
  }

  const config: Partial<Plotly.Config> = {
    responsive: true,
    displayModeBar: true,
    displaylogo: false,
    modeBarButtonsToRemove: ['lasso2d', 'select2d'],
    toImageButtonOptions: {
      format: 'png',
      filename: `climate_stripes_${kind.value}_${data.metadata.station.station_id}`,
      height: showTitle.value ? 700 : 600,
      width: 1400,
      scale: 2,
    },
  }

  await Plotly.newPlot(plotContainer.value, traces as any, layout as any, config)

  // Plotly v3 requires relayout to render the title after newPlot
  if (showTitle.value) {
    await Plotly.relayout(plotContainer.value, {
      title: {
        text: titleText,
        font: { size: 16, color: 'black' },
        y: showDataAvailability.value ? 0.96 : 0.99,
        x: 0.5,
        xanchor: 'center',
        yanchor: 'top',
      },
    })
  }
}

async function downloadStripes(format: 'png' | 'jpeg' | 'svg' = 'png') {
  if (!plotContainer.value || !Plotly || !lastFetchedData.value)
    return

  const station = lastFetchedData.value.metadata.station
  await Plotly.downloadImage(plotContainer.value, {
    format,
    filename: `climate_stripes_${kind.value}_${station.station_id}_${station.name}`,
    height: showTitle.value ? 700 : 600,
    width: 1400,
    scale: format === 'svg' ? 1 : 2,
  })
}

function clearStripes() {
  if (plotContainer.value && Plotly) {
    Plotly.purge(plotContainer.value)
    hasPlot.value = false
  }
}

const route = useRoute()
const router = useRouter()

// Preserve initial station id from URL so we can apply it once stations have loaded
const initialStationId = ref<string | null>(route.query.station?.toString() ?? null)

// Initialize simple options from URL if present
if (route.query.kind)
  kind.value = route.query.kind.toString() as StripesKind
if (route.query.show_title !== undefined && route.query.show_title !== null)
  showTitle.value = route.query.show_title?.toString() === 'true'
if (route.query.show_years !== undefined && route.query.show_years !== null)
  showYears.value = route.query.show_years?.toString() === 'true'
if (route.query.show_data_availability !== undefined && route.query.show_data_availability !== null)
  showDataAvailability.value = route.query.show_data_availability?.toString() === 'true'
if (route.query.start_year)
  startYear.value = Number(route.query.start_year.toString())
if (route.query.end_year)
  endYear.value = Number(route.query.end_year.toString())

function onSelectMenuUpdate(val: any) {
  // Normalize incoming value from the select/menu or map into a single item or null
  const item = val ? (Array.isArray(val) ? val[0] : val) : null
  // selectedStationItem is a single item or undefined
  selectedStationItem.value = item ?? undefined
  const id = item ? item.value : null
  selectedStation.value = id ? stations.value.find(s => s.station_id === id) ?? null : null
}

watch(kind, () => {
  selectedStation.value = null
  clearStripes()
})

// Ensure select menu updates selection when stations load or when user selects from list
watch(stations, () => {
  // If the selectedStation is not in the stations array, clear it
  if (selectedStation.value) {
    const selId = selectedStation.value.station_id
    if (!stations.value.find(s => s.station_id === selId)) {
      selectedStation.value = null
      // clear selection
      selectedStationItem.value = undefined
    }
  }
  // If an initial station id was provided in the URL, apply it when stations are available
  if (initialStationId.value) {
    const found = stations.value.find(s => s.station_id === initialStationId.value)
    if (found) {
      selectedStation.value = found
      // set the single selected item
      selectedStationItem.value = { label: `${found.name} (ID: ${found.station_id})`, value: found.station_id }
    }
    initialStationId.value = null
  }
  // If there is only one station in the list, preselect it
  if (!selectedStation.value && stations.value.length === 1) {
    const only = stations.value[0]
    if (only)
      selectedStationId.value = only.station_id
  }
})

// Re-plot when display settings change
watch([showTitle, showYears, showDataAvailability, showTimeseries, showTrendline, showSource], async () => {
  if (lastFetchedData.value && hasPlot.value) {
    await plotStripes(lastFetchedData.value)
  }
})

function onMapSelectedStations(val?: StripesStation[] | null) {
  if (val && val.length) {
    const s = val[0]
    if (s)
      onSelectMenuUpdate({ label: s.name, value: s.station_id })
    else onSelectMenuUpdate(null)
  }
  else {
    onSelectMenuUpdate(null)
  }
}

// Update URL query when relevant options change
function stripesToQuery(): Record<string, string> {
  const q: Record<string, string> = {}
  if (kind.value)
    q.kind = kind.value
  if (selectedStation.value)
    q.station = selectedStation.value.station_id
  if (showTitle.value !== undefined)
    q.show_title = String(showTitle.value)
  if (showYears.value !== undefined)
    q.show_years = String(showYears.value)
  if (showDataAvailability.value !== undefined)
    q.show_data_availability = String(showDataAvailability.value)
  if (startYear.value !== null && startYear.value !== undefined)
    q.start_year = String(startYear.value)
  if (endYear.value !== null && endYear.value !== undefined)
    q.end_year = String(endYear.value)
  return q
}

watch([
  () => selectedStation?.value?.station_id,
  () => kind.value,
  () => showTitle.value,
  () => showYears.value,
  () => showDataAvailability.value,
  () => startYear.value,
  () => endYear.value,
], () => {
  // Use replace to avoid polluting history while keeping URL in sync
  router.replace({ query: stripesToQuery() })
})

// Update selectedStation when selectedStationItem changes (from the select menu or map)
watch(selectedStationItem, (item) => {
  // selectedStationItem is a single item or undefined
  const id = item ? item.value : null
  selectedStation.value = id ? stations.value.find(s => s.station_id === id) ?? null : null
})

// Re-plot when display options change (but only if we already have data)
watch([showTitle, showYears, showDataAvailability], () => {
  if (hasPlot.value) {
    fetchAndPlotStripes()
  }
})

// Load Plotly dynamically on mount
onMounted(async () => {
  Plotly = await import('plotly.js-dist-min')
  plotlyLoaded.value = true
})
</script>

<template>
  <UContainer class="mx-auto max-w-3xl px-4 py-6 space-y-6">
    <div class="text-center mb-8">
      <h1 class="text-4xl font-bold mb-4">
        Climate Stripes
      </h1>
      <p class="text-gray-600 dark:text-gray-400">
        Visualize long-term climate trends with warming/cooling stripes
      </p>
    </div>

    <UCollapsible v-model="showAbout" class="mb-6">
      <UButton
        label="About Climate Stripes"
        variant="subtle"
        color="neutral"
        trailing-icon="i-lucide-chevron-down"
        block
        size="sm"
      />
      <template #content>
        <UCard>
          <p class="text-gray-600 dark:text-gray-400 mb-4">
            Climate stripes (also known as warming stripes) are a data visualization designed to communicate the
            long-term increase in temperatures. Each stripe represents the average temperature for a single year, with
            blue indicating cooler years and red indicating warmer years.
          </p>
          <p class="text-gray-600 dark:text-gray-400">
            The visualization was created by climate scientist Ed Hawkins and has become an iconic representation of
            climate change. This tool uses data from the German Weather Service (DWD) observation network.
          </p>
        </UCard>
      </template>
    </UCollapsible>

    <UCard class="mb-6">
      <template #header>
        <h2 class="text-lg font-semibold">
          Request
        </h2>
      </template>
      <div class="space-y-4 p-4">
        <div>
          <label class="block text-sm font-medium mb-1">Type</label>
          <USelect v-model="kind" :items="['temperature', 'precipitation']" />
        </div>

        <div>
          <label class="block text-sm font-medium mb-1">Station</label>
          <USelectMenu
            v-model="selectedStationItem"
            :items="stationItems"
            :multiple="false"
            searchable
            color="primary"
            class="w-full"
            :placeholder="selectedStation ? `${selectedStation?.name} (ID: ${selectedStation?.station_id})` : 'Select a station'"
            @update:model-value="onSelectMenuUpdate"
          />

          <UCollapsible v-model="showMap" class="mt-3">
            <UButton
              label="Show map"
              variant="subtle"
              color="neutral"
              trailing-icon="i-lucide-chevron-down"
              block
              size="sm"
            />
            <template #content>
              <ClientOnly>
                <MapStations
                  :stations="stations"
                  :selected-stations="selectedStation ? [selectedStation] : []"
                  :multiple="false"
                  @update:selected-stations="onMapSelectedStations"
                />
              </ClientOnly>
            </template>
          </UCollapsible>
        </div>

        <div v-if="stationsPending" class="text-sm text-gray-600 dark:text-gray-400">
          Loading stations...
        </div>

        <div v-if="selectedStation" class="text-sm text-gray-600 dark:text-gray-400 space-y-1">
          <p><strong>State:</strong> {{ selectedStation.state }}</p>
          <p>
            <strong>Available:</strong> {{ selectedStation.start_date?.slice(0, 4) }} -
            {{ selectedStation.end_date?.slice(0, 4) }}
          </p>
        </div>

        <USeparator />

        <div class="grid grid-cols-2 gap-4">
          <div>
            <label class="block text-sm font-medium mb-1">Start Year</label>
            <UInput v-model.number="startYear" type="number" placeholder="Auto" />
          </div>
          <div>
            <label class="block text-sm font-medium mb-1">End Year</label>
            <UInput v-model.number="endYear" type="number" placeholder="Auto" />
          </div>
        </div>

        <USeparator />

        <div class="flex flex-col sm:flex-row gap-2">
          <UButton
            label="Fetch" color="primary" :disabled="!selectedStation || isLoading"
            :loading="isLoading" class="w-full" @click="fetchAndPlotStripes"
          />
          <UButton label="Clear" variant="outline" class="w-full" :disabled="!hasPlot" @click="clearStripes" />
        </div>
      </div>
    </UCard>

    <UCollapsible v-model="showSettings">
      <UButton
        label="Settings"
        variant="subtle"
        color="neutral"
        trailing-icon="i-lucide-chevron-down"
        block
        size="sm"
      />
      <template #content>
        <div
          class="flex flex-col gap-3 p-4 mt-3 rounded-lg border-2 border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800/50"
        >
          <UCheckbox v-model="showTitle" label="Show title" />
          <UCheckbox v-model="showYears" label="Show years" />
          <UCheckbox v-model="showSource" label="Show source" />
          <UCheckbox v-model="showDataAvailability" label="Show data availability" />
          <UCheckbox v-model="showTimeseries" label="Show timeseries" />
          <UCheckbox v-model="showTrendline" :disabled="!showTimeseries" label="Show trendline" />
        </div>
      </template>
    </UCollapsible>

    <UCard class="mb-6">
      <template #header>
        <div class="flex items-center justify-between">
          <h2 class="text-lg font-semibold">
            Visualization
          </h2>
        </div>
      </template>

      <div class="p-4">
        <div v-if="isLoading" class="flex items-center justify-center h-64">
          <div class="flex items-center gap-2 text-gray-500">
            <UIcon name="i-lucide-loader-2" class="animate-spin" />
            Loading data and generating visualization...
          </div>
        </div>
        <div v-else-if="!hasPlot" class="flex items-center justify-center h-64 text-gray-500">
          Select a station and click Fetch to create climate stripes
        </div>
        <div
          ref="plotContainer" :class="{ hidden: !hasPlot }"
          class="w-full overflow-hidden" style="min-height: 400px;"
        />
        <div v-if="hasPlot" class="mt-4">
          <UDropdownMenu
            :items="[
              [
                { label: 'Download as PNG', onSelect: () => downloadStripes('png') },
                { label: 'Download as JPG', onSelect: () => downloadStripes('jpeg') },
                { label: 'Download as SVG', onSelect: () => downloadStripes('svg') },
              ],
            ]"
          >
            <UButton
              label="Download Image" color="primary" variant="outline"
              icon="i-lucide-download" class="w-full justify-center"
            />
          </UDropdownMenu>
        </div>
      </div>
    </UCard>
  </UContainer>
</template>
