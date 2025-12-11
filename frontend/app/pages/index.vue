<script setup lang="ts">
const features = [
  { icon: 'i-lucide-database', title: 'Multiple Data Sources', description: 'Access weather data from various meteorological services including DWD, NOAA, and more.' },
  { icon: 'i-lucide-map-pin', title: 'Geospatial Queries', description: 'Find stations by coordinates, name, or within a specific radius.' },
  { icon: 'i-lucide-download', title: 'Flexible Export', description: 'Export data in CSV, JSON, or GeoJSON formats.' },
  { icon: 'i-lucide-line-chart', title: 'Data Analysis', description: 'Interpolation, summarization, and climate stripes visualization.' },
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
          Links
        </h2>
      </template>
      <div class="flex flex-wrap gap-4">
        <UButton
          to="https://github.com/earthobservations/wetterdienst"
          target="_blank"
          variant="outline"
          icon="i-lucide-github"
        >
          GitHub
        </UButton>
        <UButton
          to="https://wetterdienst.readthedocs.io"
          target="_blank"
          variant="outline"
          icon="i-lucide-book-open"
        >
          Documentation
        </UButton>
        <UButton
          to="https://pypi.org/project/wetterdienst"
          target="_blank"
          variant="outline"
          icon="i-lucide-package"
        >
          PyPI
        </UButton>
      </div>
    </UCard>
  </div>
</template>
