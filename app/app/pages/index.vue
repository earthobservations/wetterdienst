<script setup lang="ts">
import { TOOLS } from '~/utils/sections'

const { t } = useI18n()

// The four tools, as the logo's four tiles (app/utils/sections.ts): the first thing the home page offers, beside
// the sentence that says what the site is. Explorer is a first-class entry point here (not hidden behind an
// "advanced" section): it is made approachable through the Explorer's guided Simple mode.
const TITLES: Record<string, string> = {
  forecast: 'home.forecastTitle',
  explorer: 'home.explorerTitle',
  stripes: 'home.stripesTitle',
  history: 'history.title',
}
const tasks = computed(() => TOOLS.map(tool => ({
  key: tool.key,
  to: tool.to,
  tile: tool.tile,
  icon: tool.icon,
  title: t(TITLES[tool.key]!),
  description: t(tool.description!),
})))

// What you can do with the data once you have it. Two cards rather than four: "multiple data
// sources" and "geospatial queries" said what the services card and the Explorer card above now
// say better, and a home page that repeats itself reads as padding.
const features = computed(() => [
  { icon: 'i-ph-download-simple', title: t('home.featureExportTitle'), description: t('home.featureExportDesc') },
  { icon: 'i-ph-chart-line', title: t('home.featureAnalysisTitle'), description: t('home.featureAnalysisDesc') },
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
// API the app itself runs on, and the MCP endpoint. Home linked to four routes before this and
// none of them said the data was reachable programmatically at all.
const devEntries = computed(() => [
  { key: 'pypi', label: 'pip install wetterdienst', icon: 'i-simple-icons-python', to: 'https://pypi.org/project/wetterdienst/', title: undefined },
  // this instance's own endpoints rather than the page that describes them: /docs is the backend's
  // Swagger UI, proxied onto this origin, and /mcp/v1 is the endpoint itself. Both are served by
  // nitro rather than by the Vue router, so they need a full navigation, not a client-side one.
  { key: 'api', label: 'REST API', icon: 'i-ph-code', to: '/docs', title: undefined },
  { key: 'mcp', label: 'MCP', icon: 'i-ph-robot', to: '/mcp/v1', title: t('home.devMcpHint') },
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
  { icon: 'i-ph-thermometer', title: t('home.kindObservationsTitle'), description: t('home.kindObservationsDesc') },
  { icon: 'i-ph-cloud-sun', title: t('home.kindForecastsTitle'), description: t('home.kindForecastsDesc') },
  { icon: 'i-ph-waves', title: t('home.kindHydrologyTitle'), description: t('home.kindHydrologyDesc') },
  { icon: 'i-ph-broadcast', title: t('home.kindRadarTitle'), description: t('home.kindRadarDesc') },
  { icon: 'i-ph-warning', title: t('home.kindAlertsTitle'), description: t('home.kindAlertsDesc') },
  { icon: 'i-ph-car-profile', title: t('home.kindRoadTitle'), description: t('home.kindRoadDesc') },
])
</script>

<template>
  <div class="frame home">
    <!-- What the site is, and the four things to do with it: the logo's four tiles -->
    <section class="home-hero" aria-labelledby="home-title">
      <div class="home-intro">
        <h1 id="home-title" class="home-title">
          Wetterdienst
        </h1>
        <p class="home-tagline">
          {{ t('home.tagline') }}
        </p>
        <p class="home-lede">
          {{ t('home.dataIntro') }}
        </p>
        <!-- Headline numbers: the providers and the parameters are the backend's counts (`GET /api/providers`,
             the `metadata.counts`), so neither is written out here to drift from the library -->
        <dl class="home-stats">
          <div v-for="stat in stats" :key="stat.key" class="home-stat">
            <dt class="text-sm text-muted">
              {{ stat.label }}
            </dt>
            <!-- the numbers of providers and parameters are the backend's: its place is held until it has answered,
                 and it is a dash where the request failed -->
            <dd class="stat-value">
              <span v-if="stat.value === null && providersLoading" class="inline-block h-8 w-12 rounded-md bg-elevated animate-pulse align-middle" aria-hidden="true" />
              <template v-else>
                {{ stat.value ?? '–' }}
              </template>
            </dd>
          </div>
        </dl>
      </div>

      <div class="home-tasks">
        <h2 class="sr-only">
          {{ t('home.tasksTitle') }}
        </h2>
        <ul class="grid grid-cols-1 gap-3 sm:grid-cols-2 sm:gap-4">
          <li v-for="task in tasks" :key="task.key">
            <NuxtLink :to="task.to" class="tool-card group">
              <ToolTile :tile="task.tile" :icon="task.icon" size="3rem" />
              <span class="tool-card-title">
                {{ task.title }}
                <UIcon name="i-ph-arrow-right" class="size-5 shrink-0 transition-transform group-hover:translate-x-0.5" />
              </span>
              <span class="tool-card-text">{{ task.description }}</span>
            </NuxtLink>
          </li>
        </ul>
      </div>
    </section>

    <!-- What actually arrives when you press a button above: who publishes it, and in what shapes -->
    <section class="home-section" aria-labelledby="home-data">
      <div class="home-section-head">
        <h2 id="home-data" class="home-heading">
          {{ t('home.dataTitle') }}
        </h2>
        <p class="text-muted">
          {{ t('home.intro') }}
        </p>
      </div>

      <UCard class="mb-6" data-testid="home-providers-card">
        <template #header>
          <h3 class="font-bold">
            {{ t('home.dataProvidersTitle') }}
          </h3>
        </template>
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
          <div v-for="(width, index) in placeholders" :key="index" class="h-[2.125rem] rounded-full bg-elevated animate-pulse" :class="width" aria-hidden="true" />
        </div>
        <p v-else-if="!providers.length" class="text-sm text-muted">
          {{ t('home.providersEmpty') }}
        </p>
        <ul v-else class="flex flex-wrap gap-2" data-testid="home-providers">
          <li v-for="provider in providers" :key="provider.key">
            <NuxtLink :to="`/providers/${provider.key}`" class="chip">
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

      <ul class="grid grid-cols-1 gap-x-8 gap-y-6 sm:grid-cols-2 lg:grid-cols-3">
        <li v-for="kind in dataKinds" :key="kind.title" class="flex items-start gap-3">
          <UIcon :name="kind.icon" class="mt-0.5 size-6 shrink-0 text-primary" />
          <div>
            <h3 class="font-semibold">
              {{ kind.title }}
            </h3>
            <p class="text-sm text-muted">
              {{ kind.description }}
            </p>
          </div>
        </li>
      </ul>
    </section>

    <!-- What you can do with the data once you have it, and the developer path: the same data, no clicking -->
    <section class="home-section grid gap-6 lg:grid-cols-3" aria-labelledby="home-features">
      <h2 id="home-features" class="sr-only">
        {{ t('home.featuresTitle') }}
      </h2>
      <!-- No hover here: these cards are text, not links. On the page only the tools above answer the pointer. -->
      <UCard v-for="feature in features" :key="feature.title">
        <UIcon :name="feature.icon" class="size-7 text-primary" />
        <h3 class="mt-3 font-bold">
          {{ feature.title }}
        </h3>
        <p class="mt-1 text-sm text-muted">
          {{ feature.description }}
        </p>
      </UCard>
      <UCard class="dev-card">
        <UIcon name="i-ph-terminal-window" class="size-7 text-primary" />
        <h3 class="mt-3 font-bold">
          {{ t('home.devTitle') }}
        </h3>
        <p class="mt-1 text-sm text-muted">
          {{ t('home.devText') }}
        </p>
        <div class="mt-4 flex flex-wrap gap-2">
          <!-- NuxtLink for all three: it renders an external URL as a plain anchor by itself, which is simpler than
               switching the component per entry -- and switching it via `resolveComponent` in the template silently
               rendered two of these as text, not links -->
          <NuxtLink
            v-for="entry in devEntries"
            :key="entry.key"
            :to="entry.to"
            external
            target="_blank"
            :title="entry.title"
            class="chip font-mono text-[0.8125rem]"
          >
            <UIcon :name="entry.icon" class="size-4 shrink-0" />
            {{ entry.label }}
          </NuxtLink>
        </div>
      </UCard>
    </section>

    <!-- The stance and who backs the work: two statements the project makes about itself, side by side, closing the
         page -->
    <section class="home-section grid gap-6 lg:grid-cols-[minmax(0,2fr)_minmax(0,1fr)]">
      <div class="values-band">
        <h2 class="home-heading">
          {{ t('values.title') }}
        </h2>
        <ul class="mt-4 grid gap-3 sm:grid-cols-2">
          <li v-for="value in values" :key="value.key" class="flex items-center gap-3 text-base font-semibold">
            <span class="text-2xl leading-none" aria-hidden="true">{{ value.emoji }}</span>
            {{ value.text }}
          </li>
        </ul>
      </div>
      <div class="rounded-2xl border border-default bg-default p-6">
        <h2 class="home-heading">
          {{ t('home.supportedByTitle') }}
        </h2>
        <div class="mt-4 flex flex-wrap gap-2">
          <a
            v-for="supporter in supporters"
            :key="supporter.key"
            :href="supporter.to"
            target="_blank"
            :title="supporter.detail"
            :aria-label="`${supporter.name} — ${supporter.detail}`"
            class="chip"
          >
            <UIcon :name="supporter.icon" class="size-4 shrink-0" />
            {{ supporter.name }}
          </a>
        </div>
        <!-- The project and the people behind it live on their own page, so the home page can stay about the data -->
        <UButton
          to="/about"
          variant="link"
          icon="i-ph-info"
          trailing-icon="i-ph-arrow-right"
          class="mt-4 -ms-2.5 whitespace-normal text-start"
        >
          {{ t('home.aboutLink') }}
        </UButton>
      </div>
    </section>
  </div>
</template>

<style>
.home-hero {
  display: grid;
  gap: 2.5rem;
  padding-block: 2.5rem 3rem;
}
@media (min-width: 64rem) {
  .home-hero {
    grid-template-columns: minmax(0, 5fr) minmax(0, 6fr);
    gap: 4rem;
    align-items: center;
    padding-block: 4.5rem 5rem;
  }
}
.home-title {
  font-size: clamp(2.75rem, 1.6rem + 4.5vw, 4.75rem);
  line-height: 0.95;
  font-weight: 800;
  letter-spacing: -0.035em;
  overflow-wrap: anywhere;
}
.home-tagline {
  margin-top: 1rem;
  font-size: clamp(1.375rem, 1.1rem + 1vw, 1.875rem);
  line-height: 1.2;
  font-weight: 600;
  color: var(--ui-text-toned);
  text-wrap: balance;
}
.home-lede {
  margin-top: 1rem;
  max-width: 34rem;
  font-size: 1.0625rem;
  color: var(--ui-text-muted);
}
.home-stats {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 1.25rem 2rem;
  margin-top: 2rem;
  padding-top: 1.5rem;
  border-top: 1px solid var(--ui-border);
  max-width: 34rem;
}
.home-stat {
  display: flex;
  flex-direction: column-reverse;
  gap: 0.125rem;
}
.stat-value {
  min-height: 2.25rem;
  font-size: 1.75rem;
  line-height: 1.25;
  font-weight: 800;
  letter-spacing: -0.02em;
  color: var(--ui-text-highlighted);
  font-variant-numeric: tabular-nums;
}
.tool-card {
  display: flex;
  flex-direction: column;
  gap: 0.375rem;
  height: 100%;
  padding: 1.25rem;
  border-radius: 1.25rem;
  border: 1px solid var(--ui-border);
  background: var(--ui-bg);
  box-shadow: 0 1px 2px rgb(11 26 51 / 0.04), 0 8px 24px -16px rgb(11 26 51 / 0.2);
  transition:
    border-color 150ms,
    box-shadow 150ms,
    transform 150ms var(--ease-out-soft);
}
.tool-card > .tile {
  margin-bottom: 0.75rem;
}
.tool-card:hover {
  border-color: var(--ui-border-accented);
  box-shadow: 0 1px 2px rgb(11 26 51 / 0.06), 0 14px 32px -16px rgb(11 26 51 / 0.3);
}
@media (prefers-reduced-motion: no-preference) {
  .tool-card:hover {
    transform: translateY(-2px);
  }
}
.dark .tool-card {
  box-shadow: none;
}
.tool-card-title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem;
  font-size: 1.125rem;
  font-weight: 700;
  color: var(--ui-text-highlighted);
}
.tool-card-text {
  font-size: 0.9375rem;
  line-height: 1.5;
  color: var(--ui-text-muted);
}
.home-section {
  padding-block: 2.5rem;
  border-top: 1px solid var(--ui-border);
}
.home-section:last-child {
  padding-bottom: 4rem;
}
.home-section-head {
  margin-bottom: 1.5rem;
}
.home-heading {
  font-size: 1.5rem;
  line-height: 1.25;
  font-weight: 800;
}
/* A link that is a short label (a provider, a supporter, a way in for developers) */
.chip {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  min-height: 2.125rem;
  padding: 0.25rem 0.875rem;
  border-radius: 999px;
  border: 1px solid var(--ui-border);
  background: var(--ui-bg);
  font-size: 0.875rem;
  font-weight: 600;
  color: var(--ui-text-toned);
  transition:
    border-color 150ms,
    color 150ms;
}
.chip:hover {
  border-color: var(--ui-primary);
  color: var(--ui-text-highlighted);
}
/* The stance, on the logo's navy: the one dark block of the light page */
.values-band {
  padding: 1.5rem;
  border-radius: 1rem;
  background: var(--color-tile-navy);
  color: #ffffff;
}
.values-band .home-heading {
  color: #ffffff;
}
.dark .values-band {
  background: #1a2d4d;
}
</style>
