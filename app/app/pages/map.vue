<script setup lang="ts">
import type { ProviderNetworkCoverageResponse, Station, StripesStationsResponse } from '#shared/types/api'
import type { MapLayer, MapState, MeasuredSource, PlacedStation, Point, ReportingRule } from '~/utils/map-tool'
import { defineAsyncComponent } from 'vue'
import MapForecast from '~/components/MapForecast.vue'
import MapStationsNotLoaded from '~/components/MapStationsNotLoaded.vue'
import MapStripes from '~/components/MapStripes.vue'
import { describeFetchError } from '~/utils/api-error'
import {
  DEFAULT_MEASURED,
  distanceKm,
  FORECAST_STATIONS_QUERY,
  forecastLink,
  formatDistance,
  formatPosition,
  historyLink,
  HOME_VIEW,
  MEASURED_NETWORK,
  measurementsLink,
  nearestStations,
  REACH_KM,
  reportingRule,
  SAME_PLACE_KM,
  searchStations,
  stateFromQuery,
  stateToQuery,
  stationAt,
  stationFor,
  STRIPES_KIND,
  stripesLink,
} from '~/utils/map-tool'

// The map tool (GH-3650), from the design of #3580: the stations of the layer chosen in the chips over the map, and a
// panel beside it (a sheet under it on a phone) that finds a station by name, lists the ones near the centre of the
// map and, for the station or the place picked, shows its forecast, its climate stripes, its measurements and its
// history, each at the nearest station that has them. Two layers: the forecast's points (DWD MOSMIX) and the stations
// that measure (DWD's observations, by resolution and dataset).
//
// The station the tool picks for a place is the nearest one within 100 km, a station that is still reporting before one
// that has stopped (`reportingRule`: against the newest end of its own list), and the one under a click on its dot is
// that station, whatever it is. A change of
// layer or dataset picks again by the position of the place, never by the number of the station, which is another
// station in another layer.
//
// What is shown is in the address (`?layer=&resolution=&dataset=&station=&lat=&lon=`), so that a link opens the same
// map, and so that the search of the header opens it on a station (`/map?station=10147`).

const { t, locale } = useI18n()
// the title says which page this is: WCAG 2.4.2, and what a screen reader announces after a navigation
useHead({ title: () => t('mapTool.title') })
const route = useRoute()
const router = useRouter()
const { resolutionLabel, datasetLabel } = useParameterLabel()

// the map's code, Leaflet with it, is loaded apart from the page: the panel is there before the map is. Where the
// chunk cannot be loaded (a redeploy replaced it under an open tab) the map's place says so and offers a reload
const StationMap = defineAsyncComponent({
  loader: () => import('~/components/StationMap.vue'),
  errorComponent: MapStationsNotLoaded,
})

// from 72 rem the panel is beside the map (the workbench of the other tools); below it the map comes first and the
// panel is a sheet under it. The two are in the order the window shows them in the page as well, so that the keyboard
// and a screen reader meet them in that order too (WCAG 1.3.2, 2.4.3)
const wide = useMediaQuery('(min-width: 72rem)')
const parts = computed(() => wide.value ? ['panel', 'stage'] as const : ['stage', 'panel'] as const)
const reducedMotion = useMediaQuery('(prefers-reduced-motion: reduce)')

// ---- what the map shows, from the address ---------------------------------------------------------------------

const initial = stateFromQuery(route.query)
const layer = ref<MapLayer>(initial.layer)
const source = ref<MeasuredSource>(initial.source)
const selectedId = ref<string | null>(initial.stationId)
/** The point the panel is about: the station picked, or the place picked on the map */
const anchor = ref<Point | null>(initial.place)

const keyOf = (shown: MapLayer, from: MeasuredSource) => shown === 'forecast' ? 'forecast' : `measured/${from.resolution}/${from.dataset}`
/** The view shown: the number of a station is a number in the list of one view, and no other's */
const viewKey = computed(() => keyOf(layer.value, source.value))
/** The view the station picked was picked in */
let pickedIn = viewKey.value

// ---- the lists of stations ------------------------------------------------------------------------------------

const forecast = useStationList(() => 'forecast', async () =>
  (await $fetch<{ stations: Station[] }>('/api/stations', { query: FORECAST_STATIONS_QUERY, ...API_FETCH })).stations ?? [])
// the stations that have climate stripes, which the panel asks the nearest of; no layer of the map
const stripes = useStationList(() => STRIPES_KIND, async () =>
  ((await $fetch<StripesStationsResponse>('/api/stripes/stations', { query: { kind: STRIPES_KIND }, ...API_FETCH })).stations ?? [])
    .map(station => ({ ...station, elevation: station.elevation ?? null })))
const measured = useStationList(() => `${source.value.resolution}/${source.value.dataset}`, async () =>
  (await $fetch<{ stations: Station[] }>('/api/stations', {
    query: { ...MEASURED_NETWORK, parameters: `${source.value.resolution}/${source.value.dataset}`, all: 'true' },
    ...API_FETCH,
  })).stations ?? [])

const lists = { forecast, measured }
const current = computed(() => lists[layer.value])
const stations = computed(() => current.value.stations.value)
const listStatus = computed(() => current.value.status.value)
const listFailure = computed(() => current.value.error.value ? describeFetchError(current.value.error.value) : '')

const sourceKey = computed(() => `${source.value.resolution}/${source.value.dataset}`)

// ---- the chips ------------------------------------------------------------------------------------------------

const layerItems = computed(() => [
  { value: 'forecast' as const, label: t('mapTool.layerForecast'), icon: 'i-ph-sun' },
  { value: 'measured' as const, label: t('mapTool.layerMeasured'), icon: 'i-ph-thermometer-simple' },
])
const layerLabel = computed(() => layerItems.value.find(item => item.value === layer.value)!.label)

// the resolutions and datasets DWD's observations have, asked of the backend once the measurements are wanted; a request
// that failed is asked again at the next visit of the layer
const coverage = shallowRef<ProviderNetworkCoverageResponse | null>(null)
let coverageRequest: Promise<void> | null = null
function loadCoverage() {
  coverageRequest ??= $fetch<ProviderNetworkCoverageResponse>('/api/coverage', { query: MEASURED_NETWORK, ...API_FETCH })
    .then((answer) => {
      coverage.value = answer
    })
    .catch(() => {
      // the chips then offer the one source shown, which still works
      coverageRequest = null
    })
  return coverageRequest
}

const resolutionItems = computed(() => {
  const resolutions = Object.keys(coverage.value ?? {})
  if (!resolutions.includes(source.value.resolution))
    resolutions.unshift(source.value.resolution)
  return resolutions.map(resolution => ({ value: resolution, label: resolutionLabel(resolution) }))
})
const datasetItems = computed(() => {
  const datasets = Object.keys(coverage.value?.[source.value.resolution as keyof ProviderNetworkCoverageResponse]?.datasets ?? {})
  if (!datasets.includes(source.value.dataset))
    datasets.unshift(source.value.dataset)
  return datasets.map(dataset => ({ value: dataset, label: datasetLabel(dataset) }))
})

/** The dataset of a resolution the map takes: the one it had if the resolution has it, the daily climate summary's name, or the first */
function datasetFor(resolution: string, wanted: string): string {
  const datasets = Object.keys(coverage.value?.[resolution as keyof ProviderNetworkCoverageResponse]?.datasets ?? {})
  if (!datasets.length || datasets.includes(wanted))
    return wanted
  return datasets.includes(DEFAULT_MEASURED.dataset) ? DEFAULT_MEASURED.dataset : datasets[0]!
}
/** A source of the address that DWD has: a resolution it has, and a dataset of it, which a hand-edited address may not name */
function validSource(wanted: MeasuredSource): MeasuredSource {
  if (!coverage.value)
    return wanted
  if (!Object.keys(coverage.value).includes(wanted.resolution))
    return { ...DEFAULT_MEASURED }
  return { resolution: wanted.resolution, dataset: datasetFor(wanted.resolution, wanted.dataset) }
}

/**
 * Asks for the list of the measuring stations once the source is known to be one that DWD has: a hand-edited address may
 * name a resolution or a dataset that does not exist, which is replaced (the station of the address, picked in the
 * view as it was written, stays picked in the view as it is made right), and no request is made for it.
 */
async function ensureMeasured(force = false) {
  await loadCoverage()
  // the reader has left the layer, and no station needs the list, while the coverage was on its way
  if (layer.value !== 'measured' && !selectedId.value)
    return
  const valid = validSource(source.value)
  if (valid.resolution === source.value.resolution && valid.dataset === source.value.dataset)
    return measured.ensure(force)
  const pickedHere = pickedIn === viewKey.value
  // the watch of the source asks again, for the source that exists
  source.value = valid
  if (pickedHere)
    pickedIn = viewKey.value
}

/** Asks for the list of the layer shown again, as Retry does: the coverage too, where it is what failed */
function retryList() {
  if (layer.value === 'measured')
    return ensureMeasured(true)
  return forecast.ensure(true)
}

/** Asks for the list of the layer shown */
async function ensureCurrent() {
  if (layer.value === 'measured')
    return ensureMeasured()
  void forecast.ensure()
}
watch([layer, sourceKey], ensureCurrent, { immediate: true })

const resolutionChoice = computed({
  get: () => source.value.resolution,
  set: (resolution: string) => {
    source.value = { resolution, dataset: datasetFor(resolution, source.value.dataset) }
  },
})
const datasetChoice = computed({
  get: () => source.value.dataset,
  set: (dataset: string) => {
    source.value = { ...source.value, dataset }
  },
})

// ---- the view of the map, and the stations near its centre ------------------------------------------------------

const view = ref<Point & { zoom: number }>({ ...HOME_VIEW })
const search = ref('')
const searching = computed(() => search.value.trim().length > 0)
const near = computed(() => nearestStations(stations.value, view.value, 8).map(entry => ({ ...entry, distance: entry.distance as number | null })))
const found = computed(() => searchStations(stations.value, search.value, 20).map(station => ({ station, distance: null as number | null })))
const entries = computed(() => searching.value ? found.value : near.value)
const countLabel = computed(() => t('mapTool.count', { count: stations.value.length, shown: stations.value.length.toLocaleString(locale.value) }))
const mapLabel = computed(() => t('mapTool.mapLabel', { layer: layerLabel.value }))

// ---- the station picked ---------------------------------------------------------------------------------------

const selected = computed<PlacedStation | null>(() => selectedId.value ? stations.value.find(station => station.station_id === selectedId.value) ?? null : null)
/** The place picked on the map, where it is not the station itself (more than half a kilometre from it) */
const place = computed(() => anchor.value && selected.value && distanceKm(anchor.value, selected.value) > SAME_PLACE_KM ? anchor.value : null)
/** The number of a station of the address that the layer does not have, told in the panel */
const unknownStation = ref<string | null>(null)
/** A point that the layer has no station within reach of, told in the panel */
const noStationNear = ref(false)

// the panel and its heading are in the page's loop over its two parts, where a template ref would be a list of them
const detailHeading = ref<HTMLElement | null>(null)
const panel = ref<HTMLElement | null>(null)
function setDetailHeading(element: unknown) {
  detailHeading.value = element as HTMLElement | null
}
function setPanel(element: unknown) {
  panel.value = element as HTMLElement | null
}
const announcement = ref('')
const reach = computed(() => formatDistance(REACH_KM, locale.value))

/** Counts the picks from outside the map that it is to move to; the map moves once for each, as soon as the station is there */
const recentre = ref(0)
/** The station the address opened the page with, or a pick from outside, waits to be announced and moved to until its station is there */
let fromAddress = Boolean(selectedId.value)
/** The view was changed under a pick: the list that arrives has the station for the place of it picked again */
let reselect = false

/** Which stations of the layer shown have stopped, by the clock of its list: only the measuring ones have */
const reporting = computed(() => layer.value === 'measured' ? reportingRule(stations.value) : undefined)

function choose(station: PlacedStation, options: { point?: Point, focus?: boolean } = {}) {
  selectedId.value = station.station_id
  pickedIn = viewKey.value
  anchor.value = options.point ?? { latitude: station.latitude, longitude: station.longitude }
  unknownStation.value = null
  noStationNear.value = false
  announcement.value = t('mapTool.chosen', { name: station.name ?? station.station_id })
  void nextTick(() => {
    if (options.focus)
      detailHeading.value?.focus()
    // on a phone the panel is under the map: it comes up to the middle of the window, so that the map and the panel are both seen
    if (!wide.value && panel.value) {
      const top = panel.value.getBoundingClientRect().top + window.scrollY - window.innerHeight * 0.42
      window.scrollTo({ top: Math.max(0, top), behavior: reducedMotion.value ? 'auto' : 'smooth' })
    }
  })
}

/** A point that has no station within reach: nothing is picked, the point is kept, and the panel says so */
function tellNoStationNear(point: Point) {
  selectedId.value = null
  pickedIn = viewKey.value
  anchor.value = point
  unknownStation.value = null
  noStationNear.value = true
  announcement.value = t('mapTool.noStationNear', { distance: reach.value })
}

/**
 * A pick at a point (a click on the map, the centre of the map): the station on its dot where the point is on one,
 * whatever its status, else the station for the place (`stationFor`), which has to be within reach.
 */
function pickAt(point: Point, tolerance: number, focus = false, tap = 0, disc = 0) {
  // nothing to pick from, and no word of there being none, until the list has come
  if (listStatus.value !== 'success')
    return
  // the yellow disc drawn for the station picked is bigger than a dot, and a click on it is on that station
  if (selected.value && disc > 0 && distanceKm(point, selected.value) <= disc)
    return choose(selected.value, { focus })
  const hit = stationAt(stations.value, point, tolerance)
  if (hit)
    return choose(hit, { focus })
  // a tap of a finger (a coarse pointer) has a wider ring than a dot, and in it a station that reports is preferred
  const touched = tap > tolerance ? stationFor(stations.value, point, reporting.value, tap) : null
  if (touched)
    return choose(touched.station, { point, focus })
  const found = stationFor(stations.value, point, reporting.value)
  if (found)
    choose(found.station, { point, focus })
  else
    tellNoStationNear(point)
}

/**
 * A click on the map. `tolerance` is how far from it a dot under the pointer can be (the dot as drawn, and a little
 * more), `tap` how far a station can be for a finger (none for a mouse), both measured by the map, in kilometres.
 */
function onPick(point: Point & { tolerance: number, tap?: number, disc?: number }) {
  pickAt(point, point.tolerance, false, point.tap ?? 0, point.disc ?? 0)
}

/**
 * The place at the centre of the map: the station within half a kilometre of it, else the station for the place, as
 * a click with a mouse that is not on a dot would pick (no ring of a finger): the keyboard's way to a place
 */
function pickCentre() {
  pickAt({ latitude: view.value.latitude, longitude: view.value.longitude }, SAME_PLACE_KM, true)
}

function back() {
  const id = selectedId.value
  selectedId.value = null
  anchor.value = null
  reselect = false
  fromAddress = false
  unknownStation.value = null
  noStationNear.value = false
  announcement.value = ''
  void nextTick(() => {
    // the focus goes back to the station in the list it came from, else to the search
    const button = id ? document.querySelector<HTMLElement>(`[data-station-id="${CSS.escape(id)}"]`) : null
    ;(button ?? document.querySelector<HTMLElement>('#map-search'))?.focus()
  })
}

/** The station of a new view for the place picked, picked again by its position: the same station where it is under the place */
function pickAgain(list: PlacedStation[]) {
  const point = anchor.value!
  const found = stationAt(list, point, SAME_PLACE_KM) ?? stationFor(list, point, reporting.value)?.station
  if (!found)
    return tellNoStationNear(point)
  selectedId.value = found.station_id
  pickedIn = viewKey.value
  unknownStation.value = null
  noStationNear.value = false
  // told, as a station that the reader chose is: it is another station than the one in the heading before
  announcement.value = t('mapTool.chosen', { name: found.name ?? found.station_id })
}

// A change of layer or dataset, and the list that comes after it. The number of a station is the number in the list of
// one view (DWD's forecast points and its measuring stations number their stations alike, and 59 of the numbers are
// two stations), so a pick is never taken to another view by its number: it is picked again in the new list for the
// place it was at. A list that has arrived with no change under it holds the station of the address, or the panel
// says there is none.
watch([viewKey, stations], ([key, list], [previousKey]) => {
  if (key !== previousKey && (selectedId.value || anchor.value) && pickedIn !== key) {
    // with no place to go by (the address named a station and its list has not come) there is nothing to pick again
    reselect = Boolean(anchor.value)
    selectedId.value = null
    noStationNear.value = false
    fromAddress = false
  }
  // the notice of a station that the view before did not have is not about this one
  if (key !== previousKey)
    unknownStation.value = null
  if (!list.length)
    return
  if (reselect) {
    reselect = false
    return pickAgain(list)
  }
  if (selectedId.value && !list.some(station => station.station_id === selectedId.value)) {
    unknownStation.value = selectedId.value
    selectedId.value = null
    anchor.value = null
    fromAddress = false
  }
})

// ---- the nearest station of each kind, for the panel ------------------------------------------------------------

// the lists the panel needs, beside the one shown, asked for once a station is picked; the station is a place, which the
// panel is about from then on (the station of an address has none until the list brings it)
watch(selected, (station) => {
  if (!station)
    return
  if (!anchor.value)
    anchor.value = { latitude: station.latitude, longitude: station.longitude }
  if (fromAddress) {
    fromAddress = false
    recentre.value++
    announcement.value = t('mapTool.chosen', { name: stationName(station) })
  }
  void forecast.ensure()
  void stripes.ensure()
  void ensureMeasured()
}, { immediate: true })
watch(sourceKey, () => {
  if (selected.value)
    void ensureMeasured()
})

/**
 * The station of a card: the station picked, for the layer it is of, and for the others the nearest within reach of
 * the place (`stationFor`), with its distance from the place, none where it is under half a kilometre.
 */
function cardFor(list: PlacedStation[], isShown: boolean, running?: ReportingRule) {
  if (!selected.value)
    return null
  const point = anchor.value ?? selected.value
  if (isShown) {
    const distance = distanceKm(point, selected.value)
    return { station: selected.value, distance: distance > SAME_PLACE_KM ? distance : 0 }
  }
  return stationFor(list, point, running)
}
const forecastPoint = computed(() => cardFor(forecast.stations.value, layer.value === 'forecast'))
const stripesRule = computed(() => reportingRule(stripes.stations.value))
const measuredRule = computed(() => reportingRule(measured.stations.value))
const stripesPoint = computed(() => cardFor(stripes.stations.value, false, stripesRule.value))
const measuredPoint = computed(() => cardFor(measured.stations.value, layer.value === 'measured', measuredRule.value))

const sourceLabel = computed(() => `${datasetLabel(source.value.dataset)}, ${resolutionLabel(source.value.resolution)}`)
/**
 * How long a station has measured: since its first year while it reports, from it to its last year once it has
 * stopped; nothing where it has no end, which says nothing of whether it has stopped.
 */
function measuredFor(station: Station) {
  // a date that does not parse is no year (it would read "NaN")
  const year = (timestamp?: string | null) => {
    const date = timestamp ? new Date(timestamp) : null
    return date && !Number.isNaN(date.getTime()) ? date.getUTCFullYear() : null
  }
  const from = year(station.start_timestamp)
  const to = year(station.end_timestamp)
  if (from === null || to === null)
    return null
  return measuredRule.value(station) ? t('mapTool.since', { year: from }) : t('mapTool.period', { from, to })
}
function stationName(station: Station) {
  return station.name ?? station.station_id
}

// ---- the address follows what is shown, and what the address says from outside is taken ---------------------------

const state = computed<MapState>(() => ({ layer: layer.value, source: source.value, stationId: selectedId.value, place: place.value }))
const queryOf = (map: MapState) => JSON.stringify(stateToQuery(map))

watch(state, (shown) => {
  // the keys that are the map's are replaced, any other the address has stays
  const rest = Object.fromEntries(Object.entries(route.query).filter(([key]) => !['layer', 'resolution', 'dataset', 'station', 'lat', 'lon'].includes(key)))
  // always asked, even where the address already says it: a write of an earlier state that is still on its way is then
  // replaced by this one (the router lets the newer navigation cancel the older), and does not land after it. A
  // rejected or duplicate navigation is no error of the page
  void router.replace({ query: { ...rest, ...stateToQuery(shown) } }).catch(() => {})
})

// An address that names another map than the one shown, from outside the page (the header's search while the map is
// open, a link): the page takes it. What the page wrote itself names what it shows already. Its station is a station
// of the layer it names.
watch(() => route.query, (query) => {
  const named = stateFromQuery(query)
  if (queryOf(named) === queryOf(state.value))
    return
  layer.value = named.layer
  source.value = named.source
  const namedKey = keyOf(named.layer, named.source)
  // the number of a station in another view is another station, so it is a new pick as well
  const newPick = named.stationId !== selectedId.value || namedKey !== pickedIn
  pickedIn = namedKey
  reselect = false
  noStationNear.value = false
  if (newPick) {
    selectedId.value = named.stationId
    unknownStation.value = null
    announcement.value = ''
    fromAddress = Boolean(named.stationId)
  }
  anchor.value = named.place
})
</script>

<template>
  <div class="frame">
    <PageHeader :title="t('mapTool.title')" :lede="t('mapTool.subtitle')" :about-label="t('mapTool.aboutButton')">
      <template #about>
        <div class="space-y-3 text-muted">
          <p>{{ t('mapTool.about1') }}</p>
          <p>{{ t('mapTool.about2') }}</p>
        </div>
      </template>
    </PageHeader>

    <div class="page-body">
      <div class="map-tool" data-layout="workbench">
        <template v-for="part in parts" :key="part">
          <!-- The panel: beside the map on a wide screen, a sheet under it on a phone -->
          <section v-if="part === 'panel'" :ref="setPanel" class="map-panel" aria-labelledby="map-panel-title" data-testid="map-panel">
            <!-- announced when a station is picked, by the map, the list or the address -->
            <p class="sr-only" role="status" data-testid="map-announcement">
              {{ announcement }}
            </p>

            <!-- a station or a place picked: what there is to see of it -->
            <div v-if="selected" class="map-detail">
              <UButton
                :label="t('mapTool.back')"
                icon="i-ph-arrow-left"
                color="neutral"
                variant="ghost"
                size="sm"
                class="-ms-2 self-start"
                data-testid="map-back"
                @click="back"
              />
              <div>
                <h2 id="map-panel-title" :ref="setDetailHeading" tabindex="-1" class="text-2xl font-bold text-highlighted leading-tight break-words focus:outline-none" data-testid="map-station-name">
                  {{ stationName(selected) }}
                </h2>
                <p class="mt-1 text-sm text-muted">
                  {{ t('stripes.station') }} {{ selected.station_id }}<template v-if="selected.region">
                    · {{ selected.region }}
                  </template><template v-if="selected.elevation != null">
                    · {{ t('mapTool.elevation', { value: Math.round(selected.elevation) }) }}
                  </template>
                </p>
                <p class="text-sm text-muted tabular-nums">
                  {{ formatPosition(selected) }}
                </p>
                <p v-if="place" class="mt-2 inline-flex items-center gap-1.5 text-sm text-toned" data-testid="map-place">
                  <UIcon name="i-ph-map-pin" class="size-4 shrink-0" />
                  {{ t('mapTool.pickedPlace', { distance: formatDistance(distanceKm(place, selected), locale) }) }}
                </p>
              </div>

              <!-- the forecast, at the nearest forecast point -->
              <section class="map-card" aria-labelledby="map-forecast-title" data-testid="map-card-forecast">
                <h3 id="map-forecast-title" class="map-card-title">
                  <UIcon name="i-ph-sun" class="map-card-icon" />
                  {{ t('nav.meteogram') }}
                </h3>
                <template v-if="forecastPoint">
                  <p v-if="forecastPoint.distance > 0" class="map-card-note">
                    {{ t('mapTool.at', { name: stationName(forecastPoint.station), distance: formatDistance(forecastPoint.distance, locale) }) }}
                  </p>
                  <MapForecast :station="forecastPoint.station" />
                  <UButton :to="forecastLink(forecastPoint.station.station_id)" :label="t('mapTool.openForecast')" trailing-icon="i-ph-arrow-right" variant="link" class="map-link" />
                </template>
                <p v-else-if="forecast.status.value === 'pending' || forecast.status.value === 'idle'" class="map-card-note" role="status">
                  {{ t('common.loading') }}
                </p>
                <div v-else-if="forecast.status.value === 'error'" class="flex flex-col items-start gap-2">
                  <p class="map-card-note" role="alert">
                    {{ t('mapTool.stationsFailed') }}
                  </p>
                  <UButton :label="t('common.retry')" icon="i-ph-arrow-clockwise" size="sm" color="neutral" variant="outline" @click="forecast.ensure(true)" />
                </div>
                <p v-else class="map-card-note">
                  {{ t('mapTool.noneNearby', { distance: reach }) }}
                </p>
              </section>

              <!-- the climate stripes, at the nearest station that has them -->
              <section class="map-card" aria-labelledby="map-stripes-title" data-testid="map-card-stripes">
                <h3 id="map-stripes-title" class="map-card-title">
                  <UIcon name="i-ph-thermometer-simple" class="map-card-icon" />
                  {{ t('nav.stripes') }}
                </h3>
                <template v-if="stripesPoint">
                  <p v-if="stripesPoint.distance > 0" class="map-card-note">
                    {{ t('mapTool.at', { name: stationName(stripesPoint.station), distance: formatDistance(stripesPoint.distance, locale) }) }}
                  </p>
                  <MapStripes :station-id="stripesPoint.station.station_id" :station-name="stationName(stripesPoint.station)" />
                  <UButton :to="stripesLink(stripesPoint.station.station_id)" :label="t('mapTool.openStripes')" trailing-icon="i-ph-arrow-right" variant="link" class="map-link" />
                </template>
                <p v-else-if="stripes.status.value === 'pending' || stripes.status.value === 'idle'" class="map-card-note" role="status">
                  {{ t('common.loading') }}
                </p>
                <div v-else-if="stripes.status.value === 'error'" class="flex flex-col items-start gap-2">
                  <p class="map-card-note" role="alert">
                    {{ t('mapTool.stationsFailed') }}
                  </p>
                  <UButton :label="t('common.retry')" icon="i-ph-arrow-clockwise" size="sm" color="neutral" variant="outline" @click="stripes.ensure(true)" />
                </div>
                <p v-else class="map-card-note">
                  {{ t('mapTool.noneNearby', { distance: reach }) }}
                </p>
              </section>

              <!-- the measurements and the history, at the nearest station of the source chosen in the chips -->
              <section class="map-card" aria-labelledby="map-measured-title" data-testid="map-card-measured">
                <h3 id="map-measured-title" class="map-card-title">
                  <UIcon name="i-ph-thermometer" class="map-card-icon" />
                  {{ t('home.kindObservationsTitle') }}
                </h3>
                <template v-if="measuredPoint">
                  <p class="map-card-note">
                    {{ sourceLabel }}<template v-if="measuredFor(measuredPoint.station)">
                      · {{ measuredFor(measuredPoint.station) }}
                    </template>
                  </p>
                  <p v-if="measuredPoint.distance > 0" class="map-card-note">
                    {{ t('mapTool.at', { name: stationName(measuredPoint.station), distance: formatDistance(measuredPoint.distance, locale) }) }}
                  </p>
                  <div class="flex flex-col items-start">
                    <UButton :to="measurementsLink(source, measuredPoint.station.station_id)" :label="t('mapTool.openExplorer')" trailing-icon="i-ph-arrow-right" variant="link" class="map-link" />
                    <UButton :to="historyLink(source, measuredPoint.station.station_id)" :label="t('mapTool.openHistory')" trailing-icon="i-ph-arrow-right" variant="link" class="map-link" />
                  </div>
                </template>
                <p v-else-if="measured.status.value === 'pending' || measured.status.value === 'idle'" class="map-card-note" role="status">
                  {{ t('common.loading') }}
                </p>
                <div v-else-if="measured.status.value === 'error'" class="flex flex-col items-start gap-2">
                  <p class="map-card-note" role="alert">
                    {{ t('mapTool.stationsFailed') }}
                  </p>
                  <UButton :label="t('common.retry')" icon="i-ph-arrow-clockwise" size="sm" color="neutral" variant="outline" @click="ensureMeasured(true)" />
                </div>
                <p v-else class="map-card-note">
                  {{ t('mapTool.noneNearby', { distance: reach }) }}
                </p>
              </section>
            </div>

            <!-- nothing picked: find a station, or take one near the centre of the map -->
            <div v-else class="map-browse">
              <h2 id="map-panel-title" class="sr-only">
                {{ t('mapTool.panelTitle') }}
              </h2>
              <p v-if="unknownStation" class="text-sm text-warning" role="status" data-testid="map-unknown">
                {{ t('mapTool.stationNotFound', { id: unknownStation }) }}
              </p>
              <p v-if="noStationNear" class="text-sm text-warning" role="status" data-testid="map-none-near">
                {{ t('mapTool.noStationNear', { distance: reach }) }}
              </p>
              <p v-if="listStatus === 'success'" class="text-sm text-muted sm:hidden" data-testid="map-count-panel">
                {{ countLabel }}
              </p>
              <UInput
                id="map-search"
                v-model="search"
                :aria-label="t('mapTool.search')"
                type="search"
                icon="i-ph-magnifying-glass"
                size="lg"
                :placeholder="t('mapTool.searchPlaceholder')"
                class="w-full"
                autocomplete="off"
              />

              <div>
                <h3 class="map-list-title">
                  {{ searching ? t('mapTool.results') : t('mapTool.nearCentre') }}
                </h3>
                <p v-if="listStatus === 'pending' || listStatus === 'idle'" class="text-sm text-muted" role="status">
                  {{ t('mapTool.loadingStations') }}
                </p>
                <p v-else-if="listStatus === 'error'" class="text-sm text-muted">
                  {{ t('mapTool.stationsFailed') }}
                </p>
                <p v-else-if="!stations.length" class="text-sm text-muted" data-testid="map-empty">
                  {{ t('mapTool.noStations') }}
                </p>
                <p v-else-if="searching && !found.length" class="text-sm text-muted" role="status" data-testid="map-no-results">
                  {{ t('mapTool.noResults') }}
                </p>
                <ul v-else class="map-list" data-testid="map-list">
                  <li v-for="entry in entries" :key="entry.station.station_id">
                    <button type="button" class="map-list-item" :data-station-id="entry.station.station_id" @click="choose(entry.station, { focus: true })">
                      <span class="min-w-0">
                        <span class="block font-semibold text-highlighted break-words">{{ stationName(entry.station) }}</span>
                        <span class="block text-xs text-muted">{{ entry.station.station_id }}<template v-if="entry.station.region"> · {{ entry.station.region }}</template></span>
                      </span>
                      <span v-if="entry.distance !== null" class="shrink-0 text-xs text-muted tabular-nums">{{ formatDistance(entry.distance, locale) }}</span>
                    </button>
                  </li>
                </ul>
                <!-- a click on the map, by keyboard: the place at the centre of the map, which the arrow keys move -->
                <template v-if="!searching && stations.length">
                  <UButton
                    :label="t('mapTool.pickCentre')"
                    icon="i-ph-crosshair"
                    color="neutral"
                    variant="ghost"
                    size="sm"
                    class="mt-1 -ms-2"
                    aria-describedby="map-pick-centre-hint"
                    data-testid="map-pick-centre"
                    @click="pickCentre"
                  />
                  <p id="map-pick-centre-hint" class="sr-only">
                    {{ t('mapTool.pickCentreHint') }}
                  </p>
                </template>
              </div>
            </div>
          </section>

          <!-- The map, and the chips over it that choose its layer -->
          <div v-else class="map-stage" data-testid="map-stage">
            <div class="map-chips">
              <div class="map-chips-row">
                <div class="map-segments" role="group" :aria-label="t('mapTool.layers')">
                  <button
                    v-for="option in layerItems"
                    :key="option.value"
                    type="button"
                    class="map-segment"
                    :aria-pressed="layer === option.value"
                    :data-testid="`map-layer-${option.value}`"
                    @click="layer = option.value"
                  >
                    <UIcon :name="option.icon" class="size-4 shrink-0" />
                    {{ option.label }}
                  </button>
                </div>
                <template v-if="layer === 'measured'">
                  <USelect v-model="resolutionChoice" :items="resolutionItems" :aria-label="t('parameterSelection.resolutionLabel')" size="sm" class="map-select" data-testid="map-resolution" />
                  <USelect v-model="datasetChoice" :items="datasetItems" :aria-label="t('parameterSelection.datasetLabel')" size="sm" class="map-select" data-testid="map-dataset" />
                </template>
                <!-- on a phone the count is in the panel, and the chips take less of the map -->
                <span v-if="listStatus === 'success'" class="map-status map-count" data-testid="map-count">{{ countLabel }}</span>
                <span v-else-if="listStatus === 'pending' || listStatus === 'idle'" class="map-status" role="status">
                  <UIcon name="i-ph-circle-notch" class="size-4 motion-safe:animate-spin" />
                  {{ t('mapTool.loadingStations') }}
                </span>
              </div>
              <UAlert
                v-if="listStatus === 'error'"
                class="map-failure"
                color="error"
                variant="outline"
                icon="i-ph-warning-circle"
                :title="t('mapTool.stationsFailed')"
                :description="listFailure"
                :actions="[{ label: t('common.retry'), onClick: () => retryList() }]"
                data-testid="map-failure"
              />
            </div>

            <ClientOnly>
              <StationMap
                :stations="stations"
                :selected="selected"
                :recentre="recentre"
                :place="place"
                :label="mapLabel"
                @pick="onPick"
                @view="view = $event"
              />
            </ClientOnly>
          </div>
        </template>
      </div>
    </div>
  </div>
</template>

<style>
/* The layout of the tool (GH-3650): the panel beside the map from 72 rem, the workbench's breakpoint and columns;
   below it one column, the map first and the panel under it as a sheet. */
.map-tool {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  gap: 1rem;
  align-items: start;
}
@media (min-width: 72rem) {
  .map-tool {
    grid-template-columns: minmax(20rem, 26rem) minmax(0, 1fr);
    gap: 2rem;
  }
}

/* The stage: the map under the chips. It keeps its place while the panel, which can be long, scrolls on a wide
   screen, and is about half the window on a phone, so that a sheet fits under it. */
.map-stage {
  position: relative;
  isolation: isolate;
  height: clamp(22rem, 64dvh, 36rem);
}
@media (min-width: 72rem) {
  .map-stage {
    position: sticky;
    top: calc(var(--header-height) + 1rem);
    height: clamp(30rem, calc(100dvh - var(--header-height) - 2rem), 52rem);
  }
}
/* a window too low for a map and its panel beside it (a phone on its side, zoom): the map is as high as the window */
@media (max-height: 30rem) {
  .map-stage {
    position: relative;
    top: auto;
    height: 24rem;
  }
}
.map-chips {
  position: absolute;
  z-index: 1001;
  inset-inline: 0.75rem;
  top: 0.75rem;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  /* the map is dragged where there is no chip */
  pointer-events: none;
}
.map-chips-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.5rem;
  /* the row is as wide as the map and its empty space is the map's: only what is in it takes the pointer */
  pointer-events: none;
}
.map-chips-row > *,
.map-failure {
  pointer-events: auto;
}
/* a link of a card breaks onto a second line where its words are longer than the card (320 px, the longer languages) */
.map-link.map-link {
  padding-inline: 0;
  white-space: normal;
  text-align: start;
}
/* the label of a button is a `truncate` span, which keeps one line */
.map-link.map-link .truncate {
  overflow: visible;
  white-space: normal;
  text-overflow: clip;
}
.map-segments {
  display: inline-flex;
  max-width: 100%;
  padding: 0.1875rem;
  border: 1px solid var(--ui-border-accented);
  border-radius: 999px;
  background: var(--ui-bg);
  box-shadow: 0 1px 3px rgb(15 23 42 / 0.15);
}
.map-segment {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 0.375rem;
  min-width: 0;
  min-height: 2.25rem;
  padding: 0.25rem 0.75rem;
  border-radius: 999px;
  color: var(--ui-text-toned);
  font-size: 0.875rem;
  font-weight: 600;
  line-height: 1.15;
  text-align: center;
  /* a long word (Verwachtingsstations) breaks rather than spill out of its chip */
  overflow-wrap: anywhere;
}
/* on the narrowest screens the two layers stand one over the other, so that the words of a long language fit */
@media (max-width: 23.99rem) {
  .map-segments {
    flex-direction: column;
    border-radius: 1.25rem;
  }
}
.map-segment:hover {
  background: var(--ui-bg-elevated);
  color: var(--ui-text-highlighted);
}
/* the layer shown: filled with the logo's navy (12.5:1 with white), a label in a chip that is no colour alone: it is
   pressed (aria-pressed) and its name is written */
.map-segment[aria-pressed="true"] {
  background: var(--color-tile-navy);
  color: #ffffff;
}
/* at night only: a print is the light page */
@media not print {
  .dark .map-segment[aria-pressed="true"] {
    background: var(--color-brand-300);
    color: var(--color-ink-950);
  }
}
.map-select {
  /* the two choices share a row where it is narrow, and share what is left of it */
  flex: 1 1 7rem;
  min-width: 0;
  max-width: 11rem;
  box-shadow: 0 1px 3px rgb(15 23 42 / 0.15);
}
.map-status {
  display: inline-flex;
  align-items: center;
  gap: 0.375rem;
  padding: 0.25rem 0.75rem;
  border-radius: 999px;
  background: var(--ui-bg);
  color: var(--ui-text-toned);
  font-size: 0.8125rem;
  box-shadow: 0 1px 3px rgb(15 23 42 / 0.15);
  font-variant-numeric: tabular-nums;
}
/* on a phone the count is in the panel, and the chips take less of the map (not a utility class: this rule is not in a
   layer, so a utility could not hide what it sets) */
@media (max-width: 39.99rem) {
  .map-count {
    display: none;
  }
}
.map-failure {
  max-width: 28rem;
  background: var(--ui-bg);
}

/* The panel: a card beside the map; on a phone a sheet under it, its top edge rounded and lifted over the map's foot */
.map-panel {
  min-width: 0;
  padding: 1rem;
  border: 1px solid var(--ui-border);
  border-radius: calc(var(--ui-radius) * 3);
  background: var(--ui-bg);
}
@media (max-width: 71.99rem) {
  .map-panel {
    margin-top: -0.5rem;
    border-radius: calc(var(--ui-radius) * 4) calc(var(--ui-radius) * 4) calc(var(--ui-radius) * 3) calc(var(--ui-radius) * 3);
    box-shadow: 0 -6px 16px -8px rgb(15 23 42 / 0.2);
    position: relative;
    z-index: 1;
  }
}
.map-browse,
.map-detail {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}
.map-list-title {
  margin-bottom: 0.5rem;
  font-size: 0.8125rem;
  font-weight: 700;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--ui-text-muted);
}
.map-list {
  display: flex;
  flex-direction: column;
  gap: 0.125rem;
}
.map-list-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
  width: 100%;
  min-height: 2.75rem;
  padding: 0.375rem 0.625rem;
  border-radius: calc(var(--ui-radius) * 2);
  text-align: start;
}
.map-list-item:hover {
  background: var(--ui-bg-elevated);
}
.map-card {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 0.625rem;
  padding: 0.875rem;
  border: 1px solid var(--ui-border);
  border-radius: calc(var(--ui-radius) * 2.5);
}
.map-card > :where(div, figure, ul) {
  align-self: stretch;
}
.map-card-title {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 1rem;
  font-weight: 700;
  color: var(--ui-text-highlighted);
}
.map-card-icon {
  width: 1.25rem;
  height: 1.25rem;
  color: var(--ui-text-toned);
}
.map-card-note {
  font-size: 0.875rem;
  color: var(--ui-text-muted);
}
</style>
