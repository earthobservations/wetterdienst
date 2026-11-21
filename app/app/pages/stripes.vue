<script setup lang="ts">
import type StripesChart from '~/components/StripesChart.vue'
import type { StripesView } from '~/utils/stripes-model'
import type { StripesDisplay } from '~/utils/stripes-option'
import { describeFetchError } from '~/utils/api-error'
import { downloadBlob } from '~/utils/chart-image'
import { formatNumber, formatSigned } from '~/utils/format'
import { ghcnCountryName } from '~/utils/ghcn-country'
import { GHCN_NETWORK } from '~/utils/map-tool'
import { processingNote } from '~/utils/processing-note'
import { stripesMethodNote, stripesReferenceShort, stripesReferenceText, stripesSummaryParams, stripeYears } from '~/utils/stripes'
import { isStripesDrawing, STRIPES_VIEW_QUERY, stripesViewFromQuery } from '~/utils/stripes-model'
import { MENU_SCALE } from '~/utils/stripes-option'
import { MIN_RECORD_YEARS, StripesRefusedError } from '~/utils/stripes-scale'
import { fetchStripes, fetchStripesStations, stripesFetch } from '~/utils/stripes-source'
import { stripesCsv, stripesTableColumns, stripesTableYears } from '~/utils/stripes-table'
import { stripesUnitTargets, unitSymbol } from '~/utils/unit-targets'

const { t, locale } = useI18n()

// the title says which page this is: WCAG 2.4.2, and what a screen reader announces after a navigation
useHead({ title: () => t('stripes.title') })
const toast = useToast()

// The kind and the source come from the link, read where they are made: the stations are asked for the ones chosen, and not for
// the defaults first (GH-4258)
const route = useRoute()
// a kind that is none of the two is no choice: the temperature
const kind = ref<StripesKind>(route.query.kind?.toString() === 'precipitation' ? 'precipitation' : 'temperature')
// Where the stations and the years are from (GH-4078): DWD's annual values (the default), or NOAA's GHCN daily, whose years are built from
// the days. In the link as `provider` and `network`, as the REST API takes them, and left out for DWD's
type StripesSource = 'dwd' | 'ghcn'
const source = ref<StripesSource>(route.query.provider?.toString() === GHCN_NETWORK.provider && route.query.network?.toString() === GHCN_NETWORK.network ? 'ghcn' : 'dwd')
const sourceItems = computed(() => [
  { label: t('stripes.sourceDwd'), value: 'dwd' },
  { label: t('stripes.sourceGhcn'), value: 'ghcn' },
])

const kindItems = computed(() => [
  { label: t('stripes.typeTemperature'), value: 'temperature' },
  { label: t('stripes.typePrecipitation'), value: 'precipitation' },
])

function kindLabel(k: StripesKind) {
  return k === 'precipitation' ? t('stripes.typePrecipitation') : t('stripes.typeTemperature')
}
// What is shown of the years (GH-4156, GH-4233): in the link as `variant` (`stripes`, `bars`, `bars_scale`, `table`), not in the saved settings
const variant = ref<StripesView>('stripes')
const showsTable = computed(() => !isStripesDrawing(variant.value))
const selectedStation = ref<StripesStation | null>(null)
const startYear = ref<number | null>(null)
const endYear = ref<number | null>(null)
// Display toggles default to the user's saved stripes preferences; an explicit
// URL query (e.g. from a shared link) still overrides these below.
const { settings } = useSettings()
const showTitle = ref(settings.value.stripes.showTitle)
const showYears = ref(settings.value.stripes.showYears)
const showDataAvailability = ref(settings.value.stripes.showDataAvailability)
const showSource = ref(settings.value.stripes.showSource)

// The stations the stripes are made for (GH-4258): DWD's from the generic API, GHCN's from the app's own server, each as a read of
// the source and kind chosen, which the key says so that a change of either is a new list and not the one before
const { data: stationsData, pending: stationsPending } = useAsyncData(
  computed(() => `stripes-stations-${source.value}-${kind.value}`),
  () => fetchStripesStations(stripesFetch, source.value, kind.value),
)

// A station of GHCN daily that a link names and the list has not: the list is the stations that still report and span ten years (which the
// 133,041 of the layer would be too many for a picker without), and a link from the map may be to one that has
// stopped. Asked for by its id, and added to the list (GH-4078)
const linkedStation = shallowRef<StripesStation | null>(null)
const stations = computed(() => {
  const list = stationsData.value ?? []
  const linked = linkedStation.value
  return linked && !list.some(station => station.station_id === linked.station_id) ? [...list, linked] : list
})

/** The years of the station chosen, as the list gives them; a station of GHCN daily that has no end is still reporting, and its record is "since" its first year (GH-4078) */
const availableYears = computed(() => {
  const station = selectedStation.value
  const from = station?.start_timestamp?.slice(0, 4)
  if (station && source.value === 'ghcn' && !station.end_timestamp && from)
    return t('mapTool.since', { year: from })
  return `${from ?? ''} - ${station?.end_timestamp?.slice(0, 4) ?? ''}`
})

/** The station of the link that could not be asked for (an outage): told with Retry, and never taken for a station that is not there */
const linkedFailure = ref<{ id: string, message: string } | null>(null)

/** Whether the reader has picked a station that is not the one of the link: its answer, late, is not taken in place of the pick */
const pickedOtherThan = (id: string) => selectedStation.value !== null && selectedStation.value.station_id !== id

async function takeLinkedStation(id: string) {
  linkedFailure.value = null
  try {
    const answer = await $fetch<StationsResponse>('/api/stations', { query: { ...GHCN_NETWORK, parameters: 'daily/data', stations: id }, ...API_FETCH })
    const found = answer.stations?.[0]
    // the page has moved to another source or kind, or the reader has picked another station, while the station was asked for
    if (found && source.value === 'ghcn' && !pickedOtherThan(id)) {
      linkedStation.value = found
      selectedStation.value = found
    }
  }
  catch (failure) {
    if (source.value === 'ghcn' && !pickedOtherThan(id))
      linkedFailure.value = { id, message: describeFetchError(failure) }
  }
}

// The station picker's selection, one array per chosen station: a new array on every render read to the map
// as a new selection, which turned centring on it back on.
const pickedStations = computed(() => selectedStation.value ? [selectedStation.value] : [])

function onPick(picked: StripesStation[]) {
  selectedStation.value = picked[0] ?? null
  // a station picked is not the one of the link, whose failure (and Retry) are no longer about this page's choice
  linkedFailure.value = null
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
  const params = { kind: kindLabel(kind.value), name: station.name, id: station.station_id }
  // a station of GHCN daily is in the country its id says (not Germany, as DWD's stations all are); one with no country the table knows is written without one
  if (source.value === 'ghcn') {
    const country = ghcnCountryName(station.station_id, locale.value)
    return country ? t('stripes.plotTitleCountry', { ...params, country }) : t('stripes.plotTitlePlain', params)
  }
  return t('stripes.plotTitle', params)
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
// what the colours are relative to, as the app calculated it for the station's whole record (GH-4157): in full in the file, and as
// a short line under the chart (GH-4233), the method being the About text's
const referenceFull = computed(() => lastFetchedData.value
  ? stripesReferenceText(lastFetchedData.value.reference, t, value => formatNumber(value, locale.value, 1))
  : '')
// how a day's temperature was made where the years were built from the days (GHCN daily): the midrange of the daily maximum and minimum,
// no 24-hour mean (GH-4222, GH-4078). DWD's own annual values and the precipitation have none
const methodNote = computed(() => stripesMethodNote(lastFetchedData.value?.series.method, t))
/** The line of a saved image on how the day's temperature was made: GHCN daily's temperature only (the answer's `method`) */
const methodLine = computed(() => {
  const method = lastFetchedData.value?.series.method
  return method === 'midrange' ? t('stripes.plotMethodMidrange') : method === 'tavg' ? t('stripes.plotMethodTavg') : undefined
})
const referenceText = computed(() => lastFetchedData.value
  ? stripesReferenceShort(lastFetchedData.value.reference, t, variant.value === 'bars' || variant.value === 'barsScale' ? 'bars' : 'stripes')
  : '')
// said of the image views; the table says all of it itself, and a reader who is in it needs no hint to it
const plotSummary = computed(() => {
  const years = stripeRows.value
  if (!years.length || showsTable.value)
    return undefined
  return `${t('stripes.summary', stripesSummaryParams(years, formatValue))} ${referenceText.value}. ${t('stripes.tableHint', { style: t('stripes.variant.label'), table: t('stripes.variant.table') })}`
})
const tableColumns = computed(() => stripesTableColumns(valueUnit.value, t))
const tableRows = computed(() => stripesTableYears(stripeRows.value).map(year => [
  String(year.year),
  formatNumber(year.value, locale.value, 2),
  formatSigned(year.anomaly, locale.value, 2),
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
}))
// the name of the camera's file: the kind and the station of the stripes shown
const cameraFile = computed(() => `climate_stripes_${kind.value}_${lastFetchedData.value?.series.station.station_id ?? ''}`)
// The values' fetches, numbered as they start, so that only the newest, not stopped by a Reset, shows
// what it fetched. Failed: why the newest could not fetch the values, told in the chart area
let fetchesStarted = 0
const fetchError = ref<string | null>(null)
// the fetch failed because the station has no record long enough, which is no failure of the request but the answer (told in words of the page's own)
const fetchRefused = ref(false)

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
  fetchRefused.value = false
  // this fetch reads the unit as it is now
  refetchShownAfter = false
  // the station of the stripes, as the list has it: the answer is made of its years and names it as the page does
  const askedStation = [selectedStation.value, ...stations.value].find(station => station?.station_id === asked.station) ?? { station_id: asked.station, name: asked.station }

  try {
    const response = await fetchStripes(stripesFetch, {
      source: source.value,
      kind: kind.value,
      station: askedStation,
      startYear: asked.startYear || null,
      endYear: asked.endYear || null,
      // the unit the app settings choose, read at each request (GH-3980): the numbers come back in it, and the
      // colours, which are relative, do not change with it
      unitTargets: stripesUnitTargets(kind.value, settings.value.units),
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
    fetchRefused.value = error instanceof StripesRefusedError && error.reason === 'record-too-short'
    fetchError.value = fetchRefused.value ? t('stripes.noRecord', { years: MIN_RECORD_YEARS }) : describeFetchError(error)
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
      height: shownChart.height,
      // a scale of 3 for high-quality raster images, which keep the proportions and scale the text with them
      scale: format === 'svg' ? 1 : MENU_SCALE,
    })
  }
  catch (error) {
    console.error('The chart image could not be saved', error)
    toast.add({ title: t('dataViewer.chartImageNotSaved'), color: 'error' })
  }
}

/** Saves the table as a CSV file: the columns of the table, the numbers plain, and the reference, the credit and the licence as comment lines */
function downloadTable() {
  const data = lastFetchedData.value
  if (!data)
    return
  const csv = stripesCsv(
    tableColumns.value,
    stripeRows.value,
    stripeClass => t(`stripes.table.classes.${kind.value}.${stripeClass}`),
    csvComments(data),
  )
  if (!csv)
    return
  const station = data.series.station
  downloadBlob(new Blob([csv], { type: 'text/csv;charset=utf-8' }), `climate_stripes_${kind.value}_${station.station_id}_${station.name}.csv`)
}

/** The lines before the table's header: what it is, what the colours are relative to, who the data is from and under which licence, and what wetterdienst did to it (GH-3799) */
function csvComments(data: StripesValuesResponse): string[] {
  const provider = data.metadata?.provider
  const licence = provider?.license
  return [
    plotTitle(data),
    referenceFull.value,
    methodNote.value,
    provider?.attribution || t('stripes.plotSource'),
    licence ? t('credit.licence', { name: licence.name, url: licence.url }) : '',
    processingNote(t),
  ]
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
  fetchRefused.value = false
}

const router = useRouter()

// Preserve initial station id from URL so we can apply it once stations have loaded
const initialStationId = ref<string | null>(route.query.station?.toString() ?? null)

// Initialize simple options from URL if present
// a name that is none of the four is no choice: the stripes
variant.value = stripesViewFromQuery(route.query.variant)
if (route.query.show_title !== undefined && route.query.show_title !== null)
  showTitle.value = route.query.show_title?.toString() === 'true'
if (route.query.show_years !== undefined && route.query.show_years !== null)
  showYears.value = route.query.show_years?.toString() === 'true'
if (route.query.show_data_availability !== undefined && route.query.show_data_availability !== null)
  showDataAvailability.value = route.query.show_data_availability?.toString() === 'true'
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

watch([kind, source], () => {
  linkedStation.value = null
  linkedFailure.value = null
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
    else if (source.value === 'ghcn' && stationsData.value)
      void takeLinkedStation(initialStationId.value)
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
watch([showTitle, showYears, showDataAvailability, showSource], () => {
  settings.value.stripes.showTitle = showTitle.value
  settings.value.stripes.showYears = showYears.value
  settings.value.stripes.showDataAvailability = showDataAvailability.value
  settings.value.stripes.showSource = showSource.value
})

// Update URL query when relevant options change
function stripesToQuery(): Record<string, string> {
  const q: Record<string, string> = {}
  if (kind.value)
    q.kind = kind.value
  if (source.value === 'ghcn') {
    q.provider = GHCN_NETWORK.provider
    q.network = GHCN_NETWORK.network
  }
  q.variant = STRIPES_VIEW_QUERY[variant.value]
  if (selectedStation.value)
    q.station = selectedStation.value.station_id
  if (showTitle.value !== undefined)
    q.show_title = String(showTitle.value)
  if (showYears.value !== undefined)
    q.show_years = String(showYears.value)
  if (showDataAvailability.value !== undefined)
    q.show_data_availability = String(showDataAvailability.value)
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
  () => source.value,
  () => variant.value,
  () => showTitle.value,
  () => showYears.value,
  () => showDataAvailability.value,
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
          <p class="text-gray-600 dark:text-gray-400 mb-4">
            {{ t('stripes.aboutText2') }}
          </p>
          <!-- NOAA's GHCN daily, and why its temperature is the midrange of the day's extremes (GH-4078, GH-4222) -->
          <p class="text-gray-600 dark:text-gray-400 mb-4" data-testid="stripes-about-ghcn">
            {{ t('stripes.aboutGhcn') }}
          </p>
          <!-- how the colours are made, the same for every station (GH-4233): the line under the chart says only what a station's are measured against -->
          <p class="text-gray-600 dark:text-gray-400 mb-4" data-testid="stripes-about-method">
            {{ t('stripes.aboutText3') }}
          </p>
          <!-- what the table's class and anomaly are: it is not above every table (GH-4233) -->
          <p class="text-gray-600 dark:text-gray-400 mb-4" data-testid="stripes-about-columns">
            {{ t('stripes.aboutColumns') }}
          </p>
          <p class="text-gray-600 dark:text-gray-400" data-testid="stripes-about-views">
            {{ t('stripes.aboutText4') }}
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

              <UFormField :label="t('stripes.source')">
                <USelect v-model="source" :items="sourceItems" class="w-full" data-testid="stripes-source" />
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

              <!-- the station of the link could not be asked for: said as the failure it is, not as a station that is not there -->
              <div v-if="linkedFailure" class="flex flex-col items-start gap-2" data-testid="stripes-linked-failure">
                <p role="alert" class="text-sm text-red-600 dark:text-red-400">
                  {{ t('mapTool.stationsFailed') }} ({{ linkedFailure.id }}): {{ linkedFailure.message }}
                </p>
                <UButton :label="t('common.retry')" icon="i-ph-arrow-clockwise" size="sm" color="neutral" variant="outline" data-testid="stripes-linked-retry" @click="takeLinkedStation(linkedFailure.id)" />
              </div>

              <div v-if="selectedStation" class="text-sm text-gray-600 dark:text-gray-400 space-y-1">
                <p v-if="selectedStation.region">
                  <strong>{{ t('stripes.region') }}{{ t('common.colon') }}</strong> {{ selectedStation.region }}
                </p>
                <p>
                  <strong>{{ t('stripes.available') }}{{ t('common.colon') }}</strong> {{ availableYears }}
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
                <!-- a station with no record long enough is not a failure: the sentence alone, which is the answer -->
                <span v-if="fetchRefused" class="font-medium" data-testid="stripes-no-record">{{ fetchError }}</span>
                <template v-else>
                  <span class="font-medium">{{ t('dataViewer.fetchError') }}</span>
                  <span class="text-sm">{{ fetchError }}</span>
                </template>
              </div>
              <!-- the chart tells its own failure, with its Retry -->
              <StripesChart
                v-if="hasPlot && lastFetchedData"
                ref="chart"
                v-model:variant="variant"
                :values="lastFetchedData.values"
                :reference="lastFetchedData.reference"
                :kind="kind"
                :unit="valueUnit"
                :title="plotLabel ?? ''"
                :display="display"
                :label="plotLabel"
                :described-by="plotSummary ? summaryId : undefined"
                :camera-file="cameraFile"
                :source-text="source === 'ghcn' ? t('stripes.plotSourceGhcn') : undefined"
                :method-line="methodLine"
              />
              <!-- under the source line the chart draws, and with it: where the source is not shown, no more is this (GH-3799) -->
              <ProcessingNote v-if="hasPlot && !plotFailed && showSource && !showsTable" class="mt-1 text-center" data-testid="stripes-processing-note" />
              <p v-if="hasPlot && plotSummary" :id="summaryId" class="sr-only">
                {{ plotSummary }}
              </p>
              <p v-if="hasPlot && !plotFailed && referenceText" data-testid="stripes-reference" class="mt-2 text-sm text-muted">
                {{ referenceText }}
              </p>
              <!-- how the temperature of a day was made, for the years of GHCN daily: said wherever its stripes are shown -->
              <p v-if="hasPlot && !plotFailed && methodNote" data-testid="stripes-method" class="mt-2 text-sm text-muted">
                {{ methodNote }}
              </p>
              <!-- the table is a view of its own (GH-4233), as the forecast's is: the same switch, the whole width -->
              <ValuesTable
                v-if="hasPlot && showsTable && tableRows.length"
                full :caption="plotLabel ?? ''" :columns="tableColumns" :rows="tableRows"
              />
              <!-- the table has no source line to carry the credit, as the chart does: it is here, under the table, with the note (GH-4255) -->
              <ProviderCredit
                v-if="hasPlot && !plotFailed && showsTable && lastFetchedData"
                :terms="lastFetchedData.metadata?.provider"
                :fallback="source === 'ghcn' ? t('stripes.plotSourceGhcn') : t('stripes.plotSource')"
                class="mt-3" data-testid="stripes-table-credit"
              />
              <div v-if="hasPlot && !plotFailed" class="mt-4">
                <!-- not modal: a modal menu hides the page from assistive technology (aria-hidden) while its
               own trigger is still focusable in it -->
                <UDropdownMenu
                  :modal="false"
                  :items="showsTable
                    ? [[{ label: t('stripes.downloadCsv'), onSelect: () => downloadTable() }]]
                    : [[
                      { label: t('stripes.downloadPng'), onSelect: () => downloadStripes('png') },
                      { label: t('stripes.downloadJpg'), onSelect: () => downloadStripes('jpeg') },
                      { label: t('stripes.downloadSvg'), onSelect: () => downloadStripes('svg') },
                    ]]"
                >
                  <UButton
                    :label="showsTable ? t('stripes.downloadTable') : t('stripes.downloadImage')" color="primary" variant="outline"
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
