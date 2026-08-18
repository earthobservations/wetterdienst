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

// The weather services behind the data, one entry per provider in the backend's registry. Kept in
// sync by `tests/test_frontend_i18n.py::test_frontend_home_lists_every_provider`, so a provider
// added upstream fails a test here rather than quietly going unmentioned. Names and flags are
// proper nouns and stay untranslated; the flag is the service's own country, and NOAA's GHCN is
// worldwide despite the US flag, which `home.dataProvidersDesc` says.
const providers = [
  { key: 'aemet', name: 'AEMET', flag: '🇪🇸' },
  { key: 'chmi', name: 'CHMI', flag: '🇨🇿' },
  { key: 'dmi', name: 'DMI', flag: '🇩🇰' },
  { key: 'dwd', name: 'DWD', flag: '🇩🇪' },
  { key: 'ea', name: 'EA', flag: '🇬🇧' },
  { key: 'eaufrance', name: 'Eaufrance', flag: '🇫🇷' },
  { key: 'eccc', name: 'ECCC', flag: '🇨🇦' },
  { key: 'fmi', name: 'FMI', flag: '🇫🇮' },
  { key: 'geosphere', name: 'GeoSphere', flag: '🇦🇹' },
  { key: 'imgw', name: 'IMGW', flag: '🇵🇱' },
  { key: 'ipma', name: 'IPMA', flag: '🇵🇹' },
  { key: 'knmi', name: 'KNMI', flag: '🇳🇱' },
  { key: 'lhmt', name: 'LHMT', flag: '🇱🇹' },
  { key: 'meteofrance', name: 'Météo-France', flag: '🇫🇷' },
  { key: 'meteoswiss', name: 'MeteoSwiss', flag: '🇨🇭' },
  { key: 'metno', name: 'met.no', flag: '🇳🇴' },
  { key: 'metoffice', name: 'Met Office', flag: '🇬🇧' },
  { key: 'noaa', name: 'NOAA', flag: '🇺🇸' },
  { key: 'nws', name: 'NWS', flag: '🇺🇸' },
  { key: 'rmi', name: 'RMI', flag: '🇧🇪' },
  { key: 'smhi', name: 'SMHI', flag: '🇸🇪' },
  { key: 'wsv', name: 'WSV', flag: '🇩🇪' },
]

// Headline numbers, pinned to the backend by the same test: 22 providers and the 514 canonical
// parameters of `metadata/parameter_table.py`.
const stats = computed(() => [
  { value: String(providers.length), label: t('home.statProviders') },
  { value: '514', label: t('home.statParameters') },
  { value: '1 min – 1 a', label: t('home.statResolutions') },
  { value: '0 €', label: t('home.statPrice') },
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
      <h1 class="text-3xl font-bold mb-4">
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
          <span class="text-sm font-medium text-primary-500 group-hover:underline">
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
      <UCard v-for="stat in stats" :key="stat.label" :ui="{ body: 'text-center py-4' }">
        <div class="text-2xl font-bold text-primary-500">
          {{ stat.value }}
        </div>
        <div class="text-xs text-gray-600 dark:text-gray-400 mt-1">
          {{ stat.label }}
        </div>
      </UCard>
    </div>

    <UCard class="mb-6">
      <template #header>
        <div class="flex items-center gap-2">
          <UIcon name="i-lucide-building-2" class="text-primary-500 shrink-0" />
          <h3 class="font-bold">
            {{ t('home.dataProvidersTitle') }}
          </h3>
        </div>
      </template>
      <div class="flex flex-wrap gap-2">
        <span
          v-for="provider in providers"
          :key="provider.key"
          class="inline-flex items-center gap-1.5 rounded-full border border-gray-200 dark:border-gray-700 px-3 py-1 text-sm"
        >
          <span aria-hidden="true">{{ provider.flag }}</span>
          {{ provider.name }}
        </span>
      </div>
      <p class="text-sm text-gray-500 dark:text-gray-400 mt-4">
        {{ t('home.dataProvidersDesc') }}
      </p>
    </UCard>

    <div class="grid grid-cols-1 md:grid-cols-2 gap-4 mb-12">
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

    <h2 class="text-lg font-bold mb-4">
      {{ t('home.featuresTitle') }}
    </h2>
    <div class="grid grid-cols-1 md:grid-cols-2 gap-4 mb-8">
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

    <!-- Values: an unmistakable stance for inclusion and against fascism, closing the page. -->
    <section class="mb-12 rounded-2xl border border-primary-200 dark:border-primary-900 bg-gradient-to-r from-pink-50 via-purple-50 to-sky-50 dark:from-pink-950/30 dark:via-purple-950/20 dark:to-sky-950/30 p-6 text-center">
      <h2 class="text-lg font-bold mb-3">
        {{ t('home.valuesTitle') }}
      </h2>
      <div class="flex flex-col sm:flex-row items-center justify-center gap-3 sm:gap-8">
        <p class="flex items-center gap-2 text-base font-medium">
          <span aria-hidden="true">🏳️‍🌈</span>
          <span aria-hidden="true">🏳️‍⚧️</span>
          {{ t('home.lgbtq') }}
        </p>
        <p class="flex items-center gap-2 text-base font-medium">
          <span aria-hidden="true">✊</span>
          {{ t('home.antifascist') }}
        </p>
        <!-- the one stance this project backs up by existing: it serves the measurements -->
        <p class="flex items-center gap-2 text-base font-medium">
          <span aria-hidden="true">🌡️</span>
          {{ t('home.climate') }}
        </p>
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
