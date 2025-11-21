<script setup lang="ts">
import ParameterSelection from "~/components/ParameterSelection.vue";
import StationMap from "~/components/StationMap.vue";
import MiniSearch from "minisearch";
import StationSelection from "~/components/StationSelection.vue";

interface ParameterSelection {
  provider: string | undefined
  network: string | undefined
  resolution: string | undefined
  dataset: string | undefined
  parameters: string[]
}

const parameterSelection = useState()

interface Station {
  station_id: string
  name: string
  state: string
  latitude: number
  longitude: number
}

const route = useRoute();
const router = useRouter();

const fromQuery = (q: Record<string, any>): Selection => {
  return {
    provider: q.provider?.toString(),
    network: q.network?.toString(),
    resolution: q.resolution?.toString(),
    dataset: q.dataset?.toString(),
    parameters: q.parameters
        ? q.parameters.toString().split(",").filter(Boolean)
        : []
  };
}

const toQuery = (sel: Selection): Record<string, string> => {
  const q: Record<string, string> = {};
  if (sel.provider) q.provider = sel.provider;
  if (sel.network) q.network = sel.network;
  if (sel.resolution) q.resolution = sel.resolution;
  if (sel.dataset) q.dataset = sel.dataset;
  if (sel.parameters.length) q.parameters = sel.parameters.join(",");
  return q;
}

const selection = ref<Selection>(fromQuery(route.query))


watch(
    selection,
    (val) => router.replace({query: toQuery(val)}),
    {deep: true}
);

watch(
    () => route.query,
    (q) => {
      const next = fromQuery(q);
      // Only update if different to avoid needless reactivity churn
      if (JSON.stringify(next) !== JSON.stringify(selection.value)) {
        selection.value = next;
      }
    }
);

const stationsParams = computed(() => {
  if (!selection.value.provider || !selection.value.network || !selection.value.resolution || !selection.value.dataset) return null
  return {
    provider: selection.value.provider,
    network: selection.value.network,
    parameters: `${selection.value.resolution}/${selection.value.dataset}`,
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
  return selection.value.provider && selection.value.parameters.length > 0
})
</script>

<template>
  <div class="mx-auto max-w-3xl px-4">
    <div class="flex flex-col">
      <ParameterSelection v-model="selection"/>
    </div>
    <div>
      <StationSelection v-if="showStationSelection" />
    </div>
  </div>
</template>