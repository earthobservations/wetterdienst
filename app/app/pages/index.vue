<script setup lang="ts">
const { t } = useI18n()

// Primary, consumer-facing tasks. Explorer is intentionally a first-class
// entry point here (not hidden behind an "advanced" section) — it is made
// approachable through the Explorer's guided Simple mode.
const tasks = computed(() => [
  {
    to: '/meteogram',
    icon: 'i-ph-cloud-sun',
    title: t('home.forecastTitle'),
    description: t('home.forecastDesc'),
  },
  {
    to: '/stripes',
    icon: 'i-ph-barcode',
    title: t('home.stripesTitle'),
    description: t('home.stripesDesc'),
  },
  {
    to: '/explorer',
    icon: 'i-ph-compass',
    title: t('home.explorerTitle'),
    description: t('home.explorerDesc'),
  },
])

// What you can do with the data once you have it. Two cards rather than four: "multiple data
// sources" and "geospatial queries" said what the services card and the Explorer card above now
// say better, and a home page that repeats itself reads as padding.
const features = computed(() => [
  { icon: 'i-ph-download-simple', title: t('home.featureExportTitle'), description: t('home.featureExportDesc') },
  { icon: 'i-ph-chart-line', title: t('home.featureAnalysisTitle'), description: t('home.featureAnalysisDesc') },
])

// The weather services behind the data, as the backend lists them (`GET /api/providers`): one chip for each
// provider of its registry, so a provider added upstream is on this page without a change here. Short names
// and the code of the provider's own country, and NOAA's GHCN is worldwide despite the US code, which
// `home.dataProvidersDesc` says. The request is the one the Providers pages share, by its key.
const { locale } = useI18n()
const collator = computed(() => new Intl.Collator(locale.value, { numeric: true }))
const { data: providerList, pending: providersPending, error: providersError, refresh: refreshProviders } = useProviders()

const providers = computed(() => (providerList.value?.providers ?? [])
  .map(provider => ({ key: provider.provider, name: provider.name_short, country: provider.country_code }))
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
  { key: 'pypi', label: 'pip install wetterdienst', mono: true, icon: 'i-simple-icons-python', to: 'https://pypi.org/project/wetterdienst/', title: undefined },
  // this instance's own endpoints rather than the page that describes them: /docs is the backend's
  // Swagger UI, proxied onto this origin, and /mcp/v1 is the endpoint itself. Both are served by
  // nitro rather than by the Vue router, so they need a full navigation, not a client-side one.
  { key: 'api', label: 'REST API', mono: false, icon: 'i-ph-brackets-curly', to: '/docs', title: undefined },
  { key: 'mcp', label: 'MCP', mono: false, icon: 'i-ph-robot', to: '/mcp/v1', title: t('home.devMcpHint') },
])

// What the project stands for. Shared with the footer, which shows the same four as icons.
const values = computed(() => [
  { key: 'lgbtq', icon: 'i-ph-rainbow', text: t('values.lgbtq') },
  { key: 'antifascist', icon: 'i-ph-hand-fist', text: t('values.antifascist') },
  { key: 'climate', icon: 'i-ph-thermometer-hot', text: t('values.climate') },
  { key: 'openData', icon: 'i-ph-lock-open', text: t('values.openData') },
])

// What kinds of data the networks behind those providers actually serve.
const dataKinds = computed(() => [
  { icon: 'i-ph-thermometer', title: t('home.kindObservationsTitle'), description: t('home.kindObservationsDesc') },
  { icon: 'i-ph-cloud-sun', title: t('home.kindForecastsTitle'), description: t('home.kindForecastsDesc') },
  { icon: 'i-ph-waves', title: t('home.kindHydrologyTitle'), description: t('home.kindHydrologyDesc') },
  { icon: 'i-ph-broadcast', title: t('home.kindRadarTitle'), description: t('home.kindRadarDesc') },
  { icon: 'i-ph-warning', title: t('home.kindAlertsTitle'), description: t('home.kindAlertsDesc') },
  { icon: 'i-ph-car', title: t('home.kindRoadTitle'), description: t('home.kindRoadDesc') },
])
</script>

<template>
  <PageContainer wide section>
    <!-- What it is, and where to start. The strip is the climate stripes in the colours of the logo: an illustration
         (StripesBand), not data, and a way into the page of that name. -->
    <section class="pt-2 lg:pt-8">
      <h1 class="max-w-4xl text-4xl font-semibold leading-[1.05] text-highlighted break-words text-balance min-[480px]:text-5xl sm:text-6xl lg:text-7xl">
        {{ t('home.tagline') }}
      </h1>
      <p class="mt-6 max-w-2xl text-lg text-muted text-pretty sm:text-xl">
        {{ t('home.dataIntro') }}
      </p>
      <div class="mt-8 flex flex-wrap gap-3">
        <UButton to="/explorer" size="xl" trailing-icon="i-ph-arrow-right">
          {{ t('home.explorerTitle') }}
        </UButton>
        <UButton to="/meteogram" size="xl" color="neutral" variant="outline">
          {{ t('home.forecastTitle') }}
        </UButton>
      </div>

      <NuxtLink to="/stripes" class="group mt-14 block rounded-lg">
        <div class="h-28 overflow-hidden rounded-lg sm:h-40" aria-hidden="true">
          <StripesBand :count="120" />
        </div>
        <span class="mt-3 flex flex-wrap items-baseline gap-x-3 gap-y-0.5 text-sm">
          <span class="font-medium text-highlighted group-hover:underline">{{ t('home.stripesTitle') }}</span>
          <span class="text-muted">{{ t('home.stripesDesc') }}</span>
        </span>
      </NuxtLink>
    </section>

    <section>
      <h2 class="text-3xl font-semibold text-highlighted">
        {{ t('home.tasksTitle') }}
      </h2>
      <p class="mt-2 text-muted">
        {{ t('home.intro') }}
      </p>
      <div class="mt-8 grid grid-cols-1 divide-y divide-default overflow-hidden rounded-lg border border-default sm:grid-cols-3 sm:divide-x sm:divide-y-0">
        <NuxtLink
          v-for="task in tasks"
          :key="task.to"
          :to="task.to"
          class="group flex flex-col gap-3 p-6 transition-colors hover:bg-muted motion-reduce:transition-none"
        >
          <UIcon :name="task.icon" class="size-6 text-muted group-hover:text-primary" aria-hidden="true" />
          <span class="text-lg font-medium text-highlighted">{{ task.title }}</span>
          <span class="text-muted">{{ task.description }}</span>
          <span class="mt-auto inline-flex items-center gap-1.5 pt-2 text-sm font-medium text-primary">
            {{ t('common.open') }}
            <UIcon name="i-ph-arrow-right" class="size-4 transition-transform group-hover:translate-x-0.5 motion-reduce:transition-none" />
          </span>
        </NuxtLink>
      </div>
    </section>

    <!-- What actually arrives when you press a button above: who publishes it, how much of it there is, and in
         what shapes. -->
    <section>
      <h2 class="text-3xl font-semibold text-highlighted">
        {{ t('home.dataTitle') }}
      </h2>

      <div class="mt-8 grid grid-cols-2 gap-x-6 gap-y-8 sm:grid-cols-4">
        <div v-for="stat in stats" :key="stat.key" class="border-t border-accented pt-4">
          <!-- the numbers of providers and parameters are the backend's: its place is held until it has answered (h-8 is
               the line of text-2xl), and it is a dash where the request failed -->
          <div class="text-2xl font-semibold tabular-nums text-highlighted sm:text-4xl">
            <div v-if="stat.value === null && providersLoading" class="h-8 w-12 rounded-md bg-elevated animate-pulse sm:h-10" aria-hidden="true" />
            <template v-else>
              {{ stat.value ?? '–' }}
            </template>
          </div>
          <div class="mt-1 text-sm text-muted">
            {{ stat.label }}
          </div>
        </div>
      </div>

      <div class="mt-14" data-testid="home-providers-card">
        <h3 class="text-lg font-semibold text-highlighted">
          {{ t('home.dataProvidersTitle') }}
        </h3>
        <div class="mt-4">
          <UAlert
            v-if="providersFailure"
            color="error"
            variant="subtle"
            icon="i-ph-warning-circle"
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
                class="inline-flex items-center gap-2 rounded-md border border-default px-2.5 py-1 text-sm transition-colors hover:border-accented hover:bg-elevated motion-reduce:transition-none"
              >
                <ProviderMark :country="provider.country" />
                {{ provider.name }}
              </NuxtLink>
            </li>
          </ul>
        </div>
        <p class="mt-4 max-w-2xl text-sm text-muted">
          {{ t('home.dataProvidersDesc') }}
        </p>
        <p class="mt-2 flex flex-wrap gap-x-6 gap-y-1 text-sm">
          <NuxtLink to="/glossary" class="text-primary underline underline-offset-2 hover:no-underline">
            {{ t('home.glossaryHint') }}
          </NuxtLink>
          <NuxtLink to="/providers" class="text-primary underline underline-offset-2 hover:no-underline">
            {{ t('home.providersLink') }}
          </NuxtLink>
        </p>
      </div>

      <div class="mt-14 grid grid-cols-1 gap-x-10 gap-y-8 sm:grid-cols-2 lg:grid-cols-3">
        <div v-for="kind in dataKinds" :key="kind.title" class="flex items-start gap-3">
          <UIcon :name="kind.icon" class="mt-0.5 size-5 shrink-0 text-muted" aria-hidden="true" />
          <div>
            <h3 class="font-medium text-highlighted">
              {{ kind.title }}
            </h3>
            <p class="mt-1 text-sm text-muted">
              {{ kind.description }}
            </p>
          </div>
        </div>
      </div>

      <!-- A subsection of the data block rather than a section of its own: it is still about the data. -->
      <h3 class="mb-4 mt-14 text-lg font-semibold text-highlighted">
        {{ t('home.featuresTitle') }}
      </h3>
      <div class="grid grid-cols-1 gap-8 md:grid-cols-2">
        <div v-for="feature in features" :key="feature.title" class="flex items-start gap-3">
          <UIcon :name="feature.icon" class="mt-0.5 size-5 shrink-0 text-muted" aria-hidden="true" />
          <div>
            <h4 class="font-medium text-highlighted">
              {{ feature.title }}
            </h4>
            <p class="mt-1 text-sm text-muted">
              {{ feature.description }}
            </p>
          </div>
        </div>
      </div>
    </section>

    <!-- The developer path: the same data, no clicking. -->
    <section class="grid gap-8 lg:grid-cols-[1fr_1.3fr] lg:gap-16">
      <div>
        <h2 class="text-3xl font-semibold text-highlighted">
          {{ t('home.devTitle') }}
        </h2>
        <p class="mt-3 max-w-md text-muted">
          {{ t('home.devText') }}
        </p>
      </div>
      <ul class="divide-y divide-default self-start overflow-hidden rounded-lg border border-default">
        <li v-for="entry in devEntries" :key="entry.key">
          <!-- NuxtLink for all three: it renders an external URL as a plain anchor by itself, which
               is simpler than switching the component per entry -- and switching it via
               `resolveComponent` in the template silently rendered two of these as text, not links. -->
          <NuxtLink
            :to="entry.to"
            external
            target="_blank"
            :title="entry.title"
            class="group flex items-center gap-4 px-5 py-4 transition-colors hover:bg-muted motion-reduce:transition-none"
          >
            <UIcon :name="entry.icon" class="size-5 shrink-0 text-muted" aria-hidden="true" />
            <span class="min-w-0 flex-1 break-words font-medium text-highlighted" :class="entry.mono ? 'font-mono text-sm' : ''">
              {{ entry.label }}
            </span>
            <UIcon name="i-ph-arrow-up-right" class="size-4 shrink-0 text-muted transition-transform group-hover:-translate-y-0.5 group-hover:translate-x-0.5 motion-reduce:transition-none" aria-hidden="true" />
          </NuxtLink>
        </li>
      </ul>
    </section>

    <!-- Values: an unmistakable stance for inclusion and against fascism, and who backs the work. -->
    <section class="space-y-10">
      <div>
        <h2 class="text-lg font-semibold text-highlighted">
          {{ t('values.title') }}
        </h2>
        <ul class="mt-4 grid gap-x-8 gap-y-3 sm:grid-cols-2 lg:grid-cols-4">
          <li v-for="value in values" :key="value.key" class="flex items-start gap-3 text-sm">
            <UIcon :name="value.icon" class="mt-0.5 size-5 shrink-0 text-muted" aria-hidden="true" />
            <span class="text-default">{{ value.text }}</span>
          </li>
        </ul>
      </div>

      <div class="flex flex-wrap items-center gap-x-4 gap-y-3">
        <h2 class="text-sm font-medium text-muted">
          {{ t('home.supportedByTitle') }}
        </h2>
        <a
          v-for="supporter in supporters"
          :key="supporter.key"
          :href="supporter.to"
          target="_blank"
          :title="supporter.detail"
          :aria-label="`${supporter.name}: ${supporter.detail}`"
          class="inline-flex items-center gap-2 rounded-md border border-default px-2.5 py-1 text-sm transition-colors hover:border-accented hover:bg-elevated motion-reduce:transition-none"
        >
          <UIcon :name="supporter.icon" class="size-4 shrink-0" />
          {{ supporter.name }}
        </a>
        <!-- The project and the people behind it live on their own page, so the home page can stay about the data. -->
        <UButton to="/about" variant="link" trailing-icon="i-ph-arrow-right" class="ms-auto">
          {{ t('home.aboutLink') }}
        </UButton>
      </div>
    </section>
  </PageContainer>
</template>
