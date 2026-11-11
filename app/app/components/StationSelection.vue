<script setup lang="ts">
import type { ParameterSelectionState } from '~/types/parameter-selection-state.type'
import type { StationPickerMode, StationPickerTool } from '~/utils/station-picker-mode'
import StationPicker from '~/components/StationPicker.vue'

// The station picker of the explorer and the history, which holds the list of the stations of the dataset chosen
// (fetched when the search is opened or the map shown, as it is large), the stations chosen, and those of a shared
// link; what it shows is `StationPicker`, as for the forecast and the stripes
const props = defineProps<{
  modelValue?: { stations: Station[] }
  parameterSelection: ParameterSelectionState['selection']
  initialStationIds?: string[]
  multiple?: boolean
  /** Whose picker it is: each tool remembers its own mode, the list or the map */
  tool: StationPickerTool
}>()

const emit = defineEmits(['update:modelValue', 'update:selectedStations'])

const selectedStations = ref<Station[]>(props.modelValue?.stations ?? [])

// What the picker shows, as it says: the map is on screen when its mode is the map
const mode = ref<StationPickerMode>('list')
const showMap = computed(() => mode.value === 'map')

watch(selectedStations, (newVal, oldVal) => {
  if (JSON.stringify(newVal) !== JSON.stringify(oldVal)) {
    emit('update:modelValue', {
      stations: [...selectedStations.value],
    })
  }
})

// Sync with parent's modelValue changes
watch(() => props.modelValue, (newVal) => {
  if (newVal && JSON.stringify(newVal.stations) !== JSON.stringify(selectedStations.value)) {
    selectedStations.value = [...(newVal.stations ?? [])]
  }
}, { deep: true })

// Track whether we've already restored initial stations
const hasRestoredInitialStations = ref(false)

const { data: stationsData, pending: stationsPending, error: stationsError, refresh: refreshStations } = useFetch<StationsResponse>(
  '/api/stations',
  {
    query: computed(() => ({
      provider: props.parameterSelection.provider,
      network: props.parameterSelection.network,
      parameters: `${props.parameterSelection.resolution}/${props.parameterSelection.dataset}`,
      all: 'true',
    })),
    immediate: false,
    // The query is reactive, and `useFetch` refetches on its own when it changes -- which,
    // together with the explicit `refreshStations()` in `fetchStations`, fetched the whole
    // station list twice. Fetching is driven explicitly here instead: a parameter change clears
    // the list and refetches if a picker is open, otherwise the next open does it.
    watch: false,
    ...API_FETCH,
    default: () => ({ stations: [] }),
  },
)

const allStations = computed(() => stationsData.value?.stations ?? [])

// The station list can be large, so it's only fetched lazily -- when the
// picker (select menu or map) is actually opened -- rather than as soon as
// parameters become valid. The exception is restoring a shared URL's
// preselected stations, which needs the list right away.
const stationsLoaded = ref(false)
const selectOpen = ref(false)

async function fetchStations() {
  if (stationsLoaded.value || stationsPending.value)
    return
  if (!props.parameterSelection.parameters?.length)
    return
  stationsLoaded.value = true
  await refreshStations()
  // A failed request shouldn't count as "loaded" -- otherwise reopening the
  // picker would never retry, and the empty result would misleadingly look
  // like a confirmed "no stations found" instead of a failed request.
  if (stationsError.value)
    stationsLoaded.value = false
}

watch(selectOpen, (isOpen) => {
  if (isOpen)
    fetchStations()
})

watch(showMap, (isShown) => {
  if (isShown)
    fetchStations()
})

// Restore initial stations when stations data is loaded
watch(allStations, (stations) => {
  if (hasRestoredInitialStations.value)
    return
  if (!stations.length)
    return
  if (!props.initialStationIds?.length)
    return

  // Find stations matching the initial IDs
  const restoredStations = props.initialStationIds
    .map(id => stations.find(s => s.station_id === id))
    .filter((s): s is Station => s !== undefined)
    .sort((a, b) => a.station_id.localeCompare(b.station_id))

  if (restoredStations.length > 0) {
    selectedStations.value = restoredStations
  }
  hasRestoredInitialStations.value = true
})

// What the station list is for: it is asked per dataset, so anything else in the selection (the
// parameters, `dateRequired`) leaves it as it is. `null` before the first selection with parameters
let listedFor: string | null = null
function listKey(ps: ParameterSelectionState['selection']) {
  return [ps.provider, ps.network, ps.resolution, ps.dataset].join('|')
}

watch(() => props.parameterSelection, (ps) => {
  if (!ps.parameters?.length) {
    stationsData.value = { stations: [] }
    selectedStations.value = []
    stationsLoaded.value = false
    listedFor = null
    return
  }
  // The same dataset again: the selection was replaced by an equal one (ParameterSelection answers
  // the link it was given once it has checked it), or other parameters were chosen. The list and the
  // stations chosen from it stay; clearing them here lost the stations of a shared link whenever
  // the list arrived before that answer (GH-2959)
  const key = listKey(ps)
  if (key === listedFor)
    return
  listedFor = key
  // Clear selected stations when the dataset changes (but not on initial load)
  if (hasRestoredInitialStations.value) {
    selectedStations.value = []
  }
  // The dataset changed -- any previously fetched station list is now stale.
  stationsData.value = { stations: [] }
  stationsLoaded.value = false
  // Fetch right away only to restore stations preselected via a shared URL, or when a picker is
  // open on screen right now -- an expanded map whose markers were just cleared would otherwise
  // stay empty until it is collapsed and reopened. Otherwise wait until the picker is opened.
  if ((props.initialStationIds?.length && !hasRestoredInitialStations.value) || selectOpen.value || showMap.value) {
    fetchStations()
  }
}, { deep: true, immediate: true })

// "Use my location" asks for the station nearest to the reader among those of the dataset chosen, as the list is asked
const locateQuery = computed(() => props.parameterSelection.parameters?.length
  ? {
      provider: props.parameterSelection.provider,
      network: props.parameterSelection.network,
      parameters: `${props.parameterSelection.resolution}/${props.parameterSelection.dataset}`,
    }
  : undefined)

// A pick, from the search, the map or the chips
function onPick(val: Station[]) {
  selectedStations.value = val
  // the parent is told by the watcher of the selection, once
  emit('update:selectedStations', val)
}
</script>

<template>
  <StationPicker
    :tool="tool"
    :stations="allStations"
    :selected="selectedStations"
    :multiple="multiple"
    :loading="stationsPending"
    :error="!!stationsError"
    :empty="stationsLoaded && !allStations.length"
    :locate="locateQuery"
    @update:selected="onPick"
    @update:open="selectOpen = $event"
    @update:mode="mode = $event"
  >
    <template #actions>
      <slot name="actions" />
    </template>
  </StationPicker>
</template>
