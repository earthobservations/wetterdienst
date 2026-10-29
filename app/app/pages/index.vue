<script setup lang="ts">
const { t } = useI18n()

// Primary, consumer-facing tasks, each on the tile of the logo the rail gives it (app.vue). Explorer is intentionally a first-class
// entry point here (not hidden behind an "advanced" section) — it is made
// approachable through the Explorer's guided Simple mode.
const tasks = computed(() => [
  {
    to: '/meteogram',
    icon: 'i-lucide-sun',
    title: t('home.forecastTitle'),
    description: t('home.forecastDesc'),
    tile: 'sun',
  },
  {
    to: '/stripes',
    icon: 'i-lucide-thermometer',
    title: t('home.stripesTitle'),
    description: t('home.stripesDesc'),
    tile: 'temperature',
  },
  {
    to: '/explorer',
    icon: 'i-lucide-droplets',
    title: t('home.explorerTitle'),
    description: t('home.explorerDesc'),
    tile: 'rain',
  },
])

// What you can do with the data once you have it. Two cards rather than four: "multiple data
// sources" and "geospatial queries" said what the services card and the Explorer card above now
// say better, and a home page that repeats itself reads as padding.
const features = computed(() => [
  { icon: 'i-lucide-download', title: t('home.featureExportTitle'), description: t('home.featureExportDesc') },
  { icon: 'i-lucide-line-chart', title: t('home.featureAnalysisTitle'), description: t('home.featureAnalysisDesc') },
])

// The weather services behind the data, as the backend lists them (`GET /api/providers`): one chip for each
// provider of its registry, so a provider added upstream is on this page without a change here. Short names
// and flags: the flag is the provider's own country, and NOAA's GHCN is worldwide despite the US flag, which
// `home.dataProvidersDesc` says. The request is the one the Providers pages share, by its key.
const { locale } = useI18n()
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
// API the app itself runs on, and the MCP endpoint. Home linked to four routes before this and
// none of them said the data was reachable programmatically at all.
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
</script>

<template>
  <AppPage>
    <template #header>
      <h1 class="app-page-title">
        Wetterdienst
      </h1>
      <p class="app-page-subtitle text-lg">
        {{ t('home.tagline') }}
      </p>
    </template>

    <!-- The headline numbers as a readout: one strip, hairlines between the cells, the figures first in size and
         aligned. The numbers of providers and parameters are the backend's: the place is held until it has answered
         (h-8 is the line of text-2xl), and a dash stands where the request failed. -->
    <dl class="grid grid-cols-2 lg:grid-cols-4 gap-px overflow-hidden rounded-lg border border-default bg-(--ui-border)">
      <div v-for="stat in stats" :key="stat.key" class="flex flex-col-reverse gap-1 bg-default px-4 py-4 sm:px-5">
        <dt class="text-xs font-semibold uppercase tracking-wider text-muted">
          {{ stat.label }}
        </dt>
        <dd class="tabular text-2xl font-semibold text-highlighted">
          <div v-if="stat.value === null && providersLoading" class="h-8 w-12 rounded-md bg-elevated animate-pulse" aria-hidden="true" />
          <template v-else>
            {{ stat.value ?? '–' }}
          </template>
        </dd>
      </div>
    </dl>

    <!-- The three tools anyone can use, on the tiles of the logo that mark them in the rail. -->
    <section aria-labelledby="home-tasks" class="space-y-3">
      <div>
        <h2 id="home-tasks" class="panel-title">
          {{ t('home.tasksTitle') }}
        </h2>
        <p class="mt-1 text-sm text-muted">
          {{ t('home.intro') }}
        </p>
      </div>
      <ul class="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <li v-for="task in tasks" :key="task.to">
          <NuxtLink
            :to="task.to"
            class="group flex h-full flex-col gap-3 rounded-lg border border-default bg-default p-5 hover:border-primary motion-safe:transition-colors"
          >
            <span class="app-tile size-10" :class="`app-tile--${task.tile}`" aria-hidden="true">
              <UIcon :name="task.icon" class="size-5" />
            </span>
            <h3 class="text-base font-semibold text-highlighted">
              {{ task.title }}
            </h3>
            <p class="flex-1 text-sm text-muted">
              {{ task.description }}
            </p>
            <span class="inline-flex items-center gap-1 text-sm font-semibold text-primary group-hover:underline underline-offset-4">
              {{ t('common.open') }}
              <UIcon name="i-lucide-arrow-right" class="size-4" aria-hidden="true" />
            </span>
          </NuxtLink>
        </li>
      </ul>
    </section>

    <!-- What arrives when you press one of the above: who publishes it, and in what kinds. -->
    <section aria-labelledby="home-data" class="space-y-3">
      <div>
        <h2 id="home-data" class="panel-title">
          {{ t('home.dataTitle') }}
        </h2>
        <p class="mt-1 text-sm text-muted">
          {{ t('home.dataIntro') }}
        </p>
      </div>

      <div class="grid grid-cols-1 items-start gap-4 xl:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]">
        <UCard data-testid="home-providers-card">
          <template #header>
            <div class="flex items-center gap-2">
              <UIcon name="i-lucide-building-2" class="panel-icon" />
              <h3 class="text-sm font-semibold text-highlighted">
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
            <div v-for="(width, index) in placeholders" :key="index" class="h-[1.875rem] rounded-md bg-elevated animate-pulse" :class="width" aria-hidden="true" />
          </div>
          <p v-else-if="!providers.length" class="text-sm text-muted">
            {{ t('home.providersEmpty') }}
          </p>
          <ul v-else class="flex flex-wrap gap-2" data-testid="home-providers">
            <li v-for="provider in providers" :key="provider.key">
              <NuxtLink
                :to="`/providers/${provider.key}`"
                class="inline-flex items-center gap-1.5 rounded-md border border-default bg-default px-2.5 py-1 text-sm font-medium hover:border-primary hover:text-primary motion-safe:transition-colors"
              >
                <span aria-hidden="true">{{ provider.flag }}</span>
                {{ provider.name }}
              </NuxtLink>
            </li>
          </ul>
          <p class="mt-4 text-sm text-muted">
            {{ t('home.dataProvidersDesc') }}
            <NuxtLink to="/glossary" class="text-primary underline underline-offset-2 hover:no-underline">
              {{ t('home.glossaryHint') }}
            </NuxtLink>
            {{ ' ' }}
            <NuxtLink to="/providers" class="text-primary underline underline-offset-2 hover:no-underline">
              {{ t('home.providersLink') }}
            </NuxtLink>
          </p>
        </UCard>

        <!-- the kinds of data, as a list to scan: an icon, the kind, a line about it -->
        <ul class="divide-y divide-default overflow-hidden rounded-lg border border-default bg-default">
          <li v-for="kind in dataKinds" :key="kind.title" class="flex items-start gap-3 px-4 py-3 sm:px-5">
            <UIcon :name="kind.icon" class="panel-icon mt-0.5 size-5" />
            <div class="min-w-0">
              <h3 class="text-sm font-semibold text-highlighted">
                {{ kind.title }}
              </h3>
              <p class="text-sm text-muted">
                {{ kind.description }}
              </p>
            </div>
          </li>
        </ul>
      </div>

      <!-- A subsection of the data block: what you can do with the data once you have it. Text, not links: on this
           page only the tools above and the chips answer the pointer. -->
      <div class="rounded-lg border border-default bg-default">
        <h3 class="border-b border-default bg-muted/60 px-4 py-3 text-sm font-semibold text-highlighted sm:px-5">
          {{ t('home.featuresTitle') }}
        </h3>
        <div class="grid grid-cols-1 md:grid-cols-2 md:divide-x divide-y md:divide-y-0 divide-default">
          <div v-for="feature in features" :key="feature.title" class="flex items-start gap-3 px-4 py-4 sm:px-5">
            <UIcon :name="feature.icon" class="panel-icon mt-0.5 size-5" />
            <div class="min-w-0">
              <h4 class="text-sm font-semibold text-highlighted">
                {{ feature.title }}
              </h4>
              <p class="text-sm text-muted">
                {{ feature.description }}
              </p>
            </div>
          </div>
        </div>
      </div>
    </section>

    <!-- The developer path: the same data, no clicking. -->
    <section aria-labelledby="home-dev" class="space-y-3">
      <div>
        <h2 id="home-dev" class="panel-title">
          {{ t('home.devTitle') }}
        </h2>
        <p class="mt-1 text-sm text-muted">
          {{ t('home.devText') }}
        </p>
      </div>
      <div class="flex flex-wrap gap-2">
        <!-- NuxtLink for all three: it renders an external URL as a plain anchor by itself, which
             is simpler than switching the component per entry -- and switching it via
             `resolveComponent` in the template silently rendered two of these as text, not links. -->
        <NuxtLink
          v-for="entry in devEntries"
          :key="entry.key"
          :to="entry.to"
          external
          target="_blank"
          :title="entry.title"
          class="inline-flex items-center gap-2 rounded-md border border-default bg-default px-3 py-1.5 font-mono text-sm hover:border-primary hover:text-primary motion-safe:transition-colors"
        >
          <UIcon :name="entry.icon" class="size-4 shrink-0" />
          {{ entry.label }}
        </NuxtLink>
      </div>
    </section>

    <!-- The stance and who backs the work: two statements the project makes about itself, side by side and of the
         same weight. The stance carries the flag's colours as a band, which is decoration: the words say it. -->
    <div class="grid grid-cols-1 gap-4 md:grid-cols-2">
      <section class="overflow-hidden rounded-lg border border-default bg-default">
        <div class="h-1 bg-[linear-gradient(90deg,#e40303,#ff8c00,#ffed00,#008026,#004dff,#750787,#5bcefa,#f5a9b8)]" aria-hidden="true" />
        <div class="px-4 py-4 sm:px-5">
          <h2 class="panel-title mb-3">
            {{ t('values.title') }}
          </h2>
          <ul class="space-y-2">
            <li v-for="value in values" :key="value.key" class="flex items-center gap-2.5 font-medium text-highlighted">
              <span aria-hidden="true">{{ value.emoji }}</span>
              {{ value.text }}
            </li>
          </ul>
        </div>
      </section>

      <section class="rounded-lg border border-default bg-default px-4 py-4 sm:px-5">
        <h2 class="panel-title mb-3">
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
            class="inline-flex items-center gap-1.5 rounded-md border border-default px-3 py-1.5 text-sm font-medium hover:border-primary hover:text-primary motion-safe:transition-colors"
          >
            <UIcon :name="supporter.icon" class="size-4 shrink-0" />
            {{ supporter.name }}
          </a>
        </div>
        <!-- The project and the people behind it live on their own page, so the home page can stay about the data. -->
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
  </AppPage>
</template>
