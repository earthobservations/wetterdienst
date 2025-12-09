<script setup lang="ts">

import type {ParameterSelectionState} from "~/types/parameter-selection-state.type";
import type {StationSelectionState} from "~/types/station-selection-state.type";
import type {Value} from "~/types/value.type";

const { parameterSelection, stationSelection } = defineProps<{
  parameterSelection: ParameterSelectionState["selection"],
  stationSelection: StationSelectionState["selection"]
}>()

const { data: valuesData, pending: valuesPending, refresh: refreshValues } = useFetch<{
  values: Value[]
}>(
  '/api/values',
  {
    method: 'GET',
    query: {
      provider: parameterSelection.provider,
      network: parameterSelection.network,
      parameters: parameterSelection.parameters.map((parameter) => `${parameterSelection.resolution}/${parameterSelection.dataset}/${parameter}` ).join(","),
      station: stationSelection.stations.map((station) => station.station_id).join(",")
    },
    immediate: false,
    default: () => ({ values: [] })
  }
)

const allValues = computed(() => valuesData.value?.values ?? [])

watch(
  () => [parameterSelection, stationSelection],
  () => {
    if (!parameterSelection.parameters.length || !stationSelection.stations.length) {
      // No parameters or stations selected, clear values data
      valuesData.value = { values: [] }
      return
    }
    // Refresh values data
    refreshValues()
  },
  { deep: true, immediate: true }
)
</script>
<template>
  <UCard>
    <UTable virtualize :data="allValues" class="h-[800px]"/>
  </UCard>
</template>