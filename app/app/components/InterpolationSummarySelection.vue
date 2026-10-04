<script setup lang="ts">
import type { ParameterSelectionState } from '~/types/parameter-selection-state.type'
import type { InterpolationSelection, InterpolationSource } from '~/types/station-selection-state.type'

const props = defineProps<{
  parameterSelection: ParameterSelectionState['selection']
}>()

const modelValue = defineModel<InterpolationSelection>({ required: true })

const { t } = useI18n()

const sourceOptions = computed(() => [
  { value: 'manual' as InterpolationSource, label: t('interpolation.manualCoords'), icon: 'i-lucide-pencil' },
  { value: 'station' as InterpolationSource, label: t('interpolation.fromStation'), icon: 'i-lucide-map-pin' },
])

// the point, and the boxes that describe it -- see `useInterpolationPoint` for why the coordinates
// and the elevation are kept apart
const { latitudeInput, longitudeInput, elevationInput, fromStation, pointFromStation } = useInterpolationPoint(modelValue)

// For station selection
const selectedStation = ref<Station | undefined>(modelValue.value.station)

watch(selectedStation, fromStation)

// the parent replaces the whole model when the provider or dataset changes, which clears the
// station -- and a select still holding the old one would write it back, coordinates, elevation and
// all, for a station the new dataset may not have
watch(() => modelValue.value.station, (station) => {
  if (station !== selectedStation.value)
    selectedStation.value = station
})

// Fetch stations for station source
const stationsQuery = computed(() => ({
  provider: props.parameterSelection.provider,
  network: props.parameterSelection.network,
  parameters: `${props.parameterSelection.resolution}/${props.parameterSelection.dataset}`,
  all: 'true',
}))
const { data: stationsData, pending: stationsPending, error: stationsError, refresh: refreshStations, clear: clearStations } = useFetch<StationsResponse>(
  '/api/stations',
  {
    query: stationsQuery,
    immediate: false,
    // fetched by the watcher on the list wanted below alone: useFetch's own refetch on a change of
    // the query asked for the whole station list a second time
    watch: false,
    ...RETRY_TRANSIENT,
    default: () => ({ stations: [] }),
  },
)

const allStations = computed(() => stationsData.value?.stations ?? [])

// A station offers the point it stands at, so one without a position, e.g. a postcode of
// dwd/derived climate_correction_factor, has none to offer and is left out.
const stationItems = computed(() =>
  allStations.value.filter(hasPosition).map(station => ({
    label: stationShortLabel(station),
    value: station.station_id,
  })),
)

const selectedStationItem = computed({
  get: () => selectedStation.value
    ? {
        label: stationShortLabel(selectedStation.value),
        value: selectedStation.value.station_id,
      }
    : undefined,
  set: (item: { label: string, value: string } | undefined) => {
    selectedStation.value = item ? allStations.value.find(s => s.station_id === item.value) : undefined
  },
})

// The list the selection asks for, none while it has no parameters. Watched as a string, so only a
// change of list asks again: a change of dataset comes as two updates, the new dataset first and
// its parameters a tick later, and a parameter ticked asks for the same list. With none wanted the
// list is emptied, as useFetch carries the last list over to a query it has not fetched.
const stationsWanted = computed(() =>
  props.parameterSelection.parameters?.length ? JSON.stringify(stationsQuery.value) : '')

watch(stationsWanted, (wanted) => {
  if (wanted)
    refreshStations()
  else
    clearStations()
}, { immediate: true })

function setSource(source: InterpolationSource) {
  // clicking the source already in use is not a change, and treating it as one dropped the elevation
  // of a station that stayed selected -- the form unchanged on screen, the next answer
  // uncorrected, which at 1000 m is six degrees of air temperature
  if (source === modelValue.value.source)
    return
  // one assignment: a second write in the same tick spreads the model the first replaced, and the
  // source change was being undone by the elevation change that followed it
  modelValue.value = source === 'station'
    // back to the station still in the select: it names its elevation again, where the watcher below
    // stays silent, the selection itself not having changed. With nothing selected it says
    // nothing -- taking its empty answer would clear coordinates someone had just typed
    ? { ...modelValue.value, source, ...(selectedStation.value ? pointFromStation(selectedStation.value) : {}) }
    // the elevation came from wherever the point did, so it goes with it
    : { ...modelValue.value, source, elevation: undefined }
}

// Display coordinates
const displayCoords = computed(() => {
  if (modelValue.value.latitude !== undefined && modelValue.value.longitude !== undefined) {
    return `${modelValue.value.latitude.toFixed(4)}, ${modelValue.value.longitude.toFixed(4)}`
  }
  return null
})
</script>

<template>
  <div class="space-y-4">
    <div class="flex items-center gap-2">
      <span class="text-sm text-gray-500">{{ t('interpolation.source') }}:</span>
      <UFieldGroup>
        <UButton
          v-for="option in sourceOptions"
          :key="option.value"
          :icon="option.icon"
          :label="option.label"
          color="neutral"
          :variant="modelValue.source === option.value ? 'subtle' : 'ghost'"
          size="xs"
          @click="setSource(option.value)"
        />
      </UFieldGroup>
    </div>

    <div v-if="modelValue.source === 'manual'" class="flex gap-4">
      <UFormField :label="t('interpolation.latitude')" class="flex-1">
        <UInput
          v-model="latitudeInput"
          type="number"
          step="0.0001"
          placeholder="e.g. 52.5200"
          class="w-full"
          :class="{ 'needs-input': modelValue.latitude === undefined }"
        />
      </UFormField>
      <UFormField :label="t('interpolation.longitude')" class="flex-1">
        <UInput
          v-model="longitudeInput"
          type="number"
          step="0.0001"
          placeholder="e.g. 13.4050"
          class="w-full"
          :class="{ 'needs-input': modelValue.longitude === undefined }"
        />
      </UFormField>
    </div>

    <div v-else>
      <UFormField :label="t('interpolation.selectStationForCoords')">
        <USelectMenu
          v-if="!stationsPending"
          v-model="selectedStationItem"
          :items="stationItems"
          :placeholder="t('common.stationSearch')"
          searchable
          virtualize
          class="w-full"
          :class="{ 'needs-input': !modelValue.station }"
        />
        <div v-else class="text-sm text-gray-500">
          {{ t('interpolation.loadingStations') }}
        </div>
        <!-- a failed list leaves the select empty, and only a new dataset would ask for it again -->
        <div v-if="stationsError && !stationsPending" class="mt-2 flex flex-wrap items-center gap-3">
          <p class="text-sm text-error">
            {{ t('interpolation.loadError') }}
          </p>
          <UButton :label="t('common.retry')" icon="i-lucide-rotate-cw" size="sm" color="neutral" variant="outline" @click="refreshStations()" />
        </div>
      </UFormField>
    </div>

    <!-- part of the point whichever way the point was given: a station fills it with its own
         elevation, and leaving it filled in silently is what drops the neighbours that have none -->
    <UFormField :label="t('interpolation.elevation')" :hint="t('interpolation.elevationHint')">
      <UInput
        v-model="elevationInput"
        type="number"
        step="1"
        placeholder="e.g. 34"
        class="w-full"
      />
    </UFormField>

    <div v-if="displayCoords" class="text-sm text-gray-500">
      {{ t('interpolation.coords', { coords: displayCoords }) }}
    </div>
  </div>
</template>
