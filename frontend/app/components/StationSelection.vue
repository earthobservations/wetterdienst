<script setup lang="ts">
import StationMap from "~/components/StationMap.vue";
import type {Station} from "~/types/station.type";
import type {ParameterSelectionState} from "~/types/parameter-selection-state.type";
import StationSelectionSearchSelect from "~/components/StationSelectionSearchSelect.vue";

const { parameterSelection } = defineProps<{ parameterSelection: ParameterSelectionState["selection"] }>()
const selectedStations = useState<Station[]>(() => [])

const {data: stationsData, pending: stationsPending, refresh: refreshStations} = await useFetch<{
  stations: Station[]
}>(
    '/api/stations',
    {
      query: {
        provider: parameterSelection.provider,
        network: parameterSelection.network,
        parameters: `${parameterSelection.resolution}/${parameterSelection.dataset}`,
        all: 'true'
      },
      immediate: false,
      default: () => ({stations: []})
    }
)

watch(() => parameterSelection, (ps) => {
  if (!ps.parameters.length) {
    // No parameters selected, clear stations data
    stationsData.value = {stations: []}
    selectedStations.value = []
    return
  }
  // Clear selected stations when parameters change
  stationsData.value = {stations: []}
  selectedStations.value = []
  // Refresh stations data
  refreshStations()
}, {deep: true, immediate: true})

const emit = defineEmits(['update:modelValue'])

watch(selectedStations, () => {
  emit('update:modelValue', {
    stations: [...selectedStations.value]
  })
})

</script>
<template>
  <UCard>
    <template #header>
      Select Stations
    </template>
    <div v-if="stationsPending" class="flex justify-center py-8">
      <div class="text-gray-500">Loading stations...</div>
    </div>
    <div v-else-if="!stationsData.stations.length" class="flex justify-center py-8">
      <div class="text-gray-500">No stations found for the selected parameters</div>
    </div>
    <div v-else-if="!stationsData.stations.length" class="flex justify-center py-8">
      <StationSelectionSearchSelect :stations-pending="stationsPending" :all-stations="stationsData.stations" v-model:selected-stations="selectedStations"/>
      <StationMap :all-stations="stationsData.stations" v-model:selected-stations="selectedStations" />
    </div>
  </UCard>
</template>
