<script setup lang="ts">
import type { Station } from '#shared/types/api'
import Meteogram from '~/components/Meteogram.vue'
import MeteogramStationSearch from '~/components/MeteogramStationSearch.vue'

// Auto-composed MOSMIX parameters – user never configures these
const MOSMIX = {
  provider: 'dwd',
  network: 'mosmix',
  resolution: 'hourly',
  dataset: 'large',
  // Core meteogram parameters: temperature, wind, cloud cover, precipitation, significant weather, pressure, dew point, wind gusts, max temp, min temp
  parameters: ['ttt', 'td', 'ff', 'dd', 'fx1', 'n', 'nl', 'nm', 'nh', 'rr1c', 'ww', 'pppp', 'tx', 'tn'],
}

const route = useRoute()
const router = useRouter()

const selectedStation = ref<Station | null>(null)
const values = ref<any[]>([])
const pending = ref(false)
const error = ref<string | null>(null)

async function fetchMeteogram(station: Station) {
  pending.value = true
  error.value = null
  values.value = []

  const params = new URLSearchParams({
    provider: MOSMIX.provider,
    network: MOSMIX.network,
    parameters: MOSMIX.parameters.map(p => `${MOSMIX.resolution}/${MOSMIX.dataset}/${p}`).join(','),
    station: station.station_id,
  })

  try {
    const res = await fetch(`/api/values?${params}`)
    if (!res.ok) {
      error.value = `Backend error ${res.status}: ${await res.text()}`
      return
    }
    const json = await res.json()
    values.value = json.values ?? []
  }
  catch (e: any) {
    error.value = e?.message ?? 'Request failed'
  }
  finally {
    pending.value = false
  }
}

// Auto-fetch and sync URL whenever a station is chosen or cleared
watch(selectedStation, (station) => {
  if (station) {
    void fetchMeteogram(station)
    void router.replace({ query: { station: station.station_id } })
  }
  else {
    values.value = []
    error.value = null
    void router.replace({ query: {} })
  }
})

// Restore selected station from URL query param on page load
onMounted(async () => {
  const stationId = route.query.station as string | undefined
  if (!stationId)
    return
  try {
    const res = await $fetch<{ stations: Station[] }>('/api/stations', {
      query: {
        provider: MOSMIX.provider,
        network: MOSMIX.network,
        parameters: `${MOSMIX.resolution}/${MOSMIX.dataset}`,
        station: stationId,
      },
    })
    const station = (res.stations ?? [])[0]
    if (station)
      selectedStation.value = station
  }
  catch {
    // ignore – station ID in URL may be invalid, just start fresh
  }
})
</script>

<template>
  <UContainer class="mx-auto max-w-4xl px-4 py-8 space-y-6">
    <!-- Header -->
    <div class="text-center space-y-2">
      <h1 class="text-3xl font-bold">
        Meteogram
      </h1>
      <p class="text-gray-500 dark:text-gray-400">
        DWD MOSMIX forecast — temperature, precipitation and wind
      </p>
    </div>

    <!-- Station search -->
    <UCard>
      <template #header>
        <div class="flex items-center gap-2">
          <UIcon name="i-lucide-map-pin" class="text-primary-500" />
          <span class="font-semibold">Select station</span>
        </div>
      </template>
      <MeteogramStationSearch v-model="selectedStation" />
    </UCard>

    <!-- Loading state -->
    <div v-if="pending" class="flex items-center justify-center gap-3 py-12 text-gray-500">
      <UIcon name="i-lucide-loader-circle" class="w-6 h-6 animate-spin text-primary-500" />
      <span>Fetching MOSMIX forecast…</span>
    </div>

    <!-- Error state -->
    <UAlert
      v-else-if="error"
      color="error"
      variant="subtle"
      icon="i-lucide-alert-circle"
      :title="error"
    />

    <!-- Meteogram chart -->
    <UCard v-else-if="selectedStation && values.length > 0">
      <template #header>
        <div class="flex items-center gap-2">
          <UIcon name="i-lucide-cloud-sun" class="text-primary-500" />
          <span class="font-semibold">{{ selectedStation.name }}</span>
          <span class="text-gray-400 text-sm">({{ selectedStation.station_id }})</span>
        </div>
      </template>
      <Meteogram
        :values="values"
        :station-name="selectedStation.name"
        :station-coords="{ latitude: selectedStation.latitude, longitude: selectedStation.longitude }"
      />
    </UCard>

    <!-- Empty state before selection -->
    <div
      v-else-if="!selectedStation"
      class="rounded-xl border-2 border-dashed border-gray-200 dark:border-gray-700 p-16 text-center text-gray-400 space-y-2"
    >
      <UIcon name="i-lucide-cloud-sun" class="w-12 h-12 mx-auto opacity-30" />
      <p class="text-sm">
        Search for a station above to generate a meteogram
      </p>
    </div>
  </UContainer>
</template>
