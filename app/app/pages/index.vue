<script setup lang="ts">
import type { CoverageResponse, ProviderNetworkCoverageResponse, Station, StripesStationsResponse } from '#shared/types/api'
import type { AtlasLayer, MeasuredSource, PlacedStation } from '~/utils/atlas'
import { defineAsyncComponent } from 'vue'
import MapStationsNotLoaded from '~/components/MapStationsNotLoaded.vue'
import { describeFetchError } from '~/utils/api-error'
import {
  ATLAS_LAYERS,
  DEFAULT_MEASURED,
  distanceKm,
  FORECAST_STATIONS_QUERY,
  forecastLink,
  formatDistance,
  formatPosition,
  historyLink,
  measurementsLink,
  nearestStations,
  searchStations,
  STRIPES_KIND,
  stripesLink,
} from '~/utils/atlas'

// The home page is the map (GH-3518): the stations of what is chosen in the filters over it, and a panel
// beside it (a sheet under it on a phone) that finds a station by name, lists the ones near the centre of
// the map, and, for the station or place picked, has its forecast, its climate stripes, its measurements
// and its history, each at the nearest station that has them.

const { t, locale } = useI18n()
const route = useRoute()
const router = useRouter()
const { resolutionLabel, datasetLabel } = useParameterLabel()

// the map's code, Leaflet with it, is loaded apart from the page: the panel is there before the map is
const mapNotLoaded = ref(false)
const AtlasMap = defineAsyncComponent({
  loader: () => import('~/components/AtlasMap.vue').then(
    (module) => {
      mapNotLoaded.value = false
      return module
    },
    (error) => {
      mapNotLoaded.value = true
      throw error
    },
  ),
  errorComponent: MapStationsNotLoaded,
})
const AtlasForecast = defineAsyncComponent(() => import('~/components/AtlasForecast.vue'))

const wide = useMediaQuery('(min-width: 1024px)')
const reducedMotion = useMediaQuery('(prefers-reduced-motion: reduce)')

// ---- what the map shows, from the address -------------------------------------------------------------

const query = route.query
const layer = ref<AtlasLayer>(ATLAS_LAYERS.includes(query.layer as AtlasLayer) ? query.layer as AtlasLayer : 'forecast')
const source = ref<MeasuredSource>({
  provider: query.provider?.toString() || DEFAULT_MEASURED.provider,
  network: query.network?.toString() || DEFAULT_MEASURED.network,
  resolution: query.resolution?.toString() || DEFAULT_MEASURED.resolution,
  dataset: query.dataset?.toString() || DEFAULT_MEASURED.dataset,
})
const sourceKey = computed(() => `${source.value.provider}/${source.value.network}/${source.value.resolution}/${source.value.dataset}`)

const selectedId = ref<string | null>(query.station?.toString() || null)
const anchorFromQuery = Number.isFinite(Number(query.lat)) && Number.isFinite(Number(query.lon)) && query.lat != null && query.lon != null
  ? { latitude: Number(query.lat), longitude: Number(query.lon) }
  : null
/** The point the panel is about: the station picked, or the place picked on the map */
const anchor = ref<{ latitude: number, longitude: number } | null>(anchorFromQuery)

// ---- the lists of stations --------------------------------------------------------------------------

const forecast = useAtlasStations(() => 'forecast', async () =>
  (await $fetch<{ stations: Station[] }>('/api/stations', { query: FORECAST_STATIONS_QUERY, ...RETRY_TRANSIENT })).stations ?? [])
const stripes = useAtlasStations(() => STRIPES_KIND, async () =>
  // the stripes' stations carry no elevation: none is told for them
  ((await $fetch<StripesStationsResponse>('/api/stripes/stations', { query: { kind: STRIPES_KIND }, ...RETRY_TRANSIENT })).stations ?? [])
    .map(station => ({ ...station, elevation: null })))
const measured = useAtlasStations(() => sourceKey.value, async () =>
  (await $fetch<{ stations: Station[] }>('/api/stations', {
    query: {
      provider: source.value.provider,
      network: source.value.network,
      parameters: `${source.value.resolution}/${source.value.dataset}`,
      all: 'true',
    },
    ...RETRY_TRANSIENT,
  })).stations ?? [])

const lists = { forecast, measured, stripes }
const current = computed(() => lists[layer.value])
const stations = computed(() => current.value.stations.value)
const listStatus = computed(() => current.value.status.value)
const listFailure = computed(() => current.value.error.value ? describeFetchError(current.value.error.value) : '')

watch([layer, sourceKey], () => void current.value.ensure(), { immediate: true })

// ---- the filters ------------------------------------------------------------------------------------

const layerItems = computed(() => [
  { value: 'forecast' as const, label: t('atlas.layerForecast'), icon: 'i-lucide-cloud-sun' },
  { value: 'measured' as const, label: t('atlas.layerMeasured'), icon: 'i-lucide-thermometer' },
  { value: 'stripes' as const, label: t('atlas.layerStripes'), icon: 'i-lucide-chart-column-big' },
])

// the networks that measure, and that need no key this backend lacks; asked for once the measurements are shown
const { data: coverage, execute: loadCoverage } = useFetch<CoverageResponse>('/api/coverage', { immediate: false, ...RETRY_TRANSIENT })
const networkCoverage = ref<ProviderNetworkCoverageResponse | null>(null)
let networkCoverageKey = ''

const providerItems = computed(() => {
  const items = Object.entries(coverage.value ?? {}).flatMap(([provider, networks]) =>
    Object.entries(networks)
      .filter(([, info]) => info.kind === 'observation' && (!info.auth || info.configured))
      .map(([network, info]) => ({ value: `${provider}/${network}`, label: `${info.name_short} · ${network}` })))
  const chosen = `${source.value.provider}/${source.value.network}`
  if (!items.some(item => item.value === chosen))
    items.push({ value: chosen, label: `${source.value.provider.toUpperCase()} · ${source.value.network}` })
  return items.sort((a, b) => a.label.localeCompare(b.label, locale.value))
})
const resolutionItems = computed(() => Object.keys(networkCoverage.value ?? { [source.value.resolution]: null })
  .map(resolution => ({ value: resolution, label: resolutionLabel(resolution) })))
const datasetItems = computed(() => {
  const datasets = networkCoverage.value?.[source.value.resolution as keyof ProviderNetworkCoverageResponse]?.datasets
  return Object.keys(datasets ?? { [source.value.dataset]: null }).map(dataset => ({ value: dataset, label: datasetLabel(dataset) }))
})

/** The dataset of a resolution the map takes: the one asked for, the daily climate summary, or the first */
function pickDataset(coverageOf: ProviderNetworkCoverageResponse, resolution: string, wanted: string): string {
  const datasets = Object.keys(coverageOf[resolution as keyof ProviderNetworkCoverageResponse]?.datasets ?? {})
  return datasets.includes(wanted) ? wanted : datasets.includes('climate_summary') ? 'climate_summary' : datasets[0] ?? wanted
}

async function loadNetworkCoverage(provider: string, network: string) {
  const key = `${provider}/${network}`
  if (networkCoverageKey === key && networkCoverage.value)
    return networkCoverage.value
  networkCoverageKey = key
  try {
    const answer = await $fetch<ProviderNetworkCoverageResponse>('/api/coverage', { query: { provider, network }, ...RETRY_TRANSIENT })
    if (networkCoverageKey === key)
      networkCoverage.value = answer
    return answer
  }
  catch {
    return null
  }
}

watch(layer, (shown) => {
  if (shown !== 'measured')
    return
  if (!coverage.value)
    void loadCoverage()
  void loadNetworkCoverage(source.value.provider, source.value.network)
}, { immediate: true })

const providerChoice = computed({
  get: () => `${source.value.provider}/${source.value.network}`,
  set: async (value: string) => {
    const [provider, network] = value.split('/') as [string, string]
    networkCoverage.value = null
    const answer = await loadNetworkCoverage(provider, network)
    const resolutions = Object.keys(answer ?? {})
    const resolution = resolutions.includes(source.value.resolution) ? source.value.resolution : resolutions.includes('daily') ? 'daily' : resolutions[0] ?? source.value.resolution
    source.value = { provider, network, resolution, dataset: answer ? pickDataset(answer, resolution, source.value.dataset) : source.value.dataset }
  },
})
const resolutionChoice = computed({
  get: () => source.value.resolution,
  set: (resolution: string) => {
    source.value = { ...source.value, resolution, dataset: networkCoverage.value ? pickDataset(networkCoverage.value, resolution, source.value.dataset) : source.value.dataset }
  },
})
const datasetChoice = computed({
  get: () => source.value.dataset,
  set: (dataset: string) => {
    source.value = { ...source.value, dataset }
  },
})

// ---- the view of the map, and the stations near its centre ------------------------------------------

const view = ref({ latitude: 51.2, longitude: 10.4, zoom: 6 })
const search = ref('')
const searching = computed(() => search.value.trim().length > 0)
const near = computed(() => nearestStations(stations.value, view.value, 8))
const found = computed(() => searching.value ? searchStations(stations.value, search.value, 20) : [])

const countLabel = computed(() => t('atlas.count', { count: stations.value.length, shown: stations.value.length.toLocaleString(locale.value) }))

// ---- the station picked -----------------------------------------------------------------------------

const selected = computed<PlacedStation | null>(() => selectedId.value ? stations.value.find(station => station.station_id === selectedId.value) ?? null : null)
/** The place picked on the map, where it is not the station itself (more than half a kilometre from it) */
const place = computed(() => anchor.value && selected.value && distanceKm(anchor.value, selected.value) > 0.5 ? anchor.value : null)

const detailHeading = ref<HTMLElement | null>(null)
const panel = ref<HTMLElement | null>(null)
const announcement = ref('')

function choose(station: PlacedStation, options: { point?: { latitude: number, longitude: number }, focus?: boolean } = {}) {
  selectedId.value = station.station_id
  anchor.value = options.point ?? { latitude: station.latitude, longitude: station.longitude }
  announcement.value = t('atlas.chosen', { name: station.name ?? station.station_id })
  void nextTick(() => {
    if (options.focus)
      detailHeading.value?.focus()
    // on a phone the panel is under the map: it comes up to half the window, so the map and the panel are both seen
    if (!wide.value && panel.value) {
      const top = panel.value.getBoundingClientRect().top + window.scrollY - window.innerHeight * 0.42
      window.scrollTo({ top: Math.max(0, top), behavior: reducedMotion.value ? 'auto' : 'smooth' })
    }
  })
}

/** A click on the map: the station nearest to it; a click on a dot is that station, with no place apart */
function onPick(point: { latitude: number, longitude: number, tolerance: number }) {
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
    choose(nearest.station, { point: nearest.distance <= 0.5 ? undefined : point, focus: true })
}

function back() {
  const id = selectedId.value
  selectedId.value = null
  anchor.value = null
  announcement.value = ''
  void nextTick(() => {
    // the focus goes back to the station in the list it came from, else to the search
    const button = id ? document.querySelector<HTMLElement>(`[data-station-id="${CSS.escape(id)}"]`) : null
    ;(button ?? document.querySelector<HTMLElement>('#atlas-search'))?.focus()
  })
}

// a layer shown anew keeps the point the panel is about: its station is the nearest one of the new layer
watch(stations, (list) => {
  if (!list.length || !selectedId.value)
    return
  if (list.some(station => station.station_id === selectedId.value))
    return
  const [nearest] = anchor.value ? nearestStations(list, anchor.value, 1) : []
  if (nearest)
    selectedId.value = nearest.station.station_id
  else
    selectedId.value = null
})

// ---- the nearest station of each kind, for the panel ------------------------------------------------

/** How far the nearest station of a kind may be for the panel to offer it: beyond, it is another place */
const REACH_KM = 100

watch(selected, (station) => {
  if (!station)
    return
  // the lists the panel needs, beside the one shown
  void forecast.ensure()
  void stripes.ensure()
  void measured.ensure()
}, { immediate: true })

function nearestOf(list: PlacedStation[], self: boolean) {
  if (!selected.value)
    return null
  if (self)
    return { station: selected.value, distance: 0 }
  const point = anchor.value ?? selected.value
  const [nearest] = nearestStations(list, point, 1)
  return nearest && nearest.distance <= REACH_KM ? nearest : null
}
const forecastPoint = computed(() => nearestOf(forecast.stations.value, layer.value === 'forecast'))
const stripesPoint = computed(() => nearestOf(stripes.stations.value, layer.value === 'stripes'))
const measuredPoint = computed(() => nearestOf(measured.stations.value, layer.value === 'measured'))

function status(kind: 'forecast' | 'stripes' | 'measured') {
  return lists[kind].status.value
}

function sinceYear(station: Station) {
  return station.start_timestamp ? new Date(station.start_timestamp).getUTCFullYear() : null
}

const sourceLabel = computed(() => `${datasetLabel(source.value.dataset)}, ${resolutionLabel(source.value.resolution)}`)

// ---- the address follows what is shown --------------------------------------------------------------

watch([layer, source, selectedId, place], () => {
  const next: Record<string, string> = {}
  if (layer.value !== 'forecast')
    next.layer = layer.value
  if (sourceKey.value !== `${DEFAULT_MEASURED.provider}/${DEFAULT_MEASURED.network}/${DEFAULT_MEASURED.resolution}/${DEFAULT_MEASURED.dataset}`)
    Object.assign(next, source.value)
  if (selectedId.value)
    next.station = selectedId.value
  if (place.value) {
    next.lat = place.value.latitude.toFixed(4)
    next.lon = place.value.longitude.toFixed(4)
  }
  const now = Object.fromEntries(Object.entries(route.query).map(([key, value]) => [key, value?.toString() ?? '']))
  if (JSON.stringify(now) !== JSON.stringify(next))
    void router.replace({ query: next }).catch(() => {})
})

// ---- on a phone, the map in view when it takes the focus ---------------------------------------------

function onStageFocus() {
  if (!wide.value && window.scrollY > 0)
    window.scrollTo({ top: 0, behavior: 'auto' })
}

// ---- what the panel says about the project, when no station is picked --------------------------------

const collator = computed(() => new Intl.Collator(locale.value, { numeric: true }))
const { data: providerList, pending: providersPending, error: providersError, refresh: refreshProviders } = useProviders()
const providers = computed(() => (providerList.value?.providers ?? [])
  .map(provider => ({ key: provider.provider, name: provider.name_short, flag: flagEmoji(provider.country_code) }))
  .sort((a, b) => collator.value.compare(a.name, b.name)))
const providersFailure = computed(() => providersError.value ? describeFetchError(providersError.value) : '')
const providersLoading = computed(() => providersPending.value && !providerList.value)
const PLACEHOLDER_WIDTHS = ['w-14', 'w-20', 'w-16', 'w-24', 'w-12', 'w-20', 'w-16']
const placeholders = Array.from({ length: 22 }, (_, index) => PLACEHOLDER_WIDTHS[index % PLACEHOLDER_WIDTHS.length])

const stats = computed(() => [
  { key: 'providers', value: providerList.value ? String(providerList.value.metadata.counts.providers) : null, label: t('home.statProviders') },
  { key: 'parameters', value: providerList.value ? String(providerList.value.metadata.counts.parameters) : null, label: t('home.statParameters') },
  { key: 'resolutions', value: '1 min – 1 a', label: t('home.statResolutions') },
  { key: 'price', value: '0 €', label: t('home.statPrice') },
])

const devEntries = computed(() => [
  { key: 'pypi', label: 'pip install wetterdienst', icon: 'i-simple-icons-python', to: 'https://pypi.org/project/wetterdienst/', title: undefined },
  // this instance's own endpoints: /docs is the backend's Swagger UI, proxied onto this origin, and /mcp/v1 is the
  // endpoint itself; both are nitro's, not the router's, so they need a full navigation
  { key: 'api', label: 'REST API', icon: 'i-lucide-code', to: '/docs', title: undefined },
  { key: 'mcp', label: 'MCP', icon: 'i-lucide-bot', to: '/mcp/v1', title: t('home.devMcpHint') },
])

const supporters = computed(() => [
  { key: 'jetbrains', name: 'JetBrains', icon: 'i-simple-icons-jetbrains', to: 'https://jb.gg/OpenSourceSupport', detail: t('home.supportedByJetbrains') },
  { key: 'anthropic', name: 'Anthropic', icon: 'i-simple-icons-anthropic', to: 'https://www.anthropic.com/', detail: t('home.supportedByAnthropic') },
])

// what kinds of data the networks behind those providers serve: the map shows three of them, the explorer all
const dataKinds = computed(() => [
  { key: 'observations', icon: 'i-lucide-thermometer', title: t('home.kindObservationsTitle') },
  { key: 'forecasts', icon: 'i-lucide-cloud-sun', title: t('home.kindForecastsTitle') },
  { key: 'hydrology', icon: 'i-lucide-waves', title: t('home.kindHydrologyTitle') },
  { key: 'radar', icon: 'i-lucide-radar', title: t('home.kindRadarTitle') },
  { key: 'alerts', icon: 'i-lucide-triangle-alert', title: t('home.kindAlertsTitle') },
  { key: 'road', icon: 'i-lucide-car-front', title: t('home.kindRoadTitle') },
])

// what the project stands for, as the footer shows it in icons and the about page in full
const values = computed(() => [
  { key: 'lgbtq', emoji: '🏳️‍🌈🏳️‍⚧️', text: t('values.lgbtq') },
  { key: 'antifascist', emoji: '✊', text: t('values.antifascist') },
  { key: 'climate', emoji: '🌡️', text: t('values.climate') },
  { key: 'openData', emoji: '🔓', text: t('values.openData') },
])

const mapLabel = computed(() => t('atlas.mapLabel'))
</script>

<template>
  <div class="atlas">
    <!-- The panel: on a wide screen beside the map, on a phone a sheet under it that the page scrolls up over it -->
    <section ref="panel" class="atlas-panel" aria-labelledby="atlas-title">
      <div class="atlas-grip" aria-hidden="true" />

      <header class="atlas-panel-head">
        <h1 id="atlas-title" class="text-xl font-bold text-highlighted leading-tight">
          Wetterdienst
        </h1>
        <p class="text-sm text-muted">
          {{ t('home.tagline') }}
        </p>
      </header>

      <!-- announced when a station is picked, by the map or the list -->
      <p class="sr-only" aria-live="polite">
        {{ announcement }}
      </p>

      <!-- a station or a place picked: what there is to see of it -->
      <div v-if="selected" class="atlas-detail">
        <UButton
          :label="t('atlas.back')"
          icon="i-lucide-arrow-left"
          color="neutral"
          variant="ghost"
          size="sm"
          class="-ml-2 self-start"
          @click="back"
        />
        <div>
          <h2 ref="detailHeading" tabindex="-1" class="text-2xl font-bold text-highlighted leading-tight break-words focus:outline-none">
            {{ selected.name ?? selected.station_id }}
          </h2>
          <p class="mt-1 text-sm text-muted tabular">
            {{ t('stripes.station') }} {{ selected.station_id }}<template v-if="selected.region">
              · {{ selected.region }}
            </template><template v-if="selected.elevation != null">
              · {{ t('atlas.elevation', { value: Math.round(selected.elevation) }) }}
            </template>
          </p>
          <p class="text-sm text-muted tabular">
            {{ formatPosition(selected.latitude, selected.longitude, locale) }}
          </p>
          <p v-if="place" class="mt-2 inline-flex items-center gap-1.5 text-sm text-toned">
            <UIcon name="i-lucide-map-pin" class="size-4 shrink-0" />
            {{ t('atlas.pickedPlace', { distance: formatDistance(distanceKm(place, selected), locale) }) }}
          </p>
        </div>

        <!-- the forecast, at the nearest forecast point -->
        <section class="atlas-card" aria-labelledby="atlas-forecast">
          <div class="atlas-card-head">
            <UIcon name="i-lucide-cloud-sun" class="atlas-card-icon" />
            <h3 id="atlas-forecast" class="atlas-card-title">
              {{ t('atlas.layerForecast') }}
            </h3>
          </div>
          <template v-if="forecastPoint">
            <p v-if="forecastPoint.distance > 0" class="atlas-card-note">
              {{ t('atlas.at', { name: forecastPoint.station.name ?? forecastPoint.station.station_id, distance: formatDistance(forecastPoint.distance, locale) }) }}
            </p>
            <AtlasForecast :station="forecastPoint.station" />
            <UButton :to="forecastLink(forecastPoint.station.station_id)" :label="t('atlas.openForecast')" trailing-icon="i-lucide-arrow-right" variant="link" class="px-0" />
          </template>
          <p v-else-if="status('forecast') === 'pending'" class="atlas-card-note">
            {{ t('common.loading') }}
          </p>
          <p v-else class="atlas-card-note">
            {{ t('atlas.noneNearby', { distance: formatDistance(REACH_KM, locale) }) }}
          </p>
        </section>

        <!-- the climate stripes, at the nearest station that has them -->
        <section class="atlas-card" aria-labelledby="atlas-stripes">
          <div class="atlas-card-head">
            <UIcon name="i-lucide-chart-column-big" class="atlas-card-icon" />
            <h3 id="atlas-stripes" class="atlas-card-title">
              {{ t('atlas.layerStripes') }}
            </h3>
          </div>
          <template v-if="stripesPoint">
            <p v-if="stripesPoint.distance > 0" class="atlas-card-note">
              {{ t('atlas.at', { name: stripesPoint.station.name ?? stripesPoint.station.station_id, distance: formatDistance(stripesPoint.distance, locale) }) }}
            </p>
            <AtlasStripes :station-id="stripesPoint.station.station_id" :station-name="stripesPoint.station.name ?? stripesPoint.station.station_id" />
            <UButton :to="stripesLink(stripesPoint.station.station_id)" :label="t('atlas.openStripes')" trailing-icon="i-lucide-arrow-right" variant="link" class="px-0" />
          </template>
          <p v-else-if="status('stripes') === 'pending'" class="atlas-card-note">
            {{ t('common.loading') }}
          </p>
          <p v-else class="atlas-card-note">
            {{ t('atlas.noneNearby', { distance: formatDistance(REACH_KM, locale) }) }}
          </p>
        </section>

        <!-- the measurements and the history, at the nearest station of the source chosen in the filters -->
        <section class="atlas-card" aria-labelledby="atlas-measured">
          <div class="atlas-card-head">
            <UIcon name="i-lucide-thermometer" class="atlas-card-icon" />
            <h3 id="atlas-measured" class="atlas-card-title">
              {{ t('atlas.layerMeasured') }}
            </h3>
          </div>
          <template v-if="measuredPoint">
            <p class="atlas-card-note">
              {{ sourceLabel }}<template v-if="sinceYear(measuredPoint.station)">
                · {{ t('atlas.since', { year: sinceYear(measuredPoint.station) }) }}
              </template>
            </p>
            <p v-if="measuredPoint.distance > 0" class="atlas-card-note">
              {{ t('atlas.at', { name: measuredPoint.station.name ?? measuredPoint.station.station_id, distance: formatDistance(measuredPoint.distance, locale) }) }}
            </p>
            <div class="flex flex-col items-start">
              <UButton :to="measurementsLink(source, measuredPoint.station.station_id)" :label="t('atlas.openExplorer')" trailing-icon="i-lucide-arrow-right" variant="link" class="px-0" />
              <UButton v-if="historyLink(source, measuredPoint.station.station_id)" :to="historyLink(source, measuredPoint.station.station_id)!" :label="t('atlas.openHistory')" trailing-icon="i-lucide-arrow-right" variant="link" class="px-0" />
            </div>
          </template>
          <p v-else-if="status('measured') === 'pending'" class="atlas-card-note">
            {{ t('common.loading') }}
          </p>
          <p v-else class="atlas-card-note">
            {{ t('atlas.noneNearby', { distance: formatDistance(REACH_KM, locale) }) }}
          </p>
        </section>
      </div>

      <!-- nothing picked: find a station, or take one near the centre of the map -->
      <div v-else class="atlas-browse">
        <div>
          <UInput
            id="atlas-search"
            v-model="search"
            :aria-label="t('atlas.search')"
            type="search"
            icon="i-lucide-search"
            size="lg"
            :placeholder="t('atlas.searchPlaceholder')"
            class="w-full"
            autocomplete="off"
          />
        </div>

        <div>
          <h2 class="atlas-list-title">
            {{ searching ? t('atlas.results') : t('atlas.nearCentre') }}
          </h2>
          <p v-if="listStatus === 'pending'" class="text-sm text-muted" role="status">
            {{ t('atlas.loadingStations') }}
          </p>
          <p v-else-if="searching && !found.length" class="text-sm text-muted">
            {{ t('atlas.noResults', { query: search.trim() }) }}
          </p>
          <ul v-else class="atlas-list">
            <li v-for="entry in (searching ? found.map(station => ({ station, distance: null })) : near)" :key="entry.station.station_id">
              <button type="button" class="atlas-list-item" :data-station-id="entry.station.station_id" @click="choose(entry.station, { focus: true })">
                <span class="min-w-0">
                  <span class="block font-semibold text-highlighted break-words">{{ entry.station.name ?? entry.station.station_id }}</span>
                  <span class="block text-xs text-muted tabular">{{ entry.station.station_id }}<template v-if="entry.station.region"> · {{ entry.station.region }}</template></span>
                </span>
                <span v-if="entry.distance !== null" class="shrink-0 text-xs text-muted tabular">{{ formatDistance(entry.distance, locale) }}</span>
              </button>
            </li>
          </ul>
          <!-- a click on the map, by keyboard: the place at the centre of the map, which the arrow keys move -->
          <UButton
            v-if="!searching && stations.length"
            :label="t('atlas.pickCentre')"
            icon="i-lucide-crosshair"
            color="neutral"
            variant="ghost"
            size="sm"
            class="mt-1 -ml-2"
            @click="pickCentre"
          />
        </div>

        <!-- what the data is, who publishes it, and the other ways to it -->
        <div class="atlas-about">
          <div>
            <h2 class="atlas-list-title">
              {{ t('home.dataTitle') }}
            </h2>
            <p class="text-sm text-toned">
              {{ t('home.dataIntro') }}
            </p>
          </div>
          <dl class="atlas-stats">
            <div v-for="stat in stats" :key="stat.key">
              <dt class="text-xs text-muted">
                {{ stat.label }}
              </dt>
              <dd class="text-lg font-bold text-highlighted tabular">
                <span v-if="stat.value === null && providersLoading" class="inline-block h-6 w-8 rounded bg-elevated animate-pulse align-middle" aria-hidden="true" />
                <template v-else>
                  {{ stat.value ?? '–' }}
                </template>
              </dd>
            </div>
          </dl>
          <ul class="atlas-kinds">
            <li v-for="kind in dataKinds" :key="kind.key">
              <UIcon :name="kind.icon" class="size-4 shrink-0 atlas-card-icon" />
              {{ kind.title }}
            </li>
          </ul>

          <div data-testid="home-providers-card">
            <h3 class="mb-2 text-sm font-semibold text-highlighted">
              {{ t('home.dataProvidersTitle') }}
            </h3>
            <UAlert
              v-if="providersFailure"
              color="error"
              variant="subtle"
              icon="i-lucide-alert-circle"
              :title="t('common.requestFailed')"
              :description="providersFailure"
              :actions="[{ label: t('common.retry'), onClick: () => refreshProviders() }]"
            />
            <div v-else-if="providersLoading" class="flex flex-wrap gap-1.5" role="status" :aria-label="t('common.loading')" aria-busy="true">
              <div v-for="(width, index) in placeholders" :key="index" class="h-7 rounded-full bg-elevated animate-pulse" :class="width" aria-hidden="true" />
            </div>
            <p v-else-if="!providers.length" class="text-sm text-muted">
              {{ t('home.providersEmpty') }}
            </p>
            <ul v-else class="flex flex-wrap gap-1.5" data-testid="home-providers">
              <li v-for="provider in providers" :key="provider.key">
                <NuxtLink :to="`/providers/${provider.key}`" class="atlas-chip">
                  <span aria-hidden="true">{{ provider.flag }}</span>
                  {{ provider.name }}
                </NuxtLink>
              </li>
            </ul>
            <p class="mt-3 text-sm text-muted">
              {{ t('home.dataProvidersDesc') }}
            </p>
            <ul class="mt-2 space-y-1 text-sm">
              <li>
                <NuxtLink to="/providers" class="atlas-link">
                  {{ t('home.providersLink') }}
                </NuxtLink>
              </li>
              <li>
                <NuxtLink to="/glossary" class="atlas-link">
                  {{ t('home.glossaryHint') }}
                </NuxtLink>
              </li>
            </ul>
          </div>

          <div>
            <h3 class="mb-1 text-sm font-semibold text-highlighted">
              {{ t('home.devTitle') }}
            </h3>
            <p class="mb-2 text-sm text-muted">
              {{ t('home.devText') }}
            </p>
            <ul class="flex flex-wrap gap-1.5">
              <li v-for="entry in devEntries" :key="entry.key">
                <NuxtLink :to="entry.to" external target="_blank" :title="entry.title" class="atlas-chip">
                  <UIcon :name="entry.icon" class="size-4 shrink-0" />
                  {{ entry.label }}
                </NuxtLink>
              </li>
            </ul>
          </div>

          <div>
            <h3 class="mb-2 text-sm font-semibold text-highlighted">
              {{ t('home.supportedByTitle') }}
            </h3>
            <ul class="flex flex-wrap gap-1.5">
              <li v-for="supporter in supporters" :key="supporter.key">
                <a :href="supporter.to" target="_blank" :title="supporter.detail" :aria-label="`${supporter.name} — ${supporter.detail}`" class="atlas-chip">
                  <UIcon :name="supporter.icon" class="size-4 shrink-0" />
                  {{ supporter.name }}
                </a>
              </li>
            </ul>
          </div>

          <!-- what the project stands for closes the panel, as it closed the home page before the map -->
          <div>
            <h3 class="mb-2 text-sm font-semibold text-highlighted">
              {{ t('values.title') }}
            </h3>
            <ul class="space-y-1 text-sm text-toned">
              <li v-for="value in values" :key="value.key" class="flex items-start gap-2">
                <span aria-hidden="true">{{ value.emoji }}</span>
                {{ value.text }}
              </li>
            </ul>
          </div>

          <NuxtLink to="/about" class="atlas-link text-sm">
            {{ t('home.aboutLink') }}
          </NuxtLink>
        </div>
      </div>
    </section>

    <!-- The map and the filters over it -->
    <div class="atlas-stage" @focusin="onStageFocus">
      <div class="atlas-filters">
        <div class="atlas-filters-row">
          <div class="atlas-segments" role="group" :aria-label="t('atlas.layers')">
            <button
              v-for="option in layerItems"
              :key="option.value"
              type="button"
              class="atlas-segment"
              :aria-pressed="layer === option.value"
              @click="layer = option.value"
            >
              <UIcon :name="option.icon" class="size-4 shrink-0" />
              {{ option.label }}
            </button>
          </div>
          <template v-if="layer === 'measured'">
            <USelect v-model="providerChoice" :items="providerItems" :aria-label="t('parameterSelection.providerLabel')" size="sm" class="atlas-select" />
            <USelect v-model="resolutionChoice" :items="resolutionItems" :aria-label="t('parameterSelection.resolutionLabel')" size="sm" class="atlas-select" />
            <USelect v-model="datasetChoice" :items="datasetItems" :aria-label="t('parameterSelection.datasetLabel')" size="sm" class="atlas-select" />
          </template>
          <span v-if="listStatus === 'success'" class="atlas-status tabular">{{ countLabel }}</span>
          <span v-else-if="listStatus === 'pending'" class="atlas-status" role="status">
            <UIcon name="i-lucide-loader-circle" class="size-4 motion-safe:animate-spin" />
            {{ t('atlas.loadingStations') }}
          </span>
        </div>
        <UAlert
          v-if="listStatus === 'error'"
          class="atlas-failure"
          color="error"
          variant="outline"
          icon="i-lucide-alert-circle"
          :title="t('atlas.stationsFailed')"
          :description="listFailure"
          :actions="[{ label: t('common.retry'), onClick: () => current.ensure(true) }]"
        />
      </div>

      <ClientOnly>
        <AtlasMap
          :stations="stations"
          :selected="selected"
          :place="place"
          :label="mapLabel"
          @pick="onPick"
          @view="view = $event"
        />
      </ClientOnly>
    </div>
  </div>
</template>

<style>
/* ---- the frame: a sheet under the map on a phone, a panel beside it on a wide screen ---- */
.atlas {
  --atlas-peek: 9.5rem;
  position: relative;
  display: flex;
  flex-direction: column;
}
.atlas-stage {
  order: -1;
  position: sticky;
  top: var(--ui-header-height);
  z-index: 0;
  isolation: isolate;
  height: calc(100dvh - var(--ui-header-height) - var(--atlas-peek));
  min-height: 16rem;
}
.atlas-panel {
  position: relative;
  z-index: 1;
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
  margin-top: -1.25rem;
  min-height: calc(100dvh - var(--ui-header-height) - 3rem);
  padding: 0.5rem 1rem 2rem;
  background: var(--ui-bg);
  border-top: 1px solid var(--ui-border);
  border-radius: 1.25rem 1.25rem 0 0;
  box-shadow: 0 -6px 24px rgb(15 23 42 / 0.1);
}
.atlas-grip {
  align-self: center;
  width: 2.5rem;
  height: 0.3125rem;
  border-radius: 999px;
  background: var(--ui-border-accented);
}
@media (min-width: 1024px) {
  .atlas {
    display: block;
    height: calc(100dvh - var(--ui-header-height) - var(--app-footer-height));
    min-height: 28rem;
  }
  .atlas-stage {
    position: absolute;
    inset: 0;
    height: auto;
  }
  .atlas-panel {
    position: absolute;
    top: 0.75rem;
    bottom: 0.75rem;
    left: 0.75rem;
    width: 25rem;
    min-height: 0;
    margin: 0;
    padding: 1.25rem 1.25rem 1.5rem;
    overflow-y: auto;
    overscroll-behavior: contain;
    border: 1px solid var(--ui-border);
    border-radius: 1rem;
    box-shadow: 0 8px 30px rgb(15 23 42 / 0.12);
  }
  .atlas-grip {
    display: none;
  }
}
.dark .atlas-panel {
  background: var(--ui-color-neutral-900);
  box-shadow: 0 8px 30px rgb(0 0 0 / 0.4);
}

.atlas-panel-head {
  display: flex;
  flex-direction: column;
  gap: 0.125rem;
}
.atlas-detail,
.atlas-browse {
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
}

/* ---- the lists ---- */
.atlas-list-title {
  margin-bottom: 0.375rem;
  color: var(--ui-text-muted);
  font-size: 0.8125rem;
  font-weight: 600;
  letter-spacing: 0.02em;
}
.atlas-list {
  display: flex;
  flex-direction: column;
  margin-inline: -0.5rem;
}
.atlas-list-item {
  display: flex;
  width: 100%;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
  min-height: 2.75rem;
  padding: 0.5rem;
  border-radius: calc(var(--ui-radius) * 1.5);
  text-align: start;
  cursor: pointer;
}
.atlas-list-item:hover {
  background: var(--ui-bg-elevated);
}
.atlas-about {
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
  padding-top: 1.25rem;
  border-top: 1px solid var(--ui-border);
}
.atlas-stats {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0.75rem 1rem;
}
.atlas-stats dd {
  margin: 0;
}
.atlas-kinds {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(9.5rem, 1fr));
  gap: 0.5rem 1rem;
  color: var(--ui-text-toned);
  font-size: 0.875rem;
}
.atlas-kinds li {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}
.atlas-chip {
  display: inline-flex;
  align-items: center;
  gap: 0.375rem;
  min-height: 1.75rem;
  padding: 0.125rem 0.625rem;
  border: 1px solid var(--ui-border-accented);
  border-radius: 999px;
  color: var(--ui-text);
  font-size: 0.8125rem;
}
.atlas-chip:hover {
  border-color: var(--ui-color-primary-700);
  color: var(--ui-color-primary-800);
}
.dark .atlas-chip:hover {
  border-color: var(--ui-color-primary-400);
  color: var(--ui-color-primary-300);
}
.atlas-link {
  color: var(--ui-color-primary-700);
  text-decoration: underline;
  text-underline-offset: 0.2em;
}
.atlas-link:hover {
  color: var(--ui-color-primary-800);
  text-decoration-thickness: 2px;
}
.dark .atlas-link {
  color: var(--ui-color-primary-300);
}
.dark .atlas-link:hover {
  color: var(--ui-color-primary-200);
}

/* ---- the cards of a station ---- */
.atlas-card {
  display: flex;
  flex-direction: column;
  gap: 0.625rem;
  padding-top: 1rem;
  border-top: 1px solid var(--ui-border);
}
.atlas-card-head {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}
.atlas-card-icon {
  width: 1.125rem;
  height: 1.125rem;
  color: var(--ui-color-primary-600);
}
.dark .atlas-card-icon {
  color: var(--ui-color-primary-400);
}
.atlas-card-title {
  color: var(--ui-text-highlighted);
  font-size: 1rem;
  font-weight: 700;
}
.atlas-card-note {
  color: var(--ui-text-muted);
  font-size: 0.875rem;
}

/* ---- the filters over the map ---- */
.atlas-filters {
  position: absolute;
  z-index: 1000;
  top: 0.75rem;
  left: 0;
  right: 0;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  pointer-events: none;
}
.atlas-filters > * {
  pointer-events: auto;
}
.atlas-filters-row {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  /* a row that scrolls in its own box on a narrow screen rather than widen the page (WCAG 1.4.10) */
  overflow-x: auto;
  padding: 0.25rem 0.75rem;
  scrollbar-width: none;
}
.atlas-failure {
  margin-inline: 0.75rem;
  max-width: 28rem;
}
@media (min-width: 1024px) {
  .atlas-filters {
    left: 26.5rem;
    right: 0.75rem;
  }
  .atlas-filters-row {
    flex-wrap: wrap;
    overflow-x: visible;
    padding: 0;
  }
  .atlas-failure {
    margin-inline: 0;
  }
}
.atlas-segments {
  display: inline-flex;
  flex-shrink: 0;
  padding: 0.1875rem;
  gap: 0.125rem;
  background: var(--ui-bg);
  border: 1px solid var(--ui-border-accented);
  border-radius: 999px;
  box-shadow: 0 1px 4px rgb(15 23 42 / 0.12);
}
.atlas-segment {
  display: inline-flex;
  align-items: center;
  gap: 0.375rem;
  min-height: 2.25rem;
  padding: 0.25rem 0.875rem;
  border-radius: 999px;
  color: var(--ui-text-toned);
  font-size: 0.875rem;
  font-weight: 600;
  white-space: nowrap;
  cursor: pointer;
}
.atlas-segment:hover {
  color: var(--ui-text-highlighted);
  background: var(--ui-bg-elevated);
}
.atlas-segment[aria-pressed="true"] {
  background: var(--color-navy);
  color: #ffffff;
}
.dark .atlas-segment[aria-pressed="true"] {
  background: var(--ui-color-primary-300);
  color: #0f172b;
}
@media (forced-colors: active) {
  .atlas-segment[aria-pressed="true"] {
    forced-color-adjust: none;
    background: Highlight;
    color: HighlightText;
  }
  .atlas-segment[aria-pressed="true"] .iconify {
    background-color: HighlightText !important;
  }
}
.atlas-select {
  flex-shrink: 0;
  min-width: 7rem;
  max-width: 16rem;
  border-radius: 999px;
  box-shadow: 0 1px 4px rgb(15 23 42 / 0.12);
}
.atlas-status {
  display: inline-flex;
  flex-shrink: 0;
  align-items: center;
  gap: 0.375rem;
  min-height: 2rem;
  padding: 0.25rem 0.75rem;
  background: var(--ui-bg);
  border: 1px solid var(--ui-border);
  border-radius: 999px;
  color: var(--ui-text-toned);
  font-size: 0.8125rem;
  white-space: nowrap;
  box-shadow: 0 1px 4px rgb(15 23 42 / 0.12);
}

@media print {
  .atlas,
  .atlas-stage,
  .atlas-panel {
    position: static !important;
    height: auto !important;
    min-height: 0 !important;
    overflow: visible !important;
    box-shadow: none !important;
    border: 0 !important;
    margin: 0 !important;
  }
  .atlas-stage {
    height: 60vh !important;
    break-inside: avoid;
  }
  .atlas-filters,
  .atlas-grip {
    display: none !important;
  }
}
</style>
