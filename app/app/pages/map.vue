<script setup lang="ts">
import type { ProviderNetworkCoverageResponse, Station, StripesStationsResponse } from '#shared/types/api'
import type { MapLayer, MapState, MeasuredSource, PlacedStation, Point } from '~/utils/map-tool'
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
  nearestWithin,
  REACH_KM,
  SAME_PLACE_KM,
  searchStations,
  stateFromQuery,
  stateToQuery,
  STRIPES_KIND,
  stripesLink,
} from '~/utils/map-tool'

// The map tool (GH-3650), from the design of #3580: the stations of the layer chosen in the chips over the map, and a
// panel beside it (a sheet under it on a phone) that finds a station by name, lists the ones near the centre of the
// map and, for the station or the place picked, shows its forecast, its climate stripes, its measurements and its
// history, each at the nearest station that has them. Two layers: the forecast's points (DWD MOSMIX) and the stations
// that measure (DWD's observations, by resolution and dataset).
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

// ---- the lists of stations ------------------------------------------------------------------------------------

const forecast = useStationList(() => 'forecast', async () =>
  (await $fetch<{ stations: Station[] }>('/api/stations', { query: FORECAST_STATIONS_QUERY, ...RETRY_TRANSIENT })).stations ?? [])
// the stations that have climate stripes, which the panel asks the nearest of; no layer of the map
const stripes = useStationList(() => STRIPES_KIND, async () =>
  ((await $fetch<StripesStationsResponse>('/api/stripes/stations', { query: { kind: STRIPES_KIND }, ...RETRY_TRANSIENT })).stations ?? [])
    // the stripes' stations carry no elevation
    .map(station => ({ ...station, elevation: null })))
const measured = useStationList(() => `${source.value.resolution}/${source.value.dataset}`, async () =>
  (await $fetch<{ stations: Station[] }>('/api/stations', {
    query: { ...MEASURED_NETWORK, parameters: `${source.value.resolution}/${source.value.dataset}`, all: 'true' },
    ...RETRY_TRANSIENT,
  })).stations ?? [])

const lists = { forecast, measured }
const current = computed(() => lists[layer.value])
const stations = computed(() => current.value.stations.value)
const listStatus = computed(() => current.value.status.value)
const listFailure = computed(() => current.value.error.value ? describeFetchError(current.value.error.value) : '')

watch([layer, () => `${source.value.resolution}/${source.value.dataset}`], () => void current.value.ensure(), { immediate: true })

// ---- the chips ------------------------------------------------------------------------------------------------

const layerItems = computed(() => [
  { value: 'forecast' as const, label: t('mapTool.layerForecast'), icon: 'i-ph-sun' },
  { value: 'measured' as const, label: t('mapTool.layerMeasured'), icon: 'i-ph-thermometer-simple' },
])
const layerLabel = computed(() => layerItems.value.find(item => item.value === layer.value)!.label)

// the resolutions and datasets DWD's observations have, asked of the backend once the measurements are wanted
const coverage = shallowRef<ProviderNetworkCoverageResponse | null>(null)
let coverageAsked = false
async function loadCoverage() {
  if (coverageAsked)
    return
  coverageAsked = true
  try {
    coverage.value = await $fetch<ProviderNetworkCoverageResponse>('/api/coverage', { query: MEASURED_NETWORK, ...RETRY_TRANSIENT })
  }
  catch {
    // the chips then offer the one source shown, which still works; asked for again at the next visit of the layer
    coverageAsked = false
  }
}
watch(layer, (shown) => {
  if (shown === 'measured')
    void loadCoverage()
}, { immediate: true })

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

function choose(station: PlacedStation, options: { point?: Point, focus?: boolean } = {}) {
  selectedId.value = station.station_id
  anchor.value = options.point ?? { latitude: station.latitude, longitude: station.longitude }
  unknownStation.value = null
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

/** A click on the map: the station nearest to it; a click on a dot is that station, with no place apart */
function onPick(point: Point & { tolerance: number }) {
  const [nearest] = nearestStations(stations.value, point, 1)
  if (!nearest)
    return
  choose(nearest.station, { point: nearest.distance <= point.tolerance ? undefined : { latitude: point.latitude, longitude: point.longitude } })
}

/** The place at the centre of the map, as a click there would pick it: the keyboard's way to a place */
function pickCentre() {
  const point = { latitude: view.value.latitude, longitude: view.value.longitude }
  const [nearest] = nearestStations(stations.value, point, 1)
  if (nearest)
    choose(nearest.station, { point: nearest.distance <= SAME_PLACE_KM ? undefined : point, focus: true })
}

function back() {
  const id = selectedId.value
  selectedId.value = null
  anchor.value = null
  announcement.value = ''
  void nextTick(() => {
    // the focus goes back to the station in the list it came from, else to the search
    const button = id ? document.querySelector<HTMLElement>(`[data-station-id="${CSS.escape(id)}"]`) : null
    ;(button ?? document.querySelector<HTMLElement>('#map-search'))?.focus()
  })
}

// A list that has arrived: the station of the address is in it, or, where the layer has just been changed, the nearest
// station of the new layer takes its place; a station the layer does not have is dropped, and the panel says so
watch(stations, (list) => {
  if (!list.length || !selectedId.value)
    return
  if (list.some(station => station.station_id === selectedId.value))
    return
  const [nearest] = anchor.value ? nearestStations(list, anchor.value, 1) : []
  if (nearest) {
    selectedId.value = nearest.station.station_id
  }
  else {
    unknownStation.value = selectedId.value
    selectedId.value = null
    anchor.value = null
  }
})

// ---- the nearest station of each kind, for the panel ------------------------------------------------------------

// the lists the panel needs, beside the one shown, asked for once a station is picked
watch(selected, (station) => {
  if (!station)
    return
  void forecast.ensure()
  void stripes.ensure()
  void measured.ensure()
}, { immediate: true })

/** The nearest station of a list to the point the panel is about; the station itself for the layer it is of */
function nearestOf(list: PlacedStation[], isShown: boolean) {
  if (!selected.value)
    return null
  if (isShown)
    return { station: selected.value, distance: 0 }
  return nearestWithin(list, anchor.value ?? selected.value)
}
const forecastPoint = computed(() => nearestOf(forecast.stations.value, layer.value === 'forecast'))
const stripesPoint = computed(() => nearestOf(stripes.stations.value, false))
const measuredPoint = computed(() => nearestOf(measured.stations.value, layer.value === 'measured'))

const sourceLabel = computed(() => `${datasetLabel(source.value.dataset)}, ${resolutionLabel(source.value.resolution)}`)
/** How long a station has measured: since its first year, or from it to its last where it has stopped */
function measuredFor(station: Station) {
  const year = (timestamp?: string | null) => timestamp ? new Date(timestamp).getUTCFullYear() : null
  const from = year(station.start_timestamp)
  const to = year(station.end_timestamp)
  if (from === null)
    return null
  return to === null ? t('mapTool.since', { year: from }) : t('mapTool.period', { from, to })
}
function stationName(station: Station) {
  return station.name ?? station.station_id
}
const reach = computed(() => formatDistance(REACH_KM, locale.value))

// ---- the address follows what is shown, and what the address says from outside is taken ---------------------------

const state = computed<MapState>(() => ({ layer: layer.value, source: source.value, stationId: selectedId.value, place: place.value }))
const queryOf = (map: MapState) => JSON.stringify(stateToQuery(map))

/** Counts the picks from outside the map that it is to move to; the map moves once for each, as soon as the station is there */
const recentre = ref(selectedId.value ? 1 : 0)
/** The station the address opened the page with, or a pick from outside, waits to be announced until the station is there */
let announceWhenFound = Boolean(selectedId.value)

watch(state, (shown) => {
  // the keys that are the map's are replaced, any other the address has stays
  const rest = Object.fromEntries(Object.entries(route.query).filter(([key]) => !['layer', 'resolution', 'dataset', 'station', 'lat', 'lon'].includes(key)))
  // always asked, even where the address already says it: a write of an earlier state that is still on its way is then
  // replaced by this one (the router lets the newer navigation cancel the older), and does not land after it. A
  // rejected or duplicate navigation is no error of the page
  void router.replace({ query: { ...rest, ...stateToQuery(shown) } }).catch(() => {})
})

// An address that names another map than the one shown, from outside the page (the header's search while the map is
// open, a link): the page takes it. What the page wrote itself names what it shows already.
watch(() => route.query, (query) => {
  const named = stateFromQuery(query)
  if (queryOf(named) === queryOf(state.value))
    return
  layer.value = named.layer
  source.value = named.source
  if (named.stationId !== selectedId.value) {
    selectedId.value = named.stationId
    unknownStation.value = null
    if (named.stationId)
      recentre.value++
    announceWhenFound = Boolean(named.stationId)
  }
  anchor.value = named.place
})

// told to a screen reader once its station is there, as a pick in the panel is
watch(selected, (station) => {
  if (station && announceWhenFound) {
    announceWhenFound = false
    announcement.value = t('mapTool.chosen', { name: stationName(station) })
  }
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
                  <UButton :to="forecastLink(forecastPoint.station.station_id)" :label="t('mapTool.openForecast')" trailing-icon="i-ph-arrow-right" variant="link" class="px-0" />
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
                  <UButton :to="stripesLink(stripesPoint.station.station_id)" :label="t('mapTool.openStripes')" trailing-icon="i-ph-arrow-right" variant="link" class="px-0" />
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
                    <UButton :to="measurementsLink(source, measuredPoint.station.station_id)" :label="t('mapTool.openExplorer')" trailing-icon="i-ph-arrow-right" variant="link" class="px-0" />
                    <UButton :to="historyLink(source, measuredPoint.station.station_id)" :label="t('mapTool.openHistory')" trailing-icon="i-ph-arrow-right" variant="link" class="px-0" />
                  </div>
                </template>
                <p v-else-if="measured.status.value === 'pending' || measured.status.value === 'idle'" class="map-card-note" role="status">
                  {{ t('common.loading') }}
                </p>
                <div v-else-if="measured.status.value === 'error'" class="flex flex-col items-start gap-2">
                  <p class="map-card-note" role="alert">
                    {{ t('mapTool.stationsFailed') }}
                  </p>
                  <UButton :label="t('common.retry')" icon="i-ph-arrow-clockwise" size="sm" color="neutral" variant="outline" @click="measured.ensure(true)" />
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
                <span v-if="listStatus === 'success'" class="map-status" data-testid="map-count">{{ countLabel }}</span>
                <span v-else-if="listStatus === 'pending'" class="map-status" role="status">
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
                :actions="[{ label: t('common.retry'), onClick: () => current.ensure(true) }]"
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
  height: clamp(20rem, 58dvh, 34rem);
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
.map-chips > * {
  pointer-events: auto;
}
.map-chips-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.5rem;
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
.dark .map-segment[aria-pressed="true"] {
  background: var(--color-brand-300);
  color: var(--color-ink-950);
}
.map-select {
  min-width: 8rem;
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
