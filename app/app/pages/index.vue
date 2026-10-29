<script setup lang="ts">
import type { Station } from '#shared/types/api'
import type { QuestionId } from '~/utils/questions'
import { DateTime } from 'luxon'
import { PLACE_NETWORK, placeOf } from '~/composables/usePlace'
import { lastBoxingDay } from '~/utils/answers'
import { isQuestion, QUESTIONS } from '~/utils/questions'

const { t } = useI18n()
const route = useRoute()
const router = useRouter()

// ------------------------------------------------------------------------------------------- ask the weather
// The page opens on the questions people bring to a weather service, about one place. One question is open at a
// time, and which is the link's (`?ask=summer`), so an answer can be shared; the rain question, the everyday one,
// is open when the link names none. Each is answered from the data (components/AnswerPanel.vue).

const { place, setPlace } = usePlace()
const { questionText } = useQuestions()
const { openPalette } = usePalette()

const question = computed<QuestionId>(() => isQuestion(route.query.ask) ? route.query.ask : 'rain')
const day = computed(() => {
  const asked = route.query.day?.toString()
  return asked && /^\d{4}-\d{2}-\d{2}$/.test(asked) ? asked : lastBoxingDay(DateTime.now())
})

function linkTo(id: QuestionId) {
  const query: Record<string, string> = { ask: id }
  if (route.query.place)
    query.place = String(route.query.place)
  if (id === 'wind' && route.query.day)
    query.day = String(route.query.day)
  return { path: '/', query }
}

function setDay(next: string) {
  void router.replace({ query: { ...route.query, ask: 'wind', day: next } }).catch(() => {})
}

// a question chosen by the reader moves the focus to its answer: on a phone the answer is below the fold, and a
// screen reader is told where it went. Not on the first paint, which is where the reader starts.
const panel = ref<{ focus: () => void } | null>(null)
watch(question, () => nextTick(() => panel.value?.focus()))

// A link that names a place (`?place=02564`, as the palette writes it) asks about that station: it is looked up
// once, by its id, and kept as the reader's place
const placeFailed = ref(false)
watch(() => route.query.place, async (id) => {
  if (typeof id !== 'string' || !/^\w+$/.test(id) || id === place.value.id)
    return
  placeFailed.value = false
  try {
    const response = await $fetch<{ stations: Station[] }>('/api/stations', { query: { ...PLACE_NETWORK, stations: id }, ...RETRY_TRANSIENT })
    const found = response.stations?.[0] ? placeOf(response.stations[0]) : null
    if (found)
      setPlace(found)
    else
      placeFailed.value = true
  }
  catch {
    placeFailed.value = true
  }
}, { immediate: true })

// The tools, for who knows what they need: the same entries as before, as a row under the questions
const tools = computed(() => [
  { to: '/meteogram', icon: 'i-lucide-cloud-sun', tone: 'sun' as const, title: t('home.forecastTitle'), description: t('home.forecastDesc') },
  { to: '/stripes', icon: 'i-lucide-bar-chart-3', tone: 'warmth' as const, title: t('home.stripesTitle'), description: t('home.stripesDesc') },
  { to: '/explorer', icon: 'i-lucide-compass', tone: 'rain' as const, title: t('home.explorerTitle'), description: t('home.explorerDesc') },
  { to: '/history', icon: 'i-lucide-clock', tone: 'wind' as const, title: t('history.title'), description: t('palette.pages.history') },
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
  <div>
    <!-- The questions, and the answer to the one that is open -->
    <section class="ask-hero border-b border-default">
      <div class="app-page app-page--wide">
        <p class="text-sm font-semibold uppercase tracking-wider text-primary">
          {{ t('home.tagline') }}
        </p>
        <h1 class="mt-2 text-4xl sm:text-5xl font-extrabold leading-[1.1] break-words">
          {{ t('ask.title') }}
        </h1>
        <p class="mt-3 text-lg sm:text-xl text-toned max-w-2xl">
          {{ t('ask.lead') }}
        </p>

        <div class="mt-6 flex flex-wrap items-center gap-x-3 gap-y-2">
          <span class="text-sm font-medium text-muted">{{ t('ask.placeLabel') }}</span>
          <button
            type="button"
            class="ask-place inline-flex items-center gap-2 rounded-full border border-default bg-default px-4 py-2 font-semibold text-highlighted hover:border-accented transition-colors max-w-full"
            aria-haspopup="dialog"
            data-testid="place-button"
            @click="openPalette('place')"
          >
            <UIcon name="i-lucide-map-pin" class="size-4 shrink-0 text-primary" />
            <span class="truncate">{{ place.name }}</span>
            <span class="sr-only">– {{ t('ask.placeChange') }}</span>
            <UIcon name="i-lucide-chevron-down" class="size-4 shrink-0 text-muted" />
          </button>
          <span v-if="placeFailed" class="text-sm text-error" role="status">{{ t('ask.placeNotFound') }}</span>
        </div>

        <div class="mt-8 grid gap-6 lg:grid-cols-[minmax(0,5fr)_minmax(0,7fr)] lg:items-start">
          <ul class="grid gap-3" :aria-label="t('ask.questionsLabel')">
            <li v-for="entry in QUESTIONS" :key="entry.id">
              <NuxtLink
                :to="linkTo(entry.id)"
                replace
                class="app-question group flex items-center gap-4 rounded-2xl border bg-default p-4 transition-colors"
                :class="entry.id === question
                  ? 'border-(--ui-color-primary-700) dark:border-(--ui-color-primary-300) ring-1 ring-(--ui-color-primary-700) dark:ring-(--ui-color-primary-300)'
                  : 'border-default hover:border-accented hover:bg-(--app-surface)'"
                :aria-current="entry.id === question ? 'true' : undefined"
                :data-testid="`question-${entry.id}`"
              >
                <AskTile :icon="entry.icon" :tone="entry.tone" />
                <span class="min-w-0 flex-1">
                  <span class="block font-semibold text-highlighted leading-snug break-words">{{ questionText(entry.id, day) }}</span>
                  <span class="block text-sm text-muted">{{ t(`ask.from.${entry.id}`) }}</span>
                </span>
                <UIcon name="i-lucide-chevron-right" class="size-5 shrink-0 text-muted lg:block" :class="entry.id === question ? 'text-primary' : ''" />
              </NuxtLink>
            </li>
          </ul>

          <AnswerPanel ref="panel" :question="question" :day="day" @update:day="setDay" />
        </div>
      </div>
    </section>

    <div class="app-page app-page--wide space-y-14">
      <!-- For who knows what they need: straight to the tools -->
      <section aria-labelledby="tools-title">
        <h2 id="tools-title" class="text-xl sm:text-2xl font-bold">
          {{ t('ask.toolsTitle') }}
        </h2>
        <p class="mt-1 text-muted">
          {{ t('ask.toolsLead') }}
        </p>
        <ul class="mt-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <li v-for="tool in tools" :key="tool.to">
            <NuxtLink :to="tool.to" class="group flex h-full flex-col gap-3 rounded-2xl border border-default bg-default p-4 hover:border-accented hover:bg-(--app-surface) transition-colors">
              <AskTile :icon="tool.icon" :tone="tool.tone" size="sm" />
              <span class="font-semibold text-highlighted">{{ tool.title }}</span>
              <span class="text-sm text-muted flex-1">{{ tool.description }}</span>
            </NuxtLink>
          </li>
        </ul>
      </section>

      <!-- What actually arrives when you press a button above: who publishes it, how much of it
           there is, and in what shapes. -->
      <section aria-labelledby="data-title">
        <h2 id="data-title" class="text-xl sm:text-2xl font-bold">
          {{ t('home.dataTitle') }}
        </h2>
        <p class="mt-1 text-muted">
          {{ t('home.dataIntro') }}
        </p>

        <div class="mt-5 grid grid-cols-2 sm:grid-cols-4 gap-3">
          <div v-for="stat in stats" :key="stat.key" class="rounded-2xl bg-(--app-surface) px-4 py-4">
            <!-- the numbers of providers and parameters are the backend's: its place is held until it has answered (h-8 is the
                 line of text-2xl), and it is a dash where the request failed -->
            <div class="text-2xl font-bold text-(--app-ink)">
              <div v-if="stat.value === null && providersLoading" class="h-8 w-10 rounded-md bg-elevated animate-pulse" aria-hidden="true" />
              <template v-else>
                {{ stat.value ?? '–' }}
              </template>
            </div>
            <div class="text-sm text-muted mt-0.5">
              {{ stat.label }}
            </div>
          </div>
        </div>

        <UCard class="mt-4" data-testid="home-providers-card">
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
                class="inline-flex items-center gap-1.5 rounded-full border border-default px-3 py-1 text-sm hover:border-accented hover:bg-(--app-surface) transition-colors"
              >
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

        <div class="mt-4 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
          <div v-for="kind in dataKinds" :key="kind.title" class="flex items-start gap-3 rounded-2xl border border-default p-4">
            <UIcon :name="kind.icon" class="text-2xl text-primary flex-shrink-0 mt-0.5" />
            <div>
              <h3 class="font-semibold mb-1">
                {{ kind.title }}
              </h3>
              <p class="text-sm text-muted">
                {{ kind.description }}
              </p>
            </div>
          </div>
        </div>

        <!-- A subsection of the data block rather than a section of its own: it is still about the data -->
        <h3 class="mt-8 font-bold">
          {{ t('home.featuresTitle') }}
        </h3>
        <div class="mt-3 grid grid-cols-1 md:grid-cols-2 gap-3">
          <!-- No hover here: these are text, not links -->
          <div v-for="feature in features" :key="feature.title" class="flex items-start gap-3 rounded-2xl border border-default p-4">
            <UIcon :name="feature.icon" class="text-2xl text-primary flex-shrink-0 mt-0.5" />
            <div>
              <h3 class="font-semibold mb-1">
                {{ feature.title }}
              </h3>
              <p class="text-sm text-muted">
                {{ feature.description }}
              </p>
            </div>
          </div>
        </div>
      </section>

      <!-- The developer path: same data, no clicking. -->
      <section aria-labelledby="dev-title" class="rounded-2xl bg-(--app-surface) p-6">
        <h2 id="dev-title" class="text-xl font-bold">
          {{ t('home.devTitle') }}
        </h2>
        <p class="mt-1 text-sm text-muted">
          {{ t('home.devText') }}
        </p>
        <div class="mt-4 flex flex-wrap gap-2">
          <!-- NuxtLink for all three: it renders an external URL as a plain anchor by itself -->
          <NuxtLink
            v-for="entry in devEntries"
            :key="entry.key"
            :to="entry.to"
            external
            target="_blank"
            :title="entry.title"
            class="inline-flex items-center gap-1.5 rounded-full border border-default bg-default px-3 py-1.5 text-sm font-mono hover:border-accented transition-colors"
          >
            <UIcon :name="entry.icon" class="size-4 shrink-0" />
            {{ entry.label }}
          </NuxtLink>
        </div>
      </section>

      <div class="grid gap-4 md:grid-cols-2">
        <!-- Values: an unmistakable stance for inclusion and against fascism. -->
        <section class="rounded-2xl border border-default p-6" aria-labelledby="values-title">
          <h2 id="values-title" class="text-lg font-bold mb-3">
            {{ t('values.title') }}
          </h2>
          <ul class="space-y-2">
            <li v-for="value in values" :key="value.key" class="flex items-center gap-3 font-medium">
              <span aria-hidden="true" class="text-xl">{{ value.emoji }}</span>
              {{ value.text }}
            </li>
          </ul>
        </section>

        <!-- Who backs the work -->
        <section class="rounded-2xl border border-default p-6" aria-labelledby="supported-title">
          <h2 id="supported-title" class="text-lg font-bold mb-3">
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
              class="inline-flex items-center gap-1.5 rounded-full border border-default px-3 py-1.5 text-sm hover:border-accented hover:bg-(--app-surface) transition-colors"
            >
              <UIcon :name="supporter.icon" class="size-4 shrink-0" />
              {{ supporter.name }}
            </a>
          </div>
          <div class="mt-5">
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
        </section>
      </div>
    </div>
  </div>
</template>

<style scoped>
.ask-hero {
  background:
    radial-gradient(60rem 24rem at 100% 0%, color-mix(in oklab, var(--color-rain) 8%, transparent), transparent 70%),
    var(--app-surface);
}
</style>
