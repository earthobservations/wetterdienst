<script setup lang="ts">
import StationMap from "~/components/StationMap.vue";
import MiniSearch from "minisearch";
import StationSelection from "~/components/StationSelection.vue";
import ParameterSelection from "~/components/ParameterSelection.vue";
import type {ParameterSelectionState} from "~/types/parameter-selection-state.type";

interface Station {
  station_id: string
  name: string
  state: string
  latitude: number
  longitude: number
}

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

const parameterSelectionState = ref<ParameterSelectionState>(fromQuery(route.query))


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

const stationsParams = computed(() => {
  if (!parameterSelectionState.value.selection.provider || !parameterSelectionState.value.selection.network || !parameterSelectionState.value.selection.resolution || !parameterSelectionState.value.selection.dataset) return null
  return {
    provider: parameterSelectionState.value.selection.provider,
    network: parameterSelectionState.value.selection.network,
    parameters: `${parameterSelectionState.value.selection.resolution}/${parameterSelectionState.value.selection.dataset}`,
    all: 'true'
  }
})

const {data: stationsData, pending: stationsPending, refresh: refreshStations} = await useFetch<{
  stations: Station[]
}>(
    '/api/stations',
    {
      query: stationsParams,
      immediate: false,
      default: () => ({stations: []})
    }
)

const query = ref('')
const selectedStations = useState<string[]>(() => [])

const miniSearch = new MiniSearch({
  fields: ["station_id", "name", "state"],
  idField: "station_id"
})

watch(stationsParams, (params) => {
  if (params) {
    console.log('Fetching stations with params:', params)
    refreshStations()
  }
})

watch(stationsData, (data) => {
  console.log('Stations data received:', data?.stations?.length || 0, 'stations')
}, {immediate: true})

watch(stationsData, (data) => {
  if (data?.stations) {
    miniSearch.removeAll()
    miniSearch.addAll(data.stations)
    console.log('Sample station:', data.stations[0])
  }
})

const filteredStations = computed(() => {
  if (!stationsData.value?.stations) {
    console.log('filteredStations: no stations data')
    return []
  }
  if (!query.value.trim()) {
    console.log('filteredStations: no query, returning all', stationsData.value.stations.length, 'stations')
    return stationsData.value.stations
  }

  const searchResults = miniSearch.search(query.value, {
    prefix: true,
    fuzzy: 0.2
  })

  const filtered = searchResults.map(result =>
      stationsData.value.stations.find((s: Station) => s.station_id === result.id)
  ).filter((station): station is Station => station !== undefined)

  console.log('filteredStations: search for', query.value, 'returned', filtered.length, 'results')
  return filtered
})

const showStationSelection = computed(() => {
  return parameterSelectionState.value.selection.provider && parameterSelectionState.value.selection.parameters.length > 0
})
</script>

<template>
  <div class="mx-auto max-w-3xl px-4 py-1">
    <ParameterSelection v-model="parameterSelectionState.selection"/>
    <StationSelection v-if="showStationSelection" />
  </div>
</template>