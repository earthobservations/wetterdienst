<script setup lang="ts">
const features = [
  { icon: 'i-lucide-database', title: 'Multiple Data Sources', description: 'Access weather data from various meteorological services including DWD, NOAA, and more.' },
  { icon: 'i-lucide-map-pin', title: 'Geospatial Queries', description: 'Find stations by coordinates, name, or within a specific radius.' },
  { icon: 'i-lucide-download', title: 'Flexible Export', description: 'Export data in CSV, JSON, or GeoJSON formats.' },
  { icon: 'i-lucide-line-chart', title: 'Data Analysis', description: 'Interpolation, summarization, and climate stripes visualization.' },
]

const authors = [
  { name: 'Benjamin Gutzmann', email: 'benjamin@eobs.org', githubUsername: 'gutzbenj', githubAvatarId: '29654631' },
  { name: 'Andreas Motl', email: 'andreas.motl@panodata.org', githubUsername: 'amotl', githubAvatarId: '453543' },
]
</script>

<template>
  <div class="max-w-4xl mx-auto py-8 px-4">
    <div class="text-center mb-12">
      <h1 class="text-4xl font-bold mb-4">
        Wetterdienst
      </h1>
      <p class="text-xl text-gray-600 dark:text-gray-400 mb-2">
        Open earth data for humans
      </p>
    </div>

    <UCard class="mb-8">
      <template #header>
        <h2 class="text-lg font-semibold">
          About
        </h2>
      </template>
      <p class="text-gray-600 dark:text-gray-400 mb-4">
        Wetterdienst began as a robust Python package that provides a consistent, well-tested
        interface to meteorological and environmental observation data from multiple providers
        (DWD, NOAA, and others). Over time it evolved into a full ecosystem: a command-line tool,
        a REST API, and this web application. Together these components make Wetterdienst useful
        both as a developer library and as a ready-to-use application for non-programmers.
      </p>
      <p class="text-gray-600 dark:text-gray-400 mb-2">
        Developers use the Python package for scripted downloads, reproducible analyses, and
        integration into data pipelines. The backend performs common data tasks — unit conversion,
        resampling, interpolation, and summarization — so you can focus on analysis, modeling, or
        visualization instead of low-level data wrangling.
      </p>
      <p class="text-gray-600 dark:text-gray-400">
        This web frontend includes the Explorer (a map-driven station browser) as a first-class
        feature. The app provides interactive station discovery, map-based selection, visualizations
        (including climate stripes), and flexible export options — ideal for exploration, teaching,
        rapid quality checks, or producing data for downstream use without writing any code.
      </p>
    </UCard>

    <h2 class="text-xl font-semibold mb-4">
      Features
    </h2>
    <div class="grid grid-cols-1 md:grid-cols-2 gap-4 mb-8">
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

    <UCard>
      <template #header>
        <h2 class="text-lg font-semibold">
          Authors
        </h2>
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
