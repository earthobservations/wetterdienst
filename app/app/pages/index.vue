<script setup lang="ts">
const { t } = useI18n()

// Primary, consumer-facing tasks. Explorer is intentionally a first-class
// entry point here (not hidden behind an "advanced" section) — it is made
// approachable through the Explorer's guided Simple mode.
const tasks = computed(() => [
  {
    to: '/meteogram',
    icon: 'i-lucide-cloud-sun',
    title: t('home.forecastTitle'),
    description: t('home.forecastDesc'),
    accent: 'text-amber-500',
  },
  {
    to: '/stripes',
    icon: 'i-lucide-bar-chart-big',
    title: t('home.stripesTitle'),
    description: t('home.stripesDesc'),
    accent: 'text-red-500',
  },
  {
    to: '/explorer',
    icon: 'i-lucide-compass',
    title: t('home.explorerTitle'),
    description: t('home.explorerDesc'),
    accent: 'text-primary-500',
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

// Headline numbers: the providers are the backend's count; the 514 canonical parameters of
// `metadata/parameter_table.py` are written out, and `tests/unit/i18n-parity.test.ts` holds the glossary to them.
const stats = computed(() => [
  { key: 'providers', value: providerList.value ? String(providerList.value.metadata.counts.providers) : null, label: t('home.statProviders') },
  { key: 'parameters', value: '514', label: t('home.statParameters') },
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
  <div class="max-w-4xl mx-auto py-8 px-4">
    <div class="text-center mb-10">
      <h1 class="text-3xl font-bold mb-4 break-words">
        Wetterdienst
      </h1>
      <p class="text-xl text-gray-600 dark:text-gray-400">
        {{ t('home.tagline') }}
      </p>
    </div>

    <!-- Primary task cards: the friendly, everyone-can-use entry points. -->
    <h2 class="text-center text-lg font-bold mb-1">
      {{ t('home.tasksTitle') }}
    </h2>
    <p class="text-center text-sm text-gray-500 dark:text-gray-400 mb-6">
      {{ t('home.intro') }}
    </p>
    <div class="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-12">
      <NuxtLink
        v-for="task in tasks"
        :key="task.to"
        :to="task.to"
        class="group"
      >
        <UCard
          class="h-full transition-all hover:ring-2 hover:ring-primary-400 hover:-translate-y-0.5"
          :ui="{ body: 'flex flex-col items-center text-center gap-3 h-full' }"
        >
          <UIcon :name="task.icon" class="text-4xl" :class="task.accent" />
          <h3 class="font-bold text-base">
            {{ task.title }}
          </h3>
          <p class="text-sm text-gray-600 dark:text-gray-400 flex-1">
            {{ task.description }}
          </p>
          <span class="text-sm font-medium text-primary-700 dark:text-primary-500 group-hover:underline">
            {{ t('common.open') }} →
          </span>
        </UCard>
      </NuxtLink>
    </div>

    <!-- What actually arrives when you press a button above: who publishes it, how much of it
         there is, and in what shapes. -->
    <h2 class="text-lg font-bold mb-1">
      {{ t('home.dataTitle') }}
    </h2>
    <p class="text-sm text-gray-500 dark:text-gray-400 mb-4">
      {{ t('home.dataIntro') }}
    </p>

    <div class="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-6">
      <UCard v-for="stat in stats" :key="stat.key" :ui="{ body: 'text-center py-4' }">
        <!-- the number of providers is the backend's: its place is held until it has answered (h-8 is the
             line of text-2xl), and it is a dash where the request failed -->
        <div class="text-2xl font-bold text-primary-600 dark:text-primary-500">
          <div v-if="stat.value === null && providersLoading" class="h-8 w-10 mx-auto rounded-md bg-elevated animate-pulse" aria-hidden="true" />
          <template v-else>
            {{ stat.value ?? '–' }}
          </template>
        </div>
        <div class="text-xs text-gray-600 dark:text-gray-400 mt-1">
          {{ stat.label }}
        </div>
      </UCard>
    </div>

    <UCard class="mb-6" data-testid="home-providers-card">
      <template #header>
        <div class="flex items-center gap-2">
          <UIcon name="i-lucide-building-2" class="text-primary-500 shrink-0" />
          <h3 class="font-bold">
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
      <p v-else-if="!providers.length" class="text-sm text-gray-500 dark:text-gray-400">
        {{ t('home.providersEmpty') }}
      </p>
      <ul v-else class="flex flex-wrap gap-2" data-testid="home-providers">
        <li v-for="provider in providers" :key="provider.key">
          <NuxtLink
            :to="`/providers/${provider.key}`"
            class="inline-flex items-center gap-1.5 rounded-full border border-gray-200 dark:border-gray-700 px-3 py-1 text-sm hover:border-primary-400 hover:text-primary-500 transition-colors"
          >
            <span aria-hidden="true">{{ provider.flag }}</span>
            {{ provider.name }}
          </NuxtLink>
        </li>
      </ul>
      <p class="text-sm text-gray-500 dark:text-gray-400 mt-4">
        {{ t('home.dataProvidersDesc') }}
        <NuxtLink to="/glossary" class="text-primary-700 dark:text-primary-500 underline hover:no-underline">
          {{ t('home.glossaryHint') }}
        </NuxtLink>
        <NuxtLink to="/providers" class="text-primary-700 dark:text-primary-500 underline hover:no-underline">
          {{ t('home.providersLink') }}
        </NuxtLink>
      </p>
    </UCard>

    <div class="grid grid-cols-1 md:grid-cols-2 gap-4 mb-8">
      <UCard v-for="kind in dataKinds" :key="kind.title">
        <div class="flex items-start gap-3">
          <UIcon :name="kind.icon" class="text-2xl text-primary-500 flex-shrink-0 mt-1" />
          <div>
            <h3 class="font-medium mb-1">
              {{ kind.title }}
            </h3>
            <p class="text-sm text-gray-600 dark:text-gray-400">
              {{ kind.description }}
            </p>
          </div>
        </div>
      </UCard>
    </div>

    <!-- A subsection of the data block rather than a section of its own: it is still about the
         data, and as a peer heading over two cards it read as a stub after the block above. -->
    <h3 class="font-bold mb-3">
      {{ t('home.featuresTitle') }}
    </h3>
    <div class="grid grid-cols-1 md:grid-cols-2 gap-4 mb-12">
      <!-- No hover lift here: these cards are text, not links. On the page only the task cards
           above are clickable, so they are the only ones that answer the pointer. -->
      <UCard v-for="feature in features" :key="feature.title">
        <div class="flex items-start gap-3">
          <UIcon :name="feature.icon" class="text-2xl text-primary-500 flex-shrink-0 mt-1" />
          <div>
            <h3 class="font-medium mb-1">
              {{ feature.title }}
            </h3>
            <p class="text-sm text-gray-600 dark:text-gray-400">
              {{ feature.description }}
            </p>
          </div>
        </div>
      </UCard>
    </div>

    <!-- The developer path, which the page did not mention at all: same data, no clicking. -->
    <div class="text-center mb-12">
      <h3 class="font-bold mb-1">
        {{ t('home.devTitle') }}
      </h3>
      <p class="text-sm text-gray-500 dark:text-gray-400 mb-3">
        {{ t('home.devText') }}
      </p>
      <div class="flex flex-wrap justify-center gap-2">
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
          class="inline-flex items-center gap-1.5 rounded-full border border-gray-200 dark:border-gray-700 px-3 py-1 text-sm hover:border-primary-400 hover:text-primary-500 transition-colors"
        >
          <UIcon :name="entry.icon" class="size-4 shrink-0" />
          {{ entry.label }}
        </NuxtLink>
      </div>
    </div>

    <!-- Values: an unmistakable stance for inclusion and against fascism, closing the page. -->
    <section class="mb-6 rounded-2xl border border-primary-200 dark:border-primary-900 bg-gradient-to-r from-pink-50 via-purple-50 to-sky-50 dark:from-pink-950/30 dark:via-purple-950/20 dark:to-sky-950/30 p-6 text-center">
      <h2 class="text-lg font-bold mb-3">
        {{ t('values.title') }}
      </h2>
      <div class="flex flex-col sm:flex-row items-center justify-center gap-3 sm:gap-8">
        <p v-for="value in values" :key="value.key" class="flex items-center gap-2 text-base font-medium">
          <span aria-hidden="true">{{ value.emoji }}</span>
          {{ value.text }}
        </p>
      </div>
    </section>

    <!-- Who backs the work: its own block, in the same gradient as the stance above it. Two
         statements the project makes about itself, told apart by the gap rather than by one of
         them looking like a footnote to the other. -->
    <section class="mb-12 rounded-2xl border border-primary-200 dark:border-primary-900 bg-gradient-to-r from-pink-50 via-purple-50 to-sky-50 dark:from-pink-950/30 dark:via-purple-950/20 dark:to-sky-950/30 p-6 text-center">
      <h2 class="text-lg font-bold mb-3">
        {{ t('home.supportedByTitle') }}
      </h2>
      <div class="flex flex-wrap justify-center gap-2">
        <a
          v-for="supporter in supporters"
          :key="supporter.key"
          :href="supporter.to"
          target="_blank"
          :title="supporter.detail"
          :aria-label="`${supporter.name} — ${supporter.detail}`"
          class="inline-flex items-center gap-1.5 rounded-full border border-gray-200 dark:border-gray-700 bg-white/70 dark:bg-gray-900/40 px-3 py-1 text-sm hover:border-primary-400 hover:text-primary-500 transition-colors"
        >
          <UIcon :name="supporter.icon" class="size-4 shrink-0" />
          {{ supporter.name }}
        </a>
      </div>
    </section>

    <!-- The project and the people behind it live on their own page now, so the home page can
         stay about the data. -->
    <div class="text-center">
      <UButton
        to="/about"
        variant="link"
        icon="i-lucide-info"
        trailing-icon="i-lucide-arrow-right"
      >
        {{ t('home.aboutLink') }}
      </UButton>
    </div>
  </div>
</template>
