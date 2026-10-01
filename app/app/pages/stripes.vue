<script setup lang="ts">
const { t } = useI18n()
const toast = useToast()

// Plotly instance (loaded client-side only)
let Plotly: typeof import('plotly.js-basic-dist-min') | null = null
// The import under way, shared by its callers, and dropped where it fails, so that a later drawing
// loads Plotly again rather than await the same failure
let plotlyImport: Promise<typeof import('plotly.js-basic-dist-min')> | null = null

async function ensurePlotly(): Promise<typeof import('plotly.js-basic-dist-min')> {
  if (Plotly)
    return Plotly
  plotlyImport ??= import('plotly.js-basic-dist-min').catch((error) => {
    plotlyImport = null
    throw error
  })
  Plotly = await plotlyImport
  return Plotly
}

const kind = ref<StripesKind>('temperature')

const kindItems = computed(() => [
  { label: t('stripes.typeTemperature'), value: 'temperature' },
  { label: t('stripes.typePrecipitation'), value: 'precipitation' },
])

function kindLabel(k: StripesKind) {
  return k === 'precipitation' ? t('stripes.typePrecipitation') : t('stripes.typeTemperature')
}
const selectedStation = ref<StripesStation | null>(null)
const startYear = ref<number | null>(null)
const endYear = ref<number | null>(null)
// Display toggles default to the user's saved stripes preferences; an explicit
// URL query (e.g. from a shared link) still overrides these below.
const { settings } = useSettings()
const showTitle = ref(settings.value.stripes.showTitle)
const showYears = ref(settings.value.stripes.showYears)
const showDataAvailability = ref(settings.value.stripes.showDataAvailability)
const showTimeseries = ref(settings.value.stripes.showTimeseries)
const showTrendline = ref(settings.value.stripes.showTrendline)
const showSource = ref(settings.value.stripes.showSource)

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

// The map's selection, one array per chosen station: a new array on every render read to the map
// as a new selection, which turned centring on it back on.
const mapSelectedStations = computed(() => selectedStation.value ? [selectedStation.value] : [])

const showMap = ref(false)
const showSettings = ref(true)
const showAbout = ref(false)
const plotContainer = ref<HTMLElement | null>(null)
const isLoading = ref(false)
const hasPlot = ref(false)
const lastFetchedData = ref<StripesValuesResponse | null>(null)
// The stripes' drawings, numbered as they start. Failed: the newest threw -- Plotly's import or its
// drawing -- and the chart area says so; failures counted, so a Retry that fails too is told again
let plotsStarted = 0
const plotFailed = ref(false)
const plotFailures = ref(0)

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
  const plot = ++plotsStarted
  try {
    await ensurePlotly()
    await drawStripes(data)
    if (plot === plotsStarted)
      plotFailed.value = false
  }
  catch (error) {
    console.error('The chart could not be drawn', error)
    if (plot !== plotsStarted)
      return
    plotFailed.value = true
    plotFailures.value++
  }
}

async function drawStripes(data: StripesValuesResponse) {
  if (!plotContainer.value || !Plotly)
    return

  // Purge any existing plot first to ensure clean render
  Plotly.purge(plotContainer.value)

  // Filter out null values and prepare data
  const validData = data.values.filter(v => v.value !== null && v.timestamp !== null)

  if (validData.length === 0) {
    console.warn('No valid data to plot')
    return
  }

  // Extract years and values: each year's value comes at its first moment in UTC, read in UTC, as
  // in a browser west of UTC that moment is still the year before
  const years = validData.map(v => new Date(v.timestamp!).getUTCFullYear())
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
      text: t('stripes.plotDataAvailability'),
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
      text: t('stripes.plotSource'),
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
    y: Array.from<number>({ length: years.length }).fill(1),
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
  const titleText = t('stripes.plotTitle', {
    kind: kindLabel(kind.value),
    name: data.metadata.station.name,
    id: data.metadata.station.station_id,
  })
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

  // Get the current dimensions of the plot container
  const containerWidth = plotContainer.value.clientWidth
  const containerHeight = plotContainer.value.clientHeight

  // Use current dimensions with a scale factor for high resolution
  // This preserves aspect ratio AND scales text/annotations proportionally
  const station = lastFetchedData.value.metadata.station
  try {
    await Plotly.downloadImage(plotContainer.value, {
      format,
      filename: `climate_stripes_${kind.value}_${station.station_id}_${station.name}`,
      height: containerHeight,
      width: containerWidth,
      scale: format === 'svg' ? 1 : 3, // Scale factor of 3 for high-quality raster images
    })
  }
  catch (error) {
    console.error('The chart image could not be saved', error)
    toast.add({ title: t('dataViewer.chartImageNotSaved'), color: 'error' })
  }
}

function clearStripes() {
  // with Plotly not loaded there is no drawing to purge, but the chart area is still cleared
  if (plotContainer.value && Plotly)
    Plotly.purge(plotContainer.value)
  hasPlot.value = false
  // a drawing still under way is no longer the newest, so its failure is not told after the next Show
  plotsStarted++
  plotFailed.value = false
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
if (route.query.show_timeseries !== undefined && route.query.show_timeseries !== null)
  showTimeseries.value = route.query.show_timeseries?.toString() === 'true'
if (route.query.show_trendline !== undefined && route.query.show_trendline !== null)
  showTrendline.value = route.query.show_trendline?.toString() === 'true'
if (route.query.show_source !== undefined && route.query.show_source !== null)
  showSource.value = route.query.show_source?.toString() === 'true'
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
    if (!stations.value.some(s => s.station_id === selId)) {
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

// Re-plot when display settings change and persist toggles to settings store
watch([showTitle, showYears, showDataAvailability, showTimeseries, showTrendline, showSource], async () => {
  settings.value.stripes.showTitle = showTitle.value
  settings.value.stripes.showYears = showYears.value
  settings.value.stripes.showDataAvailability = showDataAvailability.value
  settings.value.stripes.showTimeseries = showTimeseries.value
  settings.value.stripes.showTrendline = showTrendline.value
  settings.value.stripes.showSource = showSource.value
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
  if (showTimeseries.value !== undefined)
    q.show_timeseries = String(showTimeseries.value)
  if (showTrendline.value !== undefined)
    q.show_trendline = String(showTrendline.value)
  if (showSource.value !== undefined)
    q.show_source = String(showSource.value)
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
  () => showTimeseries.value,
  () => showTrendline.value,
  () => showSource.value,
  () => startYear.value,
  () => endYear.value,
], () => {
  // Use replace to avoid polluting history while keeping URL in sync. A
  // rejected navigation (e.g. superseded by a subsequent replace() before
  // this one resolves) would otherwise be an unhandled promise rejection.
  router.replace({ query: stripesToQuery() }).catch(() => {})
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

// Load Plotly dynamically on mount; a failure is told where the stripes are drawn
onMounted(() => {
  ensurePlotly().catch(() => {})
})
</script>

<template>
  <UContainer class="mx-auto max-w-3xl px-4 py-6 space-y-6">
    <div class="text-center mb-8">
      <h1 class="text-3xl font-bold mb-4">
        {{ t('stripes.title') }}
      </h1>
      <p class="text-gray-600 dark:text-gray-400">
        {{ t('stripes.subtitle') }}
      </p>
    </div>

    <UCollapsible v-model="showAbout">
      <UButton
        :label="t('stripes.aboutButton')"
        icon="i-lucide-info"
        variant="subtle"
        color="neutral"
        trailing-icon="i-lucide-chevron-down"
        block
        size="sm"
      />
      <template #content>
        <UCard>
          <p class="text-gray-600 dark:text-gray-400 mb-4">
            {{ t('stripes.aboutText1') }}
          </p>
          <p class="text-gray-600 dark:text-gray-400">
            {{ t('stripes.aboutText2') }}
          </p>
        </UCard>
      </template>
    </UCollapsible>

    <UCard class="mb-6">
      <template #header>
        <div class="flex items-center gap-2">
          <UIcon name="i-lucide-map-pin" class="text-primary-500 shrink-0" />
          <h2 class="text-lg font-bold">
            {{ t('explorer.dataSource') }}
          </h2>
        </div>
      </template>
      <div class="space-y-4">
        <UFormField :label="t('stripes.type')">
          <USelect v-model="kind" :items="kindItems" class="w-full" />
        </UFormField>

        <div>
          <UFormField :label="t('stripes.station')">
            <USelectMenu
              v-model="selectedStationItem"
              :items="stationItems"
              :multiple="false"
              searchable
              virtualize
              color="primary"
              class="w-full"
              :class="{ 'needs-input': !selectedStation }"
              :placeholder="t('common.stationSearch')"
              @update:model-value="onSelectMenuUpdate"
            />
          </UFormField>

          <UCollapsible v-model="showMap" class="mt-3">
            <UButton
              :label="t('stripes.chooseOnMap')"
              icon="i-lucide-map-pin"
              variant="subtle"
              color="primary"
              trailing-icon="i-lucide-chevron-down"
              block
              size="sm"
            />
            <template #content>
              <ClientOnly>
                <p class="flex items-center justify-center gap-2 mt-3 text-sm text-gray-500 dark:text-gray-400">
                  <UIcon name="i-lucide-hand-pointer-2" class="w-4 h-4 text-primary-500" />
                  {{ t('stripes.mapHint') }}
                </p>
                <MapStations
                  :stations="stations"
                  :selected-stations="mapSelectedStations"
                  :multiple="false"
                  @update:selected-stations="onMapSelectedStations"
                />
              </ClientOnly>
            </template>
          </UCollapsible>
        </div>

        <div v-if="stationsPending" class="text-sm text-gray-600 dark:text-gray-400">
          {{ t('stripes.loadingStations') }}
        </div>

        <div v-if="selectedStation" class="text-sm text-gray-600 dark:text-gray-400 space-y-1">
          <p><strong>{{ t('stripes.region') }}:</strong> {{ selectedStation.region }}</p>
          <p>
            <strong>{{ t('stripes.available') }}:</strong> {{ selectedStation.start_date?.slice(0, 4) }} -
            {{ selectedStation.end_date?.slice(0, 4) }}
          </p>
        </div>

        <USeparator />

        <div class="grid grid-cols-2 gap-4">
          <UFormField :label="t('stripes.startYear')">
            <UInput v-model.number="startYear" type="number" :placeholder="t('stripes.auto')" class="w-full" />
          </UFormField>
          <UFormField :label="t('stripes.endYear')">
            <UInput v-model.number="endYear" type="number" :placeholder="t('stripes.auto')" class="w-full" />
          </UFormField>
        </div>

        <USeparator />

        <div class="flex flex-col sm:flex-row gap-2">
          <UButton
            :label="t('common.fetch')" icon="i-lucide-play" color="primary" :disabled="!selectedStation || isLoading"
            :loading="isLoading" class="w-full" @click="fetchAndPlotStripes"
          />
          <UButton :label="t('common.clear')" icon="i-lucide-x" variant="outline" class="w-full" :disabled="!hasPlot" @click="clearStripes" />
        </div>
      </div>
    </UCard>

    <UCollapsible v-model="showSettings">
      <UButton
        :label="t('stripes.settingsTitle')"
        icon="i-lucide-settings-2"
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
          <UCheckbox v-model="showTitle" :label="t('stripes.showTitleOption')" />
          <UCheckbox v-model="showYears" :label="t('stripes.showYears')" />
          <UCheckbox v-model="showSource" :label="t('stripes.showSource')" />
          <UCheckbox v-model="showDataAvailability" :label="t('stripes.showDataAvailability')" />
          <UCheckbox v-model="showTimeseries" :label="t('stripes.showTimeseries')" />
          <UCheckbox v-model="showTrendline" :disabled="!showTimeseries" :label="t('stripes.showTrendline')" />
        </div>
      </template>
    </UCollapsible>

    <UCard class="mb-6">
      <template #header>
        <div class="flex items-center gap-2">
          <UIcon name="i-lucide-bar-chart-big" class="text-primary-500 shrink-0" />
          <h2 class="text-lg font-bold">
            {{ t('stripes.visualizationTitle') }}
          </h2>
        </div>
      </template>

      <div>
        <div v-if="isLoading" class="flex items-center justify-center h-64">
          <div class="flex items-center gap-2 text-gray-500">
            <UIcon name="i-lucide-loader-circle" class="animate-spin" />
            {{ t('stripes.loadingViz') }}
          </div>
        </div>
        <div v-else-if="!hasPlot" class="flex flex-col items-center justify-center h-64 gap-3 text-gray-400">
          <UIcon name="i-lucide-bar-chart-big" class="w-12 h-12 opacity-30" />
          <p class="text-sm">
            {{ t('stripes.emptyHint') }}
          </p>
        </div>
        <div
          v-if="hasPlot && plotFailed"
          class="flex items-center justify-center gap-3 pb-4 text-red-600 dark:text-red-400"
        >
          <!-- mounted anew for each failure, so a Retry that fails too is announced again; the
               button stays, and keeps its focus -->
          <span :key="plotFailures" role="alert" class="font-medium">{{ t('dataViewer.chartNotDrawn') }}</span>
          <UButton :label="t('common.retry')" icon="i-lucide-rotate-cw" size="sm" color="neutral" variant="outline" @click="lastFetchedData && plotStripes(lastFetchedData)" />
        </div>
        <div
          ref="plotContainer" :class="{ hidden: !hasPlot }"
          class="w-full overflow-hidden" style="min-height: 400px;"
        />
        <div v-if="hasPlot && !plotFailed" class="mt-4">
          <UDropdownMenu
            :items="[
              [
                { label: t('stripes.downloadPng'), onSelect: () => downloadStripes('png') },
                { label: t('stripes.downloadJpg'), onSelect: () => downloadStripes('jpeg') },
                { label: t('stripes.downloadSvg'), onSelect: () => downloadStripes('svg') },
              ],
            ]"
          >
            <UButton
              :label="t('stripes.downloadImage')" color="primary" variant="outline"
              icon="i-lucide-download" class="w-full justify-center"
            />
          </UDropdownMenu>
        </div>
      </div>
    </UCard>
  </UContainer>
</template>
