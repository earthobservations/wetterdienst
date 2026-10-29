<script setup lang="ts">
import type { Station } from '#shared/types/api'
import MeteogramStationSearch from '~/components/MeteogramStationSearch.vue'
import { nearestStation, placeName, placeOfStation } from '~/utils/place'

const { t, locale } = useI18n()

// One question first (GH-3518): which place. The search is the forecast's own (the DWD MOSMIX stations, in
// Germany and worldwide); the place is remembered in the browser, and the page answers for it: the weather
// now, and its forecast, its climate stripes and the measurements around it, each a tap away.
const { place, setPlace, forgetPlace } = usePlace()

const selectedStation = computed<Station | null>({
  get: () => place.value
    ? { station_id: place.value.id, name: place.value.name, latitude: place.value.latitude, longitude: place.value.longitude } as Station
    : null,
  set: (station) => {
    const chosen = station ? placeOfStation(station) : null
    if (chosen)
      setPlace(chosen)
    else if (!station)
      forgetPlace()
  },
})

// A few places to start from, so that a first visit is one tap from a forecast. MOSMIX stations, with the
// names and positions the station list gives them; the label is the city's own name.
const EXAMPLES = [
  { label: 'Berlin', id: '10384', name: 'BERLIN-TEMPELHOF', latitude: 52.47, longitude: 13.4 },
  { label: 'Hamburg', id: '10147', name: 'HAMBURG-FU.', latitude: 53.63, longitude: 10.0 },
  { label: 'München', id: '10865', name: 'MUENCHEN STADT', latitude: 48.17, longitude: 11.53 },
  { label: 'Köln', id: '10513', name: 'KOELN/BONN', latitude: 50.87, longitude: 7.17 },
  { label: 'Frankfurt', id: '10637', name: 'FRANKFURT/M', latitude: 50.05, longitude: 8.6 },
  { label: 'Wien', id: '11034', name: 'WIEN/CITY', latitude: 48.2, longitude: 16.37 },
  { label: 'Zürich', id: '06660', name: 'ZUERICH (TOWN/VILLE)', latitude: 47.38, longitude: 8.57 },
]
function choose(example: typeof EXAMPLES[number]) {
  setPlace({ id: example.id, name: example.name, latitude: example.latitude, longitude: example.longitude })
}

// The climate stripes of the place: the stripes' own station nearest to it, asked for once there is a place
const { data: stripesStations, execute: loadStripesStations } = useFetch<{ stations: Array<{ station_id: string, name: string, latitude: number, longitude: number }> }>(
  '/api/stripes/stations',
  { query: { kind: 'temperature' }, immediate: false, ...RETRY_TRANSIENT },
)
watch(() => place.value?.id, (id) => {
  if (id && !stripesStations.value)
    void loadStripesStations()
}, { immediate: true })
const nearestStripes = computed(() => place.value && stripesStations.value?.stations?.length
  ? nearestStation(stripesStations.value.stations, place.value)
  : null)

/** The measurements around the place: the explorer's summary of the stations near it over the last 30 days */
function explorerLink(latitude: number, longitude: number) {
  const day = (offset: number) => new Date(Date.now() - offset * 86_400_000).toISOString().slice(0, 10)
  const query = new URLSearchParams({
    provider: 'dwd',
    network: 'observation',
    resolution: 'daily',
    dataset: 'climate_summary',
    parameters: 'temperature_air_mean_2m,precipitation_height',
    mode: 'summary',
    interpolationSource: 'manual',
    lat: String(latitude),
    lon: String(longitude),
    startDate: day(31),
    endDate: day(1),
  })
  return `/explorer?${query}`
}

// The three ways in: for the place where there is one, to the pages themselves where there is none
const lenses = computed(() => {
  const p = place.value
  const stripes = nearestStripes.value
  return [
    {
      key: 'forecast',
      to: p ? `/meteogram?station=${encodeURIComponent(p.id)}` : '/meteogram',
      icon: 'i-lucide-cloud-sun',
      tint: 'bg-sun/25 text-ink-900 dark:bg-sun/15 dark:text-sun',
      title: t('home.forecastTitle'),
      description: p ? t('home.lensForecastDesc') : t('home.forecastDesc'),
    },
    {
      key: 'stripes',
      to: p && stripes ? `/stripes?kind=temperature&station=${encodeURIComponent(stripes.station.station_id)}` : '/stripes',
      icon: 'i-lucide-bar-chart-3',
      tint: 'bg-ember/15 text-ink-900 dark:bg-ember/20 dark:text-ember',
      title: t('home.stripesTitle'),
      description: p && stripes
        ? t('home.lensStripesDesc', { station: stripes.station.name, km: Math.round(stripes.km) })
        : t('home.stripesDesc'),
    },
    {
      key: 'explorer',
      to: p ? explorerLink(p.latitude, p.longitude) : '/explorer',
      icon: 'i-lucide-compass',
      tint: 'bg-lagoon/20 text-ink-900 dark:bg-lagoon/15 dark:text-lagoon',
      title: t('home.explorerTitle'),
      description: p ? t('home.lensExplorerDesc', { place: placeName(p.name) }) : t('home.explorerDesc'),
    },
  ]
})

// What you can do with the data once you have it.
const features = computed(() => [
  { icon: 'i-lucide-download', title: t('home.featureExportTitle'), description: t('home.featureExportDesc') },
  { icon: 'i-lucide-line-chart', title: t('home.featureAnalysisTitle'), description: t('home.featureAnalysisDesc') },
])

// The weather services behind the data, as the backend lists them (`GET /api/providers`): one chip for each
// provider of its registry, so a provider added upstream is on this page without a change here. Short names
// and flags: the flag is the provider's own country, and NOAA's GHCN is worldwide despite the US flag, which
// `home.dataProvidersDesc` says. The request is the one the Providers pages share, by its key.
const collator = computed(() => new Intl.Collator(locale.value, { numeric: true }))
const { data: providerList, pending: providersPending, error: providersError, refresh: refreshProviders } = useProviders()

const providers = computed(() => (providerList.value?.providers ?? [])
  .map(provider => ({ key: provider.provider, name: provider.name_short, flag: flagEmoji(provider.country_code) }))
  .sort((a, b) => collator.value.compare(a.name, b.name)))
const providersFailure = computed(() => providersError.value ? describeFetchError(providersError.value) : '')
// until the first answer there is nothing to list: the chips' place is held by as many placeholders as
// there are providers today, so the block is about as tall before the answer as after
const providersLoading = computed(() => providersPending.value && !providerList.value)
const PLACEHOLDER_WIDTHS = ['w-14', 'w-24', 'w-20', 'w-28', 'w-16', 'w-24', 'w-20']
const placeholders = Array.from({ length: 22 }, (_, index) => PLACEHOLDER_WIDTHS[index % PLACEHOLDER_WIDTHS.length])

// Headline numbers: the providers and the parameters are the backend's counts (`GET /api/providers`, the
// `metadata.counts`), so neither is written out here to drift from the library; a number that has not come
// is null, and the tile holds its place until the request has answered.
const stats = computed(() => [
  { key: 'providers', value: providerList.value ? String(providerList.value.metadata.counts.providers) : null, label: t('home.statProviders') },
  { key: 'parameters', value: providerList.value ? String(providerList.value.metadata.counts.parameters) : null, label: t('home.statParameters') },
  { key: 'resolutions', value: '1 min – 1 a', label: t('home.statResolutions') },
  { key: 'price', value: '0 €', label: t('home.statPrice') },
])

// The two open-source programmes the project runs on. Named on the page that asks nothing of the
// reader, rather than on the support page, which asks: who already gives is context for whether to.
const supporters = computed(() => [
  { key: 'jetbrains', name: 'JetBrains', icon: 'i-simple-icons-jetbrains', to: 'https://jb.gg/OpenSourceSupport', detail: t('home.supportedByJetbrains') },
  { key: 'anthropic', name: 'Anthropic', icon: 'i-simple-icons-anthropic', to: 'https://www.anthropic.com/', detail: t('home.supportedByAnthropic') },
])

// The same data, for people who would rather not click: the library the project started as, the
// API the app itself runs on, and the MCP endpoint.
const devEntries = computed(() => [
  { key: 'pypi', label: 'pip install wetterdienst', icon: 'i-simple-icons-python', to: 'https://pypi.org/project/wetterdienst/', title: undefined },
  // this instance's own endpoints rather than the page that describes them: /docs is the backend's
  // Swagger UI, proxied onto this origin, and /mcp/v1 is the endpoint itself. Both are served by
  // nitro rather than by the Vue router, so they need a full navigation, not a client-side one.
  { key: 'api', label: 'REST API', icon: 'i-lucide-code', to: '/docs', title: undefined },
  { key: 'mcp', label: 'MCP', icon: 'i-lucide-bot', to: '/mcp/v1', title: t('home.devMcpHint') },
])

// What the project stands for. Shared with the footer, which shows the same four as icons.
const values = computed(() => [
  { key: 'lgbtq', emoji: '🏳️‍🌈🏳️‍⚧️', text: t('values.lgbtq') },
  { key: 'antifascist', emoji: '✊', text: t('values.antifascist') },
  { key: 'climate', emoji: '🌡️', text: t('values.climate') },
  { key: 'openData', emoji: '🔓', text: t('values.openData') },
])

// What kinds of data the networks behind those providers actually serve.
const dataKinds = computed(() => [
  { icon: 'i-lucide-thermometer', title: t('home.kindObservationsTitle'), description: t('home.kindObservationsDesc') },
  { icon: 'i-lucide-cloud-sun', title: t('home.kindForecastsTitle'), description: t('home.kindForecastsDesc') },
  { icon: 'i-lucide-waves', title: t('home.kindHydrologyTitle'), description: t('home.kindHydrologyDesc') },
  { icon: 'i-lucide-radar', title: t('home.kindRadarTitle'), description: t('home.kindRadarDesc') },
  { icon: 'i-lucide-triangle-alert', title: t('home.kindAlertsTitle'), description: t('home.kindAlertsDesc') },
  { icon: 'i-lucide-car-front', title: t('home.kindRoadTitle'), description: t('home.kindRoadDesc') },
])

const chipClass = 'inline-flex items-center gap-1.5 rounded-full border border-transparent bg-default px-3 py-1.5 text-sm font-medium ring ring-default text-default transition-colors hover:ring-brand-600 hover:text-brand-800 dark:hover:ring-brand-400 dark:hover:text-brand-200'
</script>

<template>
  <div>
    <!-- the question, in the sky -->
    <PageShell as="section" width="default" class="pb-10 sm:pb-14" aria-labelledby="home-question">
      <div class="max-w-2xl pt-8 sm:pt-14">
        <p class="mb-3 text-sm font-semibold uppercase tracking-wider text-brand-700 dark:text-brand-300">
          {{ t('home.tagline') }}
        </p>
        <h1 id="home-question" class="text-4xl font-extrabold tracking-tight text-highlighted text-balance break-words sm:text-6xl">
          {{ t('home.placeQuestion') }}
        </h1>
        <p class="mt-4 text-lg text-toned text-pretty sm:text-xl">
          {{ t('home.placeLead') }}
        </p>
        <div class="mt-7 rounded-2xl bg-default p-2 shadow-(--shadow-lift) ring ring-default wd-surface">
          <MeteogramStationSearch v-model="selectedStation" size="xl" :pulse="false" />
        </div>
        <div class="mt-4 flex flex-wrap items-center gap-2">
          <span class="text-sm font-semibold text-toned">{{ t('home.placeExamples') }}</span>
          <button
            v-for="example in EXAMPLES"
            :key="example.id"
            type="button"
            :class="chipClass"
            :aria-pressed="place?.id === example.id"
            @click="choose(example)"
          >
            {{ example.label }}
          </button>
        </div>
        <p v-if="place" class="mt-3 flex items-center gap-1.5 text-sm text-toned">
          <UIcon name="i-lucide-lock" class="size-3.5 shrink-0" />
          {{ t('home.placeRemembered') }}
        </p>
      </div>
    </PageShell>

    <PageShell width="default" class="space-y-16">
      <!-- the place: its weather now, and three ways on -->
      <div class="space-y-6">
        <PlaceNow v-if="place" :place="place" @forget="forgetPlace()" />
        <h2 v-else class="text-xl font-extrabold tracking-tight text-highlighted sm:text-2xl">
          {{ t('home.tasksTitle') }}
        </h2>
        <ul class="grid grid-cols-1 gap-4 md:grid-cols-3">
          <li v-for="lens in lenses" :key="lens.key">
            <NuxtLink
              :to="lens.to"
              class="group wd-surface flex h-full flex-col gap-3 rounded-xl bg-default p-5 shadow-(--shadow-card) ring ring-default transition hover:-translate-y-0.5 hover:shadow-(--shadow-lift) hover:ring-brand-600 motion-reduce:transition-none motion-reduce:hover:translate-y-0 dark:hover:ring-brand-400"
            >
              <span class="grid size-11 place-items-center rounded-xl" :class="lens.tint" aria-hidden="true">
                <UIcon :name="lens.icon" class="size-6" />
              </span>
              <h3 class="text-lg font-bold text-highlighted">
                {{ lens.title }}
              </h3>
              <p class="flex-1 text-sm text-toned">
                {{ lens.description }}
              </p>
              <span class="inline-flex items-center gap-1 text-sm font-semibold text-brand-700 group-hover:underline dark:text-brand-300">
                {{ t('common.open') }}
                <UIcon name="i-lucide-arrow-right" class="size-4 transition-transform group-hover:translate-x-0.5 motion-reduce:transition-none" />
              </span>
            </NuxtLink>
          </li>
        </ul>
      </div>

      <!-- What actually arrives when you press a button above: who publishes it, how much of it
           there is, and in what shapes. -->
      <section class="space-y-6" aria-labelledby="home-data">
        <div>
          <h2 id="home-data" class="text-xl font-extrabold tracking-tight text-highlighted sm:text-2xl">
            {{ t('home.dataTitle') }}
          </h2>
          <p class="mt-1 text-toned">
            {{ t('home.dataIntro') }}
          </p>
        </div>

        <div class="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <div v-for="stat in stats" :key="stat.key" class="wd-surface rounded-xl bg-default px-4 py-5 ring ring-default">
            <!-- the numbers of providers and parameters are the backend's: its place is held until it has answered (h-8 is the
                 line of text-2xl), and it is a dash where the request failed -->
            <div class="text-2xl font-extrabold tracking-tight tabular-nums text-brand-700 dark:text-brand-300">
              <div v-if="stat.value === null && providersLoading" class="h-8 w-10 rounded-md bg-elevated animate-pulse" aria-hidden="true" />
              <template v-else>
                {{ stat.value ?? '–' }}
              </template>
            </div>
            <div class="mt-1 text-sm text-toned">
              {{ stat.label }}
            </div>
          </div>
        </div>

        <UCard data-testid="home-providers-card">
          <template #header>
            <div class="flex items-center gap-2">
              <UIcon name="i-lucide-building-2" class="shrink-0 text-brand-600 dark:text-brand-300" />
              <h3 class="font-bold text-highlighted">
                {{ t('home.dataProvidersTitle') }}
              </h3>
            </div>
          </template>
          <UAlert
            v-if="providersFailure"
            color="error"
            variant="subtle"
            icon="i-lucide-alert-circle"
            :title="t('common.requestFailed')"
            :description="providersFailure"
            :actions="[{ label: t('common.retry'), onClick: () => refreshProviders() }]"
          />
          <div v-else-if="providersLoading" class="flex flex-wrap gap-2" role="status" :aria-label="t('common.loading')" aria-busy="true">
            <div v-for="(width, index) in placeholders" :key="index" class="h-[1.875rem] rounded-full bg-elevated animate-pulse" :class="width" aria-hidden="true" />
          </div>
          <p v-else-if="!providers.length" class="text-sm text-muted">
            {{ t('home.providersEmpty') }}
          </p>
          <ul v-else class="flex flex-wrap gap-2" data-testid="home-providers">
            <li v-for="provider in providers" :key="provider.key">
              <NuxtLink
                :to="`/providers/${provider.key}`"
                class="inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-sm ring ring-default transition-colors hover:ring-brand-600 hover:text-brand-800 dark:hover:ring-brand-400 dark:hover:text-brand-200"
              >
                <span aria-hidden="true">{{ provider.flag }}</span>
                {{ provider.name }}
              </NuxtLink>
            </li>
          </ul>
          <p class="mt-4 text-sm text-muted">
            {{ t('home.dataProvidersDesc') }}
            <NuxtLink to="/glossary" class="text-brand-700 underline hover:no-underline dark:text-brand-300">
              {{ t('home.glossaryHint') }}
            </NuxtLink>
            {{ ' ' }}
            <NuxtLink to="/providers" class="text-brand-700 underline hover:no-underline dark:text-brand-300">
              {{ t('home.providersLink') }}
            </NuxtLink>
          </p>
        </UCard>

        <ul class="grid grid-cols-1 gap-x-8 gap-y-6 sm:grid-cols-2 lg:grid-cols-3">
          <li v-for="kind in dataKinds" :key="kind.title" class="flex items-start gap-3">
            <span class="grid size-10 shrink-0 place-items-center rounded-xl bg-brand-50 text-brand-700 dark:bg-brand-950 dark:text-brand-300" aria-hidden="true">
              <UIcon :name="kind.icon" class="size-5" />
            </span>
            <div>
              <h3 class="font-semibold text-highlighted">
                {{ kind.title }}
              </h3>
              <p class="text-sm text-toned">
                {{ kind.description }}
              </p>
            </div>
          </li>
        </ul>

        <!-- A subsection of the data block rather than a section of its own: it is still about the data. -->
        <div class="wd-surface rounded-xl bg-default p-5 ring ring-default sm:p-6">
          <h3 class="mb-4 font-bold text-highlighted">
            {{ t('home.featuresTitle') }}
          </h3>
          <ul class="grid grid-cols-1 gap-6 md:grid-cols-2">
            <li v-for="feature in features" :key="feature.title" class="flex items-start gap-3">
              <UIcon :name="feature.icon" class="mt-0.5 size-5 shrink-0 text-brand-600 dark:text-brand-300" />
              <div>
                <h4 class="font-semibold text-highlighted">
                  {{ feature.title }}
                </h4>
                <p class="text-sm text-toned">
                  {{ feature.description }}
                </p>
              </div>
            </li>
          </ul>
          <!-- The developer path: same data, no clicking. -->
          <div class="mt-6 border-t border-default pt-5">
            <h4 class="font-semibold text-highlighted">
              {{ t('home.devTitle') }}
            </h4>
            <p class="mb-3 text-sm text-toned">
              {{ t('home.devText') }}
            </p>
            <div class="flex flex-wrap gap-2">
              <!-- NuxtLink for all three: it renders an external URL as a plain anchor by itself -->
              <NuxtLink
                v-for="entry in devEntries"
                :key="entry.key"
                :to="entry.to"
                external
                target="_blank"
                :title="entry.title"
                class="inline-flex items-center gap-1.5 rounded-full px-3 py-1 font-mono text-sm ring ring-default transition-colors hover:ring-brand-600 hover:text-brand-800 dark:hover:ring-brand-400 dark:hover:text-brand-200"
              >
                <UIcon :name="entry.icon" class="size-4 shrink-0" />
                {{ entry.label }}
              </NuxtLink>
            </div>
          </div>
        </div>
      </section>

      <!-- Values: an unmistakable stance for inclusion and against fascism, and who backs the work -->
      <div class="grid gap-4 md:grid-cols-[2fr_1fr]">
        <section class="rounded-2xl bg-navy p-6 text-white dark:bg-brand-950 [--app-focus-ring:var(--color-sun)]" aria-labelledby="home-values">
          <h2 id="home-values" class="mb-4 text-lg font-bold">
            {{ t('values.title') }}
          </h2>
          <ul class="grid gap-3 sm:grid-cols-2">
            <li v-for="value in values" :key="value.key" class="flex items-start gap-2 font-medium">
              <span aria-hidden="true">{{ value.emoji }}</span>
              {{ value.text }}
            </li>
          </ul>
        </section>
        <section class="wd-surface rounded-2xl bg-default p-6 ring ring-default" aria-labelledby="home-supporters">
          <h2 id="home-supporters" class="mb-4 text-lg font-bold text-highlighted">
            {{ t('home.supportedByTitle') }}
          </h2>
          <div class="flex flex-wrap gap-2">
            <a
              v-for="supporter in supporters"
              :key="supporter.key"
              :href="supporter.to"
              target="_blank"
              :title="supporter.detail"
              :aria-label="`${supporter.name} — ${supporter.detail}`"
              :class="chipClass"
            >
              <UIcon :name="supporter.icon" class="size-4 shrink-0" />
              {{ supporter.name }}
            </a>
          </div>
          <UButton
            to="/about"
            variant="link"
            icon="i-lucide-info"
            trailing-icon="i-lucide-arrow-right"
            class="mt-4 -ml-2.5"
          >
            {{ t('home.aboutLink') }}
          </UButton>
        </section>
      </div>
    </PageShell>
  </div>
</template>
