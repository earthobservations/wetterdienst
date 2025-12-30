<script setup lang="ts">
const features = [
  { icon: 'i-lucide-database', title: 'Multiple Data Sources', description: 'Access weather data from various meteorological services including DWD, NOAA, and more.' },
  { icon: 'i-lucide-map-pin', title: 'Geospatial Queries', description: 'Find stations by coordinates, name, or within a specific radius.' },
  { icon: 'i-lucide-download', title: 'Flexible Export', description: 'Export data in CSV, JSON, or GeoJSON formats.' },
  { icon: 'i-lucide-line-chart', title: 'Data Analysis', description: 'Interpolation, summarization, and climate stripes visualization.' },
]

const authors = [
  { name: 'Benjamin Gutzmann', email: 'benjamin@eobs.org', githubUsername: 'gutzbenj', githubAvatarId: '29654631' },
  // TODO: add more authors here if they want to be displayed
  // { name: 'Andreas Motl', email: 'andreas.motl@panodata.org', githubUsername: 'amotl', githubAvatarId: '453543' },
]
</script>

<template>
  <div class="max-w-4xl mx-auto py-8 px-4">
    <div class="text-center mb-12">
      <h1 class="text-4xl font-bold mb-4">
        Wetterdienst
      </h1>
      <p class="text-xl text-gray-600 dark:text-gray-400 mb-2">
        Open weather data for humans
      </p>
      <p class="text-gray-500 dark:text-gray-500">
        Access to weather data in Python like a warm summer breeze
      </p>
    </div>

    <UCard class="mb-8">
      <template #header>
        <h2 class="text-lg font-semibold">
          About
        </h2>
      </template>
      <p class="text-gray-600 dark:text-gray-400 mb-4">
        Wetterdienst is a Python library that provides easy access to weather and climate data from
        multiple meteorological services. It offers a unified interface for retrieving historical
        and current weather observations from environmental agencies worldwide, with a particular
        focus on the German Weather Service (Deutscher Wetterdienst, DWD).
      </p>
      <p class="text-gray-600 dark:text-gray-400">
        This frontend application allows you to explore weather data interactively. Select a provider,
        network, and parameters to discover available stations and retrieve observation values.
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

    <UCard class="mb-8">
      <template #header>
        <h2 class="text-lg font-semibold">
          Getting Started
        </h2>
      </template>
      <ol class="list-decimal list-inside space-y-2 text-gray-600 dark:text-gray-400">
        <li>Select a <strong>Provider</strong> (e.g., DWD for German Weather Service)</li>
        <li>Choose a <strong>Network</strong> (e.g., observation for historical data)</li>
        <li>Pick a <strong>Resolution</strong> and <strong>Dataset</strong></li>
        <li>Select the <strong>Parameters</strong> you want to retrieve</li>
        <li>Browse and select <strong>Stations</strong> from the map or list</li>
        <li>View and download the <strong>Values</strong></li>
      </ol>
    </UCard>

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
