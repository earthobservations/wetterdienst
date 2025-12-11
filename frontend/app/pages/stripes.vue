<script setup lang="ts">
interface StripesStation {
  station_id: string
  name: string
  state: string
  latitude: number
  longitude: number
  start_date: string
  end_date: string
}

const kind = ref<'temperature' | 'precipitation'>('temperature')
const selectedStation = ref<StripesStation | null>(null)
const startYear = ref<number | null>(null)
const endYear = ref<number | null>(null)
const showTitle = ref(true)
const showYears = ref(true)
const showDataAvailability = ref(true)
const imageFormat = ref<'png' | 'svg'>('png')

const { data: stationsData, pending: stationsPending } = useFetch<{ stations: StripesStation[] }>(
  '/api/stripes/stations',
  {
    query: { kind },
  },
)

const stations = computed(() => stationsData.value?.stations ?? [])

const stationItems = computed(() =>
  stations.value.map(s => ({
    label: `${s.name} (${s.station_id})`,
    value: s.station_id,
  })),
)

const selectedStationItem = computed({
  get: () => selectedStation.value
    ? {
        label: `${selectedStation.value.name} (${selectedStation.value.station_id})`,
        value: selectedStation.value.station_id,
      }
    : undefined,
  set: (item: { label: string, value: string } | undefined) => {
    if (!item) {
      selectedStation.value = null
      return
    }
    selectedStation.value = stations.value.find(s => s.station_id === item.value) ?? null
  },
})

const stripesUrl = computed(() => {
  if (!selectedStation.value)
    return null

  const params = new URLSearchParams()
  params.set('kind', kind.value)
  params.set('station', selectedStation.value.station_id)
  params.set('format', imageFormat.value)
  params.set('show_title', String(showTitle.value))
  params.set('show_years', String(showYears.value))
  params.set('show_data_availability', String(showDataAvailability.value))

  if (startYear.value)
    params.set('start_year', String(startYear.value))
  if (endYear.value)
    params.set('end_year', String(endYear.value))

  return `/api/stripes/values?${params.toString()}`
})

const imageLoading = ref(false)
function onImageLoad() {
  imageLoading.value = false
}

watch(stripesUrl, () => {
  if (stripesUrl.value) {
    imageLoading.value = true
  }
})

watch(kind, () => {
  selectedStation.value = null
})
</script>

<template>
  <div class="max-w-6xl mx-auto py-8 px-4">
    <div class="text-center mb-8">
      <h1 class="text-4xl font-bold mb-4">
        Climate Stripes
      </h1>
      <p class="text-gray-600 dark:text-gray-400">
        Visualize long-term climate trends with warming/cooling stripes
      </p>
    </div>

    <div class="grid grid-cols-1 lg:grid-cols-3 gap-8">
      <UCard class="lg:col-span-1">
        <template #header>
          <h2 class="text-lg font-semibold">
            Settings
          </h2>
        </template>

        <div class="space-y-4">
          <div>
            <label class="block text-sm font-medium mb-1">Type</label>
            <USelect v-model="kind" :items="['temperature', 'precipitation']" />
          </div>

          <div>
            <label class="block text-sm font-medium mb-1">Station</label>
            <USelectMenu
              v-model="selectedStationItem"
              :items="stationItems"
              searchable
              :loading="stationsPending"
              placeholder="Select a station..."
              class="w-full"
            />
          </div>

          <div v-if="selectedStation" class="text-sm text-gray-600 dark:text-gray-400 space-y-1">
            <p><strong>State:</strong> {{ selectedStation.state }}</p>
            <p><strong>Available:</strong> {{ selectedStation.start_date?.slice(0, 4) }} - {{ selectedStation.end_date?.slice(0, 4) }}</p>
          </div>

          <USeparator />

          <div class="grid grid-cols-2 gap-4">
            <div>
              <label class="block text-sm font-medium mb-1">Start Year</label>
              <UInput v-model.number="startYear" type="number" placeholder="Auto" />
            </div>
            <div>
              <label class="block text-sm font-medium mb-1">End Year</label>
              <UInput v-model.number="endYear" type="number" placeholder="Auto" />
            </div>
          </div>

          <USeparator />

          <div class="space-y-2">
            <UCheckbox v-model="showTitle" label="Show title" />
            <UCheckbox v-model="showYears" label="Show years" />
            <UCheckbox v-model="showDataAvailability" label="Show data availability" />
          </div>

          <div>
            <label class="block text-sm font-medium mb-1">Format</label>
            <USelect v-model="imageFormat" :items="['png', 'svg']" />
          </div>
        </div>
      </UCard>

      <UCard class="lg:col-span-2">
        <template #header>
          <div class="flex items-center justify-between">
            <h2 class="text-lg font-semibold">
              Visualization
            </h2>
            <UButton
              v-if="stripesUrl"
              :to="stripesUrl"
              target="_blank"
              size="xs"
              variant="outline"
              icon="i-lucide-download"
            >
              Download
            </UButton>
          </div>
        </template>

        <div v-if="!selectedStation" class="flex items-center justify-center h-64 text-gray-500">
          Select a station to generate climate stripes
        </div>
        <div v-else class="flex flex-col items-center justify-center">
          <div v-if="imageLoading" class="flex items-center gap-2 text-gray-500 mb-4">
            <UIcon name="i-lucide-loader-2" class="animate-spin" />
            Loading stripes...
          </div>
          <img :src="stripesUrl!" :alt="`Climate stripes for ${selectedStation.name}`" class="max-w-full h-auto" @load="onImageLoad">
        </div>
      </UCard>
    </div>

    <UCard class="mt-8">
      <template #header>
        <h2 class="text-lg font-semibold">
          About Climate Stripes
        </h2>
      </template>
      <p class="text-gray-600 dark:text-gray-400 mb-4">
        Climate stripes (also known as warming stripes) are a data visualization designed to communicate
        the long-term increase in temperatures. Each stripe represents the average temperature for a single year,
        with blue indicating cooler years and red indicating warmer years.
      </p>
      <p class="text-gray-600 dark:text-gray-400">
        The visualization was created by climate scientist Ed Hawkins and has become an iconic representation
        of climate change. This tool uses data from the German Weather Service (DWD) observation network.
      </p>
    </UCard>
  </div>
</template>
