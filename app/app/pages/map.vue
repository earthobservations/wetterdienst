<script setup lang="ts">
import type { ProviderNetworkCoverageResponse, Station } from '#shared/types/api'
import type { GhcnStationColumns } from '#shared/types/ghcn-stations'
import type { CloserStation, MapLayer, MapState, MeasuredSource, PickedStation, PlacedStation, PlaceOrigin, Point, ReportingRule } from '~/utils/map-tool'
import { defineAsyncComponent } from 'vue'
import MapForecast from '~/components/MapForecast.vue'
import MapLayers from '~/components/MapLayers.vue'
import MapStationsNotLoaded from '~/components/MapStationsNotLoaded.vue'
import MapStripes from '~/components/MapStripes.vue'
import UseMyLocation from '~/components/UseMyLocation.vue'
import { describeFetchError } from '~/utils/api-error'
import { formatNumber } from '~/utils/format'
import { GHCN_STATIONS_ROUTE, stationsOfColumns } from '~/utils/ghcn-stations'
import { GROUPING_COMPULSORY_ABOVE, groupingFor, isGroupedAt } from '~/utils/map-cluster'
import {
  closerStoppedStation,
  DEFAULT_MEASURED,
  distanceKm,
  findSameStation,
  FORECAST_STATIONS_QUERY,
  forecastLink,
  formatDistance,
  formatPosition,
  GHCN_NETWORK,
  GHCN_SOURCE,
  GHCN_STATIONS_QUERY,
  ghcnReportingRule,
  historyLink,
  HOME_VIEW,
  MEASURED_NETWORK,
  measurementsLink,
  nearestStations,
  placed,
  pointFromQuery,
  prepareSearch,
  REACH_KM,
  reportingRule,
  SAME_PLACE_KM,
  searchFromQuery,
  searchStationsCounted,
  stateFromQuery,
  stateToQuery,
  stationAt,
  stationFor,
  STRIPES_KIND,
  stripesLink,
  wmoNumber,
  yearOf,
} from '~/utils/map-tool'
import { fetchStripesStations, stripesFetch } from '~/utils/stripes-source'
import { drawn, drawnOf, inWarningBox, withoutOutline } from '~/utils/warnings'

// The map tool (GH-3650), from the design of #3580: the stations of the layer chosen in the panel of the layers button over the map, and a
// panel beside it (a sheet under it on a phone) that finds a station by name, lists the ones near the centre of the
// map and, for the station or the place picked, shows its forecast, its climate stripes, its measurements and its
// history, each at the nearest station that has them. Three layers: the forecast's points (DWD MOSMIX), the stations
// that measure (DWD's observations, by resolution and dataset) and NOAA's GHCN daily (GH-4078), whose 133,041 stations
// worldwide are loaded once, as the other layers' are, from a compact list of the app's server (GH-4267: 2 MB, where the
// backend's own is 44 MB), and grouped at every zoom. A station of GHCN daily has its own climate stripes and measurements (its
// panel's cards are about it, not about the nearest DWD station), the nearest forecast point as any station has, and no history,
// which is DWD's alone.
//
// The station the tool picks for a place is the nearest one within 100 km, a station that is still reporting before one
// that has stopped (`reportingRule`: against the newest end of its own list), and the one under a click on its dot is
// that station, whatever it is. A change of
// layer or dataset picks again by the WMO number of the station where it has one and one station of the new list has
// the same (GH-4077), else by the position of the place, never by the id of the station, which is another station in
// another layer.
//
// What is shown is in the address (`?layer=&resolution=&dataset=&station=&lat=&lon=`), so that a link opens the same
// map, and so that the search of the header opens it on a station (`/map?station=10147`) or at a position the reader typed
// (`/map?lat=52.5200&lon=13.4000`, GH-3790): a position with no station is picked as a click on the map would pick it, once the
// stations are there, and the map is moved to it.

// the map fills the window between the bars, and both stay where they are on it (GH-4226, `useBarsHideOnScroll`)
definePageMeta({ barsHide: false })

const { t } = useI18n()
const creditLine = useCreditLine()
const formatLanguage = useFormatLanguage()
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
// the narrow layout (the tab bar's breakpoint, GH-4227): the map fills the screen between the bars and the page runs edge to edge
const phone = usePhone()
const parts = computed(() => wide.value ? ['panel', 'stage'] as const : ['stage', 'panel'] as const)
const reducedMotion = useMediaQuery('(prefers-reduced-motion: reduce)')

// ---- what the map shows, from the address ---------------------------------------------------------------------

const initial = stateFromQuery(route.query)
const layer = ref<MapLayer>(initial.layer)
const source = ref<MeasuredSource>(initial.source)
const selectedId = ref<string | null>(initial.stationId)
/** The point the panel is about: the station picked, or the place picked on the map */
const anchor = ref<Point | null>(initial.place)
/**
 * Where the place came from, which the panel says: a click, the centre of the map, or the position of a station the
 * reader chose. A place that the address brings (a link, a reload, the browser's Back) is of no known origin, and is
 * not told as a click.
 */
const origin = ref<PlaceOrigin>({ kind: 'unknown' })
const POINT: PlaceOrigin = { kind: 'point' }

const keyOf = (shown: MapLayer, from: MeasuredSource) => shown === 'measured' ? `measured/${from.resolution}/${from.dataset}` : shown
/** The view shown: the number of a station is a number in the list of one view, and no other's */
const viewKey = computed(() => keyOf(layer.value, source.value))
/** The view the station picked was picked in */
let pickedIn = viewKey.value
/**
 * The station picked, as it is found again in another layer (GH-4077): by its WMO number, and by its id where both layers are
 * DWD's observations. Kept through a change of layer that has no station near, so that the next layer that has the station
 * finds it again. Cleared by Back, by a click or the centre of the map that finds no station (the reader's pick is then a
 * place with none), and by an address that names another pick; replaced by any pick.
 */
let picked: PickedStation | null = null
/** The WMO number the station of the layer shown was found by, from the layer before: told in the panel */
const sameStation = ref<string | null>(null)

// ---- the lists of stations ------------------------------------------------------------------------------------

const forecast = useStationList(() => 'forecast', async () =>
  (await $fetch<{ stations: Station[] }>('/api/stations', { query: FORECAST_STATIONS_QUERY, ...API_FETCH })).stations ?? [])
// the stations that have climate stripes, which the panel asks the nearest of; no layer of the map
const stripes = useStationList(() => STRIPES_KIND, async () =>
  (await fetchStripesStations(stripesFetch, 'dwd', STRIPES_KIND))
    .map(station => ({ ...station, elevation: station.elevation ?? null })))
const measured = useStationList(() => `${source.value.resolution}/${source.value.dataset}`, async () =>
  (await $fetch<{ stations: Station[] }>('/api/stations', {
    query: { ...MEASURED_NETWORK, parameters: `${source.value.resolution}/${source.value.dataset}`, all: 'true' },
    ...API_FETCH,
  })).stations ?? [])

// GHCN daily: all 133k stations, from the app's server as columns (`stationsOfColumns` makes the stations of them)
// (its names are folded once the list is there, so that a keystroke of the search does not fold 133k of them)
const ghcn = useStationList(() => 'ghcn', async () =>
  stationsOfColumns(await $fetch<GhcnStationColumns>(GHCN_STATIONS_ROUTE, API_FETCH)), prepareSearch)

const lists = { forecast, measured, ghcn }
const current = computed(() => lists[layer.value])
const stations = computed(() => current.value.stations.value)
const listStatus = computed(() => current.value.status.value)
const listFailure = computed(() => current.value.error.value ? describeFetchError(current.value.error.value) : '')

const sourceKey = computed(() => `${source.value.resolution}/${source.value.dataset}`)

// ---- the layers ------------------------------------------------------------------------------------------------

const layerItems = computed(() => [
  { value: 'forecast' as const, label: t('mapTool.layerForecast'), icon: 'i-ph-sun' },
  { value: 'measured' as const, label: t('mapTool.layerMeasured'), icon: 'i-ph-thermometer-simple' },
  { value: 'ghcn' as const, label: t('mapTool.layerGhcn'), icon: 'i-ph-globe-hemisphere-west' },
])
/** Whether the panel of the layers button is open */
const layersOpen = ref(false)
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
      // the panel then offers the one source shown, which still works
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
  if (layer.value === 'ghcn')
    return ghcn.ensure(true)
  return forecast.ensure(true)
}

/** Asks for the list of the layer shown */
async function ensureCurrent() {
  if (layer.value === 'measured')
    return ensureMeasured()
  if (layer.value === 'ghcn')
    return ghcn.ensure()
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
// the search of the panel starts on the text the address brings (`?q=`, GH-3790: the "more" of the header's search leads here)
const search = ref(searchFromQuery(route.query))
/** How many of the stations that answer the search the panel lists */
const SEARCH_SHOWN = 20
const searching = computed(() => search.value.trim().length > 0)
const near = computed(() => nearestStations(stations.value, view.value, 8).map(entry => ({ ...entry, distance: entry.distance as number | null })))
const searched = computed(() => searchStationsCounted(stations.value, search.value, SEARCH_SHOWN))
const found = computed(() => searched.value.stations.map(station => ({ station, distance: null as number | null })))
const entries = computed(() => searching.value ? found.value : near.value)
const countLabel = computed(() => t('mapTool.count', { count: stations.value.length, shown: formatNumber(stations.value.length, formatLanguage.value, 0) }))
const mapLabel = computed(() => t('mapTool.mapLabel', { layer: layerLabel.value }))

// ---- the groups of stations at the outer zooms (GH-4079) ----------------------------------------------------------

// Whether the stations are grouped is the reader's choice (the switch in the panel of the layers button: one grouping, on by
// default, the radius of a group and the zoom from which every station is its own dot), except on a layer of more than
// `GROUPING_COMPULSORY_ABOVE` stations, which is always grouped: there the switch is on, disabled, and says why
const groupingWanted = ref(true)
const groupingInForce = computed(() => groupingFor(groupingWanted.value, stations.value.length))
const grouped = computed({
  get: () => groupingInForce.value.on,
  set: (on: boolean) => {
    groupingWanted.value = on
  },
})
const groupingCompulsoryText = computed(() => t('mapTool.groupingCompulsory', { shown: formatNumber(GROUPING_COMPULSORY_ABOVE, formatLanguage.value, 0) }))
/** Whether the stations are grouped at the zoom the map is at, which the legend (in the layers panel) says */
const groupedNow = computed(() => isGroupedAt(groupingInForce.value.grouping, view.value.zoom))

// ---- the station picked ---------------------------------------------------------------------------------------

/**
 * What the list of GHCN daily does not carry of the station picked (its elevation and its region, which the panel says), asked for by
 * its id. The list has its name, its place, its years and its WMO number (the forecast's same station goes by it), so the panel
 * and the cards are there at once; a request that fails leaves the panel without them.
 */
const ghcnDetails = shallowRef<PlacedStation | null>(null)
const selected = computed<PlacedStation | null>(() => {
  const station = selectedId.value ? stations.value.find(found => found.station_id === selectedId.value) ?? null : null
  const details = ghcnDetails.value
  if (!station || layer.value !== 'ghcn' || details?.station_id !== station.station_id)
    return station
  return { ...station, region: details.region, elevation: details.elevation }
})
/** The place picked on the map, where it is not the station itself (more than half a kilometre from it) */
const place = computed(() => anchor.value && selected.value && distanceKm(anchor.value, selected.value) > SAME_PLACE_KM ? anchor.value : null)
// ---- DWD's weather warnings (GH-4295) ---------------------------------------------------------------------------

// A layer over the stations, switched by the chip over the map (`?warnings=1` in the address): the outlines of the warnings in force or announced,
// drawn under the dots, and in the panel their list (the keyboard's way to a warning) and, for the station or place picked, the banner of the
// warnings whose polygon contains it. The snapshot is asked for while the layer is on, or a station is picked (the banner is there with the layer
// off as well), and every 5 minutes after. A warning DWD gives by area name alone has no polygon: it is listed apart and never drawn.
const warningsOn = ref(route.query.warnings === '1')
/** The place the banner is about: the place picked on the map where there is one, else the station's position */
const bannerPoint = computed<Point | null>(() => anchor.value ?? (selected.value ? { latitude: selected.value.latitude, longitude: selected.value.longitude } : null))
// the snapshot is asked for while the layer is on, or for a place picked that DWD warns for: nothing is asked for a place outside Germany
const warnings = useWarnings(() => warningsOn.value || (bannerPoint.value !== null && inWarningBox(bannerPoint.value)))
/** The warning opened in the list, which the map draws stronger */
const focusedWarning = ref<string | null>(null)
/** A warning opened in the list: the map moves to show it, once for each press */
const showWarning = ref<{ count: number, bounds: { south: number, west: number, north: number, east: number } } | null>(null)
let warningPresses = 0
function onWarningFocus(id: string | null) {
  focusedWarning.value = id
  const box = id ? warnings.snapshot.value?.warnings.find(warning => warning.id === id)?.box : null
  if (box)
    showWarning.value = { count: ++warningPresses, bounds: box }
}
const warningsDrawn = computed(() => warningsOn.value && warnings.snapshot.value
  ? drawnOf(drawn(warnings.snapshot.value.warnings, warnings.now.value), focusedWarning.value)
  : undefined)
/** The outlines and the list are about the snapshot in hand: none to count while it has not come */
const warningsCount = computed(() => warnings.snapshot.value ? drawn(warnings.snapshot.value.warnings, warnings.now.value).length + withoutOutline(warnings.snapshot.value.warnings, warnings.now.value).length : null)
const warningsChipLabel = computed(() => warningsOn.value && warningsCount.value !== null ? t('warnings.chipCount', { count: warningsCount.value }) : t('warnings.chip'))
/** The credit line of the outlines in the map's attribution, while they are drawn */
const warningsCredit = computed(() => {
  const credit = warningsOn.value ? warnings.snapshot.value?.credit : null
  return credit?.attribution ? [{ text: creditLine(credit.attribution), license: credit.license ? { label: credit.license.spdx ?? credit.license.name, url: credit.license.url } : null }] : []
})
watch(warningsOn, (on) => {
  if (!on)
    focusedWarning.value = null
})
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
/** The position was forgotten from the station card: the control that had the focus is gone, the card's heading takes it */
function focusDetailHeading() {
  void nextTick(() => detailHeading.value?.focus())
}
function setPanel(element: unknown) {
  panel.value = element as HTMLElement | null
}
const announcement = ref('')

// ---- the full screen of the map (GH-4227) -----------------------------------------------------------------------

// The stage (the map, the layers button and the chips) goes full screen by the browser's API where it has one,
// and covers the page itself where it has not (iPhone Safari) or the browser refuses: `useElementFullscreen` is the state
// machine, the element is never moved, so the map keeps its view, its layer and the station picked. The panel is out of
// reach while it lasts (hidden by the browser, or inert), so a sheet at the foot of the stage stands in for it: the station
// picked, "Pick the centre of the map" (a keyboard's way to a place) and "Show details", which leaves full screen and
// puts the focus on the panel's heading. The focus goes into the map on entering and back to the button on leaving.
const screen = ref<HTMLElement | null>(null)
function setScreen(element: unknown) {
  screen.value = element as HTMLElement | null
}
/** What the map component gives of itself: where the focus goes (its ref is the async component's, set by a function since the page's parts are in a loop) */
interface MapHandle { focusMap: () => void, focusFullscreenButton: () => void }
let mapHandle: MapHandle | null = null
function setMap(handle: unknown) {
  mapHandle = handle as MapHandle | null
}
// Escape closes the panel of the layers button first, and leaves the full screen at the next press
const fullscreen = useElementFullscreen(screen, { escapeTaken: () => layersOpen.value })
const inFullscreen = computed(() => fullscreen.active.value)
/** The attribute the styles of the full screen go by: there only while it is (a map that is not full screen has none of them: its corners, no room of the notch) */
const fullscreenMark = computed(() => fullscreen.mode.value === 'off' ? undefined : fullscreen.mode.value)
/** Where the focus goes when the full screen ends: the button that was pressed, or the panel's heading ("Show details") */
let afterFullscreen: 'button' | 'details' = 'button'
watch(fullscreen.mode, (now, before) => {
  if (before === 'off' && now !== 'off') {
    void nextTick(() => mapHandle?.focusMap())
  }
  else if (before !== 'off' && now === 'off') {
    // "Show details" puts the focus on the panel's heading itself, once the browser has left full screen
    if (afterFullscreen === 'details')
      return
    void nextTick(() => mapHandle?.focusFullscreenButton())
  }
}, { flush: 'post' })
/** "Show details": the panel is behind the full screen, so it is left, and the panel's heading has the focus */
async function showDetails() {
  afterFullscreen = 'details'
  // the browser's full screen is left when this is answered: until then the panel is behind it and a focus there is lost
  await fullscreen.exit()
  await nextTick()
  afterFullscreen = 'button'
  scrollPanelIntoView()
  detailHeading.value?.focus()
}
/** On a phone the panel is under the map: it comes up to the middle of the window, so that the map and the panel are both seen */
function scrollPanelIntoView() {
  if (wide.value || !panel.value)
    return
  const top = panel.value.getBoundingClientRect().top + window.scrollY - window.innerHeight * 0.42
  window.scrollTo({ top: Math.max(0, top), behavior: reducedMotion.value ? 'auto' : 'smooth' })
}
// the head of the page above the map (the title and the ⓘ) is measured, so that the map fills what is left of the window
const pageHeader = ref<{ $el: HTMLElement } | null>(null)
const { height: headHeight } = useElementSize(computed(() => pageHeader.value?.$el), undefined, { box: 'border-box' })
// the drop-downs of the layers panel (the selects) are in the body, which a browser's full screen does not show: into the stage
const portalTarget = computed(() => fullscreen.mode.value === 'native' ? screen.value ?? true : true)

const reach = computed(() => formatDistance(REACH_KM, formatLanguage.value))

// ---- the reader's own position (GH-3651) ------------------------------------------------------------------------

/** The position the reader gave by "Use my location", rounded to about 1 km: marked on the map, and the place picked */
const myPosition = ref<Point | null>(null)
/** Counts the presses that gave a position: the map centres on it once for each */
const locateCount = ref(0)
/** A position that came before the list of the stations: picked as soon as the list is there */
let pendingPosition: Point | null = null
const { position: rememberedPosition } = useMyLocation()
// "Forget my position" takes the position off the map and out of the panel: the mark, the place it made (the station
// stays picked, as the reader's station, with no place apart from it) and a lookup that was waiting for the list
watch(rememberedPosition, (now) => {
  if (now)
    return
  myPosition.value = null
  pendingPosition = null
  if (origin.value.kind !== 'position')
    return
  if (selected.value) {
    anchor.value = { latitude: selected.value.latitude, longitude: selected.value.longitude }
    origin.value = { kind: 'station', name: stationName(selected.value) }
  }
  else {
    anchor.value = null
    origin.value = { kind: 'unknown' }
    noStationNear.value = false
  }
})

function pickPosition(point: Point) {
  pickAt(point, SAME_PLACE_KM, true, 0, 0, { kind: 'position' })
}

function onPosition(point: Point) {
  myPosition.value = point
  locateCount.value++
  if (listStatus.value === 'success')
    pickPosition(point)
  else
    pendingPosition = point
}

watch(listStatus, (status) => {
  if (status === 'success' && pendingPosition) {
    const point = pendingPosition
    pendingPosition = null
    pickPosition(point)
  }
})

/** Counts the picks from outside the map that it is to move to; the map moves once for each, as soon as the station is there */
const recentre = ref(0)

/** The station the address opened the page with, or a pick from outside, waits to be announced and moved to until its station is there */
let fromAddress = Boolean(selectedId.value)
/** The view was changed under a pick: the list that arrives has the station for the place of it picked again */
let reselect = false

/** Which stations of the layer shown have stopped: the measuring ones have, by the clock of their list (DWD's), or by the year (GHCN daily's) */
const reporting = computed(() => layer.value === 'measured' ? reportingRule(stations.value) : layer.value === 'ghcn' ? ghcnReportingRule() : undefined)

/**
 * Whether the legend of the dots and the groups has something to say: on the measuring layer (a filled dot reports, a hollow one has
 * stopped) and where the stations are grouped at this zoom. It is in the layers panel (GH-4227), and the map's own description says it too
 */
const stationLegendShown = computed(() => (Boolean(reporting.value) || groupedNow.value) && listStatus.value === 'success' && stations.value.length > 0)
const legendShown = computed(() => stationLegendShown.value || warningsOn.value)
/** The legend as sentences, for the map's description (a screen reader does not see the dots and the discs, nor opens the panel to learn what they are) */
const legendDescription = computed(() => {
  if (!legendShown.value)
    return ''
  const sentences = [
    ...(reporting.value && stationLegendShown.value ? [t('mapTool.legendDotsDescription')] : []),
    ...(groupedNow.value ? [reporting.value ? t('mapTool.legendGroupShare') : t('mapTool.legendGroup')] : []),
    ...(warningsOn.value ? [t('warnings.legendDescription')] : []),
  ]
  return sentences.map(sentence => `${sentence.replace(/\.$/, '')}.`).join(' ')
})

/** What `picked` is for a station of the layer shown */
function remember(station: PlacedStation): PickedStation {
  return {
    station_id: station.station_id,
    wmo: wmoNumber(station),
    observation: layer.value === 'measured',
    // a forecast point has no status, and counts as current
    reports: reporting.value ? reporting.value(station) : true,
  }
}

function choose(station: PlacedStation, options: { point?: Point, focus?: boolean, from?: PlaceOrigin } = {}) {
  selectedId.value = station.station_id
  pickedIn = viewKey.value
  picked = remember(station)
  sameStation.value = null
  anchor.value = options.point ?? { latitude: station.latitude, longitude: station.longitude }
  // a station chosen by name, from the list or by its dot, is a place of its own: no click was made
  origin.value = options.point ? options.from ?? POINT : { kind: 'station', name: stationName(station) }
  unknownStation.value = null
  noStationNear.value = false
  announcement.value = chosenText(station, stations.value, anchor.value)
  void nextTick(() => {
    // the panel is behind the full screen: the sheet says what was picked, and nothing of the page behind is moved or focused
    if (inFullscreen.value)
      return
    if (options.focus)
      detailHeading.value?.focus()
    scrollPanelIntoView()
  })
}

/** A point that has no station within reach: nothing is picked, the point is kept, and the panel says so */
function tellNoStationNear(point: Point, from: PlaceOrigin = POINT) {
  selectedId.value = null
  pickedIn = viewKey.value
  anchor.value = point
  origin.value = from
  unknownStation.value = null
  sameStation.value = null
  noStationNear.value = true
  announcement.value = t('mapTool.noStationNear', { distance: reach.value })
}

/**
 * A pick at a point (a click on the map, the centre of the map): the station on its dot where the point is on one,
 * whatever its status, else the station for the place (`stationFor`), which has to be within reach.
 */
function pickAt(point: Point, tolerance: number, focus = false, tap = 0, disc = 0, from: PlaceOrigin = POINT) {
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
    return choose(touched.station, { point, focus, from })
  const found = stationFor(stations.value, point, reporting.value)
  if (found) {
    choose(found.station, { point, focus, from })
  }
  else {
    // the pick is a place with no station: the station before is not carried to the next layer for it
    picked = null
    tellNoStationNear(point, from)
  }
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
  pickAt({ latitude: view.value.latitude, longitude: view.value.longitude }, SAME_PLACE_KM, true, 0, 0, { kind: 'centre' })
}

/** A click on a group of stations has zoomed the map in on them: said, as a pick is */
let groupAnnouncement: ReturnType<typeof setTimeout> | undefined
function onGroup(count: number, reportingCount: number | null) {
  const shown = formatNumber(count, formatLanguage.value, 0)
  const said = reportingCount === null
    ? t('mapTool.groupZoomed', { shown })
    : t('mapTool.groupZoomedReporting', { shown, reporting: formatNumber(reportingCount, formatLanguage.value, 0) })
  // a status that says the same again is not read again: it is emptied first and said again after a moment (a screen reader
  // takes the emptying and the new text of one frame for no change)
  announcement.value = ''
  clearTimeout(groupAnnouncement)
  groupAnnouncement = setTimeout(() => {
    announcement.value = said
  }, 100)
}
onBeforeUnmount(() => clearTimeout(groupAnnouncement))

function back() {
  const id = selectedId.value
  selectedId.value = null
  picked = null
  sameStation.value = null
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

/**
 * The station of a new view for the place picked. Where the station picked before has a WMO number and one station of the
 * new list has the same, that is the same station (GH-4077): the map takes it and says so, however far its position is from
 * the old one (MOSMIX gives positions in whole minutes, so the two are a median 0.66 km apart). A number that the list has on
 * none or on several stations finds nothing, and neither does a station with no number: the station is picked again by its
 * position, as it was, the same station where it is under the place.
 */
function pickAgain(list: PlacedStation[]) {
  const point = anchor.value!
  const same = picked ? findSameStation(list, picked, layer.value === 'measured', reporting.value) : null
  if (same?.by === 'wmo') {
    const found = same.station
    selectedId.value = found.station_id
    pickedIn = viewKey.value
    picked = remember(found)
    unknownStation.value = null
    noStationNear.value = false
    // the place was the position of the station before: it is the position of this one
    if (origin.value.kind === 'station') {
      anchor.value = { latitude: found.latitude, longitude: found.longitude }
      origin.value = { kind: 'station', name: stationName(found) }
    }
    sameStation.value = wmoNumber(found)
    announcement.value = `${t('mapTool.chosen', { name: stationName(found) })}. ${t('mapTool.sameStation', { wmo: sameStation.value })}`
    return
  }
  sameStation.value = null
  // by its id where both lists are DWD's observations (another dataset), else by the place
  const found = same?.station ?? stationAt(list, point, SAME_PLACE_KM) ?? stationFor(list, point, reporting.value)?.station
  if (!found)
    return tellNoStationNear(point, origin.value)
  selectedId.value = found.station_id
  pickedIn = viewKey.value
  picked = remember(found)
  unknownStation.value = null
  noStationNear.value = false
  // told, as a station that the reader chose is: it is another station than the one in the heading before
  announcement.value = chosenText(found, list, point)
}

/** Whether the map is kept where it is for the pick (a pick carried to GHCN daily from a place that is off the screen) */
const holdView = ref(false)

// A position in the address with no station (`?lat=&lon=`, from the search of the header): picked as a click at it would pick,
// with the station for the place if there is one within reach, and the map moved to the position either way, not to the
// station, which may be 100 km off it. It waits for the list of stations, which a pick is made from.
/** Moves the map to a position, once for each: the count is what tells the map there is a new one */
const goTo = ref<(Point & { count: number }) | null>(null)
let pendingAddressPoint: Point | null = null
/** The position the address named, which stays its place where no station is within reach of it */
const typedPoint = ref<Point | null>(null)
/** The position of the address that was taken last, so that the address written after the pick (`?station=&lat=&lon=`) takes nothing and the same position typed again later is taken */
let takenPoint: string | null = null
function pickAddressPoint(point: Point) {
  // the station picked is brought into view by the map where it is off the screen; here the position is what the reader asked for
  holdView.value = true
  void nextTick(() => {
    holdView.value = false
  })
  pickAt(point, SAME_PLACE_KM, false, 0, 0, { kind: 'unknown' })
}
function takeAddressPoint(query: Record<string, unknown>) {
  const point = pointFromQuery(query)
  const key = point ? `${point.latitude},${point.longitude}` : null
  if (key === takenPoint)
    return
  takenPoint = key
  typedPoint.value = point
  if (!point)
    return
  // the map moves to the position at once, whether or not the list of stations comes (a failed list shows its error and the map is where it was asked about)
  goTo.value = { ...point, count: (goTo.value?.count ?? 0) + 1 }
  if (listStatus.value === 'success')
    pickAddressPoint(point)
  else
    pendingAddressPoint = point
}
watch(listStatus, (status) => {
  if (status === 'success' && pendingAddressPoint) {
    const point = pendingAddressPoint
    pendingAddressPoint = null
    pickAddressPoint(point)
  }
})
takeAddressPoint(route.query)

// A change of layer or dataset, and the list that comes after it. The id of a station is the id in the list of
// one view (DWD's forecast points and its measuring stations number their stations alike, and 59 of the ids are
// two stations), so a pick is never taken to another view by its id: it is picked again in the new list by its WMO number,
// the same station wherever one has it (`pickAgain`), else for the place it was at. A list that has arrived with no change under it holds the station of the address, or the panel
// says there is none.
watch([viewKey, stations], ([key, list], [previousKey]) => {
  if (key !== previousKey && (selectedId.value || anchor.value) && pickedIn !== key) {
    // with no place to go by (the address named a station and its list has not come) there is nothing to pick again
    reselect = Boolean(anchor.value)
    selectedId.value = null
    noStationNear.value = false
    fromAddress = false
  }
  // the notice of a station that the view before did not have is not about this one, nor is the word that it is the same
  if (key !== previousKey) {
    unknownStation.value = null
    sameStation.value = null
  }
  if (!list.length)
    return
  if (reselect) {
    reselect = false
    // a pick carried to GHCN daily: the map stays where the reader has moved it, whether or not the new station is on the screen
    if (layer.value === 'ghcn') {
      holdView.value = true
      void nextTick(() => {
        holdView.value = false
      })
    }
    return pickAgain(list)
  }
  if (selectedId.value && !list.some(station => station.station_id === selectedId.value)) {
    unknownStation.value = selectedId.value
    selectedId.value = null
    anchor.value = null
    fromAddress = false
  }
})

// ---- the details of the station of GHCN daily that is picked -------------------------------------------------------------

async function loadGhcnDetails() {
  const id = layer.value === 'ghcn' ? selected.value?.station_id : undefined
  if (!id) {
    ghcnDetails.value = null
    return
  }
  if (ghcnDetails.value?.station_id === id)
    return
  ghcnDetails.value = null
  let found: PlacedStation | undefined
  try {
    found = placed((await $fetch<{ stations: Station[] }>('/api/stations', { query: { ...GHCN_STATIONS_QUERY, stations: id }, ...API_FETCH })).stations ?? [])[0]
  }
  catch {
    // the panel has the list's name and place without them
  }
  // another station was picked, or the layer left, while it was asked for
  if (found && layer.value === 'ghcn' && selected.value?.station_id === id)
    ghcnDetails.value = found
}
watch([layer, () => selected.value?.station_id], () => void loadGhcnDetails(), { immediate: true })

// ---- the nearest station of each kind, for the panel ------------------------------------------------------------

// the lists the panel needs, beside the one shown, asked for once a station is picked; the station is a place, which the
// panel is about from then on (the station of an address has none until the list brings it)
watch(selected, (station) => {
  if (!station)
    return
  // what is remembered is the station of the view it was picked in: with the list of another view under the same id (59 ids
  // are two stations) the station is not the one picked, and the watch of the list does not depend on running before this
  if (pickedIn === viewKey.value)
    picked = remember(station)
  if (!anchor.value) {
    anchor.value = { latitude: station.latitude, longitude: station.longitude }
    origin.value = { kind: 'station', name: stationName(station) }
  }
  if (fromAddress) {
    fromAddress = false
    recentre.value++
    announcement.value = chosenText(station, stations.value, anchor.value)
  }
  void forecast.ensure()
  // a station of GHCN daily has its own stripes and measurements: the nearest DWD ones are not asked for
  if (layer.value === 'ghcn')
    return
  void stripes.ensure()
  void ensureMeasured()
}, { immediate: true })
watch(sourceKey, () => {
  if (selected.value && layer.value !== 'ghcn')
    void ensureMeasured()
})

/**
 * The station of a card: the station picked, for the layer it is of, and for the others the nearest within reach of
 * the place (`stationFor`), with its distance from the place, none where it is under half a kilometre.
 */
function cardFor(list: PlacedStation[], isShown: boolean, running?: ReportingRule, inObservation = false): { station: PlacedStation, distance: number, same?: boolean } | null {
  if (!selected.value)
    return null
  const point = anchor.value ?? selected.value
  if (isShown) {
    const distance = distanceKm(point, selected.value)
    return { station: selected.value, distance: distance > SAME_PLACE_KM ? distance : 0 }
  }
  // the same station of another list (GH-4077): by its id where both lists are DWD's observations, by its WMO number where
  // exactly one station of the list has it and does not report less than the station picked. Not a station near the place
  const same = findSameStation(list, remember(selected.value), inObservation, running)
  if (same)
    return { station: same.station, distance: 0, same: same.by === 'wmo' || undefined }
  return stationFor(list, point, running)
}
const forecastPoint = computed(() => cardFor(forecast.stations.value, layer.value === 'forecast'))
const stripesRule = computed(() => reportingRule(stripes.stations.value))
const measuredRule = computed(() => reportingRule(measured.stations.value))
// the stripes' stations are DWD's observations: the same id is the same station where the station picked is one too
const stripesPoint = computed(() => cardFor(stripes.stations.value, false, stripesRule.value, true))
const measuredPoint = computed(() => cardFor(measured.stations.value, layer.value === 'measured', measuredRule.value, true))

/** The nearer station that has stopped, where the one the card offers is farther because it reports (GH-3875) */
const measuredCloser = computed(() => {
  // the same station by its WMO number is no other station that was chosen for the place: nothing nearer to explain
  if (!selected.value || !measuredPoint.value || measuredPoint.value.same)
    return null
  return closerStoppedStation(measured.stations.value, anchor.value ?? selected.value, measuredPoint.value.station, measuredRule.value)
})
/** Why the station is not the nearest: the one that reports, and the nearer one that has stopped, with how long it measured */
function whyFarther(closer: CloserStation) {
  const params = { name: stationName(closer.station), distance: formatDistance(closer.distance, formatLanguage.value), year: closer.endYear }
  return closer.endYear === null ? t('mapTool.whyFartherNoEnd', params) : t('mapTool.whyFarther', params)
}
/** What is announced for a station chosen: its name, and for a measuring station that is not the nearest, why */
function chosenText(station: PlacedStation, list: PlacedStation[], point: Point) {
  const chosen = t('mapTool.chosen', { name: stationName(station) })
  if (!reporting.value)
    return chosen
  const closer = closerStoppedStation(list, point, station, reporting.value)
  return closer ? `${chosen}. ${whyFarther(closer)}` : chosen
}
/** The nearer station that has stopped, picked in place of the one that reports: its record can matter for the history and the stripes */
function pickCloser(closer: CloserStation) {
  choose(closer.station, { point: anchor.value ?? undefined, from: origin.value, focus: true })
}
/** Where the place is from, as the panel tells it */
const placeText = computed(() => {
  if (!place.value || !selected.value)
    return ''
  const distance = formatDistance(distanceKm(place.value, selected.value), formatLanguage.value)
  const from = origin.value
  if (from.kind === 'station')
    return t('mapTool.pickedStationPlace', { name: from.name, distance })
  return t({ centre: 'mapTool.pickedCentre', unknown: 'mapTool.pickedPlaceAddress', point: 'mapTool.pickedPlace', position: 'mapTool.pickedPosition' }[from.kind], { distance })
})

const sourceLabel = computed(() => `${datasetLabel(source.value.dataset)}, ${resolutionLabel(source.value.resolution)}`)
/**
 * How long a station has measured: since its first year while it reports, from it to its last year once it has
 * stopped; nothing where it has no end, which says nothing of whether it has stopped (DWD's lists), except in GHCN daily's, where
 * no end is a last year that is the current one: it reports.
 */
function measuredFor(station: Station) {
  const ghcnLayer = layer.value === 'ghcn'
  const from = yearOf(station.start_timestamp)
  const to = yearOf(station.end_timestamp)
  if (from === null || (to === null && !(ghcnLayer && !station.end_timestamp)))
    return null
  const running = ghcnLayer ? ghcnReportingRule() : measuredRule.value
  return running(station) ? t('mapTool.since', { year: from }) : t('mapTool.period', { from, to })
}

// ---- the climate stripes of a station of GHCN daily ----------------------------------------------------------------

/** The least years a record has for the backend to make stripes of it (its `MIN_RECORD_YEARS`) */
const STRIPES_MIN_YEARS = 10
/**
 * Whether the stripes of a station of GHCN daily are worth asking for: its record, from the list's first year to its last (or
 * this one), is as long as stripes need. Most stations of the layer are shorter, and a station that is long enough may still
 * have none (a record with gaps), which the card then says.
 */
function ghcnStripesPossible(station: Station) {
  const from = yearOf(station.start_timestamp)
  const to = yearOf(station.end_timestamp) ?? new Date().getUTCFullYear()
  return from === null || to - from + 1 >= STRIPES_MIN_YEARS
}
/** The station whose stripes the backend refused, which the card says it has none of (and offers no link to) */
const noStripes = ref<string | null>(null)
/** What a refusal says of the mirror of NOAA's data on AWS where the record it refused was read from it (GH-4390), else an empty text */
const noStripesMirrorNote = ref('')
/** The stripes of the station were refused: the card says it has none, and what the refusal says of the mirror */
function onNoStripes(stationId: string, mirrorNote: string) {
  noStripes.value = stationId
  noStripesMirrorNote.value = mirrorNote
}
function stationName(station: Station) {
  return station.name ?? station.station_id
}

// ---- the address follows what is shown, and what the address says from outside is taken ---------------------------

// the reader's own position is not written into the address, which is copied and shared: the station is
/** The place the address says: the one picked beside a station, or the position of the address's own that no station is within reach of (GH-3790); a click that finds no station is not written, as before */
const addressPlace = computed(() => place.value ?? (!selectedId.value && noStationNear.value && anchor.value && typedPoint.value && distanceKm(anchor.value, typedPoint.value) < 0.001 ? anchor.value : null))
const state = computed<MapState>(() => ({ layer: layer.value, source: source.value, stationId: selectedId.value, place: origin.value.kind === 'position' ? null : addressPlace.value }))
const queryOf = (map: MapState) => JSON.stringify(stateToQuery(map))

watch(state, (shown) => {
  // the keys that are the map's are replaced, any other the address has stays
  const rest = Object.fromEntries(Object.entries(route.query).filter(([key]) => !['layer', 'resolution', 'dataset', 'station', 'lat', 'lon', 'q', 'warnings'].includes(key)))
  // always asked, even where the address already says it: a write of an earlier state that is still on its way is then
  // replaced by this one (the router lets the newer navigation cancel the older), and does not land after it. A
  // rejected or duplicate navigation is no error of the page
  void router.replace({ query: { ...rest, ...stateToQuery(shown), ...(warningsOn.value ? { warnings: '1' } : {}) } }).catch(() => {})
})
// the chip is in the address too (`?warnings=1`), so that a link opens the map with the warnings on, as the Ask the weather question's does
watch(warningsOn, (on) => {
  const { warnings: _, ...rest } = route.query
  void router.replace({ query: { ...rest, ...(on ? { warnings: '1' } : {}) } }).catch(() => {})
})
watch(() => route.query.warnings, (value) => {
  warningsOn.value = value === '1'
})

// An address that names another map than the one shown, from outside the page (the header's search while the map is
// open, a link): the page takes it. What the page wrote itself names what it shows already. Its station is a station
// of the layer it names.
watch(() => route.query, (query) => {
  takeAddress(query)
  takeAddressPoint(query)
  // a text the address brings starts the search of the panel; the page's own writes carry none
  const typed = searchFromQuery(query)
  if (typed)
    search.value = typed
})
function takeAddress(query: Record<string, unknown>) {
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
    // another pick than the one remembered: the station of the address is remembered when its list brings it
    picked = null
    sameStation.value = null
    unknownStation.value = null
    announcement.value = ''
    fromAddress = Boolean(named.stationId)
  }
  anchor.value = named.place
  origin.value = { kind: 'unknown' }
}
</script>

<template>
  <div class="frame" :style="phone ? { '--map-head': `${Math.ceil(headHeight)}px` } : undefined">
    <PageHeader ref="pageHeader" :title="t('mapTool.title')" :lede="t('mapTool.subtitle')" :about-label="t('mapTool.aboutButton')" compact>
      <template #about>
        <div class="space-y-3 text-muted">
          <p>{{ t('mapTool.about1') }}</p>
          <p>{{ t('mapTool.about2') }}</p>
          <p>{{ t('mapTool.about3') }}</p>
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
                  {{ placeText }}
                </p>
                <p v-if="sameStation" class="mt-2 inline-flex items-center gap-1.5 text-sm text-toned" data-testid="map-same-station">
                  <UIcon name="i-ph-link" class="size-4 shrink-0" />
                  {{ t('mapTool.sameStation', { wmo: sameStation }) }}
                </p>
                <!-- the station is the one found for the reader's position (GH-4011): the list that holds the button is
                     not in view, so the option to keep the position, or the control that says it is kept, is here; the
                     list and the card are never both in the page, so there is one of them to tab to -->
                <UseMyLocation v-if="origin.kind === 'position'" offer-only class="mt-2" @forgotten="focusDetailHeading" />
              </div>

              <!-- DWD's warnings whose polygon contains the place picked (GH-4295): with the layer on or off, for the station or the place of the pick -->
              <WarningsBanner v-if="bannerPoint" :point="bannerPoint" :source="warnings" id-prefix="map-banner" data-testid="map-warnings-banner" />

              <!-- the forecast, at the nearest forecast point -->
              <section class="map-card" aria-labelledby="map-forecast-title" data-testid="map-card-forecast">
                <h3 id="map-forecast-title" class="map-card-title">
                  <UIcon name="i-ph-sun" class="map-card-icon" />
                  {{ t('nav.meteogram') }}
                </h3>
                <template v-if="forecastPoint">
                  <p v-if="forecastPoint.same" class="map-card-note" data-testid="map-card-same-forecast">
                    {{ stationName(forecastPoint.station) }} · {{ t('mapTool.sameStation', { wmo: wmoNumber(forecastPoint.station) }) }}
                  </p>
                  <p v-else-if="forecastPoint.distance > 0" class="map-card-note">
                    {{ t('mapTool.at', { name: stationName(forecastPoint.station), distance: formatDistance(forecastPoint.distance, formatLanguage) }) }}
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
                <!-- a station of GHCN daily: its own stripes, built from its days -->
                <template v-if="layer === 'ghcn'">
                  <template v-if="ghcnStripesPossible(selected) && noStripes !== selected.station_id">
                    <MapStripes :station-id="selected.station_id" :station-name="stationName(selected)" ghcn @none="onNoStripes(selected.station_id, $event)" />
                    <UButton :to="stripesLink(selected.station_id, true)" :label="t('mapTool.openStripes')" trailing-icon="i-ph-arrow-right" variant="link" class="map-link" />
                  </template>
                  <p v-else class="map-card-note" data-testid="map-stripes-none">
                    {{ t('mapTool.stripesNone') }}
                  </p>
                  <p v-if="noStripes === selected.station_id && noStripesMirrorNote" class="map-card-note" data-testid="map-stripes-none-mirror">
                    {{ noStripesMirrorNote }}
                  </p>
                </template>
                <template v-else-if="stripesPoint">
                  <p v-if="stripesPoint.same" class="map-card-note" data-testid="map-card-same-stripes">
                    {{ stationName(stripesPoint.station) }} · {{ t('mapTool.sameStation', { wmo: wmoNumber(stripesPoint.station) }) }}
                  </p>
                  <p v-else-if="stripesPoint.distance > 0" class="map-card-note">
                    {{ t('mapTool.at', { name: stationName(stripesPoint.station), distance: formatDistance(stripesPoint.distance, formatLanguage) }) }}
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

              <!-- the measurements and the history, at the nearest station of the source chosen in the layers panel -->
              <section class="map-card" aria-labelledby="map-measured-title" data-testid="map-card-measured">
                <h3 id="map-measured-title" class="map-card-title">
                  <UIcon name="i-ph-thermometer" class="map-card-icon" />
                  {{ t('home.kindObservationsTitle') }}
                </h3>
                <!-- a station of GHCN daily: its own daily values, in the Explorer; the station history is DWD's alone -->
                <template v-if="layer === 'ghcn'">
                  <p class="map-card-note" data-testid="map-card-ghcn-source">
                    {{ t('mapTool.ghcnSource') }}<template v-if="measuredFor(selected)">
                      · {{ measuredFor(selected) }}
                    </template>
                  </p>
                  <UButton :to="measurementsLink(GHCN_SOURCE, selected.station_id, GHCN_NETWORK)" :label="t('mapTool.openExplorer')" trailing-icon="i-ph-arrow-right" variant="link" class="map-link" />
                </template>
                <template v-else-if="measuredPoint">
                  <p class="map-card-note">
                    {{ sourceLabel }}<template v-if="measuredFor(measuredPoint.station)">
                      · {{ measuredFor(measuredPoint.station) }}
                    </template>
                  </p>
                  <p v-if="measuredPoint.same" class="map-card-note" data-testid="map-card-same-measured">
                    {{ stationName(measuredPoint.station) }} · {{ t('mapTool.sameStation', { wmo: wmoNumber(measuredPoint.station) }) }}
                  </p>
                  <p v-else-if="measuredPoint.distance > 0" class="map-card-note">
                    {{ t('mapTool.at', { name: stationName(measuredPoint.station), distance: formatDistance(measuredPoint.distance, formatLanguage) }) }}
                  </p>
                  <!-- the station is not the nearest: a nearer one has stopped (GH-3875) -->
                  <div v-if="measuredCloser" class="map-why" data-testid="map-why">
                    <p class="map-card-note">
                      {{ whyFarther(measuredCloser) }}
                    </p>
                    <UButton
                      v-if="layer === 'measured'"
                      :label="t('mapTool.pickCloser', { name: stationName(measuredCloser.station) })"
                      icon="i-ph-arrow-u-up-left"
                      color="neutral"
                      variant="outline"
                      size="sm"
                      class="map-why-button"
                      data-testid="map-pick-closer"
                      @click="pickCloser(measuredCloser)"
                    />
                  </div>
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
              <!-- the layer's list of the warnings, and for a click that found no station the warnings of the place (GH-4295) -->
              <WarningsBanner v-if="warningsOn && noStationNear && anchor" :point="anchor" :source="warnings" id-prefix="map-place-banner" />
              <WarningsPanel v-if="warningsOn" :source="warnings" :focused="focusedWarning" @focus="onWarningFocus" />
              <p v-if="listStatus === 'success'" class="text-sm text-muted sm:hidden" data-testid="map-count-panel">
                {{ countLabel }}
              </p>
              <UseMyLocation @position="onPosition" />
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
                      <span v-if="entry.distance !== null" class="shrink-0 text-xs text-muted tabular-nums">{{ formatDistance(entry.distance, formatLanguage) }}</span>
                    </button>
                  </li>
                </ul>
                <!-- the list shows the best few: how many there are in all is said, as the header's "N more" counts the same stations -->
                <p v-if="searching && searched.total > found.length" class="mt-2 text-sm text-muted" data-testid="map-results-of">
                  {{ t('mapTool.resultsOf', { shown: found.length, total: searched.total }) }}
                </p>
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

          <!-- The map, the one button over it that opens the layers (GH-4209), and the status chips -->
          <div v-else class="map-stage" :data-fullscreen="fullscreenMark" data-testid="map-stage">
            <div :ref="setScreen" class="map-screen" :data-fullscreen="fullscreenMark" data-testid="map-screen">
              <div class="map-canvas">
                <div class="map-layers">
                  <MapLayers
                    v-model:layer="layer"
                    v-model:open="layersOpen"
                    v-model:grouped="grouped"
                    :layer-items="layerItems"
                    :show-grouping="listStatus === 'success' && stations.length > 0"
                    :compulsory="groupingInForce.compulsory"
                    :note="groupingCompulsoryText"
                    :show-legend="legendShown"
                  >
                    <template #default>
                      <template v-if="layer === 'measured'">
                        <USelect v-model="resolutionChoice" :items="resolutionItems" :portal="portalTarget" :aria-label="t('parameterSelection.resolutionLabel')" class="w-full" data-testid="map-resolution" />
                        <USelect v-model="datasetChoice" :items="datasetItems" :portal="portalTarget" :aria-label="t('parameterSelection.datasetLabel')" class="w-full" data-testid="map-dataset" />
                      </template>
                    </template>
                    <template #legend>
                      <ul v-if="stationLegendShown" class="map-legend" data-testid="map-legend">
                        <template v-if="reporting">
                          <li>
                            <span class="map-legend-dot" aria-hidden="true" data-testid="map-legend-reporting" />
                            {{ t('mapTool.legendReporting') }}
                          </li>
                          <li>
                            <span class="map-legend-dot map-legend-dot-stopped" aria-hidden="true" data-testid="map-legend-stopped" />
                            {{ t('mapTool.legendStopped') }}
                          </li>
                        </template>
                        <li v-if="groupedNow">
                          <span class="map-legend-dot map-legend-group" :class="{ 'map-legend-group-share': reporting }" aria-hidden="true" data-testid="map-legend-group">12</span>
                          {{ reporting ? t('mapTool.legendGroupShare') : t('mapTool.legendGroup') }}
                        </li>
                      </ul>
                      <WarningsLegend v-if="warningsOn" />
                    </template>
                  </MapLayers>
                </div>
                <div class="map-chips">
                  <div class="map-chips-row">
                    <!-- on a phone the count is in the panel, and the chips take less of the map -->
                    <span v-if="listStatus === 'success'" class="map-status map-count" data-testid="map-count">{{ countLabel }}</span>
                    <span v-else-if="listStatus === 'pending' || listStatus === 'idle'" class="map-status" role="status">
                      <UIcon name="i-ph-circle-notch" class="size-4 motion-safe:animate-spin" />
                      {{ t('mapTool.loadingStations') }}
                    </span>
                    <!-- the layer of DWD's weather warnings (GH-4295): a toggle, whose state is `aria-pressed` and, for the eye, a check beside the label (no colour alone) -->
                    <button type="button" class="map-status map-chip" :aria-pressed="warningsOn" data-testid="map-warnings-chip" @click="warningsOn = !warningsOn">
                      <UIcon :name="warningsOn ? 'i-ph-check-circle-fill' : 'i-ph-warning'" class="size-4" aria-hidden="true" />
                      {{ warningsChipLabel }}
                    </button>
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

                <p id="map-legend-description" class="sr-only" data-testid="map-legend-description">
                  {{ legendDescription }}
                </p>
                <ClientOnly>
                  <StationMap
                    :ref="setMap"
                    :stations="stations"
                    :selected="selected"
                    :recentre="recentre"
                    :warnings="warningsDrawn"
                    :show-warning="showWarning"
                    :credits="warningsCredit"
                    :go-to="goTo"
                    :position="myPosition"
                    :locate="locateCount"
                    :place="place"
                    :reporting="reporting"
                    :grouping="groupingInForce.grouping"
                    :hold="holdView"
                    :panel-open="layersOpen"
                    :fullscreen="inFullscreen"
                    :described-by="legendDescription ? 'map-legend-description' : undefined"
                    :label="mapLabel"
                    @pick="onPick"
                    @view="view = $event"
                    @group="onGroup"
                    @fullscreen="fullscreen.toggle()"
                  />
                </ClientOnly>
              </div>

              <!-- while the map is full screen the panel is out of reach, and this stands in for it (GH-4227): the station picked,
                   the keyboard's way to a place, and the way back to the panel's details -->
              <div v-if="inFullscreen" class="map-sheet" role="group" :aria-label="t('mapTool.fullscreenSheet')" data-testid="map-sheet">
                <p class="sr-only" role="status" data-testid="map-sheet-announcement">
                  {{ announcement }}
                </p>
                <div class="map-sheet-text">
                  <template v-if="selected">
                    <p class="map-sheet-name" data-testid="map-sheet-name">
                      {{ stationName(selected) }}
                    </p>
                    <p class="map-sheet-meta">
                      {{ selected.station_id }}<template v-if="selected.region">
                        · {{ selected.region }}
                      </template>
                    </p>
                  </template>
                  <p v-else-if="noStationNear" class="map-sheet-meta">
                    {{ t('mapTool.noStationNear', { distance: reach }) }}
                  </p>
                  <p v-else class="map-sheet-meta">
                    {{ listStatus === 'success' ? countLabel : t('mapTool.loadingStations') }}
                  </p>
                </div>
                <div class="map-sheet-actions">
                  <UButton
                    v-if="selected"
                    :label="t('mapTool.showDetails')"
                    icon="i-ph-list-bullets"
                    color="primary"
                    variant="solid"
                    size="lg"
                    aria-describedby="map-sheet-details-hint"
                    data-testid="map-sheet-details"
                    @click="showDetails"
                  />
                  <UButton
                    v-if="stations.length"
                    :label="t('mapTool.pickCentre')"
                    icon="i-ph-crosshair"
                    color="neutral"
                    variant="outline"
                    size="lg"
                    aria-describedby="map-sheet-pick-hint"
                    data-testid="map-sheet-pick-centre"
                    @click="pickCentre"
                  />
                  <p id="map-sheet-details-hint" class="sr-only">
                    {{ t('mapTool.showDetailsHint') }}
                  </p>
                  <p id="map-sheet-pick-hint" class="sr-only">
                    {{ t('mapTool.pickCentreHint') }}
                  </p>
                </div>
              </div>
            </div>
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
  height: clamp(22rem, 64dvh, 36rem);
}
@media (min-width: 72rem) {
  .map-stage {
    position: sticky;
    top: calc(var(--header-height) + 1rem);
    height: clamp(30rem, calc(100dvh - var(--header-height) - 2rem), 52rem);
  }
}
/* The phone (GH-4227): the map fills what the bars leave of the window, under the title and its ⓘ (`--map-head`, measured by
   the page), and runs to the window's edges. The tab bar is `--tabbar-height` high where it is fixed and 0 where it scrolls with the page. */
@media screen and (width < 40rem) {
  .map-stage {
    height: max(18rem, calc(100dvh - var(--header-height) - var(--tabbar-height) - var(--map-head, 3.5rem)));
    margin-inline: calc(-1 * var(--bleed-start)) calc(-1 * var(--bleed-end));
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
/* a phone on its side: the bars scroll away, and the map is the window's height (its title is above it) */
@media screen and (width < 40rem) and (max-height: 30rem) {
  .map-stage {
    height: max(15rem, calc(100dvh - 1rem));
  }
}
/* The map's screen, the part of the stage that goes full screen (GH-4227): the map and what is over it (the canvas), and
   the sheet that stands in for the panel under it while it is full screen. It is the stage's own size until then. It has a
   stacking context of its own, so that Leaflet's panes (up to 1000) stay inside it. */
.map-screen {
  position: relative;
  isolation: isolate;
  display: flex;
  flex-direction: column;
  height: 100%;
  background: var(--ui-bg);
}
.map-canvas {
  position: relative;
  flex: 1 1 0;
  min-height: 0;
}
/* Full screen by the app (a browser that has no Fullscreen API for an element, or refuses it): the screen covers the window and the
   app's bars (the header and the tab bar are 40, the skip link 100 and inert), with the notch's and the home indicator's room kept.
   The stage in the page keeps its size, so the page behind does not move. A stage that is sticky (wide) or has a layer of its own would
   hold the screen under the bars: it has neither while the screen covers them. */
.map-stage[data-fullscreen="app"] {
  position: static;
}
.map-screen[data-fullscreen="app"] {
  position: fixed;
  inset: 0;
  z-index: 90;
  height: auto;
}
/* in either full screen: the room of the notch and the home indicator is the page's background, and the map has none of the page's corners */
.map-screen[data-fullscreen] {
  padding: var(--safe-top) var(--safe-right) var(--safe-bottom) var(--safe-left);
}
.map-screen[data-fullscreen] .station-map {
  min-height: 0;
  border-radius: 0;
}
/* the stand-in for the panel: the station picked, and two buttons, under the map (which has the rest of the screen) */
.map-sheet {
  flex: none;
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem 1rem;
  padding: 0.75rem;
  border-top: 1px solid var(--ui-border);
  background: var(--ui-bg);
}
.map-sheet-text {
  flex: 1 1 10rem;
  min-width: 0;
}
.map-sheet-name {
  font-size: 1.0625rem;
  font-weight: 700;
  line-height: 1.25;
  color: var(--ui-text-highlighted);
  overflow-wrap: anywhere;
}
.map-sheet-meta {
  font-size: 0.8125rem;
  color: var(--ui-text-muted);
  overflow-wrap: anywhere;
}
.map-sheet-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
}
/* the buttons are the label's width and wrap it where a language's words are longer than a phone's half row */
.map-sheet-actions .truncate {
  overflow: visible;
  white-space: normal;
  text-overflow: clip;
  text-align: start;
}
.map-sheet-actions > button,
.map-sheet-actions > a {
  max-width: 100%;
  white-space: normal;
  min-height: 2.75rem;
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
  /* the height of the layers button, which is in the same corner row: the failure under the row clears it */
  min-height: 2.75rem;
  /* the row is as wide as the map and its empty space is the map's: only what is in it takes the pointer; the end of it is the button's */
  padding-inline-end: 3.5rem;
  pointer-events: none;
}
.map-chips-row > *,
.map-failure {
  pointer-events: auto;
}
/* The layers button (MapLayers.vue), alone in the map's top right corner: the zoom buttons and the credit are at the
   bottom right, the legend at the bottom left and the status at the top left */
.map-layers {
  position: absolute;
  z-index: 1002;
  inset-inline-end: 0.75rem;
  top: 0.75rem;
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
.map-status.map-chip {
  min-height: 2.75rem;
  padding-inline: 1rem;
  border: 1px solid var(--ui-border-accented);
  font-weight: 600;
  cursor: pointer;
}
.map-status.map-chip:hover {
  background: var(--ui-bg-elevated);
}
/* on: the edge is heavier and the label bolder as well as the check, so the state is no colour alone */
.map-status.map-chip[aria-pressed="true"] {
  border-color: var(--ui-text-highlighted);
  border-width: 2px;
  color: var(--ui-text-highlighted);
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
.map-why {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 0.5rem;
}
.map-why-button {
  max-width: 100%;
  white-space: normal;
  text-align: start;
}
.map-why-button .truncate {
  overflow: visible;
  white-space: normal;
  text-overflow: clip;
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
/* The narrow layout runs edge to edge (GH-4227): the sheet under the map is as wide as the window, with no rounded corners and no hairline at the
   sides, and its cards reach out of its padding the same way; the text keeps the 16 px of the gutter. */
@media screen and (width < 40rem) {
  .map-panel {
    margin-inline: calc(-1 * var(--bleed-start)) calc(-1 * var(--bleed-end));
    border-radius: 0;
    border-inline-width: 0;
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
/* in the panel that runs edge to edge (GH-4227) a card does too: it reaches out of the panel's 16 px, which is its own text's gutter */
@media screen and (width < 40rem) {
  .map-card {
    margin-inline: -1rem;
    padding-inline: 1rem;
    border-radius: 0;
    border-inline-width: 0;
  }
}
</style>
