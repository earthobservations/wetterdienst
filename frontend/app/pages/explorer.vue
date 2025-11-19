<script setup lang="ts">
import ParameterSelection from "~/components/ParameterSelection.vue";
import StationMap from "~/components/StationMap.vue";
import MiniSearch from "minisearch";

interface Selection {
  provider: string | undefined
  network: string | undefined
  resolution: string | undefined
  dataset: string | undefined
  parameters: string[]
}

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

let internalUpdate = false;

watch(
  selection,
  (val) => {
    internalUpdate = true;
    router.replace({ query: toQuery(val) });
    internalUpdate = false;
  },
  { deep: true }
);

watch(
  () => route.query,
  (q) => {
    if (internalUpdate) return;
    const next = fromQuery(q);
    // Only update if different to avoid needless reactivity churn
    if (JSON.stringify(next) !== JSON.stringify(selection.value)) {
      selection.value = next;
    }
  }
);

// Show results section after parameter selection
const showResults = computed(() => {
  const result = selection.value.provider && selection.value.parameters.length > 0
  console.log('showResults:', result, 'provider:', selection.value.provider, 'parameters:', selection.value.parameters.length)
  return result
})


const stationsParams = computed(() => {
  if (!selection.value.provider || !selection.value.network || !selection.value.resolution || !selection.value.dataset) return null
  return {
    provider: selection.value.provider,
    network: selection.value.network,
    parameters: `${selection.value.resolution}/${selection.value.dataset}`,
    all: 'true'
  }
})

const { data: stationsData, pending: stationsPending, refresh: refreshStations } = await useFetch<{ stations: Station[] }>(
  '/api/stations',
  {
    query: stationsParams,
    immediate: false,
    default: () => ({ stations: [] })
  }
)

const query = ref('')
const selectedStations = ref<Station[]>([])

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
}, { immediate: true })

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

function toggleStation(station: Station) {
  const index = selectedStations.value.findIndex(s => s.station_id === station.station_id)
  if (index >= 0) {
    selectedStations.value.splice(index, 1)
  } else {
    selectedStations.value.push(station)
    selectedStations.value.sort((a, b) => a.station_id.localeCompare(b.station_id))
  }
}

function removeStation(station: Station) {
  const index = selectedStations.value.findIndex(s => s.station_id === station.station_id)
  if (index >= 0) {
    selectedStations.value.splice(index, 1)
  }
}

</script>

<template>
  <div class="flex flex-col gap-4">
    <div class="px-4 max-w-4xl mx-auto w-full">
      <ParameterSelection v-model="selection" />
    </div>

    <div class="px-4 max-w-4xl mx-auto w-full">
      <UCard v-if="showResults" :ui="{ body: { padding: 'p-0 sm:p-0' } }">
      <template #header>
        <h3 class="text-lg font-semibold">Select Stations</h3>
      </template>

      <div v-if="stationsPending" class="flex justify-center py-8">
        <div class="text-gray-500">Loading stations...</div>
      </div>

      <div v-else-if="!stationsData.stations.length" class="flex justify-center py-8">
        <div class="text-gray-500">No stations found for the selected parameters</div>
      </div>

      <div v-else class="flex flex-col gap-3">
        <div class="px-4 sm:px-6">
          <UInput
            v-model="query"
            icon="i-heroicons-magnifying-glass"
            placeholder="Search stations by ID, name, or state..."
          >
          <template v-if="query" #trailing>
            <UButton
              color="neutral"
              variant="link"
              icon="i-heroicons-x-mark-20-solid"
              :padded="false"
              @click="query = ''"
            />
          </template>
          </UInput>

          <div class="text-sm text-gray-600">
            Showing {{ filteredStations.length }} station(s)
            <span v-if="selectedStations.length > 0"> • {{ selectedStations.length }} selected</span>
          </div>

          <div class="border rounded-lg max-h-96 overflow-y-auto mt-3">
          <div
            v-for="station in filteredStations.slice(0, 100)"
            :key="station.station_id"
            class="p-3 hover:bg-gray-50 border-b last:border-b-0 cursor-pointer flex items-center gap-3"
            @click="toggleStation(station)"
          >
            <UCheckbox
              :model-value="selectedStations.some(s => s.station_id === station.station_id)"
              @click.stop="toggleStation(station)"
            />
            <div class="flex-1">
              <div class="font-medium">{{ station.name }}</div>
              <div class="text-sm text-gray-500">
                ID: {{ station.station_id }} • {{ station.state }}
              </div>
            </div>
          </div>
            <div v-if="filteredStations.length > 100" class="p-3 text-center text-sm text-gray-500 bg-gray-50">
              Showing first 100 of {{ filteredStations.length }} stations. Use search to narrow down results.
            </div>
          </div>

          <div v-if="selectedStations.length > 0" class="mt-2">
          <div class="flex items-center justify-between mb-2">
            <h4 class="text-sm font-medium">Selected Stations:</h4>
            <UButton size="xs" color="neutral" variant="ghost" @click="selectedStations = []">
              Clear all
            </UButton>
          </div>
          <div class="flex flex-wrap gap-2">
            <UBadge
              v-for="station in selectedStations"
              :key="station.station_id"
              color="primary"
              variant="subtle"
              class="cursor-pointer"
              @click="removeStation(station)"
            >
              {{ station.name }} ({{ station.station_id }})
                <span class="ml-1">×</span>
              </UBadge>
            </div>
          </div>
        </div>
      </div>
    </UCard>
    </div>

    <!-- Separate full-width map section - breaks out of container -->
    <div v-if="showResults" class="w-screen relative left-1/2 right-1/2 -mx-[50vw] bg-red-100">
      <div class="p-4 text-sm">
        DEBUG: showResults={{ showResults }}, pending={{ stationsPending }}, stations={{ stationsData.stations.length }}, filtered={{ filteredStations.length }}
      </div>
      <UCard :ui="{ body: { padding: 'p-0 sm:p-0' }, root: 'rounded-none' }">
        <template #header>
          <div class="flex items-center justify-between">
            <h3 class="text-lg font-semibold">Map View</h3>
            <div class="text-sm text-gray-500">
              {{ filteredStations.length }} station(s)
              <span class="ml-2 text-xs">
                (pending: {{ stationsPending }}, stations: {{ stationsData.stations.length }})
              </span>
            </div>
          </div>
        </template>

        <div v-if="stationsPending" class="w-full h-96 flex items-center justify-center bg-yellow-50">
          <div class="text-gray-500">Loading stations for map...</div>
        </div>

        <div v-else-if="!stationsData.stations.length" class="w-full h-96 flex items-center justify-center bg-orange-50">
          <div class="text-gray-500">No stations to display on map</div>
        </div>

        <div v-else class="w-full h-96 bg-purple-50">
          <ClientOnly>
            <StationMap
              :stations="filteredStations"
              :selected-stations="selectedStations"
              @toggle="toggleStation"
            />
            <template #fallback>
              <div class="w-full h-96 flex items-center justify-center bg-yellow-50">
                <div class="text-gray-500">Loading map component...</div>
              </div>
            </template>
          </ClientOnly>
        </div>
      </UCard>
    </div>
  </div>
</template>