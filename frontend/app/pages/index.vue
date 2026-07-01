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

const features = computed(() => [
  { icon: 'i-lucide-database', title: t('home.feature1Title'), description: t('home.feature1Desc') },
  { icon: 'i-lucide-map-pin', title: t('home.feature2Title'), description: t('home.feature2Desc') },
  { icon: 'i-lucide-download', title: t('home.feature3Title'), description: t('home.feature3Desc') },
  { icon: 'i-lucide-line-chart', title: t('home.feature4Title'), description: t('home.feature4Desc') },
])

const authors = [
  { name: 'Benjamin Gutzmann', email: 'benjamin@eobs.org', githubUsername: 'gutzbenj', githubAvatarId: '29654631' },
  { name: 'Andreas Motl', email: 'andreas.motl@panodata.org', githubUsername: 'amotl', githubAvatarId: '453543' },
]
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

    <!-- Values: a prominent, unmistakable stance for inclusion and against fascism. -->
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
      </div>
    </section>

    <UCard class="mb-8">
      <template #header>
        <div class="flex items-center gap-2">
          <UIcon name="i-lucide-info" class="text-primary-500 shrink-0" />
          <h2 class="text-lg font-bold">
            {{ t('home.aboutTitle') }}
          </h2>
        </div>
      </template>
      <p class="text-gray-600 dark:text-gray-400 mb-4">
        {{ t('home.aboutText1') }}
      </p>
      <p class="text-gray-600 dark:text-gray-400">
        {{ t('home.aboutText2') }}
      </p>
    </UCard>

    <h2 class="text-lg font-bold mb-4">
      {{ t('home.featuresTitle') }}
    </h2>
    <div class="grid grid-cols-1 md:grid-cols-2 gap-4 mb-8">
      <UCard v-for="feature in features" :key="feature.title" class="transition-all hover:ring-2 hover:ring-primary-400 hover:-translate-y-0.5">
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

    <UCard>
      <template #header>
        <div class="flex items-center gap-2">
          <UIcon name="i-lucide-users" class="text-primary-500 shrink-0" />
          <h2 class="text-lg font-bold">
            {{ t('home.authorsTitle') }}
          </h2>
        </div>
      </template>
      <div class="flex flex-wrap gap-8 justify-center">
        <div
          v-for="author in authors"
          :key="author.githubUsername"
          class="flex flex-col items-center gap-2"
        >
          <a
            :href="`https://github.com/${author.githubUsername}`"
            target="_blank"
            class="group flex flex-col items-center gap-2"
          >
            <img
              :src="`https://avatars.githubusercontent.com/u/${author.githubAvatarId}`"
              :alt="author.name"
              class="w-16 h-16 rounded-full ring-2 ring-gray-200 dark:ring-gray-700 group-hover:ring-primary-500 transition-all"
            >
            <span class="text-sm font-medium text-gray-700 dark:text-gray-300 group-hover:text-primary-500 transition-colors">
              {{ author.name }}
            </span>
          </a>
          <a
            :href="`mailto:${author.email}`"
            class="text-xs text-gray-500 dark:text-gray-500 hover:text-primary-500 transition-colors"
          >
            {{ author.email }}
          </a>
        </div>
      </div>
    </UCard>
  </div>
</template>
