<script setup lang="ts">
import type { Station } from '#shared/types/api'
import type { RequestError } from '~/utils/request-error'
import { nextTick } from 'vue'
import Meteogram from '~/components/Meteogram.vue'
import MeteogramStationSearch from '~/components/MeteogramStationSearch.vue'
import { METEOGRAM_VALUES_SETTINGS } from '~/utils/meteogram'
import { backendFailure, describeRequestError } from '~/utils/request-error'

const { MapStations, notLoaded: mapNotLoaded } = useMapStations()

// Auto-composed MOSMIX parameters – user never configures these
const MOSMIX = {
  provider: 'dwd',
  network: 'mosmix',
  resolution: 'hourly',
  dataset: 'large',
  // Core meteogram parameters: temperature, wind, cloud cover, precipitation, significant weather, pressure, dew point, wind gusts, max temp, min temp
  parameters: ['ttt', 'td', 'ff', 'dd', 'fx1', 'n', 'nl', 'nm', 'nh', 'rr1c', 'ww', 'pppp', 'tx', 'tn'],
}

const { t } = useI18n()

// the title says which page this is: WCAG 2.4.2, and what a screen reader announces after a navigation
useHead({ title: () => t('meteogram.title') })
const route = useRoute()
const router = useRouter()

const selectedStation = ref<Station | null>(null)
const values = ref<any[]>([])
const pending = ref(false)
// why the request failed, as data: the message is written at render, in the language of the moment
const failure = ref<RequestError | null>(null)
const error = computed(() => failure.value ? describeRequestError(failure.value, t) : null)

// '' = latest (auto), iso string = a specific run
const selectedIssue = ref<string>('')

// Prevents watch(selectedStation) from resetting selectedIssue when restoring from URL
const isRestoringFromUrl = ref(false)

// Real list of available runs fetched from the backend — populated when a station is selected.
const availableIssues = ref<string[]>([])

function formatIssueLabel(iso: string): string {
  const d = new Date(iso)
  const dd = String(d.getUTCDate()).padStart(2, '0')
  const mm = String(d.getUTCMonth() + 1).padStart(2, '0')
  const yyyy = d.getUTCFullYear()
  const hh = String(d.getUTCHours()).padStart(2, '0')
  return `${dd}.${mm}.${yyyy} – ${hh}:00 UTC`
}

const runItems = computed(() => [
  { label: t('meteogram.runLatest'), value: '' },
  ...availableIssues.value.slice().reverse().map(iso => ({
    label: formatIssueLabel(iso),
    value: iso.slice(0, 19),
  })),
])

async function loadAvailableIssues(stationId: string) {
  try {
    const res = await $fetch<{ issues: string[] }>('/api/issues', {
      query: { provider: MOSMIX.provider, network: MOSMIX.network, station: stationId },
      ...RETRY_TRANSIENT,
    })
    availableIssues.value = res.issues ?? []
  }
  catch {
    availableIssues.value = []
  }
}

// Optional map picker. The full MOSMIX station list is large, so it is only
// fetched the first time the user opens the map — search stays the default.
const showMap = ref(false)
const mapStations = ref<Station[]>([])
const mapLoading = ref(false)

const selectedStationsArray = computed(() => (selectedStation.value ? [selectedStation.value] : []))

async function loadMapStations() {
  if (mapStations.value.length || mapLoading.value)
    return
  mapLoading.value = true
  try {
    const res = await $fetch<{ stations: Station[] }>('/api/stations', {
      query: {
        provider: MOSMIX.provider,
        network: MOSMIX.network,
        parameters: `${MOSMIX.resolution}/${MOSMIX.dataset}`,
        all: 'true',
      },
      ...RETRY_TRANSIENT,
    })
    mapStations.value = res.stations ?? []
  }
  catch {
    // ignore – user can fall back to search
  }
  finally {
    mapLoading.value = false
  }
}

watch(showMap, (open) => {
  if (open)
    void loadMapStations()
})

// Single-station picker: keep only the most recently clicked station.
function onMapSelectedStations(val: Station[]) {
  selectedStation.value = val.length ? val[val.length - 1]! : null
}

async function fetchMeteogram(station: Station) {
  pending.value = true
  failure.value = null
  values.value = []

  const rawParams: Record<string, string> = {
    provider: MOSMIX.provider,
    network: MOSMIX.network,
    parameters: MOSMIX.parameters.map(p => `${MOSMIX.resolution}/${MOSMIX.dataset}/${p}`).join(','),
    stations: station.station_id,
    ...METEOGRAM_VALUES_SETTINGS,
  }
  if (selectedIssue.value)
    rawParams.issue = selectedIssue.value
  const params = new URLSearchParams(rawParams)

  try {
    const res = await fetch(`/api/values?${params}`)
    if (!res.ok) {
      failure.value = backendFailure(res.status, res.statusText, await res.json().catch(() => null))
      return
    }
    const json = await res.json()
    values.value = json.values ?? []
  }
  catch (e: any) {
    failure.value = e?.message ? { kind: 'text', text: e.message } : { kind: 'requestFailed' }
  }
  finally {
    pending.value = false
  }
}

watch(selectedIssue, () => {
  if (selectedStation.value)
    void fetchMeteogram(selectedStation.value)
})

// Auto-fetch and sync URL whenever a station is chosen or cleared
watch(selectedStation, (station) => {
  if (!isRestoringFromUrl.value)
    selectedIssue.value = ''
  if (station) {
    void loadAvailableIssues(station.station_id)
    void fetchMeteogram(station)
  }
  else {
    values.value = []
    failure.value = null
    availableIssues.value = []
    // A rejected navigation (e.g. superseded by a subsequent replace() before
    // this one resolves) would otherwise be an unhandled promise rejection.
    void router.replace({ query: {} }).catch(() => {})
  }
})

// Sync station + issue to URL (fires once when both change together)
watch([selectedStation, selectedIssue], ([station, issue]) => {
  if (!station)
    return
  const q: Record<string, string> = { station: station.station_id }
  if (issue)
    q.issue = issue
  // Preserve display params managed by the Meteogram component
  for (const k of ['horizon', 'panels', 'view', 'compact'] as const) {
    const v = route.query[k]
    if (v)
      q[k] = v.toString()
  }
  // A rejected navigation (e.g. superseded by a subsequent replace() before
  // this one resolves) would otherwise be an unhandled promise rejection.
  void router.replace({ query: q }).catch(() => {})
})

// Restore selected station and issue from URL query params on page load, and when the URL names another station
// while the page is shown (the search of the header goes to `/meteogram?station=…`, GH-3518)
let requestedFromUrl: string | undefined
async function restoreFromUrl() {
  const stationId = route.query.station as string | undefined
  const issueFromUrl = route.query.issue?.toString()
  if (!stationId)
    return
  requestedFromUrl = stationId
  isRestoringFromUrl.value = true
  try {
    const res = await $fetch<{ stations: Station[] }>('/api/stations', {
      query: {
        provider: MOSMIX.provider,
        network: MOSMIX.network,
        parameters: `${MOSMIX.resolution}/${MOSMIX.dataset}`,
        stations: stationId,
      },
      ...RETRY_TRANSIENT,
    })
    const station = (res.stations ?? [])[0]
    if (station) {
      if (issueFromUrl)
        selectedIssue.value = issueFromUrl
      selectedStation.value = station
    }
  }
  catch {
    // ignore – station ID in URL may be invalid, just start fresh
  }
  finally {
    await nextTick()
    isRestoringFromUrl.value = false
  }
}
onMounted(restoreFromUrl)
// the page's own choice is written to the URL as well (the watch above): only a station it did not choose is loaded
// and a station asked for already (whose answer may still be coming, or was a failure) is not asked for again
watch(() => route.query.station, (stationId) => {
  if (stationId && stationId !== selectedStation.value?.station_id && stationId !== requestedFromUrl)
    void restoreFromUrl()
})
</script>

<template>
  <div class="frame">
    <PageHeader :title="t('meteogram.title')" :lede="t('meteogram.subtitle')" :about-label="t('meteogram.aboutButton')">
      <template #about>
        <div class="space-y-3 text-muted">
          <p class="text-gray-600 dark:text-gray-400 mb-4">
            {{ t('meteogram.aboutText1') }}
          </p>
          <p class="text-gray-600 dark:text-gray-400">
            {{ t('meteogram.aboutText2') }}
          </p>
        </div>
      </template>
    </PageHeader>
    <div class="page-body">
      <ToolWorkbench>
        <template #setup>
          <!-- Station search -->
          <UCard>
            <template #header>
              <div class="flex items-center gap-2 flex-wrap">
                <UIcon name="i-ph-map-pin" class="text-primary-500 shrink-0" />
                <span class="text-lg font-bold">{{ t('explorer.dataSource') }}</span>
                <div class="ml-auto flex items-center gap-2">
                  <label for="meteogram-run" class="text-xs text-gray-500 dark:text-gray-400 shrink-0">{{ t('meteogram.runLabel') }}</label>
                  <select
                    id="meteogram-run"
                    v-model="selectedIssue"
                    class="text-xs rounded-md border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 text-gray-900 dark:text-white px-2 py-1 cursor-pointer focus:outline-none focus:ring-2 focus:ring-primary-500 dark:focus:ring-primary-400 w-48"
                  >
                    <option v-for="item in runItems" :key="item.value" :value="item.value">
                      {{ item.label }}
                    </option>
                  </select>
                </div>
              </div>
            </template>
            <MeteogramStationSearch v-model="selectedStation" />

            <!-- "or" divider, signalling the map is an equal alternative to search. -->
            <div class="flex items-center gap-3 my-4 text-xs uppercase tracking-wide text-gray-500 dark:text-gray-400">
              <div class="flex-1 border-t border-gray-200 dark:border-gray-700" />
              <span>{{ t('meteogram.orChooseMap') }}</span>
              <div class="flex-1 border-t border-gray-200 dark:border-gray-700" />
            </div>

            <!-- Pick a station from the map instead of searching. -->
            <UCollapsible v-model="showMap">
              <UButton
                :label="t('meteogram.chooseOnMap')"
                icon="i-ph-map-pin"
                variant="subtle"
                color="primary"
                trailing-icon="i-ph-caret-down"
                block
                @click="showMap = !showMap"
              />
              <template #content>
                <ClientOnly>
                  <div v-if="mapLoading" class="flex items-center justify-center gap-3 py-8 text-gray-500 dark:text-gray-400">
                    <UIcon name="i-ph-circle-notch" class="w-5 h-5 animate-spin text-primary-500" />
                    <span>{{ t('stationSelection.loading') }}</span>
                  </div>
                  <template v-else-if="mapStations.length">
                    <p v-if="!mapNotLoaded" class="flex items-center justify-center gap-2 mt-3 text-sm text-gray-500 dark:text-gray-400">
                      <UIcon name="i-ph-hand-pointing" class="w-4 h-4 text-primary-500" />
                      {{ t('meteogram.mapHint') }}
                    </p>
                    <MapStations
                      :stations="mapStations"
                      :selected-stations="selectedStationsArray"
                      :multiple="false"
                      @update:selected-stations="onMapSelectedStations"
                    />
                  </template>
                </ClientOnly>
              </template>
            </UCollapsible>
          </UCard>
        </template>
        <template #result>
          <!-- Loading state -->
          <div v-if="pending" class="flex items-center justify-center gap-3 py-12 text-gray-500 dark:text-gray-400">
            <UIcon name="i-ph-circle-notch" class="w-6 h-6 animate-spin text-primary-500" />
            <span>{{ t('meteogram.loading') }}</span>
          </div>

          <!-- Error state -->
          <UAlert
            v-else-if="error"
            color="error"
            variant="subtle"
            icon="i-ph-warning-circle"
            :title="error"
          />

          <!-- Meteogram chart -->
          <UCard v-else-if="selectedStation && values.length > 0">
            <template #header>
              <div class="flex items-center gap-2">
                <UIcon name="i-ph-cloud-sun" class="text-primary-500" />
                <span class="text-lg font-bold">{{ selectedStation.name }}</span>
                <span class="text-gray-500 dark:text-gray-400 text-sm">({{ selectedStation.station_id }})</span>
                <UButton
                  :to="`/widget?station=${selectedStation.station_id}`"
                  target="_blank"
                  icon="i-ph-picture-in-picture"
                  size="xs"
                  variant="ghost"
                  color="neutral"
                  :title="t('meteogram.openWidget')"
                  class="ml-auto"
                />
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
            class="rounded-xl border-2 border-dashed border-gray-200 dark:border-gray-700 p-16 text-center text-gray-500 dark:text-gray-400 space-y-2"
          >
            <UIcon name="i-ph-cloud-sun" class="w-12 h-12 mx-auto opacity-30" />
            <p class="text-sm">
              {{ t('meteogram.emptyHint') }}
            </p>
          </div>
        </template>
      </ToolWorkbench>
    </div>
  </div>
</template>
