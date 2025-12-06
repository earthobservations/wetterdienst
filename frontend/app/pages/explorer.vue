<script setup lang="ts">
import StationSelection from "~/components/StationSelection.vue";
import ParameterSelection from "~/components/ParameterSelection.vue";
import type {ParameterSelectionState} from "~/types/parameter-selection-state.type";
import type {StationSelectionState} from "~/types/station-selection-state.type";

const route = useRoute();
const router = useRouter();

const fromQuery = (q: Record<string, any>): ParameterSelectionState => {
  return {
  selection: {
    provider: q.provider?.toString(),
        network
  :
    q.network?.toString(),
        resolution
  :
    q.resolution?.toString(),
        dataset
  :
    q.dataset?.toString(),
        parameters
  :
    q.parameters
        ? q.parameters.toString().split(",").filter(Boolean)
        : []
  }
}
};

const toQuery = (sel: ParameterSelectionState): Record<string, string> => {
  const q: Record<string, string> = {};
  if (sel.selection.provider) q.provider = sel.selection.provider;
  if (sel.selection.network) q.network = sel.selection.network;
  if (sel.selection.resolution) q.resolution = sel.selection.resolution;
  if (sel.selection.dataset) q.dataset = sel.selection.dataset;
  if (sel.selection.parameters.length) q.parameters = sel.selection.parameters.join(",");
  return q;
}

const parameterSelectionState = useState<ParameterSelectionState>(() => fromQuery(route.query))
const stationSelectionState = useState<StationSelectionState>(() => ({ selection: { stations: [] } }));
watch(
    parameterSelectionState,
    (val) => router.replace({query: toQuery(val)}),
    {deep: true}
);

watch(
    () => route.query,
    (q) => {
      const next = fromQuery(q);
      // Only update if different to avoid needless reactivity churn
      if (JSON.stringify(next) !== JSON.stringify(parameterSelectionState.value)) {
        parameterSelectionState.value = next;
      }
    }
);

// once parameters are selected, we have all information to continue with station selection
const showStationSelection = computed(() => {
  return parameterSelectionState.value.selection.parameters.length > 0
})
</script>

<template>
  <UContainer class="mx-auto max-w-3xl px-4 py-6 space-y-6">
    <ParameterSelection v-model="parameterSelectionState.selection"/>
    <StationSelection v-if="showStationSelection" v-model="stationSelectionState.selection" :parameter-selection="parameterSelectionState.selection" />
    {{stationSelectionState.selection.stations[0]}}
  </UContainer>
</template>