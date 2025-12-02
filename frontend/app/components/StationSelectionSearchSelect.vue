<script setup lang="ts">
import type {Station} from "~/types/station.type";

const { stationsPending, allStations } = defineProps<{ stationsPending: boolean, allStations: Station[]}>()

const selectedStations = defineModel<Station[]>('selectedStations', { required: true, default: () => [] })

// Items for the select menu
const stationItems = computed(() =>
  (allStations || []).map(station => ({
    label: `${station.name} (ID: ${station.station_id}, ${station.state})`,
    value: station.station_id
  }))
)

// Bridge between Station[] and item objects
const selectedItems = computed({
  get: () => selectedStations.value.map(s => ({
    label: `${s.name} (ID: ${s.station_id}, ${s.state})`,
    value: s.station_id
  })),
  set: (items: { label: string; value: string }[]) => {
    selectedStations.value = items
      .map(item => allStations.find(s => s.station_id === item.value))
      .filter((s): s is Station => s !== undefined)
      .sort((a, b) => a.station_id.localeCompare(b.station_id))
  }
})

function removeStation(station: Station) {
  const index = selectedStations.value.findIndex(s => s.station_id === station.station_id)
  if (index >= 0) {
    selectedStations.value.splice(index, 1)
  }
}

</script>
<template>
  <div class="flex flex-col gap-3">
    <div>
      <USelectMenu
          v-model="selectedItems"
          multiple
          searchable
          :items="stationItems"
          class="w-full"
      />
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
</template>