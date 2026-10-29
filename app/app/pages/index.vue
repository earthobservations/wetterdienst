<script setup lang="ts">
const { t } = useI18n()
const { span, today } = useTimeAxis()

// The home page is the present on the axis of time (GH-3518): it lays the pages out along the axis, the past to
// the left (on a phone: above), the forecast to the right (below), and says what lies where. Explorer is a
// first-class entry point here, made approachable through its guided Simple mode.
const doors = computed(() => [
  { key: 'stripes', to: '/stripes', icon: 'i-lucide-bar-chart-3', zone: 'then', title: t('home.stripesTitle'), description: t('home.stripesDesc'), span: span('stripes') },
  { key: 'history', to: '/history', icon: 'i-lucide-history', zone: 'then', title: t('history.title'), description: t('home.historyDesc'), span: span('history') },
  { key: 'explorer', to: '/explorer', icon: 'i-lucide-table-2', zone: 'then', title: t('home.explorerTitle'), description: t('home.explorerDesc'), span: span('explorer') },
  { key: 'now', to: null, icon: 'i-lucide-locate-fixed', zone: 'now', title: t('axis.now'), description: t('axis.nowHint'), span: today.value },
  { key: 'forecast', to: '/meteogram', icon: 'i-lucide-cloud-sun', zone: 'next', title: t('home.forecastTitle'), description: t('home.forecastDesc'), span: span('forecast') },
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

const chip = 'inline-flex items-center gap-1.5 rounded-full border border-default bg-default px-3 py-1 text-sm text-toned hover:border-primary-500 hover:text-highlighted'
</script>

<template>
  <div class="app-container home">
    <header class="home-hero">
      <p class="page-head__where page-head--now">
        <span class="page-head__zone">
          <span class="page-head__dot" aria-hidden="true" />
          {{ t('axis.now') }}
        </span>
        <span class="page-head__span">{{ span('now') }}</span>
      </p>
      <h1 class="home-hero__title">
        Wetterdienst
      </h1>
      <p class="home-hero__tagline">
        {{ t('home.tagline') }}
      </p>
      <p class="home-hero__intro">
        {{ t('home.axisIntro') }}
      </p>
    </header>

    <!-- The pages along the axis of time: the past, the present, the forecast. Not a navigation landmark: the
         rail above is the navigation, these are the same places told at more length. -->
    <section class="home-axis" aria-labelledby="home-axis-title">
      <h2 id="home-axis-title" class="home-section-title">
        {{ t('home.axisTitle') }}
      </h2>
      <ol class="home-axis__list">
        <li
          v-for="door in doors"
          :key="door.key"
          class="home-axis__item"
          :class="`home-axis__item--${door.zone}`"
        >
          <span class="home-axis__point" aria-hidden="true" />
          <NuxtLink v-if="door.to" :to="door.to" class="home-door">
            <span class="home-door__zone">{{ t(`axis.${door.zone}`) }}</span>
            <UIcon :name="door.icon" class="home-door__icon" />
            <h3 class="home-door__title">
              {{ door.title }}
            </h3>
            <p class="home-door__description">
              {{ door.description }}
            </p>
            <p class="home-door__span">
              {{ door.span }}
            </p>
            <span class="home-door__go" aria-hidden="true">
              {{ t('common.open') }}
              <UIcon name="i-lucide-arrow-right" class="size-4" />
            </span>
          </NuxtLink>
          <div v-else class="home-door home-door--now">
            <span class="home-door__zone">{{ t(`axis.${door.zone}`) }}</span>
            <UIcon :name="door.icon" class="home-door__icon" />
            <h3 class="home-door__title">
              {{ door.span }}
            </h3>
            <p class="home-door__description">
              {{ door.description }}
            </p>
          </div>
        </li>
      </ol>
    </section>

    <!-- What actually arrives when you go to a place above: who publishes it, how much of it there is, and in
         what shapes. -->
    <section class="home-data" aria-labelledby="home-data-title">
      <h2 id="home-data-title" class="home-section-title">
        {{ t('home.dataTitle') }}
      </h2>
      <p class="home-section-intro">
        {{ t('home.dataIntro') }}
      </p>

      <dl class="home-stats">
        <div v-for="stat in stats" :key="stat.key" class="home-stats__item">
          <dt class="home-stats__label">
            {{ stat.label }}
          </dt>
          <!-- the numbers of providers and parameters are the backend's: its place is held until it has answered,
               and it is a dash where the request failed -->
          <dd class="home-stats__value">
            <span v-if="stat.value === null && providersLoading" class="block h-8 w-12 rounded-md bg-elevated animate-pulse" aria-hidden="true" />
            <template v-else>
              {{ stat.value ?? '–' }}
            </template>
          </dd>
        </div>
      </dl>

      <UCard class="mt-6" data-testid="home-providers-card">
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
        <p class="text-sm text-muted mt-4">
          {{ t('home.dataProvidersDesc') }}
          <NuxtLink to="/glossary" class="text-primary underline hover:no-underline">
            {{ t('home.glossaryHint') }}
          </NuxtLink>{{ ' ' }}
          <NuxtLink to="/providers" class="text-primary underline hover:no-underline">
            {{ t('home.providersLink') }}
          </NuxtLink>
        </p>
      </UCard>

      <ul class="home-kinds">
        <li v-for="kind in dataKinds" :key="kind.title" class="home-kinds__item">
          <UIcon :name="kind.icon" class="home-kinds__icon" />
          <div>
            <h3 class="font-semibold mb-1">
              {{ kind.title }}
            </h3>
            <p class="text-sm text-muted">
              {{ kind.description }}
            </p>
          </div>
        </li>
      </ul>

      <!-- A subsection of the data block rather than a section of its own: it is still about the data. -->
      <h3 class="home-subtitle">
        {{ t('home.featuresTitle') }}
      </h3>
      <ul class="home-kinds home-kinds--two">
        <li v-for="feature in features" :key="feature.title" class="home-kinds__item">
          <UIcon :name="feature.icon" class="home-kinds__icon" />
          <div>
            <h4 class="font-semibold mb-1">
              {{ feature.title }}
            </h4>
            <p class="text-sm text-muted">
              {{ feature.description }}
            </p>
          </div>
        </li>
      </ul>
    </section>

    <!-- The developer path: same data, no clicking. -->
    <section class="home-band" aria-labelledby="home-dev-title">
      <h2 id="home-dev-title" class="home-band__title">
        {{ t('home.devTitle') }}
      </h2>
      <p class="text-sm text-muted mb-3">
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
          :class="chip"
        >
          <UIcon :name="entry.icon" class="size-4 shrink-0" />
          {{ entry.label }}
        </NuxtLink>
      </div>
    </section>

    <!-- Values: an unmistakable stance for inclusion and against fascism, closing the page. -->
    <section class="home-band" aria-labelledby="home-values-title">
      <h2 id="home-values-title" class="home-band__title">
        {{ t('values.title') }}
      </h2>
      <ul class="home-values">
        <li v-for="value in values" :key="value.key" class="flex items-center gap-2 font-medium">
          <span aria-hidden="true">{{ value.emoji }}</span>
          {{ value.text }}
        </li>
      </ul>
    </section>

    <!-- Who backs the work: two statements the project makes about itself. -->
    <section class="home-band" aria-labelledby="home-supported-title">
      <h2 id="home-supported-title" class="home-band__title">
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
    </section>

    <!-- The project and the people behind it live on their own page, so the home page can stay about the data. -->
    <div class="pb-14">
      <UButton
        to="/about"
        variant="link"
        icon="i-lucide-info"
        trailing-icon="i-lucide-arrow-right"
        class="px-0"
      >
        {{ t('home.aboutLink') }}
      </UButton>
    </div>
  </div>
</template>

<style scoped>
.home-hero {
  padding-block: 2.5rem 1.5rem;
  max-width: 52rem;
}
.home-hero__title {
  margin-top: 0.75rem;
  /* one word, which wider letter spacing (WCAG 1.4.12) or a narrow window must be able to break */
  overflow-wrap: anywhere;
  color: var(--ui-text-highlighted);
  font-size: clamp(2.5rem, 1.8rem + 3vw, 4rem);
  font-weight: 700;
  line-height: 1;
  letter-spacing: -0.035em;
}
.home-hero__tagline {
  margin-top: 0.75rem;
  color: var(--ui-text-highlighted);
  font-size: clamp(1.25rem, 1.1rem + 0.6vw, 1.5rem);
  font-weight: 550;
}
.home-hero__intro {
  margin-top: 0.75rem;
  max-width: 60ch;
  color: var(--ui-text-muted);
  font-size: 1.0625rem;
}

.home-section-title {
  color: var(--ui-text-highlighted);
  font-size: 1.375rem;
  font-weight: 700;
}
.home-section-intro {
  margin-top: 0.25rem;
  color: var(--ui-text-muted);
}
.home-subtitle {
  margin: 2rem 0 0.75rem;
  font-size: 1.0625rem;
  font-weight: 700;
}

/* the axis: on a phone a line down the left with the places on it, from the oldest; on a wide screen the places
   side by side with the line under them, as the rail draws it */
.home-axis {
  padding-block: 1rem 2.5rem;
}
.home-axis__list {
  position: relative;
  display: grid;
  gap: 0.75rem;
  margin-top: 1rem;
  padding-left: 1.5rem;
}
.home-axis__list::before {
  content: "";
  position: absolute;
  left: 0.4375rem;
  top: 0.5rem;
  bottom: 0.5rem;
  width: 2px;
  background: linear-gradient(to bottom, var(--app-then) 0 72%, var(--app-next) 72% 100%);
  opacity: 0.45;
}
.home-axis__item {
  position: relative;
  --zone-ink: var(--app-then);
}
.home-axis__item--now {
  --zone-ink: var(--app-now-ink);
}
.home-axis__item--next {
  --zone-ink: var(--app-next);
}
.home-axis__point {
  position: absolute;
  left: -1.4375rem;
  top: 1.25rem;
  width: 0.875rem;
  height: 0.875rem;
  border-radius: 999px;
  background: var(--ui-bg);
  box-shadow: 0 0 0 2px var(--zone-ink);
}
.home-axis__item--now .home-axis__point {
  background: var(--app-now);
  box-shadow: 0 0 0 2px var(--app-now-ring);
}
@media (min-width: 1024px) {
  .home-axis__list {
    grid-template-columns: 1fr 1fr 1fr 0.9fr 1.1fr;
    padding-left: 0;
    padding-bottom: 1.75rem;
  }
  .home-axis__list::before {
    left: 0;
    right: 0;
    top: auto;
    bottom: 0.4375rem;
    width: auto;
    height: 2px;
    background: linear-gradient(to right, var(--app-then) 0 68%, var(--app-next) 68% 100%);
  }
  .home-axis__item {
    display: flex;
  }
  .home-axis__point {
    left: 50%;
    top: auto;
    bottom: -1.75rem;
    transform: translateX(-50%);
  }
}

.home-door {
  position: relative;
  min-width: 0;
  overflow-wrap: break-word;
  display: flex;
  flex-direction: column;
  gap: 0.375rem;
  width: 100%;
  padding: 1rem 1.125rem 1.125rem;
  border: 1px solid var(--ui-border);
  border-top: 3px solid var(--zone-ink);
  border-radius: 0.75rem;
  background: var(--ui-bg);
  color: var(--ui-text);
}
a.home-door:hover {
  border-color: var(--zone-ink);
  background: var(--ui-bg-muted);
}
@media (prefers-reduced-motion: no-preference) {
  a.home-door:hover {
    transform: translateY(-2px);
  }
}
.home-door--now {
  border-style: dashed;
  border-top-style: solid;
  border-top-color: var(--app-now);
  background: var(--ui-bg-muted);
}
.home-door__zone {
  color: var(--zone-ink);
  font-size: 0.75rem;
  font-weight: 700;
  letter-spacing: 0.09em;
  text-transform: uppercase;
}
.home-door__icon {
  width: 1.5rem;
  height: 1.5rem;
  color: var(--zone-ink);
}
.home-door__title {
  color: var(--ui-text-highlighted);
  font-size: 1.0625rem;
  font-weight: 700;
  line-height: 1.25;
}
.home-door__description {
  flex: 1;
  color: var(--ui-text-muted);
  font-size: 0.875rem;
}
.home-door__span {
  color: var(--ui-text-toned);
  font-size: 0.8125rem;
  font-weight: 600;
}
.home-door__go {
  display: inline-flex;
  align-items: center;
  gap: 0.25rem;
  margin-top: 0.25rem;
  color: var(--ui-text-highlighted);
  font-size: 0.875rem;
  font-weight: 600;
}
a.home-door:hover .home-door__go {
  text-decoration: underline;
}

.home-data {
  padding-block: 1.5rem 2.5rem;
  border-top: 1px solid var(--ui-border);
}
.home-stats {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 1px;
  margin-top: 1.25rem;
  border: 1px solid var(--ui-border);
  border-radius: 0.75rem;
  overflow: hidden;
  background: var(--ui-border);
}
@media (min-width: 768px) {
  .home-stats {
    grid-template-columns: repeat(4, minmax(0, 1fr));
  }
}
.home-stats__item {
  display: flex;
  flex-direction: column-reverse;
  gap: 0.125rem;
  padding: 1rem 1.25rem;
  background: var(--ui-bg);
}
.home-stats__value {
  color: var(--ui-text-highlighted);
  font-size: 1.75rem;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
  letter-spacing: -0.02em;
}
.home-stats__label {
  color: var(--ui-text-muted);
  font-size: 0.875rem;
}

.home-kinds {
  display: grid;
  gap: 1.25rem 2rem;
  margin-top: 1.75rem;
}
@media (min-width: 768px) {
  .home-kinds {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
@media (min-width: 1024px) {
  .home-kinds:not(.home-kinds--two) {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
}
.home-kinds--two {
  margin-top: 0;
}
.home-kinds__item {
  display: flex;
  align-items: flex-start;
  gap: 0.75rem;
}
.home-kinds__icon {
  flex-shrink: 0;
  width: 1.375rem;
  height: 1.375rem;
  margin-top: 0.125rem;
  color: var(--ui-color-primary-500);
}
:global(.dark) .home-kinds__icon {
  color: var(--ui-color-primary-400);
}

.home-band {
  padding-block: 1.5rem;
  border-top: 1px solid var(--ui-border);
}
.home-band__title {
  margin-bottom: 0.5rem;
  color: var(--ui-text-highlighted);
  font-size: 1.125rem;
  font-weight: 700;
}
.home-values {
  display: grid;
  gap: 0.5rem 2rem;
}
@media (min-width: 768px) {
  .home-values {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
</style>
