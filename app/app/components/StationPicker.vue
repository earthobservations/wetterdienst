<script setup lang="ts" generic="S extends StationPickerStation">
// The one way to pick stations, for the explorer, the history, the forecast and the stripes (GH-3877): a toggle
// "List | Map" over the one place where the choice is made, and the stations picked under it, so that a switch never
// hides what was chosen: for several stations as chips (each takes its station out), in both modes; for one station
// (the forecast, the stripes) the search shows it, so it is told once more only on the map, in one line, where there is
// no search (GH-4151). The list is the search field, the map is the map of the stations. A station picked in one
// shows in the other: both read the same `selected`.
//
// The picker holds no list of its own and fetches nothing: the caller hands it the stations, and learns by
// `update:open` (the search is open) and `update:mode` (the map is shown, which is also said once for the mode
// remembered) when it is worth fetching a list that is large. `multiple` is the explorer's and the history's
// choice of any number of stations; without it a pick replaces the one before, as the forecast and the stripes
// have it.
//
// An action that belongs beside the toggle goes in the `actions` slot.
//
// Places (GH-3791): with `places`, the search of the list also finds places by name (OpenStreetMap's, through the app's server, as the header's search does:
// from three letters, after a pause, never a position, with the credit under the list), in a group before the stations. A place is no station: choosing one
// is handed to the caller (`update:place`), which shows the stations closest to it and picks one. The list is then filtered here, the same way the
// menu does (accents and case apart), since the places are not the ones the menu's own filter would keep.
//
// "Use my location" (GH-3651): with `locate`, a row under the toggle offers to pick the station nearest to the reader
// (components/UseMyLocation.vue; the position is rounded to about 1 km, and asked for on the press alone). `locate` is
// the query of the `stations` request that is ranked by the position (`rank=1`: provider, network and parameters of
// the stations this picker lists), or `'list'` where the picker holds the whole list already (the stripes' stations
// have no ranking by position, and the list is at hand: nothing is sent). A station found is picked as a pick from the
// search would be (added for several, in place of the one before for one), and its distance is told.
import type { PlaceMatch } from '#shared/utils/places'
import type { Point } from '~/utils/map-tool'
import type { StationPickerStation } from '~/utils/station'
import type { StationPickerMode, StationPickerTool } from '~/utils/station-picker-mode'
import SegmentedControl from '~/components/SegmentedControl.vue'
import UseMyLocation from '~/components/UseMyLocation.vue'
import { distanceKm, formatDistance } from '~/utils/map-tool'
import { readStationPickerMode, writeStationPickerMode } from '~/utils/station-picker-mode'

const props = defineProps<{
  /** The tool whose picker it is: each remembers its own mode */
  tool: StationPickerTool
  /** Every station that can be picked */
  stations: S[]
  /** The stations picked, one at most without `multiple` */
  selected: S[]
  multiple?: boolean
  /** The list of the stations is on its way */
  loading?: boolean
  /** The list of the stations could not be fetched */
  error?: boolean
  /** The list was fetched and has no station */
  empty?: boolean
  /** A visible label of the choice (the stripes' "Station"): the search's own where the list is shown */
  label?: string
  /** The nearest station to the reader's position is offered: the query of the ranked `stations` request, or `'list'` */
  locate?: Record<string, string | undefined> | 'list'
  /** The search also finds places by name (GH-3791), which are handed over by `update:place` */
  places?: boolean
}>()

const emit = defineEmits<{
  'update:selected': [stations: S[]]
  /** The search is open (its menu is) */
  'update:open': [open: boolean]
  /** The mode shown: once on setup, for the one remembered, then for each change */
  'update:mode': [mode: StationPickerMode]
  /** A place was chosen in the search (with `places`): the caller finds the stations near it */
  'update:place': [place: PlaceMatch]
}>()

defineSlots<{
  /** What goes beside the toggle: an action on the choice, as one that picks a station for you */
  actions?: () => unknown
}>()

const { t, locale } = useI18n()
const { MapStations, notLoaded: mapNotLoaded } = useMapStations()

const mode = ref<StationPickerMode>(readStationPickerMode(props.tool))
watch(mode, value => emit('update:mode', value), { immediate: true })

const open = ref(false)
watch(open, value => emit('update:open', value))

const root = ref<HTMLElement | null>(null)
const panel = ref<HTMLElement | null>(null)
const panelId = useId()
const selectId = useId()
const selectedLineId = useId()

// the station a visible label leaves unnamed: the search of one station, which the label (not its text) names
const selectedForLabel = computed(() => !props.multiple && props.label && mode.value === 'list' ? props.selected[0] : undefined)

const modeOptions = computed(() => [
  { value: 'list' as const, label: t('stationSelection.modeList'), icon: 'i-ph-list-magnifying-glass' },
  { value: 'map' as const, label: t('stationSelection.modeMap'), icon: 'i-ph-map-trifold' },
])

const mapHint = computed(() => props.multiple ? t('stationSelection.mapHintMultiple') : t('stationSelection.mapHint'))

// What a screen reader is told about a change of mode that the reader made (the radio says which it is): what the
// search takes, or what a tap on the map does (not where the map's code could not be loaded, which says so itself).
// Nothing until the first change.
const changedByReader = ref(false)
const announcement = computed(() => {
  if (!changedByReader.value)
    return ''
  if (mode.value === 'list')
    return t('stationSelection.announceList')
  return mapNotLoaded.value ? '' : mapHint.value
})

// A map asked for by a switch that is not there yet (its code, and the list of the stations, are on their way) takes
// the focus as soon as it is
let focusMapWhenReady: FocusOptions | null = null

function focusMap(options?: FocusOptions) {
  const container = panel.value?.querySelector<HTMLElement>('.leaflet-container')
  if (container) {
    focusMapWhenReady = null
    container.focus(options)
  }
  else {
    focusMapWhenReady = options ?? {}
  }
}

function focusContent(options?: FocusOptions) {
  if (mode.value === 'map')
    focusMap(options)
  else
    panel.value?.querySelector<HTMLElement>('button')?.focus(options)
}

// The reader's own choice: remembered, announced, and (`onActivate`) the focus goes into what it shows
function setMode(value: StationPickerMode) {
  if (value === mode.value)
    return
  mode.value = value
  focusMapWhenReady = null
  open.value = false
  writeStationPickerMode(props.tool, value)
  changedByReader.value = true
}

// A click, or Enter or Space, on the toggle is a decision to use the mode: the focus goes into the search or the
// map. The arrow keys keep it on the toggle (`SegmentedControl`), to walk along it. A pointer's click does not scroll
// the page to what it focuses (`event.detail` is the number of clicks, 0 for a key): the reader is looking at it
async function onActivate(_value: StationPickerMode, event: MouseEvent) {
  await nextTick()
  focusContent({ preventScroll: event.detail > 0 })
}

// The map is there: it takes the focus a switch asked for, unless the reader has gone on since (the focus is in the
// picker or nowhere); the ask is dropped where it is not taken, and where the focus leaves the picker
function onMapReady() {
  if (!focusMapWhenReady)
    return
  const active = document.activeElement
  if (root.value?.contains(active) || active === document.body || active === null)
    focusMap(focusMapWhenReady)
  else
    focusMapWhenReady = null
}

function onFocusOut(event: FocusEvent) {
  const next = event.relatedTarget
  if (focusMapWhenReady && next instanceof Node && !root.value?.contains(next))
    focusMapWhenReady = null
}

// ---- what the search shows, and what it hands over ---------------------------------------------------------

const stationItems = computed(() => props.stations.map(station => ({ label: stationLabel(station), value: station.station_id })))

// the places (GH-3791): asked for by the text of the search, while the list is the search and not the map
const searchTerm = ref('')
const placesWanted = computed(() => !!props.places && mode.value === 'list')
const { places: placesFound, failed: placesFailed, off: placesOff } = usePlacesSearch(searchTerm, { enabled: placesWanted })
const PLACE_PREFIX = 'place:'
const placeItems = computed(() => !placesWanted.value || placesOff.value
  ? []
  : placesFound.value.map(place => ({
      label: place.name,
      description: [t(`shell.placeKinds.${place.kind}`), place.region].filter(Boolean).join(' · '),
      value: `${PLACE_PREFIX}${place.id}`,
      icon: 'i-ph-map-pin',
    })))
/** A text as the menu compares it: without accents and case */
const folded = (text: string) => text.normalize('NFD').replace(/\p{M}/gu, '').toLowerCase()
/** The stations the typed text keeps: with places the menu's own filter is off (it would drop a place whose name is not in the text), so it is made here */
const shownStations = computed(() => {
  const term = folded(searchTerm.value.trim())
  return !props.places || !term ? stationItems.value : stationItems.value.filter(item => folded(item.label).includes(term))
})
const items = computed(() => placeItems.value.length
  ? [{ type: 'label' as const, label: t('shell.placesGroup') }, ...placeItems.value, ...(shownStations.value.length ? [{ type: 'label' as const, label: t('stationSelection.stationsGroup') }, ...shownStations.value] : [])]
  : shownStations.value)

// A virtualised list draws a heading (a label of the menu) as a bare element with `aria-setsize` and `aria-posinset`, which no role allows (axe: aria-allowed-attr, critical),
// so the list that has places in it (and headings) is not virtualised: the text of three letters has already narrowed the stations to the ones it keeps.
// What a screen reader is told of the search (the menu has no count of its own): how many results the text has, a moment after the last key, and
// that the places could not be searched where they could not
const resultCount = computed(() => placeItems.value.length + shownStations.value.length)
const searchAnnounced = refDebounced(computed(() => {
  if (!props.places || !open.value || !searchTerm.value.trim())
    return ''
  return `${t('shell.resultsCount', resultCount.value)}${placesFailed.value ? `. ${t('shell.placesFailed')}` : ''}`
}), 600)

// The search's model: the picked stations as items, an array for several and one item (or none) for one
const selectedItems = computed({
  get: () => {
    const picked = props.selected.map(station => ({ label: stationLabel(station), value: station.station_id }))
    return props.multiple ? picked : picked[0]
  },
  set: (value: { label: string, value: string } | { label: string, value: string }[] | undefined) => {
    const chosen = Array.isArray(value) ? value : value ? [value] : []
    // a place is no pick of a station: it is handed over, and the pick stays as it was
    const place = chosen.find(item => item.value.startsWith(PLACE_PREFIX))
    if (place) {
      const match = placesFound.value.find(found => `${PLACE_PREFIX}${found.id}` === place.value)
      if (match)
        emit('update:place', match)
      return
    }
    // the stations picked before are looked up too: the list may not be in yet where the pick was restored from a link
    const known = [...props.stations, ...props.selected]
    const stations = chosen
      .map(item => known.find(station => station.station_id === item.value))
      .filter((station): station is S => station !== undefined)
    pick(props.multiple ? stations : stations.slice(0, 1))
  },
})

// The only way a pick reaches the caller, from the search, the map and the chips; an unchanged pick is not handed on
function pick(stations: S[]) {
  const ids = (list: S[]) => list.map(station => station.station_id).join('\n')
  if (ids(stations) === ids(props.selected))
    return
  emit('update:selected', stations)
}

// The map hands over the selection it was shown, changed by the tap: for one station, the one tapped
function onMapSelected(stations: S[]) {
  pick(props.multiple ? stations : stations.slice(-1))
}

// ---- the station nearest to the reader ---------------------------------------------------------------------

const resolving = ref(false)
const found = ref('')
const lookupProblem = ref('')
let lookup = 0

async function nearestTo(point: Point): Promise<S | null> {
  if (props.locate === 'list') {
    let best: { station: S, distance: number } | null = null
    for (const station of props.stations) {
      if (station.latitude == null || station.longitude == null)
        continue
      const distance = distanceKm(point, { latitude: station.latitude, longitude: station.longitude })
      if (!best || distance < best.distance)
        best = { station, distance }
    }
    return best?.station ?? null
  }
  const answer = await $fetch<{ stations: S[] }>('/api/stations', {
    query: { ...props.locate, latitude: point.latitude, longitude: point.longitude, rank: 1 },
    ...API_FETCH,
  })
  return answer.stations?.find(station => station.latitude != null && station.longitude != null) ?? null
}

// Another dataset or network (`locate` changed): a lookup on its way was made for the one before, and its answer is
// not a station of this one. It is dropped, with what was told of it.
watch(() => JSON.stringify(props.locate), () => {
  lookup++
  resolving.value = false
  found.value = ''
  lookupProblem.value = ''
})

// "Forget my position" (GH-4014): a lookup still on its way is dropped, with what was told of it, so that its late answer
// does not pick the station or tell a position that is gone. Synchronous, so that no answer lands between the forget and
// this. The station already picked stays picked, as the reader's own.
// the position's own state, which `useMyLocation` shares (it also reads the storage, which a picker without `locate` need not)
const position = useState<Point | null>('wd-location-position', () => null)
watch(position, (now) => {
  if (now)
    return
  lookup++
  resolving.value = false
  found.value = ''
  lookupProblem.value = ''
}, { flush: 'sync' })

// The position was handed over by the button: the station nearest to it is picked, and its distance told. An answer
// that arrives after a later press is not the reader's latest and is dropped.
async function onPosition(point: Point) {
  const mine = ++lookup
  resolving.value = true
  found.value = ''
  lookupProblem.value = ''
  try {
    const station = await nearestTo(point)
    if (mine !== lookup)
      return
    if (!station) {
      lookupProblem.value = t('location.noneNear')
      return
    }
    // several: the station is added, and a selection that has it already is left as it is; one: it replaces the pick
    const picked = props.selected.some(one => one.station_id === station.station_id)
    pick(props.multiple ? (picked ? props.selected : [...props.selected, station]) : [station])
    found.value = t('location.nearest', { name: stationShortLabel(station), distance: formatDistance(distanceKm(point, station as Point), locale.value) })
  }
  catch {
    if (mine === lookup)
      lookupProblem.value = t('location.lookupFailed')
  }
  finally {
    if (mine === lookup)
      resolving.value = false
  }
}

// ---- the chips ---------------------------------------------------------------------------------------------

function focusCheckedMode() {
  root.value?.querySelector<HTMLElement>('[role="radio"][aria-checked="true"]')?.focus()
}

// A chip that is gone takes the focus with it: it goes to the one that took its place, else to the one before, else
// to the toggle
async function removeStation(index: number) {
  pick([...props.selected.slice(0, index), ...props.selected.slice(index + 1)])
  await nextTick()
  const chips = [...(root.value?.querySelectorAll<HTMLElement>('[data-station-chip]') ?? [])]
  const target = chips[Math.min(index, chips.length - 1)]
  if (target)
    target.focus()
  else
    focusCheckedMode()
}

async function clearAll() {
  pick([])
  await nextTick()
  focusCheckedMode()
}
</script>

<template>
  <div ref="root" class="flex flex-col gap-3" data-testid="station-picker" @focusout="onFocusOut">
    <component :is="mode === 'list' ? 'label' : 'span'" v-if="label" :for="mode === 'list' ? selectId : undefined" class="text-sm font-medium">
      {{ label }}
    </component>
    <div class="flex flex-wrap items-center justify-between gap-2" data-print="hide">
      <SegmentedControl
        :model-value="mode"
        :options="modeOptions"
        :label="t('stationSelection.modeLabel')"
        :controls="panelId"
        :focus-on-click="false"
        data-testid="station-picker-mode"
        @update:model-value="setMode"
        @activate="onActivate"
      />
      <slot name="actions" />
    </div>

    <UseMyLocation v-if="locate" :resolving="resolving" :status="found" :problem="lookupProblem" @position="onPosition" />

    <!-- the one place of the choice, the search or the map, which the toggle controls -->
    <div :id="panelId" ref="panel" class="flex flex-col gap-3">
      <USelectMenu
        v-if="mode === 'list'"
        :id="selectId"
        v-model="selectedItems"
        v-model:open="open"
        v-model:search-term="searchTerm"
        :items="items"
        :ignore-filter="places"
        :multiple="multiple"
        :loading="loading"
        searchable
        :virtualize="!placeItems.length"
        color="primary"
        class="w-full"
        :class="{ 'needs-input': selected.length === 0 }"
        :placeholder="t('common.stationSearch')"
        :aria-describedby="selectedForLabel ? selectedLineId : undefined"
      >
        <template v-if="places" #content-bottom>
          <PlacesCredit v-if="placeItems.length" class="border-t border-default px-3 py-2" />
        </template>
      </USelectMenu>
      <div v-else data-print="hide">
        <ClientOnly>
          <div v-if="loading && !stations.length" class="flex items-center justify-center gap-3 py-8 text-gray-500 dark:text-gray-400">
            <UIcon name="i-ph-circle-notch" class="w-5 h-5 animate-spin text-primary-600 dark:text-primary-500" aria-hidden="true" />
            <span>{{ t('stationSelection.loading') }}</span>
          </div>
          <template v-else>
            <p v-if="!mapNotLoaded" class="flex items-center justify-center gap-2 mb-2 text-sm text-gray-500 dark:text-gray-400" data-testid="station-picker-map-hint">
              <UIcon name="i-ph-hand-pointing" class="w-4 h-4 shrink-0 text-primary-600 dark:text-primary-500" aria-hidden="true" />
              {{ mapHint }}
            </p>
            <MapStations
              :stations="stations"
              :selected-stations="selected"
              :multiple="multiple"
              @update:selected-stations="onMapSelected"
              @ready="onMapReady"
            />
          </template>
        </ClientOnly>
      </div>
    </div>

    <p v-if="error && !loading" class="text-sm text-error text-center">
      {{ t('stationSelection.loadError') }}
    </p>
    <p v-else-if="empty && !loading" class="text-sm text-gray-500 dark:text-gray-400 text-center">
      {{ t('stationSelection.noneFound') }}
    </p>

    <!-- several stations: the chips, in both modes, each to take one out -->
    <div v-if="multiple && selected.length > 0" data-testid="station-picker-chips">
      <div class="flex items-center justify-between mb-2">
        <h3 class="text-sm font-medium">
          {{ t('stationSelection.selectedStations') }}
        </h3>
        <UButton size="xs" color="neutral" variant="ghost" @click="clearAll">
          {{ t('stationSelection.clearAll') }}
        </UButton>
      </div>
      <ul class="flex flex-wrap gap-2">
        <li v-for="(station, index) in selected" :key="station.station_id">
          <UBadge
            as="button"
            type="button"
            variant="subtle"
            class="cursor-pointer"
            data-station-chip
            :aria-label="t('stationSelection.removeStation', { name: stationShortLabel(station) })"
            @click="removeStation(index)"
          >
            {{ stationShortLabel(station) }}
            <span class="ml-1" aria-hidden="true">×</span>
          </UBadge>
        </li>
      </ul>
    </div>
    <!-- one station: the search shows it, so it is told once more by one line only where there is no search: on the map -->
    <p v-else-if="!multiple && mode === 'map' && selected[0]" class="text-sm break-words" data-testid="station-picker-selected">
      <span class="font-medium">{{ t('stationSelection.selectedStation') }}</span>
      {{ stationShortLabel(selected[0]) }}
    </p>
    <!-- a visible label names the search's button "Station", no longer what it shows: the station is its description (GH-4151) -->
    <p v-else-if="selectedForLabel" :id="selectedLineId" class="sr-only" data-testid="station-picker-selected-description">
      {{ t('stationSelection.selectedStation') }} {{ stationShortLabel(selectedForLabel) }}
    </p>

    <!-- what a change of mode says to a screen reader -->
    <p class="sr-only" role="status" aria-live="polite">
      {{ announcement }}
    </p>
    <!-- how many results the text of the search has, with the places (GH-3791) -->
    <p v-if="places" class="sr-only" role="status" aria-live="polite" data-testid="station-picker-results">
      {{ searchAnnounced }}
    </p>
  </div>
</template>
