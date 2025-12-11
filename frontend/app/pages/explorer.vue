<script setup lang="ts">
import StationSelection from "~/components/StationSelection.vue";
import ParameterSelection from "~/components/ParameterSelection.vue";
import type {ParameterSelectionState} from "~/types/parameter-selection-state.type";
import type {StationSelectionState} from "~/types/station-selection-state.type";
import DataViewer from "~/components/DataViewer.vue";

const route = useRoute();
const router = useRouter();

const stationIdsFromQuery = (q: Record<string, any>): string[] => {
  return q.stations ? q.stations.toString().split(",").filter(Boolean) : []
}

const fromQuery = (q: Record<string, any>): ParameterSelectionState => {
  return {
    selection: {
      provider: q.provider?.toString(),
      network: q.network?.toString(),
      resolution: q.resolution?.toString(),
      dataset: q.dataset?.toString(),
      parameters: q.parameters
        ? q.parameters.toString().split(",").filter(Boolean)
        : []
    }
  }
}

const toQuery = (paramSel: ParameterSelectionState, stationSel: StationSelectionState): Record<string, string> => {
  const q: Record<string, string> = {};
  if (paramSel.selection.provider) q.provider = paramSel.selection.provider;
  if (paramSel.selection.network) q.network = paramSel.selection.network;
  if (paramSel.selection.resolution) q.resolution = paramSel.selection.resolution;
  if (paramSel.selection.dataset) q.dataset = paramSel.selection.dataset;
  if (paramSel.selection.parameters.length) q.parameters = paramSel.selection.parameters.join(",");
  if (stationSel.selection.stations.length) q.stations = stationSel.selection.stations.map(s => s.station_id).join(",");
  return q;
}

const parameterSelectionState = ref<ParameterSelectionState>(fromQuery(route.query))
const stationSelectionState = ref<StationSelectionState>({ selection: { stations: [] } });
const initialStationIds = ref<string[]>(stationIdsFromQuery(route.query))

// Track initial parameter values to detect actual changes vs initialization
const initialParamKey = `${route.query.provider}|${route.query.network}|${route.query.resolution}|${route.query.dataset}`
const lastParamKey = ref(initialParamKey)

// Clear station selection when parameter selection changes (but not on initial load)
watch(
    () => [
      parameterSelectionState.value.selection.provider,
      parameterSelectionState.value.selection.network,
      parameterSelectionState.value.selection.resolution,
      parameterSelectionState.value.selection.dataset
    ],
    (newVals) => {
      const newKey = newVals.join('|')
      if (newKey === lastParamKey.value) return
      lastParamKey.value = newKey
      stationSelectionState.value = { selection: { stations: [] } }
      initialStationIds.value = []
    }
);

// Update URL when parameter or station selection changes
watch(
    [parameterSelectionState, stationSelectionState],
    () => router.replace({query: toQuery(parameterSelectionState.value, stationSelectionState.value)}),
    {deep: true}
);

// once parameters are selected, we have all information to continue with station selection
const showStationSelection = computed(() => {
  return parameterSelectionState.value.selection.parameters.length > 0
})

// once stations are selected, we have all information to continue with data viewing
const showDataViewer = computed(() => {
  return stationSelectionState.value.selection.stations.length > 0
})
</script>

<template>
  <UContainer class="mx-auto max-w-3xl px-4 py-6 space-y-6">
    <ParameterSelection v-model="parameterSelectionState.selection"/>
    <StationSelection v-if="showStationSelection" v-model="stationSelectionState.selection" :parameter-selection="parameterSelectionState.selection" :initial-station-ids="initialStationIds" />
    <DataViewer v-if="showDataViewer" :parameter-selection="parameterSelectionState.selection" :station-selection="stationSelectionState.selection" />
  </UContainer>
</template>