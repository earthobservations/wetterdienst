<script setup lang="ts">
const { t } = useI18n()

// Start here: the three things most visitors come for, each a plain sentence that says what it does. The colour of each
// is a tile of the logo (sun, rain, thermometer); the words carry the meaning, the colour is decoration.
const journeys = computed(() => [
  {
    to: '/meteogram',
    icon: 'i-lucide-cloud-sun',
    title: t('home.startForecast'),
    description: t('home.forecastDesc'),
    tile: 'bg-(--color-sun) text-(--color-ink-950)',
  },
  {
    to: '/explorer',
    icon: 'i-lucide-download',
    title: t('home.startMeasurements'),
    description: t('home.explorerDesc'),
    tile: 'bg-brand-500 text-white',
  },
  {
    to: '/stripes',
    icon: 'i-lucide-thermometer',
    title: t('home.startWarming'),
    description: t('home.stripesDesc'),
    tile: 'bg-(--color-ember) text-white',
  },
])

// Behind the three: the tools for a closer look, each named with what it is for (the search says the same)
const { pages } = useSiteNav()
const tools = computed(() => [
  ...pages.value.filter(page => ['/history', '/providers', '/glossary', '/api'].includes(page.to)),
  {
    to: '/explorer?mode=interpolation',
    label: t('home.featureAnalysisTitle'),
    purpose: t('home.featureAnalysisDesc'),
    icon: 'i-lucide-crosshair',
  },
])

const { open: paletteOpen } = usePalette()

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
const PLACEHOLDER_WIDTHS = ['w-20', 'w-28', 'w-24', 'w-32', 'w-20', 'w-28', 'w-24']
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
  <AppPage width="wide">
    <template #header>
      <h1 class="text-4xl sm:text-5xl font-bold tracking-tight text-highlighted break-words">
        Wetterdienst
      </h1>
      <p class="mt-3 text-xl sm:text-2xl text-toned">
        {{ t('home.tagline') }}
      </p>
      <p class="mt-2 text-lg text-muted">
        {{ t('home.dataIntro') }}
      </p>
    </template>

    <!-- Start here: the three common tasks, as whole-card links with the task as their name -->
    <section aria-labelledby="home-start">
      <h2 id="home-start" class="text-2xl font-bold text-highlighted mb-4">
        {{ t('home.tasksTitle') }}
      </h2>
      <ul class="grid gap-4 md:grid-cols-3">
        <li v-for="journey in journeys" :key="journey.to">
          <NuxtLink
            :to="journey.to"
            class="group flex h-full gap-4 rounded-md border-2 border-default bg-default p-5 no-underline hover:border-(--ui-primary) md:flex-col"
          >
            <span class="flex size-12 shrink-0 items-center justify-center rounded-xl" :class="journey.tile" aria-hidden="true">
              <UIcon :name="journey.icon" class="size-7" />
            </span>
            <span class="flex flex-1 flex-col gap-2">
              <span class="text-xl font-bold text-primary underline underline-offset-4 decoration-2 group-hover:decoration-4">
                {{ journey.title }}
              </span>
              <span class="text-toned">
                {{ journey.description }}
              </span>
            </span>
            <UIcon name="i-lucide-arrow-right" class="hidden size-6 shrink-0 self-end text-primary md:block" aria-hidden="true" />
          </NuxtLink>
        </li>
      </ul>
    </section>

    <!-- Or the search: the same dialog as the header's, from a field where a newcomer looks for one -->
    <section aria-labelledby="home-search" class="mt-10 app-measure">
      <h2 id="home-search" class="text-lg font-bold text-highlighted mb-2">
        {{ t('home.searchTitle') }}
      </h2>
      <button
        type="button"
        class="flex w-full items-center gap-3 rounded-md border-2 border-(--ui-border-accented) bg-default px-4 py-3 text-start text-lg text-muted hover:border-(--ui-primary)"
        aria-haspopup="dialog"
        :aria-expanded="paletteOpen"
        @click="paletteOpen = true"
      >
        <UIcon name="i-lucide-search" class="size-5 shrink-0" />
        {{ t('palette.trigger') }}
      </button>
    </section>

    <!-- The expert's next steps, each said in a line -->
    <section aria-labelledby="home-more" class="mt-12">
      <h2 id="home-more" class="text-2xl font-bold text-highlighted">
        {{ t('home.moreTitle') }}
      </h2>
      <p class="mt-1 mb-4 text-toned">
        {{ t('home.moreIntro') }}
      </p>
      <ul class="grid gap-x-8 border-t border-default md:grid-cols-2">
        <li v-for="tool in tools" :key="tool.to" class="border-b border-default">
          <NuxtLink :to="tool.to" class="group flex items-start gap-3 py-4 no-underline">
            <UIcon :name="tool.icon" class="size-5 shrink-0 mt-1 text-toned" />
            <span>
              <span class="block text-lg font-semibold text-primary underline underline-offset-4 group-hover:decoration-2">{{ tool.label }}</span>
              <span class="block text-toned">{{ tool.purpose }}</span>
            </span>
          </NuxtLink>
        </li>
      </ul>
    </section>

    <!-- What actually arrives when you press a button above: who publishes it, how much of it
         there is, and in what shapes. -->
    <section aria-labelledby="home-data" class="mt-12">
      <h2 id="home-data" class="text-2xl font-bold text-highlighted">
        {{ t('home.dataTitle') }}
      </h2>

      <dl class="mt-4 grid grid-cols-2 gap-4 sm:grid-cols-4" data-testid="home-stats">
        <!-- the term first, as a list of terms has it; the number is shown above it -->
        <div v-for="stat in stats" :key="stat.key" class="flex flex-col-reverse justify-end border-s-4 border-brand-500 ps-3">
          <dt class="text-sm text-toned">
            {{ stat.label }}
          </dt>
          <!-- the numbers of providers and parameters are the backend's: its place is held until it has answered (h-8 is the
               line of text-2xl), and it is a dash where the request failed -->
          <dd class="text-2xl font-bold text-highlighted">
            <div v-if="stat.value === null && providersLoading" class="h-8 w-10 rounded-md bg-elevated animate-pulse" aria-hidden="true" />
            <template v-else>
              {{ stat.value ?? '–' }}
            </template>
          </dd>
        </div>
      </dl>

      <div class="mt-8" data-testid="home-providers-card">
        <h3 class="text-lg font-bold text-highlighted mb-3">
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
          <div v-for="(width, index) in placeholders" :key="index" class="h-[2.125rem] rounded-md bg-elevated animate-pulse" :class="width" aria-hidden="true" />
        </div>
        <p v-else-if="!providers.length" class="text-muted">
          {{ t('home.providersEmpty') }}
        </p>
        <ul v-else class="flex flex-wrap gap-2" data-testid="home-providers">
          <li v-for="provider in providers" :key="provider.key">
            <NuxtLink
              :to="`/providers/${provider.key}`"
              class="inline-flex items-center gap-1.5 rounded-md border border-(--ui-border-accented) px-3 py-1 leading-6 text-primary hover:bg-brand-50 dark:hover:bg-ink-800"
            >
              <span aria-hidden="true">{{ provider.flag }}</span>
              {{ provider.name }}
            </NuxtLink>
          </li>
        </ul>
        <p class="mt-4 text-toned app-measure">
          {{ t('home.dataProvidersDesc') }}
          <NuxtLink to="/glossary" class="text-primary underline">
            {{ t('home.glossaryHint') }}
          </NuxtLink>
          {{ ' ' }}
          <NuxtLink to="/providers" class="text-primary underline">
            {{ t('home.providersLink') }}
          </NuxtLink>
        </p>
      </div>

      <ul class="mt-8 grid gap-x-8 gap-y-6 md:grid-cols-2">
        <li v-for="kind in dataKinds" :key="kind.title" class="flex items-start gap-3">
          <UIcon :name="kind.icon" class="size-6 shrink-0 mt-0.5 text-toned" />
          <div>
            <h3 class="font-bold text-highlighted">
              {{ kind.title }}
            </h3>
            <p class="text-toned">
              {{ kind.description }}
            </p>
          </div>
        </li>
      </ul>
    </section>

    <!-- The developer path: same data, no clicking. -->
    <section aria-labelledby="home-dev" class="mt-12 app-measure">
      <h2 id="home-dev" class="text-2xl font-bold text-highlighted">
        {{ t('home.devTitle') }}
      </h2>
      <p class="mt-1 mb-4 text-toned">
        {{ t('home.devText') }}
      </p>
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
          class="inline-flex items-center gap-1.5 rounded-md border border-(--ui-border-accented) px-3 py-1 font-mono text-sm text-primary hover:bg-brand-50 dark:hover:bg-ink-800"
        >
          <UIcon :name="entry.icon" class="size-4 shrink-0" />
          {{ entry.label }}
        </NuxtLink>
      </div>
    </section>

    <!-- Who backs the work. -->
    <section aria-labelledby="home-supported" class="mt-12 app-measure">
      <h2 id="home-supported" class="text-lg font-bold text-highlighted mb-3">
        {{ t('home.supportedByTitle') }}
      </h2>
      <ul class="space-y-2">
        <li v-for="supporter in supporters" :key="supporter.key" class="flex items-start gap-2">
          <UIcon :name="supporter.icon" class="size-5 shrink-0 mt-0.5 text-toned" />
          <span>
            <a :href="supporter.to" target="_blank" class="font-semibold text-primary underline">{{ supporter.name }}</a>
            <span class="block text-toned">{{ supporter.detail }}</span>
          </span>
        </li>
      </ul>
      <p class="mt-8">
        <NuxtLink to="/about" class="inline-flex items-center gap-1.5 font-semibold text-primary underline">
          {{ t('home.aboutLink') }}
          <UIcon name="i-lucide-arrow-right" class="size-4" />
        </NuxtLink>
      </p>
    </section>
  </AppPage>
</template>
