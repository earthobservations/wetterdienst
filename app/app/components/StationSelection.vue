<script setup lang="ts">
import type { ParameterSelectionState } from '~/types/parameter-selection-state.type'
import { defineAsyncComponent } from 'vue'

const props = defineProps<{
  modelValue?: { stations: Station[] }
  parameterSelection: ParameterSelectionState['selection']
  initialStationIds?: string[]
  multiple?: boolean
}>()

const emit = defineEmits(['update:modelValue', 'update:selectedStations'])

const { t } = useI18n()

const MapStations = defineAsyncComponent(() => import('./MapStations.vue'))

const selectedStations = ref<Station[]>(props.modelValue?.stations ?? [])

const showMap = ref(false)

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

watch(showMap, (isOpen) => {
  if (isOpen)
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

watch(() => props.parameterSelection, (ps) => {
  if (!ps.parameters?.length) {
    stationsData.value = { stations: [] }
    selectedStations.value = []
    stationsLoaded.value = false
    return
  }
  // Clear selected stations when parameters change (but not on initial load)
  if (hasRestoredInitialStations.value) {
    selectedStations.value = []
  }
  // Parameters changed -- any previously fetched station list is now stale.
  stationsData.value = { stations: [] }
  stationsLoaded.value = false
  // Fetch right away only to restore stations preselected via a shared URL, or when a picker is
  // open on screen right now -- an expanded map whose markers were just cleared would otherwise
  // stay empty until it is collapsed and reopened. Otherwise wait until the picker is opened.
  if ((props.initialStationIds?.length && !hasRestoredInitialStations.value) || selectOpen.value || showMap.value) {
    fetchStations()
  }
}, { deep: true, immediate: true })

// Items for the select menu
const stationItems = computed(() =>
  allStations.value.map(station => ({
    label: stationLabel(station),
    value: station.station_id,
  })),
)

// Bridge between Station[] and item objects
const selectedItems = computed({
  get: () => props.multiple
    ? selectedStations.value.map(s => ({
        label: stationLabel(s),
        value: s.station_id,
      }))
    : selectedStations.value[0]
      ? [{
          label: stationLabel(selectedStations.value[0]),
          value: selectedStations.value[0].station_id,
        }]
      : [],
  set: (items: { label: string, value: string }[]) => {
    if (props.multiple) {
      // Merge new selections with existing ones, avoid reset
      const newStations = items
        .map(item => allStations.value.find(s => s.station_id === item.value))
        .filter((s): s is Station => s !== undefined)
      // Only update if changed
      if (JSON.stringify(newStations) !== JSON.stringify(selectedStations.value)) {
        selectedStations.value = newStations
      }
    }
    else {
      // items may be undefined or empty when clearing selection; guard against that
      const stationId = items && items[0] ? items[0].value : undefined
      const station = stationId ? allStations.value.find(s => s.station_id === stationId) : undefined
      if (JSON.stringify([station]) !== JSON.stringify(selectedStations.value)) {
        selectedStations.value = station ? [station] : []
      }
    }
  },
})

// Handler for map selection event with explicit typing to satisfy typecheck
function onMapSelectedStations(val: Station[]) {
  selectedStations.value = val
  emit('update:selectedStations', val)
  emit('update:modelValue', { stations: val })
}

function removeStation(station: Station) {
  const index = selectedStations.value.findIndex(s => s.station_id === station.station_id)
  if (index >= 0) {
    // Replace array to trigger reactivity
    selectedStations.value = [
      ...selectedStations.value.slice(0, index),
      ...selectedStations.value.slice(index + 1),
    ]
  }
}
</script>

<template>
  <div class="flex flex-col gap-4">
    <USelectMenu
      v-model="selectedItems"
      v-model:open="selectOpen"
      :items="stationItems"
      :multiple="multiple"
      :loading="stationsPending"
      searchable
      virtualize
      color="primary"
      class="w-full"
      :class="{ 'needs-input': selectedStations.length === 0 }"
      :placeholder="t('common.stationSearch')"
    />
    <p v-if="stationsError && !stationsPending" class="text-sm text-error text-center">
      {{ t('stationSelection.loadError') }}
    </p>
    <p v-else-if="stationsLoaded && !stationsPending && !allStations.length" class="text-sm text-gray-500 text-center">
      {{ t('stationSelection.noneFound') }}
    </p>
    <UContainer v-if="selectedStations.length > 0" class="mt-2">
      <div class="flex items-center justify-between mb-2">
        <h4 class="text-sm font-medium">
          {{ t('stationSelection.selectedStations') }}
        </h4>
        <UButton size="xs" color="neutral" variant="ghost" @click="selectedStations = []">
          {{ t('stationSelection.clearAll') }}
        </UButton>
      </div>
      <div class="flex flex-wrap gap-2">
        <UBadge
          v-for="station in selectedStations"
          :key="station.station_id"
          variant="subtle"
          class="cursor-pointer"
          @click="removeStation(station)"
        >
          {{ stationShortLabel(station) }}
          <span class="ml-1">×</span>
        </UBadge>
      </div>
    </UContainer>
    <UCollapsible v-model="showMap" class="mt-4">
      <UButton
        :label="t('stationSelection.chooseOnMap')"
        icon="i-lucide-map-pin"
        variant="subtle"
        color="primary"
        trailing-icon="i-lucide-chevron-down"
        block
        @click="showMap = !showMap"
      />
      <template #content>
        <ClientOnly>
          <p class="flex items-center justify-center gap-2 mt-3 text-sm text-gray-500 dark:text-gray-400">
            <UIcon name="i-lucide-hand-pointer-2" class="w-4 h-4 text-primary-500" />
            {{ multiple ? t('stationSelection.mapHintMultiple') : t('stationSelection.mapHint') }}
          </p>
          <MapStations
            :stations="allStations"
            :selected-stations="selectedStations"
            :multiple="multiple"
            @update:selected-stations="onMapSelectedStations"
          />
        </ClientOnly>
      </template>
    </UCollapsible>
  </div>
</template>
