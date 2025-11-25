<script setup lang="ts">
import MiniSearch from "minisearch";
import type {Station} from "~/types/station.type";
import type {ParameterSelectionState} from "~/types/parameter-selection-state.type";

const props = defineProps<{ allStations: Station[], selectedStations: Station[] }>()

const query = useState(() => "")

const miniSearch = new MiniSearch({
  fields: ["station_id", "name", "state"],
  idField: "station_id"
})

watch(props.allStations, (stations) => {
  if (stations) {
    miniSearch.removeAll()
    miniSearch.addAll(stations)
  }
})

const filteredStations = computed(() => {
  if (!props.allStations) {
    return []
  }
  if (!query.value.trim()) {
    return props.allStations
  }

  const searchResults = miniSearch.search(query.value, {
    prefix: true,
    fuzzy: 0.2
  })

  return searchResults.map(result =>
      props.allStations.find((s: Station) => s.station_id === result.id)
  ).filter((station): station is Station => station !== undefined)
})
</script>
<template>
  <UContainer>

  </UContainer>
</template>