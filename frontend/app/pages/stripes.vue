<script setup lang="ts">
import { defineAsyncComponent } from 'vue'

const MapStations = defineAsyncComponent(() => import('~/components/MapStations.vue'))

const kind = ref<StripesKind>('temperature')
const selectedStation = ref<StripesStation | null>(null)
const startYear = ref<number | null>(null)
const endYear = ref<number | null>(null)
const showTitle = ref(true)
const showYears = ref(true)
const showDataAvailability = ref(true)
const imageFormat = ref<'png' | 'svg'>('png')

const _stationSelectionModel = undefined // kept for future use

const { data: stationsData, pending: stationsPending } = useFetch<StripesStationsResponse>(
  '/api/stripes/stations',
  {
    query: { kind },
  },
)

const stations = computed(() => stationsData.value?.stations ?? [])

const stationItems = computed(() => stations.value.map(s => ({ label: `${s.name} (ID: ${s.station_id})`, value: s.station_id })))

const selectedStationId = computed({
  get: () => selectedStation.value ? selectedStation.value.station_id : null,
  set: (id: string | null) => {
    selectedStation.value = id ? stations.value.find(s => s.station_id === id) ?? null : null
  },
})

// USelectMenu (when used with :multiple="false") expects a single item or undefined
const selectedStationItem = computed<{ label: string, value: string } | undefined>({
  get: () => selectedStation.value ? { label: `${selectedStation.value.name} (ID: ${selectedStation.value.station_id})`, value: selectedStation.value.station_id } : undefined,
  set: (item: { label: string, value: string } | undefined) => {
    if (!item) {
      selectedStationId.value = null
    }
    else {
      selectedStationId.value = item.value
    }
  },
})

const showMap = ref(false)
const showAbout = ref(false)
const imageLoading = ref(false)

// Track last fetched parameters
const lastFetchedParams = ref<{
  kind: string
  stationId: string
  format: string
  showTitle: boolean
  showYears: boolean
  showDataAvailability: boolean
  startYear: number | null
  endYear: number | null
} | null>(null)

const stripesUrl = computed(() => {
  if (!lastFetchedParams.value)
    return null

  const params = new URLSearchParams()
  params.set('kind', lastFetchedParams.value.kind)
  params.set('station', lastFetchedParams.value.stationId)
  params.set('format', lastFetchedParams.value.format)
  params.set('show_title', String(lastFetchedParams.value.showTitle))
  params.set('show_years', String(lastFetchedParams.value.showYears))
  params.set('show_data_availability', String(lastFetchedParams.value.showDataAvailability))

  if (lastFetchedParams.value.startYear)
    params.set('start_year', String(lastFetchedParams.value.startYear))
  if (lastFetchedParams.value.endYear)
    params.set('end_year', String(lastFetchedParams.value.endYear))

  return `/api/stripes/values?${params.toString()}`
})

// Check if we can fetch
const canFetch = computed(() => {
  if (!selectedStation.value)
    return false

  // Check if parameters have changed since last fetch
  if (lastFetchedParams.value) {
    const unchanged
      = lastFetchedParams.value.kind === kind.value
        && lastFetchedParams.value.stationId === selectedStation.value.station_id
        && lastFetchedParams.value.format === imageFormat.value
        && lastFetchedParams.value.showTitle === showTitle.value
        && lastFetchedParams.value.showYears === showYears.value
        && lastFetchedParams.value.showDataAvailability === showDataAvailability.value
        && lastFetchedParams.value.startYear === startYear.value
        && lastFetchedParams.value.endYear === endYear.value

    if (unchanged) {
      return false
    }
  }

  return true
})

function fetchStripes() {
  if (!canFetch.value || !selectedStation.value)
    return

  // Store current parameters
  lastFetchedParams.value = {
    kind: kind.value,
    stationId: selectedStation.value.station_id,
    format: imageFormat.value,
    showTitle: showTitle.value,
    showYears: showYears.value,
    showDataAvailability: showDataAvailability.value,
    startYear: startYear.value,
    endYear: endYear.value,
  }

  imageLoading.value = true
}

function clearStripes() {
  // Only clear the fetched image, keep all form inputs
  lastFetchedParams.value = null
  imageLoading.value = false
}

const route = useRoute()
const router = useRouter()

// Preserve initial station id from URL so we can apply it once stations have loaded
const initialStationId = ref<string | null>(route.query.station?.toString() ?? null)

// Initialize simple options from URL if present
if (route.query.kind)
  kind.value = route.query.kind.toString() as StripesKind
if (route.query.format)
  imageFormat.value = (route.query.format.toString() as 'png' | 'svg') ?? imageFormat.value
if (route.query.show_title !== undefined && route.query.show_title !== null)
  showTitle.value = route.query.show_title?.toString() === 'true'
if (route.query.show_years !== undefined && route.query.show_years !== null)
  showYears.value = route.query.show_years?.toString() === 'true'
if (route.query.show_data_availability !== undefined && route.query.show_data_availability !== null)
  showDataAvailability.value = route.query.show_data_availability?.toString() === 'true'
if (route.query.start_year)
  startYear.value = Number(route.query.start_year.toString())
if (route.query.end_year)
  endYear.value = Number(route.query.end_year.toString())

function onSelectMenuUpdate(val: any) {
  // Normalize incoming value from the select/menu or map into a single item or null
  const item = val ? (Array.isArray(val) ? val[0] : val) : null
  // selectedStationItem is a single item or undefined
  selectedStationItem.value = item ?? undefined
  const id = item ? item.value : null
  selectedStation.value = id ? stations.value.find(s => s.station_id === id) ?? null : null
}

function onImageLoad() {
  imageLoading.value = false
}

watch(kind, () => {
  selectedStation.value = null
})

// Ensure select menu updates selection when stations load or when user selects from list
watch(stations, () => {
  // If the selectedStation is not in the stations array, clear it
  if (selectedStation.value) {
    const selId = selectedStation.value.station_id
    if (!stations.value.find(s => s.station_id === selId)) {
      selectedStation.value = null
      // clear selection
      selectedStationItem.value = undefined
    }
  }
  // If an initial station id was provided in the URL, apply it when stations are available
  if (initialStationId.value) {
    const found = stations.value.find(s => s.station_id === initialStationId.value)
    if (found) {
      selectedStation.value = found
      // set the single selected item
      selectedStationItem.value = { label: `${found.name} (ID: ${found.station_id})`, value: found.station_id }
    }
    initialStationId.value = null
  }
  // If there is only one station in the list, preselect it
  if (!selectedStation.value && stations.value.length === 1) {
    const only = stations.value[0]
    if (only)
      selectedStationId.value = only.station_id
  }
})

function onMapSelectedStations(val?: StripesStation[] | null) {
  if (val && val.length) {
    const s = val[0]
    if (s)
      onSelectMenuUpdate({ label: s.name, value: s.station_id })
    else onSelectMenuUpdate(null)
  }
  else {
    onSelectMenuUpdate(null)
  }
}

// Update URL query when relevant options change
function stripesToQuery(): Record<string, string> {
  const q: Record<string, string> = {}
  if (kind.value)
    q.kind = kind.value
  if (selectedStation.value)
    q.station = selectedStation.value.station_id
  if (imageFormat.value)
    q.format = imageFormat.value
  if (showTitle.value !== undefined)
    q.show_title = String(showTitle.value)
  if (showYears.value !== undefined)
    q.show_years = String(showYears.value)
  if (showDataAvailability.value !== undefined)
    q.show_data_availability = String(showDataAvailability.value)
  if (startYear.value !== null && startYear.value !== undefined)
    q.start_year = String(startYear.value)
  if (endYear.value !== null && endYear.value !== undefined)
    q.end_year = String(endYear.value)
  return q
}

watch([
  () => selectedStation?.value?.station_id,
  () => kind.value,
  () => imageFormat.value,
  () => showTitle.value,
  () => showYears.value,
  () => showDataAvailability.value,
  () => startYear.value,
  () => endYear.value,
], () => {
  // Use replace to avoid polluting history while keeping URL in sync
  router.replace({ query: stripesToQuery() })
})

// Update selectedStation when selectedStationItem changes (from the select menu or map)
watch(selectedStationItem, (item) => {
  // selectedStationItem is a single item or undefined
  const id = item ? item.value : null
  selectedStation.value = id ? stations.value.find(s => s.station_id === id) ?? null : null
})
</script>

<template>
  <UContainer class="mx-auto max-w-3xl px-4 py-6">
    <div class="text-center mb-8">
      <h1 class="text-4xl font-bold mb-4">
        Climate Stripes
      </h1>
      <p class="text-gray-600 dark:text-gray-400">
        Visualize long-term climate trends with warming/cooling stripes
      </p>
    </div>

    <UCollapsible v-model="showAbout" class="mb-6">
      <UButton
        label="About Climate Stripes"
        variant="subtle"
        color="neutral"
        trailing-icon="i-lucide-chevron-down"
        block
        size="sm"
      />
      <template #content>
        <UCard>
          <p class="text-gray-600 dark:text-gray-400 mb-4">
            Climate stripes (also known as warming stripes) are a data visualization designed to communicate the long-term increase in temperatures. Each stripe represents the average temperature for a single year, with blue indicating cooler years and red indicating warmer years.
          </p>
          <p class="text-gray-600 dark:text-gray-400">
            The visualization was created by climate scientist Ed Hawkins and has become an iconic representation of climate change. This tool uses data from the German Weather Service (DWD) observation network.
          </p>
        </UCard>
      </template>
    </UCollapsible>

    <UCard class="mb-6">
      <template #header>
        <h2 class="text-lg font-semibold">
          Settings
        </h2>
      </template>
      <div class="space-y-4 p-4">
        <div>
          <label class="block text-sm font-medium mb-1">Type</label>
          <USelect v-model="kind" :items="['temperature', 'precipitation']" />
        </div>

        <div>
          <label class="block text-sm font-medium mb-1">Station</label>
          <USelectMenu
            v-model="selectedStationItem"
            :items="stationItems"
            :multiple="false"
            searchable
            color="primary"
            class="w-full"
            :placeholder="selectedStation ? `${selectedStation?.name} (ID: ${selectedStation?.station_id})` : 'Select a station'"
            @update:model-value="onSelectMenuUpdate"
          />

          <UCollapsible v-model="showMap" class="mt-3">
            <UButton
              label="Show map"
              variant="subtle"
              color="neutral"
              trailing-icon="i-lucide-chevron-down"
              block
              size="sm"
            />
            <template #content>
              <ClientOnly>
                <MapStations
                  :stations="stations"
                  :selected-stations="selectedStation ? [selectedStation] : []"
                  :multiple="false"
                  @update:selected-stations="onMapSelectedStations"
                />
              </ClientOnly>
            </template>
          </UCollapsible>
        </div>

        <div v-if="stationsPending" class="text-sm text-gray-600 dark:text-gray-400">
          Loading stations...
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

        <USeparator />

        <div class="flex flex-col sm:flex-row gap-2">
          <UButton label="Fetch" color="primary" :disabled="!canFetch" class="w-full" @click="fetchStripes" />
          <UButton label="Clear" variant="outline" class="w-full" @click="clearStripes" />
        </div>
      </div>
    </UCard>
    <UCard class="mb-6">
      <template #header>
        <div class="flex items-center justify-between">
          <h2 class="text-lg font-semibold">
            Visualization
          </h2>
          <UButton v-if="stripesUrl" :to="stripesUrl" target="_blank" size="xs" variant="outline" icon="i-lucide-download">
            Download
          </UButton>
        </div>
      </template>

      <div v-if="!stripesUrl" class="flex items-center justify-center h-64 text-gray-500">
        Select a station and click Fetch to generate climate stripes
      </div>
      <div v-else class="flex flex-col items-center justify-center">
        <div v-if="imageLoading" class="flex items-center gap-2 text-gray-500 mb-4">
          <UIcon name="i-lucide-loader-2" class="animate-spin" />
          Loading stripes...
        </div>
        <img v-if="stripesUrl" :src="stripesUrl" alt="Climate stripes" class="max-w-full h-auto" @load="onImageLoad">
      </div>
    </UCard>
  </UContainer>
</template>
