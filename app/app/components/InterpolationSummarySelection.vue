<script setup lang="ts">
import type { PlaceMatch } from '#shared/utils/places'
import type { ParameterSelectionState } from '~/types/parameter-selection-state.type'
import type { InterpolationSelection, InterpolationSource } from '~/types/station-selection-state.type'

const props = defineProps<{
  parameterSelection: ParameterSelectionState['selection']
}>()

const modelValue = defineModel<InterpolationSelection>({ required: true })

const { t } = useI18n()
const sourceLabelId = useId()

const sourceOptions = computed(() => [
  { value: 'manual' as InterpolationSource, label: t('interpolation.manualCoords'), icon: 'i-ph-pencil-simple' },
  { value: 'station' as InterpolationSource, label: t('interpolation.fromStation'), icon: 'i-ph-map-pin' },
])

// the point, and the boxes that describe it -- see `useInterpolationPoint` for why the coordinates
// and the elevation are kept apart
const { latitudeInput, longitudeInput, elevationInput, fromStation, fromPlace, pointFromStation } = useInterpolationPoint(modelValue)

// For station selection
const selectedStation = ref<Station | undefined>(modelValue.value.station)

// a station chosen in the select names the point. Not one the model holds already, which the
// watcher below has brought into the select: the model says the point itself then, e.g. a link's
// station restored with the link's elevation
watch(selectedStation, (station) => {
  if (station !== modelValue.value.station)
    fromStation(station)
})

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
const { data: stationsData, pending: stationsPending, error: stationsError, status: stationsStatus, refresh: refreshStations, clear: clearStations } = useFetch<StationsResponse>(
  '/api/stations',
  {
    query: stationsQuery,
    immediate: false,
    // fetched by the watcher on the list wanted below alone: useFetch's own refetch on a change of
    // the query asked for the whole station list a second time
    watch: false,
    ...API_FETCH,
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

// A list that answered with no station left to offer -- none at all, or none with a position --
// would leave the select empty with nothing said. Only once it has answered: not while it is out,
// and not when it failed, which the Retry notice says.
const noStationToOffer = computed(() => stationsStatus.value === 'success' && !stationItems.value.length)

// The station a shared link names as the point (GH-2392), selected once the list has answered,
// if the list offers it. Kept while the list is out or has failed, so a Retry that answers still
// restores it; given up once the list has answered, and when the user switches to coordinates.
// Nothing else can be picked before then, the select showing no list until one has answered. The
// elevation stays the link's, which is the one the link was copied with: the station's own, or one
// typed over it
const initialStationId = defineModel<string | undefined>('initialStationId')

// A place found by its name (GH-3791) fills the point with its position, to the four decimals a link keeps. It has no height, so no elevation comes with it, and
// where none is given the readings are not brought to a height: the temperature is not corrected for height, which is said beside the point.
function onPlace(match: PlaceMatch) {
  // the link's station, if it was still to be restored, is not brought back over the place
  initialStationId.value = undefined
  fromPlace({ name: match.name, region: match.region, latitude: Number(match.latitude.toFixed(4)), longitude: Number(match.longitude.toFixed(4)) })
}
function forgetPlace() {
  modelValue.value = { ...modelValue.value, place: undefined }
}

watch(stationsStatus, (status) => {
  const id = initialStationId.value
  if (status !== 'success' || !id)
    return
  const station = stationItems.value.some(item => item.value === id)
    ? allStations.value.find(s => s.station_id === id)
    : undefined
  // the point first, so the link is never written with neither the station nor its id
  if (station)
    modelValue.value = { ...modelValue.value, ...pointFromStation(station), elevation: modelValue.value.elevation }
  initialStationId.value = undefined
})

// a Retry that works hands its focus on to the select, the list it brought being what it was for
const stationSelect = useTemplateRef<{ triggerRef?: HTMLElement }>('stationSelect')
const retryNotice = useTemplateRef<HTMLElement>('retryNotice')
useFocusAfterRetry(() => !!stationsError.value, retryNotice, () => stationSelect.value?.triggerRef)

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
  // coordinates in place of the link's station, which is not brought back over them
  initialStationId.value = undefined
  // one assignment: a second write in the same tick spreads the model the first replaced, and the
  // source change was being undone by the elevation change that followed it
  modelValue.value = source === 'station'
    // back to the station still in the select: it names its elevation again, where the watcher below
    // stays silent, the selection itself not having changed. With nothing selected it says
    // nothing -- taking its empty answer would clear coordinates someone had just typed
    ? { ...modelValue.value, source, place: undefined, ...(selectedStation.value ? pointFromStation(selectedStation.value) : {}) }
    // the elevation came from wherever the point did, so it goes with it
    : { ...modelValue.value, source, elevation: undefined }
}

// Display coordinates, with a point in every language: a position is an identifier, copied into a map
// or a query, not prose (GH-2971)
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
      <span :id="sourceLabelId" class="text-sm text-gray-500 dark:text-gray-400">{{ t('interpolation.source') }}{{ t('common.colon') }}</span>
      <UFieldGroup role="group" :aria-labelledby="sourceLabelId">
        <UButton
          v-for="option in sourceOptions"
          :key="option.value"
          :icon="option.icon"
          :label="option.label"
          color="neutral"
          :variant="modelValue.source === option.value ? 'subtle' : 'ghost'"
          :aria-pressed="modelValue.source === option.value"
          size="xs"
          @click="setSource(option.value)"
        />
      </UFieldGroup>
    </div>

    <div v-if="modelValue.source === 'manual'" class="space-y-4">
      <!-- the point by the name of a place (GH-3791): the field finds it, the place chosen is shown with its point and fills the coordinates -->
      <PlaceField :label="t('place.fieldLabel')" @pick="onPlace" />
      <div v-if="modelValue.place" class="rounded-lg border border-default p-3 text-sm" data-testid="interpolation-place">
        <div class="flex flex-wrap items-center gap-x-2 gap-y-1">
          <UIcon name="i-ph-map-pin" class="size-4 shrink-0 text-primary-600 dark:text-primary-500" aria-hidden="true" />
          <span class="font-bold" data-testid="interpolation-place-name">{{ modelValue.place.name }}</span>
          <span v-if="modelValue.place.region" class="text-muted" data-testid="interpolation-place-region">{{ modelValue.place.region }}</span>
          <UButton
            size="md"
            color="neutral"
            variant="ghost"
            icon="i-ph-x"
            class="ms-auto"
            :label="t('place.forget')"
            :aria-label="t('place.forgetPlace', { place: modelValue.place.name })"
            @click="forgetPlace"
          />
        </div>
        <p v-if="modelValue.elevation === undefined" class="mt-1 text-muted" data-testid="interpolation-place-height">
          {{ t('place.notCorrected') }}
        </p>
      </div>
      <div class="flex gap-4">
        <UFormField :label="t('interpolation.latitude')" class="flex-1">
          <UInput
            v-model="latitudeInput"
            type="number"
            step="0.0001"
            :placeholder="t('interpolation.example', { value: '52.5200' })"
            class="w-full"
            :class="{ 'needs-input': modelValue.latitude === undefined }"
          />
        </UFormField>
        <UFormField :label="t('interpolation.longitude')" class="flex-1">
          <UInput
            v-model="longitudeInput"
            type="number"
            step="0.0001"
            :placeholder="t('interpolation.example', { value: '13.4050' })"
            class="w-full"
            :class="{ 'needs-input': modelValue.longitude === undefined }"
          />
        </UFormField>
      </div>
    </div>

    <div v-else>
      <!-- the field's help, which describes the select as well, says why a list that answered has
           nothing in it -->
      <UFormField :label="t('interpolation.selectStationForCoords')" :help="noStationToOffer ? t('interpolation.noStationsWithPosition') : undefined">
        <USelectMenu
          v-if="!stationsPending"
          ref="stationSelect"
          v-model="selectedStationItem"
          :items="stationItems"
          :placeholder="t('common.stationSearch')"
          searchable
          virtualize
          class="w-full"
          :class="{ 'needs-input': !modelValue.station }"
        />
        <div v-else class="text-sm text-gray-500 dark:text-gray-400">
          {{ t('interpolation.loadingStations') }}
        </div>
        <!-- a failed list leaves the select empty, and nothing asks for it again until the selection
             wants another list. useFetch keeps the error until the next answer: the notice is
             mounted anew once each answer has failed, so a Retry that fails too is announced again;
             the button stays while Retry's request is out, and keeps its focus. Pressed again
             meanwhile, it waits for that request, where a plain refresh cancels it and asks for
             the whole list anew -->
        <div v-if="stationsError" ref="retryNotice" class="mt-2 flex flex-wrap items-center gap-3">
          <p v-if="!stationsPending" role="alert" class="text-sm text-error">
            {{ t('interpolation.loadError') }}
          </p>
          <UButton :label="t('common.retry')" icon="i-ph-arrow-clockwise" size="sm" color="neutral" variant="outline" @click="refreshStations({ dedupe: 'defer' })" />
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
        :placeholder="t('interpolation.example', { value: '34' })"
        class="w-full"
      />
    </UFormField>

    <div v-if="displayCoords" class="text-sm text-gray-500 dark:text-gray-400">
      {{ t('interpolation.coords', { coords: displayCoords }) }}
    </div>
  </div>
</template>
