<script setup lang="ts">
import StationMap from "~/components/StationMap.vue";
import type {Station} from "~/types/station.type";
import type {ParameterSelectionState} from "~/types/parameter-selection-state.type";
import MiniSearch from "minisearch";
import StationSelectionSearchSelect from "~/components/StationSelectionSearchSelect.vue";

const props = defineProps<{ parameterSelection: ParameterSelectionState["selection"] }>()
const selectedStations = useState<Station[]>(() => [])

const {data: stationsData, pending: stationsPending, refresh: refreshStations} = await useFetch<{
  stations: Station[]
}>(
    '/api/stations',
    {
      query: {
        provider: props.parameterSelection.provider,
        network: props.parameterSelection.network,
        parameters: `${props.parameterSelection.resolution}/${props.parameterSelection.dataset}`,
        all: 'true'
      },
      immediate: false,
      default: () => ({stations: []})
    }
)

// function toggleStation(station: Station) {
//   const index = selectedStations.value.findIndex(s => s.station_id === station.station_id)
//   if (index >= 0) {
//     selectedStations.value.splice(index, 1)
//   } else {
//     selectedStations.value.push(station)
//     selectedStations.value.sort((a, b) => a.station_id.localeCompare(b.station_id))
//   }
// }
//
// function removeStation(station: Station) {
//   const index = selectedStations.value.findIndex(s => s.station_id === station.station_id)
//   if (index >= 0) {
//     selectedStations.value.splice(index, 1)
//   }
// }

watch(props.parameterSelection, () => {
  if (!props.parameterSelection.parameters.length) {
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
  <UContainer>
    <StationSelectionSearchSelect :all-stations="stationsData.stations" :selected-stations="selectedStations"/>
<!--      <UCard :ui="{ body: { padding: 'p-0 sm:p-0' } }">-->
<!--    <template #header>-->
<!--      <h3 class="text-lg font-semibold">Select Stations</h3>-->
<!--    </template>-->

<!--    <div v-if="stationsPending" class="flex justify-center py-8">-->
<!--      <div class="text-gray-500">Loading stations...</div>-->
<!--    </div>-->

<!--    <div v-else-if="!stationsData.stations.length" class="flex justify-center py-8">-->
<!--      <div class="text-gray-500">No stations found for the selected parameters</div>-->
<!--    </div>-->

<!--    <div v-else class="flex flex-col gap-3">-->
<!--      <div class="px-4 sm:px-6">-->
<!--        <UInput-->
<!--            v-model="query"-->
<!--            icon="i-heroicons-magnifying-glass"-->
<!--            placeholder="Search stations by ID, name, or state..."-->
<!--        >-->
<!--          <template v-if="query" #trailing>-->
<!--            <UButton-->
<!--                color="neutral"-->
<!--                variant="link"-->
<!--                icon="i-heroicons-x-mark-20-solid"-->
<!--                :padded="false"-->
<!--                @click="query = ''"-->
<!--            />-->
<!--          </template>-->
<!--        </UInput>-->

<!--        <div class="text-sm text-gray-600">-->
<!--          Showing {{ filteredStations.length }} station(s)-->
<!--          <span v-if="selectedStations.length > 0"> • {{ selectedStations.length }} selected</span>-->
<!--        </div>-->

<!--        <div class="border rounded-lg max-h-96 overflow-y-auto mt-3">-->
<!--          <div-->
<!--              v-for="station in filteredStations.slice(0, 100)"-->
<!--              :key="station.station_id"-->
<!--              class="p-3 hover:bg-gray-50 border-b last:border-b-0 cursor-pointer flex items-center gap-3"-->
<!--              @click="toggleStation(station)"-->
<!--          >-->
<!--            <UCheckbox-->
<!--                :model-value="selectedStations.some(s => s.station_id === station.station_id)"-->
<!--                @click.stop="toggleStation(station)"-->
<!--            />-->
<!--            <div class="flex-1">-->
<!--              <div class="font-medium">{{ station.name }}</div>-->
<!--              <div class="text-sm text-gray-500">-->
<!--                ID: {{ station.station_id }} • {{ station.state }}-->
<!--              </div>-->
<!--            </div>-->
<!--          </div>-->
<!--          <div v-if="filteredStations.length > 100" class="p-3 text-center text-sm text-gray-500 bg-gray-50">-->
<!--            Showing first 100 of {{ filteredStations.length }} stations. Use search to narrow down results.-->
<!--          </div>-->
<!--        </div>-->

<!--        <div v-if="selectedStations.length > 0" class="mt-2">-->
<!--          <div class="flex items-center justify-between mb-2">-->
<!--            <h4 class="text-sm font-medium">Selected Stations:</h4>-->
<!--            <UButton size="xs" color="neutral" variant="ghost" @click="selectedStations = []">-->
<!--              Clear all-->
<!--            </UButton>-->
<!--          </div>-->
<!--          <div class="flex flex-wrap gap-2">-->
<!--            <UBadge-->
<!--                v-for="station in selectedStations"-->
<!--                :key="station.station_id"-->
<!--                color="primary"-->
<!--                variant="subtle"-->
<!--                class="cursor-pointer"-->
<!--                @click="removeStation(station)"-->
<!--            >-->
<!--              {{ station.name }} ({{ station.station_id }})-->
<!--              <span class="ml-1">×</span>-->
<!--            </UBadge>-->
<!--          </div>-->
<!--        </div>-->
<!--      </div>-->
<!--    </div>-->
<!--  </UCard>-->

<!--  &lt;!&ndash; Separate full-width map section - breaks out of container &ndash;&gt;-->
<!--  <div class="w-screen relative left-1/2 right-1/2 -mx-[50vw] bg-red-100">-->
<!--    <UCard :ui="{ body: { padding: 'p-0 sm:p-0' }, root: 'rounded-none' }">-->
<!--      <template #header>-->
<!--        <div class="flex items-center justify-between">-->
<!--          <h3 class="text-lg font-semibold">Map View</h3>-->
<!--          <div class="text-sm text-gray-500">-->
<!--            {{ filteredStations.length }} station(s)-->
<!--            <span class="ml-2 text-xs">-->
<!--                (pending: {{ stationsPending }}, stations: {{ stationsData.stations.length }})-->
<!--              </span>-->
<!--          </div>-->
<!--        </div>-->
<!--      </template>-->

<!--      <div v-if="stationsPending" class="w-full h-96 flex items-center justify-center bg-yellow-50">-->
<!--        <div class="text-gray-500">Loading stations for map...</div>-->
<!--      </div>-->

<!--      <div v-else-if="!stationsData.stations.length"-->
<!--           class="w-full h-96 flex items-center justify-center bg-orange-50">-->
<!--        <div class="text-gray-500">No stations to display on map</div>-->
<!--      </div>-->

<!--      <div v-else class="w-full h-96 bg-purple-50">-->
<!--        <ClientOnly>-->
<!--          <StationMap-->
<!--              :stations="filteredStations"-->
<!--              :selected-stations="selectedStations"-->
<!--              @toggle="toggleStation"-->
<!--          />-->
<!--          <template #fallback>-->
<!--            <div class="w-full h-96 flex items-center justify-center bg-yellow-50">-->
<!--              <div class="text-gray-500">Loading map component...</div>-->
<!--            </div>-->
<!--          </template>-->
<!--        </ClientOnly>-->
<!--      </div>-->
<!--    </UCard>-->
<!--  </div>-->
  </UContainer>
</template>
