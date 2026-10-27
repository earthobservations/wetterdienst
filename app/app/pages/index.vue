<script setup lang="ts">
const { t } = useI18n()

// Primary, consumer-facing tasks. Explorer is intentionally a first-class
// entry point here (not hidden behind an "advanced" section) — it is made
// approachable through the Explorer's guided Simple mode.
// the tiles are the colours of the logo's: the sun for the forecast, the coral of the thermometer for the stripes,
// the blue for the data
const DELAYS = ['[--app-delay:2]', '[--app-delay:3]', '[--app-delay:4]']
const tasks = computed(() => [
  {
    to: '/meteogram',
    icon: 'i-lucide-cloud-sun',
    title: t('home.forecastTitle'),
    description: t('home.forecastDesc'),
    tile: 'bg-sun text-ink-950',
  },
  {
    to: '/stripes',
    icon: 'i-lucide-bar-chart-big',
    title: t('home.stripesTitle'),
    description: t('home.stripesDesc'),
    tile: 'bg-coral text-ink-950',
  },
  {
    to: '/explorer',
    icon: 'i-lucide-compass',
    title: t('home.explorerTitle'),
    description: t('home.explorerDesc'),
    tile: 'bg-brand-600 text-white',
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
  { key: 'providers', accent: 'bg-brand-600', value: providerList.value ? String(providerList.value.metadata.counts.providers) : null, label: t('home.statProviders') },
  { key: 'parameters', accent: 'bg-teal', value: providerList.value ? String(providerList.value.metadata.counts.parameters) : null, label: t('home.statParameters') },
  { key: 'resolutions', accent: 'bg-sun', value: '1 min – 1 a', label: t('home.statResolutions') },
  { key: 'price', accent: 'bg-coral', value: '0 €', label: t('home.statPrice') },
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
  { key: 'api', label: 'REST API', mono: false, icon: 'i-lucide-code', to: '/docs', title: undefined },
  { key: 'mcp', label: 'MCP', mono: false, icon: 'i-lucide-bot', to: '/mcp/v1', title: t('home.devMcpHint') },
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
  <div>
    <!-- Hero: what the service is, in the colours of the logo. The stripes are decoration (StripesBand), not data. -->
    <section class="relative isolate overflow-hidden">
      <UContainer class="max-w-(--app-width-wide) grid items-center gap-12 py-12 sm:py-16 lg:grid-cols-[1.15fr_0.85fr] lg:gap-16 lg:py-24">
        <div class="app-rise min-w-0">
          <h1 class="text-5xl font-extrabold leading-none text-highlighted break-words sm:text-6xl lg:text-7xl">
            Wetterdienst
          </h1>
          <p class="mt-5 text-xl font-semibold text-primary text-balance sm:text-3xl">
            {{ t('home.tagline') }}
          </p>
          <p class="mt-4 max-w-xl text-lg text-muted text-pretty">
            {{ t('home.dataIntro') }}
          </p>
          <div class="mt-8 flex flex-wrap gap-3">
            <UButton to="/explorer" size="xl" icon="i-lucide-compass" trailing-icon="i-lucide-arrow-right">
              {{ t('home.explorerTitle') }}
            </UButton>
            <UButton to="/meteogram" size="xl" color="neutral" variant="outline" icon="i-lucide-cloud-sun">
              {{ t('home.forecastTitle') }}
            </UButton>
          </div>
        </div>

        <div class="app-rise relative mx-auto w-full max-w-md [--app-delay:2] lg:max-w-none" aria-hidden="true">
          <div class="aspect-[5/4] overflow-hidden rounded-[2rem] shadow-(--app-shadow-lg) ring-1 ring-default">
            <StripesBand :count="48" />
          </div>
          <img
            src="/icon.svg"
            alt=""
            class="absolute -bottom-6 -left-3 size-28 -rotate-6 rounded-[1.75rem] shadow-(--app-shadow-lg) ring-4 ring-(--ui-bg) sm:-left-6 sm:size-36"
          >
        </div>
      </UContainer>
    </section>

    <!-- Primary task cards: the friendly, everyone-can-use entry points. -->
    <section class="py-(--app-space-section)">
      <UContainer class="max-w-(--app-width-wide)">
        <div class="mb-8 max-w-2xl">
          <h2 class="text-3xl font-bold text-highlighted">
            {{ t('home.tasksTitle') }}
          </h2>
          <p class="mt-2 text-lg text-muted">
            {{ t('home.intro') }}
          </p>
        </div>
        <div class="grid grid-cols-1 gap-5 sm:grid-cols-3">
          <UPageCard
            v-for="(task, index) in tasks"
            :key="task.to"
            :to="task.to"
            :title="task.title"
            :description="task.description"
            variant="outline"
            class="app-rise app-lift"
            :class="DELAYS[index]"
            :ui="{ container: 'p-6 sm:p-7', title: 'text-lg', description: 'text-base text-muted' }"
          >
            <template #leading>
              <span class="mb-2 grid size-12 place-items-center rounded-2xl shadow-(--app-shadow-sm)" :class="task.tile" aria-hidden="true">
                <UIcon :name="task.icon" class="size-6" />
              </span>
            </template>
            <template #footer>
              <span class="inline-flex items-center gap-1.5 text-sm font-semibold text-primary">
                {{ t('common.open') }}
                <UIcon name="i-lucide-arrow-right" class="size-4" />
              </span>
            </template>
          </UPageCard>
        </div>
      </UContainer>
    </section>

    <!-- The developer path: the same data, no clicking. A navy band in both modes. -->
    <section class="app-on-dark relative overflow-hidden bg-ink-900 text-white">
      <div class="absolute inset-x-0 top-0 h-1.5 opacity-90" aria-hidden="true">
        <StripesBand :count="96" />
      </div>
      <UContainer class="max-w-(--app-width-wide) grid gap-8 py-14 sm:py-16 lg:grid-cols-[1fr_1.3fr] lg:items-center lg:gap-16">
        <div>
          <h2 class="text-3xl font-bold">
            {{ t('home.devTitle') }}
          </h2>
          <p class="mt-3 max-w-md text-lg text-ink-200">
            {{ t('home.devText') }}
          </p>
        </div>
        <ul class="grid gap-3">
          <li v-for="entry in devEntries" :key="entry.key">
            <!-- NuxtLink for all three: it renders an external URL as a plain anchor by itself, which
                 is simpler than switching the component per entry -- and switching it via
                 `resolveComponent` in the template silently rendered two of these as text, not links. -->
            <NuxtLink
              :to="entry.to"
              external
              target="_blank"
              :title="entry.title"
              class="group flex items-center gap-4 rounded-2xl border border-white/15 bg-white/5 px-5 py-4 transition-colors hover:bg-white/10 motion-reduce:transition-none"
            >
              <span class="grid size-10 shrink-0 place-items-center rounded-xl bg-white/10">
                <UIcon :name="entry.icon" class="size-5" />
              </span>
              <span class="min-w-0 flex-1 break-words font-semibold" :class="entry.mono ? 'font-mono text-sm sm:text-base' : 'text-lg'">
                {{ entry.label }}
              </span>
              <UIcon name="i-lucide-arrow-up-right" class="size-5 shrink-0 text-ink-300 transition-transform group-hover:-translate-y-0.5 group-hover:translate-x-0.5 motion-reduce:transition-none" />
            </NuxtLink>
          </li>
        </ul>
      </UContainer>
    </section>

    <!-- What actually arrives when you press a button above: who publishes it, how much of it
         there is, and in what shapes. -->
    <section class="py-(--app-space-section)">
      <UContainer class="max-w-(--app-width-wide)">
        <div class="mb-8 max-w-2xl">
          <h2 class="text-3xl font-bold text-highlighted">
            {{ t('home.dataTitle') }}
          </h2>
        </div>

        <div class="mb-6 grid grid-cols-2 gap-4 sm:grid-cols-4">
          <div
            v-for="stat in stats"
            :key="stat.key"
            class="relative overflow-hidden rounded-2xl bg-default p-5 ring ring-default shadow-(--app-shadow-sm)"
          >
            <span class="absolute inset-x-0 top-0 h-1" :class="stat.accent" aria-hidden="true" />
            <!-- the numbers of providers and parameters are the backend's: its place is held until it has answered (h-9 is the
                 line of text-3xl), and it is a dash where the request failed -->
            <div class="text-2xl font-bold tabular-nums text-highlighted sm:text-3xl">
              <div v-if="stat.value === null && providersLoading" class="h-8 w-12 rounded-md bg-elevated animate-pulse sm:h-9" aria-hidden="true" />
              <template v-else>
                {{ stat.value ?? '–' }}
              </template>
            </div>
            <div class="mt-1 text-sm text-muted">
              {{ stat.label }}
            </div>
          </div>
        </div>

        <UCard class="mb-10" data-testid="home-providers-card">
          <template #header>
            <div class="flex items-center gap-2">
              <UIcon name="i-lucide-building-2" class="text-primary shrink-0" />
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
          <p v-else-if="!providers.length" class="text-sm text-muted">
            {{ t('home.providersEmpty') }}
          </p>
          <ul v-else class="flex flex-wrap gap-2" data-testid="home-providers">
            <li v-for="provider in providers" :key="provider.key">
              <NuxtLink
                :to="`/providers/${provider.key}`"
                class="inline-flex items-center gap-1.5 rounded-full border border-accented bg-default px-3 py-1 text-sm transition-colors hover:border-primary hover:bg-primary/10 hover:text-primary motion-reduce:transition-none"
              >
                <span aria-hidden="true">{{ provider.flag }}</span>
                {{ provider.name }}
              </NuxtLink>
            </li>
          </ul>
          <p class="mt-4 text-sm text-muted">
            {{ t('home.dataProvidersDesc') }}
          </p>
          <p class="mt-1 flex flex-wrap gap-x-5 gap-y-1 text-sm">
            <NuxtLink to="/glossary" class="text-primary underline hover:no-underline">
              {{ t('home.glossaryHint') }}
            </NuxtLink>
            <NuxtLink to="/providers" class="text-primary underline hover:no-underline">
              {{ t('home.providersLink') }}
            </NuxtLink>
          </p>
        </UCard>

        <div class="grid grid-cols-1 gap-x-10 gap-y-8 sm:grid-cols-2 lg:grid-cols-3">
          <div v-for="kind in dataKinds" :key="kind.title" class="flex items-start gap-4">
            <span class="grid size-11 shrink-0 place-items-center rounded-xl bg-primary/10 text-primary" aria-hidden="true">
              <UIcon :name="kind.icon" class="size-5" />
            </span>
            <div>
              <h3 class="font-semibold text-highlighted">
                {{ kind.title }}
              </h3>
              <p class="mt-1 text-sm text-muted">
                {{ kind.description }}
              </p>
            </div>
          </div>
        </div>

        <!-- A subsection of the data block rather than a section of its own: it is still about the
             data, and as a peer heading over two cards it read as a stub after the block above. -->
        <h3 class="mb-4 mt-14 text-xl font-bold text-highlighted">
          {{ t('home.featuresTitle') }}
        </h3>
        <div class="grid grid-cols-1 gap-5 md:grid-cols-2">
          <!-- No hover lift here: these cards are text, not links. On the page only the task cards
               above are clickable, so they are the only ones that answer the pointer. -->
          <UCard v-for="feature in features" :key="feature.title" variant="subtle">
            <div class="flex items-start gap-4">
              <span class="grid size-11 shrink-0 place-items-center rounded-xl bg-sun text-ink-950" aria-hidden="true">
                <UIcon :name="feature.icon" class="size-5" />
              </span>
              <div>
                <h4 class="font-semibold text-highlighted">
                  {{ feature.title }}
                </h4>
                <p class="mt-1 text-sm text-muted">
                  {{ feature.description }}
                </p>
              </div>
            </div>
          </UCard>
        </div>
      </UContainer>
    </section>

    <!-- Values: an unmistakable stance for inclusion and against fascism, and who backs the work. -->
    <section class="pb-(--app-space-section)">
      <UContainer class="max-w-(--app-width-wide) space-y-6">
        <div class="rounded-3xl border border-default bg-muted/60 p-6 text-center sm:p-10">
          <h2 class="mb-6 text-xl font-bold text-highlighted sm:text-2xl">
            {{ t('values.title') }}
          </h2>
          <div class="grid gap-3 text-start sm:grid-cols-2 lg:grid-cols-4">
            <p v-for="value in values" :key="value.key" class="flex items-center gap-3 rounded-2xl bg-default px-4 py-3 text-base font-medium ring ring-default">
              <span class="text-xl leading-none" aria-hidden="true">{{ value.emoji }}</span>
              {{ value.text }}
            </p>
          </div>
        </div>

        <div class="flex flex-col items-center gap-4 text-center">
          <h2 class="text-lg font-bold text-highlighted">
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
              class="inline-flex items-center gap-1.5 rounded-full border border-accented bg-default px-3 py-1 text-sm transition-colors hover:border-primary hover:bg-primary/10 hover:text-primary motion-reduce:transition-none"
            >
              <UIcon :name="supporter.icon" class="size-4 shrink-0" />
              {{ supporter.name }}
            </a>
          </div>
          <!-- The project and the people behind it live on their own page now, so the home page can
               stay about the data. -->
          <UButton
            to="/about"
            variant="link"
            icon="i-lucide-info"
            trailing-icon="i-lucide-arrow-right"
          >
            {{ t('home.aboutLink') }}
          </UButton>
        </div>
      </UContainer>
    </section>
  </div>
</template>
