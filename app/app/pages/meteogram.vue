<script setup lang="ts">
import type { Station } from '#shared/types/api'
import type { RequestError } from '~/utils/request-error'
import { nextTick } from 'vue'
import Meteogram from '~/components/Meteogram.vue'
import MeteogramStationSearch from '~/components/MeteogramStationSearch.vue'
import { meteogramValuesQuery, MOSMIX_METEOGRAM } from '~/utils/meteogram'
import { backendFailure, describeRequestError, failureOfError } from '~/utils/request-error'

const { MapStations, notLoaded: mapNotLoaded } = useMapStations()

// Auto-composed MOSMIX parameters – user never configures these; the map's panel asks for the same
const MOSMIX = MOSMIX_METEOGRAM

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
// the moment the run and the station of the URL are set together: the watchers below leave them to each other
let applyingUrl = false

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

// The request of the run list that is the latest, and that of the values: the answer of an earlier one, which a
// newer pick has left behind, is not applied (GH-3732)
let issuesTicket = 0
let valuesTicket = 0

async function loadAvailableIssues(stationId: string) {
  const ticket = ++issuesTicket
  try {
    const res = await $fetch<{ issues: string[] }>('/api/issues', {
      query: { provider: MOSMIX.provider, network: MOSMIX.network, station: stationId },
      ...API_FETCH,
    })
    if (ticket === issuesTicket)
      availableIssues.value = res.issues ?? []
  }
  catch {
    if (ticket === issuesTicket)
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
      ...API_FETCH,
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
  const ticket = ++valuesTicket
  pending.value = true
  failure.value = null
  values.value = []

  const rawParams = meteogramValuesQuery(station.station_id)
  if (selectedIssue.value)
    rawParams.issue = selectedIssue.value
  const params = new URLSearchParams(rawParams)

  try {
    const res = await fetch(`/api/values?${params}`)
    if (ticket !== valuesTicket)
      return
    if (!res.ok) {
      const body = await res.json().catch(() => null)
      if (ticket === valuesTicket)
        failure.value = backendFailure(res.status, res.statusText, body)
      return
    }
    const json = await readJsonAnswer<{ values?: any[] }>('/api/values', res)
    if (ticket === valuesTicket)
      values.value = json.values ?? []
  }
  catch (e: any) {
    if (ticket === valuesTicket)
      failure.value = failureOfError(e)
  }
  finally {
    if (ticket === valuesTicket)
      pending.value = false
  }
}

// the station the URL asked for last, whether it is answered, still coming or failed: asked for once, not again
// until the reader has chosen (or cleared) another
let requestedFromUrl: string | undefined
// the request of the URL's station that is the latest: the answer of an earlier one, which a later search or the
// reader's own choice has left behind, is not applied
let restoreTicket = 0
function cancelRestore() {
  restoreTicket++
  applyingUrl = false
  isRestoringFromUrl.value = false
}

// Auto-fetch and sync URL whenever a station is chosen or cleared
watch(selectedStation, (station) => {
  if (!applyingUrl) {
    // a lookup of the URL's station that is under way is the reader's no longer
    cancelRestore()
    selectedIssue.value = ''
    // the reader's own choice, or none, ends the memory of what the URL asked for: a station it named before may be
    // asked for again (the header's search for the station that was shown, chosen away from and searched again)
    requestedFromUrl = undefined
  }
  if (station) {
    void loadAvailableIssues(station.station_id)
  }
  else {
    // no answer of an earlier request is applied to the empty page
    issuesTicket++
    values.value = []
    failure.value = null
    availableIssues.value = []
    // A rejected navigation (e.g. superseded by a subsequent replace() before
    // this one resolves) would otherwise be an unhandled promise rejection.
    void router.replace({ query: {} }).catch(() => {})
  }
})

// The values of the station and the run: one request for a change of either, or of both together. For a station the
// reader chose, the watcher above resets the run, and as it is queued first it does so before this one runs, so the
// new station is fetched once, for the latest run. Where the URL sets the run first (`restoreFromUrl`) the flag
// `applyingUrl` keeps that watcher from resetting it. Should two requests go out anyway, the ticket keeps the latest
// answer (GH-3732)
watch([selectedStation, selectedIssue], ([station]) => {
  if (station) {
    void fetchMeteogram(station)
    return
  }
  // a request that is under way answers a station that is no longer there
  valuesTicket++
  pending.value = false
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
async function restoreFromUrl() {
  const stationId = route.query.station as string | undefined
  const issueFromUrl = route.query.issue?.toString()
  if (!stationId)
    return
  requestedFromUrl = stationId
  const ticket = ++restoreTicket
  isRestoringFromUrl.value = true
  try {
    const res = await $fetch<{ stations: Station[] }>('/api/stations', {
      query: {
        provider: MOSMIX.provider,
        network: MOSMIX.network,
        parameters: `${MOSMIX.resolution}/${MOSMIX.dataset}`,
        stations: stationId,
      },
      ...API_FETCH,
    })
    if (ticket !== restoreTicket)
      return
    const station = (res.stations ?? [])[0]
    if (station) {
      // a link without a run is the latest one, not the run chosen for the station before
      applyingUrl = true
      // the run of the URL as it is now: a link to the same station may have taken the run away while it was looked up
      selectedIssue.value = (route.query.station === stationId ? route.query.issue?.toString() : issueFromUrl) ?? ''
      selectedStation.value = station
      // the watchers run before this resolves, and see the flag
      try {
        await nextTick()
      }
      finally {
        applyingUrl = false
      }
    }
  }
  catch {
    // ignore – station ID in URL may be invalid, just start fresh
  }
  finally {
    // an earlier request leaves the flags to the later one that is still under way
    if (ticket === restoreTicket) {
      applyingUrl = false
      await nextTick()
      isRestoringFromUrl.value = false
    }
  }
}
onMounted(restoreFromUrl)
// the page's own choice is written to the URL as well (the watch above): only a station it did not choose is loaded
// and a station asked for already (whose answer may still be coming, or was a failure) is not asked for again
watch(() => route.query.station, (stationId) => {
  // a link without a station (the tab bar's) while the lookup of one is under way: the lookup is not wanted any
  // more, and the station it names may be asked for again
  if (!stationId && isRestoringFromUrl.value) {
    cancelRestore()
    requestedFromUrl = undefined
  }
  // the URL is back at the station that is shown (the page wrote it): what it asked for before is no longer pending
  if (stationId && stationId === selectedStation.value?.station_id) {
    requestedFromUrl = undefined
    // a search back to the station that is shown, while one for another is still being looked up, is the later one
    cancelRestore()
  }
  if (stationId && stationId !== selectedStation.value?.station_id && stationId !== requestedFromUrl)
    void restoreFromUrl()
})
// a link to the station that is shown, without a run (the header's search), is the latest run, as for any other
// station: the run follows the URL whenever the URL is at the station that is shown (also where its station changed
// back to it, a lookup of another having left the run alone)
watch([() => route.query.station, () => route.query.issue?.toString() ?? ''], ([station, issue]) => {
  if (issue === selectedIssue.value || isRestoringFromUrl.value || !selectedStation.value || station !== selectedStation.value.station_id)
    return
  selectedIssue.value = issue
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
                <UIcon name="i-ph-map-pin" class="text-primary-600 dark:text-primary-500 shrink-0" />
                <span class="text-lg font-bold">{{ t('cardTitle.station') }}</span>
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
                    <UIcon name="i-ph-circle-notch" class="w-5 h-5 animate-spin text-primary-600 dark:text-primary-500" />
                    <span>{{ t('stationSelection.loading') }}</span>
                  </div>
                  <template v-else-if="mapStations.length">
                    <p v-if="!mapNotLoaded" class="flex items-center justify-center gap-2 mt-3 text-sm text-gray-500 dark:text-gray-400">
                      <UIcon name="i-ph-hand-pointing" class="w-4 h-4 text-primary-600 dark:text-primary-500" />
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
            <UIcon name="i-ph-circle-notch" class="w-6 h-6 animate-spin text-primary-600 dark:text-primary-500" />
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
                <UIcon name="i-ph-cloud-sun" class="text-primary-600 dark:text-primary-500" />
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
          <ToolPlaceholder v-else-if="!selectedStation" tool="forecast" />
        </template>
      </ToolWorkbench>
    </div>
  </div>
</template>
