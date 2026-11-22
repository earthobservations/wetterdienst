<script setup lang="ts">
import type { Station, StationIdsResponse, StationIdsStation } from '#shared/types/api'
import type { PlaceMatch, PlacesAnswer } from '#shared/utils/places'
import type { Place } from '~/composables/usePlace'
import type { PaletteGroup, PaletteItem } from '~/utils/palette'
import type { Hit } from '~/utils/search-index'
import type { Tile } from '~/utils/sections'
import type { TypedStationId } from '~/utils/station-hits'
import type { SearchNetwork, StationMatch, StationSearchAnswer } from '~/utils/station-search'
import { DateTime } from 'luxon'
import { isPlaceQuery, ODBL_URL, OSM_COPYRIGHT_URL, PHOTON_URL, photonLang } from '#shared/utils/places'
import { PLACE_NETWORK, placeOf } from '~/composables/usePlace'
import { readChoices } from '~/utils/ask/chip'
import { coordinatesText, hemispheresOf, mapAtPoint, parseCoordinates } from '~/utils/coordinates'
import { countsByGroup, filterGroups, GROUP_LIMITS, itemOfHit, limitCounted, limitItems, orderGroups } from '~/utils/palette'
import { EXTERNAL, HOME, LEGAL, MAP_TOOL, PROJECT, REFERENCE, TOOLS } from '~/utils/sections'
import { itemOfIdRow, itemOfStation, moreStationsLink, parseStationId, sortedIdRows, STATION_NETWORKS } from '~/utils/station-hits'

// The command palette of the search (GH-3518), inside the dialog of AppSearch.vue. One field that goes to every page
// (each with the line that says what it is for), to a provider's page, to the forecast of a station found by its
// name or to the map opened on it (GH-3650), and that changes the theme or the language.
//
// The WAI-ARIA combobox pattern with a listbox popup: the field is the combobox and keeps the focus; the arrow keys
// move the active option (`aria-activedescendant`), Enter takes it, and a click takes the one under the pointer. The
// dialog around it holds the focus, closes on Escape and gives the focus back to what opened it. How many results
// there are is said in a polite live region. The list is the one scrolling box, and takes the focus by Tab too, so a
// keyboard can scroll it (WCAG 2.1.1); there its keys are the field's.
//
// The stations (GH-3790) are looked for by name in the lists the reader chose in the settings ("Stations in the search"), from three letters
// on and a moment after the last key, and the browser never downloads a list for it. The forecast's points (DWD MOSMIX) are asked of the
// backend by name (`GET /api/stations?name=`, its best five), as they always were. NOAA GHCN daily (133k stations) and, where the reader
// turned them on, DWD's measuring stations are matched by the app's own server (`GET /_search/stations?q=&lists=`, `server/utils/stationSearch.ts`),
// which keeps them in memory (the GHCN one is the list of the map's own route) and answers the best few of each with how many there are. Each
// list is a group, each result names the provider and the network and leads to the map with the station picked, and a last option leads to
// the map's own search. A WMO number (five digits), a WIGOS identifier or an ICAO code typed in is also offered, never run on its own, to
// every network at once whatever the settings say (`GET /api/station-ids`, which reads about 30 MB of station lists, 9 s cold): Enter on
// "Search all networks for ..." runs it and the stations it finds are listed as a group, each leading to the map where it shows the
// network and else to the Explorer. The rest is matched here (utils/palette.ts).
//
// The places (GH-3790, GH-3791) are looked for by name from three letters on, 400 ms after the last key, by the app's own server, which asks Photon
// (photon.komoot.io, OpenStreetMap's data) for them (`GET /_search/places?q=&lang=`, `server/utils/placesSearch.ts`): the reader's browser
// never reaches komoot, so its address does not. They are a group of their own, after a point that is typed in, each leading to the map at that
// point, which picks the station nearest to it; the group is shown with the credit that OpenStreetMap's licence asks for, and with "via Photon".
// A position or a text with no letter is no name and is not sent. Where the operator has switched the search of places off, the server says so
// and the palette asks no more and shows no group.
//
// The words of the app (GH-3790) are matched here too, in the browser: a full-text index of the pages built with the app
// (`modules/search-index`), the glossary the backend gives, the questions of "Ask the weather" and a position typed in
// (`utils/coordinates.ts`). All of it is loaded when the search is opened, not before (`useSiteSearch`). Each kind is a
// group that shows a few results and, where its page has more, a last option that opens the page. The order of the groups
// is `GROUP_ORDER` of utils/palette.ts: a point, the stations, the rest.
//
// In its place mode (`mode="place"`, the home page's "Ask the weather") it is the same field and list for one thing
// only: the place the questions are about. It lists DWD's measuring stations by name (from two letters on), a station
// that has stopped reporting long ago left out, and choosing one makes it the reader's place (composables/usePlace.ts).
const props = withDefaults(defineProps<{
  mode?: 'search' | 'place'
}>(), { mode: 'search' })
const emit = defineEmits<{ done: [], place: [place: Place] }>()

const { t, locale, setLocale } = useI18n()
const colorMode = useColorMode()
const { data: providerList } = useProviders()
const { questionText } = useQuestions()
// the words of the app are for the search; the place of the questions asks for stations only
const site = props.mode === 'place' ? null : useSiteSearch()

const query = ref('')
const activeIndex = ref(0)
const listId = useId()

const placeMode = computed(() => props.mode === 'place')
const MIN_STATION_QUERY = computed(() => placeMode.value ? 2 : 3)
const { setPlace } = usePlace()
/** The places of the questions (the place mode): the backend's matches of DWD's measuring stations */
const stations = ref<Station[]>([])
/** The stations of the lists the reader chose that the search finds by name (the search mode): the forecast's points of the backend, the others as the app's server matched them (GH-3790) */
const stationAnswer = shallowRef<StationSearchAnswer | null>(null)
const stationsPending = ref(false)
const stationsFailed = ref(false)
let stationTicket = 0
// a search typed just before the dialog closed asks for nothing once it is gone
let closed = false
/** The request for the stations in flight, and the timer that asks again for a list that is still being read */
let nameSearch: AbortController | null = null
let nameRetry: ReturnType<typeof setTimeout> | undefined
/** How long the search waits before it asks the server again for a network whose list is still being read (GHCN daily's is 3 s when the backend is warm, a minute when it is not), and how often */
const RETRY_AFTER_MS = 3000
const MAX_RETRIES = 25
/** The search of every network for an id in flight */
let idSearchRequest: AbortController | null = null
/** The places of the text, as the app's server found them (`GET /_search/places`), and the request for them in flight */
const places = shallowRef<PlaceMatch[]>([])
const placesFailed = ref(false)
let placesTicket = 0
let placesRequest: AbortController | null = null
/** Where the operator has switched the search of places off, the server says so once and the visit asks no more */
const placesOff = useState('places-search-off', () => false)
/** How long the search of places waits after the last key: longer than the stations', since every text asked for is a request to a service of a third party */
const PLACES_DEBOUNCE_MS = 400
onBeforeUnmount(() => {
  closed = true
  nameSearch?.abort()
  idSearchRequest?.abort()
  placesRequest?.abort()
  clearTimeout(nameRetry)
})

/** The lists of stations the reader chose in the settings ("Stations in the search", GH-3790), which are the ones asked for */
const { settings } = useSettings()
/** The forecast's points are asked of the backend by name, as they always were; the lists of the other two are the app server's, which is told which */
const SERVED = ['measured', 'ghcn'] as const

/** The best few stations of the forecast's points for a text, from the backend's own search by name (its best five): null where it could not be asked */
async function forecastStations(text: string, signal: AbortSignal): Promise<StationMatch[] | null> {
  try {
    const answer = await $fetch<{ stations: Station[] }>('/api/stations', {
      query: { provider: 'dwd', network: 'mosmix', parameters: 'hourly/large', name: text },
      signal,
      retry: 0,
      ...API_ANSWER,
    })
    return (answer.stations ?? []).slice(0, 5).map(station => ({
      station_id: station.station_id,
      name: station.name ?? null,
      latitude: station.latitude ?? 0,
      longitude: station.longitude ?? 0,
      wmo_id: station.wmo_id ?? null,
      first_year: null,
      last_year: null,
      reporting: true,
    }))
  }
  catch {
    return null
  }
}

/** The best few stations of the lists of the app's server that were chosen for a text, or null where it could not be asked */
async function servedStations(text: string, lists: string[], signal: AbortSignal): Promise<StationSearchAnswer | null> {
  try {
    return await $fetch<StationSearchAnswer>('/_search/stations', { query: { q: text, limit: GROUP_LIMITS.stations! + 1, lists: lists.join(',') }, signal, retry: 0, ...API_ANSWER })
  }
  catch {
    return null
  }
}

/**
 * Asks for the best stations of the lists the reader chose (the search mode): the forecast's points of the backend, the others of the
 * app's server, each at once; a list of the server that is still being read is asked for again after a pause, and after the last attempt
 * it is one that could not be read. A list that is not chosen is not asked for.
 */
async function searchNames(text: string, ticket: number, attempt = 0, forecast?: StationMatch[] | null) {
  nameSearch?.abort()
  const controller = nameSearch = new AbortController()
  const chosen = settings.value.searchStations
  const served = SERVED.filter(list => chosen[list])
  const wantsForecast = chosen.forecast
  // the forecast's answer of the first attempt is kept for the ones that follow: only the lists of the server are asked for again
  const forecastAsked = wantsForecast ? (attempt === 0 ? forecastStations(text, controller.signal) : Promise.resolve(forecast ?? null)) : Promise.resolve(undefined)
  const servedAsked = served.length ? servedStations(text, served, controller.signal) : Promise.resolve(undefined)
  /** Whether the answer is still wanted: not given up for a newer text, nor the dialog gone */
  const wanted = () => ticket === stationTicket && !controller.signal.aborted

  /** Makes what is known of the answer the one that is shown: `own` is undefined where the server's lists are not asked for or are still being read (`waiting`) */
  function publish(mosmix: StationMatch[] | null | undefined, own: StationSearchAnswer | null | undefined, waiting: boolean) {
    const failed: SearchNetwork[] = [...(own === null ? served : own?.failed ?? []), ...(mosmix === null ? ['forecast' as const] : [])]
    // the lists of the server that have not answered yet are still being read
    const pending: SearchNetwork[] = waiting ? [...served] : own?.pending ?? []
    // everything that was asked for could not be: no answer, which is said
    if ((!wantsForecast || mosmix === null) && (!served.length || own === null)) {
      stationAnswer.value = null
      stationsFailed.value = true
      return pending
    }
    stationsFailed.value = false
    const networks: StationSearchAnswer['networks'] = []
    if (mosmix && mosmix.length)
      networks.push({ network: 'forecast', total: mosmix.length, stations: mosmix })
    networks.push(...(own?.networks ?? []))
    const retrying = waiting || (pending.length > 0 && attempt < MAX_RETRIES)
    stationAnswer.value = {
      query: text,
      networks,
      pending: retrying ? pending : [],
      // a list that is still not there after the last attempt is one that could not be read, which is said, and which a new text asks for again
      failed: retrying ? failed : [...failed, ...pending],
    }
    return pending
  }

  if (!wantsForecast && !served.length) {
    stationAnswer.value = null
    stationsFailed.value = false
    stationsPending.value = false
    return
  }
  // the forecast's points are the backend's and answer at once: they are shown as soon as they are there, and not held behind the server's
  // wait for a list that is being read (5 s for GHCN daily on a cold start)
  let mosmix: StationMatch[] | null | undefined
  if (served.length && wantsForecast && attempt === 0) {
    mosmix = await forecastAsked
    if (ticket !== stationTicket)
      return
    stationsPending.value = false
    if (controller.signal.aborted)
      return
    publish(mosmix, undefined, true)
  }
  const [forecastDone, own] = await Promise.all([forecastAsked, servedAsked])
  mosmix = forecastDone
  if (ticket !== stationTicket)
    return
  stationsPending.value = false
  if (!wanted())
    return
  const pending = publish(mosmix, own, false)
  if (pending.length > 0 && attempt < MAX_RETRIES)
    nameRetry = setTimeout(() => void (!closed && ticket === stationTicket && searchNames(text, ticket, attempt + 1, mosmix)), RETRY_AFTER_MS)
}

// a key that changes what is asked gives up what is in flight for the text before it: the answer is no longer wanted
watch(query, () => {
  nameSearch?.abort()
  placesRequest?.abort()
  clearTimeout(nameRetry)
})

watchDebounced(query, async (value) => {
  const ticket = ++placesTicket
  placesRequest?.abort()
  const text = value.trim()
  // a text that is a position or has no letter is no name of a place, and is not sent to anybody
  if (closed || placeMode.value || placesOff.value || !isPlaceQuery(text) || parseCoordinates(text, hemispheresOf(locale.value))) {
    places.value = []
    placesFailed.value = false
    return
  }
  const controller = placesRequest = new AbortController()
  try {
    const answer = await $fetch<PlacesAnswer>('/_search/places', { query: { q: text, lang: photonLang(locale.value) }, signal: controller.signal, retry: 0, ...API_ANSWER })
    if (ticket !== placesTicket || controller.signal.aborted)
      return
    if (answer.state === 'off')
      placesOff.value = true
    places.value = answer.state === 'off' ? [] : answer.places
    placesFailed.value = false
  }
  catch {
    // a failure leaves the rest of the search as it is, and is said in the live region; the next text asks again
    if (ticket === placesTicket && !controller.signal.aborted) {
      places.value = []
      placesFailed.value = true
    }
  }
}, { debounce: PLACES_DEBOUNCE_MS })

watchDebounced(query, async (value) => {
  if (closed)
    return
  const text = value.trim()
  const ticket = ++stationTicket
  if (text.length < MIN_STATION_QUERY.value) {
    stations.value = []
    stationAnswer.value = null
    stationsPending.value = false
    // a failure was of the text before: the text now is a hint, announced as one
    stationsFailed.value = false
    return
  }
  stationsPending.value = true
  stationsFailed.value = false
  if (!placeMode.value) {
    await searchNames(text, ticket)
    return
  }
  try {
    const answer = await $fetch<{ stations: Station[] }>('/api/stations', { query: { ...PLACE_NETWORK, name: text }, ...API_ANSWER })
    if (ticket === stationTicket) {
      // a station that stopped reporting years ago has no recent weather to ask about
      const recent = Date.now() - 2 * 365 * 86_400_000
      stations.value = (answer.stations ?? []).filter(station => !station.end_timestamp || Date.parse(station.end_timestamp) > recent).slice(0, 8)
    }
  }
  catch {
    // a station search that fails leaves the pages and actions to choose from
    if (ticket === stationTicket) {
      stations.value = []
      stationsFailed.value = true
    }
  }
  finally {
    if (ticket === stationTicket)
      stationsPending.value = false
  }
}, { debounce: 300 })

function page(section: { key: string, to: string, label: string, icon: string, description?: string, tile?: string }, external = false): PaletteItem {
  return {
    id: section.key,
    label: t(section.label),
    description: section.description ? t(section.description) : undefined,
    icon: section.icon,
    tile: section.tile,
    to: section.to,
    external,
  }
}

const THEMES = [
  { value: 'system', label: 'settings.themeSystem', icon: 'i-ph-monitor' },
  { value: 'light', label: 'settings.themeLight', icon: 'i-ph-sun' },
  { value: 'dark', label: 'settings.themeDark', icon: 'i-ph-moon' },
] as const

function choosePlace(place: Place) {
  setPlace(place)
  emit('place', place)
}

// ---- the groups ----------------------------------------------------------------------------------------------------

/** What is typed, for the words of the app */
const text = computed(() => query.value.trim())
/** A position typed in, with the letters this language writes the hemispheres with */
const point = computed(() => text.value ? parseCoordinates(text.value, hemispheresOf(locale.value)) : null)

const placeGroup = computed<PaletteGroup[]>(() => point.value
  ? [{
      id: 'place',
      label: t('shell.placeGroup'),
      items: [{
        id: 'place-point',
        label: coordinatesText(point.value),
        description: t('shell.placeOnMap'),
        icon: MAP_TOOL.icon,
        tile: MAP_TOOL.tile,
        to: mapAtPoint(point.value),
      }],
    }]
  : [])

/** The places OpenStreetMap has for the text, each leading to the map at its point, which picks the nearest station there (GH-3791) */
const osmPlacesGroup = computed<PaletteGroup[]>(() => {
  if (placeMode.value || placesOff.value || !places.value.length || !isPlaceQuery(text.value))
    return []
  return [{
    id: 'places-osm',
    label: t('shell.placesGroup'),
    items: places.value.map(place => ({
      id: `place-osm-${place.id}`,
      label: place.name,
      description: [t(`shell.placeKinds.${place.kind}`), place.region].filter(Boolean).join(' · '),
      icon: 'i-ph-map-pin',
      to: mapAtPoint({ latitude: place.latitude, longitude: place.longitude }),
    })),
  }]
})

/** The icon of each kind of result of the app's own words: the page's, as the reference and the project show it */
const HIT_ICONS: Record<string, string> = {
  measurement: 'i-ph-ruler',
  method: 'i-ph-seal-check',
  glossary: 'i-ph-book-open-text',
  settings: 'i-ph-gear-six',
  about: 'i-ph-info',
  support: 'i-ph-heart',
}

/** The last item of a group that shows a few of more: it opens the page that has them all */
function moreItem(id: string, page: string, to: string) {
  return (hidden: number): PaletteItem => ({ id: `more-${id}`, label: t('shell.moreIn', { count: hidden, page }), icon: 'i-ph-arrow-right', to, more: true })
}

/** The few results of a kind, from the entries of the pages (`useSiteSearch`) */
function wordGroup(id: string, label: string, hits: Hit[], more: (hidden: number) => PaletteItem): PaletteGroup {
  return { id, label, items: limitItems(hits.map(hit => itemOfHit(hit, HIT_ICONS[hit.kind] ?? 'i-ph-arrow-right')), GROUP_LIMITS[id] ?? 3, more) }
}

/** The words of the app that answer what is typed: the entries and methods, the glossary, the settings; none before a word is typed */
const wordGroups = computed<PaletteGroup[]>(() => {
  if (!site || !text.value)
    return []
  const pages = site.findPages(text.value)
  const of = (...kinds: string[]) => pages.filter(hit => kinds.includes(hit.kind))
  return [
    wordGroup('measurement', t('measurement.title'), of('measurement'), moreItem('measurement', t('measurement.title'), '/measurement')),
    wordGroup('method', t('methods.title'), of('method'), moreItem('method', t('methods.title'), '/methods')),
    wordGroup('glossary', t('glossary.title'), site.findGlossary(text.value), moreItem('glossary', t('glossary.title'), `/glossary?q=${encodeURIComponent(text.value)}`)),
    wordGroup('settings', t('common.settings'), of('settings'), moreItem('settings', t('common.settings'), '/settings')),
  ]
})

/** The questions of "Ask the weather", worded for the place the reader has chosen; each opens its question on the home page */
const questionItems = computed<PaletteItem[]>(() => {
  if (!site || !text.value)
    return []
  const now = DateTime.now()
  return site.chips.value.map(chip => ({
    id: `question-${chip.id}`,
    label: questionText(chip, readChoices(chip, {}, now)),
    description: t(chip.from),
    keywords: chip.id,
    icon: chip.icon,
    to: `/?ask=${chip.id}`,
  }))
})

/** What of the pages the search lists in a group of its own, matched here by `scoreOf` */
const pageGroups = computed<PaletteGroup[]>(() => {
  const searching = query.value.trim().length > 0
  return [
    { id: 'tools', label: t('shell.tools'), items: TOOLS.map(section => page(section)) },
    { id: 'questions', label: t('ask.title'), items: questionItems.value },
    { id: 'reference', label: t('shell.reference'), items: REFERENCE.map(section => page(section)) },
    {
      id: 'providers',
      label: t('nav.providers'),
      // by name, once something is typed: the 23 of them are a page of their own
      items: searching
        ? (providerList.value?.providers ?? []).map(provider => ({
            id: `provider-${provider.provider}`,
            label: provider.name_short,
            description: provider.name_english,
            keywords: `${provider.provider} ${provider.country ?? ''} ${provider.name_local ?? ''}`,
            icon: 'i-ph-buildings',
            to: `/providers/${provider.provider}`,
          }))
        : [],
    },
    {
      id: 'project',
      label: t('shell.project'),
      items: [HOME, ...PROJECT, ...LEGAL].map(section => page(section)).concat(EXTERNAL.map(link => page(link, true))),
    },
    {
      id: 'theme',
      label: t('settings.theme'),
      items: THEMES.map(theme => ({
        id: `theme-${theme.value}`,
        label: t(theme.label),
        keywords: t('settings.theme'),
        icon: theme.icon,
        current: colorMode.preference === theme.value,
        run: () => {
          colorMode.preference = theme.value
        },
      })),
    },
    {
      id: 'language',
      label: t('settings.language'),
      items: LANGUAGES.map(language => ({
        id: `language-${language.value}`,
        label: language.name,
        keywords: `${language.value} ${t('settings.language')}`,
        icon: 'i-ph-translate',
        current: locale.value === language.value,
        run: () => {
          void setLocale(language.value as typeof locale.value)
        },
      })),
    },
  ]
})

// ---- the stations (GH-3790) ----------------------------------------------------------------------------------------

/** What the lines of a station say, in the reader's language */
const stationWords = computed(() => ({
  network: (network: SearchNetwork) => t(`shell.stationNetworks.${network}`),
  ended: (year: number) => t('shell.stationEnded', { year }),
}))
const STATION_HEADINGS = { forecast: 'shell.stationsForecast', measured: 'shell.stationsMeasured', ghcn: 'shell.stationsGhcn' } as const
/** The icons the map's layers have in its panel */
const STATION_ICONS = { forecast: 'i-ph-sun', measured: 'i-ph-thermometer-simple', ghcn: 'i-ph-globe-hemisphere-west' } as const
const LAYER_LABELS = { forecast: 'mapTool.layerForecast', measured: 'mapTool.layerMeasured', ghcn: 'mapTool.layerGhcn' } as const

// the stations are the server's matches already, as the places are; the pages and actions are matched here
const stationGroups = computed<PaletteGroup[]>(() => {
  const answer = stationAnswer.value
  if (!answer || !text.value)
    return []
  return answer.networks.map((found) => {
    const info = STATION_NETWORKS[found.network]
    const items = found.stations.map(station => itemOfStation(found.network, station, stationWords.value, STATION_ICONS[found.network]))
    const more = (hidden: number): PaletteItem => ({
      id: `more-${info.group}`,
      label: t('shell.moreOnMap', { count: hidden, network: t(LAYER_LABELS[found.network]) }),
      icon: 'i-ph-arrow-right',
      to: moreStationsLink(found.network, answer.query),
      more: true,
    })
    // the backend's search by name gives its best five and no count: they are all shown, and the map's own search has the rest
    const shown = found.network === 'forecast' ? items : limitCounted(items, found.total, GROUP_LIMITS.stations!, more)
    return { id: info.group, label: t(STATION_HEADINGS[found.network]), items: shown }
  })
})

/** What is typed, where it is an id of WMO's or ICAO's schemes: offered to every network, not run for it */
const typedId = computed(() => placeMode.value ? null : parseStationId(text.value))
/** The search of every network for an id: running, answered (with the stations, maybe none) or failed */
interface IdSearch {
  id: string
  status: 'running' | 'done' | 'failed'
  rows: StationIdsStation[]
}
const idSearch = shallowRef<IdSearch | null>(null)
const explorerTool = TOOLS.find(tool => tool.key === 'explorer')

async function searchAllNetworks(typed: TypedStationId) {
  idSearchRequest?.abort()
  const controller = idSearchRequest = new AbortController()
  idSearch.value = { id: typed.id, status: 'running', rows: [] }
  try {
    const answer = await $fetch<StationIdsResponse>('/api/station-ids', { query: { [typed.param]: typed.id }, signal: controller.signal, retry: 0, ...API_ANSWER })
    if (controller.signal.aborted)
      return
    idSearch.value = { id: typed.id, status: 'done', rows: sortedIdRows(answer.stations ?? []) }
  }
  catch {
    if (!controller.signal.aborted)
      idSearch.value = { id: typed.id, status: 'failed', rows: [] }
  }
}

// a text that is no longer the id that was searched for gives up the search, and its stations are gone with it
watch(typedId, (typed) => {
  if (idSearch.value && idSearch.value.id !== typed?.id) {
    idSearchRequest?.abort()
    idSearch.value = null
  }
})

/**
 * The group of the search of every network for the id that is typed, or of the stations it found. Four letters are a word as often as a code
 * (`wind`, `kiel`, `dark`): where they are not typed in capitals, as a code is, the offer for them is made only where nothing else answers the
 * text, once the stations and the index of the words are in; and it follows what else is found, so that Enter is never taken for it.
 *
 * @param others - How many results the text has apart from this group
 * @param settled - Whether the stations and the words of the text have been looked for
 */
function idGroupsFor(others: number, settled: boolean): PaletteGroup[] {
  const typed = typedId.value
  if (!typed)
    return []
  const search = idSearch.value?.id === typed.id ? idSearch.value : null
  if (!search && typed.kind === 'icao' && typed.id !== text.value && !(settled && others === 0))
    return []
  const label = t('shell.stationsWithId', { id: typed.id })
  if (search?.status === 'done' && search.rows.length) {
    const providers = new Map((providerList.value?.providers ?? []).map(provider => [provider.provider, provider.name_short]))
    const words = (provider: string) => ({ provider: providers.get(provider) ?? provider.toUpperCase(), network: stationWords.value.network, opensExplorer: t('shell.opensExplorer') })
    return [{
      id: 'station-ids',
      label,
      items: search.rows.map(row => itemOfIdRow(row, words(row.provider), { map: MAP_TOOL.icon, explorer: explorerTool?.icon ?? 'i-ph-arrow-right' })),
    }]
  }
  const hint = !search
    ? t('shell.searchAllNetworksHint')
    : search.status === 'running'
      ? t('shell.searchingAllNetworks')
      : search.status === 'failed' ? t('shell.allNetworksFailed') : t('shell.allNetworksNone', { id: typed.id })
  return [{
    id: typed.kind === 'icao' ? 'station-ids-icao' : 'station-ids',
    // what it is, until it has found stations: a group of one option that asks every network
    label: t('shell.allNetworksGroup'),
    items: [{
      id: 'station-ids-search',
      label: t('shell.searchAllNetworks', { id: typed.id }),
      description: hint,
      icon: 'i-ph-globe-hemisphere-west',
      keepOpen: true,
      run: () => void searchAllNetworks(typed),
    }],
  }]
}

const placesGroup = computed<PaletteGroup>(() => ({
  id: 'places',
  label: t('ask.placesGroup'),
  items: stations.value
    .map(placeOf)
    .filter((place): place is Place => place !== null)
    .map(place => ({
      id: `place-${place.id}`,
      label: place.name,
      description: place.region ?? undefined,
      icon: 'i-ph-map-pin',
      run: () => choosePlace(place),
    })),
}))

const shown = computed<PaletteGroup[]>(() => {
  // the places are the backend's matches, as they are
  if (placeMode.value)
    return [placesGroup.value].filter(group => group.items.length)
  const matched = filterGroups(pageGroups.value, query.value)
  // the cards of About and Support, found by their words, are with the pages of the project
  const cards = site && text.value ? site.findPages(text.value).filter(hit => hit.kind === 'about' || hit.kind === 'support').map(hit => itemOfHit(hit, HIT_ICONS[hit.kind]!)) : []
  if (cards.length) {
    const project = matched.find(group => group.id === 'project')
    const items = limitItems(cards, GROUP_LIMITS.project!)
    if (project)
      project.items = [...project.items, ...items]
    else
      matched.push({ id: 'project', label: t('shell.project'), items })
  }
  const found = [...placeGroup.value, ...osmPlacesGroup.value, ...stationGroups.value, ...matched, ...wordGroups.value]
  const settled = !stationsPending.value && !site?.loading.value && !stationAnswer.value?.pending.length
  return orderGroups([...found, ...idGroupsFor(found.reduce((sum, group) => sum + group.items.length, 0), settled)])
})
const flat = computed(() => shown.value.flatMap(group => group.items))
const optionId = (item: PaletteItem) => `${listId}-${item.id}`
const active = computed(() => flat.value[Math.min(activeIndex.value, flat.value.length - 1)])
const activeId = computed(() => active.value ? optionId(active.value) : undefined)

watch(query, () => {
  activeIndex.value = 0
})
// The places come after a pause and an answer, and lead the list: the option the reader is on stays that option (under them) where only places were added or
// changed, so that an Enter pressed as they arrive takes what was under the highlight and not the place that pushed it down.
watch(flat, (list, old) => {
  const isPlace = (item: PaletteItem) => item.id.startsWith('place-osm-')
  const others = (items: PaletteItem[]) => items.filter(item => !isPlace(item)).map(item => item.id).join('\n')
  if (!old.length || others(list) !== others(old))
    return
  const previous = old[Math.min(activeIndex.value, old.length - 1)]
  const at = previous ? list.findIndex(item => item.id === previous.id) : -1
  if (at !== -1)
    activeIndex.value = at
})
// the stations that the search of every network found are what the reader asked for: the first of them is the active option
watch(idSearch, async (search) => {
  if (search?.status !== 'done' || !search.rows.length)
    return
  await nextTick()
  const first = flat.value.findIndex(item => item.id.startsWith('station-id-'))
  if (first !== -1)
    activeIndex.value = first
})
watch(activeId, async (id) => {
  await nextTick()
  if (id)
    document.getElementById(id)?.scrollIntoView({ block: 'nearest' })
})

const status = computed(() => {
  if (stationsPending.value)
    return placeMode.value ? t('ask.placeSearching') : t('common.loading')
  if (placeMode.value) {
    if (stationsFailed.value)
      return t('ask.placeFailed')
    return query.value.trim().length < MIN_STATION_QUERY.value ? t('ask.placeHint') : t('shell.resultsCount', flat.value.length)
  }
  // the search of every network for an id takes seconds: said while it runs, and again when it is done by the count of what it found
  if (idSearch.value?.status === 'running' && idSearch.value.id === typedId.value?.id)
    return t('shell.searchingAllNetworks')
  // what is typed is searched when the index of the pages is there (GH-3790)
  if (text.value && site?.loading.value && !flat.value.length)
    return t('common.loading')
  // the count of the results, not of the "more" options that lead on from a group, then how many each group has
  const count = t('shell.resultsCount', flat.value.filter(item => !item.more).length)
  const typed = text.value.length
  const groupsSaid = typed > 0 && flat.value.length ? `${count}. ${countsByGroup(shown.value, (group, number) => t('shell.resultsIn', { group, count: number }))}` : count
  const said = typed > 0 && typed < MIN_STATION_QUERY.value ? `${groupsSaid}. ${t('shell.stationsHint')}` : groupsSaid
  // a list of stations that is still being read, or could not be, is said: the results may grow, or lack a network's
  const answer = typed >= MIN_STATION_QUERY.value ? stationAnswer.value : null
  // places that could not be searched for are said as well, whatever else the text found
  const placesSaid = placesFailed.value && isPlaceQuery(text.value) ? `. ${t('shell.placesFailed')}` : ''
  if (answer?.pending.length)
    return `${said}. ${t('shell.stationListReading')}${placesSaid}`
  return `${stationsFailed.value || answer?.failed.length ? `${said}. ${t('shell.stationListFailed')}` : said}${placesSaid}`
})

/** Whether the places are shown, which is when their credit is: OpenStreetMap's licence asks for it with the data, and Photon is named as the way to it */
const showsPlaces = computed(() => shown.value.some(group => group.id === 'places-osm'))

const emptyText = computed(() => {
  if (!placeMode.value)
    return t('shell.searchEmpty')
  return query.value.trim().length < MIN_STATION_QUERY.value ? t('ask.placeHint') : stationsPending.value ? t('ask.placeSearching') : stationsFailed.value ? t('ask.placeFailed') : t('shell.searchEmpty')
})

function choose(item: PaletteItem | undefined) {
  if (!item)
    return
  // an action that works on, as the search of every network does, leaves the search open to show what it finds
  if (!item.keepOpen)
    emit('done')
  if (item.run)
    item.run()
  else if (item.external && item.to)
    window.open(item.to, '_blank', 'noopener')
  else if (item.to)
    void navigateTo(item.to)
}

function onKeydown(event: KeyboardEvent) {
  const count = flat.value.length
  if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
    event.preventDefault()
    if (count)
      activeIndex.value = (activeIndex.value + (event.key === 'ArrowDown' ? 1 : -1) + count) % count
  }
  else if (event.key === 'PageDown' || event.key === 'PageUp') {
    event.preventDefault()
    if (count)
      activeIndex.value = Math.max(0, Math.min(count - 1, activeIndex.value + (event.key === 'PageDown' ? 5 : -5)))
  }
  else if (event.key === 'Enter' && !event.isComposing) {
    event.preventDefault()
    choose(active.value)
  }
}

// no focus of its own here: the dialog puts it on the field, its first stop, once it has noted what had it before,
// which is where it goes back to on Escape
</script>

<template>
  <div class="flex min-h-0 flex-1 flex-col">
    <div class="flex items-center gap-3 border-b border-default px-4 py-1">
      <UIcon name="i-ph-magnifying-glass" class="size-5 shrink-0 text-muted" />
      <input
        v-model="query"
        type="text"
        role="combobox"
        autocomplete="off"
        spellcheck="false"
        aria-autocomplete="list"
        :aria-label="placeMode ? t('ask.placeDialogTitle') : t('shell.search')"
        :aria-expanded="flat.length > 0"
        :aria-controls="flat.length ? listId : undefined"
        :aria-activedescendant="activeId"
        :placeholder="placeMode ? t('ask.placePlaceholder') : t('shell.searchPlaceholder')"
        class="palette-input -ms-2 h-12 min-w-0 flex-1 bg-transparent px-2 text-base text-highlighted placeholder:text-dimmed"
        @keydown="onKeydown"
      >
      <!-- the way out for a touch screen reader, which cannot reach the overlay a sighted reader taps -->
      <UButton
        icon="i-ph-x"
        color="neutral"
        variant="ghost"
        size="sm"
        :aria-label="t('common.close')"
        data-testid="palette-close"
        @click="emit('done')"
      />
    </div>

    <div
      v-if="flat.length"
      :id="listId"
      role="listbox"
      tabindex="0"
      :aria-label="t('shell.results')"
      :aria-activedescendant="activeId"
      class="min-h-0 flex-1 overflow-y-auto overscroll-contain p-2"
      @keydown="onKeydown"
    >
      <div v-for="group in shown" :key="group.id" role="group" :aria-labelledby="`${listId}-group-${group.id}`">
        <div :id="`${listId}-group-${group.id}`" role="presentation" class="px-3 pb-1 pt-3 text-xs font-bold uppercase tracking-wider text-muted">
          {{ group.label }}
        </div>
        <div
          v-for="item in group.items"
          :id="optionId(item)"
          :key="item.id"
          role="option"
          :aria-selected="item === active"
          class="palette-option"
          @pointermove="activeIndex = flat.indexOf(item)"
          @click="choose(item)"
        >
          <ToolTile v-if="item.tile" :tile="item.tile as Tile" :icon="item.icon ?? ''" size="2rem" />
          <span v-else class="grid size-8 shrink-0 place-items-center rounded-lg bg-elevated" aria-hidden="true">
            <UIcon :name="item.icon ?? 'i-ph-arrow-right'" class="size-[1.125rem] text-toned" />
          </span>
          <span class="min-w-0 flex-1">
            <span class="block truncate font-semibold text-highlighted">{{ item.label }}</span>
            <span v-if="item.description" class="block truncate text-sm text-muted">{{ item.description }}</span>
          </span>
          <UIcon v-if="item.current" name="i-ph-check-bold" class="size-4 shrink-0 text-primary" />
          <UIcon v-else-if="item.external" name="i-ph-arrow-up-right" class="size-4 shrink-0 text-muted" />
          <UIcon v-else name="i-ph-arrow-elbow-down-left" class="palette-enter size-4 shrink-0 text-muted" />
        </div>
      </div>
    </div>
    <p v-else class="flex-1 px-6 py-10 text-center text-muted">
      {{ emptyText }}
    </p>

    <!-- the credit of the places (OpenStreetMap's licence, ODbL) and the service that found them, with the group (GH-3791) -->
    <i18n-t
      v-if="showsPlaces"
      keypath="shell.placesCredit"
      tag="p"
      scope="global"
      data-testid="places-credit"
      class="border-t border-default px-4 py-2 text-xs text-muted"
    >
      <template #osm>
        <a :href="OSM_COPYRIGHT_URL" target="_blank" rel="noopener noreferrer" class="underline underline-offset-2">© OpenStreetMap contributors</a>
      </template>
      <template #licence>
        <a :href="ODBL_URL" target="_blank" rel="noopener noreferrer" class="underline underline-offset-2">ODbL</a>
      </template>
      <template #photon>
        <a :href="PHOTON_URL" target="_blank" rel="noopener noreferrer" class="underline underline-offset-2">Photon</a>
      </template>
    </i18n-t>

    <div class="flex items-center justify-between gap-4 border-t border-default px-4 py-2.5 text-xs text-muted">
      <p role="status" aria-live="polite" class="min-w-0">
        {{ status }}
      </p>
      <p class="shrink-0 max-sm:hidden" aria-hidden="true">
        {{ t('shell.keysHint') }}
      </p>
    </div>
  </div>
</template>

<style>
/* the field keeps the app's focus ring, drawn inside it so that it lies on the dialog's own colour */
.palette-input:focus-visible {
  outline-offset: -2px;
  border-radius: calc(var(--ui-radius) * 2);
}
.palette-option {
  position: relative;
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.5rem 0.75rem;
  border-radius: calc(var(--ui-radius) * 2.5);
  cursor: pointer;
}
.palette-option[aria-selected="true"] {
  background: var(--ui-bg-elevated);
  box-shadow: inset 3px 0 0 var(--ui-primary);
}
.palette-enter {
  visibility: hidden;
}
.palette-option[aria-selected="true"] .palette-enter {
  visibility: visible;
}
@media (forced-colors: active) {
  .palette-option[aria-selected="true"] {
    outline: 2px solid Highlight;
    outline-offset: -2px;
  }
}
</style>
