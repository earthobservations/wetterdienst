<script setup lang="ts">
const { t } = useI18n()

// Primary, consumer-facing tasks, as the four tiles of the logo in its order and colours (app.vue's rail has the
// same): the sun for the forecast, the rain for the explorer's measurements, the wind for a station's history,
// the thermometer for the stripes. Explorer is intentionally a first-class entry point here (not hidden behind an
// "advanced" section) — it is made approachable through the Explorer's guided Simple mode.
const tasks = computed(() => [
  { to: '/meteogram', tile: 'sun', icon: 'i-lucide-sun', title: t('home.forecastTitle'), description: t('home.forecastDesc') },
  { to: '/explorer', tile: 'rain', icon: 'i-lucide-compass', title: t('home.explorerTitle'), description: t('home.explorerDesc') },
  { to: '/history', tile: 'wind', icon: 'i-lucide-history', title: t('nav.history'), description: t('history.subtitle') },
  { to: '/stripes', tile: 'heat', icon: 'i-lucide-thermometer', title: t('home.stripesTitle'), description: t('home.stripesDesc') },
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
  <div class="app-frame pt-8 pb-4 sm:pt-12">
    <!-- The hero: what the site is, and the four things it does as the four tiles of the logo -->
    <section class="grid gap-8 lg:grid-cols-[minmax(0,5fr)_minmax(0,7fr)] lg:items-center mb-16" aria-labelledby="home-tasks">
      <div>
        <h1 class="text-5xl sm:text-6xl font-bold tracking-tight text-highlighted break-words">
          Wetterdienst
        </h1>
        <p class="mt-4 text-xl sm:text-2xl text-toned text-pretty">
          {{ t('home.tagline') }}
        </p>
        <h2 id="home-tasks" class="mt-8 text-lg font-bold text-highlighted">
          {{ t('home.tasksTitle') }}
        </h2>
        <p class="mt-1 text-muted">
          {{ t('home.intro') }}
        </p>
      </div>

      <ul class="grid grid-cols-1 sm:grid-cols-2 gap-3 sm:gap-4">
        <li v-for="task in tasks" :key="task.to" class="flex">
          <NuxtLink :to="task.to" class="home-tile group" :data-tile="task.tile">
            <UIcon :name="task.icon" class="size-8" aria-hidden="true" />
            <h3 class="mt-3 sm:mt-6 text-xl font-bold">
              {{ task.title }}
            </h3>
            <p class="mt-1 text-base flex-1">
              {{ task.description }}
            </p>
            <UIcon name="i-lucide-arrow-right" class="mt-3 sm:mt-4 size-5 transition-transform motion-safe:group-hover:translate-x-1" aria-hidden="true" />
          </NuxtLink>
        </li>
      </ul>
    </section>

    <!-- What actually arrives when you press a tile above: who publishes it, how much of it there is, and in what
         shapes. -->
    <section class="mb-16" aria-labelledby="home-data">
      <h2 id="home-data" class="text-2xl sm:text-3xl font-bold tracking-tight text-highlighted">
        {{ t('home.dataTitle') }}
      </h2>
      <p class="mt-2 text-lg text-muted max-w-3xl">
        {{ t('home.dataIntro') }}
      </p>

      <dl data-testid="home-stats" class="mt-8 grid grid-cols-2 md:grid-cols-4 gap-px overflow-hidden rounded-2xl border border-default bg-(--ui-border)">
        <div v-for="stat in stats" :key="stat.key" class="bg-default p-5 flex flex-col-reverse">
          <dt class="text-sm text-muted mt-1">
            {{ stat.label }}
          </dt>
          <!-- the numbers of providers and parameters are the backend's: its place is held until it has answered
               (h-8 is the line of text-2xl), and it is a dash where the request failed -->
          <dd class="text-2xl sm:text-3xl font-bold tabular-nums text-primary">
            <div v-if="stat.value === null && providersLoading" class="h-8 w-12 rounded-md bg-elevated animate-pulse" aria-hidden="true" />
            <template v-else>
              {{ stat.value ?? '–' }}
            </template>
          </dd>
        </div>
      </dl>

      <UCard class="mt-6" data-testid="home-providers-card">
        <template #header>
          <h3 class="font-bold text-highlighted">
            {{ t('home.dataProvidersTitle') }}
          </h3>
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
              class="inline-flex items-center gap-1.5 rounded-full border border-default bg-muted px-3 py-1 text-sm hover:border-primary hover:text-primary"
            >
              <span aria-hidden="true">{{ provider.flag }}</span>
              {{ provider.name }}
            </NuxtLink>
          </li>
        </ul>
        <p class="text-sm text-muted mt-4">
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

      <!-- the kinds of data, a list rather than a wall of cards: they are text, not links -->
      <ul class="mt-10 grid gap-x-8 gap-y-6 sm:grid-cols-2 lg:grid-cols-3">
        <li v-for="kind in dataKinds" :key="kind.title" class="flex items-start gap-3">
          <span class="inline-grid place-items-center size-10 shrink-0 rounded-xl bg-primary/10 text-primary" aria-hidden="true">
            <UIcon :name="kind.icon" class="size-5" />
          </span>
          <div>
            <h3 class="font-bold text-highlighted">
              {{ kind.title }}
            </h3>
            <p class="mt-0.5 text-sm text-muted">
              {{ kind.description }}
            </p>
          </div>
        </li>
      </ul>
    </section>

    <!-- What to do with the data, and the same data without clicking: the library, the API and the MCP endpoint -->
    <section class="mb-16 grid gap-8 lg:grid-cols-2" aria-labelledby="home-features">
      <div>
        <h2 id="home-features" class="text-xl font-bold text-highlighted">
          {{ t('home.featuresTitle') }}
        </h2>
        <ul class="mt-4 space-y-4">
          <li v-for="feature in features" :key="feature.title" class="flex items-start gap-3">
            <UIcon :name="feature.icon" class="size-5 mt-0.5 shrink-0 text-primary" aria-hidden="true" />
            <div>
              <h3 class="font-bold text-highlighted">
                {{ feature.title }}
              </h3>
              <p class="mt-0.5 text-sm text-muted">
                {{ feature.description }}
              </p>
            </div>
          </li>
        </ul>
      </div>
      <div class="rounded-2xl bg-muted border border-default p-6">
        <h2 class="text-xl font-bold text-highlighted">
          {{ t('home.devTitle') }}
        </h2>
        <p class="mt-2 text-sm text-muted">
          {{ t('home.devText') }}
        </p>
        <div class="mt-4 flex flex-wrap gap-2">
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
            class="inline-flex items-center gap-2 rounded-lg border border-default bg-default px-3 py-2 text-sm font-mono hover:border-primary hover:text-primary"
          >
            <UIcon :name="entry.icon" class="size-4 shrink-0" />
            {{ entry.label }}
          </NuxtLink>
        </div>
      </div>
    </section>

    <!-- What the project stands for, and who backs the work: the navy of the logo, the one band of it on the page -->
    <section class="app-navy rounded-3xl p-6 sm:p-10 mb-10 grid gap-8 lg:grid-cols-[minmax(0,2fr)_minmax(0,1fr)]">
      <div>
        <h2 class="text-2xl font-bold">
          {{ t('values.title') }}
        </h2>
        <ul class="mt-5 grid gap-3 sm:grid-cols-2">
          <li v-for="value in values" :key="value.key" class="flex items-center gap-3 text-base font-medium">
            <span class="text-xl" aria-hidden="true">{{ value.emoji }}</span>
            {{ value.text }}
          </li>
        </ul>
      </div>
      <div>
        <h2 class="text-2xl font-bold">
          {{ t('home.supportedByTitle') }}
        </h2>
        <div class="mt-5 flex flex-wrap gap-2">
          <a
            v-for="supporter in supporters"
            :key="supporter.key"
            :href="supporter.to"
            target="_blank"
            :title="supporter.detail"
            :aria-label="`${supporter.name} — ${supporter.detail}`"
            class="inline-flex items-center gap-2 rounded-full border border-white/40 px-4 py-2 text-sm hover:bg-white/10"
          >
            <UIcon :name="supporter.icon" class="size-4 shrink-0" />
            {{ supporter.name }}
          </a>
        </div>
      </div>
    </section>

    <!-- The project and the people behind it live on their own page, so the home page can stay about the data. -->
    <UButton
      to="/about"
      variant="link"
      icon="i-lucide-info"
      trailing-icon="i-lucide-arrow-right"
      class="-ms-2.5"
    >
      {{ t('home.aboutLink') }}
    </UButton>
  </div>
</template>

<style scoped>
/* A tile of the logo, large: its colour, the logo's ink on it (white on the blue, as the logo has it). The text is
   5.0:1 (coral) to 11.3:1 (yellow) on the fills, white 4.9:1 on the blue. */
.home-tile {
  display: flex;
  flex-direction: column;
  width: 100%;
  padding: 1.25rem 1.5rem;
  border-radius: 1.75rem;
  background: var(--tile);
  color: var(--color-tile-ink);
  transition:
    transform 150ms ease,
    box-shadow 150ms ease;
}
.home-tile[data-tile='sun'] {
  --tile: var(--color-tile-sun);
}
.home-tile[data-tile='rain'] {
  --tile: var(--color-tile-rain);
  color: #fff;
}
.home-tile[data-tile='wind'] {
  --tile: var(--color-tile-wind);
}
.home-tile[data-tile='heat'] {
  --tile: var(--color-tile-heat);
}
@media (min-width: 40rem) {
  .home-tile {
    min-height: 13rem;
    padding: 1.5rem;
  }
}
.home-tile:hover {
  box-shadow: 0 12px 28px -12px rgb(11 26 51 / 0.45);
}
@media (prefers-reduced-motion: no-preference) {
  .home-tile:hover {
    transform: translateY(-2px);
  }
}
@media (forced-colors: active) {
  .home-tile {
    border: 1px solid CanvasText;
  }
}
</style>
