<script setup lang="ts">
import type StripesChart from '~/components/StripesChart.vue'
import type { StripesDisplay } from '~/utils/stripes-option'
import { describeFetchError } from '~/utils/api-error'
import { formatNumber } from '~/utils/format'
import { stripesSummaryParams, stripeYears } from '~/utils/stripes'
import { MENU_SCALE, STRIPES_HEIGHT, STRIPES_HEIGHT_TITLE } from '~/utils/stripes-option'
import { stripesUnitTargets, unitSymbol } from '~/utils/unit-targets'

const { t, locale } = useI18n()

// the title says which page this is: WCAG 2.4.2, and what a screen reader announces after a navigation
useHead({ title: () => t('stripes.title') })
const toast = useToast()

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
    ...API_FETCH,
  },
)

const stations = computed(() => stationsData.value?.stations ?? [])

// The station picker's selection, one array per chosen station: a new array on every render read to the map
// as a new selection, which turned centring on it back on.
const pickedStations = computed(() => selectedStation.value ? [selectedStation.value] : [])

function onPick(picked: StripesStation[]) {
  selectedStation.value = picked[0] ?? null
}

const showSettings = ref(true)
// the chart, drawn by its component once the stripes are fetched: the page asks it for the image
const chart = useTemplateRef<InstanceType<typeof StripesChart>>('chart')
const isLoading = ref(false)
const hasPlot = ref(false)
const lastFetchedData = ref<StripesValuesResponse | null>(null)
// the stripes' title: the kind and the station of the values. A kind changed clears the stripes, so
// the kind chosen is theirs
function plotTitle(data: StripesValuesResponse) {
  const station = data.series.station
  return t('stripes.plotTitle', { kind: kindLabel(kind.value), name: station.name, id: station.station_id })
}
// the stripes' accessible name, their title
const plotLabel = computed(() => lastFetchedData.value ? plotTitle(lastFetchedData.value) : undefined)

// What the stripes say, for a reader who does not see their colours (WCAG 1.1.1, 1.3.1): a sentence the figure
// is described by, and every year with its value and class in a table
const summaryId = useId()
// read defensively: an answer that lacks its values or its unit still draws what it can, and a table that
// cannot be made must not take the page down with it
const stripeRows = computed(() => stripeYears(lastFetchedData.value?.values ?? []))
const valueUnit = computed(() => {
  const unit = lastFetchedData.value?.series.unit
  return unit ? unitSymbol(unit) : ''
})
function formatValue(value: number) {
  return `${formatNumber(value, locale.value, 2)} ${valueUnit.value}`.trim()
}
const plotSummary = computed(() => {
  const years = stripeRows.value
  if (!years.length)
    return undefined
  return `${t('stripes.summary', stripesSummaryParams(years, formatValue))} ${t('common.chartTableHint')}`
})
const tableColumns = computed(() => [
  t('stripes.table.year'),
  valueUnit.value ? `${t('stripes.table.value')} (${valueUnit.value})` : t('stripes.table.value'),
  t('stripes.table.class'),
])
const tableRows = computed(() => stripeRows.value.map(year => [
  String(year.year),
  formatNumber(year.value, locale.value, 2),
  t(`stripes.table.classes.${kind.value}.${year.class}`),
]))
// the stripes could not be drawn: the chart says so itself, with its Retry, and the table and the image are not offered
const plotFailed = computed(() => chart.value?.renderFailed ?? false)
// the options the page offers, as the chart draws them
const display = computed<StripesDisplay>(() => ({
  showTitle: showTitle.value,
  showYears: showYears.value,
  showSource: showSource.value,
  showDataAvailability: showDataAvailability.value,
  showTimeseries: showTimeseries.value,
  showTrendline: showTrendline.value,
}))
// the name of the camera's file: the kind and the station of the stripes shown
const cameraFile = computed(() => `climate_stripes_${kind.value}_${lastFetchedData.value?.series.station.station_id ?? ''}`)
// The values' fetches, numbered as they start, so that only the newest, not stopped by a Reset, shows
// what it fetched. Failed: why the newest could not fetch the values, told in the chart area
let fetchesStarted = 0
const fetchError = ref<string | null>(null)

// What the stripes shown are of, as it was asked: the station and the years of the fetch, not what the form says now
// (GH-3980). A unit changed in the settings fetches this again, so that no selection the user has not confirmed is drawn
interface ShownStripes { station: string, startYear: number | null, endYear: number | null }
let shown: ShownStripes | null = null
// the unit changed while a fetch was under way: fetched again once it ends
let refetchShownAfter = false

/** `target`: the stripes shown, fetched again; without it the form's selection, as Show asks for it */
async function fetchAndPlotStripes(target?: ShownStripes) {
  const asked: ShownStripes | null = target ?? (selectedStation.value
    ? { station: selectedStation.value.station_id, startYear: startYear.value, endYear: endYear.value }
    : null)
  if (!asked)
    return

  // Cleared as the fetch starts: another station's stripes, so they do not stand under this one,
  // and stripes that could not be drawn, with their Retry of the earlier values. This station's
  // drawn stripes stay while they are fetched anew, as for other years; a drawing of them under way,
  // as of a display option changed, still draws, and tells its own failure
  if (plotFailed.value || lastFetchedData.value?.series.station.station_id !== asked.station)
    clearStripes()
  const started = ++fetchesStarted
  isLoading.value = true
  fetchError.value = null
  // this fetch reads the unit as it is now
  refetchShownAfter = false

  try {
    const params: StripesValuesQuery = {
      kind: kind.value,
      station: asked.station,
      format: 'json',
      // the unit the app settings choose, read at each request (GH-3980): the numbers come back in it, and the
      // colours, which are relative, do not change with it
      unit_targets: JSON.stringify(stripesUnitTargets(kind.value, settings.value.units)),
    }

    if (asked.startYear)
      params.start_year = asked.startYear
    if (asked.endYear)
      params.end_year = asked.endYear

    const response = await $fetch<StripesValuesResponse>('/api/stripes/values', {
      query: params,
      ...API_FETCH,
    })
    // a newer fetch, a Reset or another station chosen came while this one was under way: it shows
    // nothing
    if (started !== fetchesStarted)
      return

    // the stripes are drawn from the answer by their component, which mounts with it
    hasPlot.value = true
    lastFetchedData.value = response
    shown = asked
  }
  catch (error) {
    if (started !== fetchesStarted)
      return
    console.error('Failed to fetch stripes data:', error)
    // told above any stripes shown, which are this station's
    fetchError.value = describeFetchError(error)
  }
  finally {
    if (started === fetchesStarted) {
      isLoading.value = false
      // the unit changed under way: what was shown is fetched in the new one
      if (refetchShownAfter && shown && hasPlot.value)
        void fetchAndPlotStripes(shown)
    }
  }
}

/** Saves the stripes as a file: the size of the chart on the page, at a scale for a sharp raster image */
async function downloadStripes(format: 'png' | 'jpeg' | 'svg' = 'png') {
  const shownChart = chart.value
  const data = lastFetchedData.value
  if (!shownChart || !data)
    return
  const station = data.series.station
  try {
    await shownChart.save({
      format,
      filename: `climate_stripes_${kind.value}_${station.station_id}_${station.name}`,
      width: shownChart.width,
      height: showTitle.value ? STRIPES_HEIGHT_TITLE : STRIPES_HEIGHT,
      // a scale of 3 for high-quality raster images, which keep the proportions and scale the text with them
      scale: format === 'svg' ? 1 : MENU_SCALE,
    })
  }
  catch (error) {
    console.error('The chart image could not be saved', error)
    toast.add({ title: t('dataViewer.chartImageNotSaved'), color: 'error' })
  }
}

function clearStripes() {
  hasPlot.value = false
  lastFetchedData.value = null
  shown = null
  refetchShownAfter = false
  // a fetch still under way shows nothing, and its failure is not told
  fetchesStarted++
  isLoading.value = false
  fetchError.value = null
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

// a fetch under way is for the station chosen before: it is stopped, and its answer shows nothing
watch(() => selectedStation.value?.station_id, () => {
  if (!isLoading.value)
    return
  fetchesStarted++
  isLoading.value = false
})

watch(kind, () => {
  selectedStation.value = null
  clearStripes()
})

// The unit the settings choose for the kind changed while stripes are shown (the settings changed in another tab): what
// is shown is fetched again in it, as the table and the sentence say the unit of the answer (GH-3980). A fetch under way
// is followed by one
watch(() => stripesUnitTargets(kind.value, settings.value.units), (now, before) => {
  if (JSON.stringify(now) === JSON.stringify(before))
    return
  if (isLoading.value)
    refetchShownAfter = true
  else if (shown && hasPlot.value)
    void fetchAndPlotStripes(shown)
})

// The station list arrived or changed: a station chosen that is not in it is dropped, one named by the link is taken
watch(stations, () => {
  // If the selectedStation is not in the stations array, clear it
  if (selectedStation.value) {
    const selId = selectedStation.value.station_id
    if (!stations.value.some(s => s.station_id === selId))
      selectedStation.value = null
  }
  // If an initial station id was provided in the URL, apply it when stations are available
  if (initialStationId.value) {
    const found = stations.value.find(s => s.station_id === initialStationId.value)
    if (found)
      selectedStation.value = found
    initialStationId.value = null
  }
  // If there is only one station in the list, preselect it
  if (!selectedStation.value && stations.value.length === 1) {
    const only = stations.value[0]
    if (only)
      selectedStation.value = only
  }
})

// Persist the display toggles to the settings store; the chart draws what they say as they change
watch([showTitle, showYears, showDataAvailability, showTimeseries, showTrendline, showSource], () => {
  settings.value.stripes.showTitle = showTitle.value
  settings.value.stripes.showYears = showYears.value
  settings.value.stripes.showDataAvailability = showDataAvailability.value
  settings.value.stripes.showTimeseries = showTimeseries.value
  settings.value.stripes.showTrendline = showTrendline.value
  settings.value.stripes.showSource = showSource.value
})

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
</script>

<template>
  <div class="frame">
    <PageHeader :title="t('stripes.title')" :lede="t('stripes.subtitle')" :about-label="t('stripes.aboutButton')">
      <template #about>
        <div class="space-y-3 text-muted">
          <p class="text-gray-600 dark:text-gray-400 mb-4">
            {{ t('stripes.aboutText1') }}
          </p>
          <p class="text-gray-600 dark:text-gray-400">
            {{ t('stripes.aboutText2') }}
          </p>
        </div>
      </template>
    </PageHeader>
    <div class="page-body">
      <ToolWorkbench>
        <template #setup>
          <UCard>
            <template #header>
              <div class="flex items-center gap-2">
                <UIcon name="i-ph-map-pin" class="text-primary-600 dark:text-primary-500 shrink-0" />
                <h2 class="text-lg font-bold">
                  {{ t('cardTitle.stationAndPeriod') }}
                </h2>
              </div>
            </template>
            <div class="space-y-4">
              <UFormField :label="t('stripes.type')">
                <USelect v-model="kind" :items="kindItems" class="w-full" />
              </UFormField>

              <StationPicker
                tool="stripes"
                :label="t('stripes.station')"
                :stations="stations"
                :selected="pickedStations"
                :loading="stationsPending"
                locate="list"
                @update:selected="onPick"
              />

              <div v-if="selectedStation" class="text-sm text-gray-600 dark:text-gray-400 space-y-1">
                <p><strong>{{ t('stripes.region') }}{{ t('common.colon') }}</strong> {{ selectedStation.region }}</p>
                <p>
                  <strong>{{ t('stripes.available') }}{{ t('common.colon') }}</strong> {{ selectedStation.start_timestamp?.slice(0, 4) }} -
                  {{ selectedStation.end_timestamp?.slice(0, 4) }}
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
                  :label="t('common.fetch')" icon="i-ph-play" color="primary" :disabled="!selectedStation || isLoading"
                  :loading="isLoading" class="w-full" @click="fetchAndPlotStripes()"
                />
                <UButton :label="t('common.clear')" icon="i-ph-x" variant="outline" class="w-full" :disabled="!hasPlot && !isLoading && !fetchError" @click="clearStripes" />
              </div>
            </div>
          </UCard>

          <UCollapsible v-model="showSettings">
            <UButton
              :label="t('stripes.settingsTitle')"
              icon="i-ph-gear-six"
              variant="subtle"
              color="neutral"
              trailing-icon="i-ph-caret-down"
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
        </template>
        <template #result>
          <!-- the card is for what there is to put in it: the loading, the error and the stripes; before that, the
               placeholder every tool shows (GH-3850). The chart's container is in the card, and is there before
               anything is drawn, since the card is shown while the fetch is under way -->
          <ToolPlaceholder v-if="!isLoading && !fetchError && !hasPlot" tool="stripes" />
          <UCard v-else>
            <template #header>
              <div class="flex items-center gap-2">
                <UIcon name="i-ph-chart-bar" class="text-primary-600 dark:text-primary-500 shrink-0" />
                <h2 class="text-lg font-bold">
                  {{ t('stripes.visualizationTitle') }}
                </h2>
              </div>
            </template>

            <div>
              <div v-if="isLoading" class="flex items-center justify-center h-64">
                <div class="flex items-center gap-2 text-gray-500 dark:text-gray-400">
                  <UIcon name="i-ph-circle-notch" class="animate-spin" />
                  {{ t('stripes.loadingViz') }}
                </div>
              </div>
              <div
                v-else-if="fetchError" role="alert"
                class="flex flex-col items-center justify-center gap-1 text-center text-red-600 dark:text-red-400"
                :class="hasPlot ? 'pb-4' : 'h-64'"
              >
                <span class="font-medium">{{ t('dataViewer.fetchError') }}</span>
                <span class="text-sm">{{ fetchError }}</span>
              </div>
              <!-- the chart tells its own failure, with its Retry -->
              <StripesChart
                v-if="hasPlot && lastFetchedData"
                ref="chart"
                :values="lastFetchedData.values"
                :kind="kind"
                :unit="valueUnit"
                :title="plotLabel ?? ''"
                :display="display"
                :label="plotLabel"
                :described-by="plotSummary ? summaryId : undefined"
                :camera-file="cameraFile"
              />
              <p v-if="hasPlot && plotSummary" :id="summaryId" class="sr-only">
                {{ plotSummary }}
              </p>
              <ChartTable
                v-if="hasPlot && !plotFailed && tableRows.length"
                :caption="plotLabel ?? ''" :columns="tableColumns" :rows="tableRows"
                :note="t(`stripes.table.note.${kind}`)"
              />
              <div v-if="hasPlot && !plotFailed" class="mt-4">
                <!-- not modal: a modal menu hides the page from assistive technology (aria-hidden) while its
               own trigger is still focusable in it -->
                <UDropdownMenu
                  :modal="false"
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
                    icon="i-ph-download-simple" class="w-full justify-center"
                  />
                </UDropdownMenu>
              </div>
            </div>
          </UCard>
        </template>
      </ToolWorkbench>
    </div>
  </div>
</template>
