<script setup lang="ts">
const { t } = useI18n()

// Primary, consumer-facing tasks. Explorer is intentionally a first-class
// entry point here (not hidden behind an "advanced" section) — it is made
// approachable through the Explorer's guided Simple mode. Each carries the tile of the logo that is its colour
// across the app (the masthead's sections, the pages' heads).
const tasks = computed(() => [
  {
    to: '/meteogram',
    figure: 'forecast' as const,
    tile: 'bg-tile-sun',
    title: t('home.forecastTitle'),
    description: t('home.forecastDesc'),
  },
  {
    to: '/stripes',
    figure: 'stripes' as const,
    tile: 'bg-tile-heat',
    title: t('home.stripesTitle'),
    description: t('home.stripesDesc'),
  },
  {
    to: '/explorer',
    figure: 'explorer' as const,
    tile: 'bg-tile-rain',
    title: t('home.explorerTitle'),
    description: t('home.explorerDesc'),
  },
])

// What you can do with the data once you have it. Two entries rather than four: "multiple data
// sources" and "geospatial queries" said what the services block and the Explorer above now
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
// is null, and the figure holds its place until the request has answered.
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

const chip = 'inline-flex items-center gap-1.5 rounded-sm border border-(--app-rule) px-2.5 py-1 text-sm text-default hover:border-(--app-rule-strong) hover:text-highlighted transition-colors'
</script>

<template>
  <div class="app-page pb-8">
    <!-- The lead: what the site is, in a headline and a paragraph -->
    <div class="pt-10 sm:pt-16 pb-10 sm:pb-14 border-b border-(--app-rule)">
      <p class="app-kicker mb-4">
        <span class="flex gap-1" aria-hidden="true">
          <span class="app-tile bg-tile-sun" />
          <span class="app-tile bg-tile-rain" />
          <span class="app-tile bg-tile-wind" />
          <span class="app-tile bg-tile-heat" />
        </span>
        Wetterdienst
      </p>
      <h1 class="app-title max-w-4xl">
        {{ t('home.tagline') }}
      </h1>
      <p class="app-lede app-measure mt-5">
        {{ t('home.dataIntro') }}
      </p>
    </div>

    <!-- Three ways in, side by side as a newspaper's columns, each with a drawing of what it shows -->
    <section aria-labelledby="home-tasks" class="py-10 sm:py-12 border-b border-(--app-rule)">
      <div class="flex flex-wrap items-baseline justify-between gap-x-6 gap-y-1 mb-6">
        <h2 id="home-tasks" class="text-[1.625rem] sm:text-3xl font-semibold text-highlighted">
          {{ t('home.tasksTitle') }}
        </h2>
        <p class="text-muted">
          {{ t('home.intro') }}
        </p>
      </div>
      <ol class="grid grid-cols-1 md:grid-cols-3 gap-y-8 md:gap-x-8">
        <li v-for="(task, index) in tasks" :key="task.to" class="border-t-2 border-(--app-rule-strong)">
          <NuxtLink :to="task.to" class="group flex flex-col h-full gap-3 pt-4 rounded-sm">
            <div class="rounded-sm overflow-hidden border border-(--app-rule)">
              <HomeFigure :kind="task.figure" />
            </div>
            <p class="app-kicker" aria-hidden="true">
              <span class="app-tile" :class="task.tile" />
              {{ String(index + 1).padStart(2, '0') }}
            </p>
            <h3 class="text-[1.5rem] font-semibold leading-tight text-highlighted group-hover:underline decoration-2 underline-offset-4">
              {{ task.title }}
            </h3>
            <p class="text-toned flex-1">
              {{ task.description }}
            </p>
            <span class="inline-flex items-center gap-1 text-sm font-semibold text-primary">
              {{ t('common.open') }}
              <UIcon name="i-lucide-arrow-right" class="size-4 transition-transform motion-safe:group-hover:translate-x-0.5" />
            </span>
          </NuxtLink>
        </li>
      </ol>
    </section>

    <!-- What actually arrives when you press a button above: who publishes it, how much of it
         there is, and in what shapes. -->
    <section aria-labelledby="home-data" class="py-10 sm:py-12 border-b border-(--app-rule)">
      <h2 id="home-data" class="text-[1.625rem] sm:text-3xl font-semibold text-highlighted mb-6">
        {{ t('home.dataTitle') }}
      </h2>

      <!-- the figures, as an almanac sets them: the number large, what it counts under it -->
      <dl class="grid grid-cols-2 lg:grid-cols-4 gap-x-6 gap-y-6 mb-10">
        <div v-for="stat in stats" :key="stat.key" class="flex flex-col-reverse justify-end gap-1 border-t border-(--app-rule) pt-3">
          <dt class="text-sm text-muted">
            {{ stat.label }}
          </dt>
          <!-- the numbers of providers and parameters are the backend's: its place is held until it has answered,
               and it is a dash where the request failed -->
          <dd class="app-figure-number text-2xl sm:text-4xl">
            <div v-if="stat.value === null && providersLoading" class="h-8 sm:h-10 w-12 rounded-sm bg-elevated animate-pulse" aria-hidden="true" />
            <template v-else>
              {{ stat.value ?? '–' }}
            </template>
          </dd>
        </div>
      </dl>

      <div class="grid gap-10 lg:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]">
        <div data-testid="home-providers-card">
          <h3 class="text-xl font-semibold text-highlighted mb-4">
            {{ t('home.dataProvidersTitle') }}
          </h3>
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
            <div v-for="(width, index) in placeholders" :key="index" class="h-[1.875rem] rounded-sm bg-elevated animate-pulse" :class="width" aria-hidden="true" />
          </div>
          <p v-else-if="!providers.length" class="text-sm text-muted">
            {{ t('home.providersEmpty') }}
          </p>
          <ul v-else class="flex flex-wrap gap-2" data-testid="home-providers">
            <li v-for="provider in providers" :key="provider.key">
              <NuxtLink :to="`/providers/${provider.key}`" :class="chip">
                <span aria-hidden="true">{{ provider.flag }}</span>
                {{ provider.name }}
              </NuxtLink>
            </li>
          </ul>
          <p class="text-sm text-muted mt-4 app-measure">
            {{ t('home.dataProvidersDesc') }}
            <NuxtLink to="/glossary" class="text-primary underline underline-offset-2 hover:no-underline">
              {{ t('home.glossaryHint') }}
            </NuxtLink>
            {{ ' ' }}
            <NuxtLink to="/providers" class="text-primary underline underline-offset-2 hover:no-underline">
              {{ t('home.providersLink') }}
            </NuxtLink>
          </p>
        </div>

        <!-- A subsection of the data block rather than a section of its own: it is still about the data -->
        <div>
          <h3 class="text-xl font-semibold text-highlighted mb-4">
            {{ t('home.featuresTitle') }}
          </h3>
          <!-- No hover here: these are text, not links. On the page only the ways in and the chips answer the pointer. -->
          <ul class="space-y-4">
            <li v-for="feature in features" :key="feature.title" class="flex items-start gap-3">
              <UIcon :name="feature.icon" class="size-5 text-primary shrink-0 mt-0.5" />
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
        </div>
      </div>

      <!-- the kinds of data, as a contents page: entries in columns, each under a rule -->
      <ul class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-x-8 mt-10">
        <li v-for="kind in dataKinds" :key="kind.title" class="flex items-start gap-3 py-4 border-t border-(--app-rule)">
          <UIcon :name="kind.icon" class="size-5 text-primary shrink-0 mt-1" />
          <div>
            <h3 class="font-semibold text-lg leading-snug text-highlighted">
              {{ kind.title }}
            </h3>
            <p class="text-sm text-toned">
              {{ kind.description }}
            </p>
          </div>
        </li>
      </ul>
    </section>

    <!-- The developer path: same data, no clicking. -->
    <section aria-labelledby="home-dev" class="py-10 grid gap-4 md:grid-cols-[minmax(0,1fr)_auto] md:items-center border-b border-(--app-rule)">
      <div>
        <h2 id="home-dev" class="text-xl font-semibold text-highlighted mb-1">
          {{ t('home.devTitle') }}
        </h2>
        <p class="text-sm text-toned">
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
          class="font-mono" :class="[chip]"
        >
          <UIcon :name="entry.icon" class="size-4 shrink-0" />
          {{ entry.label }}
        </NuxtLink>
      </div>
    </section>

    <!-- What the project stands for and who backs it: two statements side by side, closing the page -->
    <div class="py-10 grid gap-10 md:grid-cols-[minmax(0,2fr)_minmax(0,1fr)]">
      <section aria-labelledby="home-values">
        <h2 id="home-values" class="text-xl font-semibold text-highlighted mb-4">
          {{ t('values.title') }}
        </h2>
        <ul class="grid gap-3 sm:grid-cols-2">
          <li v-for="value in values" :key="value.key" class="flex items-start gap-3 font-serif text-lg leading-snug text-highlighted">
            <span aria-hidden="true" class="shrink-0">{{ value.emoji }}</span>
            {{ value.text }}
          </li>
        </ul>
      </section>
      <section aria-labelledby="home-supporters">
        <h2 id="home-supporters" class="text-xl font-semibold text-highlighted mb-4">
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
            :class="chip"
          >
            <UIcon :name="supporter.icon" class="size-4 shrink-0" />
            {{ supporter.name }}
          </a>
        </div>
        <!-- The project and the people behind it live on their own page, so the home page can stay about the data -->
        <UButton
          to="/about"
          variant="link"
          icon="i-lucide-info"
          trailing-icon="i-lucide-arrow-right"
          class="mt-6 px-0"
        >
          {{ t('home.aboutLink') }}
        </UButton>
      </section>
    </div>
  </div>
</template>
