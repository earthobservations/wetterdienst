<script setup lang="ts" generic="S extends StationPickerStation">
// The one way to pick stations, for the explorer, the history, the forecast and the stripes (GH-3877): a toggle
// "List | Map" over the one place where the choice is made, and the stations picked as chips under it, in both
// modes, so that a switch never hides what was chosen. The list is the search field, the map is the map of the
// stations. A station picked in one shows in the other: both read the same `selected`.
//
// The picker holds no list of its own and fetches nothing: the caller hands it the stations, and learns by
// `update:open` (the search is open) and `update:mode` (the map is shown, which is also said once for the mode
// remembered) when it is worth fetching a list that is large. `multiple` is the explorer's and the history's
// choice of any number of stations; without it a pick replaces the one before, as the forecast and the stripes
// have it.
//
// An action that belongs beside the toggle, such as one that picks the station nearest to where you are, goes
// in the `actions` slot.
import type { StationPickerStation } from '~/utils/station'
import type { StationPickerMode, StationPickerTool } from '~/utils/station-picker-mode'
import SegmentedControl from '~/components/SegmentedControl.vue'
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
}>()

const emit = defineEmits<{
  'update:selected': [stations: S[]]
  /** The search is open (its menu is) */
  'update:open': [open: boolean]
  /** The mode shown: once on setup, for the one remembered, then for each change */
  'update:mode': [mode: StationPickerMode]
}>()

defineSlots<{
  /** What goes beside the toggle: an action on the choice, as one that picks a station for you */
  actions?: () => unknown
}>()

const { t } = useI18n()
const { MapStations, notLoaded: mapNotLoaded } = useMapStations()

const mode = ref<StationPickerMode>(readStationPickerMode(props.tool))
watch(mode, value => emit('update:mode', value), { immediate: true })

const open = ref(false)
watch(open, value => emit('update:open', value))

const root = ref<HTMLElement | null>(null)
const panel = ref<HTMLElement | null>(null)
const panelId = useId()

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
    return t('common.stationSearch')
  return mapNotLoaded.value ? '' : mapHint.value
})

// A map asked for by a switch that is not there yet (its code, and the list of the stations, are on their way) takes
// the focus as soon as it is
let focusMapWhenReady = false

function focusMap() {
  const container = panel.value?.querySelector<HTMLElement>('.leaflet-container')
  if (container) {
    focusMapWhenReady = false
    container.focus()
  }
  else {
    focusMapWhenReady = true
  }
}

function focusContent() {
  if (mode.value === 'map')
    focusMap()
  else
    panel.value?.querySelector<HTMLElement>('button')?.focus()
}

// The reader's own choice: remembered, announced, and (`onActivate`) the focus goes into what it shows
function setMode(value: StationPickerMode) {
  if (value === mode.value)
    return
  mode.value = value
  focusMapWhenReady = false
  open.value = false
  writeStationPickerMode(props.tool, value)
  changedByReader.value = true
}

// A click, or Enter or Space, on the toggle is a decision to use the mode: the focus goes into the search or the
// map. The arrow keys keep it on the toggle (`SegmentedControl`), to walk along it
async function onActivate() {
  await nextTick()
  focusContent()
}

function onMapReady() {
  if (focusMapWhenReady)
    focusMap()
}

// ---- what the search shows, and what it hands over ---------------------------------------------------------

const items = computed(() => props.stations.map(station => ({ label: stationLabel(station), value: station.station_id })))

// The search's model: the picked stations as items, an array for several and one item (or none) for one
const selectedItems = computed({
  get: () => {
    const picked = props.selected.map(station => ({ label: stationLabel(station), value: station.station_id }))
    return props.multiple ? picked : picked[0]
  },
  set: (value: { label: string, value: string } | { label: string, value: string }[] | undefined) => {
    const chosen = Array.isArray(value) ? value : value ? [value] : []
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
  <div ref="root" class="flex flex-col gap-3" data-testid="station-picker">
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

    <!-- the one place of the choice, the search or the map, which the toggle controls -->
    <div :id="panelId" ref="panel" class="flex flex-col gap-3">
      <USelectMenu
        v-if="mode === 'list'"
        v-model="selectedItems"
        v-model:open="open"
        :items="items"
        :multiple="multiple"
        :loading="loading"
        searchable
        virtualize
        color="primary"
        class="w-full"
        :class="{ 'needs-input': selected.length === 0 }"
        :placeholder="t('common.stationSearch')"
      />
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

    <div v-if="selected.length > 0" data-testid="station-picker-chips">
      <div class="flex items-center justify-between mb-2">
        <h3 class="text-sm font-medium">
          {{ multiple ? t('stationSelection.selectedStations') : t('stationSelection.selectedStation') }}
        </h3>
        <UButton v-if="multiple" size="xs" color="neutral" variant="ghost" @click="clearAll">
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

    <!-- what a change of mode says to a screen reader -->
    <p class="sr-only" role="status" aria-live="polite">
      {{ announcement }}
    </p>
  </div>
</template>
